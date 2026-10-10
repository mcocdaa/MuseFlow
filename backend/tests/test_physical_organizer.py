import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.entities import Collection, AssetUnit, AssetFile
from app.services.physical_organizer import (
    acquire_maintenance_lock,
    release_maintenance_lock,
    get_active_maintenance_locks,
    is_folder_in_maintenance,
    plan_rj_normalization_and_dates,
    plan_rj_separate_untranslated,
    plan_interactive_topology,
    execute_triage_plan,
)

def test_maintenance_locks():
    folder = "/tmp/test_organize_lock"
    assert not is_folder_in_maintenance(folder)
    acquire_maintenance_lock(folder, "正在进行整理测试")
    assert is_folder_in_maintenance(folder) is not None
    assert is_folder_in_maintenance(folder + "/sub") is not None
    assert len(get_active_maintenance_locks()) > 0
    release_maintenance_lock(folder)
    assert not is_folder_in_maintenance(folder)

def test_physical_organize_rj_and_execute():
    temp_dir = Path(tempfile.mkdtemp(prefix="museflow_test_org_"))
    try:
        # Create mock RJ folder with old non-standard name
        old_rj_folder = temp_dir / "RJ123456 甜蜜耳语与日常陪伴（原版）"
        old_rj_folder.mkdir(parents=True)
        sample_audio = old_rj_folder / "track01.mp3"
        sample_audio.write_bytes(b"dummy audio content")

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Mock collection & file
            col = Collection(name="RJ123456 甜蜜耳语", folder_path=str(old_rj_folder))
            session.add(col)
            session.commit()
            session.refresh(col)

            unit = AssetUnit(title="track01", unit_type="audio", collection_id=col.id)
            session.add(unit)
            session.commit()
            session.refresh(unit)

            f_rec = AssetFile(
                file_path=str(sample_audio),
                file_name="track01.mp3",
                extension=".mp3",
                mime_type="audio/mpeg",
                file_size=100,
                modified_at=datetime.now(timezone.utc),
                asset_unit_id=unit.id,
                role="primary"
            )
            session.add(f_rec)
            session.commit()

            # 1. Plan normalization and dates
            plan = plan_rj_normalization_and_dates(
                session=session,
                target_folder_str=str(temp_dir),
                rename_template="[RJ123456] 甜蜜耳语与日常陪伴",
                update_mtime_to_release=True
            )
            assert len(plan.actions) > 0
            
            # Dry run test
            res_dry = execute_triage_plan(session, plan, dry_run=True)
            assert res_dry["status"] == "dry_run"
            assert old_rj_folder.exists() # Nothing changed

            # Real execution
            res_exec = execute_triage_plan(session, plan, dry_run=False)
            assert res_exec["status"] == "success"

            # Check physical file movement
            new_folder = temp_dir / "[RJ123456] 甜蜜耳语与日常陪伴"
            assert new_folder.exists()
            assert (new_folder / "track01.mp3").exists()

            # Check database synchronization
            session.refresh(col)
            assert col.folder_path == str(new_folder)
            
            session.refresh(f_rec)
            assert f_rec.file_path == str(new_folder / "track01.mp3")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_interactive_image_topology():
    temp_dir = Path(tempfile.mkdtemp(prefix="museflow_test_img_"))
    try:
        # Create loose files
        img1 = temp_dir / "genshin_raiden.png"
        img1.write_bytes(b"image 1")
        img2 = temp_dir / "genshin_furina.png"
        img2.write_bytes(b"image 2")
        img3 = temp_dir / "landscape_nature.jpg"
        img3.write_bytes(b"image 3")

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            f1 = AssetFile(file_path=str(img1), file_name="genshin_raiden.png", extension=".png", mime_type="image/png", file_size=10, modified_at=datetime.now(timezone.utc))
            session.add(f1)
            session.commit()

            # Plan custom topology
            topology = {
                "插画/原神": ["genshin_*"],
                "壁纸/风景": ["landscape_*"],
            }
            plan = plan_interactive_topology(session, str(temp_dir), topology, "按角色与题材分类")
            assert len(plan.actions) >= 4 # 2 create_dirs + 3 move_files

            # Execute
            res = execute_triage_plan(session, plan, dry_run=False)
            assert res["status"] == "success"

            # Verify physical structure
            assert (temp_dir / "插画" / "原神" / "genshin_raiden.png").exists()
            assert (temp_dir / "插画" / "原神" / "genshin_furina.png").exists()
            assert (temp_dir / "壁纸" / "风景" / "landscape_nature.jpg").exists()

            # Verify DB sync
            session.refresh(f1)
            assert f1.file_path == str(temp_dir / "插画" / "原神" / "genshin_raiden.png")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
