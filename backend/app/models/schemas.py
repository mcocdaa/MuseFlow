from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class TagBriefRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    class_code: Optional[str] = None
    class_name: Optional[str] = None
    is_primary_landing: bool = False
    parent_id: Optional[int] = None
    parent_name: Optional[str] = None
    display_path: Optional[str] = None
    full_path: Optional[str] = None
    ancestor_ids: List[int] = []
    aliases: List[str] = []

class AssetFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    file_path: str
    file_name: str
    extension: str
    mime_type: str
    file_size: int
    role: str
    modified_at: datetime

class AssetUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    unit_type: str
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None
    cover_file_id: Optional[int] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    rating: int = 0
    is_favorite: bool = False
    view_count: int = 0
    total_dwell_seconds: float = 0.0
    last_viewed_at: Optional[datetime] = None
    created_at: datetime
    files: List[AssetFileRead] = []
    tags: List[TagBriefRead] = []
    tag_names: List[str] = []
    dynamic_attributes: Dict[str, Any] = {}

class FeedCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    card_id: str  # "col_59" or "unit_632"
    title: str
    unit_type: str  # "image", "video", "audio", "bundle"
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None
    cover_file_id: Optional[int] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    rating: int = 0
    is_favorite: bool = False
    view_count: int = 0
    total_dwell_seconds: float = 0.0
    last_viewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    files: List[AssetFileRead] = []
    # Series aggregation fields
    is_series: bool = False
    unit_count: int = 1
    representative_unit_id: Optional[int] = None
    tags: List[TagBriefRead] = []
    tag_names: List[str] = []
    dynamic_attributes: Dict[str, Any] = {}

class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    folder_path: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    cover_unit_id: Optional[int] = None
    representative_unit_id: Optional[int] = None
    primary_type: Optional[str] = "audio"  # "video", "audio", "image", "bundle"
    total_duration_seconds: Optional[float] = 0.0
    unit_count: int = 0
    rating: int = 0
    is_favorite: bool = False
    view_count: int = 0
    children: List["CollectionRead"] = []

class SupersetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    icon: Optional[str] = "sparkles"
    cover_url: Optional[str] = None
    unit_count: int = 0

class TelemetryCreate(BaseModel):
    unit_id: int
    action: str  # "click", "dwell", "rate", "favorite", "skip"
    dwell_seconds: float = 0.0

class RateRequest(BaseModel):
    rating: Optional[int] = None
    is_favorite: Optional[bool] = None

class ScanRequest(BaseModel):
    path: str
    name: Optional[str] = None

class SystemActionRequest(BaseModel):
    path: Optional[str] = None
    file_id: Optional[int] = None
    unit_id: Optional[int] = None
