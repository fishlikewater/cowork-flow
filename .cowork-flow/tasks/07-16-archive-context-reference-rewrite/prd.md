# P1 归档时重写上下文引用路径

## Goal

Rewrite archived JSONL context references to moved archive paths so validation passes after closeout.

## Scope

- Archived task context JSONL file fields
- Task/change archive move operations
- Root/template runtime parity

## Non-Goals

- Do not rewrite prose history broadly
- Do not add broad validation allowlists

## Acceptance Criteria

1. Archived task context JSONL entries pointing to moved tasks are rewritten to archived task paths.
2. Archived task context JSONL entries pointing to moved changes are rewritten to archived change paths.
3. Task validate passes on archived task fixtures immediately after archive.
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
