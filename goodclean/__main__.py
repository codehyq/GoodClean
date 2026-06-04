"""GoodClean 入口点"""

from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="goodclean",
        description="GoodClean - 终端磁盘清理工具",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="要扫描的目录路径（可选，不指定则显示交互式菜单）",
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
        "--no-cache",
        action="store_true",
        help="不使用缓存，强制实时扫描",
    )
    parser.add_argument(
        "--cache-info",
        action="store_true",
        help="显示缓存信息后退出",
    )

    args = parser.parse_args()

    # 查看缓存信息模式
    if args.cache_info:
        _show_cache_info()
        return

    # 验证指定的路径
    if args.path and not os.path.isdir(args.path):
        print(f"错误: '{args.path}' 不是有效的目录", file=sys.stderr)
        sys.exit(1)

    # 启动应用
    from .app import GoodCleanApp

    app = GoodCleanApp(
        scan_path=args.path,          # None -> 显示欢迎屏幕
        use_cache=not args.no_cache,
        export_path=args.export,
    )
    app.run()


def _show_cache_info() -> None:
    """显示缓存信息"""
    from .cache import list_all_caches
    from .analyzer import format_size

    caches = list_all_caches()
    if not caches:
        print("当前无缓存")
        return

    print(f"缓存条目: {len(caches)}")
    print("─" * 50)
    for info in caches:
        size_str = format_size(info["total_size"])
        status = "已过期" if info["expired"] else "有效"
        print(
            f"  {info['path']}\n"
            f"    扫描于 {info['age_hours']}h 前  "
            f"大小 {size_str}  "
            f"文件 {info['total_files']}  "
            f"目录 {info['total_dirs']}  "
            f"({status})"
        )


if __name__ == "__main__":
    main()
