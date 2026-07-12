
# P2 标注历史设计文档边界

## Goal

Clarify that migration-era state descriptions in FLOW-UPGRADE-DESIGN are historical context, not current runtime authority.

## Scope

- FLOW-UPGRADE-DESIGN.md
- Authority-doc scan across README/workflow/core specs

## Non-Goals

- Do not rewrite the migration design body.
- Do not change runtime behavior.

## Acceptance Criteria

1. FLOW-UPGRADE-DESIGN has a visible historical/migration boundary note near the top.
2. The note names current authority docs for runtime state.
3. Current authority docs scan clean for old state-authority wording.
4. git diff --check passes.

## Relevant Files

- `FLOW-UPGRADE-DESIGN.md`
- `README.md`
- `.cowork-flow/workflow.md`
- `.cowork-flow/spec/core/dispatch.md`
- `.cowork-flow/spec/core/lifecycle.md`

## Verification

- `rg -n "workflow-state-templates\.md|task\.json\.status|\.runtime/subagents|\.runtime/sessions" README.md .cowork-flow/workflow.md .cowork-flow/spec/core/dispatch.md .cowork-flow/spec/core/lifecycle.md`
- `git diff --check`
