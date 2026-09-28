import { access, readFile } from 'node:fs/promises';

import { parseFlags } from './cli-flags.js';


// Read a JSON document, or null when it is missing or
// malformed. The ownership guards read "not ours" out of
// that one answer.
export async function readJsonFile(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch {
    return null;
  }
}


export async function pathExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}


// `--prune-old` and any future extra flag land under their
// camelCase name, so the parsed shape follows the flag's
// own spelling.
function flagFieldName(flag) {
  return flag.replace(/^--/, '').replace(/-([a-z])/g, (_, char) => char.toUpperCase());
}


// The argv shape every installer accepts. kimi-code's hook
// passes force: false: it rewrites its shim
// unconditionally and therefore has no --force to accept.
export function parseInstallArgs(args, { force = true, extraBoolean = [] } = {}) {
  const accepted = ['--dry-run', '--uninstall', ...(force ? ['--force'] : []), ...extraBoolean];
  const { flags } = parseFlags(args, { boolean: accepted });
  return {
    dryRun: Boolean(flags['--dry-run']),
    ...(force ? { force: Boolean(flags['--force']) } : {}),
    ...Object.fromEntries(
      extraBoolean.map((name) => [flagFieldName(name), Boolean(flags[name])])
    ),
    uninstall: Boolean(flags['--uninstall'])
  };
}
