# Contracts — Human-readable Protocols

Protocol documents for agent behavior. Code references these but does not duplicate their text.

| Contract | Path | Summary |
|----------|------|---------|
| Entry Classification | [../core/entry.md](../core/entry.md) | Dual-channel prompt classification protocol |
| Subagent Dispatch | [../core/dispatch.md](../core/dispatch.md) | Runtime-context subagent dispatch protocol |
| Workflow State Templates | [../core/state-templates.md](../core/state-templates.md) | `[workflow-state:*]` fragments injected by hooks |
| Lifecycle | [../core/lifecycle.md](../core/lifecycle.md) | 5-stage task machine and quality gates |

> **Note**: Runtime enforcement logic lives in `spec/runtime/rules.json`, not in these markdown files.
