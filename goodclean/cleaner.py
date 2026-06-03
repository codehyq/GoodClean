"""清理器：安全删除文件（回收站）和永久删除"""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from send2trash import send2trash

logger = logging.getLogger(__name__)


@dataclass
class CleanResult:
    """清理结果"""
    success_count: int = 0
    fail_count: int = 0
    freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)
    cleaned_paths: list[str] = field(default_factory=list)


def trash_files(paths: list[str]) -> CleanResult:
    """将文件/目录移到回收站（安全删除）"""
    result = CleanResult()

    for path in paths:
        try:
            p = Path(path)
            if not p.exists():
                result.errors.append(f"路径不存在: {path}")
                result.fail_count += 1
                continue

            size = _get_path_size(p)
            send2trash(str(p))
            result.success_count += 1
            result.freed_bytes += size
            result.cleaned_paths.append(path)
            logger.info("已移到回收站: %s (%d bytes)", path, size)
        except OSError as e:
            result.errors.append(f"删除失败 {path}: {e}")
            result.fail_count += 1
            logger.error("删除失败 %s: %s", path, e)

    return result


def permanent_delete(paths: list[str]) -> CleanResult:
    """永久删除文件/目录（不可恢复）"""
    result = CleanResult()

    for path in paths:
        try:
            p = Path(path)
            if not p.exists():
                result.errors.append(f"路径不存在: {path}")
                result.fail_count += 1
                continue

            size = _get_path_size(p)
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            result.success_count += 1
            result.freed_bytes += size
            result.cleaned_paths.append(path)
            logger.info("已永久删除: %s (%d bytes)", path, size)
        except OSError as e:
            result.errors.append(f"删除失败 {path}: {e}")
            result.fail_count += 1
            logger.error("永久删除失败 %s: %s", path, e)

    return result


def _get_path_size(path: Path) -> int:
    """获取文件或目录的大小"""
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    elif path.is_dir():
        total = 0
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += _get_path_size(Path(entry.path))
                except OSError:
                    pass
        except PermissionError:
            pass
        return total
    return 0
