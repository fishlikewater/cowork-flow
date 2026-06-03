import { createHash } from "node:crypto"
import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const DEFAULT_CONTRACT_REGISTRY = {
  contracts: [
    {
      id: "COWORK_ENTRY_CONTRACT_V1",
      path: ".cowork-flow/spec/entry-contract.md",
      digest: [
        "Classify COWORK_DELEGATION_V1 and COWORK_DISPATCH_V1 before workflow recovery.",
        "UNKNOWN entries must not start, resume, archive, commit, or dispatch subagents.",
      ],
      readWhen: ["before task start/resume/archive", "before subagent dispatch"],
    },
    {
      id: "COWORK_DELEGATION_V1",
      path: ".cowork-flow/spec/delegation-envelope.md",
      digest: [
        "ACK must match dispatch_id and ack_token before EXECUTE.",
        "DELEGATED_SOFT entries are advisory and cannot complete Implement or Check.",
      ],
      readWhen: ["before formal subagent dispatch", "when using a generic worker"],
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

export const CoworkFlowPlugin = async () => {
  return {
    "experimental.chat.system.transform": async (input, output) => {
      output.system.push(buildContractDigest(input))
    },
  }
}
