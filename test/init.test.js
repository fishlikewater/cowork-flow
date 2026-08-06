import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { join, sep } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { main } from '../src/cli.js';
import { runInitWithOptions } from '../src/commands/init.js';
import { hostRegistry } from '../src/lib/host-assets.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import {
  createTempDir,
  exists,
  fileSystemWithRenameFailure,
  readText
} from './helpers/fs.js';

const execFileAsync = promisify(execFile);

const HOST_MANIFEST_FIXTURES = new URL('../tests/fixtures/host-manifest/', import.meta.url);
const CLI_MODULE = new URL('../src/cli.js', import.meta.url);
const CLI_IMPORT_SCRIPT = `
const args = JSON.parse(process.env.COWORK_FLOW_TEST_ARGS);
try {
  const { main } = await import(process.env.COWORK_FLOW_TEST_CLI_URL);
  process.exitCode = await main(args);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
`;

function manifestFixturePath(name) {
  return fileURLToPath(new URL(name, HOST_MANIFEST_FIXTURES));
}

async function runCliWithManifestFixture(fixtureName, args) {
  try {
    const result = await execFileAsync(process.execPath, ['--input-type=module', '--eval', CLI_IMPORT_SCRIPT], {
      env: {
        ...process.env,
        COWORK_FLOW_HOST_ASSET_MANIFEST: manifestFixturePath(fixtureName),
        COWORK_FLOW_TEST_ARGS: JSON.stringify(args),
        COWORK_FLOW_TEST_CLI_URL: CLI_MODULE.href
      }
    });
    return { code: 0, stdout: result.stdout, stderr: result.stderr };
  } catch (error) {
    return { code: error.code, stdout: error.stdout ?? '', stderr: error.stderr ?? '' };
  }
}


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


test('init uses manifest-defined extra platform assets', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const result = await runCliWithManifestFixture(
    'valid-extra-platform.json',
    ['init', target, '--developer', 'codex', '--platform', 'demo']
  );
  assert.equal(result.code, 0, result.stderr);
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.demo-host', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.codex', 'config.toml')), false);
  assert.match(result.stdout, /Platforms: demo-host/);
});


test('init rejects invalid host manifest before target mutation', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const result = await runCliWithManifestFixture(
    'invalid-unknown-field.json',
    ['init', target, '--developer', 'codex', '--platform', 'codex']
  );
  assert.equal(result.code, 1);
  assert.match(result.stderr, /unknown field/i);
  assert.equal(await exists(target), false);
});

test('init copies the template into a new target directory', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();
  const packageInfo = await readPackageInfo();

  const code = await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'adversarial-review', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'game-design', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'run')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'run.cmd')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'run.py')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'task.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'adapters', 'cli', 'change.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'infra', 'paths.py')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'services', 'lifecycle_checks.py')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'adapters', 'review', 'test_intent.py')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'common', 'gates')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'project_context.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'common', 'entry_classifier.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'spec', 'contracts', 'workflow-state-templates.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'project-context.md')), false);
  assert.equal(await exists(join(target, '.codex', 'config.toml')), true);
  assert.equal(await exists(join(target, '.codex', 'hooks.json')), true);
  assert.equal(await exists(join(target, '.codex', 'hooks', 'inject-workflow-state.py')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml')), false);
  assert.deepEqual(hostRegistry.assetOwners('.codex/hooks.json'), ['codex']);
  assert.deepEqual(
    hostRegistry.assetOwners('.cowork-flow/adapters/opencode/adapter.yaml'),
    ['opencode']
  );
  assert.equal(await exists(join(target, '.opencode')), false);
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, 'CLAUDE.md')), false);
  assert.equal(await exists(join(target, '.superpowers')), false);
  assert.match(await readText(join(target, '.cowork-flow', '.developer')), /^name=codex\ninitialized_at=.+\n$/);
  assert.equal(await exists(join(target, '.cowork-flow', 'workspace')), false);
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), `${packageInfo.version}\n`);
  assert.match(io.stdout, /created=/);
  assert.match(io.stdout, /Platforms: codex/);
  assert.match(io.stdout, /Developer initialized: codex/);
  assert.equal(io.stderr, '');
});

test('init copies only opencode host assets when platform is opencode', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'opencode-user', '--platform', 'opencode'], { io });

  assert.equal(code, 0, JSON.stringify({
    stderr: io.stderr,
    stdout: io.stdout,
    target
  }, null, 2));
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'run.cmd')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'common', 'entry_classifier.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'spec', 'contracts', 'workflow-state-templates.md')), true);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.opencode', 'agents', 'cowork-implement.md')), true);
  assert.equal(await exists(join(target, '.opencode', 'commands', 'cowork-implement.md')), true);
  assert.equal(await exists(join(target, '.opencode', 'plugins', 'cowork-flow.js')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, 'CLAUDE.md')), false);
  assert.match(io.stdout, /Platforms: opencode/);
});

test('init copies only claude-code host assets when platform is claude-code', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'claude-user', '--platform', 'claude-code'], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, 'CLAUDE.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills')), false);
  assert.equal(await exists(join(target, '.claude', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'run.cmd')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'common', 'entry_classifier.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'spec', 'contracts', 'workflow-state-templates.md')), true);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.opencode')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.claude', 'agents', 'cowork-implement.md')), true);
  assert.equal(await exists(join(target, '.claude', 'commands', 'cowork-implement.md')), true);
  assert.equal(await exists(join(target, '.claude', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills')), false);
  assert.equal(await exists(join(target, '.claude', 'skills', 'entry' + '-boundary', 'SKILL.md')), false);
  assert.equal(await exists(join(target, '.claude', 'settings.json')), true);
  assert.equal(await exists(join(target, '.claude', 'hooks', 'inject-workflow-state.py')), true);
  assert.match(await readText(join(target, 'CLAUDE.md')), /@AGENTS\.md/);
  assert.match(io.stdout, /Platforms: claude-code/);
});

test('init copies all selected host platforms', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main([
    'init',
    target,
    '--developer',
    'multi-user',
    '--platform',
    'all'
  ], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, '.codex', 'hooks.json')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.opencode', 'plugins', 'cowork-flow.js')), true);
  assert.equal(await exists(join(target, '.claude', 'agents', 'cowork-check.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'party-mode', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'party-mode', 'scripts', 'party_mode_v2.py')), true);
  assert.equal(await exists(join(target, '.claude', 'skills', 'party-mode', 'scripts', 'party_mode_v2.py')), true);
  assert.equal(await exists(join(target, '.claude', 'settings.json')), true);
  assert.equal(await exists(join(target, '.claude', 'hooks', 'inject-workflow-state.py')), true);
  assert.match(io.stdout, /Platforms: codex, opencode, claude-code/);
});

test('installed Doctor passes for codex, claude-only, and multi-host projects', async (t) => {
  if (process.platform === 'win32') {
    t.skip('POSIX runner execution is covered on POSIX hosts');
    return;
  }

  for (const platform of ['codex', 'claude-code', 'all']) {
    const target = join(await createTempDir(t), `doctor-${platform}`);
    const io = createIo();
    const code = await main([
      'init',
      target,
      '--developer',
      `doctor-${platform}`,
      '--platform',
      platform
    ], { io });

    assert.equal(code, 0, io.stderr);
    const result = await execFileAsync(
      join(target, '.cowork-flow', 'run'),
      ['doctor', '--all'],
      { cwd: target, encoding: 'utf8' }
    );
    assert.match(result.stdout, /runtime health checks passed/);
    assert.equal(result.stderr, '');
  }
});

test('init rejects removed both platform alias', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'removed-user', '--platform', 'both'], { io });

  assert.equal(code, 1);
  assert.equal(await exists(target), false);
  assert.match(io.stderr, /Unsupported platform: both/);
});

test('init installs clean-room cowork-flow skills directly', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, '.superpowers')), false);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'batch-execution', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'brainstorming', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'decision-audit', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'adversarial-review', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'agent-dispatch', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow-maintenance', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'spec-sync', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'batch-execution', 'manifest.json')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'brainstorming', 'manifest.json')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'manifest.json')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'runtime-health', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'runtime-health', 'manifest.json')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'runtime-health', 'scripts', 'doctor.py')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'before-dev', 'SKILL.md')), false);
  assert.equal(await exists(join(target, '.agents', 'skills', 'check', 'SKILL.md')), false);
  assert.equal(await exists(join(target, '.agents', 'skills', 'continue', 'SKILL.md')), false);
  assert.equal(await exists(join(target, '.agents', 'skills', 'python-runtime-design', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'using-superpowers', 'SKILL.md')), false);
});

test('init skips existing files by default', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io });

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

  const code = await main(['init', target, '--force', '--developer', 'codex', '--platform', 'codex'], { io });

  assert.equal(code, 0);
  assert.notEqual(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
  assert.match(io.stdout, /updated=/);
});

test('init rolls back template and developer assets after an injected commit failure', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const developerFile = join(target, '.cowork-flow', '.developer');
  const fileSystem = fileSystemWithRenameFailure(
    (source, destination) => source.includes(`${sep}staging${sep}`)
      && destination === developerFile
  );

  await assert.rejects(
    runInitWithOptions(
      [target, '--developer', 'codex', '--platform', 'codex'],
      { io: createIo(), prompt: null, selectPlatforms: null, fileSystem }
    ),
    /injected commit failure/
  );

  assert.equal(await exists(join(target, 'AGENTS.md')), false);
  assert.equal(await exists(developerFile), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'workspace')), false);
  assert.equal(await exists(join(target, '.cowork-flow', '.version')), false);
});

test('init dry-run does not write files', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--dry-run', '--platform', 'codex'], {
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

  const code = await main(['init', target, '--dry-run', '--developer', 'new-name', '--platform', 'codex'], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.cowork-flow', '.developer')), 'name=existing\ninitialized_at=old\n');
  assert.match(io.stdout, /preserve-existing=.cowork-flow\/.developer for developer existing/);
});

test('init fails without a platform in non-interactive mode', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'codex'], { io, prompt: null });

  assert.equal(code, 1);
  assert.equal(await exists(target), false);
  assert.match(io.stderr, /Platform selection required/);
  assert.match(io.stderr, /--platform codex\|opencode\|claude-code/);
});

test('init fails without a developer in non-interactive mode', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--platform', 'codex'], { io, prompt: null });

  assert.equal(code, 1);
  assert.equal(await exists(target), false);
  assert.match(io.stderr, /Developer name required/);
  assert.match(io.stderr, /--developer <name>/);
});

test('init uses platform selector and then prompts for developer', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();
  const prompts = [];
  const selectorCalls = [];

  const code = await main(['init', target], {
    io,
    selectPlatforms: async (request) => {
      selectorCalls.push(request);
      return ['opencode'];
    },
    prompt: async (message) => {
      prompts.push(message);
      return 'alice';
    }
  });

  assert.equal(code, 0);
  assert.match(selectorCalls[0].message, /Select platforms/);
  assert.equal(selectorCalls[0].choices.length, 3);
  assert.match(prompts[0], /Developer name/);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.opencode', 'agents', 'cowork-implement.md')), true);
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, 'CLAUDE.md')), false);
  assert.match(await readText(join(target, '.cowork-flow', '.developer')), /^name=alice\ninitialized_at=.+\n$/);
  assert.equal(await exists(join(target, '.cowork-flow', 'workspace')), false);
});

test('init preserves existing developer identity even with force', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, '.cowork-flow', '.developer'), 'name=existing\ninitialized_at=old\n', 'utf8');
  const io = createIo();

  const code = await main(['init', target, '--force', '--developer', 'new-name', '--platform', 'codex'], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.cowork-flow', '.developer')), 'name=existing\ninitialized_at=old\n');
  assert.match(io.stdout, /Developer already initialized: existing/);
});
