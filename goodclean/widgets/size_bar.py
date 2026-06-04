"""大小柱状图组件：以条形图展示 Top N 目录/文件/类型的大小"""

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
        # 类型分布模式专用
        self._category_mode = False
        self._category_items: list[dict] = []

    def set_data(
        self,
        dirs: list[DirInfo],
        title: str = "目录大小排行",
        max_items: int = 20,
    ) -> None:
        """设置要展示的目录数据"""
        self._category_mode = False
        self._category_items = []
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
        self._category_mode = False
        self._category_items = []
        self._title = title
        self._items = []
        for f in files[:max_items]:
            self._items.append((f.name, f.size, f.path))
        if self._items:
            self._max_size = max(item[1] for item in self._items)
        else:
            self._max_size = 0
        self.refresh()

    def set_category_data(
        self,
        categories: list[dict],
        title: str = "类型分布",
    ) -> None:
        """设置文件类型分类数据。

        categories 格式：
        [{"category": "图片", "count": 120, "total_size": 52428800, "top_ext": ".jpg"}, ...]
        """
        self._category_mode = True
        self._category_items = categories
        self._items = []
        self._title = title
        if categories:
            self._max_size = max(c["total_size"] for c in categories)
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
        text.append("─" * 54 + "\n", style="dim")

        if self._category_mode:
            self._render_categories(text)
        else:
            self._render_items(text)

        return text

    def _render_categories(self, text: Text) -> None:
        """渲染文件类型分类视图"""
        if not self._category_items:
            text.append("  暂无数据\n", style="dim")
            return

        # 计算汇总信息
        total_count = sum(c["count"] for c in self._category_items)
        total_size = sum(c["total_size"] for c in self._category_items)

        text.append(
            f"  共 {len(self._category_items)} 种类型 | "
            f"{total_count} 个文件 | {format_size(total_size)}\n",
            style="dim",
        )
        text.append("─" * 54 + "\n", style="dim")

        bar_width = 20
        # 类型颜色映射
        _CAT_COLORS = {
            "图片": "green", "视频": "magenta", "音频": "cyan",
            "文档": "blue", "代码": "yellow", "配置": "yellow dim",
            "压缩包": "red", "可执行文件": "bold red", "编译产物": "red dim",
            "数据库": "magenta", "字体": "white", "日志/临时": "dim",
            "磁盘镜像": "bold magenta", "电子书": "blue", "空文件": "dim",
            "其他": "dim",
        }

        for cat_info in self._category_items:
            cat = cat_info["category"]
            count = cat_info["count"]
            size = cat_info["total_size"]
            top_ext = cat_info.get("top_ext", "")

            # 百分比
            size_pct = (size / total_size * 100) if total_size > 0 else 0
            count_pct = (count / total_count * 100) if total_count > 0 else 0

            # 条形长度
            bar_len = int((size / self._max_size) * bar_width) if self._max_size > 0 else 0
            bar = "█" * bar_len + "░" * (bar_width - bar_len)

            color = _CAT_COLORS.get(cat, "white")

            # 格式化：类别名 | 条形 | 大小(百分比) | 文件数
            label = f"{cat}".ljust(8)
            size_str = format_size(size).rjust(8)
            count_str = f"{count}个".rjust(6)

            text.append(f"  ", style="")
            text.append(f"{label}", style=f"bold {color}")
            text.append(f" {bar} ", style=color)
            text.append(f"{size_str}", style="bold")
            text.append(f" ({size_pct:4.1f}%)", style="dim")
            text.append(f" {count_str}", style="dim")
            if top_ext:
                text.append(f" {top_ext}", style="dim italic")
            text.append("\n", style="")

    def _render_items(self, text: Text) -> None:
        """渲染普通列表视图（目录/文件排行）"""
        if not self._items:
            text.append("  暂无数据\n", style="dim")
            return

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
