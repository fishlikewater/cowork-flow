# Sync Phase 3 Template And Contracts

## Goal

Synchronize Phase 3 adapter capabilities, workflow/spec docs, registry metadata, and template runtime files.

## Scope

- Update adapter schema and host adapter yaml files.
- Update subagent/workflow/capability specs and registry metadata.
- Copy Phase 3 runtime/dashboard files into `template/`.
- Keep root/template script behavior aligned.

## Non-Goals

- No package release or changelog publish.
- No new dependency declarations.

## Acceptance Criteria

1. Adapter schema accepts `spawnMultipleSubagents` and `waitMultipleChildren`.
2. All host adapters declare the new capabilities consistently.
3. Template contains the same Phase 3 runtime/dashboard files as root.
4. Host adapter and template tests pass.

## References

- `.cowork-flow/spec/adapter.schema.json`
- `.cowork-flow/spec/capabilities.md`
- `.cowork-flow/spec/registry.json`
