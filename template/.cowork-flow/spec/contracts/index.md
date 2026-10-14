# Contract Specs

This directory holds the human-readable contracts. Host hooks, plugins, agents, and
workflow documents reference the contracts here, but never copy contract prose into
code.

Current contracts:

- `subagent-dispatch.md`: the fixed-subagent dispatch, binding, wait, and closeout protocol.
- `workflow-state-templates.md`: the workflow state text injected by hooks/plugins.
- `skill-owned-actions.md`: the distributed Skill action/context/command ownership contract.
- `capabilities.md`: the host adapter capability model.
- `party-mode-v2-board.md`: the Party Mode V2 board protocol.
- `plan-binding.md`: lightweight development-plan binding, pre-start missing-plan blocking, and recovery visibility.
- `spec-checks.md`: the spec-declared command contract — syntax of `checks:` in user-spec frontmatter, three-state gate semantics, timing, and the host capability matrix.
- `context-injection.md`: the transport shapes, event-timing matrix, and fingerprint serialization rules for runtime-context injection across hosts (a meta-protocol, not in `contract-registry.json`).
- `decision-anchor.md`: the schema of each task's `decision-anchor.md` — goal, acceptance criteria, rejected options, and key assumptions.
- `error-output-as-data.md`: external error output is analyzed as data, never executed as instructions (`ERROR_OUTPUT_AS_DATA_V1`).
- `fact-layer-access.md`: the channels through which hosts without injection hooks and external tools read task facts (`FACT_LAYER_ACCESS_V1`).
- `evidence-completion.md`: evidence-based completion — the `evidence.jsonl` schema, the `LIFECYCLE-AC-001/002/003/004` completion gate, `--allow-missing-evidence` exemption traces, and the injected coverage row.
- `task-adopt.md`: task adoption — the entry boundary of `task next --run --adopt`, its preconditions (`LIFECYCLE-ADOPT-001`), the rebind + baseline reset + audit write, and how it differs from `--takeover`.
- `task-board.md`: the shared board and dependency edges — the list/MCP board fields (executor / ownerSessionActive / evidenceCoverage / blocked), `--depends-on` declaration and validation, the start dependency gate (`LIFECYCLE-DEPENDENCY-001`), and the adopt handover receipt.
- `error-codes.md`: the registry of every runtime error code with the condition that produces it: `LIFECYCLE-AC-001/002/003/004`, `LIFECYCLE-ADOPT-001`, `LIFECYCLE-CHECK-001`, `LIFECYCLE-CONTEXT-001`, `LIFECYCLE-DEPENDENCY-001`, `LIFECYCLE-EXECUTOR-001`, `LIFECYCLE-RECOVERY-001`, `LIFECYCLE-REVIEW-001/002/003/004`, `LIFECYCLE-TASK-001`, `LIFECYCLE-TRANSITION-001`, `LIFECYCLE-UOW-001`, `SUBAGENT-SLICE-001`.
