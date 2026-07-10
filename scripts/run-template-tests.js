#!/usr/bin/env node
import { resolve } from 'node:path';

import {
  parseTemplateTestOptions,
  runTemplateTests
} from './template-test-runner.js';

const runner = process.platform === 'win32'
  ? resolve('template', '.cowork-flow', 'run.cmd')
  : resolve('template', '.cowork-flow', 'run');
const tempRoot = resolve('.tmp', 'template-tests');

try {
  const options = parseTemplateTestOptions();
  process.exitCode = await runTemplateTests({
    ...options,
    runner,
    tempRoot
  });
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
