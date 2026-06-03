---
description: Dispatch cowork-flow research fixed subagent.
argument-hint: "<task-dir>"
---

Use the `cowork-research` agent for `$ARGUMENTS`.

Prompt must include `COWORK_DELEGATION_V1`, `role: cowork-research`,
`host: claude-code`, `task_dir`, `context_file`, `ack_token`, and
`COWORK_DELEGATION_END`.

Return only `COWORK_ACK <dispatch_id> <ack_token>` until the coordinator sends
`EXECUTE <dispatch_id>`.
