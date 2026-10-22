---
name: cowork-flow-bootstrap
description: Use only when a repository has no .cowork-flow/ runtime and the user wants to start or continue structured development work — guides installing cowork-flow into the project. Do not use when .cowork-flow/ exists; the project's own cowork-flow Skill owns that case.
---

# Cowork Flow Bootstrap

This Skill is the plugin-side bootstrap. It applies to repositories that have no
`.cowork-flow/` runtime yet. Once `.cowork-flow/` exists, stop and use the
project's own Skills: after init, `./.cowork-flow/run task next` and the project's
skill copies are authoritative, not this Skill.

## Decide first

Check the repository root for the runtime directory `.cowork-flow/` (or the
workflow entry `./.cowork-flow/run`).

## No runtime: offer the install

Tell the user this repository has no cowork-flow runtime, then offer (replace
`<host>` with the host you are running in: `codex`, `claude-code`, `opencode`,
`zcode`, `qoder`, `kimi-code`, or `dsh`):

```bash
npx cowork-flow project init --host <host>
```

The default artifact language is `zh-CN`. When the user asks for English task or
plan artifacts, append `--language en-US`. An existing
`.cowork-flow/config.yaml` remains authoritative.

After init the project carries its own Skills (`.agents/skills/`), the task
runtime (`.cowork-flow/`), and the workflow entry `./.cowork-flow/run task next`.
Resume the work through that entry.

## Never

- Do not reproduce lifecycle rules, gates, or a second workflow document here.
- Do not hand-create `.cowork-flow/` or copy files out of the plugin payload.
- Do not run task lifecycle commands: without a project runtime there is no task
  to advance.
