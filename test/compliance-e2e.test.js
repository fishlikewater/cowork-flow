import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { doctorVerdict, driftVerdict } from '../scripts/release-gates.js';
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

async function writePlanningArtifacts(instance, name, { anchor = true } = {}) {
  const taskDir = join(instance.dir, instance.taskDir(name));
  if (anchor) {
    await writeFile(
      join(taskDir, 'decision-anchor.md'),
      `# Decision Anchor\n\n## 目标\ncompliance scenario\n\n## 验收标准\n- [ ] AC-001: scenario reaches its end state\n`,
      'utf8'
    );
  }
  await writeFile(
    join(taskDir, 'implement.jsonl'),
    `${JSON.stringify({ file: 'src/scenario.js', reason: 'scenario', type: 'planned-file' })}\n`,
    'utf8'
  );
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

// A strict task needs its declared shape before it can start: a dev type, a
// bound plan, and a non-empty context index.
async function createStartedTask(instance, name) {
  await mkdir(join(instance.dir, '.cowork-flow', 'plans'), { recursive: true });
  await writeFile(
    join(instance.dir, '.cowork-flow', 'plans', `${name}.md`),
    '# Plan\n',
    'utf8'
  );
  const created = instance.run([
    'task', 'next', '--run',
    '--title', name, '--slug', name, '--assignee', 'compliance',
    '--type', 'backend', '--from-plan', `.cowork-flow/plans/${name}.md`
  ]);
  assert.equal(created.status, 0, created.stderr);
  await writePlanningArtifacts(instance, name);
  const started = instance.run(['task', 'next', instance.taskDir(name), '--run']);
  assert.equal(started.status, 0, started.stderr);
  return JSON.parse(await readText(join(instance.dir, instance.taskDir(name), 'task.json')));
}

async function bindSubagent(instance, { name, role, agentType }) {
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
  const bind = instance.run(['subagent', 'bind', context.runtimeContextId, context.hostContextKey]);
  assert.equal(bind.status, 0, bind.stderr);
  return context;
}

async function recordReviewReceipt(instance, name) {
  const context = await bindSubagent(instance, {
    name,
    role: 'check',
    agentType: 'cowork-check'
  });
  const state = instance.run(['state', instance.taskDir(name), '--json']);
  assert.equal(state.status, 0, state.stderr);
  const fingerprint = JSON.parse(state.stdout).changeFingerprint;
  const review = instance.run([
    'subagent', 'check-review', context.runtimeContextId,
    '--task-dir', instance.taskDir(name),
    '--result', 'pass',
    '--changed-fingerprint', fingerprint
  ], { COWORK_FLOW_CONTEXT_ID: context.hostContextKey });
  assert.equal(review.status, 0, review.stderr);
  assert.match(review.stdout, /"result": "pass"/);
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

  assert.equal(doctorVerdict({ ok: true, errors: [] }).status, 'pass');
  assert.equal(doctorVerdict({ ok: false, errors: [{ code: 'RUNTIME-TOPOLOGY-001' }] }).status, 'fail');
  // `ok` alone is not the verdict: an error-severity issue fails even if a
  // future doctor forgets to flip the flag.
  assert.equal(doctorVerdict({ ok: true, errors: [{ code: 'X' }] }).status, 'fail');

  const ran = spawn(process.execPath, [join(repoRoot, 'scripts', 'release-gates.js')], { cwd: repoRoot });
  assert.match(ran.stdout, /release-gates: self-instance-drift (pass|fail|skip)/);
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
  doctor,
  cliStatus = 0,
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
  await writeFile(
    join(root, 'bin', 'cowork-flow.js'),
    `process.stdout.write('readiness=' + ${JSON.stringify(JSON.stringify(readiness))} + '\\n');\n`
      + `process.exit(${cliStatus});\n`,
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
  const ran = spawnSync(process.execPath, [
    '--test', '--test-name-pattern', 'upgrades in place', 'test/compliance-e2e.test.js'
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

test('an installed instance runs the light compatibility path without the strict gates', async (t) => {
  const instance = await installedInstance(t, 'compliance_light');
  if (instance.unavailable) {
    t.skip(instance.unavailable);
    return;
  }
  const name = '10-09-light';
  // No --type and no --from-plan: the light path is a tiny legacy task, which
  // is the shape every pre-strict project still creates.
  const created = instance.run([
    'task', 'next', '--run', '--title', 'Light', '--slug', name, '--assignee', 'compliance'
  ]);
  assert.equal(created.status, 0, created.stderr);

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
