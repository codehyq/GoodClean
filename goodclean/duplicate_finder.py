"""重复文件检测：基于文件哈希识别重复文件"""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .models import DirInfo, FileInfo


def find_duplicates(root_dir: DirInfo, min_size: int = 1024) -> list[list[FileInfo]]:
    """查找重复文件
    
    Args:
        root_dir: 根目录信息
        min_size: 最小文件大小（字节），默认 1KB，过小的文件不检测
    
    Returns:
        重复文件组列表，每组包含相同内容的文件
    """
    # 第一步：按大小分组
    size_groups: dict[int, list[FileInfo]] = defaultdict(list)
    _collect_files_by_size(root_dir, size_groups, min_size)

    # 第二步：对大小相同的文件计算哈希
    hash_groups: dict[str, list[FileInfo]] = defaultdict(list)

    for size, files in size_groups.items():
        # 只有 2 个以上文件才需要检测
        if len(files) < 2:
            continue

        for f in files:
            file_hash = _compute_file_hash(f.path)
            if file_hash:
                hash_groups[file_hash].append(f)

    # 第三步：筛选出真正的重复文件（每组 2 个以上）
    duplicates = []
    for file_hash, files in hash_groups.items():
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


def _compute_file_hash(file_path: str, chunk_size: int = 8192) -> Optional[str]:
    """计算文件的 MD5 哈希值
    
    为了效率，只读取文件的前 8KB 和最后 8KB 来计算哈希
    对于大文件，这足以区分大多数不同的文件
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


def get_duplicate_stats(duplicates: list[list[FileInfo]]) -> dict:
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
