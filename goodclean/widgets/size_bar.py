"""大小柱状图组件：以条形图展示 Top N 目录/文件/类型的大小"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from ..analyzer import format_size
from ..models import DirInfo, FileInfo


class SizeBar(Widget):
    """大小排行柱状图"""

    class FileSelected(Message):
        """用户点击了某一行"""
        def __init__(self, path: str, is_file: bool) -> None:
            self.path = path
            self.is_file = is_file
            super().__init__()

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
        self._show_parent_dir = False
        self._empty_message: str = ""
        self._junk_flags: list[bool] = []
        self._jump_index: int = 0
        self._jump_total: int = 0
        # 类型分布模式专用
        self._category_mode = False
        self._category_items: list[dict] = []
        # 清理建议模式专用
        self._suggestion_mode = False
        self._suggestion_items: list = []

    def set_empty(self, message: str = "  暂无数据\n") -> None:
        """设置空状态提示"""
        self._category_mode = False
        self._category_items = []
        self._suggestion_mode = False
        self._suggestion_items = []
        self._show_parent_dir = False
        self._empty_message = message
        self._items = []
        self._junk_flags = []
        self._jump_index = 0
        self._jump_total = 0
        self._max_size = 0
        self.refresh()

    def set_data(
        self,
        dirs: list[DirInfo],
        title: str = "目录大小排行",
        max_items: int = 20,
    ) -> None:
        """设置要展示的目录数据"""
        self._category_mode = False
        self._category_items = []
        self._suggestion_mode = False
        self._suggestion_items = []
        self._show_parent_dir = False
        self._empty_message = ""
        self._jump_index = 0
        self._jump_total = 0
        self._title = title
        self._items = []
        self._junk_flags = []
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
        self._suggestion_mode = False
        self._suggestion_items = []
        self._show_parent_dir = True
        self._empty_message = ""
        self._jump_index = 0
        self._jump_total = 0
        self._title = title
        self._items = []
        self._junk_flags = []
        for f in files[:max_items]:
            self._items.append((f.name, f.size, f.path))
            self._junk_flags.append(f.is_junk)
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

    def set_suggestion_data(
        self,
        suggestions: list,
        title: str = "清理建议",
    ) -> None:
        """设置清理建议数据。

        suggestions: list[CleanupSuggestion]
        """
        self._category_mode = False
        self._category_items = []
        self._suggestion_mode = True
        self._suggestion_items = suggestions
        self._title = title
        self._items = []
        if suggestions:
            self._max_size = max(s.size for s in suggestions)
        else:
            self._max_size = 0
        self.refresh()

    def set_highlight(self, path: str) -> None:
        """设置高亮路径"""
        self._highlight_path = path
        self.refresh()

    def set_jump_index(self, current: int, total: int) -> None:
        """设置当前跳转索引"""
        self._jump_index = current
        self._jump_total = total
        self.refresh()

    def on_click(self, event: Click) -> None:
        """鼠标点击某一行时触发跳转"""
        if not self._items or self._suggestion_mode or self._category_mode or self._empty_message:
            return

        # 计算列表项起始行（标题1行 + 可选提示1行 + 横线1行）
        start_y = 2
        if self._show_parent_dir and any(self._junk_flags):
            start_y = 3

        idx = event.y - start_y
        if 0 <= idx < len(self._items):
            name, size, path = self._items[idx]
            is_file = self._show_parent_dir
            self.post_message(self.FileSelected(path, is_file))

    def render(self) -> Text:
        text = Text()
        title = self._title
        if self._jump_index > 0 and self._jump_total > 0:
            title = f"{self._title}  |  第 {self._jump_index}/{self._jump_total}"
        text.append(f"  {title}\n", style="bold underline")
        if self._show_parent_dir and any(self._junk_flags):
            text.append("  ♻ = 可安全清理  ", style="dim green")
            text.append("|  ", style="dim")
            text.append("按 j 跳转到目录树\n", style="dim cyan")
        text.append("─" * 54 + "\n", style="dim")

        if self._empty_message:
            text.append(self._empty_message, style="dim")
        elif self._suggestion_mode:
            self._render_suggestions(text)
        elif self._category_mode:
            self._render_categories(text)
        else:
            self._render_items(text)

        return text

    def _render_suggestions(self, text: Text) -> None:
        """渲染清理建议视图"""
        if not self._suggestion_items:
            text.append("  暂无清理建议\n", style="dim")
            return

        from ..analyzer import format_size as _fmt

        # 汇总
        total_size = sum(s.size for s in self._suggestion_items)
        safe_size = sum(s.size for s in self._suggestion_items if s.risk == "safe")
        caution_size = total_size - safe_size
        safe_count = sum(1 for s in self._suggestion_items if s.risk == "safe")
        caution_count = len(self._suggestion_items) - safe_count

        text.append(
            f"  safe: {safe_count}项 {_fmt(safe_size)}  |  "
            f"caution: {caution_count}项 {_fmt(caution_size)}\n",
            style="dim",
        )
        text.append("─" * 54 + "\n", style="dim")

        bar_width = 20
        for s in self._suggestion_items:
            risk_mark = "[safe]  " if s.risk == "safe" else "[care] "
            risk_style = "bold green" if s.risk == "safe" else "bold yellow"
            name_style = "" if s.risk == "safe" else "dim"

            # 条形长度
            bar_len = int((s.size / self._max_size) * bar_width) if self._max_size > 0 else 0
            if s.size == 0:
                bar_len = 1 if s.risk == "safe" else 0
            bar = "█" * bar_len + "░" * (bar_width - bar_len)

            size_str = _fmt(s.size).rjust(8) if s.size > 0 else "     0 B"
            reason = s.reason[:24]  # 截断过长原因

            text.append(f" {risk_mark}", style=risk_style)
            text.append(f" {s.name[:18]:18s} ", style=name_style)
            text.append(f"{bar} ", style="green" if s.risk == "safe" else "yellow")
            text.append(f"{size_str} ", style="bold")
            text.append(f"{reason}\n", style="dim")

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

        # 计算最大名称宽度（限制在合理范围）
        max_name_len = min(max(len(name) for name, _, _ in self._items), 20)
        bar_width = 14 if self._show_parent_dir else 30

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

            # 文件模式下显示父目录
            parent_str = ""
            if self._show_parent_dir:
                parent = Path(path).parent.name
                if parent:
                    parent_display = parent[:14]
                    parent_str = f"  {parent_display}"

            is_junk = self._show_parent_dir and i < len(self._junk_flags) and self._junk_flags[i]
            style = "bold white on dark_green" if is_highlighted else ""
            highlight_mark = "▶" if is_highlighted else " "
            junk_mark = "♻" if is_junk else " "
            name_style = style or "bold"

            text.append(f"{highlight_mark}{junk_mark}", style="bold yellow" if is_highlighted else "bold green" if is_junk else "")
            text.append(f" {display_name} ", style=name_style)
            text.append(f"{bar}", style="green" if not is_highlighted else "bold white on dark_green")
            text.append(f" {size_str}", style="dim")
            if parent_str:
                text.append(parent_str, style="dim cyan")
            text.append("\n", style="")
