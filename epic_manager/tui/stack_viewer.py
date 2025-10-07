"""
Stack Viewer Widget

Specialized Textual widget for visualizing Graphite stacks.
Provides interactive tree view of branch relationships and status.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from textual.widget import Widget
from textual.widgets import Tree
from textual.reactive import reactive
from rich.text import Text
from rich.console import Console

console = Console()


@dataclass
class StackBranchInfo:
    """Information about a branch in the stack."""
    name: str
    issue_number: int
    status: str  # 'pending', 'in_progress', 'review', 'merged', 'failed'
    pr_number: Optional[int] = None
    parent: Optional[str] = None
    children: List[str] = None
    commits_ahead: int = 0
    commits_behind: int = 0
    last_updated: Optional[str] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class StackViewer(Widget):
    """Widget for displaying and interacting with Graphite stack structure."""

    # Reactive attributes for dynamic updates
    epic_number: reactive[Optional[int]] = reactive(None)
    selected_branch: reactive[Optional[str]] = reactive(None)

    def __init__(
        self,
        epic_number: Optional[int] = None,
        *args,
        **kwargs
    ) -> None:
        """Initialize stack viewer widget.

        Args:
            epic_number: Epic number to display initially
        """
        super().__init__(*args, **kwargs)
        self.epic_number = epic_number

        # Stack data
        self.stack_branches: Dict[str, StackBranchInfo] = {}
        self.root_branch: str = "main"

        # UI components
        self.tree_widget: Optional[Tree] = None

        # Status icons and colors
        self.status_icons = {
            'pending': '⏳',
            'in_progress': '📝',
            'review': '🔄',
            'merged': '✅',
            'failed': '❌',
            'conflict': '⚠️'
        }

        self.status_colors = {
            'pending': 'yellow',
            'in_progress': 'blue',
            'review': 'cyan',
            'merged': 'green',
            'failed': 'red',
            'conflict': 'magenta'
        }

    def compose(self):
        """Compose the stack viewer widget."""
        # TODO: Implement widget composition
        # TODO: Create tree widget for stack visualization
        # TODO: Set up interactive handlers

        self.tree_widget = Tree(self.root_branch)
        self.tree_widget.root.expand()

        yield self.tree_widget

    def update_stack_data(self, stack_data: Dict[str, Any]) -> None:
        """Update the stack with new data.

        Args:
            stack_data: Dictionary containing stack structure and branch information
        """
        # TODO: Implement stack data processing
        # TODO: Parse stack_data into StackBranchInfo objects
        # TODO: Build branch hierarchy
        # TODO: Refresh tree display

        console.print(f"[blue]Updating stack data for epic {self.epic_number}[/blue]")

        # Extract branches from stack_data
        branches = stack_data.get('branches', {})

        self.stack_branches.clear()

        for branch_name, branch_info in branches.items():
            self.stack_branches[branch_name] = StackBranchInfo(
                name=branch_name,
                issue_number=branch_info.get('issue_number', 0),
                status=branch_info.get('status', 'pending'),
                pr_number=branch_info.get('pr_number'),
                parent=branch_info.get('parent'),
                children=branch_info.get('children', []),
                commits_ahead=branch_info.get('commits_ahead', 0),
                commits_behind=branch_info.get('commits_behind', 0),
                last_updated=branch_info.get('last_updated')
            )

        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        """Rebuild the tree widget with current stack data."""
        if not self.tree_widget:
            return

        # TODO: Implement tree rebuilding
        # TODO: Clear existing tree structure
        # TODO: Build new tree from stack_branches
        # TODO: Apply styling and status indicators

        console.print("[blue]Rebuilding stack tree[/blue]")

        # Clear tree and rebuild
        self.tree_widget.clear()

        if not self.stack_branches:
            return

        # Find root branches (those with no parent or parent is main)
        root_branches = [
            branch for branch in self.stack_branches.values()
            if branch.parent is None or branch.parent == self.root_branch
        ]

        # Build tree recursively
        for branch in root_branches:
            self._add_branch_to_tree(branch, self.tree_widget.root)

    def _add_branch_to_tree(
        self,
        branch: StackBranchInfo,
        parent_node
    ) -> None:
        """Recursively add branch and its children to the tree.

        Args:
            branch: Branch information to add
            parent_node: Parent tree node
        """
        # TODO: Implement recursive branch addition
        # TODO: Create styled tree node with status icons
        # TODO: Add commit information and PR links
        # TODO: Recursively add child branches

        # Create branch display text
        branch_text = self._format_branch_display(branch)

        # Add to tree
        branch_node = parent_node.add(branch_text, data=branch.name)

        # Add child branches recursively
        child_branches = [
            self.stack_branches[child_name]
            for child_name in branch.children
            if child_name in self.stack_branches
        ]

        for child_branch in child_branches:
            self._add_branch_to_tree(child_branch, branch_node)

    def _format_branch_display(self, branch: StackBranchInfo) -> Text:
        """Format branch information for tree display.

        Args:
            branch: Branch information

        Returns:
            Formatted Rich Text object
        """
        # TODO: Implement comprehensive branch formatting
        # TODO: Add status icons and colors
        # TODO: Include commit counts and PR information
        # TODO: Add timestamps for last activity

        # Get status icon and color
        icon = self.status_icons.get(branch.status, '❓')
        color = self.status_colors.get(branch.status, 'white')

        # Build display text
        text = Text()
        text.append(f"{icon} ", style=color)
        text.append(branch.name, style="bold")

        if branch.issue_number > 0:
            text.append(f" (#{branch.issue_number})", style="dim")

        # Add PR information if available
        if branch.pr_number:
            text.append(f" PR#{branch.pr_number}", style="cyan")

        # Add commit status if available
        if branch.commits_ahead > 0:
            text.append(f" +{branch.commits_ahead}", style="green")
        if branch.commits_behind > 0:
            text.append(f" -{branch.commits_behind}", style="red")

        return text

    def get_branch_at_cursor(self) -> Optional[StackBranchInfo]:
        """Get the branch information for the currently selected tree node.

        Returns:
            StackBranchInfo for selected branch, None if no selection
        """
        # TODO: Implement cursor position handling
        # TODO: Get selected tree node
        # TODO: Return corresponding branch information

        if not self.tree_widget or not self.tree_widget.cursor_node:
            return None

        branch_name = self.tree_widget.cursor_node.data
        return self.stack_branches.get(branch_name)

    def highlight_branch(self, branch_name: str) -> None:
        """Highlight a specific branch in the tree.

        Args:
            branch_name: Name of the branch to highlight
        """
        # TODO: Implement branch highlighting
        # TODO: Find tree node for branch
        # TODO: Apply highlighting style
        # TODO: Scroll to make branch visible

        self.selected_branch = branch_name
        console.print(f"[blue]Highlighted branch: {branch_name}[/blue]")

    def show_branch_details(self, branch_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific branch.

        Args:
            branch_name: Name of the branch

        Returns:
            Dictionary with detailed branch information
        """
        # TODO: Implement detailed branch information gathering
        # TODO: Include git status, PR details, dependencies
        # TODO: Add commit history and file changes

        branch = self.stack_branches.get(branch_name)
        if not branch:
            return {}

        details = {
            'name': branch.name,
            'issue_number': branch.issue_number,
            'status': branch.status,
            'pr_number': branch.pr_number,
            'parent': branch.parent,
            'children': branch.children,
            'commits_ahead': branch.commits_ahead,
            'commits_behind': branch.commits_behind,
            'last_updated': branch.last_updated
        }

        return details

    def get_branch_path(self, branch_name: str) -> List[str]:
        """Get the path from root to the specified branch.

        Args:
            branch_name: Name of the target branch

        Returns:
            List of branch names from root to target
        """
        # TODO: Implement branch path calculation
        # TODO: Follow parent relationships to root
        # TODO: Return ordered list of branch names

        path = []
        current_branch = self.stack_branches.get(branch_name)

        while current_branch:
            path.insert(0, current_branch.name)
            parent_name = current_branch.parent

            if parent_name == self.root_branch or parent_name is None:
                break

            current_branch = self.stack_branches.get(parent_name)

        return path

    def get_dependent_branches(self, branch_name: str) -> List[str]:
        """Get all branches that depend on the specified branch.

        Args:
            branch_name: Name of the branch

        Returns:
            List of branch names that depend on the specified branch
        """
        # TODO: Implement dependency resolution
        # TODO: Find all descendant branches
        # TODO: Return flattened list of dependents

        branch = self.stack_branches.get(branch_name)
        if not branch:
            return []

        dependents = []
        self._collect_dependents(branch, dependents)

        return dependents

    def _collect_dependents(self, branch: StackBranchInfo, dependents: List[str]) -> None:
        """Recursively collect dependent branches.

        Args:
            branch: Branch to collect dependents for
            dependents: List to accumulate dependents
        """
        for child_name in branch.children:
            if child_name not in dependents:
                dependents.append(child_name)
                child_branch = self.stack_branches.get(child_name)
                if child_branch:
                    self._collect_dependents(child_branch, dependents)

    def refresh_branch_status(self, branch_name: str, new_status: str) -> None:
        """Update the status of a specific branch.

        Args:
            branch_name: Name of the branch to update
            new_status: New status for the branch
        """
        # TODO: Implement branch status updating
        # TODO: Update branch information
        # TODO: Refresh tree display
        # TODO: Trigger UI updates

        if branch_name in self.stack_branches:
            self.stack_branches[branch_name].status = new_status
            console.print(f"[green]Updated {branch_name} status to {new_status}[/green]")
            self._rebuild_tree()

    def export_stack_info(self) -> Dict[str, Any]:
        """Export current stack information for external use.

        Returns:
            Dictionary containing complete stack information
        """
        # TODO: Implement stack information export
        # TODO: Include all branch details
        # TODO: Add stack statistics and metadata

        return {
            'epic_number': self.epic_number,
            'root_branch': self.root_branch,
            'branches': {
                name: {
                    'name': branch.name,
                    'issue_number': branch.issue_number,
                    'status': branch.status,
                    'pr_number': branch.pr_number,
                    'parent': branch.parent,
                    'children': branch.children,
                    'commits_ahead': branch.commits_ahead,
                    'commits_behind': branch.commits_behind,
                    'last_updated': branch.last_updated
                }
                for name, branch in self.stack_branches.items()
            },
            'selected_branch': self.selected_branch
        }