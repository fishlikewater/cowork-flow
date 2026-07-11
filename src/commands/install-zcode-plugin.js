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
    force: args.includes('--force'),
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
  const marketPath = resolve(
    cacheRoot, '..', '..', '..', 'marketplaces', ZCODE_MARKETPLACE, 'marketplace.json'
  );
  const market = (await readJsonSafe(marketPath)) || {
    name: ZCODE_MARKETPLACE,
    plugins: [],
    version: 1,
  };

  const entry = {
    cachePath: join(cacheRoot, version).split('\\').join('/'),
    name: PLUGIN_NAME,
    source: 'filesystem',
    version,
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

export async function runInstallZCodePlugin(args = [], { io } = {}) {
  const writeOut = (msg) => (io ? io.writeOut(msg) : process.stdout.write(msg));
  const writeErr = (msg) => (io ? io.writeErr(msg) : process.stderr.write(msg));

  const { dryRun, force } = parseArgs(args);
  const pluginSrc = join(templateRoot, '.zcode');
  const skillsSrc = join(templateRoot, 'skills');
  const scaffoldSrc = join(templateRoot, '.zcode', 'scaffold');

  const { version } = await readPackageInfo().catch(() => ({ version: '0.0.0' }));

  if (!(await pathExists(pluginSrc))) {
    writeErr(`ZCode plugin source missing at ${pluginSrc}. Reinstall cowork-flow.\n`);
    return 1;
  }

  const cacheRoot = await getZCodeCacheDir();
  const destDir = join(cacheRoot, version);

  if (!force && (await pathExists(destDir))) {
    writeOut(`cowork-flow ZCode plugin v${version} already installed.\n`);
    writeOut(`  Location: ${destDir}\n`);
    writeOut('Use --force to overwrite.\n');
    return 0;
  }

  if (dryRun) {
    writeOut('[dry-run] Would install ZCode plugin:\n');
    writeOut(`  Plugin: ${pluginSrc} -> ${destDir}\n`);
    if (await pathExists(skillsSrc)) {
      writeOut(`  Skills: ${skillsSrc} -> ${join(destDir, 'skills')}\n`);
    }
    if (await pathExists(scaffoldSrc)) {
      writeOut(`  Scaffold: ${scaffoldSrc} -> ${join(destDir, 'scaffold')}\n`);
    }
    return 0;
  }

  await mkdir(cacheRoot, { recursive: true });
  if (await pathExists(destDir)) {
    await rm(destDir, { recursive: true, force: true });
  }

  // Copy plugin runtime (hooks/, .zcode-plugin/, scaffold/)
  await cp(pluginSrc, destDir, { recursive: true });

  // Copy skills into the plugin cache so plugin.json "skills" resolves
  if (await pathExists(skillsSrc)) {
    await cp(skillsSrc, join(destDir, 'skills'), { recursive: true, force: true });
  }

  await updateMarketplace(cacheRoot, version);

  await writeJsonAtomic(join(destDir, '.zcode-plugin-seed.json'), {
    marketplace: ZCODE_MARKETPLACE,
    plugin: PLUGIN_NAME,
    pluginVersion: version,
    source: 'cli-install',
    version: 1,
  });

  writeOut(`✓ cowork-flow ZCode plugin v${version} installed to ${destDir}\n`);
  writeOut('  Restart ZCode to load the plugin.\n');
  return 0;
}
