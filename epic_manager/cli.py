#!/usr/bin/env python3
"""
Epic Manager CLI

Main command-line interface for Epic Manager using Click.
Provides commands for epic management, worktree operations, and monitoring.
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.table import Table

from . import __version__
from .orchestrator import EpicOrchestrator
from .workspace_manager import WorkspaceManager
from .instance_discovery import InstanceDiscovery
from .claude_automation import ClaudeSessionManager
from .graphite_integration import GraphiteManager
from .review_monitor import ReviewMonitor
# from .tui.dashboard import DashboardApp  # TUI disabled for testing

console = Console()


class Config:
    """Global configuration object passed between commands."""

    INSTANCE_FILE = Path("data/state/selected_instance")

    def __init__(self) -> None:
        self.config: dict = {}
        self.instance: Optional[str] = None
        self.verbose: bool = False
        self.load_config()
        self.load_selected_instance()

    def load_config(self) -> None:
        """Load configuration from YAML files."""
        config_paths = [
            Path("config/config.yaml"),
            Path("config/default_config.yaml"),
        ]

        for config_path in config_paths:
            if config_path.exists():
                with open(config_path) as f:
                    self.config = yaml.safe_load(f)
                break
        else:
            console.print("[red]Warning: No configuration file found[/red]")

    def load_selected_instance(self) -> None:
        """Load previously selected instance from state file."""
        if self.INSTANCE_FILE.exists():
            try:
                self.instance = self.INSTANCE_FILE.read_text().strip()
            except Exception:
                # Ignore errors loading instance file
                pass

    def save_selected_instance(self, instance_name: str) -> None:
        """Save selected instance to state file.

        Args:
            instance_name: Name of the instance to save
        """
        try:
            # Ensure data/state directory exists
            self.INSTANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.INSTANCE_FILE.write_text(instance_name)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save instance selection: {e}[/yellow]")


pass_config = click.make_pass_decorator(Config, ensure=True)


# Helper functions for status display
def _get_status_emoji(status: str) -> str:
    """Map status string to emoji symbol.

    Args:
        status: Status string (pending, in_progress, review, completed, etc.)

    Returns:
        Emoji representing the status
    """
    status_map = {
        'completed': '✓',
        'in_progress': '⏳',
        'review': '👀',
        'pending': '○',
        'blocked': '🔴',
        'paused': '⏸️',
        'active': '▶️',
        'planning': '📋'
    }
    return status_map.get(status.lower(), '?')


def _calculate_progress(issues: list) -> tuple:
    """Calculate progress statistics for a list of issues.

    Args:
        issues: List of EpicIssue objects

    Returns:
        Tuple of (completed_count, total_count, progress_string)
    """
    total = len(issues)
    completed = sum(1 for issue in issues if issue.status == 'completed')

    # Create visual progress string
    progress_str = ''
    for issue in issues:
        progress_str += _get_status_emoji(issue.status)

    return (completed, total, progress_str)


def _format_epic_summary_table(epics: list) -> Table:
    """Create summary table for all active epics.

    Args:
        epics: List of EpicState objects

    Returns:
        Rich Table with epic summaries
    """
    table = Table(title="Active Epics")
    table.add_column("Epic", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Instance", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Progress", style="green", justify="right")
    table.add_column("Issues", style="magenta")

    for epic in epics:
        completed, total, progress_str = _calculate_progress(epic.issues)
        progress_pct = f"{completed}/{total}"

        table.add_row(
            str(epic.number),
            epic.title[:40] + "..." if len(epic.title) > 40 else epic.title,
            epic.instance,
            f"{_get_status_emoji(epic.status)} {epic.status}",
            progress_pct,
            progress_str
        )

    return table


def _format_epic_detail(epic_state) -> None:
    """Display detailed view of a single epic.

    Args:
        epic_state: EpicState object to display
    """
    # Epic header
    console.print(f"\n[bold cyan]Epic #{epic_state.number}:[/bold cyan] {epic_state.title}")
    console.print(f"[blue]Instance:[/blue] {epic_state.instance}")
    console.print(f"[yellow]Status:[/yellow] {_get_status_emoji(epic_state.status)} {epic_state.status}")

    if epic_state.created_at:
        console.print(f"[dim]Created:[/dim] {epic_state.created_at}")
    if epic_state.updated_at:
        console.print(f"[dim]Updated:[/dim] {epic_state.updated_at}")

    # Issues table
    completed, total, _ = _calculate_progress(epic_state.issues)
    console.print(f"\n[bold]Progress:[/bold] {completed}/{total} issues completed")

    table = Table(title="Issues")
    table.add_column("Issue", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("Worktree", style="blue")
    table.add_column("PR", style="green")

    for issue in epic_state.issues:
        worktree = issue.worktree_path if issue.worktree_path else "-"
        pr = f"#{issue.pr_number}" if issue.pr_number else "-"

        table.add_row(
            f"#{issue.number}",
            issue.title[:50] + "..." if len(issue.title) > 50 else issue.title,
            f"{_get_status_emoji(issue.status)} {issue.status}",
            worktree,
            pr
        )

    console.print(table)


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--instance", "-i", help="Target KB-LLM instance")
@pass_config
def main(config: Config, verbose: bool, instance: Optional[str]) -> None:
    """Epic Manager - Centralized workflow automation tool."""
    config.verbose = verbose
    # Only override instance if explicitly provided via --instance flag
    if instance is not None:
        config.instance = instance


@main.group()
def epic() -> None:
    """Epic management commands."""
    pass


@epic.command()
@click.argument("epic_number", type=int)
@pass_config
def start(config: Config, epic_number: int) -> None:
    """Start complete epic workflow: analysis, worktrees, and parallel TDD development."""
    if not config.instance:
        console.print("[red]No instance selected. Use 'epic-mgr select <instance>' first.[/red]")
        return

    console.print(f"[green]Starting epic {epic_number} on {config.instance}[/green]")

    async def run_epic():
        try:
            orchestrator = EpicOrchestrator()
            success = await orchestrator.run_complete_epic(epic_number, config.instance)

            if success:
                console.print(f"[green]Epic {epic_number} completed successfully[/green]")
            else:
                console.print(f"[red]Epic {epic_number} failed[/red]")

            return success

        except Exception as e:
            console.print(f"[red]Error running epic: {e}[/red]")
            if config.verbose:
                raise
            return False

    # Run the async workflow
    success = asyncio.run(run_epic())

    if not success:
        sys.exit(1)


@epic.command()
@click.option("--epic", "-e", type=int, help="Show detailed status for specific epic")
@pass_config
def status(config: Config, epic: Optional[int]) -> None:
    """Show status of all active epics across instances."""
    try:
        orchestrator = EpicOrchestrator()

        # Show specific epic details if requested
        if epic:
            epic_state = orchestrator.load_epic_state(epic)
            if not epic_state:
                console.print(f"[red]Epic {epic} not found[/red]")
                return

            _format_epic_detail(epic_state)
            return

        # Show summary of all active epics
        active_epics = orchestrator.list_active_epics()

        if not active_epics:
            console.print("[yellow]No active epics found[/yellow]")
            console.print("[dim]Run 'epic-mgr epic start <epic_number>' to begin an epic[/dim]")
            return

        table = _format_epic_summary_table(active_epics)
        console.print(table)

        # Show helpful hint
        console.print("\n[dim]Use --epic <number> to see detailed status for a specific epic[/dim]")

    except Exception as e:
        console.print(f"[red]Error displaying epic status: {e}[/red]")
        if config.verbose:
            raise


@epic.command()
@click.argument("epic_number", type=int)
@click.option("--force", "-f", is_flag=True, help="Force cleanup even if worktrees have commits")
@pass_config
def cleanup(config: Config, epic_number: int, force: bool) -> None:
    """Cleanup worktrees for an epic.

    By default, only cleans up worktrees with no commits (failed runs).
    Use --force to cleanup all worktrees regardless of state.
    """
    console.print(f"[green]Cleaning up epic {epic_number} worktrees[/green]")

    try:
        orchestrator = EpicOrchestrator()
        workspace_mgr = WorkspaceManager()

        # Load epic state to find worktrees
        epic_state = orchestrator.load_epic_state(epic_number)
        if not epic_state:
            console.print(f"[red]Epic {epic_number} not found[/red]")
            return

        cleaned_count = 0
        skipped_count = 0
        error_count = 0

        for issue in epic_state.issues:
            if not issue.worktree_path:
                continue

            worktree_path = Path(issue.worktree_path)

            if not worktree_path.exists():
                console.print(f"[dim]Skipping issue {issue.number}: worktree doesn't exist[/dim]")
                continue

            # Check if worktree has commits
            commit_count = workspace_mgr.get_worktree_commit_count(worktree_path)

            if commit_count > 0 and not force:
                console.print(f"[yellow]Skipping issue {issue.number}: has {commit_count} commit(s) (use --force to cleanup)[/yellow]")
                skipped_count += 1
                continue

            # Cleanup the worktree
            console.print(f"[blue]Cleaning up worktree for issue {issue.number}...[/blue]")
            success = workspace_mgr.cleanup_worktree(worktree_path, force=force)

            if success:
                cleaned_count += 1
                # Clear worktree path from state
                issue.worktree_path = None
            else:
                error_count += 1

        # Save updated epic state
        if cleaned_count > 0:
            orchestrator._save_epic_state(epic_state)

        # Summary
        console.print(f"\n[green]Cleanup complete:[/green]")
        console.print(f"  Cleaned: {cleaned_count}")
        console.print(f"  Skipped: {skipped_count}")
        console.print(f"  Errors: {error_count}")

    except Exception as e:
        console.print(f"[red]Error during cleanup: {e}[/red]")
        if config.verbose:
            raise


@epic.command()
@click.argument("epic_number", type=int)
@pass_config
def stop(config: Config, epic_number: int) -> None:
    """Stop epic and cleanup worktrees (alias for cleanup)."""
    # Call cleanup without force
    from click.testing import CliRunner
    runner = CliRunner()
    runner.invoke(cleanup, [str(epic_number)], obj=config)


@epic.command()
@click.argument("epic_number", type=int)
@click.option("--auto-sync", is_flag=True, help="Automatically sync stack with main (no prompt)")
@click.option("--skip-checks", is_flag=True, help="Skip PR health validation")
@click.option("--force", "-f", is_flag=True, help="Force build even if validation fails")
@click.option("--no-cache", is_flag=True, help="Build without Docker cache")
@pass_config
def build(config: Config, epic_number: int, auto_sync: bool, skip_checks: bool, force: bool, no_cache: bool) -> None:
    """Build epic to Docker container for pre-merge testing.

    Builds the complete epic in a container to validate functionality before merging PRs to main.
    This enables bug testing and iteration in an isolated environment.

    The build process:
    1. Validates all epic issues are completed
    2. Checks PR health (mergeable status, CI checks)
    3. Syncs the Graphite stack with latest main
    4. Checks out the top stack branch
    5. Runs build-dev.sh to create Docker container
    6. Streams build output and tracks status
    """
    if not config.instance:
        console.print("[red]No instance selected. Use 'epic-mgr select <instance>' first.[/red]")
        return

    console.print(f"[green]Building epic {epic_number} on {config.instance}[/green]")

    async def run_build():
        try:
            orchestrator = EpicOrchestrator()
            success = await orchestrator.build_epic_container(
                epic_number,
                config.instance,
                auto_sync=auto_sync,
                skip_checks=skip_checks,
                force=force,
                no_cache=no_cache
            )

            if success:
                console.print(f"[green]Epic {epic_number} build completed successfully[/green]")
            else:
                console.print(f"[red]Epic {epic_number} build failed[/red]")

            return success

        except Exception as e:
            console.print(f"[red]Error building epic: {e}[/red]")
            if config.verbose:
                raise
            return False

    # Run the async workflow
    success = asyncio.run(run_build())

    if not success:
        sys.exit(1)


@main.group()
def work() -> None:
    """Worktree and issue management commands."""
    pass


@work.command()
@click.argument("issue_number", type=int)
@click.option("--epic", type=int, help="Epic number (required for worktree creation)")
@pass_config
def issue(config: Config, issue_number: int, epic: Optional[int]) -> None:
    """Work on issue in isolated worktree."""
    if not config.instance:
        console.print("[red]No instance selected. Use 'epic-mgr select <instance>' first.[/red]")
        return

    if not epic:
        console.print("[red]Epic number required. Use --epic <number>[/red]")
        return

    console.print(f"[green]Working on issue {issue_number} in epic {epic}[/green]")

    try:
        workspace_mgr = WorkspaceManager()

        # Create or reuse worktree for the issue
        worktree_path = workspace_mgr.create_or_reuse_worktree(
            instance_name=config.instance,
            epic_num=epic,
            issue_num=issue_number
        )

        console.print(f"[blue]Worktree created: {worktree_path}[/blue]")
        console.print("[blue]You can now work in this isolated environment[/blue]")

    except Exception as e:
        console.print(f"[red]Error creating worktree: {e}[/red]")
        if config.verbose:
            raise


@work.command()
@pass_config
def list(config: Config) -> None:
    """List all active worktrees."""
    console.print("[green]Active Worktrees[/green]")

    try:
        workspace_mgr = WorkspaceManager()
        worktrees = workspace_mgr.list_worktrees(config.instance)

        if not worktrees:
            console.print("[yellow]No active worktrees found[/yellow]")
            return

        for name, info in worktrees.items():
            console.print(f"  [blue]{name}[/blue]")
            console.print(f"    Path: {info.get('worktree', 'Unknown')}")
            console.print(f"    Branch: {info.get('branch', 'Unknown')}")
            console.print(f"    Instance: {info.get('instance', 'Unknown')}")
            console.print()

    except Exception as e:
        console.print(f"[red]Error listing worktrees: {e}[/red]")
        if config.verbose:
            raise


@work.command()
@click.argument("worktree_name")
@pass_config
def cleanup(config: Config, worktree_name: str) -> None:
    """Cleanup specific worktree."""
    # TODO: Implement worktree cleanup
    console.print(f"[yellow]Cleaning up worktree: {worktree_name}[/yellow]")
    raise NotImplementedError("Worktree cleanup not yet implemented")


@main.group()
def stack() -> None:
    """Graphite stack management commands."""
    pass


@stack.command()
@pass_config
def sync(config: Config) -> None:
    """Sync and restack all worktrees."""
    # TODO: Implement stack synchronization
    console.print("[green]Syncing Graphite stacks[/green]")
    raise NotImplementedError("Stack synchronization not yet implemented")


@stack.command()
@pass_config
def status(config: Config) -> None:
    """Show current Graphite stack status."""
    # TODO: Implement stack status display
    console.print("[green]Stack Status[/green]")
    raise NotImplementedError("Stack status display not yet implemented")


@stack.command()
@click.argument("epic_number", type=int)
@pass_config
def health(config: Config, epic_number: int) -> None:
    """Check health of all PRs in an epic stack.

    Displays mergeable status, conflicts, and CI check results for all PRs.
    """
    if not config.instance:
        console.print("[red]No instance selected. Use 'epic-mgr select <instance>' first.[/red]")
        return

    async def check_health():
        try:
            from pathlib import Path
            from .review_monitor import ReviewMonitor

            instance_path = Path(f"/opt/{config.instance}")
            monitor = ReviewMonitor()

            console.print(f"\n[bold cyan]Stack Health Check for Epic #{epic_number}[/bold cyan]")
            console.print(f"[dim]Instance: {config.instance}[/dim]\n")

            # Discover PRs for the epic
            issue_to_pr = await monitor._discover_epic_prs(epic_number, instance_path)

            if not issue_to_pr:
                console.print("[yellow]No PRs found for this epic[/yellow]")
                return

            # Check health of each PR
            import subprocess
            import json

            table = Table(title=f"Epic #{epic_number} PR Health")
            table.add_column("PR", style="cyan", no_wrap=True)
            table.add_column("Issue", style="blue")
            table.add_column("Mergeable", style="white")
            table.add_column("State", style="yellow")
            table.add_column("CI Checks", style="green")

            all_healthy = True

            for issue_num, pr_num in sorted(issue_to_pr.items()):
                try:
                    # Get PR status
                    result = subprocess.run([
                        "gh", "pr", "view", str(pr_num),
                        "--json", "mergeable,mergeStateStatus,statusCheckRollup"
                    ], capture_output=True, text=True, cwd=str(instance_path))

                    if result.returncode != 0:
                        table.add_row(
                            f"#{pr_num}",
                            f"#{issue_num}",
                            "[red]ERROR[/red]",
                            "-",
                            "-"
                        )
                        all_healthy = False
                        continue

                    data = json.loads(result.stdout)
                    mergeable = data.get('mergeable', 'UNKNOWN')
                    merge_state = data.get('mergeStateStatus', 'UNKNOWN')
                    checks = data.get('statusCheckRollup', [])

                    # Format mergeable status
                    if mergeable == 'MERGEABLE':
                        mergeable_str = "[green]✓ Yes[/green]"
                    elif mergeable == 'CONFLICTING':
                        mergeable_str = "[red]✗ Conflict[/red]"
                        all_healthy = False
                    else:
                        mergeable_str = f"[yellow]{mergeable}[/yellow]"

                    # Format merge state
                    if merge_state == 'CLEAN':
                        state_str = "[green]Clean[/green]"
                    elif merge_state == 'DIRTY':
                        state_str = "[red]Dirty[/red]"
                        all_healthy = False
                    elif merge_state == 'UNSTABLE':
                        state_str = "[yellow]Unstable[/yellow]"
                    else:
                        state_str = f"[dim]{merge_state}[/dim]"

                    # Check CI status
                    if not checks:
                        checks_str = "[dim]No checks[/dim]"
                    else:
                        passing = sum(1 for c in checks if c.get('conclusion') == 'SUCCESS')
                        failing = sum(1 for c in checks if c.get('conclusion') == 'FAILURE')
                        pending = sum(1 for c in checks if c.get('conclusion') is None)

                        if failing > 0:
                            checks_str = f"[red]{failing} fail[/red]"
                            if passing > 0:
                                checks_str += f", [green]{passing} pass[/green]"
                            if pending > 0:
                                checks_str += f", [yellow]{pending} pending[/yellow]"
                            all_healthy = False
                        elif pending > 0:
                            checks_str = f"[yellow]{pending} pending[/yellow]"
                            if passing > 0:
                                checks_str += f", [green]{passing} pass[/green]"
                        elif passing > 0:
                            checks_str = f"[green]{passing} pass[/green]"
                        else:
                            checks_str = "[dim]Unknown[/dim]"

                    table.add_row(
                        f"#{pr_num}",
                        f"#{issue_num}",
                        mergeable_str,
                        state_str,
                        checks_str
                    )

                except Exception as e:
                    console.print(f"[yellow]Error checking PR #{pr_num}: {e}[/yellow]")
                    all_healthy = False

            console.print(table)
            console.print()

            if all_healthy:
                console.print("[green]✓ All PRs are healthy and ready to merge![/green]")
            else:
                console.print("[yellow]⚠ Some PRs need attention (conflicts or failing checks)[/yellow]")

        except Exception as e:
            console.print(f"[red]Error checking stack health: {e}[/red]")
            if config.verbose:
                raise

    asyncio.run(check_health())


@main.group()
def review() -> None:
    """Code review management commands."""
    pass


@review.command()
@click.argument("pr_number", type=int)
@pass_config
def pr(config: Config, pr_number: int) -> None:
    """Review PR in separate worktree."""
    # TODO: Implement PR review workflow
    console.print(f"[green]Reviewing PR {pr_number}[/green]")
    raise NotImplementedError("PR review workflow not yet implemented")


@review.command()
@click.argument("epic_number", type=int)
@pass_config
def monitor(config: Config, epic_number: int) -> None:
    """Monitor PRs for an epic and auto-fix CodeRabbit reviews."""
    if not config.instance:
        console.print("[red]No instance selected. Use 'epic-mgr select <instance>' first.[/red]")
        return

    async def run_monitor():
        try:
            # Create orchestrator with instance-specific state directory
            instance_path = Path(f"/opt/{config.instance}")
            state_dir = instance_path / "data" / "state"
            orchestrator = EpicOrchestrator(state_dir=str(state_dir))
            monitor = ReviewMonitor()

            # Try to load the epic plan (for managed epics)
            plan = orchestrator.load_plan(epic_number)

            if plan:
                console.print(f"[blue]Found epic plan - using managed workflow[/blue]")

                # Find worktrees for the epic
                workspace_mgr = WorkspaceManager()
                worktrees = {}

                for issue in plan.issues:
                    if issue.worktree_path:
                        worktrees[issue.number] = Path(issue.worktree_path)

                # Check if we have PR numbers populated
                prs_in_plan = [issue.pr_number for issue in plan.issues if issue.pr_number]

                if not prs_in_plan:
                    console.print(f"[yellow]No PR numbers in plan - discovering from GitHub...[/yellow]")
                    # Discover PRs and update plan
                    instance_path = Path(f"/opt/{config.instance}")
                    issue_to_pr = await monitor._discover_epic_prs(epic_number, instance_path)

                    if not issue_to_pr:
                        console.print("[yellow]No PRs found for this epic[/yellow]")
                        return

                    # Update plan with discovered PR numbers
                    for issue in plan.issues:
                        if issue.number in issue_to_pr:
                            issue.pr_number = issue_to_pr[issue.number]

                    # Save updated plan
                    orchestrator._save_plan(plan)
                    console.print(f"[green]Updated plan with {len(issue_to_pr)} PR numbers[/green]")

                if not worktrees:
                    console.print(f"[yellow]No worktrees found - monitoring without auto-fix[/yellow]")
                    # Monitor without worktrees (can't auto-fix)
                    await monitor.monitor_epic_by_discovery(epic_number, config.instance, instance_path)
                else:
                    # Use plan-based monitoring with worktrees
                    await monitor.monitor_epic_reviews(plan, worktrees, instance_path)
            else:
                console.print(f"[blue]No epic plan found - discovering PRs from GitHub[/blue]")

                # Use discovery-based monitoring
                instance_path = Path(f"/opt/{config.instance}")
                await monitor.monitor_epic_by_discovery(epic_number, config.instance, instance_path)

        except KeyboardInterrupt:
            console.print("\n[yellow]Review monitoring stopped[/yellow]")
        except Exception as e:
            console.print(f"[red]Error in review monitoring: {e}[/red]")
            if config.verbose:
                raise

    console.print(f"[green]Starting review monitoring for epic {epic_number}[/green]")
    console.print("[blue]Press Ctrl+C to stop monitoring[/blue]")

    asyncio.run(run_monitor())


@main.command()
@pass_config
def dashboard(config: Config) -> None:
    """Launch interactive TUI dashboard."""
    # TODO: Launch TUI dashboard
    console.print("[green]Launching dashboard[/green]")

    try:
        app = DashboardApp()
        app.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard closed[/yellow]")
    except Exception as e:
        console.print(f"[red]Dashboard error: {e}[/red]")
        if config.verbose:
            raise


@main.command()
@pass_config
def instances(config: Config) -> None:
    """List discovered KB-LLM instances."""
    # TODO: Implement instance discovery and listing
    console.print("[green]Discovered Instances[/green]")

    try:
        discovery = InstanceDiscovery()
        instances = discovery.discover_instances()

        if not instances:
            console.print("[yellow]No KB-LLM instances found[/yellow]")
            return

        for name, info in instances.items():
            console.print(f"  [blue]{name}[/blue]: {info.get('path', 'Unknown path')}")

    except Exception as e:
        console.print(f"[red]Error discovering instances: {e}[/red]")
        if config.verbose:
            raise


@main.command()
@click.argument("instance_name")
@pass_config
def select(config: Config, instance_name: str) -> None:
    """Select default instance for operations."""
    config.instance = instance_name
    config.save_selected_instance(instance_name)
    console.print(f"[green]Selected instance: {instance_name}[/green]")
    console.print("[dim]Instance selection saved. It will be used for subsequent commands.[/dim]")


if __name__ == "__main__":
    main()