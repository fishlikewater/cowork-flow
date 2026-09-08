#!/usr/bin/env node
/**
 * cowork-flow ZCode plugin hook — transport shim.
 *
 * All workflow facts (workflow-state, contract digest, decision anchor,
 * stage contract, scope/spec edit warnings) are rendered by the single
 * Python source: <scripts>/adapters/host/inject.py. This shim keeps only
 * transport duties:
 *   1. cheap PostToolUse(Bash) filter — non-lifecycle commands exit 0
 *      without spawning anything (the highest-frequency event);
 *   2. interpreter location (COWORK_FLOW_PYTHON → python3 → python → py -3);
 *   3. stdin passthrough to inject.py --host zcode, stdout/exit forwarding.
 *
 * The project's own runtime copy is preferred (same root the CLI resolves);
 * the plugin cache copy (hooks/runtime/scripts) renders only for directories
 * outside any cowork-flow project. Windows never spawns .cmd shims directly
 * (Node 24+ EINVAL) — interpreters resolve to .exe entries.
 */

import { existsSync, readFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));

const DIR_WORKFLOW = ".cowork-flow";
const LIFECYCLE_BASH_RE = /\brun(?:\.cmd)?\s+(?:task|subagent|resume)\b/;
const SPAWN_TIMEOUT_MS = 4800; // hooks.json grants 5s per event

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
  let current = startDir;
  const root = dirname(current);
  while (current !== root) {
    if (existsSync(join(current, DIR_WORKFLOW))) return current;
    current = dirname(current);
  }
  return existsSync(join(current, DIR_WORKFLOW)) ? current : null;
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
  // Plugin-cache runtime copy: renders the not-initialized context for
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

  // Cheap first: a PostToolUse Bash call only matters when it is a workflow
  // lifecycle command (mid-turn state refresh); every other Bash call exits
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
    process.exit(result.status);
  }
  // No interpreter could run the entry: stay silent rather than break the
  // host's event stream (fail-open, same contract as the spec-edit path).
  process.exit(0);
}

main();
