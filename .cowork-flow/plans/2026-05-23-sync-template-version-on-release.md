# Sync Template Version On Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure `scripts/release.sh` updates `template/.cowork-flow/.version` to the released package version.

**Architecture:** Replace direct `npm version <type>` with `npm version <type> --no-git-tag-version`, read the resulting `package.json` version, write it to `template/.cowork-flow/.version`, then create the release commit/tag explicitly before `npm publish`.

**Tech Stack:** POSIX shell, npm, Node test runner.

---

## Current Status

- Change/spec/task context created.
- Implementation and verification complete.

### Task 1: Add Failing Release Tests

**Files:**
- Modify: `test/release.test.js`

- [x] Step 1: Update fake npm to simulate `npm version <type> --no-git-tag-version` by editing temp package files.
  Verification: targeted release test fails before script implementation because command order differs and `.version` is not updated.

- [x] Step 2: Assert release script writes `template/.cowork-flow/.version` to the new package version and creates commit/tag before publish.
  Verification: `node --test test/release.test.js` fails before implementation.

### Task 2: Implement Release Script Sync

**Files:**
- Modify: `scripts/release.sh`
- Modify: `README.md` if command order text changes

- [x] Step 3: Run tests first, then `npm version <type> --no-git-tag-version`.
- [x] Step 4: Read `package.json` version and write `template/.cowork-flow/.version`.
- [x] Step 5: Stage version files, create release commit and tag, then publish.

### Task 3: Verify and Sync

**Files:**
- Check: `test/release.test.js`
- Check: `scripts/release.sh`

- [x] Step 6: Run `node --test test/release.test.js`.
- [x] Step 7: Run `npm run test:all` if feasible.
- [x] Step 8: Sync task/change/plan/session status.
