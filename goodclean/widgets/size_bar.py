"""大小柱状图组件：以条形图展示 Top N 目录/文件的大小"""

from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..analyzer import format_size
from ..models import DirInfo, FileInfo


class SizeBar(Widget):
    """大小排行柱状图"""

    DEFAULT_CSS = """
    SizeBar {
        height: 1fr;
        overflow-y: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: list[tuple[str, int, str]] = []  # (name, size, path)
        self._max_size = 0
        self._title = "大小排行"
        self._highlight_path: str = ""

    def set_data(
        self,
        dirs: list[DirInfo],
        title: str = "目录大小排行",
        max_items: int = 20,
    ) -> None:
        """设置要展示的目录数据"""
        self._title = title
        self._items = []
        for d in dirs[:max_items]:
            self._items.append((d.name, d.total_size, d.path))
        if self._items:
            self._max_size = max(item[1] for item in self._items)
        else:
            self._max_size = 0
        self.refresh()

    def set_file_data(
        self,
        files: list[FileInfo],
        title: str = "大文件排行",
        max_items: int = 20,
    ) -> None:
        """设置要展示的文件数据"""
        self._title = title
        self._items = []
        for f in files[:max_items]:
            self._items.append((f.name, f.size, f.path))
        if self._items:
            self._max_size = max(item[1] for item in self._items)
        else:
            self._max_size = 0
        self.refresh()

    def set_highlight(self, path: str) -> None:
        """设置高亮路径"""
        self._highlight_path = path
        self.refresh()

    def render(self) -> Text:
        text = Text()
        text.append(f"  {self._title}\n", style="bold underline")
        text.append("─" * 50 + "\n", style="dim")

        if not self._items:
            text.append("  暂无数据\n", style="dim")
            return text

        # 计算最大名称宽度
        max_name_len = max(len(name) for name, _, _ in self._items)
        bar_width = 30

        for i, (name, size, path) in enumerate(self._items):
            is_highlighted = path == self._highlight_path

            # 截断过长的名称
            display_name = name if len(name) <= max_name_len else name[:max_name_len - 2] + ".."
            display_name = display_name.ljust(max_name_len)

            # 计算条形长度
            if self._max_size > 0:
                bar_len = int((size / self._max_size) * bar_width)
            else:
                bar_len = 0

            bar = "█" * bar_len + "░" * (bar_width - bar_len)
            size_str = format_size(size).rjust(10)

            style = "bold white on dark_green" if is_highlighted else ""
            highlight_mark = "▶" if is_highlighted else " "

            text.append(f"{highlight_mark}", style="bold yellow" if is_highlighted else "")
            text.append(f" {display_name} ", style=style or "bold")
            text.append(f"{bar}", style="green" if not is_highlighted else "bold white on dark_green")
            text.append(f" {size_str}\n", style="dim")

        return text
