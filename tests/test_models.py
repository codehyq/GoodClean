"""数据模型测试"""

import os
from pathlib import Path

from goodclean.models import DirInfo, FileInfo, ScanResult


class TestFileInfo:
    def test_from_path_success(self, sample_file):
        fi = FileInfo.from_path(sample_file)
        assert fi is not None
        assert fi.name == "test.txt"
        assert fi.extension == ".txt"
        assert fi.size > 0
        assert fi.path == str(sample_file)

    def test_from_path_nonexistent(self):
        fi = FileInfo.from_path("/nonexistent/file.txt")
        assert fi is None

    def test_default_fields(self):
        fi = FileInfo(path="/a", name="a", size=10, extension=".txt", modified_time=0.0)
        assert fi.is_junk is False
        assert fi.junk_reason == ""
        assert fi.file_type == ""


class TestDirInfo:
    def test_add_file(self, tmp_path):
        d = DirInfo(path=str(tmp_path), name="test")
        f = FileInfo(path="/f", name="f", size=100, extension=".txt", modified_time=0.0)
        d.add_file(f)
        assert d.file_count == 1
        assert d.total_size == 100
        assert len(d.files) == 1

    def test_add_child_dir(self, tmp_path):
        parent = DirInfo(path=str(tmp_path), name="parent")
        child = DirInfo(path=str(tmp_path / "child"), name="child", total_size=500, file_count=3, dir_count=1)
        parent.add_child_dir(child)
        assert parent.file_count == 3
        assert parent.total_size == 500
        assert parent.dir_count == 2  # child + 1
        assert len(parent.children) == 1

    def test_depth(self, tmp_path):
        d = DirInfo(path=str(tmp_path / "a" / "b" / "c"), name="c")
        expected = str(tmp_path / "a" / "b" / "c").count(os.sep)
        assert d.depth == expected


class TestScanResult:
    def test_defaults(self):
        r = ScanResult(root_path="/test")
        assert r.root_path == "/test"
        assert r.total_size == 0
        assert r.total_files == 0
        assert r.total_dirs == 0
        assert r.root_dir is None
        assert r.top_dirs == []
        assert r.large_files == []
        assert r.junk_files == []
        assert r.scan_duration == 0.0
        assert r.permission_errors == 0
