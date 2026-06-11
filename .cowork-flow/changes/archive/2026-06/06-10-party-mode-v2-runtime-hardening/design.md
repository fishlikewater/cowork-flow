# Party Mode V2 Runtime Hardening Design

## Classification

Level: L2. This changes runtime state shape, file safety, host-neutral action contracts, final-report contracts, and child-agent interaction behavior.

## Target Architecture

The Python runtime remains the canonical owner of board state. It does not call host primitives. Instead, it emits host-neutral actions and accepts explicit host result records from the moderator or adapter.

Runtime state must become replayable:

- `board.json` stores canonical board history.
- `agents.json` stores lifecycle state and host child identifiers.
- `audit.jsonl` stores every state transition and command-level event.
- `actions.json` stores current next actions only.
- `action_history.jsonl` or audit action events preserve issued/completed action history.
- `reports/final.json` stores terminal conclusions with current and historical disagreement fields separated.

## Safety Rules

- `discussion_id` and `agent_id` are identifiers, not paths or shell fragments.
- Every resolved runtime path must stay under `.cowork-flow/.runtime/party-mode-v2`.
- Board writes must use a lock plus atomic replace so parallel child submissions cannot lose data.
- Generated ids are assigned inside the locked write transaction.

## State Machine Rules

- `init` creates round 1 publish state and publish actions.
- `post` is accepted only in publish phase for the explicit current round.
- `advance` from publish to respond requires one post from every active agent.
- `respond` is accepted only in respond phase for the explicit current round.
- `advance` from respond must evaluate coverage, disagreement, max rounds, and fresh-context closeout before creating the next action set.
- `finalize` is accepted only after closed state or explicit manual termination.
- Terminal and non-terminal `advance` responses must use a stable envelope.

## Prompt Rules

Publish prompt includes:

- current round and empty-view semantics,
- `party-v2 view`,
- `party-v2 post --file`,
- post payload schema.

Respond prompt includes:

- current-round visible post ids,
- target limits,
- `party-v2 respond --file`,
- maintain/revise/concede payload schema.

## Report Rules

Final report separates:

- `current_unresolved_disagreements`,
- `historical_disagreements`,
- `resolved_or_narrowed_positions`,
- `final_recommendation_inputs`.

`stop_reason=converged` requires no current unresolved disagreements.

## Root And Template Parity

Runtime script, config, specs, action schema, skills, commands, and adapter declarations must remain synchronized between root assets and `template/` mirrors.
