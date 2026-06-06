# 🧹 GoodClean

A terminal-based disk cleanup tool built with [Textual](https://github.com/Textualize/textual) — scan, analyze, and safely reclaim storage space from your disks, all within a beautiful TUI.

[中文文档](README.zh-CN.md)

---

## ✨ Features

- **⚡ Async Parallel Scanning** — ThreadPoolExecutor + asyncio for blazing-fast directory traversal
- **🔍 Smart Junk Detection** — Extension-based + magic bytes identification with 40+ file signatures
- **📊 Directory Size Ranking** — Visual bar chart showing top space-consuming directories
- **📦 Large File Finder** — Configurable threshold (default 100 MB) to surface the biggest files
- **🔁 Duplicate File Detection** — MD5 hash-based deduplication with two-phase optimization
- **🎨 File Type Analysis** — 16 logical file type categories with colorful visualization
- **🔎 Search & Filter** — Real-time keyword search with type, size, and modification-time filters
- **🖱️ Mouse Support** — Click any item in the ranking panel to jump to its location in the directory tree
- **💡 Cleanup Suggestions** — Smart risk grading (safe / cautious) with one-click safe cleanup
- **🗑️ Multiple Cleanup Modes** — Send to trash or permanent delete, with progress visualization
- **📄 Report Export** — Export to HTML, JSON, or CSV formats
- **💾 Cache System** — 24-hour TTL with incremental scanning
- **⚙️ Config Persistence** — Automatically saves last scan path, cache preference, and sort mode

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Windows, macOS, or Linux

> **Note for Windows users:** Run with administrator privileges to avoid permission errors during scanning.

### Installation

```bash
git clone https://github.com/yourname/GoodClean.git
cd GoodClean
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

### Quick Start

```bash
# Launch interactive TUI
goodclean

# Scan a specific directory directly
goodclean D:\

# Or run as a module
python -m goodclean
```

---

## 🖥️ Command Line Usage

```
goodclean [PATH] [OPTIONS]
```

| Option | Description |
| --- | --- |
| `PATH` | Directory to scan (optional, shows interactive menu if omitted) |
| `--no-cache` | Force a fresh scan, bypassing the cache |
| `--cache-info` | Display cache information and exit |
| `--export FILE` | Export report to file (`.html` / `.json` / `.csv`) |
| `--version` | Show version and exit |

Examples:

```bash
# Scan with no cache
goodclean D:\ --no-cache

# Export HTML report
goodclean C:\Users --export report.html

# Check what's cached
goodclean --cache-info
```

---

## ⌨️ Keyboard Shortcuts

### Navigation

| Key | Action |
| --- | --- |
| `↑` / `↓` | Move selection in directory tree |
| `Enter` | Expand / collapse directory |
| `Tab` | Switch focus between panels |
| `q` | Return to welcome screen / quit app |

### Sorting & Viewing

| Key | Action |
| --- | --- |
| `s` | Toggle sort mode (size → count → name → modification time) |
| `t` | Show file type distribution |
| `e` | Export report |
| `f` | Find duplicate files |
| `c` | Show cleanup suggestions |
| `x` | One-click safe cleanup |

### Search & Filter

| Key | Action |
| --- | --- |
| `/` | Focus search bar |
| `Esc` | Clear search & filters |
| `j` | Jump to next matched file in directory tree |

### Selection & Cleanup

| Key | Action |
| --- | --- |
| `Space` | Select / deselect directory |
| `Ctrl+a` | Select all visible directories |
| `Ctrl+i` | Invert selection |
| `d` | Move selected to trash |
| `D` | Permanently delete selected |
| `a` | Delete all files matching current search/filter |
| `r` | Rescan directory |
| `?` | Show help |

### Mouse

- **Click** any item in the right panel to jump to its location in the directory tree.

---

## 📸 Usage Scenarios

### Scenario 1: Find and delete old log files

1. Launch `goodclean` and scan your project directory.
2. Press `/` to focus the search bar, type `log`.
3. (Optional) Use the **Time** filter to show only files modified over 1 year ago.
4. Press `a` to delete all matched `.log` files at once.

### Scenario 2: Clean up Python cache

1. Scan your Python project.
2. Use the **Type** filter to select `.pyc` (Python compiled).
3. Matched `__pycache__` files are marked with ♻ (safe to clean).
4. Press `a` to safely remove all of them.

### Scenario 3: Locate large video files

1. Scan your home directory.
2. Use the **Size** filter to show files larger than 100 MB.
3. Use the **Type** filter to select video files.
4. Click any file in the ranking panel — the directory tree auto-expands to show its location.

---

## 🏗️ Architecture

```
goodclean/
├── __main__.py              # Entry point & CLI argument parsing
├── app.py                   # TUI coordinator (screen routing)
├── scanner.py               # Async directory scanner
├── analyzer.py              # Analysis engine (size calculation, stats)
├── cache.py                 # JSON-based caching with TTL
├── cleaner.py               # Trash / permanent delete operations
├── duplicate_finder.py      # MD5-based duplicate detection
├── exporter.py              # Report export (HTML / JSON / CSV)
├── file_type_identifier.py  # Magic bytes file type recognition
├── suggestion.py            # Cleanup suggestion & risk grading
├── config.py                # Cross-platform config persistence
├── models.py                # Data models (DirInfo, ScanResult, etc.)
├── constants.py             # Thresholds, file signatures, junk patterns
├── screens/
│   ├── welcome_screen.py    # Welcome screen (path selection, cache toggle)
│   └── main_screen.py       # Main scan view (tree, search, cleanup actions)
└── widgets/                 # Custom TUI widgets
    ├── confirm_dialog.py    # Confirmation dialog with progress
    ├── directory_tree.py    # Directory tree with keyboard/mouse support
    ├── file_info.py         # File / directory info panel
    ├── search_bar.py        # Search & filter bar
    └── size_bar.py          # Visual size bar with click support
```

---

## 🛠️ Development

### Setup

```bash
git clone https://github.com/yourname/GoodClean.git
cd GoodClean
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Project Structure

- `scanner.py` handles all file system traversal with thread-pool parallelism
- `analyzer.py` processes raw scan results into structured statistics
- `file_type_identifier.py` reads file headers to identify types by magic bytes
- `duplicate_finder.py` groups files by MD5 hash in two passes (size filter → full hash)
- `cache.py` persists scan results as JSON with a 24-hour expiration window
- `suggestion.py` categorizes findings by risk level for safe batch cleanup
- `config.py` saves user preferences across sessions
- `widgets/` contains all custom Textual widgets composing the TUI

---

## ❓ FAQ

**Q: Why do I see "permission denied" errors during scanning?**

A: On Windows, system directories and other users' folders require administrator privileges. GoodClean will skip these directories and show a tip on the welcome screen explaining how to run as administrator.

**Q: Does GoodClean modify my files without asking?**

A: No. All delete operations require explicit confirmation. Safe cleanup (`x`) only targets files marked as low-risk (like `.tmp`, `.pyc`, `.log`).

**Q: Can I recover files after deletion?**

A: If you use `d` (trash), files are moved to the system trash and can be recovered. If you use `D` (permanent delete), they are gone immediately.

**Q: Where is scan cache stored?**

A: In your system's standard app-data directory. Use `goodclean --cache-info` to see the exact path.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
