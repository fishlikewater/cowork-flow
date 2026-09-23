import { resolve } from 'node:path';

import {
  applyPlan,
  buildReadinessReport,
  buildSyncPlan,
  detectInstalledPlatforms,
  formatReadinessReport,
  summarizePlan
} from '../lib/copy-template.js';
import { readPackageInfo } from '../lib/package-info.js';
import { formatPlatformList } from '../lib/platforms.js';
import { parseFlags } from '../lib/cli-flags.js';

function parseSyncArgs(args) {
  const { flags, positionals } = parseFlags(args, {
    boolean: ['--dry-run', '--force'],
    positional: { min: 0, max: 1, name: '[target]' }
  });
  return {
    dryRun: Boolean(flags['--dry-run']),
    force: Boolean(flags['--force']),
    target: positionals[0] === undefined ? process.cwd() : resolve(positionals[0])
  };
}

export async function runSync(args, { io, fileSystem }) {
  const options = parseSyncArgs(args);
  const packageInfo = await readPackageInfo();
  const platforms = await detectInstalledPlatforms(options.target);
  const plan = await buildSyncPlan(options.target, {
    force: options.force,
    platforms,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun, fileSystem });
  io.writeOut(summarizePlan(plan, options.dryRun));
  if (options.dryRun) {
    const readiness = await buildReadinessReport(plan, { fileSystem });
    io.writeOut(formatReadinessReport(readiness));
  }
  io.writeOut(`Platforms: ${platforms.length > 0 ? formatPlatformList(platforms) : 'none'}\n`);
  return 0;
}
