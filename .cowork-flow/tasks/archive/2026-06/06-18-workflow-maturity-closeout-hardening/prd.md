# Workflow Maturity Closeout Hardening

## Goal

Close the architecture follow-up gaps left after the workflow maturity roadmap refactor so the current architecture is internally consistent, release-safe, and easier to maintain.

## Problem

The roadmap refactor improved the architecture, but four concrete gaps remain:

1. Entry docs and generated task context still reference old spec paths after the three-layer split.
2. OpenCode still depends on the compat fallback path instead of a complete structured entry-signal route, and the compat fallback remains enabled by default.
3. Package validation does not prevent runtime byproducts under `template/.cowork-flow/.runtime/` from leaking into the published npm package.
4. Coordination logic is still overly concentrated in a few large scripts, increasing change risk and slowing future maintenance.

## Benefits

- New readers and generated tasks resolve the correct spec entrypoints.
- Formal entry classification becomes more explicit and less dependent on fallback heuristics.
- Published template assets stop shipping repo-local runtime residue.
- The coordination layer becomes easier to reason about without changing the runtime-safety model.

## Non-Goals

- No redesign of runtime-context binding, fail-closed behavior, or fixed-agent protocol.
- No new change container or alternate workflow model.
- No broad refactor outside the files needed to close these four issues.

## Key Assumptions

- The active change `06-15-workflow-maturity-roadmap` remains the correct container for this follow-up hardening work.
- OpenCode can provide stable enough structured entry signals through plugin-controlled input shaping.
- Conservative helper extraction is sufficient to address the main maintainability concern without changing behavior.

## Scope

### In scope

- Sync quick-start, task context generation, and related docs to the three-layer spec paths.
- Finish the OpenCode structured entry-signal path and switch the compat fallback default off once coverage is in place.
- Exclude runtime byproducts from published template assets and enforce that in pack validation.
- Extract focused helpers from the most concentrated workflow scripts where it reduces coordination complexity without widening behavior.
- Update root/template/test assets together where the architecture contracts require parity.

### Out of scope

- Replacing FlowStore, runtime_context, or dashboard architecture.
- Reopening Party Mode positioning or pattern-engine scope decisions.
- Parallelizing this work across multiple sessions.

## Acceptance Criteria

1. Quick-start, generated task context, and related workflow guidance no longer reference deleted `spec/backend` or `spec/frontend` paths.
2. OpenCode declares and exercises structured entry signals, and the default config no longer keeps legacy text fallback enabled.
3. `npm run pack:check` fails if `template/.cowork-flow/.runtime/` artifacts would ship, and the current package output is clean.
4. At least one of the current coordination hot spots is split into clearer helpers/modules with tests still passing and behavior unchanged.
5. Root/template parity remains intact for every changed workflow asset.

## Files Likely To Change

- `AGENTS.md`
- `.cowork-flow/workflow.md`
- `.cowork-flow/spec/quick-start.md`
- `.cowork-flow/spec/registry.json`
- `.cowork-flow/config.yaml`
- `.cowork-flow/adapters/opencode/adapter.yaml`
- `.opencode/plugins/cowork-flow.js`
- `.cowork-flow/scripts/common/entry_classifier.py`
- `.cowork-flow/scripts/common/inject_workflow_state.py`
- `.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/flow/store.py`
- `package.json`
- `scripts/pack-check.js`
- `src/lib/copy-template.js`
- matching `template/` assets
- relevant Python and Node tests

## Verification

- `python -m unittest discover -s tests -v`
- `npm test`
- `npm run test:template`
- `npm run pack:check`
- `git diff --check`

## Related Artifacts

- Change: `06-15-workflow-maturity-roadmap`
- Plan: `.cowork-flow/plans/2026-06-15-workflow-maturity-roadmap.md`
