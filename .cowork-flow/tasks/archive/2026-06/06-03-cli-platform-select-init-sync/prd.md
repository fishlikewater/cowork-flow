# CLI platform-select init and sync

## Goal

Add host-platform selection to the cowork-flow CLI so projects can install and sync Codex assets, OpenCode assets, or both.

## Requirements

- `init` accepts platform selection for `codex`, `opencode`, or both.
- When no platform is provided, interactive `init` prompts the user to choose one or more platforms.
- Non-interactive `init` without platform fails with an actionable error.
- `codex` selection copies only Codex host assets.
- `opencode` selection copies only OpenCode host assets.
- Multiple selections copy all selected host assets.
- `sync` detects the target project's installed host assets and syncs only those host assets.
- If both host asset sets exist, `sync` updates both.
- Existing common assets and developer initialization keep working.

## Acceptance

- Node CLI tests cover `init` Codex-only, OpenCode-only, multi-platform, interactive prompt, and non-interactive missing platform behavior.
- Node sync tests cover Codex-only, OpenCode-only, and both-host detection.
- Existing package/template verification remains green.
