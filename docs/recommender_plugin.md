# 🔌 Pluggable Recommendation Engine & Telemetry Guide

MuseFlow features an open, modular recommendation plugin architecture that allows developers to write custom discovery algorithms or hook autonomous AI recommendation agents.

---

## 1. Recommendation Interface: `BaseRecommender`

Every algorithm inherits from `BaseRecommender` defined in `backend/app/plugins/base.py`:

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from sqlmodel import Session
from app.models.entities import AssetUnit

class BaseRecommender(ABC):
    name: str = "custom"
    display_name: str = "自定义推荐算法"
    description: str = "算法描述与逻辑说明"

    @abstractmethod
    def recommend(
        self,
        session: Session,
        context: Dict[str, Any],
        limit: int = 24
    ) -> List[AssetUnit]:
        """
        Receives session and client context (e.g. active category, collection filter),
        returns an ordered list of AssetUnits.
        """
        pass
```

---

## 2. Built-in Recommendation Plugins

1. **`DiscoverRecommender` (`discover`)**:
   - Random shuffle explorer designed to introduce serendipity and expose diverse corners of the media library.
2. **`MemoryFlashbackRecommender` (`flashback`)**:
   - "唤醒尘封的记忆": Prioritizes items that were ingested earliest or have the lowest interaction / view counts.
3. **`AffinityRecommender` (`affinity`)**:
   - Scores items by favorite status (`is_favorite == True`), user star rating (`1-5`), and aggregate dwell duration (`total_dwell_seconds`).

---

## 3. Telemetry Protection & Anti-Skew Invariants

- **Dwell Time Capping (`MAX_DWELL_SECONDS = 180.0`)**:
  When a user leaves a browser tab open overnight on a photo or paused video, the dwell tracker caps the recorded interaction at 180 seconds. This prevents overnight browser sessions from skewing recommendation models.
- **Action Log**:
  Each click, like, star rating, or skip is logged in `TelemetryLog` with UTC timestamps.
