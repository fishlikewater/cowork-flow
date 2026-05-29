# Subagent Dispatch Handshake

**Goal:** Add a lightweight dispatch envelope and ACK gate so spawned subagents can prove they received their own task before execution.

**Scope:** Fixed agent prompts, workflow docs, generic subagent context generation, and focused regression tests.

- [x] Add tests for dispatch envelope and ACK handling.
  - Verify: targeted Python tests fail before implementation and pass after.
- [x] Add dispatch fields to generic subagent context/brief.
  - Verify: `subagent init` emits `dispatchId`, `ackToken`, and a recoverable `contextFile`.
- [x] Update fixed agent definitions and workflow docs in root/template copies.
  - Verify: root and template contain the same protocol markers.
- [x] Run targeted tests and diff hygiene checks.
  - Verify: `unittest`, `doctor --subagent-safety`, and `git diff --check` pass.
- [x] Add role and generic-worker guardrails.
  - Verify: fixed agents reject role mismatches, `subagent init` emits `agentType` and `dispatchReliability`, and workflow documents generic `worker` as best-effort only.
- [x] Run a full-flow parallel fixed-agent smoke.
  - Strategy: parallel low-conflict slices under the same task, with separate file ownership and unique dispatch identifiers.
  - Slice A ownership: `.cowork-flow/tasks/05-29-subagent-dispatch-handshake/parallel-smoke/implement-a.md`.
  - Slice B ownership: `.cowork-flow/tasks/05-29-subagent-dispatch-handshake/parallel-smoke/implement-b.md`.
  - Verify: both built-in `cowork-implement` agents ACK their own `dispatch_id`, execute only after matching `EXECUTE`, write only their owned evidence file, and final integrated verification passes.
