import { cp, mkdir, writeFile, rm, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

import { parseInstallArgs, pathExists, readJsonFile } from '../lib/install-support.js';
import { readPackageInfo } from '../lib/package-info.js';
import { templateRoot } from '../lib/paths.js';
import { marketplaceIconUrl, pluginManifest, readPluginMetadata } from '../lib/plugin-metadata.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const ZCODE_MARKETPLACE = 'cowork-flow-local';
const LEGACY_ZCODE_MARKETPLACE = 'zcode-plugins-official';
const PLUGIN_NAME = 'cowork-flow';
const LOCAL_MARKETPLACE_DESCRIPTION = 'Local marketplace registration for cowork-flow during local development.';

// Rendered by `host add`/`host remove`; `--prune-old` is
// zcode-only.
export const FLAGS = ['--dry-run', '--force', '--prune-old', '--uninstall'];


function getZCodePluginsRoot() {
  const base = process.env.ZCODE_HOME || join(homedir(), '.zcode');
  return join(base, 'cli', 'plugins');
}

async function getZCodeCacheDir() {
  return join(getZCodePluginsRoot(), 'cache', ZCODE_MARKETPLACE, PLUGIN_NAME);
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

async function updateMarketplace(pluginsRoot, cacheRoot, version, metadata) {
  const { activeMarketplacePath, sourceMarketplacePath } = marketplacePaths(pluginsRoot);
  const market = (await readJsonFile(sourceMarketplacePath))
    || (await readJsonFile(activeMarketplacePath))
    || {
      name: ZCODE_MARKETPLACE,
      description: LOCAL_MARKETPLACE_DESCRIPTION,
      plugins: [],
      version: 1
    };
  const pluginPath = normalizedPath(join(cacheRoot, version));
  const manifest = pluginManifest(metadata, 'zcode', version);

  market.name = ZCODE_MARKETPLACE;
  market.description = market.description || LOCAL_MARKETPLACE_DESCRIPTION;
  market.version = 1;
  if (!Array.isArray(market.plugins)) {
    market.plugins = [];
  }

  const entry = {
    author: manifest.author,
    category: metadata.marketplaceCategory,
    description: manifest.description,
    displayName: metadata.displayName,
    icon: marketplaceIconUrl(metadata),
    license: manifest.license,
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
  const known = (await readJsonFile(knownPath)) || {
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
  const legacy = await readJsonFile(legacyPath);
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

async function pruneVersions(cacheRoot, version, pruneOld) {
  if (!pruneOld) {
    return;
  }
  const removed = await pruneOldVersions(cacheRoot, version);
  if (removed.length > 0) {
    console.log(`Pruned old cowork-flow ZCode plugin versions: ${removed.join(', ')}`);
  }
}

// The files are ZCode's but the entries inside are ours:
// uninstall removes cowork-flow's entry from each and
// leaves other registrations in place. The per-marketplace
// cache dir is ours alone, so it goes too (an empty
// directory left behind is one the user has to wonder
// about).
async function uninstall(pluginsRoot, cacheRoot, dryRun) {
  const { activeMarketplacePath, sourceMarketplacePath } = marketplacePaths(pluginsRoot);
  const activeMarketplaceDir = dirname(activeMarketplacePath);
  const sourceMarketplaceDir = dirname(sourceMarketplacePath);
  const marketplaceCacheDir = dirname(cacheRoot);
  const knownPath = join(pluginsRoot, 'known_marketplaces.json');

  if (dryRun) {
    console.log('[dry-run] Would remove cowork-flow ZCode plugin:');
    console.log(`  Cache: ${marketplaceCacheDir}`);
    console.log(`  Marketplace source: ${sourceMarketplaceDir}`);
    console.log(`  Active marketplace: ${activeMarketplaceDir}`);
    console.log(`  Known marketplaces entry: ${knownPath} -> ${ZCODE_MARKETPLACE}`);
    return 0;
  }

  const known = await readJsonFile(knownPath);
  let droppedKnownEntry = false;
  if (known && Array.isArray(known.marketplaces)) {
    const kept = known.marketplaces.filter((marketplace) => marketplace.id !== ZCODE_MARKETPLACE);
    if (kept.length !== known.marketplaces.length) {
      known.marketplaces = kept;
      await writeJsonAtomic(knownPath, known);
      droppedKnownEntry = true;
    }
  }

  const hadCache = await pathExists(cacheRoot);
  await rm(cacheRoot, { recursive: true, force: true });
  await rm(marketplaceCacheDir, { recursive: true, force: true });
  await rm(sourceMarketplaceDir, { recursive: true, force: true });
  await rm(activeMarketplaceDir, { recursive: true, force: true });

  console.log(
    hadCache || droppedKnownEntry
      ? `✓ cowork-flow ZCode plugin uninstalled (${ZCODE_MARKETPLACE})`
      : `cowork-flow ZCode plugin was not installed; nothing to remove under ${pluginsRoot}`
  );
  console.log('  Restart ZCode to drop the plugin from its list.');
  return 0;
}

function printInstallDryRun({ pluginSrc, destDir, pluginsRoot }) {
  console.log(`[dry-run] Would install ZCode plugin:`);
  console.log(`  Plugin: ${pluginSrc} -> ${destDir}`);
  console.log(`  Marketplace source: ${join(pluginsRoot, 'cache', 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json')}`);
  console.log(`  Active marketplace: ${join(pluginsRoot, 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json')}`);
  console.log(`  Known marketplaces: ${join(pluginsRoot, 'known_marketplaces.json')}`);
}

async function materializePlugin({ pluginSrc, destDir, cacheRoot, manifest, version }) {
  await mkdir(cacheRoot, { recursive: true });
  if (await pathExists(destDir)) {
    await rm(destDir, { recursive: true, force: true });
  }

  await cp(pluginSrc, destDir, { recursive: true });

  // ZCode applies plugin scaffold files to each workspace
  // folder; keep workflow runtime files out of scaffold.
  await rm(join(destDir, "scaffold", ".cowork-flow"), { recursive: true, force: true });

  // The presets/zcode/hooks/runtime/scripts copy is stale;
  // overwrite it with the authoritative version from the
  // template.
  const mainScriptsSrc = join(templateRoot, ".cowork-flow", "scripts");
  const pluginScriptsDest = join(destDir, "hooks", "runtime", "scripts");
  if (await pathExists(mainScriptsSrc)) {
    await cp(mainScriptsSrc, pluginScriptsDest, { recursive: true, force: true });
  }

  // The cache directory is named after the package
  // version, so the installed manifest is stamped to
  // match.
  await stampPayloadManifest(destDir, manifest, version);
}

// Registration files are refreshed in one order:
// marketplace, known list, old-marketplace cleanup, then
// old cache versions.
async function refreshRegistrations({ pluginsRoot, cacheRoot, version, metadata, pruneOld }) {
  await updateMarketplace(pluginsRoot, cacheRoot, version, metadata);
  await updateKnownMarketplaces(pluginsRoot);
  await removeLegacyMarketplaceEntry(pluginsRoot);
  await pruneVersions(cacheRoot, version, pruneOld);
}

async function writeInstallSeed(destDir, version) {
  await writeJsonAtomic(join(destDir, ".zcode-plugin-seed.json"), {
    hash: "placeholder-replace-on-publish",
    marketplace: ZCODE_MARKETPLACE,
    plugin: PLUGIN_NAME,
    pluginVersion: version,
    source: "cli-install",
    version: 1
  });
}

export async function runInstallZCodePlugin(args = []) {
  const { dryRun, force, pruneOld, uninstall: remove } = parseInstallArgs(args, {
    extraBoolean: ['--prune-old']
  });
  const pluginsRoot = getZCodePluginsRoot();
  const cacheRoot = await getZCodeCacheDir();

  if (remove) {
    return await uninstall(pluginsRoot, cacheRoot, dryRun);
  }

  const { sourceDir: pluginSrc, manifest } = pluginPayload('zcode');
  const { version } = await readPackageInfo();
  const metadata = await readPluginMetadata();

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`ZCode plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }
  const destDir = join(cacheRoot, version);

  if (dryRun) {
    printInstallDryRun({ pluginSrc, destDir, pluginsRoot });
    return;
  }

  if (!force && (await pathExists(destDir))) {
    await refreshRegistrations({ pluginsRoot, cacheRoot, version, metadata, pruneOld });
    console.log(`cowork-flow ZCode plugin already installed at ${destDir}`);
    console.log('Use --force to overwrite.');
    return;
  }

  await materializePlugin({ pluginSrc, destDir, cacheRoot, manifest, version });
  await refreshRegistrations({ pluginsRoot, cacheRoot, version, metadata, pruneOld });
  await writeInstallSeed(destDir, version);

  console.log(`✓ cowork-flow ZCode plugin installed to ${destDir}`);
  console.log('  Restart ZCode to load the plugin.');
}
