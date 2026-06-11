# Party Mode V2 Runtime Hardening Proposal

## Summary

Harden Party Mode V2 after a real run artifact review exposed gaps in safety, audit replay, child-agent lifecycle evidence, prompt usability, and final-report consistency.

## Motivation

The `douyin-service-provider-20260610` run produced useful board discussion, but the artifacts could not prove real host child lifecycle, could not replay every runtime decision from audit logs, and generated a final report that said `converged` while listing historical unresolved disagreements. These gaps make Party Mode V2 look plausible without being sufficiently verifiable.

## Change

- Add safe id/path handling, transactional writes, and stricter submission validation.
- Add durable action/audit/lifecycle evidence without calling host primitives from runtime.
- Make prompts phase-specific and self-sufficient for child agents.
- Tighten schemas and tests so root/template assets and runtime artifacts stay aligned.

Describe the proposed behavior change.
