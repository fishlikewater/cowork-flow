import assert from "node:assert/strict"
import { access, mkdir, mkdtemp, readFile, readdir, realpath, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"
import { pathToFileURL } from "node:url"

import { runInstallOpenCodePlugin } from "../src/commands/install-opencode-plugin.js"
import { packageRoot } from "../src/lib/paths.js"

const PLUGIN_RELATIVE = ["plugins", "cowork-flow.js"]
const CORE_RELATIVE = ["cowork-flow", "plugin-core.js"]
const SKILL_RELATIVE = ["cowork-flow", "skills", "cowork-flow-bootstrap", "SKILL.md"]

async function withXdgConfigHome(home, run) {
  const previous = process.env.XDG_CONFIG_HOME
  process.env.XDG_CONFIG_HOME = home
  try {
    return await run()
  } finally {
    if (previous === undefined) delete process.env.XDG_CONFIG_HOME
    else process.env.XDG_CONFIG_HOME = previous
  }
}

// opencode creates its own package.json/node_modules next to whatever plugin it
// loads, so every case starts from a config directory that already holds another
// plugin and an unrelated file — the installer must leave both alone.
async function seedOpencodeHome() {
  // XDG_CONFIG_HOME is the parent; the installer appends opencode/ itself, so
  // the home these cases assert against is the child.
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-home-"))
  const home = join(root, "opencode")
  const foreignPlugin = join(home, "plugins", "their-plugin.js")
  await mkdir(join(home, "plugins"), { recursive: true })
  await writeFile(foreignPlugin, "export const TheirPlugin = async () => ({})\n", "utf8")
  await writeFile(join(home, "package.json"), '{"keep":"me"}\n', "utf8")
  return { root, home, foreignPlugin }
}

function pluginPath(home) {
  return join(home, ...PLUGIN_RELATIVE)
}

// Relative path -> content for every file under a directory, so two trees can be
// compared without depending on readdir order.
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

test("install-opencode-plugin writes the plugin file and its payload", async () => {
  const { root, home, foreignPlugin } = await seedOpencodeHome()
  try {
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin([]))

    const plugin = await readFile(pluginPath(home), "utf8")
    assert.match(plugin, /CoworkFlowPlugin/)
    await access(join(home, ...CORE_RELATIVE))
    await access(join(home, ...SKILL_RELATIVE))

    // Only our two entries are added: the config directory belongs to the user
    // and to the host, and this installer writes nothing else into it.
    assert.deepEqual((await readdir(home)).sort(), ["cowork-flow", "package.json", "plugins"])
    assert.deepEqual((await readdir(join(home, "plugins"))).sort(), ["cowork-flow.js", "their-plugin.js"])
    assert.equal(await readFile(foreignPlugin, "utf8"), "export const TheirPlugin = async () => ({})\n")
    assert.equal(await readFile(join(home, "package.json"), "utf8"), '{"keep":"me"}\n')
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("the installed plugin registers its own installed skills directory", async () => {
  // The whole design rests on self-location: the plugin must derive the skills
  // path from where it was installed, not from the session directory or an
  // environment variable. Importing the installed copy and running its config
  // hook is the only way to observe that from the outside.
  const { root, home } = await seedOpencodeHome()
  try {
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin([]))

    const installed = await import(pathToFileURL(pluginPath(home)).href)
    const hooks = await installed.CoworkFlowPlugin({ directory: tmpdir() })
    const config = {}
    await hooks.config(config)

    // The plugin derives its skills path from import.meta.url, so it reports the
    // realpath of the install location. On macOS tmpdir() lives under a
    // symlinked /var, so the same directory surfaces as /private/var; compare
    // realpaths rather than the seed's literal spelling.
    assert.deepEqual(config.skills.paths, [await realpath(join(home, "cowork-flow", "skills"))])
    await access(join(config.skills.paths[0], "cowork-flow-bootstrap", "SKILL.md"))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-opencode-plugin converges on the shipped payload", async () => {
  const { root, home } = await seedOpencodeHome()
  try {
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin([]))
    // A manifestless payload carries no version, so a rerun cannot tell "same
    // version" and re-materializes instead. What has to hold is convergence:
    // after any number of runs the installed tree is exactly the shipped tree.
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin([]))
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin(["--force"]))

    const shipped = join(packageRoot, "presets", "opencode")
    assert.deepEqual(
      await tree(join(home, "cowork-flow")),
      await tree(join(shipped, "cowork-flow")),
      "the installed payload must be the shipped payload"
    )
    assert.equal(
      await readFile(pluginPath(home), "utf8"),
      await readFile(join(shipped, "plugins", "cowork-flow.js"), "utf8")
    )
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-opencode-plugin refuses a foreign file at its plugin path", async () => {
  const { root, home } = await seedOpencodeHome()
  try {
    const target = pluginPath(home)
    await writeFile(target, "export const SomeoneElse = async () => ({})\n", "utf8")

    await assert.rejects(
      () => withXdgConfigHome(root, () => runInstallOpenCodePlugin([])),
      /not the cowork-flow plugin/
    )
    // The preview must not promise an install the real run refuses.
    await assert.rejects(
      () => withXdgConfigHome(root, () => runInstallOpenCodePlugin(["--dry-run"])),
      /not the cowork-flow plugin/
    )
    assert.equal(await readFile(target, "utf8"), "export const SomeoneElse = async () => ({})\n")

    await assert.rejects(
      () => withXdgConfigHome(root, () => runInstallOpenCodePlugin(["--uninstall"])),
      /use --force to remove them anyway/
    )
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin(["--uninstall", "--force"]))
    await assert.rejects(access(target))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-opencode-plugin dry-run writes nothing", async () => {
  const { root, home } = await seedOpencodeHome()
  try {
    const before = await readdir(home)
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin(["--dry-run"]))

    assert.deepEqual(await readdir(home), before)
    await assert.rejects(access(pluginPath(home)))
    await assert.rejects(access(join(home, "cowork-flow")))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("install-opencode-plugin uninstall removes its two entries and the empty shell", async () => {
  const { root, home, foreignPlugin } = await seedOpencodeHome()
  try {
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin([]))
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin(["--uninstall"]))

    await assert.rejects(access(pluginPath(home)))
    await assert.rejects(access(join(home, "cowork-flow")))
    // Another plugin still lives there, so plugins/ is not ours to remove.
    assert.equal(await readFile(foreignPlugin, "utf8"), "export const TheirPlugin = async () => ({})\n")
    assert.equal(await readFile(join(home, "package.json"), "utf8"), '{"keep":"me"}\n')
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})

test("uninstall removes a plugins directory it emptied", async () => {
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-solo-"))
  const home = join(root, "opencode")
  try {
    await mkdir(root, { recursive: true })
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin([]))
    await withXdgConfigHome(root, () => runInstallOpenCodePlugin(["--uninstall"]))

    // No user plugin was there before us, so the directory we created for
    // ourselves is a shell and must not be left behind.
    await assert.rejects(access(join(home, "plugins")))
  } finally {
    await rm(home, { recursive: true, force: true })
  }
})
