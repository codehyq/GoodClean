"""配置持久化测试"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from goodclean.config import (
    _get_config_dir,
    _get_config_file,
    get_last_scan_path,
    get_sort_by_size,
    get_use_cache,
    load_config,
    save_config,
    set_last_scan_path,
    set_sort_by_size,
    set_use_cache,
)


@pytest.fixture(autouse=True)
def mock_config_dir(tmp_path):
    """使用临时目录作为配置目录"""
    test_dir = tmp_path / "test_config"
    with patch("goodclean.config._get_config_dir", return_value=test_dir):
        yield test_dir


class TestConfigIO:
    """测试配置读写"""

    def test_load_config_empty(self, mock_config_dir):
        """无配置文件时返回空字典"""
        assert load_config() == {}

    def test_save_and_load_config(self, mock_config_dir):
        """保存后能正确读取"""
        config = {"last_scan_path": "C:\\test", "use_cache": True}
        save_config(config)
        loaded = load_config()
        assert loaded == config

    def test_load_config_corrupted(self, mock_config_dir):
        """配置文件损坏时返回空字典"""
        config_file = _get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("not valid json", encoding="utf-8")
        assert load_config() == {}

    def test_save_config_creates_dir(self, mock_config_dir):
        """保存时自动创建配置目录"""
        save_config({"key": "value"})
        assert mock_config_dir.exists()


class TestLastScanPath:
    """测试上次扫描路径"""

    def test_get_last_scan_path_none(self, mock_config_dir):
        """无配置时返回 None"""
        assert get_last_scan_path() is None

    def test_set_and_get_last_scan_path(self, mock_config_dir, tmp_path):
        """设置后能正确读取"""
        test_dir = tmp_path / "scan_target"
        test_dir.mkdir()
        set_last_scan_path(str(test_dir))
        assert get_last_scan_path() == str(test_dir)

    def test_get_last_scan_path_nonexistent(self, mock_config_dir):
        """路径不存在时返回 None"""
        save_config({"last_scan_path": "C:\\nonexistent_path_12345"})
        assert get_last_scan_path() is None


class TestUseCache:
    """测试缓存开关配置"""

    def test_get_use_cache_none(self, mock_config_dir):
        """无配置时返回 None"""
        assert get_use_cache() is None

    def test_set_and_get_use_cache_true(self, mock_config_dir):
        """设置为 True"""
        set_use_cache(True)
        assert get_use_cache() is True

    def test_set_and_get_use_cache_false(self, mock_config_dir):
        """设置为 False"""
        set_use_cache(False)
        assert get_use_cache() is False


class TestSortBySize:
    """测试排序方式配置"""

    def test_get_sort_by_size_none(self, mock_config_dir):
        """无配置时返回 None"""
        assert get_sort_by_size() is None

    def test_set_and_get_sort_by_size_true(self, mock_config_dir):
        """设置为 True"""
        set_sort_by_size(True)
        assert get_sort_by_size() is True

    def test_set_and_get_sort_by_size_false(self, mock_config_dir):
        """设置为 False"""
        set_sort_by_size(False)
        assert get_sort_by_size() is False


class TestConfigIsolation:
    """测试配置隔离性"""

    def test_multiple_settings(self, mock_config_dir, tmp_path):
        """多个设置互不干扰"""
        test_dir = tmp_path / "scan_target"
        test_dir.mkdir()
        set_last_scan_path(str(test_dir))
        set_use_cache(False)
        set_sort_by_size(True)

        assert get_last_scan_path() == str(test_dir)
        assert get_use_cache() is False
        assert get_sort_by_size() is True
