# Implement Flow Phase 2 Pattern Engine

## Goal

Implement Phase 2 of `FLOW-UPGRADE-DESIGN.md`: make stored task patterns drive lifecycle validation, next-action reporting, and block/unblock semantics.

## Benefits

This gives users enforceable task modes: Generic for old behavior, Fan-out for parent/child coordination, Pipeline for staged review, and Human-loop for auditable human decisions.

## Key Assumptions

- FlowStore remains the single persistence writer.
- Pattern modules stay pure and host-neutral.
- Phase 3 owns actual fan-out subagent dispatch.
- Unknown task patterns resolve to Generic.

## Scope

- Add `patterns/` runtime modules and template copies.
- Keep FlowStore as the single state writer.
- Refactor `task.py` lifecycle commands to use pattern validation and transition gates.
- Add `.cowork-flow/spec/patterns/` docs and template copies.
- Add behavior tests and final full-repo verification.

## Non-Goals

- Do not implement Phase 3 `subagent spawn-family` or `check-family`.
- Do not implement Dashboard.
- Do not add dependencies outside Python stdlib.
- Do not change host adapter transport.

## Child Tasks

- `06-12-flow-phase2-pattern-contracts`: base contracts and Generic behavior.
- `06-12-flow-phase2-concrete-patterns`: Fan-out, Pipeline, Human-loop, Registry.
- `06-12-flow-phase2-task-lifecycle-integration`: lifecycle gates in `task.py`.
- `06-12-flow-phase2-spec-template-verification`: specs, template sync, final gates.

## Acceptance Criteria

1. Generic, Fan-out, Pipeline, and Human-loop patterns have tested validation and transition behavior.
2. Invalid lifecycle transitions fail before FlowStore mutation.
3. `task next` stays read-only and returns useful pattern-specific guidance.
4. Human-loop unblock requires and records a human decision.
5. Root/template runtime and spec files are synchronized.
6. `python -m pytest tests/test_patterns.py tests/test_flow_script_paths.py -q`, `npm run test:all`, and `git diff --check` pass.

## References

- `FLOW-UPGRADE-DESIGN.md`
- `.cowork-flow/plans/2026-06-12-flow-phase2-pattern-engine.md`
- `.cowork-flow/changes/06-12-flow-phase2-pattern-engine/`
