from datetime import datetime, timezone
from typing import Optional, List
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
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Relationships
    files: List["AssetFile"] = Relationship(back_populates="unit")
    collection: Optional[Collection] = Relationship(back_populates="units")
    supersets: List[Superset] = Relationship(
        back_populates="units", link_model=SupersetUnitLink
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
