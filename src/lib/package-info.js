import { execFile, spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
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

function windowsNpmCli(env = process.env) {
  if (typeof env.npm_execpath === 'string' && env.npm_execpath.trim()) {
    return env.npm_execpath;
  }
  return join(dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js');
}

export function npmCommand(platform = process.platform) {
  return platform === 'win32' ? process.execPath : 'npm';
}

export function npmCommandArgs(args, platform = process.platform, env = process.env) {
  return platform === 'win32' ? [windowsNpmCli(env), ...args] : args;
}

export async function fetchLatestVersion(packageName = 'cowork-flow') {
  const args = ['view', packageName, 'version'];
  const result = await execFileAsync(npmCommand(), npmCommandArgs(args), {
    encoding: 'utf8'
  });
  return result.stdout.trim();
}

export async function runGlobalInstall(packageSpec = 'cowork-flow@latest') {
  return new Promise((resolvePromise, rejectPromise) => {
    const args = ['install', '-g', packageSpec];
    const child = spawn(npmCommand(), npmCommandArgs(args), {
      stdio: 'inherit'
    });
    child.on('error', rejectPromise);
    child.on('close', (code) => resolvePromise(code ?? 1));
  });
}
