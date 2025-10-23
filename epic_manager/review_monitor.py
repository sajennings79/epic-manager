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
            # Filter out CSS color codes (hex patterns like #374151) and duplicates
            # Valid GitHub issue numbers are typically decimal integers without hex letters
            hash_patterns = re.findall(r'#([0-9a-fA-F]+)', body)
            issue_numbers = []
            for pattern in hash_patterns:
                # Filter out patterns that contain hex letters (likely color codes)
                if re.match(r'^[0-9]+$', pattern):
                    num = int(pattern)
                    issue_numbers.append(num)
            issue_numbers = sorted(set(issue_numbers))  # Remove duplicates

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

            # Match PRs to issues by branch name and auto-publish drafts
            for pr in prs_data:
                pr_number = pr["number"]
                branch_name = pr["headRefName"]
                is_draft = pr.get("isDraft", False)

                # Check if branch matches issue-NNN pattern
                match = re.match(r'issue-(\d+)', branch_name)
                if match:
                    issue_num = int(match.group(1))
                    if issue_num in issue_numbers:
                        if is_draft:
                            # Auto-publish draft PRs to enable CodeRabbit review
                            console.print(f"[yellow]  Issue #{issue_num} → PR #{pr_number} ({branch_name}) [DRAFT - publishing...][/yellow]")
                            published = await self._publish_draft_pr(pr_number, instance_path)
                            if published:
                                issue_to_pr[issue_num] = pr_number
                            else:
                                console.print(f"[red]  Failed to publish PR #{pr_number}, skipping[/red]")
                        else:
                            issue_to_pr[issue_num] = pr_number
                            console.print(f"[green]  Issue #{issue_num} → PR #{pr_number} ({branch_name}) [READY][/green]")

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

    async def _publish_draft_pr(self, pr_number: int, instance_path: Path) -> bool:
        """Publish a draft PR to make it ready for review.

        CodeRabbit cannot review draft PRs, so we must ensure all PRs are published.

        Args:
            pr_number: PR number to publish
            instance_path: Path to the instance repository

        Returns:
            True if PR was published successfully, False otherwise
        """
        try:
            console.print(f"[yellow]Publishing draft PR #{pr_number} to enable CodeRabbit review...[/yellow]")

            result = subprocess.run([
                self.gh_command, "pr", "ready", str(pr_number)
            ], capture_output=True, text=True, cwd=str(instance_path))

            if result.returncode != 0:
                console.print(f"[red]Failed to publish PR #{pr_number}: {result.stderr}[/red]")
                return False

            console.print(f"[green]✓ PR #{pr_number} is now published and ready for review[/green]")
            return True

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            console.print(f"[red]Error publishing PR #{pr_number}: {e}[/red]")
            return False

    async def _count_coderabbit_comments(self, pr_number: int, instance_path: Path) -> int:
        """Count the number of CodeRabbit comments on a PR.

        Args:
            pr_number: PR number to check
            instance_path: Path to the instance repository

        Returns:
            Number of CodeRabbit comments (0 if none or error)
        """
        try:
            result = subprocess.run([
                self.gh_command, "pr", "view", str(pr_number),
                "--json", "comments"
            ], capture_output=True, text=True, cwd=str(instance_path))

            if result.returncode != 0:
                return 0

            data = json.loads(result.stdout)
            comments = data.get('comments', [])

            # Count CodeRabbit comments
            return sum(
                1 for comment in comments
                if comment.get('author', {}).get('login') == self.coderabbit_username
            )

        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
            return 0

    async def monitor_epic_reviews(
        self,
        plan: EpicPlan,
        worktrees: Dict[int, Path],
        instance_path: Path,
        epic_number: Optional[int] = None
    ) -> None:
        """Monitor PRs for an epic and trigger fixes when CodeRabbit comments appear.

        Continuously polls PRs, launches fixes when comments are found, and iterates
        until all PRs have 0 CodeRabbit comments. Discovers new PRs dynamically.

        Args:
            plan: Epic plan with issue information
            worktrees: Mapping of issue_number -> worktree_path
            instance_path: Path to the instance repository
            epic_number: Epic issue number for dynamic PR discovery (optional)
        """
        # Initialize tracking state
        addressed = set()  # PRs with 0 comments (truly clean)
        fix_attempts: Dict[int, int] = {}  # PR -> attempt count
        fixes_launched_this_poll: Set[int] = set()  # Track fixes launched in current poll
        poll_count = 0

        # Get epic number from plan if not provided
        if epic_number is None and hasattr(plan, 'epic'):
            epic_number = plan.epic.number

        console.print(f"[dim]Polling every {self.poll_interval} seconds...[/dim]")
        console.print(f"[dim]Max fix attempts per PR: {Constants.MAX_FIX_ATTEMPTS}[/dim]\n")

        while True:
            poll_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"\n[dim][{timestamp}] Poll #{poll_count}[/dim]")

            # Phase 0: Discover PRs dynamically (find new PRs added during monitoring)
            if epic_number:
                console.print(f"[dim]  Discovering PRs for epic #{epic_number}...[/dim]")
                issue_to_pr = await self._discover_epic_prs(epic_number, instance_path)

                # Update plan with newly discovered PRs
                new_prs_found = 0
                for issue in plan.issues:
                    if issue.number in issue_to_pr:
                        discovered_pr = issue_to_pr[issue.number]
                        if not issue.pr_number:
                            # New PR discovered!
                            issue.pr_number = discovered_pr
                            new_prs_found += 1
                            console.print(f"[green]  ✓ New PR discovered: Issue #{issue.number} → PR #{discovered_pr}[/green]")

                if new_prs_found > 0:
                    console.print(f"[green]  Found {new_prs_found} new PR(s) during this poll[/green]")

            # Collect current PRs to monitor
            prs_to_monitor = [issue.pr_number for issue in plan.issues if issue.pr_number]

            if not prs_to_monitor:
                console.print("[yellow]No PRs found for this epic[/yellow]")
                await asyncio.sleep(self.poll_interval)
                continue

            # Display current monitoring status
            console.print(f"[blue]Monitoring {len(prs_to_monitor)} PR(s): {', '.join(f'#{pr}' for pr in prs_to_monitor)}[/blue]")
            console.print(f"[dim]  Clean: {len(addressed)}, Need attention: {len(prs_to_monitor) - len(addressed)}[/dim]")

            # Phase 1: Scan all PRs to check CodeRabbit comment status
            prs_needing_fixes = []
            checked_count = 0

            for issue in plan.issues:
                if not issue.pr_number:
                    continue

                pr_num = issue.pr_number

                # Skip if already clean
                if pr_num in addressed:
                    continue

                # Skip if max attempts reached
                if fix_attempts.get(pr_num, 0) >= Constants.MAX_FIX_ATTEMPTS:
                    console.print(f"[red]  PR #{pr_num}: Max attempts ({Constants.MAX_FIX_ATTEMPTS}) reached, skipping[/red]")
                    continue

                console.print(f"[dim]  Checking PR #{pr_num} for CodeRabbit comments...[/dim]", end=" ")

                # Count comments (not just check existence)
                comment_count = await self._count_coderabbit_comments(pr_num, instance_path)

                if comment_count > 0:
                    attempts = fix_attempts.get(pr_num, 0)
                    console.print(f"[yellow]✓ {comment_count} comment(s) (attempt {attempts + 1}/{Constants.MAX_FIX_ATTEMPTS})[/yellow]")

                    # Check if worktree exists for this issue
                    if issue.number not in worktrees:
                        console.print(f"[yellow]  ⚠ No worktree for issue #{issue.number}, cannot auto-fix[/yellow]")
                    else:
                        prs_needing_fixes.append((issue.number, pr_num))
                else:
                    # 0 comments = truly addressed!
                    console.print("[green]✓ Clean (0 comments)[/green]")
                    addressed.add(pr_num)

                checked_count += 1

            if checked_count == 0:
                console.print(f"[dim]  All {len(prs_to_monitor)} PR(s) already clean or at max attempts[/dim]")

            # Phase 2: Launch fixes for PRs with comments
            fixes_launched_this_poll = set()

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

                # Process results (DO NOT mark as addressed yet - wait for CodeRabbit response)
                for (issue_num, pr_num), result in zip(prs_needing_fixes, results):
                    # Increment attempt counter
                    fix_attempts[pr_num] = fix_attempts.get(pr_num, 0) + 1

                    if result.success:
                        console.print(f"[green]✓ Fix workflow completed for PR #{pr_num}[/green]")
                        fixes_launched_this_poll.add(pr_num)
                    else:
                        console.print(f"[red]✗ Fix workflow failed for PR #{pr_num}: {result.error}[/red]")

                # Inform user that we'll continue polling
                if fixes_launched_this_poll:
                    console.print(f"\n[blue]Fixes launched for {len(fixes_launched_this_poll)} PR(s). Continuing to poll for CodeRabbit responses...[/blue]")

            # Phase 3: Check completion criteria
            # Only exit when ALL PRs have 0 comments (are in 'addressed' set)
            if len(addressed) >= len(prs_to_monitor):
                console.print(f"\n[green]✓ All {len(prs_to_monitor)} PR(s) have 0 CodeRabbit comments. Monitoring complete![/green]")
                break

            # Check if we're stuck (all PRs either addressed or at max attempts)
            still_working = len([pr for pr in prs_to_monitor if pr not in addressed and fix_attempts.get(pr, 0) < Constants.MAX_FIX_ATTEMPTS])
            if still_working == 0:
                console.print(f"\n[yellow]All remaining PRs have reached max fix attempts. Stopping monitoring.[/yellow]")
                console.print(f"[dim]  Clean: {len(addressed)}, Max attempts: {len([pr for pr in prs_to_monitor if fix_attempts.get(pr, 0) >= Constants.MAX_FIX_ATTEMPTS])}[/dim]")
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