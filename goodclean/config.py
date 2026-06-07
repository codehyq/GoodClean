"""配置持久化：保存和读取用户偏好设置"""

from __future__ import annotations

import gzip
import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 模块级配置缓存，避免频繁读盘
_config_cache: dict[str, Any] | None = None
_config_mtime: float = 0.0


def _get_config_dir() -> Path:
    """获取配置目录（跨平台）"""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "GoodClean"


def _get_config_file() -> Path:
    """获取配置文件路径"""
    return _get_config_dir() / "config.json"


def _ensure_config_dir() -> None:
    """确保配置目录存在"""
    _get_config_dir().mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """加载配置，返回配置字典（带模块级缓存）"""
    global _config_cache, _config_mtime

    config_file = _get_config_file()
    if not config_file.exists():
        return {}

    try:
        mtime = config_file.stat().st_mtime
        if _config_cache is not None and mtime == _config_mtime:
            return _config_cache.copy()

        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        _config_cache = data
        _config_mtime = mtime
        return data.copy()
    except Exception as exc:
        logger.warning("加载配置失败: %s", exc)
        return {}


def save_config(config: dict[str, Any]) -> None:
    """保存配置"""
    global _config_cache, _config_mtime

    _ensure_config_dir()
    config_file = _get_config_file()
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        _config_cache = config.copy()
        _config_mtime = config_file.stat().st_mtime
    except Exception as exc:
        logger.warning("保存配置失败: %s", exc)


def get_last_scan_path() -> str | None:
    """获取上次扫描路径"""
    config = load_config()
    path = config.get("last_scan_path")
    if isinstance(path, str) and os.path.exists(path):
        return path
    return None


def set_last_scan_path(path: str) -> None:
    """设置上次扫描路径"""
    config = load_config()
    config["last_scan_path"] = path
    save_config(config)


def get_use_cache() -> bool | None:
    """获取缓存设置，None 表示未设置"""
    config = load_config()
    return config.get("use_cache")


def set_use_cache(use_cache: bool) -> None:
    """设置缓存开关"""
    config = load_config()
    config["use_cache"] = use_cache
    save_config(config)


SORT_MODES = ["size", "count", "name", "mtime"]


def get_sort_mode() -> str:
    """获取排序模式，默认 size"""
    config = load_config()
    mode = config.get("sort_mode")
    if isinstance(mode, str) and mode in SORT_MODES:
        return mode
    # 兼容旧配置
    old = config.get("sort_by_size")
    if old is not None:
        return "size" if old else "count"
    return "size"


def set_sort_mode(mode: str) -> None:
    """设置排序模式"""
    if mode not in SORT_MODES:
        mode = "size"
    config = load_config()
    config["sort_mode"] = mode
    save_config(config)


# 保留旧接口以兼容现有调用（内部已迁移到 sort_mode）
def get_sort_by_size() -> bool | None:
    """获取排序方式，None 表示未设置（兼容旧接口）"""
    config = load_config()
    return config.get("sort_by_size")


def set_sort_by_size(sort_by_size: bool) -> None:
    """设置排序方式（兼容旧接口）"""
    config = load_config()
    config["sort_by_size"] = sort_by_size
    save_config(config)


# ──────────────────── 扫描结果持久化 ────────────────────

def _get_scan_result_file() -> Path:
    """获取扫描结果持久化文件路径"""
    return _get_config_dir() / "last_scan.json.gz"


def _dict_to_dir_info(data: dict[str, Any]) -> Any:
    """从字典重建 DirInfo"""
    from .models import DirInfo, FileInfo

    di = DirInfo(
        path=data["path"],
        name=data["name"],
        total_size=data.get("total_size", 0),
        file_count=data.get("file_count", 0),
        dir_count=data.get("dir_count", 0),
        has_permission_error=data.get("has_permission_error", False),
        is_symlink=data.get("is_symlink", False),
        modified_time=data.get("modified_time", 0.0),
    )
    for f_data in data.get("files", []):
        di.files.append(FileInfo(**f_data))
    for c_data in data.get("children", []):
        di.children.append(_dict_to_dir_info(c_data))
    return di


def save_scan_result(result: Any) -> None:
    """保存扫描结果到本地（gzip 压缩 JSON），上限 50MB"""
    _ensure_config_dir()
    data = {
        "version": 1,
        "saved_at": time.time(),
        "root_path": result.root_path,
        "total_size": result.total_size,
        "total_files": result.total_files,
        "total_dirs": result.total_dirs,
        "scan_duration": result.scan_duration,
        "permission_errors": result.permission_errors,
        "root_dir": asdict(result.root_dir) if result.root_dir else None,
        "large_files": [asdict(f) for f in result.large_files],
        "junk_files": [asdict(f) for f in result.junk_files],
    }
    json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    if len(json_bytes) > 50 * 1024 * 1024:
        return
    with gzip.open(_get_scan_result_file(), "wb", compresslevel=6) as f:
        f.write(json_bytes)


def load_scan_result() -> Any | None:
    """加载上次保存的扫描结果，7 天过期"""
    file_path = _get_scan_result_file()
    if not file_path.exists():
        return None
    try:
        with gzip.open(file_path, "rb") as f:
            data = json.loads(f.read().decode("utf-8"))
        if data.get("version") != 1:
            return None
        saved_at = data.get("saved_at", 0)
        if time.time() - saved_at > 7 * 86400:
            return None

        from .models import FileInfo, ScanResult

        result = ScanResult(
            root_path=data["root_path"],
            total_size=data["total_size"],
            total_files=data["total_files"],
            total_dirs=data["total_dirs"],
            scan_duration=data.get("scan_duration", 0.0),
            permission_errors=data.get("permission_errors", 0),
        )
        if data.get("root_dir"):
            result.root_dir = _dict_to_dir_info(data["root_dir"])
            # 重建 top_dirs
            all_dirs: list[Any] = []
            _collect_dirs(result.root_dir, all_dirs)
            result.top_dirs = sorted(all_dirs, key=lambda d: d.total_size, reverse=True)[:50]
        for f_data in data.get("large_files", []):
            result.large_files.append(FileInfo(**f_data))
        for f_data in data.get("junk_files", []):
            result.junk_files.append(FileInfo(**f_data))
        return result
    except Exception as exc:
        logger.warning("加载扫描结果失败: %s", exc)
        return None


def has_saved_scan_result() -> bool:
    """检查是否存在有效的保存扫描结果"""
    return load_scan_result() is not None


def _collect_dirs(dir_info: Any, result: list[Any]) -> None:
    """收集所有目录（用于重建 top_dirs）"""
    for child in dir_info.children:
        result.append(child)
        _collect_dirs(child, result)
