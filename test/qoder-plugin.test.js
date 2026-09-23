import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { access, cp, mkdir, mkdtemp, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { runInstallQoderPlugin } from '../src/commands/install-qoder-plugin.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';

const PLUGIN_KEY = 'cowork-flow@cowork-flow-local';
const FOREIGN_PLUGIN_KEY = 'someone-else@their-market';

const pluginRoot = join(templateRoot, '..', 'presets', 'qoder');
const SHIM = join(pluginRoot, 'hooks', 'inject-context.py');
const FIXED_AGENTS = ['cowork-implement', 'cowork-check', 'cowork-research'];

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

function runShim(input, cwd) {
  return spawnSync('python', [SHIM], {
    cwd,
    input: `${JSON.stringify(input)}\n`,
    encoding: 'utf8',
    env: {
      ...process.env,
      COWORK_FLOW_CONTEXT_ID: '',
      COWORK_FLOW_RUNTIME_CONTEXT_ID: '',
      QODER_PROJECT_DIR: '',
      QODER_WORKING_DIR: ''
    }
  });
}

async function makeProject(root) {
  await mkdir(join(root, '.cowork-flow'), { recursive: true });
  await cp(join(templateRoot, '.cowork-flow', 'scripts'), join(root, '.cowork-flow', 'scripts'), {
    recursive: true
  });
}

test('qoder hook config runs the plugin shim without a shell', async () => {
  const hooksConfig = await readJson(join(pluginRoot, 'hooks', 'hooks.json'));

  for (const eventName of ['SessionStart', 'UserPromptSubmit', 'PostToolUse']) {
    const entries = hooksConfig.hooks[eventName];
    assert.ok(Array.isArray(entries) && entries.length >= 1, `${eventName} declared`);
    for (const group of entries) {
      for (const hook of group.hooks) {
        // Exec form (command + args) is the only shape that survives a Windows
        // default shell, where ${VAR} would never be expanded by the shell.
        assert.equal(hook.type, 'command');
        assert.equal(hook.command, 'python');
        assert.deepEqual(hook.args, ['${QODER_PLUGIN_ROOT}/hooks/inject-context.py']);
        assert.ok(hook.timeout >= 1 && hook.timeout <= 30, `${eventName} must stay bounded`);
      }
    }
  }
});

test('qoder PostToolUse matcher only names tools Qoder exposes', async () => {
  const hooksConfig = await readJson(join(pluginRoot, 'hooks', 'hooks.json'));
  const documentedTools = new Set([
    'Read', 'Grep', 'Glob', 'Bash', 'Write', 'Edit', 'WebFetch', 'WebSearch', 'Agent'
  ]);
  const matchers = hooksConfig.hooks.PostToolUse.map((group) => group.matcher);

  assert.ok(
    matchers.some((matcher) => matcher.split('|').includes('Edit')),
    'edit-phase spec checks need Edit'
  );
  assert.ok(
    matchers.some((matcher) => matcher.split('|').includes('Write')),
    'edit-phase spec checks need Write'
  );
  for (const matcher of matchers) {
    for (const tool of matcher.split('|')) {
      assert.ok(
        documentedTools.has(tool),
        `"${tool}" is not a Qoder tool name; matchers copied from another host never fire`
      );
    }
  }
});

test('qoder plugin manifest declares only components that ship', async () => {
  const manifest = await readJson(join(pluginRoot, '.qoder-plugin', 'plugin.json'));
  const pkg = await readJson(join(templateRoot, '..', 'package.json'));

  assert.equal(manifest.name, 'cowork-flow');
  assert.equal(
    manifest.version,
    pkg.version,
    'a stale manifest version makes the installed plugin disagree with its cache directory'
  );
  assert.equal(manifest.hooks, 'hooks/hooks.json');
  assert.equal(manifest.agents, 'agents');
  // The payload carries bootstrap guidance only; project Skills still ship with
  // the project copy (init/sync). Qoder enumerates the project and payload Skill
  // roots, so payload Skill names must stay disjoint from template/skills/.
  assert.equal(manifest.skills, 'skills');
  // commands/settings are declared by nothing here: no commands/ dir ships, and
  // Qoder ignores every settings key except `agent`.
  assert.equal(manifest.commands, undefined);
  assert.equal(manifest.settings, undefined);

  await readFile(join(pluginRoot, 'hooks', 'hooks.json'), 'utf8');
  for (const agent of FIXED_AGENTS) {
    await readFile(join(pluginRoot, 'agents', `${agent}.md`), 'utf8');
  }
});

test('qoder fixed agents bind tools, block nested dispatch, and skip mode claims', async () => {
  for (const agent of FIXED_AGENTS) {
    const text = await readFile(join(pluginRoot, 'agents', `${agent}.md`), 'utf8');

    assert.match(text, new RegExp(`^name: ${agent}$`, 'm'));
    assert.match(text, /^description: \S.{20,}$/m);
    assert.match(text, /^disallowedTools: \[Agent\]$/m);
    assert.doesNotMatch(text, /^tools:.*\bAgent\b.*$/m);
    // A subagent cannot make itself stricter than a permissive parent session,
    // so declaring a mode here would only look like a guarantee.
    assert.doesNotMatch(text, /^permissionMode:/m);
    assert.doesNotMatch(text, /^model:/m);

    for (const [, skillName] of text.matchAll(/\.agents\/skills\/([^/]+)\/SKILL\.md/g)) {
      await readFile(join(templateRoot, 'skills', skillName, 'SKILL.md'), 'utf8');
    }
    assert.match(text, /\.agents\/skills\/agent-dispatch\/SKILL\.md/);
    assert.doesNotMatch(text, /\.cowork-flow\/skills/);
  }
});

test('qoder shim renders the project workflow state through the project runtime', async () => {
  const project = await mkdtemp(join(tmpdir(), 'cowork-flow-qoder-hook-'));
  try {
    await makeProject(project);
    const result = runShim(
      { hook_event_name: 'SessionStart', cwd: project, session_id: 's1' },
      project
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, '');
    const envelope = JSON.parse(result.stdout).hookSpecificOutput;
    assert.equal(envelope.hookEventName, 'SessionStart');
    assert.match(envelope.additionalContext, /<workflow-state status="no_task"/);
    assert.match(envelope.additionalContext, /host="qoder" adapter="qoder\.hooks"/);
    // The generic `session_id` must resolve through the declared host into the
    // qoder-prefixed context key, which is what the CLI side re-uses to bind.
    assert.match(envelope.additionalContext, /session="qoder_s1"/);
  } finally {
    await rm(project, { recursive: true, force: true });
  }
});

test('qoder shim stays silent outside a cowork-flow project', async () => {
  const loose = await mkdtemp(join(tmpdir(), 'cowork-flow-qoder-loose-'));
  try {
    const result = runShim(
      { hook_event_name: 'SessionStart', cwd: loose, session_id: 's1' },
      loose
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), '');
  } finally {
    await rm(loose, { recursive: true, force: true });
  }
});

async function withQoderHome(home, run) {
  const previous = process.env.QODER_CONFIG_DIR;
  process.env.QODER_CONFIG_DIR = home;
  try {
    return await run();
  } finally {
    if (previous === undefined) delete process.env.QODER_CONFIG_DIR;
    else process.env.QODER_CONFIG_DIR = previous;
  }
}

async function seedQoderHome() {
  const home = await mkdtemp(join(tmpdir(), 'cowork-flow-qoder-home-'));
  const foreignInstall = join(home, 'plugins', 'cache', 'their-market', 'someone-else', '1.0.0');
  await mkdir(foreignInstall, { recursive: true });
  await writeFile(
    join(home, 'plugins', 'installed_plugins_v2.json'),
    JSON.stringify({
      version: 2,
      plugins: {
        [FOREIGN_PLUGIN_KEY]: [
          { scope: 'user', installPath: foreignInstall, version: '1.0.0', userVisible: false }
        ]
      },
      futureField: { mustSurvive: true }
    }, null, 2) + '\n',
    'utf8'
  );
  await writeFile(
    join(home, 'settings.json'),
    JSON.stringify({
      enabledPlugins: { [FOREIGN_PLUGIN_KEY]: true },
      mcpServers: { docs: { command: './scripts/docs-mcp' } },
      providers: [{ id: 'keep-me' }]
    }, null, 2) + '\n',
    'utf8'
  );
  return { home, foreignInstall };
}

async function installTargets(home) {
  const { version } = await readPackageInfo();
  const cacheRoot = join(home, 'plugins', 'cache', 'cowork-flow-local', 'cowork-flow');
  return { version, cacheRoot, installPath: join(cacheRoot, version) };
}

test('install-qoder-plugin writes payload, registry entry and enable flag', async () => {
  const { home } = await seedQoderHome();
  try {
    await withQoderHome(home, () => runInstallQoderPlugin([]));
    const { version, installPath } = await installTargets(home);

    assert.equal(
      (await readJson(join(installPath, '.qoder-plugin', 'plugin.json'))).version,
      version,
      'the installed manifest must agree with its cache directory name'
    );
    await readFile(join(installPath, 'hooks', 'hooks.json'), 'utf8');
    await readFile(join(installPath, 'agents', 'cowork-implement.md'), 'utf8');
    const payloadSkills = join(installPath, 'skills');
    await readFile(join(payloadSkills, 'cowork-flow-bootstrap', 'SKILL.md'), 'utf8');
    for (const name of await readdir(payloadSkills)) {
      await assert.rejects(
        access(join(templateRoot, 'skills', name)),
        `payload Skill ${name} must not shadow a project Skill`
      );
    }

    const registry = await readJson(join(home, 'plugins', 'installed_plugins_v2.json'));
    const entries = registry.plugins[PLUGIN_KEY];
    assert.equal(entries.length, 1);
    assert.equal(entries[0].installPath, installPath);
    assert.equal(entries[0].version, version);
    assert.equal(entries[0].scope, 'user');

    const settings = await readJson(join(home, 'settings.json'));
    assert.equal(settings.enabledPlugins[PLUGIN_KEY], true);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-qoder-plugin is idempotent and never touches foreign plugin state', async () => {
  const { home } = await seedQoderHome();
  try {
    const registryPath = join(home, 'plugins', 'installed_plugins_v2.json');
    const settingsPath = join(home, 'settings.json');
    const registryBefore = await readFile(registryPath, 'utf8');
    const settingsBefore = await readFile(settingsPath, 'utf8');

    await withQoderHome(home, () => runInstallQoderPlugin([]));
    await withQoderHome(home, () => runInstallQoderPlugin(['--force']));

    const registry = JSON.parse(await readFile(registryPath, 'utf8'));
    const settings = JSON.parse(await readFile(settingsPath, 'utf8'));

    assert.deepEqual(
      registry.plugins[FOREIGN_PLUGIN_KEY],
      JSON.parse(registryBefore).plugins[FOREIGN_PLUGIN_KEY]
    );
    assert.deepEqual(registry.futureField, { mustSurvive: true });
    assert.equal(registry.plugins[PLUGIN_KEY].length, 1, 'no duplicate registry entries');
    assert.deepEqual(settings.enabledPlugins[FOREIGN_PLUGIN_KEY], true);
    assert.deepEqual(settings.mcpServers, { docs: { command: './scripts/docs-mcp' } });
    assert.deepEqual(settings.providers, [{ id: 'keep-me' }]);
    assert.equal(
      JSON.parse(settingsBefore).enabledPlugins[FOREIGN_PLUGIN_KEY],
      settings.enabledPlugins[FOREIGN_PLUGIN_KEY]
    );
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-qoder-plugin refuses to overwrite a healthy install without --force', async () => {
  const { home } = await seedQoderHome();
  try {
    await withQoderHome(home, () => runInstallQoderPlugin([]));
    const { installPath } = await installTargets(home);
    const marker = join(installPath, 'agents', 'user-edit.md');
    await writeFile(marker, 'user kept\n', 'utf8');

    await withQoderHome(home, () => runInstallQoderPlugin([]));

    assert.equal(await readFile(marker, 'utf8'), 'user kept\n');
    await withQoderHome(home, () => runInstallQoderPlugin(['--force']));
    await assert.rejects(access(marker), 'a forced reinstall must restore the shipped payload');
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('a failed payload copy leaves registry and settings untouched', async () => {
  const home = await mkdtemp(join(tmpdir(), 'cowork-flow-qoder-blocked-'));
  try {
    // `plugins` as a regular file makes every payload path underneath
    // uncreatable, which is where an install must stop before advertising it.
    await writeFile(join(home, 'plugins'), 'not a directory', 'utf8');
    await writeFile(join(home, 'settings.json'), '{}', 'utf8');

    await assert.rejects(() => withQoderHome(home, () => runInstallQoderPlugin([])));

    assert.equal(await readFile(join(home, 'settings.json'), 'utf8'), '{}');
    assert.equal(await readFile(join(home, 'plugins'), 'utf8'), 'not a directory');
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-qoder-plugin dry-run writes nothing', async () => {
  const { home } = await seedQoderHome();
  try {
    const registryPath = join(home, 'plugins', 'installed_plugins_v2.json');
    const settingsPath = join(home, 'settings.json');
    const registryBefore = await readFile(registryPath, 'utf8');
    const settingsBefore = await readFile(settingsPath, 'utf8');
    const { cacheRoot } = await installTargets(home);

    await withQoderHome(home, () => runInstallQoderPlugin(['--dry-run']));

    assert.equal(await readFile(registryPath, 'utf8'), registryBefore);
    assert.equal(await readFile(settingsPath, 'utf8'), settingsBefore);
    await assert.rejects(access(cacheRoot));
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-qoder-plugin uninstall removes only cowork-flow state', async () => {
  const { home } = await seedQoderHome();
  try {
    await withQoderHome(home, () => runInstallQoderPlugin([]));
    const { installPath } = await installTargets(home);

    await withQoderHome(home, () => runInstallQoderPlugin(['--uninstall']));

    const registry = await readJson(join(home, 'plugins', 'installed_plugins_v2.json'));
    const settings = await readJson(join(home, 'settings.json'));
    assert.equal(registry.plugins[PLUGIN_KEY], undefined);
    assert.equal(settings.enabledPlugins[PLUGIN_KEY], undefined);
    await assert.rejects(access(installPath));
    assert.deepEqual(registry.plugins[FOREIGN_PLUGIN_KEY].length, 1);
    assert.deepEqual(settings.mcpServers, { docs: { command: './scripts/docs-mcp' } });
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});
