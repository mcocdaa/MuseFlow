from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from sqlmodel import Session
from app.models.entities import AssetUnit

class BaseRecommender(ABC):
    """可插拔推荐算法基类"""
    name: str = "base"
    display_name: str = "基础推荐"
    description: str = "推荐算法基类"

    @abstractmethod
    def recommend(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[AssetUnit]:
        """
        根据上下文返回推荐的原子单元 (AssetUnit) 列表。limit 为 None 则返回匹配的全量数据。
        """
        pass

    @abstractmethod
    def recommend_series(self, session: Session, context: Dict[str, Any], limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        根据上下文返回推荐的系列 (Collection / Album) 聚合卡片列表。
        每个卡片包含真实的 unit_count、total_duration_seconds、首轨信息与系列元数据。
        limit 为 None 则全量返回，绝不遗漏。
        """
        pass
