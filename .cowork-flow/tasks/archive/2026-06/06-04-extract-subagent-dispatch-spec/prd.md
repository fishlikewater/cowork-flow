# Extract subagent dispatch spec from workflow

## Goal

Keep `workflow.md` focused on the main workflow by moving detailed subagent dispatch protocol rules into a dedicated spec document.

## Scope

- Update `.cowork-flow/workflow.md` and `template/.cowork-flow/workflow.md`.
- Add `.cowork-flow/spec/subagent-dispatch.md` and `template/.cowork-flow/spec/subagent-dispatch.md`.
- Register the new spec contract in both `spec/registry.json` files.
- Update focused tests so dispatch protocol assertions point at the new spec.

## Acceptance Criteria

- `workflow.md` keeps fixed-agent policy and links to `subagent-dispatch.md`, but no longer carries the full dispatch envelope, ACK gate, grace calculation, and generic worker protocol details.
- `subagent-dispatch.md` preserves the existing formal dispatch, ACK, `EXECUTE`, post-ACK grace, return acceptance, and generic worker boundaries.
- Current project and template copies stay aligned.
- Focused workflow and host-adapter tests pass.

## Verification

- `python -m unittest discover -s tests -p test_workflow_parallel_sessions.py`
- `python -m unittest discover -s tests -p test_host_adapters.py`
- `.\.cowork-flow\run.cmd doctor --subagent-safety`
- `git diff --check`
