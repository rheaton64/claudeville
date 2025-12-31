# SDK Token Tracking Behavior

Detailed findings from smoke tests investigating how the Claude Agent SDK tracks and reports token usage. These findings are critical for implementing correct token tracking and compaction threshold logic.

**Date:** December 2024
**Tested with:** `claude-haiku-4-5-20251001` via `claude-agent-sdk`

---

## Executive Summary

The SDK's `ResultMessage.usage` contains **two different types of token metrics**:

1. **Per-turn metrics** (`input_tokens`, `output_tokens`) - Fresh values each turn, for billing
2. **Cumulative metrics** (`cache_read_input_tokens`) - Running total of context window, for compaction

**Critical finding:** After session resume (simulating crash/restart), the cumulative context tracking **continues from where it left off**. The SDK maintains this state server-side.

---

## Test Methodology

### Test 1: Multiple Turns in Same Session

Used `ClaudeSDKClient` with multiple `query()` calls on the same client instance.

```python
async with ClaudeSDKClient(options=ClaudeAgentOptions(...)) as client:
    await client.query("Say 'turn 1'")  # Turn 1
    # ... get usage ...
    await client.query("Say 'turn 2'")  # Turn 2
    # ... get usage ...
    await client.query("Say 'turn 3'")  # Turn 3
    # ... get usage ...
```

### Test 2: Session Resume (Simulating Crash)

1. First process: Create session, run 3 turns, capture `session_id`
2. Second process: Resume with `session_id`, run 3 more turns
3. Compare token metrics between processes

---

## Detailed Findings

### Usage Dict Structure

Each `ResultMessage.usage` contains:

```python
{
    'input_tokens': 3,                    # Per-turn: new input tokens
    'output_tokens': 6,                   # Per-turn: new output tokens
    'cache_read_input_tokens': 15132,     # Cumulative: context from cache
    'cache_creation_input_tokens': 20,    # Per-turn: new cache entries
    'server_tool_use': {...},             # Tool usage stats
    'service_tier': 'standard',
    'cache_creation': {
        'ephemeral_1h_input_tokens': 0,
        'ephemeral_5m_input_tokens': 329
    }
}
```

### Per-Turn Metrics (NOT Cumulative)

These reset each turn and represent the marginal tokens for that specific turn:

| Metric | Turn 1 | Turn 2 | Turn 3 | Behavior |
|--------|--------|--------|--------|----------|
| `input_tokens` | 3 | 3 | 3 | **Per-turn** |
| `output_tokens` | 6 | 6 | 6 | **Per-turn** |
| `cache_creation_input_tokens` | 331 | 20 | 20 | **Per-turn** |

**Use case:** Billing calculations, per-turn usage statistics.

### Cumulative Metrics (Context Window)

These grow with each turn and represent the total context being processed:

| Metric | Turn 1 | Turn 2 | Turn 3 | Behavior |
|--------|--------|--------|--------|----------|
| `cache_read_input_tokens` | 14781 | 15112 | 15132 | **Cumulative** |
| context_size (cache_read + input) | 14784 | 15115 | 15135 | **Cumulative** |

**Use case:** Compaction threshold decisions (100K/150K limits).

### Session Resume Behavior

**Critical test:** What happens after a "crash" (new process resuming old session)?

**Before restart (Process 1):**
```
Turn 1: context_size = 14784
Turn 2: context_size = 15115  (+331)
Turn 3: context_size = 15135  (+20)
```

**After restart (Process 2, resumed with session_id):**
```
Turn 4: context_size = 15155  (+20, continues from 15135!)
Turn 5: context_size = 15175  (+20)
Turn 6: context_size = 15195  (+20)
```

**Finding:** The `cache_read_input_tokens` (context window) **continues accumulating** after resume. The SDK maintains this state server-side via the session.

---

## Implications for ClaudeVille

### 1. Compaction Threshold Tracking

**Good news:** We don't need to persist context window size for compaction decisions.

The SDK tracks `cache_read_input_tokens` server-side and continues after resume. As long as we use the same `session_id`, the compaction threshold logic will work correctly.

**Recommendation:** Use `cache_read_input_tokens + input_tokens` as the context window size for compaction threshold checks.

### 2. Token Usage Tracking (Billing/Stats)

**Key insight:** `input_tokens` and `output_tokens` are per-turn, not cumulative.

**Recommendation:**
- ADD the per-turn values to cumulative billing totals
- No delta computation needed

```python
# Correct approach - add per-turn values to billing totals
total_input_tokens += usage['input_tokens']
total_output_tokens += usage['output_tokens']
```

### 3. Cache Token Tracking

Cache tokens are interesting for cost analysis:
- `cache_creation_input_tokens`: Tokens added to cache this turn (higher cost)
- `cache_read_input_tokens`: Tokens read from cache (lower cost, ~90% discount)

**Recommendation:** Track these separately for accurate cost estimation.

### 4. Restart Recovery

After restart, when resuming a session:
- **Context window (`session_tokens`):** Restored automatically on first turn when SDK reports `cache_read_input_tokens`
- **Billing totals:** Restored from persisted `TokenUsage` in `AgentSnapshot`

The SDK tracks context window size server-side via session, so the first turn after restart will report the correct `cache_read_input_tokens` value.

---

## Code Implications

### Original Assumption (WRONG)

We assumed `ResultMessage.usage` values were cumulative within a session:

```python
# WRONG - SDK doesn't report cumulative input/output
cumulative_total = usage['input_tokens'] + usage['output_tokens']
delta = cumulative_total - previous_cumulative  # This doesn't work!
```

### Correct Approach

Context window size comes directly from the SDK each turn:

```python
# CORRECT - context window is set directly, not accumulated
context_window_size = usage['cache_read_input_tokens'] + usage['input_tokens']
session_tokens = context_window_size  # SET, not add

# Billing totals are accumulated from per-turn values
total_input_tokens += usage['input_tokens']
total_output_tokens += usage['output_tokens']
```

### Compaction Threshold

Use the cumulative cache metric:

```python
# For compaction threshold decisions
context_window_size = usage['cache_read_input_tokens'] + usage['input_tokens']

if context_window_size >= CRITICAL_THRESHOLD:  # 150K
    trigger_compaction(critical=True)
elif context_window_size >= PRE_SLEEP_THRESHOLD:  # 100K
    trigger_compaction(critical=False)
```

---

## Test Scripts

The smoke tests are available at:
- `tests/smoke_test_sdk_tokens.py` - General token tracking behavior
- `tests/smoke_test_crash_resume.py` - Session resume behavior

Run them with:
```bash
# General tests
uv run python tests/smoke_test_sdk_tokens.py

# Crash/resume simulation
uv run python tests/smoke_test_crash_resume.py              # First run
uv run python tests/smoke_test_crash_resume.py <session_id>  # Resume
```

---

## Summary Table

| Metric | Type | Use Case | Persists Across Resume? |
|--------|------|----------|------------------------|
| `input_tokens` | Per-turn | Billing, usage stats | N/A (add to our tracking) |
| `output_tokens` | Per-turn | Billing, usage stats | N/A (add to our tracking) |
| `cache_read_input_tokens` | Cumulative | Context window size, compaction | Yes (SDK handles) |
| `cache_creation_input_tokens` | Per-turn | Cost tracking (cache writes) | N/A (add to our tracking) |
| `total_cost_usd` | Cumulative | Cost tracking | Yes (SDK handles) |

---

## References

- [SDK Cost Tracking Docs](https://platform.claude.com/docs/en/agent-sdk/cost-tracking)
- Local docs: `docs/claude-agent-sdk-python.md`
- Local docs: `docs/claude-agent-sdk-sessions.md`
