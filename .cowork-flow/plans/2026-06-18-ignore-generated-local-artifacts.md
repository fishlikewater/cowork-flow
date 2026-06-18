# Ignore Generated Local Artifacts Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Stop local generated directories from polluting `git status` during normal cowork-flow usage.
**Architecture:** This is a narrow repository hygiene change. The root `.gitignore` is the authority for local Git visibility, while regression coverage in `tests/test_flow_migrate.py` locks the intended ignore entries so future migrations or cleanup work do not accidentally remove them.
**Verification:** `rtk proxy git check-ignore -v .codegraph template/.cowork-flow/.runtime`; `rtk python -m pytest tests/test_flow_migrate.py -q`; `rtk git diff --check`

## Execution Strategy

Serial work. The change touches one ignore file and one Python test file in the
same behavior chain, so parallel slices would add coordination overhead without
benefit.

## Steps

1. Confirm the current repo noise and scope boundaries.
   Files: `.gitignore`, `tests/test_flow_migrate.py`, `src/lib/copy-template.js`
   Actions:
   - Verify `.codegraph/` and `template/.cowork-flow/.runtime/` are currently untracked noise.
   - Confirm template copy logic already skips `.cowork-flow/.runtime/` so this task stays root-ignore only.
   Verification:
   - `rtk proxy git check-ignore -v .codegraph template/.cowork-flow/.runtime` should return non-zero before the fix.

2. Add explicit ignore rules for the generated local directories.
   Files: `.gitignore`
   Actions:
   - Add `.codegraph/`.
   - Add `template/.cowork-flow/.runtime/`.
   - Do not add broad `.cowork-flow/.runtime/` ignore rules that could hide real repo artifacts.
   Verification:
   - `rtk proxy git check-ignore -v .codegraph template/.cowork-flow/.runtime` should show the new matching rules after the fix.

3. Lock the behavior with regression coverage.
   Files: `tests/test_flow_migrate.py`
   Actions:
   - Add a focused test that reads the committed root `.gitignore`.
   - Assert it contains `.codegraph/` and `template/.cowork-flow/.runtime/`.
   Verification:
   - `rtk python -m pytest tests/test_flow_migrate.py -q`

4. Run closeout verification for the task scope.
   Files: `.gitignore`, `tests/test_flow_migrate.py`
   Actions:
   - Confirm the generated directories disappear from `git status`.
   - Check formatting/newline safety.
   Verification:
   - `rtk git status --short`
   - `rtk git diff --check`
