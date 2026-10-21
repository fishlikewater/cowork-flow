# Runtime Specs

This directory holds machine configuration read directly by the workflow runtime.

- `contract-registry.json`: registry of the contract digests injected by hooks/plugins.
- `host-assets.json`: single source for host platforms, asset ownership, skill read roots and host discovery channels (`skillReadRoot` / `skillDiscovery[]`, entries are repo-relative paths plus `gates` / `evidence`; machine-level payloads do not participate as skill sources), machine-level plugin payload declarations (`payload`: the package-relative payload directory and plugin manifest name; `null` for hosts without a plugin payload; machine install locations are not declared here), the sync protection policy, and the obsolete-asset migration list. The structure is constrained by `../schemas/host-assets.schema.json`. `capabilityMatrix.hosts` must cover every id declared in `platforms` — the required host set is derived from platform data; the runtime does not maintain a host-name constant.

Missing or corrupted runtime files must not silently grant critical workflow capabilities. Host plugins may use a minimal fallback to avoid crashing, but must expose a warning in the digest; doctor/tests are responsible for detecting absence.

User natural-language specs are not registered in this directory; the `task-review` skill reads `spec/backend/`, `spec/frontend/`, and `spec/guides/` directly and reports review findings.

Runtime write boundaries:

- CLI/host/Git adaptation lives in `scripts/adapters/`; use-case services live in `scripts/services/`.
- JSON state is read and written through `scripts/infra/storage/` with explicit UTF-8.
- init/sync commit assets through Asset Plan, staging, backup, and rollback; the version file is updated last.
- Old state is only allowed at read boundaries with migration tests; new writes must use the current schema and authoritative paths.
