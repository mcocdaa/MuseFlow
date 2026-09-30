import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "db"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"

DB_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_DIR / 'museflow.db'}"

# Host & Port
SERVER_HOST = os.getenv("MUSEFLOW_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("MUSEFLOW_PORT", "8765"))

# Max telemetry dwell time cap in seconds (prevents overnight window inflation)
MAX_DWELL_SECONDS = 180.0

# Supported media extensions
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".heic"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"}
SUPPORTED_SUBTITLE_EXTS = {".srt", ".vtt", ".ass"}

ALL_MEDIA_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_VIDEO_EXTS | SUPPORTED_AUDIO_EXTS | SUPPORTED_SUBTITLE_EXTS
