# 05-27-subagent-safe-recovery

## Why

Subagents can be dispatched by agent-team or by other workflow components. When a child thread loses its initial task context after several turns or compaction, `.agent/skills/start` can pull it into the main coordinator workflow. Prompt wording alone is not a reliable boundary, and unscoped runtime commands currently risk treating missing context as coordinator authority.

## What changes

Add three defensive layers:

1. Start preflight classifies messages as main, subagent, or uncertain. Only clear main-session requests load full project context; subagent-like or uncertain messages use subagent-safe mode.
2. Runtime execution context defaults to no authority. Agent-team coordinator mutations require explicit coordinator context, and worker reporting requires worker context.
3. Generic subagents get durable scoped recovery under `.cowork-flow/subagents/<id>/`, with `context.json`, `brief.md`, `status.json`, and `events.jsonl` so they can recover their own assignment after compaction without loading main coordinator context.

## Non-goals

- Do not require all external dispatching components to add a prompt envelope.
- Do not claim perfect subagent detection when the host exposes no thread identity.
- Do not introduce tmux, external services, or a new agent runtime.

## Success criteria

- No-context `agent-team next`, `record-spawn`, `collect`, `retry`, and `complete` fail with a coordinator-context error.
- Worker context cannot run coordinator mutation commands.
- Coordinator context cannot run `worker-report`.
- `agent-team prepare` emits a coordinator context file for subsequent coordinator commands.
- Generic subagent contexts can be initialized and resumed without full project resume output.
- `start` documents conservative preflight behavior: uncertain messages use subagent-safe mode.
- Root and `template/` scripts and skills stay synchronized.
