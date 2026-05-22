# unified-runner-bootstrap

## Problem

`run` and `run.cmd` both implement command dispatch, Python version checks, script mapping, and error messages. The Windows batch implementation is fragile and has failed in practice due to quoting/encoding/argument handling.

## Proposed Change

Keep platform bootstrap files for selecting Python, but move command dispatch into one Python runner: `.cowork-flow/scripts/run.py`. The POSIX `run` and Windows `run.cmd` files should only select Python 3.8+ and execute the shared Python runner with the original arguments.

## Scope

- Add a shared Python command dispatcher.
- Simplify template and project `run` / `run.cmd` launchers.
- Update tests and docs that describe the runner entrypoint behavior.
- Keep both launcher files for platform ergonomics; do not require Node or Bash on Windows.
