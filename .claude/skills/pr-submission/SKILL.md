---
name: pr-submission
description: Create pull requests via Graphite with proper stacking, base branch verification, and backend registration. Use when asked to submit PR, create pull request, publish PR, or submit to GitHub. Triggers include "submit PR", "create PR", "publish PR", "submit pull request".
allowed-tools: [Bash, Read]
---

# PR Submission with Graphite

Create pull requests via Graphite (`gt submit`) with proper stacking and verification.

## Why Use This Skill

- Ensures PRs are registered with Graphite's backend (required for web UI)
- Verifies base branches are correct (prevents broken stacks)
- Publishes PRs for CodeRabbit review (drafts can't be reviewed)
- Handles stack metadata correctly

## Prerequisites

Before using this skill:
- ✓ All tests passing
- ✓ Code linted and formatted
- ✓ Implementation complete (no TODOs)
- ✓ Branch tracked in Graphite (`gt track`)
- ✓ Commits reviewed and polished

## Submission Workflow

### Step 1: Review Commits

Ensure commit history is clean and descriptive:

```bash
git log --oneline -10
```

**Check for**:
- Clear, descriptive commit messages
- Logical grouping of changes
- No "WIP" or "temp" commits (squash if needed)
- Commits tell a story of how the feature was built

### Step 2: Create PR via Graphite

**CRITICAL**: Use `gt submit`, NOT `gh pr create`. Only `gt submit` registers the PR with Graphite's backend.

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

**Flags explained**:
- `--no-interactive`: Don't prompt for input (automation-friendly)
- `--publish`: Create as ready-for-review, NOT draft (required for CodeRabbit)
- `--title`: PR title (should reference issue number)
- `--body`: PR description (Markdown supported)

**Capture PR number** from output:
```
Created PR #587: https://github.com/owner/repo/pull/587
```

### Step 3: Verify Base Branch

Ensure PR base branch matches expected parent in stack:

```bash
gh pr view <PR_NUMBER> --json baseRefName,headRefName
```

**Expected**:
- If this is first issue: `baseRefName` should be `main`
- If dependent issue: `baseRefName` should be parent `issue-{N}`

**If base is wrong**:
```bash
# Fix base branch
gh pr edit <PR_NUMBER> --base <correct-parent-branch>

# Sync Graphite
gt get
```

See [stack-verification.md](./stack-verification.md) for details.

### Step 4: Verify Graphite Backend Registration

**CRITICAL**: Confirm PR appears in Graphite's backend (not just GitHub).

```bash
gt log --stack
```

**Expected output**:
```
◯ issue-582 (HEAD)
│ Fix authentication bug
│ PR: #587 (https://github.com/...)
│
◯ issue-581
│ Update user model
│ PR: #586 (https://github.com/...)
```

**PR should show**:
- ✓ PR number appears
- ✓ PR URL shown
- ✓ Correct parent/child relationships

**If PR doesn't appear or shows as isolated**:

**Problem**: PR created with `gh` instead of `gt`, not registered in backend.

**Solution**: Re-submit to register with Graphite:
```bash
gt submit --no-edit --no-interactive
```

This updates Graphite's backend **without changing the PR**.

**Verify again**:
```bash
gt log --stack
```

PR should now appear in the stack.

### Step 5: Final Verification

Run final checks:

```bash
# Verify stack structure
gt ls

# Confirm PR URL
gt status

# Ensure clean worktree
git status --short  # Should be empty
```

**Confirm**:
- ✓ PR created and linked to issue
- ✓ PR base branch is correct
- ✓ PR registered in Graphite backend (visible in `gt log --stack`)
- ✓ No uncommitted changes

## PR Title Format

**Good PR titles**:
- `Fix #581: Add user authentication endpoints`
- `Feat #582: Implement meeting state storage`
- `Test #583: Add integration tests for API`

**Bad PR titles**:
- `Update code` (not descriptive)
- `Fix bug` (which bug?)
- `Issue 581` (missing description)

## PR Body Template

```markdown
## Summary

[2-3 sentence description of what changed and why]

## Changes Made

- Added X functionality
- Updated Y to handle Z case
- Fixed edge case in W

## Test Coverage

- Unit tests: [list key tests]
- Integration tests: [list key integration scenarios]
- Coverage: X% (Y integration tests)

## Stack Position

[If part of epic]
This PR is part of Epic #580 and depends on PR #586.

Fixes #{issue_number}
```

## Why --publish Is Required

CodeRabbit (automated code review) **cannot review draft PRs**.

**Wrong**:
```bash
gt submit  # Creates draft by default
```

Result: CodeRabbit won't review, delays feedback.

**Correct**:
```bash
gt submit --publish  # Ready for review
```

Result: CodeRabbit reviews immediately.

## Common Issues

### Issue 1: PR Created but Not in Stack

**Symptoms**:
- PR exists on GitHub
- `gt log --stack` doesn't show PR
- Graphite web UI shows isolated PR

**Cause**: Used `gh pr create` instead of `gt submit`

**Fix**:
```bash
gt submit --no-edit --no-interactive  # Re-register
gt log --stack  # Verify
```

### Issue 2: Wrong Base Branch

**Symptoms**:
- PR base is `main` but should be `issue-581`
- Stack looks broken

**Cause**: Graphite couldn't determine parent (parent PR didn't exist yet)

**Fix**:
```bash
gh pr edit <PR_NUMBER> --base issue-581
gt get
gt log --stack
```

### Issue 3: Can't Submit (Branch Not Tracked)

**Error**: "Branch issue-582 is not tracked by Graphite"

**Cause**: Forgot to run `gt track`

**Fix**:
```bash
gt track issue-582
gt submit --publish --title "..." --body "..."
```

## Graphite Backend Registration

**What it means**: Graphite has two parts:
1. **Local CLI**: Tracks branches locally
2. **Backend/Web UI**: Cloud service for stack visualization

`gh pr create` only creates GitHub PR (1, not 2).
`gt submit` creates GitHub PR AND registers with backend (1 + 2).

**Without backend registration**:
- ✗ No stack visualization in web UI
- ✗ No unified stack operations
- ✗ No Graphite-specific features

**With backend registration**:
- ✓ Stack visible at https://app.graphite.dev
- ✓ Visual dependency graph
- ✓ Batch operations on stack
- ✓ Better collaboration

**Always use `gt submit`** to get full Graphite features.

## Integration with TDD Workflow

This skill implements Step 9 of the TDD workflow:

1. Steps 1-8: Develop feature with TDD
2. **Step 9: Submit PR** ← THIS SKILL
3. Step 10: Verify base and registration
4. Step 11: Final checks

The TDD workflow provides context (issue number, worktree path).
This skill focuses on the mechanics of PR creation.

## Best Practices

1. **Always use `gt submit`**: Not `gh pr create`
2. **Always publish**: Use `--publish` flag for CodeRabbit
3. **Verify registration**: Check `gt log --stack` after submit
4. **Fix base immediately**: Don't let wrong base branches linger
5. **Clean worktree**: Ensure `git status` is clean before submit
6. **Descriptive titles**: Reference issue number and describe change

## See Also

- [stack-verification.md](./stack-verification.md) - Base branch verification
- [../tdd-graphite-workflow/graphite-commands.md](../tdd-graphite-workflow/graphite-commands.md) - Full `gt` command reference

Begin PR submission now.
