# CLI platform selector and adapter filtering

## Goal

Fix platform-specific initialization so selected Codex/OpenCode assets are isolated, including `.cowork-flow/adapters/<host>/`, and replace free-text platform input with a keyboard multi-select UI.

## Requirements

- `init --platform codex` must not copy `.cowork-flow/adapters/opencode/adapter.yaml`.
- `init --platform opencode` must not copy `.cowork-flow/adapters/codex/adapter.yaml`.
- Multiple selected platforms copy matching adapter files for all selected platforms.
- `sync` must apply the same platform filter for adapter files.
- Interactive `init` without `--platform` must use a checkbox-style multi-select UI with arrow navigation, space toggle, and enter confirm.
- Non-interactive `init` without `--platform` still fails with an actionable error.

## Acceptance

- Node tests cover platform-specific adapter filtering for init and sync.
- Node tests cover the new selector hook used by `init`.
- Existing full verification passes.
