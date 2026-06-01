# Subagent Post-ACK Execution Grace Plan

## Goal

Prevent main-session coordination from closing a subagent that has ACKed, received `EXECUTE`, and is still loading context without producing output or runtime marker files.

## Execution Strategy

Serial inline work. This task changes subagent/runtime behavior contracts, so main session executes directly instead of dispatching `cowork-implement`.

## Steps

1. [x] Clarify target behavior -> Verify: user goal restated as "post-ACK execution silence while loading context is inconclusive, not failure".
2. [x] Create task/change context -> Verify: task and L1 change exist.
3. [x] Add regression assertions -> Verify: tests fail until docs/skills mention per-dispatch post-ACK execution grace, `execute_sent_at[dispatch_id]`, and non-evidence of missing compass/status files after `EXECUTE`.
4. [x] Update workflow, start skill, config, and doctor guards -> Verify: root/template files match, close rules are explicit, and no shared/global deadline is allowed.
5. [x] Run focused verification -> Verify: `python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py"` and `.\.cowork-flow\run.cmd python .cowork-flow/scripts/doctor.py --subagent-safety`.
6. [x] Run package verification -> Verify: `npm test`, `npm run pack:check`; `npm run test:all` is blocked by existing Windows hook-command test environment issue.
7. [x] Finish task -> Verify: diff scoped, task state updated, archive and commit requested by user.
