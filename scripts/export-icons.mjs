#!/usr/bin/env node
// Dev-only. The brand mark has one source — assets/icon.svg, deliberately
// colourless so the brand colour stays single-sourced in presets/plugin-meta.json
// — and two shipped derivations: the raster the zcode marketplace entry points at
// over https, and the in-payload copy codex resolves relative to the plugin root.
//
// Nothing in the CLI reads either derived file, so this script is not part of the
// runtime and must not add a dependency. It drives whatever Chromium the machine
// already has, and refuses to write anything when it cannot find one: a silent
// skip would leave a stale raster that no test can detect (re-rasterising is the
// only way to compare, which is exactly what is missing here).
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { readPluginMetadata } from '../src/lib/plugin-metadata.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
// The source/raster paths come from the metadata file so the derivation and the
// marketplace URL that points at the raster cannot name different files.
const metadata = await readPluginMetadata();
const SOURCE = join(root, ...metadata.icon.source.split('/'));
const RASTER = join(root, ...metadata.icon.raster.split('/'));
const PAYLOAD_COPY = join(root, 'presets', 'codex', 'assets', 'logo.svg');
const RASTER_SIZE = 512;

const WINDOWS_BROWSERS = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
];

// Ordered attempts. An explicit override wins outright — a bad path there is a
// user error to report, not something to silently step over. Otherwise known
// install locations come first and the PATH names after, so a browser installed
// somewhere unusual but on PATH still works.
function browserCandidates() {
  const override = process.env.COWORK_FLOW_BROWSER;
  if (override) {
    if (!existsSync(override)) {
      throw new Error(`COWORK_FLOW_BROWSER points at a missing file: ${override}`);
    }
    return [override];
  }
  return process.platform === 'win32'
    ? [...WINDOWS_BROWSERS, 'msedge', 'chrome']
    : ['google-chrome', 'chromium', 'chromium-browser'];
}

function runBrowser(browser, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(browser, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${browser} exited with ${code}\n${stderr.trim()}`));
      }
    });
  });
}

async function render(coloured, staged) {
  const scratch = await mkdtemp(join(tmpdir(), 'cowork-flow-icons-'));
  try {
    const page = join(scratch, 'render.html');
    await writeFile(
      page,
      `<!doctype html><meta charset="utf-8">`
      // The CSS box wins over the SVG's own width/height attributes, which is
      // what makes the mark fill the canvas instead of drawing 24px in a corner.
      + `<style>html,body{margin:0;padding:0;width:${RASTER_SIZE}px;height:${RASTER_SIZE}px;`
      + `background:transparent}svg{display:block;width:100%;height:100%}`
      + `</style>${coloured}`,
      'utf8'
    );
    const args = [
      '--headless=new',
      '--disable-gpu',
      '--hide-scrollbars',
      '--no-first-run',
      '--no-default-browser-check',
      `--user-data-dir=${join(scratch, 'profile')}`,
      `--window-size=${RASTER_SIZE},${RASTER_SIZE}`,
      // AARRGGBB: the mark must sit on transparency, not on Chromium's white.
      '--default-background-color=00000000',
      '--virtual-time-budget=3000',
      `--screenshot=${staged}`,
      `file:///${page.split('\\').join('/')}`
    ];

    const failures = [];
    for (const browser of browserCandidates()) {
      if (/[\\/]/.test(browser) && !existsSync(browser)) {
        failures.push(`${browser}: not found`);
        continue;
      }
      try {
        await runBrowser(browser, args);
      } catch (error) {
        failures.push(`${browser}: ${String(error.message).split('\n')[0]}`);
        continue;
      }
      if (existsSync(staged)) {
        return;
      }
      // Chromium reports success and writes nothing when --screenshot has an
      // extension it does not recognise, so success alone proves nothing.
      failures.push(`${browser}: reported success but wrote no screenshot`);
    }
    throw new Error(`no browser produced a screenshot:\n  ${failures.join('\n  ')}`);
  } finally {
    await rm(scratch, { recursive: true, force: true });
  }
}

async function main() {
  const colour = metadata.brandColor;
  if (typeof colour !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(colour)) {
    throw new Error(`presets/plugin-meta.json brandColor is not a hex colour: ${colour}`);
  }

  const source = await readFile(SOURCE, 'utf8');
  const coloured = source.split('currentColor').join(colour);

  // The screenshot lands beside its target, not in the OS temp dir: the rename
  // that publishes it has to stay on one filesystem, and on Windows the repo
  // usually sits on a different drive than %TEMP%. It also has to end in .png —
  // any other extension makes Chromium write nothing. A run killed mid-render
  // cannot reach the cleanup below, so clear a leftover from such a run first.
  const staged = join(dirname(RASTER), 'icon.staging.png');
  await rm(staged, { force: true });

  try {
    await render(coloured, staged);
    if (!existsSync(staged)) {
      throw new Error('the browser produced no screenshot');
    }

    // Publish by rename so an interrupted run cannot leave a half-written asset.
    await mkdir(dirname(PAYLOAD_COPY), { recursive: true });
    await writeFile(`${PAYLOAD_COPY}.tmp`, coloured, 'utf8');
    await rename(`${PAYLOAD_COPY}.tmp`, PAYLOAD_COPY);
    await rename(staged, RASTER);

    console.log(`source:   ${SOURCE}`);
    console.log(`colour:   ${colour}`);
    console.log(`payload:  ${PAYLOAD_COPY}`);
    console.log(`raster:   ${RASTER} (${RASTER_SIZE}x${RASTER_SIZE}, transparent)`);
  } finally {
    await rm(staged, { force: true });
    await rm(`${PAYLOAD_COPY}.tmp`, { force: true });
  }
}

await main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.stderr.write(
    'Set COWORK_FLOW_BROWSER to a Chromium binary, or export the mark yourself:\n'
    + `  ${RASTER_SIZE}x${RASTER_SIZE} transparent PNG of assets/icon.svg (currentColor -> `
    + 'presets/plugin-meta.json brandColor)\n'
  );
  process.exitCode = 1;
});
