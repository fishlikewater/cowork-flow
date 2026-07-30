import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { access, cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { test } from 'node:test';

import { runInstallZCodePlugin } from '../src/commands/install-zcode-plugin.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';

async function listRelativeFiles(root) {
  const { readdir } = await import('node:fs/promises');
  const result = [];

  async function walk(dir) {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(path);
      } else if (entry.isFile()) {
        result.push(relative(root, path).replaceAll('\\', '/'));
      }
    }
  }

  await walk(root);
  return result.sort();
}

async function installedPluginRoot(zcodeHome) {
  const { version } = await readPackageInfo();
  return join(
    zcodeHome,
    'cli',
    'plugins',
    'cache',
    'zcode-plugins-official',
    'cowork-flow',
    version
  );
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

function runZCodeHook(input, options = {}) {
  const result = spawnSync(process.execPath, [join(templateRoot, '.zcode', 'hooks', 'inject-context.js')], {
    cwd: options.cwd || process.cwd(),
    input: `${JSON.stringify(input)}\n`,
    encoding: 'utf8',
    env: {
      ...process.env,
      ZCODE_PLUGIN_ROOT: join(templateRoot, '.zcode'),
      ZCODE_PROJECT_DIR: '',
      COWORK_FLOW_RUNTIME_CONTEXT_ID: ''
    }
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test('zcode scaffold source does not commit standalone spec tree', async () => {
  await assert.rejects(
    access(join(templateRoot, '.zcode', 'scaffold', '.cowork-flow', 'spec'))
  );
});

test('zcode hook config uses process executor with args', async () => {
  const hooksConfig = await readJson(join(templateRoot, '.zcode', 'hooks', 'hooks.json'));
  for (const eventName of ['SessionStart', 'UserPromptSubmit']) {
    const hook = hooksConfig.hooks[eventName][0].hooks[0];
    assert.equal(hook.type, 'process');
    assert.equal(hook.command, 'node');
    assert.deepEqual(hook.args, ['${ZCODE_PLUGIN_ROOT}/hooks/inject-context.js']);
  }
});

test('zcode hook reads stdin event and cwd for workflow-state injection', async (t) => {
  const unrelatedCwd = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-hook-cwd-'));
  t.after(async () => {
    await rm(unrelatedCwd, { recursive: true, force: true });
  });

  const payload = runZCodeHook(
    {
      hook_event_name: 'SessionStart',
      cwd: process.cwd(),
      source: 'startup'
    },
    { cwd: unrelatedCwd }
  );

  assert.equal(payload.hookSpecificOutput.hookEventName, 'SessionStart');
  assert.match(payload.hookSpecificOutput.additionalContext, /<workflow-state>/);
  assert.doesNotMatch(payload.hookSpecificOutput.additionalContext, /Status: not_initialized/);
});

test('zcode hook uses prompt runtime context for delegated subtask injection', async (t) => {
  const projectRoot = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-runtime-'));
  t.after(async () => {
    await rm(projectRoot, { recursive: true, force: true });
  });

  const runtimeDir = join(projectRoot, '.cowork-flow', '.runtime', 'subagents');
  await mkdir(runtimeDir, { recursive: true });
  await writeFile(
    join(runtimeDir, 'ctx-zcode-test.json'),
    JSON.stringify({
      scope: 'subagent',
      status: 'open',
      task_dir: '.cowork-flow/tasks/demo',
      agent_type: 'cowork-check',
      assignment: {
        goal: 'review zcode hook compatibility'
      }
    }),
    'utf8'
  );

  const payload = runZCodeHook({
    hook_event_name: 'UserPromptSubmit',
    cwd: projectRoot,
    prompt: 'cowork_runtime_context_id: ctx-zcode-test'
  });

  assert.equal(payload.hookSpecificOutput.hookEventName, 'UserPromptSubmit');
  assert.match(payload.hookSpecificOutput.additionalContext, /Status: delegated_subtask/);
  assert.match(payload.hookSpecificOutput.additionalContext, /Runtime context: ctx-zcode-test/);
});

test('install-zcode-plugin keeps workflow files out of zcode scaffold', async (t) => {
  const zcodeHome = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-home-'));
  const originalZCodeHome = process.env.ZCODE_HOME;
  process.env.ZCODE_HOME = zcodeHome;
  t.after(async () => {
    if (originalZCodeHome === undefined) {
      delete process.env.ZCODE_HOME;
    } else {
      process.env.ZCODE_HOME = originalZCodeHome;
    }
    await rm(zcodeHome, { recursive: true, force: true });
  });

  await runInstallZCodePlugin(['--force']);

  const pluginRoot = await installedPluginRoot(zcodeHome);
  const installedSpec = join(pluginRoot, 'scaffold', '.cowork-flow', 'spec');

  await assert.rejects(access(installedSpec));

  const installedScaffold = join(pluginRoot, 'scaffold');
  const scaffoldFiles = await listRelativeFiles(installedScaffold);
  assert.equal(
    scaffoldFiles.some((file) => file === '.cowork-flow' || file.startsWith('.cowork-flow/')),
    false
  );
  await access(join(installedScaffold, 'AGENTS.md'));
  await access(join(installedScaffold, 'CLAUDE.md'));
  await access(join(pluginRoot, 'hooks', 'inject-context.js'));
  await access(join(pluginRoot, 'skills', 'cowork-flow', 'SKILL.md'));
  await access(join(pluginRoot, 'agents', 'cowork-implement.md'));
  await access(join(pluginRoot, 'agents', 'cowork-check.md'));
  await access(join(pluginRoot, 'agents', 'cowork-research.md'));

  const manifest = await readJson(join(pluginRoot, '.zcode-plugin', 'plugin.json'));
  assert.equal(manifest.hooks, 'hooks/hooks.json');
  assert.equal(manifest.agents, 'agents');
  assert.equal(manifest.skills, 'skills');

  await access(join(pluginRoot, manifest.hooks));
  await access(join(pluginRoot, manifest.agents, 'cowork-implement.md'));
  await access(join(pluginRoot, manifest.agents, 'cowork-check.md'));
  await access(join(pluginRoot, manifest.agents, 'cowork-research.md'));
  await access(join(pluginRoot, manifest.skills, 'cowork-flow', 'SKILL.md'));

  const implementAgent = await readFile(join(pluginRoot, 'agents', 'cowork-implement.md'), 'utf8');
  assert.match(implementAgent, /skills\/agent-dispatch\/SKILL\.md/);
  assert.doesNotMatch(implementAgent, /\.agents\/skills/);
});

test('install-zcode-plugin writes documented marketplace source entry', async (t) => {
  const zcodeHome = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-home-'));
  const originalZCodeHome = process.env.ZCODE_HOME;
  process.env.ZCODE_HOME = zcodeHome;
  t.after(async () => {
    if (originalZCodeHome === undefined) {
      delete process.env.ZCODE_HOME;
    } else {
      process.env.ZCODE_HOME = originalZCodeHome;
    }
    await rm(zcodeHome, { recursive: true, force: true });
  });

  await runInstallZCodePlugin(['--force']);

  const pluginRoot = await installedPluginRoot(zcodeHome);
  const marketplace = await readJson(join(
    zcodeHome,
    'cli',
    'plugins',
    'marketplaces',
    'zcode-plugins-official',
    'marketplace.json'
  ));
  const entry = marketplace.plugins.find((plugin) => plugin.name === 'cowork-flow');

  assert.ok(entry);
  assert.equal(entry.cachePath, undefined);
  assert.deepEqual(entry.source, {
    source: 'directory',
    path: pluginRoot.replaceAll('\\', '/')
  });
});

test('zcode scaffold cannot create workflow files in module directories', async (t) => {
  const zcodeHome = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-home-'));
  const projectRoot = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-project-'));
  const originalZCodeHome = process.env.ZCODE_HOME;
  process.env.ZCODE_HOME = zcodeHome;
  t.after(async () => {
    if (originalZCodeHome === undefined) {
      delete process.env.ZCODE_HOME;
    } else {
      process.env.ZCODE_HOME = originalZCodeHome;
    }
    await rm(zcodeHome, { recursive: true, force: true });
    await rm(projectRoot, { recursive: true, force: true });
  });

  await runInstallZCodePlugin(['--force']);

  const installedScaffold = join(await installedPluginRoot(zcodeHome), 'scaffold');
  const moduleA = join(projectRoot, 'module-a');
  const moduleB = join(projectRoot, 'apps', 'module-b');
  await mkdir(moduleA, { recursive: true });
  await mkdir(moduleB, { recursive: true });

  for (const target of [projectRoot, moduleA, moduleB]) {
    await cp(installedScaffold, target, { recursive: true, force: true });
  }

  await assert.rejects(access(join(projectRoot, '.cowork-flow')));
  await assert.rejects(access(join(moduleA, '.cowork-flow')));
  await assert.rejects(access(join(moduleB, '.cowork-flow')));
});
