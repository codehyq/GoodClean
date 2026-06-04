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
