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
.cowork-flow/run doctor --host-adapters
.cowork-flow/run doctor --subagent-safety
```

## Boundaries

- Diagnostics may inspect runtime contracts, host assets, hooks, and template files.
- Diagnostics must not mutate task lifecycle state.
- Do not add lifecycle routing rules here; `task next` remains the workflow router.
