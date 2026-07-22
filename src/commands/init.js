import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

import {
  applyPlan,
  buildInitPlan,
  summarizePlan
} from '../lib/copy-template.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pathExists } from '../lib/fs-utils.js';
import {
  SUPPORTED_PLATFORMS,
  formatPlatformList,
  parsePlatformSelection
} from '../lib/platforms.js';

function parseInitArgs(args) {
  const options = {
    developer: null,
    dryRun: false,
    force: false,
    platforms: [],
    target: process.cwd()
  };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--force') {
      options.force = true;
    } else if (arg === '--platform' || arg === '--platforms') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('Missing value for --platform');
      }
      options.platforms.push(value);
      index += 1;
    } else if (arg.startsWith('--platform=')) {
      options.platforms.push(arg.slice('--platform='.length));
    } else if (arg.startsWith('--platforms=')) {
      options.platforms.push(arg.slice('--platforms='.length));
    } else if (arg === '--developer') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('Missing value for --developer');
      }
      options.developer = value;
      index += 1;
    } else if (arg.startsWith('--developer=')) {
      options.developer = arg.slice('--developer='.length);
    } else if (arg.startsWith('--')) {
      throw new Error(`Unknown init option: ${arg}`);
    } else {
      options.target = resolve(arg);
    }
  }
  return options;
}

function normalizeDeveloperName(value) {
  const name = String(value ?? '').trim();
  if (!name) {
    throw new Error('Developer name required. Run: cowork-flow init <target> --developer <name>');
  }
  if (/[\\/]/.test(name)) {
    throw new Error('Developer name must not contain path separators');
  }
  return name;
}

async function readExistingDeveloper(target) {
  const developerFile = join(target, '.cowork-flow', '.developer');
  if (!await pathExists(developerFile)) {
    return null;
  }
  const content = await readFile(developerFile, 'utf8');
  const match = content.match(/^name=(.+)$/m);
  return match ? match[1].trim() : null;
}

async function resolveDeveloperName(options, prompt) {
  const existing = await readExistingDeveloper(options.target);
  if (existing) {
    return { existing: true, name: existing };
  }

  if (options.dryRun && !options.developer) {
    return { existing: false, name: null };
  }

  let name = options.developer;
  if (!name && typeof prompt === 'function') {
    name = await prompt('Developer name: ');
  }

  return { existing: false, name: normalizeDeveloperName(name) };
}

function platformLabel(platform) {
  if (platform === 'codex') {
    return 'Codex';
  }
  if (platform === 'opencode') {
    return 'OpenCode';
  }
  if (platform === 'claude-code') {
    return 'Claude Code';
  }
  return platform;
}

async function resolvePlatforms(options, selectPlatforms) {
  if (options.platforms.length > 0) {
    return parsePlatformSelection(options.platforms);
  }

  let selected = null;
  if (typeof selectPlatforms === 'function') {
    selected = await selectPlatforms({
      message: 'Select platforms to set up',
      choices: SUPPORTED_PLATFORMS.map((platform) => ({
        label: platformLabel(platform),
        value: platform
      })),
      defaultSelected: ['codex']
    });
  }
  return parsePlatformSelection(selected);
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function initialJournalContent(name) {
  return `# Development Journal - ${name} (Part 1)

> AI development session journal
> Start date: ${todayIsoDate()}

---

`;
}

function initialIndexContent(name) {
  return `# Workspace Index - ${name}

> Tracks AI development session records.

---

## Current Status

<!-- @@@auto:current-status -->
- **Current file**: \`journal-1.md\`
- **Total Sessions**: 0
- **Last Active**: -
<!-- @@@/auto:current-status -->

---

## Active Documents

<!-- @@@auto:active-documents -->
| File | Lines | Status |
|------|------|------|
| \`journal-1.md\` | ~0 | Current |
<!-- @@@/auto:active-documents -->

---

## Session History

<!-- @@@auto:session-history -->
| # | Date | Title | Commit |
|---|------|------|------|
<!-- @@@/auto:session-history -->

---

## Notes

- Sessions are appended to the journal file
- A new journal file is created automatically after the current file exceeds 2000 lines
- Use \`add_session.py\` to record sessions
- New records use English text; legacy records can remain as they are
`;
}

async function initializeDeveloper(target, developer) {
  const workflowDir = join(target, '.cowork-flow');
  const developerFile = join(workflowDir, '.developer');
  const workspaceDir = join(workflowDir, 'workspace', developer.name);
  const journalFile = join(workspaceDir, 'journal-1.md');
  const indexFile = join(workspaceDir, 'index.md');

  await mkdir(workflowDir, { recursive: true });
  if (!developer.existing) {
    await writeFile(
      developerFile,
      `name=${developer.name}\ninitialized_at=${new Date().toISOString()}\n`,
      'utf8'
    );
  }

  await mkdir(workspaceDir, { recursive: true });
  if (!await pathExists(journalFile)) {
    await writeFile(journalFile, initialJournalContent(developer.name), 'utf8');
  }
  if (!await pathExists(indexFile)) {
    await writeFile(indexFile, initialIndexContent(developer.name), 'utf8');
  }
}

export async function runInit(args, { io, prompt, selectPlatforms }) {
  return runInitWithOptions(args, { io, prompt, selectPlatforms });
}

export async function runInitWithOptions(args, { io, prompt, selectPlatforms }) {
  const options = parseInitArgs(args);
  const platforms = await resolvePlatforms(options, selectPlatforms);
  const developer = await resolveDeveloperName(options, prompt);
  const packageInfo = await readPackageInfo();
  const plan = await buildInitPlan(options.target, {
    force: options.force,
    platforms,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun });
  io.writeOut(summarizePlan(plan, options.dryRun));
  io.writeOut(`Platforms: ${formatPlatformList(platforms)}\n`);

  if (options.dryRun) {
    if (developer.existing) {
      io.writeOut(`dry-run preserve-existing=.cowork-flow/.developer for developer ${developer.name}\n`);
    } else if (developer.name) {
      io.writeOut(`dry-run would-create=.cowork-flow/.developer for developer ${developer.name}\n`);
      io.writeOut(`dry-run would-create=.cowork-flow/workspace/${developer.name}/\n`);
    }
    io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
    return 0;
  }

  await initializeDeveloper(options.target, developer);
  if (developer.existing) {
    io.writeOut(`Developer already initialized: ${developer.name}\n`);
  } else {
    io.writeOut(`Developer initialized: ${developer.name}\n`);
  }
  io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
  return 0;
}
