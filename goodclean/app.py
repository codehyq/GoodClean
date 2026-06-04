"""GoodClean 主应用：TUI 界面，整合扫描、分析、清理"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, RadioSet, Static, Switch

from .analyzer import analyze, format_size, get_file_type_distribution
from .cache import clear_cache, list_all_caches, load_cache, save_cache
from .cleaner import CleanResult, permanent_delete, trash_files
from .constants import ScanStatus
from .duplicate_finder import find_duplicates, get_duplicate_stats
from .exporter import export_report
from .models import DirInfo, ScanResult
from .scanner import DirectoryScanner, build_old_dirs_map
from .widgets.confirm_dialog import ConfirmDialog
from .widgets.directory_tree import DirectoryTree
from .widgets.file_info import FileInfoPanel
from .widgets.search_bar import SearchBar, matches_search_filter
from .widgets.size_bar import SizeBar


def _get_presets() -> list[tuple[str, str]]:
    """获取预设扫描路径列表：[(显示名, 路径)]"""
    home = Path.home()
    presets = [
        (f"当前目录 ({os.getcwd()})", os.getcwd()),
        (f"C 盘 (C:\\)", "C:\\"),
    ]
    if os.path.exists("D:\\"):
        presets.append((f"D 盘 (D:\\)", "D:\\"))
    presets.extend([
        (f"用户目录 ({home})", str(home)),
        (f"桌面 ({home / 'Desktop'})", str(home / "Desktop")),
    ])
    return presets


class GoodCleanApp(App):
    """GoodClean 终端磁盘清理工具"""

    TITLE = "GoodClean v1.0"
    SUB_TITLE = "终端磁盘清理工具"

    CSS = """
    /* ── 欢迎视图 ── */
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

    .cache-line {
        width: 100%;
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    #start-btn {
        width: 20;
        margin-top: 1;
        align: center middle;
    }

    #welcome-help {
        text-align: center;
        width: 100%;
        color: $text-muted;
        margin-top: 1;
    }

    /* ── 主视图 ── */
    #main-view {
        height: 1fr;
        display: none;
    }

    #main-view.active {
        display: block;
    }

    #scan-progress {
        height: 3;
        padding: 0 1;
    }

    SearchBar {
        height: 3;
    }

    SearchBar > Horizontal {
        height: 3;
    }

    #search-input {
        width: 2fr;
        height: 3;
    }

    #filter-type {
        width: 1fr;
        max-width: 20;
        height: 3;
    }

    #filter-size {
        width: 1fr;
        max-width: 18;
        height: 3;
    }

    #search-info {
        width: 15;
        height: 3;
    }

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

    DirectoryTree {
        height: 1fr;
    }

    #help-text {
        height: auto;
        padding: 0 1;
        background: $surface;
    }
    """

    # 只保留主界面需要的绑定，欢迎界面由原生组件处理
    BINDINGS = [
        Binding("question_mark", "show_help", "帮助", show=True, key_display="?"),
        Binding("slash", "focus_search", "搜索", show=True),
        Binding("d", "trash_selected", "回收站", show=True),
        Binding("D", "permanent_delete_selected", "删除", show=True),
        Binding("s", "toggle_sort", "排序", show=True),
        Binding("r", "rescan", "重扫", show=True),
        Binding("t", "show_types", "类型", show=True),
        Binding("e", "export_report", "导出", show=True),
        Binding("f", "find_duplicates", "查重", show=True),
    ]

    def check_action(self, action: str, payload=None) -> bool:
        """欢迎界面时禁用所有绑定，RadioSet/Button 自己处理键盘"""
        return not self._show_welcome

    def __init__(self, scan_path: str | None = None, use_cache: bool = True,
                 export_path: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._scan_path = scan_path or ""
        self._use_cache = use_cache
        self._export_path = export_path
        self._show_welcome = scan_path is None
        self._welcome_presets = _get_presets()
        self._scanner: DirectoryScanner | None = None
        self._scan_result: ScanResult | None = None
        self._root_dir: DirInfo | None = None
        self._selected_paths: set[str] = set()
        self._sort_by_size = True
        self._showing_types = False
        self._search_query = ""
        self._filter_type = ""
        self._filter_size = ""
        self._showing_duplicates = False

    def compose(self) -> ComposeResult:
        yield Header()

        # ── 欢迎视图：全部用原生组件 ──
        with Vertical(id="welcome-view"):
            with Vertical(id="welcome-container"):
                yield Static("GoodClean v1.0.0", id="welcome-title")
                yield Static("终端磁盘清理工具", id="welcome-subtitle")

                yield Static("── 选择扫描路径 ──", classes="section-label")
                yield RadioSet(
                    *[
                        name for name, _ in self._welcome_presets
                    ],
                    id="path-radio",
                )

                yield Static("── 扫描模式 ──", classes="section-label")
                with Horizontal(id="mode-switch-container"):
                    yield Switch(value=self._use_cache, id="cache-switch")
                    yield Static("  标准模式（使用缓存加速）", id="mode-label")

                yield Static(self._make_cache_text(), classes="cache-line",
                             id="welcome-cache-line")

                yield Button("开始扫描", variant="primary", id="start-btn")

                yield Static(
                    "↑↓ 选择路径  |  Tab 切换控件  |  Enter 确认",
                    id="welcome-help",
                )

        # ── 主扫描视图 ──
        with Vertical(id="main-view"):
            with Vertical(id="top-bar"):
                yield Static("", id="scan-progress")
                yield SearchBar(id="search-bar")
            with Horizontal(id="main-container"):
                with Vertical(id="left-panel"):
                    yield DirectoryTree(id="dir-tree")
                with Vertical(id="right-panel"):
                    yield SizeBar(id="size-bar")
                    yield FileInfoPanel(id="file-info")
            yield Static(self._make_help_text(), id="help-text")

        yield Footer()

        if self._show_welcome:
            self._show_welcome_view()
        else:
            self._show_main_view()

    # ──────────────────── 视图切换 ────────────────────

    def _show_welcome_view(self) -> None:
        try:
            self.query_one("#welcome-view").styles.display = "block"
            self.query_one("#main-view").styles.display = "none"
            self.query_one("#path-radio").focus()
        except Exception:
            pass

    def _show_main_view(self) -> None:
        try:
            self.query_one("#welcome-view").styles.display = "none"
            self.query_one("#main-view").add_class("active")
            search_bar = self.query_one("#search-bar", SearchBar)
            search_bar.set_on_search_change(self._on_search_change)
        except Exception:
            pass

    def _switch_to_main(self) -> None:
        self._show_welcome = False
        self._show_main_view()
        self._start_scan(use_cache=self._use_cache)

    # ──────────────────── 欢迎界面事件 ────────────────────

    @on(Button.Pressed, "#start-btn")
    def _on_start_pressed(self) -> None:
        """点击开始按钮"""
        radio = self.query_one("#path-radio", RadioSet)
        idx = radio.pressed_index
        if idx is None or idx < 0:
            self.notify("请先选择一个扫描路径", severity="warning")
            return
        _, path = self._welcome_presets[idx]
        self._scan_path = path
        self._use_cache = self.query_one("#cache-switch", Switch).value
        self._switch_to_main()

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

    # ──────────────────── 启动 ────────────────────

    def on_mount(self) -> None:
        if not self._show_welcome:
            search_bar = self.query_one("#search-bar", SearchBar)
            search_bar.set_on_search_change(self._on_search_change)
            self._start_scan(use_cache=self._use_cache)

    # ──────────────────── 扫描 ────────────────────

    def _start_scan(self, use_cache: bool | None = None) -> None:
        if use_cache is not None:
            self._use_cache = use_cache
        self.scan_status = ScanStatus.SCANNING
        self._update_progress("正在扫描...", 0, 0)
        self._do_scan()

    @work(exclusive=True, thread=True)
    def _do_scan(self) -> None:
        start_time = time.time()
        use_cache = self._use_cache
        cached = None

        if use_cache:
            try:
                cached = load_cache(self._scan_path)
            except Exception:
                cached = None
            if cached is not None:
                self.app.call_from_thread(self._on_scan_complete, cached)
                return

        scanner = DirectoryScanner(self._scan_path)

        def on_progress(dirs: int, errors: int) -> None:
            self.app.call_from_thread(
                self._update_progress,
                f"扫描中... 已扫描 {dirs} 个目录", dirs, errors,
            )

        scanner.on_progress(on_progress)
        self._scanner = scanner

        try:
            loop = asyncio.new_event_loop()
            try:
                root_dir = loop.run_until_complete(scanner.scan())
            finally:
                loop.close()

            duration = time.time() - start_time
            result = analyze(root_dir, self._scan_path)
            result.scan_duration = duration

            if use_cache:
                try:
                    save_cache(result)
                except Exception:
                    pass

            self.app.call_from_thread(self._on_scan_complete, result)

            if self._export_path:
                try:
                    output = export_report(result, self._export_path)
                    self.app.call_from_thread(self.notify, f"报告已导出: {output}", {"timeout": 5})
                except Exception as e:
                    self.app.call_from_thread(self.notify, f"导出失败: {e}", {"severity": "error"})
                finally:
                    self.app.call_from_thread(self.exit)

        except Exception as e:
            self.app.call_from_thread(self._on_scan_error, str(e))

    # ──────────────────── 扫描结果 ────────────────────

    scan_status: reactive[str] = reactive(ScanStatus.IDLE)

    def _update_progress(self, text: str, dirs: int, errors: int) -> None:
        err_text = f"  |  权限错误: {errors}" if errors > 0 else ""
        self.query_one("#scan-progress", Static).update(f"  {text}{err_text}")

    def _on_scan_complete(self, result: ScanResult) -> None:
        self._scan_result = result
        self._root_dir = result.root_dir
        self.scan_status = ScanStatus.DONE

        cache_hint = " [cached]" if self._use_cache else ""
        self.query_one("#scan-progress", Static).update(
            f"  Done | {format_size(result.total_size)} | "
            f"{result.total_files} files | {result.total_dirs} dirs | "
            f"{result.scan_duration:.1f}s{cache_hint}"
        )

        self.query_one("#dir-tree", DirectoryTree).load_dir(result.root_dir)
        self.query_one("#size-bar", SizeBar).set_data(result.top_dirs, "Top 20")

    def _on_scan_error(self, error: str) -> None:
        self.scan_status = ScanStatus.ERROR
        self.query_one("#scan-progress", Static).update(f"  Error: {error}")

    def _update_progress_done(self) -> None:
        if self._scan_result:
            r = self._scan_result
            self.query_one("#scan-progress", Static).update(
                f"  Done | {format_size(r.total_size)} | "
                f"{r.total_files} files | {r.total_dirs} dirs | {r.scan_duration:.1f}s"
            )

    # ──────────────────── 交互 ────────────────────

    def on_directory_tree_selected_path_changed(self, event) -> None:
        path = event.value
        if path and self._root_dir:
            dir_info = self._find_dir(self._root_dir, path)
            if dir_info:
                self.query_one("#file-info", FileInfoPanel).set_dir_info(dir_info)
                self.query_one("#size-bar", SizeBar).set_highlight(path)

    def _find_dir(self, di: DirInfo | None, path: str) -> DirInfo | None:
        if di is None:
            return None
        if di.path == path:
            return di
        for child in di.children:
            result = self._find_dir(child, path)
            if result:
                return result
        return None

    def _on_search_change(self, query: str, filter_type: str, filter_size: str) -> None:
        self._search_query = query
        self._filter_type = filter_type
        self._filter_size = filter_size
        self._update_filtered_view()

    def _update_filtered_view(self) -> None:
        if not self._scan_result or not self._root_dir:
            return
        if not self._search_query and not self._filter_type and not self._filter_size:
            self.query_one("#size-bar", SizeBar).set_data(self._scan_result.top_dirs, "Top 20")
            self.query_one("#search-bar", SearchBar).update_result_count(0, 0)
            return

        matched_files = []
        self._collect_filtered_files(self._root_dir, matched_files)

        size_bar = self.query_one("#size-bar", SizeBar)
        if matched_files:
            matched_files.sort(key=lambda f: f.size, reverse=True)
            size_bar.set_file_data(matched_files[:20], "Top 20")

        self.query_one("#search-bar", SearchBar).update_result_count(
            len(matched_files), self._scan_result.total_files
        )

    def _collect_filtered_files(self, di: DirInfo, result: list) -> None:
        for f in di.files:
            if matches_search_filter(
                f.name, f.path, f.size, f.extension,
                self._search_query, self._filter_type, self._filter_size,
            ):
                result.append(f)
        for child in di.children:
            self._collect_filtered_files(child, result)

    # ──────────────────── 清理 ────────────────────

    def action_trash_selected(self) -> None:
        paths = self._get_selected_paths()
        if not paths:
            self.notify("请先选择要删除的项目（Space 选中）", severity="warning")
            return
        total_size = sum(self._get_path_size(p) for p in paths)
        self.push_screen(
            ConfirmDialog(
                f"确定将 {len(paths)} 个项目移到回收站？",
                count=len(paths), total_size=total_size, is_permanent=False,
            ),
            self._on_trash_confirm,
        )

    def _on_trash_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        paths = self._get_selected_paths()
        if not paths:
            return
        self.query_one("#scan-progress", Static).update(f"  正在将 {len(paths)} 个项目移到回收站...")
        self._do_trash(paths)

    @work(exclusive=True, thread=True)
    def _do_trash(self, paths: list[str]) -> None:
        result = trash_files(paths)
        self.app.call_from_thread(self._show_clean_result, result, "回收站")

    def action_permanent_delete_selected(self) -> None:
        paths = self._get_selected_paths()
        if not paths:
            self.notify("请先选择要删除的项目（Space 选中）", severity="warning")
            return
        total_size = sum(self._get_path_size(p) for p in paths)
        self.push_screen(
            ConfirmDialog(
                f"确定永久删除 {len(paths)} 个项目？不可恢复！",
                count=len(paths), total_size=total_size, is_permanent=True,
            ),
            self._on_permanent_confirm,
        )

    def _on_permanent_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        paths = self._get_selected_paths()
        if not paths:
            return
        self.query_one("#scan-progress", Static).update(f"  正在永久删除 {len(paths)} 个项目...")
        self._do_permanent_delete(paths)

    @work(exclusive=True, thread=True)
    def _do_permanent_delete(self, paths: list[str]) -> None:
        result = permanent_delete(paths)
        self.app.call_from_thread(self._show_clean_result, result, "永久删除")

    def _show_clean_result(self, result: CleanResult, mode: str) -> None:
        freed = format_size(result.freed_bytes)
        msg = f"  {result.success_count} 个已{mode}，释放 {freed}"
        if result.errors:
            msg += f" | {result.fail_count} 个失败"
        self.notify(msg)
        self._update_progress_done()
        self._selected_paths.clear()
        try:
            self.query_one("#dir-tree", DirectoryTree).selected_paths = set()
        except Exception:
            pass
        if result.success_count > 0:
            self._start_scan(use_cache=False)

    # ──────────────────── 工具 ────────────────────

    def action_toggle_sort(self) -> None:
        if not self._scan_result:
            return
        self._sort_by_size = not self._sort_by_size
        size_bar = self.query_one("#size-bar", SizeBar)
        if self._sort_by_size:
            size_bar.set_data(self._scan_result.top_dirs, "Top 20")
        else:
            sorted_dirs = sorted(
                self._scan_result.top_dirs, key=lambda d: d.file_count, reverse=True,
            )[:20]
            size_bar.set_data(sorted_dirs, "Top 20")
        self.notify(f"排序方式: {'大小' if self._sort_by_size else '文件数量'}")

    def action_rescan(self) -> None:
        self._start_scan(use_cache=False)

    def action_show_types(self) -> None:
        if not self._root_dir:
            return
        self._showing_types = not self._showing_types
        size_bar = self.query_one("#size-bar", SizeBar)
        if self._showing_types:
            dist = get_file_type_distribution(self._root_dir)
            from .models import DirInfo as DI
            type_dirs = []
            for ext, (count, size) in list(dist.items())[:20]:
                type_dirs.append(DI(path=ext, name=f"{ext} ({count}个文件)",
                                   total_size=size, file_count=count))
            size_bar.set_data(type_dirs, "Top 20")
        else:
            if self._scan_result:
                size_bar.set_data(self._scan_result.top_dirs, "Top 20")

    def action_focus_search(self) -> None:
        input_widget = self.query_one("#search-bar", SearchBar).query_one("#search-input")
        input_widget.focus()

    def action_clear_search(self) -> None:
        self.query_one("#search-bar", SearchBar).clear_filters()
        self._search_query = ""
        self._filter_type = ""
        self._filter_size = ""
        self._update_filtered_view()

    def action_find_duplicates(self) -> None:
        if not self._root_dir:
            self.notify("请先等待扫描完成", severity="warning")
            return
        self._showing_duplicates = not self._showing_duplicates
        size_bar = self.query_one("#size-bar", SizeBar)
        if self._showing_duplicates:
            self.notify("正在查找重复文件...")
            duplicates = find_duplicates(self._root_dir)
            stats = get_duplicate_stats(duplicates)
            if not duplicates:
                self.notify("未发现重复文件")
                self._showing_duplicates = False
                return
            savings = format_size(stats["total_size"])
            self.notify(
                f"发现 {stats['total_groups']} 组重复文件，"
                f"共 {stats['total_files']} 个，可节省 {savings}"
            )
            from .models import DirInfo as DI
            dup_dirs = []
            for i, group in enumerate(duplicates[:20], 1):
                savings_size = sum(f.size for f in group[1:])
                dup_dirs.append(DI(path=f"dup_{i}",
                                   name=f"重复组 {i} ({len(group)} 个文件)",
                                   total_size=savings_size, file_count=len(group)))
            size_bar.set_data(dup_dirs, f"Top 20 (可节省 {savings})")
        else:
            if self._scan_result:
                size_bar.set_data(self._scan_result.top_dirs, "Top 20")

    def action_show_help(self) -> None:
        self.notify(
            "GoodClean 快捷键帮助\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "↑↓       导航目录树\n"
            "Enter    展开/折叠\n"
            "Space    选中/取消\n"
            "/        搜索\n"
            "d        回收站\n"
            "D        永久删除\n"
            "s        排序\n"
            "t        类型分布\n"
            "e        导出报告\n"
            "f        查重复\n"
            "r        重新扫描\n"
            "Esc      清除搜索\n"
            "q        退出",
            timeout=8,
        )

    def action_export_report(self) -> None:
        if not self._scan_result:
            self.notify("请先等待扫描完成", severity="warning")
            return
        self.query_one("#scan-progress", Static).update("  正在导出报告...")
        self._do_export()

    @work(exclusive=True, thread=True)
    def _do_export(self) -> None:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            out = export_report(self._scan_result, f"goodclean_report_{ts}.html")
            self.app.call_from_thread(self.notify, f"报告已导出: {out}", {"timeout": 5})
        except Exception as e:
            self.app.call_from_thread(self.notify, f"导出失败: {e}", {"severity": "error"})
        finally:
            self.app.call_from_thread(self._update_progress_done)

    # ──────────────────── 辅助 ────────────────────

    def _get_selected_paths(self) -> list[str]:
        paths = list(self.query_one("#dir-tree", DirectoryTree).selected_paths)
        self.notify(f"当前选中: {len(paths)} 个项目", timeout=2)
        return paths

    def _get_path_size(self, path: str) -> int:
        if self._root_dir:
            di = self._find_dir(self._root_dir, path)
            if di:
                return di.total_size
        return 0

    def _make_help_text(self) -> str:
        return (
            "  [[/]] 搜索  [[Enter]] 展开  [[Space]] 选中  [[d]] 回收站  [[D]] 永久删除  "
            "[[s]] 排序  [[t]] 类型  [[e]] 导出  [[f]] 查重  [[r]] 重扫  [[?]] 帮助  [[q]] 退出"
        )
