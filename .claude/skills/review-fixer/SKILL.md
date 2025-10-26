---
name: review-fixer
description: Address CodeRabbit review comments on pull requests systematically. Fetch review feedback, prioritize by severity, implement fixes with tests, and update PR. Use when asked to fix review comments, address CodeRabbit feedback, handle PR reviews, or fix code review issues. Triggers include "fix review", "address review comments", "CodeRabbit feedback", "handle PR feedback".
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Task]
---

# CodeRabbit Review Fixer

Address all CodeRabbit review comments for a pull request systematically.

## Context

When this skill is invoked:
- **Worktree**: Already set up at correct path with PR branch checked out
- **PR number**: Provided in the request
- **Skills**: Epic-manager skills available for reference

## Option: Automated Fixing

For straightforward CodeRabbit fixes, consider invoking the **pr-coderabbit-fixer agent** to automatically parse and implement review suggestions.

This skill provides the manual workflow for complex reviews requiring judgment.

## Workflow

### Step 1: Fetch Review Comments

Get all CodeRabbit comments from the PR:

```bash
gh pr view {pr_number} --json reviews,comments
```

**Parse**:
- ALL review comments from CodeRabbit
- Extract review suggestions from GitHub reviews
- Include inline code comments
- Get comment thread context

**Group comments by**:
- File affected
- Severity (Critical > Major > Minor > Nit)
- Type (bug, style, performance, security, etc.)

### Step 2: Analyze Each Comment

Separate actionable from informational comments.

**Prioritize fixes by severity**:

1. **Critical**: Security issues, bugs causing failures
   - Memory leaks, SQL injection, authentication bypass
   - Crashes, data corruption
   - Must fix immediately

2. **Major**: Performance issues, incorrect behavior
   - N+1 queries, inefficient algorithms
   - Logic errors, edge case bugs
   - Should fix before merge

3. **Minor**: Code quality, maintainability
   - Missing error handling, unclear variable names
   - Code duplication, missing tests
   - Good to fix

4. **Nit**: Style preferences, minor improvements
   - Formatting, comment style
   - Variable naming preferences
   - Optional

**Create detailed fix plan** for each actionable comment.

### Step 3: Implement Fixes Systematically

For EACH CodeRabbit suggestion (in priority order):

1. **Read the affected file(s)**
   ```bash
   cat {filename}
   # or use Read tool
   ```

2. **Understand the current implementation**
   - Why does the code work this way?
   - What is CodeRabbit suggesting?
   - Is the suggestion correct and safe?

3. **Implement the suggested change**
   - Make the exact change suggested (if correct)
   - Or implement a better alternative (explain why)
   - Add tests if changing logic

4. **Verify change addresses the review comment completely**
   - Re-read the comment
   - Confirm your change resolves it
   - Check for edge cases

5. **Run tests to ensure no regression**
   ```bash
   pytest
   ```

6. **Commit with clear message**
   ```bash
   git commit -m "fix(PR#{pr_number}): [Brief description of fix]

   Addresses CodeRabbit comment: [quote relevant part of comment]"
   ```

**Example commit messages**:
```
fix(PR#587): Add null check for missing meeting IDs

Addresses CodeRabbit comment: "Potential NullPointerException if
meeting_id is None. Add validation."
```

```
refactor(PR#587): Extract duplicate validation logic

Addresses CodeRabbit comment: "This validation is duplicated in 3
places. Consider extracting to a helper method."
```

### Step 4: Verify All Fixes

Run comprehensive validation:

```bash
# Run full test suite
pytest

# Run integration tests specifically
pytest -m integration -v

# Verify ALL tests still pass (including integration tests)
```

**If changes touch data models**:
- Re-run schema compliance check (if applicable)
- Verify field names still match schema

**Run code quality checks**:
```bash
# Linting
flake8 .

# Formatting
black .
isort .
```

Fix any new linting or formatting issues.

### Step 5: Update PR

**Review all fix commits**:
```bash
git log --oneline -5
```

**Push changes**:
```bash
git push
```

**Add summary comment** to PR:
```bash
gh pr comment {pr_number} --body "## CodeRabbit Review Addressed

Fixed the following issues:

- ✓ **Critical**: [Description] (commit abc123)
- ✓ **Major**: [Description] (commit def456)
- ✓ **Minor**: [Description] (commit ghi789)

All tests passing. Ready for re-review."
```

## Completion Criteria

- ✓ ALL CodeRabbit comments addressed
- ✓ Each fix committed separately with clear message
- ✓ All tests passing (including integration tests)
- ✓ Schema compliance maintained (if model changes made)
- ✓ Code linted and formatted
- ✓ PR updated with summary comment
- ✓ No uncommitted changes

## Common Review Comment Types

### Type 1: Null/Undefined Checks

**Comment**: "Add null check for user_id"

**Fix**:
```python
# Before
def get_user(user_id):
    return db.query(User).filter_by(id=user_id).first()

# After
def get_user(user_id):
    if not user_id:
        raise ValueError("user_id is required")
    return db.query(User).filter_by(id=user_id).first()
```

### Type 2: Performance Issues

**Comment**: "N+1 query - use join instead"

**Fix**:
```python
# Before
for meeting in meetings:
    participants = meeting.participants  # N queries!

# After
meetings = Meeting.query.options(
    joinedload(Meeting.participants)
).all()  # 1 query!
```

### Type 3: Error Handling

**Comment**: "Add try/except for API call"

**Fix**:
```python
# Before
response = requests.get(url)
return response.json()

# After
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
except requests.RequestException as e:
    logger.error(f"API request failed: {e}")
    raise
```

### Type 4: Code Duplication

**Comment**: "Extract this duplicated logic"

**Fix**:
```python
# Before (duplicated in 3 places)
if not state.meeting_id:
    raise ValueError("meeting_id required")
if not state.bot_id:
    raise ValueError("bot_id required")

# After (extracted helper)
def validate_state(state):
    """Validate state has required fields."""
    if not state.meeting_id:
        raise ValueError("meeting_id required")
    if not state.bot_id:
        raise ValueError("bot_id required")

# Use in all 3 places
validate_state(state)
```

### Type 5: Missing Tests

**Comment**: "Add test for edge case: empty list"

**Fix**:
```python
# Add new test
def test_process_empty_list():
    """Test handling of empty input list."""
    result = process_items([])
    assert result == []
```

### Type 6: Type Hints

**Comment**: "Add type hints for better clarity"

**Fix**:
```python
# Before
def calculate_total(items):
    return sum(item.price for item in items)

# After
from typing import List

def calculate_total(items: List[Item]) -> float:
    return sum(item.price for item in items)
```

## Tips for Effective Fixes

### 1. Understand Before Changing

- Don't blindly apply suggestions
- Understand why the current code works
- Ensure suggestion doesn't break functionality
- Add tests if logic changes

### 2. One Fix Per Commit

- Makes review easier
- Can revert specific changes if needed
- Clear commit history

### 3. Quote CodeRabbit in Commits

- Links fix to original comment
- Provides context for future readers
- Helps track which comments were addressed

### 4. Test Everything

- Run full test suite after each fix
- Especially important for logic changes
- Integration tests catch unexpected breakage

### 5. Communicate

- Add PR comment summarizing fixes
- Explain non-obvious decisions
- Ask for clarification if comment is unclear

## When to Disagree with CodeRabbit

CodeRabbit is helpful but not always right. Disagree when:

1. **Suggestion breaks functionality**
   - Add comment explaining why suggestion won't work
   - Propose alternative if possible

2. **Suggestion conflicts with project style**
   - Defer to project conventions
   - Note this in PR comment

3. **Suggestion is out of scope**
   - "This would be good but belongs in separate PR"
   - Create new issue for future work

4. **Suggestion is incorrect**
   - Politely explain why
   - Provide correct approach if needed

**Example response**:
```
Thanks for the suggestion! However, adding the null check here
would break the factory pattern we're using - the validation
happens in the builder instead. I've added a comment to clarify
this behavior.
```

## Handling Complex Reviews

For PRs with 10+ comments:

1. **Triage first**: Group by severity and file
2. **Fix critical issues immediately**: Block merging
3. **Batch related fixes**: All fixes in one file together
4. **Test incrementally**: After each batch
5. **Update PR frequently**: Don't wait until all fixes done

## Schema Compliance for Model Changes

If CodeRabbit suggests changing data model fields:

1. **Verify against schema reference** (from TDD workflow)
2. **Update schema documentation** if fields change
3. **Re-run schema compliance check**
4. **Update tests** to match new fields

**Example**:
CodeRabbit: "Rename `last_modified` to `updated_at` for consistency"

1. Check schema - confirm this matches project convention
2. Update all references to `last_modified`
3. Run schema compliance check
4. Update tests
5. Commit as schema alignment fix

Execute systematically. Address every comment. Verify each fix independently.
