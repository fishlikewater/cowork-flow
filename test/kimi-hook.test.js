import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { cp, mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { packageRoot } from '../src/lib/paths.js';
import { readPackageInfo } from '../src/lib/package-info.js';

const execFileAsync = promisify(execFile);
const CLI = join(packageRoot, 'bin', 'cowork-flow.js');
const SHIM = join(packageRoot, 'presets', 'kimi-code', 'hooks', 'cowork-flow-inject.mjs');
const MARKER_NAME = '.cowork-flow-kimi-hook.json';


function shimPath(home) {
  return join(home, 'hooks', 'cowork-flow-inject.mjs');
}


function markerPath(home) {
  return join(home, 'hooks', MARKER_NAME);
}


// A machine-level install always writes under $KIMI_CODE_HOME; every case here
// points that variable at a temp directory, so the real ~/.kimi-code is never
// touched. The path is canonicalized because Windows hands out both 8.3 and
// long names for the temp directory, and the installed command must match the
// home the CLI resolved.
async function createKimiHome(t) {
  const dir = await realpath(await mkdtemp(join(tmpdir(), 'cowork-flow-kimi-home-')));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  return dir;
}


async function runCli(args, env) {
  try {
    const result = await execFileAsync(process.execPath, [CLI, ...args], { env });
    return { code: 0, stdout: result.stdout, stderr: result.stderr };
  } catch (error) {
    return { code: error.code, stdout: error.stdout ?? '', stderr: error.stderr ?? '' };
  }
}


async function install(t, home, args = []) {
  const result = await runCli(['install-kimi-hook', ...args], {
    ...process.env,
    KIMI_CODE_HOME: home,
  });
  assert.equal(result.code, 0, result.stderr);
  return result;
}


async function readConfig(home) {
  return readFile(join(home, 'config.toml'), 'utf8');
}


async function readMarker(home) {
  return JSON.parse(await readFile(markerPath(home), 'utf8'));
}


// The workflow runtime inside this repository is a live checkout, so a test
// project is built from the committed template — the same shape the shim
// discovers on a user machine.
async function createWorkflowProject(t) {
  const dir = await realpath(await mkdtemp(join(tmpdir(), 'cowork-flow-kimi-project-')));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  const workflow = join(dir, '.cowork-flow');
  await mkdir(workflow, { recursive: true });
  await cp(
    join(packageRoot, 'template', '.cowork-flow', 'scripts'),
    join(workflow, 'scripts'),
    { recursive: true }
  );
  await mkdir(join(workflow, 'spec', 'contracts'), { recursive: true });
  await mkdir(join(workflow, 'spec', 'runtime'), { recursive: true });
  await cp(
    join(
      packageRoot,
      'template',
      '.cowork-flow',
      'spec',
      'contracts',
      'workflow-state-templates.md'
    ),
    join(workflow, 'spec', 'contracts', 'workflow-state-templates.md')
  );
  await cp(
    join(
      packageRoot,
      'template',
      '.cowork-flow',
      'spec',
      'runtime',
      'contract-registry.json'
    ),
    join(workflow, 'spec', 'runtime', 'contract-registry.json')
  );
  return dir;
}


async function feedShim(cwd, env) {
  const payload = JSON.stringify({
    hook_event_name: 'UserPromptSubmit',
    session_id: 'session-1',
    session_title: 'test',
    client_type: 'cli',
    cwd,
  });
  const result = await new Promise((promise) => {
    const child = execFile(
      process.execPath,
      [SHIM],
      { env, maxBuffer: 1024 * 1024 },
      (error, stdout, stderr) => {
        promise({ code: error ? error.code : 0, stdout, stderr });
      }
    );
    child.stdin.end(payload);
  });
  return result;
}


test('dry-run reports the planned install without writing anything', async (t) => {
  const home = await createKimiHome(t);
  const configPath = join(home, 'config.toml');
  await mkdir(home, { recursive: true });
  const before = [
    '[providers.moonshot]',
    'api_key = "sk-test"',
    'base_url = "https://api.moonshot.cn/v1"',
    '',
    '[[providers.models]]',
    'name = "kimi-k2"',
    'limit = 200000',
    '',
  ].join('\n');
  await writeFile(configPath, before, 'utf8');

  const result = await install(t, home, ['--dry-run']);

  assert.match(result.stdout, /\[dry-run\] Would install Kimi Code context hook:/);
  assert.match(result.stdout, /cowork-flow-inject\.mjs/);
  assert.match(result.stdout, /\[\[hooks\]\]/);
  assert.match(result.stdout, new RegExp(MARKER_NAME.replace(/\./g, '\\.')));
  assert.equal(await readConfig(home), before);
  await assert.rejects(readFile(shimPath(home)));
  await assert.rejects(readFile(markerPath(home)));
});


test('installs the shim, one managed hook row, and the version marker', async (t) => {
  const home = await createKimiHome(t);
  const { version } = await readPackageInfo();

  const result = await install(t, home);

  assert.match(result.stdout, /✓ cowork-flow Kimi Code hook shim installed to /);
  const shim = await readFile(shimPath(home), 'utf8');
  assert.match(shim, /^#!\/usr\/bin\/env node\n/);
  assert.match(shim, /inject\.py/);

  // The marker is what doctor compares against the project version, so its
  // shape has to match the DSH preset marker (version + installedAt).
  const marker = await readMarker(home);
  assert.equal(marker.version, version);
  assert.equal(Number.isNaN(Date.parse(marker.installedAt)), false);
  assert.deepEqual(Object.keys(marker).sort(), ['installedAt', 'version']);

  const config = await readConfig(home);
  // TOML basic strings escape backslashes, so the stored path is doubled.
  const command = 'command = "node \\"' + shimPath(home).replace(/\\/g, '\\\\') + '\\""';
  // Kimi Code rejects a hook row carrying any field beyond the four supported
  // ones, so the row must stay at exactly these lines.
  assert.ok(
    config.includes(
      [
        '[[hooks]]',
        'event = "UserPromptSubmit"',
        command,
        'timeout = 30',
      ].join('\n'),
    ),
    config,
  );
  // One hook row, and an omitted matcher (which means "every prompt") — a
  // spelled-out matcher would silently narrow injection to matching prompts.
  assert.equal(config.split('\n').filter((line) => line.trim() === '[[hooks]]').length, 1);
  assert.equal(/matcher/.test(config), false, config);
});


test('installing twice leaves the config byte-identical and rewrites the marker', async (t) => {
  const home = await createKimiHome(t);
  const { version } = await readPackageInfo();
  await install(t, home);
  const firstConfig = await readConfig(home);
  const firstShim = await readFile(shimPath(home), 'utf8');
  // A marker left by an older release: the next install must overwrite it.
  await writeFile(
    markerPath(home),
    `${JSON.stringify({ version: '0.0.0', installedAt: '2000-01-01T00:00:00.000Z' }, null, 2)}\n`,
    'utf8',
  );

  const result = await install(t, home);

  assert.match(result.stdout, /already up to date/);
  assert.equal(await readConfig(home), firstConfig);
  assert.equal(await readFile(shimPath(home), 'utf8'), firstShim);
  assert.equal((await readMarker(home)).version, version);
  assert.equal(firstConfig.split('\n').filter((line) => line.trim() === '[[hooks]]').length, 1);
});


test('an existing hand-written config keeps its content and its hook rows', async (t) => {
  const home = await createKimiHome(t);
  await mkdir(home, { recursive: true });
  const foreignHook = [
    '[[hooks]]',
    'event = "PreToolUse"',
    'matcher = "^Bash$"',
    'command = "echo user-owned"',
    'timeout = 5',
  ].join('\n');
  const original = [
    '[providers.moonshot]',
    'api_key = "sk-test"',
    '',
    foreignHook,
    '',
    '[permissions]',
    'allow = ["read"]',
    '',
  ].join('\n');
  await writeFile(join(home, 'config.toml'), original, 'utf8');

  await install(t, home);

  const config = await readConfig(home);
  assert.ok(config.includes(foreignHook), config);
  assert.ok(config.includes('[permissions]\nallow = ["read"]'), config);
  assert.ok(config.startsWith('[providers.moonshot]\napi_key = "sk-test"\n'), config);
  assert.equal(config.split('\n').filter((line) => line.trim() === '[[hooks]]').length, 2);
});


test('a stale managed block is rewritten in place', async (t) => {
  const home = await createKimiHome(t);
  await mkdir(home, { recursive: true });
  const original = [
    '[providers.moonshot]',
    'api_key = "sk-test"',
    '',
  ].join('\n');
  await writeFile(join(home, 'config.toml'), original, 'utf8');
  await install(t, home);
  const installed = await readConfig(home);
  const tampered = installed.replace('command = "node ', 'command = "node --stale ');
  assert.notEqual(tampered, installed);
  await writeFile(join(home, 'config.toml'), tampered, 'utf8');

  const result = await install(t, home, ['--force']);

  assert.match(result.stdout, /block updated/);
  const config = await readConfig(home);
  assert.equal(config, installed);
  assert.equal(config.includes('--stale'), false, config);
  assert.equal(config.split('[[hooks]]').length, 2);
  assert.ok(config.startsWith(original), config);
});


test('--uninstall restores the config byte-for-byte and drops the hook files', async (t) => {
  const home = await createKimiHome(t);
  await mkdir(home, { recursive: true });
  const original = [
    '[providers.moonshot]',
    'api_key = "sk-test"',
    '',
    '[[hooks]]',
    'event = "PreToolUse"',
    'command = "echo user-owned"',
    '',
    '[permissions]',
    'allow = ["read"]',
    '',
  ].join('\n');
  await writeFile(join(home, 'config.toml'), original, 'utf8');

  await install(t, home);
  const installed = await readConfig(home);
  assert.notEqual(installed, original);

  const result = await install(t, home, ['--uninstall']);

  assert.match(result.stdout, /✓ Kimi Code context hook removed from /);
  assert.match(result.stdout, /✓ Removed hook shim /);
  assert.match(result.stdout, /✓ Removed version marker /);
  assert.equal(await readConfig(home), original);
  await assert.rejects(readFile(shimPath(home)));
  await assert.rejects(readFile(markerPath(home)));
});


test('a config holding only the managed block is removed on uninstall', async (t) => {
  const home = await createKimiHome(t);
  await install(t, home);

  await install(t, home, ['--uninstall']);

  await assert.rejects(readConfig(home));
});


test('the shim injects kimi-code context inside a cowork-flow project', async (t) => {
  const project = await createWorkflowProject(t);
  const env = { ...process.env, COWORK_FLOW_PYTHON: process.env.COWORK_FLOW_PYTHON ?? 'python' };
  delete env.COWORK_FLOW_HOOKS;

  const result = await feedShim(project, env);

  assert.equal(result.code, 0, result.stderr);
  assert.match(result.stdout, /^<cowork-runtime host="kimi-code" adapter="kimi-code\.hooks"/);
});


test('the shim stays silent outside a cowork-flow project', async (t) => {
  const outside = await mkdtemp(join(tmpdir(), 'cowork-flow-kimi-outside-'));
  t.after(async () => {
    await rm(outside, { recursive: true, force: true });
  });

  const result = await feedShim(outside, { ...process.env, COWORK_FLOW_PYTHON: process.execPath });

  assert.equal(result.code, 0, result.stderr);
  assert.equal(result.stdout, '');
});
