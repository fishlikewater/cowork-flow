import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { join } from 'node:path';
import { test } from 'node:test';

import {
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
      seed: 'ci-seed'
    }
  );
  assert.throws(
    () => parseTemplateTestOptions({ COWORK_TEMPLATE_TEST_REPEAT: '0' }),
    /positive integer/
  );
});

test('template test runner isolates every repeated iteration', async (t) => {
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
});
