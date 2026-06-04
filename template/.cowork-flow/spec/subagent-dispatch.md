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

## Runtime Context

Before spawning a formal child, the main session creates:

- `.cowork-flow/.runtime/subagents/<runtime_context_id>.json`
- `.cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json`

The child receives the runtime id through the host adapter transport. The
baseline prompt transport is:

```text
cowork_runtime_context_id: <runtime_context_id>
```

Hosts may use env or metadata transport only after the adapter declares and
verifies that support.

## Binding Gate

The child hook or plugin resolves `cowork_runtime_context_id` before injecting
workflow state. A valid context is bound to the host child session under
`.cowork-flow/.runtime/sessions/<host_context_key>.json` with
`scope: "subagent"`.

Binding is the formal dispatch acceptance event. If binding fails, the child
must receive fail-closed subagent state and must not run main-session
start/resume, task activation, archive, commit, or agent coordination.

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
