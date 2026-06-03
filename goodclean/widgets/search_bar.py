"""搜索/过滤组件：支持实时搜索文件名，按类型/大小过滤"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Select, Static


class SearchBar(Widget):
    """搜索/过滤栏"""

    DEFAULT_CSS = """
    SearchBar {
        height: 3;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $primary;
    }

    #search-input {
        width: 1fr;
        margin: 0 1;
    }

    #filter-type {
        width: 15;
        margin: 0 1;
    }

    #filter-size {
        width: 15;
        margin: 0 1;
    }

    #search-info {
        width: auto;
        margin: 0 1;
        color: $text-muted;
    }
    """

    search_query: reactive[str] = reactive("")
    filter_type: reactive[str] = reactive("")
    filter_size: reactive[str] = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._on_search_change: Optional[Callable[[str, str, str], None]] = None

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("🔍", id="search-icon")
            yield Input(
                placeholder="搜索文件名...",
                id="search-input",
            )
            yield Select(
                [
                    ("全部类型", ""),
                    (".py (Python)", ".py"),
                    (".js (JavaScript)", ".js"),
                    (".ts (TypeScript)", ".ts"),
                    (".json (JSON)", ".json"),
                    (".md (Markdown)", ".md"),
                    (".txt (文本)", ".txt"),
                    (".log (日志)", ".log"),
                    (".tmp (临时)", ".tmp"),
                    (".bak (备份)", ".bak"),
                ],
                prompt="文件类型",
                id="filter-type",
            )
            yield Select(
                [
                    ("全部大小", ""),
                    ("> 1 MB", "1mb"),
                    ("> 10 MB", "10mb"),
                    ("> 100 MB", "100mb"),
                    ("> 1 GB", "1gb"),
                ],
                prompt="文件大小",
                id="filter-size",
            )
            yield Static("", id="search-info")

    def on_input_changed(self, event: Input.Changed) -> None:
        """搜索输入变化"""
        if event.input.id == "search-input":
            self.search_query = event.value
            self._notify_change()

    def on_select_changed(self, event: Select.Changed) -> None:
        """过滤选项变化"""
        if event.select.id == "filter-type":
            self.filter_type = event.value or ""
            self._notify_change()
        elif event.select.id == "filter-size":
            self.filter_size = event.value or ""
            self._notify_change()

    def _notify_change(self) -> None:
        """通知搜索条件变化"""
        if self._on_search_change:
            self._on_search_change(
                self.search_query,
                self.filter_type,
                self.filter_size,
            )

    def set_on_search_change(self, callback: Callable[[str, str, str], None]) -> None:
        """设置搜索条件变化回调"""
        self._on_search_change = callback

    def update_result_count(self, count: int, total: int) -> None:
        """更新搜索结果数量显示"""
        info = self.query_one("#search-info", Static)
        if self.search_query or self.filter_type or self.filter_size:
            info.update(f"找到 {count}/{total}")
        else:
            info.update("")

    def clear_filters(self) -> None:
        """清除所有过滤条件"""
        self.search_query = ""
        self.filter_type = ""
        self.filter_size = ""

        # 重置 UI
        input_widget = self.query_one("#search-input", Input)
        input_widget.value = ""

        type_select = self.query_one("#filter-type", Select)
        type_select.value = ""

        size_select = self.query_one("#filter-size", Select)
        size_select.value = ""

        self._notify_change()


def matches_search_filter(
    name: str,
    path: str,
    size: int,
    extension: str,
    query: str,
    filter_type: str,
    filter_size: str,
) -> bool:
    """检查文件是否匹配搜索和过滤条件"""

    # 搜索文件名
    if query:
        if query.lower() not in name.lower() and query.lower() not in path.lower():
            return False

    # 过滤文件类型
    if filter_type:
        if extension != filter_type:
            return False

    # 过滤文件大小
    if filter_size:
        size_thresholds = {
            "1mb": 1024 * 1024,
            "10mb": 10 * 1024 * 1024,
            "100mb": 100 * 1024 * 1024,
            "1gb": 1024 * 1024 * 1024,
        }
        threshold = size_thresholds.get(filter_size, 0)
        if size < threshold:
            return False

    return True
