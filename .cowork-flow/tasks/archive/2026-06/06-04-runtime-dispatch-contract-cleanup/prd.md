# Runtime Dispatch Contract Cleanup

## Goal

Replace legacy formal dispatch contracts with the runtime-context dispatch
contract in live docs, specs, adapters, skills, agents, commands, and tests.

## Scope

- `.cowork-flow/spec/`
- `.cowork-flow/adapters/`
- `.agent/skills/`, `.claude/skills/`
- `.codex/agents/`, `.claude/agents/`, `.opencode/agents/`
- `.claude/commands/`, `.opencode/commands/`
- `README.md`, `AGENTS.md`, `CLAUDE.md`, template mirrors
- Tests that assert contract shape or legacy string absence

## Non-goals

- No changes to historical archive files.
- No runtime helper implementation beyond what previous tasks provide.

## Acceptance Criteria

- The former prompt-boundary skills are removed from root, Claude Code, and template.
- `start` describes main-session-only startup and runtime-context fixed-agent
  dispatch.
- Adapter schema and adapter YAML declare runtime-context transport instead of
  ACK/EXECUTE fields.
- Live code/docs/templates/tests exclude the legacy prompt envelope,
  delegation envelope, acknowledgement, and execute-followup markers outside
  historical archive directories.

## Verification

- `python -m unittest tests.test_host_adapters tests.test_cowork_agents tests.test_workflow_parallel_sessions tests.test_no_legacy_template_paths`
- Legacy string absence check excluding `.cowork-flow/changes/archive/` and
  `.cowork-flow/tasks/archive/`
- `git diff --check`
