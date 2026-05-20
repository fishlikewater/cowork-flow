---
name: finish-work
description: Use when finishing implementation work before handoff, submission, or project-defined commit
---

# Finish Work - Pre-Commit Checklist

Before handoff, submission, or commit according to the project's policy, use this checklist to ensure work completeness.

**Timing**: After code is written and tested, before final handoff or commit.

---

## Project Facts Source

Do not edit this skill to replace commands or policy. Read project-specific facts from:

1. `AGENTS.md` - test commands, commit policy, language and collaboration rules
2. `.cowork-flow/workflow.md` - workflow gates and completion definition
3. `.cowork-flow/config.yaml` - optional verification command lists
4. `.cowork-flow/spec/` - project-specific implementation contracts

If verification commands are listed in `.cowork-flow/config.yaml`, run them. If not, use the commands defined in `AGENTS.md` or infer the smallest relevant checks from the project files, then state the assumption.

---

## Checklist

### 1. Code Quality

- [ ] Read `AGENTS.md` and `.cowork-flow/config.yaml` for verification commands?
- [ ] Static checks pass, if configured?
- [ ] Build / type check pass, if configured?
- [ ] Tests pass, if configured?
- [ ] Temporary debug output removed?
- [ ] Unsafe bypasses / force assertions reviewed?

### 2. Code-Spec Sync

**Code-Spec Docs**:
- [ ] Does `.cowork-flow/spec/backend/` need updates?
  - New patterns, new modules, new conventions, if backend specs exist
- [ ] Does `.cowork-flow/spec/frontend/` need updates?
  - New components, new hooks, new patterns, if frontend specs exist
- [ ] Does `.cowork-flow/spec/guides/` need updates?
  - New cross-layer flows, lessons from bugs, if guide specs exist

**Key Question**: 
> "If I fixed a bug or discovered something non-obvious, should I document it so future me (or others) won't hit the same issue?"

If YES -> Update the relevant code-spec doc.

### 2.5. Code-Spec Hard Block (Infra/Cross-Layer)

If this change touches infra or cross-layer contracts, this is a blocking checklist:

- [ ] Spec content is executable (real signatures/contracts), not principle-only text
- [ ] Includes file path + command/API name + payload field names
- [ ] Includes validation and error matrix
- [ ] Includes Good/Base/Bad cases
- [ ] Includes required tests and assertion points

**Block Rule**:
If infra/cross-layer changed but the related spec is still abstract, do NOT finish. Run `$update-spec` manually first.

### 2.6. Plan Sync

If this task has a plan file in `.cowork-flow/plans/`:

- [ ] Completed and verified plan steps are checked (`- [x]`)
- [ ] Incomplete or blocked steps remain unchecked and are not falsely marked done
- [ ] The plan's `Current Execution Status` (or equivalent section) reflects the latest verification / review / blocker state
- [ ] Plan status matches the real task state before commit, archive, or completion claims

### 3. API Changes

If you modified API endpoints:

- [ ] Input schema updated?
- [ ] Output schema updated?
- [ ] API documentation updated?
- [ ] Client code updated to match?

### 4. Database Changes

If you modified database schema:

- [ ] Migration file created?
- [ ] Schema file updated?
- [ ] Related queries updated?
- [ ] Seed data updated (if applicable)?

### 5. Cross-Layer Verification

If the change spans multiple layers:

- [ ] Data flows correctly through all layers?
- [ ] Error handling works at each boundary?
- [ ] Types are consistent across layers?
- [ ] Loading states handled?

### 6. Manual Testing

- [ ] Feature works in browser/app?
- [ ] Edge cases tested?
- [ ] Error states tested?
- [ ] Works after page refresh?

---

## Quick Check Flow

```bash
# 1. View changes
git status
git diff --name-only

# 2. Run project verification commands from AGENTS.md or .cowork-flow/config.yaml

# 3. Based on changed files, check relevant items above
```

---

## Common Oversights

| Oversight | Consequence | Check |
|-----------|-------------|-------|
| Code-spec docs not updated | Others don't know the change | Check .cowork-flow/spec/ |
| Spec text is abstract only | Easy regressions in infra/cross-layer changes | Require signature/contract/matrix/cases/tests |
| Migration not created | Schema out of sync | Check migration directory |
| Types/contracts not synced | Runtime errors | Check shared contract definitions |
| Tests not updated | False confidence | Run full test suite |
| Console.log left in | Noisy production logs | Search for console.log |
| Plan checkboxes not synced | Docs drift from real progress | Check `.cowork-flow/plans/` before finishing |

---

## Relationship to Other Commands

```
Development Flow:
  Write code -> Test -> $finish-work -> project commit/handoff policy -> $record-session
                          |                                      |
                   Ensure completeness                      Record progress
                   
Debug Flow:
  Hit bug -> Fix -> $break-loop -> Knowledge capture
                       |
                  Deep analysis
```

- `$finish-work` - Check work completeness (this skill)
- `$record-session` - Record session and completed work
- `$break-loop` - Deep analysis after debugging

---

## Core Principle

> **Delivery includes not just code, but also documentation, verification, and knowledge capture.**

Complete work = Code + Docs + Tests + Verification
