"""扫描结果缓存：保存和加载扫描结果，加速二次扫描

使用 pickle 二进制格式替代 JSON，体积更小、速度更快。
缓存结构：{"version": 2, "scan_time": float, "meta": dict, "result": ScanResult}
"""

from __future__ import annotations

import hashlib
import logging
import pickle
import time
from pathlib import Path
from typing import Optional

from .models import ScanResult

logger = logging.getLogger(__name__)


# 缓存目录：~/.goodclean/cache/
CACHE_DIR = Path.home() / ".goodclean" / "cache"


def get_cache_path(root_path: str) -> Path:
    """根据扫描路径生成缓存文件路径"""
    path_hash = hashlib.md5(root_path.encode()).hexdigest()
    return CACHE_DIR / f"{path_hash}.pkl"


def save_cache(result: ScanResult) -> Optional[Path]:
    """将扫描结果保存到缓存文件（pickle 二进制格式）"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "version": 2,
            "scan_time": time.time(),
            "meta": {
                "root_path": result.root_path,
                "total_size": result.total_size,
                "total_files": result.total_files,
                "total_dirs": result.total_dirs,
                "scan_duration": result.scan_duration,
                "permission_errors": result.permission_errors,
            },
            "result": result,
        }

        cache_path = get_cache_path(result.root_path)
        with open(cache_path, "wb") as f:
            pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

        return cache_path
    except Exception as exc:
        logger.warning("保存缓存失败: %s", exc)
        return None


def load_cache(root_path: str, max_age_hours: int = 24) -> Optional[ScanResult]:
    """从缓存文件加载扫描结果

    Args:
        root_path: 扫描路径
        max_age_hours: 缓存最大有效期（小时），默认 24 小时

    Returns:
        缓存的 ScanResult，如果缓存不存在、过期或版本不兼容则返回 None
    """
    try:
        cache_path = get_cache_path(root_path)
        if not cache_path.exists():
            return None

        with open(cache_path, "rb") as f:
            cache_data = pickle.load(f)

        # 检查缓存版本
        if cache_data.get("version") != 2:
            return None

        # 检查缓存有效期
        scan_time = cache_data.get("scan_time", 0)
        age_hours = (time.time() - scan_time) / 3600
        if age_hours > max_age_hours:
            return None

        result = cache_data.get("result")
        if isinstance(result, ScanResult):
            return result
        return None

    except Exception as exc:
        logger.warning("加载缓存失败: %s", exc)
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
        for f in CACHE_DIR.glob("*.pkl"):
            f.unlink()
            count += 1
        return count


def list_all_caches() -> list[dict]:
    """列出所有缓存的摘要信息"""
    if not CACHE_DIR.exists():
        return []

    caches = []
    for cache_file in CACHE_DIR.glob("*.pkl"):
        try:
            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)
            meta = cache_data.get("meta", {})
            scan_time = cache_data.get("scan_time", 0)
            age_hours = round((time.time() - scan_time) / 3600, 1)
            caches.append({
                "path": meta.get("root_path", "未知"),
                "scan_time": scan_time,
                "age_hours": age_hours,
                "total_size": meta.get("total_size", 0),
                "total_files": meta.get("total_files", 0),
                "total_dirs": meta.get("total_dirs", 0),
                "expired": age_hours > 24,
            })
        except Exception as exc:
            logger.debug("读取缓存摘要失败 %s: %s", cache_file, exc)
            continue
    return caches


def get_cache_info(root_path: str) -> Optional[dict]:
    """获取缓存信息（不加载完整 ScanResult，只读取 meta）"""
    try:
        cache_path = get_cache_path(root_path)
        if not cache_path.exists():
            return None

        with open(cache_path, "rb") as f:
            cache_data = pickle.load(f)

        meta = cache_data.get("meta", {})
        scan_time = cache_data.get("scan_time", 0)
        age_hours = (time.time() - scan_time) / 3600

        return {
            "path": root_path,
            "scan_time": scan_time,
            "age_hours": round(age_hours, 1),
            "total_size": meta.get("total_size", 0),
            "total_files": meta.get("total_files", 0),
            "total_dirs": meta.get("total_dirs", 0),
            "file_size": cache_path.stat().st_size,
            "expired": age_hours > 24,
        }
    except Exception as exc:
        logger.debug("获取缓存信息失败: %s", exc)
        return None
