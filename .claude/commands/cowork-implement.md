---
description: Dispatch cowork-flow implementation fixed subagent.
argument-hint: "<task-dir>"
---

Use the `cowork-implement` agent for `$ARGUMENTS`.

Prompt must include `COWORK_DELEGATION_V1`, `role: cowork-implement`,
`host: claude-code`, `task_dir`, `context_file`, `ack_token`, and
`COWORK_DELEGATION_END`.

Return only `COWORK_ACK <dispatch_id> <ack_token>` until the coordinator sends
`EXECUTE <dispatch_id>`.
