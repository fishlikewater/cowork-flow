import { createHash } from "node:crypto"
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

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
}

const pluginRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..")

function asStringList(value) {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item) => typeof item === "string" && item.trim())
}

function inputCwd(input) {
  for (const value of [
    input?.cwd,
    input?.session?.cwd,
    input?.context?.cwd,
    input?.workspace?.cwd,
  ]) {
    if (typeof value === "string" && value.trim()) {
      return value
    }
  }
  return null
}

function findRepoRoot(input) {
  const candidates = [
    inputCwd(input),
    typeof process !== "undefined" ? process.cwd?.() : null,
    pluginRoot,
  ].filter(Boolean)

  for (const candidate of candidates) {
    let current = resolve(candidate)
    while (true) {
      if (existsSync(resolve(current, ".cowork-flow"))) {
        return current
      }
      const parent = resolve(current, "..")
      if (parent === current) {
        break
      }
      current = parent
    }
  }
  return pluginRoot
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`
  }
  return JSON.stringify(value)
}

function loadContractRegistry(root) {
  const registryFile = resolve(root, ".cowork-flow", "spec", "runtime", "contract-registry.json")
  let data = DEFAULT_CONTRACT_REGISTRY
  let warning = null
  try {
    data = JSON.parse(readFileSync(registryFile, "utf8"))
  } catch (error) {
    data = DEFAULT_CONTRACT_REGISTRY
    warning = `contract registry unavailable or invalid at ${registryFile}; using fallback digest`
  }

  if (!Array.isArray(data?.contracts)) {
    return {
      contracts: DEFAULT_CONTRACT_REGISTRY.contracts,
      warning: warning || `contract registry has no contracts array at ${registryFile}; using fallback digest`,
    }
  }
  return {
    contracts: data.contracts.filter((contract) => contract && typeof contract === "object"),
    warning,
  }
}

function contractFingerprint(root, contracts) {
  const digest = createHash("sha256")
  digest.update(stableStringify(contracts), "utf8")
  for (const contract of contracts) {
    const path = contract.path
    if (typeof path !== "string" || !path.trim()) {
      continue
    }
    try {
      digest.update(readFileSync(resolve(root, path)))
    } catch {
      digest.update(`missing:${path}`, "utf8")
    }
  }
  return digest.digest("hex").slice(0, 16)
}

function buildContractDigest(input) {
  const root = findRepoRoot(input)
  const { contracts, warning } = loadContractRegistry(root)
  const fingerprint = contractFingerprint(root, contracts)
  const lines = [
    '<cowork-runtime host="opencode" adapter="opencode.task">',
    `<contract-digest fingerprint="${fingerprint}">`,
    "policy: repeat this short digest every plugin transform; read full spec files only before listed actions.",
  ]
  if (warning) {
    lines.push(`warning: ${warning}`)
  }

  for (const contract of contracts) {
    const contractId = contract.id
    if (typeof contractId !== "string" || !contractId.trim()) {
      continue
    }
    const path = typeof contract.path === "string" && contract.path.trim() ? contract.path : "<missing-path>"
    lines.push(`- ${contractId}: ${path}`)
    for (const item of asStringList(contract.digest).slice(0, 2)) {
      lines.push(`  digest: ${item}`)
    }
    const readWhen = asStringList(contract.readWhen)
    if (readWhen.length > 0) {
      lines.push(`  read_before: ${readWhen.join("; ")}`)
    }
  }

  lines.push("</contract-digest>", "</cowork-runtime>")
  return lines.join("\n")
}

function sanitize(value) {
  return String(value ?? "")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "_")
    .replace(/^[._-]+|[._-]+$/g, "")
    .slice(0, 160)
}

function firstString(input, keys) {
  for (const key of keys) {
    const value = input?.[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }
  return null
}

function promptText(input) {
  const direct = firstString(input, ["prompt", "user_prompt", "userPrompt", "message", "input"])
  if (direct) {
    return direct
  }
  const messages = input?.messages
  if (Array.isArray(messages)) {
    return messages
      .map((item) => item?.content)
      .filter((item) => typeof item === "string" && item.trim())
      .join("\n")
  }
  return ""
}

function resolveRuntimeContextId(input) {
  const envValue =
    typeof process !== "undefined" && process?.env?.COWORK_FLOW_RUNTIME_CONTEXT_ID
      ? process.env.COWORK_FLOW_RUNTIME_CONTEXT_ID
      : null
  if (envValue && envValue.trim()) {
    return sanitize(envValue)
  }

  const direct = firstString(input, [
    "COWORK_FLOW_RUNTIME_CONTEXT_ID",
    "cowork_runtime_context_id",
    "runtime_context_id",
  ])
  if (direct) {
    return sanitize(direct)
  }

  const match = promptText(input).match(/^\s*cowork_runtime_context_id\s*:\s*([A-Za-z0-9._-]+)\s*$/im)
  return match ? sanitize(match[1]) : null
}

function resolveOpenCodeSessionId(input) {
  const direct = firstString(input, [
    "OPENCODE_SESSION_ID",
    "opencode_session_id",
    "sessionID",
    "sessionId",
    "session_id",
  ])
  if (direct) {
    return sanitize(direct)
  }
  const nested = firstString(input?.session, ["id", "sessionID", "sessionId", "session_id"])
  return nested ? sanitize(nested) : null
}

function resolveContextKey(input) {
  const explicit = firstString(input, ["COWORK_FLOW_CONTEXT_ID", "cowork_flow_context_id", "context_id"])
  if (explicit) {
    return sanitize(explicit)
  }
  const opencodeSession = resolveOpenCodeSessionId(input)
  return opencodeSession ? `opencode_${sanitize(opencodeSession)}` : null
}

function injectShellEnv(input, output) {
  const contextKey = resolveContextKey(input)
  if (!contextKey) {
    return
  }
  if (!output.env || typeof output.env !== "object") {
    output.env = {}
  }
  if (!output.env.COWORK_FLOW_CONTEXT_ID) {
    output.env.COWORK_FLOW_CONTEXT_ID = contextKey
  }
  const opencodeSession = resolveOpenCodeSessionId(input)
  if (opencodeSession && !output.env.OPENCODE_SESSION_ID) {
    output.env.OPENCODE_SESSION_ID = opencodeSession
  }
}

function resolveHostContextKey(input) {
  const direct = firstString(input, ["cowork_host_context_key", "host_context_key", "COWORK_FLOW_HOST_CONTEXT_KEY"])
  if (direct) {
    return sanitize(direct)
  }

  const match = promptText(input).match(/^\s*cowork_host_context_key\s*:\s*([A-Za-z0-9._-]+)\s*$/im)
  return match ? sanitize(match[1]) : null
}

function readJson(path) {
  try {
    const data = JSON.parse(readFileSync(path, "utf8"))
    return data && typeof data === "object" && !Array.isArray(data) ? data : null
  } catch {
    return null
  }
}

function writeJson(path, data) {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8")
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z")
}

function bindRuntimeContext(root, runtimeContextId, context, input) {
  const contextKey = resolveHostContextKey(input) || resolveContextKey(input)
  if (!contextKey) {
    return context
  }
  if (typeof context.bound_context_key === "string" && context.bound_context_key.trim() && context.bound_context_key !== contextKey) {
    return context
  }
  const session = {
    schema_version: 2,
    scope: "subagent",
    runtime_context_id: runtimeContextId,
    platform: "opencode",
    status: "bound",
    last_seen_at: nowIso(),
  }
  if (typeof context.task_dir === "string" && context.task_dir.trim()) {
    session.active_task_path = context.task_dir.trim()
  }
  writeJson(resolve(root, ".cowork-flow", ".runtime", "sessions", `${contextKey}.json`), session)
  const updated = {
    ...context,
    status: "bound",
    bound_context_key: contextKey,
    bound_at: context.bound_at || nowIso(),
    last_seen_at: nowIso(),
  }
  writeJson(resolve(root, ".cowork-flow", ".runtime", "subagents", `${runtimeContextId}.json`), updated)
  return updated
}

// Attribute header + decision-anchor helpers, mirroring
// services/fact_view.py and the zcode hook (context-injection.md stage 1).
const DECISION_ANCHOR_STATES = ["planning", "in_progress", "review"]

function xmlAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
}

const STAGE_CONTRACT_STATES = ["in_progress", "review"]
const STAGE_CONTRACT_SCOPE_LIMIT = 8
const STAGE_CONTRACT_SPECS_LIMIT = 4
const STAGE_CONTRACT_VERIFY_LIMIT = 3
const STAGE_CONTRACT_BUDGET = 1200
const GATES_TEXT =
  "Gates: edits outside Scope are review blockers; CLAUDE.md and workflow " +
  "files are protected; spec/ edits may be allowed by review policy; " +
  "scope is agent-mutable (self-declared via task context add)"
// Delegated subtasks render the parent task's scope as a read-only reference.
const GATES_TEXT_READONLY =
  "Gates: edits outside Scope are review blockers; CLAUDE.md and workflow " +
  "files are protected; spec/ edits may be allowed by review policy; " +
  "scope is inherited from the parent task (read-only reference)"

function parseDecisionAnchor(text) {
  const result = {
    goal: "",
    acceptanceCriteria: [],
    rejectedOptions: [],
    validationCommands: [],
    scopeBoundary: "",
  }
  const goalLines = []
  let section = null
  for (const raw of String(text ?? "").split("\n")) {
    const line = raw.trim()
    const heading = line.match(/^##\s*(.+?)\s*$/)
    if (heading) {
      section = ["目标", "验收标准", "被拒方案", "验证命令", "范围边界"].includes(heading[1]) ? heading[1] : null
      continue
    }
    if (section === "目标") {
      if (line) goalLines.push(line)
    } else if (section === "验收标准") {
      const match = raw.match(/^\s*-\s*\[[ xX]?\]\s*(AC-[A-Za-z0-9-]+)\s*[:：]\s*(.+?)\s*$/)
      if (match) result.acceptanceCriteria.push({ id: match[1], text: match[2] })
    } else if (section === "被拒方案") {
      const match = raw.match(/^\s*-\s*\*\*(.+?)\*\*/)
      if (match) result.rejectedOptions.push(match[1].trim())
    } else if (section === "验证命令") {
      let command = line
      if (command.startsWith("- ")) command = command.slice(2).trim()
      if (command && result.validationCommands.length < 5) {
        result.validationCommands.push(command.slice(0, 120))
      }
    } else if (section === "范围边界") {
      if (line && !result.scopeBoundary) result.scopeBoundary = line.slice(0, 160)
    }
  }
  result.goal = goalLines.join("\n").slice(0, 300)
  return result
}

// Port of services/context_paths.py::_is_valid_context_path: the JS side must
// skip exactly the entries the Python whitelist drops (absolute paths, drive
// letters, dot segments, wildcards, trailing slash on planned/deleted files).
function isValidScopePath(normalized, raw, type) {
  if (!["file", "planned-file", "deleted-file"].includes(type)) return false
  if (!normalized || normalized.startsWith("/")) return false
  if (/^[A-Za-z]:/.test(normalized)) return false
  const segments = normalized.split("/")
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) return false
  if (/[*?[\]]/.test(normalized)) return false
  if (["planned-file", "deleted-file"].includes(type) && /[\\/]$/.test(raw)) return false
  return true
}

// Mirrors services/fact_view.py file_scope_whitelist + spec_pointer_files:
// directory entries authorize nothing, non-canonical entries are dropped.
function buildScopeWhitelist(entries) {
  const whitelist = []
  const specFiles = []
  for (const entry of entries) {
    const file = typeof entry.file === "string" ? entry.file : ""
    let normalized = file.replaceAll("\\", "/")
    while (normalized.startsWith("./")) {
      normalized = normalized.slice(2)
    }
    const type = typeof entry.type === "string" && entry.type ? entry.type : "file"
    if (type === "directory") continue
    if (!isValidScopePath(normalized, file, type)) continue
    whitelist.push({ file: normalized, type })
    if (normalized.startsWith(".cowork-flow/spec/")) specFiles.push(normalized)
  }
  return { whitelist, specFiles }
}

function scopeRow(entries, total, suffix) {
  const text = entries.length > 0 ? entries.join("; ") : "(empty)"
  const more = total - entries.length
  const extra = more > 0 ? ` (+${more} more in implement.jsonl)` : ""
  return `Scope: ${text}${extra} ${suffix}`
}

// Mirrors services/fact_view.py::_fit_stage_contract: degrade an over-budget
// block without ever emitting a malformed one — closing tag and guard rows
// (Scope/Gates) always survive. Keep row-role rules and drop order identical.
function fitStageContract(lines, scopeEntries, scopeTotal, mutable) {
  const budget = STAGE_CONTRACT_BUDGET
  if (lines.join("\n").length <= budget) return lines
  const removable = []
  for (let i = 1; i < lines.length - 1; i++) {
    if (!lines[i].startsWith("Scope:") && !lines[i].startsWith("Gates:")) {
      removable.push(i)
    }
  }
  for (let i = removable.length - 1; i >= 0; i--) {
    const reduced = lines.filter((_, j) => j !== removable[i])
    if (reduced.join("\n").length <= budget) return reduced
    lines = reduced
  }
  const suffix = mutable ? "[agent-mutable]" : "[read-only]"
  let pool = scopeEntries.slice()
  while (pool.length > 1) {
    pool = pool.slice(0, -1)
    const candidate = lines.map((line) =>
      line.startsWith("Scope:") ? scopeRow(pool, scopeTotal, suffix) : line
    )
    if (candidate.join("\n").length <= budget) return candidate
    lines = candidate
  }
  if (lines.join("\n").length <= budget) return lines
  const closing = lines[lines.length - 1]
  const room = budget - closing.length
  const body = lines.slice(0, -1).join("\n")
  if (body.length <= room) return lines
  const head = body.slice(0, room).replace(/\s+$/, "")
  if (!head) return lines
  return [head, closing]
}

function stageContractBlock(root, taskPath, status, readonly = false) {
  if (!taskPath) {
    return null
  }
  let effective = status
  if (status === "delegated_subtask") {
    const data = readJson(resolve(root, taskPath, "task.json"))
    effective = data && typeof data.status === "string" ? data.status : null
    if (!effective) {
      return null
    }
  }
  if (!STAGE_CONTRACT_STATES.includes(effective)) {
    return null
  }
  let entries = []
  try {
    for (const line of String(readFileSync(resolve(root, taskPath, "implement.jsonl"), "utf8") ?? "").split("\n")) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        const entry = JSON.parse(trimmed)
        if (entry && typeof entry === "object") entries.push(entry)
      } catch {
        // Skip malformed lines; Python side reports them separately.
      }
    }
  } catch {
    // Absent jsonl: scope degrades to empty.
  }
  const { whitelist, specFiles } = buildScopeWhitelist(entries)
  let parsed
  try {
    parsed = parseDecisionAnchor(readFileSync(resolve(root, taskPath, "decision-anchor.md"), "utf8"))
  } catch {
    parsed = { goal: "", acceptanceCriteria: [], rejectedOptions: [], validationCommands: [], scopeBoundary: "" }
  }
  const suffix = readonly ? "[read-only]" : "[agent-mutable]"
  const lines = [`<stage-contract task="${xmlAttr(taskPath)}">`]
  lines.push(scopeRow(
    whitelist.slice(0, STAGE_CONTRACT_SCOPE_LIMIT).map((e) => e.file),
    whitelist.length,
    suffix
  ))
  if (specFiles.length > 0) {
    const specItems = specFiles.slice(0, STAGE_CONTRACT_SPECS_LIMIT)
    let specsText = specItems.join("; ")
    const specMore = specFiles.length - specItems.length
    if (specMore > 0) specsText += ` (+${specMore} more)`
    lines.push(`Specs: ${specsText}`)
  }
  lines.push(readonly ? GATES_TEXT_READONLY : GATES_TEXT)
  if (parsed.validationCommands.length > 0) {
    lines.push("Verify: " + parsed.validationCommands.slice(0, STAGE_CONTRACT_VERIFY_LIMIT).join("; "))
  }
  lines.push("</stage-contract>")
  return fitStageContract(
    lines,
    whitelist.slice(0, STAGE_CONTRACT_SCOPE_LIMIT).map((e) => e.file),
    whitelist.length,
    !readonly
  ).join("\n")
}

function withStageFacts(block, root, taskPath, status, readonly = false) {
  const anchor = decisionAnchorBlock(root, taskPath, status)
  const contract = stageContractBlock(root, taskPath, status, readonly)
  const parts = [anchor, contract].filter(Boolean)
  return parts.length > 0 ? `${parts.join("\n\n")}\n\n${block}` : block
}

function decisionAnchorBlock(root, taskPath, status) {
  if (!taskPath) {
    return null
  }
  let effective = status
  if (status === "delegated_subtask") {
    const data = readJson(resolve(root, taskPath, "task.json"))
    effective = data && typeof data.status === "string" ? data.status : null
    if (!effective) {
      return null
    }
  }
  if (!DECISION_ANCHOR_STATES.includes(effective)) {
    return null
  }
  let parsed
  try {
    parsed = parseDecisionAnchor(readFileSync(resolve(root, taskPath, "decision-anchor.md"), "utf8"))
  } catch {
    return null
  }
  if (!parsed.goal && parsed.acceptanceCriteria.length === 0) {
    return null
  }
  const lines = [`<decision-anchor task="${xmlAttr(taskPath)}">`]
  if (parsed.goal) {
    lines.push(`Goal: ${parsed.goal.split("\n")[0].slice(0, 160)}`)
  }
  if (parsed.acceptanceCriteria.length > 0) {
    lines.push(
      `Acceptance: ${parsed.acceptanceCriteria.slice(0, 8).map((item) => `${item.id} ${item.text.slice(0, 80)}`).join("; ")}`
    )
  }
  if (parsed.rejectedOptions.length > 0) {
    lines.push(`Rejected: ${parsed.rejectedOptions.slice(0, 6).join("; ")}`)
  }
  lines.push("</decision-anchor>")
  return lines.join("\n")
}

function withDecisionAnchor(block, root, taskPath, status) {
  const anchor = decisionAnchorBlock(root, taskPath, status)
  return anchor ? `${anchor}\n\n${block}` : block
}

function buildRuntimeWorkflowState(input) {
  const root = findRepoRoot(input)
  const runtimeContextId = resolveRuntimeContextId(input)
  if (!runtimeContextId) {
    return null
  }

  const contextFile = resolve(root, ".cowork-flow", ".runtime", "subagents", `${runtimeContextId}.json`)
  const context = readJson(contextFile)
  if (!context || context.scope !== "subagent" || context.status === "closed") {
    return [
      `<workflow-state status="delegated_subtask" source="runtime-context-invalid:${xmlAttr(runtimeContextId)}">`,
      `Runtime context: ${runtimeContextId}`,
      "Runtime context is missing, closed, or invalid. Do not run start/resume/task start/archive/commit/spawn.",
      "</workflow-state>",
    ].join("\n")
  }

  const bound = bindRuntimeContext(root, runtimeContextId, context, input)
  const assignment = bound.assignment && typeof bound.assignment === "object" ? bound.assignment : {}
  const taskDir = typeof bound.task_dir === "string" && bound.task_dir.trim() ? bound.task_dir.trim() : null
  const attrs = [
    taskDir ? ` task="${xmlAttr(taskDir)}"` : null,
    ' status="delegated_subtask"',
    ` source="runtime-context:${xmlAttr(runtimeContextId)}"`,
  ].filter(Boolean)
  const header = [
    `<workflow-state${attrs.join("")}>`,
    `Runtime context: ${runtimeContextId}`,
    `Agent: ${bound.agent_type || "unknown"}`,
    "Do not run start/resume/task start/archive/commit/spawn.",
    typeof assignment.goal === "string" && assignment.goal.trim() ? `Goal: ${assignment.goal.trim()}` : null,
    "</workflow-state>",
  ].filter(Boolean)
  return withStageFacts(header.join("\n"), root, taskDir, "delegated_subtask", true)
}

// Digest shape: full contract block on the first injection of a session,
// single fingerprint line afterwards, so long sessions do not pay the full
// listing on every prompt assembly. In-memory per plugin process; a process
// restart (e.g. resume) deliberately re-injects the full block.
const fullDigestSessions = new Set()

function buildInjectedDigest(input) {
  const root = findRepoRoot(input)
  if (!root) {
    return ""
  }
  const contextKey = resolveContextKey(input)
  const firstInjection = contextKey ? !fullDigestSessions.has(contextKey) : true
  if (firstInjection) {
    if (contextKey) {
      fullDigestSessions.add(contextKey)
    }
    return buildContractDigest(input)
  }
  const { contracts } = loadContractRegistry(root)
  return `<contract-fingerprint value="${contractFingerprint(root, contracts)}"/>`
}

export const CoworkFlowPlugin = async () => {
  return {
    "shell.env": async (input, output) => {
      injectShellEnv(input, output)
    },
    "experimental.chat.system.transform": async (input, output) => {
      output.system.push([buildInjectedDigest(input), buildRuntimeWorkflowState(input)].filter(Boolean).join("\n\n"))
    },
  }
}

export { contractFingerprint, stableStringify, stageContractBlock }
