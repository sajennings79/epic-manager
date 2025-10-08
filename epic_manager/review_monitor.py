"""
Review Monitor

Monitors CodeRabbit reviews and automatically triggers fixes.
Handles asynchronous polling and review workflow coordination.
"""

import asyncio
import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from rich.console import Console

from .models import EpicPlan
from .claude_automation import ClaudeSessionManager
from .config import Constants

console = Console()


@dataclass
class PRReview:
    """Represents a PR review from CodeRabbit."""
    pr_number: int
    issue_number: Optional[int]
    instance_name: str
    comment_count: int
    last_comment_at: str
    status: str  # 'new', 'processing', 'addressed', 'failed'
    worktree_path: Optional[str] = None
    session_id: Optional[str] = None
    addressed_at: Optional[str] = None


class ReviewMonitor:
    """Monitors CodeRabbit reviews and coordinates automatic fixes."""

    def __init__(
        self,
        poll_interval: Optional[int] = None,
        gh_command: Optional[str] = None,
        coderabbit_username: Optional[str] = None
    ) -> None:
        """Initialize review monitor.

        Args:
            poll_interval: Polling interval in seconds (default: from Constants)
            gh_command: GitHub CLI command (default: from Constants)
            coderabbit_username: Username to identify CodeRabbit comments (default: from Constants)
        """
        self.poll_interval = poll_interval or Constants.REVIEW_POLL_INTERVAL
        self.gh_command = gh_command or Constants.GITHUB_CLI_COMMAND
        self.coderabbit_username = coderabbit_username or Constants.CODERABBIT_USERNAME

        # Track addressed PRs to avoid reprocessing
        self.addressed_prs: Set[int] = set()

        # Active reviews being processed
        self.active_reviews: Dict[int, PRReview] = {}

        # Monitor task
        self._monitor_task: Optional[asyncio.Task] = None
        self._monitoring = False

        # Verify GitHub CLI is available
        try:
            result = subprocess.run([self.gh_command, "--version"], capture_output=True, text=True)
            console.print(f"[green]GitHub CLI available: {result.stdout.strip()}[/green]")
        except FileNotFoundError:
            console.print(f"[red]Warning: GitHub CLI '{gh_command}' not found[/red]")

    async def _get_active_prs(self, instance_name: str) -> List[int]:
        """Get list of active PR numbers for an instance.

        Args:
            instance_name: Name of the instance

        Returns:
            List of PR numbers that are open
        """
        try:
            # Use gh CLI to get open PRs
            result = subprocess.run([
                self.gh_command, "pr", "list",
                "--repo", f"owner/{instance_name}",  # Adjust repo format as needed
                "--state", "open",
                "--json", "number"
            ], capture_output=True, text=True, cwd=f"/opt/{instance_name}")

            if result.returncode != 0:
                console.print(f"[yellow]Could not get PRs for {instance_name}: {result.stderr}[/yellow]")
                return []

            prs_data = json.loads(result.stdout)
            return [pr["number"] for pr in prs_data]

        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
            console.print(f"[yellow]Error getting PRs for {instance_name}: {e}[/yellow]")
            return []

    async def _discover_epic_prs(self, epic_number: int, instance_path: Path) -> Dict[int, int]:
        """Discover PRs for all issues in an epic.

        Args:
            epic_number: Epic issue number
            instance_path: Path to the KB-LLM instance repository

        Returns:
            Dictionary mapping issue_number -> pr_number
        """
        try:
            # Get epic body to find linked issues
            result = subprocess.run([
                self.gh_command, "issue", "view", str(epic_number),
                "--json", "body"
            ], capture_output=True, text=True, cwd=str(instance_path))

            if result.returncode != 0:
                console.print(f"[yellow]Could not get epic #{epic_number}: {result.stderr}[/yellow]")
                return {}

            data = json.loads(result.stdout)
            body = data.get('body', '')

            # Parse issue numbers from body (matches #123 format)
            # Filter out color codes and other large numbers that can't be GitHub issues
            all_numbers = [int(m) for m in re.findall(r'#(\d+)', body)]
            issue_numbers = sorted(set(n for n in all_numbers if n < 100000))  # Remove duplicates and filter hex colors

            if not issue_numbers:
                console.print(f"[yellow]No linked issues found in epic #{epic_number}[/yellow]")
                return {}

            console.print(f"[blue]Found {len(issue_numbers)} linked issues: {', '.join(f'#{n}' for n in issue_numbers)}[/blue]")

            # Find PRs for each issue by searching for issue-NNN branches
            issue_to_pr = {}

            # Get all open PRs at once
            result = subprocess.run([
                self.gh_command, "pr", "list",
                "--state", "open",
                "--json", "number,headRefName"
            ], capture_output=True, text=True, cwd=str(instance_path))

            if result.returncode != 0:
                console.print(f"[yellow]Could not get PR list: {result.stderr}[/yellow]")
                return {}

            prs_data = json.loads(result.stdout)

            # Match PRs to issues by branch name
            for pr in prs_data:
                pr_number = pr["number"]
                branch_name = pr["headRefName"]

                # Check if branch matches issue-NNN pattern
                match = re.match(r'issue-(\d+)', branch_name)
                if match:
                    issue_num = int(match.group(1))
                    if issue_num in issue_numbers:
                        issue_to_pr[issue_num] = pr_number
                        console.print(f"[green]  Issue #{issue_num} → PR #{pr_number} ({branch_name})[/green]")

            if not issue_to_pr:
                console.print(f"[yellow]No PRs found for epic issues[/yellow]")

            return issue_to_pr

        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
            console.print(f"[yellow]Error discovering PRs: {e}[/yellow]")
            return {}

    async def _has_new_coderabbit_comments(self, pr_number: int, instance_path: Path) -> bool:
        """Check if PR has new CodeRabbit comments.

        Args:
            pr_number: PR number to check
            instance_path: Path to the instance repository

        Returns:
            True if PR has CodeRabbit comments, False otherwise
        """
        try:
            result = subprocess.run([
                self.gh_command, "pr", "view", str(pr_number),
                "--json", "comments"
            ], capture_output=True, text=True, cwd=str(instance_path))

            if result.returncode != 0:
                console.print(f"[dim]Failed to get PR #{pr_number}: {result.stderr.strip()}[/dim]")
                return False

            data = json.loads(result.stdout)
            comments = data.get('comments', [])

            # Check for CodeRabbit comments
            return any(
                comment.get('author', {}).get('login') == self.coderabbit_username
                for comment in comments
            )

        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
            console.print(f"[dim]Error checking PR #{pr_number}: {e}[/dim]")
            return False

    async def monitor_epic_reviews(
        self,
        plan: EpicPlan,
        worktrees: Dict[int, Path],
        instance_path: Path
    ) -> None:
        """Monitor PRs for an epic and trigger fixes when CodeRabbit comments appear.

        Args:
            plan: Epic plan with issue information
            worktrees: Mapping of issue_number -> worktree_path
            instance_path: Path to the instance repository
        """
        # Collect PRs to monitor
        prs_to_monitor = [issue.pr_number for issue in plan.issues if issue.pr_number]
        if not prs_to_monitor:
            console.print("[yellow]No PRs found for this epic[/yellow]")
            return

        console.print(f"[blue]Monitoring {len(prs_to_monitor)} PR(s): {', '.join(f'#{pr}' for pr in prs_to_monitor)}[/blue]")
        console.print(f"[dim]Polling every {self.poll_interval} seconds...[/dim]")

        addressed = set()
        poll_count = 0

        while True:
            poll_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"\n[dim][{timestamp}] Poll #{poll_count}[/dim]")

            # Phase 1: Scan all PRs to identify which have CodeRabbit comments
            prs_needing_fixes = []
            checked_count = 0

            for issue in plan.issues:
                if issue.pr_number and issue.pr_number not in addressed:
                    console.print(f"[dim]  Checking PR #{issue.pr_number} for CodeRabbit comments...[/dim]", end=" ")

                    has_comments = await self._has_new_coderabbit_comments(
                        issue.pr_number, instance_path
                    )

                    if has_comments:
                        console.print("[yellow]✓ Found comments![/yellow]")
                        prs_needing_fixes.append((issue.number, issue.pr_number))
                    else:
                        console.print("[dim]No new comments[/dim]")

                    checked_count += 1

            if checked_count == 0:
                console.print(f"[dim]  All {len(prs_to_monitor)} PR(s) already addressed[/dim]")

            # Phase 2: Launch all fixes in parallel
            if prs_needing_fixes:
                console.print(f"\n[blue]Launching {len(prs_needing_fixes)} CodeRabbit fix workflow(s) in parallel...[/blue]")

                # Prepare worktree-PR pairs
                pr_worktrees = [(worktrees[issue_num], pr_num) for issue_num, pr_num in prs_needing_fixes]

                # Launch all fixes in parallel
                claude_mgr = ClaudeSessionManager()
                results = await claude_mgr.run_parallel_review_fixers(
                    pr_worktrees,
                    max_concurrent=Constants.MAX_CONCURRENT_SESSIONS
                )

                # Process results
                for (issue_num, pr_num), result in zip(prs_needing_fixes, results):
                    if result.success:
                        addressed.add(pr_num)
                        console.print(f"[green]✓ Addressed review comments for PR #{pr_num}[/green]")
                    else:
                        console.print(f"[red]✗ Failed to address comments for PR #{pr_num}: {result.error}[/red]")

            # Check if all PRs have been addressed
            if len(addressed) == len(prs_to_monitor):
                console.print(f"\n[green]All {len(prs_to_monitor)} PR(s) addressed. Monitoring complete![/green]")
                break

            console.print(f"[dim]  Next check in {self.poll_interval} seconds...[/dim]")
            await asyncio.sleep(self.poll_interval)

    async def monitor_epic_by_discovery(
        self,
        epic_number: int,
        instance_name: str,
        instance_path: Path
    ) -> None:
        """Monitor PRs for an epic by discovering them from GitHub.

        This method doesn't require a plan file - it discovers issues and PRs
        directly from GitHub by parsing the epic's body and finding open PRs.

        Args:
            epic_number: Epic issue number
            instance_name: Name of the KB-LLM instance
            instance_path: Path to the instance repository
        """
        # Discover PRs for this epic
        console.print(f"[blue]Discovering PRs for epic #{epic_number}...[/blue]")
        issue_to_pr = await self._discover_epic_prs(epic_number, instance_path)

        if not issue_to_pr:
            console.print("[yellow]No PRs found for this epic[/yellow]")
            return

        prs_to_monitor = list(issue_to_pr.values())
        console.print(f"\n[blue]Monitoring {len(prs_to_monitor)} PR(s): {', '.join(f'#{pr}' for pr in prs_to_monitor)}[/blue]")
        console.print(f"[dim]Polling every {self.poll_interval} seconds...[/dim]")
        console.print("[yellow]Note: Auto-fix with Claude Code requires worktrees (not yet implemented for discovered PRs)[/yellow]")

        addressed = set()
        poll_count = 0

        while True:
            poll_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"\n[dim][{timestamp}] Poll #{poll_count}[/dim]")

            checked_count = 0
            for issue_num, pr_number in issue_to_pr.items():
                if pr_number not in addressed:
                    console.print(f"[dim]  Checking PR #{pr_number} (issue #{issue_num}) for CodeRabbit comments...[/dim]", end=" ")

                    has_comments = await self._has_new_coderabbit_comments(
                        pr_number, instance_path
                    )

                    if has_comments:
                        console.print("[yellow]✓ Found comments![/yellow]")
                        console.print(f"[yellow]CodeRabbit comments detected on PR #{pr_number}[/yellow]")
                        console.print(f"[blue]Visit: https://github.com/{instance_name}/pull/{pr_number}[/blue]")

                        # Mark as addressed (manual review needed without worktrees)
                        addressed.add(pr_number)
                    else:
                        console.print("[dim]No new comments[/dim]")

                    checked_count += 1

            if checked_count == 0:
                console.print(f"[dim]  All {len(prs_to_monitor)} PR(s) already have comments[/dim]")

            # Check if all PRs have been addressed
            if len(addressed) == len(prs_to_monitor):
                console.print(f"\n[green]All {len(prs_to_monitor)} PR(s) have CodeRabbit comments. Monitoring complete![/green]")
                break

            console.print(f"[dim]  Next check in {self.poll_interval} seconds...[/dim]")
            await asyncio.sleep(self.poll_interval)