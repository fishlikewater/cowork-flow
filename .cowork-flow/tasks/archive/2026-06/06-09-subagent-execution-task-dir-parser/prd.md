# Fix subagent execution task dir parser

## Goal

`subagent init` must preserve `--execution-task-dir` when the flag is passed before the `init` subcommand or inside the `init` subcommand.

## Scope

- Keep fixed `cowork-*` dispatch requiring a task directory.
- Keep generic `worker` dispatch best-effort and not task-bound.
- Touch only the subagent parser and regression tests needed for this behavior.

## Acceptance

- `subagent.py --execution-task-dir <task> init ...` succeeds for fixed agents.
- `subagent.py init --execution-task-dir <task> ...` succeeds for fixed agents.
- `subagent.py init ...` without a task directory still rejects fixed agents.
- Focused subagent dispatch tests pass.
