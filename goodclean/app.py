"""GoodClean 主应用：协调层，负责 Screen 切换和导出流程"""

from __future__ import annotations

from textual.app import App

from .screens import WelcomeScreen, MainScreen


class GoodCleanApp(App):
    """GoodClean 终端磁盘清理工具"""

    TITLE = "GoodClean v1.0"
    SUB_TITLE = "终端磁盘清理工具"

    def __init__(self, scan_path: str | None = None, use_cache: bool = True,
                 export_path: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._scan_path = scan_path
        self._use_cache = use_cache
        self._export_path = export_path

    def on_mount(self) -> None:
        if self._scan_path:
            # 直接指定路径，跳过欢迎界面
            self.switch_to_main(self._scan_path, self._use_cache)
        else:
            # 显示欢迎界面
            self.push_screen(WelcomeScreen(use_cache=self._use_cache))

    def switch_to_main(self, scan_path: str, use_cache: bool) -> None:
        """从欢迎界面切换到主扫描视图"""
        self._scan_path = scan_path
        self._use_cache = use_cache
        self.switch_screen(MainScreen(
            scan_path=scan_path, use_cache=use_cache,
            export_path=self._export_path,
        ))

    def push_main_screen(self, scan_path: str, use_cache: bool) -> None:
        """从命令行直接进入主扫描视图"""
        self._scan_path = scan_path
        self._use_cache = use_cache
        self.push_screen(MainScreen(scan_path=scan_path, use_cache=use_cache))
