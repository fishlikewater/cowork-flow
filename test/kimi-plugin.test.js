import assert from "node:assert/strict"
import { access, mkdir, mkdtemp, readdir, readFile, realpath, rm, stat, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"

import { runInstallKimiPlugin } from "../src/commands/install-kimi-code-plugin.js"
import { installedRegistryPath } from "../src/lib/kimi-installed-registry.js"
import { packageRoot } from "../src/lib/paths.js"
import { readPackageInfo } from "../src/lib/package-info.js"
import { readPluginMetadata } from "../src/lib/plugin-metadata.js"

const PLUGIN_NAME = "cowork-flow"
const MANIFEST_RELATIVE = [".kimi-plugin", "plugin.json"]
const SKILL_RELATIVE = ["skills", "cowork-flow-bootstrap", "SKILL.md"]

const payloadRoot = join(packageRoot, "presets", "kimi-code")

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"))
}

async function withKimiHome(home, run) {
  const previous = process.env.KIMI_CODE_HOME
  process.env.KIMI_CODE_HOME = home
  try {
    return await run()
  } finally {
    if (previous === undefined) delete process.env.KIMI_CODE_HOME
    else process.env.KIMI_CODE_HOME = previous
  }
}

async function seedKimiHome() {
  const home = await mkdtemp(join(tmpdir(), "cowork-flow-kimi-home-"))
  // A user's own plugin source sits beside ours, so every case can assert the
  // installer stays inside its own directory.
  const foreign = join(home, "plugins", "sources", "their-plugin")
  await mkdir(foreign, { recursive: true })
  await writeFile(join(foreign, "kimi.plugin.json"), '{"name":"their-plugin"}\n', "utf8")
  return { home, foreign }
}

function sourceDir(home) {
  return join(home, "plugins", "sources", PLUGIN_NAME)
}

function managedDir(home) {
  return join(home, "plugins", "managed", PLUGIN_NAME)
}

async function readRegistry(home) {
  return readJson(installedRegistryPath(home))
}

function coworkFlowRecord(registry) {
  return registry.plugins.find((entry) => entry.id === PLUGIN_NAME)
}

async function tree(dir, prefix = "") {
  const entries = {}
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const relative = `${prefix}${entry.name}`
    if (entry.isDirectory()) {
      Object.assign(entries, await tree(join(dir, entry.name), `${relative}/`))
    } else {
      entries[relative] = await readFile(join(dir, entry.name), "utf8")
    }
  }
  return entries
}

test("the kimi-code payload is a manifest plus the bootstrap skill", async () => {
  const manifest = await readJson(join(payloadRoot, ...MANIFEST_RELATIVE))
  const metadata = await readPluginMetadata()
  const { version } = await readPackageInfo()

  assert.equal(manifest.name, PLUGIN_NAME)
  assert.equal(manifest.version, version)
  assert.equal(manifest.interface.displayName, metadata.displayName)
  // This is what makes the plugin useful in a repository without a runtime:
  // Kimi Code loads the named Skill when a session starts.
  assert.deepEqual(manifest.sessionStart, { skill: "cowork-flow-bootstrap" })
  await access(join(payloadRoot, ...SKILL_RELATIVE))
})

// The byte-equality gate in plugin-metadata.test.js compares the manifest with
// its projection, so it cannot see this: teach the projection a key or a value
// the host rejects, regenerate, and byte-equality still holds. These are the
// rules the host parser actually applies (Kimi Code 1.0.3,
// `packages/agent-core-v2/src/app/plugin/manifest.ts`): a `skills` entry that
// does not start with "./" makes the host record the plugin as errored with zero
// skills, and `displayName` is only read from inside `interface`.
const HOST_READ_KEYS = [
  "name",
  "version",
  "description",
  "keywords",
  "homepage",
  "license",
  "author",
  "skills",
  "agents",
  "sessionStart",
  "mcpServers",
  "hooks",
  "commands",
  "interface",
  "skillInstructions",
  "systemPrompt",
  "systemPromptPath"
];
// The parser reads these and pushes an "info" diagnostic saying they are not
// supported by Kimi plugins, so writing one would ship a known-useless key.
const HOST_UNSUPPORTED_KEYS = ["tools", "apps", "inject", "configFile", "config_file", "bootstrap"];
const INTERFACE_KEYS = ["displayName", "shortDescription", "longDescription", "developerName", "websiteURL"];

test("the kimi-code manifest declares only what the host parser reads", async () => {
  const manifest = await readJson(join(payloadRoot, ...MANIFEST_RELATIVE))

  for (const key of Object.keys(manifest)) {
    assert.ok(
      HOST_READ_KEYS.includes(key),
      `kimi-code manifest must not declare ${key}: the host parser drops it without a diagnostic`
    );
    assert.ok(
      !HOST_UNSUPPORTED_KEYS.includes(key),
      `kimi-code manifest must not declare ${key}: the host reports it as unsupported`
    );
  }

  // Injection stays with the config.toml hook route: the host runs a plugin hook
  // with cwd pinned to the plugin root (and its hook schema is strict, so a
  // plugin cannot override it), where the shipped shim cannot locate a project.
  // Agents stay project-level because plugin agents have the lowest priority and
  // would always be shadowed.
  for (const key of ["hooks", "agents", "commands", "mcpServers"]) {
    assert.equal(manifest[key], undefined, `kimi-code manifest must not declare ${key}`)
  }

  // A relative entry without "./" is an error diagnostic for the host, and the
  // resolved directory has to sit inside the plugin or it is rejected.
  for (const entry of Array.isArray(manifest.skills) ? manifest.skills : [manifest.skills]) {
    assert.match(entry, /^\.\//, "the host requires every skills entry to start with ./");
    const resolved = join(payloadRoot, entry)
    assert.ok(resolved.startsWith(payloadRoot), `skills entry escapes the plugin: ${entry}`)
    assert.ok((await stat(resolved)).isDirectory(), `skills entry is not a directory: ${entry}`)
  }

  for (const key of Object.keys(manifest.interface)) {
    assert.ok(INTERFACE_KEYS.includes(key), `interface.${key} is not read by the host`);
  }
  for (const key of Object.keys(manifest.author)) {
    assert.ok(["name", "email"].includes(key), `author.${key} is not read by the host`);
  }
})

test("install-kimi-plugin installs the managed copy and registers it with the host", async () => {
  const { home, foreign } = await seedKimiHome()
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))

    // sources/ stays the stable reinstall source the registry's originalSource
    // names; the host itself never loads it.
    const target = sourceDir(home)
    assert.equal((await readJson(join(target, ...MANIFEST_RELATIVE))).name, PLUGIN_NAME)
    await access(join(target, ...SKILL_RELATIVE))

    // managed/ is the copy the host's loader parses on every start, stamped with
    // the package version so doctor can tell an up-to-date install from a stale one.
    const managed = managedDir(home)
    const { version } = await readPackageInfo()
    const managedManifest = await readJson(join(managed, ...MANIFEST_RELATIVE))
    assert.equal(managedManifest.name, PLUGIN_NAME)
    assert.equal(managedManifest.version, version)
    await access(join(managed, ...SKILL_RELATIVE))

    // One registry record, in the host's own field shape, pointing at managed/.
    const registry = await readRegistry(home)
    assert.equal(registry.version, 1)
    const record = coworkFlowRecord(registry)
    assert.deepEqual(Object.keys(record), [
      "id", "root", "source", "enabled", "installedAt", "updatedAt", "originalSource"
    ])
    assert.equal(record.root, await realpath(managed))
    assert.equal(record.source, "local-path")
    assert.equal(record.enabled, true)
    assert.equal(record.originalSource, target)
    assert.match(record.installedAt, /^\d{4}-\d{2}-\d{2}T/)

    assert.equal(await readFile(join(foreign, "kimi.plugin.json"), "utf8"), '{"name":"their-plugin"}\n')
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-kimi-plugin registers the plugin itself, with no slash-command handoff", async () => {
  // The registry record above is what the host's loader reads; the output must
  // not send the user into the TUI to finish an install that is already done.
  const { home } = await seedKimiHome()
  const lines = []
  const original = console.log
  try {
    console.log = (line) => lines.push(String(line))
    await withKimiHome(home, () => runInstallKimiPlugin([]))
  } finally {
    console.log = original
  }

  const output = lines.join("\n")
  assert.match(output, /Registered in /)
  assert.match(output, /Restart Kimi Code/)
  assert.doesNotMatch(output, /\/plugins install/)
  await rm(home, { recursive: true, force: true })
})

test("install-kimi-plugin dry-run writes nothing anywhere", async () => {
  const { home } = await seedKimiHome()
  const lines = []
  const original = console.log
  try {
    console.log = (line) => lines.push(String(line))
    await withKimiHome(home, () => runInstallKimiPlugin(["--dry-run"]))
  } finally {
    console.log = original
  }

  await assert.rejects(access(sourceDir(home)))
  await assert.rejects(access(managedDir(home)))
  await assert.rejects(access(installedRegistryPath(home)))
  assert.match(lines.join("\n"), /\[dry-run\] Would register/)
  await rm(home, { recursive: true, force: true })
})

test("reinstall keeps the first install time, the enable state and one record", async () => {
  const { home } = await seedKimiHome()
  try {
    const foreign = {
      id: "their-plugin",
      root: "C:\\elsewhere",
      source: "github",
      enabled: false,
      installedAt: "2026-01-01T00:00:00.000Z",
      updatedAt: "2026-01-01T00:00:00.000Z",
      originalSource: "https://github.com/their/plugin"
    }
    await mkdir(join(home, "plugins"), { recursive: true })
    await writeFile(installedRegistryPath(home), JSON.stringify({
      version: 1,
      plugins: [foreign, {
        id: PLUGIN_NAME,
        root: "C:\\old",
        source: "local-path",
        enabled: false,
        installedAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
        originalSource: "C:\\old"
      }]
    }, null, 2), "utf8")

    await withKimiHome(home, () => runInstallKimiPlugin([]))

    const registry = await readRegistry(home)
    assert.equal(registry.plugins.length, 2)
    // The neighbor's record round-trips byte for byte.
    assert.deepEqual(registry.plugins.find((entry) => entry.id === "their-plugin"), foreign)
    const record = coworkFlowRecord(registry)
    // A disabled plugin stays disabled on reinstall (the host's own
    // `enabled: existing?.enabled ?? true`), and the first install time sticks.
    assert.equal(record.enabled, false)
    assert.equal(record.installedAt, "2026-01-01T00:00:00.000Z")
    assert.notEqual(record.updatedAt, "2026-01-01T00:00:00.000Z")
    assert.equal(record.root, await realpath(managedDir(home)))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("a registry the host would reject fails the install before any write", async () => {
  const { home } = await seedKimiHome()
  try {
    await mkdir(join(home, "plugins"), { recursive: true })
    const junk = "{ definitely not JSON"
    await writeFile(installedRegistryPath(home), junk, "utf8")

    await assert.rejects(
      () => withKimiHome(home, () => runInstallKimiPlugin([])),
      /not valid JSON/
    )
    // Neither the file nor either payload copy may be touched: a merge into a
    // registry we cannot read would drop whatever other plugins it holds.
    assert.equal(await readFile(installedRegistryPath(home), "utf8"), junk)
    await assert.rejects(access(sourceDir(home)))
    await assert.rejects(access(managedDir(home)))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-kimi-plugin converges on the shipped payload", async () => {
  const { home } = await seedKimiHome()
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))
    await withKimiHome(home, () => runInstallKimiPlugin([]))
    await withKimiHome(home, () => runInstallKimiPlugin(["--force"]))

    assert.deepEqual(await tree(sourceDir(home)), await tree(payloadRoot))
    assert.deepEqual(await tree(managedDir(home)), await tree(payloadRoot))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-kimi-plugin refuses a foreign directory at its source path", async () => {
  const { home } = await seedKimiHome()
  try {
    const target = sourceDir(home)
    await mkdir(target, { recursive: true })
    await writeFile(join(target, "theirs.md"), "not ours\n", "utf8")

    await assert.rejects(
      () => withKimiHome(home, () => runInstallKimiPlugin([])),
      /not the cowork-flow plugin/
    )
    // The preview must not promise an install the real run refuses.
    await assert.rejects(
      () => withKimiHome(home, () => runInstallKimiPlugin(["--dry-run"])),
      /not the cowork-flow plugin/
    )
    assert.equal(await readFile(join(target, "theirs.md"), "utf8"), "not ours\n")

    await assert.rejects(
      () => withKimiHome(home, () => runInstallKimiPlugin(["--uninstall"])),
      /use --force to remove it anyway/
    )
    await withKimiHome(home, () => runInstallKimiPlugin(["--uninstall", "--force"]))
    await assert.rejects(access(target))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("uninstall removes the record and both copies, and keeps the neighbors", async () => {
  const { home } = await seedKimiHome()
  const foreign = {
    id: "their-plugin",
    root: "C:\\elsewhere",
    source: "github",
    enabled: false,
    installedAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    originalSource: "https://github.com/their/plugin"
  }
  const lines = []
  const original = console.log
  try {
    await mkdir(join(home, "plugins"), { recursive: true })
    await writeFile(installedRegistryPath(home), JSON.stringify({ version: 1, plugins: [foreign] }, null, 2), "utf8")

    await withKimiHome(home, () => runInstallKimiPlugin([]))
    console.log = (line) => lines.push(String(line))
    await withKimiHome(home, () => runInstallKimiPlugin(["--uninstall"]))
  } finally {
    console.log = original
  }

  // Both payload copies and the record are gone; the neighbor's record
  // round-trips byte for byte.
  await assert.rejects(access(sourceDir(home)))
  await assert.rejects(access(managedDir(home)))
  const registry = await readRegistry(home)
  assert.deepEqual(registry.plugins, [foreign])
  assert.equal(registry.version, 1)

  const output = lines.join("\n")
  assert.match(output, /Registry record removed/)
  assert.match(output, /Restart Kimi Code/)
  assert.doesNotMatch(output, /\/plugins remove/)
  await rm(home, { recursive: true, force: true })
})

test("uninstall refuses a foreign directory at the managed path until --force", async () => {
  const { home } = await seedKimiHome()
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))

    // Someone else takes over the managed path after our install.
    await rm(managedDir(home), { recursive: true, force: true })
    await mkdir(managedDir(home), { recursive: true })
    await writeFile(join(managedDir(home), "theirs.md"), "not ours\n", "utf8")

    await assert.rejects(
      () => withKimiHome(home, () => runInstallKimiPlugin(["--uninstall"])),
      /not the cowork-flow plugin/
    )
    // A refusal means nothing was touched: copies, record and the foreign file.
    await access(sourceDir(home))
    assert.ok(coworkFlowRecord(await readRegistry(home)))
    assert.equal(await readFile(join(managedDir(home), "theirs.md"), "utf8"), "not ours\n")

    await withKimiHome(home, () => runInstallKimiPlugin(["--uninstall", "--force"]))
    await assert.rejects(access(managedDir(home)))
    await assert.rejects(access(sourceDir(home)))
    assert.equal(coworkFlowRecord(await readRegistry(home)), undefined)
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("a registry the host would reject fails uninstall before any deletion", async () => {
  const { home } = await seedKimiHome()
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))

    await writeFile(installedRegistryPath(home), "{ nope", "utf8")
    await assert.rejects(
      () => withKimiHome(home, () => runInstallKimiPlugin(["--uninstall"])),
      /not valid JSON/
    )
    // Nothing was deleted: deleting first would leave a corrupt registry
    // pointing at plugin roots that no longer exist.
    await access(sourceDir(home))
    await access(managedDir(home))
    assert.equal(await readFile(installedRegistryPath(home), "utf8"), "{ nope")
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("uninstall without a record still removes the copies and says so", async () => {
  const { home } = await seedKimiHome()
  const lines = []
  const original = console.log
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))
    await rm(installedRegistryPath(home), { force: true })
    console.log = (line) => lines.push(String(line))
    await withKimiHome(home, () => runInstallKimiPlugin(["--uninstall"]))
  } finally {
    console.log = original
  }

  await assert.rejects(access(sourceDir(home)))
  await assert.rejects(access(managedDir(home)))
  assert.match(lines.join("\n"), /No cowork-flow record/)
  await rm(home, { recursive: true, force: true })
})
