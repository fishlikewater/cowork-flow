import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { runInstallDshPreset } from '../src/commands/install-dsh-preset.js';
import { packageRoot } from '../src/lib/paths.js';

const PRESET_ID = 'cowork-flow';


async function pathExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}


async function createDshHome(t) {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-dsh-home-'));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  return dir;
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


test('install-dsh-preset copies the preset into the DSH root without skills', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  await runInstallDshPreset([]);

  const dest = join(dshHome, '.agent-presets', PRESET_ID);
  assert.equal(await pathExists(join(dest, 'agent.cordis.yml')), true);
  assert.equal(await pathExists(join(dest, 'preset.yml')), true);

  const installed = await readFile(join(dest, 'agent.cordis.yml'), 'utf8');
  const source = await readFile(join(packageRoot, 'presets', 'dsh', 'agent.cordis.yml'), 'utf8');
  assert.equal(installed, source);

  const presetMeta = await readFile(join(dest, 'preset.yml'), 'utf8');
  assert.match(presetMeta, /name: Cowork Flow/);
  assert.match(presetMeta, /description:/);

  assert.match(installed, /id: skill-filesystem/);
  // Skills come from the project copy that init/sync delivers; the preset
  // registers no root of its own.
  assert.doesNotMatch(installed, /customSkillDirs/);
  assert.match(installed, /0\.1 编码前强制门禁/);
  assert.match(installed, /subagent bind \/ close/);
  assert.match(installed, /id: workflow-state-hook/);
  assert.match(installed, /name: '\.\/plugins\/workflow-state\.js'/);
  assert.equal(await pathExists(join(dest, 'plugins', 'workflow-state.js')), true);

  assert.equal(await pathExists(join(dest, 'skills')), false);
});


test('install-dsh-preset is idempotent without --force', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  await runInstallDshPreset([]);
  const dest = join(dshHome, '.agent-presets', PRESET_ID);
  await writeFile(join(dest, 'preset.yml'), 'custom user edit\n', 'utf8');

  const output = await captureConsole(() => runInstallDshPreset([]));

  assert.match(output, /already installed/);
  assert.equal(await readFile(join(dest, 'preset.yml'), 'utf8'), 'custom user edit\n');
});


test('install-dsh-preset --force overwrites an existing preset', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  await runInstallDshPreset([]);
  const dest = join(dshHome, '.agent-presets', PRESET_ID);
  await writeFile(join(dest, 'preset.yml'), 'stale\n', 'utf8');

  await runInstallDshPreset(['--force']);

  const presetMeta = await readFile(join(dest, 'preset.yml'), 'utf8');
  assert.match(presetMeta, /name: Cowork Flow/);
  assert.equal(await pathExists(join(dest, 'skills')), false);
});


test('install-dsh-preset --dry-run writes nothing', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  const output = await captureConsole(() => runInstallDshPreset(['--dry-run']));

  assert.match(output, /\[dry-run\]/);
  assert.equal(await pathExists(join(dshHome, '.agent-presets', PRESET_ID)), false);
});


test('install-dsh-preset records the installed version marker', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  await runInstallDshPreset([]);

  const dest = join(dshHome, '.agent-presets', PRESET_ID);
  const marker = JSON.parse(
    await readFile(join(dest, '.cowork-flow-preset.json'), 'utf8')
  );
  const pkg = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));
  assert.equal(marker.version, pkg.version);
  assert.match(marker.installedAt, /^\d{4}-\d{2}-\d{2}T/);
});


test('install-dsh-preset warns when the installed version is stale', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  await runInstallDshPreset([]);
  const dest = join(dshHome, '.agent-presets', PRESET_ID);
  await writeFile(
    join(dest, '.cowork-flow-preset.json'),
    '{"version":"0.0.1","installedAt":"2020-01-01T00:00:00.000Z"}\n',
    'utf8'
  );

  const output = await captureConsole(() => runInstallDshPreset([]));

  assert.match(output, /0\.0\.1/);
  assert.match(output, /cwf host add dsh --component preset --force/);
});


test('install-dsh-preset --uninstall removes the preset and is idempotent', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  await runInstallDshPreset([]);
  const presetsRoot = join(dshHome, '.agent-presets');
  const dest = join(presetsRoot, PRESET_ID);
  // A neighbouring preset is the user's own state; removing ours must leave it.
  const other = join(presetsRoot, 'user-preset');
  await mkdir(other, { recursive: true });
  await writeFile(join(other, 'preset.yml'), 'mine\n', 'utf8');

  const output = await captureConsole(() => runInstallDshPreset(['--uninstall']));

  assert.match(output, /removed from/);
  assert.equal(await pathExists(dest), false);
  assert.equal(await pathExists(other), true);

  const again = await captureConsole(() => runInstallDshPreset(['--uninstall']));
  assert.match(again, /was not installed/);
});


test('install-dsh-preset --uninstall --dry-run removes nothing', async (t) => {
  const dshHome = await createDshHome(t);
  const previous = process.env.DSH_HOME;
  process.env.DSH_HOME = dshHome;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_HOME;
    } else {
      process.env.DSH_HOME = previous;
    }
  });

  await runInstallDshPreset([]);
  const dest = join(dshHome, '.agent-presets', PRESET_ID);

  const output = await captureConsole(() => runInstallDshPreset(['--uninstall', '--dry-run']));

  assert.match(output, /Would uninstall DSH preset/);
  assert.equal(await pathExists(dest), true);
});
