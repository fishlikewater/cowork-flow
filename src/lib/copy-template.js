import { constants } from 'node:fs';
import { access, readFile, readdir } from 'node:fs/promises';
import { join, relative } from 'node:path';

import { createAssetPlan, planActions } from './asset-plan.js';
import { hostRegistry } from './host-assets.js';
import { applyAssetPlan } from './plan-applier.js';
import { templateRoot } from './paths.js';
import { shouldIncludeForPlatforms, skillDestinationForPlatform } from './platforms.js';
import { skillRegistry } from './skill-registry.js';

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

function managedPathParent(managedPath) {
  const withoutTrailingSlash = managedPath.slice(0, -1);
  return withoutTrailingSlash.slice(
    0,
    withoutTrailingSlash.lastIndexOf('/') + 1
  );
}

function buildManagedSkillMigrations() {
  const entriesById = new Map(
    skillRegistry.entries.map((entry) => [entry.id, entry])
  );
  const migrations = [];

  for (const entry of skillRegistry.entries) {
    if (entry.status !== 'deprecated') {
      continue;
    }
    const replacement = entriesById.get(entry.replacement);
    for (const sourcePath of entry.managedPaths) {
      const parent = managedPathParent(sourcePath);
      const destinationPath = replacement.managedPaths.find(
        (candidate) => managedPathParent(candidate) === parent
      );
      if (!destinationPath) {
        throw new Error(
          `Replacement Skill ${replacement.id} has no managed path for ${sourcePath}`
        );
      }
      migrations.push({ sourcePath, destinationPath });
    }
  }

  return migrations;
}

function migrateTaskContextContent(content, migrations) {
  let changed = false;
  const lines = content.split('\n').map((line) => {
    if (line.trim() === '') {
      return line;
    }

    let record;
    try {
      record = JSON.parse(line);
    } catch {
      return line;
    }
    if (
      !record
      || typeof record !== 'object'
      || Array.isArray(record)
      || typeof record.file !== 'string'
    ) {
      return line;
    }

    const file = record.file.replaceAll('\\', '/').replace(/^\.\//, '');
    for (const migration of migrations) {
      if (!file.startsWith(migration.sourcePath)) {
        continue;
      }
      record.file = `${migration.destinationPath}${file.slice(migration.sourcePath.length)}`;
      changed = true;
      return JSON.stringify(record);
    }
    return line;
  });

  return changed ? lines.join('\n') : null;
}

async function buildTaskContextMigrationActions(targetDir, migrations) {
  const tasksRoot = join(targetDir, '.cowork-flow', 'tasks');
  if (migrations.length === 0 || !await pathExists(tasksRoot)) {
    return [];
  }

  const actions = [];
  for (const file of await listFiles(tasksRoot)) {
    const normalizedFile = toTemplatePath(file);
    if (!normalizedFile.endsWith('.jsonl')) {
      continue;
    }
    const destination = join(tasksRoot, file);
    const content = migrateTaskContextContent(
      await readFile(destination, 'utf8'),
      migrations
    );
    if (content === null) {
      continue;
    }
    actions.push({
      action: 'update',
      source: null,
      destination,
      relativePath: `.cowork-flow/tasks/${normalizedFile}`,
      content
    });
  }
  return actions;
}

export async function buildInitPlan(targetDir, options = {}) {
  const files = await listFiles(templateRoot);
  const actions = [];
  const platforms = options.platforms ?? [];
  const seen = new Set();

  for (const file of files) {
    if (!shouldIncludeForPlatforms(file, platforms)) {
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

  for (const entry of skillRegistry.publicEntries) {
    for (const platform of platforms) {
      const destBase = skillDestinationForPlatform(platform);
      if (!destBase) continue;
      const dest = join(targetDir, destBase, entry.id, 'SKILL.md');
      if (seen.has(dest)) continue;
      seen.add(dest);
      actions.push({
        action: (await pathExists(dest)) ? 'skip' : 'create',
        source: join(templateRoot, entry.source),
        destination: dest,
        relativePath: join(destBase, entry.id, 'SKILL.md')
      });
    }
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

const PROTECTED_SYNC_FILES = new Set(
  hostRegistry.syncPolicy.protectedFiles
);
const PROTECTED_SYNC_PREFIXES = hostRegistry.syncPolicy.protectedPrefixes;
const SAFE_SYNC_FILES = new Set(hostRegistry.syncPolicy.safeFiles);
const SAFE_SYNC_PREFIXES = [
  ...hostRegistry.syncPolicy.safePrefixes,
  ...hostRegistry.assetPrefixes,
  ...hostRegistry.skillTargets.map((target) => `${target}/`)
];
const MANAGED_BLOCK_FILES = new Set(
  hostRegistry.syncPolicy.managedBlockFiles
);
const OBSOLETE_SYNC_FILES = new Set(
  hostRegistry.syncPolicy.obsoleteFiles
);

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
    || hostRegistry.isKnownPlatformAsset(templatePath)
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
  const seen = new Set();

  for (const file of files) {
    if (!shouldIncludeForPlatforms(file, platforms)) {
      continue;
    }

    const destination = join(targetDir, file);
    seen.add(destination);

    if (toTemplatePath(file) === '.cowork-flow/.version') {
      continue;
    }

    const source = join(templateRoot, file);
    const exists = await pathExists(destination);
    if (MANAGED_BLOCK_FILES.has(toTemplatePath(file))) {
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

  for (const entry of skillRegistry.publicEntries) {
    for (const platform of platforms) {
      const destBase = skillDestinationForPlatform(platform);
      if (!destBase) continue;
      const dest = join(targetDir, destBase, entry.id, 'SKILL.md');
      if (seen.has(dest)) continue;
      seen.add(dest);
      const destExists = await pathExists(dest);
      const safe = hostRegistry.skillTargets.some(
        (target) => dest.startsWith(join(targetDir, target))
      );
      if (destExists && (safe || options.force)) {
        actions.push({
          action: 'update',
          source: join(templateRoot, entry.source),
          destination: dest,
          relativePath: join(destBase, entry.id, 'SKILL.md')
        });
      } else if (!destExists) {
        actions.push({
          action: 'create',
          source: join(templateRoot, entry.source),
          destination: dest,
          relativePath: join(destBase, entry.id, 'SKILL.md')
        });
      }
    }
  }

  for (const entry of skillRegistry.entries) {
    if (entry.status === 'active') {
      continue;
    }
    for (const managedPath of entry.managedPaths) {
      const relativePath = managedPath.slice(0, -1);
      const destination = join(targetDir, relativePath);
      if (await pathExists(destination)) {
        actions.push({
          action: 'delete',
          source: null,
          destination,
          relativePath
        });
      }
    }
  }

  actions.push(...await buildTaskContextMigrationActions(
    targetDir,
    buildManagedSkillMigrations()
  ));

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

  return createAssetPlan({
    kind: 'sync',
    targetDir,
    actions
  });
}

export async function detectInstalledPlatforms(targetDir) {
  return hostRegistry.detectInstalledPlatforms(targetDir, pathExists);
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
