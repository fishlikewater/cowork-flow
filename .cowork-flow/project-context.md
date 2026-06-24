# Project Context

<!-- COWORK-FLOW:PROJECT-CONTEXT:START -->
## Generated Context

Generated deterministically from local project files.

## Project Identity

- Name: `cowork-flow`
- Stack: Python、Node.js
- Commit policy: 允许 AI 提交
- Documentation language: unspecified

## Package Scripts

- `npm run pack:check`: `node scripts/pack-check.js`
- `npm run release`: `sh scripts/release.sh`
- `npm run test`: `node --test`
- `npm run test:all`: `npm test && npm run test:template && npm run pack:check`
- `npm run test:template`: `node scripts/run-template-tests.js`

## Workflow Commands

- `./.cowork-flow/run task next`: show next safe workflow action.
- `./.cowork-flow/run task start <task-dir>`: activate task and run readiness gates.
- `./.cowork-flow/run task review [task-dir]`: move task to check stage.
- `./.cowork-flow/run task complete [task-dir]`: mark task completed.
- `./.cowork-flow/run change validate <slug>`: validate change metadata and required docs.
- `./.cowork-flow/run project-context refresh`: refresh this file.

## Host Adapters

- `.codex`: present
- `.opencode`: present
- `.claude`: present
- `.cowork-flow/adapters/codex/adapter.yaml`: present
- `.cowork-flow/adapters/opencode/adapter.yaml`: present
- `.cowork-flow/adapters/claude-code/adapter.yaml`: present

## Important Specs

- `.cowork-flow/spec/backend/database-guidelines.md`
- `.cowork-flow/spec/backend/directory-structure.md`
- `.cowork-flow/spec/backend/encoding-guidelines.md`
- `.cowork-flow/spec/backend/error-handling.md`
- `.cowork-flow/spec/backend/index.md`
- `.cowork-flow/spec/backend/logging-guidelines.md`
- `.cowork-flow/spec/backend/quality-guidelines.md`
- `.cowork-flow/spec/contracts/capabilities.md`
- `.cowork-flow/spec/frontend/component-guidelines.md`
- `.cowork-flow/spec/frontend/directory-structure.md`
- `.cowork-flow/spec/frontend/hook-guidelines.md`
- `.cowork-flow/spec/frontend/index.md`
- `.cowork-flow/spec/frontend/quality-guidelines.md`
- `.cowork-flow/spec/frontend/state-management.md`
- `.cowork-flow/spec/frontend/type-safety.md`
- `.cowork-flow/spec/guides/code-reuse-thinking-guide.md`
- `.cowork-flow/spec/guides/cross-layer-thinking-guide.md`
- `.cowork-flow/spec/guides/index.md`
- `.cowork-flow/spec/guides/pre-implementation-checklist.md`
- `.cowork-flow/spec/contracts/subagent-dispatch.md`
- `.cowork-flow/spec/contracts/workflow-state-templates.md`

## Local Constraints

- `AGENTS.md`: present
- `.cowork-flow/workflow.md`: present
- `.cowork-flow/config.yaml`: present
- `.cowork-flow/.version`: present
- Generated context is an index. Authoritative rules stay in `AGENTS.md`, `.cowork-flow/workflow.md`, and `.cowork-flow/spec/`.
- Do not hand-edit generated sections; add durable project notes under Manual Notes.

<!-- COWORK-FLOW:PROJECT-CONTEXT:END -->

## Manual Notes

- Add project-specific notes here.
