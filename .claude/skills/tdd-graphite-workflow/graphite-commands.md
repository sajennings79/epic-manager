# Graphite CLI Command Reference

Complete reference for Graphite (`gt`) commands used in TDD workflow.

## Overview

Graphite is a CLI tool for managing stacked pull requests. It helps create, track, and manage chains of dependent PRs where each PR builds on the previous one.

**Key concepts**:
- **Stack**: A chain of dependent branches/PRs
- **Trunk**: The main branch (usually `main`)
- **Parent**: The branch this branch is based on
- **Children**: Branches that build on this branch

## Essential Commands for TDD Workflow

### 1. gt sync

Synchronizes Graphite's metadata with GitHub's actual state.

```bash
gt sync
```

**What it does**:
- Fetches latest PR information from GitHub
- Updates Graphite's local metadata
- Syncs PR status, reviews, and CI checks

**When to use**:
- At the start of every workflow (Step 1)
- After any manual changes to PRs on GitHub
- When resuming work on an existing epic
- To fix "unknown parent" warnings

### 2. gt restack

Rebuilds the stack based on current git state.

```bash
gt restack
```

**What it does**:
- Analyzes git branch relationships
- Rebuilds Graphite's stack structure
- Ensures child branches are properly based on parents

**When to use**:
- After `gt sync` (Step 1)
- When stack structure seems incorrect
- After rebasing or merging

### 3. gt ls

Lists all branches in the repository with stack information.

```bash
gt ls
```

**Output example**:
```
main
└─ epic-580
   ├─ issue-581 ✓ (PR #586)
   ├─ issue-582 ✓ (PR #587)
   ├─ issue-583 ⏳ (in progress)
   └─ issue-584 ○ (pending)
```

**What it shows**:
- Branch hierarchy
- PR numbers (if created)
- Status indicators:
  - ✓ = PR created
  - ⏳ = Work in progress
  - ○ = Not started

**When to use**:
- To verify stack structure (Step 1, 2)
- To see which PRs exist
- To confirm parent-child relationships

### 4. gt status

Shows status of the current branch.

```bash
gt status
```

**Output example**:
```
On branch: issue-581
Parent: main
Children: issue-582
PR: #586 (https://github.com/owner/repo/pull/586)
Status: Open
Checks: ✓ All passing
```

**When to use**:
- To confirm current branch (Step 2, 3)
- To see PR information
- To check CI status

### 5. gt track

Registers an existing git branch with Graphite.

```bash
gt track <branch-name>
```

**Example**:
```bash
git branch --show-current  # Verify current branch
gt track issue-581         # Register it with Graphite
```

**What it does**:
- Adds existing branch to Graphite's tracking
- Determines parent from git ancestry
- Enables Graphite commands for this branch

**When to use**:
- After epic-manager creates worktree (Step 3)
- For branches created outside Graphite
- When "branch not tracked" error appears

**Important**: Do NOT use `gt create` - epic-manager already created the branch with correct base.

### 6. gt submit

Creates or updates a PR for the current branch.

```bash
gt submit --no-interactive --publish \
  --title "Title here" \
  --body "Body here"
```

**Flags**:
- `--no-interactive`: Don't prompt for input
- `--publish`: Create as ready-for-review (not draft)
- `--title`: PR title
- `--body`: PR description
- `--no-edit`: Don't edit existing PR (for re-registration)

**What it does**:
- Creates PR on GitHub
- Registers PR with Graphite's backend
- Sets base branch from git ancestry
- Enables Graphite web UI features

**When to use**:
- To create PR after implementation (Step 9)
- To update PR after changes
- To re-register PR with Graphite backend

**Critical**: Always use `--publish` for CodeRabbit review (CodeRabbit can't review drafts).

### 7. gt log --stack

Shows detailed stack structure with commit history.

```bash
gt log --stack
```

**Output example**:
```
◯ issue-583 (HEAD)
│ Add notification system
│ PR: Not created
│
◯ issue-582
│ Fix authentication bug
│ PR: #587 (https://github.com/...)
│
◯ issue-581
│ Update user model
│ PR: #586 (https://github.com/...)
│
◯ main (trunk)
```

**When to use**:
- To verify stack visualization (Step 10)
- To check PR registration
- To see commit messages in context

### 8. gt get

Fetches Graphite's latest metadata for current stack.

```bash
gt get
```

**What it does**:
- Updates local Graphite metadata
- Syncs with GitHub PR changes
- Refreshes PR base branches

**When to use**:
- After changing PR base branch manually (Step 10)
- To refresh metadata after GitHub changes

## Advanced Commands

### gt create

Creates a new branch with Graphite tracking.

```bash
gt create <branch-name>
```

**Note**: Epic-manager creates branches for you with correct base. Don't use this in TDD workflow.

### gt stack submit

Submits all PRs in the current stack.

```bash
gt stack submit
```

**When to use**:
- When manually creating entire stack
- Not needed in epic-manager workflow (sequential submission)

### gt branch checkout

Switches to a branch in the stack.

```bash
gt branch checkout <branch-name>
```

**Alias**: `gt co <branch-name>`

## Common Patterns

### Pattern 1: Start of Workflow

```bash
gt sync          # Fetch GitHub state
gt restack       # Rebuild stack
gt ls            # Verify structure
gt status        # Check current branch
```

### Pattern 2: Register Existing Branch

```bash
git branch --show-current  # Verify branch
gt track issue-581         # Register with Graphite
gt status                  # Confirm registration
```

### Pattern 3: Submit PR

```bash
gt submit --no-interactive --publish \
  --title "Fix #581: Description" \
  --body "## Summary\n\nChanges here"

# Capture PR number from output
```

### Pattern 4: Fix Incorrect PR Base

```bash
# Check current base
gh pr view <PR_NUMBER> --json baseRefName

# Fix base branch
gh pr edit <PR_NUMBER> --base <correct-branch>

# Sync Graphite
gt get
```

### Pattern 5: Re-register PR with Graphite

```bash
# If PR exists but not in Graphite backend
gt submit --no-edit --no-interactive

# Verify registration
gt log --stack
```

## Troubleshooting

### "Branch not tracked by Graphite"

**Solution**:
```bash
gt track <branch-name>
```

### "Unknown parent branch"

**Solution**:
```bash
gt sync
gt restack
```

### "PR doesn't appear in gt log --stack"

**Problem**: PR created with `gh` instead of `gt submit`

**Solution**:
```bash
# Re-submit to register with Graphite backend
gt submit --no-edit --no-interactive
```

### "Base branch is wrong on GitHub"

**Solution**:
```bash
# Fix via gh CLI
gh pr edit <PR_NUMBER> --base <correct-branch>

# Sync Graphite
gt get
```

## Integration with Epic Manager

Epic-manager orchestration:
1. **Creates worktrees** with correct base branches (git level)
2. **You register** branches with Graphite (`gt track`)
3. **You submit PRs** via Graphite (`gt submit`)
4. **Epic-manager verifies** PRs exist before dependent issues

This ensures:
- ✅ Correct git ancestry
- ✅ Proper Graphite stacking
- ✅ Backend registration for web UI
- ✅ Sequential PR creation prevents base branch issues

## Best Practices

1. **Always sync first**: Start every workflow with `gt sync && gt restack`
2. **Verify structure**: Use `gt ls` to confirm stack looks correct
3. **Track before submit**: Use `gt track` before `gt submit` for existing branches
4. **Use --publish**: Always publish PRs for CodeRabbit review
5. **Verify registration**: Check `gt log --stack` after PR creation
6. **Never force-push**: Breaks Graphite metadata

## Command Cheat Sheet

```bash
# Sync and verify
gt sync && gt restack && gt ls

# Track existing branch
gt track issue-581

# Submit PR (published, not draft)
gt submit --no-interactive --publish --title "..." --body "..."

# Verify PR registration
gt log --stack

# Fix PR base branch
gh pr edit <PR> --base <branch> && gt get

# Re-register PR
gt submit --no-edit --no-interactive
```

## References

- Graphite documentation: https://docs.graphite.dev
- Graphite web UI: https://app.graphite.dev
- GitHub CLI (gh): https://cli.github.com/manual/
