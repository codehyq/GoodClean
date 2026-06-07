"""缓存测试"""

import time
from pathlib import Path
from unittest.mock import patch

from goodclean.cache import (
    CACHE_DIR,
    clear_cache,
    get_cache_info,
    get_cache_path,
    list_all_caches,
    load_cache,
    save_cache,
)
from goodclean.models import DirInfo, FileInfo, ScanResult


def _make_result(root_path: str = "/test") -> ScanResult:
    fi = FileInfo(path="/test/file.txt", name="file.txt", size=100, extension=".txt", modified_time=time.time())
    di = DirInfo(path=root_path, name="test", total_size=100, file_count=1)
    di.files.append(fi)
    return ScanResult(root_path=root_path, total_size=100, total_files=1, total_dirs=0, root_dir=di)


class TestGetCachePath:
    def test_returns_path(self):
        p = get_cache_path("/some/path")
        assert isinstance(p, Path)
        assert p.suffix == ".pkl"

    def test_same_path_same_hash(self):
        p1 = get_cache_path("/same")
        p2 = get_cache_path("/same")
        assert p1 == p2


class TestSaveAndLoadCache:
    def test_save_and_load(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            result = _make_result("/test/save_load")
            saved = save_cache(result)
            assert saved is not None
            assert saved.exists()

            loaded = load_cache("/test/save_load")
            assert loaded is not None
            assert loaded.total_size == 100
            assert loaded.total_files == 1

    def test_load_expired_cache(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            result = _make_result("/test/expired")
            save_cache(result)

            # 手动修改 scan_time 为 48 小时前（pickle 二进制格式）
            cache_path = get_cache_path("/test/expired")
            import pickle
            with open(cache_path, "rb") as f:
                data = pickle.load(f)
            data["scan_time"] = time.time() - 48 * 3600
            with open(cache_path, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            loaded = load_cache("/test/expired")
            assert loaded is None

    def test_load_nonexistent(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            loaded = load_cache("/nonexistent")
            assert loaded is None


class TestClearCache:
    def test_clear_all(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            save_cache(_make_result("/a"))
            save_cache(_make_result("/b"))
            count = clear_cache()
            assert count == 2

    def test_clear_specific(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            save_cache(_make_result("/a"))
            save_cache(_make_result("/b"))
            count = clear_cache("/a")
            assert count == 1
            # /b should still exist
            assert get_cache_path("/b").exists()


class TestGetCacheInfo:
    def test_info(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            save_cache(_make_result("/test/info"))
            info = get_cache_info("/test/info")
            assert info is not None
            assert info["total_size"] == 100

    def test_info_nonexistent(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            info = get_cache_info("/nonexistent")
            assert info is None


class TestListAllCaches:
    def test_list(self, tmp_path):
        cache_dir = tmp_path / "cache"
        with patch("goodclean.cache.CACHE_DIR", cache_dir):
            save_cache(_make_result("/x"))
            caches = list_all_caches()
            assert len(caches) == 1
            assert caches[0]["total_size"] == 100
