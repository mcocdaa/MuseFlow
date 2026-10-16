import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.core.db import get_session
from app.core.config import MUSEFLOW_NAS_MOUNT
from app.models.entities import AssetFile, AssetUnit, Collection
from app.services.media_processor import srt_to_vtt, lrc_to_vtt

client = TestClient(app)

@pytest.fixture
def session_fixture():
    session = next(get_session())
    yield session

def test_http_206_range_streaming(session_fixture: Session):
    """验证流媒体 HTTP 206 Byte Range 分片传输协议及 416 越界防御"""
    unit = AssetUnit(title="Range Test Unit", unit_type="video")
    session_fixture.add(unit)
    session_fixture.commit()
    session_fixture.refresh(unit)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        data = bytes([i % 256 for i in range(5000)])
        tmp.write(data)
        tmp.flush()
        file_path = Path(tmp.name)

    asset_file = AssetFile(
        file_path=str(file_path),
        file_name="range_sample.mp4",
        extension=".mp4",
        mime_type="video/mp4",
        file_size=len(data),
        modified_at=unit.created_at,
        asset_unit_id=unit.id,
        role="primary"
    )
    session_fixture.add(asset_file)
    session_fixture.commit()
    session_fixture.refresh(asset_file)

    try:
        # 1. 规范分片 0-499
        res = client.get(f"/api/stream/file/{asset_file.id}", headers={"Range": "bytes=0-499"})
        assert res.status_code == 206
        assert res.headers["Content-Range"] == "bytes 0-499/5000"
        assert res.headers["Content-Length"] == "500"
        assert res.content == data[:500]

        # 2. 尾部分片 4500-
        res_end = client.get(f"/api/stream/file/{asset_file.id}", headers={"Range": "bytes=4500-"})
        assert res_end.status_code == 206
        assert res_end.headers["Content-Range"] == "bytes 4500-4999/5000"
        assert res_end.headers["Content-Length"] == "500"
        assert res_end.content == data[4500:]

        # 3. 越界分片 5000- -> 应返回 416
        res_oob = client.get(f"/api/stream/file/{asset_file.id}", headers={"Range": "bytes=5000-"})
        assert res_oob.status_code == 416

        # 4. 逆向非法分片 500-200 (start > end) -> 应返回 416 防止产生负 Content-Length
        res_inv = client.get(f"/api/stream/file/{asset_file.id}", headers={"Range": "bytes=500-200"})
        assert res_inv.status_code == 416

        # 5. 音频/视频/图片类型化快捷别名路由探针
        res_video = client.get(f"/api/stream/video/{asset_file.id}", headers={"Range": "bytes=0-100"})
        assert res_video.status_code == 206
        res_audio = client.get(f"/api/stream/audio/{asset_file.id}", headers={"Range": "bytes=0-100"})
        assert res_audio.status_code == 206
        res_img = client.get(f"/api/stream/image/{asset_file.id}")
        assert res_img.status_code == 200
        res_cov = client.get(f"/api/stream/cover/{unit.id}")
        # unit thumbnail generation attempt (200 or 404 depending on file content, but not 500 or route not found)
        assert res_cov.status_code in (200, 404)

    finally:
        session_fixture.delete(asset_file)
        session_fixture.delete(unit)
        session_fixture.commit()
        if file_path.exists():
            file_path.unlink()

def test_subtitle_webvtt_streaming_and_encodings(session_fixture: Session):
    """验证 WebVTT 转换协议以及多字符编码 (UTF-8, GBK) 自动探测容错"""
    unit = AssetUnit(title="Subtitle Test Unit", unit_type="bundle")
    session_fixture.add(unit)
    session_fixture.commit()
    session_fixture.refresh(unit)

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. UTF-8 SRT 字幕
        p_utf8 = Path(tmpdir) / "test_utf8.srt"
        p_utf8.write_text("1\n00:00:01,500 --> 00:00:03,000\nHello UTF8 Subtitle\n", encoding="utf-8")
        f_utf8 = AssetFile(
            file_path=str(p_utf8), file_name="test_utf8.srt", extension=".srt",
            mime_type="text/plain", file_size=p_utf8.stat().st_size,
            modified_at=unit.created_at, asset_unit_id=unit.id, role="subtitle"
        )
        session_fixture.add(f_utf8)

        # 2. GBK 中文编码 SRT 字幕
        p_gbk = Path(tmpdir) / "test_gbk.srt"
        p_gbk.write_bytes("1\n00:00:01,000 --> 00:00:04,000\n简体中文GBK字幕测试\n".encode("gbk"))
        f_gbk = AssetFile(
            file_path=str(p_gbk), file_name="test_gbk.srt", extension=".srt",
            mime_type="text/plain", file_size=p_gbk.stat().st_size,
            modified_at=unit.created_at, asset_unit_id=unit.id, role="subtitle"
        )
        session_fixture.add(f_gbk)

        # 3. LRC 歌词转 WebVTT
        p_lrc = Path(tmpdir) / "test_lyrics.lrc"
        p_lrc.write_text("[00:02.50]第一句歌词\n[00:06.80]第二句歌词\n", encoding="utf-8")
        f_lrc = AssetFile(
            file_path=str(p_lrc), file_name="test_lyrics.lrc", extension=".lrc",
            mime_type="text/plain", file_size=p_lrc.stat().st_size,
            modified_at=unit.created_at, asset_unit_id=unit.id, role="lyrics"
        )
        session_fixture.add(f_lrc)
        session_fixture.commit()

        # 4. ASS 特效字幕转 WebVTT
        p_ass = Path(tmpdir) / "test_ass.ass"
        p_ass.write_text(
            "[Script Info]\nTitle: Test ASS\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:01.20,0:00:03.50,Default,,0,0,0,,{\\pos(192,200)}ASS特效字幕内容\\N第二行文本\n",
            encoding="utf-8"
        )
        f_ass = AssetFile(
            file_path=str(p_ass), file_name="test_ass.ass", extension=".ass",
            mime_type="text/plain", file_size=p_ass.stat().st_size,
            modified_at=unit.created_at, asset_unit_id=unit.id, role="subtitle"
        )
        session_fixture.add(f_ass)
        session_fixture.commit()

        # 验证 UTF-8 SRT -> text/vtt
        res_utf8 = client.get(f"/api/stream/subtitle/{f_utf8.id}")
        assert res_utf8.status_code == 200
        assert res_utf8.headers["content-type"].startswith("text/vtt")
        assert "WEBVTT" in res_utf8.text
        assert "00:00:01.500 --> 00:00:03.000" in res_utf8.text

        # 验证 GBK 自动检测解码 -> text/vtt
        res_gbk = client.get(f"/api/stream/subtitle/{f_gbk.id}")
        assert res_gbk.status_code == 200
        assert "简体中文GBK字幕测试" in res_gbk.text

        # 验证 LRC -> text/vtt
        res_lrc = client.get(f"/api/stream/subtitle/{f_lrc.id}")
        assert res_lrc.status_code == 200
        assert "WEBVTT" in res_lrc.text
        assert "00:00:02.500 -->" in res_lrc.text

        # 验证 ASS -> text/vtt (去除特效标签并标准化时间戳)
        res_ass = client.get(f"/api/stream/subtitle/{f_ass.id}")
        assert res_ass.status_code == 200
        assert "WEBVTT" in res_ass.text
        assert "00:00:01.200 --> 00:00:03.500" in res_ass.text
        assert "ASS特效字幕内容" in res_ass.text

        # 清理
        session_fixture.delete(f_utf8)
        session_fixture.delete(f_gbk)
        session_fixture.delete(f_lrc)
        session_fixture.delete(f_ass)
        session_fixture.delete(unit)
        session_fixture.commit()

def test_stream_fault_tolerance(session_fixture: Session):
    """验证当物理文件缺失或 NAS 网络离线时，接口返回优雅的 404/503 而非未捕获 500 崩溃"""
    unit = AssetUnit(title="Fault Tolerance Unit", unit_type="video")
    session_fixture.add(unit)
    session_fixture.commit()
    session_fixture.refresh(unit)

    # 1. 模拟一个指向未挂载网络 NAS 路径的记录
    nas_file = AssetFile(
        file_path=f"{MUSEFLOW_NAS_MOUNT}/non_existent_mock_share/sample.mp4",
        file_name="sample.mp4",
        extension=".mp4",
        mime_type="video/mp4",
        file_size=1024,
        modified_at=unit.created_at,
        asset_unit_id=unit.id,
        role="primary"
    )
    # 2. 模拟一个指向本地不存在文件的记录
    local_missing_file = AssetFile(
        file_path="/var/tmp/non_existent_museflow_file_98765.mp4",
        file_name="missing.mp4",
        extension=".mp4",
        mime_type="video/mp4",
        file_size=1024,
        modified_at=unit.created_at,
        asset_unit_id=unit.id,
        role="primary"
    )
    session_fixture.add(nas_file)
    session_fixture.add(local_missing_file)
    session_fixture.commit()

    try:
        # NAS 离线流媒体请求：应优雅返回 503
        res_nas = client.get(f"/api/stream/file/{nas_file.id}")
        assert res_nas.status_code == 503
        assert "NAS 存储设备暂时离线" in res_nas.json()["detail"]

        # 本地缺失文件请求：应优雅返回 404
        res_local = client.get(f"/api/stream/file/{local_missing_file.id}")
        assert res_local.status_code == 404
        assert "Physical file not found on disk" in res_local.json()["detail"]

        # 不存在的 ID：应优雅返回 404
        res_404 = client.get("/api/stream/file/9999999")
        assert res_404.status_code == 404

    finally:
        session_fixture.delete(nas_file)
        session_fixture.delete(local_missing_file)
        session_fixture.delete(unit)
        session_fixture.commit()

def test_recommend_feed_contract():
    """验证推荐流系列聚合 (mode=series) 与单品展开 (mode=unit) 的数据形态契约"""
    # 1. 验证 series 模式契约
    res_series = client.get("/api/recommend/feed?mode=series&limit=10")
    assert res_series.status_code == 200
    cards_series = res_series.json()
    assert isinstance(cards_series, list)

    for c in cards_series:
        assert "card_id" in c
        assert c["card_id"].startswith("col_") or c["card_id"].startswith("unit_")
        assert "title" in c and c["title"] is not None
        assert "unit_type" in c
        assert "unit_count" in c and c["unit_count"] >= 1
        assert "tags" in c and isinstance(c["tags"], list)
        assert "media_breakdown" in c

    # 2. 验证 unit 模式契约
    res_unit = client.get("/api/recommend/feed?mode=unit&limit=10")
    assert res_unit.status_code == 200
    cards_unit = res_unit.json()
    assert isinstance(cards_unit, list)

    for c in cards_unit:
        assert "card_id" in c
        assert c["card_id"].startswith("unit_")
        assert "title" in c and c["title"] is not None
        assert "unit_type" in c
        assert c["is_series"] is False
        assert c["unit_count"] >= 1
        assert "tags" in c and isinstance(c["tags"], list)
        assert "files" in c and isinstance(c["files"], list)
        assert "media_breakdown" in c and isinstance(c["media_breakdown"], dict)
        assert c["media_breakdown"]["total"] >= 1
