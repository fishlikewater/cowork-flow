import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { readPackageInfo } from '../src/lib/package-info.js';
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
  const packageInfo = await readPackageInfo();

  const code = await main(['init', target, '--developer', 'codex'], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.agent', 'skills', 'start', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'run')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'run.cmd')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'run.py')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'change.py')), true);
  assert.equal(await exists(join(target, '.codex', 'config.toml')), true);
  assert.equal(await exists(join(target, '.codex', 'hooks.json')), true);
  assert.equal(await exists(join(target, '.codex', 'hooks', 'inject-workflow-state.py')), true);
  assert.equal(await exists(join(target, '.superpowers')), false);
  assert.match(await readText(join(target, '.cowork-flow', '.developer')), /^name=codex\ninitialized_at=.+\n$/);
  assert.equal(await exists(join(target, '.cowork-flow', 'workspace', 'codex', 'index.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'workspace', 'codex', 'journal-1.md')), true);
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), `${packageInfo.version}\n`);
  assert.match(io.stdout, /created=/);
  assert.match(io.stdout, /Developer initialized: codex/);
  assert.equal(io.stderr, '');
});

test('init installs clean-room cowork-flow skills directly', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'codex'], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, '.superpowers')), false);
  assert.equal(await exists(join(target, '.agent', 'skills', 'before-dev', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agent', 'skills', 'check', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agent', 'skills', 'continue', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agent', 'skills', 'meta', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agent', 'skills', 'python-design', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agent', 'skills', 'using-superpowers', 'SKILL.md')), false);
});

test('init skips existing files by default', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'codex'], { io });

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

  const code = await main(['init', target, '--force', '--developer', 'codex'], { io });

  assert.equal(code, 0);
  assert.notEqual(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
  assert.match(io.stdout, /updated=/);
});

test('init dry-run does not write files', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--dry-run'], {
    io,
    prompt: async () => {
      throw new Error('dry-run must not prompt');
    }
  });

  assert.equal(code, 0);
  assert.equal(await exists(target), false);
  assert.match(io.stdout, /dry-run/);
  assert.match(io.stdout, /would-create=/);
});

test('init dry-run reports existing developer without rewriting', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, '.cowork-flow', '.developer'), 'name=existing\ninitialized_at=old\n', 'utf8');
  const io = createIo();

  const code = await main(['init', target, '--dry-run', '--developer', 'new-name'], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.cowork-flow', '.developer')), 'name=existing\ninitialized_at=old\n');
  assert.match(io.stdout, /preserve-existing=.cowork-flow\/.developer for developer existing/);
});

test('init fails without a developer in non-interactive mode', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target], { io, prompt: null });

  assert.equal(code, 1);
  assert.equal(await exists(target), false);
  assert.match(io.stderr, /Developer name required/);
  assert.match(io.stderr, /--developer <name>/);
});

test('init prompts for developer when prompt is available', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();
  let promptText = '';

  const code = await main(['init', target], {
    io,
    prompt: async (message) => {
      promptText = message;
      return 'alice';
    }
  });

  assert.equal(code, 0);
  assert.match(promptText, /Developer name/);
  assert.match(await readText(join(target, '.cowork-flow', '.developer')), /^name=alice\ninitialized_at=.+\n$/);
  assert.equal(await exists(join(target, '.cowork-flow', 'workspace', 'alice', 'journal-1.md')), true);
});

test('init preserves existing developer identity even with force', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, '.cowork-flow', '.developer'), 'name=existing\ninitialized_at=old\n', 'utf8');
  const io = createIo();

  const code = await main(['init', target, '--force', '--developer', 'new-name'], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.cowork-flow', '.developer')), 'name=existing\ninitialized_at=old\n');
  assert.match(io.stdout, /Developer already initialized: existing/);
});
