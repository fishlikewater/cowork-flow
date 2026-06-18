# Entry contract

`COWORK_ENTRY_CONTRACT_V2` classifies main-session prompts before workflow
recovery using dual-channel classification. It does not identify formal subagents. Formal subagent identity is
resolved by runtime context binding before workflow state is injected.

## Classification order

1. Runtime context binding, handled by the hook/plugin before this classifier.
2. **Structured signal** (new in V2): Read `entrySignals` declarations from the
   active host adapter's `adapter.yaml`. Extract signal values from
   `hook_input` (or environment variables). Map to `EntryKind`.
3. **Legacy text fallback** (opt-in escape hatch): Keyword heuristics on prompt
   text. Controlled by `config.yaml`
   `entry.legacy_text_fallback.enabled` (default `false`).
4. **Fail-closed**: If no structured signal and fallback disabled → `UNKNOWN`.

## Dual-channel classification

| Channel | Source | Priority | Confidence |
| --- | --- | --- | --- |
| Structured | `adapter.yaml` entrySignals → hook_input | 1 (always wins) | ≥ 0.85 |
| Legacy fallback | Prompt text keyword heuristics | 2 (only if structured absent + fallback enabled) | 0.3–0.6 |
| Fail-closed | Neither channel produces a result | 3 | 0.0 |

### Structured signal mapping

| Signal key | Values | Maps to EntryKind |
| --- | --- | --- |
| `sessionRole` | `main` / `main_session` / `coordinator` | `MAIN_SESSION` |
| `sessionRole` | `command` / `command_wrapper` / `cli` | `COMMAND_ONLY` |
| `invocationKind` | `read_only` | `READ_ONLY` |
| `invocationKind` | `hook` / `command_wrapper` / `cli` | `COMMAND_ONLY` |
| `invocationKind` | `interactive` | `MAIN_SESSION` |
| `hookEventName` | `SessionStart` | `MAIN_SESSION` (approximation) |
| `dispatchMode` | `sub-agent` | `COMMAND_ONLY` (approximation) |

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
- **Structured signal takes priority over legacy fallback.** If a structured
  signal is present, it is used regardless of prompt text content.
- **Legacy fallback is a temporary escape hatch.** It stays disabled by default
  and should be enabled only when a host-specific structured signal path is
  unavailable or broken.

## Config control

The legacy fallback can be toggled via:
- `config.yaml`: `entry.legacy_text_fallback.enabled: true/false` (default `false`)
- Environment: `COWORK_FLOW_LEGACY_FALLBACK=1|0` (overrides config.yaml)

## Normalized object

```json
{
  "entryKind": "MAIN_SESSION",
  "confidence": 0.9,
  "source": "structured_session_role",
  "canMutateWorkflowState": true
}
```
