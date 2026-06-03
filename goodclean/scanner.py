"""异步目录扫描器：递归扫描目录，收集文件/文件夹信息"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Callable, Optional

from .models import DirInfo, FileInfo


class DirectoryScanner:
    """异步目录扫描器"""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self._visited: set[str] = set()
        self._cancelled = False
        self._on_progress: Optional[Callable[[int, int], None]] = None
        self._scanned_dirs = 0
        self._permission_errors = 0

    def cancel(self) -> None:
        """取消扫描"""
        self._cancelled = True

    def on_progress(self, callback: Callable[[int, int], None]) -> None:
        """设置进度回调：callback(scanned_dirs, permission_errors)"""
        self._on_progress = callback

    async def scan(self) -> DirInfo:
        """执行异步扫描，返回根目录的 DirInfo"""
        self._visited.clear()
        self._cancelled = False
        self._scanned_dirs = 0
        self._permission_errors = 0

        root = DirInfo(
            path=str(self.root_path),
            name=self.root_path.name or str(self.root_path),
        )

        await self._scan_dir(root)
        return root

    async def _scan_dir(self, dir_info: DirInfo) -> None:
        """递归扫描目录"""
        if self._cancelled:
            return

        real_path = os.path.realpath(dir_info.path)
        if real_path in self._visited:
            dir_info.is_symlink = True
            return
        self._visited.add(real_path)

        try:
            entries = list(os.scandir(dir_info.path))
        except PermissionError:
            dir_info.has_permission_error = True
            self._permission_errors += 1
            self._report_progress()
            return
        except OSError:
            return

        self._scanned_dirs += 1
        self._report_progress()

        # 每处理 50 个目录让出控制权，避免阻塞事件循环
        if self._scanned_dirs % 50 == 0:
            await asyncio.sleep(0)

        child_dirs: list[DirInfo] = []

        for entry in entries:
            if self._cancelled:
                return

            try:
                if entry.is_symlink():
                    continue

                if entry.is_dir(follow_symlinks=False):
                    child = DirInfo(
                        path=entry.path,
                        name=entry.name,
                    )
                    child_dirs.append(child)
                elif entry.is_file(follow_symlinks=False):
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        file_info = FileInfo(
                            path=entry.path,
                            name=entry.name,
                            size=stat.st_size,
                            extension=Path(entry.name).suffix.lower(),
                            modified_time=stat.st_mtime,
                        )
                        dir_info.add_file(file_info)
                    except OSError:
                        pass
            except OSError:
                pass

        # 递归扫描子目录
        for child in child_dirs:
            if self._cancelled:
                return
            await self._scan_dir(child)
            dir_info.add_child_dir(child)

    def _report_progress(self) -> None:
        if self._on_progress:
            self._on_progress(self._scanned_dirs, self._permission_errors)
