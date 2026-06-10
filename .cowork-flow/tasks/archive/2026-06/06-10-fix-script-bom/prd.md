# Fix script BOM encoding

## Goal

Remove UTF-8 BOM bytes from script files that currently start with `EF BB BF`.

## Scope

- `.cowork-flow/scripts/common/archive_utils.py`
- `template/.cowork-flow/scripts/common/archive_utils.py`
- `test/sync.test.js`

## Non-goals

- Do not change script behavior.
- Do not reformat unrelated files.
- Do not alter generated or local index directories such as `.codegraph/`.

## Acceptance Criteria

- The three files no longer start with UTF-8 BOM bytes.
- A repo script-file BOM scan reports zero matches.
- `git diff --check` passes.
- Focused tests for affected areas pass.

## Verification

- Byte-level BOM scan over repo script files.
- `git diff --check`
- Focused Node and Python tests related to sync/archive behavior.
