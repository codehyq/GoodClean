"""清理器测试"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from goodclean.cleaner import (
    CleanResult,
    _expand_paths,
    _get_path_size,
    permanent_delete,
    trash_files,
)


class TestExpandPaths:
    def test_expand_file(self, tmp_path):
        """展开单个文件"""
        f = tmp_path / "test.txt"
        f.write_text("hello")

        items = _expand_paths([str(f)])
        assert len(items) == 1
        assert items[0][0] == str(f)
        assert items[0][1] == 5

    def test_expand_dir(self, tmp_path):
        """展开目录"""
        root = tmp_path / "dir"
        root.mkdir()
        (root / "a.txt").write_text("a")
        (root / "b.txt").write_text("bb")

        items = _expand_paths([str(root)])
        assert len(items) == 2

    def test_expand_nonexistent(self, tmp_path):
        """展开不存在的路径"""
        items = _expand_paths([str(tmp_path / "nope")])
        assert len(items) == 1
        assert items[0][1] == 0


class TestGetPathSize:
    def test_file_size(self, tmp_path):
        """获取文件大小"""
        f = tmp_path / "test.txt"
        f.write_text("hello world")

        assert _get_path_size(f) == 11

    def test_dir_size(self, tmp_path):
        """获取目录大小"""
        root = tmp_path / "dir"
        root.mkdir()
        (root / "a.txt").write_text("aaa")
        (root / "b.txt").write_text("bb")

        assert _get_path_size(root) == 5

    def test_nonexistent(self, tmp_path):
        """不存在的路径"""
        assert _get_path_size(tmp_path / "nope") == 0


class TestPermanentDelete:
    def test_delete_file(self, tmp_path):
        """永久删除文件"""
        f = tmp_path / "del.txt"
        f.write_text("bye")

        result = permanent_delete([str(f)])
        assert result.success_count == 1
        assert not f.exists()

    def test_delete_dir(self, tmp_path):
        """永久删除目录"""
        root = tmp_path / "del_dir"
        root.mkdir()
        (root / "a.txt").write_text("a")
        (root / "b.txt").write_text("b")

        result = permanent_delete([str(root)])
        assert result.success_count >= 1
        assert not root.exists()

    def test_delete_nonexistent(self, tmp_path):
        """删除不存在的路径"""
        result = permanent_delete([str(tmp_path / "nope")])
        assert result.fail_count == 1

    def test_delete_readonly_file(self, tmp_path):
        """删除只读文件"""
        f = tmp_path / "readonly.txt"
        f.write_text("cant touch this")
        os.chmod(f, 0o444)

        result = permanent_delete([str(f)])
        assert result.success_count == 1
        assert not f.exists()


class TestTrashFiles:
    @patch("goodclean.cleaner.send2trash")
    def test_trash_file(self, mock_send2trash, tmp_path):
        """移到回收站"""
        f = tmp_path / "trash.txt"
        f.write_text("trash me")

        result = trash_files([str(f)])
        assert result.success_count >= 1
        mock_send2trash.assert_called()

    @patch("goodclean.cleaner.send2trash")
    def test_trash_nonexistent(self, mock_send2trash, tmp_path):
        """回收站不存在的路径"""
        result = trash_files([str(tmp_path / "nope")])
        assert result.fail_count == 1


class TestProgressCallback:
    def test_permanent_delete_progress(self, tmp_path):
        """永久删除进度回调"""
        root = tmp_path / "prog_dir"
        root.mkdir()
        (root / "a.txt").write_text("a")
        (root / "b.txt").write_text("b")

        progress_calls = []

        def on_progress(current, total, path, freed):
            progress_calls.append((current, total, path, freed))

        permanent_delete([str(root)], on_progress=on_progress)
        assert len(progress_calls) > 0
        # 最后一个调用应该是完成的
        assert progress_calls[-1][0] == progress_calls[-1][1]

    @patch("goodclean.cleaner.send2trash")
    def test_trash_progress(self, mock_send2trash, tmp_path):
        """回收站进度回调"""
        root = tmp_path / "prog_dir"
        root.mkdir()
        (root / "a.txt").write_text("a")

        progress_calls = []

        def on_progress(current, total, path, freed):
            progress_calls.append((current, total, path, freed))

        trash_files([str(root)], on_progress=on_progress)
        assert len(progress_calls) > 0
