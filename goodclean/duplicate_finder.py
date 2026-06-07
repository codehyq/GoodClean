"""重复文件检测：基于文件哈希识别重复文件"""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from typing import Any

from .models import DirInfo, FileInfo


def find_duplicates(root_dir: DirInfo, min_size: int = 1024) -> list[list[FileInfo]]:
    """查找重复文件

    采用三层哈希策略确保正确性：
    1. 按文件大小分组（快速排除不同大小）
    2. 对头尾采样计算 preview_hash（快速预筛）
    3. 对 preview_hash 碰撞的文件计算 full_hash（全量确认）

    Args:
        root_dir: 根目录信息
        min_size: 最小文件大小（字节），默认 1KB，过小的文件不检测

    Returns:
        重复文件组列表，每组包含相同内容的文件
    """
    # 第一步：按大小分组
    size_groups: dict[int, list[FileInfo]] = defaultdict(list)
    _collect_files_by_size(root_dir, size_groups, min_size)

    # 第二步：对头尾采样计算 preview_hash
    preview_groups: dict[str, list[FileInfo]] = defaultdict(list)

    for _size, files in size_groups.items():
        if len(files) < 2:
            continue

        for f in files:
            preview_hash = _compute_preview_hash(f.path)
            if preview_hash:
                preview_groups[preview_hash].append(f)

    # 第三步：对 preview_hash 相同的文件计算 full_hash 确认
    full_hash_groups: dict[str, list[FileInfo]] = defaultdict(list)

    for _preview_hash, files in preview_groups.items():
        if len(files) < 2:
            continue

        for f in files:
            full_hash = _compute_full_hash(f.path)
            if full_hash:
                full_hash_groups[full_hash].append(f)

    # 第四步：筛选出真正的重复文件（每组 2 个以上）
    duplicates = []
    for _file_hash, files in full_hash_groups.items():
        if len(files) >= 2:
            # 按修改时间排序，保留最新的
            files.sort(key=lambda f: f.modified_time, reverse=True)
            duplicates.append(files)

    # 按总可节省空间排序（每组只保留一个，其余可删除）
    duplicates.sort(
        key=lambda group: sum(f.size for f in group[1:]),
        reverse=True,
    )

    return duplicates


def _collect_files_by_size(
    dir_info: DirInfo,
    size_groups: dict[int, list[FileInfo]],
    min_size: int,
) -> None:
    """递归收集文件，按大小分组"""
    for f in dir_info.files:
        if f.size >= min_size:
            size_groups[f.size].append(f)
    for child in dir_info.children:
        _collect_files_by_size(child, size_groups, min_size)


def _compute_preview_hash(file_path: str, chunk_size: int = 8192) -> str | None:
    """计算文件的预览哈希（快速预筛）

    小文件（≤16KB）直接全量读取；大文件读取头尾各 8KB 采样。
    返回的哈希仅用于初步分组，**不能**作为唯一判据。
    """
    try:
        file_size = os.path.getsize(file_path)

        # 小文件直接读取全部内容
        if file_size <= chunk_size * 2:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()

        # 大文件只读取头尾
        with open(file_path, "rb") as f:
            head = f.read(chunk_size)
            f.seek(-chunk_size, 2)  # 从末尾向前偏移
            tail = f.read(chunk_size)
            return hashlib.md5(head + tail).hexdigest()

    except (OSError, PermissionError):
        return None


def _compute_full_hash(file_path: str, chunk_size: int = 65536) -> str | None:
    """计算文件的完整 MD5 哈希（全量确认）

    分块读取文件内容，避免一次性加载大文件到内存。
    仅在 preview_hash 发生碰撞时调用，确保重复判断的准确性。
    """
    try:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


def get_duplicate_stats(duplicates: list[list[FileInfo]]) -> dict[str, Any]:
    """获取重复文件统计信息

    Returns:
        包含统计信息的字典
    """
    total_groups = len(duplicates)
    total_files = sum(len(group) for group in duplicates)
    total_size = sum(
        sum(f.size for f in group[1:])  # 每组保留第一个，其余可节省
        for group in duplicates
    )
    waste_size = sum(
        sum(f.size for f in group)  # 每组的总大小
        for group in duplicates
    )

    return {
        "total_groups": total_groups,
        "total_files": total_files,
        "total_size": total_size,  # 可节省的空间
        "waste_size": waste_size,  # 总浪费空间
    }


def get_duplicate_savings(duplicates: list[list[FileInfo]]) -> int:
    """计算删除重复文件后可节省的空间（每组保留第一个文件）"""
    savings = 0
    for group in duplicates:
        # 每组保留第一个（最新的），删除其余
        for f in group[1:]:
            savings += f.size
    return savings
