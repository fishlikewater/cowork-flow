#!/usr/bin/env node
/**
 * cowork-flow ZCode plugin hook.
 * Reads .cowork-flow/ state and outputs workflow-state XML for injection.
 */

import { readFileSync, existsSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { createHash } from "crypto";

const DIR_WORKFLOW = ".cowork-flow";
const DIR_SCRIPT = "scripts";

const TAG_RE = /\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n(.*?)\n\s*\[\/workflow-state:\1\]/gs;
const RUNTIME_CONTEXT_PROMPT_RE = /^\s*cowork_runtime_context_id\s*:\s*([A-Za-z0-9._-]+)\s*$/gim;

// ---------------------------------------------------------------------------
// Find project root
// ---------------------------------------------------------------------------
function findProjectRoot() {
  const envDir = process.env.ZCODE_PROJECT_DIR;
  if (envDir && existsSync(join(envDir, DIR_WORKFLOW))) return envDir;

  let current = process.cwd();
  const root = dirname(current);
  while (current !== root) {
    if (existsSync(join(current, DIR_WORKFLOW))) return current;
    current = dirname(current);
  }
  return existsSync(join(current, DIR_WORKFLOW)) ? current : null;
}

// ---------------------------------------------------------------------------
// Read workflow state templates
// ---------------------------------------------------------------------------
function loadStateTemplates(repoRoot) {
  const path = join(repoRoot, DIR_WORKFLOW, "spec", "core", "state-templates.md");
  if (!existsSync(path)) return {};
  try {
    const text = readFileSync(path, "utf8");
    const templates = {};
    for (const match of text.matchAll(TAG_RE)) {
      templates[match[1]] = match[2].trim();
    }
    return templates;
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Read active task status from FlowStore DB
// ---------------------------------------------------------------------------
function readActiveTask(repoRoot) {
  try {
    // Try session DB first
    const dbPath = join(repoRoot, DIR_WORKFLOW, "cowork-flow.db");
    if (existsSync(dbPath)) {
      // Quick JSON read of runtime_context for active context
      const ctxPath = join(repoRoot, DIR_WORKFLOW, ".runtime", "context.json");
      if (existsSync(ctxPath)) {
        const ctx = JSON.parse(readFileSync(ctxPath, "utf8"));
        if (ctx.active_task_path) {
          return {
            taskPath: ctx.active_task_path,
            scope: ctx.scope || "main",
            status: ctx.active_task_status || "unknown",
          };
        }
      }
    }
  } catch {
    // ignore
  }
  return null;
}

// ---------------------------------------------------------------------------
// Compute contract digest fingerprint
// ---------------------------------------------------------------------------
function computeContractDigest(repoRoot) {
  try {
    const registryPath = join(repoRoot, DIR_WORKFLOW, "spec", "registry.json");
    if (!existsSync(registryPath)) return "";
    const registry = JSON.parse(readFileSync(registryPath, "utf8"));
    const hash = createHash("sha256");
    for (const contract of registry.contracts || []) {
      hash.update(contract.id + ":" + (contract.digest?.join("|") || ""));
    }
    return hash.digest("hex").slice(0, 16);
  } catch {
    return "";
  }
}

// ---------------------------------------------------------------------------
// Detect runtime context (subagent dispatch)
// ---------------------------------------------------------------------------
function detectRuntimeContext(userPrompt) {
  if (!userPrompt) return null;
  const match = RUNTIME_CONTEXT_PROMPT_RE.exec(userPrompt);
  return match ? match[1] : null;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  if (process.env.COWORK_FLOW_DISABLE_HOOKS === "1" || process.env.COWORK_FLOW_HOOKS === "0") {
    return;
  }

  const repoRoot = findProjectRoot();
  if (!repoRoot) return;  // no cowork-flow project

  const templates = loadStateTemplates(repoRoot);
  const activeTask = readActiveTask(repoRoot);
  const contractDigest = computeContractDigest(repoRoot);

  // Determine state
  let state = "no_task";
  let scope = "main";
  if (activeTask) {
    scope = activeTask.scope || "main";
    state = activeTask.status || "no_task";
    if (scope !== "main" && templates.delegated_subtask) {
      state = "delegated_subtask";
    }
  }

  // Select template
  const template = templates[state] || templates.no_task || "";

  // Output
  const output = [
    "<workflow-state>",
    `  <state>${state}</state>`,
    `  <scope>${scope}</scope>`,
    activeTask ? `  <task>${activeTask.taskPath}</task>` : "",
    contractDigest ? `  <contract-digest>${contractDigest}</contract-digest>` : "",
    "  <template>",
    ...template.split("\n").map((l) => `    ${l}`),
    "  </template>",
    "</workflow-state>",
  ].filter(Boolean).join("\n");

  process.stdout.write(output + "\n");
}

main();
