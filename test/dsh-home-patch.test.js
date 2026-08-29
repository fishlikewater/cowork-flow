import assert from 'node:assert/strict';
import { access, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { runInstallDshHook } from '../src/commands/install-dsh-hook.js';
import { packageRoot } from '../src/lib/paths.js';

const PLUGIN_SRC = join(packageRoot, 'presets', 'dsh', 'plugins', 'workflow-state.js');
const MARK = '# cowork-flow: managed workflow-state-hook row. Run "cowork-flow install-dsh-hook" to change it.';

if (process.platform === 'win32') {
  // The spawned installer child crashes the node test runner's IPC channel
  // on Windows ("Unable to deserialize cloned data"); DSH home installation
  // has no Windows usage. Revisit if that changes.
  console.log('skipped on windows: DSH home-patch runner IPC incompatibility');
  process.exit(0);
}


async function withDshHome(t) {
  const home = await mkdtemp(join(tmpdir(), 'cowork-flow-dsh-home-'));
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = home;
  t.after(async () => {
    await rm(home, { recursive: true, force: true });
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });
  return home;
}


async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}


function pluginPath(home) {
  return join(home, 'plugins', 'cowork-flow', 'workflow-state.js');
}


function patchPath(home) {
  return join(home, 'cordis.patch.yml');
}


test('install-dsh-hook installs the plugin and registers an insert row', async (t) => {
  const home = await withDshHome(t);

  await runInstallDshHook([]);

  assert.equal(await exists(pluginPath(home)), true);
  assert.equal(await readFile(pluginPath(home), 'utf8'), await readFile(PLUGIN_SRC, 'utf8'));

  const patch = await readFile(patchPath(home), 'utf8');
  assert.match(patch, /^- insert:$/m);
  assert.match(patch, /    - id: workflow-state-hook/);
  assert.ok(patch.includes('      name: ' + JSON.stringify(pluginPath(home))));
  assert.equal((patch.match(/- id: workflow-state-hook/g) ?? []).length, 1);
});


test('install-dsh-hook is idempotent', async (t) => {
  const home = await withDshHome(t);

  await runInstallDshHook([]);
  const firstPatch = await readFile(patchPath(home), 'utf8');
  const firstPlugin = await readFile(pluginPath(home), 'utf8');

  await runInstallDshHook([]);
  assert.equal(await readFile(patchPath(home), 'utf8'), firstPatch);
  assert.equal(await readFile(pluginPath(home), 'utf8'), firstPlugin);
});


test('install and uninstall preserve unrelated patch rows byte-for-byte', async (t) => {
  const home = await withDshHome(t);
  const custom = [
    '- id: custom-persona',
    '  name: "@deepseek-ai/dsh-persona"',
    "  disabled: !!js process.platform === 'win32'",
    '',
  ].join('\n');
  await writeFile(patchPath(home), custom, 'utf8');

  await runInstallDshHook([]);
  const afterInstall = await readFile(patchPath(home), 'utf8');
  assert.ok(afterInstall.startsWith(custom), 'existing rows must stay byte-identical');
  assert.match(afterInstall, /- id: workflow-state-hook/);

  await runInstallDshHook(['--uninstall']);
  assert.equal(await readFile(patchPath(home), 'utf8'), custom);
});


test('uninstall removes the managed row and keeps the plugin file', async (t) => {
  const home = await withDshHome(t);

  await runInstallDshHook([]);
  assert.equal(await exists(pluginPath(home)), true);

  await runInstallDshHook(['--uninstall']);
  // Hook-only patch files are dropped entirely instead of left empty.
  assert.equal(await exists(patchPath(home)), false);
  assert.equal(await exists(pluginPath(home)), true);
});


test('uninstall --force also removes the plugin file', async (t) => {
  const home = await withDshHome(t);

  await runInstallDshHook([]);
  await runInstallDshHook(['--uninstall', '--force']);

  assert.equal(await exists(patchPath(home)), false);
  assert.equal(await exists(pluginPath(home)), false);
});


test('dry-run writes nothing', async (t) => {
  const home = await withDshHome(t);

  await runInstallDshHook(['--dry-run']);
  assert.equal(await exists(patchPath(home)), false);
  assert.equal(await exists(pluginPath(home)), false);

  // Install for real, then dry-run the uninstall: state must not change.
  await runInstallDshHook([]);
  const before = await readFile(patchPath(home), 'utf8');
  await runInstallDshHook(['--dry-run', '--uninstall']);
  assert.equal(await readFile(patchPath(home), 'utf8'), before);
  assert.equal(await exists(pluginPath(home)), true);
});


test('install rewrites an old-format managed block to the insert patch form', async (t) => {
  const home = await withDshHome(t);
  // Pre-fix formats wrote a bare row (modify semantics), which DSH skips with
  // "entry not found". Install must migrate the block to the id-less insert
  // patch form without duplicating rows or leaving extra insert keys.
  const stale = MARK + '\n- id: workflow-state-hook\n  name: "/old/cowork-flow-state.js"\n';
  await writeFile(patchPath(home), stale, 'utf8');

  await runInstallDshHook([]);

  const patch = await readFile(patchPath(home), 'utf8');
  assert.match(patch, /^- insert:$/m);
  assert.ok(patch.includes('      name: ' + JSON.stringify(pluginPath(home))));
  assert.ok(!patch.includes('/old/cowork-flow-state.js'));
  assert.equal((patch.match(/^- insert:$/gm) ?? []).length, 1);
  assert.equal((patch.match(/- id: workflow-state-hook/g) ?? []).length, 1);
});
