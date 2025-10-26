# PR Base Branch Verification

After fixing CodeRabbit reviews, verify PR base branch is still correct (especially if rebased or merged).

## Why This Matters

During review fixes, you might:
- Rebase on main
- Merge parent branch changes
- Resolve conflicts

These operations can sometimes change the PR base branch unintentionally.

## Verification Process

### 1. Check Current Base

```bash
gh pr view {pr_number} --json baseRefName,headRefName
```

Expected output:
```json
{
  "baseRefName": "issue-581",  // Parent branch
  "headRefName": "issue-582"   // This branch
}
```

### 2. Verify Against Stack

Check if base matches expected parent:

```bash
gt ls  # See stack structure
```

If this PR should be part of a stack, the base should be the parent issue branch, not `main`.

### 3. Fix if Needed

If base is wrong:

```bash
# Fix base branch
gh pr edit {pr_number} --base <correct-parent-branch>

# Sync Graphite
gt get
gt log --stack  # Verify stack structure
```

## Common Issues

### Base Changed to Main

**Problem**: PR base was `issue-581`, now shows `main` after rebase

**Cause**: Incorrect rebase command or GitHub UI change

**Fix**:
```bash
gh pr edit {pr_number} --base issue-581
gt get
```

### Parent Branch Merged

**Problem**: Parent branch (`issue-581`) was merged, PR now orphaned

**Solution**: This is expected! Once parent merges, child PRs typically rebase on main.

**Verify**:
- If parent is merged AND in main, rebasing to main is correct
- If parent is merged but NOT in main yet, keep parent as base

### Stack Reordering

**Problem**: Stack order changed during review

**Solution**: Update base branches for entire stack

```bash
# For each affected PR
gh pr edit {pr_number} --base <new-parent>

# Sync Graphite for all
gt sync && gt restack
```

## Best Practices

1. **Check after rebasing**: Always verify base after git rebase
2. **Check after conflicts**: Conflict resolution can confuse base
3. **Use Graphite commands**: `gt` handles base branches correctly
4. **Coordinate with epic-manager**: Let automation handle complex restacking

## Integration with Review Workflow

Add this check at the end of Step 5 (Update PR):

```bash
# After pushing fixes
git push

# Verify base branch still correct
gh pr view {pr_number} --json baseRefName
gt ls  # Confirm stack structure

# Add verification to PR comment
gh pr comment {pr_number} --body "## CodeRabbit Review Addressed

[... fixes listed ...]

✓ PR base branch verified: correct parent in stack
✓ All tests passing
✓ Ready for re-review"
```

This ensures review fixes don't accidentally break the stack structure.
