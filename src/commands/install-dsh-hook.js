import { access, copyFile, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { homedir } from 'node:os';

import { packageRoot } from '../lib/paths.js';

const PLUGIN_SRC = join(packageRoot, 'presets', 'dsh', 'plugins', 'workflow-state.js');
const ROW_ID = 'workflow-state-hook';
const MANAGED_MARK = '# cowork-flow: managed workflow-state-hook row. Run "cowork-flow install-dsh-hook" to change it.';


function parseArgs(args) {
  return {
    dryRun: args.includes('--dry-run'),
    force: args.includes('--force'),
    uninstall: args.includes('--uninstall')
  };
}


function getDshHome() {
  return process.env.DSH_HOME || join(homedir(), '.dsh');
}


async function pathExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}


async function readIfExists(file) {
  try {
    return await readFile(file, 'utf8');
  } catch {
    return null;
  }
}


function hookRowBlock(pluginPath) {
  // cordis.patch.yml is a TOP-LEVEL YAML ARRAY of patch objects. A bare row
  // would be read as a "modify existing entry" patch and skipped with
  // "entry not found"; a new row therefore needs one id-less patch whose
  // insert list appends rows at the top level of the composed entry list.
  return [
    MANAGED_MARK,
    '- insert:',
    '    - id: ' + ROW_ID,
    '      name: ' + JSON.stringify(pluginPath),
  ].join('\n');
}


/**
 * Locate the managed hook block inside a patch file's text.
 *
 * The block is the marker comment (when present), the id-less insert patch
 * line, and the hook row with its indented continuation lines. Returns null
 * when no such row exists. The patch is edited as text on purpose: a YAML
 * round-trip would destroy !!js expressions used by DSH compositions.
 */
function findManagedBlock(text) {
  const lines = text.split('\n');
  const start = lines.findIndex((line) => line.trim() === '- id: ' + ROW_ID);
  if (start === -1) {
    return null;
  }
  let markStart = start;
  while (markStart > 0) {
    const previous = lines[markStart - 1].trim();
    if (
      previous === MANAGED_MARK.trim()
      || previous.startsWith('# cowork-flow: managed workflow-state-hook')
      || previous === '- insert:'
      || previous === 'insert:'
    ) {
      markStart -= 1;
    } else {
      break;
    }
  }
  let end = start + 1;
  while (end < lines.length && (lines[end].startsWith(' ') || lines[end].startsWith('\t'))) {
    end += 1;
  }
  // The block excludes any following blank separator: replacement keeps the
  // file's own line endings byte-stable, removal folds the leftover blank.
  return { start: markStart, end };
}


function patchWithRow(text, pluginPath) {
  const block = hookRowBlock(pluginPath);
  const range = findManagedBlock(text);
  if (range !== null) {
    const lines = text.split('\n');
    return lines.slice(0, range.start)
      .concat(block.split('\n'))
      .concat(lines.slice(range.end))
      .join('\n');
  }
  const base = text.replace(/\s+$/, '');
  return (base + '\n' + block + '\n').replace(/^\n+/, '');
}


function patchWithoutRow(text) {
  const range = findManagedBlock(text);
  if (range === null) {
    return text;
  }
  const lines = text.split('\n');
  const kept = lines.slice(0, range.start).concat(lines.slice(range.end));
  const merged = kept.join('\n').replace(/\n{3,}/g, '\n\n');
  if (merged.trim() === '') {
    return '';
  }
  return merged.replace(/\s+$/, '') + '\n';
}


async function upsertRow(patchFile, pluginPath) {
  const before = (await readIfExists(patchFile)) ?? '';
  const after = patchWithRow(before, pluginPath);
  if (after === before) {
    return false;
  }
  await writeFile(patchFile, after, 'utf8');
  return true;
}


async function removeRow(patchFile) {
  const before = await readIfExists(patchFile);
  if (before === null) {
    return null;
  }
  const after = patchWithoutRow(before);
  if (after === before) {
    return false;
  }
  if (after === '') {
    // Nothing of the user's own patch remains: drop the file instead of
    // leaving an empty patch that shadows nothing.
    await rm(patchFile, { force: true });
  } else {
    await writeFile(patchFile, after, 'utf8');
  }
  return true;
}


/**
 * Install (or uninstall) the machine-level DSH workflow-state hook.
 *
 * Registers the shared workflow-state.js plugin as an id-less insert patch
 * in $DSH_HOME/cordis.patch.yml, which DSH applies to every profile and
 * agent session at boot. Any preset keeps working unchanged; the hook
 * contributes nothing (and, since the plugin pre-checks for a .cowork-flow
 * root, does not even spawn an interpreter) in projects that do not run
 * cowork-flow.
 */
export async function runInstallDshHook(args = []) {
  const { dryRun, force, uninstall } = parseArgs(args);

  if (!(await pathExists(PLUGIN_SRC))) {
    throw new Error('workflow-state hook source missing at ' + PLUGIN_SRC + '. Reinstall cowork-flow.');
  }

  const home = getDshHome();
  const pluginDest = join(home, 'plugins', 'cowork-flow', 'workflow-state.js');
  const patchFile = join(home, 'cordis.patch.yml');

  if (dryRun) {
    if (uninstall) {
      console.log('[dry-run] Would uninstall workflow-state hook:');
      console.log('  Remove managed row from: ' + patchFile);
      if (force) {
        console.log('  Remove plugin file: ' + pluginDest);
      }
    } else {
      console.log('[dry-run] Would install workflow-state hook:');
      console.log('  Plugin: ' + PLUGIN_SRC + ' -> ' + pluginDest);
      console.log('  Patch insert: ' + patchFile + ' (id: ' + ROW_ID + ')');
    }
    return;
  }

  if (uninstall) {
    const removed = await removeRow(patchFile);
    if (removed === null) {
      console.log('No patch file at ' + patchFile + '; nothing to uninstall.');
    } else if (removed === false) {
      console.log('No managed hook row found in ' + patchFile + '.');
    } else {
      console.log('✓ Workflow-state hook row removed from ' + patchFile);
    }
    if (force) {
      await rm(pluginDest, { force: true });
      console.log('✓ Removed plugin file ' + pluginDest);
    }
    return;
  }

  await mkdir(dirname(pluginDest), { recursive: true });
  await copyFile(PLUGIN_SRC, pluginDest);
  const changed = await upsertRow(patchFile, pluginDest);

  console.log('✓ cowork-flow workflow-state hook installed to ' + pluginDest);
  console.log('  Registered insert row "' + ROW_ID + '" in ' + patchFile + (changed === false ? ' (already up to date)' : ''));
  console.log('  Restart DSH for the composition to load (installed at boot-time).');
  console.log('  Note: current DSH builds compose this row but do not surface host-level sections');
  console.log('  in agent prompts; use "cowork-flow install-dsh-preset" for real-time injection.');

  const presetComposition = join(home, '.agent-presets', 'cowork-flow', 'agent.cordis.yml');
  if (await pathExists(presetComposition)) {
    console.log('  Note: the cowork-flow agent preset is also installed and already bundles this hook.');
    console.log('  Keep only one to avoid duplicate injection: remove the preset, or run "cowork-flow install-dsh-hook --uninstall".');
  }
}
