"""目录树组件：展示扫描后的目录结构，支持展开/折叠、选中"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ..analyzer import format_size
from ..models import DirInfo

# 每层最大显示的子目录节点数，超过时截断并显示提示节点
_MAX_NODES_PER_LEVEL = 500


class SelectableTree(Tree):
    """可选中的 Tree 子类，拦截 Space 键改为选中/取消选中"""

    def __init__(self, *args, on_space=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_space = on_space

    def _on_key(self, event) -> None:
        """拦截 Space 键，改为选中操作"""
        if event.key == "space":
            event.prevent_default()
            event.stop()
            if self._on_space:
                self._on_space()
            return
        # 其他键交给父类处理
        super()._on_key(event)


class DirectoryTree(Widget):
    """目录树组件"""

    BINDINGS = [
        ("enter", "toggle_node", "展开/折叠"),
        ("space", "toggle_select", "选中/取消"),
        ("ctrl+a", "select_all", "全选"),
        ("ctrl+i", "invert_selection", "反选"),
    ]

    selected_path: reactive[str] = reactive("")
    selected_paths: reactive[set[str]] = reactive(set, init=False)

    def __init__(self, root_dir: DirInfo | None = None, **kwargs):
        super().__init__(**kwargs)
        self._root_dir = root_dir
        self._tree: SelectableTree | None = None
        self.selected_paths = set()
        self._sort_mode = "size"

    def compose(self):
        self._tree = SelectableTree(
            "扫描中...",
            on_space=self._do_toggle_select,
        )
        self._tree.show_root = True
        self._tree.guide_depth = 2
        yield self._tree

    def set_sort_mode(self, mode: str) -> None:
        """设置排序模式"""
        if mode in ("size", "count", "name", "mtime"):
            self._sort_mode = mode

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

    def _get_sort_key(self, dir_info: DirInfo):
        """根据当前排序模式获取排序键"""
        if self._sort_mode == "size":
            return dir_info.total_size
        elif self._sort_mode == "count":
            return dir_info.file_count
        elif self._sort_mode == "name":
            return dir_info.name.lower()
        elif self._sort_mode == "mtime":
            return dir_info.modified_time
        return dir_info.total_size

    def _populate_tree(self, parent_node: TreeNode, dir_info: DirInfo) -> None:
        """填充当前节点的直接子目录节点（单层，不递归）"""
        reverse = self._sort_mode != "name"
        sorted_children = sorted(
            dir_info.children, key=self._get_sort_key, reverse=reverse
        )

        # 节点数量限制：防止单层级子目录过多导致 UI 卡顿
        display_children = sorted_children[:_MAX_NODES_PER_LEVEL]
        remaining = len(sorted_children) - _MAX_NODES_PER_LEVEL

        for child in display_children:
            label = self._make_label(child)
            child_node = parent_node.add(label, data=child.path)

            if child.children or child.files:
                child_node.add("加载中...", data=None)

        if remaining > 0:
            parent_node.add(f"... 还有 {remaining} 个目录", data=None)

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
            check = "☑" if dir_info.path in self.selected_paths else "☐"
            text.append(f"{check} {icon} {name}", style="bold")

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

        if len(node.children) == 1 and node.children[0].data is None:
            node.remove_children()
            dir_info = self._find_dir(self._root_dir, node.data)
            if dir_info:
                self._populate_tree(node, dir_info)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """节点选中时更新选中路径"""
        if event.node.data:
            self.selected_path = event.node.data

    def _find_dir(self, dir_info: DirInfo | None, path: str) -> DirInfo | None:
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

    def expand_to_path(self, target_path: str) -> bool:
        """展开目录树到指定路径，并选中该节点"""
        if not self._tree or not self._root_dir:
            return False

        from pathlib import Path

        # 如果目标就是根目录
        if target_path == self._root_dir.path:
            self._tree.select_node(self._tree.root)
            self.selected_path = target_path
            return True

        # 获取相对路径
        try:
            rel = Path(target_path).relative_to(self._root_dir.path)
        except ValueError:
            return False

        current_node = self._tree.root
        current_dir = self._root_dir

        for part in rel.parts:
            # 确保当前节点已展开并填充
            if not current_node.is_expanded:
                current_node.expand()
                self._populate_tree(current_node, current_dir)

            # 找到下一级目录
            next_dir = None
            for child in current_dir.children:
                if child.name == part:
                    next_dir = child
                    break

            if not next_dir:
                return False

            # 在 tree 中找到对应节点
            next_node = None
            for tree_child in current_node.children:
                if tree_child.data == next_dir.path:
                    next_node = tree_child
                    break

            if not next_node:
                return False

            current_node = next_node
            current_dir = next_dir

        # 选中最终节点
        if current_node:
            self._tree.select_node(current_node)
            self.selected_path = current_node.data
            return True
        return False

    def action_toggle_node(self) -> None:
        """切换节点展开/折叠"""
        if self._tree:
            self._tree.action_toggle_node()

    def action_toggle_select(self) -> None:
        """切换当前节点的选中状态（通过 BINDINGS）"""
        self._do_toggle_select()

    def _do_toggle_select(self) -> None:
        """实际的选中切换逻辑"""
        if not self._tree:
            return

        cursor_node = self._tree.cursor_node
        if cursor_node and cursor_node.data:
            path = cursor_node.data
            current = set(self.selected_paths)
            if path in current:
                current.discard(path)
                action = "取消选中"
            else:
                current.add(path)
                action = "已选中"
            self.selected_paths = current
            self.notify(f"{action} | 当前共选中 {len(self.selected_paths)} 个项目", timeout=2)
            if self._tree:
                self._tree.refresh()

    def _collect_all_paths(self, dir_info: DirInfo | None) -> set[str]:
        """递归收集所有目录路径"""
        paths: set[str] = set()
        if dir_info is None:
            return paths
        paths.add(dir_info.path)
        for child in dir_info.children:
            paths.update(self._collect_all_paths(child))
        return paths

    def action_select_all(self) -> None:
        """全选所有目录"""
        if not self._root_dir:
            return
        all_paths = self._collect_all_paths(self._root_dir)
        self.selected_paths = all_paths
        self.notify(f"已全选 {len(all_paths)} 个项目", timeout=2)
        if self._tree:
            self._tree.refresh()

    def action_invert_selection(self) -> None:
        """反选：已选的取消，未选的选中"""
        if not self._root_dir:
            return
        all_paths = self._collect_all_paths(self._root_dir)
        current = set(self.selected_paths)
        inverted = all_paths - current
        self.selected_paths = inverted
        self.notify(f"反选完成 | 当前共选中 {len(inverted)} 个项目", timeout=2)
        if self._tree:
            self._tree.refresh()
