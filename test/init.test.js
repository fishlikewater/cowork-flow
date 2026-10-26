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

// Isolate the CLI's git lookup from the developer machine: GIT_CONFIG_GLOBAL
// points at a throwaway file and the system config is disabled.
async function withGitConfig(t, content, run) {
  const configDir = await createTempDir(t);
  const globalConfig = join(configDir, 'gitconfig');
  await writeFile(globalConfig, content, 'utf8');
  const previousGlobal = process.env.GIT_CONFIG_GLOBAL;
  const previousNoSystem = process.env.GIT_CONFIG_NOSYSTEM;
  process.env.GIT_CONFIG_GLOBAL = globalConfig;
  process.env.GIT_CONFIG_NOSYSTEM = '1';
  try {
    return await run();
  } finally {
    if (previousGlobal === undefined) {
      delete process.env.GIT_CONFIG_GLOBAL;
    } else {
      process.env.GIT_CONFIG_GLOBAL = previousGlobal;
    }
    if (previousNoSystem === undefined) {
      delete process.env.GIT_CONFIG_NOSYSTEM;
    } else {
      process.env.GIT_CONFIG_NOSYSTEM = previousNoSystem;
    }
  }
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
  assert.match(result.stdout, /Hosts: demo-host/);
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

  const code = await main(['init', target, '--developer', 'codex', '--host', 'codex'], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'adversarial-review', 'SKILL.md')), true);
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
  assert.match(io.stdout, /Hosts: codex/);
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
  assert.match(io.stdout, /Hosts: opencode/);
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
  assert.match(io.stdout, /Hosts: claude-code/);
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
  assert.equal(await exists(join(target, '.dsh', 'README.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'dsh', 'adapter.yaml')), true);
  // Qoder ships its host assets inside a machine-level plugin: even `all` must
  // not leave a project-level .qoder/ behind, only the adapter declaration.
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'qoder', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.qoder')), false);
  assert.match(io.stdout, /Hosts: codex, opencode, claude-code, dsh/);
});

test('init --platform qoder writes the adapter declaration and no .qoder directory', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main([
    'init',
    target,
    '--developer',
    'qoder-user',
    '--platform',
    'qoder'
  ], { io });

  assert.equal(code, 0, io.stderr);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'qoder', 'adapter.yaml')), true);
  // Qoder reads and discovers skills at `.agents/skills`, so one copy serves
  // both; the kernel-side replica is not written for qoder.
  assert.equal(await exists(join(target, '.agents', 'skills', 'agent-dispatch', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'skills')), false);
  assert.equal(await exists(join(target, '.qoder')), false);
  // Other hosts' assets must not ride along when only qoder is selected.
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, '.codex')), false);
});

test('init --platform zcode writes the shared skill root and no legacy replica', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main([
    'init',
    target,
    '--developer',
    'zcode-user',
    '--platform',
    'zcode'
  ], { io });

  assert.equal(code, 0, io.stderr);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'zcode', 'adapter.yaml')), true);
  // ZCode enumerates `.agents/skills` (host bundle-verified), so it shares the
  // project copy instead of the private `.cowork-flow/skills` replica.
  assert.equal(await exists(join(target, '.agents', 'skills', 'agent-dispatch', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'skills')), false);
  assert.equal(await exists(join(target, '.zcode')), false);
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, '.codex')), false);
});

test('init installs dsh-only assets when platform is dsh', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'dsh-user', '--platform', 'dsh'], { io });

  assert.equal(code, 0, JSON.stringify({
    stderr: io.stderr,
    stdout: io.stdout,
    target
  }, null, 2));
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.dsh', 'README.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'dsh', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, '.opencode')), false);
  assert.equal(await exists(join(target, '.zcode')), false);
  assert.equal(await exists(join(target, 'CLAUDE.md')), false);
  assert.match(io.stdout, /Hosts: dsh/);
  assert.match(io.stdout, /created=/);
});

test('init installs kimi-code-only assets when platform is kimi-code', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'kimi-user', '--platform', 'kimi'], { io });

  assert.equal(code, 0, JSON.stringify({
    stderr: io.stderr,
    stdout: io.stdout,
    target
  }, null, 2));
  assert.equal(await exists(join(target, 'AGENTS.md')), true);
  assert.equal(await exists(join(target, '.kimi-code', 'agents', 'cowork-implement.md')), true);
  assert.equal(await exists(join(target, '.kimi-code', 'agents', 'cowork-check.md')), true);
  assert.equal(await exists(join(target, '.kimi-code', 'agents', 'cowork-research.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'kimi-code', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, '.opencode')), false);
  assert.equal(await exists(join(target, '.dsh')), false);
  assert.equal(await exists(join(target, '.zcode')), false);
  assert.equal(await exists(join(target, 'CLAUDE.md')), false);
  assert.match(io.stdout, /Hosts: kimi-code/);
  assert.match(io.stdout, /created=/);
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

  assert.equal(code, 2);
  assert.equal(await exists(target), false);
  assert.match(io.stderr, /Unsupported host: both/);
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

test('init distinguishes a missing Python from an older one', async (t) => {
  const cases = [
    {
      name: 'missing',
      expected: /no usable Python 3\.10\+ interpreter found/,
      rejected: /older than 3\.10/,
      pythonProbe: async () => ({
        found: false,
        version: null,
        command: null,
        explicit: null,
        tooOld: false
      })
    },
    {
      name: 'too old',
      expected: /Python 3\.9 \(python\) is older than 3\.10/,
      rejected: /no usable Python 3\.10\+ interpreter found/,
      pythonProbe: async () => ({
        found: false,
        version: '3.9',
        command: 'python',
        explicit: null,
        tooOld: true
      })
    },
    {
      name: 'invalid explicit override',
      expected: /COWORK_FLOW_PYTHON does not point to a usable Python 3\.10\+ interpreter/,
      rejected: /no usable Python 3\.10\+ interpreter found/,
      pythonProbe: async () => ({
        found: false,
        version: null,
        command: '/missing/python',
        explicit: 'COWORK_FLOW_PYTHON',
        tooOld: false
      })
    }
  ];

  for (const testCase of cases) {
    const target = join(await createTempDir(t), testCase.name);
    const io = createIo();
    const code = await runInitWithOptions(
      [target, '--dry-run', '--developer', 'codex', '--platform', 'codex'],
      {
        io,
        prompt: null,
        selectPlatforms: null,
        pythonProbe: testCase.pythonProbe
      }
    );

    assert.equal(code, 0, `${testCase.name}: ${io.stderr}`);
    assert.match(io.stderr, /Warning:/);
    assert.match(io.stderr, testCase.expected);
    assert.doesNotMatch(io.stderr, testCase.rejected);
  }
});

test('init stays quiet when Python meets the floor', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();
  const code = await runInitWithOptions(
    [target, '--dry-run', '--developer', 'codex', '--platform', 'codex'],
    {
      io,
      prompt: null,
      selectPlatforms: null,
      pythonProbe: async () => ({
        found: true,
        version: '3.12',
        command: 'python',
        explicit: null,
        tooOld: false
      })
    }
  );

  assert.equal(code, 0, io.stderr);
  assert.doesNotMatch(io.stderr, /Python 3\.10/);
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

test('init auto-detects an existing host marker in non-interactive mode', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(join(target, '.codex'), { recursive: true });
  const io = createIo();

  const code = await main(['init', target, '--developer', 'codex', '--dry-run'], {
    io,
    prompt: null,
    selectPlatforms: null
  });

  assert.equal(code, 0, io.stderr);
  assert.match(io.stdout, /Hosts: codex/);
});

test('init fails without a host in non-interactive mode when nothing is detected', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(['init', target, '--developer', 'codex'], { io, prompt: null });

  assert.equal(code, 2);
  assert.equal(await exists(target), false);
  assert.match(io.stderr, /Host selection required/);
  assert.match(io.stderr, /--host codex\|opencode\|claude-code\|dsh/);
});

test('init falls back to git user.name when --developer is omitted', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(target, { recursive: true });
  const io = createIo();

  await withGitConfig(t, '[user]\n\tname = Git Fallback\n', async () => {
    const code = await main(['init', target, '--platform', 'codex'], { io, prompt: null });
    assert.equal(code, 0, io.stderr);
  });

  assert.match(io.stdout, /Developer initialized: Git Fallback \(from git user\.name\)/);
  assert.match(await readText(join(target, '.cowork-flow', '.developer')), /^name=Git Fallback\n/);
});

test('init fails without a developer when git has no identity in non-interactive mode', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(target, { recursive: true });
  const io = createIo();

  await withGitConfig(t, '', async () => {
    const code = await main(['init', target, '--platform', 'codex'], { io, prompt: null });
    assert.equal(code, 2);
  });

  assert.equal(await exists(join(target, '.cowork-flow')), false);
  assert.match(io.stderr, /Developer name required/);
  assert.match(io.stderr, /--developer <name>/);
});

test('init dry-run reports a missing developer identity without failing', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await mkdir(target, { recursive: true });
  const io = createIo();

  await withGitConfig(t, '', async () => {
    const code = await main(['init', target, '--host', 'codex', '--dry-run'], { io, prompt: null });
    assert.equal(code, 0, io.stderr);
  });

  assert.match(io.stdout, /would-skip=\.cowork-flow\/\.developer/);
  assert.equal(await exists(join(target, '.cowork-flow')), false);
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
      return /language/i.test(message) ? 'en-US' : 'alice';
    }
  });

  assert.equal(code, 0);
  assert.match(selectorCalls[0].message, /Select hosts/);
  assert.equal(selectorCalls[0].choices.length, 7);
  assert.deepEqual(
    selectorCalls[0].choices.map((choice) => choice.value),
    ['codex', 'opencode', 'claude-code', 'dsh', 'zcode', 'kimi-code', 'qoder']
  );
  assert.match(prompts[0], /Project language/);
  assert.match(prompts[1], /Developer name/);
  assert.match(await readText(join(target, '.cowork-flow', 'config.yaml')), /^language: "en-US"$/m);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.dsh')), false);
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

test('init writes the selected language into config.yaml', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(
    ['init', target, '--developer', 'codex', '--platform', 'codex', '--language', 'en'],
    { io, prompt: null }
  );

  assert.equal(code, 0, io.stderr);
  assert.match(await readText(join(target, '.cowork-flow', 'config.yaml')), /^language: "en-US"$/m);
  assert.match(io.stdout, /Language initialized: en-US/);
});

test('init defaults to zh-CN without an interactive language prompt', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(
    ['init', target, '--developer', 'codex', '--platform', 'codex'],
    { io, prompt: null }
  );

  assert.equal(code, 0, io.stderr);
  assert.match(await readText(join(target, '.cowork-flow', 'config.yaml')), /^language: "zh-CN"$/m);
  assert.match(io.stdout, /Language initialized: zh-CN \(default\)/);
});

test('init rejects an unsupported language before creating the target', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(
    ['init', target, '--developer', 'codex', '--platform', 'codex', '--language', 'fr'],
    { io, prompt: null }
  );

  assert.equal(code, 2);
  assert.equal(await exists(target), false);
  assert.match(io.stderr, /Unsupported language: fr/);
});

test('init preserves an existing config language even with force', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const configFile = join(target, '.cowork-flow', 'config.yaml');
  const content = 'custom: true\nlanguage: "en-US"\n';
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(configFile, content, 'utf8');
  const io = createIo();

  const code = await main(
    ['init', target, '--force', '--developer', 'codex', '--platform', 'codex', '--language', 'zh-CN'],
    { io, prompt: null }
  );

  assert.equal(code, 0, io.stderr);
  assert.equal(await readText(configFile), content);
  assert.match(io.stdout, /Language already initialized: en-US/);
  assert.match(io.stdout, /protected=/);
});

test('init dry-run reports the selected language without writing config', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();

  const code = await main(
    ['init', target, '--dry-run', '--developer', 'codex', '--platform', 'codex', '--language', 'en-US'],
    { io, prompt: null }
  );

  assert.equal(code, 0, io.stderr);
  assert.match(io.stdout, /would-create=\.cowork-flow\/config\.yaml for language en-US/);
  assert.equal(await exists(join(target, '.cowork-flow', 'config.yaml')), false);
});

test('init uses the default language when the prompt is blank', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const io = createIo();
  const prompts = [];

  const code = await main(['init', target], {
    io,
    selectPlatforms: async () => ['codex'],
    prompt: async (message) => {
      prompts.push(message);
      return /language/i.test(message) ? '' : 'alice';
    }
  });

  assert.equal(code, 0, io.stderr);
  assert.match(await readText(join(target, '.cowork-flow', 'config.yaml')), /^language: "zh-CN"$/m);
  assert.match(prompts[0], /Project language/);
});

test('init reports a missing language key without claiming the default wins', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const configFile = join(target, '.cowork-flow', 'config.yaml');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(configFile, 'custom: true\n', 'utf8');
  const io = createIo();

  const code = await main(
    ['init', target, '--developer', 'codex', '--platform', 'codex', '--language', 'en-US'],
    { io, prompt: null }
  );

  assert.equal(code, 0, io.stderr);
  assert.equal(await readText(configFile), 'custom: true\n');
  assert.match(io.stderr, /has no language setting; using zh-CN/);
  assert.match(io.stderr, /Add language: en-US and run cwf project sync/);
  assert.doesNotMatch(io.stderr, /wins over --language/);
  assert.match(io.stdout, /Language already initialized: zh-CN \(default; no language key\)/);
});

test('init warns when --language conflicts with the existing config', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  const configFile = join(target, '.cowork-flow', 'config.yaml');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(configFile, 'language: "en-US"\n', 'utf8');
  const io = createIo();

  const code = await main(
    ['init', target, '--developer', 'codex', '--platform', 'codex', '--language', 'zh-CN'],
    { io, prompt: null }
  );

  assert.equal(code, 0, io.stderr);
  assert.equal(await readText(configFile), 'language: "en-US"\n');
  assert.match(io.stderr, /wins over --language zh-CN/);
});
