
# Post-roadmap hardening spec

## Current authority rule

- Current runtime authority is DB `runtime_session` and DB `runtime_context`.
- Historical `.cowork-flow/.runtime/` files may be referenced only as migration or diagnostic context.
- Historical design documents that mention old state files must mark themselves as non-authoritative for current runtime behavior.

## Sync gate allowlist rule

- A template sync allowlist entry must include a concrete reason.
- A legacy flattened-path allowlist entry must either be covered by a regression test or be removed.
- Allowlist entries must not mask root/template drift for current template assets.

## Roadmap closeout rule

- A completed roadmap should not leave active tasks or draft changes.
- If sibling tasks are archived, any intentionally unarchived task must have a written reason.
- Final closeout must include `git diff --check`, relevant focused tests, and a status check proving active task is empty.
