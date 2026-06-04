# GoodClean 键盘处理完全重构计划

## 问题诊断

### 根本原因
Textual 的按键处理流程：**BINDINGS 检查 → check_action → on_key → 焦点组件 on_key**

当 Input 有焦点时，用户按 `s`（想输入字符）：
1. 焦点在 Input，Input 的 BINDINGS 先被检查（Input 只有 backspace/left/right 等控制键绑定）
2. Input 没有匹配 `s`，继续向上查找到 App
3. App 有 `Binding("s", "toggle_sort")`，匹配！
4. `check_action("toggle_sort")` 返回 True（主界面）
5. `action_toggle_sort()` 被执行
6. Input 的 `on_key` 永远收不到这个字符

**`check_action` 只能控制 action 是否执行，不能阻止 BINDINGS 拦截事件。**

### 三个核心问题
1. **App BINDINGS 中的单字符键（q/s/d/t/e/f/r/D/escape/ slash）会拦截 Input 的正常输入**
2. **on_key 重复处理了与 BINDINGS 相同的按键，导致 action 被触发两次**
3. **欢迎界面需要按键处理，主界面 Input 需要放行——BINDINGS 无法动态切换**

## 修复方案

### 核心策略：移除 App BINDINGS，统一用 on_key 处理所有按键

**为什么这是唯一正确的方案：**
- BINDINGS 是静态的，无法根据焦点组件动态决定是否拦截
- `check_action` 只能阻止 action 执行，不能让按键到达 Input
- 只有 `on_key` 可以在 BINDINGS 之前检查焦点状态，决定是否 `event.stop()`

**关于 Footer 提示：** 可以通过 `self.footer` 直接设置 BINDINGS，或手动构建帮助文本。Footer 的 `keys` 参数不影响功能。

### 具体改动

#### 文件 1: `goodclean/app.py`

**删除所有 App BINDINGS：**
```python
# 删除这整段
BINDINGS = [
    Binding("q", "quit", "退出"),
    ...
]
```

**添加 `can_focus=False` 到 App（可选，确保 App 本身不抢焦点）**

**修改 `on_key` 方法，统一处理所有按键：**
```python
def on_key(self, event) -> None:
    key = event.key
    char = event.character
    
    # ===== 欢迎界面模式 =====
    if self._show_welcome:
        if char == "q":
            event.stop()
            self.exit()
        elif char == "t":
            event.stop()
            self._use_cache = not self._use_cache
            self.query_one("#welcome-mode-line").update(self._make_welcome_mode())
        elif char == "c":
            event.stop()
            count = clear_cache()
            self.notify(...)
            self.query_one("#welcome-cache-line").update(self._make_welcome_cache())
        elif key == "enter":
            event.stop()
            self._welcome_confirm()
        elif key == "escape":
            event.stop()
            self.exit()
        elif char is not None:
            for i, (k, _, _) in enumerate(self._welcome_presets):
                if char == k:
                    event.stop()
                    self._welcome_selected = i
                    self._update_welcome_highlight()
                    return
        return
    
    # ===== 主界面模式 =====
    
    # 第一优先级：检查是否有可编辑组件有焦点
    # （Input、Select 等），如果有焦点则放行按键
    if self._has_focused_input():
        if key == "escape":
            event.stop()
            self._blur_focused_input()
            self.action_clear_search()
        # 其他键不拦截，让 Input/Select 正常接收
        return
    
    # 第二优先级：处理功能键
    if char == "q":
        event.stop()
        self.exit()
    elif key == "question_mark":
        event.stop()
        self.action_show_help()
    elif char == "/":
        event.stop()
        self.action_focus_search()
    elif char == "d":
        event.stop()
        self.action_trash_selected()
    elif char == "D":
        event.stop()
        self.action_permanent_delete_selected()
    elif char == "s":
        event.stop()
        self.action_toggle_sort()
    elif char == "r":
        event.stop()
        self.action_rescan()
    elif char == "t":
        event.stop()
        self.action_show_types()
    elif char == "e":
        event.stop()
        self.action_export_report()
    elif char == "f":
        event.stop()
        self.action_find_duplicates()
    elif key == "escape":
        event.stop()
        self.action_clear_search()
```

**新增辅助方法 `_has_focused_input()` 和 `_blur_focused_input()`：**
```python
def _has_focused_input(self) -> bool:
    """检查是否有 Input 或 Select 等可编辑组件获得焦点"""
    try:
        focused = self.focused
        if focused is None:
            return False
        from textual.widgets import Input, Select
        return isinstance(focused, (Input, Select))
    except Exception:
        return False

def _blur_focused_input(self) -> None:
    """让当前焦点的可编辑组件失去焦点"""
    try:
        focused = self.focused
        if focused:
            focused.blur()
    except Exception:
        pass
```

#### 文件 2: `goodclean/widgets/search_bar.py`（无需改动）

SearchBar 的 Input 已经正常工作，问题在 App 层。

#### 文件 3: `goodclean/widgets/directory_tree.py`（无需改动）

DirectoryTree 的 BINDINGS（enter → toggle_node, space → toggle_select）作用在 Tree 组件自身，不影响 App 的按键。当焦点在 Tree 上时，Tree 的 BINDINGS 优先于 App（即使有 App BINDINGS，但我们现在移除了，所以更不影响）。

#### 文件 4: `goodclean/screens/welcome.py`（已删除，不需要恢复）

## 关于 Footer 提示

移除 BINDINGS 后 Footer 不会自动显示快捷键。解决方案：

在 `_show_main_view()` 中手动更新 Footer 的 bindings：
```python
def _show_main_view(self) -> None:
    ...
    # 为 Footer 设置快捷键提示
    self.footer.bindings = [
        Binding("/", "focus_search", "搜索", show=True),
        Binding("d", "trash_selected", "回收站", show=True),
        Binding("D", "permanent_delete_selected", "删除", show=True),
        Binding("s", "toggle_sort", "排序", show=True),
        Binding("r", "rescan", "重扫", show=True),
        Binding("t", "show_types", "类型", show=True),
        Binding("e", "export_report", "导出", show=True),
        Binding("f", "find_duplicates", "查重", show=True),
        Binding("?", "show_help", "帮助", show=True),
        Binding("q", "quit", "退出", show=True),
    ]
```

**但注意**：这些 Footer bindings 也会拦截按键！所以 Footer 的 bindings 只用于显示提示，不用于实际处理。Footer 的 BINDINGS 优先级低于焦点组件（Input），但如果焦点在不可编辑组件上（如 DirectoryTree），Footer 的 BINDINGS 不会激活（Footer 本身不可聚焦）。

**实际上**：Footer 本身不可聚焦（`can_focus=False`），它的 BINDINGS 只用于显示键提示，不会拦截任何按键。所以这样设置是安全的。

## 验证步骤

1. `python -m goodclean` → 欢迎界面显示
2. 按数字键 `1`-`5` → 选中路径（`>` 标记移动）
3. 按 `T` → 切换扫描模式
4. 按 `C` → 清除缓存
5. 按 `Enter` → 开始扫描，进入主界面
6. 主界面按 `/` → 搜索框获得焦点
7. **在搜索框中输入 `test`** → 能正常输入字符
8. 按 `Esc` → 退出搜索框，清除搜索
9. 按 `d`/`D`/`s`/`r`/`t`/`e`/`f` → 功能正常
10. 退出后重新 `python -m goodclean` → 缓存生效
