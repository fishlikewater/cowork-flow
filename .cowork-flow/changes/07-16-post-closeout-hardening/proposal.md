# Post-closeout workflow hardening

## Goal

Harden the post-closeout workflow so task archive, linked change archive, archived context validation, Windows npm commands, and legacy completed task state remain predictable after final scans.

## User Value

Developers can run archive-first closeout without surprise change moves, manual JSONL repairs, noisy Windows npm warnings, or ambiguous old completed tasks.

## Key Assumptions

- Single-task linked change auto-archive remains useful and should keep working.
- Multi-task change closeout needs an explicit final boundary before change archive.
- Archived task validation should use real archived paths instead of accepting stale active paths.
- Windows npm commands can use explicit executable resolution instead of shell execution.

## Problem

The previous closeout completed successfully, but the final scan exposed follow-up workflow risks:

1. `task archive` auto-archived the linked active change while a multi-task follow-up still had remaining tasks.
2. Task/change archival moved source files, leaving archived JSONL context entries pointing at active paths until they were manually repaired.
3. `npm run pack:check` passes but emits Node `DEP0190` because Windows npm command execution uses `shell: true`.
4. Older 06-25 verification tasks remain `completed`, making task list output less intentional.

## Goals

- Preserve the single-task archive convenience while preventing premature multi-task change archive.
- Make archived task/change context validation pass immediately after closeout.
- Remove the Windows npm shell warning without breaking update/install commands.
- Audit older completed verification tasks and either archive safe items or document why they remain completed.

## Non-Goals

- Do not redesign the whole task/change model.
- Do not remove the existing `task archive` command.
- Do not change formal subagent dispatch semantics.
- Do not hide validation failures with broad allowlists.
