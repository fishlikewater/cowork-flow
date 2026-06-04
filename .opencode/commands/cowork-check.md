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
```

The child must execute only after the plugin binds that runtime context.
Missing, closed, invalid, or mismatched context is `needs_context`.
