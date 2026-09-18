import { cp, mkdir, rm, access, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

import { packageRoot, templateRoot } from '../lib/paths.js';
import { readPackageInfo } from '../lib/package-info.js';

const PRESET_ID = 'cowork-flow';
const MARKER_FILE = '.cowork-flow-preset.json';
const PRESET_SRC = join(packageRoot, 'presets', 'dsh');
const SKILLS_SRC = join(templateRoot, 'skills');


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
  const { dryRun, force } = parseArgs(args);

  if (!(await pathExists(PRESET_SRC))) {
    throw new Error(`DSH preset source missing at ${PRESET_SRC}. Reinstall cowork-flow.`);
  }
  if (!(await pathExists(SKILLS_SRC))) {
    throw new Error(`Skills source missing at ${SKILLS_SRC}. Reinstall cowork-flow.`);
  }

  const destDir = join(getDshPresetRoot(), PRESET_ID);
  const skillsDest = join(destDir, 'skills');

  if (dryRun) {
    console.log('[dry-run] Would install DSH preset:');
    console.log(`  Preset: ${PRESET_SRC} -> ${destDir}`);
    console.log(`  Skills: ${SKILLS_SRC} -> ${skillsDest}`);
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
      console.log('Refresh it with: cowork-flow install-dsh-preset --force');
    } else if (installedVersion !== version) {
      console.log(
        `Installed version ${installedVersion} differs from current version ${version}.`
      );
      console.log('The preset does not update with sync or npm; refresh it with:');
      console.log('  cowork-flow install-dsh-preset --force');
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
  await cp(SKILLS_SRC, skillsDest, { recursive: true, force: true });
  await writeFile(
    join(destDir, MARKER_FILE),
    `${JSON.stringify({ version, installedAt: new Date().toISOString() }, null, 2)}\n`,
    'utf8'
  );

  console.log(`✓ cowork-flow DSH preset installed to ${destDir}`);
  console.log('  Start a new DSH session and pick the "Cowork Flow" preset.');
}
