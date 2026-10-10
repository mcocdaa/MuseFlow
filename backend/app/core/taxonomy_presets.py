"""
MuseFlow (灵眸流) — 通用标签分类预设库 (Taxonomy Presets Library)

设计原则：
1. 最小核心解耦：系统核心仅保留客观物理形态 (media_kind) 与通用生命周期 (workflow)。
2. 领域预设按需加载：为不同媒体库（音乐、播客、二次元/同人、摄影设计、技术教程）提供开箱即用的分类元类族。
3. 零污染与用户自主：预设仅为推荐蓝图，用户可随意增删、修改属性或自由自建全新的永久元类。
"""

from typing import Any, Dict, List, Optional
from sqlmodel import Session, select
from app.models.entities import TagClass


TAXONOMY_PRESETS: Dict[str, Dict[str, Any]] = {
    "voice_drama": {
        "id": "voice_drama",
        "name": "广播剧 & 有声演播",
        "description": "专为广播剧、有声书、多角色演播与声学作品设计的正交分类体系",
        "icon": "headphones",
        "classes": [
            {
                "code": "domain",
                "display_name": "核心题材",
                "icon": "sparkles",
                "color": "#a855f7",
                "is_projectable": True,
                "is_required": True,
                "description": "作品核心流派、世界观设定与场景题材",
            },
            {
                "code": "character",
                "display_name": "角色人设",
                "icon": "heart",
                "color": "#ec4899",
                "is_projectable": True,
                "is_required": False,
                "description": "角色身份、关系属性与性格体态设定",
            },
            {
                "code": "interaction",
                "display_name": "互动表现",
                "icon": "flame",
                "color": "#f97316",
                "is_projectable": False,
                "is_required": False,
                "description": "声学互动方式、感官触发与动作表现",
            },
            {
                "code": "spec",
                "display_name": "语种与声学",
                "icon": "globe",
                "color": "#06b6d4",
                "is_projectable": True,
                "is_required": False,
                "description": "语音语种、双耳录音设备与声学规格",
            },
            {
                "code": "creator",
                "display_name": "创作者/社团",
                "icon": "users",
                "color": "#14b8a6",
                "is_projectable": True,
                "is_required": True,
                "description": "制作社团、个人创作者或剧团",
            },
            {
                "code": "va",
                "display_name": "声优/演职员",
                "icon": "mic",
                "color": "#f59e0b",
                "is_projectable": False,
                "is_required": False,
                "description": "配音出演者、声优或主播",
            },
        ],
    },
    "music": {
        "id": "music",
        "name": "HiFi 音乐 / 唱片专集",
        "description": "面向音乐收藏家、唱片专集、流派与曲风分类",
        "icon": "music",
        "classes": [
            {
                "code": "artist",
                "display_name": "艺术家/歌手",
                "icon": "user",
                "color": "#3b82f6",
                "is_projectable": True,
                "is_required": False,
                "description": "主唱、乐手、作曲家或乐队",
            },
            {
                "code": "album",
                "display_name": "唱片专辑",
                "icon": "disc",
                "color": "#8b5cf6",
                "is_projectable": True,
                "is_required": False,
                "description": "发行专集或合辑",
            },
            {
                "code": "genre",
                "display_name": "音乐流派",
                "icon": "activity",
                "color": "#10b981",
                "is_projectable": True,
                "is_required": False,
                "description": "摇滚、爵士、古典、流行、电子等",
            },
            {
                "code": "release_year",
                "display_name": "发行年代",
                "icon": "calendar",
                "color": "#f59e0b",
                "is_projectable": True,
                "is_required": False,
                "description": "唱片正式发行年份",
            },
        ],
    },
    "podcast": {
        "id": "podcast",
        "name": "播客 / 访谈电台",
        "description": "专为播客单集、系列访谈、话题讨论定制",
        "icon": "radio",
        "classes": [
            {
                "code": "host",
                "display_name": "主播/主持人",
                "icon": "mic",
                "color": "#3b82f6",
                "is_projectable": True,
                "is_required": False,
                "description": "栏目固定主播",
            },
            {
                "code": "guest",
                "display_name": "特邀嘉宾",
                "icon": "user-check",
                "color": "#ec4899",
                "is_projectable": False,
                "is_required": False,
                "description": "单集受访嘉宾或搭档",
            },
            {
                "code": "topic",
                "display_name": "讨论话题",
                "icon": "message-circle",
                "color": "#10b981",
                "is_projectable": True,
                "is_required": False,
                "description": "本期核心议题与领域",
            },
        ],
    },
    "photo_design": {
        "id": "photo_design",
        "name": "摄影 / 设计商业资产",
        "description": "商业拍摄、平面设计素材与设计稿归档",
        "icon": "camera",
        "classes": [
            {
                "code": "project",
                "display_name": "所属项目",
                "icon": "folder",
                "color": "#3b82f6",
                "is_projectable": True,
                "is_required": False,
                "description": "归属设计项目或品牌案",
            },
            {
                "code": "client",
                "display_name": "客户/品牌",
                "icon": "briefcase",
                "color": "#8b5cf6",
                "is_projectable": True,
                "is_required": False,
                "description": "甲方客户或商业品牌",
            },
            {
                "code": "gear",
                "display_name": "摄影器材/机型",
                "icon": "camera",
                "color": "#f59e0b",
                "is_projectable": False,
                "is_required": False,
                "description": "拍摄所用相机或镜头型号",
            },
        ],
    },
    "course": {
        "id": "course",
        "name": "技术教程 / 视频课程",
        "description": "技术讲座、编程教学与知识库归纳",
        "icon": "book-open",
        "classes": [
            {
                "code": "instructor",
                "display_name": "主讲人/讲师",
                "icon": "user",
                "color": "#3b82f6",
                "is_projectable": True,
                "is_required": False,
                "description": "课程主讲导师或机构",
            },
            {
                "code": "tech_stack",
                "display_name": "技术栈/语言",
                "icon": "code",
                "color": "#10b981",
                "is_projectable": True,
                "is_required": False,
                "description": "Python, Rust, React, AI 等核心技术",
            },
            {
                "code": "difficulty",
                "display_name": "难度级别",
                "icon": "bar-chart-2",
                "color": "#f59e0b",
                "is_projectable": True,
                "is_required": False,
                "description": "入门、进阶、大师实战",
            },
        ],
    },
}


def list_taxonomy_presets() -> List[Dict[str, Any]]:
    """获取所有支持的分类体系预设列表"""
    return list(TAXONOMY_PRESETS.values())


def apply_taxonomy_preset(session: Session, preset_id: str) -> List[TagClass]:
    """
    幂等地应用指定的分类体系预设。
    如果元类已存在则跳过，不存在则安全创建，绝不覆写用户已有数据。
    """
    preset = TAXONOMY_PRESETS.get(preset_id)
    if not preset:
        raise ValueError(f"未知的领域分类预设: '{preset_id}'")

    results: List[TagClass] = []
    codes = [c_def["code"] for c_def in preset["classes"]]
    
    # 1. 查询已存在的元类
    existing_map = {
        tc.code: tc for tc in session.exec(select(TagClass).where(TagClass.code.in_(codes))).all()
    }

    # 2. 创建缺失的元类
    new_classes = []
    for c_def in preset["classes"]:
        code = c_def["code"]
        if code not in existing_map:
            tc = TagClass(
                code=code,
                display_name=c_def["display_name"],
                icon=c_def.get("icon", "tag"),
                color=c_def.get("color", "#6366f1"),
                is_projectable=c_def.get("is_projectable", True),
                is_required=c_def.get("is_required", False),
                description=c_def.get("description"),
            )
            session.add(tc)
            new_classes.append(tc)

    if new_classes:
        session.commit()

    # 3. 统一返回全量有效元类列表
    results = session.exec(select(TagClass).where(TagClass.code.in_(codes))).all()
    return list(results)
