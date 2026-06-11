# Party Mode V2 Runtime Hardening PRD

## Goal And User Value

Harden Party Mode V2 so a real multi-agent board run is safe to execute, auditable after the fact, and clear enough for child agents to use without moderator forwarding.

User value: when Party Mode V2 is used for an important technical decision, the user can trust that child agents really interacted through the board, that the final report does not hide stale disagreements, and that any later audit can replay what happened from runtime artifacts.

## Background

Review of `.tmp/douyin-service-provider-20260610` showed that the board can carry real-looking multi-agent exchange, but the runtime cannot yet prove host child lifecycle, cannot fully replay decisions from audit logs, and can emit misleading final reports. The prompt and schema surfaces also leave too much behavior to manual convention.

## Scope

- Harden `.cowork-flow/scripts/party_mode_v2.py` and the template mirror.
- Tighten Party Mode V2 board/action/final report contracts in `.cowork-flow/spec/` and template mirrors.
- Update Party Mode V2 host-facing assets when commands or prompt wording change.
- Add regression tests for runtime state transitions, schema validation, audit replay, prompt generation, and root/template parity.
- Keep Party Mode V2 advisory only; do not let it satisfy formal `cowork-implement` or `cowork-check`.

## Non-goals

- Do not redesign Party Mode V1.
- Do not change formal `cowork-*` runtime-context dispatch semantics.
- Do not implement host primitives inside the Python runtime; the runtime still emits host-neutral actions only.
- Do not build a full UI for Party Mode V2.

## Key Assumptions

- Party Mode V2 remains advisory and cannot satisfy formal Implement or Check gates.
- Runtime state under `.cowork-flow/.runtime/party-mode-v2` is ephemeral but must be reliable enough for same-run audit and debugging.
- Host adapters can execute native dispatch, wait, list, and close primitives, but the Python runtime records only host-neutral actions and explicit host result payloads.
- Windows filesystem behavior matters; locking and atomic writes must work in PowerShell-driven local runs.
- Root assets and `template/` mirrors must stay behaviorally identical because new projects inherit the template copies.

## Required Fixes

1. Empty board views must explain whether the current round is legitimately waiting for posts or whether the view is stale, wrong discussion, wrong round, or closed.
2. The runtime must record host lifecycle evidence: action history, action result, host child id, agent status, wait/list/close outcome, and closeout reason.
3. Final reports must not report `stop_reason=converged` while presenting historical disagreements as currently unresolved.
4. Publish and respond prompts must be phase-specific and include the relevant command, payload schema, and current-round constraints.
5. Runtime file writes must be safe under parallel child submissions. Board updates must avoid lost writes and duplicate generated ids.
6. `discussion_id` and `agent_id` must be validated for safe path, file name, id, and prompt command usage.
7. `post` and `respond` payloads must require explicit current `round` when `require_current_round_only=true`.
8. `respond` must reject self-targeting, duplicate target responses, unsupported target coverage, and excess targets beyond `max_rebuttal_targets_per_agent`.
9. Response records must preserve the evidence fields validated by the runtime, including accepted/rejected parts, updated position, checked evidence, and counter evidence or reasoning.
10. Audit logs must include view, advance, finalize, action-issued, action-result, warning, and close events with timestamps sufficient to replay a discussion.
11. `fresh_context_per_round=true` must emit close actions for stale round children before dispatching fresh children, or the config/documentation must be changed to match actual reuse behavior.
12. `finalize` must be state-safe: only closed discussions or explicit manual termination can produce a final report, and finalization must update board, actions, and agent state consistently.
13. Host-forbidden output filtering must not scan user-controlled topic, claim, evidence, or reasoning after state has already been written.
14. JSON schemas must validate action, board, public view, and final report shapes with per-action required fields.
15. Root/template mirrors and host assets must stay in sync for runtime script, config, specs, schemas, skills, and commands.

## Acceptance Criteria

- A malformed `discussion_id` or `agent_id` cannot write outside `.cowork-flow/.runtime/party-mode-v2/<discussion_id>` and cannot generate unsafe prompt commands.
- Two simulated children posting or responding in close succession cannot lose a board update or create duplicate ids.
- A child cannot respond to its own post, respond twice to the same target, omit `round`, or exceed configured rebuttal target limits.
- A response with `decision=revise` persists `accepted_part`, `rejected_part`, and `updated_position`; `maintain` and `concede` persist their decision-specific evidence fields.
- `advance` returns a stable envelope across non-terminal and terminal transitions, or a documented terminal envelope that callers can distinguish without probing arbitrary keys.
- `finalize` refuses incomplete publish/respond phases unless called with an explicit manual termination mode.
- A final `converged` report contains no current unresolved disagreements; historical disagreements are either excluded or marked as historical and resolved by a later round.
- `view` output includes an explicit empty-state reason when posts or responses are empty.
- Generated `*-publish.md` and `*-respond.md` prompts differ materially and include the correct command and payload schema.
- Host-neutral action history is retained after actions are completed; final `actions.json` being empty does not erase the lifecycle trail.
- Tests validate root/template parity for runtime scripts, config, board spec, action schema, and host-facing Party Mode V2 assets.

## Verification

- `rtk python -m unittest tests.test_party_mode_v2 tests.test_host_adapters tests.test_cowork_agents tests.test_workflow_parallel_sessions`
- `rtk git diff --check`
- `.\.cowork-flow\run.cmd task validate .cowork-flow\tasks\06-10-party-mode-v2-runtime-hardening`
- Manual smoke: create a temporary Party Mode V2 discussion, run publish/respond/advance/finalize, and inspect board, public view, actions, audit, agents, and final report for the acceptance criteria.
