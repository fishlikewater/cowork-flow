#!/usr/bin/env node
/**
 * cowork-flow ZCode plugin hook — transport shim.
 *
 * Workflow facts (workflow-state, contract digest,
 * decision anchor, stage contract, scope/spec edits)
 * come from the Python source
 * <scripts>/adapters/host/inject.py; this shim does
 * transport only:
 *   1. cheap PostToolUse(Bash) filter: anything that
 *      is not a lifecycle command exits 0 unspawned;
 *   2. interpreter location, COWORK_FLOW_PYTHON -> python3
 *      -> python -> py -3;
 *   3. stdin passthrough to inject.py --host zcode, with
 *      stdout forwarded and a failing project runtime
 *      absorbed (exit 0, reason on stderr) — the hook
 *      is machine-level and may meet an older project
 *      copy, which must not fail the event.
 *
 * The project's own runtime copy wins (same root the CLI
 * resolves); the plugin cache copy (runtime/scripts)
 * renders only outside any cowork-flow project. Windows
 * never spawns .cmd shims directly (Node 24+ EINVAL), so
 * interpreters resolve to .exe entries.
 */

import { existsSync, readFileSync } from "fs";
import { dirname, join, resolve } from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));

const DIR_WORKFLOW = ".cowork-flow";
const LIFECYCLE_BASH_RE = /\brun(?:\.cmd)?\s+(?:task|subagent|resume)\b/;
// hooks.json grants 5s per event.
const SPAWN_TIMEOUT_MS = 4800;
// The .cowork-flow/run floor, reused here: a candidate that cannot run
// Python 3.10+ is skipped like a missing binary, so a stale `python3`
// never hides a working `python` further down the list.
const MIN_PYTHON_CHECK = "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)";

function interpreterIsUsable(candidate) {
  try {
    const probe = spawnSync(
      candidate[0],
      [...candidate.slice(1), "-c", MIN_PYTHON_CHECK],
      { timeout: SPAWN_TIMEOUT_MS, windowsHide: true }
    );
    // A probe killed by its own timeout reached no verdict — a loaded machine,
    // not a bad interpreter — so let the real spawn decide; it carries the
    // same timeout and its own diagnostics.
    if (probe.error && probe.error.code === "ETIMEDOUT") return true;
    return !probe.error && probe.status === 0;
  } catch {
    return false;
  }
}

function readHookInput() {
  if (process.stdin.isTTY) return { raw: "", parsed: {} };
  let raw = "";
  try {
    raw = readFileSync(0, "utf8").trim();
  } catch {
    return { raw: "", parsed: {} };
  }
  try {
    const parsed = JSON.parse(raw);
    return { raw, parsed: parsed && typeof parsed === "object" ? parsed : {} };
  } catch {
    return { raw: "", parsed: {} };
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
    process.env.ZCODE_PROJECT_DIR,
    process.env.CLAUDE_PROJECT_DIR,
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

function resolveInjectScript(parsedInput) {
  const root = findProjectRoot(parsedInput);
  if (root) {
    const projectInject = join(
      root,
      DIR_WORKFLOW,
      "scripts",
      "adapters",
      "host",
      "inject.py"
    );
    if (existsSync(projectInject)) return projectInject;
  }
  // Plugin-cache copy: the not-initialized context for
  // directories outside any cowork-flow project.
  const cacheInject = join(
    __dirname,
    "runtime",
    "scripts",
    "adapters",
    "host",
    "inject.py"
  );
  if (existsSync(cacheInject)) return cacheInject;
  return null;
}

function main() {
  if (
    process.env.COWORK_FLOW_HOOKS === "0" ||
    process.env.COWORK_FLOW_DISABLE_HOOKS === "1"
  ) {
    process.exit(0);
  }

  const { raw, parsed } = readHookInput();

  // A PostToolUse Bash call matters only when it is a
  // workflow lifecycle command; every other call exits
  // without spawning Python.
  if (
    typeof parsed?.hook_event_name === "string" &&
    parsed.hook_event_name.trim() === "PostToolUse" &&
    String(parsed?.tool_name || "") === "Bash"
  ) {
    const command = String(parsed?.tool_input?.command || "").replaceAll(
      "\\",
      "/"
    );
    if (
      !command.includes(`${DIR_WORKFLOW}/run`) &&
      !LIFECYCLE_BASH_RE.test(command)
    ) {
      process.exit(0);
    }
  }

  const injectScript = resolveInjectScript(parsed);
  if (!injectScript) process.exit(0);

  for (const candidate of pythonCandidates()) {
    if (!interpreterIsUsable(candidate)) continue;
    let result;
    try {
      result = spawnSync(
        candidate[0],
        [...candidate.slice(1), injectScript, "--host", "zcode"],
        {
          input: raw,
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
        `cowork-flow zcode hook: inject.py exited ${result.status}; skipping injection\n`
      );
    }
    process.exit(0);
  }
  // No candidate could run the entry: stay fail-open, but say why once
  // instead of hiding a misconfiguration (a Python below the floor, or
  // none at all).
  process.stderr.write(
    "cowork-flow zcode hook: no Python 3.10+ interpreter found; skipping injection\n"
  );
  process.exit(0);
}

main();
