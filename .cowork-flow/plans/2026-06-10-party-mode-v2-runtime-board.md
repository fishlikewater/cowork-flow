# Party Mode V2 Runtime Board Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Implement Party Mode V2 as a runtime-controlled, host-neutral, multi-agent board discussion mode without changing existing Party Mode V1.

**Architecture:** Add a Python runtime controller that owns board state, round transitions, schema validation, and host-neutral next actions. Children communicate through board API commands; the moderator monitors status and executes host adapter actions without forwarding or synthesizing opinions. Codex, Claude Code, and OpenCode consume the same runtime contract through their existing adapter assets.

**Verification:** targeted Python tests through `python -m unittest discover` unless pytest is available, existing package/unit runners where applicable, and `rtk git diff --check`.

## Execution Strategy

Serial execution. The runtime script, config getters, skill mirrors, host assets, and tests share contracts and file ownership. Parallel work would risk incompatible schema and template drift.

## Source Design

- `.cowork-flow/tasks/06-10-party-mode-v2-runtime-board-design/design.md`
- `.cowork-flow/changes/06-10-party-mode-v2-runtime-board/proposal.md`
- `.cowork-flow/changes/06-10-party-mode-v2-runtime-board/spec.md`
- `.cowork-flow/changes/06-10-party-mode-v2-runtime-board/design.md`

## Task 1: Runtime Foundation

Task: `.cowork-flow/tasks/06-10-party-mode-v2-runtime-foundation`

Files:

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `.cowork-flow/scripts/run.py`
- `template/.cowork-flow/scripts/run.py`
- `.cowork-flow/scripts/common/config.py`
- `template/.cowork-flow/scripts/common/config.py`
- `.cowork-flow/config.yaml`
- `template/.cowork-flow/config.yaml`
- `tests/test_party_mode_v2.py`

Steps:

1. Add config getters for `party_mode_v2.min_agents`, `max_agents`, `max_rounds`, `max_rebuttal_targets_per_agent`, `max_drift_warnings`, `fresh_context_per_round`, and `require_current_round_only`.
   - Verification: unit tests cover defaults, valid config values, invalid numeric fallback, and string boolean conversion.
2. Add `party_mode_v2.py` with `init`, `view`, `monitor`, and host-neutral `next_actions` generation.
   - Verification: tests assert `init` creates UTF-8 JSON state under `.cowork-flow/.runtime/party-mode-v2/<discussion_id>/`.
3. Implement current-round-only `view`.
   - Verification: tests create prior and current rounds, then assert child-visible output includes only the current round.
4. Register `party-v2` in root/template `run.py` or prove script-name invocation works consistently in tests.
   - Verification: command dispatch test exercises the selected entrypoint.
5. Keep root/template copies synchronized.
   - Verification: parity assertions in tests or explicit file comparison.

Expected result: Runtime can initialize a discussion, read config, expose current board state, and output host-neutral actions.

## Task 2: Debate Rules And Convergence

Task: `.cowork-flow/tasks/06-10-party-mode-v2-debate-rules-convergence`

Depends on: Task 1.

Files:

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `tests/test_party_mode_v2.py`

Steps:

1. Add `post` submission validation for required claim/evidence/risk/tradeoff/acceptance fields.
   - Verification: missing evidence or mismatched round/agent is rejected.
2. Add `respond` validation for `maintain`, `revise`, and `concede`.
   - Verification: `concede` without accepted evidence returns `shallow_concession`; `maintain` without counter evidence returns `unsupported_rebuttal`; `revise` without accepted/rejected parts returns `vague_revision`.
3. Enforce current-round target references.
   - Verification: response targeting a prior-round post returns `target_not_in_current_round`.
4. Add `advance` state transition logic.
   - Verification: publish cannot advance until all active agents post; respond cannot advance while required responses are missing.
5. Add `finalize` for converged and max-rounds-unconverged reports.
   - Verification: reaching max rounds emits pro/con evidence, changed positions, maintained positions, unresolved disagreements, and `stop_reason: max_rounds_unconverged`.

Expected result: Runtime enforces evidence-backed disagreement handling and produces deterministic final reports.

## Task 3: Host Assets And Actions

Task: `.cowork-flow/tasks/06-10-party-mode-v2-host-assets-actions`

Depends on: Task 1 and the action schema shape used by Task 2.

Files:

- `.cowork-flow/spec/party-mode-v2-actions.schema.json`
- `template/.cowork-flow/spec/party-mode-v2-actions.schema.json`
- `.cowork-flow/spec/party-mode-v2-board.md`
- `template/.cowork-flow/spec/party-mode-v2-board.md`
- `.agents/skills/party-mode-v2/SKILL.md`
- `template/.agents/skills/party-mode-v2/SKILL.md`
- `.claude/skills/party-mode-v2/SKILL.md`
- `template/.claude/skills/party-mode-v2/SKILL.md`
- `.opencode/commands/party-mode-v2.md`
- `template/.opencode/commands/party-mode-v2.md`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `.cowork-flow/spec/subagent-dispatch.md`
- `template/.cowork-flow/spec/subagent-dispatch.md`
- `tests/test_cowork_agents.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_host_adapters.py`
- `test/opencode-plugin.test.js`

Steps:

1. Define host-neutral action schema and board contract.
   - Verification: schema tests ensure actions do not contain Codex, Claude, or OpenCode primitive names.
2. Add thin `party-mode-v2` skill mirrors.
   - Verification: tests assert all root/template and `.agents`/`.claude` mirrors contain runtime-board entry rules and do not duplicate full runtime state machine.
3. Add OpenCode command assets and template copies.
   - Verification: OpenCode asset tests detect the command and confirm it references `party-v2` runtime commands.
4. Update workflow and subagent-dispatch docs with V2 advisory boundary.
   - Verification: workflow tests confirm host-neutral language and advisory-only limits.
5. Confirm adapters need no new capability.
   - Verification: host adapter tests assert Codex, Claude Code, and OpenCode expose existing dispatch/follow-up/wait/list/cancel capability or fallback.

Expected result: All host-facing assets expose Party Mode V2 without Codex-specific language in shared workflow docs.

## Task 4: Integration Verification

Task: `.cowork-flow/tasks/06-10-party-mode-v2-integration-verification`

Depends on: Tasks 1, 2, and 3.

Files:

- `tests/test_party_mode_v2.py`
- `tests/test_cowork_agents.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_host_adapters.py`
- `test/opencode-plugin.test.js`
- `README.md`
- `template/README`-related generated docs only if the repository already manages them through existing sync commands.

Steps:

1. Add end-to-end runtime simulation tests with at least three agents.
   - Verification: simulation covers init, publish, view, respond, advance, and finalize.
2. Add moderator-boundary tests.
   - Verification: monitor output contains status and next actions but not synthesized opinions.
3. Add host-neutral action tests across Codex, Claude Code, and OpenCode.
   - Verification: no shared docs mention `spawn_agent`, Claude Task details, or OpenCode task primitive outside adapter-specific assets.
4. Fix README drift for Party Mode V1 `max_rounds` if still present.
   - Verification: README aligns with current V1 skill default and distinguishes V1 from V2.
5. Run full targeted verification.
   - Verification: `rtk pytest tests/test_party_mode_v2.py tests/test_cowork_agents.py tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py`, relevant Node tests, and `rtk git diff --check`.

Expected result: V2 is covered by behavior tests, mirror tests, and host-neutral contract tests; V1 remains unchanged.

## Final Integrated Check

After all tasks complete:

1. Run targeted Python tests.
2. Run relevant Node/OpenCode asset tests.
3. Run broader project test suite if targeted tests pass.
4. Run `rtk git diff --check`.
5. Inspect `git status --short` and stage only intended files.
6. Archive completed tasks and the `06-10-party-mode-v2-runtime-board` change.

## Risks

- Python cannot directly call host primitives today; the first implementation must not claim full automation. Runtime outputs next actions, host executes them.
- Fresh context per round is the strict current-round-only default, but it increases child count and latency.
- Same-user filesystem access is not a security sandbox. Runtime can enforce workflow protocol but cannot prevent a malicious child from searching `.runtime` files.
- OpenCode follow-up support is a shim; the implementation must expose manual next action fallback when follow-up is not stable.
