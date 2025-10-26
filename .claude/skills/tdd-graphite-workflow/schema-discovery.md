# Schema Discovery Methodology

**Critical**: Field names are NOT guessable - must read actual model definitions.

## Why This Matters

Field name assumptions cause `AttributeError` exceptions in production that are only caught at runtime.

**Common errors**:
- Using `.last_updated` instead of `.updated_at`
- Using `.participant_entities` instead of `.entities_mentioned['people']`
- Using `.finalized` instead of `.is_finalized`

**Impact**: These errors cause runtime failures that integration tests catch, but ONLY if we know the correct names upfront to write the tests properly.

**Solution**: Mandatory schema discovery step that documents ALL field names from actual model definitions before any implementation begins.

## Discovery Process

### 1. Identify Models to Be Used/Modified

- Scan issue description for model mentions
- Check existing code that will be modified
- Use grep to find model imports:
  ```bash
  grep -r "from.*models" --include="*.py"
  ```
- List all models that will be touched by this implementation

### 2. Read Each Model File

- For each model identified, read the COMPLETE model definition file
- Common locations: `app/models/`, `models/`, `{app_name}/models/`
- Read entire file to see all fields, not just a few
- Don't assume field names based on other models

### 3. Document ALL Field Names Exactly

Create a schema reference list with:
- Model name (e.g., `MeetingState`)
- File path (e.g., `app/models/meeting/state.py`)
- ALL field names exactly as defined
- Field types (str, int, dict, list, etc.)
- Any nested structures (e.g., `entities_mentioned` is a dict with 'people', 'projects' keys)

**Copy field names character-for-character, do NOT paraphrase**

### 4. Document Common Errors to Avoid

For each model, list field names that might be assumed incorrectly.

Example: If model has `updated_at`, note "NOT last_updated, NOT modified_at"

## Schema Reference Output Format

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

## Next Steps After Discovery

1. Pass this schema reference to `tdd-test-writer` agent
2. Pass this schema reference to `tdd-solution-coder` agent
3. Use for schema compliance check after implementation
4. Reference during code review

## Critical Rules

- **NEVER** guess or assume field names
- **ALWAYS** read the actual model definition file
- Document **EVERY** field that will be used
- Include nested structure details
- Copy names exactly, character-for-character
- When in doubt, read the file again

## Common Pitfalls to Avoid

### Timestamp Fields
- ❌ `.last_updated`, `.modified_at`, `.changed_at`
- ✅ `.updated_at` (or whatever schema defines)

### Boolean Fields
- ❌ `.finalized`, `.completed`, `.active`
- ✅ `.is_finalized`, `.is_completed`, `.is_active` (or whatever schema defines)

### Collection Fields
- ❌ `.participant_entities`, `.project_entities`
- ✅ `.entities_mentioned['people']`, `.entities_mentioned['projects']`

### Plural vs Singular
- ❌ `.comment`, `.entity`
- ✅ `.comments`, `.entities` (check schema for correct form)

## Examples from Real Bugs

**Bug**: Assumed `meeting.participants` existed
**Reality**: Field was `meeting.entities_mentioned['people']`
**Result**: AttributeError in production

**Bug**: Used `state.last_modified`
**Reality**: Field was `state.updated_at`
**Result**: AttributeError in serialization

**Bug**: Accessed `item.is_complete`
**Reality**: Field was `item.completed_at` (datetime, not bool)
**Result**: Logic error and AttributeError

These bugs were preventable with schema discovery.
