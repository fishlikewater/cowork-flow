import { execFile } from 'node:child_process';
import { access, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';

import {
  applyPlan,
  buildInitPlan,
  detectInstalledPlatforms,
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
import {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  normalizeLanguage,
  readProjectLanguage,
  withLanguage
} from '../lib/language.js';
import { templateRoot } from '../lib/paths.js';

const execFileAsync = promisify(execFile);

// The manifest layer reports a plain Error; re-thrown as a
// usage error so a bad host name exits with the
// argv-mistake code.
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
    value: ['--host', '--platform', '--platforms', '--developer', '--language'],
    repeatable: ['--host', '--platform', '--platforms'],
    positional: { min: 0, max: 1, name: '[target]' }
  });
  return {
    developer: flags['--developer'] ?? null,
    dryRun: Boolean(flags['--dry-run']),
    force: Boolean(flags['--force']),
    language: flags['--language'] ?? null,
    platforms: [
      ...(flags['--host'] ?? []),
      ...(flags['--platform'] ?? []),
      ...(flags['--platforms'] ?? [])
    ],
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
    throw new UsageError('Developer name required. Run: cwf project init [target] --developer <name>');
  }
  if (/[\\/]/.test(name)) {
    throw new UsageError('Developer name must not contain path separators');
  }
  return name;
}

function normalizeGitDeveloper(value) {
  const name = String(value ?? '').trim();
  if (!name || /[\\/]/.test(name) || (name.startsWith('<') && name.endsWith('>'))) {
    return null;
  }
  return name;
}

// `git config user.name` reads the local repository first and falls back to the
// global config, which is the "nearest identity" this command wants. A missing
// binary, an unset value, or a directory that vanishes under us all mean "no
// git identity", never a failed init.
async function readGitDeveloper(target) {
  const cwd = await pathExists(target) ? target : process.cwd();
  try {
    const { stdout } = await execFileAsync('git', ['config', 'user.name'], {
      cwd,
      timeout: 5000,
      windowsHide: true
    });
    return normalizeGitDeveloper(stdout);
  } catch {
    return null;
  }
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
    return { existing: true, name: existing, source: 'existing' };
  }

  if (options.developer) {
    return { existing: false, name: normalizeDeveloperName(options.developer), source: 'flag' };
  }

  const gitName = await readGitDeveloper(options.target);

  if (options.dryRun) {
    return { existing: false, name: gitName, source: gitName ? 'git' : null };
  }

  if (typeof prompt === 'function') {
    const answer = await prompt(`Developer name${gitName ? ` [${gitName}]` : ''}: `);
    const typed = String(answer ?? '').trim();
    return {
      existing: false,
      name: normalizeDeveloperName(typed || gitName),
      source: typed ? 'prompt' : 'git'
    };
  }

  return { existing: false, name: normalizeDeveloperName(gitName), source: 'git' };
}

async function resolvePlatforms(options, selectPlatforms) {
  if (options.platforms.length > 0) {
    return parsePlatformSelectionOrUsage(options.platforms);
  }

  // Reuse the same marker-based detection `project sync` uses, so init and sync
  // agree on what "this project already uses" means.
  const detected = await detectInstalledPlatforms(options.target);
  if (detected.length > 0) {
    return detected;
  }

  let selected = null;
  if (typeof selectPlatforms === 'function') {
    selected = await selectPlatforms({
      message: 'Select hosts to set up',
      choices: SUPPORTED_PLATFORMS.map((platform) => ({
        label: platformLabel(platform),
        value: platform
      })),
      defaultSelected: ['codex']
    });
  }
  return parsePlatformSelectionOrUsage(selected);
}

function normalizeLanguageOrUsage(value) {
  const language = normalizeLanguage(value);
  if (!language) {
    throw new UsageError(
      `Unsupported language: ${value}. Supported: ${SUPPORTED_LANGUAGES.join(', ')}`
    );
  }
  return language;
}

// An existing config is authoritative: the choice is never re-prompted or
// rewritten, even by --force. A missing config prompts once, with zh-CN as the
// default for both non-interactive and dry-run runs.
async function resolveLanguage(options, prompt) {
  const requested = options.language
    ? normalizeLanguageOrUsage(options.language)
    : null;
  const existing = await readProjectLanguage(options.target);
  if (existing.present) {
    return {
      existing: true,
      language: existing.language,
      valid: existing.valid,
      raw: existing.raw,
      requested,
      source: 'existing'
    };
  }

  if (requested) {
    return {
      existing: false,
      language: requested,
      requested,
      source: 'flag'
    };
  }

  if (options.dryRun || typeof prompt !== 'function') {
    return {
      existing: false,
      language: DEFAULT_LANGUAGE,
      requested,
      source: 'default'
    };
  }

  const answer = String(
    await prompt(`Project language (${SUPPORTED_LANGUAGES.join('/')}) [${DEFAULT_LANGUAGE}]: `) ?? ''
  ).trim();
  return {
    existing: false,
    language: normalizeLanguageOrUsage(answer || DEFAULT_LANGUAGE),
    requested,
    source: answer ? 'prompt' : 'default'
  };
}

function emitLanguageWarnings(io, language) {
  if (!language.existing) {
    return;
  }
  if (!language.valid) {
    io.writeErr(
      `Warning: unsupported language ${JSON.stringify(language.raw)} in .cowork-flow/config.yaml; using ${language.language}. Edit the file to change it.\n`
    );
    return;
  }
  if (language.requested && language.requested !== language.language) {
    io.writeErr(
      `Warning: existing .cowork-flow/config.yaml language ${language.language} wins over --language ${language.requested}.\n`
    );
  }
}

async function buildConfigActions(target, language, existing) {
  if (existing) {
    return [];
  }
  const source = join(templateRoot, '.cowork-flow', 'config.yaml');
  const content = withLanguage(await readFile(source, 'utf8'), language);
  return [{
    action: 'create',
    source,
    destination: join(target, '.cowork-flow', 'config.yaml'),
    relativePath: '.cowork-flow/config.yaml',
    content,
    targetExists: false
  }];
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
  const language = await resolveLanguage(options, prompt);
  emitLanguageWarnings(io, language);
  const developer = await resolveDeveloperName(options, prompt);
  const packageInfo = await readPackageInfo();
  const developerActions = developer.name
    ? await buildDeveloperActions(options.target, developer)
    : [];
  const configActions = await buildConfigActions(
    options.target,
    language.language,
    language.existing
  );
  const plan = await buildInitPlan(options.target, {
    additionalActions: [...developerActions, ...configActions],
    force: options.force,
    language: language.language,
    platforms,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun, fileSystem });
  io.writeOut(summarizePlan(plan, options.dryRun));
  io.writeOut(`Hosts: ${formatPlatformList(platforms)}\n`);

  if (options.dryRun) {
    if (developer.existing) {
      io.writeOut(`dry-run preserve-existing=.cowork-flow/.developer for developer ${developer.name}\n`);
    } else if (developer.name) {
      const source = developer.source === 'git' ? ' (from git user.name)' : '';
      io.writeOut(`dry-run would-create=.cowork-flow/.developer for developer ${developer.name}${source}\n`);
    } else {
      io.writeOut('dry-run would-skip=.cowork-flow/.developer (no developer identity; pass --developer)\n');
    }
    if (language.existing) {
      io.writeOut(`dry-run preserve-existing=.cowork-flow/config.yaml for language ${language.language}\n`);
    } else {
      io.writeOut(`dry-run would-create=.cowork-flow/config.yaml for language ${language.language}\n`);
    }
    io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
    return 0;
  }

  if (developer.existing) {
    io.writeOut(`Developer already initialized: ${developer.name}\n`);
  } else {
    const source = developer.source === 'git' ? ' (from git user.name)' : '';
    io.writeOut(`Developer initialized: ${developer.name}${source}\n`);
  }
  if (language.existing) {
    io.writeOut(`Language already initialized: ${language.language}\n`);
  } else {
    const source = language.source === 'default' ? ' (default)' : '';
    io.writeOut(`Language initialized: ${language.language}${source}\n`);
  }
  io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
  return 0;
}
