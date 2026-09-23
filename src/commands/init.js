import { access, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

import {
  applyPlan,
  buildInitPlan,
  summarizePlan
} from '../lib/copy-template.js';
import { readPackageInfo } from '../lib/package-info.js';
import {
  SUPPORTED_PLATFORMS,
  formatPlatformList,
  parsePlatformSelection,
  platformLabel
} from '../lib/platforms.js';
import { parseFlags, UsageError } from '../lib/cli-flags.js';

// Host selection is validated in the manifest layer, which reports a plain
// Error. Re-thrown as a usage error here so "you named a host that does not
// exist" exits with the same code as every other argv mistake.
function parsePlatformSelectionOrUsage(values) {
  try {
    return parsePlatformSelection(values);
  } catch (error) {
    throw new UsageError(error instanceof Error ? error.message : String(error));
  }
}

function parseInitArgs(args) {
  const { flags, positionals } = parseFlags(args, {
    boolean: ['--dry-run', '--force'],
    value: ['--platform', '--platforms', '--developer'],
    repeatable: ['--platform', '--platforms'],
    positional: { min: 0, max: 1, name: '[target]' }
  });
  return {
    developer: flags['--developer'] ?? null,
    dryRun: Boolean(flags['--dry-run']),
    force: Boolean(flags['--force']),
    platforms: [...(flags['--platform'] ?? []), ...(flags['--platforms'] ?? [])],
    target: positionals[0] === undefined ? process.cwd() : resolve(positionals[0])
  };
}

async function pathExists(path) {
  try {
    await access(path);
    return true;
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return false;
    }
    throw error;
  }
}

function normalizeDeveloperName(value) {
  const name = String(value ?? '').trim();
  if (!name) {
    throw new UsageError('Developer name required. Run: cwf project init <target> --developer <name>');
  }
  if (/[\\/]/.test(name)) {
    throw new UsageError('Developer name must not contain path separators');
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

async function resolvePlatforms(options, selectPlatforms) {
  if (options.platforms.length > 0) {
    return parsePlatformSelectionOrUsage(options.platforms);
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
  return parsePlatformSelectionOrUsage(selected);
}


async function buildDeveloperActions(target, developer) {
  const workflowDir = join(target, '.cowork-flow');
  const developerFile = join(workflowDir, '.developer');
  const actions = [];

  if (!developer.existing) {
    actions.push({
      action: 'create',
      source: null,
      destination: developerFile,
      relativePath: '.cowork-flow/.developer',
      content: `name=${developer.name}\ninitialized_at=${new Date().toISOString()}\n`,
      targetExists: false
    });
  }

  return actions;
}

export async function runInit(args, { io, prompt, selectPlatforms }) {
  return runInitWithOptions(args, { io, prompt, selectPlatforms });
}

export async function runInitWithOptions(
  args,
  { io, prompt, selectPlatforms, fileSystem }
) {
  const options = parseInitArgs(args);
  const platforms = await resolvePlatforms(options, selectPlatforms);
  const developer = await resolveDeveloperName(options, prompt);
  const packageInfo = await readPackageInfo();
  const developerActions = developer.name
    ? await buildDeveloperActions(options.target, developer)
    : [];
  const plan = await buildInitPlan(options.target, {
    additionalActions: developerActions,
    force: options.force,
    platforms,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun, fileSystem });
  io.writeOut(summarizePlan(plan, options.dryRun));
  io.writeOut(`Platforms: ${formatPlatformList(platforms)}\n`);

  if (options.dryRun) {
    if (developer.existing) {
      io.writeOut(`dry-run preserve-existing=.cowork-flow/.developer for developer ${developer.name}\n`);
    } else if (developer.name) {
      io.writeOut(`dry-run would-create=.cowork-flow/.developer for developer ${developer.name}\n`);
    }
    io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
    return 0;
  }

  if (developer.existing) {
    io.writeOut(`Developer already initialized: ${developer.name}\n`);
  } else {
    io.writeOut(`Developer initialized: ${developer.name}\n`);
  }
  io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
  return 0;
}
