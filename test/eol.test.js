import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';

// `npm pack` reads the working tree, not the index, so a checkout that still
// carries CRLF bytes for a file whose attribute says LF ships those bytes.
// `.gitattributes` cannot rewrite existing worktrees; only re-materializing
// them can, which is why the fix is `git checkout-index -a -f`.
function eolViolations() {
  let output;
  try {
    output = execFileSync('git', ['ls-files', '--eol'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore']
    });
  } catch {
    return null;
  }
  return output
    .split(/\r?\n/)
    .filter((line) => line.includes('\t'))
    .filter((line) => {
      const [attributes] = line.split('\t');
      return /\battr\/.*\btext eol=lf\b/.test(attributes)
        && /\bw\/(?:crlf|mixed)\b/.test(attributes);
    });
}

test('tracked files declared eol=lf are checked out with LF', (t) => {
  const violations = eolViolations();
  if (violations === null) {
    t.skip('not a git checkout');
    return;
  }
  const paths = violations.map((line) => line.split('\t').at(-1));
  assert.deepEqual(
    paths,
    [],
    'These tracked files are declared `text eol=lf` but the working tree has '
    + `CRLF bytes: ${paths.join(', ')}. Run \`git checkout-index -a -f\` to `
    + 're-materialize them from the index.'
  );
});
