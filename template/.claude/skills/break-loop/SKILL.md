---
name: break-loop
description: Use after fixing a bug or repeated failed attempts to identify the root cause, prevention mechanism, and durable knowledge capture.
---

# Break Loop

Use this after the immediate fix is understood. The goal is to prevent the same class of bug from returning.

## Analysis

1. Root cause: identify whether the issue was missing spec, unclear contract, incomplete propagation, test gap, or hidden assumption.
2. Failed attempts: if fixes failed, explain what each attempt misunderstood.
3. Blast radius: search for similar contracts, call sites, scripts, templates, and tests.
4. Prevention: decide whether the durable fix belongs in code, tests, specs, workflow, or tooling.
5. Capture: update `.cowork-flow/spec/` or workflow docs when future agents need the lesson.

## Output

Report:

- Root cause.
- Why the final fix works.
- Similar areas checked.
- Prevention added or intentionally skipped.
- Verification command and result.
