# Rename active task runtime field

## Goal

Rename the session runtime JSON field to `active_task_path` so it is not confused with the removed `.cowork-flow/.current-task` file.

## Requirements

- `.cowork-flow/.runtime/sessions/<context-key>.json` must store the active task path under `active_task_path`.
- Runtime code must read, write, and clear session pointers using `active_task_path`.
- Tests and docs must describe the session runtime field as `active_task_path`.
- Do not restore or add compatibility with `.cowork-flow/.current-task`.

## Verification

- Focused active-task runtime tests fail before implementation and pass after.
- Full Python and Node test suites pass.
