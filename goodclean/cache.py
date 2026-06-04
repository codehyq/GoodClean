"""扫描结果缓存：保存和加载扫描结果，加速二次扫描"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from .models import DirInfo, FileInfo, ScanResult


# 缓存目录：~/.goodclean/cache/
CACHE_DIR = Path.home() / ".goodclean" / "cache"


def get_cache_path(root_path: str) -> Path:
    """根据扫描路径生成缓存文件路径"""
    path_hash = hashlib.md5(root_path.encode()).hexdigest()
    return CACHE_DIR / f"{path_hash}.json"


def save_cache(result: ScanResult) -> Optional[Path]:
    """将扫描结果保存到缓存文件"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "version": 1,
            "root_path": result.root_path,
            "total_size": result.total_size,
            "total_files": result.total_files,
            "total_dirs": result.total_dirs,
            "scan_duration": result.scan_duration,
            "permission_errors": result.permission_errors,
            "scan_time": time.time(),
            "root_dir": _serialize_dir(result.root_dir) if result.root_dir else None,
        }

        cache_path = get_cache_path(result.root_path)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)

        return cache_path
    except Exception:
        return None


def load_cache(root_path: str, max_age_hours: int = 24) -> Optional[ScanResult]:
    """从缓存文件加载扫描结果

    Args:
        root_path: 扫描路径
        max_age_hours: 缓存最大有效期（小时），默认 24 小时

    Returns:
        缓存的 ScanResult，如果缓存不存在或过期则返回 None
    """
    try:
        cache_path = get_cache_path(root_path)
        if not cache_path.exists():
            return None

        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        # 检查缓存版本
        if cache_data.get("version") != 1:
            return None

        # 检查缓存有效期
        scan_time = cache_data.get("scan_time", 0)
        age_hours = (time.time() - scan_time) / 3600
        if age_hours > max_age_hours:
            return None

        # 反序列化根目录
        root_dir = None
        if cache_data.get("root_dir"):
            root_dir = _deserialize_dir(cache_data["root_dir"])

        # 构建 ScanResult
        result = ScanResult(
            root_path=cache_data.get("root_path", root_path),
            total_size=cache_data.get("total_size", 0),
            total_files=cache_data.get("total_files", 0),
            total_dirs=cache_data.get("total_dirs", 0),
            scan_duration=cache_data.get("scan_duration", 0),
            permission_errors=cache_data.get("permission_errors", 0),
            root_dir=root_dir,
        )

        # 重建分析数据
        if root_dir:
            from .analyzer import _collect_dirs, _collect_files
            from .constants import LARGE_FILE_THRESHOLD

            all_dirs: list[DirInfo] = []
            _collect_dirs(root_dir, all_dirs)
            result.top_dirs = sorted(all_dirs, key=lambda d: d.total_size, reverse=True)[:50]

            all_files: list[FileInfo] = []
            _collect_files(root_dir, all_files)
            result.large_files = sorted(
                [f for f in all_files if f.size >= LARGE_FILE_THRESHOLD],
                key=lambda f: f.size,
                reverse=True,
            )[:100]

        return result

    except Exception:
        return None


def clear_cache(root_path: Optional[str] = None) -> int:
    """清除缓存

    Args:
        root_path: 如果指定，只清除该路径的缓存；否则清除所有缓存

    Returns:
        清除的缓存文件数
    """
    if not CACHE_DIR.exists():
        return 0

    if root_path:
        cache_path = get_cache_path(root_path)
        if cache_path.exists():
            cache_path.unlink()
            return 1
        return 0
    else:
        count = 0
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
            count += 1
        return count


def get_cache_info(root_path: str) -> Optional[dict]:
    """获取缓存信息（不加载完整数据）"""
    try:
        cache_path = get_cache_path(root_path)
        if not cache_path.exists():
            return None

        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        scan_time = cache_data.get("scan_time", 0)
        age_hours = (time.time() - scan_time) / 3600

        return {
            "path": root_path,
            "scan_time": scan_time,
            "age_hours": round(age_hours, 1),
            "total_size": cache_data.get("total_size", 0),
            "total_files": cache_data.get("total_files", 0),
            "total_dirs": cache_data.get("total_dirs", 0),
            "file_size": cache_path.stat().st_size,
            "expired": age_hours > 24,
        }
    except Exception:
        return None


# ==================== 序列化辅助函数 ====================

def _serialize_dir(dir_info: Optional[DirInfo], max_depth: int = 50, _depth: int = 0) -> Optional[dict]:
    """将 DirInfo 序列化为字典，限制最大深度防止 JSON 过大"""
    if dir_info is None:
        return None

    data = {
        "path": dir_info.path,
        "name": dir_info.name,
        "total_size": dir_info.total_size,
        "file_count": dir_info.file_count,
        "dir_count": dir_info.dir_count,
        "has_permission_error": dir_info.has_permission_error,
        "is_symlink": dir_info.is_symlink,
        "files": [_serialize_file(f) for f in dir_info.files],
    }

    if _depth < max_depth:
        data["children"] = [_serialize_dir(c, max_depth, _depth + 1) for c in dir_info.children]
    else:
        data["children"] = []

    return data


def _serialize_file(file_info: FileInfo) -> dict:
    """将 FileInfo 序列化为字典"""
    return {
        "path": file_info.path,
        "name": file_info.name,
        "size": file_info.size,
        "extension": file_info.extension,
        "modified_time": file_info.modified_time,
        "is_junk": file_info.is_junk,
        "junk_reason": file_info.junk_reason,
    }


def _deserialize_dir(data: dict) -> DirInfo:
    """从字典反序列化为 DirInfo"""
    dir_info = DirInfo(
        path=data.get("path", ""),
        name=data.get("name", ""),
        total_size=data.get("total_size", 0),
        file_count=data.get("file_count", 0),
        dir_count=data.get("dir_count", 0),
        has_permission_error=data.get("has_permission_error", False),
        is_symlink=data.get("is_symlink", False),
    )
    dir_info.children = [_deserialize_dir(c) for c in data.get("children", []) if c is not None]
    dir_info.files = [_deserialize_file(f) for f in data.get("files", [])]
    return dir_info


def _deserialize_file(data: dict) -> FileInfo:
    """从字典反序列化为 FileInfo"""
    return FileInfo(
        path=data.get("path", ""),
        name=data.get("name", ""),
        size=data.get("size", 0),
        extension=data.get("extension", ""),
        modified_time=data.get("modified_time", 0),
        is_junk=data.get("is_junk", False),
        junk_reason=data.get("junk_reason", ""),
    )
