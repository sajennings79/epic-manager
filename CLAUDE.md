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

# Epic workflow commands
epic-mgr epic start <epic_number>     # Start epic with automated TDD
epic-mgr epic status                  # Show all active epics
epic-mgr epic verify-prs <epic_number> # Verify/fix PR base branches
epic-mgr epic build <epic_number>     # Build epic in Docker for pre-merge testing
epic-mgr epic cleanup <epic_number>   # Cleanup worktrees

# Stack management commands
epic-mgr stack sync                 # Sync all worktrees with main
epic-mgr stack sync -i <instance>   # Sync specific instance
epic-mgr stack sync -e <epic>       # Sync specific epic
epic-mgr stack sync --dry-run       # Preview sync without changes
epic-mgr stack health <epic>        # Check PR health for epic
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
7. **PR Base Branch Verification** (`orchestrator.py`): Ensures stack integrity
   - Automatically verifies PR base branches after creation
   - Fixes PRs that incorrectly target `main` instead of parent branch
   - Prevents broken Graphite stacks on GitHub
   - Can be manually triggered: `epic-mgr epic verify-prs <epic_number>`

### PR Base Branch Verification

**Problem**: When PRs are created via `gt submit`, they sometimes target `main` instead of the parent branch in the stack, breaking Graphite's stack visualization on GitHub.

**Solution**: Epic Manager automatically verifies and fixes PR base branches:

```bash
# Automatic verification during TDD workflow (Claude checks after creating PR)
# Step 9 in TDD_WORKFLOW_PROMPT verifies base branch and fixes if needed

# Manual verification for existing epics
epic-mgr epic verify-prs 580

# Example output:
# ✓ PR #586 (issue 581): base branch 'main' is correct
# ⚠ PR #587 (issue 582): base is 'main', should be 'issue-581'
# ✓ Fixed PR #587 base branch: main → issue-581
```

**How it works**:
1. Loads epic plan to get expected base branches for each issue
2. For each PR, fetches actual base branch from GitHub via `gh pr view`
3. Compares actual vs. expected base branch
4. If mismatch detected, runs `gh pr edit <PR> --base <correct-branch>`
5. Reports fixes made

**When it runs**:
- Automatically: During TDD workflow after PR creation (Step 9 in prompt)
- Manually: Run `epic-mgr epic verify-prs <epic_number>` anytime
- Recommended: After any manual PR creation or stack reordering

### State Management

Epic state is persisted in each instance's hidden `.epic-mgr/state/` directory:
- `{instance}/.epic-mgr/state/epic-{N}.json`: Tracks epic status, issue statuses, worktree paths, PR numbers
- `{instance}/.epic-mgr/state/epic-{N}-plan.json`: Stores original plan from Claude Code with phase information

For example, epic 355 for the `scottbot` instance would store state in:
- `/opt/scottbot/.epic-mgr/state/epic-355.json`
- `/opt/scottbot/.epic-mgr/state/epic-355-plan.json`

This ensures state files have the same permissions as the instance they manage.

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

## Epic Resumption and State Management

### How Epic Resumption Works

When you run `epic-mgr epic start <epic_number>` on an epic that's already in progress:

1. **Load Existing Plan**: The orchestrator first tries to load an existing plan from `/opt/{instance}/.epic-mgr/state/epic-{N}-plan.json`
2. **Check for Existing PRs**: Queries GitHub via `gh pr list` to find PRs for issue branches (e.g., `issue-581`)
3. **Reuse Worktrees**: Detects existing worktrees with commits and reuses them
4. **Skip Completed Issues**: Issues that already have PRs are marked as complete and skipped
5. **Resume Workflow**: Only runs TDD workflows for issues that haven't been completed yet

**Example Output:**
```bash
epic-mgr epic start 580

Step 1: Loading or analyzing epic 580
Loaded existing plan for epic 580

Step 2: Creating worktrees
Worktree already exists: /opt/work/feature-epic-580/issue-581
Reusing existing worktree with 2 commit(s)

Step 2.6: Checking for existing PRs
Found existing PRs: {581: 586, 582: 587}

Step 4: Starting development
Phase phase_1: [581]
  Issue 581 already has PR #586, skipping

Phase phase_2: [582]
  Issue 582 already has PR #587, skipping

Phase phase_3: [583]
  Issue 583 needs TDD workflow
Launching TDD workflow for issue 583...
```

### Automatic Skipping Logic

Issues are skipped if:
- A PR exists with `headRefName` matching `issue-{number}` (checked via `gh pr list`)
- The issue's worktree has commits (indicates work was done)

Issues are processed if:
- No PR exists for the issue branch
- The worktree is empty or doesn't exist

### Manual Epic Resumption

If you need to manually resume specific issues:

```bash
# Resume entire epic (recommended)
epic-mgr epic start 580

# Or manually run TDD workflow for specific issue
cd /opt/epic-manager
# Use Claude Code SDK or slash commands directly in worktree
```

### State Persistence

Epic state is stored in two files:
- `epic-{N}-plan.json`: Epic plan from Claude's analysis (issues, dependencies, phases)
- `epic-{N}.json`: Runtime state (PR numbers, worktree paths, status) - created/updated during execution

The plan file persists across runs, enabling resumption.

## Epic Build and Integration Testing

### Overview

After all PRs in an epic are created and reviewed, use `epic build` to test the complete integration before merging to main.

### Build Workflow

```bash
# 1. Build the epic in Docker container
epic-mgr epic build 580

# What it does:
# - Validates all PRs exist and are healthy
# - Creates integration branch: epic-580-build
# - Merges all stack tops (issue-585 in this case) into build branch
# - Checks out build branch in main repo
# - Runs build-dev.sh to create Docker container
# - Streams build output

# 2. Test the container
# Container runs on localhost (port shown in output)
# Test all epic functionality

# 3. If bugs are found, fix in build branch
cd /opt/feature
git checkout epic-580-build
# Make fixes...
git commit -m "Fix: ..."

# 4. Rebuild without recreating branch
# (Current limitation: need to manually rerun build-dev.sh)
cd /opt/feature
./build-dev.sh

# 5. When testing complete, merge to main
# (Current limitation: manual merge required)
cd /opt/feature
git checkout main
git merge epic-580-build
git push
```

### Build Options

```bash
# Skip PR health validation
epic-mgr epic build 580 --skip-checks

# Force build even if validations fail
epic-mgr epic build 580 --force

# Auto-sync stack without prompting
epic-mgr epic build 580 --auto-sync

# Build without Docker cache
epic-mgr epic build 580 --no-cache
```

### How Integration Branch Works

The build command creates a temporary integration branch that merges all stack components:

1. **Creates branch**: `epic-580-build` from `main`
2. **Merges stacks**: Merges all stack top branches (e.g., `issue-585`)
3. **Handles parallel stacks**: If epic has multiple independent stacks, merges all of them
4. **Tests integration**: Runs `build-dev.sh` to create container with complete epic

**Branch structure example**:
```
main
  └─ issue-581 (PR #586)
       └─ issue-582 (PR #587)
            └─ issue-583 (PR #588)
                 └─ issue-584 (PR #589)
                      └─ issue-585 (PR #590) ← Stack top

epic-580-build ← Created by merging issue-585 into main
```

### Troubleshooting

**Problem**: PR health check fails
**Solution**: Check which PR is failing:
```bash
cd /opt/feature
gh pr list --json number,title,mergeable,statusCheckRollup
```
Use `--skip-checks` to build anyway for testing.

**Problem**: Merge conflicts during build branch creation
**Solution**: Indicates PRs have conflicts with main or each other. Fix conflicts in individual PRs first, then rebuild.

**Problem**: Build script fails
**Solution**: Check logs for Docker errors, missing dependencies, or test failures. Fix in build branch and manually rerun `./build-dev.sh`.

### PR Discovery Issue Filtering

**Note**: Epic descriptions may contain color codes (e.g., `#374151` for Tailwind CSS). The PR discovery logic filters out numbers > 100,000 to avoid mistaking these for issue references. Only actual GitHub issue numbers are processed.

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