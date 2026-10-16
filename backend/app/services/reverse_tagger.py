"""
MuseFlow (灵眸流) — 通用物理路径逆向打标与多维分类学映射引擎 (Reverse Tagger & Taxonomy Engine)

核心能力：
1. 零磁盘 I/O (PurePath 内存解析)：防止跨挂载点/网络文件系统 RPC 阻塞或死锁。
2. 面向对象通用多维元类 (TagClass) 正交打标：
   - media_kind: 音频、视频、图片、复合媒体 (基于文件 MIME/扩展名及单元主媒体类型)
   - domain: 题材/流派/分类 (基于物理路径多级语义或标准多媒体元数据)
   - creator: 创作者/艺术家/演职员 (基于受保护括号标记 [Artist]、父目录语义或媒体 Cast 元数据)
   - workflow: 整理状态 (待整理、待翻译、已汉化、已归档)
3. 跨元类同名防碰撞：支持同一名称在不同正交元类 (如 creator 与 va) 独立建标。
4. 方案 A 物理落点锚点唯一性保障：同类目继承树内仅保留最具体的子节点为落点锚点。
5. 高性能批量打标：纯内存预加载 + 分块提交，数千单元极速完成。
"""

import logging
import re
from pathlib import PurePath
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import MEDIA_SEARCH_ROOTS
from app.models.entities import AssetFile, AssetUnit, AssetUnitTagLink, LibraryRoot, Tag, TagClass
from app.services.tag_service import TagHierarchyCacheManager, normalize_tag_name
from app.core.user_rules import (
    load_user_rules,
    apply_creator_cleaning,
    apply_domain_cleaning,
    UserRules,
)

logger = logging.getLogger("museflow.reverse_tagger")

# 通用媒体形态路径映射（作为媒体库根锚点跳过）
MEDIA_KIND_MAP = {
    "音频": "音频",
    "音乐": "音频",
    "music": "音频",
    "sound": "音频",
    "audio": "音频",
    "podcast": "音频",
    "podcasts": "音频",
    "播客": "音频",
    "视频": "视频",
    "video": "视频",
    "videos": "视频",
    "movies": "视频",
    "movie": "视频",
    "film": "视频",
    "图片": "图片",
    "相册": "图片",
    "photos": "图片",
    "images": "图片",
    "gallery": "图片",
    "pictures": "图片",
}

# 通用工作流状态映射
WORKFLOW_MAP = {
    "待整理": ("待整理", True),
    "待分类": ("待整理", True),
    "inbox": ("待整理", True),
    "unsorted": ("待整理", True),
    "待翻译": ("待翻译", True),
    "已汉化": ("已汉化", True),
    "已归档": ("已归档", True),
    "已整理": ("已归档", True),
    "archived": ("已归档", True),
}

# 通用文件系统保留路径（非语义目录，打标时跳过）
SYSTEM_PATH_SEGMENTS = {
    "/", "\\", "mnt", "media", "volumes", "home", "root", "data", "users",
    "appdata", "local", "temp", "tmp", "bin", "usr", "var", "etc", "windows",
    "system32", "program files", "recycle.bin", "#recycle", ".thumbnails",
    "lost+found", "cache", "downloads",
}

# 仅提取目录名最前端的标准方括号 [Creator/Studio]（排除【宣传语】与圆括号(CV)）
BRACKET_TOKENS_REGEX = re.compile(r"^\[([^\[\]]{2,30})\]")

# 标准演职员/协作者提取正则 (例如: feat. Artist, CV: Name, Cast: Actor)
ARTIST_CREDIT_REGEX = re.compile(
    r"(?:feat\.|ft\.|CV[:：\s]|cv[:：\s]|Cast[:：\s]|cast[:：\s])\s*([A-Za-z\u4e00-\u9fa5\u3040-\u30ff]{2,25})",
    re.IGNORECASE,
)

# 通用非创作者括号内容排斥规则（防止将编号、章节号、版本号、纯数字、网址或流格式误判为创作者）
NON_CREATOR_BRACKET_PATTERNS = [
    re.compile(r"^[A-Z]{1,5}-?\d{3,10}$", re.IGNORECASE),
    re.compile(r"^\d+(?:[._\-xX×~～]\d+)*$"),
    re.compile(
        r"^(?:第[一二三四五六七八九十百千万零\d]+[章节回集话篇部幕季期天日]"
        r"|(?:Part|Vol|Disc|CD|Track|Ep|Episode|Chapter|Week|Day)\s*\d+"
        r"|宣传|宣传demo|预告|试听|体验版|附赠|附属|花絮"
        r"|全篇|全集|正篇|完整版|无损|高清|高音质|字幕版|中文版|简体中文版|繁体中文版"
        r"|简体字幕版|简体中文字幕版|日文版|日配中字|DL版|通常版|限定版|完全版"
        r"|.*特辑|.*限定)$",
        re.IGNORECASE,
    ),
    re.compile(r"\.(?:com|net|org|io|cc|tv|jp|cn|me|xyz|info)\b", re.IGNORECASE),
    re.compile(
        r"^(?:MP3|WAV|FLAC|MP4|AAC|Voice|SE\b|BGM"
        r"|Binaural|3D|VR|4K|1080P|720P|HDR|Dolby"
        r"|Voiced.*|Fully[\s_]*Voiced|Animated.*|Stream\s*Replay|Script\s*Fill"
        r"|Public|Formerly.*|中文|⚠️.*)$",
        re.IGNORECASE,
    ),
]


def is_valid_creator_candidate(candidate: str, user_rules: Optional[UserRules] = None) -> bool:
    """
    通用创作者候选词合法性守卫：
    排除作品编号、章节序号 (第一章/Part 1)、版本说明 (简体中文版/宣传/附赠)、
    纯数字/分辨率、网址域名以及通用音频格式标记。
    """
    if not candidate:
        return False
    c = candidate.strip()
    if user_rules and c in user_rules.creator_aliases.values():
        return True
    if len(c) < 2 or len(c) > 35:
        return False
    if user_rules:
        if c in user_rules.slang_filter or c in user_rules.ignore_segments:
            return False
        if c in user_rules.domain_mapping or c in user_rules.domain_aliases or c in user_rules.workflow_mapping:
            return False
        for custom_pat in user_rules.non_creator_patterns:
            try:
                if re.search(custom_pat, c, re.IGNORECASE):
                    return False
            except re.error:
                continue
    for pat in NON_CREATOR_BRACKET_PATTERNS:
        if pat.search(c):
            return False
    return True


def get_or_create_tag_fast(
    session: Session,
    tag_by_norm: Dict[str, Tag],
    name: str,
    tag_class_id: int,
    parent_id: Optional[int] = None,
) -> Tag:
    """
    纯内存秒级获取或创建标签（支持跨 TagClass 同名消歧，避免正交元类碰撞）
    """
    clean_name = name.strip()
    _, norm_name = normalize_tag_name(clean_name)
    scoped_key = f"{norm_name}::{tag_class_id}"

    # 1. 优先匹配当前元类专属键
    if scoped_key in tag_by_norm:
        existing = tag_by_norm[scoped_key]
        if parent_id is not None and existing.parent_id is None and existing.id != parent_id:
            existing.parent_id = parent_id
            session.add(existing)
        return existing

    # 2. 检查无后缀 norm_name 是否已存在且属于同一元类
    existing = tag_by_norm.get(norm_name)
    if existing and existing.tag_class_id == tag_class_id:
        tag_by_norm[scoped_key] = existing
        if parent_id is not None and existing.parent_id is None and existing.id != parent_id:
            existing.parent_id = parent_id
            session.add(existing)
        return existing

    # 3. 若 norm_name 已被其他元类占用（例如同时为声优 va 和社团 creator），使用带元类后缀的 normalized_name
    db_norm = scoped_key if existing is not None else norm_name

    new_tag = Tag(
        name=clean_name,
        normalized_name=db_norm,
        tag_class_id=tag_class_id,
        parent_id=parent_id,
    )
    session.add(new_tag)
    session.flush()
    tag_by_norm[scoped_key] = new_tag
    if existing is None:
        tag_by_norm[norm_name] = new_tag
    return new_tag


def assign_tag_fast(
    session: Session,
    existing_links: Set[Tuple[int, int]],
    unit_id: int,
    tag_id: int,
    is_primary_landing: bool = False,
    confidence: float = 1.0,
) -> None:
    """纯内存秒级查重与绑定标签关联"""
    if (unit_id, tag_id) in existing_links:
        return
    link = AssetUnitTagLink(
        unit_id=unit_id,
        tag_id=tag_id,
        is_primary_landing=is_primary_landing,
        confidence=confidence,
    )
    session.add(link)
    existing_links.add((unit_id, tag_id))


def ensure_tag_taxonomy_hierarchy(
    session: Session,
    tag_by_norm: Dict[str, Tag],
    class_map: Dict[str, int],
) -> None:
    """初始化并对齐系统基础通用标签体系"""
    mk_id = class_map.get("media_kind")
    if mk_id:
        get_or_create_tag_fast(session, tag_by_norm, "音频", mk_id)
        get_or_create_tag_fast(session, tag_by_norm, "视频", mk_id)
        get_or_create_tag_fast(session, tag_by_norm, "图片", mk_id)
        get_or_create_tag_fast(session, tag_by_norm, "复合媒体", mk_id)

    wf_id = class_map.get("workflow")
    if wf_id:
        get_or_create_tag_fast(session, tag_by_norm, "待整理", wf_id)
        get_or_create_tag_fast(session, tag_by_norm, "已归档", wf_id)

    session.flush()


def cleanup_dirty_tags(
    session: Session,
    tag_by_norm: Dict[str, Tag],
    class_map: Dict[str, int],
    user_rules: Optional[UserRules] = None,
) -> int:
    """清理历史残留的非规范路径杂质标签并维护体系约束（支持外部用户规则驱动）"""
    if user_rules is None:
        user_rules = load_user_rules()

    all_tags = session.exec(select(Tag)).all()
    cleaned = 0
    creator_class_id = class_map.get("creator")

    for t in all_tags:
        t_name = t.name.strip()
        t_name_lower = t_name.lower()
        is_drive_letter = bool(re.match(r"^[a-zA-Z]:?$", t_name))
        is_pure_punctuation = bool(re.match(r"^[\W_]+$", t_name))
        is_system_segment = t_name_lower in SYSTEM_PATH_SEGMENTS
        is_user_slang = t_name in user_rules.slang_filter or t_name in user_rules.ignore_segments

        # 用户自定义称号后缀剥离与别名规约
        if creator_class_id is not None and t.tag_class_id == creator_class_id:
            if not is_valid_creator_candidate(t_name, user_rules):
                session.execute(text("DELETE FROM asset_unit_tag_link WHERE tag_id = :tid"), {"tid": t.id})
                session.execute(text("DELETE FROM tag_alias WHERE tag_id = :tid"), {"tid": t.id})
                session.execute(text("DELETE FROM tag WHERE id = :tid"), {"tid": t.id})
                cleaned += 1
                tag_by_norm.pop(t.normalized_name, None)
                tag_by_norm.pop(f"{t.normalized_name}::{t.tag_class_id}", None)
                continue

            cleaned_creator = apply_creator_cleaning(t_name, user_rules)
            if cleaned_creator and cleaned_creator != t_name:
                t_clean = get_or_create_tag_fast(session, tag_by_norm, cleaned_creator, creator_class_id)
                session.execute(
                    text("""
                        DELETE FROM asset_unit_tag_link
                        WHERE tag_id = :old_id
                          AND unit_id IN (SELECT unit_id FROM asset_unit_tag_link WHERE tag_id = :clean_id)
                    """),
                    {"clean_id": t_clean.id, "old_id": t.id},
                )
                session.execute(
                    text("UPDATE asset_unit_tag_link SET tag_id = :clean_id WHERE tag_id = :old_id"),
                    {"clean_id": t_clean.id, "old_id": t.id},
                )
                session.execute(text("DELETE FROM tag_alias WHERE tag_id = :tid"), {"tid": t.id})
                session.execute(text("DELETE FROM tag WHERE id = :tid"), {"tid": t.id})
                cleaned += 1
                tag_by_norm.pop(t.normalized_name, None)
                tag_by_norm.pop(f"{t.normalized_name}::{t.tag_class_id}", None)
                continue

        if len(t_name) == 0 or is_drive_letter or is_pure_punctuation or is_system_segment or is_user_slang:
            session.execute(text("DELETE FROM asset_unit_tag_link WHERE tag_id = :tid"), {"tid": t.id})
            session.execute(text("DELETE FROM tag_alias WHERE tag_id = :tid"), {"tid": t.id})
            session.execute(text("DELETE FROM tag WHERE id = :tid"), {"tid": t.id})
            cleaned += 1
            tag_by_norm.pop(t.normalized_name, None)
            tag_by_norm.pop(f"{t.normalized_name}::{t.tag_class_id}", None)

    # 方案 A 落点唯一性：若同一单元在同一标签树上同时被打上父标签与子孙标签的 primary_landing，降级父级落点为 0
    session.execute(text("""
        UPDATE asset_unit_tag_link
        SET is_primary_landing = 0
        WHERE rowid IN (
            SELECT l_parent.rowid
            FROM asset_unit_tag_link l_parent
            JOIN tag t_parent ON l_parent.tag_id = t_parent.id
            WHERE l_parent.is_primary_landing = 1
            AND EXISTS (
                SELECT 1 FROM asset_unit_tag_link l_child
                JOIN tag t_child ON l_child.tag_id = t_child.id
                WHERE l_child.unit_id = l_parent.unit_id
                  AND l_child.is_primary_landing = 1
                  AND t_child.parent_id = t_parent.id
            )
        )
    """))

    session.flush()
    return cleaned


def _strip_library_root_parts(
    parts: List[str],
    library_roots: Optional[List[str]] = None,
) -> List[str]:
    """
    剥离已知媒体库根目录前缀与通用媒体形态根目录，确保只对业务语义目录段进行打标。
    """
    full_str = "/".join(parts).replace("//", "/")
    candidates = list(library_roots or []) + list(MEDIA_SEARCH_ROOTS or [])
    # 按路径长度降序匹配最具体的媒体库根
    candidates.sort(key=len, reverse=True)
    for root_str in candidates:
        if not root_str:
            continue
        root_parts = list(PurePath(root_str).parts)
        if len(parts) > len(root_parts) and list(parts[: len(root_parts)]) == root_parts:
            return list(parts[len(root_parts) : -1])

    # 回退：定位 MEDIA_KIND_MAP 锚点
    for i, p in enumerate(parts[:-1]):
        if p.strip().lower() in MEDIA_KIND_MAP:
            return list(parts[i + 1 : -1])

    return [
        p for p in parts[:-1]
        if p.strip()
        and p.strip().lower() not in SYSTEM_PATH_SEGMENTS
        and not re.match(r"^[a-zA-Z]:?$", p.strip())
    ]


def infer_and_assign_tags_from_path(
    session: Session,
    unit: AssetUnit,
    file_path_str: str,
    library_root: Optional[str] = None,
    library_roots: Optional[List[str]] = None,
    tag_by_norm: Optional[Dict[str, Tag]] = None,
    existing_links: Optional[Set[Tuple[int, int]]] = None,
    class_map: Optional[Dict[str, int]] = None,
    fast_mode: bool = False,
    user_rules: Optional[UserRules] = None,
) -> List[Dict[str, Any]]:
    """
    根据物理路径分段与通用多媒体元数据逆向推断高精度多维标签体系：
    使用 PurePath (零磁盘 I/O)，防止跨网络盘 RPC 阻塞。支持外部用户专属规则。
    """
    if user_rules is None:
        user_rules = load_user_rules()

    path = PurePath(file_path_str)
    parts = list(path.parts)
    stem = path.stem
    assigned_tags = []

    if class_map is None:
        classes = session.exec(select(TagClass)).all()
        class_map = {c.code: c.id for c in classes}

    if not isinstance(tag_by_norm, dict):
        all_t = session.exec(select(Tag)).all()
        tag_by_norm = {}
        for t in all_t:
            tag_by_norm[t.normalized_name] = t
            _, base_norm = normalize_tag_name(t.name)
            tag_by_norm[f"{base_norm}::{t.tag_class_id}"] = t

    if existing_links is None:
        existing_links = {
            (l.unit_id, l.tag_id)
            for l in session.exec(
                select(AssetUnitTagLink.unit_id, AssetUnitTagLink.tag_id).where(AssetUnitTagLink.unit_id == unit.id)
            ).all()
        }

    def _add_tag(name: str, class_code: str, is_primary: bool = False, parent_name: Optional[str] = None) -> Optional[Tag]:
        cid = class_map.get(class_code)
        if not cid or not name:
            return None
        pid = None
        if parent_name:
            ptag = get_or_create_tag_fast(session, tag_by_norm, parent_name, cid)
            pid = ptag.id
        tag = get_or_create_tag_fast(session, tag_by_norm, name, cid, parent_id=pid)
        assign_tag_fast(session, existing_links, unit.id, tag.id, is_primary_landing=is_primary)
        assigned_tags.append({"class": class_code, "name": tag.name})
        return tag

    # 1. 通用媒体形态 (media_kind)
    if unit.unit_type == "audio":
        _add_tag("音频", "media_kind", is_primary=True)
    elif unit.unit_type == "video":
        _add_tag("视频", "media_kind", is_primary=True)
    elif unit.unit_type == "image":
        _add_tag("图片", "media_kind", is_primary=True)
    elif unit.unit_type == "bundle":
        _add_tag("复合媒体", "media_kind", is_primary=True)

    # 2. 截取媒体根目录之后的有效语义层级
    roots_list = list(library_roots or [])
    if library_root:
        roots_list.insert(0, library_root)
    org_segments = _strip_library_root_parts(parts, roots_list)

    inferred_creator: Optional[str] = None
    last_domain_tag_name: Optional[str] = None
    parent_was_creator_dir = False

    # 3. 遍历各级目录段推断 workflow, creator, domain
    for idx, seg in enumerate(org_segments):
        seg_clean = seg.strip()
        seg_lower = seg_clean.lower()

        if (
            not seg_clean
            or seg_lower in SYSTEM_PATH_SEGMENTS
            or seg_lower in MEDIA_KIND_MAP
            or seg_clean in user_rules.ignore_segments
            or seg_clean in user_rules.slang_filter
        ):
            parent_was_creator_dir = False
            continue

        # 3a. 工作流状态 (支持通用 WORKFLOW_MAP 与 user_rules.workflow_mapping)
        if seg_clean in user_rules.workflow_mapping:
            wf_name = user_rules.workflow_mapping[seg_clean]
            _add_tag(wf_name, "workflow", is_primary=False)
            parent_was_creator_dir = seg_clean in user_rules.creator_parent_dirs
            continue
        if seg_lower in WORKFLOW_MAP:
            wf_name, _ = WORKFLOW_MAP[seg_lower]
            _add_tag(wf_name, "workflow", is_primary=False)
            parent_was_creator_dir = seg_clean in user_rules.creator_parent_dirs
            continue

        # 3b. 若目录名直接命中 known_creator_dirs 或父目录声明为创作者容器目录
        if seg_clean in user_rules.known_creator_dirs and not inferred_creator:
            c_name = apply_creator_cleaning(user_rules.known_creator_dirs[seg_clean], user_rules)
            if is_valid_creator_candidate(c_name, user_rules):
                _add_tag(c_name, "creator", is_primary=True)
                inferred_creator = c_name
                parent_was_creator_dir = seg_clean in user_rules.creator_parent_dirs
                continue

        if parent_was_creator_dir and not inferred_creator:
            parent_was_creator_dir = False
            if not re.search(r"[A-Z]{2,4}\d{5,8}", seg_clean, re.IGNORECASE):
                candidate = apply_creator_cleaning(seg_clean, user_rules)
                if is_valid_creator_candidate(candidate, user_rules):
                    _add_tag(candidate, "creator", is_primary=True)
                    inferred_creator = candidate
                    continue

        # 记录当前目录是否为创作者父容器
        is_creator_parent = seg_clean in user_rules.creator_parent_dirs

        # 3c. 若目录段命中 domain_mapping，映射为题材标签（支持多级路径题材）
        if seg_clean in user_rules.domain_mapping:
            dom_name = apply_domain_cleaning(seg_clean, user_rules)
            if dom_name and dom_name not in user_rules.slang_filter:
                parent_dom = last_domain_tag_name if (last_domain_tag_name and last_domain_tag_name != dom_name) else None
                _add_tag(dom_name, "domain", is_primary=True, parent_name=parent_dom)
                last_domain_tag_name = dom_name
            parent_was_creator_dir = is_creator_parent
            continue

        # 3d. 若遇到含标准作品编号的独立作品根目录，其社团/演职员/题材由元数据引擎注入，不再向下遍历作品内部子目录
        if re.search(r"[A-Z]{2,4}\d{5,8}", seg_clean, re.IGNORECASE):
            break

        # 3e. 若非编号目录段含合法前置方括号创作者标记 [Studio]
        if not inferred_creator:
            for b_token in BRACKET_TOKENS_REGEX.findall(seg_clean):
                candidate = apply_creator_cleaning(b_token.strip(), user_rules)
                if is_valid_creator_candidate(candidate, user_rules):
                    _add_tag(candidate, "creator", is_primary=True)
                    inferred_creator = candidate
                    break

        # 3f. 通用层级分类目录推断：当尚未进入创作者专属子目录时，将非作品叶目录的各级业务分类目录构建为多级 domain 标签树
        is_ancestor_category = (idx < len(org_segments) - 1) or (len(org_segments) == 1)
        is_tech_subfolder = bool(
            re.match(
                r"^(?:mp3|wav|flac|mp4|audio|video|image|images|img|bonus|extra|附赠|正篇|正文|(?:disc|cd|part|vol)\.?\s*\d+)$",
                seg_clean,
                re.IGNORECASE,
            )
        )
        if not inferred_creator and is_ancestor_category and not is_tech_subfolder:
            dom_candidate = apply_domain_cleaning(seg_clean, user_rules)
            if 2 <= len(dom_candidate) <= 20 and dom_candidate not in user_rules.slang_filter:
                parent_dom = last_domain_tag_name if (last_domain_tag_name and last_domain_tag_name != dom_candidate) else None
                _add_tag(dom_candidate, "domain", is_primary=True, parent_name=parent_dom)
                last_domain_tag_name = dom_candidate

        parent_was_creator_dir = is_creator_parent

    # 4. 从作品标题或主文件名提取明确标注的演职员 (如 feat. Artist, CV: Name)
    full_title_text = f"{unit.title or ''} {stem}"
    artist_match = ARTIST_CREDIT_REGEX.search(full_title_text)
    if artist_match:
        artist_name = apply_creator_cleaning(artist_match.group(1).strip(), user_rules)
        if is_valid_creator_candidate(artist_name, user_rules):
            if "va" not in class_map:
                va_tc = session.exec(select(TagClass).where(TagClass.code == "va")).first()
                if not va_tc:
                    va_tc = TagClass(
                        code="va",
                        display_name="声优/演职员",
                        icon="mic",
                        color="#f59e0b",
                        is_required=False,
                        is_projectable=False,
                        description="配音出演者、特邀乐手、演职员或合作嘉宾",
                    )
                    session.add(va_tc)
                    session.flush()
                class_map["va"] = va_tc.id
            _add_tag(artist_name, "va", is_primary=False)

    if not fast_mode:
        session.commit()

    return assigned_tags


def batch_reverse_tag_all_units(session: Session) -> Dict[str, int]:
    """
    全量高吞吐批量逆向推断与打标：
    1. 零磁盘 I/O，使用 PurePath 内存解析
    2. 单次查询获取全部 Primary 文件映射，消除 N+1
    3. 分块原子提交 (Chunked Commit)，极速自愈
    """
    user_rules = load_user_rules(force_reload=True)

    # 1. 获取核心类映射与初始化分类继承体系
    classes = session.exec(select(TagClass)).all()
    class_map = {c.code: c.id for c in classes}

    # 2. 获取配置的媒体库根路径集合
    lib_roots = [r.path for r in session.exec(select(LibraryRoot)).all() if r.path]

    # 3. 预加载标签字典 (同时支持 normalized_name 与 norm_name::class_id)
    all_tags = session.exec(select(Tag)).all()
    tag_by_norm: Dict[str, Tag] = {}
    for t in all_tags:
        tag_by_norm[t.normalized_name] = t
        _, base_norm = normalize_tag_name(t.name)
        tag_by_norm[f"{base_norm}::{t.tag_class_id}"] = t

    # 4. 运行分类树自愈与脏标签清理
    ensure_tag_taxonomy_hierarchy(session, tag_by_norm, class_map)
    cleaned_dirty = cleanup_dirty_tags(session, tag_by_norm, class_map, user_rules=user_rules)
    session.commit()
    logger.info("Cleaned %d dirty tags, baseline taxonomy ensured.", cleaned_dirty)

    # 5. 预加载全部已有关联
    existing_links: Set[Tuple[int, int]] = {
        (l.unit_id, l.tag_id)
        for l in session.exec(select(AssetUnitTagLink.unit_id, AssetUnitTagLink.tag_id)).all()
    }

    # 6. 单次查询获取全部 Primary 文件及对应 Unit (0 次 N+1 冗余查询)
    stmt = (
        select(AssetUnit, AssetFile.file_path)
        .join(AssetFile, AssetUnit.id == AssetFile.asset_unit_id)
        .where(AssetFile.role == "primary")
    )
    pairs = session.exec(stmt).all()
    total_units = len(pairs)
    logger.info("Batch reverse tagging %d primary asset units...", total_units)

    tag_counts: Dict[str, int] = {}
    chunk_size = 500

    for idx, (unit, file_path_str) in enumerate(pairs, 1):
        tags = infer_and_assign_tags_from_path(
            session=session,
            unit=unit,
            file_path_str=file_path_str,
            library_roots=lib_roots,
            tag_by_norm=tag_by_norm,
            existing_links=existing_links,
            class_map=class_map,
            fast_mode=True,
            user_rules=user_rules,
        )
        for t in tags:
            k = f"{t['class']}:{t['name']}"
            tag_counts[k] = tag_counts.get(k, 0) + 1

        if idx % chunk_size == 0 or idx == total_units:
            session.commit()
            logger.info("Progress: %d / %d units processed...", idx, total_units)

    session.commit()
    TagHierarchyCacheManager.invalidate()
    logger.info("Batch reverse tagging completed! Total units: %d, Tags assigned: %s", total_units, tag_counts)
    return tag_counts
