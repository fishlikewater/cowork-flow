# Post-ACK Execution Grace Requirements

## Requirements

- Main sessions MUST wait for `COWORK_ACK <dispatch_id> <ack_token>` before sending `EXECUTE <dispatch_id>`.
- Fixed `cowork-*` execution MUST use a per-dispatch post-ACK execution grace rule after `EXECUTE`: no reply or no compass/status file while loading context is inconclusive.
- Post-ACK execution grace duration MUST default to `300000` ms and be configurable through `codex.post_ack_execution_grace_ms` in `.cowork-flow/config.yaml`.
- Main sessions MUST record `execute_sent_at[dispatch_id]` and compute `deadline[dispatch_id] = execute_sent_at[dispatch_id] + codex.post_ack_execution_grace_ms`.
- Main sessions MUST NOT use a shared/global deadline across children.
- Main sessions MUST NOT close an executing fixed `cowork-*` child solely because no marker file exists.
- If `list_agents` still shows the child running, main sessions SHOULD continue waiting through post-ACK execution grace.
- Post-ACK execution grace expiration for one `dispatch_id` MUST be treated as a review checkpoint for that child only, not a close trigger and not evidence about other children.
- If progress, compass, or status files exist after grace expires, main sessions MUST continue waiting and MUST NOT close solely because grace expired.
- Main sessions MAY close a fixed child when the child returns a mismatched dispatch identifier, completes, or is cancelled by the user.
- Generic `worker` dispatch remains best-effort, but execution silence alone is not proof of a stall.

## Verification

- Workflow docs and start skill mention per-dispatch post-ACK execution grace and missing compass/status files.
- Tests assert root and template copies carry the same coordination contract.
