import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// POSIX shell capability as the tests actually use it: not just `sh -c`,
// but spawn() being able to execute a shebang script directly. Git-bash on
// Windows provides `sh`, yet node cannot exec shebang scripts there, so the
// deeper probe is what makes shell-dependent tests skip on Windows instead
// of failing.
export const shellRunner = (() => {
  for (const candidate of ['sh', 'bash']) {
    try {
      execFileSync(candidate, ['-c', 'exit 0'], { stdio: 'ignore' });
      const probeDir = mkdtempSync(join(tmpdir(), 'cowork-flow-shellprobe-'));
      const probe = join(probeDir, 'probe.sh');
      try {
        writeFileSync(probe, '#!/bin/sh\nexit 0\n', { mode: 0o755 });
        execFileSync(probe, { stdio: 'ignore' });
        return candidate;
      } catch {
        return null;
      } finally {
        rmSync(probeDir, { recursive: true, force: true });
      }
    } catch {
      // Try next shell candidate.
    }
  }
  return null;
})();

export function skipWithoutShell(t) {
  if (shellRunner === null) {
    t.skip('POSIX shell capability (direct shebang script exec) unavailable');
    return true;
  }
  return false;
}