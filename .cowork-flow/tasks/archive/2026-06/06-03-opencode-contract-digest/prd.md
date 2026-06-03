# OpenCode contract digest parity

## Goal

Make the OpenCode plugin inject the same registry-driven contract digest model as the Codex hook, while keeping workflow execution logic unchanged.

## Scope

- Update `.opencode/plugins/cowork-flow.js` and template mirror.
- Keep `.cowork-flow/spec/registry.json` as the source for contract digest entries.
- Keep OpenCode runtime injection short and fingerprinted.
- Add tests/doctor checks that OpenCode plugin is registry-driven.

## Acceptance

- OpenCode plugin reads `.cowork-flow/spec/registry.json`.
- OpenCode plugin emits `<contract-digest fingerprint="...">`.
- Digest references contract ids and `read_before` triggers, not full spec contents.
- Root/template plugin files stay synced.
- Existing doctor and tests pass.
