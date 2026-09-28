import { cp, mkdir, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

import { parseInstallArgs, pathExists, readJsonFile } from '../lib/install-support.js';
import { packageRoot } from '../lib/paths.js';
import { readPackageInfo } from '../lib/package-info.js';

const PRESET_ID = 'cowork-flow';
const MARKER_FILE = '.cowork-flow-preset.json';
const PRESET_SRC = join(packageRoot, 'presets', 'dsh');

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function getDshPresetRoot() {
  const base = process.env.DSH_HOME || join(homedir(), '.dsh');
  return join(base, '.agent-presets');
}


async function readInstalledVersion(destDir) {
  const marker = await readJsonFile(join(destDir, MARKER_FILE));
  return typeof marker?.version === 'string' ? marker.version : null;
}


export async function runInstallDshPreset(args = []) {
  const { dryRun, force, uninstall } = parseInstallArgs(args);

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
