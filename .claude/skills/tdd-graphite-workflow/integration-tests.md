# Integration Test Requirements

**Minimum Coverage**: At least 20% of tests must be integration tests (no mocks for code under test).

## Why Integration Tests Matter

- **Unit tests with mocks hide implementation bugs** (especially field name errors)
- **Integration tests call real code** and catch AttributeError, serialization issues, logic errors
- **Requirement**: At least 20% of tests must be integration tests

## Difference Between Unit and Integration Tests

### Unit Tests (with mocks)

```python
def test_save_state_calls_storage(mocker):
    """Unit: Verify save_state calls storage correctly"""
    mock_storage = mocker.patch('app.storage.StateStorage')
    service = MeetingService()
    service.save_state(state)

    # Verifies the call was made, but doesn't test actual serialization
    mock_storage.save.assert_called_once()
```

**Characteristics**:
- Mock external dependencies (APIs, DB, filesystem, time)
- Test caller behavior and control flow
- Verify correct parameters passed
- Fast execution
- ❌ **DON'T mock**: The code you're testing

### Integration Tests (without mocks)

```python
@pytest.mark.integration
def test_save_and_load_state_real_implementation(tmp_path):
    """Integration: Verify state serializes and loads correctly"""
    storage = StateStorage(state_dir=str(tmp_path))
    state = MeetingState(
        meeting_id="123",
        bot_id="bot1",
        updated_at=datetime.now()
    )

    # Real method calls - would fail if field names wrong!
    storage.save(state)
    loaded = storage.load("123")

    assert loaded.meeting_id == "123"
    assert loaded.updated_at is not None
    # Would raise AttributeError if we used wrong field name!
```

**Characteristics**:
- Call real implementation methods
- Test actual data transformations
- No mocks for code under test (only external dependencies)
- Catch field name errors, serialization bugs
- Slower but more comprehensive

## Integration Test Requirements

### 1. NO MOCKS FOR CODE UNDER TEST

- Mock ONLY external dependencies:
  - HTTP APIs (requests, httpx)
  - Databases (actual DB connections)
  - Filesystem (for reading external files, not temp files)
  - Time (datetime.now, time.sleep)
  - External services

- Call REAL implementation methods:
  - Your business logic
  - Your data transformations
  - Your serialization code
  - Your validation logic

### 2. MINIMUM COVERAGE

- **At least 20% of total tests must be integration tests**
- If creating 10 unit tests, create at least 3 integration tests
- Calculate: `(integration_tests / total_tests) * 100 >= 20%`

### 3. MARK WITH PYTEST DECORATOR

```python
@pytest.mark.integration
def test_scenario_name():
    """Integration: Description of what this tests"""
    # Test code here
```

This allows running integration tests separately:
```bash
pytest -m integration  # Run only integration tests
pytest -m "not integration"  # Run only unit tests
```

### 4. TEST SCENARIOS FOR INTEGRATION TESTS

Integration tests are **required** for:
- Data serialization/deserialization
- Field access and attribute errors
- Data transformation pipelines
- Business logic with real data
- Cross-module interactions
- API request/response handling (with real models)

Integration tests are **recommended** for:
- Complex algorithms
- State machines
- Workflow orchestrations
- Multi-step processes

### 5. USE SCHEMA REFERENCE

- Reference documented field names from schema discovery
- Verify those exact field names work in real code
- Test nested structure access
- Verify field types match expectations

## Integration Test Examples

### Example 1: Data Serialization

```python
@pytest.mark.integration
def test_meeting_state_serialization(tmp_path):
    """Integration: Verify MeetingState serializes with correct field names"""
    state = MeetingState(
        meeting_id="m1",
        bot_id="b1",
        updated_at=datetime.now(),
        entities_mentioned={'people': ['Alice'], 'projects': ['P1']},
        is_finalized=False
    )

    # Real serialization - catches field name errors
    json_data = state.to_dict()

    assert 'updated_at' in json_data  # NOT last_updated!
    assert json_data['entities_mentioned']['people'] == ['Alice']
    assert json_data['is_finalized'] is False  # NOT finalized!
```

### Example 2: Business Logic

```python
@pytest.mark.integration
def test_update_meeting_state_real_logic():
    """Integration: Test state update with real business logic"""
    state = MeetingState(meeting_id="m1", update_count=0)
    service = MeetingService()

    # Real method call - tests actual logic
    updated = service.update_state(state, body="New content")

    assert updated.update_count == 1
    assert updated.body == "New content"
    assert updated.updated_at > state.updated_at
```

### Example 3: Cross-Module Interaction

```python
@pytest.mark.integration
def test_meeting_workflow_end_to_end(tmp_path):
    """Integration: Test complete meeting workflow"""
    # Use real components, only mock external API
    storage = StateStorage(state_dir=str(tmp_path))
    service = MeetingService(storage=storage)

    # Create, update, finalize - real workflow
    meeting = service.create_meeting("bot1")
    service.add_comment(meeting.meeting_id, "Test comment")
    service.finalize_meeting(meeting.meeting_id)

    # Load and verify - tests serialization, field access, logic
    loaded = storage.load(meeting.meeting_id)
    assert loaded.is_finalized is True
    assert len(loaded.comments) == 1
```

## Test File Structure

Create separate file for integration tests:

```
tests/
├── issue_581_test_unit.py           # Unit tests
└── issue_581_test_integration.py    # Integration tests
```

or

```
tests/
├── issue_581_test_models.py         # Unit tests for models
├── issue_581_test_service.py        # Unit tests for service
└── issue_581_integration_test.py    # Integration tests
```

## Verification

After creating tests, verify coverage:

```bash
# Count total tests
pytest tests/issue_581_* --collect-only | grep "test session starts"

# Count integration tests
pytest tests/issue_581_* -m integration --collect-only

# Calculate percentage
# (integration / total) * 100 >= 20%
```

## Common Integration Test Patterns

### Pattern 1: Round-Trip Testing

Test data can be saved and loaded without corruption:

```python
@pytest.mark.integration
def test_state_round_trip(tmp_path):
    storage = StateStorage(str(tmp_path))
    original = create_complex_state()

    storage.save(original)
    loaded = storage.load(original.meeting_id)

    assert loaded == original
    # Verifies all fields serialize/deserialize correctly
```

### Pattern 2: Pipeline Testing

Test multi-step transformations:

```python
@pytest.mark.integration
def test_data_pipeline():
    raw_data = fetch_raw_data()
    cleaned = clean_data(raw_data)
    transformed = transform_data(cleaned)
    validated = validate_data(transformed)

    assert validated.is_valid
    assert all(item.has_required_fields() for item in validated.items)
```

### Pattern 3: State Machine Testing

Test state transitions:

```python
@pytest.mark.integration
def test_meeting_state_transitions():
    meeting = Meeting.create()
    assert meeting.state == MeetingState.CREATED

    meeting.start()
    assert meeting.state == MeetingState.ACTIVE

    meeting.finalize()
    assert meeting.state == MeetingState.FINALIZED
```

## What NOT to Do

### ❌ Mock Everything

```python
# This is NOT an integration test!
def test_with_all_mocks(mocker):
    mock_storage = mocker.patch('Storage')
    mock_service = mocker.patch('Service')
    mock_model = mocker.patch('Model')
    # ... testing nothing real
```

### ❌ Skip Integration Tests Entirely

```python
# 10 unit tests, 0 integration tests
# Coverage: 0% integration (FAILS requirement)
```

### ❌ Fake Integration Tests

```python
# Marked as integration but still mocking code under test
@pytest.mark.integration
def test_fake_integration(mocker):
    mock_service = mocker.patch('MyService')  # Should be real!
```

## Final Notes

- Integration tests are **slower** but catch **real bugs**
- Unit tests are **faster** but can give **false confidence**
- You need **BOTH** for comprehensive coverage
- 20% integration is the **minimum**, more is better
- Integration tests are especially critical for data models, serialization, and cross-module code
