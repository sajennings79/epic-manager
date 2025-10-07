# Epic Manager - Centralized Workflow Automation Tool

## Overview

Epic Manager is a standalone development tool that orchestrates epic-based development workflows across multiple KB-LLM instances. It provides centralized coordination for TDD workflows, Graphite stacked PRs, and automated CodeRabbit reviews while enabling parallel development through git worktrees.

## Architecture

### Core Design Principles

1. **Centralized Orchestration**: Single tool manages multiple KB-LLM deployments
2. **Parallel Development**: Git worktrees enable simultaneous work on different issues
3. **Graphite Integration**: Full support for stacked PRs with dependency management
4. **Interactive Workflow**: Real-time monitoring with intervention capability
5. **Non-Intrusive**: Manages deployments externally without embedding in containers

### System Architecture

```
/opt/
├── epic-manager/                    # Centralized workflow orchestrator
│   ├── epic_manager/               # Main application package
│   │   ├── cli.py                  # Main CLI entry point
│   │   ├── orchestrator.py         # Epic workflow coordination
│   │   ├── workspace_manager.py    # Git worktree management
│   │   ├── graphite_integration.py # Graphite stack operations
│   │   ├── claude_automation.py    # Claude Code session management
│   │   ├── instance_discovery.py   # Auto-discover KB-LLM instances
│   │   ├── review_monitor.py       # CodeRabbit review polling
│   │   └── tui/                    # Terminal UI components
│   │       ├── dashboard.py        # Main monitoring dashboard
│   │       ├── stack_viewer.py     # Graphite stack visualization
│   │       └── progress_tracker.py # Epic progress monitoring
│   └── data/                       # Runtime data and state
│       ├── state/                  # Epic progress tracking
│       └── logs/                   # Application logs
│
├── main/                           # KB-LLM instance "main"
├── scottbot/                       # KB-LLM instance "scottbot"
├── feature/                        # KB-LLM instance "feature"
│
└── work/                           # Parallel development workspaces
    ├── scottbot-epic-355/          # Epic workspace
    │   ├── issue-351/              # Worktree for issue 351
    │   ├── issue-352/              # Worktree for issue 352
    │   ├── issue-352-review/       # Review fixes worktree
    │   └── issue-353/              # Parallel development
    └── feature-epic-290/
        └── issue-287/
```

## The Epic Development Workflow

### Phase 1: Epic Analysis and Planning

1. **Epic Analysis**: Use `epic-orchestrator` agent to parse GitHub epic
   - Extract linked issues and dependencies
   - If epic has no linked issues: Use `software-architect-planner` to analyze epic and create optimized sub-issues
   - If epic has existing issues: Use them directly for stack planning
   - Identify execution order and dependencies
   - Create comprehensive execution plan

2. **Architecture Design**: Use `software-architect-planner` agent to:
   - Research existing codebase patterns
   - Design cohesive architecture for entire epic
   - Define shared interfaces and data models
   - Create architectural blueprint
   - Ensure all issues work together seamlessly

3. **Graphite Stack Initialization**:
   - Create epic coordination branch
   - Set up stacked branch structure based on issue dependencies
   - Plan branch relationships for optimal parallelization

### Phase 2: Parallel Development

1. **Worktree Creation**: For each issue that can be worked in parallel:
   ```python
   # Create isolated workspace
   worktree_path = f"/opt/work/{instance}-epic-{epic_num}/issue-{issue_num}"
   run(f"git -C /opt/{instance} worktree add {worktree_path} issue-{issue_num}")
   ```

2. **TDD Workflow in Isolation**: Each worktree runs complete TDD cycle:
   - `issue-analyzer`: Analyze requirements with architectural context
   - `tdd-test-writer`: Create comprehensive test suite
   - `tdd-solution-coder`: Implement solution incrementally
   - `implementation-completeness-verifier`: Validate completion

3. **Stacked PR Creation**: Each issue creates PR in Graphite stack:
   ```bash
   gt submit --title "Fix #351: Description" --body "Summary and test coverage"
   ```

### Phase 3: Review and Iteration

1. **Automatic CodeRabbit Integration**: When PR is published:
   - CodeRabbit automatically reviews (GitHub integration)
   - Comments are added to PR

2. **Review Monitoring and Fixes**:
   - Epic Manager polls PRs for CodeRabbit comments (60-second intervals)
   - When new comments detected, automatically:
     - Create separate review worktree
     - Run `pr-coderabbit-fixer` agent to address comments
     - Commit and push fixes to PR
     - Mark PR as addressed to avoid re-processing

3. **Stack Restacking**: When dependencies are updated:
   ```python
   # All dependent worktrees get updates
   for worktree in dependent_worktrees:
       run(f"cd {worktree} && gt sync && gt restack")
   ```

### Phase 4: Integration and Testing

1. **Progressive Merging**: Bottom-up merge as PRs are approved:
   ```bash
   gt merge issue-351  # Graphite handles dependent branch rebasing
   ```

2. **Dev Instance Deployment**: Deploy to KB-LLM dev instance for testing
   - Interactive debugging with log monitoring
   - Real-world testing and validation

3. **Final Integration**: When all issues complete:
   - Epic branch ready for final review
   - Merge to main after validation

## Workspace Management with Git Worktrees

### Parallel Development Strategy

Git worktrees provide complete isolation for parallel development:

```python
class WorkspaceManager:
    def create_epic_workspace(self, instance_name, epic_num):
        """Set up workspace for epic development"""
        base_repo = f"/opt/{instance_name}"
        workspace_dir = f"/opt/work/{instance_name}-epic-{epic_num}"

        # Create workspace directory
        os.makedirs(workspace_dir, exist_ok=True)
        return workspace_dir

    def create_issue_worktree(self, instance, epic_num, issue_num):
        """Create isolated worktree for issue development"""
        base_repo = f"/opt/{instance}"
        worktree_path = f"/opt/work/{instance}-epic-{epic_num}/issue-{issue_num}"
        branch_name = f"issue-{issue_num}-description"

        # Create worktree
        subprocess.run([
            "git", "-C", base_repo,
            "worktree", "add", worktree_path, branch_name
        ])

        return worktree_path

    def launch_claude_session(self, worktree_path, issue_num):
        """Launch Claude Code session in isolated worktree"""
        subprocess.run([
            "claude",
            f"--working-directory={worktree_path}",
            "/graphite-tdd", str(issue_num)
        ])
```

### Review Workflow with Worktrees

```python
class ReviewMonitor:
    def __init__(self):
        self.addressed_prs = set()
        self.poll_interval = 60  # seconds

    async def monitor_reviews(self):
        """Background task to monitor for CodeRabbit reviews"""
        while True:
            active_prs = self.get_active_prs()
            for pr in active_prs:
                if self.has_new_coderabbit_comments(pr) and pr not in self.addressed_prs:
                    await self.handle_review_fixes(pr)
                    self.addressed_prs.add(pr)

            await asyncio.sleep(self.poll_interval)

    def has_new_coderabbit_comments(self, pr_num):
        """Check if CodeRabbit has added new comments"""
        result = subprocess.run([
            "gh", "pr", "view", str(pr_num), "--comments", "--json", "comments"
        ], capture_output=True, text=True)

        comments = json.loads(result.stdout)['comments']
        coderabbit_comments = [c for c in comments if c['author']['login'] == 'coderabbitai']

        # Check if comments are newer than last processing
        return len(coderabbit_comments) > 0 and not self.is_already_addressed(pr_num)

    async def handle_review_fixes(self, pr_num):
        """Handle CodeRabbit review fixes in isolated workspace"""
        issue_num = self.get_issue_from_pr(pr_num)
        instance = self.get_instance_from_pr(pr_num)

        # Create separate worktree for review fixes
        review_worktree = f"/opt/work/{instance}-issue-{issue_num}-review"

        subprocess.run([
            "git", "-C", f"/opt/{instance}",
            "worktree", "add", review_worktree, f"issue-{issue_num}"
        ])

        # Run CodeRabbit fixer in isolation
        subprocess.run([
            "claude",
            f"--working-directory={review_worktree}",
            "--agent", "pr-coderabbit-fixer",
            f"Fix CodeRabbit comments for PR {pr_num}"
        ])

        # Changes automatically update the PR
        # Other worktrees can restack to get fixes
```

## Graphite Stack Integration

### Stack Structure and Dependencies

Graphite maintains branch relationships across all worktrees:

```
main
└─ epic-355-auth
   ├─ issue-351-oauth       (✅ merged)
   ├─ issue-352-tokens      (🔄 in review)
   ├─ issue-353-frontend    (📝 in progress, depends on 352)
   └─ issue-354-integration (📝 in progress, depends on 352)
```

### Parallel Development on Shared Dependencies

```python
def work_parallel_dependencies(self, epic_num, dependency_issue, dependent_issues):
    """Enable parallel work on issues that depend on same branch"""

    # Issues 353 and 354 both build on 352
    for issue in dependent_issues:
        worktree = self.create_issue_worktree(epic_num, issue)

        # Each worktree includes changes from dependency
        subprocess.run([
            "cd", worktree,
            "&&", "gt", "create", f"issue-{issue}-description"
        ])

        # Launch parallel Claude sessions
        self.launch_claude_session(worktree, issue)

    # Both can progress simultaneously!
```

### Restack and Merge Workflow

```python
def handle_stack_updates(self, updated_issue):
    """Propagate changes through Graphite stack"""

    # Get all worktrees that depend on updated issue
    dependent_worktrees = self.get_dependent_worktrees(updated_issue)

    for worktree in dependent_worktrees:
        # Sync and restack automatically gets updates
        subprocess.run(f"cd {worktree} && gt sync && gt restack", shell=True)

    # Continue development with updated dependencies
```

## Agent Integration

### Current Claude Code Agents

The tool orchestrates these existing agents:

1. **epic-orchestrator**: Analyzes epics, manages progress, coordinates workflow
2. **software-architect-planner**: Designs architecture, creates blueprints
3. **issue-analyzer**: Extracts requirements and acceptance criteria
4. **tdd-test-writer**: Creates comprehensive test suites
5. **tdd-solution-coder**: Implements solutions incrementally
6. **implementation-completeness-verifier**: Validates complete implementation
7. **pr-coderabbit-fixer**: Addresses CodeRabbit review comments
8. **pr-review-expert**: Provides comprehensive PR reviews
9. **graphite-stack-manager**: Manages Graphite stack operations

### Slash Commands Used

- `/graphite-epic <number>`: Epic workflow using Graphite stacks
- `/graphite-tdd <number>`: TDD workflow in Graphite stack context
- `/review-pr <number>`: Comprehensive PR review

## Instance Management

### Auto-Discovery of KB-LLM Instances

Epic Manager automatically discovers KB-LLM instances by scanning `/opt/` for directories containing deployment markers:

```python
class InstanceDiscovery:
    def discover_instances(self):
        """Auto-discover KB-LLM instances from filesystem"""
        instances = {}

        for path in Path("/opt").iterdir():
            if not path.is_dir():
                continue

            # Check for KB-LLM markers
            if (path / "docker-compose.dev.yml").exists() and (path / "app").exists():
                instance_name = path.name
                instances[instance_name] = self.get_instance_config(instance_name)

        return instances

    def get_instance_config(self, instance_name):
        """Read configuration from instance's existing files"""
        instance_path = Path(f"/opt/{instance_name}")

        config = {
            'name': instance_name.title().replace('-', ' '),
            'path': str(instance_path),
            'repo': self.get_git_config(instance_path)
        }

        # Read docker-compose.yml for container info
        if (instance_path / "docker-compose.dev.yml").exists():
            with open(instance_path / "docker-compose.dev.yml") as f:
                compose = yaml.safe_load(f)
                if 'services' in compose and 'app' in compose['services']:
                    service = compose['services']['app']
                    config.update({
                        'container': service.get('container_name', f"{instance_name}-dev"),
                        'ports': self.extract_ports(service.get('ports', []))
                    })

        # Read .env for additional config
        env_file = instance_path / ".env"
        if env_file.exists():
            config['env'] = self.read_env_file(env_file)

        # Read app config if available
        app_config_file = instance_path / "config" / "app_config.json"
        if app_config_file.exists():
            with open(app_config_file) as f:
                config['app_config'] = json.load(f)

        return config

    def get_git_config(self, instance_path):
        """Extract git configuration from repository"""
        try:
            result = subprocess.run([
                "git", "-C", str(instance_path), "remote", "get-url", "origin"
            ], capture_output=True, text=True)

            if result.returncode == 0:
                return {
                    'url': result.stdout.strip(),
                    'branch': self.get_current_branch(instance_path)
                }
        except Exception:
            pass

        return {'url': None, 'branch': 'main'}
```

### Dev Instance Purpose

Dev instances serve as:
- **Demo environments** for testing new features
- **Interactive debugging** platforms with log monitoring
- **Integration testing** environments for complete epics
- **Client validation** systems before production deployment

Currently fixed instances (main, scottbot, feature) will eventually become dynamically created.

## Terminal User Interface

### Dashboard Layout

```
┌─ Epic Manager Dashboard ─────────────────────────────────────────────┐
│ Instance: scottbot        Epic #355: Authentication Overhaul         │
├─────────────────────────────────────────────────────────────────────┤
│ Graphite Stack            │ Active Worktrees       │ Recent Activity  │
│                          │                        │                  │
│ main                     │ issue-352/ (TDD)       │ 14:32 PR #451    │
│ └─ epic-355             │ issue-353/ (TDD)       │ ...created       │
│    ├─ 351 ✅ merged     │ issue-352-review/      │ 14:30 Tests      │
│    ├─ 352 🔄 review     │ ...CodeRabbit fixes    │ ...passing       │
│    ├─ 353 📝 progress   │                        │ 14:25 Restack    │
│    └─ 354 📝 progress   │                        │ ...completed     │
├─────────────────────────────────────────────────────────────────────┤
│ All Instances: scottbot(4/7) | feature(2/3) | main(1/2)           │
└─────────────────────────────────────────────────────────────────────┘
[s]elect instance [w]orktrees [r]eview [g]raphite [q]uit
```

### Key Features

- **Live Updates**: Real-time refresh of stack status and worktree activity
- **Keyboard Navigation**: Quick switching between instances and operations
- **Parallel Monitoring**: Track multiple Claude sessions simultaneously
- **Stack Visualization**: Clear view of Graphite branch relationships
- **Progress Tracking**: Visual progress indicators for each epic

## Implementation Plan

### Minimally Lovable Version

**Core Components:**
1. **CLI Framework**: Python Click-based command interface
2. **Worktree Manager**: Git worktree creation and management
3. **Claude Integration**: Launch Claude Code sessions in worktrees
4. **Progress Tracking**: JSON-based state persistence
5. **Basic TUI**: Rich-based status monitoring

**Key Commands:**
```bash
# Epic management
epic-mgr select scottbot              # Switch instance context
epic-mgr epic start 355               # Start epic with worktrees
epic-mgr epic status                  # Show progress across instances

# Worktree operations
epic-mgr work issue 352               # Work on issue in worktree
epic-mgr review pr 451                # Review PR in separate worktree
epic-mgr stack sync                   # Sync and restack all worktrees

# Monitoring
epic-mgr dashboard                    # Launch TUI dashboard
epic-mgr worktrees                    # Show active worktrees
```

**Workflow:**
1. Parse epic from GitHub
2. Create worktrees for parallel development
3. Launch Claude Code sessions in isolated worktrees
4. Monitor progress via TUI dashboard
5. Handle reviews in separate worktrees
6. Coordinate Graphite stack operations
7. Progressive merging and integration

### Dependencies

**Python Packages:**
```txt
click>=8.0.0                 # CLI framework
rich>=13.0.0                # Terminal formatting
textual>=0.40.0             # TUI framework
pyyaml>=6.0                 # Configuration management
asyncio                     # Async operations
subprocess                  # Process management
pathlib                     # Path handling
```

**System Requirements:**
- Python 3.11+
- Git with SSH access to repositories
- Graphite CLI (`gt`) installed and configured
- GitHub CLI (`gh`) installed and authenticated
- Access to all managed KB-LLM instances
- Claude Code CLI available in PATH

### Integration Points

**With KB-LLM Instances:**
- Git repository access
- Docker container monitoring
- Log streaming capability
- API endpoint testing

**With GitHub:**
- Epic and issue parsing
- PR status monitoring
- CodeRabbit review integration
- Merge coordination

**With Graphite:**
- Stack creation and management
- Branch relationship tracking
- Conflict resolution
- Progressive merging

## Key Benefits

### Development Efficiency

1. **True Parallelism**: Work on multiple issues simultaneously without conflicts
2. **Dependency Management**: Graphite handles complex branch relationships
3. **Review Automation**: CodeRabbit reviews happen automatically with agent fixes
4. **Interactive Testing**: Deploy to dev instances for real-world validation
5. **Progressive Integration**: Merge incrementally as work completes

### Workflow Quality

1. **Architectural Consistency**: Upfront architecture planning ensures coherence
2. **Comprehensive Testing**: TDD workflow with architectural compliance
3. **Review Quality**: Automated review fixes with human oversight
4. **Clean History**: Graphite maintains clean, reviewable PR structure
5. **Reliable Integration**: Incremental merging reduces integration risk

### Operational Visibility

1. **Real-time Monitoring**: Dashboard shows all active work across instances
2. **Clear Dependencies**: Visual representation of issue relationships
3. **Progress Tracking**: Detailed status of each epic and issue
4. **Error Recovery**: Resume from any point with saved state
5. **Multi-instance Coordination**: Manage work across different deployments

## Conclusion

Epic Manager transforms the epic development workflow from manual coordination into an automated, parallel development system. By leveraging git worktrees for isolation, Graphite for stack management, and Claude Code agents for automation, it enables true parallel development while maintaining code quality and architectural consistency.

The tool provides immediate value through its basic CLI and TUI interfaces while supporting the complete workflow from epic analysis through final integration. Its focus on the minimally lovable version ensures rapid deployment and immediate productivity gains for epic-based development workflows.