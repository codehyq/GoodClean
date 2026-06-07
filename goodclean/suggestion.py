"""清理建议系统：基于扫描结果生成分级清理建议

风险等级：
  - safe:    安全清理（垃圾文件、编译产物、IDE 缓存等）
  - caution: 谨慎清理（大日志、空文件、重复文件等）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .analyzer import format_size
from .constants import (
    JUNK_DIRNAMES,
    JUNK_EXTENSIONS,
    JUNK_FILENAMES,
    SIZE_MB,
)
from .models import DirInfo, FileInfo, ScanResult


@dataclass
class CleanupSuggestion:
    """一条清理建议"""
    name: str          # 显示名
    path: str          # 路径
    size: int          # 占用大小（字节）
    risk: str          # "safe" | "caution"
    reason: str        # 建议原因
    item_count: int    # 包含的文件数
    is_dir: bool       # 是否为目录
    paths: list[str] = field(default_factory=list)  # 具体文件路径列表


def generate_cleanup_suggestions(result: ScanResult) -> list[CleanupSuggestion]:
    """根据扫描结果生成清理建议列表，按可释放空间降序排列。"""
    if not result.root_dir:
        return []

    suggestions: list[CleanupSuggestion] = []

    # 1. 垃圾目录（safe）
    _collect_junk_dirs(result.root_dir, suggestions)

    # 2. 垃圾文件（safe，不在垃圾目录内的）
    _collect_junk_files(result.root_dir, suggestions)

    # 3. 大日志文件 > 10MB（caution）
    _collect_large_logs(result.root_dir, suggestions)

    # 4. 空文件（caution）
    _collect_empty_files(result.root_dir, suggestions)

    # 5. 重复文件（caution）
    _collect_duplicate_suggestions(result.root_dir, suggestions)

    # 按可释放空间降序排列
    suggestions.sort(key=lambda s: s.size, reverse=True)
    return suggestions


def get_suggestion_summary(suggestions: list[CleanupSuggestion]) -> dict:
    """计算建议汇总信息。"""
    safe = [s for s in suggestions if s.risk == "safe"]
    caution = [s for s in suggestions if s.risk == "caution"]
    return {
        "total_count": len(suggestions),
        "safe_count": len(safe),
        "caution_count": len(caution),
        "safe_size": sum(s.size for s in safe),
        "caution_size": sum(s.size for s in caution),
        "total_size": sum(s.size for s in suggestions),
    }


# ─── 内部收集函数 ────────────────────────────────────────────


def _collect_junk_dirs(di: DirInfo, result: list[CleanupSuggestion]) -> None:
    """收集垃圾目录作为安全清理项"""
    for child in di.children:
        dir_name = Path(child.path).name.lower()
        if dir_name in JUNK_DIRNAMES:
            file_count = _count_files_recursive(child)
            result.append(CleanupSuggestion(
                name=child.name,
                path=child.path,
                size=child.total_size,
                risk="safe",
                reason=f"缓存/构建目录 ({dir_name})",
                item_count=file_count,
                is_dir=True,
            ))
        else:
            _collect_junk_dirs(child, result)


def _collect_junk_files(di: DirInfo, result: list[CleanupSuggestion]) -> None:
    """收集散落的垃圾文件（不在垃圾目录内的）"""
    for f in di.files:
        if f.is_junk:
            # 检查是否已被目录级建议覆盖
            parent_name = Path(f.path).parent.name.lower()
            if parent_name in JUNK_DIRNAMES:
                continue
            result.append(CleanupSuggestion(
                name=f.name,
                path=f.path,
                size=f.size,
                risk="safe",
                reason=f.junk_reason or "垃圾文件",
                item_count=1,
                is_dir=False,
                paths=[f.path],
            ))

    for child in di.children:
        dir_name = Path(child.path).name.lower()
        if dir_name not in JUNK_DIRNAMES:
            _collect_junk_files(child, result)


def _collect_large_logs(di: DirInfo, result: list[CleanupSuggestion]) -> None:
    """收集大于 10MB 的日志文件"""
    _log_threshold = 10 * SIZE_MB

    def _scan(d: DirInfo) -> None:
        for f in d.files:
            if f.extension == ".log" and f.size >= _log_threshold:
                result.append(CleanupSuggestion(
                    name=f.name,
                    path=f.path,
                    size=f.size,
                    risk="caution",
                    reason=f"大日志文件 ({format_size(f.size)})",
                    item_count=1,
                    is_dir=False,
                    paths=[f.path],
                ))
        for child in d.children:
            _scan(child)

    _scan(di)


def _collect_empty_files(di: DirInfo, result: list[CleanupSuggestion]) -> None:
    """收集空文件"""
    empty_paths: list[str] = []
    empty_size = 0

    def _scan(d: DirInfo) -> None:
        nonlocal empty_size
        for f in d.files:
            if f.size == 0:
                empty_paths.append(f.path)
        for child in d.children:
            _scan(child)

    _scan(di)

    if empty_paths:
        result.append(CleanupSuggestion(
            name=f"空文件 ({len(empty_paths)} 个)",
            path="(分散在多个位置)",
            size=0,
            risk="caution",
            reason="0 字节空文件",
            item_count=len(empty_paths),
            is_dir=False,
            paths=empty_paths,
        ))


def _collect_duplicate_suggestions(di: DirInfo, result: list[CleanupSuggestion]) -> None:
    """收集重复文件（基于内容哈希，与 duplicate_finder 标准一致）"""
    from .duplicate_finder import find_duplicates

    duplicates = find_duplicates(di, min_size=1024)
    if not duplicates:
        return

    # 限制建议数量，避免大目录下性能问题
    max_groups = 100
    duplicates = duplicates[:max_groups]

    dup_paths: list[str] = []
    wasted = 0
    dup_count = 0

    for group in duplicates:
        # find_duplicates 已按修改时间排序，第一个为保留项
        for f in group[1:]:
            dup_paths.append(f.path)
            wasted += f.size
            dup_count += 1

    if dup_paths:
        result.append(CleanupSuggestion(
            name=f"重复文件 ({dup_count} 个)",
            path="(分散在多个位置)",
            size=wasted,
            risk="caution",
            reason=f"内容完全相同的重复副本，可节省 {format_size(wasted)}",
            item_count=dup_count,
            is_dir=False,
            paths=dup_paths,
        ))


def _count_files_recursive(di: DirInfo) -> int:
    """递归统计目录下文件数"""
    count = len(di.files)
    for child in di.children:
        count += _count_files_recursive(child)
    return count
