"""主扫描视图：目录树、大小排行、文件详情、搜索、清理"""

from __future__ import annotations

import asyncio
import time

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ..analyzer import analyze, format_size
from ..cache import get_cache_info, load_cache, save_cache
from ..cleaner import CleanResult, permanent_delete, trash_files
from ..constants import ScanStatus
from ..duplicate_finder import find_duplicates, get_duplicate_stats
from ..exporter import export_report
from ..models import DirInfo, ScanResult
from ..suggestion import CleanupSuggestion, generate_cleanup_suggestions, get_suggestion_summary
from ..scanner import DirectoryScanner
from ..widgets.confirm_dialog import ConfirmDialog
from ..widgets.directory_tree import DirectoryTree
from ..widgets.file_info import FileInfoPanel
from ..widgets.search_bar import SearchBar, matches_search_filter
from ..widgets.size_bar import SizeBar


CSS = """
#scan-progress {
    height: 3;
    padding: 0 1;
}

#cache-status {
    height: 1;
    padding: 0 1;
    color: $text-muted;
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


HELP_TEXT = (
    "  [[/]] 搜索  [[Space]] 选中  [[d]] 回收站  [[D]] 永久删除  "
    "[[s]] 排序  [[t]] 类型  [[e]] 导出  [[f]] 查重  "
    "[[c]] 建议  [[x]] 一键清理  [[r]] 重扫  [[?]] 帮助  [[q]] 退出"
)


class MainScreen(Screen):
    """主扫描视图"""

    CSS = CSS

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
        Binding("c", "show_suggestions", "建议", show=True),
        Binding("x", "safe_cleanup", "一键清理", show=True),
        Binding("escape", "clear_search", "清除搜索", show=False),
    ]

    def __init__(self, scan_path: str, use_cache: bool = True,
                 export_path: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._scan_path = scan_path
        self._use_cache = use_cache
        self._export_path = export_path
        self._scanner: DirectoryScanner | None = None
        self._scan_result: ScanResult | None = None
        self._root_dir: DirInfo | None = None
        self._selected_paths: set[str] = set()
        # 从配置恢复排序方式
        from ..config import get_sort_by_size
        cached_sort = get_sort_by_size()
        self._sort_by_size = cached_sort if cached_sort is not None else True
        self._showing_types = False
        self._search_query = ""
        self._filter_type = ""
        self._filter_size = ""
        self._showing_duplicates = False
        self._showing_suggestions = False
        self._current_suggestions: list[CleanupSuggestion] = []
        self._current_scan_use_cache: bool = use_cache

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="top-bar"):
            yield Static("", id="scan-progress")
            yield Static("", id="cache-status")
            yield SearchBar(id="search-bar")
        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield DirectoryTree(id="dir-tree")
            with Vertical(id="right-panel"):
                yield SizeBar(id="size-bar")
                yield FileInfoPanel(id="file-info")
        yield Static(HELP_TEXT, id="help-text")
        yield Footer()

    def on_mount(self) -> None:
        search_bar = self.query_one("#search-bar", SearchBar)
        search_bar.set_on_search_change(self._on_search_change)
        self._start_scan(use_cache=self._use_cache)

    # ──────────────────── 扫描 ────────────────────

    scan_status: reactive[str] = reactive(ScanStatus.IDLE)

    def _start_scan(self, use_cache: bool | None = None) -> None:
        if use_cache is not None:
            self._current_scan_use_cache = use_cache
        self.scan_status = ScanStatus.SCANNING
        self._update_progress("正在扫描...", 0, 0)
        self._do_scan()

    @work(exclusive=True, thread=True)
    def _do_scan(self) -> None:
        start_time = time.time()
        use_cache = self._current_scan_use_cache
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
                    self.app.call_from_thread(self.app.exit)

        except Exception as e:
            self.app.call_from_thread(self._on_scan_error, str(e))

    # ──────────────────── 扫描结果 ────────────────────

    def _update_progress(self, text: str, dirs: int, errors: int) -> None:
        err_text = f"  |  权限错误: {errors}" if errors > 0 else ""
        self.query_one("#scan-progress", Static).update(f"  {text}{err_text}")

    def _on_scan_complete(self, result: ScanResult) -> None:
        self._scan_result = result
        self._root_dir = result.root_dir
        self.scan_status = ScanStatus.DONE

        cache_hint = " [cached]" if self._current_scan_use_cache else ""
        self.query_one("#scan-progress", Static).update(
            f"  Done | {format_size(result.total_size)} | "
            f"{result.total_files} files | {result.total_dirs} dirs | "
            f"{result.scan_duration:.1f}s{cache_hint}"
        )
        self._update_cache_status()

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
            self._update_cache_status()

    def _update_cache_status(self) -> None:
        try:
            info = get_cache_info(self._scan_path)
            status = self.query_one("#cache-status", Static)
            if not self._current_scan_use_cache:
                status.update("  Cache: off (force refresh)")
                return
            if info is None:
                status.update("  Cache: none (first scan)")
            elif info["expired"]:
                status.update(
                    f"  Cache: expired ({info['age_hours']}h old, valid 24h)"
                )
            else:
                age = info["age_hours"]
                age_str = f"{int(age * 60)}min" if age < 1 else f"{age}h"
                size = format_size(info["file_size"])
                status.update(
                    f"  Cache: hit | scanned {age_str} ago | cache {size}"
                )
        except Exception:
            pass

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
        self.app.push_screen(
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
        self.query_one("#scan-progress", Static).update(f"  正在计算项目数并移到回收站...")
        self._do_trash(paths)

    @work(exclusive=True, thread=True)
    def _do_trash(self, paths: list[str]) -> None:
        result = trash_files(paths, on_progress=self._on_delete_progress)
        self.app.call_from_thread(self._show_clean_result, result, "回收站")

    def action_permanent_delete_selected(self) -> None:
        paths = self._get_selected_paths()
        if not paths:
            self.notify("请先选择要删除的项目（Space 选中）", severity="warning")
            return
        total_size = sum(self._get_path_size(p) for p in paths)
        self.app.push_screen(
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
        self.query_one("#scan-progress", Static).update(f"  正在计算项目数并永久删除...")
        self._do_permanent_delete(paths)

    @work(exclusive=True, thread=True)
    def _do_permanent_delete(self, paths: list[str]) -> None:
        result = permanent_delete(paths, on_progress=self._on_delete_progress)
        self.app.call_from_thread(self._show_clean_result, result, "永久删除")

    def _on_delete_progress(self, current: int, total: int, path: str, freed: int) -> None:
        """删除进度回调（在后台线程中执行，需通过 call_from_thread 更新 UI）"""
        if total <= 0:
            return
        pct = current * 100 // total
        freed_str = format_size(freed)
        # 截断长路径显示
        display_path = path
        if len(display_path) > 50:
            display_path = "..." + display_path[-47:]
        msg = f"  删除中... {current}/{total} ({pct}%) | 已释放 {freed_str} | {display_path}"
        self.app.call_from_thread(self._update_progress_text, msg)

    def _update_progress_text(self, text: str) -> None:
        """在主线程中更新进度文本（供 call_from_thread 使用）"""
        try:
            self.query_one("#scan-progress", Static).update(text)
        except Exception:
            pass

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
        # 保存排序配置
        from ..config import set_sort_by_size
        set_sort_by_size(self._sort_by_size)
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
            from ..analyzer import get_file_category_distribution
            categories = get_file_category_distribution(self._root_dir)
            total_count = sum(c["count"] for c in categories)
            total_size = sum(c["total_size"] for c in categories)
            self.notify(
                f"文件类型分析: {len(categories)} 种类型 | "
                f"{total_count} 个文件 | {format_size(total_size)}",
                timeout=3,
            )
            size_bar.set_category_data(categories, f"类型分布 Top {len(categories)}")
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
            from ..models import DirInfo as DI
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

    def action_show_suggestions(self) -> None:
        if not self._root_dir:
            self.notify("请先等待扫描完成", severity="warning")
            return
        self._showing_suggestions = not self._showing_suggestions
        size_bar = self.query_one("#size-bar", SizeBar)
        if self._showing_suggestions:
            suggestions = generate_cleanup_suggestions(self._scan_result)
            self._current_suggestions = suggestions
            summary = get_suggestion_summary(suggestions)
            self.notify(
                f"清理建议: {summary['safe_count']} 项安全 "
                f"({format_size(summary['safe_size'])}) | "
                f"{summary['caution_count']} 项谨慎 "
                f"({format_size(summary['caution_size'])})",
                timeout=4,
            )
            size_bar.set_suggestion_data(
                suggestions,
                f"清理建议 (安全: {summary['safe_count']} 谨慎: {summary['caution_count']})",
            )
        else:
            self._current_suggestions = []
            if self._scan_result:
                size_bar.set_data(self._scan_result.top_dirs, "Top 20")

    def action_safe_cleanup(self) -> None:
        if not self._scan_result:
            self.notify("请先等待扫描完成", severity="warning")
            return

        suggestions = generate_cleanup_suggestions(self._scan_result)
        safe_suggestions = [s for s in suggestions if s.risk == "safe"]

        if not safe_suggestions:
            self.notify("没有可安全清理的项目", severity="info")
            return

        all_paths: list[str] = []
        total_size = 0
        for s in safe_suggestions:
            if s.is_dir:
                all_paths.append(s.path)
                total_size += s.size
            else:
                all_paths.extend(s.paths)
                total_size += s.size

        all_paths = list(dict.fromkeys(all_paths))

        self.app.push_screen(
            ConfirmDialog(
                f"一键安全清理 {len(safe_suggestions)} 个项目？",
                count=len(all_paths), total_size=total_size, is_permanent=False,
            ),
            self._on_safe_cleanup_confirm,
        )

    def _on_safe_cleanup_confirm(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        suggestions = generate_cleanup_suggestions(self._scan_result)
        safe_suggestions = [s for s in suggestions if s.risk == "safe"]

        all_paths: list[str] = []
        for s in safe_suggestions:
            if s.is_dir:
                all_paths.append(s.path)
            else:
                all_paths.extend(s.paths)
        all_paths = list(dict.fromkeys(all_paths))

        if not all_paths:
            return

        self.query_one("#scan-progress", Static).update(
            f"  一键安全清理中... ({len(all_paths)} 个项目)"
        )
        self._do_safe_cleanup(all_paths)

    @work(exclusive=True, thread=True)
    def _do_safe_cleanup(self, paths: list[str]) -> None:
        result = trash_files(paths, on_progress=self._on_delete_progress)
        self.app.call_from_thread(self._show_clean_result, result, "安全清理")

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
            "c        清理建议\n"
            "x        一键安全清理\n"
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
