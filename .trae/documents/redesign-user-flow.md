# GoodClean 用户流程重新设计方案

## 一、用户故事

**核心用户故事**：作为用户，我希望能通过 `goodclean` 命令快速进入一个交互式界面，选择扫描模式和目标路径，高效地分析和清理磁盘空间。

**场景拆解**：
1. 用户在终端输入 `goodclean`，看到欢迎界面和菜单
2. 用户选择扫描目标（快捷预设或自定义路径）
3. 用户选择扫描模式（快速/标准/深度），决定是否使用缓存
4. 扫描完成后进入主界面浏览、筛选、清理
5. 退出前可导出报告

---

## 二、当前状态分析

### 已有（可复用）
- `cache.py`：完整的缓存实现（save/load/clear/get_info），但从未被调用
- `scanner.py`：增量扫描基础设施已就绪（`set_old_dirs`、`_is_dir_unchanged`、`build_old_dirs_map`）
- 所有核心扫描/分析/清理/导出功能完好

### 需要改动
- `__main__.py`：入口过于简单，无交互式菜单
- `app.py`：启动即扫描，无选择界面；缓存逻辑被删除
- `__init__.py`：需要导出入口命令

### 问题
- `action_rescan()` 调用 `self._start_scan(force=True)` 但 `_start_scan` 不接受参数
- 缓存模块完全未集成到任何地方

---

## 三、设计方案

### 3.1 新增文件：`goodclean/screens/welcome.py` — 欢迎/菜单屏幕

Textual `Screen` 子类，作为应用的首个屏幕。

**布局**：
```
┌──────────────────────────────────────────┐
│           GoodClean v1.0.0               │
│       终端磁盘清理工具                     │
│                                          │
│  ── 快捷扫描 ──                          │
│  [1] 当前目录        (d:\workspace\...)  │
│  [2] C 盘            (C:\)               │
│  [3] D 盘            (D:\)               │
│  [4] 用户目录        (C:\Users\xxx)      │
│  [5] 桌面            (C:\Users\xxx\Desktop)│
│                                          │
│  ── 自定义 ──                            │
│  [6] 输入自定义路径                       │
│                                          │
│  ── 扫描模式 ──                          │
│  [T] 标准模式（推荐）  使用缓存加速       │
│  [F] 强制刷新          跳过缓存，重新扫描  │
│                                          │
│  ── 工具 ──                              │
│  [C] 清除缓存                            │
│  [Q] 退出                                │
└──────────────────────────────────────────┘
```

**交互逻辑**：
- 数字键 `1-5` 直接选择预设路径 + 标准模式，立即开始扫描
- 数字键 `6` 弹出 Input 对话框输入自定义路径
- `T/F` 切换扫描模式（标准=使用缓存 / 强制刷新=跳过缓存）
- `C` 清除所有缓存并提示
- 选中路径后高亮显示，按下回车确认开始扫描
- 扫描完成后自动 push 到主屏幕（`DiskExplorer`）

**缓存状态指示**：在菜单底部显示"缓存状态：X 条缓存可用"，让用户知道缓存情况。

### 3.2 改动文件：`goodclean/app.py` — 主应用重构

**改动点**：
1. 移除 `on_mount` 中的自动扫描逻辑
2. 修改 `on_mount` 为 `push_screen("welcome")` 显示欢迎屏幕
3. 新增 `start_scan(path, use_cache=True)` 公共方法，由 WelcomeScreen 回调调用
4. 集成缓存逻辑到 `_do_scan()`：
   - `use_cache=True` 时：先尝试 `load_cache()`，命中则直接加载，未命中则扫描后 `save_cache()`
   - `use_cache=False` 时：直接扫描，不读/写缓存
5. 增量扫描集成：`use_cache=True` 且缓存命中时，用缓存数据作为旧数据调用 `scanner.set_old_dirs()`
6. 修复 `action_rescan()` 中的参数传递问题

**关键方法改造**：
```python
class GoodCleanApp(App):
    def on_mount(self):
        self.push_screen("welcome")

    async def start_scan(self, path: str, use_cache: bool = True):
        """由 WelcomeScreen 调用，启动扫描"""
        self._scan_path = path
        self._use_cache = use_cache
        self._start_scan()

    def _do_scan(self):
        """扫描逻辑，集成缓存"""
        # 1. 如果 use_cache，尝试加载缓存
        if self._use_cache:
            cached = load_cache(self._scan_path)
            if cached:
                # 缓存命中，直接使用
                self.call_from_thread(self._on_scan_complete, cached)
                return
        # 2. 扫描
        scanner = DirectoryScanner(self._scan_path)
        # 3. 如果 use_cache 有旧数据，设置增量
        old_data = load_cache(self._scan_path) if self._use_cache else None
        if old_data and old_data.root_dir:
            old_map = build_old_dirs_map(old_data.root_dir)
            scanner.set_old_dirs(old_map)
        # 4. 执行扫描...
        # 5. 扫描完保存缓存
        if self._use_cache:
            save_cache(scan_result)
```

### 3.3 改动文件：`goodclean/__main__.py` — 简化入口

**改动点**：
- 保留命令行参数支持（`goodclean [path]` 可直接指定路径跳过菜单）
- 新增 `--no-cache` 参数
- 新增 `--cache-info` 参数（显示缓存信息后退出）
- `goodclean` 无参数时进入交互式菜单
- 去掉 `--no-tui` 模式（不再需要，所有操作都在 TUI 中）

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", help="扫描路径（可选，跳过菜单直接扫描）")
    parser.add_argument("--no-cache", action="store_true", help="不使用缓存")
    parser.add_argument("--version", action="version", version=...)
    parser.add_argument("--export", help="导出报告到文件")
    parser.add_argument("--cache-info", action="store_true", help="查看缓存信息")
    args = parser.parse_args()

    if args.cache_info:
        # 显示缓存信息后退出
        ...

    app = GoodCleanApp(
        scan_path=args.path,
        use_cache=not args.no_cache,
        export_path=args.export,
    )
    app.run()
```

### 3.4 改动文件：`goodclean/cache.py` — 小幅优化

**改动点**：
- `get_cache_info()` 返回 `CacheInfo` dataclass（已有，确认）
- 新增 `list_all_caches()` 函数，返回所有缓存的摘要列表（供菜单显示"X 条缓存可用"）
- 缓存有效期从 24 小时改为用户可配置（默认 24 小时，通过常量控制）

### 3.5 改动文件：`goodclean/constants.py` — 新增常量

```python
# 扫描模式
SCAN_MODE_STANDARD = "standard"   # 标准模式（使用缓存）
SCAN_MODE_FORCE = "force"         # 强制刷新（跳过缓存）

# 缓存有效期（小时）
CACHE_MAX_AGE_HOURS = 24

# 快捷扫描预设名称
PRESET_CURRENT = "当前目录"
PRESET_C_DRIVE = "C 盘"
PRESET_D_DRIVE = "D 盘"
PRESET_USER_DIR = "用户目录"
PRESET_DESKTOP = "桌面"
```

---

## 四、用户完整流程

### 流程 A：无参启动（交互式）
```
$ goodclean
  → 显示欢迎屏幕
  → 用户选择路径和模式
  → 开始扫描（带进度条）
  → 进入主界面浏览/清理
```

### 流程 B：指定路径启动
```
$ goodclean D:\
  → 跳过欢迎屏幕，直接扫描 D:\
  → 使用缓存（默认）
  → 进入主界面
```

### 流程 C：查看缓存
```
$ goodclean --cache-info
  → 显示：
    缓存条目: 3
    ├─ C:\ (扫描于 2026-06-03 14:30, 大小 2.3KB)
    ├─ D:\ (扫描于 2026-06-04 09:15, 大小 1.8KB)
    └─ D:\workspace (扫描于 2026-06-04 10:00, 大小 3.1KB)
  → 退出
```

### 流程 D：命令行导出
```
$ goodclean D:\ --export report.html
  → 后台扫描 + 分析 + 导出 HTML 报告
```

---

## 五、缓存策略设计

| 场景 | 缓存行为 | 说明 |
|------|---------|------|
| 标准模式启动 | 读缓存 → 命中则直接用，未命中则扫描后写缓存 | 加速启动 |
| 强制刷新模式 | 不读缓存，扫描后写缓存 | 获取最新结果 |
| 手动重新扫描 (r) | 强制刷新，扫描后写缓存 | 用户主动要更新 |
| 删除文件后 | 自动重新扫描（强制），扫描后写缓存 | 保证结果准确 |
| 缓存过期 (>24h) | 自动过期，视为未命中 | 避免使用过时数据 |

---

## 六、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `goodclean/screens/__init__.py` | 新建 | 包初始化 |
| `goodclean/screens/welcome.py` | 新建 | 欢迎/菜单屏幕 |
| `goodclean/app.py` | 修改 | 集成缓存、支持屏幕切换、新增 start_scan 接口 |
| `goodclean/__main__.py` | 修改 | 简化入口，新增参数 |
| `goodclean/cache.py` | 修改 | 新增 list_all_caches，优化接口 |
| `goodclean/constants.py` | 修改 | 新增扫描模式和缓存常量 |

---

## 七、验证步骤

1. `goodclean` 无参启动 → 看到欢迎菜单
2. 选择快捷扫描 → 进度条正常 → 扫描完成进入主界面
3. 退出后再次 `goodclean` 同一路径 → 标准模式下直接从缓存加载
4. `goodclean --no-cache` → 跳过缓存重新扫描
5. `goodclean D:\` → 跳过菜单直接扫描 D 盘
6. `goodclean --cache-info` → 显示缓存列表
7. 所有原有功能正常：搜索、删除、导出、重复检测
