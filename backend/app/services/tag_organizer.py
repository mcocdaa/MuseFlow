"""
MuseFlow (灵眸流) — 通用标签类组织与分类层级管理器 (Tag Organizer & Hierarchy Manager)

核心设计：
1. 面向对象 5 大核心元类 (TagClass)：
   - media_kind (媒体形态): 音频、视频、图片、复合媒体、有声专辑、独立画册
   - domain (题材流派): 题材/流派/分类，支持多级树形继承与动态挂载
   - creator (创作者/社团): 创作者、社团、艺术家
   - va (声优/演职员): 声优、配音演员、演职员
   - workflow (状态分流): 待整理、待翻译、已汉化、已归档
2. 零侵入与通用性：核心代码不硬编码任何私有创作者别名或称号规约，统一由外部 `user_rules.json` 驱动。
3. 跨元类同名消歧：支持同一名称在正交元类（如 va 与 creator）独立共存，互不覆盖。
4. 官方元数据与缓存无损对齐：自动映射本地元数据缓存（含标题逆向匹配修复缺失作品编号）。
5. 跨语言同义词归一化与分类树分层重组：自动合并多语言同义标签并写入 TagAlias。
6. 方案 A 物理落点锚点唯一性与缓存失效维护。
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import text
from sqlmodel import Session, select, func

from app.models.entities import AssetFile, AssetUnit, AssetUnitTagLink, Collection, Tag, TagClass, TagAlias
from app.services.tag_service import TagHierarchyCacheManager, normalize_tag_name
from app.services.catalog_importer import extract_work_code, fetch_and_cache_catalog_meta, COVER_CACHE_DIR, WORK_CODE_PATTERN
from app.services.reverse_tagger import is_valid_creator_candidate
from app.core.user_rules import (
    load_user_rules,
    apply_creator_cleaning,
    apply_va_cleaning,
    apply_domain_cleaning,
    UserRules,
)

logger = logging.getLogger("museflow.tag_organizer")


def get_or_create_tag_fast(
    session: Session,
    tag_by_norm: Dict[str, Tag],
    name: str,
    tag_class_id: int,
    parent_id: Optional[int] = None,
) -> Optional[Tag]:
    """
    纯内存秒级获取或创建标签（支持跨 TagClass 同名消歧，避免正交元类碰撞）
    """
    clean_name = name.strip()
    if not clean_name:
        return None
    _, norm_name = normalize_tag_name(clean_name)
    scoped_key = f"{norm_name}::{tag_class_id}"

    if scoped_key in tag_by_norm:
        existing = tag_by_norm[scoped_key]
        if parent_id is not None and existing.parent_id is None and existing.id != parent_id:
            existing.parent_id = parent_id
            session.add(existing)
        return existing

    existing = tag_by_norm.get(norm_name)
    if existing and existing.tag_class_id == tag_class_id:
        tag_by_norm[scoped_key] = existing
        if parent_id is not None and existing.parent_id is None and existing.id != parent_id:
            existing.parent_id = parent_id
            session.add(existing)
        return existing

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


def assign_link_fast(
    session: Session,
    existing_links: Set[Tuple[int, int]],
    new_links: List[AssetUnitTagLink],
    unit_id: int,
    tag_id: int,
    is_primary: bool = False,
    confidence: float = 1.0,
) -> None:
    if (unit_id, tag_id) in existing_links:
        return
    link = AssetUnitTagLink(
        unit_id=unit_id,
        tag_id=tag_id,
        is_primary_landing=is_primary,
        confidence=confidence,
    )
    new_links.append(link)
    existing_links.add((unit_id, tag_id))


def ensure_all_classes_and_tags(session: Session, user_rules: Optional[UserRules] = None) -> Dict[str, TagClass]:
    """初始化并对齐通用核心元类 (TagClass)，仅在 user_rules 声明时按需扩展领域元类"""
    if user_rules is None:
        user_rules = load_user_rules()

    classes = session.exec(select(TagClass)).all()
    class_map = {c.code: c for c in classes}

    core_defs = [
        ("media_kind", "媒体形态", "film", "#3b82f6", False),
        ("domain", "核心题材", "sparkles", "#8b5cf6", True),
        ("creator", "创作者/社团", "users", "#a855f7", True),
        ("workflow", "状态分流", "git-branch", "#10b981", False),
    ]
    optional_defs = [
        ("character", "角色人设", "user-check", "#ec4899", False),
        ("interaction", "互动表现", "flame", "#f43f5e", False),
        ("spec", "语种与声学", "headphones", "#06b6d4", False),
        ("va", "声优/演职员", "mic", "#f59e0b", False),
    ]

    needed_optional_codes = set(user_rules.class_reassignments.keys()) | set(user_rules.class_hierarchies.keys())
    if user_rules.va_aliases:
        needed_optional_codes.add("va")
    if user_rules.spec_keyword_rules:
        needed_optional_codes.add("spec")

    active_defs = list(core_defs) + [d for d in optional_defs if d[0] in needed_optional_codes or d[0] in class_map]

    for code, dname, icon, color, is_req in active_defs:
        if code not in class_map:
            tc = TagClass(
                code=code,
                display_name=dname,
                icon=icon,
                color=color,
                is_required=is_req,
                is_projectable=True,
            )
            session.add(tc)
            session.commit()
            session.refresh(tc)
            class_map[code] = tc

    return class_map


def _merge_alias_map_in_class(
    session: Session,
    alias_map: Dict[str, str],
    class_id: int,
    tag_by_norm: Dict[str, Tag],
    existing_links: Set[Tuple[int, int]],
) -> int:
    """
    在指定 TagClass 内将 alias_map 中的别名标签安全合并至标准主标签，并写入 TagAlias。
    """
    if not alias_map or not class_id:
        return 0

    merged_count = 0
    class_tags = session.exec(select(Tag).where(Tag.tag_class_id == class_id)).all()
    tag_by_name = {t.name: t for t in class_tags}

    for alias, canonical_name in alias_map.items():
        if alias == canonical_name or alias not in tag_by_name:
            continue
        alias_tag = tag_by_name[alias]
        canon_tag = tag_by_name.get(canonical_name)
        if not canon_tag:
            canon_tag = get_or_create_tag_fast(
                session, tag_by_norm, canonical_name, class_id, parent_id=alias_tag.parent_id
            )
            if canon_tag:
                tag_by_name[canonical_name] = canon_tag

        if canon_tag and canon_tag.id != alias_tag.id:
            alias_links = session.exec(
                select(AssetUnitTagLink).where(AssetUnitTagLink.tag_id == alias_tag.id)
            ).all()
            for al in alias_links:
                if (al.unit_id, canon_tag.id) not in existing_links:
                    session.add(
                        AssetUnitTagLink(
                            unit_id=al.unit_id,
                            tag_id=canon_tag.id,
                            is_primary_landing=al.is_primary_landing,
                            confidence=al.confidence,
                        )
                    )
                    existing_links.add((al.unit_id, canon_tag.id))
                session.delete(al)
                existing_links.discard((al.unit_id, alias_tag.id))

            # 将子标签过继给标准标签
            children = session.exec(select(Tag).where(Tag.parent_id == alias_tag.id)).all()
            for ch in children:
                if ch.id != canon_tag.id:
                    ch.parent_id = canon_tag.id
                    session.add(ch)

            existing_alias = session.exec(
                select(TagAlias).where(TagAlias.alias_name == alias, TagAlias.tag_id == canon_tag.id)
            ).first()
            if not existing_alias:
                session.add(
                    TagAlias(
                        tag_id=canon_tag.id,
                        alias_name=alias,
                        normalized_alias=alias.lower(),
                        language="ja" if re.search(r"[\u3040-\u30ff]", alias) else "zh",
                    )
                )

            session.flush()
            session.delete(alias_tag)
            tag_by_name.pop(alias, None)
            merged_count += 1

    session.flush()
    return merged_count


def _load_catalog_cache_with_title_index() -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, str]]]:
    """加载全部缓存的作品 JSON 元数据，并构建标题特征索引（用于修复缺失编号目录）"""
    meta_by_code: Dict[str, Dict[str, Any]] = {}
    title_index: List[Tuple[str, str]] = []
    if not COVER_CACHE_DIR.exists():
        return meta_by_code, title_index

    for p in COVER_CACHE_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            wcode = p.stem.upper()
            meta_by_code[wcode] = data
            t = (data.get("title") or "").strip()
            if len(t) >= 8:
                # 归一化空白与引号以支持模糊子串匹配
                t_norm = re.sub(r"[\s'\"”’“‘「」『』≪≫《》～~]", "", t)
                if len(t_norm) >= 8:
                    title_index.append((t_norm, wcode))
        except Exception:
            continue
    return meta_by_code, title_index


def reorganize_all_tags(session: Session) -> Dict[str, Any]:
    """
    全量多维标签体系系统性类结构重组、官方元数据映射与清洗自愈：
    1. 确保核心 TagClass 与基础媒体形态存在；
    2. 清理非法 creator 杂质标签（如编号、章节号、纯数字、宣传/特典等）与黑名单标签；
    3. 全量补齐缺失媒体形态的资产单元；
    4. 基于本地元数据缓存精确注入作品创作者、演职员与题材标签（支持标题逆向对齐）；
    5. 依据外部 user_rules.json 执行 creator / va / domain 跨语言同义词合并与称号规整；
    6. 依据 user_rules.domain_hierarchy 构建结构化多级题材分类树；
    7. 安全清理 0 引用的孤立废弃标签；
    8. 确保方案 A 物理落点锚点唯一性并刷新纯内存层级快照缓存。
    """
    logger.info("开始执行全量多维标签体系系统性类结构重组与元数据映射...")
    user_rules = load_user_rules(force_reload=True)

    class_map_objs = ensure_all_classes_and_tags(session, user_rules)
    class_map = {k: v.id for k, v in class_map_objs.items()}

    cr_id = class_map.get("creator")
    va_id = class_map.get("va")
    dom_id = class_map.get("domain")
    mk_id = class_map["media_kind"]
    wf_id = class_map.get("workflow")

    # 先清理历史污染的非法 creator 标签与黑名单标签
    all_tags_init = session.exec(select(Tag)).all()
    purged_invalid = 0
    for t in all_tags_init:
        t_clean = t.name.strip()
        is_blacklisted = t_clean in user_rules.slang_filter or t_clean in user_rules.ignore_segments
        is_bad_creator = (cr_id is not None and t.tag_class_id == cr_id and not is_valid_creator_candidate(t_clean, user_rules))
        if is_blacklisted or is_bad_creator:
            session.execute(text("DELETE FROM asset_unit_tag_link WHERE tag_id = :tid"), {"tid": t.id})
            session.execute(text("DELETE FROM tag_alias WHERE tag_id = :tid"), {"tid": t.id})
            session.execute(text("DELETE FROM tag WHERE id = :tid"), {"tid": t.id})
            purged_invalid += 1
    session.flush()

    all_tags = session.exec(select(Tag)).all()
    tag_by_norm: Dict[str, Tag] = {}
    for t in all_tags:
        tag_by_norm[t.normalized_name] = t
        _, base_norm = normalize_tag_name(t.name)
        tag_by_norm[f"{base_norm}::{t.tag_class_id}"] = t

    existing_links: Set[Tuple[int, int]] = {
        (l.unit_id, l.tag_id)
        for l in session.exec(select(AssetUnitTagLink.unit_id, AssetUnitTagLink.tag_id)).all()
    }
    new_links: List[AssetUnitTagLink] = []

    stats = {
        "total_units": 0,
        "purged_invalid_tags": purged_invalid,
        "media_kind_assigned": 0,
        "coded_collections_processed": 0,
        "creator_links_added": 0,
        "va_links_added": 0,
        "domain_links_added": 0,
        "aliases_merged": 0,
        "hierarchy_organized": 0,
        "orphans_cleaned": 0,
    }

    # 1. 媒体形态 (按需创建子形态，通用主形态保留)
    t_audio = get_or_create_tag_fast(session, tag_by_norm, "音频", mk_id)
    t_video = get_or_create_tag_fast(session, tag_by_norm, "视频", mk_id)
    t_image = get_or_create_tag_fast(session, tag_by_norm, "图片", mk_id)
    t_bundle = get_or_create_tag_fast(session, tag_by_norm, "复合媒体", mk_id)
    t_coded_audio: Optional[Tag] = None

    units = session.exec(select(AssetUnit)).all()
    stats["total_units"] = len(units)
    cols_by_id = {c.id: c for c in session.exec(select(Collection)).all()}

    meta_by_code, title_index = _load_catalog_cache_with_title_index()

    def _resolve_col_code(col: Optional[Collection]) -> Optional[str]:
        if not col:
            return None
        code = extract_work_code(col.name or "") or (extract_work_code(col.folder_path) if col.folder_path else None)
        if code:
            return code
        raw_text = f"{col.name or ''} {col.folder_path or ''}"
        for k_prefix, target_code in user_rules.folder_code_overrides.items():
            if k_prefix in raw_text:
                return target_code
        norm_text = re.sub(r"[\s'\"”’“‘「」『』≪≫《》～~]", "", raw_text)
        for t_norm, cand_code in title_index:
            if t_norm in norm_text:
                return cand_code
        return None

    col_code_map: Dict[int, str] = {}
    for cid, col in cols_by_id.items():
        resolved = _resolve_col_code(col)
        if resolved:
            col_code_map[cid] = resolved

    for cid, col in cols_by_id.items():
        if cid not in col_code_map and col.parent_id and col.parent_id in col_code_map:
            col_code_map[cid] = col_code_map[col.parent_id]

    stmt_u_path = (
        select(AssetUnit.id, AssetFile.file_path)
        .join(AssetFile, AssetUnit.id == AssetFile.asset_unit_id)
        .where(AssetFile.role == "primary")
    )
    unit_path_map: Dict[int, str] = {uid: fp for uid, fp in session.exec(stmt_u_path).all()}

    units_by_code: Dict[str, List[AssetUnit]] = {}
    for u in units:
        fp = unit_path_map.get(u.id, "")
        fp_codes = [m.upper() for m in WORK_CODE_PATTERN.findall(fp)]
        col_code = col_code_map.get(u.collection_id) if u.collection_id else None
        # 优先采用文件路径最深层的具体作品编号，回退至所属 Collection 的作品编号
        unit_code = fp_codes[-1] if fp_codes else col_code
        is_coded = bool(unit_code)
        if unit_code:
            units_by_code.setdefault(unit_code, []).append(u)

        if u.unit_type == "audio":
            assign_link_fast(session, existing_links, new_links, u.id, t_audio.id, is_primary=not is_coded)
            if is_coded:
                if t_coded_audio is None:
                    t_coded_audio = get_or_create_tag_fast(session, tag_by_norm, "有声专辑", mk_id, parent_id=t_audio.id)
                if t_coded_audio:
                    assign_link_fast(session, existing_links, new_links, u.id, t_coded_audio.id, is_primary=True)
            stats["media_kind_assigned"] += 1
        elif u.unit_type == "video":
            assign_link_fast(session, existing_links, new_links, u.id, t_video.id, is_primary=True)
            stats["media_kind_assigned"] += 1
        elif u.unit_type == "image":
            assign_link_fast(session, existing_links, new_links, u.id, t_image.id, is_primary=True)
            stats["media_kind_assigned"] += 1
        elif u.unit_type == "bundle":
            assign_link_fast(session, existing_links, new_links, u.id, t_bundle.id, is_primary=True)
            stats["media_kind_assigned"] += 1

    # 2. 映射作品官方缓存元数据（仅当库中实际存在带编号作品时按需挂载根节点）
    t_domain_root: Optional[Tag] = None
    if units_by_code and dom_id and user_rules.domain_root_name:
        t_domain_root = get_or_create_tag_fast(session, tag_by_norm, user_rules.domain_root_name, dom_id)

    reassigned_map: Dict[str, int] = {}
    for t_code, t_list in user_rules.class_reassignments.items():
        tc_id = class_map.get(t_code)
        if tc_id:
            for tn in t_list:
                reassigned_map[tn] = tc_id

    for work_code, code_units in units_by_code.items():
        meta = meta_by_code.get(work_code)
        if not meta:
            meta = fetch_and_cache_catalog_meta(work_code, download_cover=False)
            if meta:
                meta_by_code[work_code] = meta
        if not meta or not code_units:
            continue

        stats["coded_collections_processed"] += 1

        # A. Circle -> creator
        circle = meta.get("circle")
        if circle and circle.strip() and cr_id:
            clean_circle = apply_creator_cleaning(circle.strip(), user_rules)
            if is_valid_creator_candidate(clean_circle, user_rules):
                c_tag = get_or_create_tag_fast(session, tag_by_norm, clean_circle, cr_id)
                if c_tag:
                    for u in code_units:
                        assign_link_fast(session, existing_links, new_links, u.id, c_tag.id, is_primary=True)
                        stats["creator_links_added"] += 1

        # B. VAs -> va
        vas = meta.get("vas", [])
        if vas and isinstance(vas, list) and va_id:
            for va_name in vas:
                v_clean = apply_va_cleaning(va_name.strip(), user_rules)
                if v_clean and v_clean.lower() != "n/a" and len(v_clean) <= 30:
                    v_tag = get_or_create_tag_fast(session, tag_by_norm, v_clean, va_id)
                    if v_tag:
                        for u in code_units:
                            assign_link_fast(session, existing_links, new_links, u.id, v_tag.id, is_primary=False)
                            stats["va_links_added"] += 1

        # C. Tags -> 全量路由至对应正交元类 (domain / character / interaction / spec)，不截断
        meta_tags = meta.get("tags", [])
        if meta_tags and isinstance(meta_tags, list) and dom_id:
            for d_name in meta_tags:
                d_clean = apply_domain_cleaning(d_name.strip(), user_rules)
                if (
                    2 <= len(d_clean) <= 20
                    and not WORK_CODE_PATTERN.match(d_clean)
                    and d_clean not in user_rules.slang_filter
                    and d_clean not in user_rules.ignore_segments
                ):
                    dest_cid = reassigned_map.get(d_clean, dom_id)
                    dest_pid = (t_domain_root.id if t_domain_root else None) if dest_cid == dom_id else None
                    d_tag = get_or_create_tag_fast(session, tag_by_norm, d_clean, dest_cid, parent_id=dest_pid)
                    if d_tag:
                        for u in code_units:
                            assign_link_fast(session, existing_links, new_links, u.id, d_tag.id, is_primary=False)
                            stats["domain_links_added"] += 1

    # 分块提交新增关联
    if new_links:
        chunk_size = 2000
        for i in range(0, len(new_links), chunk_size):
            session.add_all(new_links[i : i + chunk_size])
            session.flush()

    # 3. 跨元类别名合并与称号清洗 (creator, va, domain)
    if cr_id:
        stats["aliases_merged"] += _merge_alias_map_in_class(
            session, user_rules.creator_aliases, cr_id, tag_by_norm, existing_links
        )
        cr_tags = session.exec(select(Tag).where(Tag.tag_class_id == cr_id)).all()
        cr_by_name = {t.name: t for t in cr_tags}
        for t in list(cr_tags):
            if t.id is None:
                continue
            clean_name = apply_creator_cleaning(t.name, user_rules)
            if clean_name and clean_name != t.name:
                target_tag = cr_by_name.get(clean_name)
                if target_tag and target_tag.id != t.id:
                    t_links = session.exec(select(AssetUnitTagLink).where(AssetUnitTagLink.tag_id == t.id)).all()
                    for tl in t_links:
                        if (tl.unit_id, target_tag.id) not in existing_links:
                            session.add(
                                AssetUnitTagLink(
                                    unit_id=tl.unit_id,
                                    tag_id=target_tag.id,
                                    is_primary_landing=tl.is_primary_landing,
                                )
                            )
                            existing_links.add((tl.unit_id, target_tag.id))
                        session.delete(tl)
                        existing_links.discard((tl.unit_id, t.id))
                    session.delete(t)
                    stats["aliases_merged"] += 1
                else:
                    t.name = clean_name
                    session.add(t)
                    cr_by_name[clean_name] = t

    if va_id:
        stats["aliases_merged"] += _merge_alias_map_in_class(
            session, user_rules.va_aliases, va_id, tag_by_norm, existing_links
        )

    if dom_id:
        combined_dom_aliases = dict(user_rules.domain_mapping)
        combined_dom_aliases.update(user_rules.domain_aliases)
        stats["aliases_merged"] += _merge_alias_map_in_class(
            session, combined_dom_aliases, dom_id, tag_by_norm, existing_links
        )

    session.flush()

    # 4. 跨元类分面剥离与去重 (将混在 domain 中的 角色人设/互动表现/语种与声学 迁移或合并至独立正交元类)
    if user_rules.class_reassignments:
        all_curr_tags = session.exec(select(Tag)).all()
        tags_by_name_list: Dict[str, List[Tag]] = {}
        for t in all_curr_tags:
            tags_by_name_list.setdefault(t.name, []).append(t)

        for target_code, t_names in user_rules.class_reassignments.items():
            target_cid = class_map.get(target_code)
            if not target_cid:
                continue
            for tname in t_names:
                candidates = tags_by_name_list.get(tname, [])
                if not candidates:
                    continue
                target_tag = next((x for x in candidates if x.tag_class_id == target_cid), None)
                if not target_tag:
                    target_tag = candidates[0]
                    target_tag.tag_class_id = target_cid
                    target_tag.parent_id = None
                    session.add(target_tag)
                    _, bnorm = normalize_tag_name(target_tag.name)
                    tag_by_norm[f"{bnorm}::{target_cid}"] = target_tag
                    stats["hierarchy_organized"] += 1
                # 若其他元类 (如 domain) 存在同名残留副本，合并其关联并删除副本
                for dup in candidates:
                    if dup.id != target_tag.id:
                        dup_links = session.exec(select(AssetUnitTagLink).where(AssetUnitTagLink.tag_id == dup.id)).all()
                        for dl in dup_links:
                            if (dl.unit_id, target_tag.id) not in existing_links:
                                session.add(
                                    AssetUnitTagLink(
                                        unit_id=dl.unit_id,
                                        tag_id=target_tag.id,
                                        is_primary_landing=dl.is_primary_landing,
                                        confidence=dl.confidence,
                                    )
                                )
                                existing_links.add((dl.unit_id, target_tag.id))
                            existing_links.discard((dl.unit_id, dup.id))
                        session.flush()
                        session.execute(text("DELETE FROM asset_unit_tag_link WHERE tag_id = :tid"), {"tid": dup.id})
                        session.execute(text("DELETE FROM tag_alias WHERE tag_id = :tid"), {"tid": dup.id})
                        session.execute(text("DELETE FROM tag WHERE id = :tid"), {"tid": dup.id})
        session.flush()

    # 4.5 跨元类同义词合并 (例如 domain_aliases 中的别名或其标准主标签已被迁移至 character/interaction/spec)
    if user_rules.domain_aliases:
        all_after_reassign = session.exec(select(Tag)).all()
        by_name_any: Dict[str, Tag] = {t.name: t for t in all_after_reassign}
        for alias_n, canon_n in user_rules.domain_aliases.items():
            if alias_n == canon_n or alias_n not in by_name_any or canon_n not in by_name_any:
                continue
            a_tag = by_name_any[alias_n]
            c_tag = by_name_any[canon_n]
            if a_tag.id and c_tag.id and a_tag.id != c_tag.id:
                a_links = session.exec(select(AssetUnitTagLink).where(AssetUnitTagLink.tag_id == a_tag.id)).all()
                for al in a_links:
                    if (al.unit_id, c_tag.id) not in existing_links:
                        session.add(
                            AssetUnitTagLink(
                                unit_id=al.unit_id,
                                tag_id=c_tag.id,
                                is_primary_landing=al.is_primary_landing,
                                confidence=al.confidence,
                            )
                        )
                        existing_links.add((al.unit_id, c_tag.id))
                    existing_links.discard((al.unit_id, a_tag.id))
                session.flush()
                session.execute(text("DELETE FROM asset_unit_tag_link WHERE tag_id = :tid"), {"tid": a_tag.id})
                session.execute(text("DELETE FROM tag_alias WHERE tag_id = :tid"), {"tid": a_tag.id})
                session.execute(text("DELETE FROM tag WHERE id = :tid"), {"tid": a_tag.id})
                by_name_any.pop(alias_n, None)
                stats["aliases_merged"] += 1
        session.flush()

    # 5. 依据 user_rules.domain_hierarchy 组织 domain 分类层级树
    if dom_id and user_rules.domain_hierarchy:
        dom_tags = session.exec(select(Tag).where(Tag.tag_class_id == dom_id)).all()
        dom_by_name = {t.name: t for t in dom_tags}
        root_dom: Optional[Tag] = None
        if user_rules.domain_root_name:
            root_dom = dom_by_name.get(user_rules.domain_root_name) or get_or_create_tag_fast(
                session, tag_by_norm, user_rules.domain_root_name, dom_id
            )

        for parent_cat_name, child_names in user_rules.domain_hierarchy.items():
            parent_tag = dom_by_name.get(parent_cat_name)
            if not parent_tag:
                parent_tag = get_or_create_tag_fast(
                    session, tag_by_norm, parent_cat_name, dom_id, parent_id=root_dom.id if root_dom else None
                )
                if parent_tag:
                    dom_by_name[parent_cat_name] = parent_tag
            elif root_dom and parent_tag.id != root_dom.id and parent_tag.parent_id != root_dom.id:
                parent_tag.parent_id = root_dom.id
                session.add(parent_tag)

            if not parent_tag:
                continue

            for ch_name in child_names:
                ch_tag = dom_by_name.get(ch_name)
                if ch_tag and ch_tag.id != parent_tag.id and ch_tag.parent_id != parent_tag.id:
                    ch_tag.parent_id = parent_tag.id
                    session.add(ch_tag)
                    stats["hierarchy_organized"] += 1

    # 6. 依据 user_rules.class_hierarchies 组织其他正交元类 (character, interaction, spec) 的内部层级树
    if user_rules.class_hierarchies:
        for target_code, h_map in user_rules.class_hierarchies.items():
            target_cid = class_map.get(target_code)
            if not target_cid:
                continue
            c_tags = session.exec(select(Tag).where(Tag.tag_class_id == target_cid)).all()
            c_by_name = {t.name: t for t in c_tags}
            for p_name, ch_list in h_map.items():
                p_tag = c_by_name.get(p_name)
                if not p_tag:
                    p_tag = get_or_create_tag_fast(session, tag_by_norm, p_name, target_cid, parent_id=None)
                    if p_tag:
                        c_by_name[p_name] = p_tag
                elif p_tag.parent_id is not None:
                    p_tag.parent_id = None
                    session.add(p_tag)
                if not p_tag:
                    continue
                for ch_name in ch_list:
                    ch_tag = c_by_name.get(ch_name)
                    if ch_tag and ch_tag.id != p_tag.id and ch_tag.parent_id != p_tag.id:
                        ch_tag.parent_id = p_tag.id
                        session.add(ch_tag)
                        stats["hierarchy_organized"] += 1

    session.flush()

    # 6.5 若配置了 domain_root_name，为因位于待分类/散装目录而缺失具体题材标签的单元补齐根题材兜底
    if dom_id and user_rules.domain_root_name:
        root_dom_tag = get_or_create_tag_fast(session, tag_by_norm, user_rules.domain_root_name, dom_id)
        if root_dom_tag:
            dom_tag_ids = {t.id for t in session.exec(select(Tag).where(Tag.tag_class_id == dom_id)).all() if t.id}
            units_with_dom = {uid for (uid, tid) in existing_links if tid in dom_tag_ids}
            fallback_dom_links: List[AssetUnitTagLink] = []
            for u in units:
                if u.id not in units_with_dom:
                    assign_link_fast(session, existing_links, fallback_dom_links, u.id, root_dom_tag.id, is_primary=True)
            if fallback_dom_links:
                for i in range(0, len(fallback_dom_links), 2000):
                    session.add_all(fallback_dom_links[i : i + 2000])
                    session.flush()

    # 7. 依据 user_rules.spec_keyword_rules 或集合信息按需补齐 spec 标签
    spec_id = class_map.get("spec")
    if spec_id and (user_rules.spec_keyword_rules or col_code_map):
        spec_parent_by_child: Dict[str, str] = {}
        for p_name, ch_list in user_rules.class_hierarchies.get("spec", {}).items():
            for ch_name in ch_list:
                spec_parent_by_child[ch_name] = p_name

        def _get_spec_tag_on_demand(t_name: str) -> Optional[Tag]:
            p_name = spec_parent_by_child.get(t_name)
            p_tag = get_or_create_tag_fast(session, tag_by_norm, p_name, spec_id) if p_name else None
            return get_or_create_tag_fast(
                session, tag_by_norm, t_name, spec_id, parent_id=p_tag.id if p_tag else None
            )

        stmt_files = select(AssetUnit.id, AssetUnit.title, AssetUnit.collection_id, AssetFile.file_path).join(
            AssetFile, AssetUnit.id == AssetFile.asset_unit_id
        ).where(AssetFile.role == "primary")
        spec_links: List[AssetUnitTagLink] = []
        for uid, utitle, ucid, fpath in session.exec(stmt_files).all():
            full_s = f"{utitle or ''} {fpath or ''}"
            matched_lang = False
            for spec_tag_name, kw_list in user_rules.spec_keyword_rules.items():
                if any(kw.lower() in full_s.lower() for kw in kw_list):
                    st = _get_spec_tag_on_demand(spec_tag_name)
                    if st:
                        assign_link_fast(session, existing_links, spec_links, uid, st.id, is_primary=False)
                        if "语" in spec_tag_name:
                            matched_lang = True
            if not matched_lang and ucid and ucid in col_code_map and user_rules.spec_keyword_rules:
                default_orig_lang = next((k for k in spec_parent_by_child if "原声" in k), "原声")
                st_orig = _get_spec_tag_on_demand(default_orig_lang)
                if st_orig:
                    assign_link_fast(session, existing_links, spec_links, uid, st_orig.id, is_primary=False)

        if spec_links:
            for i in range(0, len(spec_links), 2000):
                session.add_all(spec_links[i : i + 2000])
                session.flush()

    # 7.5 基于伴随字幕/歌词文件 (subtitle / lyrics) 与本地化特征自动对齐 workflow 状态
    if wf_id and user_rules.workflow_mapping:
        wf_tags = session.exec(select(Tag).where(Tag.tag_class_id == wf_id)).all()
        wf_by_name = {t.name: t for t in wf_tags}
        t_localized = wf_by_name.get("已汉化") or get_or_create_tag_fast(session, tag_by_norm, "已汉化", wf_id)
        t_untranslated = wf_by_name.get("待翻译") or get_or_create_tag_fast(session, tag_by_norm, "待翻译", wf_id)
        t_archived = wf_by_name.get("已归档") or get_or_create_tag_fast(session, tag_by_norm, "已归档", wf_id)

        sub_unit_ids = set(
            session.exec(select(AssetFile.asset_unit_id).where(AssetFile.role.in_(["subtitle", "lyrics"]))).all()
        )
        localized_col_ids: Set[int] = set()
        for u in units:
            if u.id in sub_unit_ids and u.collection_id:
                localized_col_ids.add(u.collection_id)
        for cid, col in cols_by_id.items():
            c_text = f"{col.name or ''} {col.folder_path or ''}"
            if any(kw in c_text for kw in ("汉化", "中字", "中文", "字幕", "简体", "繁体", "繁體")):
                localized_col_ids.add(cid)

        wf_tag_ids = {t.id for t in session.exec(select(Tag).where(Tag.tag_class_id == wf_id)).all() if t.id}
        units_with_wf = {
            uid for (uid, tid) in existing_links if tid in wf_tag_ids
        }

        wf_links: List[AssetUnitTagLink] = []
        for u in units:
            has_loc = (u.id in sub_unit_ids) or (u.collection_id in localized_col_ids)
            if has_loc and t_localized:
                assign_link_fast(session, existing_links, wf_links, u.id, t_localized.id, is_primary=False)
                units_with_wf.add(u.id)
            elif u.id not in units_with_wf:
                if u.collection_id in col_code_map and t_untranslated:
                    assign_link_fast(session, existing_links, wf_links, u.id, t_untranslated.id, is_primary=False)
                elif t_archived:
                    assign_link_fast(session, existing_links, wf_links, u.id, t_archived.id, is_primary=False)

        if wf_links:
            for i in range(0, len(wf_links), 2000):
                session.add_all(wf_links[i : i + 2000])
                session.flush()

        # 消除互斥冲突：若同一单元同时拥有 已汉化 与 待翻译，移除 待翻译
        if t_localized and t_untranslated:
            session.execute(
                text("""
                    DELETE FROM asset_unit_tag_link
                    WHERE tag_id = :untrans_id
                      AND unit_id IN (
                          SELECT unit_id FROM asset_unit_tag_link WHERE tag_id = :loc_id
                      )
                """),
                {"untrans_id": t_untranslated.id, "loc_id": t_localized.id},
            )
            session.flush()

    # 8. 清理孤立废弃标签（仅保护通用核心标签与 user_rules 显式声明的层级根节点）
    all_db_tags = session.exec(select(Tag)).all()
    protected_system_names = {
        "音频", "视频", "图片", "复合媒体",
        "待整理", "已归档",
    }
    if user_rules.domain_root_name:
        protected_system_names.add(user_rules.domain_root_name)
    protected_system_names.update(user_rules.domain_hierarchy.keys())
    for h_map in user_rules.class_hierarchies.values():
        protected_system_names.update(h_map.keys())

    for t in all_db_tags:
        if t.name in protected_system_names:
            continue
        link_cnt = session.exec(
            select(func.count(AssetUnitTagLink.unit_id)).where(AssetUnitTagLink.tag_id == t.id)
        ).one()
        child_cnt = session.exec(select(func.count(Tag.id)).where(Tag.parent_id == t.id)).one()
        if link_cnt == 0 and child_cnt == 0:
            session.execute(text("DELETE FROM tag_alias WHERE tag_id = :tid"), {"tid": t.id})
            session.delete(t)
            stats["orphans_cleaned"] += 1

    # 9. 方案 A 落点唯一性自愈（递归消除祖先链重复 primary_landing）
    for _ in range(3):
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

    session.commit()
    TagHierarchyCacheManager.invalidate()
    logger.info("全量标签系统性重组与元数据映射完成！指标: %s", stats)
    return stats


cleanup_and_reorganize_media_kind_tags = reorganize_all_tags

if __name__ == "__main__":
    from app.core.db import engine
    with Session(engine) as s:
        res = reorganize_all_tags(s)
        print("Reorganize All Tags Result:", res)
