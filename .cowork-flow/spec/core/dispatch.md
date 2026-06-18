# Runtime-context subagent dispatch

Formal `cowork-*` dispatch is identified by runtime context, not by prompt
classification or a prompt handshake.

## Scope

- Formal dispatch uses `cowork-research`, `cowork-implement`, or `cowork-check`.
- The main session owns dispatch, wait, acceptance, and closeout.
- Child agents are leaf executors and must not dispatch, wait for, list, or
  cancel other agents.
- Generic `worker`, `default`, or `explorer` dispatch is advisory only and
  cannot satisfy formal Implement or Check completion.

## Advisory Party Mode

Party Mode discussion children are advisory leaf executors. They use fresh child contexts for evidence gathering, disagreement surfacing, risk review, and acceptance-signal review. They cannot mutate task status, write code, archive, commit, or coordinate other agents. Their output cannot satisfy formal Implement or Check completion.

The `party-mode` skill owns round limits, continuation gates, stop gates, and output schemas. This document remains the formal `cowork-*` dispatch protocol source.

Party Mode V2 discussion children are also advisory leaf executors. The `party-mode-v2` entrypoint delegates discussion state, current-round board visibility, schema validation, drift warnings, round limits, and final reports to the Party Mode V2 runtime board controller. The runtime emits host-neutral next actions; it does not change the formal `cowork-*` dispatch protocol and does not satisfy Implement or Check completion.

## Runtime Context

Before spawning a formal child, the main session creates DB runtime rows:

- `runtime_context`: one row keyed by `<runtime_context_id>`
- `runtime_session`: one logical row keyed by `subagent_<runtime_context_id>`

Formal dispatch no longer writes or reads compatibility JSON runtime files.
`runtime_context` and `runtime_session` in the DB are the only active state
authority.

For direct formal dispatch with `--execution-task-dir`, `subagent init`
resolves the Flow task id, stores the resolved `cowork-*` agent type in
`runtime_context`, and suggests a host context key for binding. `agent_run`
rows are no longer written by the runtime; the table remains compatibility-only
and must not be treated as the active dispatch authority.

The child receives the runtime id and host context key through the host adapter
transport. The baseline prompt transport is:

```text
cowork_runtime_context_id: <runtime_context_id>
cowork_host_context_key: <host_context_key>
```

Hosts may use env or metadata transport only after the adapter declares and
verifies that support. If `subagent init` emits a suggested host context key,
the parent may use that key unless the host adapter has a stronger stable child
session key.

## Binding Gate

The child hook or plugin may resolve `cowork_runtime_context_id` early and bind
the runtime context before injecting workflow state. Because not every host can
prove model-before-execution binding, the child must run this first-step shim
before formal work:

```text
./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>
```

A valid context is bound to the host child session as a `runtime_session` DB row
keyed by `<host_context_key>` with `scope: "subagent"`. Binding the same runtime
id to the same key is idempotent; binding it to a different key must fail.

Verified binding is the formal dispatch acceptance event. The parent must check
that the `runtime_context` row has `status: "bound"` and
`bound_context_key: "<host_context_key>"` before accepting child output. If
binding fails, the child must receive fail-closed subagent state and must not run
main-session start/resume, task activation, archive, commit, or agent
coordination.

## Return Acceptance And Closeout

- Wait for the child result with the adapter wait primitive.
- Confirm no stray running children with the adapter list primitive.
- Verify the child report by checking files, commands, and results; do not
  trust completed text alone.
- After completion or failure, close the child with the adapter cancel/close
  primitive and clean the runtime context sessions.
- The child remains a leaf executor and must not dispatch, wait for, list, or
  cancel other agents.

## Fan-out Family Helpers

Fan-out parents may prepare child contexts in one CLI step:

```text
./.cowork-flow/run subagent spawn-family <parent-task> --agent-type cowork-implement
```

`spawn-family` creates one runtime context per eligible child task. It is
idempotent for active `(task_id, agent_type)` runtime contexts and returns JSON
for the host adapter to dispatch. It does not call host-specific child
primitives by itself.

The main session can inspect family progress with:

```text
./.cowork-flow/run subagent check-family <parent-task>
```

`check-family` returns JSON buckets for pending, done, and failed children. It
exits `0` only when all children are done and no failed run remains. Task status
transitions still go through `task.py`; family helpers do not complete or review
tasks directly.

## Cleanup

Closing a child removes the bound and logical `runtime_session` DB rows. The
subagent `runtime_context` row is marked `closed` until DB maintenance removes
it after the configured retention window.
