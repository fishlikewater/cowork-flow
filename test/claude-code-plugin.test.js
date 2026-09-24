import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { runInstallClaudeCodePlugin } from '../src/commands/install-claude-code-plugin.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';

const PLUGIN_NAME = 'cowork-flow';
const MANIFEST_RELATIVE = ['.claude-plugin', 'plugin.json'];
const BOOTSTRAP_SKILL = ['skills', 'cowork-flow-bootstrap', 'SKILL.md'];

const payloadRoot = join(templateRoot, '..', 'presets', 'claude-code');

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function withClaudeHome(home, run) {
  const previous = process.env.CLAUDE_CONFIG_DIR;
  process.env.CLAUDE_CONFIG_DIR = home;
  try {
    return await run();
  } finally {
    if (previous === undefined) delete process.env.CLAUDE_CONFIG_DIR;
    else process.env.CLAUDE_CONFIG_DIR = previous;
  }
}

// `~/.claude` is a directory users fill by hand, so every case starts from a
// home that already holds someone else's skill and an unrelated settings file.
async function seedClaudeHome() {
  const home = await mkdtemp(join(tmpdir(), 'cowork-flow-claude-home-'));
  const foreignSkill = join(home, 'skills', 'their-skill');
  await mkdir(foreignSkill, { recursive: true });
  await writeFile(join(foreignSkill, 'SKILL.md'), '# theirs\n', 'utf8');
  await writeFile(join(home, 'settings.json'), '{"keep":"me"}\n', 'utf8');
  return { home, foreignSkill };
}

function installPath(home) {
  return join(home, 'skills', PLUGIN_NAME);
}

async function install(root, ...parts) {
  return readFile(join(root, ...parts), 'utf8');
}

test('the claude-code payload is a manifest plus the bootstrap skill', async () => {
  const manifest = await readJson(join(payloadRoot, ...MANIFEST_RELATIVE));
  const pkg = await readJson(join(templateRoot, '..', 'package.json'));

  assert.equal(manifest.name, PLUGIN_NAME);
  assert.equal(
    manifest.version,
    pkg.version,
    'a stale manifest version makes the installed plugin disagree with the package'
  );
  // `skills` is the component that makes this folder a plugin at all: Claude
  // Code reads the declared directory and nothing else here.
  assert.equal(manifest.skills, './skills/');
  await access(join(payloadRoot, ...BOOTSTRAP_SKILL));
});

test('no payload skill shadows a project skill', async () => {
  // Claude Code enumerates the project and the plugin skill roots together, so a
  // payload skill with a project skill's name would make one of them unreachable.
  const names = await readdir(join(payloadRoot, 'skills'));
  assert.deepEqual(names, ['cowork-flow-bootstrap']);
  for (const name of names) {
    await assert.rejects(
      access(join(templateRoot, 'skills', name)),
      `payload Skill ${name} must not shadow a project Skill`
    );
  }
});

test('install-claude-code-plugin writes the payload into the skills directory', async () => {
  const { home } = await seedClaudeHome();
  try {
    const { version } = await readPackageInfo();
    await withClaudeHome(home, () => runInstallClaudeCodePlugin([]));
    const target = installPath(home);

    const manifest = await readJson(join(target, ...MANIFEST_RELATIVE));
    assert.equal(manifest.name, PLUGIN_NAME);
    assert.equal(
      manifest.version,
      version,
      'the installed manifest must carry the package version, not the shipped one'
    );
    // The declared path is what Claude Code resolves against the plugin root, so
    // the install is only loadable when it resolves to a real directory.
    const declared = manifest.skills.replace(/^\.\//, '').replace(/\/$/, '');
    const skill = await readFile(join(target, ...declared.split('/'), 'cowork-flow-bootstrap', 'SKILL.md'), 'utf8');
    assert.match(skill, /cowork-flow/);
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('the skills-directory channel leaves no second record behind', async () => {
  // This channel has no marketplace and no install record: Claude Code loads the
  // folder because of the manifest inside it. An installer that started writing
  // a registry or an enabledPlugins flag would be writing state nothing reads.
  const { home, foreignSkill } = await seedClaudeHome();
  try {
    await withClaudeHome(home, () => runInstallClaudeCodePlugin([]));

    assert.deepEqual(
      (await readdir(home)).sort(),
      ['settings.json', 'skills'],
      'the installer must not create anything beside the skills directory'
    );
    assert.deepEqual((await readdir(join(home, 'skills'))).sort(), ['cowork-flow', 'their-skill']);
    assert.equal(await readFile(join(home, 'settings.json'), 'utf8'), '{"keep":"me"}\n');
    assert.equal(await readFile(join(foreignSkill, 'SKILL.md'), 'utf8'), '# theirs\n');
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-claude-code-plugin is idempotent and reports an up-to-date install', async () => {
  const { home } = await seedClaudeHome();
  try {
    await withClaudeHome(home, () => runInstallClaudeCodePlugin([]));
    const target = installPath(home);
    const marker = join(target, 'user-note.md');
    await writeFile(marker, 'kept\n', 'utf8');

    await withClaudeHome(home, () => runInstallClaudeCodePlugin([]));
    assert.equal(
      await readFile(marker, 'utf8'),
      'kept\n',
      'a same-version rerun must not rewrite the installed copy'
    );

    await withClaudeHome(home, () => runInstallClaudeCodePlugin(['--force']));
    await assert.rejects(access(marker), 'a forced reinstall must restore the shipped payload');
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-claude-code-plugin refuses a foreign folder at its install path', async () => {
  const { home } = await seedClaudeHome();
  try {
    const target = installPath(home);
    await mkdir(join(target, '.claude-plugin'), { recursive: true });
    await writeFile(
      join(target, ...MANIFEST_RELATIVE),
      JSON.stringify({ name: 'someone-else', version: '1.0.0' }, null, 2) + '\n',
      'utf8'
    );
    await writeFile(join(target, 'theirs.md'), 'not ours\n', 'utf8');

    await assert.rejects(
      () => withClaudeHome(home, () => runInstallClaudeCodePlugin([])),
      /not the cowork-flow plugin/
    );
    assert.equal(await readFile(join(target, 'theirs.md'), 'utf8'), 'not ours\n');

    // The preview must not promise an install the real run refuses.
    await assert.rejects(
      () => withClaudeHome(home, () => runInstallClaudeCodePlugin(['--dry-run'])),
      /not the cowork-flow plugin/
    );

    await assert.rejects(
      () => withClaudeHome(home, () => runInstallClaudeCodePlugin(['--uninstall'])),
      /Refusing to delete a folder this installer did not create/
    );
    assert.equal(await readFile(join(target, 'theirs.md'), 'utf8'), 'not ours\n');
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('--force is the explicit override for both overwrite and removal', async () => {
  const { home } = await seedClaudeHome();
  try {
    const target = installPath(home);
    await mkdir(target, { recursive: true });
    // No readable manifest: neither a folder we own nor one we can reason about,
    // which is exactly the case that has no path forward without --force.
    await writeFile(join(target, 'leftover.md'), 'half-written\n', 'utf8');

    await assert.rejects(
      () => withClaudeHome(home, () => runInstallClaudeCodePlugin(['--uninstall'])),
      /use --force to remove it anyway/
    );
    assert.equal(await readFile(join(target, 'leftover.md'), 'utf8'), 'half-written\n');

    await withClaudeHome(home, () => runInstallClaudeCodePlugin(['--uninstall', '--force']));
    await assert.rejects(access(target));
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-claude-code-plugin dry-run writes nothing', async () => {
  const { home } = await seedClaudeHome();
  try {
    await withClaudeHome(home, () => runInstallClaudeCodePlugin(['--dry-run']));

    assert.deepEqual((await readdir(home)).sort(), ['settings.json', 'skills']);
    await assert.rejects(access(installPath(home)));
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});

test('install-claude-code-plugin uninstall removes only its own folder', async () => {
  const { home, foreignSkill } = await seedClaudeHome();
  try {
    await withClaudeHome(home, () => runInstallClaudeCodePlugin([]));
    await withClaudeHome(home, () => runInstallClaudeCodePlugin(['--uninstall']));

    await assert.rejects(access(installPath(home)));
    assert.equal(await readFile(join(foreignSkill, 'SKILL.md'), 'utf8'), '# theirs\n');
    assert.equal(await readFile(join(home, 'settings.json'), 'utf8'), '{"keep":"me"}\n');
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});
