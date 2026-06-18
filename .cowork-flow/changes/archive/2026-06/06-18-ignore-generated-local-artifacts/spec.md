## Expected Behavior

1. The repository root `.gitignore` ignores `.codegraph/`.
2. The repository root `.gitignore` ignores `template/.cowork-flow/.runtime/`.
3. Real workflow artifacts under `.cowork-flow/tasks/`, `.cowork-flow/changes/`,
   and `.cowork-flow/plans/` remain visible to Git unless explicitly ignored by
   existing rules.
4. Regression coverage asserts the root `.gitignore` keeps these generated-path
   ignore entries.

## Verification

- `rtk proxy git check-ignore -v .codegraph template/.cowork-flow/.runtime`
- `rtk python -m pytest tests/test_flow_migrate.py -q`
- `rtk git diff --check`
