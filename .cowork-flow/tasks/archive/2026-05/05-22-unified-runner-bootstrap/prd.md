# Unify cowork-flow Runner Logic

## Goal

Keep `run` and `run.cmd` as platform-specific Python bootstrap launchers, but move all cowork-flow command dispatch to one Python runner.

## Requirements

- Add `.cowork-flow/scripts/run.py` as the shared command dispatcher.
- Simplify `run` and `run.cmd` so they only select Python 3.8+ and forward to `scripts/run.py`.
- Preserve existing command names and aliases.
- Do not require Bash on Windows.
- Update template and current project files consistently.

## Acceptance Criteria

- [ ] `run.py` maps `task list` to `task.py list` and `agent-team init` to `agent_team.py init`.
- [ ] `run.cmd` no longer contains command-specific labels or direct `task.py` dispatch.
- [ ] POSIX `run` still prefers `python3`, then falls back as before.
- [ ] Package/init/template tests include the new shared runner.
