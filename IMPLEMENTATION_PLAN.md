# Epic Manager Implementation Plan

## Architecture Philosophy

Epic Manager is a **worktree coordinator** that orchestrates parallel development. It does NOT reimplement Claude Code functionality - it creates isolated environments and lets Claude Code do the actual work.

### Division of Responsibilities

**Epic Manager:**
- Creates git worktrees for issue isolation
- Launches Claude Code SDK sessions with slash commands
- Monitors session completion
- Tracks epic/issue state in JSON
- Coordinates parallel execution with dependency awareness

**Claude Code (via SDK, MCP, and agents):**
- Analyzes epics using `epic-orchestrator` agent
- Runs complete TDD workflows using agents
- Interacts with git/Graphite via Graphite MCP server
- Handles CodeRabbit feedback via `pr-coderabbit-fixer` agent
- Manages stack operations via `graphite-stack-manager` agent

### Technology Choices

- **Claude Code SDK**: Programmatic session management (NOT CLI subprocess)
- **Graphite CLI (`gt`)**: All git/Graphite operations via subprocess
- **Graphite MCP**: Built into Claude Code for repo interaction within sessions
- **GitHub CLI (`gh`)**: PR/review queries
- **PyGithub**: Epic metadata if needed as fallback

---

## Core Workflow

### 1. Epic Analysis via `/epic-plan` Slash Command

Epic Manager asks Claude to analyze an epic and output coordination JSON:

```bash
# Conceptually (via SDK):
await client.query("/epic-plan 355")
```

**Output Format:**
```json
{
  "epic": {
    "number": 355,
    "title": "Authentication Overhaul",
    "repo": "owner/kb-llm",
    "instance": "scottbot"
  },
  "issues": [
    {
      "number": 351,
      "title": "OAuth integration",
      "status": "pending",
      "dependencies": [],
      "base_branch": "main"
    },
    {
      "number": 352,
      "title": "Token management",
      "status": "pending",
      "dependencies": [351],
      "base_branch": "issue-351"
    }
  ],
  "parallelization": {
    "phase_1": [351],
    "phase_2": [352]
  }
}
```

**Why:** The `epic-orchestrator` agent understands epic structure, dependencies, and optimal execution order. Epic Manager doesn't need to reimplement this logic.

**Implementation:**
```python
# epic_manager/orchestrator.py
async def analyze_epic(self, instance_name: str, epic_number: int) -> EpicPlan:
    """Use Claude to generate coordination plan."""
    from .claude_automation import ClaudeSessionManager
    claude_mgr = ClaudeSessionManager()

    instance_path = Path(f"/opt/{instance_name}")

    # Ask Claude for JSON plan
    plan_json = await claude_mgr.get_epic_plan(instance_path, epic_number)

    # Parse and save
    plan = EpicPlan.from_json(plan_json)
    self._save_plan(plan)

    return plan
```

---

### 2. Worktree Creation from Plan

Epic Manager creates isolated git worktrees based on the plan's dependency information:

```python
# epic_manager/workspace_manager.py
def create_issue_worktree(
    self,
    instance_name: str,
    epic_num: int,
    issue_num: int,
    base_branch: str  # From plan!
) -> Path:
    """Create worktree for issue development."""
    base_repo = Path(f"/opt/{instance_name}")
    workspace_dir = self.work_base_path / f"{instance_name}-epic-{epic_num}"
    worktree_path = workspace_dir / f"issue-{issue_num}"
    branch_name = f"issue-{issue_num}"

    workspace_dir.mkdir(exist_ok=True, parents=True)

    # Create branch from specified base (handles dependencies)
    subprocess.run([
        "git", "-C", str(base_repo),
        "worktree", "add", "-b", branch_name,
        str(worktree_path), base_branch
    ], check=True, capture_output=True, text=True)

    # Optional: Track in Graphite
    subprocess.run([
        "gt", "track", branch_name
    ], cwd=worktree_path, capture_output=True)

    return worktree_path
```

**Why use git CLI directly:**
- Native git operation, no abstraction needed
- Atomic branch + worktree creation with `-b` flag
- Simple subprocess call, no complex state management

**Why track in Graphite:**
- Prepares branch for stack operations
- Claude can use Graphite MCP immediately
- Non-critical if it fails (Claude can track later)

---

### 3. Parallel TDD Execution with Phasing

Epic Manager launches Claude sessions in parallel, respecting dependency phases:

```python
# epic_manager/orchestrator.py
async def start_development(
    self,
    plan: EpicPlan,
    worktrees: dict[int, Path]
) -> dict[int, WorkflowResult]:
    """Launch TDD workflows respecting dependency phases."""
    from .claude_automation import ClaudeSessionManager
    claude_mgr = ClaudeSessionManager()

    results = {}

    # Process phases sequentially (dependencies)
    for phase_name, issue_numbers in plan.parallelization.items():
        console.print(f"[green]Phase {phase_name}: {issue_numbers}[/green]")

        # Issues within phase run in parallel
        phase_tasks = [
            (worktrees[num], num)
            for num in issue_numbers
            if num in worktrees
        ]

        phase_results = await claude_mgr.run_parallel_tdd_workflows(
            phase_tasks,
            max_concurrent=3
        )

        # Check for failures
        for result in phase_results:
            results[result.issue_number] = result
            if not result.success:
                # Stop on phase failure
                return results

    return results
```

**Why phase execution:**
- Respects dependencies (phase_2 waits for phase_1)
- Maximizes parallelism within each phase
- Fails fast if dependencies aren't met

---

### 4. Claude Session Management via SDK

```python
# epic_manager/claude_automation.py
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

class ClaudeSessionManager:
    async def get_epic_plan(
        self,
        instance_path: Path,
        epic_number: int
    ) -> str:
        """Request epic plan JSON from Claude."""
        options = ClaudeAgentOptions(cwd=str(instance_path))

        response_parts = []
        async with ClaudeSDKClient(options=options) as client:
            await client.query(f"/epic-plan {epic_number}")

            async for message in client.receive_response():
                if isinstance(message, dict) and message.get("type") == "text":
                    response_parts.append(message.get("text", ""))

        return "\n".join(response_parts)

    async def launch_tdd_workflow(
        self,
        worktree_path: Path,
        issue_number: int
    ) -> WorkflowResult:
        """Launch /graphite-tdd in isolated worktree."""
        start_time = datetime.now()

        try:
            options = ClaudeAgentOptions(cwd=str(worktree_path))

            async with ClaudeSDKClient(options=options) as client:
                # Send TDD command - Claude handles everything
                await client.query(f"/graphite-tdd {issue_number}")

                # Stream output
                async for message in client.receive_response():
                    if isinstance(message, dict):
                        if message.get("type") == "text":
                            console.print(f"[dim]{issue_number}:[/dim] {message.get('text', '')}")
                        elif message.get("type") == "error":
                            console.print(f"[red]{issue_number}: {message.get('error')}[/red]")

            duration = (datetime.now() - start_time).total_seconds()
            return WorkflowResult(
                issue_number=issue_number,
                success=True,
                duration_seconds=duration
            )

        except Exception as e:
            return WorkflowResult(
                issue_number=issue_number,
                success=False,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error=str(e)
            )

    async def run_parallel_tdd_workflows(
        self,
        worktree_issues: list[tuple[Path, int]],
        max_concurrent: int = 3
    ) -> list[WorkflowResult]:
        """Run TDD workflows in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_limit(worktree: Path, issue_num: int):
            async with semaphore:
                return await self.launch_tdd_workflow(worktree, issue_num)

        tasks = [run_with_limit(wt, issue) for wt, issue in worktree_issues]
        return await asyncio.gather(*tasks)
```

**Why use SDK not CLI:**
- Programmatic control over sessions
- Structured message streaming
- Better error handling
- Can await completion

**Why semaphore for concurrency:**
- Prevents resource exhaustion (too many Claude sessions)
- Configurable based on system capacity
- Natural async/await pattern

---

### 5. What Happens Inside Each Worktree

When `/graphite-tdd {issue}` runs in a worktree:

1. **Issue Analysis** - `issue-analyzer` agent extracts requirements
2. **Test Writing** - `tdd-test-writer` agent creates comprehensive tests
3. **Implementation** - `tdd-solution-coder` agent implements solution incrementally
4. **Verification** - `implementation-completeness-verifier` validates completion
5. **Graphite Operations** - Uses Graphite MCP to:
   - Create commits
   - Run tests
   - Submit PR via `gt submit`

**Why this works:**
- Complete isolation per worktree
- Claude uses Graphite MCP for all repo operations
- No need for Epic Manager to know about commits, tests, PRs
- Each issue is self-contained

---

### 6. CodeRabbit Feedback Loop

Epic Manager monitors PRs and re-enters worktrees when CodeRabbit comments appear:

```python
# epic_manager/review_monitor.py
class ReviewMonitor:
    async def monitor_epic_reviews(
        self,
        plan: EpicPlan,
        worktrees: dict[int, Path]
    ):
        """Poll PRs for CodeRabbit comments and trigger fixes."""
        from .claude_automation import ClaudeSessionManager
        claude_mgr = ClaudeSessionManager()

        addressed = set()

        while True:
            for issue in plan.issues:
                if issue.pr_number and issue.pr_number not in addressed:
                    has_comments = self._check_coderabbit_comments(issue.pr_number)

                    if has_comments:
                        console.print(f"[yellow]CodeRabbit on PR {issue.pr_number}[/yellow]")

                        # Launch Claude in same worktree
                        result = await claude_mgr.launch_session(
                            worktrees[issue.number],
                            f"Address CodeRabbit review comments for PR {issue.pr_number}"
                        )

                        if result.success:
                            addressed.add(issue.pr_number)

            await asyncio.sleep(60)

    def _check_coderabbit_comments(self, pr_number: int) -> bool:
        """Check PR for CodeRabbit comments via gh CLI."""
        result = subprocess.run([
            "gh", "pr", "view", str(pr_number), "--json", "comments"
        ], capture_output=True, text=True)

        data = json.loads(result.stdout)
        comments = data.get('comments', [])

        return any(
            c.get('author', {}).get('login') == 'coderabbitai'
            for c in comments
        )
```

**Why separate monitor:**
- Runs in background during development
- Independent polling cycle
- Re-uses same worktrees (no cleanup needed)

**Why use `gh` CLI:**
- Simple JSON output
- No need for complex GitHub API client
- Direct PR comment access

---

### 7. Restack Operations

Handled entirely by Claude Code via Graphite MCP:

```python
# Inside worktree, user (or Epic Manager) can trigger:
await claude_mgr.launch_session(
    worktree_path,
    "Restack this branch to incorporate upstream changes"
)

# Claude uses Graphite MCP tools:
# - gt sync
# - gt restack
# - Conflict resolution if needed
```

**Why Claude handles restack:**
- Graphite MCP provides all necessary tools
- `graphite-stack-manager` agent understands stack operations
- Epic Manager doesn't need stack-specific logic

---

## Data Structures

```python
# epic_manager/models.py
from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class EpicInfo:
    number: int
    title: str
    repo: str
    instance: str

@dataclass
class IssueInfo:
    number: int
    title: str
    status: str
    dependencies: list[int]
    base_branch: str  # Critical for worktree creation
    worktree_path: Optional[str] = None
    pr_number: Optional[int] = None

@dataclass
class EpicPlan:
    epic: EpicInfo
    issues: list[IssueInfo]
    parallelization: dict[str, list[int]]  # phase_name -> issue_numbers

    @classmethod
    def from_json(cls, json_str: str) -> 'EpicPlan':
        """Parse JSON from /epic-plan command."""
        data = json.loads(json_str)
        return cls(
            epic=EpicInfo(**data['epic']),
            issues=[IssueInfo(**i) for i in data['issues']],
            parallelization=data['parallelization']
        )

    def save(self, path: Path):
        """Persist plan to JSON file."""
        path.write_text(json.dumps({
            'epic': self.epic.__dict__,
            'issues': [i.__dict__ for i in self.issues],
            'parallelization': self.parallelization
        }, indent=2))

    @classmethod
    def load(cls, path: Path) -> 'EpicPlan':
        """Load plan from JSON file."""
        return cls.from_json(path.read_text())
```

---

## Implementation Priorities

### Priority 1: Fix Branch Creation Bug
**File:** `epic_manager/workspace_manager.py`

Current bug: Tries to create worktree before branch exists.

**Fix:**
```python
# Use -b flag to create branch atomically with worktree
subprocess.run([
    "git", "-C", str(base_repo),
    "worktree", "add", "-b", branch_name,  # Creates branch!
    str(worktree_path), base_branch
], check=True, capture_output=True, text=True)
```

**Why critical:** Everything else depends on working worktrees.

---

### Priority 2: Claude SDK Integration
**File:** `epic_manager/claude_automation.py`

Replace subprocess `claude` calls with SDK:

**Add dependency:**
```txt
# requirements.txt
claude-agent-sdk>=0.1.0
```

**Implement:**
```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# NOT this:
# subprocess.run(["claude", "--working-directory", ...])

# THIS:
async with ClaudeSDKClient(options=ClaudeAgentOptions(
    working_directory=str(path)
)) as client:
    await client.query("/graphite-tdd 123")
```

**Why:** SDK provides proper async control, structured messages, error handling.

---

### Priority 3: Implement `/epic-plan` Data Flow
**Files:**
- `epic_manager/models.py` - Data structures
- `epic_manager/orchestrator.py` - Plan consumption
- `epic_manager/claude_automation.py` - Plan retrieval

**Flow:**
1. Ask Claude for plan: `await claude_mgr.get_epic_plan(path, epic_num)`
2. Parse JSON: `plan = EpicPlan.from_json(json_str)`
3. Create worktrees: Use `issue.base_branch` from plan
4. Execute phases: Use `plan.parallelization` for ordering

**Why:** Plan encodes all coordination logic. Epic Manager just executes it.

---

### Priority 4: Minimal Review Monitor
**File:** `epic_manager/review_monitor.py`

Simple polling loop:
1. Check PRs for CodeRabbit comments (`gh pr view`)
2. If found, launch Claude in worktree with prompt
3. Mark as addressed to avoid re-processing

**Why async:** Runs in background during development without blocking.

---

## What NOT To Implement

### ❌ GitHub API for Epic Analysis
**Why:** Let Claude's `/epic-plan` handle this via `epic-orchestrator` agent.

### ❌ Graphite Stack State Management
**Why:** Query live state via `gt log` when needed. No caching.

### ❌ TDD Workflow Orchestration
**Why:** `/graphite-tdd` handles entire workflow via agents.

### ❌ Commit/PR Creation Logic
**Why:** Claude uses Graphite MCP to create commits and submit PRs.

### ❌ Test Execution Management
**Why:** Agents run tests internally via MCP tools.

### ❌ Complex Error Recovery
**Why:** Start simple - just cleanup failed worktrees. Add transactions later if needed.

---

## File Structure Summary

```
epic_manager/
├── models.py              # EpicPlan, IssueInfo (50 lines)
├── workspace_manager.py   # Git worktree ops (100 lines)
├── claude_automation.py   # SDK session management (150 lines)
├── orchestrator.py        # Main workflow coordination (200 lines)
├── review_monitor.py      # PR monitoring (100 lines)
├── cli.py                 # Click commands (update existing)
└── graphite_integration.py # Keep minimal (optional helpers)
```

**Total new/modified code: ~600 lines**

---

## Testing Approach

### Integration Test Strategy

```python
# tests/test_epic_workflow.py

@pytest.mark.integration
async def test_worktree_creation_with_dependencies():
    """Verify worktrees are created with correct base branches."""
    manager = WorkspaceManager()

    # Simulate plan with dependencies
    # Issue 352 depends on 351, so base should be issue-351
    worktree = manager.create_issue_worktree(
        instance_name="test-instance",
        epic_num=100,
        issue_num=352,
        base_branch="issue-351"  # From plan
    )

    assert worktree.exists()

    # Verify branch was created from correct base
    result = subprocess.run([
        "git", "-C", str(worktree), "log", "--oneline", "-1"
    ], capture_output=True, text=True)

    # Should show issue-351's commits
    assert result.returncode == 0

@pytest.mark.integration
async def test_claude_sdk_session():
    """Verify Claude SDK can launch sessions."""
    claude_mgr = ClaudeSessionManager()

    # Need real worktree for this test
    # Or mock ClaudeSDKClient

    result = await claude_mgr.launch_tdd_workflow(
        Path("/tmp/test-worktree"),
        issue_number=123
    )

    assert isinstance(result, WorkflowResult)
```

**Why integration tests:**
- Verify actual git operations work
- Test Claude SDK integration
- Catch subprocess errors
- Validate JSON parsing

---

## Success Criteria

Epic Manager implementation is complete when:

1. ✅ Can create worktrees with correct base branches (dependencies)
2. ✅ Can launch Claude SDK sessions with `/graphite-tdd`
3. ✅ Can execute phases in dependency order
4. ✅ Can monitor PRs and trigger review fixes
5. ✅ Can run 1 complete epic end-to-end

**Measure:** Run `epic-mgr -i scottbot epic start 355` and observe parallel development across worktrees with proper dependency handling.