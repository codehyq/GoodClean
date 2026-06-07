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

    def test_large_file_duplicates(self, tmp_path):
        """大于 16KB 的真正重复文件应被正确识别"""
        content = b"X" * 50000
        (tmp_path / "big_a.bin").write_bytes(content)
        (tmp_path / "big_b.bin").write_bytes(content)

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=1)
        assert len(dupes) == 1
        assert len(dupes[0]) == 2

    def test_head_tail_collision_not_duplicate(self, tmp_path):
        """头尾相同但中间不同的大文件不应被误判为重复"""
        # 构造两个 24KB 文件：前 8KB 和后 8KB 相同，中间 8KB 不同
        head = b"HEAD" * 2048
        mid_a = b"MIDDLE_A" * 1024
        mid_b = b"MIDDLE_B" * 1024
        tail = b"TAIL" * 2048

        (tmp_path / "collide_a.bin").write_bytes(head + mid_a + tail)
        (tmp_path / "collide_b.bin").write_bytes(head + mid_b + tail)

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=1)
        # 头尾哈希会碰撞，但全量哈希应排除它们
        assert len(dupes) == 0

    def test_three_layer_hash(self, tmp_path):
        """验证三层哈希：大小不同直接排除；大小相同但内容不同排除；真正重复保留"""
        (tmp_path / "same_1.bin").write_bytes(b"D" * 30000)
        (tmp_path / "same_2.bin").write_bytes(b"D" * 30000)
        (tmp_path / "diff.bin").write_bytes(b"E" * 30000)

        root = _build_dir(tmp_path)
        dupes = find_duplicates(root, min_size=1)
        assert len(dupes) == 1
        names = {f.name for f in dupes[0]}
        assert names == {"same_1.bin", "same_2.bin"}


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
