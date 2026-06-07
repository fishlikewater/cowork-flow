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
2. Round 1 uses fresh child contexts. Send each child the same packet and one lens. Child agents cannot see each other.
3. Synthesize only evidence-backed positions, disagreements, rejected options, and acceptance signals.
4. Continue only when a continue condition is met. Send narrow follow-up prompts to the smallest useful set of children.
5. Stop when any stop condition is met. Close all live children through the Host Adapter close primitive.

Round intent:

- Round 1: independent first judgments.
- Round 2: rebuttal or risk drilldown on specific disagreements.
- Round 3: decision check only. Do not open new directions.

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

Reject unsupported opinion. Evidence should name files, commands, rules, observed behavior, user scenarios, or concrete assumptions.

## Coordinator Output Schema

Final synthesis must return these core fields. Extra fields are allowed only after them.

```text
consensus:
disagreements:
evidence:
decision:
rejected_options:
acceptance_criteria:
open_questions:
stop_reason:
```

Keep the final decision traceable to child evidence. Do not count votes as validation.
