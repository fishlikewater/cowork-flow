import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const DEFAULT_CONTRACT_REGISTRY = {
  contracts: [
    {
      id: "COWORK_ENTRY_CONTRACT_V2",
      path: ".cowork-flow/spec/core/entry.md",
      digest: [
        "Structured signals from adapter.yaml entrySignals are authoritative; legacy fallback is opt-in and fail-closed remains the default.",
        "Runtime context, not prompt labels, identifies formal subagent sessions.",
      ],
      readWhen: ["before task start/resume/archive", "when prompt and bootstrap text conflict"],
    },
    {
      id: "RUNTIME_CONTEXT_DISPATCH_V2",
      path: ".cowork-flow/spec/core/dispatch.md",
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
  const registryFile = resolve(root, ".cowork-flow", "spec", "registry.json")
  let data = DEFAULT_CONTRACT_REGISTRY
  try {
    data = JSON.parse(readFileSync(registryFile, "utf8"))
  } catch {
    data = DEFAULT_CONTRACT_REGISTRY
  }

  if (!Array.isArray(data?.contracts)) {
    return DEFAULT_CONTRACT_REGISTRY.contracts
  }
  return data.contracts.filter((contract) => contract && typeof contract === "object")
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
  const contracts = loadContractRegistry(root)
  const fingerprint = contractFingerprint(root, contracts)
  const lines = [
    '<cowork-runtime host="opencode" adapter="opencode.task">',
    `<contract-digest fingerprint="${fingerprint}">`,
    "policy: repeat this short digest every plugin transform; read full spec files only before listed actions.",
  ]

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

function resolveSessionRole(input) {
  return resolveRuntimeContextId(input) ? "command" : "main"
}

function resolveInvocationKind(_input) {
  return "interactive"
}

function buildEntrySignalsBlock(input) {
  return [
    "<opencode-entry-signals>",
    `sessionRole: ${resolveSessionRole(input)}`,
    `invocationKind: ${resolveInvocationKind(input)}`,
    "</opencode-entry-signals>",
  ].join("\n")
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
  if (!output.env || typeof output.env !== "object") {
    output.env = {}
  }
  if (!output.env.SESSIONROLE) {
    output.env.SESSIONROLE = resolveSessionRole(input)
  }
  if (!output.env.INVOCATIONKIND) {
    output.env.INVOCATIONKIND = resolveInvocationKind(input)
  }
  const contextKey = resolveContextKey(input)
  if (!contextKey) {
    return
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

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z")
}

function flowStoreEval(root, code, payload = {}) {
  const script = [
    "import json, os, sys",
    "from pathlib import Path",
    "root = Path(sys.argv[1])",
    "payload = json.loads(sys.stdin.read() or '{}')",
    "sys.path.insert(0, str(root / '.cowork-flow' / 'scripts'))",
    "from flow.store import FlowStore",
    "from common.paths import FILE_FLOW_DB",
    "db = root / '.cowork-flow' / FILE_FLOW_DB",
    "with FlowStore(str(db)) as store:",
    ...code.map((line) => `    ${line}`),
  ].join("\n")
  try {
    const output = execFileSync(process.env.PYTHON || "python3", ["-c", script, root], {
      encoding: "utf8",
      input: JSON.stringify(payload),
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
    })
    return output.trim() ? JSON.parse(output) : null
  } catch {
    return null
  }
}

function readRuntimeContext(root, runtimeContextId) {
  return flowStoreEval(root, [
    "context = store.get_runtime_context(payload.get('runtime_context_id', ''))",
    "print(json.dumps(context, ensure_ascii=False, sort_keys=True))",
  ], { runtime_context_id: runtimeContextId })
}

function writeRuntimeContext(root, context) {
  return flowStoreEval(root, [
    "context = payload.get('context')",
    "if isinstance(context, dict):",
    "    store.upsert_runtime_context(context)",
    "    print(json.dumps(store.get_runtime_context(context.get('runtime_context_id') or context.get('id')), ensure_ascii=False, sort_keys=True))",
  ], { context })
}

function writeRuntimeSession(root, contextKey, session) {
  return flowStoreEval(root, [
    "context_key = payload.get('context_key')",
    "session = payload.get('session')",
    "if isinstance(context_key, str) and isinstance(session, dict):",
    "    store.upsert_runtime_session(context_key, session)",
    "    print(json.dumps(store.get_runtime_session(context_key), ensure_ascii=False, sort_keys=True))",
  ], { context_key: contextKey, session })
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
  writeRuntimeSession(root, contextKey, session)
  const updated = {
    ...context,
    status: "bound",
    bound_context_key: contextKey,
    bound_at: context.bound_at || nowIso(),
    last_seen_at: nowIso(),
  }
  return writeRuntimeContext(root, updated) || updated
}

function buildRuntimeWorkflowState(input) {
  const root = findRepoRoot(input)
  const runtimeContextId = resolveRuntimeContextId(input)
  if (!runtimeContextId) {
    return null
  }

  const context = readRuntimeContext(root, runtimeContextId)
  if (!context || context.scope !== "subagent" || context.status === "closed") {
    return [
      "<workflow-state>",
      "Status: delegated_subtask",
      `Source: runtime-context-invalid:${runtimeContextId}`,
      `Runtime context: ${runtimeContextId}`,
      "Scope: subagent",
      "Runtime context is missing, closed, or invalid. Do not run start/resume/task start/archive/commit/spawn.",
      "</workflow-state>",
    ].join("\n")
  }

  const bound = bindRuntimeContext(root, runtimeContextId, context, input)
  const assignment = bound.assignment && typeof bound.assignment === "object" ? bound.assignment : {}
  const header = [
    "<workflow-state>",
    typeof bound.task_dir === "string" && bound.task_dir.trim() ? `Task: ${bound.task_dir.trim()}` : null,
    "Status: delegated_subtask",
    `Source: runtime-context:${runtimeContextId}`,
    `Runtime context: ${runtimeContextId}`,
    `Agent: ${bound.agent_type || "unknown"}`,
    "Scope: subagent",
    "Do not run start/resume/task start/archive/commit/spawn.",
    typeof assignment.goal === "string" && assignment.goal.trim() ? `Goal: ${assignment.goal.trim()}` : null,
    "</workflow-state>",
  ].filter(Boolean)
  return header.join("\n")
}

export const CoworkFlowPlugin = async () => {
  return {
    "shell.env": async (input, output) => {
      injectShellEnv(input, output)
    },
    "experimental.chat.system.transform": async (input, output) => {
      output.system.push(
        [
          buildContractDigest(input),
          buildEntrySignalsBlock(input),
          buildRuntimeWorkflowState(input),
        ]
          .filter(Boolean)
          .join("\n\n")
      )
    },
  }
}
