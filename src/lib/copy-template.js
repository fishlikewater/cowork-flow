import { constants } from 'node:fs';
import { access, chmod, copyFile, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';

import { templateRoot } from './paths.js';
import { shouldIncludeForPlatforms, skillDestinationForPlatform } from './platforms.js';

async function pathExists(path) {
  try {
    await access(path, constants.F_OK);
    return true;
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return false;
    }
    throw error;
  }
}

function toTemplatePath(relativePath) {
  return relativePath.replaceAll('\\', '/');
}

function shouldSkipTemplatePath(relativePath) {
  const templatePath = toTemplatePath(relativePath);
  return (
    templatePath === '.cowork-flow/.runtime'
    || templatePath.startsWith('.cowork-flow/.runtime/')
    || templatePath === 'skills'
    || templatePath.startsWith('skills/')
  );
}

async function listFiles(root, current = root) {
  const entries = await readdir(current, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const absolute = join(current, entry.name);
    const relativePath = relative(root, absolute);
    if (shouldSkipTemplatePath(relativePath)) {
      continue;
    }
    if (entry.isDirectory()) {
      files.push(...await listFiles(root, absolute));
    } else if (entry.isFile()) {
      files.push(relativePath);
    }
  }

  return files.sort();
}

export async function buildInitPlan(targetDir, options = {}) {
  const files = await listFiles(templateRoot);
  const actions = [];
  const platforms = options.platforms ?? [];

  for (const file of files) {
    if (!shouldIncludeForPlatforms(file, platforms)) {
      continue;
    }

    if (toTemplatePath(file) === '.cowork-flow/.version') {
      continue;
    }

    const source = join(templateRoot, file);
    const destination = join(targetDir, file);
    const exists = await pathExists(destination);
    const action = exists ? (options.force ? 'update' : 'skip') : 'create';
    actions.push({ action, source, destination, relativePath: file });
  }

  const versionDestination = join(targetDir, '.cowork-flow', '.version');
  const versionExists = await pathExists(versionDestination);
  actions.push({
    action: versionExists ? (options.force ? 'update' : 'skip') : 'create',
    source: null,
    destination: versionDestination,
    relativePath: '.cowork-flow/.version',
    content: `${options.version}\n`
  });

  return actions;
}

const PROTECTED_SYNC_FILES = new Set([
  '.cowork-flow/config.yaml'
]);

const PROTECTED_SYNC_PREFIXES = [
  '.cowork-flow/spec/',
  '.cowork-flow/workspace/',
  '.cowork-flow/tasks/',
  '.cowork-flow/changes/',
  '.cowork-flow/plans/'
];

const SAFE_SYNC_PREFIXES = [
  '.agents/',
  '.codex/',
  '.opencode/',
  '.claude/',
  '.cowork-flow/'
];

const SAFE_SYNC_FILES = new Set([
  '.cowork-flow/.gitignore',
  '.cowork-flow/.version',
  '.cowork-flow/run',
  '.cowork-flow/run.cmd',
  '.cowork-flow/spec/core/state-templates.md'
]);

const COWORK_FLOW_START = '<!-- COWORK-FLOW:START -->';
const COWORK_FLOW_END = '<!-- COWORK-FLOW:END -->';

function isProtectedSyncFile(relativePath) {
  const templatePath = toTemplatePath(relativePath);
  if (SAFE_SYNC_FILES.has(templatePath)) {
    return false;
  }
  return PROTECTED_SYNC_FILES.has(templatePath)
    || PROTECTED_SYNC_PREFIXES.some((prefix) => templatePath.startsWith(prefix));
}

function isSafeSyncFile(relativePath) {
  const templatePath = toTemplatePath(relativePath);
  return SAFE_SYNC_FILES.has(templatePath)
    || SAFE_SYNC_PREFIXES.some((prefix) => templatePath.startsWith(prefix))
    || templatePath.endsWith('/.gitkeep');
}

function replaceManagedBlock(targetContent, templateContent) {
  const targetStart = targetContent.indexOf(COWORK_FLOW_START);
  const targetEnd = targetContent.indexOf(COWORK_FLOW_END, targetStart + COWORK_FLOW_START.length);
  const templateStart = templateContent.indexOf(COWORK_FLOW_START);
  const templateEnd = templateContent.indexOf(COWORK_FLOW_END, templateStart + COWORK_FLOW_START.length);

  if (targetStart === -1 || targetEnd === -1 || templateStart === -1 || templateEnd === -1) {
    return null;
  }

  const targetBlockEnd = targetEnd + COWORK_FLOW_END.length;
  const templateBlockEnd = templateEnd + COWORK_FLOW_END.length;
  return [
    targetContent.slice(0, targetStart),
    templateContent.slice(templateStart, templateBlockEnd),
    targetContent.slice(targetBlockEnd)
  ].join('');
}

async function buildManagedBlockSyncAction({ source, destination, exists, options, relativePath }) {
  if (!exists || options.force) {
    return {
      action: exists ? 'update' : 'create',
      source,
      destination,
      relativePath
    };
  }

  const [templateContent, targetContent] = await Promise.all([
    readFile(source, 'utf8'),
    readFile(destination, 'utf8')
  ]);
  const content = replaceManagedBlock(targetContent, templateContent);

  if (content === null) {
    return { action: 'protected', source, destination, relativePath };
  }

  return { action: 'update', source, destination, relativePath, content };
}

export async function buildSyncPlan(targetDir, options = {}) {
  if (!await pathExists(join(targetDir, '.cowork-flow'))) {
    throw new Error(`Target is not initialized: ${targetDir}`);
  }

  const files = await listFiles(templateRoot);
  const actions = [];
  const platforms = options.platforms ?? await detectInstalledPlatforms(targetDir);

  for (const file of files) {
    if (!shouldIncludeForPlatforms(file, platforms)) {
      continue;
    }

    if (toTemplatePath(file) === '.cowork-flow/.version') {
      continue;
    }

    const source = join(templateRoot, file);
    const destination = join(targetDir, file);
    const exists = await pathExists(destination);
    if (file === 'AGENTS.md' || file === 'CLAUDE.md') {
      actions.push(await buildManagedBlockSyncAction({ source, destination, exists, options, relativePath: file }));
      continue;
    }

    const protectedFile = isProtectedSyncFile(file) && !options.force && exists;
    const safeFile = isSafeSyncFile(file);

    if (protectedFile) {
      actions.push({ action: 'protected', source, destination, relativePath: file });
    } else if (exists && (safeFile || options.force)) {
      actions.push({ action: 'update', source, destination, relativePath: file });
    } else if (!exists) {
      actions.push({ action: 'create', source, destination, relativePath: file });
    } else {
      actions.push({ action: 'protected', source, destination, relativePath: file });
    }
  }

  // Inject per-platform skills directories from the canonical template/skills/.
  const skillsSrc = join(templateRoot, 'skills');
  if (await pathExists(skillsSrc)) {
    const skillEntries = await readdir(skillsSrc, { withFileTypes: true });
    const seen = new Set(actions.map((a) => a.destination));
    for (const entry of skillEntries) {
      if (!entry.isDirectory()) continue;
      const skillName = entry.name;
      const skillSource = join(skillsSrc, skillName, 'SKILL.md');
      if (!(await pathExists(skillSource))) continue;
      for (const platform of platforms) {
        const destBase = skillDestinationForPlatform(platform);
        if (!destBase) continue;
        const dest = join(targetDir, destBase, skillName, 'SKILL.md');
        if (seen.has(dest)) continue;
        seen.add(dest);
        const exists = await pathExists(dest);
        actions.push({
          action: exists ? 'update' : 'create',
          source: skillSource,
          destination: dest,
          relativePath: join(destBase, skillName, 'SKILL.md')
        });
      }
    }
  }

  actions.push({
    action: 'update',
    source: null,
    destination: join(targetDir, '.cowork-flow', '.version'),
    relativePath: '.cowork-flow/.version',
    content: `${options.version}\n`
  });

  return actions;
}

export async function detectInstalledPlatforms(targetDir) {
  const platforms = [];
  if (await pathExists(join(targetDir, '.codex'))) {
    platforms.push('codex');
  }
  if (await pathExists(join(targetDir, '.opencode'))) {
    platforms.push('opencode');
  }
  if (await pathExists(join(targetDir, '.claude')) || await pathExists(join(targetDir, 'CLAUDE.md'))) {
    platforms.push('claude-code');
  }
  return platforms;
}

export function summarizePlan(actions, dryRun = false) {
  const counts = { create: 0, update: 0, skip: 0, protected: 0 };
  for (const action of actions) {
    counts[action.action] += 1;
  }

  const prefix = dryRun ? 'dry-run ' : '';
  const createLabel = dryRun ? 'would-create' : 'created';
  const updateLabel = dryRun ? 'would-update' : 'updated';
  return `${prefix}${createLabel}=${counts.create} ${updateLabel}=${counts.update} skipped=${counts.skip} protected=${counts.protected}\n`;
}

export async function applyPlan(actions, options = {}) {
  if (options.dryRun) {
    return;
  }

  for (const item of actions) {
    if (item.action === 'skip' || item.action === 'protected') {
      continue;
    }

    await mkdir(dirname(item.destination), { recursive: true });
    if (item.content !== undefined) {
      await writeFile(item.destination, item.content, 'utf8');
    } else {
      await copyFile(item.source, item.destination);
      const sourceStats = await stat(item.source);
      await chmod(item.destination, sourceStats.mode & 0o777);
    }
  }
}
