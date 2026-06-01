# Runtime Post-ACK Grace Config Design

## Decision

Use the existing config reader and Codex hook as the runtime boundary. The coordinator already receives hook-injected workflow context every turn, so the smallest effective change is to parse the grace value once through `common.config` and inject the resolved value next to `codex-mode`.

## Runtime Shape

Add:

```text
<codex-runtime>
post_ack_execution_grace_ms: 300000
</codex-runtime>
```

The value is resolved from `.cowork-flow/config.yaml` and always emitted as a safe positive integer.

## Why This Path

- It avoids adding another state machine.
- It makes the setting visible before any subagent dispatch.
- It preserves the existing rule that the main session coordinates native Codex subagents.
- It keeps invalid or omitted config safe.

## Non-Goals

- No automatic `close_agent` scheduling.
- No change to `COWORK_DISPATCH_V1`.
- No change to generic worker best-effort behavior.
