# Ignore generated local artifacts in git status

## Goal

Make normal cowork-flow usage stop polluting repository `git status` with
local-only generated directories.

## Scope

- Update the repository root `.gitignore` to ignore:
  - `.codegraph/`
  - `template/.cowork-flow/.runtime/`
- Add regression coverage that locks those ignore entries in place.
- Verify the two generated directories disappear from `git status`.

## Non-Goals

- Do not ignore real workflow data under `.cowork-flow/tasks/`, `.cowork-flow/changes/`,
  or `.cowork-flow/plans/`.
- Do not change template copy behavior, package layout, or runtime persistence.
- Do not clean unrelated untracked artifacts as part of this task.

## Acceptance Criteria

1. `.gitignore` contains `.codegraph/`.
2. `.gitignore` contains `template/.cowork-flow/.runtime/`.
3. `rtk proxy git check-ignore -v .codegraph template/.cowork-flow/.runtime`
   shows both paths are ignored by the repository root `.gitignore`.
4. A regression test covers the required ignore entries.
5. `rtk python -m pytest tests/test_flow_migrate.py -q` passes.

## Related Files

- `.gitignore`
- `tests/test_flow_migrate.py`
- `src/lib/copy-template.js`
- `.cowork-flow/changes/06-18-ignore-generated-local-artifacts/`
- `.cowork-flow/plans/2026-06-18-ignore-generated-local-artifacts.md`

## Verification

- `rtk proxy git check-ignore -v .codegraph template/.cowork-flow/.runtime`
- `rtk python -m pytest tests/test_flow_migrate.py -q`
- `rtk git diff --check`
