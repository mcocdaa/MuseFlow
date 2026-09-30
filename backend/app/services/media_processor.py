import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from mutagen import File as MutagenFile
from app.core.config import THUMBNAILS_DIR

def srt_to_vtt(srt_content: str) -> str:
    """Converts SubRip (.srt) subtitle string to WebVTT format for browser <track>"""
    # Replace comma in timestamps: 00:01:20,000 --> 00:01:20.000
    vtt = "WEBVTT\n\n"
    # Normalize line endings
    content = srt_content.replace("\r\n", "\n").replace("\r", "\n")
    # Pattern for timestamp line
    pattern = re.compile(r"(\d{2}:\d{2}:\d{2}),(\d{3}) --> (\d{2}:\d{2}:\d{2}),(\d{3})")
    content = pattern.sub(r"\1.\2 --> \3.\4", content)
    return vtt + content

def extract_image_thumbnail(file_path: Path, output_path: Path, max_size: int = 800) -> bool:
    try:
        with Image.open(file_path) as img:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, "JPEG", quality=85)
            return True
    except Exception as e:
        print(f"Failed to generate image thumbnail for {file_path}: {e}")
        return False

def extract_video_thumbnail(file_path: Path, output_path: Path, time_offset: str = "00:00:01") -> bool:
    try:
        # Use ffmpeg to grab a frame
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", time_offset,
            "-i", str(file_path),
            "-vframes", "1",
            "-vf", "scale='min(800,iw)':-2",
            "-q:v", "3",
            str(output_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return res.returncode == 0 and output_path.exists()
    except Exception as e:
        print(f"Failed to generate video thumbnail for {file_path}: {e}")
        return False

def extract_audio_artwork(file_path: Path, output_path: Path) -> bool:
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return False
        
        # Check ID3 APIC
        if hasattr(audio, "tags") and audio.tags:
            for key in audio.tags.keys():
                if key.startswith("APIC:"):
                    artwork_data = audio.tags[key].data
                    with open(output_path, "wb") as f:
                        f.write(artwork_data)
                    return True
        # Check FLAC / OGG
        if hasattr(audio, "pictures") and audio.pictures:
            artwork_data = audio.pictures[0].data
            with open(output_path, "wb") as f:
                f.write(artwork_data)
            return True
    except Exception as e:
        print(f"Failed to extract audio artwork for {file_path}: {e}")
    return False

def get_media_dimensions_and_duration(file_path: Path) -> Tuple[Optional[int], Optional[int], Optional[float]]:
    """Returns (width, height, duration_seconds) using ffprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=8).decode()
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        
        width, height, duration = None, None, None
        for line in lines:
            try:
                val = float(line)
                if duration is None and val > 0:
                    duration = val
                elif width is None and val.is_integer() and val > 10:
                    width = int(val)
                elif height is None and val.is_integer() and val > 10:
                    height = int(val)
            except ValueError:
                continue
        return width, height, duration
    except Exception:
        # Fallback for PIL images
        try:
            with Image.open(file_path) as img:
                return img.width, img.height, None
        except Exception:
            return None, None, None

def get_or_create_unit_thumbnail(unit_id: int, file_path: str, unit_type: str) -> Optional[str]:
    """Ensures a thumbnail exists on disk and returns its file path"""
    src_path = Path(file_path)
    if not src_path.exists():
        return None
        
    thumb_filename = f"thumb_{unit_id}.jpg"
    thumb_path = THUMBNAILS_DIR / thumb_filename
    if thumb_path.exists():
        return str(thumb_path)

    success = False
    if unit_type in ("image",):
        success = extract_image_thumbnail(src_path, thumb_path)
    elif unit_type in ("video", "bundle"):
        success = extract_video_thumbnail(src_path, thumb_path)
    elif unit_type in ("audio",):
        success = extract_audio_artwork(src_path, thumb_path)

    if success and thumb_path.exists():
        return str(thumb_path)
    return None
