# Flow Phase 2 Pattern Engine Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Implement the Phase 2 pattern engine from `FLOW-UPGRADE-DESIGN.md` so task lifecycle commands can enforce Generic, Fan-out, Pipeline, and Human-loop behavior.
**Architecture:** Keep `flow.store.FlowStore` as the SQLite access layer and make `patterns/` a pure decision layer. `task.py` builds a `TaskContext` from FlowStore data, resolves the task pattern, then applies validation and transition gates before mutating status or block state.
**Verification:** `python -m pytest tests/test_patterns.py tests/test_flow_script_paths.py -q`, root/template parity checks for touched runtime files, `npm run test:all`, `git diff --check`.

**Execution Strategy:** Serial mainline. The work shares `task.py`, FlowStore views, root/template copies, and lifecycle tests. The contract and concrete pattern modules may be implemented first as a low-conflict slice, but lifecycle integration and final verification must run after all pattern code lands.

## Task 1: Define Pattern Contracts And Generic Behavior

Files:
- Create `.cowork-flow/scripts/patterns/__init__.py`
- Create `.cowork-flow/scripts/patterns/base.py`
- Create `.cowork-flow/scripts/patterns/generic.py`
- Create template copies under `template/.cowork-flow/scripts/patterns/`
- Modify `.cowork-flow/scripts/flow/store.py`
- Modify `template/.cowork-flow/scripts/flow/store.py`
- Create or extend `tests/test_patterns.py`

Steps:
1. Add tests for `StepKind`, `Action`, `BlockView`, `TaskContext`, and Generic transitions.
2. Move or re-export the existing `TaskView` contract so FlowStore and patterns use one shared dataclass shape.
3. Implement `Pattern` base class with `validate()`, `next_action()`, `transition_allowed()`, and `can_transition()`.
4. Implement `Generic` with `planning -> in_progress -> review -> completed -> archived` plus `in_progress -> blocked -> in_progress`.
5. Sync root/template pattern files and FlowStore import changes.

Verification:
- `python -m pytest tests/test_patterns.py -q`
- Root/template hashes match for `scripts/patterns/*` and any touched FlowStore files.

## Task 2: Implement Concrete Patterns And Registry

Files:
- Create `.cowork-flow/scripts/patterns/fan_out.py`
- Create `.cowork-flow/scripts/patterns/pipeline.py`
- Create `.cowork-flow/scripts/patterns/human_loop.py`
- Create `.cowork-flow/scripts/patterns/registry.py`
- Create template copies under `template/.cowork-flow/scripts/patterns/`
- Extend `tests/test_patterns.py`

Steps:
1. Add Fan-out tests proving parent tasks require child tasks, children must be `generic`, and `next_action()` waits until all children are completed or archived.
2. Add Pipeline tests proving `stages` is required, `current_stage` drives completion eligibility, and `review -> completed` is blocked until all stages have passed.
3. Add Human-loop tests proving `decision_points` is required and unblock requires a decision before returning to `in_progress`.
4. Implement the three pattern classes against the tested behavior.
5. Implement `PatternRegistry` with explicit registration, `get()`, `resolve()`, and advisory `select()` behavior.

Verification:
- `python -m pytest tests/test_patterns.py -q`
- Registry selection tests cover children, `stages`, `decision_points`, and default Generic fallback.

## Task 3: Wire Pattern Engine Into Task Lifecycle

Files:
- Modify `.cowork-flow/scripts/task.py`
- Modify `template/.cowork-flow/scripts/task.py`
- Extend `tests/test_flow_script_paths.py`
- Extend `tests/test_patterns.py` only for pure pattern coverage gaps

Steps:
1. Add tests showing `task start/review/complete/block/unblock/next` consult the resolved pattern before state changes.
2. Add a private `_build_pattern_context(store, task_id)` helper that loads the task, children via `FlowStore.list_children()`, active block via `get_active_block()`, and relevant task metadata.
3. Route lifecycle commands through registry resolution and `can_transition()` before calling FlowStore mutators.
4. Make Fan-out reject parent review while any child remains non-completed and non-archived.
5. Make Pipeline advance `current_stage` through meta updates when a stage passes review, and allow final completion only after the last stage.
6. Make Human-loop require `task unblock --decision <text>`; non-Human-loop unblock keeps the existing `--force` requirement.
7. Make `task next` surface `Action.kind`, description, child list, and current pipeline stage without mutating state.
8. Sync template `task.py`.

Verification:
- `python -m pytest tests/test_flow_script_paths.py tests/test_patterns.py -q`
- Manual smoke commands in a temp repo for Generic, Fan-out, Pipeline, and Human-loop lifecycle paths.

## Task 4: Document Specs, Sync Template, And Run Final Gates

Files:
- Create `.cowork-flow/spec/patterns/index.md`
- Create `.cowork-flow/spec/patterns/fan-out.md`
- Create `.cowork-flow/spec/patterns/pipeline.md`
- Create `.cowork-flow/spec/patterns/human-loop.md`
- Create template copies under `template/.cowork-flow/spec/patterns/`
- Modify `.cowork-flow/spec/registry.json`
- Modify `template/.cowork-flow/spec/registry.json`
- Modify docs only when they claim old lifecycle behavior
- Extend tests that enforce shipped template content

Steps:
1. Add pattern specs that document statuses, metadata shape, valid transitions, and lifecycle command behavior.
2. Update `registry.json` so pattern specs are discoverable by contract digest tooling.
3. Sync root/template runtime and spec files.
4. Add tests for root/template parity of `patterns/` runtime and pattern spec files.
5. Run final integrated checks.

Verification:
- `python -m pytest tests/test_patterns.py tests/test_flow_script_paths.py tests/test_host_adapters.py -q`
- `npm run test:all`
- `git diff --check`

## Acceptance Mapping

- Phase 2.1 and 2.2 are covered by Task 1.
- Phase 2.3 and 2.4 are covered by Task 2.
- Phase 2.5 and 2.6 are covered by Task 3.
- Phase 2.7 and final template/spec gates are covered by Task 4.

## Risks And Guardrails

- Do not introduce a second task state store; all writes remain through `FlowStore`.
- Do not make `patterns/` read files, spawn agents, or mutate state; it only returns validation issues and next actions.
- Do not claim Fan-out can dispatch children in Phase 2; actual `spawn-family` and `check-family` are Phase 3.
- Keep root and template copies byte-aligned for every shipped runtime/spec file.
