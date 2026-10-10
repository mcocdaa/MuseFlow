import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlmodel import Session, select

from app.models.entities import AssetFile, AssetUnit, AssetUnitTagLink, Tag, TagClass
from app.services.asmr_importer import extract_rj_code
from app.services.tag_service import assign_tag_to_unit, create_tag

logger = logging.getLogger("museflow.reverse_tagger")

MEDIA_KIND_MAP = {
    "音声": "音频",
    "音频": "音频",
    "音乐": "音频",
    "music": "音频",
    "sound": "音频",
    "audio": "音频",
    "视频": "视频",
    "video": "视频",
    "movies": "视频",
    "相册": "插画/图片",
    "图片": "插画/图片",
    "插画": "插画/图片",
    "photos": "插画/图片",
    "images": "插画/图片",
}

WORKFLOW_MAP = {
    "待翻译": ("待翻译", False),
    "生肉": ("待翻译", False),
    "听不懂": ("待翻译", False),
    "已汉化": ("已汉化", True),
    "精翻": ("已汉化", True),
    "中文": ("已汉化", True),
    "中字": ("已汉化", True),
    "待整理": ("待整理", True),
    "散装收纳": ("散装收纳", True),
    "散装视频收纳": ("散装收纳", True),
    "网络下载暂存": ("网络暂存", True),
    "待提取音频": ("待提取", True),
}

DOMAIN_NORMALIZATION = {
    "助眠": "助眠",
    "催眠": "催眠",
    "广播剧": "广播剧",
    "音乐": "音乐",
    "影视": "影视",
    "有声书": "有声书",
    "杂项剧情": "杂项剧情",
}

SYSTEM_PATH_SEGMENTS = {
    "/", "\\", "mnt", "z", "c", "d", "mcoc", "home", "data", "media", "users",
    "待分类", "其他", "#", "appdata", "local"
}


def infer_and_assign_tags_from_path(
    session: Session,
    unit: AssetUnit,
    file_path_str: str,
    library_root: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    根据物理路径分段与作品元数据逆向推断高精度多维标签体系：
    1. 自动注入 [媒体形态: 音频 / 视频 / 图片]
    2. 自动注入 [题材流派: 助眠 / 催眠 / 广播剧 / 音乐 / ...]
    3. 自动注入 [工作流状态: 已汉化 / 待翻译 / 散装收纳]
    4. 提取 RJ 码与社团/创作者并激活 VoiceDrama 多态属性
    """
    path = Path(file_path_str).resolve()
    parts = list(path.parts)

    assigned_tags = []

    # 获取系统核心标签类
    classes = session.exec(select(TagClass)).all()
    class_map = {c.code: c.id for c in classes}

    has_translation = True
    inferred_domain = None
    inferred_creator = None

    # 1. 寻找媒体形态锚点 (音声 / 视频 / 相册)
    media_idx = -1
    for i, p in enumerate(parts):
        p_clean = p.strip()
        p_lower = p_clean.lower()
        if p_lower in MEDIA_KIND_MAP:
            media_idx = i
            t_name = MEDIA_KIND_MAP[p_lower]
            if "media_kind" in class_map:
                tag = create_tag(session, t_name, class_map["media_kind"])
                assign_tag_to_unit(session, unit.id, tag.id, is_primary_landing=True)
                assigned_tags.append({"class": "media_kind", "name": t_name})
            break

    # 截取媒体根目录之后的有效层级
    if media_idx != -1:
        org_segments = parts[media_idx + 1 : -1]
    else:
        # Fallback: 排除系统盘符挂载名
        org_segments = [
            p for p in parts[:-1]
            if p.strip() and p.strip().lower() not in SYSTEM_PATH_SEGMENTS
            and not re.match(r"^[a-zA-Z]:", p.strip())
        ]

    # 2. 遍历各级目录段推断 domain, workflow, creator
    for seg in org_segments:
        seg_clean = seg.strip()
        seg_lower = seg_clean.lower()

        if not seg_clean or seg_lower in SYSTEM_PATH_SEGMENTS:
            continue

        # 工作流状态推断
        if seg_clean in WORKFLOW_MAP and "workflow" in class_map:
            wf_name, trans_status = WORKFLOW_MAP[seg_clean]
            has_translation = trans_status
            tag = create_tag(session, wf_name, class_map["workflow"])
            assign_tag_to_unit(session, unit.id, tag.id, is_primary_landing=True)
            assigned_tags.append({"class": "workflow", "name": wf_name})
            continue

        # 创作者识别 (如 [社团名] 或 (社团名))
        if seg_clean.startswith("[") and "]" in seg_clean and "creator" in class_map:
            creator_name = seg_clean[1 : seg_clean.find("]")].strip()
            if creator_name and not re.match(r"^(RJ|VJ|BJ)\d+", creator_name, re.I):
                tag = create_tag(session, creator_name, class_map["creator"])
                assign_tag_to_unit(session, unit.id, tag.id, is_primary_landing=True)
                assigned_tags.append({"class": "creator", "name": creator_name})
                inferred_creator = creator_name
                continue

        # 题材分类推断 (优先规范化别名)
        if "domain" in class_map and not inferred_domain:
            domain_name = DOMAIN_NORMALIZATION.get(seg_clean, None)
            if not domain_name:
                # 排除 RJ 前缀作品主目录
                if not re.match(r"^\[?(RJ|VJ|BJ)\d+", seg_clean, re.I) and len(seg_clean) <= 25:
                    domain_name = seg_clean
            if domain_name:
                tag = create_tag(session, domain_name, class_map["domain"])
                assign_tag_to_unit(session, unit.id, tag.id, is_primary_landing=True)
                assigned_tags.append({"class": "domain", "name": domain_name})
                inferred_domain = domain_name

    # 3. 检查汉化与字幕线索 (标题中含汉化/中文/中字，或者单元下挂有字幕文件)
    full_text_hint = f"{unit.title} {path.name} {path.parent.name}"
    is_translated = False
    if any(k in full_text_hint for k in ["【简体中文版】", "【简体中文字幕版】", "【中文音声】", "【中文】", "汉化", "中字", "精翻"]):
        is_translated = True
    elif unit.files and any(
        f.role == "subtitle" or f.extension.lower() in [".vtt", ".srt", ".lrc"]
        for f in unit.files
    ):
        is_translated = True

    if is_translated and "workflow" in class_map:
        tag = create_tag(session, "已汉化", class_map["workflow"])
        assign_tag_to_unit(session, unit.id, tag.id, is_primary_landing=False)
        assigned_tags.append({"class": "workflow", "name": "已汉化"})
        has_translation = True

    # 4. 检查 RJ 码与激活 VoiceDrama 多态属性
    rj_code = (
        extract_rj_code(unit.title)
        or extract_rj_code(path.name)
        or extract_rj_code(path.parent.name)
    )
    if rj_code:
        unit.primary_class = "VoiceDrama"
        dyn = unit.dynamic_attributes or {}
        dyn["rj_code"] = rj_code
        dyn["has_translation"] = has_translation
        if inferred_creator and "circle" not in dyn:
            dyn["circle"] = inferred_creator
        unit.dynamic_attributes = dyn
        session.add(unit)
        session.commit()

    return assigned_tags


def batch_reverse_tag_all_units(session: Session) -> Dict[str, int]:
    """
    全量扫描并自动逆向打标库中所有已纳管资产单元：
    清理脏标签、自愈多态属性、建立 Adjacency List 落点锚点。
    """
    # 1. 清理历史上误打的非法字符标签 (如 '/' 或盘符)
    dirty_tags = session.exec(
        select(Tag).where(Tag.name.in_(["/", "\\", "mcoc", "mnt", "z", "c", "d"]))
    ).all()
    for dt in dirty_tags:
        # 清除其关联
        links = session.exec(select(AssetUnitTagLink).where(AssetUnitTagLink.tag_id == dt.id)).all()
        for lnk in links:
            session.delete(lnk)
        session.delete(dt)
    session.commit()

    # 2. 获取全部 AssetUnit 并批量逆向推断打标
    units = session.exec(select(AssetUnit)).all()
    tagged_count = 0
    tag_counts: Dict[str, int] = {}

    for unit in units:
        primary_file = session.exec(
            select(AssetFile).where(AssetFile.asset_unit_id == unit.id, AssetFile.role == "primary")
        ).first()
        if not primary_file:
            continue

        tags = infer_and_assign_tags_from_path(session, unit, primary_file.file_path)
        for t in tags:
            k = f"{t['class']}:{t['name']}"
            tag_counts[k] = tag_counts.get(k, 0) + 1
        tagged_count += 1

    session.commit()
    logger.info("Batch reverse tagged %d units. Top tags: %s", tagged_count, tag_counts)
    return tag_counts

