# L2 readiness gate

## Goal

Make L2 work fail closed before start or formal dispatch when required analysis,
design, spec, plan, task, or verification artifacts are missing.

## Scope

- Add shared readiness checker.
- Link L2 change metadata to task readiness.
- Block `task start` for linked L2 work with missing artifacts.
- Expose readiness blockers for `task next`.
- Keep L0/L1 behavior unaffected unless explicitly linked to L2.

## Acceptance

1. Ready L2 task passes readiness.
2. Missing `proposal.md`, `spec.md`, `design.md`, plan, task link, or acceptance
   criteria produces actionable blockers.
3. Failed readiness does not mutate task state.
4. Non-L2 tasks bypass the blocking gate.
5. Tests cover ready and blocked paths.

## Verification

- `python -m unittest discover -s tests -p "test_flow_script_paths.py"`
- `python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py"`
- `git diff --check`
