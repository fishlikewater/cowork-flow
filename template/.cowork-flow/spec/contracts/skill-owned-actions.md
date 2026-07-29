# Skill-owned actions

The kernel resolves `status + intent + execution context` into an action id,
allowed operations, required artifacts, and machine-checkable blockers. It does
not contain Skill ids, prompt wording, CLI commands, or script paths.

Each Skill may declare its own `manifest.json` with:

- `actions`: action id, display label, lifecycle check, mutation fact, and an
  optional command description;
- `context`: implement/check/debug activation rules by dev type or path;
- `commands`: Skill-owned runtime entrypoints.

`schemaVersion` is required and currently equals `1`. Actions, context rules,
and commands are parsed by the same runtime loader. A command declares one
non-empty `name`, zero or more unique non-empty `aliases`, and one relative
`script` that must resolve to a file inside the declaring Skill. Missing
scripts, path escapes, duplicate command names or aliases, unknown or malformed
fields, empty manifests, and replica metadata or script-content drift fail
closed. Command adapters consume this loader; they do not parse manifest JSON
independently.

At load time every managed action and command must have exactly one owner.
Lifecycle state, session/runtime-context, file scope, approval checks, and
transactional persistence remain in the shared runtime. After shared Batch
approval, the adapter invokes the manifest-owned `batch-action start`; Batch
resume and result recording are also Skill commands rather than task CLI
handlers.

Text and JSON task navigation render the same resolved action contract. Text
adapters may show the action label, owner, command, and blockers, but must not
add phase instructions, follow-up commands, or hard-coded Skill ids. The owner
Skill contains the detailed phase guidance. Context consumers use the
manifest-selected entries and a stable lexical order; services do not maintain
Skill-id priority tables.

Runtime Health has two scopes. An installed project validates its installed
runtime, detected host platforms, and installed Skill manifests without
requiring a `template/` directory. A cowork-flow source checkout additionally
validates complete template host assets and template-to-live runtime and Skill
replica parity, including every detected Skill target.
