import { cp, mkdir, rm, access } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

import { packageRoot, templateRoot } from '../lib/paths.js';

const PRESET_ID = 'cowork-flow';
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

  if (!force && (await pathExists(destDir))) {
    console.log(`cowork-flow DSH preset already installed at ${destDir}`);
    console.log('Use --force to overwrite.');
    return;
  }

  await mkdir(getDshPresetRoot(), { recursive: true });
  if (await pathExists(destDir)) {
    await rm(destDir, { recursive: true, force: true });
  }

  await cp(PRESET_SRC, destDir, { recursive: true });
  await cp(SKILLS_SRC, skillsDest, { recursive: true, force: true });

  console.log(`✓ cowork-flow DSH preset installed to ${destDir}`);
  console.log('  Start a new DSH session and pick the "Cowork Flow" preset.');
}
