# Skill-owned actions

The kernel resolves `status + intent + execution context` into an action id,
allowed operations, required artifacts, and machine-checkable blockers. It does
not contain Skill ids, prompt wording, CLI commands, or script paths.

Each Skill may declare its own `manifest.json` with:

- `actions`: action id, display label, lifecycle check, mutation fact, and an
  optional command description plus optional `diagnosticsCommand`;
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
resume, read-only inspect, and result recording are also Skill commands rather
than task CLI handlers. `batch-action inspect <operation_id>` may report
existing operation facts, including current phase, current task, failed action,
next action, and recovery hints, but it must not advance, resume, create, or
save Batch state.

Review-oriented Skill commands may provide advisory facts, such as changed-file
coverage, applicable spec sources, and test-intent signals. An action-level
`diagnosticsCommand` may expose these helpers in text and JSON navigation, but
it does not make the helper runnable as a lifecycle action. They must remain
read-only helpers: no task-local review evidence file, lifecycle state mutation,
natural-language spec hard gate, or pass/fail completion verdict.
`task-review` JSON output may add `normalizedIssues` for machine consumers. Each
normalized issue uses the stable envelope `code`, `severity`, `path`, `message`,
and `source`, while existing `scopeFacts` and `testIntentSignals` fields remain
the compatibility contract for older consumers.

Text and JSON task navigation render the same resolved action contract. Text
adapters may show the action label, owner, command, and blockers, but must not
add phase instructions, follow-up commands, or hard-coded Skill ids. The owner
Skill contains the detailed phase guidance. Context consumers use the
manifest-selected entries and a stable lexical order; services do not maintain
Skill-id priority tables.

Route services use `lifecycleCheck` as the internal lifecycle-check field.
`runtimeGate` is a compatibility alias owned by task-navigation adapters and may
be emitted in text or JSON route payloads for older consumers. Kernel and
service-layer contracts must not depend on `runtimeGate`; they compare Skill
manifest ownership against `lifecycleCheck` and add compatibility aliases only
when rendering adapter output.

Lifecycle checks may expose structured issue facts in addition to blocker
messages. The blocker messages remain the human-facing compatibility contract,
while advisory helpers such as `task-review` should prefer structured issue
codes and paths when classifying protected workflow files, unlisted changed
files, or task-context problems.

Runtime Health has two scopes. An installed project validates its installed
runtime, detected host platforms, and installed Skill manifests without
requiring a `template/` directory. A cowork-flow source checkout distinguishes
ignored local live runtime from the template distribution source. Source
checkout health must not force-track `.cowork-flow/` runtime files: local live
runtime is compared only when present, and Skill replica parity is checked for
every detected installed Skill target.

Runtime Health also reports stale task hygiene read-only. It may warn about
completed-unarchived tasks, active-unbound tasks, and missing task context, and
it may include command hints. These warnings must not mutate task lifecycle
state, write evidence files, or become completion gates. Runtime Health JSON
issues use a stable envelope: `code`, `severity`, `path`, `message`,
`commandHint`, and `contract`. Task hygiene output keeps its compatibility
fields such as `kind`, `task`, `status`, and `hint`; host-adapter JSON output
uses the same envelope for asset validation failures.
