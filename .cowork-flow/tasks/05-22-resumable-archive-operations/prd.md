# Make Archive Operations Resumable

## Goal
Reduce archive-flow failures by making `task archive` and `change archive` safe to rerun after partial progress.

## Requirements
- Use one archive behavior for task and change directory moves.
- If source and archive destination both exist with identical contents, rerun should resume instead of failing immediately.
- If source and archive destination differ, stop with a clear conflict message.
- Verify archive contents before deleting source.
- Preserve existing command names and arguments.
- Resolve change `task` links correctly when written with or without `.cowork-flow/tasks/`.
- Normalize archived task references in archived change metadata.

## Acceptance Criteria
- [ ] Regression tests fail before implementation and pass after implementation.
- [ ] `task archive` can converge from identical source/destination duplicate state.
- [ ] `change archive` can converge from identical source/destination duplicate state.
- [ ] `change validate` accepts `.cowork-flow/tasks/<task>` links without constructing a doubled path.
- [ ] Archived change metadata records `status: archived`, `archived_at`, and normalized archived task path when applicable.
- [ ] Targeted Python tests and template tests pass.

## Technical Notes
- This is an L1 backend/script behavior change.
- Keep the implementation small and standard-library only.
- Prefer automatic resume over adding new CLI flags.
