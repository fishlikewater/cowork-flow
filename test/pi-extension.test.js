import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, readFile, realpath, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);
const CLI = join(packageRoot, 'bin', 'cowork-flow.js');
const EXTENSION_RELATIVE = ['extensions', 'cowork-flow.ts'];
const MARKER = 'CoworkFlowPiExtension';


function extensionPath(agentDir) {
  return join(agentDir, ...EXTENSION_RELATIVE);
}


// `cwf host add pi` always writes under $PI_CODING_AGENT_DIR; every case here
// points that variable at a temp directory, so the real ~/.pi/agent is never
// touched.
async function createAgentDir(t) {
  const dir = await realpath(await mkdtemp(join(tmpdir(), 'cowork-flow-pi-agent-')));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  return dir;
}


async function runCli(args, agentDir) {
  try {
    const result = await execFileAsync(process.execPath, [CLI, ...args], {
      env: { ...process.env, PI_CODING_AGENT_DIR: agentDir }
    });
    return { code: 0, stdout: result.stdout, stderr: result.stderr };
  } catch (error) {
    return { code: error.code, stdout: error.stdout ?? '', stderr: error.stderr ?? '' };
  }
}


async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}


test('host add pi installs the workflow-state extension into the Pi agent dir', async (t) => {
  const agentDir = await createAgentDir(t);
  const result = await runCli(['host', 'add', 'pi'], agentDir);

  assert.equal(result.code, 0, result.stderr);
  const installed = await readFile(extensionPath(agentDir), 'utf8');
  // The ownership marker and the single rendering entry are the two facts the
  // installer and the inspector depend on.
  assert.ok(installed.includes(MARKER));
  assert.ok(installed.includes('"--host", "pi"'));
  assert.match(result.stdout, /installed at/);
});


test('host add pi --dry-run reports the target and writes nothing', async (t) => {
  const agentDir = await createAgentDir(t);
  const result = await runCli(['host', 'add', 'pi', '--dry-run'], agentDir);

  assert.equal(result.code, 0, result.stderr);
  assert.match(result.stdout, /\[dry-run\] Would write/);
  assert.match(result.stdout, /cowork-flow\.ts/);
  assert.equal(await exists(extensionPath(agentDir)), false);
});


test('host add pi converges on a second run', async (t) => {
  const agentDir = await createAgentDir(t);
  assert.equal((await runCli(['host', 'add', 'pi'], agentDir)).code, 0);
  const first = await readFile(extensionPath(agentDir), 'utf8');

  const second = await runCli(['host', 'add', 'pi'], agentDir);

  assert.equal(second.code, 0, second.stderr);
  assert.match(second.stdout, /already installed/);
  assert.equal(await readFile(extensionPath(agentDir), 'utf8'), first);
});


test('host remove pi deletes only the cowork-flow extension', async (t) => {
  const agentDir = await createAgentDir(t);
  assert.equal((await runCli(['host', 'add', 'pi'], agentDir)).code, 0);
  const sibling = join(agentDir, 'extensions', 'someone-else.ts');
  await writeFile(sibling, 'export default function () {}\n', 'utf8');

  const result = await runCli(['host', 'remove', 'pi'], agentDir);

  assert.equal(result.code, 0, result.stderr);
  assert.equal(await exists(extensionPath(agentDir)), false);
  // A non-empty extensions directory keeps its other files and itself.
  assert.equal(await exists(sibling), true);
});


test('host add pi refuses a foreign file unless --force is explicit', async (t) => {
  const agentDir = await createAgentDir(t);
  const target = extensionPath(agentDir);
  await mkdir(join(agentDir, 'extensions'), { recursive: true });
  await writeFile(target, 'export default function () {}\n', 'utf8');

  const refused = await runCli(['host', 'add', 'pi'], agentDir);
  assert.notEqual(refused.code, 0);
  assert.match(refused.stderr, /Refusing to overwrite/);
  assert.equal(await readFile(target, 'utf8'), 'export default function () {}\n');

  const forced = await runCli(['host', 'add', 'pi', '--force'], agentDir);
  assert.equal(forced.code, 0, forced.stderr);
  assert.ok((await readFile(target, 'utf8')).includes(MARKER));
});


test('host inspect reports pi installed, then missing after removal', async (t) => {
  const agentDir = await createAgentDir(t);

  const missing = await runCli(['host', 'inspect', 'pi', '--json'], agentDir);
  assert.equal(missing.code, 0, missing.stderr);
  const missingRow = JSON.parse(missing.stdout).hosts.find((row) => row.id === 'pi');
  assert.equal(missingRow.status, 'missing');

  assert.equal((await runCli(['host', 'add', 'pi'], agentDir)).code, 0);
  const installed = await runCli(['host', 'inspect', 'pi', '--json'], agentDir);
  const installedRow = JSON.parse(installed.stdout).hosts.find((row) => row.id === 'pi');
  assert.equal(installedRow.status, 'installed');
  assert.equal(installedRow.detailPath, extensionPath(agentDir));
});
