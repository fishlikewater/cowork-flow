import { access, cp, mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

import { readPackageInfo } from '../lib/package-info.js';
import { packageRoot, templateRoot } from '../lib/paths.js';

const QODER_MARKETPLACE = 'cowork-flow-local';
const PLUGIN_NAME = 'cowork-flow';
const PLUGIN_KEY = `${PLUGIN_NAME}@${QODER_MARKETPLACE}`;
const REGISTRY_FILE = 'installed_plugins_v2.json';

function parseArgs(args) {
  return {
    dryRun: args.includes('--dry-run'),
    force: args.includes('--force'),
    uninstall: args.includes('--uninstall')
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

function qoderHome() {
  const configured = (process.env.QODER_CONFIG_DIR || '').trim();
  return configured || join(homedir(), '.qoder');
}

function pluginPaths(home, version) {
  const pluginsRoot = join(home, 'plugins');
  const cacheRoot = join(pluginsRoot, 'cache', QODER_MARKETPLACE, PLUGIN_NAME);
  return {
    pluginsRoot,
    cacheRoot,
    installPath: version ? join(cacheRoot, version) : null,
    registry: join(pluginsRoot, REGISTRY_FILE),
    settings: join(home, 'settings.json')
  };
}

async function readJsonSafe(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch {
    return null;
  }
}

// The Qoder plugin registry is not part of the published docs, so every write
// keeps unknown keys and unrelated entries verbatim: cowork-flow may only own
// its own key inside a file it did not create.
async function writeJsonAtomic(path, data) {
  await mkdir(dirname(path), { recursive: true });
  const temp = `${path}.cowork-flow.tmp`;
  await writeFile(temp, JSON.stringify(data, null, 2) + '\n', 'utf8');
  await rename(temp, path);
}

function registryEntry(existing, installPath, version, now) {
  const previous = Array.isArray(existing) ? existing[0] : null;
  return {
    scope: 'user',
    installPath,
    version,
    installedAt: previous?.installedAt || now,
    lastUpdated: now,
    userVisible: true
  };
}

async function updateRegistry(paths, version, now, dryRun) {
  const registry = (await readJsonSafe(paths.registry)) ?? { version: 2, plugins: {} };
  if (!registry.plugins || typeof registry.plugins !== 'object') {
    registry.plugins = {};
  }
  const entries = Array.isArray(registry.plugins[PLUGIN_KEY]) ? registry.plugins[PLUGIN_KEY] : [];
  registry.plugins[PLUGIN_KEY] = [
    registryEntry(entries, paths.installPath, version, now),
    ...entries.slice(1)
  ];

  if (dryRun) {
    console.log(`  Registry entry: ${paths.registry} -> ${PLUGIN_KEY}@${version}`);
    return;
  }
  await writeJsonAtomic(paths.registry, registry);
}

async function enablePlugin(paths, dryRun) {
  const settings = (await readJsonSafe(paths.settings)) ?? {};
  if (!settings.enabledPlugins || typeof settings.enabledPlugins !== 'object') {
    settings.enabledPlugins = {};
  }
  settings.enabledPlugins[PLUGIN_KEY] = true;

  if (dryRun) {
    console.log(`  Enabled flag: ${paths.settings} -> enabledPlugins["${PLUGIN_KEY}"]=true`);
    return;
  }
  await writeJsonAtomic(paths.settings, settings);
}

async function stampManifest(installPath, version) {
  const manifestPath = join(installPath, '.qoder-plugin', 'plugin.json');
  const manifest = await readJsonSafe(manifestPath);
  if (!manifest) {
    throw new Error(`Qoder plugin manifest missing or unreadable: ${manifestPath}`);
  }
  manifest.version = version;
  await writeJsonAtomic(manifestPath, manifest);
}

async function uninstall(paths, dryRun) {
  const registry = await readJsonSafe(paths.registry);
  const owned = registry?.plugins?.[PLUGIN_KEY];
  if (dryRun) {
    console.log(`[dry-run] Would remove ${PLUGIN_KEY} from ${paths.registry}`);
    console.log(`[dry-run] Would remove ${paths.cacheRoot}`);
    return 0;
  }
  if (registry && owned) {
    delete registry.plugins[PLUGIN_KEY];
    await writeJsonAtomic(paths.registry, registry);
  }
  const settings = await readJsonSafe(paths.settings);
  if (settings?.enabledPlugins && PLUGIN_KEY in settings.enabledPlugins) {
    delete settings.enabledPlugins[PLUGIN_KEY];
    await writeJsonAtomic(paths.settings, settings);
  }
  await rm(paths.cacheRoot, { recursive: true, force: true });
  console.log(
    owned
      ? `✓ cowork-flow Qoder plugin uninstalled (${PLUGIN_KEY})`
      : `cowork-flow Qoder plugin was not registered; removed any cached copy at ${paths.cacheRoot}`
  );
  return 0;
}

export async function runInstallQoderPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseArgs(args);
  const home = qoderHome();
  const { version } = await readPackageInfo();
  const target = pluginPaths(home, version);

  if (remove) {
    return uninstall(target, dryRun);
  }

  const pluginSrc = join(packageRoot, 'presets', 'qoder');
  const skillsSrc = join(templateRoot, 'skills');
  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Qoder plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }
  if (!(await pathExists(skillsSrc))) {
    throw new Error(`Skills source missing at ${skillsSrc}. Reinstall cowork-flow.`);
  }

  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow Qoder plugin:`);
  console.log(`  Plugin: ${pluginSrc} -> ${target.installPath}`);
  console.log(`  Skills: ${skillsSrc} -> ${join(target.installPath, 'skills')}`);

  if (!dryRun && (await pathExists(target.installPath)) && !force) {
    console.log(`cowork-flow Qoder plugin already installed at ${target.installPath}`);
    console.log('Use --force to overwrite.');
    return 0;
  }

  const now = new Date().toISOString();
  if (dryRun) {
    await updateRegistry(target, version, now, true);
    await enablePlugin(target, true);
    return 0;
  }

  await mkdir(target.cacheRoot, { recursive: true });
  await rm(target.installPath, { recursive: true, force: true });
  await cp(pluginSrc, target.installPath, { recursive: true });
  // plugin.json's "skills" component resolves inside the plugin payload, so the
  // canonical template skills are copied in at install time instead of being
  // duplicated into the repository.
  await cp(skillsSrc, join(target.installPath, 'skills'), { recursive: true, force: true });
  await stampManifest(target.installPath, version);
  // Registry and enable flag come last: a half-copied payload must never be
  // advertised as installed.
  await updateRegistry(target, version, now, false);
  await enablePlugin(target, false);

  console.log(`✓ cowork-flow Qoder plugin installed to ${target.installPath}`);
  console.log('  Restart Qoder to load the plugin (the IDE has no hook hot reload).');
  return 0;
}
