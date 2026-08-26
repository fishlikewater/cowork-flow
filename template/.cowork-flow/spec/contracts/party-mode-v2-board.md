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

Child-visible views include `empty_state` and `expected_next_action` so an
empty current panel is distinguishable from a stale or broken view.

## Position Changes

Children respond to disagreement with one of:

- `maintain`
- `revise`
- `concede`

Each response must include evidence or reasoning required by the runtime.
Evidence-free agreement and unsupported rebuttal are invalid.

When current-round-only mode is enabled, `post` and `respond` payloads must
include the explicit current round. A child may not respond to its own post,
repeat a target in the same round, or exceed the configured rebuttal target
limit. Stored responses preserve the decision-specific evidence that passed
validation.

## Action And Audit History

`actions.json` contains only current next actions. Issued actions and host
results are preserved in audit/action history so a completed discussion can
still prove dispatch, wait, follow-up, and closeout intent.

`actions.json` must validate against
`.cowork-flow/spec/schemas/party-mode-v2-actions.schema.json` before the
runtime exposes it to monitor or Host execution surfaces. Missing required
fields, unknown action types, and Host-specific fields in `next_actions` fail
closed instead of becoming executable moderator work.

Host action results are recorded through runtime commands. The runtime records
host child ids and agent status, but it still does not call host primitives
directly.

## Final Reports

Final reports distinguish current unresolved disagreements from historical
disagreements. A report with `stop_reason=converged` must not present prior
round disagreements as currently unresolved.

Final reports are advisory fact records only. They cannot satisfy Implement,
Check, lifecycle gate, or task completion requirements. A final report must not
claim that implementation or review work is complete.

Final reports include audit-oriented summaries:

- `rounds_summary`: one entry per round with `round`, terminal `phase`,
  `post_count`, `response_count`, and `unresolved_count`.
- `action_results`: summaries of `action-result` entries from
  `action_history.jsonl`, including `action_id`, `type`, `outcome`, and
  `agent_id` when present.
- `accepted_evidence`: evidence accepted by `concede` responses, linked to
  `agent_id` and `target_post_id`.

## Moderator Boundary

The moderator monitors runtime status, executes host-neutral next actions, and
records drift warnings. The moderator does not forward, rewrite, summarize, or
synthesize child opinions.
