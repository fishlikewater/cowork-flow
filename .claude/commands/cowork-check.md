---
description: Dispatch cowork-flow check fixed subagent.
argument-hint: "<task-dir>"
---

Use the `cowork-check` agent for `$ARGUMENTS`.

Before dispatch, create a runtime context:

```bash
./.cowork-flow/run subagent init --role check --agent-type cowork-check --execution-task-dir "$ARGUMENTS" --title "Check $ARGUMENTS" --host claude-code --adapter claude-code.subagent
```

Pass the returned prompt transport to the subagent:

```text
cowork_runtime_context_id: <runtime_context_id>
```

The child must execute only after its hook binds that runtime context. Missing,
closed, invalid, or mismatched context is `needs_context`.
