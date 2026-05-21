#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const npmCache = join(tmpdir(), 'cowork-flow-npm-cache');
mkdirSync(npmCache, { recursive: true });

const child = spawn('npm', ['pack', '--dry-run', '--json'], {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: {
    ...process.env,
    npm_config_cache: npmCache
  }
});

child.on('error', (error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});

child.on('close', (code) => {
  process.exitCode = code ?? 1;
});
