"""
Tests for InstanceDiscovery

Tests KB-LLM instance discovery and configuration parsing.
"""

import pytest
import json
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from epic_manager.instance_discovery import InstanceDiscovery


class TestInstanceDiscovery:
    """Test cases for InstanceDiscovery."""

    def test_init(self, temp_dir: Path):
        """Test InstanceDiscovery initialization."""
        discovery = InstanceDiscovery(base_path=str(temp_dir))

        assert discovery.base_path == temp_dir
        assert "docker-compose.dev.yml" in discovery.instance_markers
        assert "app/" in discovery.instance_markers
        assert "epic-manager" in discovery.exclude_instances

    def test_discover_instances_with_valid_instance(
        self,
        instance_discovery: InstanceDiscovery,
        mock_instance_dir: Path
    ):
        """Test discovery of valid KB-LLM instance."""
        # The mock_instance_dir should be discovered
        instances = instance_discovery.discover_instances()

        assert "test-instance" in instances
        instance_config = instances["test-instance"]

        assert instance_config["name"] == "Test Instance"
        assert instance_config["path"] == str(mock_instance_dir)
        assert "repo" in instance_config

    def test_discover_instances_empty_directory(self, temp_dir: Path):
        """Test discovery with empty directory."""
        discovery = InstanceDiscovery(base_path=str(temp_dir))
        instances = discovery.discover_instances()

        assert len(instances) == 0

    def test_discover_instances_excludes_epic_manager(self, temp_dir: Path):
        """Test that epic-manager directory is excluded."""
        # Create epic-manager directory that would otherwise be detected
        epic_manager_dir = temp_dir / "epic-manager"
        epic_manager_dir.mkdir()
        (epic_manager_dir / "docker-compose.dev.yml").touch()
        (epic_manager_dir / "app").mkdir()

        discovery = InstanceDiscovery(base_path=str(temp_dir))
        instances = discovery.discover_instances()

        assert "epic-manager" not in instances

    def test_is_kbllm_instance_valid(
        self,
        instance_discovery: InstanceDiscovery,
        mock_instance_dir: Path
    ):
        """Test _is_kbllm_instance with valid instance."""
        result = instance_discovery._is_kbllm_instance(mock_instance_dir)
        assert result is True

    def test_is_kbllm_instance_missing_markers(
        self,
        instance_discovery: InstanceDiscovery,
        temp_dir: Path
    ):
        """Test _is_kbllm_instance with missing markers."""
        incomplete_dir = temp_dir / "incomplete"
        incomplete_dir.mkdir()
        # Only create one marker, not both
        (incomplete_dir / "docker-compose.dev.yml").touch()
        # Missing app/ directory

        result = instance_discovery._is_kbllm_instance(incomplete_dir)
        assert result is False

    def test_get_instance_config(
        self,
        instance_discovery: InstanceDiscovery,
        mock_instance_dir: Path
    ):
        """Test instance configuration extraction."""
        config = instance_discovery.get_instance_config("test-instance")

        assert config["name"] == "Test Instance"
        assert config["path"] == str(mock_instance_dir)
        assert "repo" in config
        assert "docker" in config
        assert "env" in config
        assert "app_config" in config

    def test_read_docker_compose(
        self,
        instance_discovery: InstanceDiscovery,
        mock_instance_dir: Path
    ):
        """Test docker-compose configuration reading."""
        compose_file = mock_instance_dir / "docker-compose.dev.yml"
        docker_config = instance_discovery._read_docker_compose(compose_file)

        assert "services" in docker_config
        assert "app" in docker_config["services"]

        app_service = docker_config["services"]["app"]
        assert app_service["container_name"] == "test-instance-dev"
        assert len(app_service["ports"]) == 1
        assert app_service["ports"][0]["host"] == 8000
        assert app_service["ports"][0]["container"] == 8000

    def test_extract_ports(self, instance_discovery: InstanceDiscovery):
        """Test port mapping extraction."""
        port_configs = ["8000:8000", "9000", "3000:4000"]
        extracted = instance_discovery._extract_ports(port_configs)

        expected = [
            {"host": 8000, "container": 8000},
            {"host": 9000, "container": 9000},
            {"host": 3000, "container": 4000}
        ]

        assert extracted == expected

    def test_read_env_file(
        self,
        instance_discovery: InstanceDiscovery,
        mock_instance_dir: Path
    ):
        """Test .env file reading."""
        env_file = mock_instance_dir / ".env"
        env_vars = instance_discovery._read_env_file(env_file)

        assert env_vars["NODE_ENV"] == "development"
        assert env_vars["PORT"] == "8000"
        assert env_vars["DATABASE_URL"] == "postgresql://localhost/test_db"

    def test_read_app_config(
        self,
        instance_discovery: InstanceDiscovery,
        mock_instance_dir: Path
    ):
        """Test application configuration reading."""
        config_file = mock_instance_dir / "config" / "app_config.json"
        app_config = instance_discovery._read_app_config(config_file)

        assert app_config["name"] == "Test Instance"
        assert app_config["version"] == "1.0.0"
        assert "auth" in app_config["features"]
        assert "api" in app_config["features"]

    @patch('subprocess.run')
    def test_get_git_config_success(self, mock_run, instance_discovery: InstanceDiscovery):
        """Test git configuration extraction success."""
        # Mock successful git commands
        mock_run.side_effect = [
            Mock(returncode=0, stdout="https://github.com/test/repo.git\n", stderr=""),
            Mock(returncode=0, stdout="main\n", stderr="")
        ]

        instance_path = Path("/fake/path")
        git_config = instance_discovery._get_git_config(instance_path)

        assert git_config["url"] == "https://github.com/test/repo.git"
        assert git_config["branch"] == "main"

    @patch('subprocess.run')
    def test_get_git_config_failure(self, mock_run, instance_discovery: InstanceDiscovery):
        """Test git configuration extraction failure."""
        # Mock failed git command
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])

        instance_path = Path("/fake/path")
        git_config = instance_discovery._get_git_config(instance_path)

        assert git_config["url"] is None
        assert git_config["branch"] == "main"  # Default value

    def test_get_instance_status_not_implemented(self, instance_discovery: InstanceDiscovery):
        """Test that get_instance_status raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            instance_discovery.get_instance_status("test-instance")

    def test_validate_instance_not_implemented(self, instance_discovery: InstanceDiscovery):
        """Test that validate_instance raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            instance_discovery.validate_instance("test-instance")


class TestInstanceDiscoveryEdgeCases:
    """Test edge cases and error handling."""

    def test_nonexistent_base_path(self):
        """Test discovery with nonexistent base path."""
        discovery = InstanceDiscovery(base_path="/nonexistent/path")
        instances = discovery.discover_instances()

        assert len(instances) == 0

    def test_malformed_docker_compose(self, temp_dir: Path):
        """Test handling of malformed docker-compose.yml."""
        instance_dir = temp_dir / "malformed-instance"
        instance_dir.mkdir()

        # Create malformed YAML
        compose_file = instance_dir / "docker-compose.dev.yml"
        compose_file.write_text("invalid: yaml: content: [")

        (instance_dir / "app").mkdir()

        discovery = InstanceDiscovery(base_path=str(temp_dir))

        # Should handle the error gracefully
        instances = discovery.discover_instances()
        # The instance might be discovered but with incomplete config

    def test_missing_env_file(self, temp_dir: Path):
        """Test handling of missing .env file."""
        instance_dir = temp_dir / "no-env-instance"
        instance_dir.mkdir()

        # Create required markers but no .env
        (instance_dir / "docker-compose.dev.yml").write_text("version: '3.8'\nservices: {}")
        (instance_dir / "app").mkdir()

        discovery = InstanceDiscovery(base_path=str(temp_dir))
        config = discovery.get_instance_config("no-env-instance")

        # Should not have env section
        assert "env" not in config or len(config["env"]) == 0

    def test_missing_app_config(self, temp_dir: Path):
        """Test handling of missing app configuration."""
        instance_dir = temp_dir / "no-config-instance"
        instance_dir.mkdir()

        # Create required markers but no config
        (instance_dir / "docker-compose.dev.yml").write_text("version: '3.8'\nservices: {}")
        (instance_dir / "app").mkdir()

        discovery = InstanceDiscovery(base_path=str(temp_dir))
        config = discovery.get_instance_config("no-config-instance")

        # Should not have app_config section
        assert "app_config" not in config


@pytest.mark.integration
class TestInstanceDiscoveryIntegration:
    """Integration tests for instance discovery."""

    def test_full_discovery_workflow(self, temp_dir: Path):
        """Test complete discovery workflow with multiple instances."""
        # Create multiple mock instances
        for i in range(3):
            instance_dir = temp_dir / f"instance-{i}"
            instance_dir.mkdir()

            # Create required markers
            compose_content = f"""
version: '3.8'
services:
  app:
    container_name: instance-{i}-dev
    ports:
      - "{8000 + i}:{8000 + i}"
"""
            (instance_dir / "docker-compose.dev.yml").write_text(compose_content)
            (instance_dir / "app").mkdir()

            # Create .env
            (instance_dir / ".env").write_text(f"PORT={8000 + i}\nINSTANCE_NAME=instance-{i}")

        discovery = InstanceDiscovery(base_path=str(temp_dir))
        instances = discovery.discover_instances()

        assert len(instances) == 3
        for i in range(3):
            assert f"instance-{i}" in instances
            config = instances[f"instance-{i}"]
            assert f"Instance {i}" in config["name"]