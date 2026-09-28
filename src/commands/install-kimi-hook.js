import { copyFile, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { homedir } from 'node:os';

import { parseInstallArgs, pathExists } from '../lib/install-support.js';
import { packageRoot } from '../lib/paths.js';
import { readPackageInfo } from '../lib/package-info.js';

const SHIM_NAME = 'cowork-flow-inject.mjs';
const SHIM_SRC = join(packageRoot, 'presets', 'kimi-code', 'hooks', SHIM_NAME);
const MARKER_FILE = '.cowork-flow-kimi-hook.json';
const HOOK_EVENT = 'UserPromptSubmit';
// Kimi Code's own hook default; kept explicit so an edit
// is visible.
const HOOK_TIMEOUT = 30;
// Written into the user's own config.toml, so these
// strings are a wire format: how an existing install is
// recognised for idempotent replacement. Changing them
// would append a second block.
const MANAGED_START = '# cowork-flow: kimi hook start. Managed by "cowork-flow install-kimi-hook"; edits inside this block are replaced.';
const MANAGED_END = '# cowork-flow: kimi hook end.';

// Rendered by `host add`/`host remove`. No --force:
// installing always rewrites the shim and its managed
// block, so the flag would be a no-op; the helper rejects
// it for this installer.
export const FLAGS = ['--dry-run', '--uninstall'];


function getKimiHome() {
  return process.env.KIMI_CODE_HOME || join(homedir(), '.kimi-code');
}


async function readIfExists(file) {
  try {
    return await readFile(file, 'utf8');
  } catch {
    return null;
  }
}


/**
 * Kimi Code's user-level config.toml, holding the
 * `[[hooks]]` rows.
 */
function configFile(home) {
  return join(home, 'config.toml');
}


/**
 * Transport shim installed beside the config, spawned as
 * `node <home>/hooks/cowork-flow-inject.mjs` from every
 * session.
 */
function shimDest(home) {
  return join(home, 'hooks', SHIM_NAME);
}


/**
 * Version marker for the installed hook, written next to
 * the shim. The installed files live outside any project,
 * so nothing else records which release put them there;
 * doctor reads this to tell an up-to-date install from one
 * that predates the project runtime.
 */
function markerDest(home) {
  return join(home, 'hooks', MARKER_FILE);
}


/**
 * One `[[hooks]]` row piping every UserPromptSubmit
 * payload into the shim. Kimi Code allows exactly four
 * hook fields (event, matcher, command, timeout) and
 * rejects the whole config when a row carries anything
 * else, so the row stays minimal; `matcher` is omitted on
 * purpose, since omitted means "match every prompt". Paths
 * are quoted because a Kimi Code home may contain spaces.
 */
function hookBlock(home) {
  const command = 'node "' + shimDest(home) + '"';
  return [
    MANAGED_START,
    '[[hooks]]',
    'event = ' + JSON.stringify(HOOK_EVENT),
    'command = ' + JSON.stringify(command),
    'timeout = ' + HOOK_TIMEOUT,
    MANAGED_END
  ].join('\n');
}


/**
 * End of the `[[hooks]]` row starting at `start`: the next
 * table header, the next row of the same array, or the end
 * of file. Trailing blank lines stay outside the range so
 * removal leaves them.
 */
function hookRowEnd(lines, start) {
  let end = start + 1;
  while (end < lines.length) {
    const trimmed = lines[end].trim();
    if (trimmed === '[[hooks]]' || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      break;
    }
    end += 1;
  }
  while (end > start + 1 && lines[end - 1].trim() === '') {
    end -= 1;
  }
  return end;
}


/**
 * Locate the managed block inside the config text.
 *
 * The config is edited as text on purpose: a TOML
 * round-trip would rewrite every pretty-printed entry of
 * the user's own config, and the file must stay
 * byte-stable outside the block. Marker comments take
 * precedence, so a block whose row was edited is still
 * removed; without markers the ownership signal is a
 * `[[hooks]]` row whose command names this shim. Null when
 * neither exists.
 */
function findManagedBlock(text, home) {
  const lines = text.split('\n');
  const marked = lines.findIndex((line) => line.trim() === MANAGED_START);
  if (marked !== -1) {
    let end = marked + 1;
    while (end < lines.length && lines[end].trim() !== MANAGED_END) {
      end += 1;
    }
    return { start: marked, end: Math.min(end + 1, lines.length) };
  }
  const owns = shimDest(home).replace(/\\/g, '/');
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].trim() !== '[[hooks]]') {
      continue;
    }
    const end = hookRowEnd(lines, index);
    const row = lines.slice(index, end).join('\n');
    if (row.includes(MANAGED_START) || row.replace(/\\/g, '/').includes(owns)) {
      return { start: index, end };
    }
  }
  return null;
}


function withBlock(text, home) {
  const block = hookBlock(home).split('\n');
  const range = findManagedBlock(text, home);
  if (range !== null) {
    const lines = text.split('\n');
    if (lines.slice(range.start, range.end).join('\n') === block.join('\n')) {
      return { text, changed: false, existed: true };
    }
    return {
      text: lines.slice(0, range.start).concat(block).concat(lines.slice(range.end)).join('\n'),
      changed: true,
      existed: true
    };
  }
  const base = text.replace(/\s+$/, '');
  const appended = base === '' ? block.join('\n') : base + '\n\n' + block.join('\n');
  return { text: appended + '\n', changed: true, existed: false };
}


function withoutBlock(text, home) {
  const range = findManagedBlock(text, home);
  if (range === null) {
    return { text, changed: false };
  }
  const lines = text.split('\n');
  const kept = lines.slice(0, range.start).concat(lines.slice(range.end));
  const body = kept.join('\n').replace(/^\n+/, '').replace(/\s+$/, '');
  if (body === '') {
    // An empty file left behind would be a config that
    // only ever held this hook.
    return { text: '', changed: true };
  }
  return { text: body + '\n', changed: true };
}


/**
 * Compact line preview for --dry-run: every line that
 * differs plus its two neighbours either side, so the
 * operator sees where the block lands without a full-file
 * dump.
 */
function previewDiff(before, after) {
  // A trailing newline is a line terminator, not an extra
  // empty line; without this the preview reports a phantom
  // last-line change.
  const toLines = (text) => {
    if (text === '') {
      return [];
    }
    return (text.endsWith('\n') ? text.slice(0, -1) : text).split('\n');
  };
  const left = toLines(before);
  const right = toLines(after);
  const total = Math.max(left.length, right.length);
  const shown = new Set();
  for (let index = 0; index < total; index += 1) {
    if (left[index] !== right[index]) {
      for (let offset = -2; offset <= 2; offset += 1) {
        if (index + offset >= 0 && index + offset < total) {
          shown.add(index + offset);
        }
      }
    }
  }
  const lines = [];
  let previous = -1;
  for (const index of [...shown].sort((a, b) => a - b)) {
    if (previous !== -1 && index > previous + 1) {
      lines.push('  ...');
    }
    const marker = left[index] === right[index] ? '  ' : '+ ';
    lines.push('  ' + (index + 1) + ' ' + marker + (right[index] ?? ''));
    previous = index;
  }
  return lines;
}


function printDryRunUninstall({ config, home, shim, marker, before }) {
  const result = before === null ? { changed: false } : withoutBlock(before, home);
  console.log('[dry-run] Would uninstall Kimi Code context hook:');
  console.log(
    '  Config: ' + config
      + (before === null
        ? ' (absent; nothing to remove)'
        : (result.changed ? ' (managed block found)' : ' (no managed block)'))
  );
  console.log('  Remove shim: ' + shim);
  console.log('  Remove marker: ' + marker);
}


function printDryRunInstall({ config, home, shim, marker, before }) {
  console.log('[dry-run] Would install Kimi Code context hook:');
  console.log('  Shim: ' + SHIM_SRC + ' -> ' + shim);
  console.log('  Marker: ' + marker);
  if (before === null) {
    console.log('  Create config: ' + config);
    for (const line of previewDiff('', hookBlock(home))) {
      console.log(line);
    }
    return;
  }
  const result = withBlock(before, home);
  if (!result.changed) {
    console.log('  Config: ' + config + ' (managed block already up to date)');
    return;
  }
  console.log('  Config: ' + config + (result.existed ? ' (update managed block)' : ' (append managed block)'));
  for (const line of previewDiff(before, result.text)) {
    console.log(line);
  }
}


async function uninstallHook({ config, home, shim, marker }) {
  const before = await readIfExists(config);
  if (before === null) {
    console.log('No Kimi Code config at ' + config + '; nothing to uninstall.');
  } else {
    const result = withoutBlock(before, home);
    if (!result.changed) {
      console.log('No managed hook block found in ' + config + '.');
    } else if (result.text === '') {
      await rm(config, { force: true });
      console.log('✓ Kimi Code context hook removed; ' + config + ' held nothing else and was deleted.');
    } else {
      await writeFile(config, result.text, 'utf8');
      console.log('✓ Kimi Code context hook removed from ' + config);
    }
  }
  const hadShim = await pathExists(shim);
  await rm(shim, { force: true });
  if (hadShim) {
    console.log('✓ Removed hook shim ' + shim);
  }
  const hadMarker = await pathExists(marker);
  await rm(marker, { force: true });
  if (hadMarker) {
    console.log('✓ Removed version marker ' + marker);
  }
}


async function installHook({ config, home, shim, marker }) {
  const { version } = await readPackageInfo();
  await mkdir(dirname(shim), { recursive: true });
  await copyFile(SHIM_SRC, shim);
  await writeFile(
    marker,
    `${JSON.stringify({ version, installedAt: new Date().toISOString() }, null, 2)}\n`,
    'utf8'
  );
  const before = (await readIfExists(config)) ?? '';
  const result = withBlock(before, home);
  if (result.changed) {
    await writeFile(config, result.text, 'utf8');
  }

  console.log('✓ cowork-flow Kimi Code hook shim installed to ' + shim);
  console.log('  Recorded version ' + version + ' in ' + marker);
  console.log(
    '  Registered UserPromptSubmit hook in ' + config
      + (result.changed ? (result.existed ? ' (block updated)' : ' (block appended)') : ' (already up to date)')
  );
  console.log('  Start a new Kimi Code session (or reload the config) for the hook to load.');
  console.log('  Note: injection happens once per submitted prompt; other Kimi Code events cannot inject.');
}


/**
 * Install (or uninstall) the user-level Kimi Code
 * context-injection hook. Kimi Code reads hooks only from
 * $KIMI_CODE_HOME/config.toml, so the shim sits under the
 * same home and every session in every project invokes it;
 * the shim exits silently outside cowork-flow projects.
 */
export async function runInstallKimiHook(args = []) {
  const { dryRun, uninstall } = parseInstallArgs(args, { force: false });

  if (!(await pathExists(SHIM_SRC))) {
    throw new Error('Kimi Code hook shim missing at ' + SHIM_SRC + '. Reinstall cowork-flow.');
  }

  const home = getKimiHome();
  const config = configFile(home);
  const shim = shimDest(home);
  const marker = markerDest(home);

  if (dryRun) {
    const before = await readIfExists(config);
    if (uninstall) {
      printDryRunUninstall({ config, home, shim, marker, before });
    } else {
      printDryRunInstall({ config, home, shim, marker, before });
    }
    return;
  }

  if (uninstall) {
    await uninstallHook({ config, home, shim, marker });
    return;
  }

  await installHook({ config, home, shim, marker });
}
