"""配置持久化：保存和读取用户偏好设置"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


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
    """加载配置，返回配置字典"""
    config_file = _get_config_file()
    if not config_file.exists():
        return {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict[str, Any]) -> None:
    """保存配置"""
    _ensure_config_dir()
    config_file = _get_config_file()
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_last_scan_path() -> str | None:
    """获取上次扫描路径"""
    config = load_config()
    path = config.get("last_scan_path")
    if path and os.path.exists(path):
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


def get_sort_by_size() -> bool | None:
    """获取排序方式，None 表示未设置"""
    config = load_config()
    return config.get("sort_by_size")


def set_sort_by_size(sort_by_size: bool) -> None:
    """设置排序方式"""
    config = load_config()
    config["sort_by_size"] = sort_by_size
    save_config(config)
