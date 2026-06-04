# GoodClean 全面 Bug 修复计划

## 问题汇总

经过完整代码审查，发现以下 Bug：

### Bug 1: `SelectableTree.on_key` 调用 `super().on_key(event)` 但 Tree 没有 `on_key` 方法
- **文件**: `goodclean/widgets/directory_tree.py` 第 34-42 行
- **原因**: Textual 的 Widget 类没有公开的 `on_key` 方法，内部使用 `_on_key`
- **修复**: 不调用 `super().on_key(event)`，非 Space 键直接 return 不做处理，让 Textual 的事件系统自动传播

### Bug 2: `_make_help_text` 返回的字符串包含未转义的 Rich markup 方括号
- **文件**: `goodclean/app.py` 第 535-540 行
- **原因**: Static widget 使用 Rich 渲染，`[d]` `[D]` `[s]` `[t]` `[e]` `[f]` `[r]` `[q]` `[Enter]` `[Space]` 都会被解析为 Rich 样式标签
- **修复**: 所有方括号都需要转义为 `[[` 和 `]]`

### Bug 3: `_do_toggle_select` 中多次 notify 调用导致通知闪烁
- **文件**: `goodclean/widgets/directory_tree.py` 第 173-192 行
- **修复**: 合并为一次 notify

### Bug 4: 删除后 `_show_clean_result` 清除的是 App 的 `_selected_paths` 而不是 Tree 的 `selected_paths`
- **文件**: `goodclean/app.py` 第 358-361 行
- **修复**: 删除成功后同时清除 Tree 的 `selected_paths`

### Bug 5: Rich markup 中 `[[/]]` 和 `[[]?]]` 转义不完整
- **文件**: `goodclean/app.py` 第 538-539 行
- **原因**: 之前的修复只转义了 `/` 和 `?`，但 `[d]` `[D]` `[s]` 等也会被解析
- **修复**: 使用纯文本方式，避免在 Static widget 中使用 Rich markup

## 修复方案

### 文件 1: `goodclean/widgets/directory_tree.py`

**改动**:
1. `SelectableTree.on_key`: 不调用 `super().on_key(event)`，非 Space 键直接 return
2. `_do_toggle_select`: 合并多次 notify 为一次
3. 删除多余的 `import on`

### 文件 2: `goodclean/app.py`

**改动**:
1. `_make_help_text`: 使用纯文本，转义所有方括号
2. `_show_clean_result`: 删除后清除 Tree 的 selected_paths
3. `action_show_help`: 确保 notify 文本不含 Rich markup

## 验证步骤

1. `python -c "from goodclean.app import GoodCleanApp; print('OK')"` - 导入测试
2. `python -m goodclean .` - 启动测试
3. 按 Space 选中目录 → 应显示 ☑ 标记和通知
4. 按 d 删除 → 弹出确认框 → 确认后删除成功
5. 按 ? 帮助 → 正常显示帮助文本
6. 按 / 搜索 → 聚焦搜索框
7. 按 e 导出 → 生成报告文件
8. 按 f 查重 → 显示重复文件
9. 按 q 退出
