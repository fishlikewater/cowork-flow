import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { createTempDir, exists, readText } from './helpers/fs.js';

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

test('init copies the template into a new target directory', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.agent', 'skills', 'start', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'change.py')), true);
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), '0.3.10\n');
  assert.match(io.stdout, /created=/);
  assert.equal(io.stderr, '');
});

test('init skips existing files by default', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['init', target], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), '0.1.0\n');
  assert.match(io.stdout, /skipped=/);
});

test('init overwrites existing files with --force', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(target, { recursive: true });
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');
  const io = createIo();

  const code = await main(['init', target, '--force'], { io });

  assert.equal(code, 0);
  assert.notEqual(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
  assert.match(io.stdout, /updated=/);
});

test('init dry-run does not write files', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--dry-run'], { io });

  assert.equal(code, 0);
  assert.equal(await exists(target), false);
  assert.match(io.stdout, /dry-run/);
  assert.match(io.stdout, /would-create=/);
});
