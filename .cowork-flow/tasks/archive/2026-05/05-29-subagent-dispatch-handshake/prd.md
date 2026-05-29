# Harden subagent dispatch recognition

## Goal

Spawned cowork-flow subagents must identify their own delegated task before doing work, so parallel dispatches do not lose, mix, or execute another agent's assignment.

## Requirements

- Keep the model lightweight: no old agent-team state machine, no new coordinator daemon, no broad runtime rewrite.
- Every fixed-agent dispatch must include a machine-readable dispatch envelope with task path, role, context path, and acknowledgement token.
- A spawned agent must acknowledge the matching dispatch before execution.
- Main-session workflow must treat missing or mismatched acknowledgement as not dispatched, requiring retry or close-and-respawn.
- Fixed `cowork-*` agent definitions must prioritize the dispatch envelope over bootstrap/no-task context.
- Fixed-agent dispatch must reject role mismatches, so `cowork-check` cannot execute a `cowork-implement` dispatch.
- Generic `worker` dispatch must be marked best-effort and remain outside formal execution paths.
- The root and template copies must stay in sync.
- A full-flow smoke must exercise the path from PRD to development plan to parallel fixed-agent execution.
- Parallel smoke agents must prove isolation with distinct `dispatch_id`, `agent_type`, `role`, and `ack_token` values.

## Acceptance

- Tests assert fixed agent definitions require `COWORK_DISPATCH_V1`, `COWORK_ACK`, and dispatch-id validation.
- Tests assert `subagent init` emits `agentType`, `dispatchReliability`, `expectedAck`, `dispatchMessage`, and `executeMessage`.
- Tests assert workflow docs describe the ACK gate and mismatch handling.
- Tests assert generic `worker` dispatch is documented as best-effort only.
- Existing subagent safety checks still pass.
- A real parallel smoke starts at least two built-in `cowork-*` subagents with `fork_turns="none"`, receives matching ACKs, sends matching `EXECUTE <dispatch_id>` follow-ups, and records whether each agent completed its own assigned slice.
