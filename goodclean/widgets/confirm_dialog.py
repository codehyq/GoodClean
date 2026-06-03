"""确认删除对话框"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ..analyzer import format_size


class ConfirmDialog(ModalScreen[bool]):
    """确认删除对话框，返回 True 表示确认，False 表示取消"""

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #confirm-container {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 2;
        width: 60;
        height: auto;
        max-height: 20;
        border: thick $primary;
        background: $surface;
    }

    #confirm-message {
        column-span: 2;
        height: auto;
        padding: 1 0;
    }

    #confirm-btn {
        width: 100%;
    }

    #cancel-btn {
        width: 100%;
    }
    """

    def __init__(
        self,
        message: str,
        count: int = 0,
        total_size: int = 0,
        is_permanent: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._message = message
        self._count = count
        self._total_size = total_size
        self._is_permanent = is_permanent

    def compose(self) -> ComposeResult:
        size_str = format_size(self._total_size)
        warning = "⚠️ 永久删除不可恢复！" if self._is_permanent else "（可从回收站恢复）"

        yield Grid(
            Label(self._message, id="confirm-message"),
            Static(
                f"共 {self._count} 个项目，占用 {size_str}\n{warning}",
                id="confirm-detail",
            ),
            Button("确认", variant="error" if self._is_permanent else "warning", id="confirm-btn"),
            Button("取消", variant="default", id="cancel-btn"),
            id="confirm-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)
