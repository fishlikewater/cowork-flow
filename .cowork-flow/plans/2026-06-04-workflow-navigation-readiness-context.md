# Workflow Navigation Readiness And Project Context Plan

## Goal

Turn the brainstorming clarification gate into an operational path: visible next
steps, enforceable L2 readiness, and a maintained project-context artifact.

## Execution Strategy

Serial main-session work.

Reason: all work items touch shared workflow entry points, task/change lifecycle,
runner dispatch, template sync, and tests. Parallel slices would collide on
`.cowork-flow/scripts/task.py`, `.cowork-flow/scripts/run.py`, README, and template
mirrors. Child tasks are execution slices, not parallel sessions.

## Child Tasks

| Order | Task | Purpose | Dependency | Output |
| --- | --- | --- | --- | --- |
| 1 | `.cowork-flow/tasks/06-04-workflow-navigator-task-next` | Add `task next` navigator | Parent PRD/change | Read-only next-action command and route help |
| 2 | `.cowork-flow/tasks/06-04-l2-readiness-gate` | Define and enforce L2 readiness | `task next` blocker extension point | Readiness helper, start/next blockers, tests |
| 3 | `.cowork-flow/tasks/06-04-project-context-generator` | Generate and refresh project context | Navigator command surface | `.cowork-flow/project-context.md` generator |
| 4 | `.cowork-flow/tasks/06-04-template-verification-sync` | Sync template/docs/tests and final verification | Tasks 1-3 | Template parity, README updates, final test pass |

## Detailed Work Items

### 1. Workflow Navigator And `task next`

Scope:

- Add read-only task-aware next-action output.
- Cover no-task, planning, active planning, in-progress, completed, stale/unknown,
  delegated-subtask guidance, and future L2 readiness blockers.
- Keep output clean: no context validation `[OK]` noise.
- Integrate `task next` into `workflow.md` stage boundaries and README.
- Keep `task.json.status` aligned through `task start`, `task review`, and
  `task complete`.

File ownership:

- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `README.md`
- `tests/test_flow_script_paths.py`
- `tests/test_python_runner.py`

Expected output:

- `.\.cowork-flow\run.cmd task next` prints status, next action, command, and
  blockers without writing files.
- Active ready planning tasks route to implementation/check dispatch guidance,
  while inactive ready planning tasks route to `task start`.
- Lifecycle commands advance durable task status:
  `planning -> in_progress -> review -> completed`.
- Future readiness blockers can plug into `common.readiness.task_readiness_blockers`
  without changing the navigator surface.

Verification:

- [x] `python -m unittest discover -s tests -p "test_flow_script_paths.py"`
- [x] `python -m unittest discover -s tests -p "test_python_runner.py"`
- [x] `.\.cowork-flow\run.cmd task next`
- [x] `git diff --check`

### 2. L2 Readiness Gate

Scope:

- Add a shared readiness checker under `.cowork-flow/scripts/common/`.
- Detect L2 change/task relationship from `change.yaml` and task path.
- Check required L2 fields: goal, non-goals, assumptions, scope boundary,
  acceptance criteria, proposal/spec/design, plan link, task link, and
  verification commands.
- Surface blockers before `task start`.
- Expose the same blocker list for `task next`.

File ownership:

- `.cowork-flow/scripts/common/<readiness-helper>.py`
- `template/.cowork-flow/scripts/common/<readiness-helper>.py`
- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/change.py` only if shared parsing is needed
- Tests under `tests/`

Expected output:

- `task start` blocks linked L2 work when readiness artifacts are missing.
- Readiness output is actionable and includes exact missing file/field.
- Non-L2 work remains unaffected.

Verification:

- [x] `python -m unittest discover -s tests -p "test_flow_script_paths.py"`
- [x] New readiness tests cover ready, missing design, missing spec, missing plan,
  missing task link, non-L2 bypass, and start failure without mutation.

### 3. `project-context.md` Generation/Maintenance

Scope:

- Add generator/refresh command for `.cowork-flow/project-context.md`.
- Read local project facts only: `AGENTS.md`, workflow, config, specs, package
  scripts, host adapters, CLI metadata, README.
- Preserve manual notes.
- Keep generated sections deterministic and idempotent.

File ownership:

- New script under `.cowork-flow/scripts/`
- Template copy under `template/.cowork-flow/scripts/`
- Possibly shared helper under `.cowork-flow/scripts/common/`
- `.cowork-flow/project-context.md`
- `template/.cowork-flow/project-context.md` only if a placeholder is useful
- README and tests

Expected output:

- Refresh command creates the context file when missing.
- Refresh command does not duplicate generated blocks.
- Manual notes survive refresh.
- The file is concise and links to authoritative docs instead of copying them.

Verification:

- [x] Project-context tests cover create, refresh idempotence, preserved manual notes,
  missing optional files, and template sync.
- [x] `.\.cowork-flow\run.cmd project-context refresh`
- [x] `git diff --check`

### 4. Template Docs And Verification Sync

Scope:

- Mirror root workflow script changes into template.
- Update README command docs.
- Update init/sync/package expectations if new files enter the template.
- Run targeted tests and final full test command if feasible.

File ownership:

- `README.md`
- `src/commands/init.js`
- `src/commands/sync.js`
- `src/lib/platforms.js`
- `src/lib/copy-template.js`
- `tests/`
- Template files touched by tasks 1-3

Expected output:

- New commands and generated context behavior are documented.
- `init` and `sync` include new template assets when appropriate.
- Root/template parity tests pass.

Verification:

- [x] `python -m unittest discover -s tests`
- [x] `npm test`
- [x] `npm run pack:check`
- [x] `git diff --check`

## Overall Steps

1. [x] Audit current architecture and gaps -> Verify: `rg` confirms no existing
   `task next`, no `project-context.md`, and L2 readiness is not surfaced as a
   pre-start gate.
2. [x] Open parent task/change -> Verify: parent task, change, PRD, plan, and
   context files exist.
3. [x] Split execution into child tasks -> Verify: parent task lists four child
   tasks and each child has context initialized.
4. [x] Execute child task 1: workflow navigator and `task next` -> Verify command
   output tests pass.
5. [x] Execute child task 2: L2 readiness gate -> Verify readiness tests pass.
6. [x] Execute child task 3: `project-context.md` generation -> Verify idempotence
   and manual-note tests pass.
7. [x] Execute child task 4: template/docs/final verification -> Verify targeted
   Python tests, npm tests, pack check, and `git diff --check`.
8. [x] Final check -> Verify parent and child task states, change metadata,
   final diff, and test results are consistent.
9. [ ] Archive/commit/session record -> Verify commit, archive, and session record
   are consistent after explicit closeout.

## Dispatch Policy

Use inline main-session implementation for these children unless user asks to
dispatch fixed agents. Reason: tasks modify subagent/runtime/bootstrap workflow
behavior, and the workflow already allows inline work for such changes. If fixed
agents are used, dispatch only leaf `cowork-implement` / `cowork-check` tasks with
`COWORK_DISPATCH_V1`.
