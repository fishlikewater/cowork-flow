# Replace spec placeholders with defaults

## Goal

Replace placeholder-style spec content under `template/.cowork-flow/spec/` with reusable generic standards that can be used immediately after init.

## Requirements

- Template spec files must not contain fill-in markers such as `<...>`, `按项目填写`, `TBD`, or `TODO`.
- Backend, frontend, and guide specs should define conservative defaults rather than project-specific commands or frameworks.
- Sync the root `.cowork-flow/spec/` copy where the same template specs exist so the repository stays aligned with the template.
- Add regression coverage that fails when template spec placeholders are reintroduced.

## Verification

- Placeholder scan over `template/.cowork-flow/spec/` and root `.cowork-flow/spec/` passes.
- Focused template-path tests pass.
- Full test suite passes.
