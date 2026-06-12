# 06-12-flow-phase2-pattern-engine

## Goal

Implement Phase 2 of `FLOW-UPGRADE-DESIGN.md`: add a pure pattern engine for task lifecycle decisions and wire it into `task.py`.

## Benefits

- Users can choose an explicit collaboration mode per task instead of relying on one generic lifecycle.
- Parent/child Flow tasks gain enforceable Fan-out semantics before Phase 3 adds family dispatch.
- Human decision pauses become auditable through the existing block table.
- Pipeline work can model staged review without inventing another state store.

## Problem

Phase 1 created the SQLite FlowStore and made task lifecycle state reliable, but every task still behaves like the old generic workflow. The design now requires explicit collaboration patterns:

- Generic: old behavior plus blocked/unblocked support.
- Fan-out: one parent waits for multiple generic children.
- Pipeline: staged review and rework.
- Human-loop: blocked state carries human decision metadata.

Without Phase 2, `task create --pattern ...` stores metadata but lifecycle commands do not enforce it.

## Scope

- Add `patterns/` runtime modules for contracts, concrete patterns, and registry lookup.
- Reuse FlowStore data to build `TaskContext`.
- Gate `task.py` lifecycle commands through the resolved pattern.
- Add pattern specs and template copies.
- Add behavior tests for transitions, validation, `task next`, and block/unblock semantics.

## Key Assumptions

- FlowStore remains the only writer for task status, child links, audit, agent run, and block data.
- Pattern modules are deterministic pure logic and receive all needed state through `TaskContext`.
- Phase 2 may report Fan-out next actions, but actual multi-agent family dispatch belongs to Phase 3.
- Existing tasks with missing or unknown pattern values can safely behave as Generic.

## Non-Goals

- No Phase 3 `subagent spawn-family` or `check-family`.
- No Dashboard implementation.
- No new third-party dependencies.
- No change to the host adapter runtime protocol.

## Acceptance

- Generic, Fan-out, Pipeline, and Human-loop behavior is covered by tests.
- Invalid pattern transitions fail before FlowStore mutation.
- `task next` reports pattern-specific next action without changing state.
- Root/template runtime and spec files are synchronized.
- `npm run test:all` and `git diff --check` pass.
