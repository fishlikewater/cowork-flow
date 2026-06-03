---
name: python-design
description: Use when writing, reviewing, or refactoring Python CLI/runtime scripts in cowork-flow.
---

# Python Design

Use this for `.cowork-flow/scripts/**/*.py` and other Python utilities.

## Guidelines

- Keep command parsing thin; move reusable behavior into named functions.
- Use `pathlib.Path` for filesystem paths.
- Separate pure decisions from filesystem mutation so tests can cover decisions directly.
- Prefer explicit data structures over stringly-typed control flow.
- Handle UTF-8 deliberately on Windows.
- Catch narrow exceptions; let unexpected failures surface with useful messages.
- Keep root and `template/` runtime copies aligned.

## Tests

For behavior changes, add or update tests that prove:

- Command arguments are parsed correctly.
- Files are created, updated, or protected as intended.
- Error output is specific enough to diagnose the failure.
- Windows entrypoints remain valid when relevant.
