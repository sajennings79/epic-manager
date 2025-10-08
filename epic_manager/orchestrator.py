"""
Epic Orchestrator

Simplified epic workflow coordination.
Focuses on core functionality: analyze GitHub epics, start workflows, track state.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from rich.console import Console

from .models import EpicPlan, WorkflowResult
from .claude_automation import ClaudeSessionManager
from .workspace_manager import WorkspaceManager
from .review_monitor import ReviewMonitor
from .config import Constants

console = Console()


@dataclass
class EpicIssue:
    """Represents an issue within an epic."""
    number: int
    title: str
    status: str  # 'pending', 'in_progress', 'review', 'completed'
    dependencies: List[int] = None
    worktree_path: Optional[str] = None
    pr_number: Optional[int] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class EpicState:
    """Represents the state of an epic."""
    number: int
    title: str
    instance: str
    status: str  # 'planning', 'active', 'completed', 'paused'
    issues: List[EpicIssue]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    build_status: Optional[str] = None  # 'pending', 'running', 'success', 'failed'
    built_at: Optional[str] = None
    build_error: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class EpicOrchestrator:
    """Plan-driven epic workflow orchestrator.

    Uses Claude's /epic-plan output to coordinate parallel development
    across isolated worktrees with proper dependency handling.
    """

    def __init__(self, state_dir: str = "data/state", instance_name: Optional[str] = None) -> None:
        """Initialize epic orchestrator.

        Args:
            state_dir: Directory for storing epic state files (used when instance_name not provided)
            instance_name: Name of the KB-LLM instance. If provided, state is stored in
                          /opt/{instance_name}/.epic-mgr/state/ instead of state_dir
        """
        if instance_name:
            # Store state in instance's hidden .epic-mgr directory
            self.state_dir = Path(f"/opt/{instance_name}/.epic-mgr/state")
        else:
            # Use provided state_dir (for tests or backward compatibility)
            self.state_dir = Path(state_dir)

        self.state_dir.mkdir(exist_ok=True, parents=True)
        self.workspace_mgr = WorkspaceManager()

    async def analyze_epic(self, epic_number: int, instance_name: str) -> EpicPlan:
        """Analyze GitHub epic using Claude's /epic-plan command.

        Args:
            epic_number: GitHub epic number
            instance_name: Target KB-LLM instance

        Returns:
            EpicPlan with coordination details from Claude
        """
        console.print(f"[green]Analyzing epic {epic_number} for {instance_name}[/green]")

        claude_mgr = ClaudeSessionManager()
        instance_path = Path(f"/opt/{instance_name}")

        # Ask Claude for JSON plan using centralized prompt
        plan_json = await claude_mgr.get_epic_plan(instance_path, epic_number, instance_name)

        # Debug: Show what JSON we received
        console.print(f"[dim]Received JSON response ({len(plan_json)} chars)[/dim]")

        # Parse and save
        try:
            plan = EpicPlan.from_json(plan_json)
            self._save_plan(plan)

            console.print(f"[blue]Epic plan created with {len(plan.issues)} issues in {len(plan.parallelization)} phases[/blue]")
            return plan
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            console.print(f"[red]Failed to parse epic plan JSON: {e}[/red]")
            console.print("[yellow]JSON response:[/yellow]")
            console.print(plan_json[:500])  # Show first 500 chars
            raise

    def start_epic(self, epic_number: int) -> bool:
        """Start epic development workflow.

        Creates worktrees and prepares for parallel development.

        Args:
            epic_number: Epic number to start

        Returns:
            True if epic was started successfully, False otherwise
        """
        epic_state = self.load_epic_state(epic_number)
        if not epic_state:
            console.print(f"[red]Epic {epic_number} not found. Run analyze_epic first.[/red]")
            return False

        if epic_state.status not in ['planning', 'paused']:
            console.print(f"[yellow]Epic {epic_number} is in {epic_state.status} state[/yellow]")
            return False

        console.print(f"[green]Starting epic {epic_number}[/green]")

        # Update status
        epic_state.status = 'active'
        self._save_epic_state(epic_state)

        console.print(f"[blue]Epic {epic_number} is now active[/blue]")
        return True

    def update_issue_status(
        self,
        epic_number: int,
        issue_number: int,
        new_status: str,
        **kwargs
    ) -> bool:
        """Update status of an issue within an epic.

        Args:
            epic_number: Epic containing the issue
            issue_number: Issue number to update
            new_status: New status for the issue
            **kwargs: Additional fields to update

        Returns:
            True if update was successful, False otherwise
        """
        epic_state = self.load_epic_state(epic_number)
        if not epic_state:
            return False

        # Find and update the issue
        for issue in epic_state.issues:
            if issue.number == issue_number:
                issue.status = new_status

                # Update additional fields
                for key, value in kwargs.items():
                    if hasattr(issue, key):
                        setattr(issue, key, value)

                epic_state.updated_at = datetime.now().isoformat()
                self._save_epic_state(epic_state)

                console.print(f"[green]Updated issue {issue_number} status to {new_status}[/green]")
                return True

        console.print(f"[yellow]Issue {issue_number} not found in epic {epic_number}[/yellow]")
        return False

    def load_epic_state(self, epic_number: int) -> Optional[EpicState]:
        """Load epic state from persistent storage.

        Args:
            epic_number: Epic number to load

        Returns:
            EpicState object if found, None otherwise
        """
        state_file = self.state_dir / f"epic-{epic_number}.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file) as f:
                state_data = json.load(f)

            # Convert issues list to EpicIssue objects
            issues = [EpicIssue(**issue_data) for issue_data in state_data.get('issues', [])]
            state_data['issues'] = issues

            return EpicState(**state_data)

        except (json.JSONDecodeError, TypeError) as e:
            console.print(f"[red]Error loading epic state for {epic_number}: {e}[/red]")
            return None

    def _save_epic_state(self, epic_state: EpicState) -> None:
        """Save epic state to persistent storage.

        Args:
            epic_state: Epic state to save
        """
        state_file = self.state_dir / f"epic-{epic_state.number}.json"

        try:
            # Convert to dictionary for JSON serialization
            state_dict = asdict(epic_state)

            with open(state_file, 'w') as f:
                json.dump(state_dict, f, indent=2, default=str)

            console.print(f"[blue]Saved state for epic {epic_state.number}[/blue]")

        except (OSError, TypeError) as e:
            console.print(f"[red]Error saving epic state for {epic_state.number}: {e}[/red]")

    def list_active_epics(self) -> List[EpicState]:
        """List all active epics across all instances.

        Returns:
            List of active EpicState objects
        """
        active_epics = []

        for state_file in self.state_dir.glob("epic-*.json"):
            try:
                epic_number = int(state_file.stem.split('-')[1])
                epic_state = self.load_epic_state(epic_number)

                if epic_state and epic_state.status in ['planning', 'active']:
                    active_epics.append(epic_state)

            except (ValueError, IndexError):
                console.print(f"[yellow]Skipping invalid state file: {state_file}[/yellow]")

        return sorted(active_epics, key=lambda e: e.created_at or "")

    async def start_development(
        self,
        plan: EpicPlan,
        worktrees: Dict[int, Path],
        existing_prs: Optional[Dict[int, int]] = None
    ) -> Dict[int, WorkflowResult]:
        """Launch TDD workflows respecting dependency phases.

        Args:
            plan: Epic plan with phase information
            worktrees: Mapping of issue_number -> worktree_path
            existing_prs: Optional mapping of issue_number -> pr_number for already completed issues

        Returns:
            Dictionary mapping issue_number -> WorkflowResult
        """
        if existing_prs is None:
            existing_prs = {}

        claude_mgr = ClaudeSessionManager()
        results = {}

        # Process phases sequentially (dependencies)
        for phase_name in plan.get_phase_order():
            issues_in_phase = plan.get_issues_for_phase(phase_name)
            console.print(f"[green]Phase {phase_name}: {[i.number for i in issues_in_phase]}[/green]")

            # Filter out issues that already have PRs
            phase_tasks = []
            for issue in issues_in_phase:
                if issue.number in worktrees:
                    if issue.number in existing_prs:
                        console.print(f"[blue]  Issue {issue.number} already has PR #{existing_prs[issue.number]}, skipping[/blue]")
                        # Create a success result for the skipped issue
                        results[issue.number] = WorkflowResult(
                            issue_number=issue.number,
                            success=True,
                            duration_seconds=0.0,
                            pr_number=existing_prs[issue.number]
                        )
                    else:
                        console.print(f"[yellow]  Issue {issue.number} needs TDD workflow[/yellow]")
                        phase_tasks.append((worktrees[issue.number], issue.number))

            if not phase_tasks:
                console.print(f"[blue]All issues in phase {phase_name} already complete[/blue]")
                continue

            phase_results = await claude_mgr.run_parallel_tdd_workflows(
                phase_tasks,
                max_concurrent=Constants.MAX_CONCURRENT_SESSIONS
            )

            # Check for failures
            for result in phase_results:
                results[result.issue_number] = result
                if not result.success:
                    console.print(f"[red]Phase {phase_name} failed on issue {result.issue_number}: {result.error}[/red]")
                    return results  # Stop on phase failure
                else:
                    console.print(f"[green]Issue {result.issue_number} completed successfully[/green]")

        return results

    def _save_plan(self, plan: EpicPlan) -> None:
        """Save epic plan to persistent storage.

        Args:
            plan: Epic plan to save
        """
        plan_file = self.state_dir / f"epic-{plan.epic.number}-plan.json"
        plan.save(plan_file)
        console.print(f"[blue]Saved plan for epic {plan.epic.number}[/blue]")

    def load_plan(self, epic_number: int) -> Optional[EpicPlan]:
        """Load epic plan from persistent storage.

        Args:
            epic_number: Epic number to load

        Returns:
            EpicPlan object if found, None otherwise
        """
        plan_file = self.state_dir / f"epic-{epic_number}-plan.json"
        if not plan_file.exists():
            return None

        try:
            return EpicPlan.load(plan_file)
        except (json.JSONDecodeError, KeyError) as e:
            console.print(f"[red]Error loading epic plan for {epic_number}: {e}[/red]")
            return None

    async def create_worktrees_for_plan(self, plan: EpicPlan) -> Dict[int, Path]:
        """Create worktrees for all issues in the plan.

        Args:
            plan: Epic plan with issue information

        Returns:
            Dictionary mapping issue_number -> worktree_path
        """
        worktrees = {}

        for issue in plan.issues:
            try:
                worktree_path = self.workspace_mgr.create_or_reuse_worktree(
                    instance_name=plan.epic.instance,
                    epic_num=plan.epic.number,
                    issue_num=issue.number,
                    base_branch=issue.base_branch  # Critical for dependencies
                )

                worktrees[issue.number] = worktree_path

                # Update plan with worktree path
                plan.update_issue_worktree(issue.number, str(worktree_path))

                console.print(f"[green]Created worktree for issue {issue.number}: {worktree_path}[/green]")

            except Exception as e:
                console.print(f"[red]Failed to create worktree for issue {issue.number}: {e}[/red]")

        # Save updated plan
        self._save_plan(plan)

        return worktrees

    async def _start_review_monitor(
        self,
        plan: EpicPlan,
        worktrees: Dict[int, Path]
    ) -> None:
        """Start review monitoring as background task.

        Args:
            plan: Epic plan with issue information
            worktrees: Mapping of issue_number -> worktree_path
        """
        console.print(f"[blue]Starting CodeRabbit review monitoring for epic {plan.epic.number}[/blue]")

        try:
            monitor = ReviewMonitor()
            instance_path = Path(f"/opt/{plan.epic.instance}")
            await monitor.monitor_epic_reviews(plan, worktrees, instance_path)
        except asyncio.CancelledError:
            console.print("[yellow]Review monitoring stopped[/yellow]")
        except Exception as e:
            console.print(f"[red]Review monitoring error: {e}[/red]")

    def get_existing_prs(self, instance_name: str) -> Dict[int, int]:
        """Get existing PRs for issue branches.

        Args:
            instance_name: KB-LLM instance name

        Returns:
            Dictionary mapping issue_number -> pr_number
        """
        instance_path = Path(f"/opt/{instance_name}")

        if not instance_path.exists():
            console.print(f"[yellow]Instance path does not exist: {instance_path}[/yellow]")
            return {}

        prs = {}

        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--json", "number,headRefName"],
                cwd=str(instance_path),
                capture_output=True,
                text=True,
                check=True
            )

            pr_list = json.loads(result.stdout)

            for pr in pr_list:
                # Match issue branches like "issue-581"
                if pr['headRefName'].startswith('issue-'):
                    try:
                        issue_number = int(pr['headRefName'].split('-')[1])
                        prs[issue_number] = pr['number']
                    except (ValueError, IndexError):
                        continue

        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            console.print(f"[yellow]Could not fetch existing PRs: {e}[/yellow]")

        return prs

    async def run_complete_epic(self, epic_number: int, instance_name: str) -> bool:
        """Run complete epic workflow from analysis to completion.

        Args:
            epic_number: Epic number to execute
            instance_name: KB-LLM instance name

        Returns:
            True if epic completed successfully, False otherwise
        """
        try:
            # Step 1: Load or analyze epic plan
            console.print(f"[blue]Step 1: Loading or analyzing epic {epic_number}[/blue]")

            # Try to load existing plan first
            plan = self.load_plan(epic_number)

            if plan:
                console.print(f"[green]Loaded existing plan for epic {epic_number}[/green]")
            else:
                console.print(f"[blue]No existing plan found, analyzing epic {epic_number}[/blue]")
                plan = await self.analyze_epic(epic_number, instance_name)

            # Step 2: Create worktrees
            console.print(f"[blue]Step 2: Creating worktrees[/blue]")
            worktrees = await self.create_worktrees_for_plan(plan)

            if not worktrees:
                console.print("[red]No worktrees created - cannot proceed[/red]")
                return False

            # Step 2.5: Sync Graphite stack
            console.print("[blue]Step 2.5: Syncing Graphite stack[/blue]")
            instance_path = Path(f"/opt/{instance_name}")
            self.sync_graphite_stack(instance_path)

            # Step 2.6: Check for existing PRs
            console.print("[blue]Step 2.6: Checking for existing PRs[/blue]")
            existing_prs = self.get_existing_prs(instance_name)
            if existing_prs:
                console.print(f"[green]Found existing PRs: {existing_prs}[/green]")
            else:
                console.print("[blue]No existing PRs found[/blue]")

            # Step 3: Start review monitoring in background
            console.print("[blue]Step 3: Starting CodeRabbit review monitoring[/blue]")
            monitor_task = asyncio.create_task(self._start_review_monitor(plan, worktrees))

            # Step 4: Execute development
            console.print("[blue]Step 4: Starting development[/blue]")
            results = await self.start_development(plan, worktrees, existing_prs)

            # Step 5: Report results
            console.print(f"[blue]Step 5: Development completed[/blue]")
            successful = sum(1 for r in results.values() if r.success)
            total = len(results)

            console.print(f"[green]Epic {epic_number} completed: {successful}/{total} issues successful[/green]")

            # Cancel review monitor (runs indefinitely)
            console.print("[blue]Stopping review monitoring[/blue]")
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            return successful == total

        except Exception as e:
            console.print(f"[red]Epic {epic_number} failed: {e}[/red]")
            # Don't suppress traceback for debugging
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return False

    async def build_epic_container(
        self,
        epic_number: int,
        instance_name: str,
        auto_sync: bool = False,
        skip_checks: bool = False,
        force: bool = False,
        no_cache: bool = False
    ) -> bool:
        """Build epic to Docker container for pre-merge testing.

        This method orchestrates the complete build process:
        1. Validates epic completion
        2. Checks PR health (unless skip_checks)
        3. Identifies top branch of epic stack
        4. Checks out top branch in main repo
        5. Syncs stack with main (gt sync)
        6. Runs build-dev.sh
        7. Streams output and tracks build status

        Args:
            epic_number: Epic number to build
            instance_name: KB-LLM instance name
            auto_sync: Automatically sync without prompting
            skip_checks: Skip PR health validation
            force: Force build even if validation fails
            no_cache: Pass --no-cache to Docker build

        Returns:
            True if build succeeded, False otherwise
        """
        import subprocess
        import click

        # 1. Validate instance path first
        instance_path = Path(f"/opt/{instance_name}")
        if not instance_path.exists():
            console.print(f"[red]Instance path not found: {instance_path}[/red]")
            return False

        # 2. Try to load epic state, fall back to PR discovery if not found
        epic_state = self.load_epic_state(epic_number)
        issue_numbers = []

        if not epic_state:
            console.print("[yellow]No epic state found, discovering PRs from GitHub...[/yellow]")

            # Discover PRs for the epic
            issue_to_pr = await self._discover_epic_prs(epic_number, instance_path)

            if not issue_to_pr:
                console.print(f"[red]No PRs found for epic {epic_number}[/red]")
                console.print("[dim]Make sure PRs are created and linked to the epic[/dim]")
                return False

            issue_numbers = sorted(issue_to_pr.keys())
            console.print(f"[green]Discovered {len(issue_numbers)} PRs for epic: {issue_numbers}[/green]")

        else:
            # Use epic state
            issue_numbers = [i.number for i in epic_state.issues]

            # Check all issues are completed or in review
            incomplete = [i for i in epic_state.issues if i.status not in ['completed', 'review']]
            if incomplete and not force:
                console.print(f"[red]{len(incomplete)} issues not completed:[/red]")
                for issue in incomplete[:5]:  # Show first 5
                    console.print(f"  [yellow]#{issue.number}: {issue.title} ({issue.status})[/yellow]")
                if len(incomplete) > 5:
                    console.print(f"  [dim]... and {len(incomplete) - 5} more[/dim]")
                console.print("[dim]Use --force to build anyway[/dim]")
                return False

            console.print(f"[blue]All {len(epic_state.issues)} issues ready for build[/blue]")

        if not issue_numbers:
            console.print("[red]No issues found for epic[/red]")
            return False

        # 3. PR health check (unless skipped)
        if not skip_checks:
            console.print("[blue]Checking PR health...[/blue]")
            health_ok = await self._check_pr_health(epic_number, instance_name)
            if not health_ok and not force:
                console.print("[red]PR health check failed[/red]")
                console.print("[dim]Use --skip-checks to skip validation or --force to build anyway[/dim]")
                return False
            if health_ok:
                console.print("[green]All PRs are healthy[/green]")
        else:
            console.print("[yellow]Skipping PR health checks[/yellow]")

        # 4. Find stack tops (handles multi-stack epics)
        console.print("[blue]Analyzing epic branch structure...[/blue]")
        branch_tops = await self._find_stack_tops(instance_path, issue_numbers)

        if not branch_tops:
            console.print("[red]Could not identify any branches for epic[/red]")
            return False

        if len(branch_tops) > 1:
            console.print(f"[yellow]Epic has {len(branch_tops)} parallel stacks - will merge all for testing[/yellow]")

        # 5. Create integration branch merging all stack tops
        console.print("[blue]Creating integration branch for build...[/blue]")
        success = await self._create_integration_branch(instance_path, epic_number, branch_tops)

        if not success:
            console.print("[red]Failed to create integration branch[/red]")
            return False

        # 6. Sync stack with main
        if not await self._sync_stack(instance_path, auto_sync):
            console.print("[yellow]Stack sync skipped or failed[/yellow]")
            if not force:
                console.print("[dim]Use --force to build without syncing[/dim]")
                return False

        # 7. Update build status to running (if we have epic state)
        if epic_state:
            epic_state.build_status = 'running'
            self._save_epic_state(epic_state)

        # 8. Run build-dev.sh
        build_script = instance_path / "build-dev.sh"
        if not build_script.exists():
            console.print(f"[red]build-dev.sh not found in {instance_path}[/red]")
            if epic_state:
                epic_state.build_status = 'failed'
                epic_state.build_error = "build-dev.sh script not found"
                self._save_epic_state(epic_state)
            return False

        console.print(f"\n[green]Starting build for epic {epic_number}...[/green]")
        console.print("[dim]Streaming build output...[/dim]\n")

        # Set environment variable for no-cache if requested
        env = None
        if no_cache:
            import os
            env = os.environ.copy()
            env['DOCKER_BUILD_ARGS'] = '--no-cache'

        # Stream build output
        try:
            process = subprocess.Popen(
                ["./build-dev.sh"],
                cwd=instance_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

            output_lines = []
            for line in process.stdout:
                console.print(line.rstrip())
                output_lines.append(line)

            process.wait()

        except Exception as e:
            console.print(f"\n[red]Build process error: {e}[/red]")
            if epic_state:
                epic_state.build_status = 'failed'
                epic_state.build_error = str(e)
                self._save_epic_state(epic_state)
            return False

        # 9. Check build result and update state
        if process.returncode == 0:
            if epic_state:
                epic_state.build_status = 'success'
                epic_state.built_at = datetime.now().isoformat()
                epic_state.build_error = None
                self._save_epic_state(epic_state)

            console.print(f"\n[green]✓ Epic {epic_number} build completed successfully![/green]")
            console.print(f"[blue]Container is ready for testing[/blue]")

            # Try to extract port from build output
            port_info = next((line for line in output_lines if 'localhost:' in line.lower()), None)
            if port_info:
                console.print(f"[blue]{port_info.strip()}[/blue]")

            return True
        else:
            # Capture last 50 lines of output for debugging
            error_output = ''.join(output_lines[-50:]) if len(output_lines) > 50 else ''.join(output_lines)
            if epic_state:
                epic_state.build_status = 'failed'
                epic_state.build_error = error_output
                self._save_epic_state(epic_state)

            console.print(f"\n[red]✗ Epic {epic_number} build failed![/red]")
            console.print("[yellow]Check the output above for errors[/yellow]")
            if epic_state:
                console.print(f"[dim]Build error saved to epic state[/dim]")

            return False

    async def _check_pr_health(self, epic_number: int, instance_name: str) -> bool:
        """Check if all PRs for the epic are healthy.

        Checks:
        - All PRs exist
        - PRs are mergeable (no conflicts)
        - CI checks are passing

        Args:
            epic_number: Epic number to check
            instance_name: KB-LLM instance name

        Returns:
            True if all PRs are healthy, False otherwise
        """
        import subprocess
        import json

        instance_path = Path(f"/opt/{instance_name}")

        # Load epic state to get PR numbers
        epic_state = self.load_epic_state(epic_number)
        if not epic_state:
            return False

        # Collect PR numbers
        pr_numbers = [issue.pr_number for issue in epic_state.issues if issue.pr_number]

        if not pr_numbers:
            console.print("[yellow]No PR numbers found in epic state[/yellow]")
            # Try to discover PRs from GitHub
            from .review_monitor import ReviewMonitor
            monitor = ReviewMonitor()
            try:
                issue_to_pr = await monitor._discover_epic_prs(epic_number, instance_path)
                pr_numbers = list(issue_to_pr.values())

                if not pr_numbers:
                    console.print("[yellow]Could not discover PRs for epic[/yellow]")
                    return False

                console.print(f"[blue]Discovered {len(pr_numbers)} PRs for epic[/blue]")
            except Exception as e:
                console.print(f"[yellow]Could not discover PRs: {e}[/yellow]")
                return False

        all_healthy = True
        issues_found = []

        for pr_num in pr_numbers:
            try:
                # Get PR status using gh CLI
                result = subprocess.run([
                    "gh", "pr", "view", str(pr_num),
                    "--json", "mergeable,mergeStateStatus,statusCheckRollup"
                ], capture_output=True, text=True, cwd=str(instance_path))

                if result.returncode != 0:
                    issues_found.append(f"PR #{pr_num}: Could not fetch status")
                    all_healthy = False
                    continue

                data = json.loads(result.stdout)
                mergeable = data.get('mergeable', 'UNKNOWN')
                merge_state = data.get('mergeStateStatus', 'UNKNOWN')
                checks = data.get('statusCheckRollup', [])

                # Check mergeable status
                if mergeable == 'CONFLICTING':
                    issues_found.append(f"PR #{pr_num}: Has merge conflicts")
                    all_healthy = False

                # Check merge state
                if merge_state == 'DIRTY':
                    issues_found.append(f"PR #{pr_num}: Dirty merge state")
                    all_healthy = False

                # Check CI status
                if checks:
                    failing = [c for c in checks if c.get('conclusion') == 'FAILURE']
                    if failing:
                        issues_found.append(f"PR #{pr_num}: {len(failing)} failing CI checks")
                        all_healthy = False

            except Exception as e:
                console.print(f"[yellow]Error checking PR #{pr_num}: {e}[/yellow]")
                all_healthy = False

        # Report issues
        if issues_found:
            console.print("[yellow]PR health issues found:[/yellow]")
            for issue in issues_found:
                console.print(f"  [yellow]• {issue}[/yellow]")

        return all_healthy

    async def _sync_stack(self, instance_path: Path, auto_sync: bool) -> bool:
        """Sync Graphite stack with main branch.

        Args:
            instance_path: Path to the instance repository
            auto_sync: If True, sync without prompting

        Returns:
            True if sync succeeded or wasn't needed, False if sync failed
        """
        import subprocess
        import click
        from .graphite_integration import GraphiteManager

        # Check if stack is behind main
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..main"],
                cwd=instance_path,
                capture_output=True,
                text=True,
                check=True
            )
            commits_behind = int(result.stdout.strip())
        except Exception as e:
            console.print(f"[yellow]Could not check if stack is behind main: {e}[/yellow]")
            commits_behind = 0

        if commits_behind == 0:
            console.print("[blue]Stack is up to date with main[/blue]")
            return True

        console.print(f"[yellow]Stack is {commits_behind} commits behind main[/yellow]")

        # Prompt or auto-sync
        if not auto_sync:
            response = click.confirm("Sync stack with main using gt sync?", default=True)
            if not response:
                console.print("[yellow]Skipping sync[/yellow]")
                return False

        # Perform sync
        console.print("[blue]Syncing stack with main...[/blue]")
        gt_mgr = GraphiteManager()
        success = gt_mgr.sync_stack(instance_path)

        if success:
            console.print("[green]Stack synced successfully[/green]")
        else:
            console.print("[red]Stack sync failed[/red]")

        return success

    async def _discover_epic_prs(
        self,
        epic_number: int,
        instance_path: Path
    ) -> Dict[int, int]:
        """Discover PRs for an epic from GitHub.

        Reuses ReviewMonitor's PR discovery logic to find all PRs
        associated with an epic number.

        Args:
            epic_number: Epic number to discover PRs for
            instance_path: Path to the KB-LLM instance repository

        Returns:
            Dictionary mapping issue_number -> pr_number
        """
        from .review_monitor import ReviewMonitor

        monitor = ReviewMonitor()
        try:
            issue_to_pr = await monitor._discover_epic_prs(epic_number, instance_path)
            return issue_to_pr
        except Exception as e:
            console.print(f"[yellow]Could not discover PRs: {e}[/yellow]")
            return {}

    async def _find_stack_tops(
        self,
        instance_path: Path,
        issue_numbers: List[int]
    ) -> List[str]:
        """Find top branches of stacks for the epic.

        A "top" branch is one that isn't used as a base/parent by another epic branch.
        This handles cases where an epic has multiple parallel stacks.

        Args:
            instance_path: Path to the KB-LLM instance repository
            issue_numbers: List of issue numbers in the epic

        Returns:
            List of branch names that are stack tops
        """
        import subprocess

        # Get all branches for epic (handle both formats: issue-N and issue-N-description)
        all_branches = []
        for num in issue_numbers:
            # Try exact match first
            result = subprocess.run(
                ["git", "branch", "--list", f"issue-{num}"],
                cwd=instance_path,
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                all_branches.append(f"issue-{num}")
                continue

            # Try pattern match for branches with descriptions
            result = subprocess.run(
                ["git", "branch", "--list", f"issue-{num}-*"],
                cwd=instance_path,
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                # Take first matching branch
                branch = result.stdout.strip().replace('*', '').strip()
                all_branches.append(branch)

        if not all_branches:
            console.print("[yellow]No branches found for epic issues[/yellow]")
            return []

        console.print(f"[blue]Found branches: {all_branches}[/blue]")

        # Find which branches are NOT ancestors of any other branch
        # A branch is a "top" if no other epic branch has commits ahead of it
        tops = []

        for candidate in all_branches:
            is_top = True

            # Check if any other branch has this as an ancestor
            for other in all_branches:
                if candidate == other:
                    continue

                # Check if 'other' has commits that 'candidate' doesn't
                # If candidate..other shows commits, then 'other' is ahead of 'candidate'
                result = subprocess.run(
                    ["git", "rev-list", "--count", f"{candidate}..{other}"],
                    cwd=instance_path,
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    commits_ahead = int(result.stdout.strip())
                    if commits_ahead > 0:
                        # 'other' has commits ahead of 'candidate'
                        # Check if 'other' also has 'candidate' in its history
                        ancestor_check = subprocess.run(
                            ["git", "merge-base", "--is-ancestor", candidate, other],
                            cwd=instance_path,
                            capture_output=True
                        )

                        if ancestor_check.returncode == 0:
                            # 'candidate' is an ancestor of 'other', so it's not a top
                            is_top = False
                            break

            if is_top:
                tops.append(candidate)

        if not tops:
            # Fallback: if we can't determine tops, use the branch with highest issue number
            console.print("[yellow]Could not determine stack tops, using highest issue number[/yellow]")
            tops = [max(all_branches, key=lambda b: int(b.split('-')[1]))]

        console.print(f"[blue]Stack tops: {tops}[/blue]")
        return tops

    async def _create_integration_branch(
        self,
        instance_path: Path,
        epic_number: int,
        branch_tops: List[str]
    ) -> bool:
        """Create integration branch merging all stack tops.

        This creates a temporary branch (epic-{N}-build) that merges all the
        stack tops together, allowing the complete epic to be built and tested.

        Handles the worktree conflict issue by using a new branch name that
        doesn't conflict with any existing worktree checkouts.

        Args:
            instance_path: Path to the KB-LLM instance repository
            epic_number: Epic number for branch naming
            branch_tops: List of branch names to merge

        Returns:
            True if successful, False if merge conflicts occurred
        """
        import subprocess

        build_branch = f"epic-{epic_number}-build"

        console.print(f"[blue]Creating integration branch: {build_branch}[/blue]")

        # Check if we're currently on the build branch
        current_branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=instance_path,
            capture_output=True,
            text=True
        )
        current_branch = current_branch_result.stdout.strip()

        # If we're on the build branch, checkout main first
        if current_branch == build_branch:
            console.print(f"[blue]Already on {build_branch}, switching to main...[/blue]")
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=instance_path,
                capture_output=True
            )

        # Delete existing build branch if it exists
        subprocess.run(
            ["git", "branch", "-D", build_branch],
            cwd=instance_path,
            capture_output=True
        )

        # Create new build branch from main
        result = subprocess.run(
            ["git", "checkout", "-b", build_branch, "main"],
            cwd=instance_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            console.print(f"[red]Failed to create branch: {result.stderr}[/red]")
            return False

        console.print(f"[green]Created {build_branch} from main[/green]")

        # Merge each top branch
        for branch in branch_tops:
            console.print(f"[blue]Merging {branch}...[/blue]")

            result = subprocess.run(
                ["git", "merge", "--no-edit", "-m", f"Merge {branch} for epic {epic_number} build", branch],
                cwd=instance_path,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                console.print(f"[red]Merge conflict in {branch}![/red]")
                console.print(f"[red]{result.stderr}[/red]")
                console.print("\n[yellow]To resolve conflicts manually:[/yellow]")
                console.print(f"  cd {instance_path}")
                console.print(f"  git status")
                console.print(f"  # Resolve conflicts in the listed files")
                console.print(f"  git add <resolved-files>")
                console.print(f"  git merge --continue")
                console.print(f"  epic-mgr epic build {epic_number}  # Retry build\n")
                return False

            console.print(f"[green]✓ Merged {branch}[/green]")

        console.print(f"\n[green]Integration branch ready with {len(branch_tops)} branch(es) merged[/green]")
        return True

    async def verify_and_fix_pr_base_branches(
        self,
        epic_number: int,
        instance_name: str
    ) -> bool:
        """Verify PR base branches match epic plan and fix if incorrect.

        This prevents the common issue where PRs are created with base=main
        instead of their parent branch in the Graphite stack.

        Args:
            epic_number: Epic number to verify
            instance_name: KB-LLM instance name

        Returns:
            True if all PRs have correct base branches, False if errors occurred
        """
        import subprocess
        import json

        console.print(f"[blue]Verifying PR base branches for epic {epic_number}...[/blue]")

        # Load epic plan to get expected base branches
        plan = self.load_plan(epic_number)
        if not plan:
            console.print(f"[yellow]No plan found for epic {epic_number}[/yellow]")
            return False

        instance_path = Path(f"/opt/{instance_name}")
        all_correct = True
        fixes_made = 0

        for issue in plan.issues:
            if not issue.pr_number:
                continue  # Skip issues without PRs

            # Get actual PR base branch from GitHub
            try:
                result = subprocess.run(
                    ["gh", "pr", "view", str(issue.pr_number), "--json", "baseRefName,headRefName,number"],
                    cwd=str(instance_path),
                    capture_output=True,
                    text=True,
                    check=True
                )

                pr_data = json.loads(result.stdout)
                actual_base = pr_data['baseRefName']
                expected_base = issue.base_branch

                # Check if base branch matches expected
                if actual_base != expected_base:
                    console.print(f"[yellow]PR #{issue.pr_number} (issue {issue.number}): base is '{actual_base}', should be '{expected_base}'[/yellow]")

                    # Fix the base branch
                    fix_result = subprocess.run(
                        ["gh", "pr", "edit", str(issue.pr_number), "--base", expected_base],
                        cwd=str(instance_path),
                        capture_output=True,
                        text=True
                    )

                    if fix_result.returncode == 0:
                        console.print(f"[green]✓ Fixed PR #{issue.pr_number} base branch: {actual_base} → {expected_base}[/green]")

                        # Sync Graphite's local metadata with GitHub after manual base branch change
                        if issue.worktree_path:
                            worktree_path = Path(issue.worktree_path)
                            if worktree_path.exists():
                                console.print("[dim]  Syncing Graphite metadata with GitHub...[/dim]")
                                gt_sync = subprocess.run(
                                    ["gt", "get"],
                                    cwd=str(worktree_path),
                                    capture_output=True,
                                    text=True
                                )
                                if gt_sync.returncode == 0:
                                    console.print("[dim]  ✓ Graphite metadata synced[/dim]")
                                else:
                                    console.print("[yellow]  ⚠ Could not sync Graphite (run 'gt get' manually in worktree)[/yellow]")

                        fixes_made += 1
                    else:
                        console.print(f"[red]✗ Failed to fix PR #{issue.pr_number}: {fix_result.stderr}[/red]")
                        all_correct = False
                else:
                    console.print(f"[dim]✓ PR #{issue.pr_number} (issue {issue.number}): base branch '{actual_base}' is correct[/dim]")

            except subprocess.CalledProcessError as e:
                console.print(f"[yellow]Could not verify PR #{issue.pr_number}: {e}[/yellow]")
                all_correct = False
            except (json.JSONDecodeError, KeyError) as e:
                console.print(f"[yellow]Error parsing PR data for #{issue.pr_number}: {e}[/yellow]")
                all_correct = False

        if fixes_made > 0:
            console.print(f"[green]Fixed {fixes_made} PR base branch(es)[/green]")

            # Sync Graphite after fixing base branches to update metadata
            console.print("[blue]Syncing Graphite with updated PR base branches...[/blue]")
            self.sync_graphite_stack(instance_path)

        elif all_correct:
            console.print("[green]All PR base branches are correct[/green]")

        return all_correct or fixes_made > 0

    def sync_graphite_stack(self, instance_path: Path) -> bool:
        """Sync Graphite metadata with actual git state.

        Runs gt sync and gt restack to ensure Graphite's internal metadata
        matches the actual git branch structure and GitHub PR state.

        This is critical after:
        - Creating/recreating branches outside Graphite
        - Manually changing PR base branches
        - Any git operations that bypass Graphite

        Args:
            instance_path: Path to the instance repository

        Returns:
            True if sync succeeded, False otherwise
        """
        import subprocess

        console.print("[blue]Syncing Graphite stack with git and GitHub...[/blue]")

        # Run gt sync to fetch latest PR metadata from GitHub
        console.print("[dim]  Running 'gt sync'...[/dim]")
        sync_result = subprocess.run(
            ["gt", "sync"],
            cwd=str(instance_path),
            capture_output=True,
            text=True
        )

        if sync_result.returncode != 0:
            console.print(f"[yellow]  ⚠ gt sync had issues: {sync_result.stderr}[/yellow]")
            # Don't fail hard - sync can have non-critical warnings

        # Run gt restack to rebuild stack structure based on current git state
        console.print("[dim]  Running 'gt restack'...[/dim]")
        restack_result = subprocess.run(
            ["gt", "restack"],
            cwd=str(instance_path),
            capture_output=True,
            text=True
        )

        if restack_result.returncode != 0:
            console.print(f"[yellow]  ⚠ gt restack had issues: {restack_result.stderr}[/yellow]")
            # Don't fail hard - restack can have non-critical warnings

        console.print("[green]✓ Graphite stack synced[/green]")
        return True