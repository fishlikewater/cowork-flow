#!/usr/bin/env node
/**
 * cowork-flow Qoder plugin hook — transport shim.
 *
 * Workflow facts (workflow-state, contract digest, decision
 * anchor, stage contract, scope/spec edits) come from the
 * Python source
 * <scripts>/adapters/host/inject.py; this shim does
 * transport only:
 *   1. project resolution from the hook payload (`cwd`),
 *      then QODER_PROJECT_DIR / QODER_WORKING_DIR;
 *   2. interpreter location, COWORK_FLOW_PYTHON -> python3
 *      -> python -> py -3 — the hook runs under the host's
 *      process PATH, which is not the user's login shell;
 *   3. stdin passthrough to inject.py --host qoder, with
 *      stdout forwarded and a failing project runtime
 *      absorbed (exit 0, reason on stderr) — Qoder refuses
 *      the prompt on a non-zero hook exit, and the hook is
 *      machine-level, so it may meet a project runtime
 *      older than itself.
 *
 * Deliberately named .mjs: the installed plugin cache has
 * no package.json, so a plain .js entry point is parsed as
 * CommonJS there and an `import` file would only load on
 * Node versions that auto-detect module syntax.
 */

import { existsSync, readFileSync } from "fs";
import { dirname, join, resolve } from "path";
import { spawnSync } from "child_process";

const HOST = "qoder";
const DIR_WORKFLOW = ".cowork-flow";
// hooks.json grants 30s per event.
const SPAWN_TIMEOUT_MS = 25000;

function readHookInput() {
  if (process.stdin.isTTY) return { raw: "", parsed: {} };
  let raw = "";
  try {
    raw = readFileSync(0, "utf8");
  } catch {
    return { raw: "", parsed: {} };
  }
  try {
    // Tolerate a UTF-8 BOM and surrounding whitespace: the payload is
    // forwarded verbatim either way, only the parse needs it clean.
    const parsed = JSON.parse(raw.replace(/^\uFEFF/, "").trim());
    return { raw, parsed: parsed && typeof parsed === "object" ? parsed : {} };
  } catch {
    return { raw, parsed: {} };
  }
}

function findWorkflowRoot(startDir) {
  if (typeof startDir !== "string" || !startDir.trim()) return null;
  let current;
  try {
    current = resolve(startDir);
  } catch {
    return null;
  }
  for (;;) {
    if (existsSync(join(current, DIR_WORKFLOW))) return current;
    const parent = dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

function findProjectRoot(parsedInput) {
  const candidates = [
    parsedInput?.cwd,
    process.env.QODER_PROJECT_DIR,
    process.env.QODER_WORKING_DIR,
    process.cwd(),
  ];
  for (const candidate of candidates) {
    const root = findWorkflowRoot(candidate);
    if (root) return root;
  }
  return null;
}

function pythonCandidates() {
  const list = [];
  const env = (process.env.COWORK_FLOW_PYTHON || "").trim();
  if (env) list.push([env]);
  list.push(["python3"], ["python"]);
  if (process.platform === "win32") list.push(["py", "-3"]);
  return list;
}

function main() {
  if (
    process.env.COWORK_FLOW_HOOKS === "0" ||
    process.env.COWORK_FLOW_DISABLE_HOOKS === "1"
  ) {
    process.exit(0);
  }

  const { raw, parsed } = readHookInput();
  const root = findProjectRoot(parsed);
  if (!root) process.exit(0);
  const injectScript = join(
    root,
    DIR_WORKFLOW,
    "scripts",
    "adapters",
    "host",
    "inject.py"
  );
  if (!existsSync(injectScript)) process.exit(0);

  for (const candidate of pythonCandidates()) {
    let result;
    try {
      result = spawnSync(
        candidate[0],
        [...candidate.slice(1), injectScript, "--host", HOST],
        {
          input: raw,
          cwd: root,
          timeout: SPAWN_TIMEOUT_MS,
          encoding: "utf8",
          windowsHide: true,
        }
      );
    } catch {
      continue;
    }
    if (result.error || result.status === null) continue;
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    // The interpreter ran; its exit status is the project runtime's verdict,
    // not ours. Forwarding it would let a stale project copy fail the event
    // this hook only decorates.
    if (result.status !== 0) {
      process.stderr.write(
        `cowork-flow qoder hook: inject.py exited ${result.status}; skipping injection\n`
      );
    }
    process.exit(0);
  }
  // No interpreter could run the entry: stay silent rather
  // than break the host's event stream (fail-open).
  process.exit(0);
}

main();
