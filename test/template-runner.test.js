import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { test } from 'node:test';

import {
  CORE_TEMPLATE_TEST_MODULES,
  createTemplateTestTempRoot,
  parseTemplateTestOptions,
  runTemplateTests
} from '../scripts/template-test-runner.js';
import { createTempDir } from './helpers/fs.js';

test('template test options support repeat count and stable seed', () => {
  assert.deepEqual(
    parseTemplateTestOptions({
      COWORK_TEMPLATE_TEST_REPEAT: '3',
      COWORK_TEMPLATE_TEST_SEED: 'ci-seed'
    }),
    {
      repeat: 3,
      seed: 'ci-seed',
      suite: 'core'
    }
  );
  assert.equal(
    parseTemplateTestOptions({}, ['--suite', 'full']).suite,
    'full'
  );
  assert.equal(
    parseTemplateTestOptions({}, ['--suite=full']).suite,
    'full'
  );
  assert.throws(
    () => parseTemplateTestOptions({ COWORK_TEMPLATE_TEST_REPEAT: '0' }),
    /positive integer/
  );
  assert.throws(
    () => parseTemplateTestOptions({}, ['--suite', 'unknown']),
    /suite must be one of: core, full/
  );
  assert.throws(
    () => parseTemplateTestOptions({}, ['--unknown']),
    /Unknown template test option/
  );
});

test('template test temp roots are unique and outside the project tree', (t) => {
  const first = createTemplateTestTempRoot();
  const second = createTemplateTestTempRoot();
  t.after(() => {
    rmSync(first, { recursive: true, force: true });
    rmSync(second, { recursive: true, force: true });
  });

  assert.equal(dirname(first), resolve(tmpdir()));
  assert.equal(dirname(second), resolve(tmpdir()));
  assert.notEqual(first, second);
});

test('core template suite runs a stable high-signal module list', async (t) => {
  const root = await createTempDir(t);
  const calls = [];
  const spawnImpl = (runner, args, options) => {
    calls.push({ runner, args, options });
    const child = new EventEmitter();
    queueMicrotask(() => child.emit('close', 0));
    return child;
  };

  const exitCode = await runTemplateTests({
    repeat: 3,
    seed: 'repeatable',
    suite: 'core',
    runner: join(root, 'run.cmd'),
    tempRoot: join(root, 'template-tests'),
    spawnImpl,
    platform: 'win32'
  });

  assert.equal(exitCode, 0);
  assert.equal(calls.length, 3);
  assert.deepEqual(
    calls.map((call) => call.options.env.COWORK_TEMPLATE_TEST_ITERATION),
    ['1', '2', '3']
  );
  assert.equal(new Set(calls.map((call) => call.options.env.TMP)).size, 3);
  assert.equal(
    calls.every((call) => call.options.env.COWORK_TEMPLATE_TEST_SEED === 'repeatable'),
    true
  );
  assert.deepEqual(
    calls[0].args,
    ['python', '-m', 'unittest', ...CORE_TEMPLATE_TEST_MODULES, '-v']
  );
});

test('full template suite retains unittest discovery', async (t) => {
  const root = await createTempDir(t);
  const calls = [];
  const spawnImpl = (runner, args) => {
    calls.push({ runner, args });
    const child = new EventEmitter();
    queueMicrotask(() => child.emit('close', 0));
    return child;
  };

  const exitCode = await runTemplateTests({
    repeat: 1,
    seed: 'full-suite',
    suite: 'full',
    runner: join(root, 'run.cmd'),
    tempRoot: join(root, 'template-tests'),
    spawnImpl,
    platform: 'win32'
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(
    calls[0].args,
    ['python', '-m', 'unittest', 'discover', 'tests', '-v']
  );
});
