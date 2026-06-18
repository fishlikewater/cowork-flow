# Backend Development Guidelines

## Default Baseline

- Backend code prioritizes clear business boundaries, stable interface contracts, and verifiable behavior.
- Spec source priority: existing code, config, tests, migration scripts, API docs in the repo first, then generic rules in this directory.
- New implementations should align with the existing architecture; do not silently introduce a second layering, naming, error model, or data access pattern.
- When conventions cannot be inferred from existing code, apply the conservative defaults in this directory and document assumptions in the task record.

---

## Reading Order

| Document | Purpose |
|------|------|
| [Directory Structure](./directory-structure.md) | Module layout, package structure, naming conventions |
| [Database Guidelines](./database-guidelines.md) | Entities, migrations, queries, transactions |
| [Error Handling](./error-handling.md) | Error codes, exception boundaries, unified responses |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, sensitive data, trace identifiers |
| [Quality Guidelines](./quality-guidelines.md) | Testing, linting, gates, prohibited patterns |
| [Encoding Guidelines](./encoding-guidelines.md) | Encoding, line endings, BOM, and cross-platform read/write conventions |

---

## Usage Principles

- Follow existing repo patterns first; do not introduce styles that conflict with existing conventions.
- Check existing shared modules, libraries, or infrastructure wrappers before writing new code.
- Keep Controller / API layers thin; place business rules in services, use cases, or domain layers.
- When changing interfaces, data structures, permissions, async chains, or persistence models, update callers, tests, and related docs in sync.
- For cross-module, async chain, or permission boundary changes, also read the thinking guides under `guides/`.

---

## Default Completion Criteria

- Critical paths have automated verification or explicit manual verification records.
- Error paths, null values, insufficient permissions, duplicate submissions, and other edge cases are explicitly addressed.
- Runtime config, data migration, compatibility, and rollback impacts are documented.
- Do not describe "tests not run" as "tests passed".
