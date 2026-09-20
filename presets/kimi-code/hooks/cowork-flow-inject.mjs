#!/usr/bin/env node
/**
 * cowork-flow Kimi Code hook — transport shim.
 *
 * Kimi Code appends a UserPromptSubmit hook's stdout to the prompt context
 * verbatim, so all workflow facts are rendered by the single Python source
 * (inject.py --host kimi-code, emit_text policy). This shim keeps only
 * transport duties:
 *   1. cheap project-root pre-check — a cwd outside any cowork-flow project
 *      exits 0 without spawning anything, so the user-level hook never
 *      touches unrelated repositories;
 *   2. interpreter location (COWORK_FLOW_PYTHON → python3 → python → py -3);
 *   3. stdin passthrough to inject.py, stdout/exit forwarding.
 *
 * Fail-open by construction: a missing interpreter, a missing runtime, or a
 * broken project copy all exit 0 with empty stdout instead of blocking the
 * user's prompt (a non-zero exit on UserPromptSubmit aborts the submit).
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";

const WORKFLOW_DIR = ".cowork-flow";
const INJECT_RELATIVE = join(
  WORKFLOW_DIR,
  "scripts",
  "adapters",
  "host",
  "inject.py"
);
const HOST = "kimi-code";
const SPAWN_TIMEOUT_MS = 20000; // config.toml grants the hook 30s

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

function findProjectRoot(startDir) {
  if (typeof startDir !== "string" || !startDir.trim()) return null;
  let current = startDir.trim();
  const root = dirname(current);
  while (current !== root) {
    if (existsSync(join(current, INJECT_RELATIVE))) return current;
    current = dirname(current);
  }
  return existsSync(join(current, INJECT_RELATIVE)) ? current : null;
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
  const cwd =
    typeof parsed?.cwd === "string" && parsed.cwd.trim()
      ? parsed.cwd
      : process.cwd();
  const root = findProjectRoot(cwd);
  if (!root) process.exit(0);

  const injectScript = join(root, INJECT_RELATIVE);
  for (const candidate of pythonCandidates()) {
    let result;
    try {
      result = spawnSync(
        candidate[0],
        [...candidate.slice(1), injectScript, "--host", HOST],
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
    process.exit(result.status);
  }
  // No interpreter could run the entry: stay silent rather than break the
  // user's submit (fail-open, same contract as the other host shims).
  process.exit(0);
}

main();
