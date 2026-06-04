# Runtime Session Subagent Dispatch Design

## Overview

Formal subagent dispatch moves from prompt classification to runtime identity.
The parent creates a runtime context before spawning the child. The child hook or
plugin resolves that context before injecting workflow state, binds the host's
real child session key, and injects only subagent-scoped state.

This makes the first screen deterministic even for a weak child prompt. The
child no longer has to infer whether it is a subagent from `AGENTS.md`, skill
descriptions, natural language, or legacy envelope markers.

## Assumptions

- Current Codex `spawn_agent` has no custom env or metadata field in the local
  tool schema; the verified baseline transport is prompt-carried
  `cowork_runtime_context_id`.
- Claude Code and OpenCode must use the same runtime contract. Their adapter
  files declare whether runtime context is transported by prompt, env, metadata,
  or a host plugin. Until verified otherwise, prompt transport is the safe
  baseline.
- Runtime context is transient. Durable implementation evidence remains in task
  files, reports, tests, or git diff, not in `.runtime`.

## Runtime Files

### Subagent Context

Parent creates `.cowork-flow/.runtime/subagents/<runtime_context_id>.json`:

```json
{
  "schema_version": 2,
  "runtime_context_id": "rtx_20260604_001",
  "scope": "subagent",
  "host": "codex",
  "adapter": "codex.spawn_agent",
  "agent_type": "cowork-implement",
  "role": "implement",
  "task_dir": ".cowork-flow/tasks/06-04-runtime-session-subagent-dispatch",
  "parent_context_key": "codex_<main-thread-id>",
  "transport": {
    "kind": "prompt",
    "key": "cowork_runtime_context_id"
  },
  "assignment": {
    "title": "Implement runtime-context dispatch",
    "goal": "Apply the plan slice without starting or resuming the main workflow.",
    "allowed_context": [],
    "expected_output": "Files changed, validation commands, and blockers."
  },
  "authority": {
    "may_start_task": false,
    "may_resume_main": false,
    "may_archive": false,
    "may_commit": false,
    "may_spawn": false
  },
  "status": "pending",
  "created_at": "2026-06-04T00:00:00Z",
  "bound_context_key": null,
  "closed_at": null
}
```

### Logical Subagent Session

At creation time the parent also writes
`.cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json`:

```json
{
  "schema_version": 2,
  "scope": "subagent",
  "runtime_context_id": "rtx_20260604_001",
  "active_task_path": ".cowork-flow/tasks/06-04-runtime-session-subagent-dispatch",
  "platform": "codex",
  "status": "pending_bind",
  "last_seen_at": "2026-06-04T00:00:00Z"
}
```

### Bound Host Session

When the child hook/plugin sees `cowork_runtime_context_id`, it resolves the
real host context key and writes
`.cowork-flow/.runtime/sessions/<host_context_key>.json`:

```json
{
  "schema_version": 2,
  "scope": "subagent",
  "runtime_context_id": "rtx_20260604_001",
  "active_task_path": ".cowork-flow/tasks/06-04-runtime-session-subagent-dispatch",
  "platform": "codex",
  "status": "bound",
  "last_seen_at": "2026-06-04T00:00:00Z"
}
```

The main session remains a separate `.runtime/sessions/<main_context_key>.json`
with `scope: "main"`.

## Hook Resolution Order

Hooks/plugins resolve state in this order:

1. Find `cowork_runtime_context_id` from host metadata, env, structured hook
   input, then prompt text.
2. If found, load `.runtime/subagents/<id>.json`.
3. Validate that the context exists, is active or pending, and belongs to a
   supported host/adapter.
4. Bind the current host context key to the runtime context.
5. Inject subagent-scoped state and skip main active-task lookup.
6. If no runtime id is present, load the main session state normally.

Invalid runtime ids fail closed: the hook emits a subagent-context error and
does not fall back to legacy prompt protocols.

## Injected Child State

A bound child receives state shaped like:

```text
<workflow-state>
Status: delegated_subtask
Source: runtime-context:<runtime_context_id>
Task: .cowork-flow/tasks/<task>
Agent: cowork-implement
Scope: subagent
Do not run start/resume/task start/archive/commit/spawn.
Execute the assignment from runtime context.
</workflow-state>
```

The child does not receive the main no-task breadcrumb, main start guidance, or
legacy dispatch digest.

## Dispatch Lifecycle

1. Main session runs a new runtime init path, for example:

   ```bash
   ./.cowork-flow/run subagent init --agent-type cowork-implement --task-dir <task> --goal <goal>
   ```

2. The command returns `runtime_context_id` and the transport payload.
3. Main session dispatches the host child with fresh context. For prompt
   transport, the first line is only:

   ```text
   cowork_runtime_context_id: <runtime_context_id>
   ```

4. The child hook/plugin binds the host session and injects the assignment.
5. Main session waits for the child through the host wait primitive.
6. Main session validates outputs with files/tests, then closes the child.
7. Close removes `.runtime/sessions/<host_context_key>.json` and
   `.runtime/sessions/subagent_<runtime_context_id>.json`; it also deletes or
   marks `.runtime/subagents/<runtime_context_id>.json` closed. A TTL GC removes
   stale pending contexts.

There is no ACK/EXECUTE gate. The hook binding is the dispatch acceptance event.

## Host Adapter Sync

Adapters add runtime context fields and remove legacy contract fields:

```yaml
capabilities:
  runtimeContextDispatch: native
  runtimeContextBinding: native
  runtimeContextCleanup: native
runtimeContext:
  transport: prompt
  promptKey: cowork_runtime_context_id
  envKey: COWORK_FLOW_RUNTIME_CONTEXT_ID
  metadataKey: cowork_runtime_context_id
contracts:
  dispatch: RUNTIME_CONTEXT_DISPATCH_V2
  leafExecutor: true
fallback:
  whenRuntimeContextMissing: fail_closed
```

Codex currently uses `transport: prompt` because the local `spawn_agent` schema
does not expose custom env/metadata. Claude Code and OpenCode use the same
schema; their transport stays `prompt` unless a verified host capability is
added.

## Skill Changes

- Delete the former prompt-boundary skill from `.agent/skills/` and `.claude/skills/`
  plus template mirrors. Runtime context replaces prompt classification for
  subagent detection.
- Keep `.agent/skills/start` and `.claude/skills/start`, but make it explicitly
  main-session-only. It should describe main workflow loading and fixed-agent
  dispatch through runtime context. It should not contain a delegated prompt
  classifier.
- OpenCode does not have `.agent/skills`, but its commands/agents must mirror
  the same main-vs-subagent semantics.

## Spec And Test Migration

- Replace `.cowork-flow/spec/subagent-dispatch.md` with runtime-context
  dispatch semantics or rename it to `.cowork-flow/spec/runtime-context-dispatch.md`.
- Delete `.cowork-flow/spec/delegation-envelope.md`.
- Update `.cowork-flow/spec/entry-contract.md` so it no longer classifies
  delegated fixed agents by prompt marker.
- Update `.cowork-flow/spec/registry.json`, hook default registries, and
  OpenCode plugin default registries to reference only live contracts.
- Rewrite tests that currently assert legacy markers so they instead assert
  runtime context creation, binding, cleanup, and absence of legacy protocol
  strings.

## Why This Prevents First-screen Capture

Prompt labels and weak heuristics run after the model has already received some
text. Runtime binding runs in the hook/plugin before workflow state is injected.
The first meaningful workflow state the child sees is therefore subagent-scoped.
If the hook cannot bind runtime context, formal dispatch fails closed instead of
letting bootstrap decide.
