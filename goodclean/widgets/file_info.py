"""文件详情面板：展示选中文件/目录的详细信息"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from ..analyzer import format_size
from ..models import DirInfo, FileInfo


class FileInfoPanel(Widget):
    """文件详情面板"""

    DEFAULT_CSS = """
    FileInfoPanel {
        height: auto;
        max-height: 8;
        padding: 0 1;
        border-top: solid $primary;
    }
    """

    path: reactive[str] = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dir_info: DirInfo | None = None
        self._file_info: FileInfo | None = None

    def set_dir_info(self, dir_info: DirInfo) -> None:
        """设置要展示的目录信息"""
        self._dir_info = dir_info
        self._file_info = None
        self.path = dir_info.path
        self.refresh()

    def set_file_info(self, file_info: FileInfo) -> None:
        """设置要展示的文件信息"""
        self._file_info = file_info
        self._dir_info = None
        self.path = file_info.path
        self.refresh()

    def clear_info(self) -> None:
        """清除信息"""
        self._dir_info = None
        self._file_info = None
        self.path = ""
        self.refresh()

    def render(self) -> Text:
        text = Text()

        if self._dir_info:
            d = self._dir_info
            text.append(" 📁 ", style="bold")
            text.append(f"{d.name}\n", style="bold")
            text.append(f"   路径: {d.path}\n", style="dim")
            text.append(f"   大小: {format_size(d.total_size)}", style="green bold")
            text.append(f"   文件: {d.file_count}", style="cyan")
            text.append(f"   子目录: {d.dir_count}\n", style="cyan")

            if d.has_permission_error:
                text.append("   ⚠️ 部分内容无权限访问\n", style="yellow")

        elif self._file_info:
            f = self._file_info
            icon = "🗑️" if f.is_junk else "📄"
            style = "yellow" if f.is_junk else ""

            text.append(f" {icon} ", style="bold")
            text.append(f"{f.name}\n", style=f"bold {style}")
            text.append(f"   路径: {f.path}\n", style="dim")
            text.append(f"   大小: {format_size(f.size)}", style="green bold")
            text.append(f"   类型: {f.extension or '未知'}", style="cyan")

            try:
                mtime = datetime.fromtimestamp(f.modified_time).strftime("%Y-%m-%d %H:%M")
                text.append(f"   修改: {mtime}", style="dim")
            except (ValueError, OSError):
                pass

            if f.is_junk:
                text.append(f"\n   ⚠️ {f.junk_reason}", style="yellow bold")

        else:
            text.append("  选择一个文件或目录查看详情", style="dim italic")

        return text
