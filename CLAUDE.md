# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Epic Manager is a standalone orchestration tool that coordinates epic-based development workflows across multiple KB-LLM instances. It manages parallel development via git worktrees, Graphite stacked PRs, automated Claude Code TDD workflows, and CodeRabbit review integration.

**Key Concepts:**
- **Centralized orchestration**: Single tool at `/opt/epic-manager` manages multiple KB-LLM instances at `/opt/{instance-name}`
- **Worktree-based parallelization**: Creates isolated workspaces in `/opt/work/{instance}-epic-{N}/issue-{M}` for concurrent development
- **Graphite stacked PRs**: Issues create PRs with proper dependency chains using `gt` CLI
- **Claude Code SDK integration**: Launches automated TDD workflows in isolated worktrees
- **Plan-driven coordination**: Uses JSON plans from `/epic-plan` command to orchestrate multi-issue workflows

## Development Environment

### Installation

```bash
cd /opt/epic-manager
pip install -e .                    # Install in editable mode
pip install -e ".[dev]"            # Include dev dependencies
```

### Running Commands

```bash
epic-mgr --version                  # Verify installation
epic-mgr instances                  # Discover KB-LLM instances
epic-mgr select <instance>          # Set active instance
```

### Testing

```bash
# Run full test suite
pytest

# Run with coverage
pytest --cov=epic_manager --cov-report=html

# Run specific test file
pytest tests/test_orchestrator.py

# Run specific test function
pytest tests/test_workspace_manager.py::TestWorkspaceManager::test_create_issue_worktree
```

### Code Quality

```bash
# Format code (applies changes)
black epic_manager/ tests/

# Sort imports (applies changes)
isort epic_manager/ tests/

# Type checking (analysis only)
mypy epic_manager/

# Linting (analysis only)
flake8 epic_manager/ tests/
```

**Important**: Always run `black` and `isort` before committing changes.

## Architecture

### Module Structure

The codebase follows a modular architecture with clear separation of concerns:

```
epic_manager/
├── cli.py                    # Click-based CLI commands (main entry point)
├── orchestrator.py           # Epic workflow coordination and state management
├── workspace_manager.py      # Git worktree operations (create, list, cleanup)
├── instance_discovery.py     # Auto-discover KB-LLM deployments in /opt/
├── graphite_integration.py   # Graphite stack operations (sync, restack, status)
├── claude_automation.py      # Claude Code SDK wrapper for TDD workflows
├── review_monitor.py         # CodeRabbit review polling and auto-fix workflows
├── models.py                 # Data models (EpicPlan, IssueInfo, WorkflowResult)
└── tui/                      # Textual-based terminal UI components
    ├── dashboard.py          # Real-time monitoring dashboard
    ├── stack_viewer.py       # Graphite stack visualization
    └── progress_tracker.py   # Epic progress display
```

### Data Flow: Epic Workflow Execution

1. **CLI entry** (`cli.py`): User runs `epic-mgr epic start 355`
2. **Orchestrator** (`orchestrator.py`): Coordinates the workflow
   - Calls `analyze_epic()` to get JSON plan from Claude Code
   - Parses JSON into `EpicPlan` model (defines phases and dependencies)
   - Calls `create_worktrees_for_plan()` to create isolated environments
   - Calls `start_development()` to launch phase-based execution
3. **Workspace Manager** (`workspace_manager.py`): Creates worktrees
   - For each issue: `git worktree add -b issue-{N} {path} {base_branch}`
   - Tracks worktrees via `git worktree list --porcelain`
4. **Claude Automation** (`claude_automation.py`): Launches TDD workflows
   - Uses Claude Code SDK to run `/graphite-tdd {issue_number}` in each worktree
   - Streams progress output to console
   - Returns `WorkflowResult` with success status and timing
5. **Graphite Integration** (`graphite_integration.py`): Manages PR stacks
   - Creates stacked PRs with proper base branches
   - Syncs and restacks when main branch changes
6. **Review Monitor** (`review_monitor.py`): Handles CodeRabbit feedback
   - Polls GitHub API for CodeRabbit comments (60s intervals)
   - Creates review fix worktrees when comments appear
   - Launches Claude Code to address feedback automatically

### State Management

Epic state is persisted in `data/state/`:
- `epic-{N}.json`: Tracks epic status, issue statuses, worktree paths, PR numbers
- `epic-{N}-plan.json`: Stores original plan from Claude Code with phase information

### Key Design Patterns

**Plan-driven coordination**: The `EpicPlan` model (from Claude's `/epic-plan` output) encodes all coordination logic:
- `issues`: List with `base_branch` field for dependency relationships
- `parallelization`: Dict mapping phases to issue numbers for sequential execution
- Issues in same phase run in parallel; phases execute sequentially

**Async concurrency**: `asyncio` with semaphores for controlled parallelism:
```python
# Example: Run 3 concurrent Claude Code sessions
results = await claude_mgr.run_parallel_tdd_workflows(
    phase_tasks,
    max_concurrent=3
)
```

**Git worktree isolation**: Each issue gets a dedicated worktree:
```bash
# Base repo remains at /opt/scottbot
# Worktree created at /opt/work/scottbot-epic-355/issue-351
git -C /opt/scottbot worktree add -b issue-351 /opt/work/scottbot-epic-355/issue-351 main
```

## Common Development Tasks

### Adding a New CLI Command

1. Add command function to `epic_manager/cli.py`:
```python
@main.command()
@click.argument("arg_name")
@pass_config
def new_command(config: Config, arg_name: str) -> None:
    """Command description."""
    # Implementation
```

2. Add corresponding logic to appropriate module (e.g., `orchestrator.py`)
3. Add tests to `tests/test_cli.py` using Click's `CliRunner`

### Extending the EpicPlan Model

When Claude's `/epic-plan` output changes:
1. Update `epic_manager/models.py` dataclasses
2. Update `from_json()` and `save()` methods
3. Update tests in `tests/test_orchestrator.py`
4. Update state file schema version if needed

### Adding New Claude Code Workflows

1. Add method to `ClaudeSessionManager` in `claude_automation.py`:
```python
async def launch_new_workflow(self, worktree_path: Path, issue_number: int) -> WorkflowResult:
    """Launch custom workflow."""
    options = ClaudeAgentOptions(cwd=str(worktree_path))
    async with ClaudeSDKClient(options=options) as client:
        await client.query(f"/custom-workflow {issue_number}")
        # Handle response streaming
```

2. Add tests using mocked `ClaudeSDKClient`

## Critical Implementation Notes

### Worktree Base Branches

**CRITICAL**: When creating worktrees, the `base_branch` parameter determines dependencies:
```python
# Issue 352 depends on issue 351
workspace_mgr.create_issue_worktree(
    instance_name="scottbot",
    epic_num=355,
    issue_num=352,
    base_branch="issue-351"  # NOT "main" - this creates the dependency chain
)
```

This ensures Graphite stacks work correctly with proper branch ancestry.

### Claude Agent SDK Integration

The project uses `claude-agent-sdk` (installable via `pip install claude-agent-sdk`):
- Import check pattern used: `try/except ImportError` with runtime validation
- Always use `ClaudeAgentOptions(cwd=...)` to specify working directory context
- Use `async with ClaudeSDKClient` for proper session lifecycle
- Stream responses with `async for message in client.receive_response()`

### Graphite CLI Usage

All `gt` commands run in worktree directories:
```bash
cd /opt/work/scottbot-epic-355/issue-351
gt track issue-351              # Track branch in Graphite
gt submit --title "..." --body "..."  # Create stacked PR
gt sync                         # Sync with main and restack
```

### Async Error Handling

All async workflows use structured error handling:
```python
try:
    result = await orchestrator.run_complete_epic(epic_number, instance_name)
    return result
except Exception as e:
    console.print(f"[red]Epic {epic_number} failed: {e}[/red]")
    if config.verbose:
        raise  # Re-raise for debugging
    return False
```

### Testing with Pytest Fixtures

Use pytest fixtures from `tests/conftest.py`:
- `temp_repo`: Creates temporary git repository
- `mock_claude_client`: Mocks Claude Code SDK client
- `mock_workspace`: Mocks worktree creation

Example:
```python
def test_create_worktree(temp_repo):
    workspace_mgr = WorkspaceManager(work_base_path=temp_repo / "work")
    worktree = workspace_mgr.create_issue_worktree("test", 1, 101)
    assert worktree.exists()
```

## Configuration

Configuration is loaded from `config/default_config.yaml` or `config/config.yaml` (user overrides).

Key settings:
- `discovery.search_paths`: Directories to scan for KB-LLM instances (default: `/opt/`)
- `workspace.base_path`: Root for worktrees (default: `/opt/work`)
- `claude.max_concurrent_sessions`: Parallel TDD workflow limit (default: 3)
- `reviews.poll_interval_seconds`: CodeRabbit check frequency (default: 60)

## Project Status

**Current Phase**: Early implementation stage with scaffolded modules and comprehensive test infrastructure.

**Implemented**:
- Complete module structure with type hints
- CLI command framework with Click
- Core data models (EpicPlan, WorkflowResult)
- Basic workspace management (worktree creation and listing)
- Epic orchestration skeleton with state persistence
- Test infrastructure with pytest fixtures

**In Progress**:
- Claude Code SDK integration for automated TDD workflows
- Graphite integration for stack operations
- Review monitoring and auto-fix workflows
- TUI dashboard implementation

**Testing Approach**: Following TDD methodology - write tests first, then implement incrementally.