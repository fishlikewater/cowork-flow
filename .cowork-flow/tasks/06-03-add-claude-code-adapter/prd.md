# Add Claude Code adapter

## Goal

Add Claude Code as a first-class host platform alongside Codex and OpenCode,
using the existing host-neutral adapter architecture.

## Scope

- Add root and template Claude Code assets under `.claude/`.
- Add root and template `.cowork-flow/adapters/claude-code/adapter.yaml`.
- Update platform selection, init/sync filtering, README, and tests.
- Keep workflow host-neutral.
- Do not change Codex/OpenCode behavior beyond shared platform lists.

## Acceptance

- `cowork-flow init --platform claude-code` copies `.claude/` assets and the
  Claude Code adapter only.
- `--platform all` includes Codex, OpenCode, and Claude Code assets.
- Claude Code fixed agents encode `COWORK_DISPATCH_V1`,
  `COWORK_DELEGATION_V1`, `COWORK_ACK`, `EXECUTE <dispatch_id>`, and leaf
  executor limits.
- Existing Codex and OpenCode tests still pass.

## Verification

- `npm test`
- `python -m unittest discover -s tests -p test_host_adapters.py`
- `python -m unittest discover -s tests -p test_cowork_agents.py`
- `python .cowork-flow/scripts/doctor.py --host-adapters`
- `git diff --check`
