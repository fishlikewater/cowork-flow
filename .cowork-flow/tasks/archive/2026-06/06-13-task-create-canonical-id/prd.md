# Fix Task Create Canonical Id

## Goal

Fix `task create` so a date-prefixed `--slug` creates a canonical Flow task id without the date prefix.

## Scope

- Normalize date-prefixed task create slugs before writing FlowStore task ids.
- Preserve artifact directory date prefix behavior.
- Update root and template runtime copies.
- Add regression coverage in the template runtime test suite.

## Non-Goals

- No historical DB migration.
- No broad lifecycle refactor.
- No release/publish work.

## Key Assumptions

- `MM-DD-` prefixes are artifact-directory metadata, not part of the logical task id.
- `_resolve_task_id()` already strips date prefixes for lifecycle lookup.
- Root/template runtime parity is required for installed projects.

## Acceptance Criteria

1. `task create --slug <MM-DD-slug>` stores Flow task id `<slug>`.
2. The artifact directory stays `<MM-DD-slug>` and is not doubled.
3. Focused lifecycle regression test passes.
4. `npm run test:template` passes.
5. `git diff --check` passes.

## Relevant Files

- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `tests/test_flow_script_paths.py`
- `.cowork-flow/spec/patterns/index.md`

## Verification

- `.\.cowork-flow\run.cmd python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_cmd_create_keeps_existing_date_prefix -v`
- `npm run test:template`
- `git diff --check`
