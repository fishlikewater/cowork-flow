---
name: party-mode
description: Use when the user manually requests Party Mode or a real multi-agent roundtable for advisory discussion, option review, risk review, or decision convergence.
---

# Party Mode

Use this skill as a manual advisory roundtable. Coordinate true child agents, not simulated personas, through the current Host Adapter.

## Boundaries

- Party Mode is advisory only.
- It cannot mutate task status, start/review/complete/archive tasks, add sessions, commit, push, or satisfy formal workflow gates.
- It cannot satisfy formal Implement or Check completion. Use `cowork-implement` and `cowork-check` for formal phases.
- Discussion children are leaf executors. They do not dispatch, wait for, list, or close other agents.
- Generic `worker`, `default`, or `explorer` agents may provide advisory views, but their output never proves implementation or checking done.

## Defaults And Config

Built-in defaults:

- `max_agents=3`
- `max_rounds=3`

These defaults are configurable values, not hard-coded constants. Effective config order:

```text
call arguments > task/change config > `.cowork-flow/config.yaml` > skill defaults
```

Configurable fields:

- `max_agents`
- `max_rounds`
- agent roster or review lenses
- report enabled
- report path
- whether round 2 or round 3 is allowed

Safety gates:

- continue conditions can be tightened but not removed
- stop conditions can be tightened but not removed
- schema core fields can be extended but not removed
- exceeding effective limits requires explicit user approval

## Round Model

1. Frame the question, decision needed, scope, and evidence packet.
2. Select the smallest useful agent roster or review lenses within effective `max_agents`. Record why each selected voice is useful and why omitted voices are not needed.
3. Round 1 uses fresh child contexts. Send each child the same packet and one lens. Child agents cannot see each other.
4. Synthesize only evidence-backed positions, disagreements, rejected options, and acceptance signals.
5. Continue only when a continue condition is met. Send narrow follow-up prompts to the smallest useful set of children.
6. Follow-up rounds should prefer the same live child that produced or challenged the relevant position. Send only evidence-backed disagreement summaries, and ask the child to `agree`, `reject`, or `revise`.
7. Spawn an extra child only when the effective roster or lens config allows it, a live child failed, or the user approves expansion.
8. Stop when any stop condition is met. Close all live children through the Host Adapter close primitive.

Round intent:

- Opening round: independent first judgments.
- Challenge rounds: rebuttal, risk drilldown, or evidence repair on specific disagreements.
- Convergence rounds: decision check only. Verify, narrow, or choose. Do not open new directions.

Default mapping:

- Round 1 = Opening.
- Round 2 = Challenge.
- Round 3+ = Convergence.

Only the user can restart exploration after convergence begins.

## Continue Conditions

Run another round only if at least one condition holds:

- A disagreement could change the recommended decision.
- A high risk lacks enough evidence.
- Acceptance criteria are still not testable.
- A child found new file, command, rule, or user-scenario evidence.
- The coordinator cannot write one recommended direction.

## Stop Conditions

Stop when any condition holds:

- Recommendation, rejected options, and measurable acceptance criteria are clear.
- Remaining issue is user value preference, not missing evidence.
- A full round adds no evidence and does not narrow scope.
- Effective `max_rounds` is reached.
- Output fails schema, and one repair prompt does not fix it.

## Child Output Schema

Each child must return these core fields. Extra fields are allowed only after them.

```text
position:
evidence:
risk:
tradeoff:
rejected_option:
acceptance_signal:
what_would_change_my_mind:
```

Follow-up rounds may add these fields after the core fields:

```text
responding_to:
opposing_claim:
position_delta:
evidence_delta:
still_disagree:
```

Use `position_delta` to say whether the child maintained, narrowed, or changed its position.
Reject unsupported opinion. Evidence should name files, commands, rules, observed behavior, user scenarios, or concrete assumptions.

## Coordinator Output Schema

Final synthesis must return these core fields. Extra fields are allowed only after them.

```text
effective_max_agents:
effective_max_rounds:
rounds_used:
selected_agents:
agent_turns:
consensus:
disagreements:
evidence:
decision:
rejected_options:
acceptance_criteria:
open_questions:
early_stop_reason:
stop_reason:
```

`selected_agents` must include the selected agent or lens names and selection reasons. `agent_turns` should preserve each child's position and follow-up response in a compact form. Keep the final decision traceable to child evidence. Do not count votes as validation.
