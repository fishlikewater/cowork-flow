import assert from 'node:assert/strict';
import { mkdir, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';
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
  await writeFile(join(target, '.cowork-flow', 'run'), 'old posix runner\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'run.cmd'), 'old windows runner\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'scripts', 'task.py'), 'old task script\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'workflow.md'), 'old workflow\n', 'utf8');
  await mkdir(join(target, '.codex', 'agents'), { recursive: true });
  await writeFile(join(target, '.codex', 'agents', 'cowork-implement.toml'), 'old agent\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'config.yaml'), 'custom config\n', 'utf8');
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.agent', 'skills', 'start', 'SKILL.md')),
    await readText(join(templateRoot, '.agent', 'skills', 'start', 'SKILL.md'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'run')),
    await readText(join(templateRoot, '.cowork-flow', 'run'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'run.cmd')),
    await readText(join(templateRoot, '.cowork-flow', 'run.cmd'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'scripts', 'task.py')),
    await readText(join(templateRoot, '.cowork-flow', 'scripts', 'task.py'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'workflow.md')),
    await readText(join(templateRoot, '.cowork-flow', 'workflow.md'))
  );
  assert.equal(
    await readText(join(target, '.codex', 'agents', 'cowork-implement.toml')),
    await readText(join(templateRoot, '.codex', 'agents', 'cowork-implement.toml'))
  );
  if (process.platform !== 'win32') {
    assert.notEqual((await stat(join(target, '.cowork-flow', 'run'))).mode & 0o111, 0);
  }
  assert.equal(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
  assert.equal(await readText(join(target, '.cowork-flow', 'config.yaml')), 'custom config\n');
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), `${(await readPackageInfo()).version}\n`);
  assert.match(io.stdout, /updated=/);
  assert.match(io.stdout, /protected=/);
});

test('sync replaces only the cowork-flow block in AGENTS.md', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target], { io: createIo() }), 0);
  const customAgents = [
    '# Project Rules',
    '',
    'Keep this project-specific introduction.',
    '',
    '<!-- COWORK-FLOW:START -->',
    'old managed workflow instructions',
    '<!-- COWORK-FLOW:END -->',
    '',
    'Keep this project-specific footer.',
    ''
  ].join('\n');
  await writeFile(join(target, 'AGENTS.md'), customAgents, 'utf8');
  const templateAgents = await readText(join(templateRoot, 'AGENTS.md'));
  const templateBlock = templateAgents.match(
    /<!-- COWORK-FLOW:START -->[\s\S]*<!-- COWORK-FLOW:END -->/
  )[0];

  const code = await main(['sync', target], { io: createIo() });

  assert.equal(code, 0);
  const syncedAgents = await readText(join(target, 'AGENTS.md'));
  assert.match(syncedAgents, /Keep this project-specific introduction/);
  assert.match(syncedAgents, /Keep this project-specific footer/);
  assert.doesNotMatch(syncedAgents, /old managed workflow instructions/);
  assert.equal(syncedAgents.match(
    /<!-- COWORK-FLOW:START -->[\s\S]*<!-- COWORK-FLOW:END -->/
  )[0], templateBlock);
});

test('sync does not copy internal superpowers seed material to the target root', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target], { io: createIo() }), 0);
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, '.superpowers')), false);
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

test('sync refreshes project-level cowork agent template files', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target], { io: createIo() }), 0);
  await mkdir(join(target, '.codex', 'agents'), { recursive: true });
  await writeFile(join(target, '.codex', 'agents', 'cowork-check.toml'), 'custom: true\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.codex', 'agents', 'cowork-check.toml')),
    await readText(join(templateRoot, '.codex', 'agents', 'cowork-check.toml'))
  );
  assert.match(io.stdout, /updated=/);
});
