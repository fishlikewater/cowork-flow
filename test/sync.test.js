import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';
import { createTempDir, readText } from './helpers/fs.js';

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

test('sync fails when the target has not been initialized', async (t) => {
  const target = await createTempDir(t);
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 1);
  assert.match(io.stderr, /not initialized/);
});

test('sync updates safe template files and preserves protected files', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target], { io: createIo() }), 0);

  await writeFile(join(target, '.agent', 'skills', 'start', 'SKILL.md'), 'old skill\n', 'utf8');
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.agent', 'skills', 'start', 'SKILL.md')),
    await readText(join(templateRoot, '.agent', 'skills', 'start', 'SKILL.md'))
  );
  assert.equal(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), `${(await readPackageInfo()).version}\n`);
  assert.match(io.stdout, /updated=/);
  assert.match(io.stdout, /protected=/);
});

test('sync overwrites protected files with --force', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target], { io: createIo() }), 0);
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');

  const code = await main(['sync', target, '--force'], { io: createIo() });

  assert.equal(code, 0);
  assert.notEqual(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
});

test('sync dry-run does not write safe file updates', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target], { io: createIo() }), 0);
  await writeFile(join(target, '.agent', 'skills', 'start', 'SKILL.md'), 'old skill\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target, '--dry-run'], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.agent', 'skills', 'start', 'SKILL.md')), 'old skill\n');
  assert.match(io.stdout, /dry-run/);
  assert.match(io.stdout, /would-update=/);
});

test('sync creates missing safe placeholder files', async (t) => {
  const target = await createTempDir(t);
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), `${(await readPackageInfo()).version}\n`);
  assert.match(io.stdout, /created=/);
});
