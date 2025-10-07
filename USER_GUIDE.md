# Epic Manager User Guide

A comprehensive guide to using Epic Manager for orchestrating epic-based development workflows across multiple KB-LLM instances.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Core Concepts](#core-concepts)
3. [Command Reference](#command-reference)
4. [Epic Development Workflow](#epic-development-workflow)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Usage](#advanced-usage)

## Getting Started

### Prerequisites

Before installing Epic Manager, ensure you have:

- **Python 3.11+** - Required runtime environment
- **Git** - With SSH access to your repositories
- **Graphite CLI** (`gt`) - Installed and configured for stacked PRs
- **GitHub CLI** (`gh`) - Installed and authenticated
- **Claude Code CLI** - Available in your PATH
- **KB-LLM instances** - One or more deployed in `/opt/`

### Installation

1. **Navigate to Epic Manager directory:**
   ```bash
   cd /opt/epic-manager
   ```

2. **Install Epic Manager:**
   ```bash
   pip install -e .
   ```

3. **Verify installation:**
   ```bash
   epic-mgr --version
   # Should output: epic-manager, version 0.1.0
   ```

4. **Discover available instances:**
   ```bash
   epic-mgr instances
   # Lists all KB-LLM instances found in /opt/
   ```

### Quick Start

1. **Select your working instance:**
   ```bash
   epic-mgr select scottbot
   ```

2. **Start an epic workflow:**
   ```bash
   epic-mgr epic start 355
   ```

3. **Monitor progress:**
   ```bash
   epic-mgr dashboard
   ```

## Core Concepts

### Epics

**Epics** are large features or initiatives that span multiple GitHub issues. Epic Manager:
- Analyzes epic requirements and linked issues
- Creates execution plans with dependency management
- Coordinates parallel development across multiple issues
- Manages progressive integration through Graphite stacks

### Instances

**Instances** are separate KB-LLM deployments discovered in `/opt/`. Each instance:
- Has its own git repository and container environment
- Can work on different epics simultaneously
- Maintains isolated development environments
- Provides dedicated resources for parallel work

### Worktrees

**Git worktrees** enable true parallel development by creating isolated working directories:
- Each issue gets its own worktree with a dedicated branch
- Multiple developers/agents can work simultaneously without conflicts
- Changes are isolated until ready for integration
- Cleanup is automatic when work completes

Example structure:
```
/opt/work/
├── scottbot-epic-355/
│   ├── issue-351/          # OAuth implementation
│   ├── issue-352/          # Token management
│   ├── issue-353/          # Frontend integration
│   └── issue-352-review/   # CodeRabbit fixes
```

### Graphite Stacks

**Graphite stacks** manage dependencies between pull requests:
- Creates stacked PRs that build on each other
- Handles automatic rebasing when dependencies change
- Enables parallel work on dependent features
- Maintains clean, reviewable PR structure

Stack example:
```
main
└─ epic-355-auth
   ├─ issue-351-oauth       ✅ merged
   ├─ issue-352-tokens      🔄 in review
   ├─ issue-353-frontend    📝 depends on 352
   └─ issue-354-integration 📝 depends on 352
```

## Command Reference

### Epic Management

#### `epic-mgr epic start <epic-number>`
Starts complete epic workflow including analysis, worktree creation, and parallel development.

```bash
# Start epic workflow
epic-mgr epic start 355

# What happens:
# 1. Analyzes epic #355 and extracts linked issues
# 2. Creates architectural plan for all issues
# 3. Sets up git worktrees for parallel development
# 4. Launches Claude Code sessions for TDD workflow
# 5. Creates Graphite stack with proper dependencies
```

#### `epic-mgr epic status`
Shows status of all active epics across instances.

```bash
epic-mgr epic status

# Example output:
# Instance: scottbot
#   Epic #355: Authentication Overhaul
#     Issue #351: ✅ OAuth implementation (merged)
#     Issue #352: 🔄 Token management (in review)
#     Issue #353: 📝 Frontend integration (in progress)
#
# Instance: feature
#   Epic #290: Data Pipeline
#     Issue #287: 📝 Stream processing (in progress)
```

#### `epic-mgr epic stop <epic-number>`
Stops epic workflow and cleans up worktrees.

```bash
epic-mgr epic stop 355

# Cleanup includes:
# - Removes all worktrees for the epic
# - Archives epic state data
# - Preserves git branches for manual cleanup if needed
```

### Instance Management

#### `epic-mgr instances`
Lists all discovered KB-LLM instances.

```bash
epic-mgr instances

# Example output:
# Available instances:
#   main     - /opt/main (container: main-dev)
#   scottbot - /opt/scottbot (container: scottbot-dev)
#   feature  - /opt/feature (container: feature-dev)
```

#### `epic-mgr select <instance-name>`
Sets the default instance for subsequent commands.

```bash
epic-mgr select scottbot
# All epic commands will now target scottbot instance
```

### Worktree Operations

#### `epic-mgr work issue <issue-number>`
Creates worktree and starts development for a specific issue.

```bash
epic-mgr work issue 352

# Creates:
# - Worktree at /opt/work/scottbot-epic-355/issue-352/
# - Git branch issue-352-token-management
# - Launches Claude Code TDD session
```

#### `epic-mgr work list`
Shows all active worktrees across instances.

```bash
epic-mgr work list

# Example output:
# Active worktrees:
#   scottbot-epic-355/issue-352/     (TDD in progress)
#   scottbot-epic-355/issue-353/     (Testing phase)
#   feature-epic-290/issue-287/      (Implementation)
```

#### `epic-mgr work cleanup <worktree-name>`
Removes specific worktree and cleans up resources.

```bash
epic-mgr work cleanup scottbot-epic-355/issue-352
```

### Stack Management

#### `epic-mgr stack sync`
Syncs and restacks all worktrees with latest changes.

```bash
epic-mgr stack sync

# For each worktree:
# 1. Pulls latest changes from dependencies
# 2. Rebases current branch on updated base
# 3. Resolves any conflicts automatically where possible
```

#### `epic-mgr stack status`
Shows current Graphite stack status.

```bash
epic-mgr stack status

# Example output:
# Graphite Stack Status:
# main
# └─ epic-355-auth
#    ├─ issue-351-oauth       ✅ Merged
#    ├─ issue-352-tokens      🔄 In Review (PR #451)
#    ├─ issue-353-frontend    📝 In Progress
#    └─ issue-354-integration 📝 In Progress
```

### Review Management

#### `epic-mgr review pr <pr-number>`
Creates review worktree for addressing PR feedback.

```bash
epic-mgr review pr 451

# Creates separate worktree for review fixes:
# - /opt/work/scottbot-epic-355/issue-352-review/
# - Launches pr-coderabbit-fixer agent
# - Addresses CodeRabbit comments automatically
```

#### `epic-mgr review monitor`
Starts background monitoring for CodeRabbit reviews.

```bash
epic-mgr review monitor

# Monitors all active PRs every 60 seconds:
# - Detects new CodeRabbit comments
# - Automatically creates fix worktrees
# - Launches agents to address feedback
# - Updates PRs with fixes
```

### Monitoring

#### `epic-mgr dashboard`
Launches interactive TUI dashboard for real-time monitoring.

```bash
epic-mgr dashboard

# Interactive dashboard shows:
# - Live epic progress across all instances
# - Graphite stack visualization
# - Active worktree status
# - Recent activity feed
# - Keyboard shortcuts for quick actions
```

## Epic Development Workflow

### Phase 1: Epic Analysis and Planning

1. **Start the epic workflow:**
   ```bash
   epic-mgr select scottbot
   epic-mgr epic start 355
   ```

2. **Epic Manager automatically:**
   - Uses `epic-orchestrator` agent to analyze GitHub epic #355
   - Extracts linked issues and identifies dependencies
   - Uses `software-architect-planner` to create cohesive architecture
   - Plans optimal execution order and parallelization strategy

3. **Review the generated plan:**
   ```bash
   epic-mgr epic status
   # Shows which issues can be worked in parallel
   # Displays dependency relationships
   ```

### Phase 2: Parallel Development

1. **Epic Manager creates isolated worktrees:**
   ```
   /opt/work/scottbot-epic-355/
   ├── issue-351/    # OAuth implementation (no dependencies)
   ├── issue-352/    # Token management (depends on 351)
   ├── issue-353/    # Frontend (depends on 352)
   └── issue-354/    # Integration (depends on 352)
   ```

2. **TDD workflow runs in each worktree:**
   - `issue-analyzer`: Extracts requirements and acceptance criteria
   - `tdd-test-writer`: Creates comprehensive test suite
   - `tdd-solution-coder`: Implements solution incrementally
   - `implementation-completeness-verifier`: Validates completion

3. **Graphite stack creation:**
   ```bash
   # Each completed issue creates stacked PR
   # Dependencies are maintained automatically
   gt submit --title "Fix #351: OAuth implementation"
   gt submit --title "Fix #352: Token management" --onto issue-351
   ```

### Phase 3: Review and Iteration

1. **Automatic CodeRabbit integration:**
   - CodeRabbit reviews PRs automatically via GitHub integration
   - Comments are added to PRs with suggestions

2. **Epic Manager monitors and responds:**
   ```bash
   epic-mgr review monitor
   # Polls PRs every 60 seconds for new CodeRabbit comments
   # Creates fix worktrees automatically when comments detected
   ```

3. **Review fix workflow:**
   ```bash
   # When CodeRabbit comments found on PR #451:
   # 1. Creates /opt/work/scottbot-epic-355/issue-352-review/
   # 2. Launches pr-coderabbit-fixer agent
   # 3. Addresses all CodeRabbit suggestions
   # 4. Commits and pushes fixes to PR
   ```

### Phase 4: Integration and Testing

1. **Progressive merging:**
   ```bash
   # As PRs are approved, merge bottom-up
   gt merge issue-351  # Base dependency merges first
   # Graphite handles dependent branch rebasing automatically
   ```

2. **Stack updates propagate:**
   ```bash
   epic-mgr stack sync
   # All dependent worktrees get updated with merged changes
   # Development continues with latest integrated code
   ```

3. **Final integration:**
   ```bash
   # When all issues complete:
   epic-mgr epic status  # Verify all issues completed
   # Epic branch ready for final review and merge to main
   ```

### Working with Multiple Issues

**Parallel development example:**
```bash
# Start epic that creates multiple worktrees
epic-mgr epic start 355

# Monitor progress across all issues
epic-mgr dashboard

# Work on specific issue if needed
epic-mgr work issue 353

# Handle reviews as they come in
epic-mgr review pr 452
```

## Configuration

Epic Manager uses YAML configuration files in the `config/` directory.

### Configuration Files

- `config/default_config.yaml` - Default settings (don't modify)
- `config/config.yaml` - User customizations (create this file)

### Key Configuration Sections

#### Instance Discovery
```yaml
discovery:
  base_path: "/opt"
  instance_markers:
    - "docker-compose.dev.yml"
    - "app/"
  exclude_instances:
    - "epic-manager"
```

#### Workspace Management
```yaml
workspace:
  work_base_path: "/opt/work"
  auto_cleanup_completed: true
  keep_worktrees_days: 7
```

#### Claude Integration
```yaml
claude:
  cli_command: "claude"
  agents:
    epic_analysis: "epic-orchestrator"
    architecture_planning: "software-architect-planner"
    issue_analysis: "issue-analyzer"
    test_writing: "tdd-test-writer"
    solution_coding: "tdd-solution-coder"
    completeness_check: "implementation-completeness-verifier"
    coderabbit_fixes: "pr-coderabbit-fixer"
    stack_management: "graphite-stack-manager"
```

#### Review Monitoring
```yaml
reviews:
  poll_interval: 60
  coderabbit_username: "coderabbitai"
  auto_create_fix_worktrees: true
```

#### TUI Dashboard
```yaml
tui:
  refresh_interval: 5
  theme: "dark"
  shortcuts:
    quit: "q"
    select_instance: "s"
    worktrees: "w"
    review: "r"
    graphite: "g"
```

### Custom Configuration

Create `config/config.yaml` to override defaults:

```yaml
# Example custom configuration
claude:
  cli_command: "/usr/local/bin/claude"

reviews:
  poll_interval: 30  # Check for reviews every 30 seconds

workspace:
  work_base_path: "/custom/work/path"
  keep_worktrees_days: 14

tui:
  theme: "light"
  refresh_interval: 3
```

## Troubleshooting

### Common Issues

#### "No instance selected" Error
```bash
# Error: No instance selected. Use 'epic-mgr select <instance>' first.
# Solution:
epic-mgr instances  # See available instances
epic-mgr select scottbot  # Select an instance
```

#### Instance Not Found
```bash
# If instances aren't discovered:
ls -la /opt/  # Verify instance directories exist
# Check for docker-compose.dev.yml and app/ in each instance
```

#### Worktree Creation Fails
```bash
# If worktree creation fails:
cd /opt/scottbot
git status  # Check repository state
git worktree list  # See existing worktrees

# Clean up if needed:
git worktree prune
```

#### Claude Code Session Fails
```bash
# Check Claude Code is available:
which claude
claude --version

# Check working directory:
ls -la /opt/work/scottbot-epic-355/issue-352/
```

#### Graphite Commands Fail
```bash
# Verify Graphite setup:
gt --version
gt auth status

# Check repository configuration:
cd /opt/scottbot
gt repo init  # If needed
```

### Debug Mode

Enable verbose output for debugging:
```bash
epic-mgr --verbose epic start 355
epic-mgr -v work issue 352
```

### Log Files

Epic Manager logs to `data/logs/epic-manager.log`:
```bash
tail -f data/logs/epic-manager.log
```

### State Recovery

If Epic Manager state becomes corrupted:
```bash
# Check state files:
ls -la data/state/

# Remove corrupted state (will restart epic):
rm data/state/epic-355-state.json

# Restart epic:
epic-mgr epic start 355
```

## Advanced Usage

### Custom Agents

Override default agents for specific workflows:
```yaml
# In config/config.yaml
claude:
  agents:
    solution_coding: "custom-tdd-coder"  # Use custom agent
```

### Multiple Instance Coordination

Work on different epics across instances:
```bash
# Instance 1: Authentication epic
epic-mgr select scottbot
epic-mgr epic start 355

# Instance 2: Data pipeline epic
epic-mgr select feature
epic-mgr epic start 290

# Monitor both:
epic-mgr dashboard  # Shows all instances
```

### Manual Worktree Management

Create worktrees manually for custom workflows:
```bash
# Create worktree without epic
cd /opt/scottbot
git worktree add /opt/work/custom-feature feature-branch

# Use with Epic Manager:
epic-mgr work list  # Will show custom worktree
```

### Review Automation Customization

```yaml
# Custom review handling
reviews:
  poll_interval: 30
  auto_create_fix_worktrees: false  # Manual review handling

# Then handle reviews manually:
epic-mgr review pr 451
```

### Graphite Stack Customization

```bash
# Custom stack operations in worktrees
cd /opt/work/scottbot-epic-355/issue-352/

# Create custom stack structure
gt create issue-352-tokens --onto issue-351-oauth
gt create issue-352-validation --onto issue-352-tokens

# Epic Manager will track custom structure
epic-mgr stack status
```

### Performance Optimization

For large epics with many issues:
```yaml
# Optimize for performance
workspace:
  auto_cleanup_completed: true
  parallel_limit: 4  # Limit concurrent Claude sessions

reviews:
  poll_interval: 120  # Reduce polling frequency
```

### Integration with CI/CD

Epic Manager can integrate with continuous integration:
```bash
# Check epic completion in CI
epic-mgr epic status --json | jq '.completed'

# Automated cleanup
epic-mgr work cleanup --completed
```

---

## Support

For additional help:
- Check project documentation in `README.md` and `SPECIFICATION.md`
- Review configuration examples in `config/default_config.yaml`
- Examine test files in `tests/` for usage patterns
- Submit issues to the project repository

Epic Manager is designed to streamline epic-based development workflows while maintaining flexibility for custom use cases. This guide covers the core functionality - explore the CLI help system for additional options:

```bash
epic-mgr --help
epic-mgr epic --help
epic-mgr work --help
```