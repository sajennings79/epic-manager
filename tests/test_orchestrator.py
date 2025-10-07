"""
Tests for EpicOrchestrator

Tests epic workflow coordination and state management.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from epic_manager.orchestrator import EpicOrchestrator, EpicState, EpicIssue


class TestEpicIssue:
    """Test cases for EpicIssue dataclass."""

    def test_epic_issue_creation(self):
        """Test EpicIssue creation with defaults."""
        issue = EpicIssue(number=351, title="Test Issue", status="pending")

        assert issue.number == 351
        assert issue.title == "Test Issue"
        assert issue.status == "pending"
        assert issue.dependencies == []
        assert issue.assignee is None
        assert issue.created_at is not None
        assert issue.updated_at is not None

    def test_epic_issue_with_dependencies(self):
        """Test EpicIssue creation with dependencies."""
        issue = EpicIssue(
            number=352,
            title="Dependent Issue",
            status="pending",
            dependencies=[351],
            assignee="test-user"
        )

        assert issue.dependencies == [351]
        assert issue.assignee == "test-user"


class TestEpicState:
    """Test cases for EpicState dataclass."""

    def test_epic_state_creation(self, sample_epic_state: EpicState):
        """Test EpicState creation."""
        assert sample_epic_state.number == 355
        assert sample_epic_state.title == "Authentication Overhaul"
        assert sample_epic_state.instance == "test-instance"
        assert sample_epic_state.status == "planning"
        assert len(sample_epic_state.issues) == 4
        assert sample_epic_state.execution_order == [351, 352, 353, 354]

    def test_epic_state_defaults(self):
        """Test EpicState defaults."""
        state = EpicState(
            number=100,
            title="Test Epic",
            instance="test",
            status="active",
            issues=[]
        )

        assert state.execution_order == []
        assert state.architecture_plan is None
        assert state.created_at is not None
        assert state.updated_at is not None


class TestEpicOrchestrator:
    """Test cases for EpicOrchestrator."""

    def test_init(self, epic_orchestrator: EpicOrchestrator):
        """Test EpicOrchestrator initialization."""
        assert epic_orchestrator.state_dir.exists()
        assert isinstance(epic_orchestrator._epic_cache, dict)

    def test_analyze_epic_not_implemented(self, epic_orchestrator: EpicOrchestrator):
        """Test that analyze_epic raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            epic_orchestrator.analyze_epic(355, "test-instance")

    def test_create_execution_plan_not_implemented(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test that create_execution_plan raises NotImplementedError."""
        # Save sample state first
        epic_orchestrator._save_epic_state(sample_epic_state)

        with pytest.raises(NotImplementedError):
            epic_orchestrator.create_execution_plan(355)

    def test_create_execution_plan_epic_not_found(self, epic_orchestrator: EpicOrchestrator):
        """Test create_execution_plan with nonexistent epic."""
        with pytest.raises(ValueError, match="Epic 999 not found"):
            epic_orchestrator.create_execution_plan(999)

    def test_start_epic_not_implemented(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test that start_epic raises NotImplementedError."""
        # Save sample state first
        epic_orchestrator._save_epic_state(sample_epic_state)

        with pytest.raises(NotImplementedError):
            epic_orchestrator.start_epic(355)

    def test_start_epic_not_found(self, epic_orchestrator: EpicOrchestrator):
        """Test start_epic with nonexistent epic."""
        with pytest.raises(ValueError, match="Epic 999 not found"):
            epic_orchestrator.start_epic(999)

    def test_start_epic_wrong_status(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test start_epic with epic in wrong status."""
        # Set epic to active status
        sample_epic_state.status = "active"
        epic_orchestrator._save_epic_state(sample_epic_state)

        with pytest.raises(ValueError, match="is in active state, cannot start"):
            epic_orchestrator.start_epic(355)

    def test_monitor_progress_not_implemented(self, epic_orchestrator: EpicOrchestrator):
        """Test that monitor_progress raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            epic_orchestrator.monitor_progress()

    def test_update_issue_status_success(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test successful issue status update."""
        epic_orchestrator._save_epic_state(sample_epic_state)

        result = epic_orchestrator.update_issue_status(355, 351, "in_progress")
        assert result is True

        # Verify status was updated
        updated_state = epic_orchestrator.load_epic_state(355)
        issue_351 = next(i for i in updated_state.issues if i.number == 351)
        assert issue_351.status == "in_progress"

    def test_update_issue_status_not_found(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test issue status update for nonexistent issue."""
        epic_orchestrator._save_epic_state(sample_epic_state)

        result = epic_orchestrator.update_issue_status(355, 999, "in_progress")
        assert result is False

    def test_update_issue_status_epic_not_found(self, epic_orchestrator: EpicOrchestrator):
        """Test issue status update for nonexistent epic."""
        result = epic_orchestrator.update_issue_status(999, 351, "in_progress")
        assert result is False

    def test_get_ready_issues(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test getting ready issues."""
        epic_orchestrator._save_epic_state(sample_epic_state)

        ready_issues = epic_orchestrator.get_ready_issues(355)

        # Only issue 351 should be ready (no dependencies)
        assert len(ready_issues) == 1
        assert ready_issues[0].number == 351

    def test_get_ready_issues_with_completed_dependency(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test getting ready issues after completing dependencies."""
        # Mark issue 351 as completed
        sample_epic_state.issues[0].status = "completed"  # issue 351
        epic_orchestrator._save_epic_state(sample_epic_state)

        ready_issues = epic_orchestrator.get_ready_issues(355)

        # Now issue 352 should be ready (dependency 351 completed)
        ready_numbers = [issue.number for issue in ready_issues]
        assert 352 in ready_numbers

    def test_are_dependencies_satisfied_no_deps(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test dependency check for issue with no dependencies."""
        issue_351 = sample_epic_state.issues[0]  # No dependencies
        result = epic_orchestrator._are_dependencies_satisfied(issue_351, sample_epic_state)
        assert result is True

    def test_are_dependencies_satisfied_with_completed_deps(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test dependency check with completed dependencies."""
        # Mark dependency as completed
        sample_epic_state.issues[0].status = "completed"  # issue 351

        issue_352 = sample_epic_state.issues[1]  # Depends on 351
        result = epic_orchestrator._are_dependencies_satisfied(issue_352, sample_epic_state)
        assert result is True

    def test_are_dependencies_satisfied_with_pending_deps(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test dependency check with pending dependencies."""
        issue_352 = sample_epic_state.issues[1]  # Depends on 351 (still pending)
        result = epic_orchestrator._are_dependencies_satisfied(issue_352, sample_epic_state)
        assert result is False

    def test_save_and_load_epic_state(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test saving and loading epic state."""
        # Save state
        epic_orchestrator._save_epic_state(sample_epic_state)

        # Load state
        loaded_state = epic_orchestrator.load_epic_state(355)

        assert loaded_state is not None
        assert loaded_state.number == sample_epic_state.number
        assert loaded_state.title == sample_epic_state.title
        assert loaded_state.instance == sample_epic_state.instance
        assert len(loaded_state.issues) == len(sample_epic_state.issues)

    def test_load_nonexistent_epic_state(self, epic_orchestrator: EpicOrchestrator):
        """Test loading nonexistent epic state."""
        result = epic_orchestrator.load_epic_state(999)
        assert result is None

    def test_list_active_epics(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test listing active epics."""
        # Create multiple epics with different statuses
        sample_epic_state.status = "active"
        epic_orchestrator._save_epic_state(sample_epic_state)

        # Create completed epic
        completed_epic = EpicState(
            number=356,
            title="Completed Epic",
            instance="test-instance",
            status="completed",
            issues=[]
        )
        epic_orchestrator._save_epic_state(completed_epic)

        active_epics = epic_orchestrator.list_active_epics()

        # Only the active epic should be returned
        assert len(active_epics) == 1
        assert active_epics[0].number == 355

    def test_pause_epic(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test pausing an active epic."""
        sample_epic_state.status = "active"
        epic_orchestrator._save_epic_state(sample_epic_state)

        result = epic_orchestrator.pause_epic(355)
        assert result is True

        # Verify status was updated
        updated_state = epic_orchestrator.load_epic_state(355)
        assert updated_state.status == "paused"

    def test_pause_epic_not_active(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test pausing a non-active epic."""
        # Epic is in planning status
        epic_orchestrator._save_epic_state(sample_epic_state)

        result = epic_orchestrator.pause_epic(355)
        assert result is False

    def test_resume_epic(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test resuming a paused epic."""
        sample_epic_state.status = "paused"
        epic_orchestrator._save_epic_state(sample_epic_state)

        result = epic_orchestrator.resume_epic(355)
        assert result is True

        # Verify status was updated
        updated_state = epic_orchestrator.load_epic_state(355)
        assert updated_state.status == "active"

    def test_resume_epic_not_paused(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test resuming a non-paused epic."""
        sample_epic_state.status = "active"
        epic_orchestrator._save_epic_state(sample_epic_state)

        result = epic_orchestrator.resume_epic(355)
        assert result is False


class TestEpicOrchestratorStateManagement:
    """Test state management functionality."""

    def test_epic_cache(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test epic state caching."""
        # Save state
        epic_orchestrator._save_epic_state(sample_epic_state)

        # Load state (should cache it)
        loaded_state1 = epic_orchestrator.load_epic_state(355)
        loaded_state2 = epic_orchestrator.load_epic_state(355)

        # Should be the same object from cache
        assert loaded_state1 is loaded_state2

    def test_malformed_state_file(
        self,
        epic_orchestrator: EpicOrchestrator,
        temp_dir: Path
    ):
        """Test handling of malformed state file."""
        # Create malformed JSON file
        state_file = epic_orchestrator.state_dir / "epic-999.json"
        state_file.write_text("invalid json content")

        result = epic_orchestrator.load_epic_state(999)
        assert result is None

    def test_update_issue_with_additional_fields(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test updating issue with additional fields."""
        epic_orchestrator._save_epic_state(sample_epic_state)

        result = epic_orchestrator.update_issue_status(
            355, 351, "in_progress",
            assignee="test-user",
            worktree_path="/path/to/worktree"
        )
        assert result is True

        # Verify additional fields were updated
        updated_state = epic_orchestrator.load_epic_state(355)
        issue_351 = next(i for i in updated_state.issues if i.number == 351)
        assert issue_351.assignee == "test-user"
        assert issue_351.worktree_path == "/path/to/worktree"


@pytest.mark.integration
class TestEpicOrchestratorIntegration:
    """Integration tests for EpicOrchestrator."""

    def test_full_epic_lifecycle(
        self,
        epic_orchestrator: EpicOrchestrator,
        sample_epic_state: EpicState
    ):
        """Test complete epic lifecycle."""
        # Save initial state
        epic_orchestrator._save_epic_state(sample_epic_state)

        # Start working on first issue
        epic_orchestrator.update_issue_status(355, 351, "in_progress")

        # Complete first issue
        epic_orchestrator.update_issue_status(355, 351, "completed")

        # Second issue should now be ready
        ready_issues = epic_orchestrator.get_ready_issues(355)
        assert any(issue.number == 352 for issue in ready_issues)

        # Start and complete second issue
        epic_orchestrator.update_issue_status(355, 352, "in_progress")
        epic_orchestrator.update_issue_status(355, 352, "completed")

        # Both issues 353 and 354 should now be ready (they both depend on 352)
        ready_issues = epic_orchestrator.get_ready_issues(355)
        ready_numbers = [issue.number for issue in ready_issues]
        assert 353 in ready_numbers
        assert 354 in ready_numbers