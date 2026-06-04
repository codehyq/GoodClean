"""文件头识别测试"""

import pytest

from goodclean.file_type_identifier import (
    classify_file_type,
    get_real_extension,
    identify_by_magic_bytes,
    needs_magic_check,
)


class TestIdentifyByMagicBytes:
    def test_jpeg(self, tmp_path):
        f = tmp_path / "photo"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        assert "JPEG" in identify_by_magic_bytes(str(f))

    def test_png(self, tmp_path):
        f = tmp_path / "image"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        assert "PNG" in identify_by_magic_bytes(str(f))

    def test_pdf(self, tmp_path):
        f = tmp_path / "doc"
        f.write_bytes(b"%PDF-1.4" + b"\x00" * 100)
        assert "PDF" in identify_by_magic_bytes(str(f))

    def test_zip(self, tmp_path):
        f = tmp_path / "archive"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        assert "ZIP" in identify_by_magic_bytes(str(f))

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty"
        f.touch()
        assert identify_by_magic_bytes(str(f)) == ""

    def test_nonexistent_file(self):
        assert identify_by_magic_bytes("/nonexistent") == ""

    def test_unknown_content(self, tmp_path):
        f = tmp_path / "unknown"
        f.write_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08")
        assert identify_by_magic_bytes(str(f)) == ""


class TestNeedsMagicCheck:
    def test_known_extension(self):
        assert needs_magic_check(".jpg") is False
        assert needs_magic_check(".py") is False
        assert needs_magic_check(".json") is False

    def test_unknown_extension(self):
        assert needs_magic_check(".xyz") is True
        assert needs_magic_check("") is True

    def test_case_insensitive(self):
        assert needs_magic_check(".JPG") is False
        assert needs_magic_check(".Py") is False


class TestGetRealExtension:
    def test_jpeg_without_ext(self, tmp_path):
        f = tmp_path / "noext"
        f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        assert get_real_extension(str(f)) == ".jpg"

    def test_png_without_ext(self, tmp_path):
        f = tmp_path / "noext"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        assert get_real_extension(str(f)) == ".png"

    def test_unknown_returns_empty(self, tmp_path):
        f = tmp_path / "noext"
        f.write_bytes(b"\x01\x02\x03\x04")
        assert get_real_extension(str(f)) == ""


class TestClassifyFileType:
    def test_known_extensions(self):
        assert classify_file_type(".jpg", "/f", 100) == "图片"
        assert classify_file_type(".mp4", "/f", 100) == "视频"
        assert classify_file_type(".py", "/f", 100) == "代码"
        assert classify_file_type(".json", "/f", 100) == "配置"
        assert classify_file_type(".zip", "/f", 100) == "压缩包"

    def test_empty_file(self):
        assert classify_file_type("", "/f", 0) == "空文件"

    def test_unknown_ext_with_magic(self, tmp_path):
        f = tmp_path / "unknown_ext"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = classify_file_type(".unknown", str(f), f.stat().st_size)
        assert result == "图片"
