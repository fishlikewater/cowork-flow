import assert from 'node:assert/strict';
import { access, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { runInstallDshPreset } from '../src/commands/install-dsh-preset.js';
import { packageRoot, templateRoot } from '../src/lib/paths.js';

const PRESET_ID = 'cowork-flow';
const EXPECTED_SKILL_DIRS = [
  'adversarial-review',
  'agent-dispatch',
  'batch-execution',
  'brainstorming',
  'cowork-flow',
  'cowork-flow-maintenance',
  'decision-audit',
  'failure-analysis',
  'game-design',
  'party-mode',
  'python-runtime-design',
  'runtime-health',
  'spec-sync',
  'task-planning',
  'task-review',
  'test-first'
];


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


test('install-dsh-preset copies preset and skills into the DSH root', async (t) => {
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

  assert.match(installed, /customSkillDirs/);
  assert.match(installed, /new URL\('skills\/', baseUrl\)/);
  assert.match(installed, /0\.1 编码前强制门禁/);
  assert.match(installed, /subagent bind \/ close/);
  assert.match(installed, /id: workflow-state-hook/);
  assert.match(installed, /name: '\.\/plugins\/workflow-state\.js'/);
  assert.equal(await pathExists(join(dest, 'plugins', 'workflow-state.js')), true);

  const skills = join(dest, 'skills');
  assert.equal(await pathExists(join(skills, 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await pathExists(join(skills, 'party-mode', 'scripts', 'party_mode_v2.py')), true);

  const installedSkillDirs = (await readdir(skills, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  assert.deepEqual(installedSkillDirs, [...EXPECTED_SKILL_DIRS].sort());
  assert.equal(await pathExists(join(skills, 'start')), false);
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
  assert.equal(await pathExists(join(dest, 'skills', 'cowork-flow', 'SKILL.md')), true);
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


test('install-dsh-preset resolves skills from the package template', async (t) => {
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
  const installedSkill = await readFile(join(dest, 'skills', 'cowork-flow', 'SKILL.md'), 'utf8');
  const templateSkill = await readFile(join(templateRoot, 'skills', 'cowork-flow', 'SKILL.md'), 'utf8');
  assert.equal(installedSkill, templateSkill);
});
