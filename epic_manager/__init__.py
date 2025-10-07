"""
Epic Manager - Centralized Workflow Automation Tool

A standalone development tool that orchestrates epic-based development workflows
across multiple KB-LLM instances, providing centralized coordination for TDD workflows,
Graphite stacked PRs, and automated CodeRabbit reviews.
"""

__version__ = "0.1.0"
__author__ = "Epic Manager Development Team"

from .orchestrator import EpicOrchestrator
from .workspace_manager import WorkspaceManager
from .instance_discovery import InstanceDiscovery
from .graphite_integration import GraphiteManager
from .claude_automation import ClaudeSessionManager
from .review_monitor import ReviewMonitor

__all__ = [
    "EpicOrchestrator",
    "WorkspaceManager",
    "InstanceDiscovery",
    "GraphiteManager",
    "ClaudeSessionManager",
    "ReviewMonitor",
]