---
name: record-session
description: Use when recording completed work after verification and project commit or handoff policy has been satisfied
---

[!] **Prerequisite**: This skill should only be used AFTER verification is complete and business changes have been handled according to the project's commit / handoff policy, or when this is a planning / documentation-only session.

Read `AGENTS.md` and `.cowork-flow/workflow.md` for the project's commit policy. The scripts below handle their own commits for `.cowork-flow/` metadata when git is available; do not use this skill to decide who commits business code.

---

## Record Work Progress

### Step 0: Sync Plan Status First

If the current task uses a plan file in `.cowork-flow/plans/`, update it before recording the session:

- Check every completed and verified step as `- [x]`
- Keep incomplete / blocked steps unchecked
- Update the plan's current execution status with the latest review, verification, blocker, or handoff result

Do not archive a task while the plan file still shows stale progress.

### Step 1: Get Context & Check Tasks

```bash
./.cowork-flow/run get-context --mode record
```

[!] Archive tasks whose work is **actually done** — judge by work status, not the `status` field in task.json:
- Business changes handled per project policy? → Archive it
- All acceptance criteria met? → Archive it
- Don't skip archiving just because `status` still says `planning` or `in_progress`

```bash
./.cowork-flow/run task archive <task-name>
```

### Step 2: One-Click Add Session

```bash
# Method 1: Simple parameters
./.cowork-flow/run add-session \
  --title "Session Title" \
  --commit "hash1,hash2" \
  --summary "Brief summary of what was done"

# Method 2: Pass detailed content via stdin
cat << 'EOF' | ./.cowork-flow/run add-session --title "Title" --commit "hash"
| Feature | Description |
|---------|-------------|
| Change | Description |
|--------|-------------|
| API | Updated endpoint contract |
| UI | Synced client interaction |

**Updated Files**:
- `src/module/example-file.ext`
- `docs/spec/example.md`
EOF
```

**Auto-completes**:
- [OK] Appends session to journal-N.md
- [OK] Auto-detects line count, creates new file if >2000 lines
- [OK] Updates index.md (Total Sessions +1, Last Active, line stats, history)
- [OK] Auto-commits .cowork-flow/workspace and .cowork-flow/tasks changes when git is available

---

## Script Command Reference

| Command | Purpose |
|---------|---------|
| `./.cowork-flow/run get-context --mode record` | Get context for record-session |
| `./.cowork-flow/run add-session --title "..." --commit "..."` | **One-click add session (recommended)** |
| `./.cowork-flow/run task archive <name>` | Archive completed task (auto-commits) |
| `./.cowork-flow/run task list` | List active tasks |
