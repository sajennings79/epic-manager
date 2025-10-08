"""
Claude Automation

Manages Claude Code sessions using the official Claude Code SDK.
Provides simple wrappers for launching TDD workflows and agent sessions.
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from rich.console import Console

from .models import WorkflowResult
from .config import Constants

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, query
    from claude_agent_sdk.types import (
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        TextBlock,
        UserMessage,
    )
except ImportError:
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    query = None
    AssistantMessage = None
    ResultMessage = None
    SystemMessage = None
    TextBlock = None
    UserMessage = None

console = Console()


class ClaudeSessionManager:
    """Manages Claude Code sessions using the official SDK."""

    def __init__(self) -> None:
        """Initialize Claude session manager."""
        if ClaudeSDKClient is None:
            console.print("[yellow]Warning: claude-agent-sdk not installed. Install with: pip install claude-agent-sdk[/yellow]")

    async def get_epic_plan(
        self,
        instance_path: Path,
        epic_number: int,
        instance_name: str
    ) -> str:
        """Request epic plan JSON from Claude using centralized prompt.

        Args:
            instance_path: Path to the KB-LLM instance repository
            epic_number: Epic number to analyze
            instance_name: Name of the KB-LLM instance

        Returns:
            JSON string from Claude's /epic-plan response

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if ClaudeSDKClient is None:
            raise ImportError("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")

        from .prompts import EPIC_PLAN_PROMPT

        console.print(f"[green]Requesting epic plan for epic {epic_number}[/green]")
        console.print(f"[blue]Instance: {instance_path}[/blue]")

        # Use bypassPermissions mode for automation - allow gh API access
        options = ClaudeAgentOptions(
            cwd=str(instance_path),
            permission_mode='bypassPermissions'
        )

        # Create prompt for epic analysis using centralized template
        prompt = EPIC_PLAN_PROMPT.format(
            epic_number=epic_number,
            instance_name=instance_name
        )

        response_parts = []
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for message in client.receive_response():
                    if isinstance(message, dict):
                        if message.get("type") == "text":
                            text = message.get("text", "")
                            response_parts.append(text)
                        elif message.get("type") == "error":
                            console.print(f"[red]Error: {message.get('error')}[/red]")
                    elif isinstance(message, AssistantMessage):
                        # Extract text from content blocks
                        try:
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    response_parts.append(block.text)
                        except Exception as e:
                            console.print(f"[yellow]Warning: Error processing message content: {e}[/yellow]")
                    elif isinstance(message, ResultMessage):
                        # Result message may contain final output
                        if hasattr(message, 'result') and message.result:
                            response_parts.append(message.result)
                    elif isinstance(message, SystemMessage):
                        # System messages are informational, skip them
                        pass
                    elif isinstance(message, UserMessage):
                        # User messages contain tool results, skip them (internal SDK flow)
                        pass
                    else:
                        # Log unexpected message types
                        console.print(f"[yellow]WARNING: Unexpected message type {type(message).__name__}[/yellow]")

        except Exception as e:
            console.print(f"[red]Error during Claude SDK communication: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            raise

        final_response = "\n".join(response_parts)
        console.print(f"[dim]Collected {len(response_parts)} response parts, total {len(final_response)} chars[/dim]")

        if not final_response.strip():
            console.print("[red]ERROR: Empty response from Claude[/red]")
            raise ValueError("Claude returned empty response")

        # Extract JSON from markdown code blocks if present
        json_response = self._extract_json_from_response(final_response)

        if not json_response.strip():
            console.print("[red]ERROR: Could not extract JSON from response[/red]")
            console.print(f"[yellow]Raw response:[/yellow]\n{final_response[:500]}")
            raise ValueError("Could not extract valid JSON from Claude's response")

        return json_response

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from response that may contain markdown code blocks.

        Args:
            response: Full response text that may contain markdown

        Returns:
            Extracted JSON string, or original response if no JSON found
        """
        import re

        # Try to extract JSON from markdown code blocks: ```json ... ```
        json_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_block_pattern, response, re.DOTALL)

        if matches:
            # Return the first JSON block found
            return matches[0].strip()

        # Try to find raw JSON (starts with { and ends with })
        json_pattern = r'\{.*\}'
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            return match.group(0)

        # No JSON found, return original
        console.print(f"[yellow]WARNING: No JSON found in response, returning as-is[/yellow]")
        return response

    def _validate_workflow_execution(
        self,
        worktree_path: Path,
        issue_number: int,
        duration: float
    ) -> Tuple[bool, str]:
        """Validate that workflow actually executed and completed work.

        Args:
            worktree_path: Path to the worktree where workflow ran
            issue_number: Issue number for logging
            duration: Workflow execution duration in seconds

        Returns:
            Tuple of (success: bool, error_message: str)
            If success is True, error_message will be empty string.
        """
        # Check 1: Duration validation (should take >30s for real work, not <1s)
        if duration < 30:
            return False, f"Workflow completed too quickly ({duration:.1f}s) - likely failed silently without doing any work"

        # Check 2: Git log validation (should have commits from workflow)
        try:
            result = subprocess.run(
                ["git", "-C", str(worktree_path), "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                check=False
            )
            if not result.stdout.strip():
                return False, "No commits created - workflow did not execute any development work"
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check git log: {e}[/yellow]")

        # Check 3: Git status validation (should be clean, not uncommitted changes)
        try:
            result = subprocess.run(
                ["git", "-C", str(worktree_path), "status", "--short"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.stdout.strip():
                return False, f"Uncommitted changes detected - workflow incomplete:\n{result.stdout}"
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check git status: {e}[/yellow]")

        # All validations passed
        return True, ""

    async def launch_tdd_workflow(
        self,
        worktree_path: Path,
        issue_number: int
    ) -> WorkflowResult:
        """Launch Claude Code TDD workflow for an issue using explicit prompt.

        Replaces /graphite-tdd slash command with self-contained workflow prompt.
        Includes validation to detect silent failures.

        Args:
            worktree_path: Path to the worktree for development
            issue_number: Issue number for context

        Returns:
            WorkflowResult with execution details

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if ClaudeSDKClient is None:
            raise ImportError("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")

        from .prompts import TDD_WORKFLOW_PROMPT, TDD_SYSTEM_PROMPT

        console.print(f"[green]Launching TDD workflow for issue {issue_number}[/green]")
        console.print(f"[blue]Worktree: {worktree_path}[/blue]")

        start_time = datetime.now()

        try:
            # Create explicit TDD workflow prompt
            prompt = TDD_WORKFLOW_PROMPT.format(
                issue_number=issue_number,
                worktree_path=worktree_path
            )

            # Configure Claude for TDD workflow with centralized system prompt
            options = ClaudeAgentOptions(
                cwd=str(worktree_path),
                permission_mode='bypassPermissions',
                system_prompt=TDD_SYSTEM_PROMPT
            )

            async with ClaudeSDKClient(options=options) as client:
                # Send explicit TDD workflow prompt
                await client.query(prompt)

                # Stream output
                async for message in client.receive_response():
                    if isinstance(message, dict):
                        if message.get("type") == "text":
                            console.print(f"[dim]{issue_number}:[/dim] {message.get('text', '')}")
                        elif message.get("type") == "error":
                            console.print(f"[red]{issue_number}: {message.get('error')}[/red]")
                    elif isinstance(message, AssistantMessage):
                        # Stream text from assistant messages
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                console.print(f"[dim]{issue_number}:[/dim] {block.text}")
                    elif isinstance(message, SystemMessage):
                        # Skip system messages
                        pass
                    elif isinstance(message, UserMessage):
                        # Skip user messages (tool results)
                        pass
                    elif isinstance(message, ResultMessage):
                        # Log result info if verbose
                        if message.is_error:
                            console.print(f"[red]{issue_number}: Workflow failed[/red]")
                    else:
                        console.print(f"[dim]{issue_number}: Received {type(message).__name__}[/dim]")

            duration = (datetime.now() - start_time).total_seconds()

            # Validate that workflow actually executed
            valid, error_msg = self._validate_workflow_execution(
                worktree_path,
                issue_number,
                duration
            )

            if not valid:
                console.print(f"[red]{issue_number}: Workflow validation failed: {error_msg}[/red]")
                return WorkflowResult(
                    issue_number=issue_number,
                    success=False,
                    duration_seconds=duration,
                    error=f"Workflow validation failed: {error_msg}"
                )

            console.print(f"[green]{issue_number}: Workflow completed and validated successfully[/green]")
            return WorkflowResult(
                issue_number=issue_number,
                success=True,
                duration_seconds=duration
            )

        except Exception as e:
            return WorkflowResult(
                issue_number=issue_number,
                success=False,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error=str(e)
            )

    async def run_parallel_tdd_workflows(
        self,
        worktree_issues: List[Tuple[Path, int]],
        max_concurrent: Optional[int] = None
    ) -> List[WorkflowResult]:
        """Run TDD workflows in parallel with concurrency limit.

        Args:
            worktree_issues: List of (worktree_path, issue_number) tuples
            max_concurrent: Maximum concurrent Claude sessions (default: from Constants)

        Returns:
            List of WorkflowResult objects with execution details
        """
        if max_concurrent is None:
            max_concurrent = Constants.MAX_CONCURRENT_SESSIONS
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_limit(worktree: Path, issue_num: int):
            async with semaphore:
                return await self.launch_tdd_workflow(worktree, issue_num)

        tasks = [run_with_limit(wt, issue) for wt, issue in worktree_issues]
        return await asyncio.gather(*tasks)

    async def run_parallel_review_fixers(
        self,
        pr_worktrees: List[Tuple[Path, int]],
        max_concurrent: Optional[int] = None
    ) -> List[WorkflowResult]:
        """Run CodeRabbit review fix workflows in parallel with concurrency limit.

        Args:
            pr_worktrees: List of (worktree_path, pr_number) tuples
            max_concurrent: Maximum concurrent Claude sessions (default: from Constants)

        Returns:
            List of WorkflowResult objects with execution details
        """
        if max_concurrent is None:
            max_concurrent = Constants.MAX_CONCURRENT_SESSIONS
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_limit(worktree: Path, pr_num: int):
            async with semaphore:
                return await self.launch_review_fixer(worktree, pr_num)

        tasks = [run_with_limit(wt, pr) for wt, pr in pr_worktrees]
        return await asyncio.gather(*tasks)

    async def launch_session(
        self,
        worktree_path: Path,
        prompt: str
    ) -> WorkflowResult:
        """Launch Claude Code with a generic prompt.

        Args:
            worktree_path: Path to the worktree
            prompt: Prompt to send to Claude

        Returns:
            WorkflowResult with execution details

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if ClaudeSDKClient is None:
            raise ImportError("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")

        console.print(f"[green]Launching Claude Code session[/green]")
        console.print(f"[blue]Worktree: {worktree_path}[/blue]")
        console.print(f"[blue]Prompt: {prompt[:100]}...[/blue]")

        start_time = datetime.now()

        try:
            options = ClaudeAgentOptions(
                cwd=str(worktree_path),
                permission_mode='bypassPermissions'
            )

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for message in client.receive_response():
                    if isinstance(message, dict):
                        if message.get("type") == "text":
                            console.print(message.get("text", ""))
                        elif message.get("type") == "error":
                            console.print(f"[red]Error: {message.get('error')}[/red]")
                    elif isinstance(message, AssistantMessage):
                        # Stream text from assistant messages
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                console.print(block.text)
                    elif isinstance(message, SystemMessage):
                        # Skip system messages
                        pass
                    elif isinstance(message, UserMessage):
                        # Skip user messages (tool results)
                        pass
                    elif isinstance(message, ResultMessage):
                        # Log result info if verbose
                        if message.is_error:
                            console.print(f"[red]Session failed[/red]")
                    else:
                        console.print(f"[dim]Received {type(message).__name__}[/dim]")

            duration = (datetime.now() - start_time).total_seconds()
            return WorkflowResult(
                issue_number=0,  # Generic session
                success=True,
                duration_seconds=duration
            )

        except Exception as e:
            return WorkflowResult(
                issue_number=0,
                success=False,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error=str(e)
            )

    async def launch_review_fixer(
        self,
        worktree_path: Path,
        pr_number: int
    ) -> WorkflowResult:
        """Launch Claude Code to fix CodeRabbit review comments using explicit workflow.

        Replaces generic prompt with detailed CodeRabbit review fixing workflow.

        Args:
            worktree_path: Path to the review worktree
            pr_number: Pull request number with CodeRabbit comments

        Returns:
            WorkflowResult with execution details

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if ClaudeSDKClient is None:
            raise ImportError("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")

        from .prompts import REVIEW_FIX_PROMPT, REVIEW_FIX_SYSTEM_PROMPT

        console.print(f"[green]Launching CodeRabbit fixer for PR {pr_number}[/green]")
        console.print(f"[blue]Review worktree: {worktree_path}[/blue]")

        # Create explicit review fixing prompt
        prompt = REVIEW_FIX_PROMPT.format(
            pr_number=pr_number,
            worktree_path=worktree_path
        )

        # Use centralized system prompt to configure review fixing behavior
        start_time = datetime.now()

        try:
            options = ClaudeAgentOptions(
                cwd=str(worktree_path),
                permission_mode='bypassPermissions',
                system_prompt=REVIEW_FIX_SYSTEM_PROMPT
            )

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for message in client.receive_response():
                    if isinstance(message, dict):
                        if message.get("type") == "text":
                            console.print(message.get("text", ""))
                        elif message.get("type") == "error":
                            console.print(f"[red]Error: {message.get('error')}[/red]")
                    elif isinstance(message, AssistantMessage):
                        # Stream text from assistant messages
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                console.print(block.text)
                    elif isinstance(message, SystemMessage):
                        # Skip system messages
                        pass
                    elif isinstance(message, UserMessage):
                        # Skip user messages (tool results)
                        pass
                    elif isinstance(message, ResultMessage):
                        # Log result info if verbose
                        if message.is_error:
                            console.print(f"[red]Review fixing failed[/red]")
                    else:
                        console.print(f"[dim]Received {type(message).__name__}[/dim]")

            duration = (datetime.now() - start_time).total_seconds()
            return WorkflowResult(
                issue_number=pr_number,
                success=True,
                duration_seconds=duration
            )

        except Exception as e:
            return WorkflowResult(
                issue_number=pr_number,
                success=False,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error=str(e)
            )

    async def simple_query(
        self,
        prompt: str,
        worktree_path: Optional[Path] = None
    ) -> str:
        """Simple query to Claude Code that returns a text response.

        Args:
            prompt: Question or task for Claude
            worktree_path: Optional working directory

        Returns:
            Text response from Claude

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if query is None:
            raise ImportError("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")

        console.print(f"[blue]Query: {prompt[:100]}...[/blue]")

        response_parts = []

        options = {}
        if worktree_path:
            options["cwd"] = str(worktree_path)

        async for message in query(prompt=prompt, **options):
            if isinstance(message, dict) and message.get("type") == "text":
                response_parts.append(message.get("text", ""))
            elif isinstance(message, str):
                response_parts.append(message)
            elif isinstance(message, AssistantMessage):
                # Extract text from assistant messages
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                # Result message may contain final output
                if message.result:
                    response_parts.append(message.result)
            elif isinstance(message, SystemMessage):
                # Skip system messages
                pass
            elif isinstance(message, UserMessage):
                # Skip user messages (tool results)
                pass
            else:
                # Handle unexpected message types
                console.print(f"[dim]Received {type(message).__name__} in simple_query[/dim]")

        return "\n".join(response_parts)