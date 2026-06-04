# 🧹 GoodClean

A terminal-based disk cleanup tool built with [Textual](https://github.com/Textualize/textual) — scan, analyze, and safely reclaim storage space from your disks, all within a beautiful TUI.

## ✨ Features

- **⚡ Async Parallel Scanning** — ThreadPoolExecutor + asyncio for blazing-fast directory traversal
- **🔍 Smart Junk Detection** — Extension-based + magic bytes identification with 41 file signatures
- **📊 Directory Size Ranking** — Visual bar chart showing top space-consuming directories
- **📦 Large File Finder** — Configurable threshold (default 100 MB) to surface the biggest files
- **🔁 Duplicate File Detection** — MD5 hash-based deduplication with two-phase optimization
- **🎨 File Type Analysis** — 16 logical file type categories with colorful visualization
- **💡 Cleanup Suggestions** — Smart risk grading (safe / cautious) with one-click safe cleanup
- **🗑️ Multiple Cleanup Modes** — Send to trash or permanent delete
- **📄 Report Export** — Export to HTML, JSON, or CSV formats
- **💾 Cache System** — 24-hour TTL with incremental scanning

## 🚀 Getting Started

### Prerequisites

- Python 3.10+

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

# Or scan a specific directory directly
goodclean D:\

# Or run as a module
python -m goodclean
```

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

## ⌨️ Keyboard Shortcuts

| Key | Action |
| --- | --- |
| `r` | Rescan directory |
| `d` | Delete selected (move to trash) |
| `D` | Permanently delete selected (Shift+D) |
| `e` | Export report |
| `t` | Show file type distribution |
| `c` | Show cleanup suggestions |
| `x` | One-click safe cleanup |
| `s` | Toggle sort (size / modification time) |
| `Tab` | Switch between panels |
| `Enter` | Expand / collapse directory |
| `q` | Quit |

## 🏗️ Architecture

```
goodclean/
├── __main__.py              # Entry point & CLI argument parsing
├── app.py                   # Main TUI application (Textual App)
├── scanner.py               # Async directory scanner
├── analyzer.py              # Analysis engine (size calculation, stats)
├── cache.py                 # JSON-based caching with TTL
├── cleaner.py               # Trash / permanent delete operations
├── duplicate_finder.py      # MD5-based duplicate detection
├── exporter.py              # Report export (HTML / JSON / CSV)
├── file_type_identifier.py  # Magic bytes file type recognition
├── suggestion.py            # Cleanup suggestion & risk grading
├── models.py                # Data models (DirInfo, ScanResult, etc.)
├── constants.py             # Thresholds, file signatures, junk patterns
├── screens/                 # Textual screen definitions
└── widgets/                 # Custom TUI widgets
    ├── confirm_dialog.py    # Confirmation dialog
    ├── directory_tree.py    # Directory tree view
    ├── file_info.py         # File info panel
    ├── search_bar.py        # Search / filter bar
    └── size_bar.py          # Visual size bar
```

## 🛠️ Development

### Setup

```bash
git clone https://github.com/yourname/GoodClean.git
cd GoodClean
python -m venv .venv
.venv\Scripts\activate      # Windows
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
- `widgets/` contains all custom Textual widgets composing the TUI

## 📄 License

This project is licensed under the [MIT License](LICENSE).
