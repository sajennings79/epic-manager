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

IMPORTANT: SEQUENTIAL EXECUTION FOR PROPER PR STACKING
This workflow is part of a dependency chain where PRs must be created sequentially
to ensure correct Graphite stacking. The parent issue's PR must exist on GitHub
BEFORE this issue creates its PR. Epic Manager handles the sequencing - your job
is to complete the TDD workflow and create the PR via 'gt submit'. Epic Manager
will verify the PR exists before starting dependent issues.

Why this matters: Graphite determines PR base branches from git ancestry. If a
parent PR doesn't exist when 'gt submit' runs, Graphite falls back to targeting
main, breaking the stack. Sequential execution prevents this.

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
   - **Invoke issue-analyzer agent** for comprehensive requirements extraction
   - Fetch issue: gh issue view {issue_number} --json title,body,comments
   - Extract all requirements from issue description
   - Identify acceptance criteria from issue body
   - List edge cases and error scenarios to test
   - Document test scenarios needed for complete coverage
   - Create test plan covering all scenarios

4.5. SCHEMA DISCOVERY (CRITICAL - Prevents field name bugs):
   **WHY**: Field names are NOT guessable - must read actual model definitions
   **HOW**:
   - Identify all models that will be modified or used
   - Read each model definition file (app/models/...)
   - Document ALL field names EXACTLY as defined in the model
   - Create schema reference list for implementation
   - **RULE**: Implementation may ONLY reference documented fields

   **EXAMPLE**: For MeetingState in app/models/meeting/state.py:
   - Fields: meeting_id, bot_id, updated_at, entities_mentioned, body, update_count, is_finalized
   - ❌ WRONG: last_updated, participant_entities, project_entities
   - ✅ CORRECT: updated_at, entities_mentioned['people']

   **CRITICAL**: Copy field names EXACTLY from model file
   **NEVER**: Assume, guess, or use "similar" field names

   Save schema reference to pass to test-writer and solution-coder agents.

5. CREATE COMPREHENSIVE TEST SUITE (Unit + Integration tests required):
   - **Invoke tdd-test-writer agent** WITH schema reference context
   - Create TWO types of tests:

   A. UNIT TESTS (with mocks):
      - Test caller behavior and control flow
      - Mock external dependencies (APIs, DB, filesystem, time)
      - Verify correct parameters passed
      - ❌ DON'T mock: The code you're testing

   B. INTEGRATION TESTS (without mocks):
      - Call real implementation methods
      - Test data transformations and business logic
      - **MINIMUM**: 20% of tests must be integration tests
      - **REQUIRED for**: Serialization, data models, field access
      - Mark with: @pytest.mark.integration

   **INTEGRATION TEST EXAMPLE**:
   ```python
   @pytest.mark.integration
   def test_create_markdown_real_implementation(sample_state):
       # Calls real method - would catch AttributeError if wrong field used!
       storage = StateStorage(state_dir="/tmp/test")
       markdown = storage._create_meeting_markdown(sample_state)
       assert "updated_at:" in markdown  # Would fail if using wrong field name
   ```

   - Write tests for ALL of the following:
     * Every acceptance criterion from the issue
     * All edge cases identified
     * Error handling scenarios
     * Integration points with existing code
   - Use descriptive test names that explain what is being tested
   - Create files: tests/issue_{issue_number}_test_*.py and tests/issue_{issue_number}_integration_test.py
   - Commit tests: git commit -m "test(#{issue_number}): Add failing tests (unit + integration)"

6. VERIFY TEST FAILURES:
   - Run: pytest tests/issue_{issue_number}_* -v
   - Run integration tests: pytest tests/issue_{issue_number}_* -m integration -v
   - Confirm ALL tests fail initially
   - Verify failures are for correct reasons (NotImplementedError, missing functionality)
   - **RED FLAG**: AttributeError = schema mismatch, stop and fix schema discovery
   - Document expected failure messages

7. IMPLEMENT FEATURE INCREMENTALLY (Step-by-step implementation):
   - **Invoke tdd-solution-coder agent** WITH schema reference context
   - Implement smallest testable increment first
   - **RULE**: Copy field names from schema reference only
   - **RULE**: Never guess or assume field names
   - Run tests after EACH change: pytest tests/issue_{issue_number}_* -v
   - Continue implementing until tests pass
   - Commit logical chunks with clear messages:
     * git commit -m "feat(#{issue_number}): Add data models"
     * git commit -m "feat(#{issue_number}): Implement core logic"
     * git commit -m "feat(#{issue_number}): Add API endpoints"
   - NEVER leave TODO comments or stubbed methods
   - Continue until ALL tests pass

7.5. SCHEMA COMPLIANCE CHECK (CRITICAL - Catches field errors):
   **WHY**: Prevents AttributeError in production
   **HOW**:
   - Review implementation files for field access patterns
   - Verify all field names match documented schema from step 4.5
   - Check for common errors: .last_updated, .participant_entities, etc.
   - Use grep to find attribute access: grep -E "\\.[a-z_]+" modified_files
   - **BLOCKER**: Fix all field name mismatches before proceeding

   **EXAMPLE VIOLATIONS**:
   - ❌ state.last_updated → ✅ state.updated_at
   - ❌ state.participant_entities → ✅ state.entities_mentioned['people']

8. VERIFY COMPLETENESS (Implementation validation):
   - **Invoke implementation-completeness-verifier agent**
   - Run full test suite: pytest
   - **REQUIRE**: All integration tests pass (no AttributeError!)
   - **REQUIRE**: Schema compliance = 100%
   - Run integration tests specifically: pytest -m integration -v
   - Verify ALL new tests pass
   - Run type checking: mypy {{module_path}}/ (if applicable)
   - Run linting: flake8 .
   - Run formatting: black . && isort .
   - Search for incomplete implementations: grep -r "TODO\\|NotImplementedError\\|pass  # TODO" . --include="*.py"
   - Verify ZERO stubbed methods remain
   - Verify ALL acceptance criteria from issue are implemented
   - Fix any linting or formatting issues found

9. SUBMIT STACKED PR (PUBLISHED, NOT DRAFT):
   - Review all commits: git log --oneline -10
   - Verify commit messages are clear and descriptive
   - Create PR with Graphite (MUST be published for CodeRabbit review):
     gt submit --no-interactive --publish \\
       --title "Fix #{issue_number}: [Descriptive title from issue]" \\
       --body "## Summary\\n\\n[Detailed description of changes made]\\n\\n## Test Coverage\\n\\n[List all tests added and what they cover]\\n\\n## Stack Position\\n\\n[Describe if this is part of an epic and any dependencies]\\n\\nFixes #{issue_number}"
   - **CRITICAL**: PR must be published (ready for review), NOT draft
   - **WHY**: CodeRabbit cannot review draft PRs. Use --publish flag.
   - Capture PR number from output

10. VERIFY PR BASE BRANCH AND GRAPHITE REGISTRATION:
   - Get PR number from previous step
   - Run: gh pr view <PR_NUMBER> --json baseRefName,headRefName
   - Verify baseRefName matches expected parent branch from stack
   - If PR base is 'main' but should be another issue branch:
     * Run: gh pr edit <PR_NUMBER> --base <correct-parent-branch>
     * Run: gt get (sync Graphite's local metadata with GitHub)
     * Confirm: "Fixed PR base branch to maintain stack integrity"
   - This ensures Graphite stack structure is preserved on GitHub

   - VERIFY GRAPHITE BACKEND REGISTRATION:
     * Run: gt log --stack
     * Confirm the PR appears in the stack with correct parent/child relationships
     * The PR URL should be shown (https://app.graphite.dev/...)
     * If PR doesn't appear in stack or shows as isolated:
       > Problem: PR was created but not registered with Graphite's backend
       > Solution: Run `gt submit --no-edit --no-interactive` to re-submit and register
       > This updates Graphite's backend without changing the PR
     * Verify again with: gt log --stack
     * **CRITICAL**: Graphite web UI will ONLY show stack if PR is registered via gt submit

11. FINAL VERIFICATION:
   - Run: gt ls (verify stack structure)
   - Run: gt status (confirm PR URL)
   - Confirm ALL tests passing: pytest
   - Confirm PR created and linked to issue

11.5. CLEANUP AND COMMIT ALL FILES:
   - Run: git status --short
   - Review ALL uncommitted files:

   **DELETE temporary helper scripts**:
   - Patterns: verify_*.py, test_*.tmp, debug_*.py, temp_*.py
   - Run: rm <filename>

   **COMMIT test documentation** (REQUIRED if created):
   - Files like: RUN_TESTS_*.md, TEST_SUMMARY_*.md, *_tdd_plan.md
   - These are LEGITIMATE documentation that MUST be committed
   - Run: git add tests/*.md && git commit -m "docs(#{issue_number}): Add test documentation"

   **COMMIT any other implementation files**:
   - New source files, config files, or documentation
   - Run: git add <files> && git commit -m "appropriate message"

   - **CRITICAL**: Final check: git status --short should show NOTHING
   - This ensures the worktree is clean and the workflow validation will pass

COMPLETION CRITERIA (ALL must be true):
- ✓ Schema discovery completed with all field names documented
- ✓ Tests created (both unit AND integration tests, minimum 20% integration)
- ✓ Tests initially failed with expected errors (NOT AttributeError from wrong fields)
- ✓ ALL tests now passing (including integration tests)
- ✓ Schema compliance check passed with 100% match
- ✓ Code linted and formatted (flake8, black, isort)
- ✓ PR submitted via Graphite with proper title and body
- ✓ PR base branch verified to match stack structure (not wrongly pointing to main)
- ✓ NO TODOs, NotImplementedError, or stub methods remaining
- ✓ Multiple logical commits with clear, descriptive messages
- ✓ All acceptance criteria from issue implemented
- ✓ No uncommitted implementation files (temporary helper scripts cleaned up or ignored)

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

OPTION: For straightforward CodeRabbit fixes, consider invoking **pr-coderabbit-fixer agent**
to automatically parse and implement review suggestions.

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
   - Run integration tests: pytest -m integration -v
   - Verify ALL tests still pass (including integration tests)
   - **If changes touch data models**: Re-run schema compliance check
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
- ✓ All tests passing (including integration tests)
- ✓ Schema compliance maintained (if model changes made)
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


SCHEMA_DISCOVERY_PROMPT = """
Document all data model schemas for issue #{issue_number} implementation.

CRITICAL: Field names are NOT guessable - must read actual model definitions.

WHY THIS MATTERS:
- Field name assumptions cause AttributeError in production
- Common errors: using .last_updated instead of .updated_at, .participant_entities instead of .entities_mentioned['people']
- Integration tests catch these but only if we know the correct names upfront

DISCOVERY PROCESS:

1. IDENTIFY MODELS TO BE USED/MODIFIED:
   - Scan issue description for model mentions
   - Check existing code that will be modified
   - Use grep to find model imports: grep -r "from.*models" --include="*.py"
   - List all models that will be touched by this implementation

2. READ EACH MODEL FILE:
   - For each model identified, read the complete model definition file
   - Common locations: app/models/, models/, {app_name}/models/
   - Read entire file to see all fields, not just a few

3. DOCUMENT ALL FIELD NAMES EXACTLY:
   - Create a schema reference list with:
     * Model name (e.g., MeetingState)
     * File path (e.g., app/models/meeting/state.py)
     * ALL field names exactly as defined
     * Field types (str, int, dict, list, etc.)
     * Any nested structures (e.g., entities_mentioned is a dict with 'people', 'projects' keys)
   - Copy field names character-for-character, do NOT paraphrase

4. DOCUMENT COMMON ERRORS TO AVOID:
   - For each model, list field names that might be assumed incorrectly
   - Example: If model has "updated_at", note "NOT last_updated, NOT modified_at"

SCHEMA REFERENCE OUTPUT FORMAT:

```
Model: MeetingState
File: app/models/meeting/state.py
Fields:
  - meeting_id: str
  - bot_id: str
  - updated_at: datetime (NOT last_updated, NOT modified_at)
  - entities_mentioned: Dict[str, List[str]] (keys: 'people', 'projects')
  - body: str
  - update_count: int
  - is_finalized: bool (NOT finalized, NOT is_final)

Common Errors to Avoid:
  ❌ state.last_updated → ✅ state.updated_at
  ❌ state.participant_entities → ✅ state.entities_mentioned['people']
  ❌ state.finalized → ✅ state.is_finalized
```

NEXT STEPS AFTER DISCOVERY:
- Pass this schema reference to tdd-test-writer agent
- Pass this schema reference to tdd-solution-coder agent
- Use for schema compliance check after implementation
- Reference during code review

CRITICAL RULES:
- NEVER guess or assume field names
- ALWAYS read the actual model definition file
- Document EVERY field that will be used
- Include nested structure details
- Copy names exactly, character-for-character

Begin schema discovery now for issue #{issue_number}.
"""


SCHEMA_COMPLIANCE_CHECK_PROMPT = """
Verify all field access in implementation matches documented schema reference.

CURRENT CONTEXT:
- Issue: #{issue_number}
- Schema Reference: {schema_reference}

WHY THIS MATTERS:
This check prevents AttributeError bugs in production by catching field name mismatches
before code is committed. Even a single typo (e.g., .last_updated vs .updated_at) causes
runtime failures.

VALIDATION STEPS:

1. LOAD SCHEMA REFERENCE:
   - Review the schema reference created during discovery phase
   - Note all documented field names for each model
   - Pay attention to "Common Errors to Avoid" section

2. IDENTIFY MODIFIED FILES:
   - Find all Python files changed for this issue
   - Use: git diff --name-only --cached --diff-filter=AM "*.py"
   - Focus on files that access data models

3. EXTRACT FIELD ACCESS PATTERNS:
   - For each modified file, find all attribute access:
     * Use: grep -E "\\.[a-z_]+" filename.py
     * Look for patterns like: object.field_name
     * Include nested access: object.field['key']
   - Create list of all field names referenced in code

4. COMPARE AGAINST SCHEMA:
   - For each field access found:
     * Check if field name exists in schema reference
     * Verify exact spelling (case-sensitive)
     * Confirm nested structure access is correct
   - Flag ANY field name not in schema reference as a violation

5. REPORT VIOLATIONS:
   - List all field name mismatches found
   - For each violation, show:
     * File and line number
     * Incorrect field name used
     * Correct field name from schema
     * Suggested fix
   - Example format:
     ```
     VIOLATION in app/services/meeting.py:45
     ❌ state.last_updated
     ✅ state.updated_at
     Fix: Change line 45 from "state.last_updated" to "state.updated_at"
     ```

COMMON VIOLATION PATTERNS TO CHECK:

1. Timestamp fields:
   - ❌ .last_updated, .modified_at, .changed_at
   - ✅ .updated_at (or whatever schema defines)

2. Boolean fields:
   - ❌ .finalized, .completed, .active
   - ✅ .is_finalized, .is_completed, .is_active (or whatever schema defines)

3. Collection fields:
   - ❌ .participant_entities, .project_entities
   - ✅ .entities_mentioned['people'], .entities_mentioned['projects']

4. Plural vs singular:
   - ❌ .comment, .entity
   - ✅ .comments, .entities (check schema for correct form)

ENFORCEMENT:

If violations found:
- Report as BLOCKER
- Do NOT proceed to PR creation
- Fix all violations first
- Re-run compliance check after fixes

If no violations found:
- Report: "✅ Schema compliance: 100% - All field names match schema reference"
- Proceed to next workflow step

CRITICAL: This check must pass with ZERO violations before PR creation.

Begin schema compliance check now.
"""


INTEGRATION_TEST_PROMPT = """
Create integration tests for issue #{issue_number} (minimum 20% of test suite).

CURRENT CONTEXT:
- Issue: #{issue_number}
- Schema Reference: {schema_reference}

WHY INTEGRATION TESTS MATTER:
- Unit tests with mocks hide implementation bugs (especially field name errors)
- Integration tests call real code and catch AttributeError, serialization issues, logic errors
- Requirement: At least 20% of tests must be integration tests

DIFFERENCE BETWEEN UNIT AND INTEGRATION TESTS:

UNIT TESTS (with mocks):
```python
def test_save_state_calls_storage(mocker):
    mock_storage = mocker.patch('app.storage.StateStorage')
    service = MeetingService()
    service.save_state(state)

    # Verifies the call was made, but doesn't test actual serialization
    mock_storage.save.assert_called_once()
```

INTEGRATION TESTS (without mocks):
```python
@pytest.mark.integration
def test_save_and_load_state_real_implementation(tmp_path):
    storage = StateStorage(state_dir=str(tmp_path))
    state = MeetingState(meeting_id="123", bot_id="bot1", updated_at=datetime.now())

    # Real method calls - would fail if field names wrong!
    storage.save(state)
    loaded = storage.load("123")

    assert loaded.meeting_id == "123"
    assert loaded.updated_at is not None
    # Would raise AttributeError if we used wrong field name!
```

INTEGRATION TEST REQUIREMENTS:

1. NO MOCKS FOR CODE UNDER TEST:
   - Mock ONLY external dependencies (APIs, filesystem, databases, time)
   - Call real implementation methods
   - Test actual data transformations

2. MINIMUM COVERAGE:
   - At least 20% of total tests must be integration tests
   - If creating 10 unit tests, create at least 3 integration tests

3. MARK WITH PYTEST DECORATOR:
   - Add @pytest.mark.integration to each integration test
   - This allows running: pytest -m integration

4. TEST SCENARIOS FOR INTEGRATION TESTS:
   - Data serialization/deserialization
   - Field access and attribute errors
   - Data transformation pipelines
   - Business logic with real data
   - Cross-module interactions

5. USE SCHEMA REFERENCE:
   - Reference documented field names from schema
   - Verify those exact field names work in real code
   - Test nested structure access

INTEGRATION TEST EXAMPLES:

Example 1 - Data Serialization:
```python
@pytest.mark.integration
def test_meeting_state_serialization(tmp_path):
    \"\"\"Integration: Verify MeetingState serializes with correct field names\"\"\"
    state = MeetingState(
        meeting_id="m1",
        bot_id="b1",
        updated_at=datetime.now(),
        entities_mentioned={{'people': ['Alice'], 'projects': ['P1']}},
        is_finalized=False
    )

    # Real serialization - catches field name errors
    json_data = state.to_dict()

    assert 'updated_at' in json_data  # NOT last_updated!
    assert json_data['entities_mentioned']['people'] == ['Alice']
    assert json_data['is_finalized'] is False  # NOT finalized!
```

Example 2 - Business Logic:
```python
@pytest.mark.integration
def test_update_meeting_state_real_logic():
    \"\"\"Integration: Test state update with real business logic\"\"\"
    state = MeetingState(meeting_id="m1", update_count=0)
    service = MeetingService()

    # Real method call - tests actual logic
    updated = service.update_state(state, body="New content")

    assert updated.update_count == 1
    assert updated.body == "New content"
    assert updated.updated_at > state.updated_at
```

TEST FILE STRUCTURE:

Create tests/issue_{issue_number}_integration_test.py:
```python
\"\"\"Integration tests for issue #{issue_number}\"\"\"
import pytest
from datetime import datetime

@pytest.mark.integration
def test_scenario_1():
    # Integration test 1
    pass

@pytest.mark.integration
def test_scenario_2():
    # Integration test 2
    pass
```

VERIFICATION:

After creating tests, verify:
1. Count total tests: pytest tests/issue_{issue_number}_* --collect-only | grep "test session starts"
2. Count integration tests: pytest tests/issue_{issue_number}_* -m integration --collect-only
3. Calculate percentage: (integration / total) * 100
4. Ensure >= 20%

Create integration tests now for issue #{issue_number} using the schema reference provided.
"""


# System prompts for Claude Code SDK sessions

TDD_SYSTEM_PROMPT = """You are a TDD-focused software engineer using Graphite stacked PRs. Follow test-driven development principles strictly: write tests first, verify they fail, implement incrementally, commit frequently with clear messages. Never use TODO comments or placeholder implementations."""

REVIEW_FIX_SYSTEM_PROMPT = """You are a code reviewer addressing PR feedback systematically. Fetch CodeRabbit comments via gh CLI, analyze each suggestion by priority, implement fixes with clear commits, and verify all changes with tests."""
