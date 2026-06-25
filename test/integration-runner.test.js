import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

test('integration runner reports missing pytest dependency clearly', async (t) => {
  const tempDir = await mkdtemp(join(tmpdir(), 'cowork-flow-integration-'));
  t.after(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  let failure = null;
  try {
    await execFileAsync(
      process.execPath,
      [join(packageRoot, 'scripts', 'run-integration-tests.js')],
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          COWORK_FLOW_PYTHON: join(tempDir, 'missing-python')
        }
      }
    );
  } catch (error) {
    failure = error;
  }

  assert.ok(failure, 'runner should fail when Python/pytest is unavailable');
  assert.equal(failure.code, 1);
  assert.match(failure.stderr, /npm run test:integration requires Python and pytest/);
  assert.match(failure.stderr, /Install pytest/);
  assert.match(failure.stderr, /python -m pytest tests\/integration -q/);
});
