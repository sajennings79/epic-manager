"""
Instance Discovery

Auto-discovery of KB-LLM instances from filesystem.
Scans for deployment markers and extracts configuration information.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from rich.console import Console

from .config import Constants

console = Console()


class InstanceDiscovery:
    """Automatically discovers KB-LLM instances on the filesystem."""

    def __init__(self, base_path: Optional[str] = None) -> None:
        """Initialize instance discovery.

        Args:
            base_path: Base directory to scan for instances (default: from Constants)
        """
        if base_path is None:
            base_path = Constants.INSTANCES_BASE_PATH
        self.base_path = Path(base_path)

        # Markers that identify a KB-LLM instance
        self.instance_markers = Constants.INSTANCE_MARKERS

        # Instances to exclude from discovery
        self.exclude_instances = Constants.EXCLUDE_INSTANCES

    def discover_instances(self) -> Dict[str, Dict[str, Any]]:
        """Auto-discover KB-LLM instances from filesystem.

        Returns:
            Dictionary mapping instance names to their configuration

        Raises:
            OSError: If base path is not accessible
        """
        instances = {}

        if not self.base_path.exists():
            console.print(f"[red]Base path does not exist: {self.base_path}[/red]")
            return instances

        console.print(f"[green]Scanning for instances in: {self.base_path}[/green]")

        # TODO: Implement comprehensive instance discovery
        # TODO: Check for all required markers
        # TODO: Validate instance structure
        # TODO: Handle permission errors gracefully

        for path in self.base_path.iterdir():
            if not path.is_dir() or path.name in self.exclude_instances:
                continue

            if self._is_kbllm_instance(path):
                instance_name = path.name
                console.print(f"[blue]Found instance: {instance_name}[/blue]")

                try:
                    instance_config = self.get_instance_config(instance_name)
                    instances[instance_name] = instance_config
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to load config for {instance_name}: {e}[/yellow]")

        return instances

    def _is_kbllm_instance(self, path: Path) -> bool:
        """Check if directory contains KB-LLM instance markers.

        Args:
            path: Directory path to check

        Returns:
            True if path contains KB-LLM markers, False otherwise
        """
        # TODO: Implement comprehensive marker checking
        # TODO: Check for docker-compose.dev.yml AND app/ directory
        # TODO: Optional: Check for additional markers like package.json, requirements.txt

        for marker in self.instance_markers:
            marker_path = path / marker
            if not marker_path.exists():
                return False

        return True

    def get_instance_config(self, instance_name: str) -> Dict[str, Any]:
        """Read configuration from instance's existing files.

        Args:
            instance_name: Name of the instance to read config for

        Returns:
            Dictionary containing instance configuration

        Raises:
            FileNotFoundError: If instance directory doesn't exist
            yaml.YAMLError: If YAML parsing fails
            json.JSONDecodeError: If JSON parsing fails
        """
        instance_path = self.base_path / instance_name

        config = {
            'name': instance_name.title().replace('-', ' '),
            'path': str(instance_path),
            'repo': self._get_git_config(instance_path)
        }

        # TODO: Implement comprehensive config reading
        # TODO: Read docker-compose.dev.yml for container configuration
        # TODO: Read .env file for environment variables
        # TODO: Read app configuration if available
        # TODO: Extract port mappings and service information

        # Read docker-compose.yml for container info
        compose_file = instance_path / "docker-compose.dev.yml"
        if compose_file.exists():
            config['docker'] = self._read_docker_compose(compose_file)

        # Read .env for additional config
        env_file = instance_path / ".env"
        if env_file.exists():
            config['env'] = self._read_env_file(env_file)

        # Read app config if available
        app_config_file = instance_path / "config" / "app_config.json"
        if app_config_file.exists():
            config['app_config'] = self._read_app_config(app_config_file)

        return config

    def _get_git_config(self, instance_path: Path) -> Dict[str, Optional[str]]:
        """Extract git configuration from repository.

        Args:
            instance_path: Path to the instance directory

        Returns:
            Dictionary with git URL and current branch
        """
        git_config = {'url': None, 'branch': 'main'}

        # TODO: Implement git configuration extraction
        # TODO: Get remote URL using 'git remote get-url origin'
        # TODO: Get current branch using 'git branch --show-current'
        # TODO: Handle cases where git is not available or repo is not initialized

        try:
            # Get remote URL
            result = subprocess.run([
                "git", "-C", str(instance_path), "remote", "get-url", "origin"
            ], capture_output=True, text=True, check=True)

            git_config['url'] = result.stdout.strip()

            # Get current branch
            result = subprocess.run([
                "git", "-C", str(instance_path), "branch", "--show-current"
            ], capture_output=True, text=True, check=True)

            git_config['branch'] = result.stdout.strip() or 'main'

        except (subprocess.CalledProcessError, FileNotFoundError):
            # Git not available or not a git repository
            pass

        return git_config

    def _read_docker_compose(self, compose_file: Path) -> Dict[str, Any]:
        """Read docker-compose configuration.

        Args:
            compose_file: Path to docker-compose.yml file

        Returns:
            Dictionary with docker configuration

        Raises:
            yaml.YAMLError: If YAML parsing fails
        """
        # TODO: Implement docker-compose parsing
        # TODO: Extract service information
        # TODO: Get port mappings
        # TODO: Get container names

        with open(compose_file) as f:
            compose_data = yaml.safe_load(f)

        docker_config = {}

        if 'services' in compose_data:
            docker_config['services'] = {}

            for service_name, service_config in compose_data['services'].items():
                docker_config['services'][service_name] = {
                    'container_name': service_config.get('container_name', f"{compose_file.parent.name}-{service_name}"),
                    'ports': self._extract_ports(service_config.get('ports', []))
                }

        return docker_config

    def _extract_ports(self, ports: List[str]) -> List[Dict[str, Any]]:
        """Extract port mappings from docker-compose ports list.

        Args:
            ports: List of port mapping strings

        Returns:
            List of dictionaries with host and container ports
        """
        extracted_ports = []

        for port in ports:
            try:
                if isinstance(port, str) and ':' in port:
                    # Handle IP-prefixed port mappings like "127.0.0.1:8085:8080"
                    parts = port.split(':')
                    if len(parts) == 3:
                        # Format: IP:host_port:container_port
                        ip_address, host_port, container_port = parts
                        extracted_ports.append({
                            'ip': ip_address,
                            'host': int(host_port),
                            'container': int(container_port)
                        })
                    elif len(parts) == 2:
                        # Format: host_port:container_port
                        host_port, container_port = parts
                        extracted_ports.append({
                            'host': int(host_port),
                            'container': int(container_port)
                        })
                elif isinstance(port, (int, str)):
                    # Single port number
                    port_num = int(port)
                    extracted_ports.append({
                        'host': port_num,
                        'container': port_num
                    })
            except (ValueError, TypeError) as e:
                console.print(f"[yellow]Warning: Could not parse port mapping '{port}': {e}[/yellow]")
                continue

        return extracted_ports

    def _read_env_file(self, env_file: Path) -> Dict[str, str]:
        """Read environment variables from .env file.

        Args:
            env_file: Path to .env file

        Returns:
            Dictionary with environment variables

        Raises:
            OSError: If file cannot be read
        """
        # TODO: Implement .env file parsing
        # TODO: Handle comments and empty lines
        # TODO: Support quoted values
        # TODO: Handle variable expansion

        env_vars = {}

        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value.strip('"\'')

        return env_vars

    def _read_app_config(self, config_file: Path) -> Dict[str, Any]:
        """Read application configuration from JSON file.

        Args:
            config_file: Path to app config JSON file

        Returns:
            Dictionary with application configuration

        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        # TODO: Implement app config reading
        # TODO: Handle different config file formats
        # TODO: Validate config structure

        with open(config_file) as f:
            return json.load(f)

    def get_instance_status(self, instance_name: str) -> Dict[str, str]:
        """Get runtime status of an instance.

        Args:
            instance_name: Name of the instance

        Returns:
            Dictionary with status information (running, stopped, etc.)
        """
        # TODO: Implement instance status checking
        # TODO: Check if docker containers are running
        # TODO: Check if services are responding
        # TODO: Get resource usage information

        console.print(f"[green]Checking status for: {instance_name}[/green]")

        raise NotImplementedError("Instance status checking not yet implemented")

    def validate_instance(self, instance_name: str) -> bool:
        """Validate that an instance is properly configured.

        Args:
            instance_name: Name of the instance to validate

        Returns:
            True if instance is valid, False otherwise
        """
        # TODO: Implement instance validation
        # TODO: Check required files exist
        # TODO: Validate docker-compose structure
        # TODO: Check git repository status

        console.print(f"[green]Validating instance: {instance_name}[/green]")

        raise NotImplementedError("Instance validation not yet implemented")