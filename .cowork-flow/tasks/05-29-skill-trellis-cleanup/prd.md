# Trellis-like Skill Cleanup PRD

## Goal

Remove the legacy Superpowers seed layer and make cowork-flow skills a direct Trellis-like `.agent/skills` surface.

## Requirements

- `template/.superpowers/` is removed.
- `init`, `sync`, package tests, and docs no longer reference Superpowers seed behavior.
- Root and template `.agent/skills` expose the same current workflow skills.
- Add clean-room Trellis-like skills for `before-dev`, `check`, `continue`, `meta`, and `python-design`.
- Remove skills that are obsolete under the new fixed-agent workflow.
- Audit all remaining skill descriptions and bodies for stale references, redundant constraints, and inaccurate workflow instructions.
- Update task default context so new tasks point at current skills only.

## Acceptance Criteria

- No root/template active skill references `.superpowers`, `superpowers:*`, or old execution skills.
- `template/.agent/skills` contains only current workflow skills.
- `npm run test:all` passes.
- `git diff --check` passes.
- Final review reports the skill set and any remaining risk.
