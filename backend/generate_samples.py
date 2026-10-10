import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_media"
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

def get_font(size: int = 36):
    if os.path.exists(FONT_PATH):
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()

def create_gradient_image(width: int, height: int, start_color: tuple, end_color: tuple) -> Image.Image:
    """Create a high-aesthetic diagonal gradient canvas with subtle glass accents"""
    base = Image.new('RGB', (width, height), start_color)
    top = Image.new('RGB', (width, height), end_color)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        for x in range(width):
            # Diagonal gradient factor
            val = int(255 * ((x / width * 0.45) + (y / height * 0.55)))
            mask_data.append(min(255, max(0, val)))
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

def create_sample_image(
    path: Path,
    title: str,
    category: str,
    start_color: tuple,
    end_color: tuple,
    meta_text: str = "MuseFlow · 4K Ultra HD Digital Collection"
):
    path.parent.mkdir(parents=True, exist_ok=True)
    base = create_gradient_image(1280, 800, start_color, end_color).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_title = get_font(48)
    font_sub = get_font(24)
    font_badge = get_font(20)

    # Outer subtle frosted card outline
    draw.rounded_rectangle([36, 36, 1244, 764], radius=24, outline=(255, 255, 255, 45), width=2)
    
    # Elegant subtle decorative geometry in background (modern abstract circles)
    draw.ellipse([850, -50, 1350, 450], outline=(255, 255, 255, 30), width=2)
    draw.ellipse([920, 20, 1280, 380], outline=(255, 255, 255, 20), width=1)

    # Technical badge (top right, subtle translucent dark glass)
    draw.rounded_rectangle([1040, 60, 1210, 105], radius=12, fill=(0, 0, 0, 90), outline=(255, 255, 255, 45))
    draw.text((1065, 72), "4K · HDR", fill=(240, 240, 255, 220), font=font_badge)

    # Category chip (bottom left above title)
    chip_w = max(110, len(category) * 26 + 32)
    draw.rounded_rectangle([64, 530, 64 + chip_w, 572], radius=10, fill=(255, 255, 255, 35), outline=(255, 255, 255, 55))
    draw.text((80, 540), category, fill=(255, 255, 255, 240), font=font_badge)

    # Title & Metadata
    draw.text((64, 600), title, fill=(255, 255, 255, 255), font=font_title)
    draw.text((64, 675), meta_text, fill=(220, 225, 240, 210), font=font_sub)

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    final_img.save(path, quality=94)

def create_sample_video(
    path: Path,
    title: str,
    category: str,
    duration: int = 5,
    start_color: tuple = (25, 20, 65),
    end_color: tuple = (95, 35, 140),
    meta_text: str = "Shot on Sony FX3 · 4K 60FPS · 10-bit 4:2:2"
):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_cover = path.with_suffix(".temp_cover.png")
    create_sample_image(temp_cover, title, category, start_color, end_color, meta_text)

    # Render animated video with smooth subtle camera zoom motion
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(temp_cover),
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-vf", "scale=1280:720,zoompan=z='min(zoom+0.0006,1.05)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-t", str(duration),
        str(path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if temp_cover.exists():
        temp_cover.unlink()

def create_sample_audio_with_cover(
    audio_path: Path,
    title: str,
    artist: str,
    duration: int = 15,
    freq: int = 330
):
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    # Generate WAV audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration}",
        "-c:a", "pcm_s16le",
        str(audio_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Generate companion album cover art
    cover_path = audio_path.parent / "cover.png"
    create_sample_image(
        cover_path,
        title,
        "HI-RES AUDIO",
        start_color=(20, 24, 45),
        end_color=(125, 45, 120),
        meta_text=f"Artist: {artist} · 24-bit 96kHz Lossless Master"
    )

def create_sample_subtitles(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = """1
00:00:00.500 --> 00:00:02.500
欢迎来到 MuseFlow 沉浸式流媒体播放器！

2
00:00:02.800 --> 00:00:04.800
这是自动挂载的同名 SRT 字幕，已通过 WebVTT 实时渲染。
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def generate_all():
    print("Regenerating modern, high-aesthetic sample media library...")
    # Clean previous sample folder to prevent stale files
    if SAMPLE_DIR.exists():
        shutil.rmtree(SAMPLE_DIR)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Travel Photos collection (Kyoto)
    create_sample_image(
        SAMPLE_DIR / "Travel_Kyoto" / "fushimi_inari.png",
        "京都 · 伏见稻荷大社千本鸟居",
        "风景纪实",
        (190, 45, 30),
        (245, 120, 50),
        "Fuji X-T5 · XF 16-55mm F2.8 · Velvia Film Sim"
    )
    create_sample_image(
        SAMPLE_DIR / "Travel_Kyoto" / "arashiyama_bamboo.png",
        "京都 · 岚山竹林小道静谧之夏",
        "夏日旅拍",
        (15, 80, 55),
        (45, 165, 115),
        "Sony A7R5 · FE 24-70mm GM II · Morning Mist"
    )

    # 2. Vlog Composite Bundle (mp4 + srt + wav) in dedicated project folder
    vlog_dir = SAMPLE_DIR / "Vlog_Series_2024" / "Tokyo_Vlog_Ep01"
    create_sample_video(
        vlog_dir / "tokyo_vlog.mp4",
        "Tokyo Vlog Ep.01 · 漫步秋叶原",
        "城市记录",
        duration=6,
        start_color=(30, 20, 80),
        end_color=(150, 40, 160),
        meta_text="Panasonic S5M2X · 4K 60P ProRes · V-Log"
    )
    create_sample_subtitles(vlog_dir / "tokyo_vlog.srt")
    create_sample_audio_with_cover(vlog_dir / "tokyo_vlog_bgm.wav", "秋叶原午夜漫游 BGM", "MuseFlow Beat", duration=6, freq=520)

    # 3. Standalone video (Shorts)
    create_sample_video(
        SAMPLE_DIR / "Shorts" / "autumn_walk.mp4",
        "秋日午后散步 · 黄金森林漫游",
        "短片创作",
        duration=5,
        start_color=(15, 75, 45),
        end_color=(185, 115, 30),
        meta_text="Sony A7M4 · 35mm F1.4 GM · S-Cinetone 4K"
    )

    # 4. Music Audio with companion cover art
    create_sample_audio_with_cover(
        SAMPLE_DIR / "Music_Lofi" / "midnight_chill_piano.wav",
        "深夜静谧钢琴曲 · Midnight Chill",
        "MuseFlow Lo-Fi Records",
        duration=15,
        freq=261
    )

    # 5. Scattered media (Single Photo)
    create_sample_image(
        SAMPLE_DIR / "scattered_sunset.png",
        "散落未整理 · 傍晚海滩日落",
        "生活拾光",
        (215, 55, 90),
        (245, 160, 60),
        "Leica Q3 · Summilux 28mm F1.7 · Sunset Glow"
    )

    # 6. Complex Project A (nested sub-series)
    project_a = SAMPLE_DIR / "Project_Complex_A"
    create_sample_image(
        project_a / "a1.png",
        "A主工程 · 概念设计草图",
        "概念设计",
        (25, 35, 85),
        (55, 95, 165),
        "Figma · Vector Wireframe Component Spec v2.4"
    )
    create_sample_image(
        project_a / "a2.png",
        "A主工程 · 界面交互动态规范",
        "视觉系统",
        (35, 25, 80),
        (95, 55, 155),
        "After Effects · Motion Guidelines · 60fps Lottie"
    )

    sub_b = project_a / "Sub_Project_B"
    create_sample_image(
        sub_b / "b1.png",
        "B子项目 · 空间渲染概念稿 01",
        "3D渲染",
        (15, 65, 85),
        (35, 145, 165),
        "Blender 4.2 · Cycles Ray Tracing · 3840x2160"
    )
    create_sample_image(
        sub_b / "b2.png",
        "B子项目 · 空间材质贴图 02",
        "材质工程",
        (25, 75, 80),
        (45, 165, 145),
        "Substance 3D · 8K PBR Textures · Octane Render"
    )

    # Cross-folder Vlog bundle inside Project A
    cross_dir = project_a / "Cross_Folder_Vlog"
    create_sample_video(
        cross_dir / "render_vlog.mp4",
        "渲染成果展示 · 项目汇报终版",
        "汇报宣讲",
        duration=5,
        start_color=(15, 30, 80),
        end_color=(45, 110, 180),
        meta_text="DaVinci Resolve Studio · Rec.709 · Master 4K"
    )
    create_sample_subtitles(cross_dir / "render_vlog.srt")
    create_sample_audio_with_cover(cross_dir / "render_vlog_bgm.wav", "项目汇报终版 背景配乐", "Studio Master", duration=5, freq=440)

    print(f"Sample media successfully generated at {SAMPLE_DIR}!")

if __name__ == "__main__":
    generate_all()
