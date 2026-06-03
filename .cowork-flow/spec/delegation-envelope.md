# Delegation envelope

`COWORK_DELEGATION_V1` is the host-neutral first-screen marker for bounded delegated work. It is stronger than prose and must be parsed before workflow bootstrap or recovery.

## Envelope

```text
COWORK_DELEGATION_V1
dispatch_id: <unique-id>
host: <host-id>
role: cowork-implement
task_dir: .cowork-flow/tasks/<task>
entry_kind: DELEGATED_HARD
allowed_actions: read,edit,test
forbidden_actions: start,resume,archive,commit,spawn_agent
context_file: .cowork-flow/tasks/<task>/implement.jsonl
ack_token: <ack-token>
COWORK_DELEGATION_END
```

The delegated agent first returns only:

```text
COWORK_ACK <dispatch_id> <ack_token>
```

The coordinator then sends:

```text
EXECUTE <dispatch_id>
```

## Rules

- Missing or mismatched ACK means not dispatched.
- Missing or mismatched `EXECUTE <dispatch_id>` means do not run.
- Envelope role must match the fixed agent.
- A delegated fixed agent is a leaf executor.
- Legacy `COWORK_DISPATCH_V1` remains valid for fixed agents.
- Natural-language delegated prompts remain allowed, but are `DELEGATED_SOFT` unless normalized into this envelope by the main session.
