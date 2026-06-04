"""分析引擎测试"""

from pathlib import Path

from goodclean.analyzer import (
    analyze,
    format_size,
    get_file_category_distribution,
    get_file_type_distribution,
)
from goodclean.constants import JUNK_EXTENSIONS
from goodclean.models import DirInfo, FileInfo, ScanResult


class TestFormatSize:
    def test_bytes(self):
        assert format_size(0) == "0 B"
        assert format_size(512) == "512 B"
        assert format_size(1023) == "1023 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"

    def test_megabytes(self):
        mb = 1024 * 1024
        assert format_size(mb) == "1.0 MB"
        assert format_size(mb * 256) == "256.0 MB"

    def test_gigabytes(self):
        gb = 1024 * 1024 * 1024
        assert format_size(gb) == "1.00 GB"


class TestAnalyze:
    def test_basic_analysis(self, scan_result):
        assert scan_result.total_files > 0
        assert scan_result.total_dirs > 0
        assert scan_result.total_size > 0
        assert scan_result.root_dir is not None

    def test_junk_files_detected(self, scan_result):
        assert len(scan_result.junk_files) > 0

    def test_top_dirs_sorted(self, scan_result):
        if len(scan_result.top_dirs) > 1:
            for i in range(len(scan_result.top_dirs) - 1):
                assert scan_result.top_dirs[i].total_size >= scan_result.top_dirs[i + 1].total_size


class TestCheckFileJunk:
    def test_junk_extension(self):
        for ext in [".tmp", ".pyc", ".bak", ".log"]:
            fi = FileInfo(path="/f", name=f"test{ext}", size=100, extension=ext, modified_time=0.0)
            from goodclean.analyzer import _check_file_junk
            _check_file_junk(fi, in_junk_dir=False)
            assert fi.is_junk is True, f"{ext} should be junk"

    def test_junk_filename(self):
        for name in ["thumbs.db", "desktop.ini", ".ds_store"]:
            fi = FileInfo(path="/f", name=name, size=100, extension="", modified_time=0.0)
            from goodclean.analyzer import _check_file_junk
            _check_file_junk(fi, in_junk_dir=False)
            assert fi.is_junk is True, f"{name} should be junk"

    def test_in_junk_dir(self):
        fi = FileInfo(path="/f", name="something.js", size=100, extension=".js", modified_time=0.0)
        from goodclean.analyzer import _check_file_junk
        _check_file_junk(fi, in_junk_dir=True)
        assert fi.is_junk is True

    def test_normal_file_not_junk(self):
        fi = FileInfo(path="/f", name="readme.md", size=100, extension=".md", modified_time=0.0)
        from goodclean.analyzer import _check_file_junk
        _check_file_junk(fi, in_junk_dir=False)
        assert fi.is_junk is False


class TestFileTypeDistribution:
    def test_returns_sorted_by_size(self, scan_result):
        dist = get_file_type_distribution(scan_result.root_dir)
        sizes = [v[1] for v in dist.values()]
        assert sizes == sorted(sizes, reverse=True)

    def test_covers_all_files(self, scan_result):
        dist = get_file_type_distribution(scan_result.root_dir)
        total_from_dist = sum(v[0] for v in dist.values())
        assert total_from_dist == scan_result.total_files


class TestFileCategoryDistribution:
    def test_returns_list(self, scan_result):
        result = get_file_category_distribution(scan_result.root_dir)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_has_required_fields(self, scan_result):
        result = get_file_category_distribution(scan_result.root_dir)
        for item in result:
            assert "category" in item
            assert "count" in item
            assert "total_size" in item
            assert "top_ext" in item
