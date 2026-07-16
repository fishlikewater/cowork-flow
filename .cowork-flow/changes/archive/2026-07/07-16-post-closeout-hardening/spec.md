# Behavior Spec

## Archive Lifecycle

- `task archive` MUST NOT archive a linked active change while that change still has known unfinished task work.
- `task archive` MUST keep the current single-task linked-change happy path intact.
- After `task archive` or linked `change archive`, archived task context JSONL files SHOULD validate without manual path repair.

## NPM Command Execution

- Windows npm command execution SHOULD use an explicit npm command executable instead of `shell: true`.
- `npm run pack:check` SHOULD complete without `DEP0190` warnings caused by cowork-flow's npm command options.

## Legacy Completed Tasks

- Old completed tasks SHOULD be either archived when safe or documented with an explicit reason for remaining completed.
