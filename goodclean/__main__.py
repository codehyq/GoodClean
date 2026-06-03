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
        help="要扫描的目录路径（默认为当前目录）",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="GoodClean 1.0.0",
    )

    args = parser.parse_args()

    # 确定扫描路径
    scan_path = args.path or os.getcwd()

    # 验证路径
    if not os.path.isdir(scan_path):
        print(f"错误: '{scan_path}' 不是有效的目录", file=sys.stderr)
        sys.exit(1)

    # 启动应用
    from .app import GoodCleanApp

    app = GoodCleanApp(scan_path=scan_path)
    app.run()


if __name__ == "__main__":
    main()
