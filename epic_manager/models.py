"""
Data Models for Epic Manager

Implementation plan-compliant data structures for epic coordination.
These models bridge Claude's /epic-plan output with Epic Manager's coordination logic.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class EpicInfo:
    """Represents epic metadata from /epic-plan command."""
    number: int
    title: str
    repo: str
    instance: str


@dataclass
class IssueInfo:
    """Represents an issue within an epic from /epic-plan command."""
    number: int
    title: str
    status: str  # 'pending', 'in_progress', 'review', 'completed'
    dependencies: List[int]
    base_branch: str  # Critical for worktree creation with correct dependencies
    worktree_path: Optional[str] = None
    pr_number: Optional[int] = None


@dataclass
class EpicPlan:
    """
    Complete epic coordination plan from Claude's /epic-plan command.

    This structure encodes all the coordination logic that Epic Manager needs:
    - Epic metadata
    - Issue dependencies via base_branch
    - Phase-based execution order
    """
    epic: EpicInfo
    issues: List[IssueInfo]
    parallelization: Dict[str, List[int]]  # phase_name -> issue_numbers

    @classmethod
    def from_json(cls, json_str: str) -> 'EpicPlan':
        """Parse JSON from /epic-plan command output.

        Args:
            json_str: JSON string from Claude's /epic-plan response

        Returns:
            EpicPlan object with parsed data

        Raises:
            json.JSONDecodeError: If JSON is invalid
            KeyError: If required fields are missing
        """
        data = json.loads(json_str)

        # Validate required top-level fields
        if 'epic' not in data:
            raise KeyError("Missing 'epic' field in JSON response")
        if 'issues' not in data:
            raise KeyError("Missing 'issues' field in JSON response")
        if 'parallelization' not in data:
            raise KeyError("Missing 'parallelization' field in JSON response")

        # Parse epic info with better error messages
        try:
            epic = EpicInfo(**data['epic'])
        except TypeError as e:
            raise KeyError(f"Invalid epic data: {e}. Epic data: {data['epic']}") from e

        # Parse issues with better error messages
        try:
            issues = [IssueInfo(**issue_data) for issue_data in data['issues']]
        except TypeError as e:
            raise KeyError(f"Invalid issue data: {e}") from e

        return cls(
            epic=epic,
            issues=issues,
            parallelization=data['parallelization']
        )

    def save(self, path: Path) -> None:
        """Persist plan to JSON file for state management.

        Args:
            path: File path to save the plan

        Raises:
            OSError: If file cannot be written
        """
        plan_data = {
            'epic': self.epic.__dict__,
            'issues': [issue.__dict__ for issue in self.issues],
            'parallelization': self.parallelization
        }

        path.write_text(json.dumps(plan_data, indent=2))

    @classmethod
    def load(cls, path: Path) -> 'EpicPlan':
        """Load plan from JSON file.

        Args:
            path: File path to load the plan from

        Returns:
            EpicPlan object loaded from file

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        return cls.from_json(path.read_text())

    def get_phase_order(self) -> List[str]:
        """Get phases in execution order.

        Returns:
            List of phase names sorted for sequential execution
        """
        return sorted(self.parallelization.keys())

    def get_issues_for_phase(self, phase_name: str) -> List[IssueInfo]:
        """Get issue objects for a specific phase.

        Args:
            phase_name: Name of the phase (e.g., 'phase_1', 'phase_2')

        Returns:
            List of IssueInfo objects for the phase
        """
        issue_numbers = self.parallelization.get(phase_name, [])
        return [issue for issue in self.issues if issue.number in issue_numbers]

    def update_issue_worktree(self, issue_number: int, worktree_path: str) -> None:
        """Update worktree path for an issue.

        Args:
            issue_number: Issue number to update
            worktree_path: Path to the created worktree
        """
        for issue in self.issues:
            if issue.number == issue_number:
                issue.worktree_path = worktree_path
                break

    def update_issue_status(self, issue_number: int, new_status: str) -> None:
        """Update status for an issue.

        Args:
            issue_number: Issue number to update
            new_status: New status value
        """
        for issue in self.issues:
            if issue.number == issue_number:
                issue.status = new_status
                break

    def get_dependency_chains(self) -> List[List[int]]:
        """Identify independent dependency chains for sequential execution.

        A dependency chain is a sequence of issues where each issue depends on
        the previous one. Issues within a chain must be executed sequentially
        to ensure parent PRs exist before creating child PRs (required for
        Graphite stacking).

        Independent chains (no shared dependencies) can be executed in parallel.

        Example:
            Issues: [581, 582, 583, 584, 585]
            Dependencies: 582→581, 583→582, 585→584
            Returns: [[581, 582, 583], [584, 585]]
                     Chain 1: 581 → 582 → 583 (sequential)
                     Chain 2: 584 → 585 (sequential, parallel to Chain 1)

        Returns:
            List of chains, where each chain is a list of issue numbers in
            dependency order (parent first, children after).
        """
        # Build dependency graph
        issue_map = {issue.number: issue for issue in self.issues}
        children = {}  # parent_issue -> [child_issues]
        has_parent = set()  # issues that have dependencies

        for issue in self.issues:
            if issue.dependencies:
                has_parent.add(issue.number)
                for dep in issue.dependencies:
                    if dep not in children:
                        children[dep] = []
                    children[dep].append(issue.number)

        # Find root issues (no dependencies)
        roots = [issue.number for issue in self.issues if issue.number not in has_parent]

        # Build chains by traversing from each root
        chains = []
        visited = set()

        def build_chain(start_issue: int) -> List[int]:
            """Build chain starting from a root issue via DFS."""
            chain = []
            stack = [start_issue]

            while stack:
                current = stack.pop(0)  # BFS to maintain order
                if current in visited:
                    continue

                visited.add(current)
                chain.append(current)

                # Add direct children to continue chain
                if current in children:
                    # Sort children by issue number for deterministic ordering
                    for child in sorted(children[current]):
                        if child not in visited:
                            stack.append(child)

            return chain

        for root in sorted(roots):  # Sort for deterministic ordering
            if root not in visited:
                chain = build_chain(root)
                if chain:
                    chains.append(chain)

        return chains


@dataclass
class WorkflowResult:
    """Result of a Claude SDK workflow execution."""
    issue_number: int
    success: bool
    duration_seconds: float
    error: Optional[str] = None
    pr_number: Optional[int] = None