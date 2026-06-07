"""清理器：安全删除文件（回收站）和永久删除，支持进度回调"""

from __future__ import annotations

import logging
import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from send2trash import send2trash

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str, int], None]
"""进度回调: (current_done, total_items, current_path, freed_bytes_so_far)"""


@dataclass
class CleanResult:
    """清理结果"""
    success_count: int = 0
    fail_count: int = 0
    freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)
    cleaned_paths: list[str] = field(default_factory=list)


def _expand_paths(paths: list[str]) -> list[tuple[str, int]]:
    """将路径列表展开为所有叶子项（文件和空目录），返回 [(path, size)]

    对于目录，递归展开为内部所有文件；目录本身不在列表中（会在文件删完后处理）。
    """
    items: list[tuple[str, int]] = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            items.append((path, 0))
            continue
        if p.is_file():
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            items.append((path, size))
        elif p.is_dir():
            _collect_dir_items(p, items)
    return items


def _collect_dir_items(root: Path, items: list[tuple[str, int]]) -> None:
    """递归收集目录内所有文件，按深度优先顺序"""
    try:
        for entry in os.scandir(root):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    try:
                        size = entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        size = 0
                    items.append((entry.path, size))
                elif entry.is_dir(follow_symlinks=False):
                    _collect_dir_items(Path(entry.path), items)
            except OSError:
                pass
    except (OSError, PermissionError):
        pass


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


def trash_files(
    paths: list[str],
    on_progress: ProgressCallback | None = None,
) -> CleanResult:
    """将文件/目录移到回收站（安全删除），支持进度回调

    文件直接 send2trash；目录交给 send2trash 递归处理，避免手动展开后
    二次操作外层目录导致的非空目录错误或重复删除。
    """
    result = CleanResult()
    total = len(paths)

    for i, path in enumerate(paths, start=1):
        p = Path(path)
        if not p.exists():
            result.errors.append(f"路径不存在: {path}")
            result.fail_count += 1
            if on_progress:
                on_progress(i, total, path, result.freed_bytes)
            continue

        try:
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

        if on_progress:
            on_progress(i, total, path, result.freed_bytes)

    return result


def permanent_delete(
    paths: list[str],
    on_progress: ProgressCallback | None = None,
) -> CleanResult:
    """永久删除文件/目录（不可恢复），支持进度回调

    文件直接删除；目录交给 shutil.rmtree 递归处理，避免手动展开后
    二次操作外层目录导致的非空目录错误或重复删除。
    """
    result = CleanResult()
    total = len(paths)

    for i, path in enumerate(paths, start=1):
        p = Path(path)
        if not p.exists():
            result.errors.append(f"路径不存在: {path}")
            result.fail_count += 1
            if on_progress:
                on_progress(i, total, path, result.freed_bytes)
            continue

        try:
            size = _get_path_size(p)
            if p.is_dir():
                shutil.rmtree(p, onerror=_handle_remove_error)
            else:
                _remove_file(p)
            result.success_count += 1
            result.freed_bytes += size
            result.cleaned_paths.append(path)
            logger.info("已永久删除: %s (%d bytes)", path, size)
        except OSError as e:
            result.errors.append(f"删除失败 {path}: {e}")
            result.fail_count += 1
            logger.error("永久删除失败 %s: %s", path, e)

        if on_progress:
            on_progress(i, total, path, result.freed_bytes)

    return result


def _handle_remove_error(
    func: Callable[[str], None], path: str, exc_info: tuple[Any, ...],
) -> None:
    """处理删除错误，尝试修改权限后重试"""
    exc_type = exc_info[0]
    if exc_type is PermissionError:
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass
    elif exc_type is OSError:
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass


def _remove_file(path: Path) -> None:
    """删除单个文件，处理权限问题"""
    try:
        path.unlink()
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        path.unlink()
