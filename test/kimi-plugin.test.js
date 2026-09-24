import assert from "node:assert/strict"
import { access, mkdir, mkdtemp, readdir, readFile, rm, stat, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"

import { runInstallKimiPlugin } from "../src/commands/install-kimi-code-plugin.js"
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

test("install-kimi-plugin materializes a stable source directory", async () => {
  const { home, foreign } = await seedKimiHome()
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))

    const target = sourceDir(home)
    assert.equal((await readJson(join(target, ...MANIFEST_RELATIVE))).name, PLUGIN_NAME)
    await access(join(target, ...SKILL_RELATIVE))
    // The registry records the path a plugin was installed from and re-reads it
    // on reinstall, so this directory has to be the payload — not the host's
    // managed tree, which is the host's own copy.
    await assert.rejects(access(join(home, "plugins", "managed")))
    assert.equal(await readFile(join(foreign, "kimi.plugin.json"), "utf8"), '{"name":"their-plugin"}\n')
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-kimi-plugin prints the one slash command that finishes the install", async () => {
  // Kimi Code has no CLI subcommand for plugins, so the installer cannot finish
  // the job itself. The printed command has to name the directory it just wrote,
  // with an absolute path: the host rejects a relative plugin root outright.
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
  assert.match(output, new RegExp(`/plugins install ${sourceDir(home).replace(/\\/g, "\\\\")}`))
  assert.match(output, /\/reload/)
  await rm(home, { recursive: true, force: true })
})

test("install-kimi-plugin dry-run writes nothing but still prints the command", async () => {
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
  assert.match(lines.join("\n"), /\/plugins install /)
  await rm(home, { recursive: true, force: true })
})

test("install-kimi-plugin converges on the shipped payload", async () => {
  const { home } = await seedKimiHome()
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))
    await withKimiHome(home, () => runInstallKimiPlugin([]))
    await withKimiHome(home, () => runInstallKimiPlugin(["--force"]))

    assert.deepEqual(await tree(sourceDir(home)), await tree(payloadRoot))
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

test("uninstall removes the source and says the host copy is not its to delete", async () => {
  const { home, foreign } = await seedKimiHome()
  const lines = []
  const original = console.log
  try {
    await withKimiHome(home, () => runInstallKimiPlugin([]))
    console.log = (line) => lines.push(String(line))
    await withKimiHome(home, () => runInstallKimiPlugin(["--uninstall"]))
  } finally {
    console.log = original
  }

  await assert.rejects(access(sourceDir(home)))
  assert.equal(await readFile(join(foreign, "kimi.plugin.json"), "utf8"), '{"name":"their-plugin"}\n')
  // Kimi Code's own remove only drops the registry record; the managed copy and
  // the source stay on disk. The output must not imply a clean sweep.
  const output = lines.join("\n")
  assert.match(output, /\/plugins remove cowork-flow/)
  assert.match(output, /managed/)
  await rm(home, { recursive: true, force: true })
})
