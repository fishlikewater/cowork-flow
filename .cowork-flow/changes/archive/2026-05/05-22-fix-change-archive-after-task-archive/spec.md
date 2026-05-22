# Change Archive Task Link Resolution Spec

## Task already archived

- Given a change metadata file has `task: .cowork-flow/tasks/<task-name>`
- And `.cowork-flow/tasks/<task-name>` no longer exists
- And `.cowork-flow/tasks/archive/YYYY-MM/<task-name>` exists
- When the user runs `change archive <change-name>`
- Then the command MUST succeed if all other change requirements are valid.
- And the archived `change.yaml` MUST store `task: archive/YYYY-MM/<task-name>`.

## Missing repo-relative links

- Given a metadata link is written as `.cowork-flow/tasks/missing-task`
- And that path does not exist
- When validation reports the missing path
- Then the error MUST reference `.cowork-flow/tasks/missing-task` once.
- And the error MUST NOT contain `.cowork-flow/tasks/.cowork-flow/tasks/`.

## Strictness

- If neither the active task path nor an archived task with the same task directory name exists, validation MUST still fail.
- Existing valid active and archived task links MUST continue to validate.
- Plan link validation remains strict and unchanged except for repo-relative path display correctness.
