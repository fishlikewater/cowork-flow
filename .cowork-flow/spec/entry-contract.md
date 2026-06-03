# Entry contract

`COWORK_ENTRY_CONTRACT_V1` classifies the current prompt before workflow recovery. This prevents bootstrap text, AGENTS.md, or no-task hints from overriding a delegated assignment.

## Classification order

1. Structured delegation envelope: `COWORK_DELEGATION_V1`.
2. Structured dispatch envelope: `COWORK_DISPATCH_V1`.
3. Legacy fixed-agent line: `Active task: .cowork-flow/tasks/<task>`.
4. Strong delegated prompt shape: `任务：` / `约束：` / `输出：`, bounded scope, explicit output.
5. Host metadata or command metadata.
6. User direct main-session request.

## Entry kinds

| Kind | Meaning | May mutate workflow state |
| --- | --- | --- |
| `MAIN_SESSION` | User is asking the coordinator to run cowork-flow. | Yes |
| `DELEGATED_HARD` | Structured envelope or fixed-agent dispatch. | No, except assigned files/state explicitly allowed |
| `DELEGATED_SOFT` | Advisory bounded subagent prompt without hard envelope. | No |
| `READ_ONLY` | Question, inspection, or research without writes. | No |
| `COMMAND_ONLY` | Host command wrapper with explicit command semantics. | No, unless command contract allows |
| `UNKNOWN` | Insufficient confidence. | No |

## Fail-closed rules

- Entry classification happens before task start, task resume, archive, or subagent dispatch.
- `UNKNOWN` must not start/resume/archive/spawn.
- `DELEGATED_HARD` and `DELEGATED_SOFT` must not run unscoped resume, create or activate tasks, archive, commit, or dispatch more agents unless the envelope explicitly allows coordination.
- `DELEGATED_SOFT` output is advisory and cannot complete Implement or Check.
- Structured delegation envelopes override project bootstrap text.

## Normalized object

```json
{
  "entryKind": "DELEGATED_HARD",
  "confidence": 0.95,
  "source": "envelope",
  "allowedActions": ["read", "edit", "test"],
  "forbiddenActions": ["start", "resume", "archive", "commit", "spawn_agent"],
  "canMutateWorkflowState": false
}
```
