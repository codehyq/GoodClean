"""扫描结果导出：支持 HTML、JSON、CSV 格式"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import TextIO

from jinja2 import Template

from .analyzer import format_size
from .models import DirInfo, FileInfo, ScanResult


# ──────────────────── HTML 报告模板 ────────────────────
_HTML_TEMPLATE = Template(
    r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GoodClean 扫描报告 - {{ result.root_path }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; margin-bottom: 20px; }
        h2 { color: #34495e; margin: 30px 0 15px; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .summary-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .summary-card .label { color: #7f8c8d; font-size: 14px; }
        .summary-card .value { font-size: 24px; font-weight: bold; color: #2c3e50; }
        table { width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #3498db; color: white; }
        tr:hover { background: #f8f9fa; }
        .size { font-family: monospace; font-weight: bold; }
        .junk { color: #e74c3c; }
        .large { color: #f39c12; }
        .footer { text-align: center; color: #7f8c8d; margin-top: 40px; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 GoodClean 扫描报告</h1>
        <p>扫描路径: <strong>{{ result.root_path }}</strong></p>
        <p>扫描时间: {{ now }}</p>

        <div class="summary">
            <div class="summary-card">
                <div class="label">总大小</div>
                <div class="value">{{ format_size(result.total_size) }}</div>
            </div>
            <div class="summary-card">
                <div class="label">文件数</div>
                <div class="value">{{ "{:,}".format(result.total_files) }}</div>
            </div>
            <div class="summary-card">
                <div class="label">目录数</div>
                <div class="value">{{ "{:,}".format(result.total_dirs) }}</div>
            </div>
            <div class="summary-card">
                <div class="label">扫描耗时</div>
                <div class="value">{{ "{:.2f}".format(result.scan_duration) }}秒</div>
            </div>
        </div>

        <h2>📁 目录大小排行 Top 20</h2>
        <table>
            <thead>
                <tr><th>排名</th><th>目录名</th><th>大小</th><th>文件数</th><th>子目录数</th></tr>
            </thead>
            <tbody>
            {% for d in top_dirs %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ d.name }}</td>
                    <td class="size">{{ format_size(d.total_size) }}</td>
                    <td>{{ "{:,}".format(d.file_count) }}</td>
                    <td>{{ "{:,}".format(d.dir_count) }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>

        <h2>📄 大文件排行 Top 20</h2>
        <table>
            <thead>
                <tr><th>排名</th><th>文件名</th><th>大小</th><th>类型</th></tr>
            </thead>
            <tbody>
            {% for f in large_files %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ f.name }}</td>
                    <td class="size large">{{ format_size(f.size) }}</td>
                    <td>{{ f.extension or '未知' }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>

        <h2>🗑️ 垃圾文件</h2>
        <table>
            <thead>
                <tr><th>文件名</th><th>大小</th><th>类型</th><th>原因</th></tr>
            </thead>
            <tbody>
            {% for f in junk_files %}
                <tr>
                    <td>{{ f.name }}</td>
                    <td class="size junk">{{ format_size(f.size) }}</td>
                    <td>{{ f.extension or '未知' }}</td>
                    <td>{{ f.junk_reason }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>

        <div class="footer">
            <p>由 GoodClean v1.0 生成 | {{ now }}</p>
        </div>
    </div>
</body>
</html>"""
)


def export_json(result: ScanResult, output_path: str) -> str:
    """导出为 JSON 格式"""
    data = {
        "scan_info": {
            "root_path": result.root_path,
            "total_size": result.total_size,
            "total_size_formatted": format_size(result.total_size),
            "total_files": result.total_files,
            "total_dirs": result.total_dirs,
            "scan_duration": result.scan_duration,
            "permission_errors": result.permission_errors,
            "export_time": datetime.now().isoformat(),
        },
        "top_dirs": [
            {
                "path": d.path,
                "name": d.name,
                "size": d.total_size,
                "size_formatted": format_size(d.total_size),
                "file_count": d.file_count,
                "dir_count": d.dir_count,
            }
            for d in result.top_dirs[:50]
        ],
        "large_files": [
            {
                "path": f.path,
                "name": f.name,
                "size": f.size,
                "size_formatted": format_size(f.size),
                "extension": f.extension,
                "modified_time": f.modified_time,
            }
            for f in result.large_files[:100]
        ],
        "junk_files": [
            {
                "path": f.path,
                "name": f.name,
                "size": f.size,
                "size_formatted": format_size(f.size),
                "extension": f.extension,
                "reason": f.junk_reason,
            }
            for f in result.junk_files[:200]
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


def export_csv(result: ScanResult, output_path: str) -> str:
    """导出为 CSV 格式"""
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)

        # 写入概览信息
        writer.writerow(["扫描概览"])
        writer.writerow(["扫描路径", result.root_path])
        writer.writerow(["总大小", format_size(result.total_size)])
        writer.writerow(["文件数", result.total_files])
        writer.writerow(["目录数", result.total_dirs])
        writer.writerow(["扫描耗时", f"{result.scan_duration:.2f}秒"])
        writer.writerow([])

        # 写入目录排行
        writer.writerow(["目录大小排行"])
        writer.writerow(["排名", "目录名", "路径", "大小", "文件数", "子目录数"])
        for i, d in enumerate(result.top_dirs[:50], 1):
            writer.writerow([
                i,
                d.name,
                d.path,
                format_size(d.total_size),
                d.file_count,
                d.dir_count,
            ])
        writer.writerow([])

        # 写入大文件
        writer.writerow(["大文件排行 (>100MB)"])
        writer.writerow(["排名", "文件名", "路径", "大小", "扩展名"])
        for i, f in enumerate(result.large_files[:100], 1):
            writer.writerow([
                i,
                f.name,
                f.path,
                format_size(f.size),
                f.extension,
            ])
        writer.writerow([])

        # 写入垃圾文件
        writer.writerow(["垃圾文件"])
        writer.writerow(["文件名", "路径", "大小", "扩展名", "原因"])
        for f in result.junk_files[:200]:
            writer.writerow([
                f.name,
                f.path,
                format_size(f.size),
                f.extension,
                f.junk_reason,
            ])

    return output_path


def export_html(result: ScanResult, output_path: str) -> str:
    """导出为 HTML 格式（使用 jinja2 模板渲染）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = _HTML_TEMPLATE.render(
        result=result,
        now=now,
        top_dirs=result.top_dirs[:20],
        large_files=result.large_files[:20],
        junk_files=result.junk_files[:50],
        format_size=format_size,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def export_report(result: ScanResult, output_path: str, format: str = "auto") -> str:
    """导出扫描报告

    Args:
        result: 扫描结果
        output_path: 输出文件路径
        format: 导出格式 (auto/json/csv/html)，auto 时根据扩展名自动判断

    Returns:
        实际输出的文件路径
    """
    if format == "auto":
        ext = Path(output_path).suffix.lower()
        if ext == ".json":
            format = "json"
        elif ext == ".csv":
            format = "csv"
        elif ext in (".html", ".htm"):
            format = "html"
        else:
            format = "html"
            output_path = output_path + ".html"

    if format == "json":
        return export_json(result, output_path)
    elif format == "csv":
        return export_csv(result, output_path)
    elif format == "html":
        return export_html(result, output_path)
    else:
        raise ValueError(f"不支持的导出格式: {format}")
