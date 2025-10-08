"""
Prompt Templates for Claude Code Workflows

Self-contained workflow prompts that replace slash commands and specialized agents.
Each prompt includes explicit step-by-step instructions, Graphite commands, and
validation criteria.
"""

TDD_WORKFLOW_PROMPT = """
Execute complete TDD workflow for GitHub issue #{issue_number} using Graphite stacked branches.

CURRENT CONTEXT:
- Worktree: {worktree_path}
- Issue: #{issue_number}

WORKFLOW STEPS:

1. SYNC GRAPHITE STACK:
   - Run: gt sync (fetch latest PR metadata from GitHub)
   - Run: gt restack (rebuild stack based on current git state)
   - Verify: gt ls shows correct stack structure
   - This ensures Graphite metadata matches git reality

2. STACK CONTEXT CHECK:
   - Run: gt ls
   - Run: gt status
   - Verify stack is up-to-date with trunk
   - Confirm current branch position in stack

3. REGISTER EXISTING BRANCH IN GRAPHITE:
   - Note: Branch 'issue-{issue_number}' already exists (created by worktree manager with correct base branch)
   - Run: git branch --show-current (should show issue-{issue_number})
   - Run: gt track issue-{issue_number}
   - This registers the pre-existing branch in Graphite's stack
   - Verify with: gt status && git status
   - DO NOT run 'gt create' - the branch already exists with the correct base

4. ANALYZE ISSUE (Requirements extraction and test scenarios):
   - Fetch issue: gh issue view {issue_number} --json title,body,comments
   - Extract all requirements from issue description
   - Identify acceptance criteria from issue body
   - List edge cases and error scenarios to test
   - Document test scenarios needed for complete coverage
   - Create test plan covering all scenarios

5. CREATE COMPREHENSIVE TEST SUITE (Test-driven development):
   - Create test files: tests/issue_{issue_number}_test_*.py
   - Write tests for ALL of the following:
     * Every acceptance criterion from the issue
     * All edge cases identified
     * Error handling scenarios
     * Integration points with existing code
   - Use descriptive test names that explain what is being tested
   - Commit tests: git commit -m "test(#{issue_number}): Add failing tests for [description]"

6. VERIFY TEST FAILURES:
   - Run: pytest tests/issue_{issue_number}_* -v
   - Confirm ALL tests fail initially
   - Verify failures are for correct reasons (NotImplementedError, missing functionality)
   - Document expected failure messages

7. IMPLEMENT FEATURE INCREMENTALLY (Step-by-step implementation):
   - Implement smallest testable increment first
   - Run tests after EACH change: pytest tests/issue_{issue_number}_* -v
   - Continue implementing until tests pass
   - Commit logical chunks with clear messages:
     * git commit -m "feat(#{issue_number}): Add data models"
     * git commit -m "feat(#{issue_number}): Implement core logic"
     * git commit -m "feat(#{issue_number}): Add API endpoints"
   - NEVER leave TODO comments or stubbed methods
   - Continue until ALL tests pass

8. VERIFY COMPLETENESS (Implementation validation):
   - Run full test suite: pytest
   - Verify ALL new tests pass
   - Run linting: flake8 .
   - Run formatting: black . && isort .
   - Search for incomplete implementations: grep -r "TODO\\|NotImplementedError\\|pass  # TODO" . --include="*.py"
   - Verify ZERO stubbed methods remain
   - Verify ALL acceptance criteria from issue are implemented
   - Fix any linting or formatting issues found

9. SUBMIT STACKED PR:
   - Review all commits: git log --oneline -10
   - Verify commit messages are clear and descriptive
   - Create PR with Graphite:
     gt submit --no-interactive \\
       --title "Fix #{issue_number}: [Descriptive title from issue]" \\
       --body "## Summary\\n\\n[Detailed description of changes made]\\n\\n## Test Coverage\\n\\n[List all tests added and what they cover]\\n\\n## Stack Position\\n\\n[Describe if this is part of an epic and any dependencies]\\n\\nFixes #{issue_number}"
   - Capture PR number from output

10. VERIFY PR BASE BRANCH:
   - Get PR number from previous step
   - Run: gh pr view <PR_NUMBER> --json baseRefName,headRefName
   - Verify baseRefName matches expected parent branch from stack
   - If PR base is 'main' but should be another issue branch:
     * Run: gh pr edit <PR_NUMBER> --base <correct-parent-branch>
     * Run: gt get (sync Graphite's local metadata with GitHub)
     * Confirm: "Fixed PR base branch to maintain stack integrity"
   - This ensures Graphite stack structure is preserved on GitHub

11. FINAL VERIFICATION:
   - Run: gt ls (verify stack structure)
   - Run: gt status (confirm PR URL)
   - Confirm ALL tests passing: pytest
   - Confirm PR created and linked to issue
   - Confirm no uncommitted changes: git status

COMPLETION CRITERIA (ALL must be true):
- ✓ Tests created and initially failed with expected errors
- ✓ ALL tests now passing
- ✓ Code linted and formatted (flake8, black, isort)
- ✓ PR submitted via Graphite with proper title and body
- ✓ PR base branch verified to match stack structure (not wrongly pointing to main)
- ✓ NO TODOs, NotImplementedError, or stub methods remaining
- ✓ Multiple logical commits with clear, descriptive messages
- ✓ All acceptance criteria from issue implemented
- ✓ No uncommitted changes in worktree

CRITICAL INSTRUCTIONS:
- Execute EACH step completely before moving to next
- Do NOT skip any validation steps
- Run tests frequently (after each implementation change)
- Verify success at each stage before proceeding
- If any step fails, stop and report the failure clearly
- Never use placeholder implementations or TODOs
- Commit frequently with descriptive messages

Begin execution now. Work methodically through each step.
"""


REVIEW_FIX_PROMPT = """
Address all CodeRabbit review comments for PR #{pr_number}.

CURRENT CONTEXT:
- Worktree: {worktree_path}
- PR: #{pr_number}

WORKFLOW:

1. FETCH REVIEW COMMENTS:
   - Run: gh pr view {pr_number} --json reviews,comments
   - Parse ALL review comments from CodeRabbit
   - Extract review suggestions from GitHub reviews
   - Group comments by:
     * File affected
     * Severity (Critical > Major > Minor > Nit)
     * Type (bug, style, performance, security, etc.)

2. ANALYZE EACH COMMENT:
   - Separate actionable from informational comments
   - Prioritize fixes by severity:
     * Critical: Security issues, bugs causing failures
     * Major: Performance issues, incorrect behavior
     * Minor: Code quality, maintainability
     * Nit: Style preferences, minor improvements
   - Create detailed fix plan for each actionable comment

3. IMPLEMENT FIXES SYSTEMATICALLY:
   For EACH CodeRabbit suggestion (in priority order):
   - Read the affected file(s)
   - Understand the current implementation
   - Implement the suggested change
   - Verify change addresses the review comment completely
   - Run tests to ensure no regression: pytest
   - Commit: git commit -m "fix(PR#{pr_number}): [Brief description of fix]\\n\\nAddresses CodeRabbit comment: [quote relevant part of comment]"

4. VERIFY ALL FIXES:
   - Run full test suite: pytest
   - Verify ALL tests still pass
   - Run linting: flake8 .
   - Run formatting: black . && isort .
   - Fix any new linting or formatting issues

5. UPDATE PR:
   - Review all fix commits: git log --oneline -5
   - Push changes: git push
   - Add comment to PR summarizing fixes:
     gh pr comment {pr_number} --body "## CodeRabbit Review Addressed\\n\\nFixed the following issues:\\n\\n[Bulleted list of each fix with commit SHA]\\n\\nAll tests passing. Ready for re-review."

COMPLETION CRITERIA:
- ✓ ALL CodeRabbit comments addressed
- ✓ Each fix committed separately with clear message
- ✓ All tests passing
- ✓ Code linted and formatted
- ✓ PR updated with summary comment
- ✓ No uncommitted changes

Execute systematically. Address every comment. Verify each fix independently.
"""


ISSUE_ANALYSIS_PROMPT = """
Analyze GitHub issue #{issue_number} and extract complete requirements.

TASKS:

1. FETCH ISSUE DATA:
   - Run: gh issue view {issue_number} --json title,body,comments,labels
   - Read the complete issue description
   - Read ALL comments for additional context

2. EXTRACT REQUIREMENTS:
   - List all explicit requirements mentioned
   - Identify implicit requirements from context
   - Note any acceptance criteria provided
   - Document technical constraints mentioned

3. IDENTIFY TEST SCENARIOS:
   - List happy path scenarios
   - Identify edge cases
   - Document error conditions to handle
   - Note integration points with existing code

4. CREATE TEST PLAN:
   - Map each requirement to test scenarios
   - Identify test coverage gaps
   - Suggest additional tests for robustness

Return a structured analysis covering all points above.
"""


IMPLEMENTATION_VERIFICATION_PROMPT = """
Verify implementation completeness for issue #{issue_number}.

VERIFICATION CHECKLIST:

1. CODE COMPLETENESS:
   - Search for TODO comments: grep -r "TODO" . --include="*.py"
   - Search for NotImplementedError: grep -r "NotImplementedError" . --include="*.py"
   - Search for stub implementations: grep -r "pass  # TODO\\|pass  # FIXME" . --include="*.py"
   - Verify ZERO placeholders found

2. TEST COVERAGE:
   - Run: pytest --cov=. tests/issue_{issue_number}_* --cov-report=term
   - Verify all new code has test coverage
   - Verify all acceptance criteria have corresponding tests

3. ACCEPTANCE CRITERIA:
   - Review original issue: gh issue view {issue_number}
   - Map each acceptance criterion to implementation
   - Verify ALL criteria are met

4. CODE QUALITY:
   - Run: flake8 .
   - Run: black --check .
   - Run: isort --check .
   - Verify ZERO issues found

5. FUNCTIONAL VERIFICATION:
   - Run full test suite: pytest
   - Verify ALL tests pass
   - No skipped tests
   - No failing tests

Report any incomplete implementations or missing requirements found.
"""


EPIC_PLAN_PROMPT = """Analyze GitHub epic #{epic_number} and create a JSON execution plan.

Read the epic and all linked issues, then return ONLY a JSON object (no markdown, no explanation) with this structure:

{{
  "epic": {{
    "number": {epic_number},
    "title": "Epic title",
    "repo": "owner/repo-name",
    "instance": "{instance_name}"
  }},
  "issues": [
    {{
      "number": 123,
      "title": "First issue - starts from main",
      "status": "pending",
      "dependencies": [],
      "base_branch": "main"
    }},
    {{
      "number": 124,
      "title": "Second issue - depends on 123",
      "status": "pending",
      "dependencies": [123],
      "base_branch": "issue-123"
    }},
    {{
      "number": 125,
      "title": "Third issue - also depends on 123",
      "status": "pending",
      "dependencies": [123],
      "base_branch": "issue-123"
    }}
  ],
  "parallelization": {{
    "phase_1": [123],
    "phase_2": [124, 125]
  }}
}}

CRITICAL INSTRUCTIONS FOR base_branch:
- base_branch MUST be a valid git branch reference, NOT a description or component name
- Use "main" for issues that start from trunk (first issue, or independent parallel issues)
- Use "issue-{{number}}" for issues that depend on another issue's branch
- The base_branch creates the Graphite stack parent-child relationship
- NEVER use folder paths, component names, or descriptions (e.g., NOT "backend/service-name")

Examples:
- First issue or independent: {{"base_branch": "main", "dependencies": []}}
- Depends on issue 123: {{"base_branch": "issue-123", "dependencies": [123]}}
- Depends on issue 124: {{"base_branch": "issue-124", "dependencies": [124]}}
- Parallel issues both starting from main: {{"base_branch": "main", "dependencies": []}}

Return ONLY the JSON, no other text."""


# System prompts for Claude Code SDK sessions

TDD_SYSTEM_PROMPT = """You are a TDD-focused software engineer using Graphite stacked PRs. Follow test-driven development principles strictly: write tests first, verify they fail, implement incrementally, commit frequently with clear messages. Never use TODO comments or placeholder implementations."""

REVIEW_FIX_SYSTEM_PROMPT = """You are a code reviewer addressing PR feedback systematically. Fetch CodeRabbit comments via gh CLI, analyze each suggestion by priority, implement fixes with clear commits, and verify all changes with tests."""
