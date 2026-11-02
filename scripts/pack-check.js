#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { mkdirSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

function bytecodeOffenders(root) {
  const offenders = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === '__pycache__') {
          offenders.push(path);
        } else {
          walk(path);
        }
      } else if (entry.name.endsWith('.pyc')) {
        offenders.push(path);
      }
    }
  };
  walk(root);
  return offenders;
}

const offenders = bytecodeOffenders('template');
if (offenders.length > 0) {
  process.stderr.write(
    `pack:check found Python bytecode in the shipped template tree:\n${offenders.join('\n')}\n`
  );
  process.exit(1);
}

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
