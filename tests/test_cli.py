"""
Tests for CLI commands

Tests Click-based CLI interface for Epic Manager commands.
"""

import pytest
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import Mock, patch

from epic_manager.cli import main
from epic_manager.orchestrator import EpicState, EpicIssue


class TestEpicStatusCommand:
    """Test cases for 'epic-mgr epic status' command."""

    def test_status_no_active_epics(self, temp_dir: Path):
        """Test status command with no active epics."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Mock InstanceDiscovery to return empty results
            with patch('epic_manager.cli.InstanceDiscovery') as mock_discovery:
                mock_instance = Mock()
                mock_instance.discover_instances.return_value = {}
                mock_discovery.return_value = mock_instance

                result = runner.invoke(main, ['epic', 'status'])

                assert result.exit_code == 0
                assert "No active epics found" in result.output
                assert "epic-mgr epic start" in result.output

    def test_status_with_single_active_epic(
        self,
        temp_dir: Path
    ):
        """Test status command with single active epic."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create epic state data
            epic_state = EpicState(
                number=355,
                title="Authentication Overhaul",
                instance="test-instance",
                status='active',
                issues=[
                    EpicIssue(number=351, title="OAuth2", status="pending"),
                    EpicIssue(number=352, title="JWT", status="pending")
                ]
            )

            # Mock InstanceDiscovery and EpicOrchestrator
            with patch('epic_manager.cli.InstanceDiscovery') as mock_discovery:
                mock_instance = Mock()
                mock_instance.discover_instances.return_value = {'test-instance': {}}
                mock_discovery.return_value = mock_instance

                with patch('epic_manager.cli.EpicOrchestrator') as mock_orch_cls:
                    mock_orch = Mock()
                    mock_orch.list_active_epics.return_value = [epic_state]
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(main, ['epic', 'status'])

                    assert result.exit_code == 0
                    assert "Active Epics" in result.output
                    assert "355" in result.output
                    assert "Authentication" in result.output  # Title may be wrapped
                    assert "test-instance" in result.output

    def test_status_with_multiple_active_epics(self, temp_dir: Path):
        """Test status command with multiple active epics."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create first epic
            epic1 = EpicState(
                number=355,
                title="Authentication Overhaul",
                instance="test-instance",
                status="active",
                issues=[
                    EpicIssue(number=351, title="OAuth2", status="completed"),
                    EpicIssue(number=352, title="JWT", status="in_progress")
                ]
            )

            # Create second epic
            epic2 = EpicState(
                number=400,
                title="Database Migration",
                instance="test-instance",
                status="planning",
                issues=[
                    EpicIssue(number=401, title="Schema Update", status="pending")
                ]
            )

            # Mock InstanceDiscovery and EpicOrchestrator
            with patch('epic_manager.cli.InstanceDiscovery') as mock_discovery:
                mock_instance = Mock()
                mock_instance.discover_instances.return_value = {'test-instance': {}}
                mock_discovery.return_value = mock_instance

                with patch('epic_manager.cli.EpicOrchestrator') as mock_orch_cls:
                    mock_orch = Mock()
                    mock_orch.list_active_epics.return_value = [epic1, epic2]
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(main, ['epic', 'status'])

                    assert result.exit_code == 0
                    assert "Active Epics" in result.output
                    assert "355" in result.output
                    assert "400" in result.output
                    assert "Authentication" in result.output  # Title may be wrapped
                    assert "Database Migration" in result.output

    def test_status_with_epic_flag(
        self,
        temp_dir: Path
    ):
        """Test status command with --epic flag for detailed view."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create epic with worktree and PR info
            epic_state = EpicState(
                number=355,
                title="Authentication Overhaul",
                instance="test-instance",
                status='active',
                issues=[
                    EpicIssue(
                        number=351,
                        title="OAuth2",
                        status="completed",
                        worktree_path="/opt/work/test/issue-351",
                        pr_number=451
                    ),
                    EpicIssue(number=352, title="JWT", status="pending")
                ]
            )

            # Mock InstanceDiscovery and EpicOrchestrator
            with patch('epic_manager.cli.InstanceDiscovery') as mock_discovery:
                mock_instance = Mock()
                mock_instance.discover_instances.return_value = {'test-instance': {}}
                mock_discovery.return_value = mock_instance

                with patch('epic_manager.cli.EpicOrchestrator') as mock_orch_cls:
                    mock_orch = Mock()
                    mock_orch.load_epic_state.return_value = epic_state
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(main, ['epic', 'status', '--epic', '355'])

                    assert result.exit_code == 0
                    assert "Epic #355" in result.output
                    assert "Authentication Overhaul" in result.output
                    assert "Issues" in result.output
                    assert "#351" in result.output
                    assert "/opt/work/test/issue-351" in result.output
                    assert "#451" in result.output

    def test_status_epic_not_found(self, temp_dir: Path):
        """Test status command with invalid epic number."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Mock InstanceDiscovery and EpicOrchestrator to return no epic
            with patch('epic_manager.cli.InstanceDiscovery') as mock_discovery:
                mock_instance = Mock()
                mock_instance.discover_instances.return_value = {'test-instance': {}}
                mock_discovery.return_value = mock_instance

                with patch('epic_manager.cli.EpicOrchestrator') as mock_orch_cls:
                    mock_orch = Mock()
                    mock_orch.load_epic_state.return_value = None
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(main, ['epic', 'status', '--epic', '999'])

                    assert result.exit_code == 0
                    assert "Epic 999 not found" in result.output

    def test_status_shows_progress(self, temp_dir: Path):
        """Test that status command shows progress indicators."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create epic with mixed issue statuses
            epic = EpicState(
                number=355,
                title="Test Epic",
                instance="test-instance",
                status="active",
                issues=[
                    EpicIssue(number=351, title="Issue 1", status="completed"),
                    EpicIssue(number=352, title="Issue 2", status="in_progress"),
                    EpicIssue(number=353, title="Issue 3", status="pending"),
                ]
            )

            # Mock InstanceDiscovery and EpicOrchestrator
            with patch('epic_manager.cli.InstanceDiscovery') as mock_discovery:
                mock_instance = Mock()
                mock_instance.discover_instances.return_value = {'test-instance': {}}
                mock_discovery.return_value = mock_instance

                with patch('epic_manager.cli.EpicOrchestrator') as mock_orch_cls:
                    mock_orch = Mock()
                    mock_orch.list_active_epics.return_value = [epic]
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(main, ['epic', 'status'])

                    assert result.exit_code == 0
                    # Check for progress count
                    assert "1/3" in result.output

    def test_status_with_verbose_flag(
        self,
        temp_dir: Path
    ):
        """Test status command with verbose flag."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create state directory in the isolated filesystem
            state_dir = Path("data/state")
            state_dir.mkdir(parents=True)

            from epic_manager.orchestrator import EpicOrchestrator, EpicState, EpicIssue
            orchestrator = EpicOrchestrator()

            epic_state = EpicState(
                number=355,
                title="Test Epic",
                instance="test-instance",
                status='active',
                issues=[EpicIssue(number=351, title="Issue 1", status="pending")]
            )
            orchestrator._save_epic_state(epic_state)

            result = runner.invoke(main, ['--verbose', 'epic', 'status'])

            assert result.exit_code == 0

    def test_status_handles_corrupted_state(self, temp_dir: Path):
        """Test that status command handles corrupted state files gracefully."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create state directory with corrupted file
            state_dir = Path(temp_dir) / "data" / "state"
            state_dir.mkdir(parents=True)

            # Write invalid JSON
            state_file = state_dir / "epic-355.json"
            state_file.write_text("{ invalid json }")

            result = runner.invoke(main, ['epic', 'status'])

            # Should not crash, might show no epics or error message
            assert result.exit_code == 0


class TestHelperFunctions:
    """Test helper functions for status display."""

    def test_get_status_emoji(self):
        """Test _get_status_emoji function."""
        from epic_manager.cli import _get_status_emoji

        assert _get_status_emoji('completed') == '✓'
        assert _get_status_emoji('in_progress') == '⏳'
        assert _get_status_emoji('pending') == '○'
        assert _get_status_emoji('blocked') == '🔴'
        assert _get_status_emoji('unknown') == '?'

    def test_calculate_progress(self):
        """Test _calculate_progress function."""
        from epic_manager.cli import _calculate_progress

        issues = [
            EpicIssue(number=1, title="Issue 1", status="completed"),
            EpicIssue(number=2, title="Issue 2", status="in_progress"),
            EpicIssue(number=3, title="Issue 3", status="pending"),
        ]

        completed, total, progress_str = _calculate_progress(issues)

        assert completed == 1
        assert total == 3
        assert '✓' in progress_str
        assert '⏳' in progress_str
        assert '○' in progress_str

    def test_format_epic_summary_table(self):
        """Test _format_epic_summary_table function."""
        from epic_manager.cli import _format_epic_summary_table

        epics = [
            EpicState(
                number=355,
                title="Test Epic",
                instance="test-instance",
                status="active",
                issues=[
                    EpicIssue(number=351, title="Issue 1", status="completed"),
                    EpicIssue(number=352, title="Issue 2", status="pending")
                ]
            )
        ]

        table = _format_epic_summary_table(epics)

        # Table should have the expected structure
        assert table.title == "Active Epics"
        assert len(table.columns) == 6


class TestEpicBuildCommand:
    """Test cases for 'epic-mgr epic build' command."""

    def test_build_no_instance_selected(self, temp_dir: Path):
        """Test build command fails when no instance selected."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, ['epic', 'build', '355'])

            assert result.exit_code == 0
            assert "No instance selected" in result.output

    @patch('epic_manager.cli.EpicOrchestrator')
    def test_build_epic_not_found(self, mock_orchestrator, temp_dir: Path):
        """Test build command with non-existent epic."""
        runner = CliRunner()

        # Mock orchestrator to return None for load_epic_state
        mock_orch_instance = Mock()
        mock_orch_instance.build_epic_container.return_value = False
        mock_orchestrator.return_value = mock_orch_instance

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, ['-i', 'test-instance', 'epic', 'build', '999'])

            assert result.exit_code == 1

    @patch('epic_manager.cli.EpicOrchestrator')
    def test_build_success(self, mock_orchestrator, temp_dir: Path):
        """Test successful build command."""
        from unittest.mock import AsyncMock
        runner = CliRunner()

        # Mock successful build with AsyncMock
        mock_orch_instance = Mock()
        mock_orch_instance.build_epic_container = AsyncMock(return_value=True)
        mock_orchestrator.return_value = mock_orch_instance

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, ['-i', 'test-instance', 'epic', 'build', '355'])

            assert result.exit_code == 0
            assert "Building epic 355" in result.output

    @patch('epic_manager.cli.EpicOrchestrator')
    def test_build_with_auto_sync(self, mock_orchestrator, temp_dir: Path):
        """Test build command with --auto-sync flag."""
        runner = CliRunner()

        mock_orch_instance = Mock()
        mock_orch_instance.build_epic_container.return_value = True
        mock_orchestrator.return_value = mock_orch_instance

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, [
                '-i', 'test-instance',
                'epic', 'build', '355',
                '--auto-sync'
            ])

            # Verify auto_sync=True was passed
            mock_orch_instance.build_epic_container.assert_called_once()
            call_kwargs = mock_orch_instance.build_epic_container.call_args[1]
            assert call_kwargs['auto_sync'] is True

    @patch('epic_manager.cli.EpicOrchestrator')
    def test_build_with_skip_checks(self, mock_orchestrator, temp_dir: Path):
        """Test build command with --skip-checks flag."""
        runner = CliRunner()

        mock_orch_instance = Mock()
        mock_orch_instance.build_epic_container.return_value = True
        mock_orchestrator.return_value = mock_orch_instance

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, [
                '-i', 'test-instance',
                'epic', 'build', '355',
                '--skip-checks'
            ])

            # Verify skip_checks=True was passed
            call_kwargs = mock_orch_instance.build_epic_container.call_args[1]
            assert call_kwargs['skip_checks'] is True

    @patch('epic_manager.cli.EpicOrchestrator')
    def test_build_with_force(self, mock_orchestrator, temp_dir: Path):
        """Test build command with --force flag."""
        runner = CliRunner()

        mock_orch_instance = Mock()
        mock_orch_instance.build_epic_container.return_value = True
        mock_orchestrator.return_value = mock_orch_instance

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, [
                '-i', 'test-instance',
                'epic', 'build', '355',
                '--force'
            ])

            # Verify force=True was passed
            call_kwargs = mock_orch_instance.build_epic_container.call_args[1]
            assert call_kwargs['force'] is True

    @patch('epic_manager.cli.EpicOrchestrator')
    def test_build_with_no_cache(self, mock_orchestrator, temp_dir: Path):
        """Test build command with --no-cache flag."""
        runner = CliRunner()

        mock_orch_instance = Mock()
        mock_orch_instance.build_epic_container.return_value = True
        mock_orchestrator.return_value = mock_orch_instance

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, [
                '-i', 'test-instance',
                'epic', 'build', '355',
                '--no-cache'
            ])

            # Verify no_cache=True was passed
            call_kwargs = mock_orch_instance.build_epic_container.call_args[1]
            assert call_kwargs['no_cache'] is True

    @patch('epic_manager.cli.EpicOrchestrator')
    def test_build_failure_exits_with_error(self, mock_orchestrator, temp_dir: Path):
        """Test build command exits with error code on failure."""
        from unittest.mock import AsyncMock
        runner = CliRunner()

        # Mock failed build with AsyncMock
        mock_orch_instance = Mock()
        mock_orch_instance.build_epic_container = AsyncMock(return_value=False)
        mock_orchestrator.return_value = mock_orch_instance

        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, [
                '-i', 'test-instance',
                'epic', 'build', '355'
            ])

            assert result.exit_code == 1
            assert "build failed" in result.output
