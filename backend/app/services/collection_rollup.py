import re
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict
from sqlmodel import Session, select, func
from app.models.entities import Collection, AssetUnit

WORK_CODE_REGEX = re.compile(r'([A-Z]{2,4}\d{5,8})', re.IGNORECASE)
DISC_REGEX = re.compile(r'^(disc|cd|vol|part|volume)[\s\._-]*\d+$', re.IGNORECASE)

ACCESSORY_PATTERNS = [
    r'^(img|image|images|photo|photos|pic|pics|picture|pictures|illust|jacket)$',
    r'^(イラスト|画像|图片|插图|插圖|插画|插画变体|插绘|cg|cgs|bk|scans|booklet|封面.*|壁纸|壁紙)$',
    r'^\d+[\._-]?(イラスト|插画|插图|画像|图片|cg|封面.*)$',
    r'^(mp3|wav|flac|mkv|01_mp3|01_wav|02_mp3|01通常版|通常版|本篇.*|本編.*|正篇.*|SE.*|無SE|有SE|効果音.*|音频数据.*|.*リバーブ.*ver|.*エコー.*ver|リバーブなし.*|リバーブあり.*|排除)$',
    r'^(特典|おまけ|購入.*特典|购买特典|购入特典|附赠|附屬.*|附属.*|サンプル|样本|体験版|台本.*|字幕.*)$',
]
COMBINED_ACCESSORY_REGEX = re.compile('|'.join(ACCESSORY_PATTERNS), re.IGNORECASE)

def is_accessory_collection_name(name: str) -> bool:
    if not name:
        return False
    return bool(COMBINED_ACCESSORY_REGEX.search(name.strip()))

def find_canonical_work_collection(col: Collection, col_map: Dict[int, Collection]) -> Optional[Collection]:
    """
    检查该集合是否属于某个独立作品（如带标准编号的合集或多碟合集）的内部子目录。
    若其祖先链中存在作品根目录，则返回该作品根目录 Collection。
    """
    curr = col
    visited = set()
    chain = []
    while curr and curr.id not in visited:
        visited.add(curr.id)
        chain.append(curr)
        if curr.parent_id and curr.parent_id in col_map:
            curr = col_map[curr.parent_id]
        else:
            break

    # 1. 在从 col 到根的祖先链中，从最高祖先往下查找第一个拥有标准作品编号的目录（即作品根目录）
    for ancestor in reversed(chain):
        anc_str = f"{ancestor.name or ''} {ancestor.folder_path or ''}"
        if WORK_CODE_REGEX.search(anc_str):
            if ancestor.id != col.id:
                return ancestor
            else:
                # 自身就是最高作品根目录
                return None

    # 2. 对于无编号目录，检查是否为 Disc 1 / CD 2 或附件目录，若是且存在直接父级，则归拢到父级
    if col.parent_id and (DISC_REGEX.search(col.name or '') or is_accessory_collection_name(col.name or '')):
        parent = col_map.get(col.parent_id)
        if parent:
            return parent

    return None

def rollup_all_split_works(session: Session) -> Dict[str, Any]:
    """
    自愈并归拢所有属于作品附属目录、碟片分流、插画特典或分支子目录的资产，
    将其安全合并收纳至对应的真实作品合集（Canonical Work Collection）中，
    彻底消除单个作品被碎裂拆分成多张卡片的问题。
    """
    cols = session.exec(select(Collection)).all()
    col_map = {c.id: c for c in cols}

    to_rollup = {}
    for c in cols:
        target = find_canonical_work_collection(c, col_map)
        if target and target.id != c.id:
            to_rollup[c.id] = (c, target)

    rolled_up_cols = 0
    consolidated_units = 0
    affected_works = set()

    for cid, (sub, parent) in to_rollup.items():
        units = session.exec(select(AssetUnit).where(AssetUnit.collection_id == sub.id)).all()
        for u in units:
            u.collection_id = parent.id
            attrs = dict(u.dynamic_attributes or {})
            attrs["is_subfolder_item"] = True
            attrs["subfolder_name"] = sub.name
            
            # 计算相对于作品根目录的相对子路径
            if sub.folder_path and parent.folder_path and sub.folder_path.startswith(parent.folder_path):
                rel_sub = sub.folder_path[len(parent.folder_path):].lstrip('/\\')
                attrs["sub_folder"] = rel_sub

            if is_accessory_collection_name(sub.name):
                attrs["is_accessory"] = True
                if u.unit_type == "image":
                    attrs["role"] = "illustration"
                elif "特典" in sub.name or "おまけ" in sub.name:
                    attrs["role"] = "bonus"

            u.dynamic_attributes = attrs
            session.add(u)
            consolidated_units += 1

        # 若子集合自身还有下级集合，将其重新指向 parent
        child_cols = session.exec(select(Collection).where(Collection.parent_id == sub.id)).all()
        for child in child_cols:
            child.parent_id = parent.id
            session.add(child)

        session.flush()

        # 安全删除已掏空的子集合记录
        session.delete(sub)
        session.flush()
        rolled_up_cols += 1
        affected_works.add(parent.id)

    # 补齐作品根合集的封面关联
    for pid in affected_works:
        p = session.get(Collection, pid)
        if p and not p.cover_asset_id:
            img_u = session.exec(
                select(AssetUnit)
                .where(AssetUnit.collection_id == p.id, AssetUnit.unit_type == "image")
            ).first()
            if img_u:
                p.cover_asset_id = img_u.id
            else:
                first_u = session.exec(
                    select(AssetUnit)
                    .where(AssetUnit.collection_id == p.id)
                ).first()
                if first_u:
                    p.cover_asset_id = first_u.id
            session.add(p)

    session.commit()
    return {
        "rolled_up_collections": rolled_up_cols,
        "merged_collections_count": rolled_up_cols,
        "consolidated_units": consolidated_units,
        "affected_works": len(affected_works)
    }

def rollup_all_accessory_collections(session: Session) -> Dict[str, Any]:
    return rollup_all_split_works(session)

rollup_split_work_collections = rollup_all_split_works


SUB_ALBUM_KEYWORDS = [
    '限定', '专栏', '定制', '第一季', '第二季', 'Special', 'Season', 'Bonus'
]

def is_container_or_author_bucket(col: Collection, unit_count: int) -> bool:
    """判断一个集合是否为作者目录或批次归档大目录（而非单个具体作品）"""
    desc = col.description or ""
    return "容器" in desc or "归档大目录" in desc


def is_eligible_series_container(col: Collection, unit_count: int) -> bool:
    """判断集合是否允许从中提取并聚类多篇目子系列作品"""
    if not col.name:
        return False
    if "旗下独立系列作品" in (col.description or ""):
        return False
    if WORK_CODE_REGEX.search(f"{col.name} {col.folder_path or ''}"):
        return False
    if re.search(r'^(img|image|特典|附赠|cg|bk|scans)', col.name, re.I):
        return False
    return unit_count >= 2


def clean_series_name(name: str) -> str:
    """清理提取出的系列名称中的 CV 标注、作者信息、多余标点与后缀"""
    name = re.sub(
        r'[-_ ]*(?:--|-)?(?:CV|cv|演职员|声优|作者|社团|By|by)[:：\s]*\S+.*$',
        '',
        name,
        flags=re.IGNORECASE
    ).strip()
    name = name.rstrip('（(【[ ·-_—：:.~')
    return name.strip()


def extract_group_key_and_title(clean_title: str) -> Tuple[Optional[str], Optional[str]]:
    """
    智能解析单个标题中的分集特征，返回 (系列分组主键, 推荐系列展示标题)。
    支持带编号、带中文括弧、带汉字回/集/期/日/天、带上下部、带减号序列的多样化剧集命名。
    """
    # 模式 1: 带小数点的编号前缀，例如 A-06.1, A-06.7
    m_code_dec = re.match(r'^([A-Za-z]+[-_ ]*\d+)[\._](\d+)[-_ ]*(.*)', clean_title)
    if m_code_dec:
        code = m_code_dec.group(1).upper()
        subname = m_code_dec.group(3).strip()
        subname = re.sub(r'第\s*[0-9一二三四五六七八九十\d]+\s*[回集章期夜天日节篇部步话話]', '', subname).strip()
        subname = re.sub(r'[（(【\[]\s*[0-9一二三四五六七八九十\d]+\s*[)）】\]]', '', subname).strip()
        subname = clean_series_name(subname)
        return code, f'{code} {subname}'.strip() if subname else code

    # 模式 2: 字母编号前缀如 N006, S079, S140, N206
    m_code = re.match(r'^([A-Za-z]+[-_ ]*\d{3,4})[-_ ]*(.*)', clean_title)
    if m_code:
        code = m_code.group(1).upper()
        rest = m_code.group(2).strip()
        clean_sub = clean_series_name(rest)
        clean_sub = re.sub(r'[-_ ]*(?:\d+|第[一二三四五六七八九十\d]+[章节回天集部期]|(?:上|中|下)集?).*$', '', clean_sub).strip()
        clean_sub = clean_series_name(clean_sub)
        return code, f'{code} {clean_sub}'.strip() if clean_sub else code

    # 模式 3: 中文或半角括弧分集，例如 漫步专栏（2）, 专题讲座（上）
    m_bracket = re.search(r'^(.*?)[-_ ]*[（(【\[]\s*([0-9一二三四五六七八九十\d]+|第[0-9一二三四五六七八九十\d]+[回集章期夜天日节篇部步话話]|上|中|下|前|后)\s*[)）】\]](.*)$', clean_title)
    if m_bracket:
        base = clean_series_name(m_bracket.group(1))
        if len(base) >= 2 and not base.isdigit():
            return base, base

    # 模式 4: 第X集/回/章/期/夜/天/日/节/篇/部/步/话，例如 播客系列第3期, 训练营 第1天
    m_num = re.search(r'^(.*?)[-_ ]*第\s*([0-9一二三四五六七八九十\d]+)\s*[回集章期夜天日节篇部步话話](.*)$', clean_title)
    if m_num:
        base = clean_series_name(m_num.group(1))
        if len(base) >= 2 and not base.isdigit():
            return base, base

    # 模式 5: 上/中/下/前/后 (集/篇/部/本/篇目)，例如 科技专题上篇, 纪录片上部
    m_updown = re.search(r'^(.*?)[-_ ]*(?:上|中|下|前|后)(?:[集篇部本])?(?:[-_ ]+(.*)|$)', clean_title)
    if m_updown:
        base = clean_series_name(m_updown.group(1))
        if len(base) >= 2 and not base.isdigit():
            return base, base

    # 模式 6: 短横线编号序列，例如 示例系列-1, 专栏-2 (仅限 1~3 位数字集数，排除网址水印或分辨率后缀)
    m_dash = re.match(r'^(.*?)[-_ ]+([0-9]{1,3})$', clean_title)
    if m_dash:
        base = clean_series_name(m_dash.group(1))
        if (
            len(base) >= 2
            and not base.isdigit()
            and not re.search(r'\.(?:com|net|org|cc|tv|me|xyz)|\b(?:720p|1080p|4k|4000k)\b', base, re.I)
        ):
            return base, base

    return None, None


def group_multipart_works_in_buckets(session: Session) -> Dict[str, Any]:
    """
    智能识别平铺作者目录与容器集合内部的多章节/多篇目系列作品，
    为其创建规范的子系列作品 Collection 并收纳对应的 AssetUnit，
    同时自动重锚父级 Collection 的封面指针，
    彻底解决“系列被错误当成零散个体、或明明标着系列点开却只有单个文件”的问题。
    """
    cols = session.exec(select(Collection)).all()
    col_map = {c.id: c for c in cols}

    # 统计各集合直接关联的 units
    units_by_col = defaultdict(list)
    all_units = session.exec(select(AssetUnit)).all()
    for u in all_units:
        if u.collection_id:
            units_by_col[u.collection_id].append(u)

    created_series_count = 0
    grouped_units_count = 0

    for cid, c in col_map.items():
        c_units = units_by_col.get(cid, [])
        if not is_eligible_series_container(c, len(c_units)):
            continue

        # 尝试聚类
        groups = defaultdict(list)
        for u in c_units:
            clean = re.sub(r'\.(mp3|wav|flac|m4a|mp4|mkv)$', '', u.title or '', flags=re.I).strip()
            gkey, sname = extract_group_key_and_title(clean)
            if gkey:
                g_clean = re.sub(r'\d+$', '', gkey.lower()).strip()
                c_clean = (c.name or '').lower().strip()
                # 若提取出的前缀本身就是父集合名或其简称（例如作者目录内以作者名开头的散曲），不建同名套娃子集合
                if g_clean and len(g_clean) >= 2 and (g_clean == c_clean or g_clean in c_clean):
                    continue
                groups[gkey].append((u, sname or gkey))

        # 对 >= 2 个分集的组创建子系列
        for group_key, ulist in groups.items():
            if len(ulist) < 2:
                continue

            # 若该集合内的全部单元均属于这同一个系列，说明该集合本身就是该系列的独立目录，不重复套娃
            if len(ulist) == len(c_units) and c.parent_id:
                for u, _ in ulist:
                    attrs = dict(u.dynamic_attributes or {})
                    attrs["is_series_episode"] = True
                    attrs["series_name"] = c.name
                    u.dynamic_attributes = attrs
                    session.add(u)
                continue

            # 选择最长且最具有代表性的系列名称
            best_name = max([sname for _, sname in ulist], key=len)
            best_name = clean_series_name(best_name)
            if not best_name or len(best_name) < 2:
                best_name = group_key

            # 检查是否已有同名同 parent 的集合
            existing_sub = session.exec(
                select(Collection).where(Collection.parent_id == c.id, Collection.name == best_name)
            ).first()

            if not existing_sub:
                existing_sub = Collection(
                    name=best_name,
                    folder_path=c.folder_path,
                    parent_id=c.id,
                    description=f"{c.name} 旗下独立系列作品"
                )
                session.add(existing_sub)
                session.flush()
                session.refresh(existing_sub)
                created_series_count += 1

            for u, _ in ulist:
                u.collection_id = existing_sub.id
                attrs = dict(u.dynamic_attributes or {})
                attrs["is_series_episode"] = True
                attrs["series_name"] = best_name
                u.dynamic_attributes = attrs
                session.add(u)
                grouped_units_count += 1

            if not existing_sub.cover_asset_id and ulist:
                existing_sub.cover_asset_id = ulist[0][0].id
                session.add(existing_sub)

    # 全局重锚所有父级集合的 cover_asset_id（防止封面指针悬空或漂移至子集合单元）
    for c in cols:
        if c.cover_asset_id:
            cu = session.get(AssetUnit, c.cover_asset_id)
            if not cu or cu.collection_id != c.id:
                # 优先选用剩余的直接图片单元，其次选用第一个直接音频/媒体单元
                rem_img = session.exec(
                    select(AssetUnit)
                    .where(AssetUnit.collection_id == c.id, AssetUnit.unit_type == "image")
                ).first()
                if rem_img:
                    c.cover_asset_id = rem_img.id
                else:
                    rem_any = session.exec(
                        select(AssetUnit)
                        .where(AssetUnit.collection_id == c.id)
                    ).first()
                    c.cover_asset_id = rem_any.id if rem_any else None
                session.add(c)

    session.commit()
    return {
        "created_series_count": created_series_count,
        "grouped_units_count": grouped_units_count,
    }
