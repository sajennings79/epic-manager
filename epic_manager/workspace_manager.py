"""
Workspace Manager

Simplified git worktree management for parallel development.
Provides core functions: create, list, and cleanup worktrees.
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

console = Console()


class WorkspaceManager:
    """Manages git worktrees for parallel epic development."""

    def __init__(self, work_base_path: str = "/opt/work") -> None:
        """Initialize workspace manager.

        Args:
            work_base_path: Base directory for all worktrees
        """
        self.work_base_path = Path(work_base_path)
        self.work_base_path.mkdir(exist_ok=True, parents=True)

    def worktree_exists(self, worktree_path: Path) -> bool:
        """Check if worktree path exists and is a valid git worktree.

        Args:
            worktree_path: Path to check

        Returns:
            True if path exists and is a git worktree
        """
        if not worktree_path.exists():
            return False

        # Check if it has .git file (worktrees have .git file, not directory)
        git_path = worktree_path / ".git"
        return git_path.exists()

    def branch_exists(self, base_repo: Path, branch_name: str) -> bool:
        """Check if branch exists in repository.

        Args:
            base_repo: Path to base repository
            branch_name: Name of branch to check

        Returns:
            True if branch exists
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(base_repo), "rev-parse", "--verify", f"refs/heads/{branch_name}"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_worktree_commit_count(self, worktree_path: Path) -> int:
        """Count commits in worktree that aren't on main branch.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Number of commits beyond main/base branch
        """
        try:
            # Count commits on current branch not in main
            result = subprocess.run(
                ["git", "-C", str(worktree_path), "rev-list", "--count", "HEAD", "^main"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception as e:
            console.print(f"[yellow]Could not count commits in {worktree_path}: {e}[/yellow]")

        return 0

    def is_worktree_clean(self, worktree_path: Path) -> bool:
        """Check if worktree has no uncommitted changes.

        Args:
            worktree_path: Path to the worktree

        Returns:
            True if worktree is clean (no uncommitted changes)
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(worktree_path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False
            )
            # Empty output means clean
            return result.returncode == 0 and not result.stdout.strip()
        except Exception as e:
            console.print(f"[yellow]Could not check status of {worktree_path}: {e}[/yellow]")
            return False

    def prune_stale_worktrees(self, base_repo: Path) -> None:
        """Remove stale worktree references where directory no longer exists.

        Args:
            base_repo: Path to base repository
        """
        try:
            subprocess.run(
                ["git", "-C", str(base_repo), "worktree", "prune"],
                capture_output=True,
                text=True,
                check=False
            )
        except Exception as e:
            console.print(f"[yellow]Could not prune stale worktrees: {e}[/yellow]")

    def create_issue_worktree(
        self,
        instance_name: str,
        epic_num: int,
        issue_num: int,
        base_branch: str = "main",
        branch_name: Optional[str] = None,
    ) -> Path:
        """Create isolated worktree for issue development.

        Args:
            instance_name: Name of the KB-LLM instance
            epic_num: Epic number from GitHub
            issue_num: Issue number from GitHub
            base_branch: Base branch for the new branch (handles dependencies)
            branch_name: Optional custom branch name

        Returns:
            Path to the created worktree

        Raises:
            subprocess.CalledProcessError: If git worktree creation fails
        """
        base_repo = Path(f"/opt/{instance_name}")
        workspace_dir = self.work_base_path / f"{instance_name}-epic-{epic_num}"
        worktree_path = workspace_dir / f"issue-{issue_num}"

        if branch_name is None:
            branch_name = f"issue-{issue_num}"

        console.print(f"[green]Creating worktree: {worktree_path}[/green]")
        console.print(f"[blue]Branch: {branch_name}[/blue]")

        # Ensure workspace directory exists
        workspace_dir.mkdir(exist_ok=True, parents=True)

        try:
            # Create git worktree with new branch from base_branch (fixes bug)
            result = subprocess.run([
                "git", "-C", str(base_repo),
                "worktree", "add", "-b", branch_name,  # -b flag creates branch atomically
                str(worktree_path), base_branch
            ], capture_output=True, text=True, check=True)

            console.print(f"[blue]Worktree created successfully[/blue]")

            # Optional: Track in Graphite for stack operations
            self._track_in_graphite(worktree_path, branch_name)

            return worktree_path

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to create worktree: {e.stderr}[/red]")
            raise

    def create_or_reuse_worktree(
        self,
        instance_name: str,
        epic_num: int,
        issue_num: int,
        base_branch: str = "main",
        branch_name: Optional[str] = None,
    ) -> Path:
        """Smart worktree creation that handles existing worktrees.

        Strategy:
        1. Prune stale git worktree references
        2. If worktree exists:
           - If no commits: Clean up and recreate (failed previous run)
           - If has commits and clean: Reuse it
           - If has commits and dirty: Error (don't lose uncommitted work)
        3. If branch exists without worktree: Delete stale branch and create
        4. Otherwise: Create normally

        Args:
            instance_name: Name of the KB-LLM instance
            epic_num: Epic number from GitHub
            issue_num: Issue number from GitHub
            base_branch: Base branch for the new branch (handles dependencies)
            branch_name: Optional custom branch name

        Returns:
            Path to the worktree (created or reused)

        Raises:
            ValueError: If worktree has uncommitted changes
            subprocess.CalledProcessError: If git operations fail
        """
        base_repo = Path(f"/opt/{instance_name}")
        workspace_dir = self.work_base_path / f"{instance_name}-epic-{epic_num}"
        worktree_path = workspace_dir / f"issue-{issue_num}"

        if branch_name is None:
            branch_name = f"issue-{issue_num}"

        # Step 1: Prune any stale references
        self.prune_stale_worktrees(base_repo)

        # Step 2: Check if worktree already exists
        if self.worktree_exists(worktree_path):
            console.print(f"[yellow]Worktree already exists: {worktree_path}[/yellow]")

            # Check if it has any commits beyond base branch
            commit_count = self.get_worktree_commit_count(worktree_path)

            if commit_count == 0:
                # No work done - likely failed previous run
                console.print("[yellow]No commits found - cleaning up failed worktree and recreating[/yellow]")
                success = self.cleanup_worktree(worktree_path, force=True)
                if not success:
                    # Cleanup failed, try to continue anyway
                    console.print("[yellow]Cleanup had issues, attempting to continue[/yellow]")

                # After cleanup, delete the branch if it still exists
                if self.branch_exists(base_repo, branch_name):
                    console.print(f"[yellow]Deleting stale branch '{branch_name}' after worktree cleanup[/yellow]")
                    try:
                        subprocess.run(
                            ["git", "-C", str(base_repo), "branch", "-D", branch_name],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                    except subprocess.CalledProcessError as e:
                        console.print(f"[yellow]Could not delete branch: {e.stderr}[/yellow]")

                # Continue to create fresh worktree below
            else:
                # Has commits - check if clean
                if self.is_worktree_clean(worktree_path):
                    console.print(f"[blue]Reusing existing worktree with {commit_count} commit(s)[/blue]")
                    return worktree_path
                else:
                    raise ValueError(
                        f"Worktree {worktree_path} has uncommitted changes. "
                        f"Commit or stash changes before retrying epic, or run 'epic-mgr epic cleanup {epic_num} --force'"
                    )

        # Step 3: Check if branch exists without worktree (stale branch)
        elif self.branch_exists(base_repo, branch_name):
            console.print(f"[yellow]Stale branch '{branch_name}' exists without worktree - deleting[/yellow]")
            try:
                subprocess.run(
                    ["git", "-C", str(base_repo), "branch", "-D", branch_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
                console.print(f"[blue]Deleted stale branch '{branch_name}'[/blue]")
            except subprocess.CalledProcessError as e:
                console.print(f"[yellow]Could not delete stale branch: {e.stderr}[/yellow]")
                # Continue anyway, create_issue_worktree might handle it

        # Step 4: Create fresh worktree
        return self.create_issue_worktree(
            instance_name, epic_num, issue_num, base_branch, branch_name
        )

    def list_worktrees(self, instance_name: Optional[str] = None) -> Dict[str, Dict]:
        """List all active worktrees.

        Args:
            instance_name: Optional filter by instance name

        Returns:
            Dictionary mapping worktree names to their information
        """
        console.print("[green]Listing worktrees[/green]")

        worktrees = {}

        if instance_name:
            # List worktrees for specific instance
            base_repo = Path(f"/opt/{instance_name}")
            if base_repo.exists():
                worktrees.update(self._get_instance_worktrees(instance_name, base_repo))
        else:
            # List worktrees for all instances
            for opt_dir in Path("/opt").iterdir():
                if opt_dir.is_dir() and (opt_dir / ".git").exists():
                    instance_name = opt_dir.name
                    worktrees.update(self._get_instance_worktrees(instance_name, opt_dir))

        return worktrees

    def _get_instance_worktrees(self, instance_name: str, repo_path: Path) -> Dict[str, Dict]:
        """Get worktrees for a specific instance repository.

        Args:
            instance_name: Name of the instance
            repo_path: Path to the repository

        Returns:
            Dictionary of worktree information
        """
        worktrees = {}

        try:
            result = subprocess.run([
                "git", "-C", str(repo_path), "worktree", "list", "--porcelain"
            ], capture_output=True, text=True, check=True)

            current_worktree = {}
            for line in result.stdout.strip().split('\n'):
                if line.startswith('worktree '):
                    if current_worktree:
                        # Save previous worktree
                        path = current_worktree.get('worktree', '')
                        if path:
                            name = Path(path).name
                            worktrees[f"{instance_name}-{name}"] = current_worktree

                    # Start new worktree
                    current_worktree = {'worktree': line[9:], 'instance': instance_name}
                elif line.startswith('branch '):
                    current_worktree['branch'] = line[7:]
                elif line.startswith('HEAD '):
                    current_worktree['commit'] = line[4:]

            # Save last worktree
            if current_worktree:
                path = current_worktree.get('worktree', '')
                if path:
                    name = Path(path).name
                    worktrees[f"{instance_name}-{name}"] = current_worktree

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to list worktrees for {instance_name}: {e.stderr}[/red]")

        return worktrees

    def cleanup_worktree(self, worktree_path: Path, force: bool = False) -> bool:
        """Cleanup and remove a worktree.

        Args:
            worktree_path: Path to the worktree to remove
            force: Force removal even if worktree has uncommitted changes

        Returns:
            True if cleanup was successful, False otherwise
        """
        console.print(f"[yellow]Cleaning up worktree: {worktree_path}[/yellow]")

        if not worktree_path.exists():
            console.print(f"[yellow]Worktree does not exist: {worktree_path}[/yellow]")
            return True

        # Find the base repository for this worktree
        base_repo = self._find_base_repo(worktree_path)
        if not base_repo:
            console.print(f"[red]Could not find base repository for worktree[/red]")
            return False

        try:
            # Remove git worktree
            cmd = ["git", "-C", str(base_repo), "worktree", "remove", str(worktree_path)]
            if force:
                cmd.append("--force")

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            console.print(f"[blue]Worktree removed successfully[/blue]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to remove worktree: {e.stderr}[/red]")
            return False

    def _find_base_repo(self, worktree_path: Path) -> Optional[Path]:
        """Find the base repository for a given worktree.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Path to the base repository, or None if not found
        """
        # Check if this is in our standard work directory structure
        if "/opt/work/" in str(worktree_path):
            # Extract instance name from path like /opt/work/instance-epic-123/issue-456
            parts = worktree_path.parts
            work_index = parts.index("work")
            if work_index + 1 < len(parts):
                workspace_name = parts[work_index + 1]
                instance_name = workspace_name.split("-epic-")[0]
                base_repo = Path(f"/opt/{instance_name}")
                if base_repo.exists() and (base_repo / ".git").exists():
                    return base_repo

        return None

    def _track_in_graphite(self, worktree_path: Path, branch_name: str) -> None:
        """Track branch in Graphite for stack operations (optional).

        Args:
            worktree_path: Path to the worktree
            branch_name: Name of the branch to track

        Note:
            This is non-critical - Claude can track the branch later if this fails.
        """
        try:
            result = subprocess.run([
                "gt", "track", branch_name
            ], cwd=str(worktree_path), capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                console.print(f"[blue]Branch {branch_name} tracked in Graphite[/blue]")
            else:
                console.print(f"[yellow]Could not track in Graphite (non-critical): {result.stderr}[/yellow]")

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            console.print(f"[yellow]Graphite tracking failed (non-critical): {e}[/yellow]")