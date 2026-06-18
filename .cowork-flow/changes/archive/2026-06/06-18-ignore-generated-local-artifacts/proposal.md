# 06-18-ignore-generated-local-artifacts

## Why

Normal cowork-flow usage currently leaves two local-only generated paths visible
in `git status`:

- `.codegraph/`
- `template/.cowork-flow/.runtime/`

These are not source-of-truth artifacts for repository history, but they keep
showing up as untracked noise during closeout and workflow verification.

## Proposal

Add ignore rules for those generated paths in the repository root `.gitignore`
so normal local workflow operations no longer pollute `git status`.

## Scope

- Update the repository root `.gitignore`.
- Add regression coverage that locks the intended ignore entries in place.
- Verify that the ignored paths disappear from `git status` without hiding
  actual workflow artifacts such as `.cowork-flow/tasks/archive/...`.

## Out of Scope

- Do not ignore active or archived task/change artifacts under `.cowork-flow/`.
- Do not change template copy/runtime behavior.
- Do not change package filtering or dashboard/runtime persistence behavior.
