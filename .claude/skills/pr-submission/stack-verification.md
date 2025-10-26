# Stack Verification and Base Branch Checks

Detailed guide for verifying PR base branches and Graphite stack integrity.

## Why Base Branches Matter

In Graphite stacked PRs:
- PR base branch = dependency relationship
- Correct base = proper stack visualization
- Wrong base = broken stack, merge conflicts

**Example stack**:
```
main
 └─ issue-581 (PR #586)
     └─ issue-582 (PR #587)  ← base should be issue-581, NOT main
         └─ issue-583 (PR #588)  ← base should be issue-582, NOT main
```

If #587 bases on `main` instead of `issue-581`, the stack breaks.

## Verification Steps

### 1. Check PR Base Branch

```bash
gh pr view <PR_NUMBER> --json baseRefName,headRefName
```

**Output**:
```json
{
  "baseRefName": "issue-581",  // Where this PR will merge
  "headRefName": "issue-582"   // This PR's branch
}
```

**Verify**:
- Is `baseRefName` correct for this PR's position in stack?
- First PR in stack should base on `main`
- Dependent PRs should base on parent `issue-{N}`

### 2. Check Stack Structure

```bash
gt ls
```

**Expected**:
```
main
 └─ issue-581 ✓ (PR #586)
     └─ issue-582 ✓ (PR #587)
         └─ issue-583 ⏳ (in progress)
```

**Verify**:
- Visual hierarchy matches expected dependencies
- Child branches appear under correct parents
- No orphaned branches

### 3. Check Git Ancestry

```bash
# Show actual git ancestry
git log --oneline --graph --all
```

**Verify**:
- Branch ancestry matches stack structure
- Child branches contain parent commits
- No divergent histories

### 4. Check Graphite Backend

```bash
gt log --stack
```

**Expected**:
```
◯ issue-583 (HEAD)
│ Add notification system
│ PR: #588 (https://github.com/...)
│ Parent: issue-582
│
◯ issue-582
│ Fix authentication bug
│ PR: #587 (https://github.com/...)
│ Parent: issue-581
│
◯ issue-581
│ Update user model
│ PR: #586 (https://github.com/...)
│ Parent: main
```

**Verify**:
- Each PR shows correct parent
- PR URLs are present
- No "unknown parent" warnings

## Common Base Branch Problems

### Problem 1: PR Targets Main Instead of Parent

**Symptoms**:
```bash
gh pr view 587 --json baseRefName
# Shows: {"baseRefName": "main"}
# Expected: {"baseRefName": "issue-581"}
```

**Cause**:
- Parent PR didn't exist when this PR was created
- Graphite fell back to `main`
- Epic-manager's sequential execution prevents this!

**Fix**:
```bash
gh pr edit 587 --base issue-581
gt get  # Sync Graphite metadata
gt log --stack  # Verify fix
```

### Problem 2: Circular Base References

**Symptoms**:
- Issue A bases on B
- Issue B bases on A

**Cause**: Manual PR editing error

**Fix**: Break the cycle:
```bash
# Decide correct order (e.g., B depends on A)
gh pr edit <PR_B> --base issue-A
gt get
```

### Problem 3: Base Points to Merged Branch

**Symptoms**:
- PR base is `issue-581`
- But `issue-581` was already merged to main

**Expected behavior**: This is actually OK during review!

**After parent merges**:
- Child PR automatically updates to new parent
- Or rebases on main (if last in chain)

**No action needed** unless you want to manually rebase.

### Problem 4: Base Points to Wrong Branch

**Symptoms**:
- Issue 583 should depend on 582
- But base is `issue-581`

**Fix**:
```bash
# Update base to correct parent
gh pr edit 588 --base issue-582

# Rebase local branch if needed
git rebase --onto issue-582 issue-581 issue-583

# Force push (updates PR)
git push -f

# Sync Graphite
gt get
```

## Automated Verification Script

Create a script to verify all PRs in a stack:

```bash
#!/bin/bash
# verify_stack.sh

EPIC_NUM=$1

echo "Verifying stack for epic $EPIC_NUM..."

# Get all PRs for this epic
PR_NUMBERS=$(gh pr list --json number,title | jq -r ".[] | select(.title | contains(\"#\")) | .number")

for PR in $PR_NUMBERS; do
    echo ""
    echo "Checking PR #$PR..."

    # Get base and head
    BASE=$(gh pr view $PR --json baseRefName | jq -r .baseRefName)
    HEAD=$(gh pr view $PR --json headRefName | jq -r .headRefName)

    echo "  Head: $HEAD"
    echo "  Base: $BASE"

    # Check if base matches expected pattern
    if [[ $BASE == "issue-"* ]] || [[ $BASE == "main" ]]; then
        echo "  ✓ Base branch format OK"
    else
        echo "  ✗ WARNING: Unexpected base branch format"
    fi

    # Check Graphite registration
    if gt log --stack | grep -q "PR: #$PR"; then
        echo "  ✓ Registered in Graphite backend"
    else
        echo "  ✗ NOT in Graphite backend - run 'gt submit --no-edit' in $HEAD"
    fi
done

echo ""
echo "Stack verification complete!"
```

Run it:
```bash
chmod +x verify_stack.sh
./verify_stack.sh 580
```

## Manual Verification Checklist

For each PR in the stack:

- [ ] PR exists on GitHub
- [ ] Base branch is correct (matches dependency)
- [ ] Head branch name matches issue (`issue-{N}`)
- [ ] PR appears in `gt log --stack`
- [ ] PR URL shown in `gt status`
- [ ] Git ancestry matches (parent commits in child branch)
- [ ] No "unknown parent" warnings
- [ ] PR visible in Graphite web UI (https://app.graphite.dev)

## Fixing Broken Stacks

If verification fails for multiple PRs:

### Option 1: Fix Base Branches Individually

```bash
# For each PR with wrong base
gh pr edit <PR> --base <correct-parent>
gt get
```

### Option 2: Rebuild Stack from Scratch

```bash
# Only if stack is completely broken
cd /opt/{instance}

# Sync with GitHub
gt sync
gt restack

# Verify structure
gt ls
gt log --stack

# Fix any remaining issues
# ...
```

### Option 3: Use Epic-Manager Verification

```bash
# Epic-manager has built-in verification
epic-mgr epic verify-prs <epic_number>
```

This automatically checks and fixes all PR base branches for an epic.

## Prevention

To avoid base branch issues:

1. **Use epic-manager**: Handles sequencing automatically
2. **Always use `gt submit`**: Registers with backend correctly
3. **Verify immediately**: Check base right after PR creation
4. **Sequential execution**: Epic-manager ensures parent PR exists first
5. **Regular sync**: Run `gt sync && gt restack` frequently

## Integration with Epic Workflow

Epic-manager's TDD workflow includes automatic verification:

- **Step 9**: Create PR via `gt submit`
- **Step 10**: Verify base branch and registration ← THIS
- **Step 11**: Final checks

The verification is built into the workflow, not a separate manual step.

## When Base Branch Changes Are OK

Some base changes are intentional:

1. **Parent merges**: Base updates from `issue-581` to `main` (OK!)
2. **Stack reordering**: Deliberate dependency change (OK if planned)
3. **Rebasing**: Base stays same, commits change (OK!)

Don't "fix" these legitimate changes.

## Resources

- Graphite docs: https://docs.graphite.dev/guides/stacking-pull-requests
- GitHub CLI: https://cli.github.com/manual/gh_pr_edit
- Epic-manager CLAUDE.md: Base branch verification section
