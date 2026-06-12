# Wire Pattern Engine Into Task Lifecycle

## Goal

Make `task.py` lifecycle commands enforce resolved pattern behavior before mutating FlowStore.

## Scope

- Add a `TaskContext` builder in root/template `task.py`.
- Route `start`, `review`, `complete`, `block`, `unblock`, and `next` through `PatternRegistry`.
- Preserve Phase 1 reliability guarantees: missing DB rows fail loudly and archive consistency is unchanged.
- Add lifecycle regression tests in `tests/test_flow_script_paths.py`.

## Non-Goals

- Do not change FlowStore transaction semantics unless lifecycle integration exposes a missing primitive.
- Do not implement Phase 3 family dispatch.
- Do not change lifecycle hook environment contracts.

## Acceptance Criteria

1. Invalid pattern transitions return non-zero and leave DB state unchanged.
2. Fan-out parent review is blocked while a child remains unfinished.
3. Pipeline stage progress updates meta deterministically.
4. Human-loop `unblock` requires `--decision`; non-Human-loop unblock still requires `--force`.
5. `task next` reports pattern actions without mutating DB state.

## Verification

```powershell
python -m pytest tests/test_flow_script_paths.py tests/test_patterns.py -q
```
