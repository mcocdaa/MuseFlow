import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_media"

def create_sample_image(path: Path, title: str, color: tuple):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1280, 720), color=color)
    draw = ImageDraw.Draw(img)
    # Draw simple frame & text
    draw.rectangle([40, 40, 1240, 680], outline=(255, 255, 255), width=4)
    draw.text((80, 100), f"MuseFlow Sample Media", fill=(255, 255, 255))
    draw.text((80, 160), title, fill=(255, 255, 255))
    img.save(path)

def create_sample_video(path: Path, title: str, duration: int = 5, bg_color: str = "blue"):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Generate test video with ffmpeg test pattern
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={bg_color}:s=1280x720:d={duration}",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-vf", f"drawtext=text='{title}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def create_sample_audio(path: Path, duration: int = 8, freq: int = 330):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration}",
        "-c:a", "pcm_s16le",
        str(path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def create_sample_subtitles(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = """1
00:00:00,500 --> 00:00:02,500
欢迎来到 MuseFlow 沉浸式流媒体播放器！

2
00:00:02,800 --> 00:00:04,800
这是自动挂载的同名 SRT 字幕，已通过 WebVTT 实时渲染。
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def generate_all():
    print("Generating sample media...")
    # 1. Travel Photos collection
    create_sample_image(SAMPLE_DIR / "Travel_Kyoto" / "fushimi_inari.png", "京都 · 伏见稻荷大社千本鸟居", (180, 50, 40))
    create_sample_image(SAMPLE_DIR / "Travel_Kyoto" / "arashiyama_bamboo.png", "京都 · 岚山竹林小道之夏", (34, 112, 60))
    
    # 2. Vlog Composite Bundle (mp4 + srt + wav) in dedicated project folder
    vlog_dir = SAMPLE_DIR / "Vlog_Series_2024" / "Tokyo_Vlog_Ep01"
    create_sample_video(vlog_dir / "tokyo_vlog.mp4", "Tokyo Vlog Ep.01 [主视频轨]", duration=6, bg_color="purple")
    create_sample_subtitles(vlog_dir / "tokyo_vlog.srt")
    create_sample_audio(vlog_dir / "tokyo_vlog_bgm.wav", duration=6, freq=520)

    # 3. Another standalone video
    create_sample_video(SAMPLE_DIR / "Shorts" / "autumn_walk.mp4", "秋日午后散步 · 4K", duration=4, bg_color="darkgreen")

    # 4. Music Audio
    create_sample_audio(SAMPLE_DIR / "Music_Lofi" / "midnight_chill_piano.wav", duration=15, freq=261)

    # 5. Scattered media
    create_sample_image(SAMPLE_DIR / "scattered_sunset.png", "散落未整理 · 傍晚海滩日落", (220, 100, 30))

    print(f"Sample media successfully generated at {SAMPLE_DIR}!")

if __name__ == "__main__":
    generate_all()
