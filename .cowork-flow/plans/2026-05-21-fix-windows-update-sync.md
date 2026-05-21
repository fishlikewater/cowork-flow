# Fix Windows Update Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Windows 下 `cowork-flow update` 调用 npm 失败的问题，并让 `sync` 只保护用户指定的 `.cowork-flow` 路径。

**Architecture:** 保持现有 CLI 结构不变，只在 `src/lib/package-info.js` 中集中封装 npm 子进程调用选项，在 `src/lib/copy-template.js` 中收窄 sync 保护规则。测试继续使用 Node 内置 `node:test`，避免新增依赖。

**Tech Stack:** Node.js ESM, `node:test`, `node:assert/strict`, existing cowork-flow CLI helpers.

---

## Current Execution Status

- Status: archived, ready to commit
- Current task: archived to `.cowork-flow/tasks/archive/2026-05/05-21-fix-windows-update-sync`; Python template suite blocked by Windows temp-directory permissions
- Last verified command: `.\.cowork-flow\run.cmd task validate .cowork-flow/tasks/archive/2026-05/05-21-fix-windows-update-sync`

## Files

- Modify: `src/lib/package-info.js` - add a small helper for npm command execution options and use it in npm query/install.
- Modify: `test/update.test.js` - cover Windows npm command options.
- Modify: `src/lib/copy-template.js` - protect only requested `.cowork-flow` paths during sync.
- Modify: `test/sync.test.js` - cover `.cowork-flow/scripts/` refresh and newly unprotected template paths.
- Modify: `.cowork-flow/changes/fix-windows-update-sync/change.yaml` - link plan and task after task creation.

## Task 1: Make npm execution Windows-compatible

**Files:**
- Modify: `test/update.test.js`
- Modify: `src/lib/package-info.js`

- [x] **Step 1: Write the failing test**

Add this import and tests in `test/update.test.js`:

```js
import { compareVersions, npmCommandOptions } from '../src/lib/package-info.js';

test('npmCommandOptions enables shell execution on Windows', () => {
  assert.deepEqual(npmCommandOptions('win32'), { shell: true });
});

test('npmCommandOptions keeps direct execution on non-Windows platforms', () => {
  assert.deepEqual(npmCommandOptions('linux'), {});
  assert.deepEqual(npmCommandOptions('darwin'), {});
});
```

- [x] **Step 2: Run the focused test to verify it fails**

Run: `node --test --test-isolation=none test/update.test.js`

Expected: FAIL because `npmCommandOptions` is not exported.

- [x] **Step 3: Write minimal implementation**

In `src/lib/package-info.js`, add:

```js
export function npmCommandOptions(platform = process.platform) {
  return platform === 'win32' ? { shell: true } : {};
}
```

Then pass `...npmCommandOptions()` into both npm subprocess calls:

```js
const result = await execFileAsync('npm', ['view', packageName, 'version'], {
  encoding: 'utf8',
  ...npmCommandOptions()
});
```

```js
const child = spawn('npm', ['install', '-g', packageSpec], {
  stdio: 'inherit',
  ...npmCommandOptions()
});
```

- [x] **Step 4: Run the focused test to verify it passes**

Run: `node --test --test-isolation=none test/update.test.js`

Expected: PASS.

## Task 2: Narrow sync protection for `.cowork-flow`

**Files:**
- Modify: `test/sync.test.js`
- Modify: `src/lib/copy-template.js`

- [x] **Step 1: Write the failing sync tests**

Extend the existing `sync updates safe template files and preserves protected files` test with:

```js
await writeFile(join(target, '.cowork-flow', 'scripts', 'task.py'), 'old task script\n', 'utf8');
await writeFile(join(target, '.cowork-flow', 'workflow.md'), 'old workflow\n', 'utf8');
await writeFile(join(target, '.cowork-flow', 'agent-team', 'agents.yaml'), 'old agents\n', 'utf8');
await writeFile(join(target, '.cowork-flow', 'config.yaml'), 'custom config\n', 'utf8');
```

Add assertions after sync:

```js
assert.equal(
  await readText(join(target, '.cowork-flow', 'scripts', 'task.py')),
  await readText(join(templateRoot, '.cowork-flow', 'scripts', 'task.py'))
);
assert.equal(
  await readText(join(target, '.cowork-flow', 'workflow.md')),
  await readText(join(templateRoot, '.cowork-flow', 'workflow.md'))
);
assert.equal(
  await readText(join(target, '.cowork-flow', 'agent-team', 'agents.yaml')),
  await readText(join(templateRoot, '.cowork-flow', 'agent-team', 'agents.yaml'))
);
assert.equal(await readText(join(target, '.cowork-flow', 'config.yaml')), 'custom config\n');
```

Replace the old `sync preserves project-level agent-team configuration` expectation with an expectation that agent-team is refreshed, because it is no longer protected by the requested whitelist.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `node --test --test-isolation=none test/sync.test.js`

Expected: FAIL on `.cowork-flow/workflow.md` or `.cowork-flow/agent-team/agents.yaml` still being protected.

- [x] **Step 3: Write minimal implementation**

In `src/lib/copy-template.js`, keep these protected entries:

```js
const PROTECTED_SYNC_FILES = new Set([
  '.cowork-flow/config.yaml'
]);

const PROTECTED_SYNC_PREFIXES = [
  '.cowork-flow/spec/',
  '.cowork-flow/workspace/',
  '.cowork-flow/tasks/',
  '.cowork-flow/changes/',
  '.cowork-flow/plans/'
];
```

Keep `AGENTS.md` handled by `buildAgentsSyncAction`, because that is outside `.cowork-flow` and preserves project custom text while refreshing the managed block.

- [x] **Step 4: Run the focused test to verify it passes**

Run: `node --test --test-isolation=none test/sync.test.js`

Expected: PASS.

## Task 3: Verify and sync workflow state

**Files:**
- Modify: `.cowork-flow/tasks/<task>/prd.md`
- Modify: `.cowork-flow/tasks/<task>/implement.jsonl`
- Modify: `.cowork-flow/tasks/<task>/check.jsonl`
- Modify: `.cowork-flow/tasks/<task>/debug.jsonl`
- Modify: `.cowork-flow/changes/fix-windows-update-sync/change.yaml`
- Modify: `.cowork-flow/plans/2026-05-21-fix-windows-update-sync.md`

- [x] **Step 1: Run full Node tests**

Run: `npm test -- --test-isolation=none`

Expected: PASS.

- [x] **Step 2: Run pack check if npm cache is available**

Run: `npm run pack:check`

Expected: PASS or document any environment/cache failure.

Observed on Windows: `npm run pack:check` fails because the package script uses POSIX-style `npm_config_cache=/tmp/...`. Equivalent command passed:

```powershell
$cache = Join-Path $env:TEMP "cowork-flow-npm-cache-codex"; npm --cache $cache pack --dry-run --json
```

- [x] **Step 3: Update plan status**

Set `Current Execution Status` to:

```md
- Status: implemented
- Current task: verification complete; Python template suite blocked by Windows temp-directory permissions
- Last verified command: `.\.cowork-flow\run.cmd change validate fix-windows-update-sync`
```

- [x] **Step 4: Validate the change metadata**

Run: `.\.cowork-flow\run.cmd change validate fix-windows-update-sync`

Expected: PASS.

## Verification Notes

- `node --test --test-isolation=none test/update.test.js`: PASS, 7/7.
- `node --test --test-isolation=none test/sync.test.js`: PASS, 8/8.
- `npm test -- --test-isolation=none`: PASS, 27/27.
- `npm run pack:check`: failed on Windows because the npm script uses POSIX env-var prefix syntax.
- Windows-equivalent `npm --cache <temp> pack --dry-run --json`: PASS.
- `.\template\.cowork-flow\run.cmd python -m unittest discover tests -v`: attempted, blocked by Windows temp-directory `PermissionError` while tests create temporary repositories; this is not treated as passed.
- `.\.cowork-flow\run.cmd change validate fix-windows-update-sync`: PASS.
- `.\.cowork-flow\run.cmd task validate .cowork-flow/tasks/05-21-fix-windows-update-sync`: PASS.

## Self-Review

- Spec coverage: Task 1 covers Windows npm query/install; Task 2 covers sync protection whitelist; Task 3 covers verification and metadata.
- Placeholder scan: no placeholder steps remain.
- Type consistency: `npmCommandOptions(platform = process.platform)` is the only new exported helper and is used by `fetchLatestVersion` and `runGlobalInstall`.
