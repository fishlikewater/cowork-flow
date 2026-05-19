import assert from 'node:assert/strict';
import { test } from 'node:test';

import { main } from '../src/cli.js';

function createIo() {
  return {
    stdout: '',
    stderr: '',
    writeOut(message) {
      this.stdout += message;
    },
    writeErr(message) {
      this.stderr += message;
    }
  };
}

test('prints help when no command is provided', async () => {
  const io = createIo();

  const code = await main([], { io });

  assert.equal(code, 0);
  assert.match(io.stdout, /cowork-flow init/);
  assert.match(io.stdout, /cowork-flow update/);
  assert.match(io.stdout, /cowork-flow sync/);
  assert.equal(io.stderr, '');
});

test('prints version with --version', async () => {
  const io = createIo();

  const code = await main(['--version'], { io });

  assert.equal(code, 0);
  assert.match(io.stdout, /^0\.3\.10\n$/);
  assert.equal(io.stderr, '');
});

test('returns an error for an unknown command', async () => {
  const io = createIo();

  const code = await main(['missing'], { io });

  assert.equal(code, 1);
  assert.equal(io.stdout, '');
  assert.match(io.stderr, /Unknown command: missing/);
});
