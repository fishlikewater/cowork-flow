import { cp, mkdir, readdir, rmdir, rm } from 'node:fs/promises';
import { dirname } from 'node:path';

import { pathExists } from './install-support.js';


// The payload-directory skeleton: claude-code, kimi-code and
// opencode materialize a payload under a host home and walk
// one phase order — header, ownership guard, dry-run preview,
// materialize, report. `label` fills the sentences all three
// share; the hooks carry whatever a host does differently
// (`onForeign: false` silences the forced-overwrite note).
export async function installPayloadDir({
  target,
  source,
  label,
  displaySource = source,
  displayTarget = target,
  sourceKind = 'Plugin',
  dryRun,
  force,
  ownsInstall,
  onExisting,
  onForeign,
  onPreview,
  onInstalled,
  onDone
}) {
  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow ${label}:`);
  console.log(`  ${sourceKind}: ${displaySource} -> ${displayTarget}`);

  if (await pathExists(target)) {
    const ours = await ownsInstall();
    // The guard runs before the dry-run exit too: a preview
    // that promises an install the real run refuses is
    // worse than none.
    if (!ours && !force) {
      throw new Error(
        `${target} already exists and is not the cowork-flow plugin. `
        + 'Use --force to overwrite it, or remove it yourself first.'
      );
    }
    if (!ours && onForeign !== false) {
      console.log(`${target} is not the cowork-flow plugin; overwriting it anyway (--force).`);
    }
    if (onExisting && (await onExisting(ours))) {
      return 0;
    }
  }

  if (dryRun) {
    if (onPreview) {
      onPreview();
    }
    return 0;
  }

  await mkdir(dirname(target), { recursive: true });
  await rm(target, { recursive: true, force: true });
  await cp(source, target, { recursive: true });
  if (onInstalled) {
    await onInstalled();
  }

  console.log(`✓ cowork-flow ${label} installed to ${displayTarget}`);
  if (onDone) {
    onDone();
  }
  return 0;
}


// The "not ours, and --force was not given" refusal, built
// from the probe that failed to name the plugin: the manifest
// the folder should have carried, or the marker the file
// should have held.
export function foreignTargetRefusal({ target, probe, name, noun = 'folder' }) {
  return new Error(
    `${target} exists but is not the cowork-flow plugin (its ${probe} does not name `
    + `${name}). Refusing to delete a ${noun} this installer did not create; `
    + 'use --force to remove it anyway.'
  );
}


// The uninstall mirror: absent → statement and stop; the same
// ownership guard; dry-run; then the caller's own removal.
// `refusal()` builds the host's "not ours, and --force was
// not given" error.
export async function uninstallPayloadDir({
  target,
  label,
  displayTarget = target,
  dryRun,
  force,
  ownsInstall,
  exists,
  refusal,
  onPreview,
  remove
}) {
  const present = exists ? await exists() : await pathExists(target);
  if (!present) {
    console.log(`cowork-flow ${label} was not installed; nothing to remove at ${displayTarget}`);
    return 0;
  }
  const ours = await ownsInstall();
  if (!ours && !force) {
    throw refusal();
  }
  if (!ours) {
    console.log(`${target} is not the cowork-flow plugin; removing it anyway (--force).`);
  }
  if (dryRun) {
    onPreview();
    return 0;
  }
  await remove();
  return 0;
}


// After our own files are gone, a directory that only ever
// held them is a shell: remove it when it stands empty,
// leave it when it still holds someone else's files.
export async function pruneEmptyDir(dir) {
  try {
    if ((await readdir(dir)).length === 0) {
      await rmdir(dir);
      return true;
    }
  } catch {
    // Missing or non-empty: nothing to clean up either way.
  }
  return false;
}


// Managed-block text surgery, shared by kimi-hook and
// dsh-hook. Each writes one managed block into a
// user-maintained config file, with a host syntax of its own
// (a TOML [[hooks]] row group, a YAML patch entry), so each
// caller keeps its own locate-and-render; the mechanics
// around a located line range are the same for both.
//
// `locate(lines)` returns the half-open line range
// `{ start, end }` of the managed block, or null.

// Replace the located block in place, or append it when
// absent. `append(text, block)` renders the host's append
// form. An already-matching block is a no-op, which is what
// keeps a repeated install idempotent.
export function upsertManagedBlock(text, { locate, block, append }) {
  const lines = text.split('\n');
  const range = locate(lines);
  if (range !== null) {
    if (lines.slice(range.start, range.end).join('\n') === block) {
      return { text, changed: false, existed: true };
    }
    return {
      text: lines
        .slice(0, range.start)
        .concat(block.split('\n'))
        .concat(lines.slice(range.end))
        .join('\n'),
      changed: true,
      existed: true
    };
  }
  return { text: append(text, block), changed: true, existed: false };
}


// Remove the located block. `collapse(text)` folds the
// joined remainder the host's way, or returns '' when
// nothing of the user's own file remains.
export function removeManagedBlock(text, { locate, collapse }) {
  const lines = text.split('\n');
  const range = locate(lines);
  if (range === null) {
    return { text, changed: false };
  }
  const kept = lines.slice(0, range.start).concat(lines.slice(range.end));
  return { text: collapse(kept.join('\n')), changed: true };
}
