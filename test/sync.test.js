import assert from 'node:assert/strict';
import { chmod, mkdir, stat, writeFile } from 'node:fs/promises';
import { join, sep } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { runSync } from '../src/commands/sync.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';
import {
  createTempDir,
  exists,
  fileSystemWithRenameFailure,
  readText
} from './helpers/fs.js';

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
  assert.equal(
    await main(['init', target, '--developer', 'codex', '--platform', 'codex,opencode'], { io: createIo() }),
    0
  );

  await writeFile(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md'), 'old skill\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'run'), 'old posix runner\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'run.cmd'), 'old windows runner\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'scripts', 'task.py'), 'old task script\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'scripts', 'common', 'gates.py'), 'old gates script\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'scripts', 'project_context.py'), 'old project context script\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'project-context.md'), 'local generated context\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'workflow.md'), 'old workflow\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'spec', 'contracts', 'workflow-state-templates.md'), 'old state templates\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'spec', 'contracts', 'entry-contract.md'), 'custom entry contract\n', 'utf8');
  await mkdir(join(target, '.codex', 'agents'), { recursive: true });
  await writeFile(join(target, '.codex', 'agents', 'cowork-implement.toml'), 'old agent\n', 'utf8');
  await writeFile(join(target, '.codex', 'hooks.json'), 'old hooks\n', 'utf8');
  await mkdir(join(target, '.opencode', 'agents'), { recursive: true });
  await writeFile(join(target, '.opencode', 'agents', 'cowork-implement.md'), 'old opencode agent\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'config.yaml'), 'custom config\n', 'utf8');
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')),
    await readText(join(templateRoot, 'skills', 'cowork-flow', 'SKILL.md'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'run')),
    await readText(join(templateRoot, '.cowork-flow', 'run'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'run.cmd')),
    await readText(join(templateRoot, '.cowork-flow', 'run.cmd'))
  );
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'task.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'common', 'gates.py')), false);
  assert.equal(
    await readText(join(target, '.cowork-flow', 'scripts', 'commands', 'task.py')),
    await readText(join(templateRoot, '.cowork-flow', 'scripts', 'commands', 'task.py'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'scripts', 'common', 'gates', 'gates.py')),
    await readText(join(templateRoot, '.cowork-flow', 'scripts', 'common', 'gates', 'gates.py'))
  );
  assert.equal(await exists(join(target, '.cowork-flow', 'scripts', 'project_context.py')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'project-context.md')), false);
  assert.equal(
    await readText(join(target, '.cowork-flow', 'workflow.md')),
    await readText(join(templateRoot, '.cowork-flow', 'workflow.md'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'spec', 'contracts', 'workflow-state-templates.md')),
    await readText(join(templateRoot, '.cowork-flow', 'spec', 'contracts', 'workflow-state-templates.md'))
  );
  assert.equal(await exists(join(target, '.cowork-flow', 'spec', 'contracts', 'entry-contract.md')), false);
  assert.equal(
    await readText(join(target, '.codex', 'agents', 'cowork-implement.toml')),
    await readText(join(templateRoot, '.codex', 'agents', 'cowork-implement.toml'))
  );
  assert.equal(
    await readText(join(target, '.codex', 'hooks.json')),
    await readText(join(templateRoot, '.codex', 'hooks.json'))
  );
  assert.equal(
    await readText(join(target, '.opencode', 'agents', 'cowork-implement.md')),
    await readText(join(templateRoot, '.opencode', 'agents', 'cowork-implement.md'))
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

test('sync upgrades framework-owned runtime rules metadata without overwriting local specs', async (t) => {
  const target = await createTempDir(t);
  assert.equal(
    await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io: createIo() }),
    0
  );
  const rulesPath = join(target, '.cowork-flow', 'spec', 'runtime', 'rules.json');
  const templateRules = await readText(
    join(templateRoot, '.cowork-flow', 'spec', 'runtime', 'rules.json')
  );
  const legacyRules = JSON.parse(templateRules);
  for (const rule of legacyRules.rules) {
    delete rule.validator;
    delete rule.parameters;
  }
  await writeFile(
    rulesPath,
    `${JSON.stringify(legacyRules, null, 2)}\n`,
    'utf8'
  );
  const localSpecPath = join(
    target,
    '.cowork-flow',
    'spec',
    'contracts',
    'local-extension.md'
  );
  await writeFile(localSpecPath, '# Local extension\n', 'utf8');

  const code = await main(['sync', target], { io: createIo() });

  assert.equal(code, 0);
  assert.equal(await readText(rulesPath), templateRules);
  assert.equal(await readText(localSpecPath), '# Local extension\n');
});

test('sync replaces only the cowork-flow block in AGENTS.md', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io: createIo() }), 0);
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

test('sync preserves direct skill layout without legacy seed material', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io: createIo() }), 0);
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(await exists(join(target, '.superpowers')), false);
  assert.equal(await exists(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), true);
});

test('sync leaves unregistered Skills and task contexts untouched', async (t) => {
  const target = await createTempDir(t);
  assert.equal(
    await main([
      'init',
      target,
      '--developer',
      'codex',
      '--platform',
      'codex,claude'
    ], { io: createIo() }),
    0
  );

  const legacyAgentSkill = join(target, '.agents', 'skills', 'start');
  const legacyClaudeSkill = join(target, '.claude', 'skills', 'finish-work');
  const customSkill = join(target, '.agents', 'skills', 'custom-local', 'SKILL.md');
  await mkdir(legacyAgentSkill, { recursive: true });
  await mkdir(legacyClaudeSkill, { recursive: true });
  await writeFile(join(legacyAgentSkill, 'SKILL.md'), 'legacy start\n', 'utf8');
  await writeFile(join(legacyClaudeSkill, 'SKILL.md'), 'legacy finish\n', 'utf8');
  await mkdir(join(target, '.agents', 'skills', 'custom-local'), { recursive: true });
  await writeFile(customSkill, 'custom content\n', 'utf8');
  if (process.platform !== 'win32') {
    await chmod(customSkill, 0o640);
  }
  const customMode = (await stat(customSkill)).mode & 0o777;

  const activeTask = join(target, '.cowork-flow', 'tasks', 'demo');
  const archivedTask = join(
    target,
    '.cowork-flow',
    'tasks',
    'archive',
    '2026-07',
    'done'
  );
  await mkdir(activeTask, { recursive: true });
  await mkdir(archivedTask, { recursive: true });
  await writeFile(
    join(activeTask, 'implement.jsonl'),
    [
      JSON.stringify({
        file: '.agents/skills/start/SKILL.md',
        reason: 'legacy managed path',
        reference: '.agents/skills/start/SKILL.md'
      }),
      JSON.stringify({
        file: '.agents/skills/custom-local/SKILL.md',
        reason: 'custom path'
      }),
      ''
    ].join('\n'),
    'utf8'
  );
  await writeFile(
    join(archivedTask, 'check.jsonl'),
    `${JSON.stringify({
      file: '.claude/skills/finish-work/SKILL.md',
      reason: 'legacy archived path'
    })}\n`,
    'utf8'
  );
  const activeContextBefore = await readText(
    join(activeTask, 'implement.jsonl')
  );
  const archivedContextBefore = await readText(
    join(archivedTask, 'check.jsonl')
  );

  assert.equal(await main(['sync', target], { io: createIo() }), 0);

  assert.equal(await exists(legacyAgentSkill), true);
  assert.equal(await exists(legacyClaudeSkill), true);
  assert.equal(
    await readText(join(legacyAgentSkill, 'SKILL.md')),
    'legacy start\n'
  );
  assert.equal(
    await readText(join(legacyClaudeSkill, 'SKILL.md')),
    'legacy finish\n'
  );
  assert.equal(await readText(customSkill), 'custom content\n');
  if (process.platform !== 'win32') {
    assert.equal((await stat(customSkill)).mode & 0o777, customMode);
  }
  const activeContext = await readText(join(activeTask, 'implement.jsonl'));
  const archivedContext = await readText(join(archivedTask, 'check.jsonl'));
  assert.equal(activeContext, activeContextBefore);
  assert.equal(archivedContext, archivedContextBefore);

  const secondIo = createIo();
  assert.equal(await main(['sync', target], { io: secondIo }), 0);
  assert.match(secondIo.stdout, /deleted=0/);
  assert.equal(
    await readText(join(activeTask, 'implement.jsonl')),
    activeContext
  );
  assert.equal(
    await readText(join(archivedTask, 'check.jsonl')),
    archivedContext
  );
  assert.equal(await readText(customSkill), 'custom content\n');
});

test('sync overwrites protected files with --force', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io: createIo() }), 0);
  await writeFile(join(target, 'AGENTS.md'), 'custom agents\n', 'utf8');

  const code = await main(['sync', target, '--force'], { io: createIo() });

  assert.equal(code, 0);
  assert.notEqual(await readText(join(target, 'AGENTS.md')), 'custom agents\n');
});

test('sync dry-run does not write safe file updates', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io: createIo() }), 0);
  await writeFile(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md'), 'old skill\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target, '--dry-run'], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')), 'old skill\n');
  assert.match(io.stdout, /dry-run/);
  assert.match(io.stdout, /would-update=/);
});

test('sync rolls back after an injected commit failure', async (t) => {
  const target = await createTempDir(t);
  assert.equal(
    await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io: createIo() }),
    0
  );
  const runner = join(target, '.cowork-flow', 'run');
  const versionFile = join(target, '.cowork-flow', '.version');
  await writeFile(runner, 'old runner\n', 'utf8');
  await writeFile(versionFile, '0.1.0\n', 'utf8');
  const fileSystem = fileSystemWithRenameFailure(
    (source, destination) => source.includes(`${sep}staging${sep}`)
      && destination === versionFile
  );

  await assert.rejects(
    runSync([target], { io: createIo(), fileSystem }),
    /injected commit failure/
  );

  assert.equal(await readText(runner), 'old runner\n');
  assert.equal(await readText(versionFile), '0.1.0\n');
});

test('sync creates missing safe placeholder files', async (t) => {
  const target = await createTempDir(t);
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(join(target, '.cowork-flow', '.version'), '0.1.0\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.cowork-flow', '.version')), `${(await readPackageInfo()).version}\n`);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.opencode')), false);
  assert.equal(await exists(join(target, '.claude')), false);
  assert.equal(await exists(join(target, 'CLAUDE.md')), false);
  assert.match(io.stdout, /created=/);
});

test('sync refreshes codex assets without creating opencode assets', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target, '--developer', 'codex', '--platform', 'codex'], { io: createIo() }), 0);
  await mkdir(join(target, '.codex', 'agents'), { recursive: true });
  await writeFile(join(target, '.codex', 'agents', 'cowork-check.toml'), 'custom: true\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml'), 'old codex adapter\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.codex', 'agents', 'cowork-check.toml')),
    await readText(join(templateRoot, '.codex', 'agents', 'cowork-check.toml'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')),
    await readText(join(templateRoot, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml'))
  );
  assert.equal(await exists(join(target, '.opencode')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), false);
  assert.match(io.stdout, /Platforms: codex/);
  assert.match(io.stdout, /updated=/);
});

test('sync refreshes opencode assets without creating codex assets', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target, '--developer', 'codex', '--platform', 'opencode'], { io: createIo() }), 0);
  await mkdir(join(target, '.opencode', 'agents'), { recursive: true });
  await writeFile(join(target, '.opencode', 'agents', 'cowork-check.md'), 'custom: true\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml'), 'old opencode adapter\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.opencode', 'agents', 'cowork-check.md')),
    await readText(join(templateRoot, '.opencode', 'agents', 'cowork-check.md'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')),
    await readText(join(templateRoot, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml'))
  );
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), false);
  assert.match(io.stdout, /Platforms: opencode/);
  assert.match(io.stdout, /updated=/);
});

test('sync refreshes claude-code assets without creating codex or opencode assets', async (t) => {
  const target = await createTempDir(t);
  assert.equal(await main(['init', target, '--developer', 'codex', '--platform', 'claude'], { io: createIo() }), 0);
  await mkdir(join(target, '.claude', 'agents'), { recursive: true });
  await writeFile(join(target, '.claude', 'agents', 'cowork-check.md'), 'custom: true\n', 'utf8');
  await mkdir(join(target, '.claude', 'skills', 'cowork-flow'), { recursive: true });
  await writeFile(join(target, '.claude', 'skills', 'cowork-flow', 'SKILL.md'), 'old skill\n', 'utf8');
  await writeFile(join(target, '.claude', 'settings.json'), '{"hooks": {}}\n', 'utf8');
  await writeFile(join(target, '.claude', 'hooks', 'inject-workflow-state.py'), 'old claude hook\n', 'utf8');
  await writeFile(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml'), 'old claude adapter\n', 'utf8');
  const customClaude = [
    '# Custom Claude Rules',
    '',
    'Keep this project-specific introduction.',
    '',
    '<!-- COWORK-FLOW:START -->',
    'old managed claude instructions',
    '<!-- COWORK-FLOW:END -->',
    '',
    'Keep this project-specific footer.',
    ''
  ].join('\n');
  await writeFile(join(target, 'CLAUDE.md'), customClaude, 'utf8');
  const templateClaude = await readText(join(templateRoot, 'CLAUDE.md'));
  const templateBlock = templateClaude.match(
    /<!-- COWORK-FLOW:START -->[\s\S]*<!-- COWORK-FLOW:END -->/
  )[0];
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.claude', 'agents', 'cowork-check.md')),
    await readText(join(templateRoot, '.claude', 'agents', 'cowork-check.md'))
  );
  assert.equal(
    await readText(join(target, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml')),
    await readText(join(templateRoot, '.cowork-flow', 'adapters', 'claude-code', 'adapter.yaml'))
  );
  assert.equal(
    await readText(join(target, '.claude', 'skills', 'cowork-flow', 'SKILL.md')),
    await readText(join(templateRoot, 'skills', 'cowork-flow', 'SKILL.md'))
  );
  assert.equal(
    await readText(join(target, '.claude', 'settings.json')),
    await readText(join(templateRoot, '.claude', 'settings.json'))
  );
  assert.equal(
    await readText(join(target, '.claude', 'hooks', 'inject-workflow-state.py')),
    await readText(join(templateRoot, '.claude', 'hooks', 'inject-workflow-state.py'))
  );
  const syncedClaude = await readText(join(target, 'CLAUDE.md'));
  assert.match(syncedClaude, /Keep this project-specific introduction/);
  assert.match(syncedClaude, /Keep this project-specific footer/);
  assert.match(syncedClaude, /@AGENTS\.md/);
  assert.doesNotMatch(syncedClaude, /old managed claude instructions/);
  assert.equal(syncedClaude.match(
    /<!-- COWORK-FLOW:START -->[\s\S]*<!-- COWORK-FLOW:END -->/
  )[0], templateBlock);
  assert.equal(await exists(join(target, '.codex')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.opencode')), false);
  assert.equal(await exists(join(target, '.cowork-flow', 'adapters', 'opencode', 'adapter.yaml')), false);
  assert.equal(await exists(join(target, '.claude', 'skills', 'cowork-flow', 'SKILL.md')), true);
  assert.equal(await exists(join(target, '.agents', 'skills')), false);
  assert.match(io.stdout, /Platforms: claude-code/);
  assert.match(io.stdout, /updated=/);
});

test('sync refreshes all host asset sets when all are installed', async (t) => {
  const target = await createTempDir(t);
  assert.equal(
    await main(['init', target, '--developer', 'codex', '--platform', 'all'], { io: createIo() }),
    0
  );
  await writeFile(join(target, '.codex', 'hooks.json'), 'old codex hooks\n', 'utf8');
  await writeFile(join(target, '.opencode', 'plugins', 'cowork-flow.js'), 'old opencode plugin\n', 'utf8');
  await writeFile(join(target, '.claude', 'commands', 'cowork-check.md'), 'old claude command\n', 'utf8');
  await writeFile(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md'), 'old skill\n', 'utf8');
  await writeFile(join(target, '.claude', 'skills', 'cowork-flow', 'SKILL.md'), 'old skill\n', 'utf8');
  await writeFile(join(target, '.claude', 'settings.json'), '{"hooks": {}}\n', 'utf8');
  await writeFile(join(target, '.claude', 'hooks', 'inject-workflow-state.py'), 'old claude hook\n', 'utf8');
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 0);
  assert.equal(
    await readText(join(target, '.codex', 'hooks.json')),
    await readText(join(templateRoot, '.codex', 'hooks.json'))
  );
  assert.equal(
    await readText(join(target, '.opencode', 'plugins', 'cowork-flow.js')),
    await readText(join(templateRoot, '.opencode', 'plugins', 'cowork-flow.js'))
  );
  assert.equal(
    await readText(join(target, '.claude', 'commands', 'cowork-check.md')),
    await readText(join(templateRoot, '.claude', 'commands', 'cowork-check.md'))
  );
  assert.equal(
    await readText(join(target, '.agents', 'skills', 'cowork-flow', 'SKILL.md')),
    await readText(join(templateRoot, 'skills', 'cowork-flow', 'SKILL.md'))
  );
  assert.equal(
    await readText(join(target, '.claude', 'skills', 'cowork-flow', 'SKILL.md')),
    await readText(join(templateRoot, 'skills', 'cowork-flow', 'SKILL.md'))
  );
  assert.equal(
    await readText(join(target, '.claude', 'settings.json')),
    await readText(join(templateRoot, '.claude', 'settings.json'))
  );
  assert.equal(
    await readText(join(target, '.claude', 'hooks', 'inject-workflow-state.py')),
    await readText(join(templateRoot, '.claude', 'hooks', 'inject-workflow-state.py'))
  );
  assert.match(io.stdout, /Platforms: codex, opencode, claude-code/);
  assert.match(io.stdout, /updated=/);
});
