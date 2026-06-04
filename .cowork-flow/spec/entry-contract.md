# Entry contract

`COWORK_ENTRY_CONTRACT_V1` classifies main-session prompts before workflow
recovery. It does not identify formal subagents. Formal subagent identity is
resolved by runtime context binding before workflow state is injected.

## Classification order

1. Runtime context binding, handled by the hook/plugin before this classifier.
2. Explicit user main-session request.
3. Read-only question or inspection request.
4. Command-only wrapper with explicit command semantics.
5. Unknown or task-shaped input without runtime binding.

## Entry kinds

| Kind | Meaning | May mutate workflow state |
| --- | --- | --- |
| `MAIN_SESSION` | User is asking the coordinator to run cowork-flow. | Yes |
| `READ_ONLY` | Question, inspection, or research without writes. | No |
| `COMMAND_ONLY` | Host command wrapper with explicit command semantics. | No, unless command contract allows |
| `UNKNOWN` | Insufficient confidence. | No |

## Fail-closed rules

- Entry classification happens before task start, task resume, archive, or subagent dispatch.
- `UNKNOWN` must not start/resume/archive/spawn.
- `UNKNOWN` is not subagent evidence; it must preserve active-task/no-task
  visibility and ask for clarification before workflow mutation.
- A prompt that looks like a child assignment but has no runtime context remains
  `UNKNOWN` or `READ_ONLY`; it does not become a formal subagent.
- A missing, closed, or invalid runtime context produces fail-closed subagent
  workflow state and must not fall back to main-session start/resume.
- Runtime context binding overrides project bootstrap text for formal subagents.

## Normalized object

```json
{
  "entryKind": "MAIN_SESSION",
  "confidence": 0.55,
  "source": "main_session_heuristic",
  "canMutateWorkflowState": true
}
```
