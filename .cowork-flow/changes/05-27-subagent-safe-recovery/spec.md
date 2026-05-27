# Subagent safe recovery spec

## 1. Start preflight must be conservative

`.agent/skills/start` must describe a preflight before full context loading:

- Classify the current message as `MAIN_SESSION`, `SUBAGENT_SESSION`, or `UNCERTAIN`.
- Treat explicit user override phrases such as `not a subagent`, `main agent`, or `run full cowork-flow start` as `MAIN_SESSION`.
- Treat role-dispatch patterns such as `you are explorer`, `you are worker`, `only investigate`, `do not modify files`, `Assignment ID`, `dispatched worker`, or explicit report-format instructions as `SUBAGENT_SESSION`.
- Treat `UNCERTAIN` as subagent-safe: do not run full project resume, do not activate tasks, and read only prompt-named files until a main-session override appears.

## 2. Execution context must be explicit

The runtime must support these modes:

- `none`: default for unscoped commands, no coordinator mutation authority.
- `coordinator`: explicit coordinator authority.
- `worker`: assignment-scoped agent-team worker authority.
- `subagent`: generic subagent authority.

Unscoped execution must not imply coordinator authority.

## 3. Agent-team authority gates

The following commands require coordinator context:

- `next`
- `record-spawn`
- `record-result`
- `record-review`
- `collect`
- `retry`
- `complete`

The following command requires worker context:

- `worker-report`

Worker and generic subagent contexts must be rejected for coordinator-only commands. Coordinator and unscoped contexts must be rejected for `worker-report`.

`prepare` may run unscoped for compatibility, but it must emit `agent-team/coordinator.context.json` with `mode=coordinator` and `taskDir` for subsequent coordinator commands.

## 4. Generic subagent scoped recovery

A new `subagent` command must provide:

- `subagent init --title <title> [--role <role>] [--source <source>] [--goal <goal>] [--allowed-context <path>]...`
- `subagent status <subagent-id>`
- `subagent update <subagent-id> --status <status> [--note <note>]`

`subagent init` must create:

- `.cowork-flow/subagents/<id>/context.json`
- `.cowork-flow/subagents/<id>/brief.md`
- `.cowork-flow/subagents/<id>/status.json`
- `.cowork-flow/subagents/<id>/events.jsonl`

The context file must use `mode=subagent` and must be accepted by `run --context-file <context.json> resume`.

Generic subagent resume must output only subagent-local scope: title, role, goal, allowed context, forbidden coordinator actions, current status, and recent events. It must not output the main `RESUME CHECKLIST`.

## 5. Completion semantics

Generic subagent status values are:

- `active`
- `success`
- `needs_context`
- `blocked`

A stopped generic subagent should leave either success evidence, a missing-context request, or a blocker note in `status.json` and `events.jsonl`.

## 6. Doctor verification

`doctor --subagent-safety` must verify the local safety shape:

- start skill contains subagent-safe preflight guidance.
- agent-team coordinator commands reject missing coordinator context.
- worker resume and generic subagent resume avoid main resume output.
- root and template safety-critical files are present.
