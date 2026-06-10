# Party Mode V2 Runtime Board Design

## Summary

Party Mode V2 is a new advisory mode beside existing Party Mode V1. It replaces moderator-mediated claim forwarding with a runtime-controlled shared board. Child agents use board API commands to view current-round posts, publish positions, and respond to disagreement. The moderator only monitors status, executes host actions, and writes off-topic warnings.

The source detailed design is:

```text
.cowork-flow/tasks/06-10-party-mode-v2-runtime-board-design/design.md
```

## Architecture

```text
party_mode_v2.py
  -> owns config, state, board, schema validation, convergence
  -> writes .cowork-flow/.runtime/party-mode-v2/<discussion_id>/
  -> emits host-neutral next_actions

Host Adapter / Moderator
  -> translates next_actions into Codex, Claude Code, or OpenCode primitives
  -> does not forward or synthesize opinions

Child Agents
  -> call view/post/respond/wait
  -> communicate through current-round board only
```

## Tasks

1. Runtime Foundation
   - Config getters.
   - `init`, `view`, `monitor`.
   - Current-round-only board view.
   - Host-neutral `next_actions`.

2. Debate Rules And Convergence
   - `post`, `respond`, `advance`, `finalize`.
   - Validation for `maintain`, `revise`, `concede`.
   - Max-rounds-unconverged reports.

3. Host Assets And Actions
   - Action schema and board spec.
   - `party-mode-v2` skill mirrors.
   - Claude/OpenCode assets.
   - Workflow/spec advisory boundary.

4. Integration Verification
   - Multi-agent simulation.
   - Moderator-boundary tests.
   - Host-neutral checks.
   - README drift fix if still present.

## Key Decisions

- V2 is new; V1 remains unchanged.
- Runtime controls protocol but does not call host primitives directly.
- Host-neutral actions keep Codex, Claude Code, and OpenCode compatible.
- Current-round-only strictness defaults to fresh child context per round.
- Shallow concession is a runtime validation error.
