"""目录树组件：展示扫描后的目录结构，支持展开/折叠、选中"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ..analyzer import format_size
from ..models import DirInfo


class DirectoryTree(Widget):
    """目录树组件"""

    BINDINGS = [
        ("enter", "toggle_node", "展开/折叠"),
        ("space", "toggle_select", "选中/取消"),
    ]

    selected_path: reactive[str] = reactive("")
    selected_paths: reactive[set[str]] = reactive(set, init=False)

    def __init__(self, root_dir: Optional[DirInfo] = None, **kwargs):
        super().__init__(**kwargs)
        self._root_dir = root_dir
        self._tree: Optional[Tree] = None
        self.selected_paths = set()  # 确保每个实例有自己的 set

    def compose(self):
        self._tree = Tree("扫描中...")
        self._tree.show_root = True
        self._tree.guide_depth = 2
        yield self._tree

    def load_dir(self, dir_info: DirInfo) -> None:
        """加载目录数据到树中"""
        self._root_dir = dir_info
        if self._tree is None:
            return

        self._tree.clear()
        self._tree.root.label = self._make_label(dir_info)
        self._tree.root.data = dir_info.path
        self._tree.root.expand()

        self._populate_tree(self._tree.root, dir_info)

    def _populate_tree(self, parent_node: TreeNode, dir_info: DirInfo) -> None:
        """递归填充树节点"""
        # 按大小排序子目录
        sorted_children = sorted(
            dir_info.children, key=lambda d: d.total_size, reverse=True
        )

        for child in sorted_children:
            label = self._make_label(child)
            icon = self._get_dir_icon(child)
            child_node = parent_node.add(label, data=child.path)

            # 如果有子目录或文件，添加占位节点（懒加载）
            if child.children or child.files:
                child_node.add("加载中...", data=None)

    def _make_label(self, dir_info: DirInfo) -> Text:
        """生成目录标签文本"""
        text = Text()
        name = dir_info.name

        if dir_info.has_permission_error:
            text.append(f"🔒 {name}", style="dim yellow")
        elif dir_info.is_symlink:
            text.append(f"🔗 {name}", style="dim cyan")
        else:
            icon = self._get_dir_icon(dir_info)
            text.append(f"{icon} {name}", style="bold")

        text.append(f"  ({format_size(dir_info.total_size)})", style="dim green")

        if dir_info.file_count > 0:
            text.append(f"  [{dir_info.file_count} 个文件]", style="dim")

        return text

    def _get_dir_icon(self, dir_info: DirInfo) -> str:
        """根据目录类型返回图标"""
        name = dir_info.name.lower()
        if name == "node_modules":
            return "📦"
        elif name in ("__pycache__", ".pytest_cache", ".mypy_cache"):
            return "🐍"
        elif name in ("dist", "build", "out", "target"):
            return "🔨"
        elif name in (".git", ".svn"):
            return "📋"
        elif name in (".idea", ".vs", ".vscode"):
            return "⚙️"
        else:
            return "📁"

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """节点展开时懒加载子节点"""
        node = event.node
        if node.data is None:
            return

        # 检查是否是占位节点
        if len(node.children) == 1 and node.children[0].data is None:
            node.remove_children()
            dir_info = self._find_dir(self._root_dir, node.data)
            if dir_info:
                self._populate_tree(node, dir_info)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """节点选中时更新选中路径"""
        if event.node.data:
            self.selected_path = event.node.data

    def _find_dir(self, dir_info: Optional[DirInfo], path: str) -> Optional[DirInfo]:
        """在目录树中查找指定路径的 DirInfo"""
        if dir_info is None:
            return None
        if dir_info.path == path:
            return dir_info
        for child in dir_info.children:
            result = self._find_dir(child, path)
            if result:
                return result
        return None

    def action_toggle_node(self) -> None:
        """切换节点展开/折叠"""
        if self._tree:
            self._tree.action_toggle()

    def action_toggle_select(self) -> None:
        """切换当前节点的选中状态"""
        if not self._tree:
            return
        
        # 获取当前光标所在的节点
        cursor_node = self._tree.cursor_node
        if cursor_node and cursor_node.data:
            path = cursor_node.data
            current = set(self.selected_paths)
            if path in current:
                current.discard(path)
            else:
                current.add(path)
            self.selected_paths = current
            self.notify(f"已选中: {len(self.selected_paths)} 个项目")
