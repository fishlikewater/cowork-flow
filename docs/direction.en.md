# cowork-flow direction: agent runtime context and the collaboration fact layer

[中文](direction.md) | English

> Status: **approved** · Created: 2026-08-27 · Last updated: 2026-10-19
> This document is the authoritative input for starting later phases. Any revision to the direction must update this document first, then start the phase.
> Implementation details and commit history for completed phases are in the [CHANGELOG](../CHANGELOG.md) (Chinese); this document keeps only the positioning, trade-offs, boundaries, and open items that still hold.

---

## 1. Positioning

> **cowork-flow does not constrain how a model thinks; it guarantees that any agent on any host starts from the same authoritative facts, in any session, at any moment.**

| | Previous positioning | New positioning |
|---|---|---|
| Narrative | Help you build a process (process templates) | Runtime context and collaboration fact layer |
| Means | Task flows, gates, spec documents | State injection, fact consistency, cross-host governance |
| Purpose | Make collaboration "follow the rules" | Make collaboration "start from the correct state" |
| When model capability rises | Constraint-type value decreases (models follow the rules on their own) | Fact-type value increases (state is something a model cannot invent) |

The test: a project's consumer is an agent, not a person. So injection formats, fact output, and contracts always follow "machine-parseable first, human-readable as a fallback".

## 2. Settled trade-offs

- **Injection format: option A (structured fact header + human-readable summary body, with graded degradation)** — structured first; when the channel does not allow it, degrade to attribute lines or a plain summary.
  - Rejected "all-JSON injection": the plain-text channels of dsh / codex waste tokens and break the readability of compact prose breadcrumbs.
  - Rejected "keep text and only add a `--json` output": the core value proposition would not land in injection itself.
- **Fact-layer output**: the CLI + JSON protocol comes first (zero dependencies); MCP follows as a thin adapter.
- **Three-line convergence**: start with "a single protocol spec + three lines implemented against the spec"; code-level sharing is left for later (high cost, and the benefit has already been delivered through protocol consistency).

## 3. What we explicitly do not do

1. No "smarter prompts / AGENTS.md writing craft" — model capability will catch up, and that leaves no data assets.
2. No home-grown cross-agent communication standard — this is a period of protocol competition; wait for the ecosystem to converge.
3. No task execution engine — not a substitute for the agent doing the work, only a guarantee that it starts from the correct state.
4. No deeper process-only gates — keep them as a safety net and stop investing.

## 4. Rejected candidates

| Candidate | Why it was rejected |
|---|---|
| AgentOps / observability | No runtime telemetry assets; building from scratch means switching lanes and breaks with the workflow-engine positioning |
| Task orchestration engine | Overlaps with the orchestration hosts already provide; turning the state model into a distributed system explodes complexity |
| Pure governance and compliance layer | The value of pure gates decreases as models become more self-directed; no differentiation |
| ✅ Fact layer + injection | The repository's thickest assets all live here; cross-host consistency is a structural difference no single-host tool can provide |

## 5. Version line

- **1.8.x released**: evidence-based completion (ACs as facts, `evidence.jsonl`, completion gates).
- **1.9.x released**: collaboration facts for multiple executors — visible board ownership, dependency edges, handoff records.
- **2.0.0 released**: the spec-check mechanism removed in a breaking change, edit-time out-of-scope warnings on every host, and relaxed injection capacity (Verify 10 items / block budget 3400). See the `[2.0.0]` section of the [CHANGELOG](../CHANGELOG.md) (Chinese).
- Per-version delivery details always follow the CHANGELOG; this document does not repeat them.

## 6. Open items and deferred work

- **Settled (2026-10-21): detailed documentation stays Chinese; the README stays bilingual.** The English community is the main venue for spec-driven development discussion, but the detailed documentation is currently about 590 lines and ships in the npm package as plain Markdown, so full bilingual coverage would introduce translation drift and documentation-framework cost. Decision: `docs/`, `template/AGENTS.md`, and `CHANGELOG.md` stay Chinese; `README.md` / `README.en.md` are kept in sync in both languages; no VuePress/mkdocs or directory-based bilingual setup is introduced.
  - **2026-10-22 (step three): English demand confirmed, and `docs/` gains parallel `docs/*.en.md` files.** Five documents (index, architecture, hosts, release, direction) each gain an English version, the Chinese and English pages link to each other at the top, and everything still ships in the npm package as plain Markdown. Translation drift is held down by the pairing and heading-structure gates in `test/docs.test.js`: a missing English file, inconsistent heading levels, or a missing counterpart link all fail.
  - 2026-10-13 clarification: "documentation language: Chinese" constrains the language of **documents produced** while working in a downstream host; it does not require translating the product payloads shipped with the package (`template/skills/`, `template/.cowork-flow/spec/contracts/`, `presets/`) into Chinese.
  - 2026-10-21 (step one): the framework spec documentation shipped with the package is unified in English — `spec/index.md`, `spec/runtime/index.md`, `spec/schemas/index.md`, `spec/references/**`. The six parsed headings in `decision-anchor.md`, the injection block in `workflow-state-templates.md`, `backend/frontend/guides`, and `template/AGENTS.md` stay Chinese.
  - 2026-10-22 (step two): installation can choose `zh-CN` / `en-US`, written to the protected `.cowork-flow/config.yaml` and affecting only `decision-anchor.md` and plan artifacts. The parser permanently accepts both the Chinese and English heading sets; `decision-anchor.md` keeps the Chinese contract and adds an English variant, while `workflow-state-templates.md`, `AGENTS.md`, spec documents, and Skills are not localized by that option. `references/` is still protected by project sync, so an installed project needs a manual refresh to receive the English copies.
- **Still deferred**: MCP write tools (the `fact-layer-access` contract must be reopened first), new host integrations, and a home-grown cross-agent protocol.
- **Watch item (trigger reached)**: machine-parseable ACs are the first building block for interoperability with Spec Kit / OpenSpec (spec artifacts ↔ decision-anchor mapping), and fit the "state layer beneath SDD tools" positioning. It was originally "to be discussed once the agent-teams schedule is settled"; since the 1.9.0 multi-executor collaboration mainline is already implemented, it can be put on the discussion schedule.

## 7. Metrics

1. **Cross-host behavioral consistency**: fingerprints and slim triggers on each host are asserted by tests, with 0 drift.
2. **Cost of integrating a new host**: from days down to hours (a direct measure of protocol-spec completeness).
3. **Injection token cost**: injected volume in long sessions does not grow linearly with the number of messages.
4. **Fact freshness incidents**: multi-session task contamination / stomping incidents trend toward zero.
5. **Adoption**: weekly npm downloads and the number of activated projects — using numbers to verify whether the "deep route" delivers.
