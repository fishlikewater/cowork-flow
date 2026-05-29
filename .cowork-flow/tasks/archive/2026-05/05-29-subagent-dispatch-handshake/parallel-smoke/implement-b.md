# Parallel Smoke Implement B

FULL_FLOW_IMPL_B_OK

- role: cowork-implement slice B
- dispatch_id: full-flow-impl-b-20260529
- ack_token: ACK_FULL_FLOW_IMPL_B_20260529
- ack_matched: yes
- python_version: Python 3.12.1
- search_hit_count: 41

## Search command

```powershell
rtk rg -n 'COWORK_ACK|EXECUTE <dispatch_id>|ACK_FULL_FLOW_IMPL_B_20260529|Generic `worker` dispatch is best-effort only' .codex/agents template/.codex/agents .cowork-flow/workflow.md template/.cowork-flow/workflow.md .cowork-flow/tasks/05-29-subagent-dispatch-handshake .cowork-flow/plans/2026-05-29-subagent-dispatch-handshake.md tests
```

## Search first 5 lines

```text
.cowork-flow/workflow.md:14:2. Implement: 主会话用 `spawn_agent` 派发 `cowork-implement`，`fork_turns="none"`，先发 `COWORK_DISPATCH_V1` 信封并等待 `COWORK_ACK`。
.cowork-flow/workflow.md:15:3. Check: 主会话用 `spawn_agent` 派发 `cowork-check`，`fork_turns="none"`，先发 `COWORK_DISPATCH_V1` 信封并等待 `COWORK_ACK`。
.cowork-flow/workflow.md:33:The active task is in progress. Main session dispatches cowork-implement work according to the plan, then cowork-check after integration. Every spawn_agent call uses fork_turns="none" and a COWORK_DISPATCH_V1 envelope. Main session waits for COWORK_ACK, sends EXECUTE with followup_task, verifies child output, lists agents, and closes children.
.cowork-flow/workflow.md:104:        "Return only: COWORK_ACK <dispatch_id> <ack_token>"
.cowork-flow/workflow.md:111:- Use `wait_agent` for `COWORK_ACK <dispatch_id> <ack_token>` before execution.
```

## Commands run

```powershell
rtk python --version
rtk rg -n 'COWORK_ACK|EXECUTE <dispatch_id>|ACK_FULL_FLOW_IMPL_B_20260529|Generic `worker` dispatch is best-effort only' .codex/agents template/.codex/agents .cowork-flow/workflow.md template/.cowork-flow/workflow.md .cowork-flow/tasks/05-29-subagent-dispatch-handshake .cowork-flow/plans/2026-05-29-subagent-dispatch-handshake.md tests
```
