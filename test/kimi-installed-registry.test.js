import assert from "node:assert/strict"
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"

import {
  installedRegistryPath,
  readInstalledRegistry,
  removePluginRecord,
  upsertPluginRecord
} from "../src/lib/kimi-installed-registry.js"

async function withHome(run) {
  const home = await mkdtemp(join(tmpdir(), "cowork-flow-kimi-registry-"))
  try {
    return await run(home)
  } finally {
    await rm(home, { recursive: true, force: true })
  }
}

async function readRegistryFile(home) {
  return JSON.parse(await readFile(installedRegistryPath(home), "utf8"))
}

async function seedRegistry(home, data) {
  await mkdir(join(home, "plugins"), { recursive: true })
  await writeFile(installedRegistryPath(home), JSON.stringify(data, null, 2), "utf8")
}

test("an absent registry reads as the empty host shape", async () => {
  await withHome(async (home) => {
    assert.deepEqual(await readInstalledRegistry(home), { version: 1, plugins: [] })
  })
})

test("upsert writes a new record in the host's field shape", async () => {
  await withHome(async (home) => {
    const record = await upsertPluginRecord(home, {
      id: "cowork-flow",
      root: "C:\\managed\\cowork-flow",
      source: "local-path",
      enabled: true,
      originalSource: "C:\\sources\\cowork-flow"
    })

    assert.equal(record.enabled, true)
    const registry = await readRegistryFile(home)
    assert.equal(registry.version, 1)
    assert.equal(registry.plugins.length, 1)
    assert.deepEqual(Object.keys(registry.plugins[0]), [
      "id", "root", "source", "enabled", "installedAt", "updatedAt", "originalSource"
    ])
    const entry = registry.plugins[0]
    assert.equal(entry.id, "cowork-flow")
    assert.equal(entry.root, "C:\\managed\\cowork-flow")
    assert.equal(entry.source, "local-path")
    assert.equal(entry.originalSource, "C:\\sources\\cowork-flow")
    assert.match(entry.installedAt, /^\d{4}-\d{2}-\d{2}T/)
    assert.equal(entry.installedAt, entry.updatedAt)
    // The host pretty-prints with a two-space indent and re-reads this file on
    // load, so the first byte of the document must already be its shape.
    assert.match(await readFile(installedRegistryPath(home), "utf8"), /^\{\n {2}"version": 1,/)
  })
})

test("record ids match case-insensitively and re-entry keeps one record", async () => {
  await withHome(async (home) => {
    await upsertPluginRecord(home, {
      id: "Cowork-Flow", root: "a", source: "local-path", enabled: true, originalSource: "b"
    })
    assert.equal((await readRegistryFile(home)).plugins[0].id, "cowork-flow")

    await upsertPluginRecord(home, {
      id: "COWORK-FLOW", root: "c", source: "local-path", enabled: true, originalSource: "d"
    })
    const registry = await readRegistryFile(home)
    assert.equal(registry.plugins.length, 1)
    assert.equal(registry.plugins[0].root, "c")
  })
})

test("re-entry keeps enable state, installedAt and capabilities, and drops stale github metadata", async () => {
  await withHome(async (home) => {
    await seedRegistry(home, {
      version: 1,
      plugins: [{
        id: "cowork-flow",
        root: "C:\\old",
        source: "github",
        enabled: false,
        installedAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-02T00:00:00.000Z",
        originalSource: "https://github.com/fishlikewater/cowork-flow",
        capabilities: { mcpServers: { taskboard: { enabled: false } } },
        github: { owner: "fishlikewater", repo: "cowork-flow", ref: { kind: "branch", value: "dev" } }
      }]
    })

    const record = await upsertPluginRecord(home, {
      id: "cowork-flow",
      root: "C:\\new",
      source: "local-path",
      enabled: true,
      originalSource: "C:\\sources\\cowork-flow"
    })

    assert.equal(record.enabled, false)
    assert.equal(record.installedAt, "2026-01-01T00:00:00.000Z")
    assert.notEqual(record.updatedAt, "2026-01-02T00:00:00.000Z")
    assert.equal(record.root, "C:\\new")
    assert.equal(record.source, "local-path")
    assert.deepEqual(record.capabilities, { mcpServers: { taskboard: { enabled: false } } })
    assert.equal(record.github, undefined)
  })
})

test("other plugins and unknown top-level keys survive upsert and remove", async () => {
  await withHome(async (home) => {
    const foreign = {
      id: "superpowers",
      root: "C:\\managed\\superpowers",
      source: "github",
      enabled: false,
      installedAt: "2026-09-23T08:14:33.425Z",
      updatedAt: "2026-09-23T08:14:42.166Z",
      originalSource: "https://github.com/obra/superpowers",
      github: {
        owner: "obra",
        repo: "superpowers",
        ref: { kind: "tag", value: "v6.4.1" },
        installedSha: "5bf4e78011075bcfc0dc295f0724994cd123ee71"
      }
    }
    await seedRegistry(home, { version: 1, futureKey: { keep: true }, plugins: [foreign] })

    await upsertPluginRecord(home, {
      id: "cowork-flow", root: "C:\\managed\\cowork-flow", source: "local-path",
      enabled: true, originalSource: "C:\\sources\\cowork-flow"
    })
    let registry = await readRegistryFile(home)
    assert.equal(registry.plugins.length, 2)
    assert.deepEqual(registry.plugins[0], foreign)
    assert.deepEqual(registry.futureKey, { keep: true })

    assert.equal(await removePluginRecord(home, "cowork-flow"), true)
    assert.equal(await removePluginRecord(home, "cowork-flow"), false)
    registry = await readRegistryFile(home)
    assert.deepEqual(registry.plugins, [foreign])
    assert.deepEqual(registry.futureKey, { keep: true })
  })
})

test("an unreadable registry fails closed without rewriting the file", async () => {
  await withHome(async (home) => {
    const path = installedRegistryPath(home)
    const junk = "{ definitely not json"
    await seedRegistry(home, { version: 1, plugins: [] })
    await writeFile(path, junk, "utf8")

    await assert.rejects(
      () => upsertPluginRecord(home, {
        id: "cowork-flow", root: "x", source: "local-path", enabled: true, originalSource: "y"
      }),
      /not valid JSON/
    )
    await assert.rejects(() => readInstalledRegistry(home), /not valid JSON/)
    await assert.rejects(() => removePluginRecord(home, "cowork-flow"), /not valid JSON/)
    assert.equal(await readFile(path, "utf8"), junk)

    await writeFile(path, JSON.stringify({ version: 1, plugins: "no" }), "utf8")
    await assert.rejects(() => readInstalledRegistry(home), /not a Kimi Code plugin registry/)
  })
})
