# 🧹 GoodClean

基于 [Textual](https://github.com/Textualize/textual) 开发的终端磁盘清理工具 —— 在美观的 TUI 界面中扫描、分析并安全回收磁盘空间。

[English Documentation](README.md)

---

## ✨ 功能特性

- **⚡ 异步并行扫描** —— ThreadPoolExecutor + asyncio，目录遍历速度快
- **🔍 智能垃圾识别** —— 基于扩展名 + 文件头魔数（magic bytes）识别，内置 40+ 文件签名
- **📊 目录大小排行** —— 可视化条形图展示最占空间的目录
- **📦 大文件发现** —— 可配置阈值（默认 100 MB），快速找出占用空间的大文件
- **🔁 重复文件检测** —— 三层哈希策略（大小分组 → 头尾预筛 → 全量哈希确认），避免碰撞误删
- **🎨 文件类型分析** —— 16 种逻辑文件类型分类，彩色可视化展示
- **🔎 搜索与过滤** —— 实时关键词搜索，支持按类型、大小、修改时间过滤
- **🖱️ 鼠标支持** —— 点击右侧面板中的任意条目，左侧目录树自动定位到该位置
- **💡 清理建议** —— 智能风险分级（安全 / 谨慎），支持一键安全清理
- **🗑️ 多种清理模式** —— 支持移到回收站或永久删除，带进度可视化
- **📄 报告导出** —— 支持导出 HTML、JSON、CSV 格式
- **💾 缓存系统** —— 24 小时 TTL，支持增量扫描
- **⚙️ 配置持久化** —— 自动保存上次扫描路径、缓存偏好、排序方式

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Windows、macOS 或 Linux

> **Windows 用户注意：** 建议以管理员身份运行，避免扫描时出现权限错误。

### 安装

```bash
git clone https://github.com/yourname/GoodClean.git
cd GoodClean
pip install -e .
```

开发环境：

```bash
pip install -e ".[dev]"
```

### 快速启动

```bash
# 启动交互式 TUI
goodclean

# 直接扫描指定目录
goodclean D:\

# 或以模块方式运行
python -m goodclean
```

---

## 🖥️ 命令行用法

```
goodclean [PATH] [OPTIONS]
```

| 选项 | 说明 |
| --- | --- |
| `PATH` | 要扫描的目录（可选，省略则显示交互菜单） |
| `--no-cache` | 强制全新扫描，忽略缓存 |
| `--cache-info` | 显示缓存信息并退出 |
| `--export FILE` | 导出报告（`.html` / `.json` / `.csv`） |
| `--version` | 显示版本并退出 |

示例：

```bash
# 不使用缓存扫描
goodclean D:\ --no-cache

# 导出 HTML 报告
goodclean C:\Users --export report.html

# 查看缓存状态
goodclean --cache-info
```

---

## ⌨️ 快捷键

### 导航

| 按键 | 功能 |
| --- | --- |
| `↑` / `↓` | 在目录树中移动选中项 |
| `Enter` | 展开 / 折叠目录 |
| `Tab` | 切换面板焦点 |
| `q` | 返回欢迎界面 / 退出应用 |

### 排序与查看

| 按键 | 功能 |
| --- | --- |
| `s` | 切换排序模式（大小 → 数量 → 名称 → 修改时间） |
| `t` | 显示文件类型分布 |
| `e` | 导出报告 |
| `f` | 查找重复文件 |
| `c` | 显示清理建议 |
| `x` | 一键安全清理 |

### 搜索与过滤

| 按键 | 功能 |
| --- | --- |
| `/` | 聚焦搜索栏 |
| `Esc` | 清除搜索和过滤条件 |
| `j` | 在目录树中跳转到下一个匹配的文件 |

### 选择与清理

| 按键 | 功能 |
| --- | --- |
| `Space` | 选中 / 取消选中目录 |
| `Ctrl+a` | 全选所有可见目录 |
| `Ctrl+i` | 反选 |
| `d` | 将选中项移到回收站 |
| `D` | 永久删除选中项 |
| `a` | 删除当前搜索/过滤匹配的所有文件 |
| `r` | 重新扫描目录 |
| `?` | 显示帮助 |

### 鼠标

- **点击** 右侧面板中的任意条目，左侧目录树自动展开并定位到对应位置。

---

## 📸 使用场景

### 场景一：查找并删除旧日志文件

1. 启动 `goodclean`，扫描项目目录。
2. 按 `/` 聚焦搜索栏，输入 `log`。
3. （可选）使用 **时间** 过滤器，只显示 1 年以上未修改的文件。
4. 按 `a` 一键删除所有匹配的 `.log` 文件。

### 场景二：清理 Python 缓存

1. 扫描 Python 项目。
2. 使用 **类型** 过滤器选择 `.pyc`（Python 编译文件）。
3. 匹配的 `__pycache__` 文件会标有 ♻（可安全清理）。
4. 按 `a` 安全移除所有缓存文件。

### 场景三：定位大视频文件

1. 扫描用户目录。
2. 使用 **大小** 过滤器，只显示大于 100 MB 的文件。
3. 使用 **类型** 过滤器选择视频文件。
4. 点击右侧面板中的任意文件 —— 左侧目录树自动展开显示其所在位置。

---

## 🏗️ 项目架构

```
goodclean/
├── __main__.py              # 入口与命令行参数解析
├── app.py                   # TUI 协调器（屏幕路由）
├── scanner.py               # 异步目录扫描器
├── analyzer.py              # 分析引擎（大小计算、统计）
├── cache.py                 # 基于 JSON 的缓存（TTL）
├── cleaner.py               # 回收站 / 永久删除操作
├── duplicate_finder.py      # 基于 MD5 的重复文件检测
├── exporter.py              # 报告导出（HTML / JSON / CSV）
├── file_type_identifier.py  # 基于魔数的文件类型识别
├── suggestion.py            # 清理建议与风险分级
├── config.py                # 跨平台配置持久化
├── models.py                # 数据模型（DirInfo、ScanResult 等）
├── constants.py             # 阈值、文件签名、垃圾文件模式
├── screens/
│   ├── welcome_screen.py    # 欢迎界面（路径选择、缓存开关）
│   └── main_screen.py       # 主扫描视图（树、搜索、清理操作）
└── widgets/                 # 自定义 TUI 组件
    ├── confirm_dialog.py    # 确认对话框（带进度）
    ├── directory_tree.py    # 目录树（支持键盘/鼠标）
    ├── file_info.py         # 文件 / 目录信息面板
    ├── search_bar.py        # 搜索与过滤栏
    └── size_bar.py          # 可视化大小条（支持点击）
```

---

## 🛠️ 开发

### 环境搭建

```bash
git clone https://github.com/yourname/GoodClean.git
cd GoodClean
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
```

### 项目结构说明

- `scanner.py` —— 线程池并行的文件系统遍历
- `analyzer.py` —— 将原始扫描结果处理为结构化统计数据
- `file_type_identifier.py` —— 读取文件头魔数识别文件类型
- `duplicate_finder.py` —— 两阶段 MD5 哈希去重（先按大小筛选，再算完整哈希）
- `cache.py` —— 将扫描结果持久化为 JSON，24 小时过期
- `suggestion.py` —— 按风险级别分类，支持安全批量清理
- `config.py` —— 跨会话保存用户偏好设置
- `widgets/` —— 所有自定义 Textual 组件，构成 TUI 界面

---

## ❓ 常见问题

**Q: 扫描时为什么会出现"权限被拒绝"的错误？**

A: 在 Windows 上，系统目录和其他用户的文件夹需要管理员权限才能访问。GoodClean 会跳过这些目录，并在欢迎界面上提示如何以管理员身份运行。

**Q: GoodClean 会在未经确认的情况下修改我的文件吗？**

A: 不会。所有删除操作都需要显式确认。安全清理（`x`）只针对标记为低风险的文件（如 `.tmp`、`.pyc`、`.log`）。

**Q: 删除后的文件可以恢复吗？**

A: 如果使用 `d`（回收站），文件会被移到系统回收站，可以恢复。如果使用 `D`（永久删除），文件将立即被删除，无法恢复。

**Q: 扫描缓存存储在哪里？**

A: 存储在系统标准的应用数据目录中。使用 `goodclean --cache-info` 可查看具体路径。

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源许可。
