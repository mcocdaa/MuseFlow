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

def init_db():
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

        # 2. 覆盖索引加固：消除回表，加速批量预加载与多维标签检索
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asset_unit_tag_link_covering ON asset_unit_tag_link (tag_id, unit_id, is_primary_landing);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asset_unit_tag_link_unit ON asset_unit_tag_link (unit_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asset_file_unit_id ON assetfile (asset_unit_id);"))
        conn.commit()

    # 2. 初始化核心标签族元类 (Default Tag Classes)
    with Session(engine) as session:
        default_classes = [
            ("media_kind", "媒体形态", "film", "#3b82f6"),
            ("domain", "题材流派", "sparkles", "#8b5cf6"),
            ("creator", "创作者/社团", "users", "#ec4899"),
            ("va", "声优/演职员", "mic", "#f59e0b"),
            ("workflow", "状态分流", "git-branch", "#10b981"),
        ]
        for code, name, icon, color in default_classes:
            existing = session.exec(select(TagClass).where(TagClass.code == code)).first()
            if not existing:
                tc = TagClass(code=code, display_name=name, icon=icon, color=color)
                session.add(tc)
        session.commit()

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
