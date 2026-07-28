#!/usr/bin/env node
import { resolve } from 'node:path';

import {
  createTemplateTestTempRoot,
  parseTemplateTestOptions,
  runTemplateTests
} from './template-test-runner.js';

const runner = process.platform === 'win32'
  ? resolve('template', '.cowork-flow', 'run.cmd')
  : resolve('template', '.cowork-flow', 'run');
const tempRoot = createTemplateTestTempRoot();

try {
  const options = parseTemplateTestOptions(process.env, process.argv.slice(2));
  process.exitCode = await runTemplateTests({
    ...options,
    runner,
    tempRoot
  });
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
