import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { assetDriftVerdict, doctorVerdict, driftVerdict } from '../scripts/release-gates.js';
import { createTempDir, exists, readText } from './helpers/fs.js';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));
const cliPath = join(repoRoot, 'bin', 'cowork-flow.js');
const templateRoot = join(repoRoot, 'template');
const packageVersion = JSON.parse(
  await readFile(join(repoRoot, 'package.json'), 'utf8')
).version;

function runnerPath(instanceDir) {
  return join(
    instanceDir,
    '.cowork-flow',
    process.platform === 'win32' ? 'run.cmd' : 'run'
  );
}

// A .cmd entry point has to go through a shell, and a shell takes one command
// string — so every argument is quoted here rather than handed over as a list.
// Arguments carrying a double quote are avoided by design for that reason.
function quoteArg(value) {
  const text = String(value);
  return /\s/.test(text) ? `"${text}"` : text;
}

function spawn(command, args, options = {}) {
  const useShell = process.platform === 'win32' && command.endsWith('.cmd');
  return spawnSync(
    useShell ? [command, ...args].map(quoteArg).join(' ') : command,
    useShell ? [] : args,
    {
      encoding: 'utf8',
      shell: useShell,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', ...options.env },
      cwd: options.cwd
    }
  );
}

function nodeCli(args, options = {}) {
  return spawn(process.execPath, [cliPath, ...args], options);
}

function git(instanceDir, args) {
  const result = spawn('git', args, { cwd: instanceDir });
  assert.equal(result.status, 0, `git ${args.join(' ')}: ${result.stderr}`);
  return result;
}

// Every scenario drives the instance the way a user does — through the runner
// that install created — so what is verified is the shipped artifact, not this
// checkout's modules. A machine without a usable interpreter reports the
// scenario as skipped; it must never read as a pass. `requiresRunner: false` is
// for the paths that only touch the Node CLI, which must not be skipped for a
// missing interpreter they never use.
async function installedInstance(t, contextId, { requiresRunner = true } = {}) {
  const dir = await createTempDir(t);
  const init = nodeCli(['init', dir, '--developer', 'codex', '--platform', 'codex']);
  if (init.status !== 0) {
    return { unavailable: `init exited ${init.status}: ${init.stderr.trim()}` };
  }
  await writeFile(join(dir, '.gitignore'), '.cowork-flow/\n', 'utf8');
  git(dir, ['init', '-q']);
  git(dir, ['config', 'user.email', 'compliance@example.test']);
  git(dir, ['config', 'user.name', 'compliance']);
  git(dir, ['config', 'core.autocrlf', 'false']);
  git(dir, ['add', '-A']);
  git(dir, ['commit', '-qm', 'install baseline']);

  if (requiresRunner) {
    const probe = spawn(runnerPath(dir), ['task', 'next'], {
      cwd: dir,
      env: { COWORK_FLOW_CONTEXT_ID: contextId }
    });
    if (probe.status !== 0) {
      return {
        unavailable: `instance runner exited ${probe.status}: ${(probe.stderr || probe.stdout).trim()}`
      };
    }
  }
  return {
    dir,
    run(args, extraEnv = {}) {
      return spawn(runnerPath(dir), args, {
        cwd: dir,
        env: { COWORK_FLOW_CONTEXT_ID: contextId, ...extraEnv }
      });
    },
    cli(args) {
      return nodeCli(args, { cwd: dir });
    },
    taskDir(name) {
      return join('.cowork-flow', 'tasks', name);
    }
  };
}

async function writePlanningArtifacts(instance, name, { anchor = true, specs = [] } = {}) {
  const taskDir = join(instance.dir, instance.taskDir(name));
  if (anchor) {
    await writeFile(
      join(taskDir, 'decision-anchor.md'),
      `# Decision Anchor\n\n## 目标\ncompliance scenario\n\n## 验收标准\n- [ ] AC-001: scenario reaches its end state\n\n## 验证命令\n规范核对：逐条核对 \`.cowork-flow/spec/backend/\` 适用规范 → pass（理由：scenario）。\n`,
      'utf8'
    );
  }
  const entries = [{ file: 'src/scenario.js', reason: 'scenario', type: 'planned-file' }];
  // A declared spec pointer is what puts that spec's body inside the review
  // fingerprint; without one, editing the spec changes nothing the receipt
  // covers.
  for (const spec of specs) {
    entries.push({ file: spec, reason: 'applicable spec for the review', type: 'file' });
  }
  await writeFile(
    join(taskDir, 'implement.jsonl'),
    entries.map((entry) => `${JSON.stringify(entry)}\n`).join(''),
    'utf8'
  );
}

function strictPlanText(name) {
  return [
    `# ${name} 实施计划`,
    '',
    '**目标:** compliance scenario',
    '',
    '## 目标',
    'compliance scenario',
    '',
    '## 验收标准',
    '- AC-001: scenario reaches its end state',
    '',
    '## 全局约束',
    '- Do not expand the scenario.',
    '',
    '## 文件边界',
    '- `src/scenario.js`',
    '',
    '## 任务',
    '### 任务 1：scenario',
    '',
    '**目的**',
    '- Reach the scenario end state.',
    '',
    '**代码事实来源**',
    '- Read: `src/scenario.js`',
    '',
    '**文件边界**',
    '- Modify: `src/scenario.js`',
    '',
    '**关键符号**',
    '- Change: `scenario`',
    '',
    '**实现说明**',
    '```javascript',
    'const scenario = true;',
    '```',
    '',
    '**测试证明**',
    '- The scenario reaches its end state.',
    '',
    '**验证命令**',
    '```bash',
    'node --check src/scenario.js',
    '```',
    '',
    '**完成条件**',
    '- The verification command exits 0.',
    '',
    '**禁止漂移**',
    '- Do not expand the scenario.',
    '',
    '**偏差条件**',
    '- Stop if the scenario conflicts with the code facts.',
    '',
    '## 最终验证',
    '规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 → pass（理由：scenario）。',
    ''
  ].join('\n');
}

async function closeOutEvidence(instance, name) {
  const taskDir = join(instance.dir, instance.taskDir(name));
  await writeFile(
    join(taskDir, 'evidence.jsonl'),
    `${JSON.stringify({ ac: 'AC-001', kind: 'manual', ref: 'scenario', note: 'scenario' })}\n`,
    'utf8'
  );
  const anchorPath = join(taskDir, 'decision-anchor.md');
  await writeFile(
    anchorPath,
    (await readText(anchorPath)).replace('- [ ] AC-001', '- [x] AC-001'),
    'utf8'
  );
}

async function taskStatus(instance, name) {
  const raw = await readText(join(instance.dir, instance.taskDir(name), 'task.json'));
  return JSON.parse(raw).status;
}

async function finalizeTask(instance, name) {
  const finalized = instance.run(['plan', 'finalize', instance.taskDir(name)]);
  assert.equal(finalized.status, 0, finalized.stderr);
}

// A strict task needs its declared shape and a finalized plan before it can
// start: a dev type, a bound plan, and a non-empty context index.
async function createStartedTask(instance, name, { specs = [] } = {}) {
  await mkdir(join(instance.dir, '.cowork-flow', 'plans'), { recursive: true });
  await writeFile(
    join(instance.dir, '.cowork-flow', 'plans', `${name}.md`),
    strictPlanText(name),
    'utf8'
  );
  const created = instance.run([
    'task', 'next', '--run',
    '--title', name, '--slug', name, '--assignee', 'compliance',
    '--type', 'backend', '--from-plan', `.cowork-flow/plans/${name}.md`
  ]);
  assert.equal(created.status, 0, created.stderr);
  await writePlanningArtifacts(instance, name, { specs });
  await finalizeTask(instance, name);
  const started = instance.run(['task', 'next', instance.taskDir(name), '--run']);
  assert.equal(started.status, 0, started.stderr);
  return JSON.parse(await readText(join(instance.dir, instance.taskDir(name), 'task.json')));
}

async function bindSubagent(instance, { name, role, agentType, bind = true }) {
  const init = instance.run([
    'subagent', 'init',
    '--title', `compliance-${role}`,
    '--role', role,
    '--agent-type', agentType,
    '--execution-task-dir', instance.taskDir(name),
    '--source', 'compliance',
    '--goal', 'scenario',
    '--expected-output', 'scenario',
    '--host', 'zcode'
  ]);
  assert.equal(init.status, 0, init.stderr);
  const context = JSON.parse(init.stdout.slice(init.stdout.indexOf('{')));
  // `bind: false` leaves a context that exists but was never attached to a host
  // session — the state the write path will not submit a receipt from.
  if (!bind) {
    return context;
  }
  const bindRun = instance.run(['subagent', 'bind', context.runtimeContextId, context.hostContextKey]);
  assert.equal(bindRun.status, 0, bindRun.stderr);
  return context;
}

async function recordReviewReceipt(instance, name) {
  const context = await bindSubagent(instance, {
    name,
    role: 'check',
    agentType: 'cowork-check'
  });
  const fingerprint = await currentFingerprint(instance, name);
  const review = instance.run([
    'subagent', 'check-review', context.runtimeContextId,
    '--task-dir', instance.taskDir(name),
    '--result', 'pass',
    '--changed-fingerprint', fingerprint
  ], { COWORK_FLOW_CONTEXT_ID: context.hostContextKey });
  assert.equal(review.status, 0, review.stderr);
  assert.match(review.stdout, /"result": "pass"/);
}

// The change fingerprint the completion gate compares a receipt against.
async function currentFingerprint(instance, name) {
  const state = instance.run(['state', instance.taskDir(name), '--json']);
  assert.equal(state.status, 0, state.stderr);
  return JSON.parse(state.stdout).changeFingerprint;
}

// Plant a receipt the way the write path refuses to: straight into
// review.jsonl. Everything else about it can be correct — a passing result and
// the current fingerprint — because what the gate has to catch is the claim of
// provenance, not the shape of the record.
async function writeReviewReceipt(instance, name, { contextId, fingerprint }) {
  await writeFile(
    join(instance.dir, instance.taskDir(name), 'review.jsonl'),
    `${JSON.stringify({
      schemaVersion: 1,
      contextId,
      agentType: 'cowork-check',
      result: 'pass',
      changedFingerprint: fingerprint,
      findings: [],
      bindingEvidence: 'hand-written'
    })}
`,
    'utf8'
  );
}

// The release check is only worth what it can refuse: a suite cannot express
// "this checkout drifted" or "doctor found an error", so the gates that decide
// those have to be wired in and have to fail when they should.
test('release:check carries the drift and doctor gates, and they refuse real failures', async () => {
  const packageInfo = JSON.parse(await readFile(join(repoRoot, 'package.json'), 'utf8'));
  assert.match(
    packageInfo.scripts['release:check'],
    /^npm run test:all && node scripts\/release-gates\.js$/
  );

  assert.equal(driftVerdict({ wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [] }).status, 'pass');
  // Each drift key is pinned on its own: a key dropped from the list would
  // otherwise keep every assertion here green.
  for (const key of ['wouldCopy', 'wouldRemoveObsolete', 'hostAssetRefresh']) {
    const single = driftVerdict({
      wouldCopy: [],
      wouldRemoveObsolete: [],
      hostAssetRefresh: [],
      [key]: [{ path: 'AGENTS.md' }]
    });
    assert.equal(single.status, 'fail', `${key} must count as drift`);
    assert.match(single.detail, new RegExp(`${key}=1`));
  }
  assert.match(driftVerdict({
    wouldCopy: [{ path: 'AGENTS.md' }],
    wouldRemoveObsolete: [{ path: '.cowork-flow/scripts/task.py' }],
    hostAssetRefresh: []
  }).detail, /source:refresh/);
  // A retained retirement is a decision the user owes, not drift: source:refresh
  // leaves content it cannot prove it owns, and failing the release on that
  // would force deleting someone else's file.
  const retained = driftVerdict({ wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [], wouldKeep: [{ path: '.agents/skills/tdd' }] });
  assert.equal(retained.status, 'pass');
  assert.match(retained.detail, /wouldKeep/);

  // The live copies `sync --force` rewrites (.claude/**, .codex/**, skills) are
  // judged by their own verdict off the same readiness shape; each key is pinned
  // on its own for the same reason as above.
  assert.equal(assetDriftVerdict({ wouldCopy: [], wouldRemoveObsolete: [] }).status, 'pass');
  for (const key of ['wouldCopy', 'wouldRemoveObsolete']) {
    const single = assetDriftVerdict({
      wouldCopy: [],
      wouldRemoveObsolete: [],
      [key]: [{ path: '.claude/agents/cowork-check.md' }]
    });
    assert.equal(single.status, 'fail', `${key} must count as asset drift`);
    assert.match(single.detail, new RegExp(`${key}=1`));
    assert.match(single.detail, /project sync/);
  }
  // The failing detail has to name what drifted: a count alone sends its reader
  // hunting through a two-hundred-entry readiness report.
  assert.match(
    assetDriftVerdict({
      wouldCopy: [{ path: '.claude/agents/cowork-check.md' }],
      wouldRemoveObsolete: []
    }).detail,
    /\.claude\/agents\/cowork-check\.md/
  );
  // Protected files are a normal state of every instance, not drift.
  const protectedOnly = assetDriftVerdict({
    wouldCopy: [],
    wouldRemoveObsolete: [],
    wouldSkipProtected: [{ path: '.cowork-flow/.developer' }]
  });
  assert.equal(protectedOnly.status, 'pass');
  assert.match(protectedOnly.detail, /wouldSkipProtected/);
  // The report shape is part of the contract: a renamed or non-array key must
  // fail loudly, not read as "no drift" forever.
  const renamed = assetDriftVerdict({ wouldCopy: [], wouldRename: [] });
  assert.equal(renamed.status, 'fail');
  assert.match(renamed.detail, /wouldRemoveObsolete/);
  assert.match(renamed.detail, /cannot judge drift/);
  assert.equal(assetDriftVerdict({ wouldCopy: [], wouldRemoveObsolete: null }).status, 'fail');

  assert.equal(doctorVerdict({ ok: true, errors: [] }).status, 'pass');
  assert.equal(doctorVerdict({ ok: false, errors: [{ code: 'RUNTIME-TOPOLOGY-001' }] }).status, 'fail');
  // `ok` alone is not the verdict: an error-severity issue fails even if a
  // future doctor forgets to flip the flag.
  assert.equal(doctorVerdict({ ok: true, errors: [{ code: 'X' }] }).status, 'fail');

  const ran = spawn(process.execPath, [join(repoRoot, 'scripts', 'release-gates.js')], { cwd: repoRoot });
  assert.match(ran.stdout, /release-gates: self-instance-drift (pass|fail|skip)/);
  assert.match(ran.stdout, /release-gates: self-instance-asset-drift (pass|fail|skip)/);
  assert.match(ran.stdout, /release-gates: doctor (pass|fail|skip)/);
  // The exit code has to follow the verdicts it just printed: a run that
  // reported a failure and still exited 0 would be a gate nobody hears.
  const reportedFailure = /release-gates: \S+ fail/.test(ran.stdout);
  assert.equal(ran.status, reportedFailure ? 1 : 0, ran.stderr);
});

// The gate reads its repository from its own location, so a throwaway root with
// a stubbed CLI is enough to drive the failing branches the real checkout only
// reaches when something is actually wrong. `cliStatus`/`runnerStatus` let a
// stub fail the way the real tools do: a nonzero exit with the report on stdout.
async function gateHarness(t, {
  readiness,
  syncReadiness = readiness,
  doctor,
  cliStatus = 0,
  syncStatus = cliStatus,
  runnerStatus = 0
}) {
  const root = await createTempDir(t);
  await mkdir(join(root, 'scripts'), { recursive: true });
  await mkdir(join(root, 'bin'), { recursive: true });
  await mkdir(join(root, '.cowork-flow'), { recursive: true });
  await copyFile(
    join(repoRoot, 'scripts', 'release-gates.js'),
    join(root, 'scripts', 'release-gates.js')
  );
  // Both dry-run gates read the same report shape, so the stub answers each run
  // from its own fixture and each can fail without the other: a shared payload
  // would blur which verdict actually fired.
  await writeFile(
    join(root, 'bin', 'cowork-flow.js'),
    "const sync = process.argv.includes('sync');\n"
      + `const payload = sync ? ${JSON.stringify(JSON.stringify(syncReadiness))} : ${JSON.stringify(JSON.stringify(readiness))};\n`
      + "process.stdout.write('readiness=' + payload + '\\n');\n"
      + 'process.exit(sync ? ' + syncStatus + ' : ' + cliStatus + ');\n',
    'utf8'
  );
  const doctorJson = JSON.stringify(doctor);
  if (process.platform === 'win32') {
    await writeFile(
      join(root, '.cowork-flow', 'run.cmd'),
      `@echo off\r\necho ${doctorJson}\r\nexit /b ${runnerStatus}\r\n`,
      'utf8'
    );
  } else {
    await writeFile(
      join(root, '.cowork-flow', 'run'),
      `#!/bin/sh\nprintf '%s\\n' '${doctorJson}'\nexit ${runnerStatus}\n`,
      { encoding: 'utf8', mode: 0o755 }
    );
  }
  return spawn(process.execPath, [join(root, 'scripts', 'release-gates.js')], { cwd: root });
}

test('the release gates fail closed and say so in the exit code', async (t) => {
  const clean = await gateHarness(t, {
    readiness: { wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [] },
    doctor: { ok: true, errors: [] }
  });
  assert.equal(clean.status, 0, clean.stdout + clean.stderr);
  assert.match(clean.stdout, /self-instance-drift pass/);
  assert.match(clean.stdout, /self-instance-asset-drift pass/);
  assert.match(clean.stdout, /doctor pass/);

  const drifted = await gateHarness(t, {
    readiness: {
      wouldCopy: [{ path: 'AGENTS.md' }],
      wouldRemoveObsolete: [],
      hostAssetRefresh: []
    },
    doctor: { ok: true, errors: [] }
  });
  assert.equal(drifted.status, 1, drifted.stdout + drifted.stderr);
  assert.match(drifted.stdout, /self-instance-drift fail/);
  assert.match(drifted.stdout, /wouldCopy=1/);

  // A live copy the self-instance check never looks at: the sync verdict has to
  // fail on it alone, naming the file step 5 would otherwise overwrite.
  const assetDrifted = await gateHarness(t, {
    readiness: { wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [] },
    syncReadiness: {
      wouldCopy: [{ path: '.claude/agents/cowork-check.md' }],
      wouldRemoveObsolete: []
    },
    doctor: { ok: true, errors: [] }
  });
  assert.equal(assetDrifted.status, 1, assetDrifted.stdout + assetDrifted.stderr);
  assert.match(assetDrifted.stdout, /self-instance-drift pass/);
  assert.match(assetDrifted.stdout, /self-instance-asset-drift fail/);
  assert.match(assetDrifted.stdout, /\.claude\/agents\/cowork-check\.md/);

  const sick = await gateHarness(t, {
    readiness: { wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [] },
    doctor: { ok: false, errors: [{ code: 'RUNTIME-TOPOLOGY-001' }] }
  });
  assert.equal(sick.status, 1, sick.stdout + sick.stderr);
  assert.match(sick.stdout, /doctor fail/);
  assert.match(sick.stdout, /RUNTIME-TOPOLOGY-001/);
});

// A gate that fails without saying why sends its reader hunting. doctor exits 1
// on an error-severity issue and prints the report on stdout, so a detail built
// from stderr alone would be empty exactly when it is needed.
test('a gate that fails on a nonzero exit still carries the report', async (t) => {
  const driftCrashed = await gateHarness(t, {
    readiness: { wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [] },
    doctor: { ok: true, errors: [] },
    cliStatus: 1
  });
  assert.equal(driftCrashed.status, 1, driftCrashed.stdout + driftCrashed.stderr);
  assert.match(driftCrashed.stdout, /self-instance-drift fail/);
  assert.match(driftCrashed.stdout, /dev refresh --dry-run exited 1: readiness=/);

  const assetCrashed = await gateHarness(t, {
    readiness: { wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [] },
    syncStatus: 1,
    doctor: { ok: true, errors: [] }
  });
  assert.equal(assetCrashed.status, 1, assetCrashed.stdout + assetCrashed.stderr);
  assert.match(assetCrashed.stdout, /self-instance-asset-drift fail/);
  assert.match(assetCrashed.stdout, /project sync . --dry-run exited 1: readiness=/);
  // One crashed gate must not swallow the others: doctor still reports.
  assert.match(assetCrashed.stdout, /doctor pass/);

  const doctorCrashed = await gateHarness(t, {
    readiness: { wouldCopy: [], wouldRemoveObsolete: [], hostAssetRefresh: [] },
    doctor: { ok: false, errors: [{ code: 'RUNTIME-TOPOLOGY-001' }] },
    runnerStatus: 1
  });
  assert.equal(doctorCrashed.status, 1, doctorCrashed.stdout + doctorCrashed.stderr);
  assert.match(doctorCrashed.stdout, /doctor fail/);
  assert.match(doctorCrashed.stdout, /RUNTIME-TOPOLOGY-001/);
});

test('a missing interpreter skips only the scenarios that need the runtime', async () => {
  // The upgrade path is Node-only. Losing the interpreter must cost exactly the
  // coverage that needs it — not the coverage that does not, and never a pass.
  const env = { ...process.env, COWORK_FLOW_PYTHON: join(repoRoot, 'no-such-python') };
  // The runner marks this process as a test child; inheriting that makes the
  // nested `node --test` suppress its own reporter, which would turn this
  // assertion into a check of an empty string.
  delete env.NODE_TEST_CONTEXT;
  // The marker assertions below read the spec reporter's `✔`/`﹣` lines. The
  // unpiped default reporter prints TAP through Node 20 and spec from 22 on,
  // so the reporter is pinned rather than trusting the version default.
  const ran = spawnSync(process.execPath, [
    '--test', '--test-reporter=spec', '--test-name-pattern', 'upgrades in place', 'test/compliance-e2e.test.js'
  ], { cwd: repoRoot, encoding: 'utf8', env });
  assert.equal(ran.status, 0, ran.stderr);
  assert.match(ran.stdout, /✔ an installed instance upgrades in place/);
  assert.doesNotMatch(ran.stdout, /﹣ an installed instance upgrades in place/);
});

test('an installed instance runs the strict task path and refuses to complete it unreviewed', async (t) => {
  const instance = await installedInstance(t, 'compliance_normal');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }
  const name = '10-09-normal';
  const task = await createStartedTask(instance, name);
  assert.equal(task.meta.gateProfile, 'strict', 'a new task must be born strict');
  assert.equal(task.status, 'in_progress');

  await closeOutEvidence(instance, name);
  const reviewed = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.equal(reviewed.status, 0, reviewed.stderr);
  assert.equal(await taskStatus(instance, name), 'review');

  // The counterexample that makes this scenario worth running: a strict task
  // that never saw an independent review must not be completable.
  const unreviewed = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.notEqual(unreviewed.status, 0);
  assert.match(unreviewed.stdout + unreviewed.stderr, /independent review receipt/);
  assert.equal(await taskStatus(instance, name), 'review');

  await recordReviewReceipt(instance, name);
  const completed = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.equal(completed.status, 0, completed.stderr);
  assert.equal(await taskStatus(instance, name), 'completed');

  const archived = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'archive']);
  assert.equal(archived.status, 0, archived.stderr);
  assert.equal(
    existsSync(join(instance.dir, '.cowork-flow', 'tasks', 'archive', '2026-10', name)),
    true
  );
});

test('an installed instance blocks a strict task whose bound plan is not template-shaped', async (t) => {
  const instance = await installedInstance(t, 'compliance_plan_shape');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }

  const name = '10-23-plan-shape';
  await mkdir(join(instance.dir, '.cowork-flow', 'plans'), { recursive: true });
  const planPath = join(instance.dir, '.cowork-flow', 'plans', `${name}.md`);
  await writeFile(planPath, '# Plan\n', 'utf8');
  const created = instance.run([
    'task', 'next', '--run',
    '--title', name, '--slug', name, '--assignee', 'compliance',
    '--type', 'backend', '--from-plan', `.cowork-flow/plans/${name}.md`
  ]);
  assert.equal(created.status, 0, created.stderr);
  await writePlanningArtifacts(instance, name);

  const blocked = instance.run(['task', 'next', instance.taskDir(name), '--run']);
  assert.notEqual(blocked.status, 0, blocked.stdout + blocked.stderr);
  assert.match(blocked.stdout + blocked.stderr, /实施计划|plan title/);
  assert.equal(await taskStatus(instance, name), 'planning');

  await writeFile(planPath, strictPlanText(name), 'utf8');
  await finalizeTask(instance, name);
  const started = instance.run(['task', 'next', instance.taskDir(name), '--run']);
  assert.equal(started.status, 0, started.stderr);
  assert.equal(await taskStatus(instance, name), 'in_progress');
});

test('an installed instance still completes a pre-strict tiny task', async (t) => {
  const instance = await installedInstance(t, 'compliance_legacy_light');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }
  const name = '10-09-legacy-light';
  const created = instance.run([
    'task', 'next', '--run', '--title', 'Legacy light', '--slug', name, '--assignee', 'compliance'
  ]);
  assert.equal(created.status, 0, created.stderr);

  // Every task a current instance creates is strict, so the only way to reach
  // the compatibility path is to build the pre-strict metadata by hand. This
  // is a fixture for legacy data, not a shortcut around the creation entry
  // point — that one is covered by the scenario above.
  const taskPath = join(instance.dir, instance.taskDir(name), 'task.json');
  const task = JSON.parse(await readText(taskPath));
  delete task.meta.gateProfile;
  task.meta.taskType = 'tiny';
  await writeFile(taskPath, `${JSON.stringify(task, null, 2)}\n`, 'utf8');

  await writePlanningArtifacts(instance, name);
  const started = instance.run(['task', 'next', instance.taskDir(name), '--run']);
  assert.equal(started.status, 0, started.stderr);
  assert.equal(await taskStatus(instance, name), 'in_progress');

  await closeOutEvidence(instance, name);
  assert.equal(instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']).status, 0);
  // No receipt on this path: the compatibility contract is that a legacy task
  // completes exactly as it did before the strict profile existed.
  const completed = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.equal(completed.status, 0, completed.stderr);
  assert.equal(await taskStatus(instance, name), 'completed');
});

test('an installed instance runs the light path for a strict tiny task, and only for it', async (t) => {
  const instance = await installedInstance(t, 'compliance_light');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }

  // The light profile is declared at creation, through the shipped CLI — not
  // by hand-editing task.json, which is what the compatibility scenario used
  // to do and which proved nothing about the creation entry point.
  const lightName = '10-09-light';
  const created = instance.run([
    'task', 'next', '--run',
    '--title', 'Light', '--slug', lightName, '--assignee', 'compliance',
    '--task-type', 'tiny'
  ]);
  assert.equal(created.status, 0, created.stderr);
  await writePlanningArtifacts(instance, lightName);
  const started = instance.run(['task', 'next', instance.taskDir(lightName), '--run']);
  assert.equal(started.status, 0, started.stderr);

  const taskPath = join(instance.dir, instance.taskDir(lightName), 'task.json');
  const task = JSON.parse(await readText(taskPath));
  assert.equal(task.meta.gateProfile, 'strict', 'the light profile is a strict profile');
  assert.equal(task.meta.taskType, 'tiny');
  assert.equal(task.status, 'in_progress');

  // Visibility: a reduced gate set must never be silent.
  const listed = instance.run(['task', 'next', '--list', '--json']);
  assert.equal(listed.status, 0, listed.stderr);
  const records = JSON.parse(listed.stdout).tasks;
  assert.equal(
    records.find((record) => record.name === lightName).lightProfile,
    true
  );
  const textList = instance.run(['task', 'next', '--list']);
  assert.equal(textList.status, 0, textList.stderr);
  assert.match(textList.stdout, /10-09-light\/.*\[light\]/);

  // No evidence file, an unchecked AC and no review receipt: all three are
  // waived, so the light task still reaches completed.
  assert.equal(instance.run(['task', 'next', instance.taskDir(lightName), '--run', '--intent', 'review']).status, 0);
  const completed = instance.run(['task', 'next', instance.taskDir(lightName), '--run', '--intent', 'review']);
  assert.equal(completed.status, 0, completed.stderr);
  assert.equal(await taskStatus(instance, lightName), 'completed');
  const archived = instance.run(['task', 'next', instance.taskDir(lightName), '--run', '--intent', 'archive']);
  assert.equal(archived.status, 0, archived.stderr);

  // The counterexample that keeps the exemption from being too wide: the same
  // instance, an ordinary strict task, and the receipt gate still bites.
  const strictName = '10-09-strict-untouched';
  await createStartedTask(instance, strictName);
  await closeOutEvidence(instance, strictName);
  assert.equal(instance.run(['task', 'next', instance.taskDir(strictName), '--run', '--intent', 'review']).status, 0);
  const unreviewed = instance.run(['task', 'next', instance.taskDir(strictName), '--run', '--intent', 'review']);
  assert.notEqual(unreviewed.status, 0);
  assert.match(unreviewed.stdout + unreviewed.stderr, /independent review receipt/);
  assert.equal(await taskStatus(instance, strictName), 'review');
});

test('an installed instance refuses a review receipt it cannot trace to a checker', async (t) => {
  const instance = await installedInstance(t, 'compliance_receipt');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }

  const name = '10-10-untraceable-receipt';
  await createStartedTask(instance, name);
  await closeOutEvidence(instance, name);
  assert.equal(
    instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']).status,
    0
  );

  const fingerprint = await currentFingerprint(instance, name);
  await writeReviewReceipt(instance, name, { contextId: 'rtx-hand-written', fingerprint });
  const fabricated = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.notEqual(fabricated.status, 0, fabricated.stdout + fabricated.stderr);
  assert.match(fabricated.stdout + fabricated.stderr, /does not exist/);
  assert.equal(await taskStatus(instance, name), 'review');

  // A context that does exist but was never bound to a host session: the CLI
  // refuses to submit that receipt, so hand-writing is the only way to get one
  // in, and the gate has to catch it on the way out too.
  const unbound = await bindSubagent(instance, { name, role: 'check', agentType: 'cowork-check', bind: false });
  await writeReviewReceipt(instance, name, { contextId: unbound.runtimeContextId, fingerprint });
  const unverified = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.notEqual(unverified.status, 0, unverified.stdout + unverified.stderr);
  assert.match(unverified.stdout + unverified.stderr, /never bound to a host session/);
  assert.equal(await taskStatus(instance, name), 'review');

  // The gate is about provenance, not about this file being left alone: the
  // very same receipt, submitted through the CLI by a bound checker, completes
  // the task. Without that half, a green result above could just be a gate
  // that refuses everything.
  await writeFile(join(instance.dir, instance.taskDir(name), 'review.jsonl'), '', 'utf8');
  await recordReviewReceipt(instance, name);
  const completed = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.equal(completed.status, 0, completed.stdout + completed.stderr);
  assert.equal(await taskStatus(instance, name), 'completed');
});

test('an installed instance stops trusting a receipt once a referenced spec changes', async (t) => {
  const instance = await installedInstance(t, 'compliance_specchange');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }

  const name = '10-10-spec-change';
  await createStartedTask(instance, name, { specs: ['.cowork-flow/spec/backend/index.md'] });
  await closeOutEvidence(instance, name);
  assert.equal(
    instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']).status,
    0
  );

  await recordReviewReceipt(instance, name);

  // The receipt covers the applicable specs, not just the code diff: this task
  // is a backend task, so its spec pointers include the backend guide.
  const specPath = join(instance.dir, '.cowork-flow', 'spec', 'backend', 'index.md');
  const originalSpec = await readText(specPath);
  await writeFile(specPath, `${originalSpec}
Edited after the review.
`, 'utf8');

  const stale = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.notEqual(stale.status, 0, stale.stdout + stale.stderr);
  assert.match(stale.stdout + stale.stderr, /review receipt is stale/);
  assert.equal(await taskStatus(instance, name), 'review');

  // The other half of the attribution: put the spec back and the same receipt
  // completes again, so what refused above was the spec change and nothing else.
  await writeFile(specPath, originalSpec, 'utf8');
  const completed = instance.run(['task', 'next', instance.taskDir(name), '--run', '--intent', 'review']);
  assert.equal(completed.status, 0, completed.stdout + completed.stderr);
  assert.equal(await taskStatus(instance, name), 'completed');
});

test('a bound implement context cannot drive main-session workflow state', async (t) => {
  const instance = await installedInstance(t, 'compliance_delegated');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }
  const name = '10-09-delegated';
  await createStartedTask(instance, name);

  const context = await bindSubagent(instance, {
    name,
    role: 'implement',
    agentType: 'cowork-implement'
  });

  // Delegated means delegated: the worker sees its assignment, and the main
  // session's lifecycle is out of its reach.
  const delegated = instance.run(['task', 'next'], { COWORK_FLOW_CONTEXT_ID: context.hostContextKey });
  assert.equal(delegated.status, 0, delegated.stderr);
  assert.match(delegated.stdout, /delegated context cannot operate main-session workflow state/);
  assert.equal(await taskStatus(instance, name), 'in_progress');

  const evidence = instance.run([
    'subagent', 'evidence', context.runtimeContextId,
    '--note', 'scenario'
  ], { COWORK_FLOW_CONTEXT_ID: context.hostContextKey });
  assert.equal(evidence.status, 0, evidence.stderr);
});

test('an installed instance starts Batch, pauses on a failed step, and resumes', async (t) => {
  const instance = await installedInstance(t, 'compliance_batch');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }
  const name = '10-09-batch';
  await createStartedTask(instance, name);

  const started = instance.run([
    'task', 'next', instance.taskDir(name), '--run', '--intent', 'batch', '--auto', '--approved'
  ]);
  assert.equal(started.status, 0, started.stderr);
  const statePath = join(instance.dir, '.cowork-flow', 'runtime', 'batches', `batch-${name}.json`);
  const startedState = JSON.parse(await readText(statePath));
  assert.equal(startedState.phase, 'awaiting_host');
  assert.equal(startedState.next_action.type, 'start_task');

  const resultPath = join(instance.dir, 'batch-result.json');
  await writeFile(
    resultPath,
    `${JSON.stringify({
      action_id: startedState.next_action.action_id,
      type: startedState.next_action.type,
      outcome: 'failed',
      detail: 'scenario injected failure'
    })}\n`,
    'utf8'
  );
  const recorded = instance.run(['batch-action', 'record-result', `batch-${name}`, 'batch-result.json']);
  // A paused Batch reports that as its exit code, so the pause cannot be
  // mistaken for a clean advance.
  assert.equal(recorded.status, 2, recorded.stderr);
  const pausedState = JSON.parse(await readText(statePath));
  assert.equal(pausedState.phase, 'paused');
  assert.match(pausedState.pause_reason, /scenario injected failure/);

  const resumed = instance.run(['batch-action', 'resume', `batch-${name}`]);
  assert.equal(resumed.status, 0, resumed.stderr);
  const resumedState = JSON.parse(await readText(statePath));
  assert.notEqual(resumedState.phase, 'paused');
  assert.equal(resumedState.pause_reason, null);
  assert.equal(resumedState.next_action.type, 'start_task');
});

test('an installed instance upgrades in place without losing protected content', async (t) => {
  // The upgrade path is the Node CLI's, so a missing interpreter must not skip
  // it: nothing here needs the runtime to run.
  const instance = await installedInstance(t, 'compliance_upgrade', { requiresRunner: false });
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }
  const safeFile = join(instance.dir, '.agents', 'skills', 'cowork-flow', 'SKILL.md');
  const configFile = join(instance.dir, '.cowork-flow', 'config.yaml');
  const localSpec = join(instance.dir, '.cowork-flow', 'spec', 'backend', 'local-extension.md');
  const versionFile = join(instance.dir, '.cowork-flow', '.version');

  // Make it look like an older install: a stale safe file, a stale version, and
  // content the framework does not own.
  await writeFile(safeFile, 'old skill body\n', 'utf8');
  await writeFile(versionFile, '0.0.1\n', 'utf8');
  await writeFile(configFile, 'custom config\n', 'utf8');
  await writeFile(localSpec, '# Local extension\n', 'utf8');

  const upgraded = instance.cli(['sync', instance.dir]);
  assert.equal(upgraded.status, 0, upgraded.stderr);

  assert.equal(
    await readText(safeFile),
    await readText(join(templateRoot, 'skills', 'cowork-flow', 'SKILL.md')),
    'a template-owned file must be refreshed to the shipped bytes'
  );
  assert.equal((await readText(versionFile)).trim(), packageVersion);
  assert.equal(await readText(configFile), 'custom config\n');
  assert.equal(await readText(localSpec), '# Local extension\n');
  assert.equal(await exists(join(instance.dir, '.cowork-flow', 'tasks')), true);
});
