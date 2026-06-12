# Implement Concrete Phase 2 Patterns

## Goal

Implement Fan-out, Pipeline, Human-loop, and PatternRegistry behavior.

## Scope

- Create root/template `patterns/fan_out.py`.
- Create root/template `patterns/pipeline.py`.
- Create root/template `patterns/human_loop.py`.
- Create root/template `patterns/registry.py`.
- Extend pattern tests for validation, next actions, registry lookup, and advisory selection.

## Non-Goals

- Do not integrate `task.py` lifecycle commands in this task.
- Do not dispatch child agents; Fan-out dispatch is Phase 3.
- Do not write Dashboard behavior.

## Acceptance Criteria

1. Fan-out requires generic children and reports waiting children until all are done.
2. Pipeline requires valid `stages` and only completes after all stages pass.
3. Human-loop requires decision points and models decision-required blocking.
4. Registry resolves unknown patterns to Generic and selects advisory patterns from task shape.

## Verification

```powershell
python -m pytest tests/test_patterns.py -q
```
