#!/usr/bin/env node
/**
 * cowork-flow ZCode plugin hook.
 * Reads .cowork-flow/ state, parses workflow-state-templates.md, computes contract digest.
 * Project files are installed by explicit cowork-flow init/sync, not by hook scaffolding.
 * Output: ZCode/Claude Code hook format (stdout JSON).
 */

import { readFileSync, existsSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { createHash } from "crypto";

const DIR_WORKFLOW = ".cowork-flow";
const FILE_TASK_JSON = "task.json";

const TAG_RE = /\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n(.*?)\n\s*\[\/workflow-state:\1\]/gs;
const RUNTIME_CONTEXT_PROMPT_RE = /^\s*cowork_runtime_context_id\s*:\s*([A-Za-z0-9._-]+)\s*$/gim;
const DEFAULT_CONTRACT_REGISTRY = {
  contracts: [
    {
      id: "RUNTIME_CONTEXT_DISPATCH_V2",
      path: ".cowork-flow/spec/contracts/subagent-dispatch.md",
      digest: [
        "Formal subagent work is keyed by cowork_runtime_context_id.",
        "Explicit shim bind records bound_context_key before formal output is accepted.",
      ],
      readWhen: ["before formal subagent dispatch", "when checking subagent health"],
    },
  ],
};

function readHookInput() {
  if (process.stdin.isTTY) return {};
  try {
    const raw = readFileSync(0, "utf8").trim();
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function detectEventName(input) {
  if (typeof input?.hook_event_name === "string" && input.hook_event_name.trim()) {
    return input.hook_event_name.trim();
  }
  if (process.env.CURSOR_PLUGIN_ROOT) return "SessionStart";
  return "UserPromptSubmit";
}

function outputFormat() {
  if (process.env.CURSOR_PLUGIN_ROOT) return "cursor";
  if (process.env.CLAUDE_PLUGIN_ROOT && !process.env.COPILOT_CLI) return "claude";
  return "generic";
}

// ---------------------------------------------------------------------------
// Find project root
// ---------------------------------------------------------------------------
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

function findProjectRoot(input) {
  const candidates = [
    input?.cwd,
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

// ---------------------------------------------------------------------------
// Read active task from .cowork-flow/.runtime/sessions/
// ---------------------------------------------------------------------------
// Sanitize rules mirror Python session_state._sanitize so both sides resolve
// the same session file name for one context key.
function sanitizeContextKey(raw) {
  const safe = String(raw ?? "")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "_")
    .replace(/^[._-]+|[._-]+$/g, "");
  return safe.slice(0, 160);
}

function resolveSessionKey(input) {
  const explicit = process.env.COWORK_FLOW_CONTEXT_ID;
  const candidates = [
    explicit,
    process.env.ZCODE_SESSION_ID,
    input?.zcode_session_id,
    input?.ZCODE_SESSION_ID,
    input?.sessionId,
    input?.session_id,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      const key = sanitizeContextKey(candidate);
      if (key) return `zcode_${key}`;
    }
  }
  return null;
}

function loadSessionEntries(sessionsDir) {
  const entries = [];
  try {
    const files = readdirSync(sessionsDir).filter((f) => f.endsWith(".json"));
    for (const file of files) {
      try {
        const data = JSON.parse(readFileSync(join(sessionsDir, file), "utf8"));
        if (data && typeof data === "object") {
          entries.push({ name: file, data });
        }
      } catch {
        // skip malformed session file
      }
    }
  } catch {
    // sessions dir unreadable
  }
  return entries;
}

function toActiveTask(data) {
  return {
    taskPath: data.active_task_path,
    scope: data.scope || "main",
    platform: data.platform || "unknown",
  };
}

function readActiveTask(repoRoot, sessionKey = null) {
  const sessionsDir = join(repoRoot, DIR_WORKFLOW, ".runtime", "sessions");
  if (!existsSync(sessionsDir)) return null;
  const entries = loadSessionEntries(sessionsDir);

  // The current session's own binding wins even when another host wrote a
  // newer session file; a dead path here is reported as-is by buildContext.
  if (sessionKey) {
    const own = entries.find((entry) => entry.name === `${sessionKey}.json`);
    if (own?.data.active_task_path) return toActiveTask(own.data);
  }

  // Global fallback: newest first, but skip subagent-scoped files and entries
  // whose task directory no longer exists so stale sessions cannot poison
  // fresh sessions.
  const candidates = entries
    .filter((entry) => entry.data.active_task_path && entry.data.scope !== "subagent")
    .sort((a, b) => String(b.data.last_seen_at || "").localeCompare(String(a.data.last_seen_at || "")));
  for (const entry of candidates) {
    const taskPath = entry.data.active_task_path;
    if (
      existsSync(join(repoRoot, taskPath)) &&
      existsSync(join(repoRoot, taskPath, FILE_TASK_JSON))
    ) {
      return toActiveTask(entry.data);
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Read task status from task.json
// ---------------------------------------------------------------------------
function readTaskStatus(repoRoot, taskPath) {
  const taskDir = join(repoRoot, taskPath);
  if (!existsSync(taskDir)) return { status: "missing", missing: true };
  const taskJsonPath = join(taskDir, FILE_TASK_JSON);
  if (!existsSync(taskJsonPath)) return { status: "missing", missing: true };
  try {
    const data = JSON.parse(readFileSync(taskJsonPath, "utf8"));
    return { status: (data.status || "unknown").trim(), missing: false };
  } catch {
    return { status: "unknown", missing: false };
  }
}

// ---------------------------------------------------------------------------
// Load workflow-state breadcrumb texts from templates.md
// ---------------------------------------------------------------------------
function loadBreadcrumbs(repoRoot) {
  const templatesFile = join(repoRoot, DIR_WORKFLOW, "spec", "contracts", "workflow-state-templates.md");
  try {
    const text = readFileSync(templatesFile, "utf8");
    return Object.fromEntries(
      [...text.matchAll(TAG_RE)].map((m) => [m[1], m[2].trim()])
    );
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Contract digest computation
// ---------------------------------------------------------------------------
function loadContractRegistry(repoRoot) {
  const registryFile = join(repoRoot, DIR_WORKFLOW, "spec", "runtime", "contract-registry.json");
  try {
    const data = JSON.parse(readFileSync(registryFile, "utf8"));
    const contracts = data?.contracts;
    return Array.isArray(contracts)
      ? contracts.filter((c) => c && typeof c === "object")
      : DEFAULT_CONTRACT_REGISTRY.contracts;
  } catch {
    return DEFAULT_CONTRACT_REGISTRY.contracts;
  }
}

function contractFingerprint(root, contracts) {
  const hash = createHash("sha256");
  hash.update(JSON.stringify(contracts));
  for (const contract of contracts) {
    const p = contract?.path;
    if (typeof p !== "string" || !p.trim()) continue;
    try {
      hash.update(readFileSync(join(root, p), "utf8"));
    } catch {
      hash.update(`missing:${p}`);
    }
  }
  return hash.digest("hex").slice(0, 16);
}

function buildContractDigest(root) {
  const contracts = loadContractRegistry(root);
  const fingerprint = contractFingerprint(root, contracts);
  const lines = [
    `<cowork-runtime host="zcode" adapter="zcode.plugin">`,
    `<contract-digest fingerprint="${fingerprint}">`,
    "policy: repeat fingerprint every hook; read full spec files only before listed actions.",
  ];
  for (const contract of contracts) {
    const id = contract?.id;
    const path = contract?.path;
    if (typeof id !== "string" || !id.trim()) continue;
    const pathText = typeof path === "string" && path.trim() ? path : "<missing-path>";
    lines.push(`- ${id}: ${pathText}`);
    const digest = Array.isArray(contract?.digest) ? contract.digest : [];
    for (const item of digest.slice(0, 2)) {
      if (typeof item === "string") lines.push(`  digest: ${item}`);
    }
    const readWhen = Array.isArray(contract?.readWhen) ? contract.readWhen : [];
    if (readWhen.length > 0) {
      lines.push(`  read_before: ${readWhen.join("; ")}`);
    }
  }
  lines.push(`</contract-digest>`);
  lines.push(`</cowork-runtime>`);
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Check essential project files
// ---------------------------------------------------------------------------
function checkEssentialFiles(repoRoot) {
  const missing = [];
  const essentials = [
    ["AGENTS.md", "AGENTS.md"],
    [".cowork-flow/config.yaml", ".cowork-flow/config.yaml"],
    [".cowork-flow/run", ".cowork-flow/run"],
    [".cowork-flow/spec/runtime/contract-registry.json", ".cowork-flow/spec/runtime/contract-registry.json"],
    [".cowork-flow/spec/contracts/workflow-state-templates.md", ".cowork-flow/spec/contracts/workflow-state-templates.md"],
  ];
  for (const [relPath, label] of essentials) {
    if (!existsSync(join(repoRoot, relPath))) missing.push(label);
  }
  return missing;
}

// ---------------------------------------------------------------------------
// Runtime context detection
// ---------------------------------------------------------------------------
function extractRuntimeContextId(promptText) {
  if (typeof promptText !== "string") return null;
  RUNTIME_CONTEXT_PROMPT_RE.lastIndex = 0;
  const match = RUNTIME_CONTEXT_PROMPT_RE.exec(promptText);
  return match ? match[1] : null;
}

function detectDelegatedSubtask(repoRoot, userPrompt) {
  const envId = process.env.COWORK_FLOW_RUNTIME_CONTEXT_ID;
  const contextId = envId || extractRuntimeContextId(userPrompt);
  if (!contextId) return null;

  const ctxFile = join(repoRoot, DIR_WORKFLOW, ".runtime", "subagents", `${contextId}.json`);
  try {
    const ctx = JSON.parse(readFileSync(ctxFile, "utf8"));
    if (ctx.scope === "subagent" && ctx.status !== "closed") {
      return { contextId, ctx };
    }
  } catch {
    // missing/invalid context
  }
  return { contextId, ctx: null };
}

// ---------------------------------------------------------------------------
// Build context blocks
// ---------------------------------------------------------------------------
function buildContext(repoRoot, activeTask, breadcrumbs) {
  const fallback = "Run ./.cowork-flow/run task next for the current workflow step.";

  if (!activeTask) {
    const body = breadcrumbs.no_task || fallback;
    return `<workflow-state>
Status: no_task
Source: task next / ${DIR_WORKFLOW}/spec
${body}
</workflow-state>`;
  }

  const { status, missing } = readTaskStatus(repoRoot, activeTask.taskPath);
  const scope = activeTask.scope === "subagent" ? "\nScope: subagent" : "";

  if (missing) {
    return `<workflow-state>
Status: no_task
Source: runtime-session
Session 指向的任务目录不存在（${activeTask.taskPath}）。
当前项目无有效任务。请运行 ./.cowork-flow/run task next --run --title "<title>" --slug <task-name> --assignee <name> 创建新任务。
</workflow-state>`;
  }

  const body = breadcrumbs[status] || fallback;
  return `<workflow-state>
Task: ${activeTask.taskPath}
Status: ${status}
Source: runtime-session${scope}
${body}
</workflow-state>`;
}

function buildDelegatedSubtask(contextId, ctx) {
  const lines = [
    `<workflow-state>`,
    `Task: ${ctx?.task_dir || "unknown"}`,
    `Status: delegated_subtask`,
    `Source: runtime-context:${contextId}`,
    `Runtime context: ${contextId}`,
    `Agent: ${ctx?.agent_type || "unknown"}`,
    `Scope: subagent`,
    `Do not run start/resume/task start/archive/commit/spawn.`,
  ];
  const goal = ctx?.assignment?.goal;
  if (typeof goal === "string" && goal.trim()) {
    lines.push(`Goal: ${goal.trim()}`);
  }
  lines.push(`</workflow-state>`);
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  if (process.env.COWORK_FLOW_HOOKS === "0" || process.env.COWORK_FLOW_DISABLE_HOOKS === "1") {
    process.exit(0);
  }

  const input = readHookInput();
  const event = detectEventName(input);
  const format = outputFormat();
  const repoRoot = findProjectRoot(input);

  let context;

  const envDir = process.env.ZCODE_PROJECT_DIR || process.env.CLAUDE_PROJECT_DIR;
  const effectiveRoot = repoRoot || findWorkflowRoot(envDir);

  if (!effectiveRoot) {
    context = `<workflow-state>
Status: not_initialized
Source: cowork-flow-plugin
⚠️ 项目未初始化 cowork-flow 工作流。

请通过显式 init/sync 安装 cowork-flow 模板后再继续；hook 不会在注入阶段创建或复制项目文件。
</workflow-state>`;
  } else {
    // PRIORITY 1: Detect delegated_subtask from runtime context
    const userPrompt = typeof input.prompt === "string" ? input.prompt : "";
    const delegated = detectDelegatedSubtask(effectiveRoot, userPrompt);
    if (delegated) {
      context = buildDelegatedSubtask(delegated.contextId, delegated.ctx);
    } else {
      // PRIORITY 2: Normal session workflow state
      const activeTask = readActiveTask(effectiveRoot, resolveSessionKey(input));
      const breadcrumbs = loadBreadcrumbs(effectiveRoot);
      context = buildContext(effectiveRoot, activeTask, breadcrumbs);
    }
  }

  // Inject contract digest: the full block rides session start (startup,
  // clear, compact re-runs it); later prompts only repeat the fingerprint
  // so long sessions don't pay for the full listing on every message.
  const rootForDigest = effectiveRoot || envDir || input.cwd;
  if (rootForDigest) {
    if (
      typeof input?.hook_event_name === "string" &&
      input.hook_event_name.trim() === "SessionStart"
    ) {
      context = `${buildContractDigest(rootForDigest)}\n\n${context}`;
    } else {
      const contracts = loadContractRegistry(rootForDigest);
      const fingerprint = contractFingerprint(rootForDigest, contracts);
      context = `<contract-fingerprint value="${fingerprint}"/>\n\n${context}`;
    }
  }

  const missingFiles = effectiveRoot ? checkEssentialFiles(effectiveRoot) : [];
  if (missingFiles.length > 0) {
    context += `

⚠️ 缺少必要文件：${missingFiles.join(", ")}。
请立即创建这些文件以保障工作流正常运行。`;
  }

  const payload =
    format === "cursor"
      ? { additional_context: context }
      : { hookSpecificOutput: { hookEventName: event, additionalContext: context } };

  process.stdout.write(JSON.stringify(payload, null, 2));
  process.exit(0);
}

main();
