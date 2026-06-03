# Fix Claude Code skill loading

## Goal

Align Claude Code adapter assets with official Claude Code project loading:
Claude Code does not auto-load `.agent/skills`; it loads `CLAUDE.md`,
`.claude/agents`, and project skills under `.claude/skills`.

## Scope

- Update root and template `CLAUDE.md` to import `AGENTS.md` explicitly.
- Add root and template `.claude/skills` wrappers for cowork-flow workflow
  skills that Claude Code should discover.
- Update Claude Code adapter metadata from command-focused skill loading to the
  official `.claude/skills` surface.
- Keep existing `.agent/skills` for Codex and shared template users.
- Update README and tests to reflect host-specific skill loading.

## Acceptance

- Claude Code assets do not rely on automatic `.agent/skills` loading.
- `CLAUDE.md` explicitly imports `AGENTS.md`.
- Init, sync, package, and host-adapter tests cover `.claude/skills`.
- Existing Codex and OpenCode behavior remains unchanged.
