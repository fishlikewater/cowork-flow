import { copyFile, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { homedir } from 'node:os';

import { parseInstallArgs, pathExists } from '../lib/install-support.js';
import { packageRoot } from '../lib/paths.js';
import { readPackageInfo } from '../lib/package-info.js';
import { removeManagedBlock, upsertManagedBlock } from '../lib/payload-install.js';

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
const HOOK_START_MARK = '# cowork-flow: kimi hook start.';

// Rendered by `host add`/`host remove`. No --force:
// installing always rewrites the shim and its managed
// block, so the flag would be a no-op; the helper rejects
// it for this installer.
export const FLAGS = ['--dry-run', '--uninstall'];


function getKimiHome(env = process.env) {
  return env.KIMI_CODE_HOME || join(homedir(), '.kimi-code');
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


// A TOML basic string escapes every backslash, so a Windows install path
// reaches the config as `C:\\Users\\...`. A plain backslash-to-slash pass
// turns each escaped pair into `//`, which never matches the single-slash
// form of the same path — the row would go unrecognised and a second install
// would append instead of adopting it. Collapse runs of either separator so
// both spellings compare equal.
function normalizeSeparators(text) {
  return text.replace(/[\\/]+/g, '/');
}


/**
 * Locate the managed block inside the config's lines.
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
function locateBlock(lines, home) {
  const marked = lines.findIndex((line) => line.trim() === MANAGED_START);
  if (marked !== -1) {
    let end = marked + 1;
    while (end < lines.length && lines[end].trim() !== MANAGED_END) {
      end += 1;
    }
    return { start: marked, end: Math.min(end + 1, lines.length) };
  }
  const owns = normalizeSeparators(shimDest(home));
  for (let index = 0; index < lines.length; index += 1) {
    if (lines[index].trim() !== '[[hooks]]') {
      continue;
    }
    const end = hookRowEnd(lines, index);
    const row = lines.slice(index, end).join('\n');
    if (row.includes(MANAGED_START) || normalizeSeparators(row).includes(owns)) {
      return { start: index, end };
    }
  }
  return null;
}


// The TOML append form: one blank line before a fresh block
// when the file already has content, none when it does not.
function appendBlock(text, block) {
  const base = text.replace(/\s+$/, '');
  return (base === '' ? block : base + '\n\n' + block) + '\n';
}


// Removal folds the seam: surrounding blank lines go, the
// trailing newline stays, and an emptied file stays empty —
// a config that only ever held this hook leaves nothing.
function collapseRemoval(body) {
  const trimmed = body.replace(/^\n+/, '').replace(/\s+$/, '');
  return trimmed === '' ? '' : trimmed + '\n';
}


function withBlock(text, home) {
  return upsertManagedBlock(text, {
    locate: (lines) => locateBlock(lines, home),
    block: hookBlock(home),
    append: appendBlock
  });
}


function withoutBlock(text, home) {
  return removeManagedBlock(text, {
    locate: (lines) => locateBlock(lines, home),
    collapse: collapseRemoval
  });
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


// Read-only installed-state facts for `host inspect`.
export async function inspectInstalledState({ env = process.env } = {}) {
  const home = getKimiHome(env);
  const config = configFile(home);
  const shim = shimDest(home);
  const marker = markerDest(home);
  const configText = await readIfExists(config);
  if (configText === null) {
    return {
      status: 'missing',
      version: null,
      payloadPath: shim,
      detailPath: config,
      registeredSource: config,
      enabled: null,
      reason: 'config file is absent'
    };
  }
  if (!configText.includes(HOOK_START_MARK)) {
    return {
      status: 'missing',
      version: null,
      payloadPath: shim,
      detailPath: config,
      registeredSource: config,
      enabled: null,
      reason: 'hook block is absent'
    };
  }
  if (!(await pathExists(shim))) {
    return {
      status: 'broken',
      version: null,
      payloadPath: shim,
      detailPath: shim,
      registeredSource: config,
      enabled: true,
      reason: 'shim is missing'
    };
  }
  const markerDocument = await readIfExists(marker);
  if (markerDocument === null) {
    return {
      status: 'broken',
      version: null,
      payloadPath: shim,
      detailPath: marker,
      registeredSource: config,
      enabled: true,
      reason: 'version marker is missing'
    };
  }
  let version = null;
  try {
    version = JSON.parse(markerDocument).version ?? null;
  } catch {
    version = null;
  }
  if (typeof version !== 'string' || version === '') {
    return {
      status: 'broken',
      version: null,
      payloadPath: shim,
      detailPath: marker,
      registeredSource: config,
      enabled: true,
      reason: 'version marker is unreadable'
    };
  }
  return {
    status: 'installed',
    version,
    payloadPath: shim,
    detailPath: marker,
    registeredSource: config,
    enabled: true,
    reason: null
  };
}
