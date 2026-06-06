"""扫描器测试"""

import asyncio
import os
from pathlib import Path

import pytest

from goodclean.models import DirInfo, FileInfo
from goodclean.scanner import DirectoryScanner, build_old_dirs_map


class TestDirectoryScanner:
    def test_scan_basic(self, tmp_path):
        """基本扫描功能"""
        root = tmp_path / "scan_test"
        root.mkdir()
        (root / "a.txt").write_text("hello")
        (root / "b.txt").write_text("world")
        sub = root / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("nested")

        scanner = DirectoryScanner(str(root))
        result = asyncio.run(scanner.scan())

        assert result.name == "scan_test"
        assert result.total_size > 0
        assert result.file_count == 3
        assert result.dir_count == 1

    def test_scan_empty_dir(self, tmp_path):
        """扫描空目录"""
        root = tmp_path / "empty"
        root.mkdir()

        scanner = DirectoryScanner(str(root))
        result = asyncio.run(scanner.scan())

        assert result.name == "empty"
        assert result.total_size == 0
        assert result.file_count == 0
        assert result.dir_count == 0

    @pytest.mark.skipif(os.name == "nt", reason="Windows 权限模型不同")
    def test_scan_permission_error(self, tmp_path):
        """扫描遇到权限错误"""
        root = tmp_path / "perm_test"
        root.mkdir()
        (root / "readable.txt").write_text("ok")
        sub = root / "no_access"
        sub.mkdir()
        (sub / "secret.txt").write_text("secret")

        os.chmod(sub, 0o000)
        try:
            scanner = DirectoryScanner(str(root))
            result = asyncio.run(scanner.scan())
            assert result.file_count >= 1
            assert result.has_permission_error or any(
                c.has_permission_error for c in result.children
            )
        finally:
            os.chmod(sub, 0o755)

    @pytest.mark.skipif(os.name == "nt", reason="Windows 创建符号链接需要管理员权限")
    def test_scan_symlink_skipped(self, tmp_path):
        """符号链接被跳过"""
        root = tmp_path / "link_test"
        root.mkdir()
        (root / "real.txt").write_text("real")
        (root / "link.txt").symlink_to(root / "real.txt")

        scanner = DirectoryScanner(str(root))
        result = asyncio.run(scanner.scan())

        assert result.file_count == 1
        assert result.total_size == len("real")

    def test_scan_modified_time(self, tmp_path):
        """扫描记录修改时间"""
        root = tmp_path / "mtime_test"
        root.mkdir()
        f = root / "test.txt"
        f.write_text("hello")

        scanner = DirectoryScanner(str(root))
        result = asyncio.run(scanner.scan())

        assert result.modified_time > 0
        assert len(result.files) == 1
        assert result.files[0].modified_time > 0

    def test_cancel_scan(self, tmp_path):
        """取消扫描"""
        root = tmp_path / "cancel_test"
        root.mkdir()
        for i in range(100):
            (root / f"f{i}.txt").write_text("x")

        scanner = DirectoryScanner(str(root))
        scanner.cancel()
        result = asyncio.run(scanner.scan())
        # 取消后扫描应该尽快结束
        assert result is not None


class TestBuildOldDirsMap:
    def test_build_map(self, sample_dir):
        """从 DirInfo 构建路径映射"""
        root_info, _ = sample_dir
        old_map = build_old_dirs_map(root_info)

        assert str(root_info.path) in old_map
        for child in root_info.children:
            assert str(child.path) in old_map

    def test_empty_dir(self):
        """空目录映射"""
        di = DirInfo(path="/tmp/empty", name="empty")
        old_map = build_old_dirs_map(di)
        assert old_map == {"/tmp/empty": di}


class TestIncrementalScan:
    def test_copy_dir_info(self, sample_dir):
        """复制 DirInfo 信息"""
        root_info, _ = sample_dir
        scanner = DirectoryScanner("")
        target = DirInfo(path=root_info.path, name=root_info.name)
        scanner._copy_dir_info(target, root_info)

        assert target.total_size == root_info.total_size
        assert target.file_count == root_info.file_count
        assert target.dir_count == root_info.dir_count
        assert target.modified_time == root_info.modified_time
        assert len(target.children) == len(root_info.children)
        # 确保是深拷贝
        assert target.children is not root_info.children
