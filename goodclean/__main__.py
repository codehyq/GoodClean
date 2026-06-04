"""GoodClean 入口点"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="goodclean",
        description="GoodClean - 终端磁盘清理工具",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="要扫描的目录路径（默认为当前目录）",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="GoodClean 1.0.0",
    )
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="导出扫描报告到文件（支持 .html/.json/.csv）",
    )
    parser.add_argument(
        "--no-tui",
        action="store_true",
        help="不启动 TUI 界面，仅导出报告",
    )

    args = parser.parse_args()

    # 确定扫描路径
    scan_path = args.path or os.getcwd()

    # 验证路径
    if not os.path.isdir(scan_path):
        print(f"错误: '{scan_path}' 不是有效的目录", file=sys.stderr)
        sys.exit(1)

    # 如果指定了导出参数且不需要 TUI
    if args.export and args.no_tui:
        _export_only(scan_path, args.export)
        return

    # 启动应用
    from .app import GoodCleanApp

    app = GoodCleanApp(scan_path=scan_path)
    app.run()


def _export_only(scan_path: str, output_path: str) -> None:
    """仅导出报告，不启动 TUI"""
    from .analyzer import analyze, format_size
    from .exporter import export_report
    from .scanner import DirectoryScanner

    print(f"正在扫描: {scan_path}")
    start_time = time.time()

    scanner = DirectoryScanner(scan_path)

    def on_progress(dirs: int, errors: int) -> None:
        print(f"\r已扫描 {dirs} 个目录...", end="", flush=True)

    scanner.on_progress(on_progress)

    loop = asyncio.new_event_loop()
    try:
        root_dir = loop.run_until_complete(scanner.scan())
        duration = time.time() - start_time
        print(f"\n扫描完成，耗时 {duration:.2f}秒")

        # 分析结果
        result = analyze(root_dir, scan_path)
        result.scan_duration = duration

        print(f"总大小: {format_size(result.total_size)}")
        print(f"文件数: {result.total_files}")
        print(f"目录数: {result.total_dirs}")

        # 导出报告
        output = export_report(result, output_path)
        print(f"报告已导出: {output}")

    finally:
        loop.close()


if __name__ == "__main__":
    main()
