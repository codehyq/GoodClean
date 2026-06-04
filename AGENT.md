# GoodClean 项目开发规则

## 项目简介

GoodClean 是一个基于 Python + Textual 的终端磁盘清理工具。

## 运行方式

pip install -e .
goodclean
python -m goodclean
goodclean D:\
goodclean --no-cache
goodclean --cache-info
goodclean D:\ --export report.html

## 技术架构

goodclean/__main__.py   - 入口点
goodclean/app.py        - 主TUI应用(~750行，含欢迎界面+主界面)
goodclean/scanner.py    - 异步目录扫描器
goodclean/analyzer.py   - 分析引擎
goodclean/cache.py      - JSON缓存
goodclean/cleaner.py    - 清理器
goodclean/duplicate_finder.py - 重复文件检测
goodclean/exporter.py   - 报告导出
goodclean/models.py     - 数据模型
goodclean/constants.py  - 常量
goodclean/widgets/      - UI组件

## 关键技术决策

### 键盘处理（踩过坑，务必遵守！）
- 不要使用 App BINDINGS 绑定单字符键会让 Input 收不到字符
- Textual BINDINGS 在 on_key 之前拦截
- 当前方案: check_action 在欢迎界面返回 False 禁用绑定;主界面保留绑定
- 欢迎界面完全用原生组件(RadioSet, Switch, Button)
- 主界面 SearchBar Input 可正常输入

### 缓存策略
- 标准模式: 读缓存 命中直接用 未命中扫描后写
- 强制刷新: 不读缓存 扫描后写
- 手动重扫(r): 强制刷新
- 删除后: 自动强制重扫
- 过期(>24h): 视为未命中

### 扫描模式
- ThreadPoolExecutor(max_workers=8) 并行扫描
- asyncio.gather + Semaphore 限制并发

## Git 工作流

- master: 主分支  dev: 开发分支
- 禁止自动合并到 master
- 提交规范: feat:/fix:/chore:/docs:/refactor:

## 已知注意事项

- textual>=0.80
- PowerShell heredoc 不可用 用 git commit -m
- index.lock 错误需手动删除

## 代码质量规则
- 修复Bug时全面检查相关代码
- 耗时操作必须提供进度反馈
- 不引入不必要的依赖
