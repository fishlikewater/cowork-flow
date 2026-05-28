---
name: finish-work
description: Use when finishing cowork-flow implementation work before commit, archive, session recording, or handoff.
---

# Finish Work

Use this in the main session after implementation and check work are done.

## Required Inputs

Read:

1. `AGENTS.md`
2. `.cowork-flow/workflow.md`
3. Current task PRD and plan
4. `.cowork-flow/config.yaml` if present

## Completion Gate

Before claiming completion:

- [ ] A current session task exists, or this was explicitly read-only/no-task work.
- [ ] `cowork-check` ran, or an equivalent final inline check ran.
- [ ] `git diff` was reviewed for scope.
- [ ] Relevant tests/build/lint were run, or blocked commands are stated with reason.
- [ ] `.cowork-flow/spec/` was updated, or explicitly judged unchanged.
- [ ] Plan checkboxes and `Current Execution Status` match reality.
- [ ] No unrelated dirty files are staged.
- [ ] Commit is created before task archive or session recording when commit policy requires it.

## Verification Source Order

1. `.cowork-flow/config.yaml`
2. `AGENTS.md`
3. Existing package/test scripts
4. Smallest focused command inferred from changed files

Do not report a command as passing unless it was run and the output was checked.

## Finish Sequence

```bash
git status --short
git diff --check
# run focused tests and then full project verification when appropriate
git add <expected files>
git commit -m "<message>"
./.cowork-flow/run task archive <task-name>
./.cowork-flow/run add-session --title "<title>" --commit "<commit>" --summary "<summary>"
```

If the project or user asks not to commit, stop before staging and report the verified state.
