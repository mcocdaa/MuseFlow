from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.core.config import (
    SUPPORTED_IMAGE_EXTS,
    SUPPORTED_VIDEO_EXTS,
    SUPPORTED_AUDIO_EXTS,
    SUPPORTED_SUBTITLE_EXTS
)

class DetectedUnit:
    def __init__(self, title: str, unit_type: str, primary_file: Path):
        self.title = title
        self.unit_type = unit_type
        self.primary_file = primary_file
        self.files: List[Tuple[Path, str]] = [(primary_file, "primary")] # (path, role)

    def add_file(self, file_path: Path, role: str):
        self.files.append((file_path, role))

def analyze_folder_for_bundles(folder_path: Path, file_paths: List[Path]) -> List[DetectedUnit]:
    """
    智能聚类算法：将一个文件夹内的散落物理文件归拢为原子消费单元 (AssetUnit)。
    重点解决：
    1. 同名复合包 (vlog.mp4 + vlog.srt + vlog.wav)
    2. 项目文件夹型复合包 (一个文件夹内包含单个视频和其附属的字幕/音轨)
    3. 独立多媒体 (独立单图、独立单曲、独立视频)
    """
    units: List[DetectedUnit] = []
    
    # 统计扩展名分组
    video_files: List[Path] = []
    audio_files: List[Path] = []
    subtitle_files: List[Path] = []
    image_files: List[Path] = []
    
    for f in file_paths:
        ext = f.suffix.lower()
        if ext in SUPPORTED_VIDEO_EXTS:
            video_files.append(f)
        elif ext in SUPPORTED_AUDIO_EXTS:
            audio_files.append(f)
        elif ext in SUPPORTED_SUBTITLE_EXTS:
            subtitle_files.append(f)
        elif ext in SUPPORTED_IMAGE_EXTS:
            image_files.append(f)

    claimed_files = set()

    # 策略 1：检查是否是“专用单项目输出文件夹”
    # 例如文件夹下只有 1 个主视频，伴随若干字幕或音轨
    if len(video_files) == 1 and (len(subtitle_files) > 0 or len(audio_files) > 0):
        main_video = video_files[0]
        # 此时该单元标题优先采用文件夹名或视频文件名
        title = folder_path.name if folder_path.name else main_video.stem
        bundle_unit = DetectedUnit(title=title, unit_type="bundle", primary_file=main_video)
        claimed_files.add(main_video)
        
        for s in subtitle_files:
            bundle_unit.add_file(s, "subtitle")
            claimed_files.add(s)
            
        for a in audio_files:
            bundle_unit.add_file(a, "audio")
            claimed_files.add(a)
            
        units.append(bundle_unit)
        
        # 剩下的图片作为独立单元
        for img in image_files:
            if img not in claimed_files:
                units.append(DetectedUnit(title=img.stem, unit_type="image", primary_file=img))
                claimed_files.add(img)
        return units

    # 策略 2：基于 Stem 同名匹配（如 ep1.mp4, ep1.srt, ep1.wav）
    by_stem: Dict[str, List[Path]] = defaultdict(list)
    for f in file_paths:
        by_stem[f.stem].append(f)

    for stem, stem_files in by_stem.items():
        v_list = [f for f in stem_files if f.suffix.lower() in SUPPORTED_VIDEO_EXTS]
        s_list = [f for f in stem_files if f.suffix.lower() in SUPPORTED_SUBTITLE_EXTS]
        a_list = [f for f in stem_files if f.suffix.lower() in SUPPORTED_AUDIO_EXTS]

        if v_list and (s_list or a_list):
            primary = v_list[0]
            unit = DetectedUnit(title=stem, unit_type="bundle", primary_file=primary)
            claimed_files.add(primary)
            for s in s_list:
                unit.add_file(s, "subtitle")
                claimed_files.add(s)
            for a in a_list:
                unit.add_file(a, "audio")
                claimed_files.add(a)
            units.append(unit)

    # 策略 3：未被匹配的多媒体作为独立原子元素
    for f in file_paths:
        if f in claimed_files:
            continue
        ext = f.suffix.lower()
        if ext in SUPPORTED_IMAGE_EXTS:
            units.append(DetectedUnit(title=f.stem, unit_type="image", primary_file=f))
            claimed_files.add(f)
        elif ext in SUPPORTED_VIDEO_EXTS:
            units.append(DetectedUnit(title=f.stem, unit_type="video", primary_file=f))
            claimed_files.add(f)
        elif ext in SUPPORTED_AUDIO_EXTS:
            units.append(DetectedUnit(title=f.stem, unit_type="audio", primary_file=f))
            claimed_files.add(f)

    return units
