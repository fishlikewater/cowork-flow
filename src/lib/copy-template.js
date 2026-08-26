import { constants } from 'node:fs';
import { access, readFile, readdir, stat } from 'node:fs/promises';
import { join, relative } from 'node:path';

import { createAssetPlan, planActions } from './asset-plan.js';
import { hostRegistry } from './host-assets.js';
import { applyAssetPlan, inspectAssetTransactions } from './plan-applier.js';
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
    if (entry.name === '__pycache__') {
      continue;
    }
    const absolute = join(current, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listFiles(root, absolute));
    } else if (entry.isFile() && !entry.name.endsWith('.pyc')) {
      files.push(relative(root, absolute));
    }
  }

  return files.sort();
}

function toTemplatePath(relativePath) {
  return relativePath.replaceAll('\\', '/');
}

async function listSkillDirs() {
  const skillsRoot = join(templateRoot, 'skills');
  const entries = await readdir(skillsRoot, { withFileTypes: true });
  const skills = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const skillRoot = join(skillsRoot, entry.name);
    if (await pathExists(join(skillRoot, 'SKILL.md'))) {
      skills.push({ id: entry.name, sourceRoot: skillRoot });
    }
  }
  return skills.sort((left, right) => left.id.localeCompare(right.id));
}

async function listSkillFiles(skill) {
  const sourceRoot = skill.sourceRoot;
  return (await listFiles(sourceRoot)).map((file) => ({
    source: join(sourceRoot, file),
    skillRelativePath: file
  }));
}

async function sourceMatchesDestination(source, destination) {
  try {
    const [sourceContent, targetContent, sourceStats, targetStats] = await Promise.all([
      readFile(source),
      readFile(destination),
      stat(source),
      stat(destination)
    ]);
    return sourceContent.equals(targetContent)
      && (sourceStats.mode & 0o777) === (targetStats.mode & 0o777);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return false;
    }
    throw error;
  }
}

async function appendSkillFileActions(actions, {
  targetDir,
  platforms,
  seen,
  sync = false
}) {
  for (const skill of await listSkillDirs()) {
    const skillFiles = await listSkillFiles(skill);
    for (const platform of platforms) {
      const destBase = hostRegistry.skillDestination(platform);
      if (!destBase) continue;
      for (const skillFile of skillFiles) {
        const destination = join(
          targetDir,
          destBase,
          skill.id,
          skillFile.skillRelativePath
        );
        if (seen.has(destination)) continue;
        seen.add(destination);
        const exists = await pathExists(destination);
        const unchanged = sync && exists
          ? await sourceMatchesDestination(skillFile.source, destination)
          : false;
        actions.push({
          action: exists ? (sync ? (unchanged ? 'skip' : 'update') : 'skip') : 'create',
          source: skillFile.source,
          destination,
          relativePath: join(destBase, skill.id, skillFile.skillRelativePath)
        });
      }
    }
  }
}

async function appendSkillTargetActions(actions, {
  targetDir,
  skillTargets,
  seen,
  sync = false
}) {
  const normalizedTargets = [...new Set(skillTargets.map(toTemplatePath))].sort();
  for (const skill of await listSkillDirs()) {
    const skillFiles = await listSkillFiles(skill);
    for (const destBase of normalizedTargets) {
      for (const skillFile of skillFiles) {
        const destination = join(
          targetDir,
          destBase,
          skill.id,
          skillFile.skillRelativePath
        );
        if (seen.has(destination)) continue;
        seen.add(destination);
        const exists = await pathExists(destination);
        const unchanged = sync && exists
          ? await sourceMatchesDestination(skillFile.source, destination)
          : false;
        actions.push({
          action: exists ? (sync ? (unchanged ? 'skip' : 'update') : 'skip') : 'create',
          source: skillFile.source,
          destination,
          relativePath: join(destBase, skill.id, skillFile.skillRelativePath)
        });
      }
    }
  }
}

function isSourceCheckoutProtected(relativePath) {
  const normalized = toTemplatePath(relativePath);
  if (hostRegistry.syncPolicy.protectedFiles.includes(normalized)) {
    return true;
  }
  return hostRegistry.syncPolicy.protectedPrefixes
    .filter((prefix) => prefix !== '.cowork-flow/spec/')
    .some((prefix) => normalized.startsWith(prefix))
    || normalized.startsWith('.cowork-flow/.runtime/');
}

function shouldIncludeSourceCheckoutRuntimeFile(relativePath) {
  const normalized = toTemplatePath(relativePath);
  return normalized.startsWith('.cowork-flow/')
    && normalized !== '.cowork-flow/.version'
    && !isSourceCheckoutProtected(normalized);
}

function isSourceRefreshObsoleteFile(relativePath) {
  const normalized = toTemplatePath(relativePath);
  if (isSourceCheckoutProtected(normalized)) {
    return false;
  }
  return normalized.startsWith('.cowork-flow/')
    || hostRegistry.skillTargets.some((target) => normalized.startsWith(`${target}/`));
}

export async function buildInitPlan(targetDir, options = {}) {
  const files = await listFiles(templateRoot);
  const actions = [];
  const platforms = options.platforms ?? [];
  const seen = new Set();

  for (const file of files) {
    if (!hostRegistry.shouldInclude(file, platforms)) {
      continue;
    }

    const templatePath = toTemplatePath(file);
    if (templatePath === '.cowork-flow/.version') {
      continue;
    }

    const source = join(templateRoot, file);
    const destination = join(targetDir, file);
    seen.add(destination);
    const exists = await pathExists(destination);
    const action = exists
      ? (options.force && templatePath !== '.cowork-flow/.developer' ? 'update' : 'skip')
      : 'create';
    actions.push({ action, source, destination, relativePath: file });
  }

  await appendSkillFileActions(actions, { targetDir, platforms, seen });

  const versionDestination = join(targetDir, '.cowork-flow', '.version');
  const versionExists = await pathExists(versionDestination);
  actions.push({
    action: versionExists ? (options.force ? 'update' : 'skip') : 'create',
    source: null,
    destination: versionDestination,
    relativePath: '.cowork-flow/.version',
    content: `${options.version}\n`
  });

  const additionalActions = options.additionalActions ?? [];
  const overrides = new Set(
    additionalActions.map((action) => action.destination)
  );
  return createAssetPlan({
    kind: 'init',
    targetDir,
    actions: [
      ...actions.filter((action) => !overrides.has(action.destination)),
      ...additionalActions
    ]
  });
}

const COWORK_FLOW_START = '<!-- COWORK-FLOW:START -->';
const COWORK_FLOW_END = '<!-- COWORK-FLOW:END -->';

function isCoveredByDeletedParent(relativePath, deletedParents) {
  return deletedParents.some((parent) => relativePath.startsWith(`${parent}/`));
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

  if (content === targetContent) {
    return { action: 'skip', source, destination, relativePath };
  }

  return { action: 'update', source, destination, relativePath, content };
}

async function buildFileSyncAction({ source, destination, relativePath }) {
  return {
    action: await sourceMatchesDestination(source, destination) ? 'skip' : 'update',
    source,
    destination,
    relativePath
  };
}

export async function buildSourceCheckoutRefreshPlan(targetDir, options = {}) {
  const files = await listFiles(templateRoot);
  const actions = [];
  const seen = new Set();

  for (const file of files) {
    const templatePath = toTemplatePath(file);
    if (!shouldIncludeSourceCheckoutRuntimeFile(templatePath)) {
      continue;
    }
    const source = join(templateRoot, file);
    const destination = join(targetDir, file);
    seen.add(destination);
    const exists = await pathExists(destination);
    if (!exists) {
      actions.push({ action: 'create', source, destination, relativePath: file });
      continue;
    }
    actions.push(await buildFileSyncAction({
      source,
      destination,
      relativePath: file
    }));
  }

  await appendSkillTargetActions(actions, {
    targetDir,
    skillTargets: options.skillTargets ?? hostRegistry.skillTargets,
    seen,
    sync: true
  });

  const deletedObsoleteParents = [];
  for (const file of hostRegistry.obsoleteSyncFiles()) {
    if (!isSourceRefreshObsoleteFile(file) || isCoveredByDeletedParent(file, deletedObsoleteParents)) {
      continue;
    }
    const destination = join(targetDir, file);
    if (await pathExists(destination)) {
      deletedObsoleteParents.push(file);
      actions.push({ action: 'delete', source: null, destination, relativePath: file });
    }
  }

  const versionDestination = join(targetDir, '.cowork-flow', '.version');
  const versionSource = join(templateRoot, '.cowork-flow', '.version');
  const versionContent = await readFile(versionSource, 'utf8');
  const versionExists = await pathExists(versionDestination);
  const versionUnchanged = versionExists
    && (await readFile(versionDestination, 'utf8')) === versionContent;
  actions.push({
    action: versionExists ? (versionUnchanged ? 'skip' : 'update') : 'create',
    source: null,
    destination: versionDestination,
    relativePath: '.cowork-flow/.version',
    content: versionContent
  });

  return createAssetPlan({
    kind: 'source-refresh',
    targetDir,
    actions
  });
}

export async function buildSyncPlan(targetDir, options = {}) {
  if (!await pathExists(join(targetDir, '.cowork-flow'))) {
    throw new Error(`Target is not initialized: ${targetDir}`);
  }

  const files = await listFiles(templateRoot);
  const actions = [];
  const platforms = options.platforms ?? await detectInstalledPlatforms(targetDir);
  const seen = new Set();

  for (const file of files) {
    if (!hostRegistry.shouldInclude(file, platforms)) {
      continue;
    }

    const destination = join(targetDir, file);
    seen.add(destination);

    if (toTemplatePath(file) === '.cowork-flow/.version') {
      continue;
    }

    const source = join(templateRoot, file);
    const exists = await pathExists(destination);
    if (hostRegistry.isManagedBlockFile(file)) {
      actions.push(await buildManagedBlockSyncAction({ source, destination, exists, options, relativePath: file }));
      continue;
    }

    const protectedFile = hostRegistry.isProtectedSyncFile(file) && !options.force && exists;
    const safeFile = hostRegistry.isSafeSyncFile(file);

    if (protectedFile) {
      actions.push({ action: 'protected', source, destination, relativePath: file });
    } else if (exists && (safeFile || options.force)) {
      actions.push(await buildFileSyncAction({
        source,
        destination,
        relativePath: file
      }));
    } else if (!exists) {
      actions.push({ action: 'create', source, destination, relativePath: file });
    } else {
      actions.push({ action: 'protected', source, destination, relativePath: file });
    }
  }

  await appendSkillFileActions(actions, { targetDir, platforms, seen, sync: true });

  const deletedObsoleteParents = [];
  for (const file of hostRegistry.obsoleteSyncFiles()) {
    if (isCoveredByDeletedParent(file, deletedObsoleteParents)) {
      continue;
    }
    const destination = join(targetDir, file);
    if (await pathExists(destination)) {
      deletedObsoleteParents.push(file);
      actions.push({ action: 'delete', source: null, destination, relativePath: file });
    }
  }

  const versionDestination = join(targetDir, '.cowork-flow', '.version');
  const versionContent = `${options.version}\n`;
  const versionUnchanged = await pathExists(versionDestination)
    && (await readFile(versionDestination, 'utf8')) === versionContent;
  actions.push({
    action: versionUnchanged ? 'skip' : 'update',
    source: null,
    destination: versionDestination,
    relativePath: '.cowork-flow/.version',
    content: versionContent
  });

  return createAssetPlan({
    kind: 'sync',
    targetDir,
    actions
  });
}

export async function detectInstalledPlatforms(targetDir) {
  return hostRegistry.detectInstalledPlatforms(targetDir, pathExists);
}

function normalizeReportPath(value) {
  return String(value).replaceAll('\\', '/');
}

function hostAssetOwners(relativePath) {
  const normalized = normalizeReportPath(relativePath);
  const owners = new Set(hostRegistry.assetOwners(normalized));
  for (const platform of hostRegistry.platforms) {
    const skillTarget = platform.skillTarget ? normalizeReportPath(platform.skillTarget) : null;
    if (skillTarget && normalized.startsWith(`${skillTarget}/`)) {
      owners.add(platform.id);
    }
  }
  return [...owners];
}

function readinessAction(action) {
  const item = { path: action.relativePath, action: action.action };
  const platforms = hostAssetOwners(action.relativePath);
  if (platforms.length > 0) {
    item.platforms = platforms;
  }
  return item;
}

function recoveryWarning(transaction) {
  if (transaction.error) {
    return `pending recovery metadata unreadable at ${transaction.path}: ${transaction.error}`;
  }
  if (transaction.status === 'committed') {
    return `stale committed transaction cleanup pending at ${transaction.path}`;
  }
  return `pending ${transaction.status} transaction recovery at ${transaction.path}`;
}

export async function buildReadinessReport(plan, options = {}) {
  const actions = planActions(plan);
  const pendingRecovery = await inspectAssetTransactions(plan.targetDir, {
    fileSystem: options.fileSystem
  });
  return {
    wouldCopy: actions
      .filter((action) => action.action === 'create' || action.action === 'update')
      .map(readinessAction),
    wouldSkipProtected: actions
      .filter((action) => action.action === 'protected')
      .map(readinessAction),
    wouldRemoveObsolete: actions
      .filter((action) => action.action === 'delete')
      .map(readinessAction),
    hostAssetRefresh: actions
      .filter((action) => action.action !== 'skip' && hostAssetOwners(action.relativePath).length > 0)
      .map(readinessAction),
    pendingRecovery,
    warnings: pendingRecovery.map(recoveryWarning)
  };
}

export function formatReadinessReport(report) {
  return `readiness=${JSON.stringify(report)}\n`;
}

export function summarizePlan(plan, dryRun = false) {
  const actions = planActions(plan);
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

export async function applyPlan(plan, options = {}) {
  await applyAssetPlan(plan, options);
}
