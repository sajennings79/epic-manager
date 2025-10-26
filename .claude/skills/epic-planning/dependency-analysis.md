# Dependency Analysis Patterns

Advanced patterns for analyzing issue dependencies in epics.

## Dependency Types

### 1. Direct Code Dependency

Issue B needs code written in Issue A.

**Example**:
- Issue A: "Create User model"
- Issue B: "Create User API" (needs User model)

**Relationship**: B depends on A, `base_branch: "issue-A"`

### 2. Data Dependency

Issue B needs data/state created by Issue A.

**Example**:
- Issue A: "Add database schema"
- Issue B: "Add migration scripts" (needs schema definition)

**Relationship**: B depends on A

### 3. Interface Dependency

Issue B implements an interface defined in Issue A.

**Example**:
- Issue A: "Define notification interface"
- Issue B: "Implement email notifications" (uses interface)

**Relationship**: B depends on A

### 4. Test Dependency

Issue B tests functionality from Issue A.

**Example**:
- Issue A: "Implement authentication"
- Issue B: "Add authentication tests"

**Relationship**: B depends on A (must test actual implementation)

### 5. Independent (No Dependency)

Issues can be developed completely independently.

**Example**:
- Issue A: "Add logging system"
- Issue B: "Add caching system"

**Relationship**: No dependency, both `base_branch: "main"`

## Complex Patterns

### Shared Foundation Pattern

Multiple issues depend on the same foundation.

```
main
 └─ issue-581 (Foundation)
     ├─ issue-582 (Feature A using foundation)
     ├─ issue-583 (Feature B using foundation)
     └─ issue-584 (Feature C using foundation)
```

**Parallelization**:
- Phase 1: [581]
- Phase 2: [582, 583, 584] (all parallel)

### Sequential Chain Pattern

Each issue builds on the previous.

```
main
 └─ issue-581
     └─ issue-582
         └─ issue-583
             └─ issue-584
```

**Parallelization**:
- Phase 1: [581]
- Phase 2: [582]
- Phase 3: [583]
- Phase 4: [584]

**Performance**: No parallelism, but ensures correct order.

### Diamond Pattern

Branches converge back together.

```
main
 └─ issue-581
     ├─ issue-582
     │   └─ issue-584 (needs both 582 and 583)
     └─ issue-583 ─┘
```

**Parallelization**:
- Phase 1: [581]
- Phase 2: [582, 583] (parallel branches)
- Phase 3: [584] (convergence)

**Base branch for 584**: Choose `issue-583` (or whichever is done last)

### Multi-Root Pattern

Multiple independent starting points.

```
main
 ├─ issue-581 (Backend)
 │   └─ issue-582
 └─ issue-583 (Frontend)
     └─ issue-584
```

**Parallelization**:
- Phase 1: [581, 583] (independent roots)
- Phase 2: [582, 584] (parallel chains)

## Determining Dependencies from Issue Descriptions

### Keywords Indicating Dependency

**Strong dependency indicators**:
- "uses", "depends on", "requires", "builds on"
- "extends", "implements interface from"
- "tests functionality from"
- "integrates with"

**Example**:
> "This issue implements the user API **using the User model from #581**"

**Analysis**: Depends on #581

### Keywords Indicating Independence

**Independence indicators**:
- "separate", "independent", "standalone"
- "different module", "unrelated to"
- "parallel effort"

**Example**:
> "This issue adds logging, which is **independent of** the authentication work in #581"

**Analysis**: No dependency

### Implicit Dependencies

Sometimes dependencies aren't explicitly stated.

**Look for**:
- Shared data models
- Shared utilities/helpers
- Component layering (API layer uses service layer)

**Example**:
> Issue A: "Add StateStorage class"
> Issue B: "Add meeting state persistence"

**Analysis**: B likely uses StateStorage from A, even if not stated.

## Edge Cases

### Optional Dependencies

Issue B would benefit from A but doesn't strictly require it.

**Solution**: Treat as independent unless epic description specifies order.

### Circular Dependencies

Issue A needs B, and B needs A.

**Solution**: This is a design error. Recommend:
1. Split into three issues: common foundation, A, B
2. Or make one issue depend on the other (break the cycle)

### Conflicting Dependencies

Issue C depends on both A and B, but A and B conflict.

**Solution**: Report as epic design error. Need to resolve conflict first.

## Validation Checks

After creating dependency graph, verify:

### 1. No Cycles

```python
def has_cycles(graph):
    visited = set()
    rec_stack = set()

    def is_cyclic(node):
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph[node]:
            if neighbor not in visited:
                if is_cyclic(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    for node in graph:
        if node not in visited:
            if is_cyclic(node):
                return True
    return False
```

### 2. All Dependencies Exist

Every dependency number is a valid issue in the epic.

### 3. Base Branches Match Dependencies

If issue B depends on A, then `base_branch` should be `"issue-A"`.

### 4. Phases Are Consistent

All issues in phase N should only depend on issues from phases < N.

## Example Analysis

**Epic description**:
> "Add user management with authentication and testing"
>
> - #581: Add User model and database schema
> - #582: Add User API endpoints
> - #583: Add JWT authentication middleware
> - #584: Add integration tests for user workflows
> - #585: Add API documentation

**Analysis**:

**Issue 581** (User model):
- No mentions of other issues
- Foundation piece
- Dependencies: none
- Base: `main`

**Issue 582** (User API):
- Likely uses User model from 581
- Description doesn't explicitly say, but API needs model
- Dependencies: [581]
- Base: `issue-581`

**Issue 583** (JWT auth):
- Authentication middleware is separate concern
- May use User model but could be implemented independently
- Description doesn't mention dependencies
- Conservative: Dependencies: [581] (needs to auth users)
- Base: `issue-581`

**Issue 584** (Integration tests):
- Tests "user workflows" - needs all user functionality
- Must wait for 581, 582, 583
- Dependencies: [581, 582, 583]
- Base: `issue-583` (last in chain)

**Issue 585** (API docs):
- Documents API from 582
- Dependencies: [582]
- Base: `issue-582`

**Result**:
```json
{
  "parallelization": {
    "phase_1": [581],
    "phase_2": [582, 583],
    "phase_3": [584, 585]
  }
}
```

**Explanation**:
- Phase 1: Foundation (581)
- Phase 2: API and auth can be parallel (both depend only on 581)
- Phase 3: Tests and docs (depend on phase 2)

This allows maximum parallelism while respecting dependencies.
