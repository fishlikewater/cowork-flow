from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_DISPATCH = "COWORK_" + "DISPATCH_V1"
LEGACY_ACK = "COWORK_" + "ACK"
LEGACY_POST_ACK = "post" + "_ack_execution_grace_ms"
LEGACY_HARD = "DELEGATED_" + "HARD"
LEGACY_SOFT = "DELEGATED_" + "SOFT"
ENTRY_BOUNDARY = "entry" + "-boundary"


class WorkflowParallelSessionsTest(unittest.TestCase):
    def test_flow_authority_is_task_next_actions_skills_and_specs(self) -> None:
        self.assertFalse((ROOT / "template" / ".cowork-flow" / "workflow.md").exists())
        self.assertFalse((ROOT / "template" / ".zcode" / "scaffold" / ".cowork-flow" / "workflow.md").exists())

        self.assertFalse((ROOT / "template" / ".cowork-flow" / "spec" / "runtime" / "skill-registry.json").exists())
        skill_ids = {
            path.parent.name
            for path in (ROOT / "template" / "skills").glob("*/SKILL.md")
        }
        for skill_id in ("brainstorming", "task-planning", "cowork-flow", "task-review", "batch-execution"):
            self.assertIn(skill_id, skill_ids)
        self.assertTrue((ROOT / "template" / "skills" / "party-mode" / "manifest.json").is_file())
        self.assertTrue((ROOT / "template" / "skills" / "runtime-health" / "manifest.json").is_file())

        cowork_skill = (ROOT / "template" / "skills" / "cowork-flow" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("only public workflow router", cowork_skill)
        self.assertIn("Skill command manifests", cowork_skill)
        self.assertIn("authoritative flow surfaces", cowork_skill)
        self.assertNotIn("Registry", cowork_skill)
        self.assertNotIn("spawn_agent", cowork_skill)
        self.assertNotIn("fork_turns=\"none\"", cowork_skill)

        dispatch = (ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md").read_text(encoding="utf-8")
        for marker in ("cowork-research", "cowork-implement", "cowork-check", "runtime context"):
            self.assertIn(marker, dispatch)
        self.assertNotIn(LEGACY_DISPATCH, dispatch)
        self.assertNotIn(LEGACY_ACK, dispatch)
        self.assertNotIn(LEGACY_POST_ACK, dispatch)

    def test_obsolete_cleanup_without_compatibility_period(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        host_assets = json.loads((ROOT / "template" / ".cowork-flow" / "spec" / "runtime" / "host-assets.json").read_text(encoding="utf-8"))

        self.assertIn("正式版旧资产清理", readme)
        self.assertIn("obsoleteFiles", json.dumps(host_assets, ensure_ascii=False))
        self.assertNotIn("兼容升级", readme)
        self.assertNotIn("兼容迁移", json.dumps(host_assets, ensure_ascii=False))


    def test_public_docs_do_not_teach_removed_task_subcommands(self) -> None:
        docs = [
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "template" / "AGENTS.md",
        ]
        docs.extend((ROOT / "template" / "skills").glob("*/SKILL.md"))
        live_skills = ROOT / ".agents" / "skills"
        if live_skills.is_dir():
            docs.extend(live_skills.glob("*/SKILL.md"))

        removed_command_snippets = (
            "./.cowork-flow/run task create",
            "./.cowork-flow/run task start",
            "./.cowork-flow/run task review",
            "./.cowork-flow/run task complete",
            "./.cowork-flow/run task archive",
            "./.cowork-flow/run task init-context",
            "./.cowork-flow/run task add-context",
            "./.cowork-flow/run task add-planned-file",
            "./.cowork-flow/run task list",
            "./.cowork-flow/run task batch-",
        )
        for path in docs:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                for snippet in removed_command_snippets:
                    self.assertNotIn(snippet, text)

    def test_readme_describes_current_runtime_layout(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        required_markers = (
            "scripts/services/",
            "scripts/infra/storage/",
            "scripts/adapters/host/workflow_state_hook.py",
            "kernel 只解析状态事实和 action",
            "Skill 所有权由 manifest loader 注入",
        )
        stale_markers = (
            "scripts/application/",
            "scripts/common/storage/",
            "scripts/common/host/workflow_state_hook.py",
            "内核动作表推荐对应 Skill",
        )

        self.assertEqual(
            [],
            [marker for marker in required_markers if marker not in readme],
        )
        self.assertEqual(
            [],
            [marker for marker in stale_markers if marker in readme],
        )

    def test_workflow_state_templates_are_externalized(self) -> None:
        for path in (
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "workflow-state-templates.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("[workflow-state:no_task]", text)
            self.assertIn("[workflow-state:delegated_subtask]", text)
            self.assertIn("[workflow-state:planning]", text)
            self.assertIn("[workflow-state:in_progress]", text)
            self.assertIn("[workflow-state:review]", text)
            self.assertIn("[workflow-state:completed]", text)
            self.assertIn("runtime context", text)
            self.assertIn("UNKNOWN is not a delegated", text)
            self.assertNotIn(LEGACY_HARD, text)
            self.assertNotIn(LEGACY_SOFT, text)

    def test_brainstorming_skill_owns_clarification_gate(self) -> None:
        required_markers = (
            "active clarification gate",
            "goal, non-goals, assumptions, scope boundary, success criteria",
            "Acceptance criteria",
            "Open questions, risks, or blockers",
            "Hand off to `task-planning`",
        )
        path = ROOT / "template" / "skills" / "brainstorming" / "SKILL.md"
        skill_text = path.read_text(encoding="utf-8")
        for marker in required_markers:
            self.assertIn(marker, skill_text, f"{marker} missing from {path}")
        self.assertNotIn("workflow.md", skill_text)

    def test_workflow_requires_runtime_context_dispatch_gate(self) -> None:
        required_markers = (
            "Runtime-context subagent dispatch",
            "cowork_runtime_context_id",
            ".cowork-flow/.runtime/subagents/<runtime_context_id>.json",
            ".cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json",
            "cowork_host_context_key",
            "subagent bind <runtime_context_id> <host_context_key>",
            "Verified binding is the formal dispatch acceptance event",
            "fail-closed subagent state",
        )
        for path in (
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_zcode_scaffold_does_not_include_workflow_entrypoint_files(self) -> None:
        scaffold = ROOT / "template" / ".zcode" / "scaffold"

        self.assertFalse((scaffold / "AGENTS.md").exists())
        self.assertFalse((scaffold / "CLAUDE.md").exists())
        self.assertFalse((scaffold / ".cowork-flow").exists())

    def test_zcode_scaffold_does_not_vendor_workflow_files(self) -> None:
        scaffold = ROOT / "template" / ".zcode" / "scaffold"

        for relative_path in ("AGENTS.md", "CLAUDE.md", ".cowork-flow"):
            self.assertFalse((scaffold / relative_path).exists(), relative_path)

    def test_workflow_limits_generic_worker_to_advisory_work(self) -> None:
        required_markers = (
            "Formal dispatch uses `cowork-research`, `cowork-implement`, or `cowork-check`.",
            "Generic `worker`, `default`, or `explorer` dispatch is advisory only",
            "cannot satisfy formal Implement or Check completion",
        )
        for path in (
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_party_mode_is_single_runtime_board_advisory_workflow(self) -> None:
        skill_text = (ROOT / "template" / "skills" / "party-mode" / "SKILL.md").read_text(encoding="utf-8")
        for marker in ("Party Mode", "runtime-controlled", "board APIs", "moderator"):
            self.assertIn(marker, skill_text)

        spec_markers = (
            "Party Mode discussion children are advisory leaf executors.",
            "communicate through the `party-v2` runtime board",
            "cannot mutate task status",
            "cannot satisfy formal Implement or Check completion",
            "The public `party-mode` skill delegates discussion state",
            "current-round board visibility",
            "schema validation",
            "drift warnings",
            "round limits",
            "final reports",
            "host-neutral next actions",
            "does not change the formal `cowork-*` dispatch protocol",
            "does not satisfy Implement or Check completion",
        )
        for path in (
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in spec_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")
            self.assertNotIn("party-mode-v2` entrypoint", text)
            self.assertNotIn("spawn_agent", text)
            self.assertNotIn("wait_agent", text)
            self.assertNotIn("close_agent", text)

    def test_workflow_requires_runtime_context_closeout(self) -> None:
        required_markers = (
            "Wait for the child result with the adapter wait primitive.",
            "Confirm no stray running children with the adapter list primitive.",
            "Verify the child report by checking files, commands, and results",
            "close the child with the adapter cancel/close",
            ".cowork-flow/.runtime/sessions/<host_context_key>.json",
            ".cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json",
        )
        for path in (
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

        for path in (
            ROOT / "template" / ".cowork-flow" / "config.yaml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Formal subagent identity is runtime-context based", text)
            self.assertNotIn(LEGACY_POST_ACK, text)

    def test_lifecycle_runtime_common_modules_exist_in_template(self) -> None:
        required_markers = {
            "services/lifecycle_checks.py": ("LifecycleCheckRunner", "Modified file not listed in implement.jsonl", "collect_changed_paths"),
            "infra/git_snapshot.py": ("collect_changed_files", "staged", "untracked"),
            "kernel/task_state.py": ("transition_blockers", "task next <task-dir> --run --intent review", "completed"),
            "adapters/review/test_intent.py": ("validate_test_intent", "assert " + "True", "test_intent_review"),
        }

        common_root = ROOT / "template" / ".cowork-flow" / "scripts"
        gates_dir = common_root / "common" / "gates"
        gate_sources = []
        if gates_dir.exists():
            gate_sources = [
                path
                for path in gates_dir.rglob("*")
                if path.is_file() and path.suffix in {".py", ".json"}
            ]
        self.assertEqual([], gate_sources)
        for file_name, markers in required_markers.items():
            template_text = (common_root / Path(file_name)).read_text(encoding="utf-8")

            for marker in markers:
                self.assertIn(marker, template_text)

    def test_closeout_contract_avoids_placeholder_commits(self) -> None:
        text = (ROOT / "template" / ".cowork-flow" / "spec" / "references" / "definition-of-done.md").read_text(encoding="utf-8")

        self.assertIn("git status --porcelain=v1 -uall", text)
        self.assertNotIn('commit "-"', text)
        self.assertNotIn('add-session --title "<title>" --commit "-"', text)
        self.assertNotIn("add_session", text)

    def test_add_session_and_workspace_journal_are_not_public_flow(self) -> None:
        docs = [
            ROOT / "README.md",
            ROOT / "template" / ".cowork-flow" / "scripts" / "run.py",
            ROOT / "src" / "commands" / "init.js",
            ROOT / "template" / ".cowork-flow" / "scripts" / "adapters" / "git" / "git_context.py",
        ]
        forbidden_markers = (
            "add-session",
            "add_session",
            "workspace journals",
            "Development Journal",
            "Workspace Index",
            "--mode record",
        )
        for path in docs:
            text = path.read_text(encoding="utf-8")
            self.assertEqual([], [marker for marker in forbidden_markers if marker in text], path)

        self.assertFalse((ROOT / "template" / ".cowork-flow" / "scripts" / "adapters" / "cli" / "add_session.py").exists())
        self.assertFalse((ROOT / "template" / ".cowork-flow" / "workspace" / "index.md").exists())

    def test_definition_of_done_uses_complete_git_status_snapshot(self) -> None:
        text = (
            ROOT
            / "template"
            / ".cowork-flow"
            / "spec"
            / "references"
            / "definition-of-done.md"
        ).read_text(encoding="utf-8")

        self.assertIn("git status --porcelain=v1 -uall", text)
        self.assertIn("staged、unstaged、untracked", text)
        self.assertNotIn("git diff --name-only", text)

    def test_local_bootstrap_files_match_template_when_present(self) -> None:
        local_root = ROOT / ".cowork-flow"
        mirrored_files = (
            Path("spec/runtime/contract-registry.json"),
            Path("spec/references/definition-of-done.md"),
            Path("spec/contracts/workflow-state-templates.md"),
        )
        missing_files = [
            str(relative_path)
            for relative_path in mirrored_files
            if not (local_root / relative_path).is_file()
        ]
        if missing_files:
            self.skipTest(
                "local bootstrap .cowork-flow files are absent: "
                + ", ".join(missing_files)
            )

        for relative_path in mirrored_files:
            local_text = (local_root / relative_path).read_text(encoding="utf-8")
            template_text = (
                ROOT / "template" / ".cowork-flow" / relative_path
            ).read_text(encoding="utf-8")
            self.assertEqual(template_text, local_text, str(relative_path))

    def test_runtime_rule_registry_assets_are_removed_from_template_spec(self) -> None:
        template_spec = ROOT / "template" / ".cowork-flow" / "spec"
        zcode_spec = (
            ROOT
            / "template"
            / ".zcode"
            / "scaffold"
            / ".cowork-flow"
            / "spec"
        )
        self.assertFalse(zcode_spec.exists())
        for relative_path in (
            Path("runtime") / "rules.json",
            Path("schemas") / "rules.schema.json",
        ):
            self.assertFalse((template_spec / relative_path).exists(), str(relative_path))

    def test_public_tdd_skill_has_no_evidence_artifact_contract(self) -> None:
        tdd_text = (
            ROOT
            / "template"
            / "skills"
            / "test-first"
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("red-green-refactor", tdd_text)
        self.assertIn("Do not write TDD evidence objects", tdd_text)
        for forbidden in (
            "redExitCode",
            "greenExitCode",
            'type: "tdd"',
            "tdd_exemption",
            "TDD Evidence Runtime",
        ):
            self.assertNotIn(forbidden, tdd_text)

    def test_spec_maintenance_skill_preserves_update_checklist(self) -> None:
        required_markers = (
            "Choose Location",
            "`backend/` or `frontend/`",
            "`guides/`",
            "State the trigger and scope",
            "Show the contract or command shape",
            "Include good/bad cases when useful",
            "State tests or checks that protect the behavior",
            "Update the matching `index.md`",
            "duplicate guidance",
            "stale wording",
        )
        skill_text = (
            ROOT
            / "template"
            / "skills"
            / "spec-sync"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            [],
            [marker for marker in required_markers if marker not in skill_text],
        )

    def test_review_skill_and_agent_require_test_intent_review(self) -> None:
        required_markers = (
            "test intent",
            "shallow tests",
            "test_intent_review",
        )
        for path in (
            ROOT / "template" / "skills" / "task-review" / "SKILL.md",
            ROOT / "template" / ".codex" / "agents" / "cowork-check.toml",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_cowork_flow_skill_routes_without_copying_agent_protocol(self) -> None:
        text = (
            ROOT / "template" / "skills" / "cowork-flow" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("only public workflow router", text)
        self.assertIn("./.cowork-flow/run task next --json", text)
        self.assertIn("allowedOperations", text)
        self.assertIn("recommendedSkill", text)
        self.assertIn("Runtime Gates carry hard enforcement", text)
        self.assertNotIn(".cowork-flow/run subagent init", text)
        self.assertNotIn("cowork_host_context_key", text)
        self.assertNotIn("adapter wait/list/cancel primitives", text)

    def test_brainstorming_skill_requires_clarification_output(self) -> None:
        required_markers = (
            "active clarification gate",
            "before decision-anchor, planning, fixed-agent dispatch, or code changes begin",
            "goal, non-goals, assumptions, scope boundary, success criteria",
            "recommended direction",
            "Do not write decision-anchor, planning, or fixed-agent dispatch input",
            "Key assumptions",
            "Scope boundary",
            "Recommended direction and rejected alternatives",
            "Acceptance criteria",
            "Open questions, risks, or blockers",
        )
        text = (ROOT / "template" / "skills" / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
        for marker in required_markers:
            self.assertIn(marker, text, f"{marker} missing from template/skills/brainstorming/SKILL.md")

    def test_planning_and_brainstorming_use_guides_before_implementation(self) -> None:
        planning = (ROOT / "template" / "skills" / "task-planning" / "SKILL.md").read_text(encoding="utf-8")
        brainstorming = (ROOT / "template" / "skills" / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")

        planning_markers = (
            ".cowork-flow/spec/guides/index.md",
            "non-trivial, ambiguous, cross-layer, or reusable-work planning",
            "capture the selected conclusion in `decision-anchor.md`",
        )
        brainstorming_markers = (
            ".cowork-flow/spec/guides/index.md",
            "Use guide material to shape requirements, options, and implementation boundaries",
            "next planning handoff",
        )

        self.assertEqual([], [marker for marker in planning_markers if marker not in planning])
        self.assertEqual([], [marker for marker in brainstorming_markers if marker not in brainstorming])

    def test_cowork_flow_skill_does_not_copy_parallel_session_model(self) -> None:
        text = (
            ROOT / "template" / "skills" / "cowork-flow" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("parallel sessions", text)
        self.assertNotIn("separate `git worktree`", text)
        self.assertNotIn("low-conflict slices", text)
        self.assertNotIn("final integrated verification", text)

    def test_entry_boundary_skill_is_removed(self) -> None:
        self.assertFalse((ROOT / "template" / "skills" / ENTRY_BOUNDARY / "SKILL.md").exists())

    def test_doctor_subagent_safety_matches_runtime_context_model(self) -> None:
        doctor = ROOT / "template" / "skills" / "runtime-health" / "scripts" / "doctor.py"
        text = doctor.read_text(encoding="utf-8")
        self.assertIn("check_distribution", text)
        self.assertIn("action_owners", text)
        self.assertIn("workflow-state-templates.md", text)

    def test_task_planning_routes_to_fixed_agents(self) -> None:
        text = (ROOT / "template" / "skills" / "task-planning" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("cowork-implement", text)
        self.assertIn("cowork-check", text)
        self.assertIn("Host Adapter", text)
        self.assertIn(".cowork-flow/run subagent init", text)
        self.assertIn("cowork_runtime_context_id", text)
        self.assertNotIn("spawn_agent", text)
        self.assertNotIn("fork_turns=\"none\"", text)
        self.assertNotIn("subagent-driven-development", text)

    def test_template_does_not_ship_standalone_workflow_authority(self) -> None:
        self.assertFalse((ROOT / "template" / ".cowork-flow" / "workflow.md").exists())
        self.assertFalse((ROOT / "template" / ".zcode" / "scaffold" / ".cowork-flow" / "workflow.md").exists())

    def test_task_planning_skill_documents_parallel_operations(self) -> None:
        text = (ROOT / "template" / "skills" / "task-planning" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Do not require the user to predeclare parallel execution", text)
        self.assertIn("Every plan must state the execution strategy", text)
        self.assertIn("git worktree", text)
        self.assertIn("low-conflict slices", text)
        self.assertIn("file ownership", text)
        self.assertIn("dependencies", text)
        self.assertIn("expected outputs", text)
        self.assertIn("final integrated verification", text)

    def test_task_planning_skills_require_parallel_scope_fields(self) -> None:
        text = (ROOT / "template" / "skills" / "task-planning" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("executable scope", text)
        self.assertIn("acceptance criteria", text)
        self.assertIn("Task Briefs, Not Design Docs", text)
        self.assertIn("prevent implementation drift", text)
        self.assertIn("must not explain every possible option", text)
        self.assertIn("Tiny", text)
        self.assertIn("Normal", text)
        self.assertIn("High-risk", text)
        self.assertIn("**File Boundaries**", text)
        self.assertIn("**Key Symbols**", text)
        self.assertIn("**Implementation Notes**", text)
        self.assertIn("**Test Proof**", text)
        self.assertIn("**Completion Conditions**", text)
        self.assertIn("**Prohibited Drift**", text)
        self.assertIn("must stop and report back", text)
        self.assertIn("Execution strategy guide", text)
        self.assertIn("Use serial work when slices share files", text)
        self.assertIn("Use parallel low-conflict slices only when file ownership is clean", text)
        self.assertIn("Use worktree parallel when independent tasks may touch", text)
        self.assertIn("Parallel work items", text)
        self.assertIn("Do not require the user to predeclare parallel execution", text)
        self.assertIn("Every plan must state the execution strategy", text)
        self.assertIn("file ownership", text)
        self.assertIn("dependencies", text)
        self.assertIn("expected outputs", text)
        self.assertIn("verification commands", text)
        self.assertNotRegex(text, r"[\u4e00-\u9fff]")
