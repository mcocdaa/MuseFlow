import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from sqlmodel import Session, select

from app.core.path_resolver import resolve_physical_path
from app.models.entities import AssetFile, AssetUnit, AssetUnitTagLink, Tag, TagClass
from app.services.path_sanitizer import (
    DEFAULT_MAX_PATH_LENGTH,
    DEFAULT_MAX_SEGMENT_LENGTH,
    check_path_length_budget,
    sanitize_path_segment,
)

logger = logging.getLogger("museflow.projection_dsl")


class LevelOperator(BaseModel):
    """
    投影管线层级算子：
    每个层级定义该级文件夹的生成逻辑，可为：
    1. 标签族提取 (facet: "tag.class('domain')")；
    2. 条件分支分流 (condition: "not has_translation", folder_name: "待翻译")；
    3. 叶子实体命名 (naming: "[{meta.rj_code}] {unit.title}%unique{meta.rj_code}")
    """
    level_index: int = 0
    name: Optional[str] = None
    
    # 提取模式
    facet: Optional[str] = None  # e.g. "tag.domain", "tag.creator", "tag.media_kind", "collection.name"
    fallback: Optional[str] = "未分类" # 若提取为空且 fallback 为 None，则该层级自动坍缩消除
    
    # 条件分支模式
    condition: Optional[str] = None # e.g. "not unit.has_translation", "unit.unit_type == 'bundle'"
    folder_name: Optional[str] = None # 满足条件时生成的目录名
    
    # 命名模版 (通常位于最后一层叶子节点)
    naming: Optional[str] = None # e.g. "[{meta.rj_code}] {title}"


class PipelineConfig(BaseModel):
    """可自定义投影管线配置"""
    id: str = "custom"
    name: str = "自定义整理管线"
    description: Optional[str] = None
    target_root: str
    levels: List[LevelOperator] = Field(default_factory=list)
    max_segment_length: int = DEFAULT_MAX_SEGMENT_LENGTH
    max_path_length: int = DEFAULT_MAX_PATH_LENGTH


def extract_unit_context(session: Session, unit: AssetUnit) -> Dict[str, Any]:
    """提取资产单元及其标签属性的求值上下文 (Context Dictionary)"""
    links = session.exec(
        select(AssetUnitTagLink, Tag, TagClass)
        .join(Tag, AssetUnitTagLink.tag_id == Tag.id)
        .join(TagClass, Tag.tag_class_id == TagClass.id)
        .where(AssetUnitTagLink.unit_id == unit.id)
    ).all()

    tag_by_class: Dict[str, str] = {}
    primary_landing_by_class: Dict[str, str] = {}
    all_tags: List[str] = []

    for link, tag, tc in links:
        all_tags.append(tag.name)
        tag_by_class[tc.code] = tag.name
        if link.is_primary_landing:
            primary_landing_by_class[tc.code] = tag.name

    dyn_attrs = unit.dynamic_attributes or {}

    context = {
        "unit": {
            "id": unit.id,
            "title": unit.title,
            "unit_type": unit.unit_type,
            "primary_class": unit.primary_class,
            "has_translation": dyn_attrs.get("has_translation", True),
            "view_count": unit.view_count,
            "rating": unit.rating,
        },
        "meta": dyn_attrs,
        "tag": primary_landing_by_class or tag_by_class, # 优先使用落点锚点标签
        "all_tags": all_tags,
        "collection": {
            "name": unit.collection.name if unit.collection else "未分系列"
        },
    }
    return context


def evaluate_condition(condition_str: str, context: Dict[str, Any]) -> bool:
    """在安全只读沙箱中求值条件分支"""
    if not condition_str:
        return True
    try:
        # 提供安全上下文变量
        safe_env = {
            "unit": context["unit"],
            "meta": context["meta"],
            "tag": context["tag"],
            "all_tags": context["all_tags"],
            "collection": context["collection"],
        }
        return bool(eval(condition_str, {"__builtins__": {}}, safe_env))
    except Exception as e:
        logger.warning(f"Condition evaluation failed for '{condition_str}': {e}")
        return False


def build_adaptive_disambiguation_map(
    session: Session, units: List[AssetUnit]
) -> Dict[int, str]:
    """
    移植 Beets %unique{} 自适应消歧机制：
    1. 统计当前批次所有资产的标准标题；
    2. 若某个标题在同一作用域内唯一出现，则消歧后缀为空字符串（保持纯净目录名）；
    3. 若发生 2 个或以上重名碰撞，则提取第一个非空的区分字段（如 RJ 码、发售年份、ID）自适应追加后缀。
    """
    title_groups: Dict[str, List[AssetUnit]] = {}
    for u in units:
        clean_title = sanitize_path_segment(u.title)
        title_groups.setdefault(clean_title, []).append(u)

    disambig_map: Dict[int, str] = {}
    for clean_title, group in title_groups.items():
        if len(group) == 1:
            disambig_map[group[0].id] = ""
        else:
            # 发生碰撞，自适应追加区分标识符
            for u in group:
                rj = (u.dynamic_attributes or {}).get("rj_code")
                if rj:
                    disambig_map[u.id] = f" [{rj}]"
                elif (u.dynamic_attributes or {}).get("release_year"):
                    disambig_map[u.id] = f" [{(u.dynamic_attributes or {}).get('release_year')}]"
                else:
                    disambig_map[u.id] = f" [ID_{u.id}]"

    return disambig_map


def render_template_string(template: str, context: Dict[str, Any], disambig_suffix: str = "") -> str:
    """渲染形如 [{meta.rj_code}] {unit.title}%unique{} 的模板"""
    result = template

    # 处理 %unique{}
    result = re.sub(r"%unique\{[^}]*\}", disambig_suffix, result)

    # 替换变量占位符 {a.b | fallback}
    pattern = re.compile(r"\{([a-zA-Z0-9_.]+)(?:\s*\|\s*['\"]?([^'\"}]+)['\"]?)?\}")

    def _replace_var(match):
        var_path = match.group(1)
        fallback_val = match.group(2) or ""

        parts = var_path.split(".")
        val: Any = context
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                val = None
                break

        if val is not None and str(val).strip():
            return str(val).strip()
        return fallback_val

    rendered = pattern.sub(_replace_var, result)
    return rendered.strip()


def calculate_unit_landing_path(
    session: Session,
    unit: AssetUnit,
    pipeline: PipelineConfig,
    disambig_suffix: str = "",
) -> Tuple[List[str], str]:
    """
    为指定资产单元计算目标物理文件夹分段列表及叶子名称
    返回: (文件夹分段列表, 叶子名称)
    """
    context = extract_unit_context(session, unit)
    segments: List[str] = []

    for level in pipeline.levels:
        # 1. 命名层 (叶子节点)
        if level.naming:
            leaf_name = render_template_string(level.naming, context, disambig_suffix)
            sanitized_leaf = sanitize_path_segment(leaf_name, pipeline.max_segment_length)
            return segments, sanitized_leaf

        # 2. 条件分流层
        if level.condition:
            if evaluate_condition(level.condition, context):
                fn = level.folder_name or "分流目录"
                segments.append(sanitize_path_segment(fn, pipeline.max_segment_length))
            elif level.fallback:
                segments.append(sanitize_path_segment(level.fallback, pipeline.max_segment_length))
            continue

        # 3. 标签族提取层
        if level.facet:
            val = None
            if level.facet.startswith("tag."):
                class_code = level.facet.split(".")[1]
                val = context["tag"].get(class_code)
            elif level.facet == "collection.name":
                val = context["collection"]["name"]

            if val:
                segments.append(sanitize_path_segment(str(val), pipeline.max_segment_length))
            elif level.fallback:
                segments.append(sanitize_path_segment(level.fallback, pipeline.max_segment_length))

    # 默认叶子名
    default_leaf = sanitize_path_segment(unit.title + disambig_suffix, pipeline.max_segment_length)
    return segments, default_leaf


def generate_pipeline_projection_plan(
    session: Session,
    units: List[AssetUnit],
    pipeline: PipelineConfig,
) -> Dict[str, Any]:
    """
    依据管线规则生成全量物理整理计划与三色风险体检表：
    🟢 绿色 (Safe): 同盘安全改名/归位
    🟡 黄色 (Warning): 路径长度越界预警、跨分区复制耗时提示
    🔴 红色 (Critical Conflict): 目标路径已存在其他资产碰撞
    """
    target_root_p = resolve_physical_path(pipeline.target_root)
    disambig_map = build_adaptive_disambiguation_map(session, units)

    items = []
    seen_destinations: Dict[str, int] = {} # 目标绝对路径 -> unit_id (检测内部重名碰撞)
    stats = {"safe_count": 0, "warning_count": 0, "conflict_count": 0}

    for unit in units:
        segments, leaf_name = calculate_unit_landing_path(session, unit, pipeline, disambig_map.get(unit.id, ""))

        # 组合目标文件夹路径
        unit_target_dir = target_root_p
        for seg in segments:
            unit_target_dir = unit_target_dir / seg

        # 针对复合包 vs 独立单文件
        files = session.exec(select(AssetFile).where(AssetFile.asset_unit_id == unit.id)).all()
        if not files:
            continue

        is_bundle = (unit.unit_type == "bundle") or (len(files) > 1)

        if is_bundle:
            # 复合包作为整体文件夹移动
            final_unit_folder = unit_target_dir / leaf_name
            for af in files:
                src_path = Path(af.file_path)
                dst_path = final_unit_folder / src_path.name
                _record_action_item(items, stats, af, src_path, dst_path, seen_destinations, unit.id, pipeline)
        else:
            # 独立单文件
            primary_file = files[0]
            src_path = Path(primary_file.file_path)
            ext = src_path.suffix
            dst_file_name = f"{leaf_name}{ext}" if not leaf_name.endswith(ext) else leaf_name
            dst_path = unit_target_dir / dst_file_name
            _record_action_item(items, stats, primary_file, src_path, dst_path, seen_destinations, unit.id, pipeline)

    return {
        "pipeline_name": pipeline.name,
        "target_root": str(target_root_p),
        "total_actions": len(items),
        "stats": stats,
        "actions": items,
    }


def _record_action_item(
    items: List[Dict[str, Any]],
    stats: Dict[str, int],
    asset_file: AssetFile,
    src_path: Path,
    dst_path: Path,
    seen_destinations: Dict[str, int],
    unit_id: int,
    pipeline: PipelineConfig,
) -> None:
    src_str = str(src_path.resolve()) if src_path.exists() else str(src_path)
    dst_str = str(dst_path)

    # 判断是否原地不需要搬移
    if src_str == dst_str:
        return

    # 风险检测
    risk_level = "safe" # safe, warning, conflict
    risk_messages = []

    # 1. 目标冲突碰撞检测
    if dst_str in seen_destinations and seen_destinations[dst_str] != unit_id:
        risk_level = "conflict"
        risk_messages.append("目标位置与另一资产重名碰撞")
    elif dst_path.exists() and dst_path.resolve() != src_path.resolve():
        risk_level = "conflict"
        risk_messages.append("目标位置在物理磁盘上已存在其他同名文件")

    seen_destinations[dst_str] = unit_id

    # 2. 全路径长度预算检测
    is_safe_len, cur_len, warn_msg = check_path_length_budget(dst_str, pipeline.max_path_length)
    if not is_safe_len:
        if risk_level != "conflict":
            risk_level = "warning"
        risk_messages.append(warn_msg)

    # 3. 统计计数
    if risk_level == "conflict":
        stats["conflict_count"] += 1
    elif risk_level == "warning":
        stats["warning_count"] += 1
    else:
        stats["safe_count"] += 1

    items.append({
        "unit_id": unit_id,
        "file_id": asset_file.id,
        "file_name": asset_file.file_name,
        "src_path": src_str,
        "dst_path": dst_str,
        "risk_level": risk_level,
        "risk_messages": risk_messages,
    })
