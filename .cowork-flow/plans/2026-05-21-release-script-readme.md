# Release Script README Implementation Plan

> **For agentic workers:** Use cowork-flow fixed agents for execution: dispatch implementation tasks to `cowork-implement` and verification tasks to `cowork-check`. Every dispatch prompt must start with `Active task: <task-dir>`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 添加 npm release shell 脚本，默认 patch 升级版本、发布前完整验证，并同步 README 发布说明。

**Architecture:** 使用独立 POSIX shell 脚本封装发布顺序和参数校验，核心版本升级和发布仍交给 npm 原生命令。测试通过 fake npm 验证命令序列，不触发真实 npm publish。

**Tech Stack:** POSIX shell、Node.js 20、node:test、npm scripts、现有 `npm run test:all` 验证链路。

---

## Current Execution Status

- 状态：实现和验证完成，当前 task 指针已清理
- 当前步骤：收尾检查
- 决策：按用户反馈使用 `scripts/release.sh`，不使用 Node 发版程序；默认 release type 为 `patch`；使用 `npm version <type>` 而不是手写 JSON 版本更新。

## Files

- Create: `scripts/release.sh`
- Create: `test/release.test.js`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `test/package.test.js`
- Modify: `README.md`

### Task 1: Release shell 脚本行为测试

**Files:**
- Create: `test/release.test.js`
- Create later: `scripts/release.sh`

- [x] **Step 1: Write failing tests**

Use `node:test` to run `sh scripts/release.sh` with a fake `npm` executable in `PATH`. Assert command order for default patch, explicit minor, failed verification, and unsupported release type.

- [x] **Step 2: Verify tests fail for missing script**

Run: `npm test -- test/release.test.js`

Observed: FAIL because release script was missing before implementation.

- [x] **Step 3: Implement minimal release script**

Implemented `scripts/release.sh` with allowed release type validation and sequential commands:

```sh
npm run test:all
npm version "$RELEASE_TYPE"
npm publish
```

- [x] **Step 4: Verify release tests pass**

Run: `npm test -- test/release.test.js`

Observed: PASS.

### Task 2: 包元数据与 npm script

**Files:**
- Modify: `test/package.test.js`
- Modify: `package.json`
- Modify: `package-lock.json`

- [x] **Step 1: Write failing package metadata tests**

Added assertions that `package.json` has `scripts.release` and `package-lock.json` root package version equals `package.json` version.

- [x] **Step 2: Verify package metadata tests fail**

Run: `npm test -- test/package.test.js`

Observed: FAIL while `package.json` still pointed to the old release command.

- [x] **Step 3: Add npm release script and fix lock version**

Set `package.json` scripts:

```json
"release": "sh scripts/release.sh"
```

Set `package-lock.json` root package version to `0.0.5` to match `package.json`.

- [x] **Step 4: Verify package metadata tests pass**

Run: `npm test -- test/package.test.js`

Observed: PASS.

### Task 3: README 发布说明

**Files:**
- Modify: `README.md`

- [x] **Step 1: Update README release section**

Replaced the short release paragraph with commands for `npm run release`, `npm run release -- minor`, `npm run release -- major`, and `npm run release -- prerelease`, plus notes about validation and credentials.

- [x] **Step 2: Verify README text**

Run: `rg -n "npm run release|prerelease|NPM_TOKEN" README.md`

Observed: README contains the new release commands and credential note.

### Task 4: Full verification and status sync

**Files:**
- Modify: `.cowork-flow/plans/2026-05-21-release-script-readme.md`
- Modify: `.cowork-flow/tasks/05-21-release-script-readme/task.json`

- [x] **Step 1: Run full verification**

Run: `npm run test:all`

Observed: PASS for Node tests, template tests, and npm pack check.

- [x] **Step 2: Review diff against spec**

Run: `git diff -- package.json package-lock.json scripts/release.sh test/release.test.js test/package.test.js README.md`

Observed: diff contains release script, tests, package metadata, README release docs, and cowork-flow state files.

- [x] **Step 3: Sync plan status**

Updated this plan checkbox state and Current Execution Status with verification evidence.

- [x] **Step 4: Finish cowork-flow task**

Run: `./.cowork-flow/run task finish`

Observed: current task pointer is cleared.
