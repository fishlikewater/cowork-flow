# Slim Claude memory instructions

## Goal

Keep Claude Code memory instructions concise and move runtime-contract assertions to real source-of-truth files.

## Requirements

- `CLAUDE.md` and `template/CLAUDE.md` should no longer duplicate Claude Code asset lists or runtime-context dispatch protocol.
- Keep `@AGENTS.md` and the cowork-flow managed marker block.
- Keep tests proving Claude Code assets and runtime-context protocol exist in `.claude/agents`, `.claude/commands`, `.claude/settings.json`, hooks, adapters, and specs.
- Do not remove or weaken the actual runtime-context contract.

## Verification

- Focused host/agent tests pass.
- `git diff --check` passes.
