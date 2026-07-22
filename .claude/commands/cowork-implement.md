---
description: Dispatch cowork-flow implementation fixed subagent.
argument-hint: "<task-dir>"
---

Use the `cowork-implement` agent for `$ARGUMENTS`.

Before dispatch, create a runtime context:

```bash
${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run subagent init --role implement --agent-type cowork-implement --execution-task-dir "$ARGUMENTS" --title "Implement $ARGUMENTS" --host claude-code --adapter claude-code.subagent
```

Pass the returned prompt transport to the subagent:

```text
cowork_runtime_context_id: <runtime_context_id>
cowork_host_context_key: <host_context_key>
```

The child must first bind the runtime context before role work:

```bash
${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>
```

Missing, closed, invalid, mismatched, or unbound context is `needs_context`.
