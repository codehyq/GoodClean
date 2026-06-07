"""分析引擎：大小聚合、垃圾文件识别、Top N 排行、文件类型分析"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Optional

from .constants import (
    JUNK_DIRNAMES,
    JUNK_EXTENSIONS,
    JUNK_FILENAMES,
    LARGE_FILE_THRESHOLD,
)
from .file_type_identifier import classify_file_type
from .models import DirInfo, FileInfo, ScanResult


def analyze(root_dir: DirInfo, root_path: str) -> ScanResult:
    """分析扫描结果，生成完整报告

    使用单次树遍历同时完成垃圾标记、文件分类、目录收集、
    文件收集和权限错误统计，将分析阶段复杂度从 4×O(N) 降至 1×O(N)。
    """
    result = ScanResult(root_path=root_path)
    result.root_dir = root_dir
    result.total_size = root_dir.total_size
    result.total_files = root_dir.file_count
    result.total_dirs = root_dir.dir_count

    all_dirs: list[DirInfo] = []
    all_files: list[FileInfo] = []
    permission_errors = 0

    def _walk(di: DirInfo) -> None:
        nonlocal permission_errors
        # 标记垃圾文件并分类（原 _mark_junk_files 的单层逻辑）
        dir_name = Path(di.path).name.lower()
        is_junk_dir = dir_name in JUNK_DIRNAMES
        for f in di.files:
            _check_file_junk(f, is_junk_dir)
            f.file_type = classify_file_type(f.extension, f.path, f.size)
            all_files.append(f)

        all_dirs.append(di)
        if di.has_permission_error:
            permission_errors += 1

        for child in di.children:
            _walk(child)

    _walk(root_dir)

    result.top_dirs = sorted(all_dirs, key=lambda d: d.total_size, reverse=True)[:50]
    result.large_files = sorted(
        [f for f in all_files if f.size >= LARGE_FILE_THRESHOLD],
        key=lambda f: f.size,
        reverse=True,
    )[:100]
    result.junk_files = sorted(
        [f for f in all_files if f.is_junk],
        key=lambda f: f.size,
        reverse=True,
    )[:200]
    result.permission_errors = permission_errors

    return result


def format_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _mark_junk_files(dir_info: DirInfo, root_path: str) -> None:
    """递归标记垃圾文件并分类文件类型"""
    # 检查目录本身是否是垃圾目录
    dir_name = Path(dir_info.path).name.lower()
    is_junk_dir = dir_name in JUNK_DIRNAMES

    for f in dir_info.files:
        _check_file_junk(f, is_junk_dir)
        f.file_type = classify_file_type(f.extension, f.path, f.size)

    for child in dir_info.children:
        child_name = Path(child.path).name.lower()
        child_is_junk = child_name in JUNK_DIRNAMES
        for f in child.files:
            _check_file_junk(f, child_is_junk)
            f.file_type = classify_file_type(f.extension, f.path, f.size)
        _mark_junk_files(child, root_path)


def _check_file_junk(file_info: FileInfo, in_junk_dir: bool) -> None:
    """检查单个文件是否是垃圾文件"""
    name_lower = file_info.name.lower()

    # 检查文件名
    if name_lower in JUNK_FILENAMES:
        file_info.is_junk = True
        file_info.junk_reason = "系统文件"
        return

    # 检查扩展名
    if file_info.extension in JUNK_EXTENSIONS:
        file_info.is_junk = True
        reason_map = {
            ".tmp": "临时文件",
            ".temp": "临时文件",
            ".bak": "备份文件",
            ".swp": "交换文件",
            ".swo": "交换文件",
            ".log": "日志文件",
            ".pyc": "编译缓存",
            ".pyo": "编译缓存",
            ".obj": "编译产物",
            ".o": "编译产物",
            ".class": "编译产物",
            ".thumbs.db": "缩略图缓存",
            ".ds_store": "系统文件",
        }
        file_info.junk_reason = reason_map.get(file_info.extension, "垃圾文件")
        return

    # 在垃圾目录中的文件
    if in_junk_dir:
        file_info.is_junk = True
        file_info.junk_reason = "缓存/构建产物"
        return

    # 模糊匹配
    for pattern in ["~$*", "*.thumbs.db"]:
        if fnmatch.fnmatch(name_lower, pattern):
            file_info.is_junk = True
            file_info.junk_reason = "临时文件"
            return


def _collect_dirs(dir_info: DirInfo, result: list[DirInfo]) -> None:
    """收集所有目录"""
    for child in dir_info.children:
        result.append(child)
        _collect_dirs(child, result)


def _collect_files(dir_info: DirInfo, result: list[FileInfo]) -> None:
    """收集所有文件"""
    result.extend(dir_info.files)
    for child in dir_info.children:
        _collect_files(child, result)


def _count_permission_errors(dir_info: DirInfo) -> int:
    """统计权限错误数量"""
    count = 1 if dir_info.has_permission_error else 0
    for child in dir_info.children:
        count += _count_permission_errors(child)
    return count


def get_file_type_distribution(dir_info: DirInfo) -> dict[str, tuple[int, int]]:
    """获取文件类型分布：{扩展名: (文件数, 总大小)}"""
    dist: dict[str, tuple[int, int]] = {}

    def _collect(d: DirInfo) -> None:
        for f in d.files:
            ext = f.extension or "(无扩展名)"
            if ext not in dist:
                dist[ext] = (0, 0)
            count, size = dist[ext]
            dist[ext] = (count + 1, size + f.size)
        for child in d.children:
            _collect(child)

    _collect(dir_info)
    return dict(sorted(dist.items(), key=lambda x: x[1][1], reverse=True))


def get_file_category_distribution(dir_info: DirInfo) -> list[dict]:
    """获取文件按逻辑类型的分布统计。

    使用 file_type 字段（已通过文件头/扩展名分类），返回按大小降序的列表。
    返回格式：[{"category": "图片", "count": 120, "total_size": 52428800, "top_ext": ".jpg"}, ...]
    """
    categories: dict[str, dict[str, object]] = {}
    ext_counter: dict[str, dict[str, int]] = {}  # category -> {ext: count}

    def _collect(d: DirInfo) -> None:
        for f in d.files:
            cat = f.file_type or "其他"
            if cat not in categories:
                categories[cat] = {"category": cat, "count": 0, "total_size": 0, "top_ext": ""}
                ext_counter[cat] = {}
            categories[cat]["count"] = int(categories[cat]["count"]) + 1  # type: ignore
            categories[cat]["total_size"] = int(categories[cat]["total_size"]) + f.size  # type: ignore

            ext = f.extension or "(无)"
            ext_counter[cat][ext] = ext_counter[cat].get(ext, 0) + 1

        for child in d.children:
            _collect(child)

    _collect(dir_info)

    # 为每个分类找 top 扩展名
    for cat, exts in ext_counter.items():
        if exts:
            top_ext = max(exts, key=exts.get)  # type: ignore
            categories[cat]["top_ext"] = top_ext

    result = sorted(categories.values(), key=lambda x: x["total_size"], reverse=True)  # type: ignore
    return result  # type: ignore
