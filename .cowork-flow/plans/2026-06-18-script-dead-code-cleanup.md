# Script Dead Code Cleanup Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Remove only evidence-backed dead code or redundant script paths without changing workflow behavior.
**Architecture:** The repo now uses runtime context plus FlowStore as the runtime authority, while task directories and hooks remain artifact and integration layers. Cleanup must preserve host injection, task lifecycle commands, root/template parity, and any explicit compatibility read paths that are still part of the contract.
**Verification:** `rtk python -m unittest discover -s tests -p "test_*" -v`, `rtk npm run test:template`, `rtk git diff --check`

## Execution Strategy

Serial work. The likely cleanup areas share runtime contracts, template parity, and overlapping tests, so parallel slicing would increase false positives and merge risk.

## Steps

1. Establish evidence for candidate dead code.
   Files: `.cowork-flow/scripts/**/*.py`, `.codex/hooks/*.py`, `template/.cowork-flow/scripts/**/*.py`
   Check:
   - Use CodeGraph caller scans plus targeted text search to classify candidates as active, compatibility-only, or dead.
   - Record whether each candidate is referenced by docs/tests/template parity.

2. Confirm contract-sensitive exclusions before editing.
   Files: `.cowork-flow/spec/core/dispatch.md`, `.cowork-flow/spec/core/entry.md`, `.cowork-flow/spec/reference/patterns/index.md`, touched source files
   Check:
   - Exclude anything still required as a compatibility read path, hook boundary, or doc-stable anchor.
   - Exclude anything whose removal would change command output or task-state semantics.

3. Remove or simplify only safe candidates.
   Files: exact touched source files in root and matching template files
   Check:
   - Delete unused functions/files or collapse duplicate logic only where the remaining path is already the sole runtime authority.
   - Keep comments concise and update adjacent docs only if they would become inaccurate.

4. Verify root/template parity and behavior safety.
   Files: touched source files, relevant tests
   Check:
   - Run focused and repo-level verification commands.
   - Confirm no leftover references to removed symbols remain.

## Risks

- Some apparently unused code may still serve as migration/compat import paths.
- Template parity can silently drift if only root is edited.
- Hook and runtime-context code is sensitive to seemingly small deletions; require caller evidence before removing any branch.
