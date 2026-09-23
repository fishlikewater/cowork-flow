import { resolve } from 'node:path';

import {
  applyPlan,
  buildReadinessReport,
  buildSourceCheckoutRefreshPlan,
  formatReadinessReport,
  summarizePlan
} from '../lib/copy-template.js';

import { parseFlags } from '../lib/cli-flags.js';

function parseSourceRefreshArgs(args) {
  const { flags, positionals } = parseFlags(args, {
    boolean: ['--dry-run'],
    positional: { min: 0, max: 1, name: '[target]' }
  });
  return {
    dryRun: Boolean(flags['--dry-run']),
    target: positionals[0] === undefined ? process.cwd() : resolve(positionals[0])
  };
}

export async function runSourceRefresh(args, { io, fileSystem } = {}) {
  const options = parseSourceRefreshArgs(args);
  const plan = await buildSourceCheckoutRefreshPlan(options.target);

  await applyPlan(plan, { dryRun: options.dryRun, fileSystem });
  io.writeOut(summarizePlan(plan, options.dryRun));
  if (options.dryRun) {
    const readiness = await buildReadinessReport(plan, { fileSystem });
    io.writeOut(formatReadinessReport(readiness));
  }
  io.writeOut('Source checkout refresh: template/.cowork-flow -> .cowork-flow; template/skills -> host Skill replicas\n');
  if (!options.dryRun) {
    io.writeOut('Next check: ./.cowork-flow/run doctor --all --json\n');
  }
  return 0;
}
