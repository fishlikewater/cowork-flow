---
description: Dispatch cowork-flow check as a subtask.
agent: cowork-check
subtask: true
---

COWORK_DELEGATION_V1
dispatch_id: $ARGUMENTS
host: opencode
role: cowork-check
task_dir: .cowork-flow/tasks/<task>
entry_kind: DELEGATED_HARD
allowed_actions: read,edit,test
forbidden_actions: start,resume,archive,commit,spawn_agent
context_file: .cowork-flow/tasks/<task>/check.jsonl
ack_token: <ack-token>
COWORK_DELEGATION_END

Return only `COWORK_ACK <dispatch_id> <ack_token>` until the coordinator sends `EXECUTE <dispatch_id>`.
