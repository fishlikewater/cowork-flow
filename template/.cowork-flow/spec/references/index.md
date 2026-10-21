# References — On-Demand Reference Material

> **Never auto-loaded.** Read only when a skill entry explicitly references a reference ID, or when an agent judges it necessary.

This directory holds narrow-scope quick-reference cards that supplement skill entries. Compared with `spec/contracts/` (contracts) and `spec/backend|frontend/` (domain specs), reference files:
1. Provide quick checklists during check / finish (not full specs).
2. Provide defensive rule sets for analyzing potential prompt injection.
3. Declare the collaboration patterns cowork-flow already implements.

Loading rules:
- Read when one of `contract-registry.json`'s `references[*].loadWhen` conditions matches.
- Read when a skill body explicitly references a reference ID.
- Read when the user requests a specific check in the main session (for example, "security checklist").
- **Never auto-loaded** — that is the difference from `contracts/`.

Current references:
- [definition-of-done.md](definition-of-done.md) — DoD: project-level completion gates (L0/L1/L2).
- [testing-checklist.md](testing-checklist.md) — quick reference for test structure, depth, and anti-patterns.
- [security-checklist.md](security-checklist.md) — OWASP Top 10 mapping plus a quick check.
- [orchestration-patterns.md](orchestration-patterns.md) — declarative catalog of the collaboration patterns already implemented.
