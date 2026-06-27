# Audit host path portability

## Goal

Fix Claude Code hook command portability so workflow-state injection works even
when Claude Code does not run hook commands from the project root.

## Scope

- Audit host adapter and hook command references for root/template drift.
- Update Claude Code hook command configuration to anchor `.cowork-flow/run`
  through `CLAUDE_PROJECT_DIR`.
- Update Claude Code command, skill, and fixed-agent bind examples so formal
  subagent init/bind and workflow commands do not depend on the current working
  directory.
- Ensure host asset text describes DB `runtime_context` as the active state
  authority, not removed `.cowork-flow/.runtime/subagents/*.json` files.
- Keep root and template Claude assets synchronized.
- Add regression coverage for the command string and executable behavior.

## Acceptance Criteria

1. `.claude/settings.json` and `template/.claude/settings.json` use a
   project-root anchored command for `UserPromptSubmit` and `SessionStart`.
2. The Claude hook command test proves the configured command is not a bare
   Python invocation and can execute after resolving the project-root prefix.
3. Claude Code command/agent/skill assets and `subagent init --host
   claude-code` emit project-root anchored workflow and subagent init/bind
   commands.
4. Claude/OpenCode fixed-agent assets describe the DB `runtime_context` row as
   the active state authority and do not reference legacy runtime JSON files.
5. A scan of supported host hook/command config finds no additional actionable
   root/template drift.
6. Focused Python tests, `git diff --check`, and subagent safety doctor pass.

## Relevant Files

- `.claude/settings.json`
- `template/.claude/settings.json`
- `tests/test_claude_hooks.py`
- `tests/test_host_adapters.py`
- `tests/test_cowork_agents.py`
- `tests/test_subagent_dispatch.py`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/doctor.py`
- `.cowork-flow/spec/reference/adapters/capabilities.md`
- `.claude/skills/start/SKILL.md`
- `.claude/skills/continue/SKILL.md`
- `.claude/skills/finish-work/SKILL.md`
- `.claude/skills/writing-plans/SKILL.md`
- `.claude/skills/party-mode-v2/SKILL.md`

## Verification

- `.cowork-flow/run.cmd python -m pytest tests/test_claude_hooks.py tests/test_host_adapters.py tests/test_cowork_agents.py tests/test_subagent_dispatch.py tests/test_no_legacy_template_paths.py -q`
- `.cowork-flow/run.cmd doctor --host-adapters`
- `.cowork-flow/run.cmd doctor --subagent-safety`
- `git diff --check`
