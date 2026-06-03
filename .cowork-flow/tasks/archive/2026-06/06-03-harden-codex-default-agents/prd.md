# Harden Codex default agents

## Goal

Prevent Codex default `worker`, `default`, and `explorer` subagents from
being pulled into main-session bootstrap/start/resume behavior when they are
spawned for bounded delegated work.

## Scope

- Add project and template `.codex/agents/*.toml` definitions for:
  - `worker`
  - `default`
  - `explorer`
- Keep existing `cowork-*` fixed-agent behavior intact.
- Make generic worker dispatch payloads include `COWORK_DISPATCH_V1`.
- Improve Codex hook delegated-prompt detection for generic worker signals.
- Update focused tests and diagnostics only where needed.

## Acceptance

- Root and template ship matching `worker.toml`, `default.toml`, and
  `explorer.toml`.
- Generic worker dispatch still reports best-effort reliability but includes
  a hard dispatch marker that hooks can classify before bootstrap.
- Hook treats clear default/explorer/worker delegated prompts as
  `delegated_subtask`.
- Existing fixed-agent safety checks still pass.
- Targeted tests pass on Windows.

## Verification

- `python tests/test_cowork_agents.py`
- `python tests/test_subagent_dispatch.py`
- `python tests/test_codex_hooks.py`
- `python tests/test_workflow_parallel_sessions.py`
- `python .cowork-flow/scripts/doctor.py --subagent-safety`
- `git diff --check`
