# Party Mode V2 Runtime Hardening Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Repair Party Mode V2 runtime correctness, auditability, host lifecycle evidence, and child prompt usability.
**Architecture:** Keep the Python runtime as source of truth and keep host primitives outside the runtime. Add strict ids, transactional state writes, durable action/audit trails, stable state transitions, and schemas that can validate real artifacts. Mirror every root runtime/spec/asset change into `template/`.
**Verification:** Add failing behavior tests first, then implement until `rtk python -m unittest tests.test_party_mode_v2 tests.test_host_adapters tests.test_cowork_agents tests.test_workflow_parallel_sessions` and `rtk git diff --check` pass.

## Execution Strategy

Serial work. The same files define state shape, command behavior, schemas, host actions, and tests. Parallel slices would conflict on `.cowork-flow/scripts/party_mode_v2.py`, template mirrors, and Party Mode V2 specs.

## 1. Baseline Regression Tests

Files:

- `tests/test_party_mode_v2.py`
- `tests/test_host_adapters.py`

Steps:

1. Add failing tests for invalid `discussion_id` and `agent_id` path escape / unsafe prompt command text.
2. Add failing tests for omitted `round`, self-target response, duplicate target response, and target count above `max_rebuttal_targets_per_agent`.
3. Add failing tests proving terminal `advance` output is stable and `finalize` refuses incomplete discussions.
4. Add failing tests for `converged` final report with no current unresolved disagreements and preserved historical disagreements under an explicit historical key.
5. Add failing tests for action schema required fields per action type.

Verification:

```powershell
rtk python -m unittest tests.test_party_mode_v2 tests.test_host_adapters
```

Expected result before implementation: new tests fail for the specific missing behaviors, not import errors or fixture mistakes.

## 2. Runtime Id Safety And Transactional State

Files:

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`

Steps:

1. Add safe id validators for `discussion_id` and `agent_id` with a documented pattern.
2. Resolve runtime paths and assert they remain under `.cowork-flow/.runtime/party-mode-v2`.
3. Replace direct state overwrite with a small state write helper that uses an inter-process lock and atomic replace.
4. Ensure id generation for posts/responses happens under the same lock as append/write.

Verification:

```powershell
rtk python -m unittest tests.test_party_mode_v2
```

Expected result: unsafe ids are rejected; simulated close-succession writes preserve all posts/responses and unique ids.

## 3. Board Submission Rules

Files:

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `.cowork-flow/config.yaml`
- `template/.cowork-flow/config.yaml`

Steps:

1. Require explicit `round` when `require_current_round_only=true`.
2. Reject self-target responses.
3. Reject duplicate response by the same agent to the same target in the same round.
4. Enforce `max_rebuttal_targets_per_agent`.
5. Preserve decision-specific payload evidence in stored responses.
6. Validate booleans and confidence enum values explicitly.

Verification:

```powershell
rtk python -m unittest tests.test_party_mode_v2
```

Expected result: invalid submissions fail before mutating board; valid submissions retain audit-ready evidence fields.

## 4. Action And Agent Lifecycle Evidence

Files:

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `.cowork-flow/spec/party-mode-v2-actions.schema.json`
- `template/.cowork-flow/spec/party-mode-v2-actions.schema.json`
- `.cowork-flow/adapters/*/adapter.yaml`
- `template/.cowork-flow/adapters/*/adapter.yaml`

Steps:

1. Add durable `action_history.jsonl` or append action-issued/action-result events into `audit.jsonl`.
2. Add runtime commands or payload files for recording host action results and binding `host_child_id`.
3. Update `agents.json` status through pending, active, waiting, closed, closed_off_topic, or failed.
4. When `fresh_context_per_round=true`, emit close actions for stale round children before new dispatch actions.
5. Tighten action schema with required fields for `dispatch_child`, `send_control_message`, `wait_children`, `close_child`, and `report_to_user`.

Verification:

```powershell
rtk python -m unittest tests.test_party_mode_v2 tests.test_host_adapters
```

Expected result: lifecycle evidence remains after final `actions.json` is empty; action schema rejects incomplete actions.

## 5. View, Prompt, And Audit Semantics

Files:

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `.agents/skills/party-mode-v2/SKILL.md`
- `template/.agents/skills/party-mode-v2/SKILL.md`
- `.claude/skills/party-mode-v2/SKILL.md`
- `template/.claude/skills/party-mode-v2/SKILL.md`
- `.opencode/commands/party-mode-v2.md`
- `template/.opencode/commands/party-mode-v2.md`

Steps:

1. Make `view` a pure read operation or write per-agent view snapshots instead of overwriting shared `public_round.json`.
2. Add `empty_reason` and `expected_next_action` to child-visible views.
3. Generate different prompt text for publish and respond phases.
4. Include `post --file` / `respond --file` examples and minimal JSON payload schema in prompts.
5. Append audit events for view, advance, finalize, action-issued, action-result, warning, and close events.

Verification:

```powershell
rtk python -m unittest tests.test_party_mode_v2 tests.test_cowork_agents
```

Expected result: generated prompt files differ materially by phase; view/audit artifacts can explain empty current panels and replay a run.

## 6. Finalization And Report Contract

Files:

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `.cowork-flow/spec/party-mode-v2-board.md`
- `template/.cowork-flow/spec/party-mode-v2-board.md`

Steps:

1. Require closed state or explicit manual termination before `finalize`.
2. Make `advance` return a stable envelope for terminal and non-terminal transitions.
3. Split final report disagreement fields into current unresolved, historical disagreements, and resolved-by-later-round evidence.
4. Ensure finalization clears or archives outstanding actions and sets agent status consistently.
5. Prevent host-forbidden filtering from scanning user-controlled discussion content after state mutation.

Verification:

```powershell
rtk python -m unittest tests.test_party_mode_v2
```

Expected result: reports cannot contradict termination reason; callers can handle terminal advance without schema guessing.

## 7. Parity, Documentation, And Integrated Verification

Files:

- `tests/test_party_mode_v2.py`
- `tests/test_host_adapters.py`
- `tests/test_cowork_agents.py`
- `tests/test_workflow_parallel_sessions.py`
- Root and `template/` Party Mode V2 runtime/spec/asset files.

Steps:

1. Extend parity tests to include board spec, action schema, config, adapter yaml, skills, and commands.
2. Update README/workflow/spec wording only where runtime behavior changed.
3. Run full targeted verification.
4. Run a manual smoke discussion in a temporary runtime directory and inspect `board.json`, `agents.json`, `audit.jsonl`, `actions.json`, public views, prompts, and final report.

Verification:

```powershell
rtk python -m unittest tests.test_party_mode_v2 tests.test_host_adapters tests.test_cowork_agents tests.test_workflow_parallel_sessions
rtk git diff --check
.\.cowork-flow\run.cmd task validate .cowork-flow\tasks\06-10-party-mode-v2-runtime-hardening
```

Expected result: tests pass, no whitespace errors, and task validation succeeds.

## Risks

- Locking implementation must stay portable on Windows without introducing a dependency that breaks host environments.
- Tightening schema can invalidate old `.runtime/party-mode-v2` snapshots. Treat runtime state as ephemeral unless a migration need is found.
- Host lifecycle evidence needs a clear boundary: runtime records host results, but still must not call host primitives directly.
