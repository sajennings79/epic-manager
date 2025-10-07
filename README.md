# Epic Manager

A demonstration project showing how to orchestrate epic-based development workflows using the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk). This tool manages parallel development across multiple software packages using git worktrees, Graphite stacked PRs, and automated Claude Code TDD workflows.

## Overview

Epic Manager showcases a pattern for coordinating complex multi-issue development workflows by:

- Launching automated Claude Code sessions via the Claude Agent SDK
- Managing parallel development through git worktrees
- Creating dependency chains with Graphite stacked PRs
- Monitoring and responding to code review feedback

This is an example implementation demonstrating Claude Agent SDK integration patterns for workflow automation.

## Key Features

**Claude Agent SDK Integration**
- Programmatic Claude Code session management
- Automated TDD workflow execution
- Streaming response handling
- Multi-session concurrency control

**Parallel Development**
- Git worktree isolation for concurrent work
- Phase-based execution with dependency management
- Automated PR creation and stack management

**Workflow Automation**
- Epic analysis and planning via Claude Code
- Automated test writing and implementation
- CodeRabbit review monitoring and auto-fixes

## Quick Start

### Prerequisites

- Python 3.11+
- Git with repository access
- Graphite CLI (`gt`) installed and configured
- GitHub CLI (`gh`) authenticated
- Claude Code CLI available in PATH

### Installation

```bash
git clone https://github.com/sajennings79/epic-manager.git
cd epic-manager
pip install -e .
```

### Basic Usage

```bash
# Discover available software packages
epic-mgr instances

# Select a package to work with
epic-mgr select package-1

# Start epic development workflow
epic-mgr epic start 123

# Monitor progress
epic-mgr dashboard
```

## Architecture

Epic Manager operates as a centralized orchestrator managing multiple software packages:

```
/opt/
├── epic-manager/           # Orchestration tool
├── package-1/              # Software package instance
├── package-2/              # Software package instance
├── package-3/              # Software package instance
└── work/                   # Parallel development workspaces
    ├── package-1-epic-123/
    │   ├── issue-101/      # Isolated worktree
    │   ├── issue-102/      # Parallel development
    │   └── issue-102-review/
    └── package-2-epic-456/
```

### Core Workflow

1. **Epic Analysis** - Claude Code analyzes GitHub epic and creates execution plan
2. **Worktree Creation** - Isolated git worktrees for each issue
3. **Parallel Development** - Concurrent Claude Code TDD sessions via SDK
4. **Stack Management** - Graphite PRs with dependency chains
5. **Review Automation** - Monitor and auto-fix CodeRabbit feedback

## Claude Agent SDK Usage

The project demonstrates key SDK patterns:

### Session Management

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def launch_tdd_workflow(worktree_path: Path, issue_number: int):
    options = ClaudeAgentOptions(cwd=str(worktree_path))

    async with ClaudeSDKClient(options=options) as client:
        # Send command to Claude Code
        await client.query(f"/tdd-workflow {issue_number}")

        # Stream responses
        async for message in client.receive_response():
            handle_response(message)
```

### Concurrent Sessions

```python
# Run multiple Claude Code sessions in parallel
tasks = [
    launch_tdd_workflow(worktree1, issue_101),
    launch_tdd_workflow(worktree2, issue_102),
    launch_tdd_workflow(worktree3, issue_103),
]

# Control concurrency with semaphore
semaphore = asyncio.Semaphore(3)
results = await asyncio.gather(*tasks)
```

## Commands

```bash
# Epic management
epic-mgr epic start <epic-number>     # Start epic workflow
epic-mgr epic status                  # Show active epics
epic-mgr epic stop <epic-number>      # Stop and cleanup

# Worktree operations
epic-mgr work issue <issue-number>    # Work on issue
epic-mgr work list                    # List worktrees
epic-mgr work cleanup <name>          # Remove worktree

# Stack management
epic-mgr stack sync                   # Sync and restack
epic-mgr stack status                 # Show stack status

# Review handling
epic-mgr review pr <pr-number>        # Review PR
epic-mgr review monitor               # Monitor for reviews

# Monitoring
epic-mgr dashboard                    # Interactive TUI
epic-mgr instances                    # List packages
epic-mgr select <instance>            # Set active package
```

## Project Structure

```
epic_manager/
├── cli.py                      # CLI entry point
├── orchestrator.py             # Epic workflow coordination
├── workspace_manager.py        # Git worktree operations
├── claude_automation.py        # Claude Agent SDK integration
├── graphite_integration.py     # Graphite stack operations
├── review_monitor.py           # CodeRabbit automation
├── instance_discovery.py       # Package discovery
└── tui/                        # Terminal UI
    ├── dashboard.py
    ├── stack_viewer.py
    └── progress_tracker.py
```

## Configuration

Configuration via `config/default_config.yaml`:

```yaml
discovery:
  search_paths: ["/opt/"]

workspace:
  base_path: "/opt/work"

claude:
  max_concurrent_sessions: 3

reviews:
  poll_interval_seconds: 60
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=epic_manager

# Code quality
black epic_manager/ tests/
isort epic_manager/ tests/
mypy epic_manager/
flake8 epic_manager/ tests/
```

## Status

This project demonstrates Claude Agent SDK integration patterns for workflow orchestration. The codebase includes scaffolded modules and test infrastructure ready for incremental development.

## Dependencies

**Core:**
- `click` - CLI framework
- `rich` - Terminal formatting
- `textual` - TUI framework
- `pyyaml` - Configuration
- `aiofiles` - Async file operations
- `httpx` - HTTP client
- `claude-agent-sdk` - Claude Code automation

**Development:**
- `pytest` - Testing
- `pytest-asyncio` - Async tests
- `black` - Code formatting
- `isort` - Import sorting
- `mypy` - Type checking

**External Tools:**
- Git - Version control and worktrees
- Graphite CLI (`gt`) - Stacked PR management
- GitHub CLI (`gh`) - GitHub integration
- Claude Code CLI - AI-powered development

## License

MIT License - see LICENSE file for details.

## Links

- [GitHub Repository](https://github.com/sajennings79/epic-manager)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
- [Claude Code Documentation](https://docs.claude.com/claude-code)
