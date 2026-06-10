# 06-10-party-mode-v2-runtime-board

Describe the proposed behavior change.
# Party Mode V2 Runtime Board Proposal

## Goal

Build Party Mode V2 as a runtime-controlled, host-neutral, multi-agent discussion mode that can run across Codex, Claude Code, and OpenCode without changing existing Party Mode V1.

## User Value

Users get a stronger advisory discussion mode where multiple child agents truly interact through a board, cannot casually concede without evidence, and are monitored by a lightweight moderator that does not rewrite or forward opinions.

## Problem

Current Party Mode is a skill-first advisory roundtable. The moderator collects child-agent opinions, builds a claim table, sends follow-up prompts, and synthesizes the final decision. That is useful for V1, but it is too soft for Party Mode V2.

V2 needs runtime-enforced discussion:

- Multiple child agents communicate through a shared board.
- The moderator monitors and corrects off-topic behavior but does not forward or synthesize opinions.
- Child agents must not concede without evidence-backed reasoning.
- The design must work across Codex, Claude Code, and OpenCode.

## Proposed Change

Add Party Mode V2 as a new runtime-controlled advisory mode:

- Add `party_mode_v2.py` to own board state, round transitions, schema validation, and final reports.
- Add host-neutral next actions so Codex, Claude Code, and OpenCode can execute the same runtime contract.
- Add thin `party-mode-v2` skill/command assets for each supported host.
- Add tests for current-round-only board visibility, anti-shallow-concession validation, multi-agent simulation, and host-neutral docs.

## Non-goals

- Do not change existing `party-mode` V1 behavior.
- Do not let Party Mode V2 satisfy formal Implement or Check workflow gates.
- Do not make Python directly call Codex, Claude Code, or OpenCode host primitives in the first version.
- Do not claim OS-level sandboxing for child agents.

## Key Assumptions

- Existing host adapters already provide enough dispatch/follow-up/wait/list/cancel capability or fallback for V2.
- Python runtime can be the protocol source of truth while the host executes abstract next actions.
- Current-round-only board visibility is enforced by the board API; strict model-memory isolation requires fresh child context per round.
- OpenCode follow-up remains a shim, so V2 must expose manual next-action fallback.

## Development Tasks

- `06-10-party-mode-v2-runtime-foundation`
- `06-10-party-mode-v2-debate-rules-convergence`
- `06-10-party-mode-v2-host-assets-actions`
- `06-10-party-mode-v2-integration-verification`
