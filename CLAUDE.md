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

## Claude Code Skills Architecture

Epic Manager uses **Claude Code Skills** to define development workflows as discoverable, git-tracked methodologies. Skills replace monolithic Python prompts with modular, maintainable markdown files.

### What Are Skills?

Skills are packages of expertise that Claude discovers autonomously based on the user's request. Each skill contains:
- `SKILL.md`: Main skill definition with YAML frontmatter and workflow steps
- Supporting `.md` files: Referenced documentation (e.g., `schema-discovery.md`, `integration-tests.md`)

**Key advantages**:
- **Git-tracked**: Skills evolve with the codebase, versioned in `.claude/skills/`
- **Discoverable**: Claude autonomously selects appropriate skills based on context
- **Modular**: Small, focused skills can reference each other
- **Team-shared**: Anyone pulling the repo gets latest workflow improvements
- **User-visible**: Skills are markdown files users can read/modify directly

### Available Skills

Epic Manager provides 4 primary skills provisioned into every worktree:

#### 1. **tdd-graphite-workflow** (380 lines)
Complete TDD workflow for issue implementation with Graphite stacked PRs.

**Triggers**: "TDD workflow", "implement issue", "run TDD", "develop feature"

**Key features**:
- 11-step workflow from analysis through PR submission
- Schema discovery to prevent field name bugs
- Integration test requirements (minimum 20%)
- Graphite stack synchronization and PR verification
- Published PRs for CodeRabbit review

**Supporting files**:
- `schema-discovery.md`: Field name documentation methodology
- `integration-tests.md`: 20% integration test requirement details
- `schema-compliance.md`: Field validation process
- `graphite-commands.md`: Complete `gt` CLI reference

#### 2. **epic-planning** (383 lines)
Analyzes GitHub epics and creates JSON execution plans with dependency chains.

**Triggers**: "analyze epic", "epic plan", "create plan for epic"

**Key features**:
- Extracts dependencies from epic description
- Determines base branches for git worktrees
- Identifies parallelization opportunities
- Returns structured JSON for epic orchestration

**Supporting files**:
- `dependency-analysis.md`: Advanced dependency patterns

#### 3. **review-fixer** (388 lines)
Addresses CodeRabbit review comments systematically.

**Triggers**: "fix review", "address review comments", "CodeRabbit feedback"

**Key features**:
- Fetches and prioritizes review comments by severity
- Implements fixes with tests
- Verifies PR base branches after changes
- Updates PR with summary of fixes

**Supporting files**:
- `pr-verification.md`: Base branch verification after review

#### 4. **pr-submission** (311 lines)
Creates PRs via Graphite with proper stacking and backend registration.

**Triggers**: "submit PR", "create PR", "publish PR"

**Key features**:
- Ensures Graphite backend registration (required for web UI)
- Verifies base branches match stack structure
- Publishes PRs for CodeRabbit review
- Validates stack integrity

**Supporting files**:
- `stack-verification.md`: Base branch verification details

### Skill Provisioning Workflow

When epic-manager creates a worktree, skills are automatically provisioned:

```python
def install_skills_to_worktree(worktree_path, instance_path):
    """
    Merge strategy:
    1. Copy epic-manager skills (base layer) from /opt/epic-manager/.claude/skills/
    2. Copy KB-LLM instance skills (if exist) from instance/.claude/skills/
    3. Result: worktree/.claude/skills/ contains both
    """
```

**Example**:
```
Worktree creation for issue 581:
  ✓ Creating git worktree at /opt/work/feature-epic-580/issue-581
  ✓ Tracking branch 'issue-581' in Graphite
  ✓ Installing epic-manager skills...
  ✓ Installed 4 epic-manager skill(s)
  ✓ Merged KB-LLM instance skills (if any)
```

**Result**: Claude running in the worktree discovers skills from `.claude/skills/` and executes workflows autonomously.

### Customizing Workflows

Skills are editable markdown files - modify them for project-specific needs:

#### Option 1: Edit Epic-Manager Skills (Global Changes)
```bash
# Edit the TDD workflow for all future epics
vim /opt/epic-manager/.claude/skills/tdd-graphite-workflow/SKILL.md

# Changes apply to new worktrees (existing worktrees use snapshot from creation)
```

#### Option 2: Add KB-LLM Instance Skills (Project-Specific)
```bash
# Create instance-specific skills
mkdir -p /opt/feature/.claude/skills/kb-llm-custom/
vim /opt/feature/.claude/skills/kb-llm-custom/SKILL.md

# These merge with epic-manager skills in every worktree
```

#### Option 3: Override Epic-Manager Skills
If KB-LLM instance has a skill with the same name as epic-manager, the instance version takes precedence (copied last in merge).

### Skill Discovery Process

When Claude receives a request in a worktree:

1. **Discovers skills** from `worktree/.claude/skills/` (epic-manager + instance skills merged)
2. **Matches request** to skill descriptions (e.g., "implement issue" → `tdd-graphite-workflow`)
3. **Invokes skill** autonomously with appropriate context
4. **References supporting files** as needed (progressive disclosure)

**Example**:
```
User request: "Execute TDD workflow for issue #581"
          ↓
Claude discovers: tdd-graphite-workflow skill
          ↓
Executes: 11-step TDD workflow from SKILL.md
          ↓
References: schema-discovery.md (step 4.5), integration-tests.md (step 5)
```

### Migration from Prompts

Epic Manager has **fully migrated** from Python prompt templates to skills:

**Before (prompt-based)**:
- 745 lines of Python strings in `prompts.py`
- Hardcoded in codebase, requires code changes to modify
- Not visible to users without reading Python

**After (skills-based)**:
- 3,293 lines of structured markdown in `.claude/skills/`
- Git-tracked, editable without code changes
- Visible and modifiable by all users
- Modular and composable

**Code impact**:
- Deleted: `epic_manager/prompts.py` (745 lines)
- Simplified: `claude_automation.py` methods now send minimal prompts
- Added: `workspace_manager.install_skills_to_worktree()` for provisioning

## Architecture

### Execution Model: Chain-Based Sequential Stacking

Epic Manager uses **dependency chain execution** to ensure proper Graphite PR stacking:

**Key Concepts:**
- **Dependency Chain**: Sequence of issues where each depends on the previous (e.g., 581 → 582 → 583)
- **Sequential Within Chain**: Issues in a chain execute one at a time, waiting for parent PR creation
- **Parallel Across Chains**: Independent chains run concurrently for performance

**Why Sequential Execution Matters:**

When `gt submit` creates a PR, Graphite determines the base branch from git ancestry. If the parent PR doesn't exist on GitHub yet, Graphite falls back to targeting `main`, breaking the stack. By executing chains sequentially and verifying PR existence between steps, we ensure:
- ✅ Parent PR exists before child PR creation
- ✅ Correct base branches (issue-582 targets issue-581, not main)
- ✅ Proper stack visualization in Graphite web UI

**Example Execution:**

Given epic with dependencies: 582→581, 583→582, 585→584

```
Chains Identified:
  Chain 1: [581 → 582 → 583]  (sequential)
  Chain 2: [584 → 585]         (sequential, parallel to Chain 1)

Execution Flow:
1. Start Chain 1 and Chain 2 in parallel
2. Chain 1:
   - Run TDD for 581 → Create PR #601 → Verify PR exists
   - Run TDD for 582 → Create PR #602 (targets issue-581) → Verify PR exists
   - Run TDD for 583 → Create PR #603 (targets issue-582)
3. Chain 2 (concurrent with Chain 1):
   - Run TDD for 584 → Create PR #604 → Verify PR exists
   - Run TDD for 585 → Create PR #605 (targets issue-584)

Result: All PRs properly stacked ✅
```

**Performance:**
- Best case (all independent): Full parallelism
- Worst case (single chain): Sequential execution
- Typical (2-3 chains): Good parallelism with correct stacking

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
   - Parses JSON into `EpicPlan` model (defines dependencies via `base_branch` field)
   - Calls `create_worktrees_for_plan()` to create isolated environments
   - Calls `start_development()` to launch **chain-based execution**
3. **Workspace Manager** (`workspace_manager.py`): Creates worktrees
   - For each issue: `git worktree add -b issue-{N} {path} {base_branch}`
   - Base branch determines git ancestry (e.g., issue-582 branches from issue-581)
   - Tracks worktrees via `git worktree list --porcelain`
4. **Chain Identification** (`models.py`): EpicPlan analyzes dependencies
   - Calls `plan.get_dependency_chains()` to identify independent chains
   - Chains are sequences like [581 → 582 → 583] where each depends on previous
   - Independent chains can run in parallel
5. **Chain Execution** (`orchestrator.py`): Sequential within chain, parallel across
   - For each chain: Execute issues sequentially
   - Between sequential steps: Verify parent PR exists via `_verify_pr_exists()`
   - Independent chains run concurrently via `asyncio.gather()`
6. **Claude Automation** (`claude_automation.py`): Launches TDD workflows
   - Uses Claude Code SDK with explicit TDD workflow prompt
   - Streams progress output to console
   - Extracts PR number from output via `_extract_pr_number_from_output()`
   - Returns `WorkflowResult` with success status, timing, and PR number
7. **PR Verification** (`orchestrator.py`): Ensures parent PRs exist
   - After each issue completes, verifies PR exists on GitHub
   - Retries with exponential backoff to handle GitHub API lag
   - Only proceeds to dependent issue after parent PR confirmed
8. **Graphite Integration** (`graphite_integration.py`): Manages PR stacks
   - Creates stacked PRs with proper base branches (via `gt submit`)
   - Syncs and restacks when main branch changes
9. **Review Monitor** (`review_monitor.py`): Handles CodeRabbit feedback
   - Polls GitHub API for CodeRabbit comments (60s intervals)
   - Creates review fix worktrees when comments appear
   - Launches Claude Code to address feedback automatically
10. **PR Base Branch Verification** (`orchestrator.py`): Ensures stack integrity
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
```text
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

## Schema Discovery and Validation Workflow

### Overview

Epic Manager implements a comprehensive schema discovery and validation workflow to prevent `AttributeError` bugs caused by incorrect field name assumptions. This workflow is integrated into the TDD process and includes three critical components:

1. **Schema Discovery**: Documents all model field names before implementation
2. **Integration Tests**: Requires minimum 20% integration tests to catch field errors
3. **Schema Compliance Check**: Verifies field access matches documented schema

### Why Schema Discovery Matters

**Problem**: Field names are not guessable. Common errors include:
- Using `.last_updated` instead of `.updated_at`
- Using `.participant_entities` instead of `.entities_mentioned['people']`
- Using `.finalized` instead of `.is_finalized`

**Impact**: These errors cause `AttributeError` exceptions in production that are only caught at runtime.

**Solution**: Mandatory schema discovery step that documents ALL field names from actual model definitions before any implementation begins.

### TDD Workflow with Schema Discovery

The enhanced TDD workflow (`TDD_WORKFLOW_PROMPT` in `prompts.py`) includes these steps:

1. **Sync Graphite Stack**: Ensure stack is up-to-date
2. **Stack Context Check**: Verify branch position and relationships
3. **Register Branch**: Track existing worktree branch in Graphite
4. **Analyze Issue**: Extract requirements (via `issue-analyzer` agent)
5. **Schema Discovery (NEW)**: Document all model field names
   - Identify models to be used/modified
   - Read each model definition file
   - Document ALL field names exactly as defined
   - Create schema reference for implementation
6. **Create Tests**: Write unit AND integration tests (via `tdd-test-writer` agent)
   - Unit tests (with mocks for external dependencies)
   - Integration tests (minimum 20%, no mocks for code under test)
7. **Verify Failures**: Confirm tests fail initially (NOT with AttributeError!)
8. **Implement**: Code feature incrementally (via `tdd-solution-coder` agent)
9. **Schema Compliance Check (NEW)**: Verify field names match schema
10. **Verify Completeness**: All tests pass, no TODOs
11. **Submit PR**: Create stacked PR via Graphite
12. **Verify PR Base**: Ensure base branch is correct

### Schema Discovery Process

**Automated Method** (via ClaudeSessionManager):
```python
claude_mgr = ClaudeSessionManager()
schema_reference = await claude_mgr.run_schema_discovery(
    worktree_path=Path("/opt/work/feature-epic-580/issue-581"),
    issue_number=581
)
```

**Schema Reference Format**:
```
Model: MeetingState
File: app/models/meeting/state.py
Fields:
  - meeting_id: str
  - bot_id: str
  - updated_at: datetime (NOT last_updated, NOT modified_at)
  - entities_mentioned: Dict[str, List[str]] (keys: 'people', 'projects')
  - body: str
  - update_count: int
  - is_finalized: bool (NOT finalized, NOT is_final)

Common Errors to Avoid:
  ❌ state.last_updated → ✅ state.updated_at
  ❌ state.participant_entities → ✅ state.entities_mentioned['people']
  ❌ state.finalized → ✅ state.is_finalized
```

### Integration Test Requirements

**Minimum Coverage**: At least 20% of tests must be integration tests (no mocks for code under test).

**Why Integration Tests**:
- Unit tests with mocks hide implementation bugs
- Integration tests call real methods and catch AttributeError
- Required for: serialization, data models, field access

**Example Integration Test**:
```python
@pytest.mark.integration
def test_meeting_state_serialization(tmp_path):
    """Integration: Verify MeetingState serializes with correct field names"""
    state = MeetingState(
        meeting_id="m1",
        bot_id="b1",
        updated_at=datetime.now(),
        entities_mentioned={'people': ['Alice'], 'projects': ['P1']},
        is_finalized=False
    )

    # Real serialization - catches field name errors
    json_data = state.to_dict()

    assert 'updated_at' in json_data  # NOT last_updated!
    assert json_data['is_finalized'] is False  # NOT finalized!
```

**Automated Check** (via ClaudeSessionManager):
```python
coverage_ok = await claude_mgr.check_integration_test_coverage(
    worktree_path=Path("/opt/work/feature-epic-580/issue-581"),
    issue_number=581
)
# Returns True if >= 20%, False otherwise
```

### Schema Compliance Check

**Purpose**: Verify all field access in implementation matches documented schema.

**Automated Check** (via ClaudeSessionManager):
```python
compliance_ok = await claude_mgr.run_schema_compliance_check(
    worktree_path=Path("/opt/work/feature-epic-580/issue-581"),
    issue_number=581,
    schema_reference=schema_reference  # From discovery step
)
# Returns False if violations found (BLOCKER)
```

**What It Checks**:
1. Extracts all attribute access patterns from modified files
2. Compares against documented schema reference
3. Reports violations with file/line numbers
4. Suggests fixes for each violation

**Example Violation Report**:
```
VIOLATION in app/services/meeting.py:45
❌ state.last_updated
✅ state.updated_at
Fix: Change line 45 from "state.last_updated" to "state.updated_at"
```

**Enforcement**: Schema compliance must pass with 100% before PR creation.

### Integration with TDD Workflow

The schema discovery and validation workflow is fully integrated into the automated TDD process:

1. **Claude Automation** (`claude_automation.py`):
   - `run_schema_discovery()`: Runs schema discovery
   - `run_schema_compliance_check()`: Validates field access
   - `check_integration_test_coverage()`: Ensures 20% minimum

2. **Prompts** (`prompts.py`):
   - `SCHEMA_DISCOVERY_PROMPT`: Guides schema documentation
   - `SCHEMA_COMPLIANCE_CHECK_PROMPT`: Guides validation
   - `INTEGRATION_TEST_PROMPT`: Guides integration test creation
   - `TDD_WORKFLOW_PROMPT`: Orchestrates entire workflow

3. **Agent Invocations**:
   - `issue-analyzer`: Extracts requirements
   - `tdd-test-writer`: Creates tests with schema context
   - `tdd-solution-coder`: Implements with schema context
   - `implementation-completeness-verifier`: Final validation

### Best Practices

1. **Always Run Schema Discovery First**: Before writing any tests or implementation
2. **Pass Schema Reference to Agents**: Ensure test-writer and solution-coder have schema context
3. **Never Guess Field Names**: Always reference the documented schema
4. **Require Integration Tests**: Don't accept 100% mocked test suites
5. **Block on Violations**: Don't proceed to PR if schema compliance fails
6. **Include in Reviews**: Check for schema compliance during code reviews

### Common Patterns and Pitfalls

**Timestamp Fields**:
- ❌ `.last_updated`, `.modified_at`, `.changed_at`
- ✅ `.updated_at` (or whatever schema defines)

**Boolean Fields**:
- ❌ `.finalized`, `.completed`, `.active`
- ✅ `.is_finalized`, `.is_completed`, `.is_active`

**Collection Fields**:
- ❌ `.participant_entities`, `.project_entities`
- ✅ `.entities_mentioned['people']`, `.entities_mentioned['projects']`

**Plural vs Singular**:
- ❌ `.comment`, `.entity`
- ✅ `.comments`, `.entities`

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

## Troubleshooting Graphite Stack Registration

### Problem: PRs Don't Appear as a Unified Stack in Graphite Web UI

**Symptoms**:
- PRs exist on GitHub with correct base branches
- Local `gt log --stack` shows correct stack structure
- But Graphite web UI (app.graphite.dev) shows PRs as individual stacks of 1
- No restack benefits or unified stack visualization

**Root Cause**:
Branches were pushed using regular `git push` instead of Graphite's `gt submit`. This means:
- ✅ Git structure is correct (branches properly based on each other)
- ✅ GitHub PR base branches are correct
- ✅ Local Graphite CLI sees the stack
- ❌ **Graphite backend has NO metadata about the stack**

When you see this message from `gt repo sync`:
```
Branch issue-598 is up to date with remote, but the current remote version was not pushed with Graphite.
Branch issue-599 is up to date with remote, but the current remote version was not pushed with Graphite.
```

This confirms the PRs are not registered with Graphite's backend.

**Solution: Register PRs with Graphite Backend**

Use the `epic sync-graphite` command to fix existing epics:

```bash
# Synchronize all PRs in an epic with Graphite's backend
epic-mgr epic sync-graphite 597

# What it does:
# 1. Loads epic plan to find all issues and worktrees
# 2. For each issue with an existing PR:
#    - Checks out the branch in its worktree
#    - Runs 'gt submit --no-edit --no-interactive'
#    - This registers the PR with Graphite without changing anything
# 3. Verifies stack structure after registration

# Example output:
# Syncing PR #607 (issue 598)...
#   ✓ PR #607 registered with Graphite
# Syncing PR #608 (issue 599)...
#   ✓ PR #608 registered with Graphite
#
# Sync Summary
# ✓ Synced: 3
# ○ Skipped: 2
#
# ✓ All PRs synchronized successfully!
# Check the Graphite web UI to see the unified stack
```

**Manual Fix (if command not available)**:

```bash
cd /opt/main  # Or your instance directory

# For each branch with an existing PR:
git checkout issue-598
gt submit --no-edit --no-interactive  # Registers PR #607

git checkout issue-599
gt submit --no-edit --no-interactive  # Registers PR #608

# Verify stack is now registered
gt log --stack

# Should now show proper stack in Graphite web UI
```

**Prevention: Always Use `gt submit`**

To prevent this issue in the future, always create PRs using Graphite's submission command:

```bash
# ✅ CORRECT: Use gt submit to create PR
gt submit --no-interactive --title "..." --body "..."

# ❌ WRONG: Don't use git push + gh pr create
git push origin issue-599
gh pr create --title "..." --body "..."
```

**Why This Matters**:

`gt submit` does TWO things:
1. **Creates/updates the PR on GitHub** (what manual workflows do)
2. **Registers the PR with Graphite's backend** (what manual workflows miss)

Without step 2, Graphite's web UI can't:
- Display stack relationships visually
- Enable restacking across the stack
- Show stack health and dependencies
- Provide unified stack operations

**TDD Workflow Integration**:

The TDD workflow (`TDD_WORKFLOW_PROMPT`) now includes automatic verification in Step 10:
- After PR creation, verify it appears in `gt log --stack`
- If PR doesn't appear or shows as isolated, run `gt submit --no-edit --no-interactive`
- This ensures every PR is properly registered from the start