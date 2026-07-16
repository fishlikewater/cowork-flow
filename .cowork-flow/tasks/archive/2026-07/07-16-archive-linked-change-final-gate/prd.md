# P1 收紧 linked change 自动归档门禁

## Goal

Prevent task archive from prematurely archiving a multi-task linked change before the final linked task is ready.

## Scope

- Archive lifecycle helpers in task/change scripts
- Root/template runtime parity
- Focused lifecycle tests

## Non-Goals

- Do not remove single-task auto archive
- Do not redesign the whole change schema

## Acceptance Criteria

1. A multi-task linked change is not auto-archived when archiving a non-final completed task.
2. The existing single-task linked-change auto archive path still passes.
3. Root and template runtime scripts remain aligned for the changed helpers.
4. Focused lifecycle tests and git diff check pass.

## Relevant Files

- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/change.py`
- `template/.cowork-flow/scripts/change.py`
- `tests/test_flow_script_paths.py`
- `tests/test_change_script.py`

## Verification

- `.cowork-flow/run.cmd python -m unittest tests.test_flow_script_paths tests.test_change_script -v`
- `git diff --check`
