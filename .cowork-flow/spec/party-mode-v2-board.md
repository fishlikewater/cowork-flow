# Party Mode V2 Board Contract

Party Mode V2 is an advisory runtime-board discussion mode. It is separate
from formal `cowork-*` dispatch and cannot satisfy Implement or Check.

## Runtime Ownership

The Python runtime owns:

- discussion id,
- agent roster,
- current round,
- board state,
- schema validation,
- host-neutral next actions,
- final reports.

The runtime does not call Codex, Claude Code, or OpenCode primitives directly.

## Board Visibility

The runtime may store full board history under `.cowork-flow/.runtime`, but
child-visible `view` output must include only the current round.

Child agents must use runtime commands to read and write board state. They
must not receive moderator-summarized child opinions.

## Position Changes

Children respond to disagreement with one of:

- `maintain`
- `revise`
- `concede`

Each response must include evidence or reasoning required by the runtime.
Evidence-free agreement and unsupported rebuttal are invalid.

## Moderator Boundary

The moderator monitors runtime status, executes host-neutral next actions, and
records drift warnings. The moderator does not forward, rewrite, summarize, or
synthesize child opinions.
