"""
Pytest configuration and fixtures for Epic Manager tests.

Provides common test fixtures, setup, and utilities for testing
Epic Manager components.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Generator, List
from unittest.mock import Mock, MagicMock
import json
import yaml

from epic_manager.workspace_manager import WorkspaceManager
from epic_manager.instance_discovery import InstanceDiscovery
from epic_manager.orchestrator import EpicOrchestrator, EpicState, EpicIssue
from epic_manager.graphite_integration import GraphiteManager
from epic_manager.claude_automation import ClaudeSessionManager
from epic_manager.review_monitor import ReviewMonitor


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_instance_dir(temp_dir: Path) -> Path:
    """Create a mock KB-LLM instance directory structure."""
    instance_dir = temp_dir / "test-instance"
    instance_dir.mkdir()

    # Create required markers
    (instance_dir / "docker-compose.dev.yml").write_text("""
version: '3.8'
services:
  app:
    container_name: test-instance-dev
    ports:
      - "8000:8000"
    environment:
      - NODE_ENV=development
""")

    (instance_dir / "app").mkdir()
    (instance_dir / "app" / "__init__.py").touch()

    # Create .env file
    (instance_dir / ".env").write_text("""
NODE_ENV=development
PORT=8000
DATABASE_URL=postgresql://localhost/test_db
""")

    # Create config directory and app config
    config_dir = instance_dir / "config"
    config_dir.mkdir()
    (config_dir / "app_config.json").write_text(json.dumps({
        "name": "Test Instance",
        "version": "1.0.0",
        "features": ["auth", "api"]
    }))

    return instance_dir


@pytest.fixture
def mock_git_repo(temp_dir: Path) -> Path:
    """Create a mock git repository for testing."""
    repo_dir = temp_dir / "git-repo"
    repo_dir.mkdir()

    # Create .git directory to simulate git repo
    git_dir = repo_dir / ".git"
    git_dir.mkdir()

    # Create mock git config
    config_file = git_dir / "config"
    config_file.write_text("""
[core]
    repositoryformatversion = 0
    filemode = true
    bare = false
[remote "origin"]
    url = https://github.com/test-org/test-repo.git
    fetch = +refs/heads/*:refs/remotes/origin/*
[branch "main"]
    remote = origin
    merge = refs/heads/main
""")

    return repo_dir


@pytest.fixture
def sample_epic_data() -> Dict[str, Any]:
    """Provide sample epic data for testing."""
    return {
        "number": 355,
        "title": "Authentication Overhaul",
        "description": "Complete overhaul of authentication system",
        "issues": [
            {
                "number": 351,
                "title": "Implement OAuth2 integration",
                "dependencies": []
            },
            {
                "number": 352,
                "title": "Add JWT token management",
                "dependencies": [351]
            },
            {
                "number": 353,
                "title": "Update frontend authentication",
                "dependencies": [352]
            },
            {
                "number": 354,
                "title": "Integration tests",
                "dependencies": [352]
            }
        ]
    }


@pytest.fixture
def sample_epic_state(sample_epic_data: Dict[str, Any]) -> EpicState:
    """Provide sample EpicState object for testing."""
    issues = [
        EpicIssue(
            number=issue['number'],
            title=issue['title'],
            status='pending',
            dependencies=issue['dependencies']
        )
        for issue in sample_epic_data['issues']
    ]

    return EpicState(
        number=sample_epic_data['number'],
        title=sample_epic_data['title'],
        instance='test-instance',
        status='planning',
        issues=issues,
        execution_order=[351, 352, 353, 354]
    )


@pytest.fixture
def workspace_manager(temp_dir: Path) -> WorkspaceManager:
    """Provide WorkspaceManager instance for testing."""
    work_base = temp_dir / "work"
    return WorkspaceManager(work_base_path=str(work_base))


@pytest.fixture
def instance_discovery(temp_dir: Path) -> InstanceDiscovery:
    """Provide InstanceDiscovery instance for testing."""
    return InstanceDiscovery(base_path=str(temp_dir))


@pytest.fixture
def epic_orchestrator(temp_dir: Path) -> EpicOrchestrator:
    """Provide EpicOrchestrator instance for testing."""
    state_dir = temp_dir / "state"
    return EpicOrchestrator(state_dir=str(state_dir))


@pytest.fixture
def graphite_manager() -> GraphiteManager:
    """Provide GraphiteManager instance for testing."""
    return GraphiteManager(gt_command="echo")  # Use echo to avoid actual gt calls


@pytest.fixture
def claude_session_manager() -> ClaudeSessionManager:
    """Provide ClaudeSessionManager instance for testing."""
    return ClaudeSessionManager(claude_command="echo")  # Use echo to avoid actual claude calls


@pytest.fixture
def review_monitor() -> ReviewMonitor:
    """Provide ReviewMonitor instance for testing."""
    return ReviewMonitor(
        poll_interval=1,  # Short interval for testing
        gh_command="echo",  # Use echo to avoid actual gh calls
        coderabbit_username="coderabbitai"
    )


@pytest.fixture
def mock_subprocess():
    """Mock subprocess calls for testing."""
    with pytest.mock.patch('subprocess.run') as mock_run:
        # Configure default successful response
        mock_run.return_value = Mock(
            returncode=0,
            stdout="mock output",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_claude_process():
    """Mock Claude Code process for testing."""
    mock_process = Mock()
    mock_process.poll.return_value = None  # Process is running
    mock_process.returncode = None
    mock_process.pid = 12345
    return mock_process


@pytest.fixture
def mock_github_api_responses():
    """Mock GitHub API responses for testing."""
    return {
        "epic_355": {
            "number": 355,
            "title": "Authentication Overhaul",
            "state": "open",
            "body": "Complete authentication system overhaul with OAuth2 and JWT"
        },
        "pr_451": {
            "number": 451,
            "title": "Fix #351: Implement OAuth2 integration",
            "state": "open",
            "comments": [
                {
                    "id": 1,
                    "author": {"login": "coderabbitai"},
                    "body": "Consider adding error handling for OAuth failures",
                    "created_at": "2023-10-01T10:00:00Z"
                }
            ]
        }
    }


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Provide mock configuration for testing."""
    return {
        "discovery": {
            "base_path": "/opt",
            "instance_markers": ["docker-compose.dev.yml", "app/"],
            "exclude_instances": ["epic-manager"]
        },
        "workspace": {
            "work_base_path": "/opt/work",
            "auto_cleanup_completed": True,
            "keep_worktrees_days": 7
        },
        "claude": {
            "cli_command": "claude",
            "agents": {
                "epic_analysis": "epic-orchestrator",
                "architecture_planning": "software-architect-planner"
            }
        },
        "graphite": {
            "cli_command": "gt",
            "auto_restack": True,
            "auto_sync": True
        },
        "reviews": {
            "poll_interval": 60,
            "coderabbit_username": "coderabbitai",
            "auto_create_fix_worktrees": True
        },
        "logging": {
            "level": "INFO",
            "file": "data/logs/epic-manager.log"
        }
    }


@pytest.fixture
def mock_textual_app():
    """Mock Textual app for TUI testing."""
    with pytest.mock.patch('textual.app.App') as mock_app:
        yield mock_app


# Test utilities

def create_mock_worktree(base_path: Path, instance: str, epic_num: int, issue_num: int) -> Path:
    """Create a mock worktree directory structure.

    Args:
        base_path: Base path for worktrees
        instance: Instance name
        epic_num: Epic number
        issue_num: Issue number

    Returns:
        Path to created worktree
    """
    worktree_path = base_path / f"{instance}-epic-{epic_num}" / f"issue-{issue_num}"
    worktree_path.mkdir(parents=True)

    # Create some mock files
    (worktree_path / "README.md").write_text("# Test Worktree")
    (worktree_path / "src").mkdir()
    (worktree_path / "src" / "main.py").write_text("# Mock source file")

    return worktree_path


def create_mock_stack_data(epic_num: int, issues: List[int]) -> Dict[str, Any]:
    """Create mock Graphite stack data.

    Args:
        epic_num: Epic number
        issues: List of issue numbers

    Returns:
        Mock stack data dictionary
    """
    branches = {}

    # Epic branch
    epic_branch = f"epic-{epic_num}"
    branches[epic_branch] = {
        "name": epic_branch,
        "issue_number": 0,
        "status": "in_progress",
        "parent": "main",
        "children": [f"issue-{issues[0]}"] if issues else []
    }

    # Issue branches
    for i, issue_num in enumerate(issues):
        branch_name = f"issue-{issue_num}"
        parent = epic_branch if i == 0 else f"issue-{issues[i-1]}"
        children = [f"issue-{issues[i+1]}"] if i < len(issues) - 1 else []

        branches[branch_name] = {
            "name": branch_name,
            "issue_number": issue_num,
            "status": "pending",
            "parent": parent,
            "children": children,
            "commits_ahead": 0,
            "commits_behind": 0
        }

    return {
        "epic_number": epic_num,
        "branches": branches
    }


# Pytest configuration

pytest_plugins = ["pytest_asyncio"]

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_git: mark test as requiring git"
    )
    config.addinivalue_line(
        "markers", "requires_docker: mark test as requiring docker"
    )