from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class LibraryRoot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)
    name: str
    auto_watch: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
    last_scanned_at: Optional[datetime] = Field(default=None)

class Collection(SQLModel, table=True):
    """系列 / 集合：例如某次旅游相册、某个短片工程集"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    folder_path: Optional[str] = Field(default=None, index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="collection.id")
    cover_asset_id: Optional[int] = Field(default=None)
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)

    # Relationships
    units: List["AssetUnit"] = Relationship(back_populates="collection")

class SupersetUnitLink(SQLModel, table=True):
    """虚拟超集与原子单元的关联表 (多对多)"""
    superset_id: int = Field(foreign_key="superset.id", primary_key=True)
    unit_id: int = Field(foreign_key="assetunit.id", primary_key=True)

class Superset(SQLModel, table=True):
    """虚拟超集：跨物理目录的多维集合（例如：好友小李全部照片、2024海滩精选）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    icon: Optional[str] = Field(default="sparkles")
    cover_url: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)

    units: List["AssetUnit"] = Relationship(
        back_populates="supersets", link_model=SupersetUnitLink
    )

class TagClass(SQLModel, table=True):
    """
    标签元类 (OOP Tag Class):
    定义标签属于哪个族系 (如 media_kind, domain, creator, workflow, character, style)
    """
    __tablename__ = "tag_class"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True) # e.g. "domain", "creator", "media_kind", "workflow"
    display_name: str = Field(index=True)
    icon: Optional[str] = Field(default="tag")
    color: Optional[str] = Field(default="#6366f1")
    attribute_schema: Optional[str] = Field(default="{}") # JSON Schema for dynamic attributes
    created_at: datetime = Field(default_factory=utc_now)

    tags: List["Tag"] = Relationship(back_populates="tag_class")

class AssetUnitTagLink(SQLModel, table=True):
    """
    资产单元与标签的多对多超图关联表 (方案 A: is_primary_landing 标记物理落点锚点)
    """
    __tablename__ = "asset_unit_tag_link"
    
    unit_id: int = Field(foreign_key="assetunit.id", primary_key=True, index=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True, index=True)
    is_primary_landing: bool = Field(default=False, index=True) # 物理落点锚点 (不具语义排他性)
    confidence: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=utc_now)

class Tag(SQLModel, table=True):
    """
    标签实体 (OOP Tag):
    采用 Adjacency List (parent_id) 支撑 O(1) 原子移动与 SQLite 递归 CTE 检索
    """
    __tablename__ = "tag"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    normalized_name: str = Field(index=True, unique=True) # 小写规范名，防大小写冲突
    tag_class_id: int = Field(foreign_key="tag_class.id", index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="tag.id", index=True)

    # 动态多态属性 (如 rj_code, circle, vas, has_translation 等)
    dynamic_attributes: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)

    # Relationships
    tag_class: Optional[TagClass] = Relationship(back_populates="tags")
    parent: Optional["Tag"] = Relationship(
        sa_relationship_kwargs={"remote_side": "Tag.id", "backref": "children"}
    )
    units: List["AssetUnit"] = Relationship(
        back_populates="tags", link_model=AssetUnitTagLink
    )
    aliases: List["TagAlias"] = Relationship(back_populates="tag")

class TagAlias(SQLModel, table=True):
    """
    标签别名与同义词映射实体 (对齐 W3C SKOS altLabel):
    支持多语言、拼音缩写与近义词映射，使异构输入统一归一化到受控核心概念
    """
    __tablename__ = "tag_alias"

    id: Optional[int] = Field(default=None, primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", index=True)
    alias_name: str = Field(index=True)
    normalized_alias: str = Field(index=True)
    language: str = Field(default="zh", index=True) # "zh", "en", "ja", "pinyin", "romaji"
    is_preferred: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)

    tag: Optional[Tag] = Relationship(back_populates="aliases")

class AssetUnit(SQLModel, table=True):
    """
    原子消费单元（根元素）：
    - 单张独立图片
    - 独立音频（单曲）
    - 独立视频
    - 复合包 (例如 mp4 + srt + wav 打包为一个不可分割的播放单元)
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    unit_type: str = Field(index=True)  # "image", "video", "audio", "bundle"
    
    collection_id: Optional[int] = Field(default=None, foreign_key="collection.id")
    cover_file_id: Optional[int] = Field(default=None)
    
    duration_seconds: Optional[float] = Field(default=None)
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    
    # 评价与反馈
    rating: int = Field(default=0)  # 0~5
    is_favorite: bool = Field(default=False)
    
    # 统计数据（喂给推荐算法）
    view_count: int = Field(default=0)
    total_dwell_seconds: float = Field(default=0.0)
    last_viewed_at: Optional[datetime] = Field(default=None)

    # 虚拟与物理自愈标记
    projection_drift: bool = Field(default=False, index=True)
    primary_class: str = Field(default="MediaAsset") # e.g. "VoiceDrama", "Image", "Video"
    dynamic_attributes: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Relationships
    files: List["AssetFile"] = Relationship(back_populates="unit")
    collection: Optional[Collection] = Relationship(back_populates="units")
    supersets: List[Superset] = Relationship(
        back_populates="units", link_model=SupersetUnitLink
    )
    tags: List[Tag] = Relationship(
        back_populates="units", link_model=AssetUnitTagLink
    )

class AssetFile(SQLModel, table=True):
    """物理磁盘文件映射"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_path: str = Field(unique=True, index=True)
    file_name: str
    extension: str = Field(index=True)
    mime_type: str
    file_size: int
    modified_at: datetime
    
    asset_unit_id: Optional[int] = Field(default=None, foreign_key="assetunit.id")
    role: str = Field(default="primary") # primary, video, audio, subtitle, image, thumbnail
    
    unit: Optional[AssetUnit] = Relationship(back_populates="files")

class TelemetryLog(SQLModel, table=True):
    """用户行为日志埋点"""
    id: Optional[int] = Field(default=None, primary_key=True)
    unit_id: int = Field(index=True, foreign_key="assetunit.id")
    action: str = Field(index=True) # "impression", "click", "dwell", "rate", "favorite", "skip"
    dwell_seconds: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=utc_now)

class MaintenanceLeaseLock(SQLModel, table=True):
    """持久化目录排他租约锁 (带有超时时间，防死锁和崩溃残留)"""
    __tablename__ = "maintenance_lock"
    
    folder_path: str = Field(primary_key=True)
    reason: str
    owner_token: str # plan_id 或 session_token
    locked_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime

class ProjectionJournal(SQLModel, table=True):
    """两阶段物理投影意图日志 (两阶段事务保障)"""
    __tablename__ = "projection_journal"

    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: str = Field(index=True)
    action_type: str # rename_dir, move_dir, move_file, set_mtime
    src_path: str
    dst_path: Optional[str] = None
    status: str = Field(default="PENDING", index=True) # PENDING, EXECUTED, COMMITTED, FAILED, COMPENSATED
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

