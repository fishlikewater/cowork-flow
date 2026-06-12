# Task 1.7: Update template for Flow system

**Goal:** Update template files to reflect Flow system: remove task.json references, add SQLite db gitignore.

**Scope:**
- Create 	emplate/.gitignore: add .cowork-flow/cowork-flow.db and 	asks.backup/
- Remove any task.json creation logic from init scripts
- Verify new project install creates cowork-flow.db on first task create

**Files:**
- Create: 	emplate/.gitignore
- Check: 	emplate/.cowork-flow/ (if task.json references exist)

**Acceptance:**
- cowork-flow init test-proj --platform opencode succeeds
- cd test-proj && ./cowork-flow/run task create "test" creates cowork-flow.db
- task.json file NOT created in new project
- tasks.backup/ and cowork-flow.db are gitignored

**Reference:** .cowork-flow/plans/2026-06-11-flow-pattern-engine.md Task 1.7