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

def lrc_to_vtt(lrc_content: str) -> str:
    """Converts LRC format to WebVTT format for browser <track>"""
    lines = lrc_content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    entries = []
    # Pattern: [mm:ss.xx] or [mm:ss:xx]
    pattern = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\](.*)")
    for line in lines:
        line = line.strip()
        m = pattern.match(line)
        if m:
            mins, secs, frac, text = m.groups()
            text = text.strip()
            total_sec = int(mins) * 60 + int(secs)
            ms = int(frac.ljust(3, "0")[:3]) if frac else 0
            start_sec = total_sec + (ms / 1000.0)
            entries.append((start_sec, text))
    
    if not entries:
        return "WEBVTT\n\n"
    
    entries.sort(key=lambda x: x[0])
    vtt = ["WEBVTT\n"]
    for i, (start_sec, text) in enumerate(entries):
        if not text:
            continue
        if i + 1 < len(entries):
            end_sec = min(entries[i+1][0], start_sec + 10.0)
        else:
            end_sec = start_sec + 6.0
        if end_sec <= start_sec:
            end_sec = start_sec + 2.0
            
        def fmt_vtt_time(s: float) -> str:
            hrs = int(s // 3600)
            mins = int((s % 3600) // 60)
            secs = int(s % 60)
            ms = int(round((s - int(s)) * 1000))
            return f"{hrs:02d}:{mins:02d}:{secs:02d}.{ms:03d}"
            
        vtt.append(f"{fmt_vtt_time(start_sec)} --> {fmt_vtt_time(end_sec)}\n{text}\n")
        
    return "\n".join(vtt)

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

def extract_video_thumbnail(file_path: Path, output_path: Path, time_offset: str = "00:00:00.5") -> bool:
    try:
        # Use ffmpeg to grab a frame
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", time_offset,
            "-i", str(file_path),
            "-vframes", "1",
            "-update", "1",
            "-vf", "scale='min(800,iw)':-2",
            "-q:v", "3",
            str(output_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if res.returncode == 0 and output_path.exists():
            return True

        # Fallback to first frame without -ss offset
        cmd_fallback = [
            "ffmpeg",
            "-y",
            "-i", str(file_path),
            "-vframes", "1",
            "-update", "1",
            "-vf", "scale='min(800,iw)':-2",
            "-q:v", "3",
            str(output_path)
        ]
        res = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
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
        if not success:
            # Fallback: check for companion album art in same folder (cover.jpg, folder.jpg, {stem}.png, etc.)
            for cand_name in (f"{src_path.stem}.png", f"{src_path.stem}.jpg", "cover.png", "cover.jpg", "folder.jpg", "folder.png"):
                cand = src_path.parent / cand_name
                if cand.exists() and cand.is_file():
                    success = extract_image_thumbnail(cand, thumb_path)
                    if success:
                        break

    if success and thumb_path.exists():
        return str(thumb_path)
    return None
