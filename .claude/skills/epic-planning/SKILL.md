---
name: epic-planning
description: Analyze GitHub epic issues and create JSON execution plans with dependency chains and parallelization phases. Use this when asked to analyze an epic, create an epic plan, plan epic execution, or determine issue dependencies. Triggers include "analyze epic", "epic plan", "plan epic", "create plan for epic", "determine dependencies".
allowed-tools: [Read, Bash, Grep, Glob, WebFetch]
---

# Epic Planning and Dependency Analysis

Analyze a GitHub epic issue and create a comprehensive JSON execution plan that defines issue dependencies, base branches, and parallelization phases.

## Purpose

Epic Manager needs a structured plan to:
1. Understand issue dependencies (which issues build on others)
2. Determine base branches for git worktree creation
3. Identify parallelization opportunities (independent issues)
4. Sequence execution correctly (sequential within chains, parallel across chains)

## Input

- **Epic number**: GitHub issue number tagged as epic
- **Instance name**: KB-LLM instance being developed

## Output

A JSON plan with this exact structure:

```json
{
  "epic": {
    "number": 580,
    "title": "Epic title",
    "repo": "owner/repo-name",
    "instance": "feature"
  },
  "issues": [
    {
      "number": 581,
      "title": "First issue - starts from main",
      "status": "pending",
      "dependencies": [],
      "base_branch": "main"
    },
    {
      "number": 582,
      "title": "Second issue - depends on 581",
      "status": "pending",
      "dependencies": [581],
      "base_branch": "issue-581"
    },
    {
      "number": 583,
      "title": "Third issue - also depends on 581",
      "status": "pending",
      "dependencies": [581],
      "base_branch": "issue-581"
    }
  ],
  "parallelization": {
    "phase_1": [581],
    "phase_2": [582, 583]
  }
}
```

## Critical Instructions for base_branch

**CRITICAL**: The `base_branch` field determines git ancestry and Graphite stack structure.

### Rules

- `base_branch` MUST be a valid git branch reference, NOT a description or component name
- Use `"main"` for issues that start from trunk (first issue, or independent parallel issues)
- Use `"issue-{number}"` for issues that depend on another issue's branch
- The base_branch creates the Graphite stack parent-child relationship
- NEVER use folder paths, component names, or descriptions (e.g., NOT `"backend/service-name"`)

### Examples

✅ **Correct**:
```json
{"base_branch": "main", "dependencies": []}
{"base_branch": "issue-123", "dependencies": [123]}
{"base_branch": "issue-124", "dependencies": [124]}
```

❌ **Wrong**:
```json
{"base_branch": "backend", "dependencies": []}
{"base_branch": "feature/auth", "dependencies": []}
{"base_branch": "user-service", "dependencies": []}
```

## Planning Process

### Step 1: Fetch Epic Data

```bash
gh issue view {epic_number} --json title,body,labels,comments
```

Read the complete epic description and all comments for context.

### Step 2: Identify Linked Issues

Fetch all issues referenced in the epic:

```bash
# Get linked issues
gh issue view {epic_number} --json body | jq -r '.body'

# Extract issue numbers
# Look for patterns like: #581, #582, etc.
```

**Note**: Filter out CSS color codes (e.g., `#374151` for Tailwind). Only actual GitHub issue numbers < 100,000.

### Step 3: Analyze Each Issue

For each linked issue, fetch details:

```bash
gh issue view {issue_number} --json title,body,labels
```

Determine:
- What functionality it implements
- Prerequisites or dependencies on other issues
- Whether it can start from `main` or needs another issue first

### Step 4: Build Dependency Graph

**Analyze dependencies**:
1. Does this issue need code from another issue to function?
2. Can this issue be implemented independently?
3. Are there shared dependencies (both depend on the same issue)?

**Example dependency analysis**:
- Issue 581: "Add User model" → No dependencies, starts from `main`
- Issue 582: "Add User API using User model" → Depends on 581, base: `issue-581`
- Issue 583: "Add User tests" → Depends on 581, base: `issue-581`
- Issue 584: "Add logging system" → Independent, starts from `main`

### Step 5: Determine Base Branches

For each issue:

**If no dependencies** (can start from main):
```json
{
  "number": 581,
  "dependencies": [],
  "base_branch": "main"
}
```

**If depends on one issue**:
```json
{
  "number": 582,
  "dependencies": [581],
  "base_branch": "issue-581"
}
```

**If depends on multiple issues** (choose the last one in sequence):
```json
{
  "number": 585,
  "dependencies": [583, 584],
  "base_branch": "issue-584"
}
```

### Step 6: Create Parallelization Phases

Group issues into execution phases:

**Rules**:
- Phase 1: Issues with no dependencies (start from `main`)
- Phase 2: Issues that depend only on Phase 1 issues
- Phase 3: Issues that depend on Phase 2 issues
- etc.

**Example**:
```json
"parallelization": {
  "phase_1": [581, 584],     // Independent, can run in parallel
  "phase_2": [582, 583, 585], // All depend on phase 1, can run in parallel
  "phase_3": [586]            // Depends on phase 2
}
```

### Step 7: Validate Plan

Check for logical consistency:
- ✓ Every issue has a valid `base_branch` (either "main" or "issue-{N}")
- ✓ Dependency chains are correct (no circular dependencies)
- ✓ Parallelization phases match dependencies
- ✓ All issues from epic are included
- ✓ Issue numbers are valid (< 100,000, not color codes)

## Supporting Reference

See [dependency-analysis.md](./dependency-analysis.md) for advanced dependency patterns.

## Output Format

Return ONLY the JSON object. No markdown code blocks, no explanations, just pure JSON.

**Correct**:
```
{
  "epic": {...},
  "issues": [...],
  "parallelization": {...}
}
```

**Wrong**:
```markdown
Here's the plan:
```json
{...}
```
```

## Common Patterns

### Pattern 1: Linear Chain

Issues must execute sequentially:

```json
{
  "issues": [
    {"number": 581, "base_branch": "main", "dependencies": []},
    {"number": 582, "base_branch": "issue-581", "dependencies": [581]},
    {"number": 583, "base_branch": "issue-582", "dependencies": [582]}
  ],
  "parallelization": {
    "phase_1": [581],
    "phase_2": [582],
    "phase_3": [583]
  }
}
```

### Pattern 2: Parallel Branches

Independent issues can run simultaneously:

```json
{
  "issues": [
    {"number": 581, "base_branch": "main", "dependencies": []},
    {"number": 582, "base_branch": "main", "dependencies": []},
    {"number": 583, "base_branch": "main", "dependencies": []}
  ],
  "parallelization": {
    "phase_1": [581, 582, 583]  // All parallel
  }
}
```

### Pattern 3: Diamond Pattern

Multiple branches converge:

```json
{
  "issues": [
    {"number": 581, "base_branch": "main", "dependencies": []},
    {"number": 582, "base_branch": "issue-581", "dependencies": [581]},
    {"number": 583, "base_branch": "issue-581", "dependencies": [581]},
    {"number": 584, "base_branch": "issue-583", "dependencies": [583]}
  ],
  "parallelization": {
    "phase_1": [581],
    "phase_2": [582, 583],  // Parallel branches from 581
    "phase_3": [584]        // Converges after 583
  }
}
```

## Troubleshooting

### Too Many Linked Issues (30+)

**Problem**: Epic description contains Tailwind color codes (e.g., `#374151`)

**Solution**: Filter issue numbers:
- Only include numbers < 100,000
- Verify each number is a real GitHub issue
- Exclude duplicates

### Unclear Dependencies

**Problem**: Can't determine if Issue A depends on Issue B

**Solution**:
- Read both issue descriptions carefully
- Look for mentions of shared code/models
- Check if one issue's acceptance criteria mentions the other
- When in doubt, assume independence (both start from `main`)

### Circular Dependencies

**Problem**: Issue A depends on B, B depends on A

**Solution**:
- This is a design error in the epic
- Choose a logical starting point
- Report the circular dependency
- Suggest splitting or reordering issues

## Example Analysis Session

**Epic 580**: "Add user management system"

**Linked issues**:
- #581: "Add User data model"
- #582: "Add User API endpoints"
- #583: "Add User authentication"
- #584: "Add User tests"

**Analysis**:
- 581: Foundation, no dependencies → `base_branch: "main"`
- 582: Needs User model from 581 → `base_branch: "issue-581"`
- 583: Needs User model from 581 → `base_branch: "issue-581"`
- 584: Needs User model from 581 → `base_branch: "issue-581"`

**Parallelization**:
- Phase 1: [581] (foundation)
- Phase 2: [582, 583, 584] (all depend only on 581, can run parallel)

**Result**:
```json
{
  "epic": {
    "number": 580,
    "title": "Add user management system",
    "repo": "owner/kb-llm",
    "instance": "feature"
  },
  "issues": [
    {
      "number": 581,
      "title": "Add User data model",
      "status": "pending",
      "dependencies": [],
      "base_branch": "main"
    },
    {
      "number": 582,
      "title": "Add User API endpoints",
      "status": "pending",
      "dependencies": [581],
      "base_branch": "issue-581"
    },
    {
      "number": 583,
      "title": "Add User authentication",
      "status": "pending",
      "dependencies": [581],
      "base_branch": "issue-581"
    },
    {
      "number": 584,
      "title": "Add User tests",
      "status": "pending",
      "dependencies": [581],
      "base_branch": "issue-581"
    }
  ],
  "parallelization": {
    "phase_1": [581],
    "phase_2": [582, 583, 584]
  }
}
```

Begin epic analysis now.
