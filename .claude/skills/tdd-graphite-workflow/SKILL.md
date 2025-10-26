---
name: tdd-graphite-workflow
description: Execute complete TDD (Test-Driven Development) workflow for GitHub issues using Graphite stacked PRs. Includes schema discovery to prevent field name bugs, integration test requirements (minimum 20%), incremental implementation, and PR submission with base branch verification. Use this skill when asked to implement an issue, run TDD workflow, develop a feature, or start development work on a GitHub issue. Triggers include "TDD workflow", "implement issue", "run TDD", "develop feature", "implement feature", "start development".
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, WebFetch, Task, TodoWrite]
---

# TDD Workflow with Graphite Stacked PRs

Execute this comprehensive 11-step Test-Driven Development workflow when implementing a GitHub issue using Graphite stacked branches.

## Current Context

When this skill is invoked, the following setup has already been completed by epic-manager:
- **Worktree**: Created at correct path with proper git branch
- **Issue**: Number provided in the request
- **Base branch**: Branch already created from correct parent (for stack dependencies)
- **Skills**: Epic-manager and instance skills provisioned in `.claude/skills/`

Your job is to execute the TDD workflow from analysis through PR submission.

## IMPORTANT: Sequential Execution for Proper PR Stacking

This workflow is part of a dependency chain where PRs must be created sequentially to ensure correct Graphite stacking. The parent issue's PR must exist on GitHub BEFORE this issue creates its PR. Epic Manager handles the sequencing - your job is to complete the TDD workflow and create the PR via `gt submit`. Epic Manager will verify the PR exists before starting dependent issues.

**Why this matters**: Graphite determines PR base branches from git ancestry. If a parent PR doesn't exist when `gt submit` runs, Graphite falls back to targeting main, breaking the stack. Sequential execution prevents this.

## Workflow Steps

### Step 1: Sync Graphite Stack

Ensure Graphite metadata is synchronized with GitHub's actual PR state.

```bash
gt sync      # Fetch latest PR metadata from GitHub
gt restack   # Rebuild stack based on current git state
gt ls        # Verify correct stack structure
```

**Verification**:
- `gt ls` shows this branch in correct position
- No warnings about unknown parents
- Stack structure matches expected dependencies

**Reference**: See [graphite-commands.md](./graphite-commands.md) for detailed Graphite command reference.

### Step 2: Stack Context Check

Verify the branch position and stack relationships.

```bash
gt ls        # Show stack structure
gt status    # Show current branch status
```

**Confirm**:
- Current branch position in stack
- Stack is up-to-date with trunk
- Base branch is correct

### Step 3: Register Existing Branch in Graphite

The branch `issue-{number}` already exists (created by worktree manager with correct base branch). Register it in Graphite's tracking system.

```bash
git branch --show-current  # Should show issue-{number}
gt track issue-{number}    # Register branch in Graphite
```

**Verify**:
```bash
gt status   # Branch should now appear in Graphite
git status  # Worktree should be clean
```

**DO NOT** run `gt create` - the branch already exists with the correct base.

### Step 4: Analyze Issue (Requirements Extraction)

Extract comprehensive requirements and create test plan.

**Recommended**: Invoke the `issue-analyzer` agent for thorough requirements extraction.

```bash
gh issue view {issue_number} --json title,body,comments
```

**Extract**:
- All requirements from issue description
- Acceptance criteria from issue body
- Edge cases and error scenarios to test
- Test scenarios needed for complete coverage

**Document**:
- Create test plan covering all scenarios
- List all acceptance criteria
- Identify integration points with existing code

### Step 4.5: Schema Discovery (CRITICAL - Prevents Field Name Bugs)

**WHY**: Field names are NOT guessable - must read actual model definitions to prevent `AttributeError` bugs in production.

**Reference**: See [schema-discovery.md](./schema-discovery.md) for complete methodology.

**Process**:
1. Identify all models that will be modified or used
2. Read each model definition file (app/models/...)
3. Document ALL field names EXACTLY as defined in the model
4. Create schema reference list for implementation

**EXAMPLE**: For `MeetingState` in `app/models/meeting/state.py`:
- Fields: `meeting_id`, `bot_id`, `updated_at`, `entities_mentioned`, `body`, `update_count`, `is_finalized`
- ❌ WRONG: `last_updated`, `participant_entities`, `project_entities`
- ✅ CORRECT: `updated_at`, `entities_mentioned['people']`

**CRITICAL**: Copy field names EXACTLY from model file. NEVER assume, guess, or use "similar" field names.

**Save** schema reference to pass to test-writer and solution-coder agents.

### Step 5: Create Comprehensive Test Suite (Unit + Integration Required)

**Recommended**: Invoke the `tdd-test-writer` agent WITH schema reference context.

**Reference**: See [integration-tests.md](./integration-tests.md) for 20% requirement details.

Create TWO types of tests:

#### A. Unit Tests (with mocks)
- Test caller behavior and control flow
- Mock external dependencies (APIs, DB, filesystem, time)
- Verify correct parameters passed
- ❌ DON'T mock: The code you're testing

#### B. Integration Tests (without mocks)
- Call real implementation methods
- Test data transformations and business logic
- **MINIMUM**: 20% of tests must be integration tests
- **REQUIRED for**: Serialization, data models, field access
- Mark with: `@pytest.mark.integration`

**Write tests for ALL of the following**:
- Every acceptance criterion from the issue
- All edge cases identified
- Error handling scenarios
- Integration points with existing code

**File naming**:
- `tests/issue_{issue_number}_test_*.py` (unit tests)
- `tests/issue_{issue_number}_integration_test.py` (integration tests)

**Commit tests**:
```bash
git add tests/issue_{issue_number}_*
git commit -m "test(#{issue_number}): Add failing tests (unit + integration)"
```

### Step 6: Verify Test Failures

Run tests and confirm they fail for the RIGHT reasons.

```bash
pytest tests/issue_{issue_number}_* -v
pytest tests/issue_{issue_number}_* -m integration -v
```

**Expected**:
- ALL tests fail initially
- Failures are `NotImplementedError` or missing functionality
- **RED FLAG**: `AttributeError` = schema mismatch, stop and fix schema discovery

**Document** expected failure messages.

### Step 7: Implement Feature Incrementally

**Recommended**: Invoke the `tdd-solution-coder` agent WITH schema reference context.

**Implementation Rules**:
- Implement smallest testable increment first
- **RULE**: Copy field names from schema reference ONLY
- **RULE**: Never guess or assume field names
- Run tests after EACH change: `pytest tests/issue_{issue_number}_* -v`
- Continue implementing until tests pass
- **NEVER** leave TODO comments or stubbed methods
- Continue until ALL tests pass

**Commit logical chunks** with clear messages:
```bash
git commit -m "feat(#{issue_number}): Add data models"
git commit -m "feat(#{issue_number}): Implement core logic"
git commit -m "feat(#{issue_number}): Add API endpoints"
```

### Step 7.5: Schema Compliance Check (CRITICAL - Catches Field Errors)

**WHY**: Prevents `AttributeError` in production by verifying all field names match schema.

**Reference**: See [schema-compliance.md](./schema-compliance.md) for complete methodology.

**Process**:
1. Review implementation files for field access patterns
2. Verify all field names match documented schema from step 4.5
3. Check for common errors: `.last_updated`, `.participant_entities`, etc.
4. Use grep to find attribute access: `grep -E "\.[a-z_]+" modified_files`
5. **BLOCKER**: Fix all field name mismatches before proceeding

**Example violations**:
- ❌ `state.last_updated` → ✅ `state.updated_at`
- ❌ `state.participant_entities` → ✅ `state.entities_mentioned['people']`

### Step 8: Verify Completeness (Implementation Validation)

**Recommended**: Invoke the `implementation-completeness-verifier` agent.

**Checks**:
1. Run full test suite: `pytest`
2. **REQUIRE**: All integration tests pass (no AttributeError!)
3. **REQUIRE**: Schema compliance = 100%
4. Run integration tests specifically: `pytest -m integration -v`
5. Verify ALL new tests pass
6. Run type checking: `mypy {module_path}/` (if applicable)
7. Run linting: `flake8 .`
8. Run formatting: `black . && isort .`
9. Search for incomplete implementations:
   ```bash
   grep -r "TODO\|NotImplementedError\|pass  # TODO" . --include="*.py"
   ```
10. Verify ZERO stubbed methods remain
11. Verify ALL acceptance criteria from issue are implemented
12. Fix any linting or formatting issues found

### Step 9: Submit Stacked PR (PUBLISHED, NOT DRAFT)

Review commits and create PR via Graphite.

**Review commits**:
```bash
git log --oneline -10
```

**Create PR** (MUST be published for CodeRabbit review):
```bash
gt submit --no-interactive --publish \
  --title "Fix #{issue_number}: [Descriptive title from issue]" \
  --body "## Summary

[Detailed description of changes made]

## Test Coverage

[List all tests added and what they cover]

## Stack Position

[Describe if this is part of an epic and any dependencies]

Fixes #{issue_number}"
```

**CRITICAL**:
- PR must be **published** (ready for review), NOT draft
- **WHY**: CodeRabbit cannot review draft PRs. Use `--publish` flag.
- Capture PR number from output

### Step 10: Verify PR Base Branch and Graphite Registration

**Get PR number** from previous step, then verify:

```bash
gh pr view <PR_NUMBER> --json baseRefName,headRefName
```

**Verify** baseRefName matches expected parent branch from stack.

**If PR base is 'main' but should be another issue branch**:
```bash
gh pr edit <PR_NUMBER> --base <correct-parent-branch>
gt get  # Sync Graphite's local metadata with GitHub
```

Confirm: "Fixed PR base branch to maintain stack integrity"

**Verify Graphite Backend Registration**:

```bash
gt log --stack
```

**Confirm**:
- PR appears in the stack with correct parent/child relationships
- PR URL is shown (https://app.graphite.dev/...)

**If PR doesn't appear in stack or shows as isolated**:
- **Problem**: PR was created but not registered with Graphite's backend
- **Solution**: Run `gt submit --no-edit --no-interactive` to re-submit and register
- This updates Graphite's backend without changing the PR
- **CRITICAL**: Graphite web UI will ONLY show stack if PR is registered via gt submit

**Verify again**: `gt log --stack`

### Step 11: Final Verification

Run final checks to ensure workflow completion.

```bash
gt ls        # Verify stack structure
gt status    # Confirm PR URL
pytest       # Confirm ALL tests passing
git status --short  # Should be empty (no uncommitted files)
```

**Confirm**:
- ✓ ALL tests passing
- ✓ PR created and linked to issue
- ✓ PR registered in Graphite backend
- ✓ Base branch is correct
- ✓ No uncommitted changes

### Step 11.5: Cleanup and Commit All Files

**Review uncommitted files**:
```bash
git status --short
```

**DELETE temporary helper scripts**:
- Patterns: `verify_*.py`, `test_*.tmp`, `debug_*.py`, `temp_*.py`
```bash
rm <filename>
```

**COMMIT test documentation** (REQUIRED if created):
- Files like: `RUN_TESTS_*.md`, `TEST_SUMMARY_*.md`, `*_tdd_plan.md`
- These are LEGITIMATE documentation that MUST be committed
```bash
git add tests/*.md
git commit -m "docs(#{issue_number}): Add test documentation"
```

**COMMIT any other implementation files**:
- New source files, config files, or documentation
```bash
git add <files>
git commit -m "appropriate message"
```

**CRITICAL**: Final check: `git status --short` should show NOTHING. This ensures the worktree is clean and the workflow validation will pass.

## Completion Criteria (ALL must be true)

- ✓ Schema discovery completed with all field names documented
- ✓ Tests created (both unit AND integration tests, minimum 20% integration)
- ✓ Tests initially failed with expected errors (NOT AttributeError from wrong fields)
- ✓ ALL tests now passing (including integration tests)
- ✓ Schema compliance check passed with 100% match
- ✓ Code linted and formatted (flake8, black, isort)
- ✓ PR submitted via Graphite with proper title and body
- ✓ PR base branch verified to match stack structure (not wrongly pointing to main)
- ✓ PR registered in Graphite backend (visible in web UI)
- ✓ NO TODOs, NotImplementedError, or stub methods remaining
- ✓ Multiple logical commits with clear, descriptive messages
- ✓ All acceptance criteria from issue implemented
- ✓ No uncommitted implementation files (temporary helper scripts cleaned up or ignored)

## Critical Instructions

- Execute EACH step completely before moving to next
- Do NOT skip any validation steps
- Run tests frequently (after each implementation change)
- Verify success at each stage before proceeding
- If any step fails, stop and report the failure clearly
- Never use placeholder implementations or TODOs
- Commit frequently with descriptive messages

## Supporting References

- [schema-discovery.md](./schema-discovery.md) - Complete schema discovery methodology
- [integration-tests.md](./integration-tests.md) - Integration test requirements
- [schema-compliance.md](./schema-compliance.md) - Field validation process
- [graphite-commands.md](./graphite-commands.md) - Graphite CLI reference

Begin execution now. Work methodically through each step.
