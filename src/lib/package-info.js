import { execFile, spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { promisify } from 'node:util';

import { packageRoot } from './paths.js';

const execFileAsync = promisify(execFile);

export async function readPackageInfo() {
  const raw = await readFile(join(packageRoot, 'package.json'), 'utf8');
  return JSON.parse(raw);
}

export function compareVersions(left, right) {
  const leftParts = left.split('.').map((part) => Number.parseInt(part, 10));
  const rightParts = right.split('.').map((part) => Number.parseInt(part, 10));
  const length = Math.max(leftParts.length, rightParts.length);

  for (let index = 0; index < length; index += 1) {
    const leftValue = Number.isFinite(leftParts[index]) ? leftParts[index] : 0;
    const rightValue = Number.isFinite(rightParts[index]) ? rightParts[index] : 0;
    if (leftValue < rightValue) {
      return -1;
    }
    if (leftValue > rightValue) {
      return 1;
    }
  }

  return 0;
}

export async function fetchLatestVersion(packageName = 'cowork-flow') {
  const result = await execFileAsync('npm', ['view', packageName, 'version'], {
    encoding: 'utf8'
  });
  return result.stdout.trim();
}

export async function runGlobalInstall(packageSpec = 'cowork-flow@latest') {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn('npm', ['install', '-g', packageSpec], {
      stdio: 'inherit'
    });
    child.on('error', rejectPromise);
    child.on('close', (code) => resolvePromise(code ?? 1));
  });
}
