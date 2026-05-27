# Subagent safe recovery design

## Overview

The design follows the same boundary principle as oh-my-codex: durable local state and explicit runtime authority are more reliable than prompt memory. Since the host may not expose a definitive child-thread identity, detection is intentionally conservative and backed by runtime gates.

## Start triage

`start` remains a skill-level rule, not a parser. It should not try to be perfect. It uses a small score-style checklist and defaults uncertain cases to subagent-safe mode. This reduces the dangerous false-negative case where a child becomes a coordinator. False positives are recoverable because a main-session override can rerun full start.

## Execution authority

`none` becomes the default context. Coordinator mutation must be explicit. This means a subagent that forgets its scope and runs an unscoped coordinator command gets a runtime error instead of mutating state.

`prepare` is left compatible as the one unscoped setup command because it creates the coordinator context used by the stricter follow-up commands. A later breaking version can require task-level coordinator context for `prepare` too.

## Generic subagent recovery

Agent-team already has assignment context. Other dispatchers do not. The generic subagent ledger gives a child a local recovery file without requiring every dispatcher to change its prompt format. On first subagent-safe start, the child persists its understood assignment into `.cowork-flow/subagents/<id>/`. After compaction, the child can resume from that context file and avoid main project recovery.

## Misclassification handling

Classification evidence should be documented in the skill guidance and, for generic contexts, stored in `context.json` when available. The runtime gate is the hard safety layer; triage is only a context-loading filter.

## Verification

Tests should prove the hard gates first, then the recovery shape. Documentation tests should check that start guidance includes the conservative preflight and subagent-safe recovery instructions.
