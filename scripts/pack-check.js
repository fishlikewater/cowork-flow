#!/usr/bin/env node
import { execFile } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';

import {
  npmCommand,
  npmCommandArgs
} from '../src/lib/package-info.js';
import { packageRoot } from '../src/lib/paths.js';
import { checkTemplateSync } from '../src/lib/template-sync-gate.js';

const execFileAsync = promisify(execFile);
const FORBIDDEN_PREFIXES = ['template/.cowork-flow/.runtime/'];

function packFilesFrom(stdout) {
  const [pack] = JSON.parse(stdout);
  if (!Array.isArray(pack?.files)) {
    throw new Error('npm pack --dry-run --json returned no file list');
  }
  return pack.files
    .map((file) => file?.path)
    .filter((path) => typeof path === 'string' && path.trim());
}

function forbiddenPackFiles(files) {
  return files.filter((path) =>
    FORBIDDEN_PREFIXES.some((prefix) => path.startsWith(prefix))
  );
}

const npmCache = await mkdtemp(join(tmpdir(), 'cowork-flow-npm-cache-'));

try {
  const npmArgs = ['pack', '--dry-run', '--json'];
  const result = await execFileAsync(npmCommand(), npmCommandArgs(npmArgs), {
    cwd: packageRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      npm_config_cache: npmCache,
    },
  });
  process.stdout.write(result.stdout);
  if (result.stderr) {
    process.stderr.write(result.stderr);
  }

  const files = packFilesFrom(result.stdout);
  const forbidden = forbiddenPackFiles(files);
  const sync = await checkTemplateSync({ packageRoot });
  if (forbidden.length > 0) {
    process.stderr.write('Forbidden package paths detected:\n');
    for (const path of forbidden) {
      process.stderr.write(`- ${path}\n`);
    }
    process.exitCode = 1;
  } else if (!sync.ok) {
    process.stderr.write('Template sync drift detected:\n');
    for (const drift of sync.drifts) {
      process.stderr.write(`- ${drift.path} -> ${drift.templatePath}: ${drift.reason}\n`);
    }
    process.exitCode = 1;
  } else {
    process.stdout.write(`template-sync ok: checked ${sync.checked} mirrored files\n`);
    process.stdout.write(`pack-check ok: inspected ${files.length} files\n`);
  }
} catch (error) {
  if (typeof error?.stdout === 'string' && error.stdout) {
    process.stdout.write(error.stdout);
  }
  if (typeof error?.stderr === 'string' && error.stderr) {
    process.stderr.write(error.stderr);
  }
  process.stderr.write(`${error?.message ?? String(error)}\n`);
  process.exitCode = 1;
} finally {
  await rm(npmCache, { recursive: true, force: true });
}
