---
name: party-mode
description: Use when the user manually requests Party Mode or a runtime-controlled multi-agent board discussion where children communicate through board APIs and the moderator only monitors or corrects drift.
---

# Party Mode

Use this skill as the single public Party Mode entrypoint.

The Python runtime is the source of truth for discussion state, board
visibility, validation, round limits, and final reports. Its controller lives at
`scripts/party_mode_v2.py`. The runtime board owns child-visible discussion
state.

## Boundaries

See [SHARED-BOUNDARIES.md](SHARED-BOUNDARIES.md) for common boundaries and advisory limits.

- Party Mode is advisory only. It does not satisfy formal Implement or Check.
- The moderator does not forward, summarize, rewrite, or synthesize child opinions for other child agents.

## Runtime First

Always use the runtime controller:

```text
.cowork-flow/run party-v2 init
.cowork-flow/run party-v2 monitor
.cowork-flow/run party-v2 view
.cowork-flow/run party-v2 post
.cowork-flow/run party-v2 respond
.cowork-flow/run party-v2 advance
.cowork-flow/run party-v2 record-action-result
.cowork-flow/run party-v2 finalize
```

Do not bypass a runtime rejection by manually accepting child output. Runtime
validation failures must be fixed by a corrected child submission or by ending
the discussion.

## Board Rules

- Child agents communicate through the board API.
- Child-visible board output must be current-round only.
- Historical board state is runtime-private and may be used only for audit or final reports.
- Use at least three child agents unless the effective runtime config explicitly allows a different value.
- The runtime emits host-neutral next actions. The active Host Adapter or moderator executes them for Codex, Claude Code, or OpenCode.
- Host action results must be recorded back through `record-action-result` so `agents.json`, audit logs, and action history can prove lifecycle state.

## Child Response Rules

When a child sees a different position, it must choose exactly one:

```text
maintain
revise
concede
```

`concede` requires accepted evidence and why the prior position failed.
`revise` requires the accepted part, rejected part, and updated position.
`maintain` requires counter evidence or counter reasoning.

Unsupported agreement, vague revision, and evidence-free rebuttal are invalid.

## Moderator Role

The moderator may:

- run runtime commands,
- execute host-neutral next actions through the active host,
- record off-topic warnings through the runtime,
- close children only when the runtime asks for closeout,
- show runtime status or final reports to the user.

The moderator must not:

- forward one child opinion to another child,
- create a claim table for child prompts,
- vote-count as validation,
- decide which child is correct.
