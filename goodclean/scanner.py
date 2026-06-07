"""异步目录扫描器：递归扫描目录，收集文件/文件夹信息

支持：
- 异步扫描，不阻塞 UI
- 并行扫描子目录，利用多核 CPU
- 增量扫描，只扫描变化的目录
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .models import DirInfo, FileInfo

logger = logging.getLogger(__name__)

# 并行扫描的线程池大小
MAX_WORKERS = 8


class DirectoryScanner:
    """异步目录扫描器（支持并行和增量扫描）"""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self._visited: set[str] = set()
        self._cancelled = False
        self._on_progress: Callable[[int, int], None] | None = None
        self._scanned_dirs = 0
        self._permission_errors = 0
        # 增量扫描：旧目录数据 {路径: DirInfo}
        self._old_dirs: dict[str, DirInfo] = {}
        self._use_parallel = True

    def cancel(self) -> None:
        """取消扫描"""
        self._cancelled = True

    def on_progress(self, callback: Callable[[int, int], None]) -> None:
        """设置进度回调：callback(scanned_dirs, permission_errors)"""
        self._on_progress = callback

    def set_old_dirs(self, old_dirs: dict[str, DirInfo]) -> None:
        """设置旧的目录数据，用于增量扫描"""
        self._old_dirs = old_dirs

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

        if self._use_parallel:
            await self._scan_dir_parallel(root)
        else:
            await self._scan_dir(root)
        return root

    # ==================== 并行扫描 ====================

    async def _scan_dir_parallel(self, dir_info: DirInfo) -> None:
        """并行扫描目录（使用线程池加速 IO 操作）"""
        if self._cancelled:
            return

        real_path = os.path.realpath(dir_info.path)
        if real_path in self._visited:
            dir_info.is_symlink = True
            return
        self._visited.add(real_path)

        # 尝试增量扫描
        if self._is_dir_unchanged(dir_info):
            cached = self._old_dirs.get(dir_info.path)
            if cached:
                self._copy_dir_info(dir_info, cached)
                self._report_progress()
                return

        # 读取目录条目（在线程池中执行以避免阻塞）
        loop = asyncio.get_event_loop()
        try:
            entries = await loop.run_in_executor(
                _thread_pool, _scan_entries, dir_info.path
            )
        except PermissionError:
            dir_info.has_permission_error = True
            self._permission_errors += 1
            self._report_progress()
            return
        except OSError as exc:
            logger.debug("扫描目录失败 %s: %s", dir_info.path, exc)
            return

        self._scanned_dirs += 1
        self._report_progress()

        # 分离文件和子目录
        child_dirs: list[DirInfo] = []
        for entry_path, entry_name, is_dir in entries:
            if self._cancelled:
                return
            if is_dir:
                child_dirs.append(DirInfo(path=entry_path, name=entry_name))
            else:
                # 文件 stat 也在线程池中执行
                try:
                    file_info = await loop.run_in_executor(
                        _thread_pool, _scan_file, entry_path, entry_name
                    )
                    if file_info:
                        dir_info.add_file(file_info)
                except Exception as exc:
                    logger.debug("扫描文件失败 %s: %s", entry_path, exc)

        # 并行扫描所有子目录
        if child_dirs:
            # 限制并发数，避免线程池爆炸
            semaphore = asyncio.Semaphore(min(len(child_dirs), MAX_WORKERS))

            async def scan_with_semaphore(child: DirInfo) -> None:
                async with semaphore:
                    await self._scan_dir_parallel(child)
                    dir_info.add_child_dir(child)

            tasks = [scan_with_semaphore(child) for child in child_dirs]
            await asyncio.gather(*tasks, return_exceptions=True)

    # ==================== 顺序扫描（降级方案） ====================

    async def _scan_dir(self, dir_info: DirInfo) -> None:
        """递归顺序扫描目录"""
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
        except OSError as exc:
            logger.debug("扫描目录失败 %s: %s", dir_info.path, exc)
            return

        self._scanned_dirs += 1
        self._report_progress()

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
                    child = DirInfo(path=entry.path, name=entry.name)
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
                    except OSError as exc:
                        logger.debug("获取文件信息失败 %s: %s", entry.path, exc)
            except OSError as exc:
                logger.debug("判断条目类型失败 %s: %s", entry.path, exc)

        for child in child_dirs:
            if self._cancelled:
                return
            await self._scan_dir(child)
            dir_info.add_child_dir(child)

    # ==================== 增量扫描辅助 ====================

    def _is_dir_unchanged(self, dir_info: DirInfo) -> bool:
        """检查目录是否有变化（基于修改时间 + 条目数量联合判断）"""
        if dir_info.path not in self._old_dirs:
            return False

        try:
            stat = os.stat(dir_info.path)
            old = self._old_dirs[dir_info.path]

            # 联合判断：修改时间变化 → 必然有变化
            if stat.st_mtime != old.modified_time:
                return False

            # 修改时间未变 → 再比较条目数量
            current_entries = len(os.listdir(dir_info.path))
            old_entries = old.file_count + old.dir_count
            return current_entries == old_entries
        except OSError:
            return False

    def _copy_dir_info(self, target: DirInfo, source: DirInfo) -> None:
        """从缓存复制目录信息"""
        target.total_size = source.total_size
        target.file_count = source.file_count
        target.dir_count = source.dir_count
        target.has_permission_error = source.has_permission_error
        target.is_symlink = source.is_symlink
        target.modified_time = source.modified_time
        target.files = list(source.files)
        target.children = []

        # 递归复制子目录
        for child in source.children:
            child_copy = DirInfo(
                path=child.path,
                name=child.name,
                total_size=child.total_size,
                file_count=child.file_count,
                dir_count=child.dir_count,
                has_permission_error=child.has_permission_error,
                is_symlink=child.is_symlink,
                modified_time=child.modified_time,
                files=list(child.files),
            )
            child_copy.children = []
            self._copy_dir_info(child_copy, child)
            target.children.append(child_copy)

    def _report_progress(self) -> None:
        if self._on_progress:
            self._on_progress(self._scanned_dirs, self._permission_errors)


# ==================== 线程池辅助函数 ====================

_thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)


def _scan_entries(path: str) -> list[tuple[str, str, bool]]:
    """在线程池中扫描目录条目，返回 (路径, 名称, 是否目录)"""
    entries = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    if not entry.is_symlink():
                        entries.append((entry.path, entry.name, is_dir))
                except OSError:
                    pass
    except PermissionError:
        raise
    except OSError:
        pass
    return entries


def _scan_file(path: str, name: str) -> FileInfo | None:
    """在线程池中扫描单个文件"""
    try:
        stat = os.stat(path)
        return FileInfo(
            path=path,
            name=name,
            size=stat.st_size,
            extension=Path(name).suffix.lower(),
            modified_time=stat.st_mtime,
        )
    except OSError:
        return None


def build_old_dirs_map(dir_info: DirInfo) -> dict[str, DirInfo]:
    """从 DirInfo 构建路径映射，用于增量扫描"""
    result: dict[str, DirInfo] = {}

    def _collect(d: DirInfo) -> None:
        result[d.path] = d
        for child in d.children:
            _collect(child)

    if dir_info:
        _collect(dir_info)

    return result
