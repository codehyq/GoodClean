"""欢迎视图：路径选择、扫描模式切换"""

from __future__ import annotations

import os
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, RadioSet, Static, Switch

from ..analyzer import format_size
from ..cache import list_all_caches
from ..config import get_last_scan_path, get_use_cache, has_saved_scan_result, load_scan_result


def get_presets() -> list[tuple[str, str]]:
    """获取预设扫描路径列表：[(显示名, 路径)]"""
    presets: list[tuple[str, str]] = []

    # 上次扫描路径（如果有）
    last_path = get_last_scan_path()
    if last_path:
        presets.append((f"上次扫描 ({last_path})", last_path))

    home = Path.home()
    presets.extend([
        (f"当前目录 ({os.getcwd()})", os.getcwd()),
        ("C 盘 (C:\\)", "C:\\"),
    ])
    if os.path.exists("D:\\"):
        presets.append(("D 盘 (D:\\)", "D:\\"))
    presets.extend([
        (f"用户目录 ({home})", str(home)),
        (f"桌面 ({home / 'Desktop'})", str(home / "Desktop")),
    ])
    presets.append(("自定义路径...", ""))
    return presets


CSS = """
#welcome-view {
    height: 1fr;
    align: center middle;
}

#welcome-container {
    width: 70;
    max-width: 98%;
    height: auto;
    border: tall $primary;
    background: $surface;
    padding: 1 2;
    align: center middle;
}

#welcome-title {
    text-align: center;
    text-style: bold;
    color: $primary;
    margin-bottom: 0;
    width: 100%;
}

#welcome-subtitle {
    text-align: center;
    color: $text-muted;
    margin-bottom: 1;
    width: 100%;
}

.section-label {
    text-style: bold;
    color: $accent;
    margin-top: 1;
    width: 100%;
}

#path-radio {
    width: 100%;
    height: auto;
}

#mode-switch-container {
    width: 100%;
    height: auto;
    padding: 0 1;
}

#mode-switch-container Label {
    width: auto;
}

#custom-path-input {
    width: 100%;
    height: 3;
    display: none;
}

#custom-path-input.show {
    display: block;
}

.cache-line {
    width: 100%;
    height: auto;
    color: $text-muted;
    margin-bottom: 1;
}

#permission-tip {
    width: 100%;
    height: auto;
    color: $warning;
    text-align: center;
    margin-top: 1;
    margin-bottom: 0;
}

#start-btn {
    width: 20;
    margin-top: 1;
    align: center middle;
}

#load-persisted-btn {
    width: 24;
    margin-top: 1;
    align: center middle;
}

#welcome-help {
    text-align: center;
    width: 100%;
    color: $text-muted;
    margin-top: 1;
}
"""


class WelcomeScreen(Screen):
    """欢迎视图：路径选择、扫描模式切换"""

    CSS = CSS

    BINDINGS = [
        ("q", "quit_app", "退出"),
    ]

    def __init__(self, use_cache: bool = True, **kwargs):
        super().__init__(**kwargs)
        self._presets = get_presets()
        # 从配置恢复缓存设置（如果用户设置过）
        cached_setting = get_use_cache()
        self._use_cache = cached_setting if cached_setting is not None else use_cache
        self._has_persisted = has_saved_scan_result()

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-view"):
            with Vertical(id="welcome-container"):
                yield Static("GoodClean v1.0.0", id="welcome-title")
                yield Static("终端磁盘清理工具", id="welcome-subtitle")

                yield Static("── 选择扫描路径 ──", classes="section-label")
                yield RadioSet(
                    *[name for name, _ in self._presets],
                    id="path-radio",
                )
                yield Input(
                    placeholder="输入目录路径，如 D:\\MyFolder",
                    id="custom-path-input",
                )

                yield Static("── 扫描模式 ──", classes="section-label")
                with Horizontal(id="mode-switch-container"):
                    yield Switch(value=self._use_cache, id="cache-switch")
                    yield Static("  标准模式（使用缓存加速）", id="mode-label")

                yield Static(self._make_cache_text(), classes="cache-line",
                             id="welcome-cache-line")

                yield Static(
                    "提示：扫描系统盘时可能遇到权限报错，"
                    "右键 PowerShell → 以管理员身份运行可减少此类情况。"
                    "有权限限制的文件通常是系统关键文件，不建议清理。",
                    id="permission-tip",
                )

                yield Button("开始扫描", variant="primary", id="start-btn")

                if self._has_persisted:
                    yield Button("查看上次扫描结果", variant="default", id="load-persisted-btn")

                yield Static(
                    "↑↓ 选择路径  |  Tab 切换控件  |  Enter 确认",
                    id="welcome-help",
                )

    def on_mount(self) -> None:
        self.query_one("#path-radio").focus()

    def action_quit_app(self) -> None:
        """退出应用"""
        self.app.exit()

    @on(Button.Pressed, "#start-btn")
    def _on_start_pressed(self) -> None:
        """点击开始按钮"""
        radio = self.query_one("#path-radio", RadioSet)
        idx = radio.pressed_index
        if idx is None or idx < 0:
            self.notify("请先选择一个扫描路径", severity="warning")
            return

        _, path = self._presets[idx]

        if not path:
            custom = self.query_one("#custom-path-input", Input).value.strip()
            if not custom:
                self.notify("请输入扫描路径", severity="warning")
                return
            if not os.path.isdir(custom):
                self.notify(f"路径不存在: {custom}", severity="warning")
                return
            path = custom

        use_cache = self.query_one("#cache-switch", Switch).value
        # 保存配置
        from ..config import set_last_scan_path, set_use_cache
        set_last_scan_path(path)
        set_use_cache(use_cache)
        self.app.switch_to_main(path, use_cache)

    @on(Button.Pressed, "#load-persisted-btn")
    def _on_load_persisted_pressed(self) -> None:
        """点击加载上次扫描结果按钮"""
        result = load_scan_result()
        if result is None:
            self.notify("上次扫描结果已过期或不存在", severity="warning")
            return
        self.app.switch_to_main(result.root_path, self._use_cache, persisted_result=result)

    @on(RadioSet.Changed, "#path-radio")
    def _on_path_radio_changed(self, event: RadioSet.Changed) -> None:
        inp = self.query_one("#custom-path-input", Input)
        idx = event.radio_set.pressed_index
        is_custom = idx == len(self._presets) - 1
        if is_custom:
            inp.add_class("show")
            inp.focus()
        else:
            inp.remove_class("show")

    @on(Switch.Changed, "#cache-switch")
    def _on_cache_switch_changed(self, event: Switch.Changed) -> None:
        self._use_cache = event.value
        label = self.query_one("#mode-label", Static)
        if event.value:
            label.update("  标准模式（使用缓存加速）")
        else:
            label.update("  强制刷新（跳过缓存）")
        self.query_one("#welcome-cache-line", Static).update(self._make_cache_text())

    def _make_cache_text(self) -> str:
        caches = list_all_caches()
        if not caches:
            return "  缓存: 无"
        lines = [f"  缓存: {len(caches)} 条可用"]
        for info in caches[:5]:
            size_str = format_size(info["total_size"])
            lines.append(f"    - {info['path']} ({size_str}, {info['age_hours']}h前)")
        if len(caches) > 5:
            lines.append(f"    ... 还有 {len(caches) - 5} 条")
        return "\n".join(lines)
