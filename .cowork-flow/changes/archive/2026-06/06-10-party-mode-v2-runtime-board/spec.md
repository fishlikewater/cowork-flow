# Party Mode V2 Runtime Board Spec

## Requirements

### Runtime Ownership

- Party Mode V2 MUST be controlled by a Python runtime controller.
- The runtime MUST own discussion state, board files, round transitions, schema validation, and final report generation.
- The runtime MUST write text files using UTF-8.

### V1 Compatibility

- Existing `party-mode` behavior MUST NOT be changed.
- V2 MUST use separate skill/command entrypoints.

### Multi-Agent Board

- V2 MUST support at least three child agents.
- Child agents MUST communicate through board API commands.
- The moderator MUST NOT forward, summarize, rewrite, or synthesize child opinions for other child agents.

### Current-Round Visibility

- Child-visible board views MUST include only the current round.
- Historical rounds MAY be stored in private runtime state for audit and final reports.
- Responses targeting non-current-round posts MUST be rejected.

### Evidence-Backed Position Changes

- `concede` MUST require accepted evidence and an explanation of why the previous position failed.
- `revise` MUST require accepted and rejected parts.
- `maintain` MUST require counter evidence or counter reasoning.
- Runtime MUST reject shallow or unsupported responses.

### Host Neutrality

- Runtime MUST output host-neutral next actions.
- Shared workflow/spec docs MUST NOT name Codex, Claude Code, or OpenCode primitives except in adapter-specific assets.
- Codex, Claude Code, and OpenCode MUST be supported through their existing adapter capability model or documented fallback.

### Max Rounds

- `party_mode_v2.max_rounds` MUST be configurable through `.cowork-flow/config.yaml`.
- When max rounds are reached without convergence, runtime MUST output pro/con positions, evidence, changed positions, maintained positions, unresolved disagreements, and stop reason.

## Non-Requirements

- V2 does not satisfy formal Implement or Check workflow gates.
- V2 does not mutate task status, archive tasks, record sessions, commit, or push.
- V2 does not provide OS-level filesystem isolation in the first version.
