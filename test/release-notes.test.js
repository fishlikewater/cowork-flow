import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';
import { extractReleaseNotes } from '../scripts/release-notes.js';

const scriptPath = join(packageRoot, 'scripts', 'release-notes.js');

// Unreleased plus three versions, newest first, with trailing link references:
// the same shape as the real CHANGELOG.md the release workflow consumes.
const changelogFixture = [
  '# Changelog',
  '',
  '## [Unreleased]',
  '',
  '### Added',
  '',
  '- upcoming work',
  '',
  '## [1.3.0] - 2026-01-03',
  '',
  '### Added',
  '',
  '- newest feature',
  '',
  '## [1.2.30] - 2026-01-02',
  '',
  '### Fixed',
  '',
  '- patch thirty',
  '',
  '## [1.2.3] - 2026-01-01',
  '',
  '### Fixed',
  '',
  '- patch three',
  '',
  '[Unreleased]: https://example.com/compare/v1.3.0...HEAD',
  '[1.3.0]: https://example.com/compare/v1.2.30...v1.3.0',
  '[1.2.30]: https://example.com/compare/v1.2.3...v1.2.30',
  '[1.2.3]: https://example.com/compare/v1.2.2...v1.2.3',
  ''
].join('\n');

test('extractReleaseNotes returns a middle section without its heading or neighbours', () => {
  const notes = extractReleaseNotes(changelogFixture, '1.2.30');
  assert.equal(notes, '### Fixed\n\n- patch thirty');
  assert.ok(!notes.includes('## ['));
  assert.ok(!notes.includes('newest feature'));
  assert.ok(!notes.includes('patch three'));
});

test('extractReleaseNotes stops the oldest section at trailing link references', () => {
  const notes = extractReleaseNotes(changelogFixture, '1.2.3');
  assert.equal(notes, '### Fixed\n\n- patch three');
  assert.ok(!notes.includes('[1.2.3]:'));
  assert.ok(!notes.includes('https://example.com'));
});

test('extractReleaseNotes throws an error naming a missing version', () => {
  assert.throws(
    () => extractReleaseNotes(changelogFixture, '9.9.9'),
    (error) => {
      assert.ok(error instanceof Error);
      assert.match(error.message, /9\.9\.9/);
      return true;
    }
  );
});

test('extractReleaseNotes matches versions exactly: 1.2.3 does not hit 1.2.30', () => {
  const notes = extractReleaseNotes(changelogFixture, '1.2.3');
  assert.ok(notes.includes('- patch three'));
  assert.ok(!notes.includes('- patch thirty'));
});

test('release-notes CLI exits 1 and names the missing version on stderr', () => {
  assert.throws(
    () => execFileSync(process.execPath, [scriptPath, '9.9.9'], { encoding: 'utf8' }),
    (error) => {
      assert.equal(error.status, 1);
      assert.match(error.stderr, /9\.9\.9/);
      return true;
    }
  );
});

test('release-notes CLI prints the current package version section', () => {
  const { version } = JSON.parse(readFileSync(join(packageRoot, 'package.json'), 'utf8'));
  const stdout = execFileSync(process.execPath, [scriptPath, version], { encoding: 'utf8' });
  assert.ok(stdout.trim().length > 0);
  assert.ok(stdout.endsWith('\n'));
});