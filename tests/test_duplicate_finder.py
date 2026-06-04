"""重复文件检测测试"""

from pathlib import Path

from goodclean.duplicate_finder import (
    find_duplicates,
    get_duplicate_stats,
    get_duplicate_savings,
)
from goodclean.models import DirInfo, FileInfo


def _build_dir(path: Path) -> DirInfo:
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
            child = _build_dir(item)
            di.add_child_dir(child)
    return di


class TestFindDuplicates:
    def test_finds_duplicates(self, tmp_path):
        content = b"same content " * 200
        (tmp_path / "a.bin").write_bytes(content)
        (tmp_path / "b.bin").write_bytes(content)
        (tmp_path / "unique.bin").write_bytes(b"something else " * 200)

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=100)
        assert len(dupes) == 1
        assert len(dupes[0]) == 2

    def test_no_duplicates(self, tmp_path):
        (tmp_path / "a.bin").write_bytes(b"aaa")
        (tmp_path / "b.bin").write_bytes(b"bbb")

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=1)
        assert len(dupes) == 0

    def test_min_size_filter(self, tmp_path):
        content = b"tiny"
        (tmp_path / "a.bin").write_bytes(content)
        (tmp_path / "b.bin").write_bytes(content)

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=100)
        assert len(dupes) == 0


class TestDuplicateStats:
    def test_stats(self, tmp_path):
        content = b"x" * 200
        (tmp_path / "a.bin").write_bytes(content)
        (tmp_path / "b.bin").write_bytes(content)
        (tmp_path / "c.bin").write_bytes(content)

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=100)
        stats = get_duplicate_stats(dupes)
        assert stats["total_groups"] == 1
        assert stats["total_files"] == 3


class TestDuplicateSavings:
    def test_savings(self, tmp_path):
        content = b"save me " * 200
        (tmp_path / "a.bin").write_bytes(content)
        (tmp_path / "b.bin").write_bytes(content)

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=100)
        savings = get_duplicate_savings(dupes)
        size = (tmp_path / "a.bin").stat().st_size
        assert savings == size  # one copy can be saved
