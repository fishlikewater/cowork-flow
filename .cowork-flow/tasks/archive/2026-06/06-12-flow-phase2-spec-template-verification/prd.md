# Document And Verify Phase 2 Pattern Engine

## Goal

Document pattern contracts, sync template copies, and run final Phase 2 verification.

## Scope

- Create root/template `.cowork-flow/spec/patterns/` docs.
- Update root/template `.cowork-flow/spec/registry.json`.
- Add or update parity tests for pattern runtime/spec files.
- Run final test gates and whitespace checks.

## Non-Goals

- Do not implement additional pattern behavior beyond Phase 2.
- Do not update README or workflow unless existing text contradicts the implemented behavior.
- Do not publish or push.

## Acceptance Criteria

1. Pattern specs document statuses, metadata shape, transitions, and lifecycle behavior.
2. `registry.json` includes the new pattern specs.
3. Root/template parity tests cover the new runtime/spec files.
4. Full verification passes.

## Verification

```powershell
python -m pytest tests/test_patterns.py tests/test_flow_script_paths.py tests/test_host_adapters.py -q
npm run test:all
git diff --check
```
