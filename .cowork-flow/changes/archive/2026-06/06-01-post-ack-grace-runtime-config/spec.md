# Runtime Post-ACK Grace Config Requirements

## Requirements

- Runtime config MUST expose `codex.post_ack_execution_grace_ms` as a positive integer millisecond value.
- The default value MUST be `300000`.
- Missing `.cowork-flow/config.yaml`, missing `codex`, missing `post_ack_execution_grace_ms`, non-numeric values, and non-positive values MUST fall back to the default.
- The Codex workflow-state hook MUST include the resolved `post_ack_execution_grace_ms` value in its injected context.
- Changing `.cowork-flow/config.yaml` from `300000` to another valid positive integer MUST change hook output without code changes.
- Existing `codex.dispatch_mode` behavior MUST remain unchanged.
- Root and template copies MUST remain synchronized.

## Verification

- Unit tests cover valid custom config and invalid fallback behavior.
- Workflow safety tests continue to assert the post-ACK grace coordination contract.
