# Workflow navigator and task next

## Goal

Add a read-only navigator that tells the main session the next safe workflow
action and exact command from current task/change state.

## Scope

- Add `task next` or equivalent command.
- Optionally add `flow help` route help.
- Report task status, next action, command, and blockers.
- Cover no-task, planning, in-progress, completed, stale/unknown, delegated-subtask
  guidance, and L2 readiness blocker display.
- Integrate `task next` into workflow stage boundaries instead of documenting it
  as a standalone helper only.
- Ensure lifecycle commands keep `task.json.status` aligned with planning,
  implementation, check, and completion stages.

## Dependencies

- Can run before `.cowork-flow/tasks/06-04-l2-readiness-gate`.
- Provides an optional blocker extension point for future readiness helpers.

## Acceptance

1. Navigator commands are read-only.
2. Output names current task/source when present.
3. Output includes one concrete next action and command.
4. Output includes readiness blockers when a readiness helper is present.
5. Root/template command wiring stays synchronized.
6. Active ready planning tasks route to implementation/check dispatch guidance,
   while inactive ready planning tasks route to `task start`.
7. `task start`, `task review`, and `task complete` update `task.json.status`
   so `task next` reads durable stage state.
8. Workflow docs tell the main session when to run `task next` and when to
   advance status.

## Verification

- `python -m unittest discover -s tests -p "test_python_runner.py"`
- `python -m unittest discover -s tests -p "test_flow_script_paths.py"`
- `git diff --check`
