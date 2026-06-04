# Subagent dispatch protocol

`COWORK_SUBAGENT_DISPATCH_V1` defines how the main session dispatches fixed `cowork-*` agents. `workflow.md` decides when dispatch belongs in the flow; this spec defines the protocol.

Host-specific tool names stay in `.cowork-flow/adapters/<host>/adapter.yaml`. This document only names required capabilities and contract behavior.

## Scope

- Formal dispatch uses `cowork-research`, `cowork-implement`, or `cowork-check`.
- The main session owns dispatch, wait, acceptance, and closeout.
- Child agents are leaf executors and must not dispatch, wait for, list, or cancel other agents.
- Generic `worker`, `default`, or `explorer` dispatch is soft delegation only and cannot satisfy formal Implement or Check completion.

## Preconditions

Formal dispatch requires:

- `COWORK_ENTRY_CONTRACT_V1` classification is complete.
- The host adapter provides `dispatchSubagent`, `freshChildContext`, `waitChild`, `listChildren`, and `cancelChild`, or follows `fallback.whenRequiredCapabilityMissing`.
- The child first screen contains `COWORK_DISPATCH_V1` or `COWORK_DELEGATION_V1`.
- The child agent is a leaf executor.

## Dispatch Envelope

The main session sends:

```text
COWORK_DISPATCH_V1
dispatch_id: <unique-id>
task_dir: .cowork-flow/tasks/<task>
agent_type: cowork-implement
role: implement
context_file: <context-file>
ack_token: <ack-token>
COWORK_DISPATCH_END

Return only: COWORK_ACK <dispatch_id> <ack_token>
```

## ACK And Execute Gate

- Before execution, wait for `COWORK_ACK <dispatch_id> <ack_token>` with the adapter wait primitive.
- Missing or mismatched `COWORK_ACK` means the task has not been successfully dispatched.
- Only after a matching ACK, send `EXECUTE <dispatch_id>` with the adapter follow-up send primitive.
- If the host cannot send follow-up messages, the formal command or task prompt must contain an equivalent execution gate.
- When sending `EXECUTE <dispatch_id>`, record `execute_sent_at[dispatch_id]`.

## Post-ACK Grace And Health

- Calculate `deadline[dispatch_id] = execute_sent_at[dispatch_id] + post_ack_execution_grace_ms`; do not use a shared/global deadline across children.
- After `EXECUTE <dispatch_id>`, no reply or no `compass` / `status` file while the child loads context is not enough to declare failure.
- Use post-ACK execution grace before judging execution health. Default is `300000` ms and may be changed by adapter runtime config.
- Do not cancel or close a running child only because it has not produced `compass` / `status`.
- If the adapter list primitive still shows the child running, keep waiting through post-ACK execution grace.
- Grace expiry for one `dispatch_id` is a review checkpoint for that child only. It is not a close trigger and not evidence about other children.
- If `progress`, `compass`, or `status` exists, keep waiting. Do not close only because grace expired.
- If the child reports another `dispatch_id`, close that child and redispatch the target task.
- A running child may be closed only after clear wrong-dispatch evidence, child completion, or user cancellation.

## Return Acceptance And Closeout

- Wait for the child result with the adapter wait primitive.
- Confirm no stray running children with the adapter list primitive.
- Verify the child report by checking files, commands, and results; do not trust completed text alone.
- After completion or failure, close the child with the adapter cancel/close primitive.
- The child remains a leaf executor and must not dispatch, wait for, list, or cancel other agents.

## Generic Worker Boundary

- Formal execution uses only `cowork-research`, `cowork-implement`, or `cowork-check`.
- Generic `worker` dispatch is best effort only.
- For Codex default `worker`, `default`, and `explorer`, project-level `.codex/agents/*.toml` prevents first-screen bootstrap, start, or resume drift. This does not change the formal fixed-agent mainline.
- If a generic worker still does not ACK after one retry, close it and do not execute the task.
- Without a hard envelope, advisory or default subagents are `DELEGATED_SOFT`. The first sentence should still say this is a bounded delegated task, not a main-session start request. This natural-language first-screen boundary is not formal dispatch evidence.
- Soft delegation output cannot satisfy formal Implement or Check completion.
