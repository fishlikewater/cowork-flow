---
name: check-cross-layer
description: Use when reviewing changes that span layers, contracts, repeated patterns, shared utilities, or cowork-flow runtime behavior.
---

# Cross-Layer Check

Use this after implementation and before finish when the change crosses boundaries or updates shared runtime behavior.

## Steps

1. Read current task PRD and plan.
2. Review `git diff --name-only`.
3. Trace every changed contract across caller and callee boundaries.
4. Check whether `.cowork-flow/spec/` needs an update.
5. Run focused tests that would fail if the contract is broken.
6. Report remaining risk and exact verification commands.

## Required Dimensions

- Data flow: source, transformation, destination.
- Command/API contract: parameters, output, error behavior.
- State persistence: files written, files removed, recovery behavior.
- Template parity: root and `template/` copies stay aligned when both exist.
- Test intent: tests fail for the behavior, not only for implementation details.

## Output

Report:

1. Dimensions checked.
2. Issues found and fixes made.
3. Verification commands and results.
4. Any spec update made or why no spec update was needed.
