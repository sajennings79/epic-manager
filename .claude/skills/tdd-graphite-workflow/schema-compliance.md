# Schema Compliance Check

Verify all field access in implementation matches documented schema reference.

## Why This Matters

This check prevents `AttributeError` bugs in production by catching field name mismatches **before** code is committed. Even a single typo (e.g., `.last_updated` vs `.updated_at`) causes runtime failures.

## Validation Steps

### 1. Load Schema Reference

- Review the schema reference created during discovery phase
- Note all documented field names for each model
- Pay attention to "Common Errors to Avoid" section

### 2. Identify Modified Files

Find all Python files changed for this issue:

```bash
git diff --name-only --cached --diff-filter=AM "*.py"
```

Focus on files that access data models.

### 3. Extract Field Access Patterns

For each modified file, find all attribute access:

```bash
# Find all attribute access patterns
grep -E "\.[a-z_]+" filename.py

# More sophisticated: find object.field patterns
grep -E "[a-z_]+\.[a-z_]+" filename.py
```

Look for patterns like:
- `object.field_name`
- `object.field['key']`
- `object.nested.field`

Create list of all field names referenced in code.

### 4. Compare Against Schema

For each field access found:
- Check if field name exists in schema reference
- Verify exact spelling (case-sensitive)
- Confirm nested structure access is correct

**Flag ANY field name not in schema reference as a violation.**

### 5. Report Violations

List all field name mismatches found.

For each violation, show:
- File and line number
- Incorrect field name used
- Correct field name from schema
- Suggested fix

**Example format**:
```
VIOLATION in app/services/meeting.py:45
❌ state.last_updated
✅ state.updated_at
Fix: Change line 45 from "state.last_updated" to "state.updated_at"
```

## Common Violation Patterns to Check

### 1. Timestamp Fields

❌ `.last_updated`, `.modified_at`, `.changed_at`
✅ `.updated_at` (or whatever schema defines)

```bash
# Search for common timestamp errors
grep -rn "\.last_updated\|\.modified_at\|\.changed_at" . --include="*.py"
```

### 2. Boolean Fields

❌ `.finalized`, `.completed`, `.active`
✅ `.is_finalized`, `.is_completed`, `.is_active` (or whatever schema defines)

```bash
# Search for boolean fields missing "is_" prefix
grep -rn "\.finalized\|\.completed\|\.active" . --include="*.py"
```

### 3. Collection Fields

❌ `.participant_entities`, `.project_entities`
✅ `.entities_mentioned['people']`, `.entities_mentioned['projects']`

### 4. Plural vs Singular

❌ `.comment`, `.entity`
✅ `.comments`, `.entities` (check schema for correct form)

## Automated Compliance Check

You can create a simple script to automate this:

```python
# verify_schema_compliance.py
import re
import sys
from pathlib import Path

SCHEMA = {
    'MeetingState': {
        'fields': ['meeting_id', 'bot_id', 'updated_at', 'entities_mentioned',
                   'body', 'update_count', 'is_finalized'],
        'forbidden': ['last_updated', 'participant_entities', 'finalized']
    }
}

def check_file(filepath):
    """Check a Python file for schema violations."""
    violations = []
    content = Path(filepath).read_text()

    # Find attribute access patterns
    pattern = r'([a-z_]+)\.([a-z_]+)'
    for match in re.finditer(pattern, content):
        obj, field = match.groups()

        # Check against schema
        if obj in SCHEMA and field not in SCHEMA[obj]['fields']:
            violations.append({
                'file': filepath,
                'field': f'{obj}.{field}',
                'line': content[:match.start()].count('\n') + 1
            })

    return violations

# Run on modified files
files = sys.argv[1:]
all_violations = []
for f in files:
    all_violations.extend(check_file(f))

if all_violations:
    print("SCHEMA VIOLATIONS FOUND:")
    for v in all_violations:
        print(f"  {v['file']}:{v['line']} - {v['field']}")
    sys.exit(1)
else:
    print("✅ Schema compliance: 100%")
```

Run it:
```bash
python verify_schema_compliance.py $(git diff --name-only --cached "*.py")
```

## Enforcement

### If Violations Found

- Report as **BLOCKER**
- Do NOT proceed to PR creation
- Fix all violations first
- Re-run compliance check after fixes

**Example violations report**:
```
BLOCKER: Schema compliance violations detected

Violations found:
1. app/services/meeting.py:45
   ❌ state.last_updated
   ✅ state.updated_at

2. app/services/meeting.py:67
   ❌ state.finalized
   ✅ state.is_finalized

3. app/models/state.py:89
   ❌ meeting.participant_entities
   ✅ meeting.entities_mentioned['people']

Action required: Fix all 3 violations before proceeding to PR.
```

### If No Violations Found

Report success and proceed:
```
✅ Schema compliance: 100% - All field names match schema reference

Checked files:
  - app/services/meeting.py
  - app/models/meeting_state.py
  - app/api/endpoints.py

All field access validated against schema. Safe to proceed to PR creation.
```

## Critical Rules

- This check must pass with **ZERO violations** before PR creation
- No exceptions - even "minor" violations cause runtime errors
- If unsure about a field name, check the schema reference again
- When in doubt, re-read the model definition file

## Integration with TDD Workflow

This check happens at **Step 7.5** (after implementation, before verification).

**Workflow position**:
1. Step 4.5: Schema Discovery (document fields)
2. Step 5: Create Tests (use documented fields)
3. Step 7: Implement Feature (use documented fields)
4. **Step 7.5: Schema Compliance Check** ← WE ARE HERE
5. Step 8: Verify Completeness
6. Step 9: Submit PR

**Purpose**: Catch any field name errors introduced during implementation before tests run.

## Manual Check Process

If you don't have an automated script:

1. **Open schema reference** from discovery phase
2. **For each modified file**:
   - Read through implementation
   - Note every attribute access (`.field_name`)
   - Compare against schema reference
   - Mark violations
3. **List all violations** with line numbers
4. **Fix each violation** one by one
5. **Verify** no violations remain

## Example Violations and Fixes

### Violation 1: Timestamp Field

**File**: `app/services/state_manager.py:34`

```python
# BEFORE (WRONG)
state.last_updated = datetime.now()

# AFTER (CORRECT)
state.updated_at = datetime.now()
```

### Violation 2: Boolean Field

**File**: `app/models/meeting.py:56`

```python
# BEFORE (WRONG)
if meeting.finalized:
    return

# AFTER (CORRECT)
if meeting.is_finalized:
    return
```

### Violation 3: Nested Structure

**File**: `app/api/endpoints.py:78`

```python
# BEFORE (WRONG)
participants = meeting.participant_entities

# AFTER (CORRECT)
participants = meeting.entities_mentioned['people']
```

## Success Metrics

After compliance check passes:
- **Zero** field name violations
- **100%** compliance rate
- **High confidence** that implementation uses correct field names
- **Reduced risk** of AttributeError in production

This step is **critical** - do not skip or rush it.
