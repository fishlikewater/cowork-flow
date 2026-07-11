import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import {
  TEMPLATE_SYNC_ALLOWED_DIFFERENCES,
  checkTemplateSync,
  explainAllowedDifference
} from '../src/lib/template-sync-gate.js';
import { packageRoot } from '../src/lib/paths.js';
import { createTempDir } from './helpers/fs.js';

test('template sync gate reports concrete drift paths', async (t) => {
  const root = await createTempDir(t);
  await mkdir(join(root, '.cowork-flow', 'scripts'), { recursive: true });
  await mkdir(join(root, 'template', '.cowork-flow', 'scripts'), { recursive: true });
  await writeFile(join(root, '.cowork-flow', 'scripts', 'doctor.py'), 'root\n', 'utf8');
  await writeFile(join(root, 'template', '.cowork-flow', 'scripts', 'doctor.py'), 'template\n', 'utf8');

  const result = await checkTemplateSync({ packageRoot: root });

  assert.equal(result.ok, false);
  assert.deepEqual(result.drifts.map((item) => item.path), ['.cowork-flow/scripts/doctor.py']);
  assert.equal(result.drifts[0].templatePath, 'template/.cowork-flow/scripts/doctor.py');
  assert.match(result.drifts[0].reason, /content differs/);
});

test('template sync gate exposes documented allowed differences', () => {
  assert.ok(TEMPLATE_SYNC_ALLOWED_DIFFERENCES.length > 0);
  for (const entry of TEMPLATE_SYNC_ALLOWED_DIFFERENCES) {
    assert.match(entry.pattern, /[A-Za-z0-9.*_-]/);
    assert.match(entry.reason, /\S/);
  }
  assert.match(
    explainAllowedDifference('.cowork-flow/tasks/example/prd.md'),
    /task state/
  );
});

test('template sync gate ignores local runtime archive cache and generated files', async (t) => {
  const root = await createTempDir(t);
  await mkdir(join(root, '.cowork-flow', '.runtime'), { recursive: true });
  await mkdir(join(root, '.cowork-flow', 'tasks', 'archive', '2026-07', 'x'), { recursive: true });
  await mkdir(join(root, '.cowork-flow', 'scripts', '__pycache__'), { recursive: true });
  await writeFile(join(root, '.cowork-flow', '.runtime', 'state.json'), '{}\n', 'utf8');
  await writeFile(join(root, '.cowork-flow', 'tasks', 'archive', '2026-07', 'x', 'prd.md'), 'archived\n', 'utf8');
  await writeFile(join(root, '.cowork-flow', 'scripts', '__pycache__', 'doctor.pyc'), 'cache\n', 'utf8');

  const result = await checkTemplateSync({ packageRoot: root });

  assert.equal(result.ok, true);
  assert.deepEqual(result.drifts, []);
});

test('repository template sync gate is clean for mirrored runtime assets', async () => {
  const result = await checkTemplateSync({ packageRoot });

  assert.equal(
    result.ok,
    true,
    result.drifts.map((item) => `${item.path}: ${item.reason}`).join('\n')
  );
});
