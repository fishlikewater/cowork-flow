# unified-runner-bootstrap Spec

## Behavior

- `.cowork-flow/scripts/run.py <command> [args...]` maps cowork-flow commands to existing Python scripts.
- `run.py python [python-args...]` executes the selected current Python interpreter with the supplied arguments.
- `run.py` supports existing command aliases: `get-context/get_context`, `get-developer/get_developer`, `init-developer/init_developer`, `add-session/add_session`, and `agent-team/agent_team`.
- `run` and `run.cmd` are bootstrap launchers only: they select a Python 3.8+ interpreter and execute `scripts/run.py` with original arguments.
- Windows must not rely on Bash.

## Acceptance Criteria

- POSIX runner tests still verify Python selection order.
- Windows runner test verifies `run.cmd` contains no command-specific dispatch such as `task.py` labels and forwards to `scripts/run.py`.
- Python runner tests verify command mapping lives in `scripts/run.py`.
- Template package/init/sync behavior still includes both launchers and the new shared runner.
