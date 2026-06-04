# Project context generator

## Goal

Generate and refresh `.cowork-flow/project-context.md` so main sessions and
subagents have a compact project map before planning or implementation.

## Scope

- Generate project identity, stack, commands, workflow, host adapters, important
  specs, package scripts, and local constraints.
- Preserve manual notes across refresh.
- Keep generated sections deterministic and concise.
- Avoid replacing authoritative files such as `AGENTS.md`, workflow, and specs.

## Acceptance

1. Refresh creates `.cowork-flow/project-context.md` when missing.
2. Refresh is idempotent.
3. Manual notes survive refresh.
4. Missing optional files do not crash generation.
5. Root/template assets and tests cover generator behavior.

## Verification

- Project-context unit tests for create, refresh, manual-note preservation, and
  missing optional file behavior.
- `git diff --check`
