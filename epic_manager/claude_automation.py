"""
Claude Automation

Manages Claude Code sessions using the official Claude Code SDK.
Provides simple wrappers for launching TDD workflows and agent sessions.
"""

import asyncio
import fnmatch
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
        """Request epic plan JSON from Claude using epic-planning skill.

        Args:
            instance_path: Path to the KB-LLM instance repository
            epic_number: Epic number to analyze
            instance_name: Name of the KB-LLM instance

        Returns:
            JSON string from Claude's response

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if ClaudeSDKClient is None:
            raise ImportError("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")

        console.print(f"[green]Requesting epic plan for epic {epic_number}[/green]")
        console.print(f"[blue]Instance: {instance_path}[/blue]")

        # Use bypassPermissions mode for automation - allow gh API access
        options = ClaudeAgentOptions(
            cwd=str(instance_path),
            permission_mode='bypassPermissions'
        )

        # Minimal prompt - Claude will discover epic-planning skill
        prompt = f"Analyze epic #{epic_number} for instance '{instance_name}' and create execution plan with dependencies"

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
        # Filter out temporary files that are OK to leave uncommitted
        try:
            result = subprocess.run(
                ["git", "-C", str(worktree_path), "status", "--short"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.stdout.strip():
                # Filter out temporary/helper files that are OK to leave uncommitted
                lines = result.stdout.strip().split('\n')
                problematic_files = []
                test_doc_files = []

                # Patterns for temporary files that can be ignored
                temp_patterns = [
                    'verify_*.py',
                    'test_*.tmp',
                    'debug_*.py',
                    'temp_*.py',
                    '*.pyc',
                    '__pycache__/*',
                    '.pytest_cache/*',
                    '*.log',
                    '*.swp',
                    '*~',
                    '.DS_Store',
                ]

                # Patterns for test documentation that should be auto-committed
                test_doc_patterns = [
                    'tests/RUN_TESTS_*.md',
                    'tests/TEST_SUMMARY_*.md',
                    'tests/*_tdd_plan.md',
                    'tests/*_TEST_SUMMARY.md',
                ]

                for line in lines:
                    if not line.strip():
                        continue

                    # Extract filename from git status short format (e.g., "?? filename" or " M filename")
                    parts = line.split(maxsplit=1)
                    if len(parts) < 2:
                        continue
                    filename = parts[1].strip()

                    # Check if file matches temp patterns (can be ignored)
                    is_temp = any(
                        fnmatch.fnmatch(filename, pattern)
                        for pattern in temp_patterns
                    )

                    # Check if file is test documentation (should be auto-committed)
                    is_test_doc = any(
                        fnmatch.fnmatch(filename, pattern)
                        for pattern in test_doc_patterns
                    )

                    if is_temp:
                        continue  # Ignore temporary files
                    elif is_test_doc:
                        test_doc_files.append(filename)
                    else:
                        problematic_files.append(line)

                # Auto-commit test documentation files if found
                if test_doc_files:
                    console.print(f"[yellow]Auto-committing test documentation files: {', '.join(test_doc_files)}[/yellow]")
                    try:
                        subprocess.run(
                            ["git", "-C", str(worktree_path), "add"] + test_doc_files,
                            check=True,
                            capture_output=True
                        )
                        subprocess.run(
                            ["git", "-C", str(worktree_path), "commit", "-m", f"docs(#{issue_number}): Add test documentation"],
                            check=True,
                            capture_output=True
                        )
                        console.print(f"[green]✓ Auto-committed {len(test_doc_files)} test documentation file(s)[/green]")
                    except subprocess.CalledProcessError as e:
                        console.print(f"[yellow]Warning: Could not auto-commit test docs: {e}[/yellow]")
                        # Still include in problematic files if commit failed
                        problematic_files.extend([f"?? {f}" for f in test_doc_files])

                if problematic_files:
                    return False, f"Uncommitted changes detected - workflow incomplete:\n" + "\n".join(problematic_files)
                elif test_doc_files:
                    # Test docs were auto-committed, re-check git status
                    console.print(f"[dim]Verifying worktree is now clean...[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check git status: {e}[/yellow]")

        # All validations passed
        return True, ""

    def _extract_pr_number_from_output(self, output_text: str) -> Optional[int]:
        """Extract PR number from Claude's output.

        Looks for patterns like:
        - "PR #123 created"
        - "Created PR #456"
        - "#789"
        - "Pull request #123"

        Args:
            output_text: Text output from Claude Code session

        Returns:
            PR number if found, None otherwise
        """
        import re

        # Try multiple patterns in order of specificity
        patterns = [
            r'PR #(\d+) created',
            r'Created PR #(\d+)',
            r'Pull request #(\d+)',
            r'pull request #(\d+)',
            r'PR #(\d+)',
            r'#(\d+)',  # Fallback: any #number (last resort)
        ]

        for pattern in patterns:
            match = re.search(pattern, output_text, re.IGNORECASE)
            if match:
                pr_num = int(match.group(1))
                # Sanity check: PR numbers are usually < 10000 for most repos
                if pr_num < 100000:
                    console.print(f"[blue]Extracted PR number: {pr_num}[/blue]")
                    return pr_num

        return None

    async def launch_tdd_workflow(
        self,
        worktree_path: Path,
        issue_number: int
    ) -> WorkflowResult:
        """Launch Claude Code TDD workflow for an issue using tdd-graphite-workflow skill.

        Claude discovers the skill from worktree/.claude/skills/ and executes autonomously.
        Includes validation to detect silent failures and PR number extraction.

        Args:
            worktree_path: Path to the worktree for development
            issue_number: Issue number for context

        Returns:
            WorkflowResult with execution details and PR number

        Raises:
            ImportError: If claude-agent-sdk is not installed
        """
        if ClaudeSDKClient is None:
            raise ImportError("claude-agent-sdk not installed. Install with: pip install claude-agent-sdk")

        console.print(f"[green]Launching TDD workflow for issue {issue_number}[/green]")
        console.print(f"[blue]Worktree: {worktree_path}[/blue]")

        start_time = datetime.now()
        pr_number = None
        full_output = []  # Collect all output for PR number extraction

        try:
            # Minimal prompt - Claude will discover tdd-graphite-workflow skill
            prompt = f"Execute TDD workflow for GitHub issue #{issue_number}"

            # Configure Claude for TDD workflow - skills are in worktree/.claude/skills/
            options = ClaudeAgentOptions(
                cwd=str(worktree_path),
                permission_mode='bypassPermissions'
            )

            async with ClaudeSDKClient(options=options) as client:
                # Send explicit TDD workflow prompt
                await client.query(prompt)

                # Stream output and collect for PR extraction
                async for message in client.receive_response():
                    if isinstance(message, dict):
                        if message.get("type") == "text":
                            text = message.get('text', '')
                            full_output.append(text)
                            console.print(f"[dim]{issue_number}:[/dim] {text}")
                        elif message.get("type") == "error":
                            console.print(f"[red]{issue_number}: {message.get('error')}[/red]")
                    elif isinstance(message, AssistantMessage):
                        # Stream text from assistant messages
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                full_output.append(block.text)
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

            # Extract PR number from collected output
            combined_output = "\n".join(full_output)
            pr_number = self._extract_pr_number_from_output(combined_output)

            if not pr_number:
                # Fallback: Try to find PR via gh CLI
                console.print(f"[yellow]{issue_number}: Could not extract PR from output, checking GitHub...[/yellow]")
                pr_number = self._find_pr_for_issue_branch(worktree_path, issue_number)

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
                    error=f"Workflow validation failed: {error_msg}",
                    pr_number=pr_number
                )

            console.print(f"[green]{issue_number}: Workflow completed and validated successfully[/green]")
            if pr_number:
                console.print(f"[green]{issue_number}: PR #{pr_number} created[/green]")

            return WorkflowResult(
                issue_number=issue_number,
                success=True,
                duration_seconds=duration,
                pr_number=pr_number
            )

        except Exception as e:
            return WorkflowResult(
                issue_number=issue_number,
                success=False,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error=str(e),
                pr_number=pr_number
            )

    def _find_pr_for_issue_branch(self, worktree_path: Path, issue_number: int) -> Optional[int]:
        """Find PR for issue branch using gh CLI.

        Args:
            worktree_path: Path to the worktree
            issue_number: Issue number

        Returns:
            PR number if found, None otherwise
        """
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--head", f"issue-{issue_number}", "--json", "number"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                pr_list = json.loads(result.stdout)
                if pr_list:
                    pr_num = pr_list[0]['number']
                    console.print(f"[blue]Found PR #{pr_num} via gh CLI for issue {issue_number}[/blue]")
                    return pr_num

        except Exception as e:
            console.print(f"[dim]Could not find PR via gh CLI: {e}[/dim]")

        return None

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
        """Launch Claude Code to fix CodeRabbit review comments using review-fixer skill.

        Claude discovers the skill and executes the review fixing workflow autonomously.

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

        console.print(f"[green]Launching CodeRabbit fixer for PR {pr_number}[/green]")
        console.print(f"[blue]Review worktree: {worktree_path}[/blue]")

        # Minimal prompt - Claude will discover review-fixer skill
        prompt = f"Fix CodeRabbit review comments for PR #{pr_number}"

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