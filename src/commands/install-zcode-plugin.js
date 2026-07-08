import { cp, mkdir, readFile, writeFile, access, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { homedir } from 'node:os';

import { readPackageInfo } from '../lib/package-info.js';
import { templateRoot } from '../lib/paths.js';

const ZCODE_MARKETPLACE = 'zcode-plugins-official';
const PLUGIN_NAME = 'cowork-flow';

function parseArgs(args) {
  return {
    dryRun: args.includes('--dry-run'),
    force: args.includes('--force')
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

async function getZCodeCacheDir() {
  const base = process.env.ZCODE_HOME || join(homedir(), '.zcode');
  return join(base, 'cli', 'plugins', 'cache', ZCODE_MARKETPLACE, PLUGIN_NAME);
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

async function updateMarketplace(cacheRoot, version) {
  const marketPath = resolve(cacheRoot, '..', '..', '..', 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json');
  const market = (await readJsonSafe(marketPath)) || { name: ZCODE_MARKETPLACE, plugins: [], version: 1 };

  const entry = {
    cachePath: join(cacheRoot, version).split('\\').join('/'),
    name: PLUGIN_NAME,
    source: 'filesystem',
    version
  };

  const existingIdx = market.plugins.findIndex((p) => p.name === PLUGIN_NAME);
  if (existingIdx >= 0) {
    market.plugins[existingIdx] = entry;
  } else {
    market.plugins.push(entry);
  }

  await mkdir(dirname(marketPath), { recursive: true });
  await writeJsonAtomic(marketPath, market);
}

export async function runInstallZCodePlugin(args = []) {
  const { dryRun, force } = parseArgs(args);
  const pluginSrc = join(templateRoot, ".zcode");
  const skillsSrc = join(templateRoot, "skills");
  const { version } = await readPackageInfo();

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`ZCode plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }
  if (!(await pathExists(skillsSrc))) {
    throw new Error(`Skills source missing at ${skillsSrc}. Reinstall cowork-flow.`);
  }

  const cacheRoot = await getZCodeCacheDir();
  const destDir = join(cacheRoot, version);

  if (!force && (await pathExists(destDir))) {
    console.log(`cowork-flow ZCode plugin already installed at ${destDir}`);
    console.log('Use --force to overwrite.');
    return;
  }

  if (dryRun) {
    console.log(`[dry-run] Would install ZCode plugin:`);
    console.log(`  Plugin: ${pluginSrc} -> ${destDir}`);
    console.log(`  Skills: ${skillsSrc} -> ${join(destDir, 'skills')}`);
    return;
  }

  await mkdir(cacheRoot, { recursive: true });
  if (await pathExists(destDir)) {
    await rm(destDir, { recursive: true, force: true });
  }

  // Copy plugin runtime (.zcode-plugin/, hooks/, runtime/, scaffold/) from .zcode/
  await cp(pluginSrc, destDir, { recursive: true });

  // Sync package.json version to scaffold/.version so the plugin-only launcher
  // can resolve the correct versioned plugin cache path at runtime.
  const scaffoldVersionPath = join(destDir, "scaffold", ".cowork-flow", ".version");
  await writeFile(scaffoldVersionPath, `${version}\n`, "utf8");

  // Copy canonical skills into the plugin cache so plugin.json "skills" resolves.
  await cp(skillsSrc, join(destDir, "skills"), { recursive: true, force: true });

  await updateMarketplace(cacheRoot, version);

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
