import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
_env_data_dir = os.getenv("MUSEFLOW_DATA_DIR")
DATA_DIR = Path(_env_data_dir).resolve() if _env_data_dir else BASE_DIR / "data"
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
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".heic", ".raw", ".cr2", ".nef", ".arw"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".m4v"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".ape"}
# Subtitles and companion lyric/cue files
SUPPORTED_SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".sub", ".lrc", ".slc", ".cue"}

ALL_MEDIA_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_VIDEO_EXTS | SUPPORTED_AUDIO_EXTS | SUPPORTED_SUBTITLE_EXTS

# AI LLM Settings
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://pool.creative-koala-llm.top/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-ad3e4bdafe5c4c832cefe1562eb82dce20c2d103b54716cf266c7a4a0cf1fa5f")
LLM_MODEL = os.getenv("LLM_MODEL", "grok-4.7")
