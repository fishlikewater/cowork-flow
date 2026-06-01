# Delay Subagent Close During Post-ACK Context Loading

## Assumptions

- The user-reported failure happens after ACK: the child has acknowledged dispatch, received `EXECUTE`, and is doing normal context loading.
- Fixed `cowork-*` agents should still ACK before execution; this task does not weaken the ACK gate.
- After `EXECUTE`, missing output or missing compass/status files are not enough evidence to close the child.
- Generic `worker` dispatch remains best-effort, but executing workers should not be closed solely because context loading is quiet.

## Goal

Prevent the main session from closing a normally running subagent after ACK/EXECUTE only because the child has not produced a compass/status file or reply while loading context.

## Scope

- Update main-session `cowork-*` subagent coordination docs and skills.
- Keep root and `template/` copies aligned.
- Add regression tests for post-ACK execution grace.
- Do not introduce a new runtime state machine, result ledger, or outbox.
- Do not change unrelated agent-team archive content.

## Acceptance Criteria

- `cowork-*` subagent dispatch docs preserve the ACK gate.
- After `EXECUTE`, docs say no reply or no compass/status file while the child loads context is inconclusive.
- Main session must use post-ACK execution grace before closing an executing subagent.
- Main session must record `execute_sent_at[dispatch_id]` and compute `deadline[dispatch_id] = execute_sent_at[dispatch_id] + codex.post_ack_execution_grace_ms`.
- Main session must not use a shared/global grace deadline across children.
- If `list_agents` still shows the child running, main session continues waiting through grace instead of closing it.
- Grace duration is configurable through `codex.post_ack_execution_grace_ms` in `.cowork-flow/config.yaml`, defaulting to `300000` ms.
- Grace expiration for one `dispatch_id` is a review checkpoint for that child only, not a close trigger and not evidence about other children.
- If progress, compass, or status files exist after grace expires, main session continues waiting and must not close solely because grace expired.
- Main session may close an executing subagent only after clear wrong-dispatch evidence, child completion, or user cancellation.
- Generic workers still remain best-effort, but execution silence alone is not a stall signal.
- Root and template workflow/start-skill files stay synchronized where tests require it.
- Focused tests pass.

## Relevant Files

- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `.agent/skills/start/SKILL.md`
- `template/.agent/skills/start/SKILL.md`
- `.cowork-flow/config.yaml`
- `template/.cowork-flow/config.yaml`
- `.cowork-flow/scripts/doctor.py`
- `template/.cowork-flow/scripts/doctor.py`
- `tests/test_workflow_parallel_sessions.py`

## Verification

- `python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py"`
- `.\.cowork-flow\run.cmd python .cowork-flow/scripts/doctor.py --subagent-safety`
- `npm run test:all`
