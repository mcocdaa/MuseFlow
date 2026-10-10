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

import hashlib
import io

SPAM_ARTWORK_MD5S = {
    "31399c440b363b2fd8b172b1a07ade47",
    "0324b51d334737b085e9cd5412f8e342",
    "c83757c0ab2a5c0cc81cac7175487169",
    "471be5f05c3ea41ca7a3e8b723e7e9e2",
    "a2f5adef057567d6ab7d11c795823244",
}

def _is_spam_or_qr_artwork(artwork_data: bytes) -> bool:
    """Detect known promotional watermarks or binary QR-code images embedded in audio tags."""
    if not artwork_data:
        return True
    h = hashlib.md5(artwork_data).hexdigest()
    if h in SPAM_ARTWORK_MD5S:
        return True
    try:
        with Image.open(io.BytesIO(artwork_data)) as im:
            gray = im.convert("L").resize((64, 64), Image.Resampling.NEAREST)
            px = list(gray.tobytes())
            total = len(px)
            black = sum(1 for v in px if v < 25) / total
            white = sum(1 for v in px if v > 230) / total
            # Binary QR code signature: high contrast pure black + pure white modules
            if black > 0.18 and white > 0.45 and (black + white) > 0.90:
                return True
    except Exception:
        pass
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
                    if _is_spam_or_qr_artwork(artwork_data):
                        return False
                    with open(output_path, "wb") as f:
                        f.write(artwork_data)
                    return True
        # Check FLAC / OGG
        if hasattr(audio, "pictures") and audio.pictures:
            artwork_data = audio.pictures[0].data
            if _is_spam_or_qr_artwork(artwork_data):
                return False
            with open(output_path, "wb") as f:
                f.write(artwork_data)
            return True
    except Exception as e:
        print(f"Failed to extract audio artwork for {file_path}: {e}")
    return False

def ass_to_vtt(ass_content: str) -> str:
    """Converts Advanced SubStation Alpha (.ass) subtitle string to WebVTT format"""
    lines = ass_content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    vtt = ["WEBVTT\n"]

    # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    # Time format in ASS: 0:01:20.50 (H:MM:SS.cs)
    diag_pattern = re.compile(r"^Dialogue:\s*[^,]+,([^,]+),([^,]+),.*?,.*?,.*?,.*?,.*?,.*?,(.*)$")

    def ass_time_to_vtt(t_str: str) -> str:
        t_str = t_str.strip()
        parts = t_str.split(":")
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            sec_cs = parts[2].split(".")
            s = int(sec_cs[0])
            cs = int(sec_cs[1].ljust(3, "0")[:3]) if len(sec_cs) > 1 else 0
            return f"{h:02d}:{m:02d}:{s:02d}.{cs:03d}"
        return t_str

    for line in lines:
        line = line.strip()
        m = diag_pattern.match(line)
        if m:
            start_t, end_t, text = m.groups()
            vtt_start = ass_time_to_vtt(start_t)
            vtt_end = ass_time_to_vtt(end_t)
            # Strip ASS override tags like {\an8}, {\c&Hffffff&}, \N -> newline
            clean_text = re.sub(r"\{.*?\}", "", text).replace("\\N", "\n").replace("\\n", "\n").strip()
            if clean_text:
                vtt.append(f"{vtt_start} --> {vtt_end}\n{clean_text}\n")

    if len(vtt) == 1:
        return srt_to_vtt(ass_content)
    return "\n".join(vtt)

def get_media_dimensions_and_duration(file_path: Path) -> Tuple[Optional[int], Optional[int], Optional[float]]:
    """Returns (width, height, duration_seconds) using fast in-memory mutagen/PIL, with ffprobe for videos"""
    ext = file_path.suffix.lower()

    # 1. Fast in-memory image dimensions (<1ms)
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
        try:
            with Image.open(file_path) as img:
                return img.width, img.height, None
        except Exception:
            return None, None, None

    # 2. Fast in-memory audio duration via Mutagen (<2ms)
    if ext in (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".ape"):
        try:
            audio = MutagenFile(file_path)
            if audio is not None and getattr(audio, "info", None) and hasattr(audio.info, "length"):
                return None, None, float(audio.info.length)
        except Exception:
            pass

    # 3. Fallback to ffprobe for videos or complex container formats
    try:
        import json
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=width,height,duration,codec_type:format=duration",
            "-of", "json",
            str(file_path)
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=5).decode()
        probe_data = json.loads(out)

        width, height, duration = None, None, None

        # Check streams
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video" and width is None and height is None:
                w_val = stream.get("width")
                h_val = stream.get("height")
                if w_val and h_val:
                    width = int(w_val)
                    height = int(h_val)
            if duration is None and stream.get("duration"):
                try:
                    dur_val = float(stream["duration"])
                    if dur_val > 0:
                        duration = dur_val
                except (ValueError, TypeError):
                    pass

        # Check format duration fallback
        if duration is None and probe_data.get("format", {}).get("duration"):
            try:
                dur_val = float(probe_data["format"]["duration"])
                if dur_val > 0:
                    duration = dur_val
            except (ValueError, TypeError):
                pass

        return width, height, duration
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
