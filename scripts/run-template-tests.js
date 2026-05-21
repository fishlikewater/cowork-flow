#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

const runner = process.platform === 'win32'
  ? resolve('template', '.cowork-flow', 'run.cmd')
  : resolve('template', '.cowork-flow', 'run');
const tempDir = resolve('.tmp', 'template-tests');

rmSync(tempDir, { recursive: true, force: true });
mkdirSync(tempDir, { recursive: true });

const child = spawn(
  runner,
  ['python', '-m', 'unittest', 'discover', 'tests', '-v'],
  {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: '1',
      TMP: tempDir,
      TEMP: tempDir,
      TMPDIR: tempDir
    }
  }
);

child.on('error', (error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});

child.on('close', (code) => {
  rmSync(tempDir, { recursive: true, force: true });
  process.exitCode = code ?? 1;
});
