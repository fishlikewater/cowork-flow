# Frontend Development Guidelines

## Default Baseline

- Frontend code prioritizes clear information architecture, stable interaction state, and maintainable component boundaries.
- Contract source priority: backend APIs, shared types, design system, existing page patterns in the repo first, then generic rules in this directory.
- New pages or components should align with existing routing, state management, styling system, and accessibility conventions.
- If the repo has no frontend code, the rules in this directory serve as default constraints when frontend is introduced later.

---

## Document Index

| Document | Purpose |
|------|------|
| [Directory Structure](./directory-structure.md) | Module layout and directory boundaries |
| [Component Guidelines](./component-guidelines.md) | Component responsibilities, composition, and interaction boundaries |
| [Hook Guidelines](./hook-guidelines.md) | Reusable logic and side-effect boundaries |
| [State Management](./state-management.md) | Server state, client state, and permission state |
| [Quality Guidelines](./quality-guidelines.md) | Frontend quality gates |
| [Type Safety](./type-safety.md) | Shared types and contract synchronization principles |

---

## Usage Principles

- Page entries orchestrate flows; business components handle local interactions; shared components stay free of business assumptions.
- Server state, client ephemeral state, permission state, and form drafts should maintain clear boundaries.
- All user-visible states must cover loading, empty, error, disabled, and permission-denied.
- When changing interfaces or shared types, update callers, validation logic, and display boundaries in sync.

---

## Default Completion Criteria

- Critical interaction paths are verified.
- Component text, layout, and state do not overlap or truncate critical content at common screen widths.
- Type checking, build, or equivalent verification covers the changes made.
- No forced assertions, global state, or implicit side effects are used to mask real contract issues.
