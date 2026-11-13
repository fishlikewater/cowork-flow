#!/usr/bin/env node
// Extracts one version's section from CHANGELOG.md as GitHub Release notes:
// the github-release job in .github/workflows/publish.yml pipes this script's
// stdout into `gh release create --notes-file`.
//
// Pure function plus main(), mirroring scripts/release-gates.js: extraction is
// testable without a CLI, and main() owns argument validation, file reading,
// stream output and the exit code.
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));

export function extractReleaseNotes(changelogText, version) {
  // The closing bracket keeps the match exact: `## [1.2.3]` must not hit
  // `## [1.2.30]`.
  const heading = `## [${version}]`;
  const lines = changelogText.split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith(heading));
  if (start === -1) {
    throw new Error(`no entry for version ${version} in CHANGELOG.md`);
  }
  const section = [];
  for (let index = start + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.startsWith('## [') || /^\[[^\]]+\]:/.test(line)) {
      break;
    }
    section.push(line);
  }
  while (section.length > 0 && section[0].trim() === '') {
    section.shift();
  }
  while (section.length > 0 && section[section.length - 1].trim() === '') {
    section.pop();
  }
  return section.join('\n');
}

export function main() {
  const version = process.argv[2];
  if (!version) {
    process.stderr.write('release-notes: usage: node scripts/release-notes.js <version>\n');
    return 1;
  }
  try {
    const changelogText = readFileSync(join(repoRoot, 'CHANGELOG.md'), 'utf8');
    process.stdout.write(`${extractReleaseNotes(changelogText, version)}\n`);
    return 0;
  } catch (error) {
    process.stderr.write(`release-notes: ${error.message}\n`);
    return 1;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main();
}