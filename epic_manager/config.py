"""
Configuration and Constants for Epic Manager

Centralizes all configuration values and magic constants used throughout the codebase.
Values can be overridden via config YAML files or environment variables.
"""

from pathlib import Path
from typing import Optional
import os


class Constants:
    """Centralized constants for Epic Manager.

    These can be overridden at runtime or via configuration files.
    """

    # Workspace paths
    WORK_BASE_PATH: str = os.getenv("EPIC_MGR_WORK_PATH", "/opt/work")
    INSTANCES_BASE_PATH: str = os.getenv("EPIC_MGR_INSTANCES_PATH", "/opt")

    # Concurrency settings
    MAX_CONCURRENT_SESSIONS: int = int(os.getenv("EPIC_MGR_MAX_CONCURRENT", "3"))

    # Review monitoring
    REVIEW_POLL_INTERVAL: int = int(os.getenv("EPIC_MGR_POLL_INTERVAL", "60"))
    CODERABBIT_USERNAME: str = os.getenv("EPIC_MGR_CODERABBIT_USER", "coderabbitai")
    MAX_FIX_ATTEMPTS: int = int(os.getenv("EPIC_MGR_MAX_FIX_ATTEMPTS", "5"))

    # External tool commands
    GRAPHITE_COMMAND: str = os.getenv("EPIC_MGR_GT_CMD", "gt")
    GITHUB_CLI_COMMAND: str = os.getenv("EPIC_MGR_GH_CMD", "gh")

    # Instance discovery
    INSTANCE_MARKERS: list = [
        "docker-compose.dev.yml",
        "app/",
    ]
    EXCLUDE_INSTANCES: set = {
        "epic-manager",
    }

    # Git operations
    DEFAULT_BRANCH: str = "main"

    # Timeouts (in seconds)
    SUBPROCESS_TIMEOUT: int = int(os.getenv("EPIC_MGR_SUBPROCESS_TIMEOUT", "300"))
    GRAPHITE_TRACK_TIMEOUT: int = 10

    @classmethod
    def get_work_base_path(cls) -> Path:
        """Get work base path as Path object."""
        return Path(cls.WORK_BASE_PATH)

    @classmethod
    def get_instances_base_path(cls) -> Path:
        """Get instances base path as Path object."""
        return Path(cls.INSTANCES_BASE_PATH)


# Configuration singleton that can be updated at runtime
_config: Optional[Constants] = None


def get_config() -> Constants:
    """Get configuration singleton.

    Returns:
        Constants object with current configuration
    """
    global _config
    if _config is None:
        _config = Constants()
    return _config


def update_config(**kwargs) -> None:
    """Update configuration values at runtime.

    Args:
        **kwargs: Configuration key-value pairs to update

    Example:
        update_config(MAX_CONCURRENT_SESSIONS=5, REVIEW_POLL_INTERVAL=30)
    """
    config = get_config()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            raise ValueError(f"Unknown configuration key: {key}")
