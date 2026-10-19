#!/usr/bin/env node
// Pre-flight gates that are not test suites: this checkout is its own
// cowork-flow instance, so the self-instance must not have drifted from
// template/, neither may the live copies `sync --force` rewrites, and doctor
// must report no error-severity issue.
//
// A Node script rather than a shell one on purpose: release:check is expected
// to run on Windows as well, and a POSIX-only step would be a gate nobody
// there can run.
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));
const selfInstanceDir = join(repoRoot, '.cowork-flow');
const runnerPath = join(
  selfInstanceDir,
  process.platform === 'win32' ? 'run.cmd' : 'run'
);

// Keys whose contents mean the self-instance and template/ disagree.
const DRIFT_KEYS = ['wouldCopy', 'wouldRemoveObsolete', 'hostAssetRefresh'];
// Keys that are facts to report rather than failures. A retained retirement
// (wouldKeep) is a decision the user owes, not a defect: source:refresh leaves
// unverifiable content alone by design, and failing the release on it would
// force deleting something sync cannot prove it owns.
const REPORT_KEYS = ['wouldSkipProtected', 'wouldKeep', 'pendingRecovery', 'warnings'];

function entries(readiness, key) {
  const value = readiness ? readiness[key] : null;
  return Array.isArray(value) ? value : [];
}

export function driftVerdict(readiness) {
  const drifted = DRIFT_KEYS.filter((key) => entries(readiness, key).length > 0);
  const notes = REPORT_KEYS.filter((key) => entries(readiness, key).length > 0);
  if (drifted.length === 0) {
    return {
      name: 'self-instance-drift',
      status: 'pass',
      detail: notes.length === 0
        ? 'self-instance matches template/'
        : `self-instance matches template/ (reported: ${notes.join(', ')})`
    };
  }
  const counts = drifted.map((key) => `${key}=${entries(readiness, key).length}`);
  return {
    name: 'self-instance-drift',
    status: 'fail',
    detail: `run \`npm run source:refresh\` first; drifted: ${counts.join(' ')}`
  };
}

// The self-instance is not the only tree a release overwrites: step 5 runs
// `sync --force`, which also rewrites the gitignored live copies (.claude/**,
// .codex/**, .agents/skills) — and `dev refresh` never looks at those. This
// verdict reads the same readiness shape from `project sync . --dry-run`, so a
// drifted live copy fails the release instead of being silently overwritten.
const ASSET_DRIFT_KEYS = ['wouldCopy', 'wouldRemoveObsolete'];
const ASSET_REPORT_KEYS = ['wouldSkipProtected', 'wouldKeep', 'warnings'];

export function assetDriftVerdict(readiness) {
  // A missing key is not "no drift": this gate reads the report shape, so a
  // renamed key would otherwise turn every future drift into a silent pass.
  // Fail with the shape it expected instead.
  const missing = ASSET_DRIFT_KEYS.filter((key) => !Array.isArray(readiness?.[key]));
  if (missing.length > 0) {
    return {
      name: 'self-instance-asset-drift',
      status: 'fail',
      detail: `project sync . --dry-run readiness is missing ${missing.join(', ')}; `
        + 'the report shape changed and this gate cannot judge drift'
    };
  }
  const drifted = ASSET_DRIFT_KEYS.filter((key) => entries(readiness, key).length > 0);
  const notes = ASSET_REPORT_KEYS.filter((key) => entries(readiness, key).length > 0);
  if (drifted.length === 0) {
    return {
      name: 'self-instance-asset-drift',
      status: 'pass',
      detail: notes.length === 0
        ? 'project assets match their template sources'
        : `project assets match their template sources (reported: ${notes.join(', ')})`
    };
  }
  const names = ASSET_DRIFT_KEYS.flatMap((key) => entries(readiness, key))
    .map((entry) => entry?.path)
    .filter(Boolean)
    .slice(0, 5);
  const counts = drifted.map((key) => `${key}=${entries(readiness, key).length}`);
  return {
    name: 'self-instance-asset-drift',
    status: 'fail',
    detail: `run \`node bin/cowork-flow.js project sync .\` first; drifted: `
      + `${counts.join(' ')}${names.length > 0 ? ` (${names.join(', ')})` : ''}`
  };
}

export function doctorVerdict(report) {
  const errors = Array.isArray(report?.errors) ? report.errors : [];
  if (report?.ok === true && errors.length === 0) {
    return { name: 'doctor', status: 'pass', detail: 'no error-severity issue' };
  }
  const codes = errors
    .map((issue) => (issue && (issue.code || issue.message)) || 'unknown')
    .slice(0, 5);
  return {
    name: 'doctor',
    status: 'fail',
    detail: `doctor reported ${errors.length} error(s): ${codes.join(', ') || 'ok=false'}`
  };
}

export function skippedVerdicts(reason) {
  return [
    { name: 'self-instance-drift', status: 'skip', detail: reason },
    { name: 'self-instance-asset-drift', status: 'skip', detail: reason },
    { name: 'doctor', status: 'skip', detail: reason }
  ];
}

function spawnNode(args) {
  return spawnSync(process.execPath, args, {
    cwd: repoRoot,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }
  });
}

function spawnRunner(args) {
  const options = {
    cwd: repoRoot,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }
  };
  // Windows cannot execute the .cmd entry without a shell, and a shell needs
  // the command as one already-quoted string — passing an args array alongside
  // `shell: true` is the shape Node deprecates. Every caller passes fixed flags.
  if (process.platform === 'win32') {
    return spawnSync(`"${runnerPath}" ${args.join(' ')}`, { ...options, shell: true });
  }
  return spawnSync(runnerPath, args, options);
}

function parseReadiness(stdout, command) {
  const match = /readiness=(\{.*\})/.exec(String(stdout ?? ''));
  if (match === null) {
    throw new Error(`${command} printed no readiness report`);
  }
  return JSON.parse(match[1]);
}

function parseJson(stdout) {
  return JSON.parse(String(stdout ?? ''));
}

function failureVerdict(name, detail) {
  return { name, status: 'fail', detail };
}

// doctor prints its JSON on stdout and exits 1 on an error-severity issue, so a
// nonzero status is not by itself a diagnosis; keep both streams.
function streamDetail(result) {
  return [result.stderr, result.stdout]
    .map((stream) => String(stream ?? '').trim())
    .filter((text) => text.length > 0)
    .join(' ')
    .slice(0, 400);
}

function collectVerdicts() {
  const driftRun = spawnNode(['bin/cowork-flow.js', 'dev', 'refresh', '--dry-run']);
  if (driftRun.status !== 0) {
    return [failureVerdict('self-instance-drift', `dev refresh --dry-run exited ${driftRun.status}: ${streamDetail(driftRun)}`)];
  }
  let drift;
  try {
    drift = driftVerdict(parseReadiness(driftRun.stdout, 'dev refresh --dry-run'));
  } catch (error) {
    return [failureVerdict('self-instance-drift', error.message)];
  }

  const assetRun = spawnNode(['bin/cowork-flow.js', 'project', 'sync', '.', '--dry-run']);
  let assets;
  if (assetRun.status !== 0) {
    assets = failureVerdict('self-instance-asset-drift', `project sync . --dry-run exited ${assetRun.status}: ${streamDetail(assetRun)}`);
  } else {
    try {
      assets = assetDriftVerdict(parseReadiness(assetRun.stdout, 'project sync . --dry-run'));
    } catch (error) {
      assets = failureVerdict('self-instance-asset-drift', error.message);
    }
  }

  const doctorRun = spawnRunner(['doctor', '--all', '--json']);
  let doctor;
  if (doctorRun.status !== 0) {
    doctor = failureVerdict('doctor', `doctor --all --json exited ${doctorRun.status}: ${streamDetail(doctorRun)}`);
  } else {
    try {
      doctor = doctorVerdict(parseJson(doctorRun.stdout));
    } catch (error) {
      doctor = failureVerdict('doctor', `doctor --all --json printed unparsable output: ${error.message}`);
    }
  }
  return [drift, assets, doctor];
}

export function main() {
  if (!existsSync(selfInstanceDir)) {
    // A fresh clone has no self-instance to compare against; saying so beats
    // both a false failure and a silent pass.
    for (const verdict of skippedVerdicts('no .cowork-flow/ in this checkout (fresh clone)')) {
      process.stdout.write(`release-gates: ${verdict.name} skip — ${verdict.detail}\n`);
    }
    return 0;
  }

  const verdicts = collectVerdicts();
  for (const verdict of verdicts) {
    process.stdout.write(`release-gates: ${verdict.name} ${verdict.status} — ${verdict.detail}\n`);
  }
  const failed = verdicts.filter((verdict) => verdict.status === 'fail');
  if (failed.length > 0) {
    process.stderr.write(`release-gates: ${failed.length} gate(s) failed\n`);
    return 1;
  }
  return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main();
}
