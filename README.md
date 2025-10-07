# Epic Manager

A standalone development tool that orchestrates epic-based development workflows across multiple KB-LLM instances. Epic Manager provides centralized coordination for TDD workflows, Graphite stacked PRs, and automated CodeRabbit reviews while enabling parallel development through git worktrees.

## Features

- **Centralized Orchestration**: Single tool manages multiple KB-LLM deployments
- **Parallel Development**: Git worktrees enable simultaneous work on different issues
- **Graphite Integration**: Full support for stacked PRs with dependency management
- **Interactive Workflow**: Real-time monitoring with intervention capability
- **Automated Reviews**: CodeRabbit review monitoring and automatic fixes
- **TDD Workflow**: Complete test-driven development cycle automation
- **Terminal UI**: Rich interactive dashboard for monitoring and control

## Quick Start

### Prerequisites

- Python 3.11+
- Git with SSH access to repositories
- Graphite CLI (`gt`) installed and configured
- GitHub CLI (`gh`) installed and authenticated
- Claude Code CLI available in PATH

### Installation

1. **Clone and install Epic Manager:**
   ```bash
   git clone https://github.com/sajennings79/epic-manager.git
   cd epic-manager
   pip install -e .
   ```

2. **Verify installation:**
   ```bash
   epic-mgr --version
   ```

3. **Discover KB-LLM instances:**
   ```bash
   epic-mgr instances
   ```

### Basic Usage

1. **Select an instance:**
   ```bash
   epic-mgr select scottbot
   ```

2. **Start an epic:**
   ```bash
   epic-mgr epic start 355
   ```

3. **Monitor progress:**
   ```bash
   epic-mgr dashboard
   ```

4. **Work on an issue:**
   ```bash
   epic-mgr work issue 351
   ```

## Architecture

Epic Manager operates on a hub-and-spoke model:

```
/opt/
├── epic-manager/           # Centralized workflow orchestrator
├── main/                   # KB-LLM instance "main"
├── scottbot/              # KB-LLM instance "scottbot"
├── feature/               # KB-LLM instance "feature"
└── work/                  # Parallel development workspaces
    ├── scottbot-epic-355/
    │   ├── issue-351/     # Isolated worktree
    │   ├── issue-352/     # Parallel development
    │   └── issue-352-review/ # Review fixes
    └── feature-epic-290/
```

### Core Components

- **CLI Interface** (`epic_manager.cli`): Command-line interface with Click
- **Orchestrator** (`epic_manager.orchestrator`): Epic workflow coordination
- **Workspace Manager** (`epic_manager.workspace_manager`): Git worktree management
- **Instance Discovery** (`epic_manager.instance_discovery`): Auto-discover KB-LLM instances
- **Graphite Integration** (`epic_manager.graphite_integration`): Stacked PR management
- **Claude Automation** (`epic_manager.claude_automation`): Claude Code session management
- **Review Monitor** (`epic_manager.review_monitor`): CodeRabbit review automation
- **TUI Dashboard** (`epic_manager.tui.dashboard`): Interactive monitoring interface

## Commands

### Epic Management

```bash
# Start epic development workflow
epic-mgr epic start <epic-number>

# Show status of all active epics
epic-mgr epic status

# Stop epic and cleanup worktrees
epic-mgr epic stop <epic-number>
```

### Worktree Operations

```bash
# Work on issue in isolated worktree
epic-mgr work issue <issue-number>

# List all active worktrees
epic-mgr work list

# Cleanup specific worktree
epic-mgr work cleanup <worktree-name>
```

### Stack Management

```bash
# Sync and restack all worktrees
epic-mgr stack sync

# Show current Graphite stack status
epic-mgr stack status
```

### Review Management

```bash
# Review PR in separate worktree
epic-mgr review pr <pr-number>

# Monitor active PRs for CodeRabbit reviews
epic-mgr review monitor
```

### Monitoring

```bash
# Launch interactive TUI dashboard
epic-mgr dashboard

# List discovered KB-LLM instances
epic-mgr instances

# Select default instance
epic-mgr select <instance-name>
```

## The Epic Development Workflow

### 1. Epic Analysis and Planning

Epic Manager analyzes GitHub epics to extract linked issues and dependencies:

- Uses `epic-orchestrator` agent to parse GitHub epic
- Extracts linked issues and identifies execution order
- Uses `software-architect-planner` to design cohesive architecture
- Creates comprehensive execution plan

### 2. Parallel Development

Creates isolated worktrees for parallel development:

- Sets up git worktrees for each issue
- Launches Claude Code sessions in isolated environments
- Runs complete TDD workflow: analyze → test → implement → verify
- Creates Graphite stacked PRs with proper dependencies

### 3. Review and Iteration

Automated review handling:

- Monitors PRs for CodeRabbit comments (60-second intervals)
- Automatically creates review fix worktrees
- Launches `pr-coderabbit-fixer` agent to address comments
- Commits and pushes fixes to PRs

### 4. Integration and Testing

Progressive merging and validation:

- Bottom-up merge as PRs are approved
- Graphite handles dependent branch rebasing
- Deploy to dev instances for integration testing
- Final merge to main after validation

## Configuration

Configuration is managed through YAML files in the `config/` directory:

- `config/default_config.yaml`: Default settings
- `config/config.yaml`: User customizations (optional)

Key configuration sections:

- `discovery`: Instance discovery settings
- `workspace`: Worktree management
- `claude`: Claude Code integration
- `graphite`: Graphite CLI settings
- `reviews`: CodeRabbit monitoring
- `tui`: Dashboard preferences

## Development

### Project Structure

```
epic_manager/
├── __init__.py                 # Package initialization
├── cli.py                      # Main CLI entry point
├── orchestrator.py             # Epic workflow coordination
├── workspace_manager.py        # Git worktree management
├── instance_discovery.py       # Auto-discover KB-LLM instances
├── graphite_integration.py     # Graphite stack operations
├── claude_automation.py        # Claude Code session management
├── review_monitor.py           # CodeRabbit review polling
└── tui/                        # Terminal UI components
    ├── __init__.py
    ├── dashboard.py            # Main monitoring dashboard
    ├── stack_viewer.py         # Graphite stack visualization
    └── progress_tracker.py     # Epic progress monitoring
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=epic_manager

# Run specific test file
pytest tests/test_orchestrator.py

# Run integration tests only
pytest -m integration
```

### Code Quality

```bash
# Format code
black epic_manager/ tests/

# Sort imports
isort epic_manager/ tests/

# Type checking
mypy epic_manager/

# Linting
flake8 epic_manager/ tests/
```

## Current Status

🚧 **This project is currently in scaffolding phase** 🚧

Epic Manager has been scaffolded with complete module structure, type hints, and comprehensive test infrastructure. All major components are stubbed with detailed docstrings and method signatures ready for incremental TDD implementation.

**Completed:**
- ✅ Complete project structure and configuration
- ✅ All core module classes with method signatures
- ✅ Comprehensive type hints throughout
- ✅ Test infrastructure with pytest fixtures
- ✅ CLI command structure with Click
- ✅ TUI components with Textual framework
- ✅ Configuration management with YAML

**Next Steps for Implementation:**
1. **Instance Discovery** - Auto-discover KB-LLM instances
2. **Workspace Management** - Git worktree operations
3. **Claude Integration** - Session management and monitoring
4. **Graphite Operations** - Stack creation and management
5. **Epic Orchestration** - Workflow coordination
6. **Review Monitoring** - CodeRabbit integration
7. **TUI Implementation** - Interactive dashboard

Each module includes detailed TODO comments marking exactly what needs to be implemented. The codebase follows TDD principles and includes comprehensive test coverage for incremental development.

## Dependencies

**Core Runtime:**
- `click>=8.0.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting
- `textual>=0.40.0` - TUI framework
- `pyyaml>=6.0` - Configuration management
- `aiofiles>=23.0.0` - Async file operations
- `httpx>=0.24.0` - HTTP client

**Development:**
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `black>=23.0.0` - Code formatting
- `isort>=5.12.0` - Import sorting
- `mypy>=1.0.0` - Type checking

**External Tools:**
- Git - Version control and worktrees
- Graphite CLI (`gt`) - Stacked PR management
- GitHub CLI (`gh`) - GitHub integration
- Claude Code CLI - AI-powered development

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Run quality checks: `black`, `isort`, `mypy`, `flake8`
5. Ensure all tests pass: `pytest`
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/sajennings79/epic-manager).