import { constants } from 'node:fs';
import { access, chmod, copyFile, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
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

function toTemplatePath(relativePath) {
  return relativePath.replaceAll('\\', '/');
}

export async function buildInitPlan(targetDir, options = {}) {
  const files = await listFiles(templateRoot);
  const actions = [];

  for (const file of files) {
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
  '.codex/',
  '.agent/skills/',
  '.cowork-flow/'
];

const SAFE_SYNC_FILES = new Set([
  '.cowork-flow/.gitignore',
  '.cowork-flow/.version',
  '.cowork-flow/run',
  '.cowork-flow/run.cmd'
]);

const COWORK_FLOW_START = '<!-- COWORK-FLOW:START -->';
const COWORK_FLOW_END = '<!-- COWORK-FLOW:END -->';

function isProtectedSyncFile(relativePath) {
  const templatePath = toTemplatePath(relativePath);
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

async function buildAgentsSyncAction({ source, destination, exists, options }) {
  if (!exists || options.force) {
    return {
      action: exists ? 'update' : 'create',
      source,
      destination,
      relativePath: 'AGENTS.md'
    };
  }

  const [templateContent, targetContent] = await Promise.all([
    readFile(source, 'utf8'),
    readFile(destination, 'utf8')
  ]);
  const content = replaceManagedBlock(targetContent, templateContent);

  if (content === null) {
    return { action: 'protected', source, destination, relativePath: 'AGENTS.md' };
  }

  return { action: 'update', source, destination, relativePath: 'AGENTS.md', content };
}

export async function buildSyncPlan(targetDir, options = {}) {
  if (!await pathExists(join(targetDir, '.cowork-flow'))) {
    throw new Error(`Target is not initialized: ${targetDir}`);
  }

  const files = await listFiles(templateRoot);
  const actions = [];

  for (const file of files) {
    if (toTemplatePath(file) === '.cowork-flow/.version') {
      continue;
    }

    const source = join(templateRoot, file);
    const destination = join(targetDir, file);
    const exists = await pathExists(destination);
    if (file === 'AGENTS.md') {
      actions.push(await buildAgentsSyncAction({ source, destination, exists, options }));
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
      const sourceStats = await stat(item.source);
      await chmod(item.destination, sourceStats.mode & 0o777);
    }
  }
}
