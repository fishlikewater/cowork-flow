# Formal subagent result timing probe result

## Runtime Probe

- Runtime id: `rtx_20260618_225239_fast-formal-timing-probe`
- Created at: `2026-06-18T14:52:39Z`
- Bound at: `2026-06-18T14:54:08Z`
- Marker written at: `2026-06-18T23:00:33.8199363+08:00`
- Closed at: `2026-06-18T15:31:39Z`
- Marker file: `implement-fast.txt`

## Verdict

The host child did execute far enough to bind and write a marker file, so the
internal run was not a pure "child never existed" case. The user-visible problem
was still real: the workflow did not clearly expose child creation state, and
the parent session did not receive a usable final result even after an extended
wait.

## Fix Applied

- `subagent dispatch-codex` now emits machine-readable fields showing that the
  runtime context is created but the host child is not created by the CLI.
- `task next` now states that a host child does not exist until the host
  primitive is called and verified through list/wait evidence.
- `workflow.md` and `spec/core/dispatch.md` now define payload preparation as
  separate from host child creation.
- Tests cover payload visibility, task-next wording, and root/template contract
  sync.

## Remaining Risk

The repository can clarify and verify the dispatch contract, but it cannot fix
the Codex platform result-return path directly. If `wait_agent` receives no final
answer from a child that has executed work, the parent must rely on runtime
state, file/command evidence, child listing, and explicit cleanup.
