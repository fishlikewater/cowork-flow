# Team collaboration

[中文](team.md) | English

When several people, branches, or worktrees use cowork-flow together, task state lives in the repository while runtime state lives locally. This page covers what to commit, why a binding stops resolving after a branch switch, what executor and assignee each mean, and how to repair conflicts.

## What to commit, what to ignore

- Commit: `.cowork-flow/tasks/`, `.cowork-flow/plans/`, the project-owned directories under `.cowork-flow/spec/` (`backend/`, `frontend/`, `guides/`, `references/`), `.cowork-flow/config.yaml`, and `AGENTS.md`.
- Ignore: `.cowork-flow/.runtime/`. On the first runtime write, cowork-flow creates `.runtime/.gitignore` automatically (containing `*` and `!.gitignore`), so locks, session bindings, operation logs, and state snapshots stay out of git.
- Do not commit `.runtime` by hand; if an earlier version already committed it, see the cleanup section below.
- `project sync` only updates framework-managed files; tasks, plans, and project-owned specs are preserved by default.

## Branches and worktrees

- Tasks and plans follow the branch. After switching to a branch that does not contain the current task, the session binding still points at the old path but the directory is gone; the hook and CLI report "task directory not found" and suggest switching back or rebinding explicitly instead of creating a duplicate task.
- Rebind: after returning to the branch that contains the task, run `./.cowork-flow/run task next <task-dir>`; or pick an existing task with `task next --list`.
- Each worktree has its own `.runtime/`, so session bindings, locks, and state snapshots are not shared; task files follow each worktree's checked-out branch.
- Do not advance the same task in parallel worktrees: different checkouts hold different copies of `task.json`, and runtime locks only protect a single working tree.
- To advance several tasks in parallel, coordinate through the task board (`task next --list --json`) and dependencies (`--depends-on`), then converge after merging.

## executor vs assignee

- `assignee` is the person: `--assignee` at task creation, used for board ownership and filtering (`task next --list --mine`).
- `executor` is the session identity that currently holds the task: written when `task next <dir> --run` starts it. To continue from another machine or session, take over explicitly with `--adopt`; adoption resets the review baseline and keeps the former executor's audit fields.
- `ownerSessionActive` is only a binding hint: `false` does not mean the task is unowned, and sessions working with an explicit directory or in another worktree never show up as bindings here.
- Hand ownership over with `--adopt`; `--takeover` only applies at start and does not reset the baseline.

## Cross-machine handover

1. The original executor commits and pushes the task directory (`task.json`, `decision-anchor.md`, `implement.jsonl`, and so on).
2. The new executor pulls the branch and runs `./.cowork-flow/run task next <task-dir> --run --adopt`.
3. The handover output lists the former executor, the former baseline, remaining unchecked ACs, and evidence coverage, so work can continue directly.

## Merge conflicts and manual repair

- `task.json` is a fact file, and hand-editing it is a legitimate repair path; after resolving a merge conflict, `task next --validate` and `doctor --all` should report no new errors.
- Cycles, dependencies on missing tasks, empty executors, and similar anomalies fail closed at the start / review gates instead of passing silently.
- Do not hand-edit `_state`: `revision` and `operation_id` are concurrency-control and idempotency metadata.
- After a merge, run `./.cowork-flow/run doctor --all` before continuing.

## Cleaning up a committed .runtime

- `doctor --all` reports `RUNTIME-GIT-HYGIENE-UNIGNORED` (runtime files are not ignored) or `RUNTIME-GIT-HYGIENE-TRACKED` (runtime files are tracked).
- Clean up with `git rm -r --cached .cowork-flow/.runtime`; after committing, the next runtime write creates `.runtime/.gitignore` automatically.
- Cleanup does not delete local files; locks, bindings, and snapshots stay in the working tree.
