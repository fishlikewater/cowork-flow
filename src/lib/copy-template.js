import { constants } from 'node:fs';
import { access, chmod, copyFile, mkdir, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';

import { templateRoot } from './paths.js';
import { shouldIncludeForPlatforms } from './platforms.js';

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
  '.codex/',
  '.opencode/',
  '.claude/',
  '.agents/skills/',
  '.cowork-flow/'
];

const SAFE_SYNC_FILES = new Set([
  '.cowork-flow/.gitignore',
  '.cowork-flow/.version',
  '.cowork-flow/run',
  '.cowork-flow/run.cmd',
  '.cowork-flow/spec/contracts/workflow-state-templates.md'
]);

const OBSOLETE_SYNC_FILES = new Set([
  '.cowork-flow/project-context.md',
  '.cowork-flow/scripts/add_session.py',
  '.cowork-flow/scripts/change.py',
  '.cowork-flow/scripts/doctor.py',
  '.cowork-flow/scripts/get_context.py',
  '.cowork-flow/scripts/get_developer.py',
  '.cowork-flow/scripts/init_developer.py',
  '.cowork-flow/scripts/party_mode_v2.py',
  '.cowork-flow/scripts/project_context.py',
  '.cowork-flow/scripts/resume.py',
  '.cowork-flow/scripts/subagent.py',
  '.cowork-flow/scripts/task.py',
  '.cowork-flow/scripts/common/active_task.py',
  '.cowork-flow/scripts/common/archive_utils.py',
  '.cowork-flow/scripts/common/coding_standards.py',
  '.cowork-flow/scripts/common/config.py',
  '.cowork-flow/scripts/common/developer.py',
  '.cowork-flow/scripts/common/execution_context.py',
  '.cowork-flow/scripts/common/files.py',
  '.cowork-flow/scripts/common/gates.py',
  '.cowork-flow/scripts/common/git_context.py',
  '.cowork-flow/scripts/common/git_snapshot.py',
  '.cowork-flow/scripts/common/paths.py',
  '.cowork-flow/scripts/common/readiness.py',
  '.cowork-flow/scripts/common/state_machine.py',
  '.cowork-flow/scripts/common/task_utils.py',
  '.cowork-flow/scripts/common/tdd_evidence.py',
  '.cowork-flow/scripts/common/test_intent.py',
  '.cowork-flow/scripts/common/validate_coding_standards.py',
  '.cowork-flow/scripts/common/validate_implementation.py',
  '.cowork-flow/scripts/common/validate_rules.py',
  '.cowork-flow/spec/contracts/entry-contract.md'
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

  for (const file of OBSOLETE_SYNC_FILES) {
    const destination = join(targetDir, file);
    if (await pathExists(destination)) {
      actions.push({ action: 'delete', source: null, destination, relativePath: file });
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
  const counts = { create: 0, update: 0, skip: 0, protected: 0, delete: 0 };
  for (const action of actions) {
    counts[action.action] += 1;
  }

  const prefix = dryRun ? 'dry-run ' : '';
  const createLabel = dryRun ? 'would-create' : 'created';
  const updateLabel = dryRun ? 'would-update' : 'updated';
  const deleteLabel = dryRun ? 'would-delete' : 'deleted';
  return `${prefix}${createLabel}=${counts.create} ${updateLabel}=${counts.update} ${deleteLabel}=${counts.delete} skipped=${counts.skip} protected=${counts.protected}\n`;
}

export async function applyPlan(actions, options = {}) {
  if (options.dryRun) {
    return;
  }

  for (const item of actions) {
    if (item.action === 'skip' || item.action === 'protected') {
      continue;
    }
    if (item.action === 'delete') {
      await rm(item.destination, { force: true });
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
