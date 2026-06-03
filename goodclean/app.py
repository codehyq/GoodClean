"""GoodClean 主应用：TUI 界面，整合扫描、分析、清理"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, ProgressBar, Static

from .analyzer import analyze, format_size, get_file_type_distribution
from .cleaner import CleanResult, permanent_delete, trash_files
from .constants import ScanStatus
from .models import DirInfo, ScanResult
from .scanner import DirectoryScanner
from .widgets.confirm_dialog import ConfirmDialog
from .widgets.directory_tree import DirectoryTree
from .widgets.file_info import FileInfoPanel
from .widgets.size_bar import SizeBar


class GoodCleanApp(App):
    """GoodClean 终端磁盘清理工具"""

    TITLE = "GoodClean v1.0"
    SUB_TITLE = "终端磁盘清理工具"

    CSS = """
    #main-container {
        height: 1fr;
    }

    #left-panel {
        width: 1fr;
        min-width: 40;
        border-right: solid $primary;
    }

    #right-panel {
        width: 1fr;
        min-width: 40;
    }

    #status-bar {
        height: 3;
        dock: bottom;
        padding: 0 1;
        background: $surface;
        border-top: solid $primary;
    }

    #scan-progress {
        height: 3;
        padding: 0 1;
    }

    DirectoryTree {
        height: 1fr;
    }

    #help-text {
        height: auto;
        padding: 0 1;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("question_mark", "show_help", "帮助", show=True, key_display="?"),
        Binding("d", "trash_selected", "移到回收站", show=True),
        Binding("D", "permanent_delete_selected", "永久删除", show=True),
        Binding("s", "toggle_sort", "切换排序", show=True),
        Binding("r", "rescan", "重新扫描", show=True),
        Binding("t", "show_types", "类型分布", show=True),
        Binding("escape", "clear_selection", "取消选择", show=True),
    ]

    scan_status: reactive[str] = reactive(ScanStatus.IDLE)
    status_text: reactive[str] = reactive("")

    def __init__(self, scan_path: str, **kwargs):
        super().__init__(**kwargs)
        self._scan_path = scan_path
        self._scanner: DirectoryScanner | None = None
        self._scan_result: ScanResult | None = None
        self._root_dir: DirInfo | None = None
        self._selected_paths: set[str] = set()
        self._sort_by_size = True
        self._showing_types = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="scan-progress")

        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield DirectoryTree(id="dir-tree")
            with Vertical(id="right-panel"):
                yield SizeBar(id="size-bar")
                yield FileInfoPanel(id="file-info")

        yield Static(self._make_help_text(), id="help-text")
        yield Footer()

    def on_mount(self) -> None:
        """应用启动后开始扫描"""
        self._start_scan()

    def _start_scan(self) -> None:
        """开始扫描"""
        self.scan_status = ScanStatus.SCANNING
        self._update_progress("正在扫描...", 0, 0)
        self._do_scan()

    @work(exclusive=True, thread=True)
    def _do_scan(self) -> None:
        """在后台线程中执行扫描"""
        start_time = time.time()

        scanner = DirectoryScanner(self._scan_path)

        # 由于在工作线程中，需要同步执行扫描
        import asyncio
        loop = asyncio.new_event_loop()

        def on_progress(dirs: int, errors: int) -> None:
            self.app.call_from_thread(
                self._update_progress, f"扫描中... 已扫描 {dirs} 个目录", dirs, errors
            )

        scanner.on_progress(on_progress)
        self._scanner = scanner

        try:
            root_dir = loop.run_until_complete(scanner.scan())
            duration = time.time() - start_time

            # 分析结果
            result = analyze(root_dir, self._scan_path)
            result.scan_duration = duration

            self.app.call_from_thread(self._on_scan_complete, result)
        except Exception as e:
            self.app.call_from_thread(self._on_scan_error, str(e))
        finally:
            loop.close()

    def _update_progress(self, text: str, dirs: int, errors: int) -> None:
        """更新进度显示"""
        progress = self.query_one("#scan-progress", Static)
        err_text = f"  |  权限错误: {errors}" if errors > 0 else ""
        progress.update(f"  🔍 {text}{err_text}")

    def _on_scan_complete(self, result: ScanResult) -> None:
        """扫描完成回调"""
        self._scan_result = result
        self._root_dir = result.root_dir
        self.scan_status = ScanStatus.DONE

        # 更新进度
        duration_str = f"{result.scan_duration:.1f}s"
        size_str = format_size(result.total_size)
        progress = self.query_one("#scan-progress", Static)
        progress.update(
            f"  ✅ 扫描完成 | {size_str} | "
            f"{result.total_files} 个文件 | {result.total_dirs} 个目录 | "
            f"耗时 {duration_str}"
        )

        # 加载目录树
        tree = self.query_one("#dir-tree", DirectoryTree)
        tree.load_dir(result.root_dir)

        # 加载大小排行
        size_bar = self.query_one("#size-bar", SizeBar)
        size_bar.set_data(result.top_dirs, "目录大小排行 Top 20")

        # 更新状态
        self.status_text = "扫描完成"

    def _on_scan_error(self, error: str) -> None:
        """扫描错误回调"""
        self.scan_status = ScanStatus.ERROR
        progress = self.query_one("#scan-progress", Static)
        progress.update(f"  ❌ 扫描失败: {error}")

    def on_directory_tree_selected_path_changed(self, event) -> None:
        """目录树选中路径变化"""
        path = event.value
        if path and self._root_dir:
            dir_info = self._find_dir(self._root_dir, path)
            if dir_info:
                file_info_panel = self.query_one("#file-info", FileInfoPanel)
                file_info_panel.set_dir_info(dir_info)

                size_bar = self.query_one("#size-bar", SizeBar)
                size_bar.set_highlight(path)

    def _find_dir(self, dir_info: DirInfo | None, path: str) -> DirInfo | None:
        """递归查找目录"""
        if dir_info is None:
            return None
        if dir_info.path == path:
            return dir_info
        for child in dir_info.children:
            result = self._find_dir(child, path)
            if result:
                return result
        return None

    def action_trash_selected(self) -> None:
        """将选中项移到回收站"""
        paths = self._get_selected_paths()
        if not paths:
            self.notify("请先在目录树中选择要删除的项目（按 Space 选中）", severity="warning")
            return

        total_size = sum(
            self._get_path_size(p) for p in paths
        )

        self.push_screen(
            ConfirmDialog(
                f"确定将 {len(paths)} 个项目移到回收站？",
                count=len(paths),
                total_size=total_size,
                is_permanent=False,
            ),
            self._on_trash_confirm,
        )

    def _on_trash_confirm(self, confirmed: bool | None) -> None:
        """回收站确认回调"""
        if not confirmed:
            return

        paths = self._get_selected_paths()
        if not paths:
            return

        result = trash_files(paths)
        self._show_clean_result(result, "回收站")

    def action_permanent_delete_selected(self) -> None:
        """永久删除选中项"""
        paths = self._get_selected_paths()
        if not paths:
            self.notify("请先在目录树中选择要删除的项目（按 Space 选中）", severity="warning")
            return

        total_size = sum(
            self._get_path_size(p) for p in paths
        )

        self.push_screen(
            ConfirmDialog(
                f"确定永久删除 {len(paths)} 个项目？此操作不可恢复！",
                count=len(paths),
                total_size=total_size,
                is_permanent=True,
            ),
            self._on_permanent_confirm,
        )

    def _on_permanent_confirm(self, confirmed: bool | None) -> None:
        """永久删除确认回调"""
        if not confirmed:
            return

        paths = self._get_selected_paths()
        if not paths:
            return

        result = permanent_delete(paths)
        self._show_clean_result(result, "永久删除")

    def _show_clean_result(self, result: CleanResult, mode: str) -> None:
        """显示清理结果"""
        freed = format_size(result.freed_bytes)
        if result.errors:
            msg = f"✅ {result.success_count} 个已{mode}，释放 {freed} | ❌ {result.fail_count} 个失败"
        else:
            msg = f"✅ {result.success_count} 个已{mode}，释放 {freed}"
        self.notify(msg)

        # 清除选中并刷新
        self._selected_paths.clear()
        if result.success_count > 0:
            self._start_scan()

    def action_toggle_sort(self) -> None:
        """切换排序方式"""
        if not self._scan_result:
            return

        self._sort_by_size = not self._sort_by_size
        size_bar = self.query_one("#size-bar", SizeBar)

        if self._sort_by_size:
            size_bar.set_data(self._scan_result.top_dirs, "目录大小排行 Top 20")
        else:
            # 按文件数量排序
            sorted_dirs = sorted(
                self._scan_result.top_dirs,
                key=lambda d: d.file_count,
                reverse=True,
            )[:20]
            size_bar.set_data(sorted_dirs, "文件数量排行 Top 20")

        mode = "大小" if self._sort_by_size else "文件数量"
        self.notify(f"排序方式: {mode}")

    def action_rescan(self) -> None:
        """重新扫描"""
        self._start_scan()

    def action_show_types(self) -> None:
        """显示文件类型分布"""
        if not self._root_dir:
            return

        self._showing_types = not self._showing_types
        size_bar = self.query_one("#size-bar", SizeBar)

        if self._showing_types:
            dist = get_file_type_distribution(self._root_dir)
            # 转换为临时 DirInfo 格式展示
            from .models import DirInfo as DI
            type_dirs = []
            for ext, (count, size) in list(dist.items())[:20]:
                type_dirs.append(DI(
                    path=ext,
                    name=f"{ext} ({count}个文件)",
                    total_size=size,
                    file_count=count,
                ))
            size_bar.set_data(type_dirs, "文件类型分布 Top 20")
        else:
            if self._scan_result:
                size_bar.set_data(self._scan_result.top_dirs, "目录大小排行 Top 20")

    def action_clear_selection(self) -> None:
        """清除选中"""
        self._selected_paths.clear()
        tree = self.query_one("#dir-tree", DirectoryTree)
        tree.selected_paths = set()

    def action_show_help(self) -> None:
        """显示帮助"""
        help_text = (
            "GoodClean 快捷键帮助\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "↑↓       导航目录树\n"
            "Enter    展开/折叠目录\n"
            "Space    选中/取消选中\n"
            "d        移到回收站\n"
            "D        永久删除\n"
            "s        切换排序方式\n"
            "t        文件类型分布\n"
            "r        重新扫描\n"
            "q        退出\n"
            "?        显示此帮助"
        )
        self.notify(help_text, timeout=8)

    def _get_selected_paths(self) -> list[str]:
        """获取选中的路径列表"""
        tree = self.query_one("#dir-tree", DirectoryTree)
        return list(tree.selected_paths)

    def _get_path_size(self, path: str) -> int:
        """获取路径大小"""
        if self._root_dir:
            dir_info = self._find_dir(self._root_dir, path)
            if dir_info:
                return dir_info.total_size
        return 0

    def _make_help_text(self) -> str:
        """生成底部帮助文本"""
        return (
            "  [Enter] 展开  [Space] 选中  [d] 回收站  [D] 永久删除  "
            "[s] 排序  [t] 类型  [r] 重扫  [?] 帮助  [q] 退出"
        )
