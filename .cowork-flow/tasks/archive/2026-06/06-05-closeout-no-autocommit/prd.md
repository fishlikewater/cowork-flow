# Default closeout commands to no auto commit

## Goal

Make closeout commands support one final commit by default.

## Requirements

- `task archive <name>` archives task metadata without creating a git commit by default.
- `task archive <name> --commit` keeps explicit archive auto-commit behavior.
- `add-session ...` records workspace metadata without creating a git commit by default.
- `add-session ... --commit` keeps explicit metadata auto-commit behavior.
- Existing `--no-commit` callers remain accepted during transition.
- `add-session --commit` must not fail with missing path constants.

## Verification

- Focused tests cover default no-commit and explicit commit paths.
- Existing archive/session behavior remains compatible.
