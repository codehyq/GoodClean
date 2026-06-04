# GoodClean 项目状态

## 最后更新：2026-06-04

## 当前版本：v1.0.0

## 已完成功能

### 核心功能
- [x] 扫描指定目录（异步并行，ThreadPoolExecutor + asyncio）
- [x] 分析磁盘占用（Top 50 目录、Top 100 大文件、垃圾文件标记）
- [x] 清理文件（回收站 / 永久删除，支持批量）
- [x] 搜索/过滤（按名称、类型、大小）
- [x] 重复文件检测（MD5 哈希）
- [x] 导出报告（HTML/JSON/CSV）
- [x] 进度反馈（扫描、删除、导出均有进度提示）

### 交互界面
- [x] 欢迎界面（RadioSet 选择路径、Switch 缓存模式、Button 确认）
- [x] 自定义路径输入（RadioSet 最后一项）
- [x] 主界面（目录树 + 大小排行 + 文件详情）
- [x] 缓存状态可视化（命中/过期/无缓存/强制刷新）
- [x] 命令行参数（--no-cache、--cache-info、--export）

### 缓存系统
- [x] JSON 缓存（~/.goodclean/cache/）
- [x] 标准模式自动读写缓存
- [x] 强制刷新模式跳过缓存
- [x] 删除后自动强制重扫
- [x] 24 小时过期策略

### 工程化
- [x] Git 分支管理（dev/master）
- [x] pyproject.toml 配置（pip install -e . 可用）
- [x] AGENT.md 开发规则文档

## 当前分支：master

### 最近提交
- 661bbd7 docs: 更新 AGENT.md
- 558bbca feat: 缓存状态可视化 + 自定义路径输入
- 1177f1f merge: dev -> master (欢迎界面+缓存集成)
- 5b7ddae feat: 交互式欢迎界面 + 缓存集成 + pyproject 修复

## 已知问题

### 已修复
- Rich markup 解析错误（[/] 被解析为关闭标签）
- SelectableTree.on_key 不存在（改用 _on_key）
- Space 键选中被 Tree 拦截
- 搜索栏不可见（dock: top 解决）
- 永久删除只读文件失败（chmod 重试）
- 缓存导致重新扫描看不到新文件
- .git/index.lock 锁文件问题

### 待解决
- 无远程仓库（需要配置 GitHub/Gitee 才能 push）
- 没有测试文件（可选：添加 pytest 测试）

## 技术栈
- Python 3.12
- Textual >= 0.80（TUI 框架）
- Rich（终端格式化）
- send2trash（安全删除）
- pathlib（跨平台路径）

## 文件结构
```
goodclean/
├── __main__.py          # 入口点
├── app.py               # 主应用（~750行）
├── scanner.py           # 扫描器
├── analyzer.py          # 分析引擎
├── cache.py             # 缓存
├── cleaner.py           # 清理器
├── duplicate_finder.py  # 重复检测
├── exporter.py          # 导出
├── models.py            # 数据模型
├── constants.py         # 常量
└── widgets/             # UI 组件
```

## 关键决策记录

### 2026-06-04: 欢迎界面方案
- 初始方案：自定义 on_key + Static 菜单项 → 失败（Input 无法输入）
- 中间方案：check_action 禁用 BINDINGS → 失败（仍然拦截）
- 最终方案：RadioSet + Switch + Button 原生组件 → 成功
- 教训：不要用 App BINDINGS 绑定单字符键，Input 会收不到字符

### 2026-06-04: 缓存策略
- 最初：TUI 模式完全不用缓存（导致每次都全量扫描）
- 最终：标准模式用缓存 + 强制刷新可选 + 删除后自动重扫
