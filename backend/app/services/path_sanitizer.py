import hashlib
import re
import unicodedata
from typing import Tuple

# Windows 非法字符: \ / : * ? " < > | 以及 0-31 控制字符
WINDOWS_FORBIDDEN_CHARS = re.compile(r'[\\/*?:"<>|\x00-\x1f]')

# Windows DOS 时代遗留保留设备名 (大小写不敏感，无论是否有扩展名，如 CON.txt, aux.mp4 均非法)
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# 字符安全替换映射 (将英文冒号问号等转为人类可读全角字符)
SAFE_CHAR_MAP = {
    ':': '：',
    '?': '？',
    '*': '＊',
    '"': "''",
    '<': '＜',
    '>': '＞',
    '|': '｜',
    '/': '-',
    '\\': '-',
}

DEFAULT_MAX_SEGMENT_LENGTH = 80
DEFAULT_MAX_PATH_LENGTH = 230


def sanitize_path_segment(raw_name: str, max_length: int = DEFAULT_MAX_SEGMENT_LENGTH) -> str:
    """
    单级目录名与文件名跨平台工业级净化器：
    1. Unicode NFC 标准化；
    2. 将 Windows/SMB 禁用字符转换为安全全角字符；
    3. 剥除末尾非法空格与句点（Windows 资源管理器无法打开以点或空格结尾的文件）；
    4. 拦截并加前缀规避 DOS 保留设备名 (CON, NUL, AUX, PRN 等)；
    5. 预算截断并追加 6 位 MD5 哈希，杜绝因截断导致的重名覆盖。
    """
    if not raw_name:
        return "_unnamed"

    # 1. Unicode NFC 规范化
    s = unicodedata.normalize("NFC", str(raw_name).strip())

    # 2. 安全替换特殊字符
    for bad_char, safe_char in SAFE_CHAR_MAP.items():
        s = s.replace(bad_char, safe_char)

    # 去除剩余的控制字符
    s = WINDOWS_FORBIDDEN_CHARS.sub("_", s).strip()

    # 3. 剥除末尾空格与句点
    s = s.rstrip(" .")
    if not s:
        return "_unnamed"

    # 4. 检查 DOS 保留名 (如 "CON", "aux.mp4")
    name_without_ext = s.split(".")[0].upper()
    if name_without_ext in WINDOWS_RESERVED_NAMES:
        s = f"_{s}"

    # 5. 长度预算截断与确定性哈希
    if len(s) > max_length:
        content_hash = hashlib.md5(s.encode("utf-8")).hexdigest()[:6]
        keep_len = max(max_length - 8, 10)
        s = f"{s[:keep_len].rstrip(' .')}_{content_hash}"

    return s


def check_path_length_budget(
    full_path: str, max_total_length: int = DEFAULT_MAX_PATH_LENGTH
) -> Tuple[bool, int, str]:
    """
    检查全路径是否超出安全预算 (默认 230 字符，保留 30 字符余量给系统与长扩展名)
    返回: (是否安全, 当前长度, 警告信息)
    """
    cur_len = len(full_path)
    if cur_len > max_total_length:
        return (
            False,
            cur_len,
            f"路径长度 ({cur_len} 字符) 超出安全预算 ({max_total_length} 字符)，可能导致 Windows 无法打开",
        )
    return True, cur_len, ""
