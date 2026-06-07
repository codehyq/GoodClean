"""基于文件头（magic bytes）的文件类型识别

仅对无扩展名或未知扩展名的文件做文件头检测，避免全量扫描性能损耗。
每个文件最多读取头部 261 字节（覆盖 TAR 签名偏移），开销极小。
"""

from __future__ import annotations

from .constants import FILE_SIGNATURES, KNOWN_EXTENSIONS


# 读取文件头的最大字节数（TAR ustar 在偏移 257）
_HEADER_READ_SIZE = 261

# ──────────────────── 扩展名到分类的全局常量 ────────────────────
_EXT_TO_CATEGORY: dict[str, str] = {
    # 图片
    ".jpg": "图片", ".jpeg": "图片", ".png": "图片", ".gif": "图片",
    ".bmp": "图片", ".webp": "图片", ".tiff": "图片", ".tif": "图片",
    ".ico": "图片", ".svg": "图片", ".heic": "图片", ".heif": "图片",
    # 视频
    ".mp4": "视频", ".mov": "视频", ".avi": "视频", ".mkv": "视频",
    ".webm": "视频", ".flv": "视频", ".wmv": "视频", ".m4v": "视频",
    ".ts": "视频",
    # 音频
    ".mp3": "音频", ".flac": "音频", ".ogg": "音频", ".wav": "音频",
    ".aac": "音频", ".m4a": "音频", ".wma": "音频",
    # 文档
    ".pdf": "文档", ".doc": "文档", ".docx": "文档", ".xls": "文档",
    ".xlsx": "文档", ".ppt": "文档", ".pptx": "文档", ".odt": "文档",
    ".ods": "文档", ".odp": "文档", ".rtf": "文档", ".txt": "文档",
    ".md": "文档",
    # 代码
    ".py": "代码", ".js": "代码", ".ts": "代码", ".java": "代码",
    ".c": "代码", ".cpp": "代码", ".h": "代码", ".rs": "代码",
    ".go": "代码", ".rb": "代码", ".php": "代码", ".swift": "代码",
    ".kt": "代码", ".scala": "代码", ".r": "代码", ".m": "代码",
    ".html": "代码", ".css": "代码", ".scss": "代码", ".less": "代码",
    ".vue": "代码", ".jsx": "代码", ".tsx": "代码", ".svelte": "代码",
    # 配置
    ".json": "配置", ".xml": "配置", ".yaml": "配置", ".yml": "配置",
    ".toml": "配置", ".ini": "配置", ".cfg": "配置", ".conf": "配置",
    ".env": "配置", ".csv": "配置",
    # 压缩包
    ".zip": "压缩包", ".rar": "压缩包", ".7z": "压缩包",
    ".tar": "压缩包", ".gz": "压缩包", ".bz2": "压缩包",
    ".xz": "压缩包", ".tgz": "压缩包",
    # 可执行/二进制
    ".exe": "可执行文件", ".dll": "可执行文件", ".so": "可执行文件",
    ".dylib": "可执行文件", ".bin": "可执行文件",
    # 编译/缓存产物
    ".pyc": "编译产物", ".pyo": "编译产物", ".class": "编译产物",
    ".obj": "编译产物", ".o": "编译产物", ".a": "编译产物",
    ".lib": "编译产物",
    # 数据库
    ".sqlite": "数据库", ".db": "数据库", ".mdb": "数据库",
    ".accdb": "数据库",
    # 字体
    ".ttf": "字体", ".otf": "字体", ".woff": "字体", ".woff2": "字体",
    # 日志/临时
    ".log": "日志/临时", ".tmp": "日志/临时", ".temp": "日志/临时",
    ".bak": "日志/临时", ".swp": "日志/临时", ".swo": "日志/临时",
    # 虚拟磁盘/镜像
    ".vmdk": "磁盘镜像", ".vdi": "磁盘镜像", ".vhd": "磁盘镜像",
    ".vhdx": "磁盘镜像", ".iso": "磁盘镜像", ".img": "磁盘镜像",
    ".dmg": "磁盘镜像",
    # 电子书
    ".epub": "电子书", ".mobi": "电子书", ".azw": "电子书",
}

_MAGIC_TO_CATEGORY: dict[str, str] = {
    "JPEG 图片": "图片", "PNG 图片": "图片", "GIF 图片": "图片",
    "BMP 图片": "图片", "WebP 图片": "图片", "TIFF 图片": "图片",
    "ICO 图标": "图片",
    "MP4 视频": "视频", "QuickTime 视频": "视频",
    "AVI 视频": "视频", "Matroska 视频": "视频",
    "MP3 音频": "音频", "M4A 音频": "音频",
    "FLAC 音频": "音频", "OGG 音频": "音频", "WAV 音频": "音频",
    "ZIP 压缩包": "压缩包", "RAR 压缩包": "压缩包",
    "7z 压缩包": "压缩包", "TAR 归档": "压缩包",
    "PDF 文档": "文档",
    "Windows 可执行文件": "可执行文件",
    "ELF 可执行文件": "可执行文件",
    "Mach-O 可执行文件": "可执行文件",
    "Java Class 文件": "编译产物",
    "Python 字节码": "编译产物",
    "SQLite 数据库": "数据库",
    "TrueType 字体": "字体", "OpenType 字体": "字体",
    "VMDK 虚拟磁盘": "磁盘镜像", "ISO 磁盘镜像": "磁盘镜像",
}

_TYPE_TO_EXT: dict[str, str] = {
    "JPEG 图片": ".jpg",
    "PNG 图片": ".png",
    "GIF 图片": ".gif",
    "BMP 图片": ".bmp",
    "WebP 图片": ".webp",
    "TIFF 图片": ".tiff",
    "ICO 图标": ".ico",
    "MP4 视频": ".mp4",
    "QuickTime 视频": ".mov",
    "AVI 视频": ".avi",
    "Matroska 视频": ".mkv",
    "MP3 音频": ".mp3",
    "M4A 音频": ".m4a",
    "FLAC 音频": ".flac",
    "OGG 音频": ".ogg",
    "WAV 音频": ".wav",
    "ZIP 压缩包": ".zip",
    "RAR 压缩包": ".rar",
    "7z 压缩包": ".7z",
    "TAR 归档": ".tar",
    "PDF 文档": ".pdf",
    "Windows 可执行文件": ".exe",
    "ELF 可执行文件": ".elf",
    "Mach-O 可执行文件": ".macho",
    "Java Class 文件": ".class",
    "Python 字节码": ".pyc",
    "SQLite 数据库": ".sqlite",
    "TrueType 字体": ".ttf",
    "OpenType 字体": ".otf",
    "VMDK 虚拟磁盘": ".vmdk",
    "ISO 磁盘镜像": ".iso",
}


def identify_by_magic_bytes(file_path: str) -> str:
    """读取文件头，匹配已知文件签名，返回文件类型描述。

    返回空字符串表示无法识别。
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(_HEADER_READ_SIZE)
    except (OSError, PermissionError, ValueError):
        return ""

    if len(header) == 0:
        return ""

    for offset, signature, description in FILE_SIGNATURES:
        if offset + len(signature) <= len(header):
            if header[offset: offset + len(signature)] == signature:
                return description

    return ""


def needs_magic_check(extension: str) -> bool:
    """判断给定扩展名是否需要做文件头检测。

    已知扩展名不需要，只对未知/无扩展名的文件做检测。
    """
    return extension.lower() not in KNOWN_EXTENSIONS


def get_real_extension(file_path: str) -> str:
    """通过文件头识别真实扩展名，用于无扩展名或扩展名不匹配的场景。

    返回空字符串表示无需修正或无法识别。
    """
    real_type = identify_by_magic_bytes(file_path)
    if not real_type:
        return ""

    return _TYPE_TO_EXT.get(real_type, "")


def classify_file_type(extension: str, file_path: str, file_size: int) -> str:
    """分类文件的逻辑类型（用于类型分布统计）。

    优先使用扩展名分类，对未知扩展名尝试文件头识别。
    返回中文类型分组名。
    """
    ext = extension.lower()
    if ext in _EXT_TO_CATEGORY:
        return _EXT_TO_CATEGORY[ext]

    # 对未知扩展名做文件头检测
    if needs_magic_check(extension) and file_size > 0:
        magic_type = identify_by_magic_bytes(file_path)
        if magic_type:
            return _MAGIC_TO_CATEGORY.get(magic_type, "其他")

    if file_size == 0:
        return "空文件"

    return "其他"
