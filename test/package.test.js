import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { npmCommandOptions } from '../src/lib/package-info.js';
import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

test('npm package includes cli source and template assets', async (t) => {
  const npmCache = await mkdtemp(join(tmpdir(), 'cowork-flow-npm-cache-'));
  t.after(async () => {
    await rm(npmCache, { recursive: true, force: true });
  });

  const result = await execFileAsync('npm', ['pack', '--dry-run', '--json'], {
    cwd: packageRoot,
    encoding: 'utf8',
    ...npmCommandOptions(),
    env: {
      ...process.env,
      npm_config_cache: npmCache
    }
  });
  const [pack] = JSON.parse(result.stdout);
  const files = new Set(pack.files.map((file) => file.path));

  assert.equal(files.has('bin/cowork-flow.js'), true);
  assert.equal(files.has('CHANGELOG.md'), true);
  assert.equal(files.has('src/cli.js'), true);
  assert.equal(files.has('template/AGENTS.md'), true);
  assert.equal(files.has('template/CLAUDE.md'), true);
  assert.equal(files.has('template/.cowork-flow/run'), true);
  assert.equal(files.has('template/.cowork-flow/run.cmd'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/run.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/change.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/common/entry_classifier.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/common/task_context_defaults.py'), true);
  assert.equal(files.has('template/.cowork-flow/spec/core/state-templates.md'), true);
  assert.equal(files.has('template/.cowork-flow/adapters/claude-code/adapter.yaml'), true);
  assert.equal(files.has('template/.codex/config.toml'), true);
  assert.equal(files.has('template/.codex/hooks.json'), true);
  assert.equal(files.has('template/.codex/hooks/inject-workflow-state.py'), true);
  assert.equal(files.has('template/.claude/agents/cowork-implement.md'), true);
  assert.equal(files.has('template/.claude/commands/cowork-implement.md'), true);
  assert.equal(files.has('template/.claude/settings.json'), true);
  assert.equal(files.has('template/.claude/hooks/inject-workflow-state.py'), true);
  assert.equal(files.has('template/.claude/skills/start/SKILL.md'), true);
  assert.equal(files.has('template/.claude/skills/' + 'entry' + '-boundary/SKILL.md'), false);
  assert.equal(files.has('template/.opencode/agents/cowork-implement.md'), true);
  assert.equal(files.has('template/.opencode/commands/cowork-implement.md'), true);
  assert.equal(files.has('template/.opencode/plugins/cowork-flow.js'), true);
  assert.equal(files.has('template/.agents/skills/start/SKILL.md'), true);
  assert.equal(files.has('template/.agents/skills/before-dev/SKILL.md'), true);
  assert.equal(files.has('template/.agents/skills/check/SKILL.md'), true);
  assert.equal(files.has('template/.agents/skills/continue/SKILL.md'), true);
  assert.equal(files.has('template/.agents/skills/meta/SKILL.md'), true);
  assert.equal(files.has('template/.agents/skills/python-design/SKILL.md'), true);
  assert.equal([...files].some((file) => file.startsWith('template/.superpowers/')), false);
  assert.equal(
    [...files].some((file) => file.includes('__pycache__') || file.endsWith('.pyc')),
    false
  );
  assert.equal(
    [...files].some((file) => file.startsWith('template/.cowork-flow/.runtime/')),
    false
  );
});

test('package metadata exposes release script and synchronized lockfile version', async () => {
  const packageInfo = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));
  const packageLock = JSON.parse(await readFile(join(packageRoot, 'package-lock.json'), 'utf8'));

  assert.equal(packageInfo.scripts.release, 'sh scripts/release.sh');
  assert.equal(packageLock.version, packageInfo.version);
  assert.equal(packageLock.packages[''].version, packageInfo.version);
});
