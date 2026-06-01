# Runtime Post-ACK Grace Config

## Problem

`codex.post_ack_execution_grace_ms` is documented in workflow/start-skill text, but runtime code only reads `codex.dispatch_mode`. Changing the grace value in `.cowork-flow/config.yaml` does not currently change the injected workflow context seen by the coordinator.

## Proposal

- Add a config getter for `codex.post_ack_execution_grace_ms`.
- Default to `300000` ms when the config is missing or invalid.
- Inject the resolved value into Codex workflow-state hook output.
- Keep root/template runtime files synchronized.
- Add tests that prove changing config changes hook output.

## Impact

Main-session coordination can now use the concrete configured grace value without manually opening `config.yaml`, while the existing workflow rule remains unchanged: grace expiration is a review checkpoint, not an automatic close trigger.
