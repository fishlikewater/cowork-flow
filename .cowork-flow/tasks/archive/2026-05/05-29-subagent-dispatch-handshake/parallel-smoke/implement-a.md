# Parallel Smoke Implement A

FULL_FLOW_IMPL_A_OK

dispatch_id: full-flow-impl-a-20260529
ack_token: ACK_FULL_FLOW_IMPL_A_20260529
ack_matched: yes
agent_type: cowork-implement
role: implement

## Command Evidence

- `rtk python --version`
  - output: `Python 3.12.1`
- `rtk rg -n "COWORK_DISPATCH_V1|agent_type|ACK_FULL_FLOW_IMPL_A_20260529" .codex/agents .cowork-flow/workflow.md .cowork-flow/tasks/05-29-subagent-dispatch-handshake .cowork-flow/plans/2026-05-29-subagent-dispatch-handshake.md tests`
  - hit_count: 33

## Search First 5 Lines

```text
.cowork-flow/workflow.md:14:2. Implement: 主会话用 `spawn_agent` 派发 `cowork-implement`，`fork_turns="none"`，先发 `COWORK_DISPATCH_V1` 信封并等待 `COWORK_ACK`。
.cowork-flow/workflow.md:15:3. Check: 主会话用 `spawn_agent` 派发 `cowork-check`，`fork_turns="none"`，先发 `COWORK_DISPATCH_V1` 信封并等待 `COWORK_ACK`。
.cowork-flow/workflow.md:33:The active task is in progress. Main session dispatches cowork-implement work according to the plan, then cowork-check after integration. Every spawn_agent call uses fork_turns="none" and a COWORK_DISPATCH_V1 envelope. Main session waits for COWORK_ACK, sends EXECUTE with followup_task, verifies child output, lists agents, and closes children.
.cowork-flow/workflow.md:93:    agent_type="cowork-implement",
.cowork-flow/workflow.md:96:        "COWORK_DISPATCH_V1\n"
```
