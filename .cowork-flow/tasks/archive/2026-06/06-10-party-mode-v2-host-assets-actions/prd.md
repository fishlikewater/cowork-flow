# Party Mode V2 Host Assets And Actions PRD

## Goal

Expose Party Mode V2 across Codex, Claude Code, and OpenCode through host-neutral action contracts, thin skill/command assets, and advisory workflow documentation.

## Scope

Do not implement runtime debate behavior here. This task owns host-facing assets, specs, mirrors, and tests that ensure V2 is available without changing V1.

## Files

- `.cowork-flow/spec/party-mode-v2-actions.schema.json`
- `template/.cowork-flow/spec/party-mode-v2-actions.schema.json`
- `.cowork-flow/spec/party-mode-v2-board.md`
- `template/.cowork-flow/spec/party-mode-v2-board.md`
- `.agents/skills/party-mode-v2/SKILL.md`
- `template/.agents/skills/party-mode-v2/SKILL.md`
- `.claude/skills/party-mode-v2/SKILL.md`
- `template/.claude/skills/party-mode-v2/SKILL.md`
- `.opencode/commands/party-mode-v2.md`
- `template/.opencode/commands/party-mode-v2.md`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `.cowork-flow/spec/subagent-dispatch.md`
- `template/.cowork-flow/spec/subagent-dispatch.md`
- `tests/test_cowork_agents.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_host_adapters.py`
- `test/opencode-plugin.test.js`
- `.cowork-flow/plans/2026-06-10-party-mode-v2-runtime-board.md`
- `.cowork-flow/tasks/06-10-party-mode-v2-runtime-board-design/design.md`

## Requirements

- Add V2 action and board docs/specs.
- Add V2 skill mirrors for `.agents` and `.claude`.
- Add OpenCode command/template assets.
- Keep shared workflow docs host-neutral.
- Preserve existing V1 `party-mode` behavior and tests.
- Do not add adapter capabilities unless implementation proves a hard requirement.

## Acceptance Criteria

- Tests confirm all V2 skill mirrors exist and carry thin runtime-entry wording.
- Tests confirm shared workflow/spec docs mention V2 advisory boundary without Codex/Claude/OpenCode primitive names.
- OpenCode tests confirm the V2 command asset exists and points to runtime board commands.
- Host adapter tests confirm existing capabilities or fallback are sufficient.
- V1 Party Mode tests remain unchanged and pass.
- `rtk git diff --check` passes.

## Verification

```powershell
rtk pytest tests/test_cowork_agents.py tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py
rtk npm test -- test/opencode-plugin.test.js
rtk git diff --check
```
