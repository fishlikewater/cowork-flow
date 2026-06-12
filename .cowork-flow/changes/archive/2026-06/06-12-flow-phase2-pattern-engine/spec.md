# Phase 2 Pattern Engine Spec

## Required Behavior

1. `task.py` lifecycle commands must resolve the task pattern before mutating FlowStore state.
2. `patterns/` modules must be pure logic: no filesystem writes, no SQLite writes, no host adapter calls.
3. Unknown or empty pattern values must resolve to Generic.
4. Pattern validation errors must produce non-zero CLI exits for lifecycle commands that would mutate state.
5. `task next` must stay read-only and may report a pattern-specific `Action`.
6. Root and template runtime/spec copies must remain synchronized.

## Pattern Metadata

### Generic

No required metadata.

### Fan-out

No required metadata. The parent must have at least one child and each child must use `pattern='generic'`.

### Pipeline

Required metadata:

```json
{
  "stages": [
    {"name": "implement", "agent_type": "cowork-implement"},
    {"name": "check", "agent_type": "cowork-check"}
  ],
  "current_stage": 0
}
```

### Human-loop

Required metadata:

```json
{
  "decision_points": [
    {"question": "Choose A or B before continuing"}
  ],
  "current_decision": 0
}
```

## Verification Contract

The Phase 2 implementation is acceptable only when the following commands pass:

```powershell
python -m pytest tests/test_patterns.py tests/test_flow_script_paths.py -q
npm run test:all
git diff --check
```
