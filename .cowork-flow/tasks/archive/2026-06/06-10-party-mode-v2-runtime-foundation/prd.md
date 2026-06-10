# Party Mode V2 Runtime Foundation PRD

## Goal

Implement the Party Mode V2 runtime foundation: configuration, runtime state initialization, current-round board view, and host-neutral next action output.

## Scope

Create the first version of the Python runtime without implementing full debate validation. The runtime must initialize discussion state, enforce basic agent count/config defaults, expose current-round-only `view`, and generate host-neutral actions.

## Files

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `.cowork-flow/scripts/run.py`
- `template/.cowork-flow/scripts/run.py`
- `.cowork-flow/scripts/common/config.py`
- `template/.cowork-flow/scripts/common/config.py`
- `.cowork-flow/config.yaml`
- `template/.cowork-flow/config.yaml`
- `tests/test_party_mode_v2.py`
- `.cowork-flow/plans/2026-06-10-party-mode-v2-runtime-board.md`
- `.cowork-flow/tasks/06-10-party-mode-v2-runtime-board-design/design.md`

## Requirements

- Add `party_mode_v2` config getters with sensible defaults.
- Add runtime commands for `init`, `view`, and `monitor`.
- Runtime state must be written as UTF-8 JSON/JSONL.
- `view` must return only current-round board data.
- `next_actions` must use host-neutral action names.
- Root and template copies must stay in sync.

## Acceptance Criteria

- Tests prove defaults and config overrides for V2.
- `init` creates a discussion directory under `.cowork-flow/.runtime/party-mode-v2/<discussion_id>/`.
- `view` excludes previous rounds.
- `monitor` returns board status and host-neutral `next_actions`.
- No shared runtime output uses `spawn_agent`, Claude Task names, or OpenCode primitive names.
- `rtk git diff --check` passes.

## Verification

```powershell
rtk proxy powershell -NoProfile -Command '& { python -m unittest discover -s tests -p ''test_party_mode_v2.py'' -v }'
rtk git diff --check
```
