"""公共测试 fixtures：临时目录结构、ScanResult 等"""

import time
from pathlib import Path

import pytest

from goodclean.models import DirInfo, FileInfo, ScanResult


@pytest.fixture
def sample_file(tmp_path):
    """创建一个临时文件并返回路径"""
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")
    return f


@pytest.fixture
def sample_dir(tmp_path):
    """创建包含多种类型文件的临时目录结构，返回 (DirInfo, root_path)"""
    root = tmp_path / "scan_target"
    root.mkdir()

    # 正常文件
    (root / "readme.md").write_text("# Hello", encoding="utf-8")
    (root / "main.py").write_text("print('hi')", encoding="utf-8")
    (root / "config.json").write_text('{"key": "value"}', encoding="utf-8")

    # 垃圾文件
    (root / "temp.tmp").write_bytes(b"\x00" * 2048)
    (root / "backup.bak").write_bytes(b"\x00" * 1024)

    # 空文件
    (root / "empty.txt").touch()

    # 重复文件（两个同内容）
    dup_content = b"duplicate content here " * 100
    (root / "copy_a.bin").write_bytes(dup_content)
    sub = root / "subdir"
    sub.mkdir()
    (sub / "copy_b.bin").write_bytes(dup_content)

    # 垃圾目录 __pycache__
    pycache = root / "__pycache__"
    pycache.mkdir()
    (pycache / "module.cpython-310.pyc").write_bytes(b"\x0d\x0d\x0a" + b"\x00" * 100)

    # 垃圾目录 node_modules
    nm = root / "node_modules"
    nm.mkdir()
    pkg = nm / "package"
    pkg.mkdir()
    (pkg / "index.js").write_text("module.exports = {}", encoding="utf-8")
    (pkg / "readme.txt").write_text("pkg readme", encoding="utf-8")

    # 垃圾目录 dist
    dist = root / "dist"
    dist.mkdir()
    (dist / "bundle.js").write_text("var x=1;", encoding="utf-8")

    # 正常子目录
    src = root / "src"
    src.mkdir()
    (src / "app.py").write_text("def main(): pass", encoding="utf-8")

    # 构建 DirInfo
    def build_dir(path: Path) -> DirInfo:
        di = DirInfo(path=str(path), name=path.name)
        for item in path.iterdir():
            if item.is_file():
                stat = item.stat()
                fi = FileInfo(
                    path=str(item),
                    name=item.name,
                    size=stat.st_size,
                    extension=item.suffix.lower(),
                    modified_time=stat.st_mtime,
                )
                di.add_file(fi)
            elif item.is_dir():
                child = build_dir(item)
                di.add_child_dir(child)
        return di

    root_info = build_dir(root)
    return root_info, str(root)


@pytest.fixture
def scan_result(sample_dir):
    """基于 sample_dir 生成的完整 ScanResult"""
    root_info, root_path = sample_dir
    from goodclean.analyzer import analyze

    return analyze(root_info, root_path)


@pytest.fixture
def large_log_dir(tmp_path):
    """创建包含大日志文件的目录"""
    root = tmp_path / "log_target"
    root.mkdir()
    # 11MB 的日志文件
    (root / "app.log").write_bytes(b"x" * (11 * 1024 * 1024))
    # 小日志文件（不触发 caution）
    (root / "debug.log").write_bytes(b"y" * 1024)

    def build_dir(path: Path) -> DirInfo:
        di = DirInfo(path=str(path), name=path.name)
        for item in path.iterdir():
            if item.is_file():
                stat = item.stat()
                fi = FileInfo(
                    path=str(item),
                    name=item.name,
                    size=stat.st_size,
                    extension=item.suffix.lower(),
                    modified_time=stat.st_mtime,
                )
                di.add_file(fi)
            elif item.is_dir():
                di.add_child_dir(build_dir(item))
        return di

    return build_dir(root), str(root)
