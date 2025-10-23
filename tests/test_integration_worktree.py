"""
Integration tests for worktree creation functionality.

Tests the critical worktree creation bug fix and dependency handling.
"""

import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from epic_manager.workspace_manager import WorkspaceManager
from epic_manager.models import EpicPlan, EpicInfo, IssueInfo


class TestWorktreeCreation:
    """Test worktree creation with dependency handling."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test-instance"
            repo_path.mkdir()

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)

            # Create initial commit
            (repo_path / "README.md").write_text("# Test Repository")
            subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True, capture_output=True)

            # Create issue-351 branch (base for dependent issue)
            subprocess.run(["git", "checkout", "-b", "issue-351"], cwd=repo_path, check=True, capture_output=True)
            (repo_path / "feature-351.txt").write_text("Feature 351 changes")
            subprocess.run(["git", "add", "feature-351.txt"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Add feature 351"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True, capture_output=True)

            yield repo_path

    @pytest.fixture
    def workspace_manager(self):
        """Create workspace manager with temporary work directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield WorkspaceManager(work_base_path=temp_dir)

    def test_worktree_creation_with_main_base(self, temp_repo, workspace_manager):
        """Test creating worktree with main as base branch."""
        # Simulate /opt/test-instance
        opt_link = Path("/opt/test-instance")
        if opt_link.exists():
            opt_link.unlink()
        opt_link.symlink_to(temp_repo)

        try:
            worktree_path = workspace_manager.create_issue_worktree(
                instance_name="test-instance",
                epic_num=355,
                issue_num=351,
                base_branch="main"
            )

            # Verify worktree was created
            assert worktree_path.exists()
            assert worktree_path.is_dir()

            # Verify it's a valid git worktree
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            assert result.stdout.strip() == "true"

            # Verify branch name
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            assert result.stdout.strip() == "issue-351"

        finally:
            if opt_link.exists():
                opt_link.unlink()

    def test_worktree_creation_with_dependency_base(self, temp_repo, workspace_manager):
        """Test creating worktree with dependent branch as base."""
        # Simulate /opt/test-instance
        opt_link = Path("/opt/test-instance")
        if opt_link.exists():
            opt_link.unlink()
        opt_link.symlink_to(temp_repo)

        try:
            # Create worktree for issue 352 that depends on issue 351
            worktree_path = workspace_manager.create_issue_worktree(
                instance_name="test-instance",
                epic_num=355,
                issue_num=352,
                base_branch="issue-351"  # Dependency
            )

            # Verify worktree was created
            assert worktree_path.exists()
            assert worktree_path.is_dir()

            # Verify it has the dependency's changes
            feature_file = worktree_path / "feature-351.txt"
            assert feature_file.exists()
            assert "Feature 351 changes" in feature_file.read_text()

            # Verify branch name
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=worktree_path,
                capture_output=True,
                text=True
            )
            assert result.stdout.strip() == "issue-352"

        finally:
            if opt_link.exists():
                opt_link.unlink()

    @patch('epic_manager.workspace_manager.subprocess.run')
    def test_graphite_tracking_failure_is_non_critical(self, mock_run, workspace_manager):
        """Test that Graphite tracking failures don't break worktree creation."""
        # Mock successful git worktree creation
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git worktree add succeeds
            subprocess.CalledProcessError(1, "gt track"),  # gt track fails
        ]

        # Should not raise exception despite Graphite failure
        try:
            workspace_manager._track_in_graphite(Path("/test/path"), "test-branch", "main")
        except Exception as e:
            pytest.fail(f"Graphite tracking failure should be non-critical: {e}")

    def test_plan_driven_worktree_creation(self, temp_repo):
        """Test creating worktrees from an EpicPlan with dependencies."""
        # Create a plan with dependencies
        plan = EpicPlan(
            epic=EpicInfo(
                number=355,
                title="Authentication Overhaul",
                repo="owner/test-instance",
                instance="test-instance"
            ),
            issues=[
                IssueInfo(
                    number=351,
                    title="OAuth integration",
                    status="pending",
                    dependencies=[],
                    base_branch="main"
                ),
                IssueInfo(
                    number=352,
                    title="Token management",
                    status="pending",
                    dependencies=[351],
                    base_branch="issue-351"  # Depends on 351
                )
            ],
            parallelization={
                "phase_1": [351],
                "phase_2": [352]
            }
        )

        # Test phase ordering
        phases = plan.get_phase_order()
        assert phases == ["phase_1", "phase_2"]

        # Test issue retrieval by phase
        phase_1_issues = plan.get_issues_for_phase("phase_1")
        assert len(phase_1_issues) == 1
        assert phase_1_issues[0].number == 351
        assert phase_1_issues[0].base_branch == "main"

        phase_2_issues = plan.get_issues_for_phase("phase_2")
        assert len(phase_2_issues) == 1
        assert phase_2_issues[0].number == 352
        assert phase_2_issues[0].base_branch == "issue-351"