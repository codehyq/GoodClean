"""数据模型：文件信息、目录信息、扫描结果"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FileInfo:
    """单个文件的信息"""
    path: str
    name: str
    size: int
    extension: str
    modified_time: float
    is_junk: bool = False
    junk_reason: str = ""

    @classmethod
    def from_path(cls, path: str | Path) -> Optional["FileInfo"]:
        """从文件路径创建 FileInfo"""
        try:
            p = Path(path)
            stat = p.stat()
            return cls(
                path=str(p),
                name=p.name,
                size=stat.st_size,
                extension=p.suffix.lower(),
                modified_time=stat.st_mtime,
            )
        except (OSError, PermissionError):
            return None


@dataclass
class DirInfo:
    """目录信息，包含子目录和文件的聚合数据"""
    path: str
    name: str
    total_size: int = 0
    file_count: int = 0
    dir_count: int = 0
    children: list["DirInfo"] = field(default_factory=list)
    files: list[FileInfo] = field(default_factory=list)
    has_permission_error: bool = False
    is_symlink: bool = False

    @property
    def depth(self) -> int:
        """目录深度"""
        return self.path.count(os.sep)

    def add_child_dir(self, child: "DirInfo") -> None:
        """添加子目录并更新统计"""
        self.children.append(child)
        self.total_size += child.total_size
        self.file_count += child.file_count
        self.dir_count += child.dir_count + 1

    def add_file(self, f: FileInfo) -> None:
        """添加文件并更新统计"""
        self.files.append(f)
        self.total_size += f.size
        self.file_count += 1


@dataclass
class ScanResult:
    """扫描结果"""
    root_path: str
    total_size: int = 0
    total_files: int = 0
    total_dirs: int = 0
    root_dir: Optional[DirInfo] = None
    top_dirs: list[DirInfo] = field(default_factory=list)
    large_files: list[FileInfo] = field(default_factory=list)
    junk_files: list[FileInfo] = field(default_factory=list)
    scan_duration: float = 0.0
    permission_errors: int = 0
