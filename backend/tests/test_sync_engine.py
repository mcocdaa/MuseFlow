import os
import tempfile
import pytest
from pathlib import Path
from sqlmodel import Session, select
from app.core.db import engine, init_db
from app.models.entities import (
    Collection,
    AssetUnit,
    AssetFile,
    AssetUnitTagLink,
    TagClass,
    Tag,
)
from app.services.sync_engine import (
    check_mount_status,
    wipe_media_database,
    sync_library_changes,
    wipe_and_rebuild_all,
)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_check_mount_status():
    status = check_mount_status()
    assert isinstance(status, dict)
    assert "is_mounted" in status
    assert "mount_point" in status
    assert "valid_roots" in status

def test_wipe_and_sync_pipeline():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Create a mock media directory structure
        work_dir = tmp_path / "[AB888888] 同步引擎测试作品"
        work_dir.mkdir(parents=True, exist_ok=True)
        sample_audio = work_dir / "main_track.mp3"
        sample_audio.write_bytes(b"\x00" * 1024)
        sample_cover = work_dir / "cover.jpg"
        sample_cover.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 500)

        with Session(engine) as session:
            # 1. Test initial sync on mock directory
            sync_res = sync_library_changes(session, root_paths=[str(tmp_path)], prune_missing=True)
            assert sync_res["status"] == "success"
            assert sync_res["added_units"] >= 1
            assert sync_res["added_files"] >= 2

            # Verify assets exist
            units = session.exec(select(AssetUnit)).all()
            assert len(units) >= 1
            files = session.exec(select(AssetFile)).all()
            assert len(files) >= 2

            # Verify TagClass & Tag definitions are intact
            tag_classes = session.exec(select(TagClass)).all()
            assert len(tag_classes) > 0
            tags = session.exec(select(Tag)).all()
            assert len(tags) > 0

            # 2. Test prune when a file is removed
            os.remove(sample_audio)
            prune_res = sync_library_changes(session, root_paths=[str(tmp_path)], prune_missing=True)
            assert prune_res["status"] == "success"
            assert prune_res["pruned_files"] >= 1

            # 3. Test wipe_media_database
            wipe_res = wipe_media_database(session)
            assert isinstance(wipe_res, dict)
            # TagClass and Tag should still exist!
            remaining_tags = session.exec(select(Tag)).all()
            assert len(remaining_tags) == len(tags)
            # While media files and units should be 0
            assert len(session.exec(select(AssetFile)).all()) == 0
            assert len(session.exec(select(AssetUnit)).all()) == 0
