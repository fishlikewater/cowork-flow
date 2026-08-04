---
name: runtime-health
description: Use when checking cowork-flow runtime, host assets, fixed-agent safety, or template health.
---

# Runtime Health

Use this Skill for runtime and template health checks. Keep diagnostics separate
from the workflow kernel and from user-facing phase Skills.

## Commands

Run diagnostics through the common runner:

```text
.cowork-flow/run doctor --all
.cowork-flow/run doctor --host-adapters
.cowork-flow/run doctor --subagent-safety
.cowork-flow/run doctor --task-hygiene
.cowork-flow/run doctor --task-hygiene --json
```

## Support Triage

Use runtime-health when the user reports host asset drift, hook drift, fixed-agent
binding failures, stale completed tasks, missing task context, or template/source
checkout health issues. Start with the narrowest doctor command that matches the
symptom, then broaden to `doctor --all` only when the focused result is
insufficient.

Runtime-health output is diagnostic evidence. It may provide command hints, but
it must not replace `task next --json` as the workflow router and must not mutate
lifecycle state.

## Boundaries

- Diagnostics may inspect runtime contracts, host assets, hooks, and template files.
- Installed projects validate only detected host platforms and do not require a source `template/` tree.
- Source checkouts distinguish ignored local live runtime from the template distribution source.
- Source checkout health must not force-track `.cowork-flow/` runtime files; ignored local live runtime files are checked only when present.
- Source checkouts also validate Skill replica parity for detected installed host targets.
- stale task hygiene reports completed-unarchived tasks, active-unbound tasks, and missing task context with command hints only.
- Diagnostics must not mutate task lifecycle state.
- Do not add lifecycle routing rules here; `task next` remains the workflow router.
