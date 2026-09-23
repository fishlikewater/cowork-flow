import { cp, mkdir, rm, access, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

import { packageRoot } from '../lib/paths.js';
import { readPackageInfo } from '../lib/package-info.js';
import { parseFlags } from '../lib/cli-flags.js';

const PRESET_ID = 'cowork-flow';
const MARKER_FILE = '.cowork-flow-preset.json';
const PRESET_SRC = join(packageRoot, 'presets', 'dsh');

// Declared so `host add`/`host remove` can render the flags this installer
// accepts without keeping a second copy of the list.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function parseArgs(args) {
  const { flags } = parseFlags(args, { boolean: FLAGS });
  return {
    dryRun: Boolean(flags['--dry-run']),
    force: Boolean(flags['--force']),
    uninstall: Boolean(flags['--uninstall'])
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


function getDshPresetRoot() {
  const base = process.env.DSH_HOME || join(homedir(), '.dsh');
  return join(base, '.agent-presets');
}


async function readInstalledVersion(destDir) {
  try {
    const raw = await readFile(join(destDir, MARKER_FILE), 'utf8');
    const parsed = JSON.parse(raw);
    return typeof parsed.version === 'string' ? parsed.version : null;
  } catch {
    return null;
  }
}


export async function runInstallDshPreset(args = []) {
  const { dryRun, force, uninstall } = parseArgs(args);

  const destDir = join(getDshPresetRoot(), PRESET_ID);

  if (uninstall) {
    if (dryRun) {
      console.log('[dry-run] Would uninstall DSH preset:');
      console.log(`  Remove: ${destDir}`);
      return;
    }
    const installed = await pathExists(destDir);
    await rm(destDir, { recursive: true, force: true });
    console.log(
      installed
        ? `✓ cowork-flow DSH preset removed from ${destDir}`
        : `cowork-flow DSH preset was not installed at ${destDir}; nothing to remove`
    );
    return;
  }

  if (!(await pathExists(PRESET_SRC))) {
    throw new Error(`DSH preset source missing at ${PRESET_SRC}. Reinstall cowork-flow.`);
  }

  if (dryRun) {
    console.log('[dry-run] Would install DSH preset:');
    console.log(`  Preset: ${PRESET_SRC} -> ${destDir}`);
    return;
  }

  const { version } = await readPackageInfo();

  if (!force && (await pathExists(destDir))) {
    const installedVersion = await readInstalledVersion(destDir);
    console.log(`cowork-flow DSH preset already installed at ${destDir}`);
    if (installedVersion === null) {
      console.log(
        `Installed version unknown (no ${MARKER_FILE}); current version is ${version}.`
      );
      console.log('Refresh it with: cwf host add dsh --component preset --force');
    } else if (installedVersion !== version) {
      console.log(
        `Installed version ${installedVersion} differs from current version ${version}.`
      );
      console.log('The preset does not update with sync or npm; refresh it with:');
      console.log('  cwf host add dsh --component preset --force');
    } else {
      console.log('Use --force to overwrite.');
    }
    return;
  }

  await mkdir(getDshPresetRoot(), { recursive: true });
  if (await pathExists(destDir)) {
    await rm(destDir, { recursive: true, force: true });
  }

  await cp(PRESET_SRC, destDir, { recursive: true });
  await writeFile(
    join(destDir, MARKER_FILE),
    `${JSON.stringify({ version, installedAt: new Date().toISOString() }, null, 2)}\n`,
    'utf8'
  );

  console.log(`✓ cowork-flow DSH preset installed to ${destDir}`);
  console.log('  Start a new DSH session and pick the "Cowork Flow" preset.');
}
