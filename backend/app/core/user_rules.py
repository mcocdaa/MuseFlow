"""
MuseFlow (灵眸流) — 用户专属规则加载器 (User Rules Configuration Loader)

架构设计：
1. 彻底解耦：核心框架不包含任何特定用户的特定创作者别名、称号后缀或领域术语。
2. 规则外挂：自动加载用户本地专属的 `user_rules.json`（位于 DATA_DIR/config/ 或环境变量 MUSEFLOW_USER_RULES）。
3. 优雅降级：若用户未提供配置文件，默认回退为空规则集，通用引擎按标准模式运行。
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.config import DATA_DIR

logger = logging.getLogger("museflow.user_rules")


class UserRules(BaseModel):
    """用户本地自定义规则配置模型"""
    creator_aliases: Dict[str, str] = Field(
        default_factory=dict,
        description="创作者别名规范化映射"
    )
    va_aliases: Dict[str, str] = Field(
        default_factory=dict,
        description="声优/演职员多语言或括弧别名规范化映射"
    )
    domain_aliases: Dict[str, str] = Field(
        default_factory=dict,
        description="题材/流派跨语言近义词归一化映射"
    )
    domain_hierarchy: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="题材/流派父子层级树定义 {父标签名: [子标签名列表]}"
    )
    class_reassignments: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="跨元类标签重分配映射 {target_class_code: [tag_names]}"
    )
    class_hierarchies: Dict[str, Dict[str, List[str]]] = Field(
        default_factory=dict,
        description="各元类内部父子层级树定义 {class_code: {parent_name: [child_names]}}"
    )
    domain_root_name: Optional[str] = Field(
        default=None,
        description="domain 分类树的默认根标签名称（可选，如由 user_rules.json 指定）"
    )
    spec_keyword_rules: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="规格标签关键词自动推断规则 {标签名: [路径或标题关键词列表]}"
    )
    folder_code_overrides: Dict[str, str] = Field(
        default_factory=dict,
        description="特定缺失编号目录前缀到真实作品编号的映射"
    )
    creator_parent_dirs: List[str] = Field(
        default_factory=list,
        description="子目录直接代表创作者名称的父目录集合"
    )
    known_creator_dirs: Dict[str, str] = Field(
        default_factory=dict,
        description="特定目录名直接映射为创作者标签"
    )
    strip_suffixes: List[str] = Field(
        default_factory=list,
        description="需要从创作者名字末尾剔除的特定称号/后缀"
    )
    slang_filter: List[str] = Field(
        default_factory=list,
        description="非语义/脏标签/黑名单过滤"
    )
    domain_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="物理目录名到题材流派标签的映射"
    )
    workflow_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="物理目录名到工作流状态标签的映射"
    )
    ignore_segments: List[str] = Field(
        default_factory=list,
        description="自定义在解析物理路径时需要忽略的文件夹名称"
    )


_CACHED_USER_RULES: Optional[UserRules] = None


def get_user_rules_file_path() -> Optional[Path]:
    """探测用户自定义规则文件的物理落点"""
    env_path = os.getenv("MUSEFLOW_USER_RULES")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists() and p.is_file():
            return p

    standard_path = DATA_DIR / "config" / "user_rules.json"
    if standard_path.exists() and standard_path.is_file():
        return standard_path

    cwd_path = Path("user_rules.json").resolve()
    if cwd_path.exists() and cwd_path.is_file():
        return cwd_path

    return None


def load_user_rules(force_reload: bool = False) -> UserRules:
    """加载用户专属规则配置（单例缓存 + 安全回退）"""
    global _CACHED_USER_RULES
    if _CACHED_USER_RULES is not None and not force_reload:
        return _CACHED_USER_RULES

    rule_file = get_user_rules_file_path()
    if not rule_file:
        _CACHED_USER_RULES = UserRules()
        return _CACHED_USER_RULES

    try:
        with open(rule_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            rules = UserRules(**data)
            logger.info("Loaded custom user rules from %s (%d creator aliases, %d domain aliases)",
                        rule_file, len(rules.creator_aliases), len(rules.domain_aliases))
            _CACHED_USER_RULES = rules
            return rules
    except Exception as e:
        logger.warning("Failed to parse user rules from %s: %s. Fallback to empty rules.", rule_file, e)
        _CACHED_USER_RULES = UserRules()
        return _CACHED_USER_RULES


def apply_creator_cleaning(raw_name: str, rules: Optional[UserRules] = None) -> str:
    """基于用户外挂规则清洗创作者名称"""
    if not raw_name:
        return ""
    if rules is None:
        rules = load_user_rules()

    name = raw_name.strip()

    # 1. 优先别名精准匹配
    if name in rules.creator_aliases:
        return rules.creator_aliases[name]

    # 2. 后缀剥离 (如 XX工作室 -> XX)
    for sfx in rules.strip_suffixes:
        if name.endswith(sfx) and len(name) > len(sfx) + 1:
            clean = name[:-len(sfx)].strip()
            return rules.creator_aliases.get(clean, clean)

    return name


def apply_va_cleaning(raw_name: str, rules: Optional[UserRules] = None) -> str:
    """基于用户外挂规则清洗并归一化声优/演职员名称"""
    if not raw_name:
        return ""
    if rules is None:
        rules = load_user_rules()

    name = raw_name.strip()
    if name in rules.va_aliases:
        return rules.va_aliases[name]
    return name


def apply_domain_cleaning(raw_name: str, rules: Optional[UserRules] = None) -> str:
    """基于用户外挂规则清洗并归一化题材/流派名称"""
    if not raw_name:
        return ""
    if rules is None:
        rules = load_user_rules()

    name = raw_name.strip()
    if name in rules.domain_mapping:
        name = rules.domain_mapping[name]
    if name in rules.domain_aliases:
        name = rules.domain_aliases[name]
    return name

