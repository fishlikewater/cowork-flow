#!/usr/bin/env node
/**
 * Sync canonical skills from template/skills/ to platform directories.
 *
 * Usage:
 *   node scripts/sync-skills.js          # sync (copy) canonical -> platforms
 *   node scripts/sync-skills.js --check  # verify in-sync (exit 1 if drift)
 *
 * Platform destinations:
 *   template/skills/* -> template/.claude/skills/* (claude-code)
 *   template/skills/* -> template/.agents/skills/* (codex, opencode)
 */

import { cp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { pathExists } from '../src/lib/fs-utils.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const CANONICAL = join(ROOT, 'template', 'skills');
const DESTINATIONS = [
  { dir: join(ROOT, 'template', '.claude', 'skills'), platform: 'claude-code' },
  { dir: join(ROOT, 'template', '.agents', 'skills'), platform: 'codex/opencode' },
];

const CHECK_ONLY = process.argv.includes('--check');

async function main() {
  const skills = (await readdir(CANONICAL, { withFileTypes: true }))
    .filter((e) => e.isDirectory())
    .map((e) => e.name);

  let drift = 0;
  let copied = 0;

  for (const skillName of skills) {
    const srcFile = join(CANONICAL, skillName, 'SKILL.md');
    const srcContent = await readFile(srcFile, 'utf8').catch(() => null);
    if (srcContent === null) continue;

    for (const dest of DESTINATIONS) {
      const destDir = join(dest.dir, skillName);
      const destFile = join(destDir, 'SKILL.md');

      if (CHECK_ONLY) {
        const exists = await pathExists(destFile);
        if (!exists) {
          console.log(`MISSING: ${destFile} (from ${dest.platform})`);
          drift++;
          continue;
        }
        const destContent = await readFile(destFile, 'utf8');
        if (destContent !== srcContent) {
          console.log(`DRIFT: ${destFile} differs from canonical`);
          drift++;
        }
      } else {
        await mkdir(destDir, { recursive: true });
        // Transform: claude-code uses ${CLAUDE_PROJECT_DIR:-.} prefix
        let outContent = srcContent;
        if (dest.platform === 'claude-code') {
          outContent = srcContent
            .split('\n')
            .map((line) => {
              // Replace `.cowork-flow/run` but NOT the already-prefixed form or cmd form
              if (line.includes('.cowork-flow/run') && !line.includes('${CLAUDE_PROJECT_DIR:-.}')) {
                return line.replace(/\.cowork-flow\/run/g, '${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run');
              }
              return line;
            })
            .join('\n');
        }
        await writeFile(destFile, outContent, 'utf8');
        copied++;
      }
    }
  }

  if (CHECK_ONLY) {
    if (drift > 0) {
      console.log(`\n${drift} drift(s) detected. Run "node scripts/sync-skills.js" to fix.`);
      process.exit(1);
    }
    console.log('All platform skills are in sync with template/skills/.');
  } else {
    console.log(`Synced ${skills.length} skills to ${DESTINATIONS.length} platform directories.`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
