#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';

const python = process.env.COWORK_FLOW_PYTHON || 'python3';
const pytestArgs = ['-m', 'pytest', 'tests/integration', '-q'];
const requirementMessage = [
  'npm run test:integration requires Python and pytest.',
  'Install pytest in your Python environment, then run:',
  `${python} ${pytestArgs.join(' ')}`
].join('\n');

const probe = spawnSync(python, ['-m', 'pytest', '--version'], {
  encoding: 'utf8',
  shell: process.platform === 'win32'
});

if (probe.error || probe.status !== 0) {
  process.stderr.write(`${requirementMessage}\n`);
  if (probe.stderr) {
    process.stderr.write(`\n${probe.stderr}`);
  }
  process.exit(1);
}

const child = spawn(python, pytestArgs, {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: {
    ...process.env,
    PYTHONDONTWRITEBYTECODE: '1'
  }
});

child.on('error', (error) => {
  process.stderr.write(`${requirementMessage}\n\n${error.message}\n`);
  process.exitCode = 1;
});

child.on('close', (code) => {
  process.exitCode = code ?? 1;
});
