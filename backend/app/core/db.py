from typing import Generator
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine, Session
from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 15,  # 15s timeout on connection level
    },
    echo=False
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")  # 10s busy timeout
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

from typing import Generator, Optional

def init_db(preset: Optional[str] = None):
    from sqlalchemy import text
    from sqlmodel import select
    from app.models.entities import TagClass

    SQLModel.metadata.create_all(engine)

    # 1. SQLite 动态安全列自愈迁移 (保证现有 assetunit 表拥有新列)
    with engine.connect() as conn:
        cursor = conn.execute(text("PRAGMA table_info(assetunit)"))
        columns = [row[1] for row in cursor.fetchall()]
        if columns:
            if "projection_drift" not in columns:
                conn.execute(text("ALTER TABLE assetunit ADD COLUMN projection_drift BOOLEAN DEFAULT 0"))
            if "primary_class" not in columns:
                conn.execute(text("ALTER TABLE assetunit ADD COLUMN primary_class VARCHAR DEFAULT 'MediaAsset'"))
            if "dynamic_attributes" not in columns:
                conn.execute(text("ALTER TABLE assetunit ADD COLUMN dynamic_attributes JSON DEFAULT '{}'"))

        cursor_t = conn.execute(text("PRAGMA table_info(telemetrylog)"))
        columns_t = [row[1] for row in cursor_t.fetchall()]
        if columns_t:
            if "score" not in columns_t:
                conn.execute(text("ALTER TABLE telemetrylog ADD COLUMN score FLOAT"))
            if "context_metadata" not in columns_t:
                conn.execute(text("ALTER TABLE telemetrylog ADD COLUMN context_metadata JSON DEFAULT '{}'"))

        # 2. 覆盖索引加固：消除回表，加速批量预加载与多维标签检索
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_collection_parent_id ON collection (parent_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_assetunit_collection_id ON assetunit (collection_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_assetunit_collection_type ON assetunit (collection_id, unit_type);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asset_unit_tag_link_covering ON asset_unit_tag_link (tag_id, unit_id, is_primary_landing);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asset_unit_tag_link_unit ON asset_unit_tag_link (unit_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asset_file_unit_id ON assetfile (asset_unit_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_assetfile_unit_role ON assetfile (asset_unit_id, role);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_telemetrylog_unit_action ON telemetrylog (unit_id, action);"))
        conn.commit()

    # 2. 初始化核心系统通用元类 (Universal Core System Facets)
    # 默认提供物理形态 (media_kind)、内容分类 (domain)、创作者/来源 (creator) 与整理状态 (workflow)，其余细分领域维度可通过预设模板或用户自建动态扩展
    with Session(engine) as session:
        from app.core.taxonomy_presets import apply_taxonomy_preset
        core_classes = [
            ("media_kind", "媒体形态", "film", "#3b82f6", True, True, "底层客观物理媒体形态 (音频/视频/图片/复合包)"),
            ("domain", "核心题材", "sparkles", "#8b5cf6", True, True, "通用内容分类、主题流派或领域层级树"),
            ("creator", "创作者/社团", "users", "#14b8a6", False, True, "作品创作者、艺术家、讲师、社团或出品方"),
            ("workflow", "状态分流", "git-branch", "#10b981", False, False, "资产处理与整理生命周期状态 (待整理/已归档)"),
        ]
        for code, name, icon, color, is_req, is_proj, desc in core_classes:
            existing = session.exec(select(TagClass).where(TagClass.code == code)).first()
            if not existing:
                tc = TagClass(
                    code=code,
                    display_name=name,
                    icon=icon,
                    color=color,
                    is_required=is_req,
                    is_projectable=is_proj,
                    description=desc,
                )
                session.add(tc)
        session.commit()

        if preset:
            apply_taxonomy_preset(session, preset)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
