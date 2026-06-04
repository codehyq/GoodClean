"""报告导出测试"""

import csv
import json
from pathlib import Path

from goodclean.exporter import export_csv, export_html, export_json, export_report
from goodclean.models import ScanResult


class TestExportJson:
    def test_creates_valid_json(self, scan_result, tmp_path):
        output = str(tmp_path / "report.json")
        result = export_json(scan_result, output)
        assert Path(result).exists()

        with open(result, encoding="utf-8") as f:
            data = json.load(f)
        assert "scan_info" in data
        assert data["scan_info"]["total_files"] > 0

    def test_includes_top_dirs(self, scan_result, tmp_path):
        output = str(tmp_path / "report.json")
        export_json(scan_result, output)
        with open(output, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data["top_dirs"], list)


class TestExportCsv:
    def test_creates_valid_csv(self, scan_result, tmp_path):
        output = str(tmp_path / "report.csv")
        result = export_csv(scan_result, output)
        assert Path(result).exists()

        with open(result, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) > 5  # header + data rows


class TestExportHtml:
    def test_creates_valid_html(self, scan_result, tmp_path):
        output = str(tmp_path / "report.html")
        result = export_html(scan_result, output)
        assert Path(result).exists()

        content = Path(result).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "GoodClean" in content


class TestExportReport:
    def test_auto_json(self, scan_result, tmp_path):
        output = str(tmp_path / "report.json")
        result = export_report(scan_result, output, format="auto")
        assert result.endswith(".json")

    def test_auto_csv(self, scan_result, tmp_path):
        output = str(tmp_path / "report.csv")
        result = export_report(scan_result, output, format="auto")
        assert result.endswith(".csv")

    def test_auto_html(self, scan_result, tmp_path):
        output = str(tmp_path / "report.html")
        result = export_report(scan_result, output, format="auto")
        assert result.endswith(".html")

    def test_unknown_extension_defaults_html(self, scan_result, tmp_path):
        output = str(tmp_path / "report.xyz")
        result = export_report(scan_result, output, format="auto")
        assert result.endswith(".html")

    def test_explicit_format(self, scan_result, tmp_path):
        output = str(tmp_path / "report")
        result = export_report(scan_result, output, format="json")
        assert Path(result).exists()

    def test_invalid_format_raises(self, scan_result, tmp_path):
        import pytest
        output = str(tmp_path / "report.bin")
        with pytest.raises(ValueError, match="不支持"):
            export_report(scan_result, output, format="bin")
