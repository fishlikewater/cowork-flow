import { resolve } from 'node:path';

import {
  applyPlan,
  buildReadinessReport,
  buildSourceCheckoutRefreshPlan,
  formatReadinessReport,
  summarizePlan
} from '../lib/copy-template.js';

function parseSourceRefreshArgs(args) {
  const options = { dryRun: false, target: process.cwd() };
  for (const arg of args) {
    if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg.startsWith('--')) {
      throw new Error(`Unknown source-refresh option: ${arg}`);
    } else {
      options.target = resolve(arg);
    }
  }
  return options;
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
