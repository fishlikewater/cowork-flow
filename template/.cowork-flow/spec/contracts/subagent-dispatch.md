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

Party Mode discussion children are advisory leaf executors. They communicate through the `party-v2` runtime board for evidence gathering, disagreement surfacing, risk review, and acceptance-signal review. They cannot mutate task status, write code, archive, commit, or coordinate other agents. Their output cannot satisfy formal Implement or Check completion.

The public `party-mode` skill delegates discussion state, current-round board visibility, schema validation, drift warnings, round limits, and final reports to the `party-v2` runtime board controller. The runtime emits host-neutral next actions; it does not change the formal `cowork-*` dispatch protocol and does not satisfy Implement or Check completion. This document remains the formal `cowork-*` dispatch protocol source.

## Runtime Context

Before spawning a formal child, the main session creates:

- `.cowork-flow/.runtime/subagents/<runtime_context_id>.json`
- `.cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json`

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

A valid context is bound to the host child session under
`.cowork-flow/.runtime/sessions/<host_context_key>.json` with
`scope: "subagent"`. Binding the same runtime id to the same key is idempotent;
binding it to a different key must fail.

Verified binding is the formal dispatch acceptance event. The parent must check
that `.cowork-flow/.runtime/subagents/<runtime_context_id>.json` has
`status: "bound"` and `bound_context_key: "<host_context_key>"` before accepting
child output. If binding fails, the child must receive fail-closed subagent state
and must not run main-session start/resume, task activation, archive, commit,
or agent coordination.

## Return Acceptance And Closeout

- Wait for the child result with the adapter wait primitive.
- Confirm no stray running children with the adapter list primitive.
- Verify the child report by checking files, commands, and results; do not
  trust completed text alone.
- After completion or failure, close the child with the adapter cancel/close
  primitive and clean the runtime context sessions.
- The child remains a leaf executor and must not dispatch, wait for, list, or
  cancel other agents.

## Cleanup

Closing a child removes:

- `.cowork-flow/.runtime/sessions/<host_context_key>.json`
- `.cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json`

The subagent context is deleted or marked `closed` until runtime garbage
collection removes it.
