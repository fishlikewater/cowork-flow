import { cp, mkdir, readFile, writeFile, access, rm, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

import { readPackageInfo } from '../lib/package-info.js';
import { templateRoot } from '../lib/paths.js';

const ZCODE_MARKETPLACE = 'cowork-flow-local';
const LEGACY_ZCODE_MARKETPLACE = 'zcode-plugins-official';
const PLUGIN_NAME = 'cowork-flow';
const LOCAL_MARKETPLACE_DESCRIPTION = 'Local marketplace registration for cowork-flow during local development.';

function parseArgs(args) {
  return {
    dryRun: args.includes('--dry-run'),
    force: args.includes('--force'),
    pruneOld: args.includes('--prune-old')
  };
}

async function pathExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

function getZCodePluginsRoot() {
  const base = process.env.ZCODE_HOME || join(homedir(), '.zcode');
  return join(base, 'cli', 'plugins');
}

async function getZCodeCacheDir() {
  return join(getZCodePluginsRoot(), 'cache', ZCODE_MARKETPLACE, PLUGIN_NAME);
}

async function readJsonSafe(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch {
    return null;
  }
}

async function writeJsonAtomic(path, data) {
  await writeFile(path, JSON.stringify(data, null, 2) + '\n', 'utf8');
}

function dirname(path) {
  const idx = path.replace(/\\/g, '/').lastIndexOf('/');
  return idx >= 0 ? path.slice(0, idx) : path;
}

function normalizedPath(path) {
  return path.split('\\').join('/');
}

function marketplacePaths(pluginsRoot) {
  return {
    activeMarketplacePath: join(pluginsRoot, 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json'),
    sourceMarketplacePath: join(pluginsRoot, 'cache', 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json')
  };
}

async function updateMarketplace(pluginsRoot, cacheRoot, version, manifest = {}) {
  const { activeMarketplacePath, sourceMarketplacePath } = marketplacePaths(pluginsRoot);
  const market = (await readJsonSafe(sourceMarketplacePath))
    || (await readJsonSafe(activeMarketplacePath))
    || {
      name: ZCODE_MARKETPLACE,
      description: LOCAL_MARKETPLACE_DESCRIPTION,
      plugins: [],
      version: 1
    };
  const pluginPath = normalizedPath(join(cacheRoot, version));

  market.name = ZCODE_MARKETPLACE;
  market.description = market.description || LOCAL_MARKETPLACE_DESCRIPTION;
  market.version = 1;
  if (!Array.isArray(market.plugins)) {
    market.plugins = [];
  }

  const entry = {
    author: manifest.author || { name: 'fisklikewater' },
    category: 'developer-tools',
    description: manifest.description || 'cowork-flow task lifecycle, hooks, skills, and fixed subagents for ZCode.',
    license: manifest.license || 'MIT',
    name: PLUGIN_NAME,
    source: {
      source: 'directory',
      path: pluginPath
    },
    version
  };

  const existingIdx = market.plugins.findIndex((p) => p.name === PLUGIN_NAME);
  if (existingIdx >= 0) {
    market.plugins[existingIdx] = entry;
  } else {
    market.plugins.push(entry);
  }

  for (const targetPath of [sourceMarketplacePath, activeMarketplacePath]) {
    await mkdir(dirname(targetPath), { recursive: true });
    await writeJsonAtomic(targetPath, market);
  }
  return { activeMarketplacePath, sourceMarketplacePath };
}

async function updateKnownMarketplaces(pluginsRoot) {
  const knownPath = join(pluginsRoot, 'known_marketplaces.json');
  const known = (await readJsonSafe(knownPath)) || {
    version: 1,
    marketplaces: []
  };
  const now = new Date().toISOString();
  const marketplaceDir = join(pluginsRoot, 'cache', 'marketplaces', ZCODE_MARKETPLACE);
  const existingIdx = Array.isArray(known.marketplaces)
    ? known.marketplaces.findIndex((marketplace) => marketplace.id === ZCODE_MARKETPLACE)
    : -1;
  const existing = existingIdx >= 0 ? known.marketplaces[existingIdx] : {};
  const entry = {
    id: ZCODE_MARKETPLACE,
    source: {
      source: 'directory',
      path: normalizedPath(marketplaceDir)
    },
    name: ZCODE_MARKETPLACE,
    description: LOCAL_MARKETPLACE_DESCRIPTION,
    addedAt: existing.addedAt || now,
    pluginCount: 1,
    lastUpdated: now
  };

  known.version = 1;
  if (!Array.isArray(known.marketplaces)) {
    known.marketplaces = [];
  }
  if (existingIdx >= 0) {
    known.marketplaces[existingIdx] = entry;
  } else {
    known.marketplaces.push(entry);
  }

  await mkdir(dirname(knownPath), { recursive: true });
  await writeJsonAtomic(knownPath, known);
  return knownPath;
}

async function removeLegacyMarketplaceEntry(pluginsRoot) {
  const legacyPath = join(
    pluginsRoot,
    'marketplaces',
    LEGACY_ZCODE_MARKETPLACE,
    'marketplace.json'
  );
  const legacy = await readJsonSafe(legacyPath);
  if (!legacy || !Array.isArray(legacy.plugins)) {
    return false;
  }

  const filteredPlugins = legacy.plugins.filter((plugin) => plugin.name !== PLUGIN_NAME);
  if (filteredPlugins.length === legacy.plugins.length) {
    return false;
  }

  legacy.plugins = filteredPlugins;
  await writeJsonAtomic(legacyPath, legacy);
  return true;
}

async function pruneOldVersions(cacheRoot, currentVersion) {
  if (!(await pathExists(cacheRoot))) {
    return [];
  }

  const removed = [];
  const entries = await readdir(cacheRoot, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name === currentVersion) {
      continue;
    }
    const target = join(cacheRoot, entry.name);
    await rm(target, { recursive: true, force: true });
    removed.push(entry.name);
  }
  return removed;
}

export async function runInstallZCodePlugin(args = []) {
  const { dryRun, force, pruneOld } = parseArgs(args);
  const pluginSrc = join(templateRoot, ".zcode");
  const skillsSrc = join(templateRoot, "skills");
  const { version } = await readPackageInfo();
  const manifest = (await readJsonSafe(join(pluginSrc, '.zcode-plugin', 'plugin.json'))) || {};

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`ZCode plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }
  if (!(await pathExists(skillsSrc))) {
    throw new Error(`Skills source missing at ${skillsSrc}. Reinstall cowork-flow.`);
  }

  const pluginsRoot = getZCodePluginsRoot();
  const cacheRoot = await getZCodeCacheDir();
  const destDir = join(cacheRoot, version);

  if (dryRun) {
    console.log(`[dry-run] Would install ZCode plugin:`);
    console.log(`  Plugin: ${pluginSrc} -> ${destDir}`);
    console.log(`  Skills: ${skillsSrc} -> ${join(destDir, 'skills')}`);
    console.log(`  Marketplace source: ${join(pluginsRoot, 'cache', 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json')}`);
    console.log(`  Active marketplace: ${join(pluginsRoot, 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json')}`);
    console.log(`  Known marketplaces: ${join(pluginsRoot, 'known_marketplaces.json')}`);
    return;
  }

  if (!force && (await pathExists(destDir))) {
    await updateMarketplace(pluginsRoot, cacheRoot, version, manifest);
    await updateKnownMarketplaces(pluginsRoot);
    await removeLegacyMarketplaceEntry(pluginsRoot);
    if (pruneOld) {
      const removed = await pruneOldVersions(cacheRoot, version);
      if (removed.length > 0) {
        console.log(`Pruned old cowork-flow ZCode plugin versions: ${removed.join(', ')}`);
      }
    }
    console.log(`cowork-flow ZCode plugin already installed at ${destDir}`);
    console.log('Use --force to overwrite.');
    return;
  }

  await mkdir(cacheRoot, { recursive: true });
  if (await pathExists(destDir)) {
    await rm(destDir, { recursive: true, force: true });
  }

  // Copy plugin runtime (.zcode-plugin/, hooks/, runtime/, scaffold/) from .zcode/
  await cp(pluginSrc, destDir, { recursive: true });

  // ZCode may apply plugin scaffold files to each workspace folder. Keep
  // workflow runtime files out of scaffold; explicit init/sync owns .cowork-flow.
  await rm(join(destDir, "scaffold", ".cowork-flow"), { recursive: true, force: true });

  // Sync canonical scripts from main template (single source of truth).
  // The .zcode/hooks/runtime/scripts/ copy is stale; overwrite with the
  // authoritative version from template/.cowork-flow/scripts/.
  const mainScriptsSrc = join(templateRoot, ".cowork-flow", "scripts");
  const pluginScriptsDest = join(destDir, "hooks", "runtime", "scripts");
  if (await pathExists(mainScriptsSrc)) {
    await cp(mainScriptsSrc, pluginScriptsDest, { recursive: true, force: true });
  }

  // Copy canonical skills into the plugin cache so plugin.json "skills" resolves.
  await cp(skillsSrc, join(destDir, "skills"), { recursive: true, force: true });

  await updateMarketplace(pluginsRoot, cacheRoot, version, manifest);
  await updateKnownMarketplaces(pluginsRoot);
  await removeLegacyMarketplaceEntry(pluginsRoot);
  if (pruneOld) {
    const removed = await pruneOldVersions(cacheRoot, version);
    if (removed.length > 0) {
      console.log(`Pruned old cowork-flow ZCode plugin versions: ${removed.join(', ')}`);
    }
  }

  // Write seed file for install tracking
  await writeJsonAtomic(join(destDir, ".zcode-plugin-seed.json"), {
    hash: "placeholder-replace-on-publish",
    marketplace: ZCODE_MARKETPLACE,
    plugin: PLUGIN_NAME,
    pluginVersion: version,
    source: "cli-install",
    version: 1
  });

  console.log(`✓ cowork-flow ZCode plugin installed to ${destDir}`);
  console.log('  Restart ZCode to load the plugin.');
}
