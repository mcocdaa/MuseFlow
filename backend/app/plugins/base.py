from abc import ABC, abstractmethod
from typing import List, Dict, Any
from sqlmodel import Session
from app.models.entities import AssetUnit

class BaseRecommender(ABC):
    """可插拔推荐算法基类"""
    name: str = "base"
    display_name: str = "基础推荐"
    description: str = "推荐算法基类"

    @abstractmethod
    def recommend(self, session: Session, context: Dict[str, Any], limit: int = 20) -> List[AssetUnit]:
        """
        根据上下文（包含当前分类过滤、用户近期交互、分页）返回推荐的原子单元 (AssetUnit) 列表。
        """
        pass
