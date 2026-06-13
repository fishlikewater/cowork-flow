# Dashboard Runtime Control Design

## Decisions

### Agent Run Recording

`subagent init` already has all needed data: runtime id, resolved agent type, creation time, host context key, and execution task dir. The smallest reliable fix is to create `agent_run` immediately after the runtime context and logical session are written.

The implementation resolves `task_dir` through the existing Flow task resolver. If no Flow database or task exists, recording is skipped so advisory/temp use remains tolerant. Duplicate runtime ids are not expected because ids are generated from the runtime directory; if a duplicate insert is observed, the command should fail loudly in tests rather than silently inventing a second id.

### Archived Layout

The existing board column model works for active workflow states, but archived tasks are history. The UI will render active statuses as columns and archived tasks as a separate full-width history section. This avoids an empty right rail when the archived tab is selected and keeps "all + show archived" readable.

### Filter State

`state.status` and the archived checkbox are separate inputs:

- `state.status === "archived"`: show only archived in history layout.
- `state.status === "all" && showArchived.checked`: show active board plus archived history section.
- specific non-archived status: show only that status and ignore archived checkbox for the visible result.

### CLI Process Control

Dashboard process state is local to the repository at `.cowork-flow/.runtime/dashboard.json`. The process manager uses only stdlib primitives:

- `start`: spawn `server.py serve --host --port` in the repo root, write pid/url/log paths.
- `status`: read the state file and verify the pid is still alive.
- `stop`: terminate the recorded pid; fallback to Windows `taskkill` when needed.

No global registry is introduced, so multiple projects can manage their own Dashboard state independently.

## Risks

- Browser smoke depends on whichever Dashboard process is currently serving `127.0.0.1:8080`.
- Windows process termination can be slow; tests should use short-lived dedicated ports and stop in `finally`.
