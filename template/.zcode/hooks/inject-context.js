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
  // Python session_state resolves an explicit COWORK_FLOW_CONTEXT_ID as the
  // raw context key - it must not gain a host prefix here either.
  const explicit = process.env.COWORK_FLOW_CONTEXT_ID;
  if (typeof explicit === "string" && explicit.trim()) {
    const key = sanitizeContextKey(explicit);
    if (key) return key;
  }
  const candidates = [
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

// One-level scan of bindable tasks for rebind hints; tasks/archive lives two
// levels deeper so a plain readdir already excludes it.
function listActiveTasks(repoRoot) {
  const tasksDir = join(repoRoot, DIR_WORKFLOW, "tasks");
  const out = [];
  try {
    for (const name of readdirSync(tasksDir)) {
      const relative = `${DIR_WORKFLOW}/tasks/${name}`;
      const { status, missing } = readTaskStatus(repoRoot, relative);
      if (!missing && status !== "completed") out.push(`${relative} (${status})`);
    }
  } catch {
    // tasks dir unreadable
  }
  return out;
}

function formatRebindHints(repoRoot) {
  const active = listActiveTasks(repoRoot);
  if (active.length === 0) return "";
  return [
    "",
    "活动任务（可用 ./.cowork-flow/run task next <dir> 改绑）：",
    ...active.map((entry) => `- ${entry}`),
  ].join("\n");
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
    // An explicitly identified session without its own file must not adopt
    // another session's binding - the CLI reports no_task for the same state.
    if (!own) return null;
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

// Stable-sorted serialization shared by every host implementation of the
// contract fingerprint (Python sort_keys and the opencode plugin use the
// same semantics), so the digest stays identical across hosts.
function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function contractFingerprint(root, contracts) {
  const hash = createHash("sha256");
  hash.update(stableStringify(contracts));
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
// State snapshot (written atomically by lifecycle transitions)
// ---------------------------------------------------------------------------
function loadStateSnapshot(repoRoot) {
  try {
    const data = JSON.parse(
      readFileSync(
        join(repoRoot, DIR_WORKFLOW, ".runtime", "state-snapshot.json"),
        "utf8"
      )
    );
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

function resolveBreadcrumbKey(repoRoot, activeTask, status) {
  // A lifecycle-written snapshot describing exactly this task is more
  // authoritative than re-deriving the breadcrumb key from status.
  const snapshot = loadStateSnapshot(repoRoot);
  if (
    snapshot &&
    typeof snapshot.breadcrumbKey === "string" &&
    snapshot.breadcrumbKey.trim() &&
    snapshot.activeTaskPath === activeTask.taskPath &&
    snapshot.status === status
  ) {
    return snapshot.breadcrumbKey;
  }
  return status;
}

// ---------------------------------------------------------------------------
// Build context blocks
// ---------------------------------------------------------------------------
const DECISION_ANCHOR_STATES = ["planning", "in_progress", "review"];

function xmlAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

// Mirrors services/fact_view.py parse_decision_anchor (line-level, same
// section names) so the JS lines inject the same decision facts.
const STAGE_CONTRACT_STATES = ["in_progress", "review"];
const STAGE_CONTRACT_SCOPE_LIMIT = 8;
const STAGE_CONTRACT_SPECS_LIMIT = 4;
const STAGE_CONTRACT_VERIFY_LIMIT = 3;
const STAGE_CONTRACT_BUDGET = 1200;
const GATES_TEXT =
  "Gates: edits outside Scope are review blockers; CLAUDE.md and workflow " +
  "files are protected; spec/ edits may be allowed by review policy; " +
  "scope is agent-mutable (self-declared via task context add)";

function parseDecisionAnchor(text) {
  const result = {
    goal: "",
    acceptanceCriteria: [],
    rejectedOptions: [],
    validationCommands: [],
    scopeBoundary: "",
  };
  const goalLines = [];
  let section = null;
  for (const raw of String(text ?? "").split("\n")) {
    const line = raw.trim();
    const heading = line.match(/^##\s*(.+?)\s*$/);
    if (heading) {
      section = ["目标", "验收标准", "被拒方案", "验证命令", "范围边界"].includes(heading[1])
        ? heading[1]
        : null;
      continue;
    }
    if (section === "目标") {
      if (line) goalLines.push(line);
    } else if (section === "验收标准") {
      const match = raw.match(/^\s*-\s*\[[ xX]?\]\s*(AC-[A-Za-z0-9-]+)\s*[:：]\s*(.+?)\s*$/);
      if (match) result.acceptanceCriteria.push({ id: match[1], text: match[2] });
    } else if (section === "被拒方案") {
      const match = raw.match(/^\s*-\s*\*\*(.+?)\*\*/);
      if (match) result.rejectedOptions.push(match[1].trim());
    } else if (section === "验证命令") {
      let command = line;
      if (command.startsWith("- ")) command = command.slice(2).trim();
      if (command && result.validationCommands.length < 5) {
        result.validationCommands.push(command.slice(0, 120));
      }
    } else if (section === "范围边界") {
      if (line && !result.scopeBoundary) result.scopeBoundary = line.slice(0, 160);
    }
  }
  result.goal = goalLines.join("\n").slice(0, 300);
  return result;
}

function decisionAnchorBlock(repoRoot, taskPath, status) {
  if (!taskPath) return null;
  let effective = status;
  if (status === "delegated_subtask") {
    const taskStatus = readTaskStatus(repoRoot, taskPath);
    if (taskStatus.missing || typeof taskStatus.status !== "string") return null;
    effective = taskStatus.status;
  }
  if (!DECISION_ANCHOR_STATES.includes(effective)) return null;
  let parsed;
  try {
    parsed = parseDecisionAnchor(
      readFileSync(join(repoRoot, taskPath, "decision-anchor.md"), "utf8")
    );
  } catch {
    return null;
  }
  if (!parsed.goal && parsed.acceptanceCriteria.length === 0) return null;
  const lines = [`<decision-anchor task="${xmlAttr(taskPath)}">`];
  if (parsed.goal) {
    lines.push(`Goal: ${parsed.goal.split("\n")[0].slice(0, 160)}`);
  }
  if (parsed.acceptanceCriteria.length > 0) {
    lines.push(
      `Acceptance: ${parsed.acceptanceCriteria
        .slice(0, 8)
        .map((item) => `${item.id} ${item.text.slice(0, 80)}`)
        .join("; ")}`
    );
  }
  if (parsed.rejectedOptions.length > 0) {
    lines.push(`Rejected: ${parsed.rejectedOptions.slice(0, 6).join("; ")}`);
  }
  lines.push("</decision-anchor>");
  return lines.join("\n");
}

function withDecisionAnchor(block, repoRoot, taskPath, status) {
  const anchor = decisionAnchorBlock(repoRoot, taskPath, status);
  return anchor ? `${anchor}\n\n${block}` : block;
}

// Mirrors services/fact_view.py file_scope_whitelist + spec_pointer_files +
// build_stage_contract. Keep the line formatting byte-identical to Python —
// the cross-host equality test locks it.
function readImplementEntries(repoRoot, taskPath) {
  let text;
  try {
    text = readFileSync(join(repoRoot, taskPath, "implement.jsonl"), "utf8");
  } catch {
    return [];
  }
  const entries = [];
  for (const line of String(text ?? "").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const entry = JSON.parse(trimmed);
      if (entry && typeof entry === "object") entries.push(entry);
    } catch {
      // Skip malformed lines; Python side reports them separately.
    }
  }
  return entries;
}

function stageContractBlock(repoRoot, taskPath, status) {
  if (!taskPath) return null;
  let effective = status;
  if (status === "delegated_subtask") {
    const taskStatus = readTaskStatus(repoRoot, taskPath);
    if (taskStatus.missing || typeof taskStatus.status !== "string") return null;
    effective = taskStatus.status;
  }
  if (!STAGE_CONTRACT_STATES.includes(effective)) return null;

  const entries = readImplementEntries(repoRoot, taskPath);
  const whitelist = [];
  const specFiles = [];
  for (const entry of entries) {
    const file = typeof entry.file === "string" ? entry.file : "";
    const normalized = file.replaceAll("\\", "/");
    while (normalized.startsWith("./")) {
      normalized = normalized.slice(2);
    }
    if (!normalized) continue;
    const type = typeof entry.type === "string" && entry.type ? entry.type : "file";
    if (type === "directory") continue;
    whitelist.push({ file: normalized, type });
    if (normalized.startsWith(".cowork-flow/spec/")) specFiles.push(normalized);
  }

  let parsed = {
    goal: "",
    acceptanceCriteria: [],
    rejectedOptions: [],
    validationCommands: [],
    scopeBoundary: "",
  };
  try {
    parsed = parseDecisionAnchor(
      readFileSync(join(repoRoot, taskPath, "decision-anchor.md"), "utf8")
    );
  } catch {
    // Absent anchor: the contract still carries scope/gates.
  }

  const lines = [`<stage-contract task="${xmlAttr(taskPath)}">`];
  const scopeItems = whitelist.slice(0, STAGE_CONTRACT_SCOPE_LIMIT).map((e) => e.file);
  let scopeText = scopeItems.length > 0 ? scopeItems.join("; ") : "(empty)";
  const more = whitelist.length - scopeItems.length;
  if (more > 0) scopeText += ` (+${more} more in implement.jsonl)`;
  lines.push(`Scope: ${scopeText} [agent-mutable]`);
  if (specFiles.length > 0) {
    const specItems = specFiles.slice(0, STAGE_CONTRACT_SPECS_LIMIT);
    let specsText = specItems.join("; ");
    const specMore = specFiles.length - specItems.length;
    if (specMore > 0) specsText += ` (+${specMore} more)`;
    lines.push(`Specs: ${specsText}`);
  }
  lines.push(GATES_TEXT);
  if (parsed.validationCommands.length > 0) {
    lines.push(
      "Verify: " +
        parsed.validationCommands.slice(0, STAGE_CONTRACT_VERIFY_LIMIT).join("; ")
    );
  }
  lines.push("</stage-contract>");
  return lines.join("\n").slice(0, STAGE_CONTRACT_BUDGET);
}

function withStageFacts(block, repoRoot, taskPath, status) {
  const anchor = decisionAnchorBlock(repoRoot, taskPath, status);
  const contract = stageContractBlock(repoRoot, taskPath, status);
  const parts = [anchor, contract].filter(Boolean);
  return parts.length > 0 ? `${parts.join("\n\n")}\n\n${block}` : block;
}

function normalizeScopePath(value) {
  let normalized = String(value ?? "").replaceAll("\\", "/");
  while (normalized.startsWith("./")) {
    normalized = normalized.slice(2);
  }
  return normalized;
}

// Per-edit out-of-scope warning (zcode-only capability: editScopeWarning).
// Short path by design — returns at most one warning line, or "" when the
// edit is in scope, there is no active in_progress/review task, or the
// session is a subagent (delegated sessions stay silent, per the capability
// matrix fallback to the static stage-contract preview).
function editScopeWarning(input, filePath) {
  const root = findProjectRoot(input);
  if (!root) return "";
  const activeTask = readActiveTask(root, resolveSessionKey(input));
  if (!activeTask || !activeTask.taskPath) return "";
  if (activeTask.scope === "subagent") return "";
  const { status, missing } = readTaskStatus(root, activeTask.taskPath);
  if (missing || !STAGE_CONTRACT_STATES.includes(status)) return "";

  const target = normalizeScopePath(filePath);
  const entries = readImplementEntries(root, activeTask.taskPath);
  const inScope = entries.some((entry) => {
    const type = typeof entry.type === "string" && entry.type ? entry.type : "file";
    if (type === "directory") return false;
    return normalizeScopePath(entry.file) === target;
  });
  if (inScope) return "";

  const payload = {
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext:
        `⚠️ ${target} is outside the task's declared scope. ` +
        "If intended, add it with `task context add` (agent-mutable) or revert the edit.",
    },
  };
  return JSON.stringify(payload, null, 2);
}

function buildContext(repoRoot, activeTask, breadcrumbs) {
  const fallback = "Run ./.cowork-flow/run task next for the current workflow step.";

  if (!activeTask) {
    const body = breadcrumbs.no_task || fallback;
    const hints = formatRebindHints(repoRoot);
    return `<workflow-state status="no_task" source="task next / ${DIR_WORKFLOW}/spec">
${body}${hints ? `\n${hints}` : ""}
</workflow-state>`;
  }

  const { status, missing } = readTaskStatus(repoRoot, activeTask.taskPath);
  const scope = activeTask.scope === "subagent" ? "\nScope: subagent" : "";

  if (missing) {
    const hints = formatRebindHints(repoRoot);
    return `<workflow-state status="no_task" source="runtime-session">
Session 指向的任务目录不存在（${activeTask.taskPath}）。
当前项目无有效任务。请运行 ./.cowork-flow/run task next --run --title "<title>" --slug <task-name> --assignee <name> 创建新任务。${hints ? `\n${hints}` : ""}
</workflow-state>`;
  }

  const breadcrumbKey = resolveBreadcrumbKey(repoRoot, activeTask, status);
  const body = breadcrumbs[breadcrumbKey] || breadcrumbs[status] || fallback;
  return withStageFacts(
    `<workflow-state task="${xmlAttr(activeTask.taskPath)}" status="${xmlAttr(status)}" source="runtime-session">
${body}${scope}
</workflow-state>`,
    repoRoot,
    activeTask.taskPath,
    status
  );
}

function buildDelegatedSubtask(contextId, ctx) {
  const taskPath = ctx?.task_dir || "unknown";
  const lines = [
    `<workflow-state task="${xmlAttr(taskPath)}" status="delegated_subtask" source="runtime-context:${xmlAttr(contextId)}">`,
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
  return withStageFacts(
    lines.join("\n"),
    findProjectRoot({}),
    taskPath,
    "delegated_subtask"
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  if (process.env.COWORK_FLOW_HOOKS === "0" || process.env.COWORK_FLOW_DISABLE_HOOKS === "1") {
    process.exit(0);
  }

  const input = readHookInput();

  // Mid-turn refresh: only lifecycle commands may re-inject state; every
  // other Bash call stays silent so tool streams are not spammed.
  if (
    typeof input?.hook_event_name === "string" &&
    input.hook_event_name.trim() === "PostToolUse"
  ) {
    // Edit-scope short path: one warning line at most, never the full block
    // (an edit storm must not multiply the whole injection payload).
    const toolName = String(input?.tool_name || "");
    const editedPath = input?.tool_input?.file_path;
    if (
      ["Edit", "Write", "MultiEdit"].includes(toolName) &&
      typeof editedPath === "string" &&
      editedPath.trim()
    ) {
      process.stdout.write(
        editScopeWarning(input, editedPath.trim())
      );
      process.exit(0);
    }
    // Normalize separators so Windows run.cmd invocations still match; the
    // bare-run fallback covers `cd .cowork-flow && ./run task ...` forms.
    const command = String(input?.tool_input?.command || "").replaceAll("\\", "/");
    if (
      !command.includes(".cowork-flow/run") &&
      !/\brun(?:\.cmd)?\s+task\b/.test(command)
    ) {
      process.exit(0);
    }
  }

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
    // Use the normalized event so legacy hosts whose only signal is the
    // plugin-root env (detectEventName guesses SessionStart) keep receiving
    // the full block they got before slimming.
    if (event === "SessionStart") {
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
