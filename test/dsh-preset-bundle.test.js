import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { readPresetMeta, runInstallDshPreset } from '../src/commands/install-dsh-preset.js';
import { packageRoot } from '../src/lib/paths.js';

const PRESET_ID = 'cowork-flow';
const PRESET_SRC = join(packageRoot, 'presets', 'dsh');

// The workflow row is the one row the two DSH lines disagree on, in both
// directions: 0.2.0-rc.1 (desktop) dropped
// `@deepseek-ai/dsh-workflow-worker-thread`, and its shipped `standard` preset
// mounts `dsh-workflow-ptc`; 0.1.2-rc.1 (CLI) ships only the former. A row that
// resolves nowhere makes its own line report the whole preset as broken
// (0.1.x discovery health check) or reject the mount, so each delivered
// artifact must name only the package its own line ships.
const PACKAGES_ABSENT_FROM_DSH_0_2_0 = ['@deepseek-ai/dsh-workflow-worker-thread'];
const PACKAGES_ABSENT_FROM_DSH_0_1_X = ['@deepseek-ai/dsh-workflow-ptc'];


async function pathExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}


async function withDshHome(t) {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-dsh-bundle-'));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dir;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });
  return {
    home: dir,
    legacyDir: join(dir, '.agent-presets', PRESET_ID),
    bundleDir: join(dir, 'bundles', PRESET_ID),
  };
}


async function captureConsole(fn) {
  const lines = [];
  const original = console.log;
  console.log = (...args) => {
    lines.push(args.join(' '));
  };
  try {
    await fn();
  } finally {
    console.log = original;
  }
  return lines.join('\n');
}


// Row ids in file order, nested rows included.
function rowIds(text) {
  return [...text.matchAll(/^\s*- id: (\S+)$/gm)].map((match) => match[1]);
}


// Row bodies by id, comments and blank lines dropped, indentation folded, so
// the same row can be compared across the two delivered forms.
function rowBlocks(text) {
  const blocks = new Map();
  let current = null;
  for (const line of text.split('\n')) {
    const start = /^\s*- id: (\S+)\s*$/.exec(line);
    if (start) {
      current = start[1];
      blocks.set(current, []);
      continue;
    }
    if (current === null || line.trim() === '' || line.trim().startsWith('#')) continue;
    blocks.get(current).push(line.trim().replace(/\s+/g, ' '));
  }
  return blocks;
}


test('the bundle declares the preset the desktop installs', async (t) => {
  const { legacyDir, bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);

  const pkg = JSON.parse(await readFile(join(bundleDir, 'package.json'), 'utf8'));
  const rootPkg = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));
  assert.equal(pkg.name, '@cowork-flow/dsh-cowork-flow-preset');
  assert.equal(pkg.version, rootPkg.version);
  assert.equal(pkg.private, true);
  assert.equal(pkg.type, 'module');
  assert.deepEqual(pkg.dsh, { bundle: { patch: './cordis.patch.yml' } });

  const marker = JSON.parse(await readFile(join(bundleDir, '.cowork-flow-preset.json'), 'utf8'));
  assert.equal(marker.version, rootPkg.version);

  const hook = await readFile(join(bundleDir, 'workflow-state.js'), 'utf8');
  const sourceHook = await readFile(join(PRESET_SRC, 'plugins', 'workflow-state.js'), 'utf8');
  assert.equal(hook, sourceHook);

  // The legacy directory keeps its own copy: the two lines are independent.
  assert.equal(await pathExists(join(legacyDir, 'agent.cordis.yml')), true);
});


test('the bundle patch nests the composition under one preset declaration', async (t) => {
  const { bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);

  const patch = await readFile(join(bundleDir, 'cordis.patch.yml'), 'utf8');
  const composition = await readFile(join(PRESET_SRC, 'agent.cordis.yml'), 'utf8');
  const presetMeta = await readFile(join(PRESET_SRC, 'preset.yml'), 'utf8');

  assert.match(patch, /^- insert:$/m);
  assert.match(patch, /^ {4}- id: preset-cowork-flow$/m);
  assert.match(patch, /^ {6}name: '@deepseek-ai\/dsh-agent-preset'$/m);
  assert.match(patch, /^ {8}id: cowork-flow$/m);
  assert.match(patch, /^ {8}name: 'Cowork Flow'$/m);
  assert.match(patch, /^ {8}order: 10$/m);
  assert.match(patch, /^ {8}plugins:$/m);
  assert.match(presetMeta, /^name: Cowork Flow$/m);

  // Every composition row survives, in order, one level deeper; the workflow
  // row is the one the desktop rename touches (see the per-line test below).
  // Every composition row survives, in order, under the one declaration row;
  // the workflow row is the single rename the desktop needs (see the per-line
  // test below).
  const [declarationId, ...bundleIds] = rowIds(patch);
  const sourceIds = rowIds(composition);
  assert.equal(declarationId, 'preset-cowork-flow');
  assert.equal(bundleIds.length, sourceIds.length);
  assert.ok(sourceIds.includes('workflow-worker-thread'));
  assert.deepEqual(
    bundleIds.filter((id) => id !== 'workflow-ptc'),
    sourceIds.filter((id) => id !== 'workflow-worker-thread')
  );
  assert.ok(bundleIds.includes('workflow-state-hook'));

  // The hook is referenced where the bundle will actually sit.
  assert.match(
    patch,
    new RegExp(`^ {14}name: 'file:///.*/bundles/${PRESET_ID}/workflow-state\\.js'$`, 'm')
  );
  assert.doesNotMatch(patch, /\.\/plugins\/workflow-state\.js/);
});


test('each delivered line names the workflow package that line ships', async (t) => {
  const { legacyDir, bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);

  const patch = await readFile(join(bundleDir, 'cordis.patch.yml'), 'utf8');
  const legacy = await readFile(join(legacyDir, 'agent.cordis.yml'), 'utf8');

  // The bundle targets the desktop, which dropped the worker-thread package.
  for (const removed of PACKAGES_ABSENT_FROM_DSH_0_2_0) {
    assert.doesNotMatch(patch, new RegExp(removed.replace(/[/@.]/g, '\\$&')));
  }
  // The row that replaced it is what the desktop's own preset mounts.
  assert.match(patch, /^ +- id: workflow-ptc$/m);
  assert.match(patch, /^ +name: '@deepseek-ai\/dsh-workflow-ptc'$/m);

  // The directory is read by 0.1.x, which does not ship `ptc` at all.
  for (const removed of PACKAGES_ABSENT_FROM_DSH_0_1_X) {
    assert.doesNotMatch(legacy, new RegExp(removed.replace(/[/@.]/g, '\\$&')));
  }
  assert.match(legacy, /^ +- id: workflow-worker-thread$/m);
  assert.match(legacy, /^ +name: '@deepseek-ai\/dsh-workflow-worker-thread'$/m);
});


test('each delivered line carries the persona key that line schema takes', async (t) => {
  const { legacyDir, bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);

  const patch = await readFile(join(bundleDir, 'cordis.patch.yml'), 'utf8');
  const legacy = await readFile(join(legacyDir, 'agent.cordis.yml'), 'utf8');

  // 0.2.0's `dsh-persona` schema requires `prefix` (with `suffix` optional);
  // a row still carrying `text` fails validation, which fails the mount and
  // leaves the desktop listing the preset as broken.
  assert.match(patch, /^ {16}prefix: >-$/m);
  assert.doesNotMatch(patch, /^\s*text: /m);

  // 0.1.x is the reverse: `text` is the required key and `prefix` is unknown.
  assert.match(legacy, /^ {4}text: >-$/m);
  assert.doesNotMatch(legacy, /^\s*prefix: /m);
});


test('the two lines differ only in the rows the host APIs force them to', async (t) => {
  const { legacyDir, bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);

  const source = await readFile(join(PRESET_SRC, 'agent.cordis.yml'), 'utf8');
  const patch = await readFile(join(bundleDir, 'cordis.patch.yml'), 'utf8');
  const legacy = await readFile(join(legacyDir, 'agent.cordis.yml'), 'utf8');

  // The directory line is the source file, whole.
  assert.equal(legacy, source);

  // The desktop line edits three rows — the workflow row the two lines ship
  // under different names, the persona config key their schemas disagree on,
  // and the hook specifier that has no file to resolve against in a bundle.
  // Any fourth difference is drift no line needs.
  const sourceRows = rowBlocks(source);
  const desktopRows = rowBlocks(patch);
  desktopRows.delete('preset-cowork-flow');
  const renamed = (id) => (id === 'workflow-worker-thread' ? 'workflow-ptc' : id);

  const changed = [...sourceRows.keys()].filter((id) => {
    const delivered = desktopRows.get(renamed(id));
    return delivered === undefined || sourceRows.get(id).join('\n') !== delivered.join('\n');
  });
  assert.deepEqual(changed.sort(), ['persona', 'workflow-state-hook', 'workflow-worker-thread']);
  assert.deepEqual(
    [...desktopRows.keys()].sort(),
    [...sourceRows.keys()].map(renamed).sort()
  );
});


test('the hook warms up on both the 0.1.x and the 0.2.0 start event', async (t) => {
  const { bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);

  const hook = await readFile(join(bundleDir, 'workflow-state.js'), 'utf8');
  assert.match(hook, /ctx\.on\('agent\/session-start'/);
  assert.match(hook, /ctx\.on\('agent\/created'/);
  assert.match(hook, /ctx\.on\('agent\/inbox\/claimed'/);
});


test('a legacy-only install keeps its files and gains the bundle', async (t) => {
  const { bundleDir, legacyDir } = await withDshHome(t);

  // The state every pre-0.2.0 install upgrades from: legacy directory only.
  await runInstallDshPreset([]);
  await rm(bundleDir, { recursive: true, force: true });
  const edited = 'name: Edited locally\n';
  await writeFile(join(legacyDir, 'preset.yml'), edited, 'utf8');
  await writeFile(join(legacyDir, 'my-extra-plugin.js'), 'export const name = "mine";\n', 'utf8');

  const output = await captureConsole(() => runInstallDshPreset([]));

  assert.match(output, /installed/);
  assert.doesNotMatch(output, /already installed/);
  assert.equal(await readFile(join(legacyDir, 'preset.yml'), 'utf8'), edited);
  assert.equal(await pathExists(join(legacyDir, 'my-extra-plugin.js')), true);
  assert.equal(await pathExists(join(bundleDir, 'cordis.patch.yml')), true);
});


test('a bundle-only install keeps its files and gains the legacy directory', async (t) => {
  const { bundleDir, legacyDir } = await withDshHome(t);

  await runInstallDshPreset([]);
  await rm(legacyDir, { recursive: true, force: true });
  const edited = '# edited locally\n';
  await writeFile(join(bundleDir, 'cordis.patch.yml'), edited, 'utf8');

  await runInstallDshPreset([]);

  assert.equal(await readFile(join(bundleDir, 'cordis.patch.yml'), 'utf8'), edited);
  assert.equal(await pathExists(join(legacyDir, 'agent.cordis.yml')), true);
});


test('the bundle is written without --force and refreshed by it', async (t) => {
  const { bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);
  await writeFile(join(bundleDir, 'cordis.patch.yml'), 'stale\n', 'utf8');

  const output = await captureConsole(() => runInstallDshPreset([]));
  assert.match(output, /already installed/);
  // Without --force an existing install is left alone, bundle included.
  assert.equal(await readFile(join(bundleDir, 'cordis.patch.yml'), 'utf8'), 'stale\n');

  await runInstallDshPreset(['--force']);
  const refreshed = await readFile(join(bundleDir, 'cordis.patch.yml'), 'utf8');
  assert.match(refreshed, /^ {8}plugins:$/m);
});


test('a bundle missing from an existing install is restored', async (t) => {
  const { bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);
  // An install predating the bundle line has the legacy directory only.
  await rm(bundleDir, { recursive: true, force: true });

  await runInstallDshPreset([]);

  assert.equal(await pathExists(join(bundleDir, 'cordis.patch.yml')), true);
});


test('--dry-run writes neither the preset directory nor the bundle', async (t) => {
  const { legacyDir, bundleDir } = await withDshHome(t);

  const output = await captureConsole(() => runInstallDshPreset(['--dry-run']));

  assert.match(output, /\[dry-run\]/);
  assert.match(output, /bundles/);
  assert.equal(await pathExists(legacyDir), false);
  assert.equal(await pathExists(bundleDir), false);
});


test('--uninstall removes both lines and is idempotent', async (t) => {
  const { home, legacyDir, bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);
  // A neighbour bundle is the user's own state; removing ours must leave it.
  const neighbour = join(home, 'bundles', 'someone-else');
  await mkdir(neighbour, { recursive: true });
  await writeFile(join(neighbour, 'package.json'), '{}\n', 'utf8');

  const output = await captureConsole(() => runInstallDshPreset(['--uninstall']));

  assert.match(output, /removed from/);
  assert.equal(await pathExists(legacyDir), false);
  assert.equal(await pathExists(bundleDir), false);
  assert.equal(await pathExists(join(neighbour, 'package.json')), true);

  const again = await captureConsole(() => runInstallDshPreset(['--uninstall']));
  assert.match(again, /was not installed/);
});


test('--uninstall --dry-run removes nothing from either line', async (t) => {
  const { legacyDir, bundleDir } = await withDshHome(t);

  await runInstallDshPreset([]);

  const output = await captureConsole(() => runInstallDshPreset(['--uninstall', '--dry-run']));

  assert.match(output, /Would uninstall DSH preset/);
  assert.equal(await pathExists(legacyDir), true);
  assert.equal(await pathExists(bundleDir), true);
});


test('only single-line scalars are lifted from preset.yml', () => {
  const plain = readPresetMeta('name: Cowork Flow\ndescription: 一句话\norder: 7\n');
  assert.deepEqual(plain, { name: 'Cowork Flow', description: '一句话', order: 7 });

  // A block scalar has no single-line value; lifting `>-` verbatim would
  // publish that marker as the preset description.
  const block = readPresetMeta('name: Cowork Flow\ndescription: >-\n  folded text\n');
  assert.equal(block.description, '');
  assert.equal(block.order, 10);

  // Quoted values arrive without their quotes, so the generated row can
  // re-quote them once.
  assert.equal(readPresetMeta("name: 'Quoted Flow'\n").name, 'Quoted Flow');
  assert.equal(readPresetMeta('name: "Quoted Flow"\n').name, 'Quoted Flow');
  assert.equal(readPresetMeta('name: Cowork Flow\norder: nope\n').order, 10);
});
