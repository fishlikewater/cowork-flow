# Runtime Binding Shim

**Goal:** Add an explicit runtime-context binding shim for formal subagents on
Codex, Claude Code, and OpenCode so child work is accepted only after runtime
state is bound and verified.

**Execution strategy:** Sequential main-session implementation. This task
changes the subagent dispatch contract itself, so fixed-agent dispatch should
only be used after the shim contract and tests are in place.

**Verification:** Focused runtime, adapter, host asset, and hook/plugin tests,
then sync/package checks and `npm run test:all`.

## Steps

1. Finalize change readiness.
   - Verify: `./.cowork-flow/run change validate 06-05-runtime-binding-shim`
   - Verify: `./.cowork-flow/run task next .cowork-flow/tasks/06-05-runtime-binding-shim`

2. Tighten runtime bind semantics.
   - Add tests for explicit `subagent bind` success, same-key idempotency, and
     different-key rejection.
   - Implement the smallest runtime change needed to satisfy those tests.
   - Verify: `python -m unittest tests.test_subagent_dispatch tests.test_active_task_runtime`

3. Update host adapter truth.
   - Mark Codex runtime context binding as shim, not native.
   - Align Claude Code and OpenCode declarations with the explicit shim/fallback
     contract without overstating model-before-execution binding.
   - Keep root and template adapters synchronized.
   - Verify: `python -m unittest tests.test_host_adapters`

4. Update formal agent and command assets.
   - Add required `cowork_host_context_key` and first-step `subagent bind`
     instructions to Codex, Claude Code, and OpenCode fixed agents.
   - Update command assets so main sessions generate runtime id, host context
     key, and parent-side bound-state verification steps.
   - Keep root and template host assets synchronized.
   - Verify: `python -m unittest tests.test_cowork_agents tests.test_no_legacy_template_paths`

5. Preserve automatic hook/plugin binding as an earlier path.
   - Keep direct Codex/Claude hook and OpenCode plugin binding tests green.
   - Add coverage that shim bind remains valid when auto-binding is unavailable.
   - Verify: `python -m unittest tests.test_codex_hooks tests.test_claude_hooks`
   - Verify: `node --test test/opencode-plugin.test.js`

6. Run integration checks.
   - Verify: `./.cowork-flow/run doctor --subagent-safety`
   - Verify: `git diff --check`
   - Verify: `npm run test:all`
