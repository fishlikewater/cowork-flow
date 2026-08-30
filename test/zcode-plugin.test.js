import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { access, cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { test } from 'node:test';

import { runInstallZCodePlugin } from '../src/commands/install-zcode-plugin.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';

const LOCAL_MARKETPLACE = 'cowork-flow-local';
const OFFICIAL_MARKETPLACE = 'zcode-plugins-official';

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
    LOCAL_MARKETPLACE,
    'cowork-flow',
    version
  );
}

function localMarketplaceDir(zcodeHome) {
  return join(zcodeHome, 'cli', 'plugins', 'marketplaces', LOCAL_MARKETPLACE);
}

function localMarketplaceSourceDir(zcodeHome) {
  return join(zcodeHome, 'cli', 'plugins', 'cache', 'marketplaces', LOCAL_MARKETPLACE);
}

function localCacheRoot(zcodeHome) {
  return join(zcodeHome, 'cli', 'plugins', 'cache', LOCAL_MARKETPLACE, 'cowork-flow');
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function pathExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
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

test('zcode scaffold source does not commit workflow bootstrap files', async () => {
  const sourceScaffold = join(templateRoot, '.zcode', 'scaffold');

  for (const relativePath of ['.cowork-flow', 'AGENTS.md', 'CLAUDE.md']) {
    await assert.rejects(access(join(sourceScaffold, relativePath)));
  }
});

test('zcode hook config uses process executor with args', async () => {
  const hooksConfig = await readJson(join(templateRoot, '.zcode', 'hooks', 'hooks.json'));
  for (const eventName of ['SessionStart', 'UserPromptSubmit', 'PostToolUse']) {
    const hook = hooksConfig.hooks[eventName][0].hooks[0];
    assert.equal(hook.type, 'process');
    assert.equal(hook.command, 'node');
    assert.deepEqual(hook.args, ['${ZCODE_PLUGIN_ROOT}/hooks/inject-context.js']);
  }
});

test('zcode PostToolUse matcher covers every edit-capable tool', async () => {
  const hooksConfig = await readJson(join(templateRoot, '.zcode', 'hooks', 'hooks.json'));
  const matchers = hooksConfig.hooks.PostToolUse.map((entry) => entry.matcher);
  for (const tool of ['Edit', 'Write', 'MultiEdit', 'Bash']) {
    assert.ok(
      matchers.some((m) => m.split('|').includes(tool)),
      `${tool} must be matched (edit-scope warnings / lifecycle refresh rely on it)`
    );
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
  assert.match(payload.hookSpecificOutput.additionalContext, /<workflow-state[^>]*>/);
  assert.doesNotMatch(payload.hookSpecificOutput.additionalContext, /status="not_initialized"/);
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

  const payload = runZCodeHook(
    {
      hook_event_name: 'UserPromptSubmit',
      cwd: projectRoot,
      prompt: 'cowork_runtime_context_id: ctx-zcode-test'
    },
    { cwd: projectRoot }
  );

  assert.equal(payload.hookSpecificOutput.hookEventName, 'UserPromptSubmit');
  assert.match(payload.hookSpecificOutput.additionalContext, /status="delegated_subtask"/);
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
  const installedScaffold = join(pluginRoot, 'scaffold');

  for (const relativePath of ['.cowork-flow', 'AGENTS.md', 'CLAUDE.md']) {
    await assert.rejects(access(join(installedScaffold, relativePath)));
  }
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

test('install-zcode-plugin writes local marketplace and known marketplace entry', async (t) => {
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

  const knownPath = join(zcodeHome, 'cli', 'plugins', 'known_marketplaces.json');
  await mkdir(join(knownPath, '..'), { recursive: true });
  await writeFile(
    knownPath,
    JSON.stringify({
      version: 1,
      marketplaces: [
        {
          id: OFFICIAL_MARKETPLACE,
          source: { source: 'url', url: 'https://cdn-zcode.z.ai/zcode/official-plugin/marketplace.json' },
          name: OFFICIAL_MARKETPLACE
        }
      ]
    }, null, 2),
    'utf8'
  );

  await runInstallZCodePlugin(['--force']);

  const pluginRoot = await installedPluginRoot(zcodeHome);
  const marketplacePath = join(localMarketplaceDir(zcodeHome), 'marketplace.json');
  const marketplaceSourcePath = join(localMarketplaceSourceDir(zcodeHome), 'marketplace.json');
  const marketplace = await readJson(marketplacePath);
  const sourceMarketplace = await readJson(marketplaceSourcePath);
  const entry = marketplace.plugins.find((plugin) => plugin.name === 'cowork-flow');

  assert.deepEqual(sourceMarketplace, marketplace);

  assert.equal(marketplace.name, LOCAL_MARKETPLACE);
  assert.equal(marketplace.version, 1);
  assert.ok(entry);
  assert.equal(entry.cachePath, undefined);
  assert.equal(entry.category, 'developer-tools');
  assert.deepEqual(entry.source, {
    source: 'directory',
    path: pluginRoot.replaceAll('\\', '/')
  });

  const known = await readJson(knownPath);
  const knownEntry = known.marketplaces.find((marketplaceEntry) => marketplaceEntry.id === LOCAL_MARKETPLACE);
  assert.equal(known.version, 1);
  assert.ok(knownEntry);
  assert.ok(known.marketplaces.find((marketplaceEntry) => marketplaceEntry.id === OFFICIAL_MARKETPLACE));
  assert.deepEqual(knownEntry.source, {
    source: 'directory',
    path: localMarketplaceSourceDir(zcodeHome).replaceAll('\\', '/')
  });
  assert.notEqual(knownEntry.source.path, localMarketplaceDir(zcodeHome).replaceAll('\\', '/'));
  assert.equal(knownEntry.pluginCount, 1);
});

test('install-zcode-plugin restores active marketplace from stable source after refresh deletion', async (t) => {
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

  const activeMarketplaceDir = localMarketplaceDir(zcodeHome);
  const sourceMarketplacePath = join(localMarketplaceSourceDir(zcodeHome), 'marketplace.json');
  await access(sourceMarketplacePath);

  await rm(activeMarketplaceDir, { recursive: true, force: true });
  await assert.rejects(access(join(activeMarketplaceDir, 'marketplace.json')));
  await access(sourceMarketplacePath);

  await runInstallZCodePlugin([]);

  assert.deepEqual(
    await readJson(join(activeMarketplaceDir, 'marketplace.json')),
    await readJson(sourceMarketplacePath)
  );
});

test('install-zcode-plugin dry-run does not update marketplace metadata', async (t) => {
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

  await mkdir(await installedPluginRoot(zcodeHome), { recursive: true });
  const knownPath = join(zcodeHome, 'cli', 'plugins', 'known_marketplaces.json');
  await mkdir(join(knownPath, '..'), { recursive: true });
  await writeFile(knownPath, JSON.stringify({ version: 1, marketplaces: [] }, null, 2), 'utf8');

  const officialMarketplacePath = join(
    zcodeHome,
    'cli',
    'plugins',
    'marketplaces',
    OFFICIAL_MARKETPLACE,
    'marketplace.json'
  );
  await mkdir(join(officialMarketplacePath, '..'), { recursive: true });
  await writeFile(
    officialMarketplacePath,
    JSON.stringify({
      name: OFFICIAL_MARKETPLACE,
      plugins: [{ name: 'cowork-flow', version: '0.0.44', source: { source: 'directory', path: 'legacy' } }],
      version: 1
    }, null, 2),
    'utf8'
  );

  await runInstallZCodePlugin(['--dry-run']);

  await assert.rejects(access(join(localMarketplaceDir(zcodeHome), 'marketplace.json')));
  assert.deepEqual(await readJson(knownPath), { version: 1, marketplaces: [] });
  const officialMarketplace = await readJson(officialMarketplacePath);
  assert.equal(officialMarketplace.plugins.length, 1);
  assert.equal(officialMarketplace.plugins[0].name, 'cowork-flow');
});

test('install-zcode-plugin preserves old versions by default and prunes on request', async (t) => {
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

  const oldVersionDir = join(localCacheRoot(zcodeHome), '0.0.1');
  await mkdir(oldVersionDir, { recursive: true });
  await writeFile(join(oldVersionDir, 'marker.txt'), 'old version', 'utf8');

  await runInstallZCodePlugin(['--force']);

  const currentRoot = await installedPluginRoot(zcodeHome);
  await access(currentRoot);
  await access(join(oldVersionDir, 'marker.txt'));

  await runInstallZCodePlugin(['--force', '--prune-old']);

  await access(currentRoot);
  await assert.rejects(access(oldVersionDir));
});

test('install-zcode-plugin removes legacy official marketplace entry', async (t) => {
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

  const officialMarketplacePath = join(
    zcodeHome,
    'cli',
    'plugins',
    'marketplaces',
    OFFICIAL_MARKETPLACE,
    'marketplace.json'
  );
  await mkdir(join(officialMarketplacePath, '..'), { recursive: true });
  await writeFile(
    officialMarketplacePath,
    JSON.stringify({
      name: OFFICIAL_MARKETPLACE,
      plugins: [
        { name: 'cowork-flow', version: '0.0.44', source: { source: 'directory', path: 'legacy' } },
        { name: 'zcode-guide', version: '0.1.0', source: 'filesystem' }
      ],
      version: 1
    }, null, 2),
    'utf8'
  );

  await runInstallZCodePlugin(['--force']);

  const officialMarketplace = await readJson(officialMarketplacePath);
  assert.equal(
    officialMarketplace.plugins.some((plugin) => plugin.name === 'cowork-flow'),
    false
  );
  assert.equal(
    officialMarketplace.plugins.some((plugin) => plugin.name === 'zcode-guide'),
    true
  );
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
  await mkdir(join(projectRoot, '.cowork-flow'), { recursive: true });
  await writeFile(join(projectRoot, 'AGENTS.md'), 'root workflow owner\n', 'utf8');
  await writeFile(join(projectRoot, 'CLAUDE.md'), 'root workflow owner\n', 'utf8');
  await mkdir(moduleA, { recursive: true });
  await mkdir(moduleB, { recursive: true });

  if (await pathExists(installedScaffold)) {
    for (const target of [moduleA, moduleB]) {
      await cp(installedScaffold, target, { recursive: true, force: true });
    }
  }

  await access(join(projectRoot, '.cowork-flow'));
  await access(join(projectRoot, 'AGENTS.md'));
  await access(join(projectRoot, 'CLAUDE.md'));
  for (const moduleDir of [moduleA, moduleB]) {
    for (const relativePath of ['.cowork-flow', 'AGENTS.md', 'CLAUDE.md']) {
      await assert.rejects(access(join(moduleDir, relativePath)));
    }
  }
});
