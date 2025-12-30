# Integration Tests

Progressive integration tests for engine, from simple components to full simulation.

## Philosophy

- **Progressive complexity**: Start simple (single components), build up to full simulation
- **API-key gated**: Tests with real Haiku skip without `ANTHROPIC_API_KEY`
- **Deterministic first**: Use mock LLM provider for reliable CI tests
- **Real LLM last**: Full Haiku tests for acceptance/behavior validation
- **Generic test agents**: Use Alice/Bob/Carol (not Ember/Sage/River)
- **Soft assertions for behavior**: LLM-as-judge for emergent behavior validation

## Test Levels

| Level | Focus | LLM | File |
|-------|-------|-----|------|
| 1 | Interpreter only | Real Haiku | `test_interpreter_haiku.py` |
| 1 | Event store recovery | None | `test_event_store.py` |
| 2 | Pipeline + effects | Mock | `test_pipeline_mock.py` |
| 3 | Conversation flows | Mock | `test_conversation_flow.py` (TODO) |
| 4 | Multi-tick sequences | Mock | `test_multi_tick_mock.py` (TODO) |
| 5 | Single agent behavior | Real Haiku | `test_single_agent_haiku.py` (TODO) |
| 6 | Two-agent conversation | Real Haiku | `test_two_agent_haiku.py` (TODO) |
| 7 | Full village simulation | Real Haiku | `test_full_simulation_haiku.py` (TODO) |

## Running Tests

```bash
# All integration tests (requires ANTHROPIC_API_KEY for Haiku tests)
uv run pytest tests/integration/ -v

# Skip Haiku tests (no API key needed)
uv run pytest tests/integration/ -v -m "not haiku"

# Only Haiku interpreter tests
uv run pytest tests/integration/test_interpreter_haiku.py -v

# Event store tests (fast, no API calls)
uv run pytest tests/integration/test_event_store.py -v

# Pipeline tests (uses mock LLM)
uv run pytest tests/integration/test_pipeline_mock.py -v

# Skip slow tests
uv run pytest tests/integration/ -v -m "not slow"

# Skip expensive full simulation tests
uv run pytest tests/integration/ -v -m "not expensive"
```

## Running Tests in Parallel

Tests can be run in parallel using pytest-xdist for faster execution.
Each test uses isolated temp directories, so there are no file conflicts.

```bash
# Run all tests with 4 parallel workers
uv run pytest tests/integration/ -v -n 4

# Run mock tests in parallel (fast, no API rate limit concerns)
uv run pytest tests/integration/ -v -m "not haiku" -n auto

# Run Haiku tests in parallel (adjust -n based on your rate limits)
uv run pytest tests/integration/ -v -m "haiku" -n 4

# Run all Haiku tests with higher parallelism (if you have good rate limits)
uv run pytest tests/integration/ -v -m "haiku" -n 8
```

**Notes on parallelization:**
- Mock tests (`not haiku`) can use `-n auto` for max parallelism
- Haiku tests: use `-n 2` for low rate limits, `-n 4-8` for higher limits (4k+ RPM)
- Each test gets isolated `tmp_path` - no file conflicts
- Output is collected and shown at end when running parallel
- With 4k RPM / 2M input TPM, `-n 8` works well for Haiku tests

## Directory Structure

```
tests/integration/
├── __init__.py
├── conftest.py              # Fixtures and markers
├── CLAUDE.md                # This file
├── fixtures/
│   ├── __init__.py          # Exports all fixtures
│   ├── mock_provider.py     # MockLLMProvider for deterministic tests
│   ├── test_village.py      # Test village setup (Alice, Bob, Carol)
│   └── sample_narratives.py # Realistic narratives for interpreter tests
├── test_interpreter_haiku.py  # Level 1: Interpreter with real Haiku
├── test_event_store.py        # Level 1: Event sourcing recovery
└── test_pipeline_mock.py      # Level 2: Pipeline with mock LLM
```

## Key Fixtures

### `mock_provider`
Deterministic LLM provider that returns pre-configured narratives.

```python
mock_provider.set_narrative("Alice", "I walk to the garden.")
mock_provider.set_tool_call("Bob", "invite_to_conversation", {"invitee": "Alice"})
```

### `haiku_interpreter`
Real Claude Haiku interpreter for testing narrative extraction.

```python
result = await haiku_interpreter.interpret("I walk to the garden.")
assert result.movement is not None
```

### `test_engine`
VillageEngine with mock LLM, initialized with test village.

```python
result = await test_engine.tick_once()
assert test_engine.tick == 1
```

### `haiku_engine`
VillageEngine with real Haiku for behavior tests.

### `llm_judge`
LLM-as-judge for evaluating emergent behavior in tests.

```python
judgment = llm_judge(
    "Is this narrative coherent?",
    f"Narrative: {narrative}"
)
if not judgment.passed:
    pytest.skip(f"LLM judge: {judgment.reasoning}")
```

## Test Village Setup

The test village uses generic agents instead of the actual village characters:

| Agent | Location | Personality |
|-------|----------|-------------|
| Alice | workshop | Curious, creative artist |
| Bob | library | Thoughtful librarian |
| Carol | garden | Energetic gardener |

Locations form a connected graph:
```
workshop ↔ library ↔ garden
    ↖________↗
```

## Adding New Tests

### Level 1-2 (Component/Integration)
1. Create test file in `tests/integration/`
2. Use `mock_provider` for deterministic tests
3. Use `haiku_interpreter` for real Haiku interpreter tests
4. Mark haiku tests with `@pytest.mark.haiku` and `requires_api_key`

### Level 5+ (Behavior/Simulation)
1. Use `haiku_engine` fixture
2. Mark tests with `@pytest.mark.slow` and `@pytest.mark.expensive`
3. Use `llm_judge` for soft assertions on emergent behavior
4. Log outcomes for analysis rather than hard assertions

## Cost Estimation

| Test Type | Haiku Calls | Est. Cost |
|-----------|-------------|-----------|
| Interpreter test | 1-3 | ~$0.001 |
| Single agent (5 ticks) | 5-10 | ~$0.005 |
| Two agent (10 ticks) | 20-30 | ~$0.02 |
| Full sim (20 ticks) | 60-100 | ~$0.10 |

## Markers

- `@pytest.mark.haiku` - Uses real Claude Haiku API
- `@pytest.mark.slow` - Takes > 10 seconds
- `@pytest.mark.expensive` - Significant API cost

## Sample Narratives

`fixtures/sample_narratives.py` provides realistic narratives for testing:

- Movement: `MOVEMENT_TO_GARDEN`, `MOVEMENT_TO_LIBRARY`, etc.
- Mood: `PEACEFUL_MOOD`, `JOYFUL_MOOD`, etc.
- Actions: `SINGLE_ACTION`, `MULTIPLE_ACTIONS`, etc.
- Sleep: `GOING_TO_SLEEP`, `JUST_RESTING`, etc.
- Conversation: `INVITE_BOB`, `ADDRESS_CAROL`, etc.
- Edge cases: `EMPTY_NARRATIVE`, `VERY_SHORT`, `VERY_LONG`

Access via `SAMPLE_NARRATIVES` dict:
```python
narrative = SAMPLE_NARRATIVES["movement_to_garden"]
```
