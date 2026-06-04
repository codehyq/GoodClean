"""常量定义：垃圾文件模式、大小阈值等"""

# 大小阈值（字节）
SIZE_KB = 1024
SIZE_MB = 1024 * 1024
SIZE_GB = 1024 * 1024 * 1024

# 大文件阈值：100MB
LARGE_FILE_THRESHOLD = 100 * SIZE_MB

# 垃圾文件扩展名模式
JUNK_EXTENSIONS = {
    # 临时文件
    ".tmp", ".temp", ".bak", ".swp", ".swo",
    # 系统文件
    ".thumbs.db", ".ds_store",
    # 日志
    ".log",
    # 编译产物
    ".obj", ".o", ".pyc", ".pyo", ".class",
}

# 垃圾文件名模式（完整文件名匹配）
JUNK_FILENAMES = {
    "thumbs.db",
    "desktop.ini",
    ".ds_store",
    ".gitkeep",
}

# 垃圾目录名模式
JUNK_DIRNAMES = {
    # 包管理缓存
    "node_modules",
    # Python 缓存
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    # 构建产物
    "dist",
    "build",
    "out",
    "target",
    ".next",
    ".nuxt",
    ".output",
    # IDE 缓存
    ".idea",
    ".vs",
    "__build__",
    # 版本控制
    ".svn",
}

# 系统临时目录环境变量
TEMP_DIR_VARS = ["TEMP", "TMP", "TMPDIR"]

# 扫描状态
class ScanStatus:
    IDLE = "idle"
    SCANNING = "scanning"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


# 扫描模式
SCAN_MODE_STANDARD = "standard"   # 标准模式（使用缓存）
SCAN_MODE_FORCE = "force"         # 强制刷新（跳过缓存）

# 缓存有效期（小时）
CACHE_MAX_AGE_HOURS = 24

# 文件头签名表：(偏移量, magic_bytes, 中文描述)
# 偏移量指从文件开头的字节偏移，用于支持 RIFF 容器等需要在特定位置检查的格式
FILE_SIGNATURES = [
    # ── 图片 ──
    (0,  b"\xff\xd8\xff",                     "JPEG 图片"),
    (0,  b"\x89PNG\r\n\x1a\n",               "PNG 图片"),
    (0,  b"GIF87a",                           "GIF 图片"),
    (0,  b"GIF89a",                           "GIF 图片"),
    (0,  b"BM",                               "BMP 图片"),
    (0,  b"II\x2a\x00",                       "TIFF 图片"),
    (0,  b"MM\x00\x2a",                       "TIFF 图片"),
    (0,  b"\x00\x00\x01\x00",                 "ICO 图标"),
    # RIFF 容器子类型（在偏移 8 处检查）
    (8,  b"WEBP",                             "WebP 图片"),

    # ── 视频 ──
    # MP4/MOV 家族（ftyp box，偏移 4 处检查 "ftyp"）
    (4,  b"ftypmp4",                          "MP4 视频"),
    (4,  b"ftypisom",                         "MP4 视频"),
    (4,  b"ftypMSNV",                         "MP4 视频"),
    (4,  b"ftypqt ",                          "QuickTime 视频"),
    (4,  b"ftypM4A ",                         "M4A 音频"),
    (4,  b"ftypdash",                         "MP4 视频"),
    # Matroska 家族
    (0,  b"\x1a\x45\xdf\xa3",                 "Matroska 视频"),
    # RIFF 容器子类型
    (8,  b"AVI ",                             "AVI 视频"),

    # ── 音频 ──
    (0,  b"ID3",                              "MP3 音频"),
    (0,  b"\xff\xfb",                         "MP3 音频"),
    (0,  b"\xff\xf3",                         "MP3 音频"),
    (0,  b"fLaC",                             "FLAC 音频"),
    (0,  b"OggS",                             "OGG 音频"),
    # RIFF 容器子类型
    (8,  b"WAVE",                             "WAV 音频"),

    # ── 压缩包 ──
    (0,  b"PK\x03\x04",                       "ZIP 压缩包"),
    (0,  b"Rar!\x1a\x07",                     "RAR 压缩包"),
    (0,  b"7z\xbc\xaf\x27\x1c",              "7z 压缩包"),
    (257, b"ustar",                           "TAR 归档"),

    # ── 文档 ──
    (0,  b"%PDF",                             "PDF 文档"),

    # ── 可执行文件 / 二进制 ──
    (0,  b"MZ",                               "Windows 可执行文件"),
    (0,  b"\x7fELF",                          "ELF 可执行文件"),
    (0,  b"\xfe\xed\xfa\xce",                 "Mach-O 可执行文件"),
    (0,  b"\xfe\xed\xfa\xcf",                 "Mach-O 可执行文件"),

    # ── 编译产物 ──
    (0,  b"\xca\xfe\xba\xde",                 "Java Class 文件"),
    (0,  b"\x0d\x0d\x0a",                     "Python 字节码"),
    (0,  b"\x55\x0d\x0d\x0a",                 "Python 字节码"),
    (0,  b";\x0c\r\n",                        "Python 字节码"),

    # ── 数据库 ──
    (0,  b"SQLite format 3",                  "SQLite 数据库"),

    # ── 字体 ──
    (0,  b"\x00\x01\x00\x00",                "TrueType 字体"),
    (0,  b"OTTO",                             "OpenType 字体"),

    # ── 虚拟磁盘 / 磁盘镜像 ──
    (0,  b"KDMV",                             "VMDK 虚拟磁盘"),
    (0,  b"CD00\x01",                         "ISO 磁盘镜像"),
]

# 已知的可识别扩展名集合（用于判断是否需要做文件头检测）
KNOWN_EXTENSIONS = {
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".ico", ".svg",
    # 视频
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v",
    # 音频
    ".mp3", ".flac", ".ogg", ".wav", ".aac", ".m4a", ".wma",
    # 压缩包
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz",
    # 文档
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".rtf",
    # 可执行文件
    ".exe", ".dll", ".so", ".dylib", ".elf",
    # 编译产物
    ".pyc", ".pyo", ".class", ".obj", ".o",
    # 数据库
    ".sqlite", ".db", ".mdb", ".accdb",
    # 电子书
    ".epub", ".mobi",
    # 字体
    ".ttf", ".otf", ".woff", ".woff2",
    # 虚拟磁盘
    ".vmdk", ".vdi", ".vhd", ".vhdx",
    # 磁盘镜像
    ".iso", ".img", ".dmg",
    # 文本/代码（一般不需要文件头检测）
    ".txt", ".md", ".json", ".xml", ".csv", ".yaml", ".yml",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".rs", ".go",
    ".log", ".ini", ".cfg", ".conf",
    # 垃圾/临时
    ".tmp", ".temp", ".bak", ".swp", ".swo", ".log",
    ".thumbs.db", ".ds_store",
}
