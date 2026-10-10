from pathlib import Path
from app.services.bundle_detector import analyze_folder_for_bundles

def test_bundle_detection(tmp_path: Path):
    # Setup mock files for a vlog bundle and an independent photo
    vlog_dir = tmp_path / "Tokyo_Trip"
    vlog_dir.mkdir()
    
    (vlog_dir / "tokyo_vlog.mp4").write_text("dummy video")
    (vlog_dir / "tokyo_vlog.srt").write_text("1\n00:00:01,000 --> 00:00:04,000\nHello Tokyo\n")
    (vlog_dir / "tokyo_vlog_bgm.wav").write_text("dummy audio")
    (vlog_dir / "shibuya_night.jpg").write_text("dummy image")

    all_files = list(vlog_dir.iterdir())
    units = analyze_folder_for_bundles(vlog_dir, all_files)

    # We expect 2 units: 1 bundle (tokyo_vlog) and 1 image (shibuya_night.jpg)
    assert len(units) == 2
    
    bundle_unit = next((u for u in units if u.unit_type == "bundle"), None)
    assert bundle_unit is not None
    assert bundle_unit.primary_file.name == "tokyo_vlog.mp4"
    assert len(bundle_unit.files) == 3 # primary + srt + wav
    
    companion_names = {f[0].name for f in bundle_unit.files}
    assert "tokyo_vlog.mp4" in companion_names
    assert "tokyo_vlog.srt" in companion_names
    assert "tokyo_vlog_bgm.wav" in companion_names

    image_unit = next((u for u in units if u.unit_type == "image"), None)
    assert image_unit is not None
    assert image_unit.primary_file.name == "shibuya_night.jpg"
