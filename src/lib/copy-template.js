import { constants } from 'node:fs';
import { access, copyFile, mkdir, readdir, writeFile } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';

import { templateRoot } from './paths.js';

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

async function listFiles(root, current = root) {
  const entries = await readdir(current, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const absolute = join(current, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listFiles(root, absolute));
    } else if (entry.isFile()) {
      files.push(relative(root, absolute));
    }
  }

  return files.sort();
}

export async function buildInitPlan(targetDir, options = {}) {
  const files = await listFiles(templateRoot);
  const actions = [];

  for (const file of files) {
    if (file === '.cowork-flow/.version') {
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
  'AGENTS.md',
  '.cowork-flow/config.yaml',
  '.cowork-flow/workflow.md'
]);

const PROTECTED_SYNC_PREFIXES = [
  '.cowork-flow/spec/',
  '.cowork-flow/workspace/',
  '.cowork-flow/tasks/',
  '.cowork-flow/changes/',
  '.cowork-flow/plans/'
];

const SAFE_SYNC_PREFIXES = [
  '.agent/skills/',
  '.cowork-flow/scripts/'
];

const SAFE_SYNC_FILES = new Set([
  '.cowork-flow/.gitignore',
  '.cowork-flow/.version'
]);

function isProtectedSyncFile(relativePath) {
  return PROTECTED_SYNC_FILES.has(relativePath)
    || PROTECTED_SYNC_PREFIXES.some((prefix) => relativePath.startsWith(prefix));
}

function isSafeSyncFile(relativePath) {
  return SAFE_SYNC_FILES.has(relativePath)
    || SAFE_SYNC_PREFIXES.some((prefix) => relativePath.startsWith(prefix))
    || relativePath.endsWith('/.gitkeep');
}

export async function buildSyncPlan(targetDir, options = {}) {
  if (!await pathExists(join(targetDir, '.cowork-flow'))) {
    throw new Error(`Target is not initialized: ${targetDir}`);
  }

  const files = await listFiles(templateRoot);
  const actions = [];

  for (const file of files) {
    if (file === '.cowork-flow/.version') {
      continue;
    }

    const source = join(templateRoot, file);
    const destination = join(targetDir, file);
    const exists = await pathExists(destination);
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

  actions.push({
    action: 'update',
    source: null,
    destination: join(targetDir, '.cowork-flow', '.version'),
    relativePath: '.cowork-flow/.version',
    content: `${options.version}\n`
  });

  return actions;
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
    }
  }
}
