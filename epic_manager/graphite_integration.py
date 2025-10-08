"""
Graphite Integration

Simplified Graphite stacked PR management using direct CLI queries.
No state management - queries live state from Graphite on demand.
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from rich.console import Console

from .config import Constants

console = Console()


class GraphiteManager:
    """Manages Graphite stacked PR workflows with live state queries."""

    def __init__(self, gt_command: Optional[str] = None) -> None:
        """Initialize Graphite manager.

        Args:
            gt_command: Command to execute Graphite CLI (default: from Constants)
        """
        self.gt_command = gt_command or Constants.GRAPHITE_COMMAND

        # Verify Graphite is available
        try:
            result = subprocess.run([self.gt_command, "--version"], capture_output=True, text=True)
            console.print(f"[green]Graphite CLI available: {result.stdout.strip()}[/green]")
        except FileNotFoundError:
            console.print(f"[red]Warning: Graphite CLI '{self.gt_command}' not found[/red]")

    def create_branch(self, worktree_path: Path, branch_name: str) -> bool:
        """Create a new Graphite branch in the specified worktree.

        Args:
            worktree_path: Path to the worktree
            branch_name: Name of the branch to create

        Returns:
            True if branch creation was successful, False otherwise
        """
        console.print(f"[green]Creating branch: {branch_name}[/green]")
        console.print(f"[blue]In worktree: {worktree_path}[/blue]")

        try:
            result = subprocess.run([
                self.gt_command, "create", branch_name
            ], cwd=worktree_path, capture_output=True, text=True, check=True)

            console.print(f"[blue]Branch created: {branch_name}[/blue]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Branch creation failed: {e.stderr}[/red]")
            return False

    def submit_pr(self, worktree_path: Path, title: str, body: str) -> Optional[int]:
        """Submit PR for current branch using Graphite.

        Args:
            worktree_path: Path to the worktree
            title: PR title
            body: PR description

        Returns:
            PR number if successful, None otherwise
        """
        console.print(f"[green]Submitting PR: {title}[/green]")
        console.print(f"[blue]From worktree: {worktree_path}[/blue]")

        try:
            result = subprocess.run([
                self.gt_command, "submit", "--title", title, "--body", body
            ], cwd=worktree_path, capture_output=True, text=True, check=True)

            # Parse PR number from output (Graphite usually prints it)
            output = result.stdout.strip()
            console.print(f"[blue]PR submitted: {output}[/blue]")

            # Extract PR number if present in output
            import re
            match = re.search(r'#(\d+)', output)
            if match:
                return int(match.group(1))

            return None

        except subprocess.CalledProcessError as e:
            console.print(f"[red]PR submission failed: {e.stderr}[/red]")
            return None

    def sync_stack(self, worktree_path: Path) -> bool:
        """Sync worktree with remote and restack if needed.

        Args:
            worktree_path: Path to the worktree to sync

        Returns:
            True if sync was successful, False otherwise
        """
        console.print(f"[green]Syncing stack in: {worktree_path}[/green]")

        try:
            # Sync with remote
            sync_result = subprocess.run([
                self.gt_command, "sync"
            ], cwd=worktree_path, capture_output=True, text=True, check=True)

            console.print("[blue]Stack synced with remote[/blue]")

            # Restack branches
            restack_result = subprocess.run([
                self.gt_command, "restack"
            ], cwd=worktree_path, capture_output=True, text=True, check=True)

            console.print("[blue]Stack restacked[/blue]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Stack sync failed: {e.stderr}[/red]")
            return False

    def get_stack_status(self, worktree_path: Path) -> Dict[str, Any]:
        """Get current status of the Graphite stack by querying live state.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Dictionary with stack status information
        """
        console.print(f"[green]Getting stack status for: {worktree_path}[/green]")

        try:
            # Get stack information using gt log
            result = subprocess.run([
                self.gt_command, "log", "--stack"
            ], cwd=worktree_path, capture_output=True, text=True, check=True)

            stack_output = result.stdout.strip()

            # Parse the output to extract branch information
            branches = []
            for line in stack_output.split('\n'):
                line = line.strip()
                if line and not line.startswith('─'):
                    # Extract branch info from gt log output
                    # Format varies, but typically includes branch name
                    branches.append(line)

            return {
                'branches': branches,
                'raw_output': stack_output,
                'worktree_path': str(worktree_path)
            }

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Stack status query failed: {e.stderr}[/red]")
            return {
                'error': e.stderr,
                'branches': [],
                'worktree_path': str(worktree_path)
            }