"""清理建议系统测试"""

from pathlib import Path

from goodclean.models import DirInfo, FileInfo, ScanResult
from goodclean.suggestion import (
    CleanupSuggestion,
    generate_cleanup_suggestions,
    get_suggestion_summary,
)
from goodclean.analyzer import analyze


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


class TestGenerateCleanupSuggestions:
    def test_finds_junk_dirs(self, scan_result):
        suggestions = generate_cleanup_suggestions(scan_result)
        safe = [s for s in suggestions if s.risk == "safe"]
        assert len(safe) > 0

    def test_empty_result(self):
        empty = ScanResult(root_path="/empty")
        suggestions = generate_cleanup_suggestions(empty)
        assert suggestions == []

    def test_suggestions_sorted_by_size(self, scan_result):
        suggestions = generate_cleanup_suggestions(scan_result)
        for i in range(len(suggestions) - 1):
            assert suggestions[i].size >= suggestions[i + 1].size

    def test_large_logs_caution(self, large_log_dir):
        root_info, root_path = large_log_dir
        result = analyze(root_info, root_path)
        suggestions = generate_cleanup_suggestions(result)
        caution = [s for s in suggestions if s.risk == "caution"]
        log_suggestions = [s for s in caution if "日志" in s.reason]
        assert len(log_suggestions) >= 1

    def test_empty_files_caution(self, tmp_path):
        root = tmp_path / "empty_test"
        root.mkdir()
        (root / "empty1.txt").touch()
        (root / "empty2.txt").touch()

        root_info = _build_dir(root)
        result = analyze(root_info, str(root))
        suggestions = generate_cleanup_suggestions(result)
        empty_suggestions = [s for s in suggestions if "空文件" in s.name]
        assert len(empty_suggestions) == 1
        assert empty_suggestions[0].item_count == 2


class TestDuplicateSuggestions:
    def test_real_duplicates_detected(self, tmp_path):
        """内容相同的文件（即使不同名）应被检测为重复"""
        root = tmp_path / "dup_test"
        root.mkdir()
        content = b"duplicate payload " * 200
        (root / "file_a.bin").write_bytes(content)
        (root / "file_b.bin").write_bytes(content)

        root_info = _build_dir(root)
        result = analyze(root_info, str(root))
        suggestions = generate_cleanup_suggestions(result)
        dup_suggestions = [s for s in suggestions if "重复" in s.name]
        assert len(dup_suggestions) == 1
        assert dup_suggestions[0].item_count == 1  # 1 个可删除副本

    def test_same_name_size_different_content_not_duplicate(self, tmp_path):
        """同名同大小但内容不同的文件不应被误判为重复"""
        root = tmp_path / "false_dup"
        root.mkdir()
        # 两个 24KB 文件，同名（通过不同子目录实现），大小相同，内容不同
        sub_a = root / "a"
        sub_a.mkdir()
        sub_b = root / "b"
        sub_b.mkdir()
        (sub_a / "data.bin").write_bytes(b"A" * 24576)
        (sub_b / "data.bin").write_bytes(b"B" * 24576)

        root_info = _build_dir(root)
        result = analyze(root_info, str(root))
        suggestions = generate_cleanup_suggestions(result)
        dup_suggestions = [s for s in suggestions if "重复" in s.name]
        assert len(dup_suggestions) == 0


class TestGetSuggestionSummary:
    def test_summary_counts(self, scan_result):
        suggestions = generate_cleanup_suggestions(scan_result)
        summary = get_suggestion_summary(suggestions)
        assert summary["total_count"] == summary["safe_count"] + summary["caution_count"]
        assert summary["total_size"] == summary["safe_size"] + summary["caution_size"]

    def test_empty_summary(self):
        summary = get_suggestion_summary([])
        assert summary["total_count"] == 0
        assert summary["total_size"] == 0
