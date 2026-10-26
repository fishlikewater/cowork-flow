# Host install inspection

`cwf host inspect` is the single read model for machine-level host install
state. The Node CLI owns that read; the Python doctor consumes it and does not
resolve host home directories or parse host registries, TOML, settings or
payload manifests itself.

The read model covers components installed by `cwf host add` into a host's
user configuration directory. Project-level files under `.cowork-flow/` and
host project directories are not part of it.

## Command contract

```
cwf host inspect [host] [--json]
```

- Read-only: it never installs, repairs, removes, enables or writes host state.
- Without `<host>`, every platform declared in `host-assets.json` is inspected.
- With `<host>`, only that platform is inspected. Aliases are accepted; an
  unknown host is a usage error with exit code 2.
- Text output prints one line per row. `--json` prints one report object.
- Exit code 0 means the inspection ran. A row reporting `missing`, `broken`,
  `stale` or `unsupported` is data, not a command failure.

## JSON shape

```json
{
  "schemaVersion": 1,
  "cliVersion": "2.4.2",
  "hosts": [
    {
      "id": "qoder",
      "displayName": "Qoder",
      "component": "plugin",
      "status": "installed",
      "version": "2.4.2",
      "payloadPath": "/home/user/.qoder/plugins/cache/cowork-flow-local/cowork-flow/2.4.2",
      "detailPath": "/home/user/.qoder/plugins/cache/cowork-flow-local/cowork-flow/2.4.2/.qoder-plugin/plugin.json",
      "registeredSource": "/home/user/.qoder/plugins/installed_plugins_v2.json",
      "enabled": true,
      "reason": null
    }
  ]
}
```

There is one row per installable component. `kimi-code`'s `all` component is a
command composition, not an installed artifact, so it has no row.

| Field | Meaning |
|---|---|
| `id` | Platform id from `host-assets.json`. |
| `displayName` | Host display name from the same manifest. |
| `component` | Installable component name (`plugin`, `preset`, `hook`). |
| `status` | One of the five statuses below. |
| `version` | Installed payload version, or `null` when the host records none. |
| `payloadPath` | Absolute path of the installed payload, or `null` when none exists. |
| `detailPath` | Most specific artifact for the reported status: the registration file that should hold the record, the payload or install directory when that is what is missing, the absent or unreadable file, the enable settings file when `enabled` is false, or the version manifest/marker/file the host loads. `null` when no more specific path applies. |
| `registeredSource` | Registry, config file or marketplace path the host reads, or `null`. |
| `enabled` | `true`/`false` when the host has an enable flag; `null` when it has none or the state is unknown. |
| `reason` | Human-readable explanation, or `null` when there is nothing to explain. |

Unknown fields are ignored by consumers. A breaking change to the shape, the
statuses or the meaning of a field bumps `schemaVersion`; the doctor then
reports `HOST-INSPECT-UNAVAILABLE` instead of guessing.

## Statuses

- `installed`: every required artifact exists. The host may still be disabled,
  which is reported through `enabled`.
- `missing`: no cowork-flow install is registered. A same-named path owned by a
  different plugin is also `missing`, with a reason saying so; it is never a
  license to overwrite or delete that path.
- `stale`: the installed payload version differs from the running CLI version.
  The comparison belongs to the read model, not to the caller. The doctor
  applies a second, project-relative comparison for hosts that record a
  version: it compares the same version with the project's
  `.cowork-flow/.version`, because the doctor answers for that project's
  runtime. A payload that differs from the CLI but matches the project is
  healthy for the project; a payload that matches the CLI but lags the project
  is still stale.
- `broken`: the host knows about a cowork-flow install, but a required payload
  artifact is absent or unreadable. The reason starts with `missing ` and names
  the relative artifact when one path is at fault.
- `unsupported`: the component exposes no installed-state reader. Reserved for
  future components; every component in this release has a reader.

Hosts that record no version (today OpenCode and the DSH hook) report
`version: null` and can only be `installed`, `missing` or `broken`. The doctor
may compare their files against the project's own copies to detect drift.

## Reason sentinels

`reason` is prose, but a small prefix vocabulary is stable because the doctor
maps it to issue codes:

| Reason | Caller meaning |
|---|---|
| `missing <relative>` (optionally followed by a parenthetical) | The named payload artifact is absent. |
| `a different plugin owns this file` / `this directory` | The path belongs to another install; stay silent. |
| `config file is absent` | The host is not configured at all; stay silent. |
| `shim is missing` | The hook registration points at a missing command. |
| `version marker is missing` / `version marker is unreadable` | The install has no trustworthy version. |
| `stable reinstall source directory is missing` | The plugin is installed but its reinstall source is gone. |
| `enable flag is not true` | The plugin is installed but its host enable flag is off. |

## Doctor consumption

The doctor executes:

```
cwf host inspect --json
```

- CLI resolution: `COWORK_FLOW_CLI` when set (a `.js`, `.mjs` or `.cjs` path is
  run through `node`), otherwise `cwf`, then `cowork-flow` from `PATH`.
- One inspection per doctor pass. Facts are cached for that pass, not across
  processes.
- Timeout: 5 seconds.
- The command runs with stdin closed and its output parsed as UTF-8.

If the CLI is absent, exits non-zero, times out, emits invalid JSON, reports a
`schemaVersion` other than 1, omits the `hosts` list, or omits the row the
caller needs, the doctor emits one `HOST-INSPECT-UNAVAILABLE` warning for that
host check. It must not translate an unavailable inspection into
`PLUGIN-NOT-INSTALLED`: "could not read" and "read as missing" are different
facts.

The doctor maps rows to host-specific issue codes:

| Status/field | Qoder, ZCode, Codex, Claude Code, Kimi Code | OpenCode | DSH preset | Kimi hook |
|---|---|---|---|---|
| `missing` | `PLUGIN-NOT-INSTALLED` | `PLUGIN-NOT-INSTALLED` | silent (absent preset is not a defect) | `HOOK-NOT-INSTALLED`, except silent when the config file is absent |
| `broken` | `PLUGIN-PAYLOAD-MISSING` / `PLUGIN-PAYLOAD-INCOMPLETE` | `PLUGIN-PAYLOAD-INCOMPLETE` | `PRESET-UNKNOWN-VERSION` | `HOOK-SHIM-MISSING` / `HOOK-UNKNOWN-VERSION` |
| `stale` | `PLUGIN-STALE` | `PLUGIN-STALE` (versionless in practice) | `PRESET-STALE` | `HOOK-STALE` |
| `installed`, `enabled: false` | `PLUGIN-DISABLED` for hosts with an enable flag (Qoder, Codex, Kimi Code plugin) | not applicable | not applicable | not applicable |
| `installed` | silent | silent, unless a project copy differs (`PLUGIN-STALE`) | silent | silent |

A host install-state warning's `path` is the row's `detailPath` when present,
then `payloadPath`, then `registeredSource`. The doctor never reconstructs a
host path from the `reason` string, so the read model remains the only owner of
host layout. Content-drift warnings (OpenCode) name the file they compared, and
the skill-delivery check names `payloadPath/skills`; both point at the artifact
that actually differs rather than the install record.

The `stale` row above is the inspect status. The doctor's code depends on the
project-relative comparison described under statuses: an `installed` row whose
payload version also differs from the project's `.version` produces
`PLUGIN-STALE` as well, while a CLI-only skew whose payload matches the project
stays silent.

`HOST-INSPECT-UNAVAILABLE` includes an upgrade hint, because the most common
cause is an installed CLI older than the project that does not have the
command yet.

## Ownership boundary

- Each installer owns its host's layout and exports `inspectInstalledState`.
- `src/commands/host-inspect.js` only normalizes installer facts against the
  running CLI version; it does not know host layouts.
- The doctor consumes rows. `tests/test_host_layout_single_source.py` guards
  that host layouts, home-directory resolution and registry/TOML parsing do not
  come back into the Python runtime.
- The skill-delivery check reads each host's `payloadPath` from the same rows;
  it has no separate install-layout reader either.

## Compatibility

- Adding a host platform or component is additive.
- Renaming or removing a field or status is breaking (`schemaVersion` bump).
- `unsupported` stays a valid status so a future component can be declared
  before its reader exists.
