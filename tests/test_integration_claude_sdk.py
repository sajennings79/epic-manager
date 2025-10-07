"""
Integration tests for Claude SDK functionality.

Tests Claude session management and workflow execution.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from epic_manager.claude_automation import ClaudeSessionManager
from epic_manager.models import WorkflowResult


class TestClaudeSDKIntegration:
    """Test Claude SDK integration functionality."""

    @pytest.fixture
    def claude_manager(self):
        """Create Claude session manager for testing."""
        return ClaudeSessionManager()

    @pytest.mark.asyncio
    async def test_epic_plan_request(self, claude_manager):
        """Test requesting epic plan from Claude."""
        mock_response_messages = [
            {"type": "text", "text": '{"epic": {"number": 355, "title": "Test Epic", "repo": "owner/test", "instance": "test"}, "issues": [{"number": 351, "title": "Test Issue", "status": "pending", "dependencies": [], "base_branch": "main"}], "parallelization": {"phase_1": [351]}}'}
        ]

        with patch('epic_manager.claude_automation.ClaudeSDKClient') as mock_client_class:
            # Mock the async context manager
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # Mock the response stream
            async def mock_receive_response():
                for message in mock_response_messages:
                    yield message

            mock_client.receive_response.return_value = mock_receive_response()

            # Test the method
            instance_path = Path("/opt/test")
            result = await claude_manager.get_epic_plan(instance_path, 355)

            # Verify the result contains valid JSON
            assert "epic" in result
            assert "issues" in result
            assert "parallelization" in result

            # Verify Claude SDK was called correctly
            mock_client.query.assert_called_once_with("/epic-plan 355")

    @pytest.mark.asyncio
    async def test_tdd_workflow_success(self, claude_manager):
        """Test successful TDD workflow execution."""
        mock_response_messages = [
            {"type": "text", "text": "Starting TDD workflow for issue 351"},
            {"type": "text", "text": "Writing tests..."},
            {"type": "text", "text": "Implementing solution..."},
            {"type": "text", "text": "All tests passing!"}
        ]

        with patch('epic_manager.claude_automation.ClaudeSDKClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            async def mock_receive_response():
                for message in mock_response_messages:
                    yield message

            mock_client.receive_response.return_value = mock_receive_response()

            # Test the method
            worktree_path = Path("/opt/work/test-epic-355/issue-351")
            result = await claude_manager.launch_tdd_workflow(worktree_path, 351)

            # Verify result
            assert isinstance(result, WorkflowResult)
            assert result.issue_number == 351
            assert result.success is True
            assert result.duration_seconds > 0
            assert result.error is None

            # Verify Claude SDK was called correctly
            mock_client.query.assert_called_once_with("/graphite-tdd 351")

    @pytest.mark.asyncio
    async def test_tdd_workflow_failure(self, claude_manager):
        """Test TDD workflow with failure handling."""
        with patch('epic_manager.claude_automation.ClaudeSDKClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # Simulate an exception during workflow
            mock_client.receive_response.side_effect = Exception("Test failure")

            # Test the method
            worktree_path = Path("/opt/work/test-epic-355/issue-351")
            result = await claude_manager.launch_tdd_workflow(worktree_path, 351)

            # Verify failure is handled properly
            assert isinstance(result, WorkflowResult)
            assert result.issue_number == 351
            assert result.success is False
            assert result.error == "Test failure"
            assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_parallel_tdd_workflows(self, claude_manager):
        """Test parallel execution of TDD workflows with concurrency control."""
        # Mock multiple successful workflows
        mock_results = [
            WorkflowResult(issue_number=351, success=True, duration_seconds=10.0),
            WorkflowResult(issue_number=352, success=True, duration_seconds=15.0),
            WorkflowResult(issue_number=353, success=True, duration_seconds=12.0)
        ]

        with patch.object(claude_manager, 'launch_tdd_workflow', side_effect=mock_results):
            worktree_issues = [
                (Path("/opt/work/test-epic-355/issue-351"), 351),
                (Path("/opt/work/test-epic-355/issue-352"), 352),
                (Path("/opt/work/test-epic-355/issue-353"), 353)
            ]

            results = await claude_manager.run_parallel_tdd_workflows(
                worktree_issues,
                max_concurrent=2
            )

            # Verify all workflows completed
            assert len(results) == 3
            assert all(result.success for result in results)
            assert [r.issue_number for r in results] == [351, 352, 353]

    @pytest.mark.asyncio
    async def test_review_fixer_integration(self, claude_manager):
        """Test CodeRabbit review fixer integration."""
        mock_result = WorkflowResult(
            issue_number=0,  # Generic session
            success=True,
            duration_seconds=5.0
        )

        with patch.object(claude_manager, 'launch_session', return_value=mock_result) as mock_launch:
            worktree_path = Path("/opt/work/test-epic-355/issue-351")
            result = await claude_manager.launch_review_fixer(worktree_path, 123)

            # Verify review fixer delegates to generic session launcher
            assert result == mock_result
            mock_launch.assert_called_once_with(
                worktree_path,
                "Address CodeRabbit review comments for PR 123"
            )

    def test_sdk_not_installed_handling(self):
        """Test graceful handling when Claude SDK is not installed."""
        with patch('epic_manager.claude_automation.ClaudeSDKClient', None):
            manager = ClaudeSessionManager()

            # Should not raise during initialization
            assert manager is not None

    @pytest.mark.asyncio
    async def test_sdk_not_installed_method_calls(self):
        """Test that methods raise appropriate errors when SDK is not installed."""
        with patch('epic_manager.claude_automation.ClaudeSDKClient', None):
            manager = ClaudeSessionManager()

            with pytest.raises(ImportError, match="claude-agent-sdk not installed"):
                await manager.get_epic_plan(Path("/opt/test"), 355)

            with pytest.raises(ImportError, match="claude-agent-sdk not installed"):
                await manager.launch_tdd_workflow(Path("/opt/work/test"), 351)

    @pytest.mark.asyncio
    async def test_concurrent_session_limit(self, claude_manager):
        """Test that semaphore properly limits concurrent sessions."""
        call_times = []

        async def mock_workflow(worktree, issue):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)  # Simulate work
            return WorkflowResult(issue_number=issue, success=True, duration_seconds=0.1)

        with patch.object(claude_manager, 'launch_tdd_workflow', side_effect=mock_workflow):
            worktree_issues = [
                (Path(f"/opt/work/test-epic-355/issue-{i}"), i)
                for i in range(351, 356)  # 5 issues
            ]

            # Limit to 2 concurrent sessions
            results = await claude_manager.run_parallel_tdd_workflows(
                worktree_issues,
                max_concurrent=2
            )

            # Verify all completed successfully
            assert len(results) == 5
            assert all(result.success for result in results)

            # Verify concurrency was limited (not all started at the same time)
            # First 2 should start immediately, others should be delayed
            time_gaps = [call_times[i+1] - call_times[i] for i in range(len(call_times)-1)]
            # At least some gaps should be > 0 due to semaphore limiting
            assert any(gap > 0.05 for gap in time_gaps)