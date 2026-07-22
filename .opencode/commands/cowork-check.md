---
description: Dispatch cowork-flow check as a runtime-context subtask.
agent: cowork-check
subtask: true
---

Before dispatch, create a runtime context:

```bash
./.cowork-flow/run subagent init --role check --agent-type cowork-check --execution-task-dir <task-dir> --title "Check <task-dir>" --host opencode --adapter opencode.task
```

Pass the returned prompt transport to the subagent:

```text
cowork_runtime_context_id: <runtime_context_id>
cowork_host_context_key: <host_context_key>
```

The child must first bind the runtime context before role work:

```bash
./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>
```

Missing, closed, invalid, mismatched, or unbound context is `needs_context`.
