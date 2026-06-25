from __future__ import annotations

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
    def test_workflow_uses_fixed_agent_mainline(self) -> None:
        text = (ROOT / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("cowork-research", text)
        self.assertIn("cowork-implement", text)
        self.assertIn("cowork-check", text)
        self.assertIn("宿主适配器", text)
        self.assertIn("新鲜子上下文", text)
        self.assertIn("workflow-state-templates.md", text)
        self.assertIn("subagent-dispatch.md", text)
        self.assertIn("runtime context", text)
        self.assertNotIn("[workflow-state:", text)
        self.assertIn("适配器等待原语", text)
        self.assertIn("适配器列表原语", text)
        self.assertIn("适配器取消/关闭原语", text)
        self.assertNotIn(LEGACY_DISPATCH, text)
        self.assertNotIn(LEGACY_ACK, text)
        self.assertNotIn(LEGACY_POST_ACK, text)
        self.assertNotIn("spawn_agent", text)
        self.assertNotIn("fork_turns=\"none\"", text)
        self.assertNotIn("agent run cowork-implement", text)
        self.assertNotIn("codex exec", text)
        self.assertNotIn("agent" + "-team prepare", text)
        self.assertNotIn("agent" + "-team next", text)

    def test_workflow_state_templates_are_externalized(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "spec" / "contracts" / "workflow-state-templates.md",
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

    def test_workflow_requires_brainstorming_clarification_gate(self) -> None:
        required_markers = (
            "需求澄清与头脑风暴门禁",
            "新需求先判断清晰度",
            "范围边界",
            "验收标准",
            "推荐方向",
            "开放问题/阻塞",
            "PRD、计划或固定代理派发",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

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
            ROOT / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_workflow_limits_generic_worker_to_advisory_work(self) -> None:
        required_markers = (
            "Formal dispatch uses `cowork-research`, `cowork-implement`, or `cowork-check`.",
            "Generic `worker`, `default`, or `explorer` dispatch is advisory only",
            "cannot satisfy formal Implement or Check completion",
        )
        for path in (
            ROOT / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_party_mode_is_bounded_manual_advisory_workflow(self) -> None:
        workflow_markers = (
            "手动 Party Mode",
            "advisory roundtable",
            "fresh child contexts",
            "不能推进任务状态",
            "不能满足正式实现或检查完成条件",
            "party-mode skill",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in workflow_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

        spec_markers = (
            "Party Mode discussion children are advisory leaf executors.",
            "They use fresh child contexts for evidence gathering",
            "cannot mutate task status",
            "cannot satisfy formal Implement or Check completion",
            "The `party-mode` skill owns round limits, continuation gates, stop gates, and output schemas.",
        )
        for path in (
            ROOT / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in spec_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_party_mode_v2_is_runtime_board_advisory_workflow(self) -> None:
        workflow_markers = (
            "手动 Party Mode V2",
            "runtime board advisory workflow",
            "Python runtime 控制看板",
            "当前轮视图",
            "子代理通过 board API 交流",
            "主持人只监控 runtime status",
            "V2 runtime 只输出 host-neutral next actions",
            "不能满足正式实现或检查完成条件",
            "宿主专属原语仍只在 `.cowork-flow/adapters/<host>/adapter.yaml` 和宿主资产中声明",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in workflow_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")
            self.assertNotIn("spawn_agent", text)
            self.assertNotIn("wait_agent", text)
            self.assertNotIn("close_agent", text)
            self.assertNotIn("Claude Task", text)
            self.assertNotIn("OpenCode task", text)

        spec_markers = (
            "Party Mode V2 discussion children are also advisory leaf executors.",
            "`party-mode-v2` entrypoint delegates discussion state",
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
            ROOT / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in spec_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")
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
            ROOT / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

        skill_markers = (
            ".cowork-flow/run subagent init",
            "cowork_runtime_context_id",
            "fails closed",
            "adapter wait/list/cancel primitives",
            ".cowork-flow/run subagent close",
        )
        for path in (
            ROOT / ".agents" / "skills" / "start" / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / "start" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in skill_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

        for path in (
            ROOT / ".cowork-flow" / "config.yaml",
            ROOT / "template" / ".cowork-flow" / "config.yaml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Formal subagent identity is runtime-context based", text)
            self.assertNotIn(LEGACY_POST_ACK, text)

    def test_gate_runtime_common_modules_are_synced_between_root_and_template(self) -> None:
        required_markers = {
            "gates/coding_standards.py": ("validate_changed_files", "encoding=\"utf-8\"", "CS-UTF8"),
            "gates/gates.py": ("GateResult", "GateRunner", "exit_code"),
            "git/git_snapshot.py": ("collect_changed_files", "staged", "untracked"),
            "task/state_machine.py": ("transition_blockers", "task review", "completed"),
            "gates/tdd_evidence.py": ("validate_tdd_evidence", "tdd.jsonl", "redExitCode"),
            "gates/test_intent.py": ("validate_test_intent", "assert " + "True", "test_intent_review"),
            "gates/validate_coding_standards.py": ("validate_coding_standards", "collect_changed_files", "--validate"),
        }

        for file_name, markers in required_markers.items():
            root_text = (
                ROOT / ".cowork-flow" / "scripts" / "common" / Path(file_name)
            ).read_text(encoding="utf-8")
            template_text = (
                ROOT / "template" / ".cowork-flow" / "scripts" / "common" / Path(file_name)
            ).read_text(encoding="utf-8")

            self.assertEqual(root_text, template_text)
            for marker in markers:
                self.assertIn(marker, root_text)

    def test_tdd_skill_is_synced_between_root_template_and_claude_mirrors(self) -> None:
        required_markers = (
            "red-green-refactor",
            "tdd.jsonl",
            "acceptanceId",
            "redExitCode",
            "greenExitCode",
            "whyThisTestMatters",
            "ClassName.test_method",
            "exemption",
        )
        root_text = (ROOT / ".agents" / "skills" / "tdd" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for path in (
            ROOT / "template" / ".agents" / "skills" / "tdd" / "SKILL.md",
            ROOT / ".claude" / "skills" / "tdd" / "SKILL.md",
            ROOT / "template" / ".claude" / "skills" / "tdd" / "SKILL.md",
        ):
            self.assertEqual(root_text, path.read_text(encoding="utf-8"), str(path))
        for marker in required_markers:
            self.assertIn(marker, root_text)

    def test_check_skill_and_agent_require_test_intent_review(self) -> None:
        required_markers = (
            "test intent",
            "shallow tests",
            "test_intent_review",
        )
        for path in (
            ROOT / ".agents" / "skills" / "check" / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / "check" / "SKILL.md",
            ROOT / ".claude" / "skills" / "check" / "SKILL.md",
            ROOT / "template" / ".claude" / "skills" / "check" / "SKILL.md",
            ROOT / ".codex" / "agents" / "cowork-check.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-check.toml",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_start_skill_routes_to_fixed_agents(self) -> None:
        text = (ROOT / ".agents" / "skills" / "start" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Plan -> Implement -> Check -> Finish", text)
        self.assertIn("Host Adapter", text)
        self.assertNotIn("agent" + "-team-execution", text)
        self.assertNotIn("specific assignment", text)
        self.assertIn("accepted only after runtime context binding is recorded", text)
        self.assertIn("cowork_host_context_key", text)
        self.assertIn("subagent bind <runtime_context_id> <host_context_key>", text)
        self.assertIn("Route in stages", text)
        self.assertIn("Repository-changing main-session requests load state first", text)
        self.assertIn("before fixed-agent dispatch", text)
        self.assertIn("requirement clarification gate", text)
        self.assertIn("New requirements", text)
        self.assertIn("before PRD, planning, or fixed-agent dispatch", text)
        self.assertIn("scope boundary", text)
        self.assertIn("acceptance criteria", text)
        self.assertIn(".cowork-flow/run subagent init", text)
        self.assertIn("Do not infer subagent identity from prompt shape", text)

    def test_brainstorming_skill_requires_clarification_output(self) -> None:
        required_markers = (
            "active clarification gate",
            "before PRD, planning, fixed-agent dispatch, or code changes begin",
            "goal, non-goals, assumptions, scope boundary, success criteria",
            "recommended direction",
            "Do not write PRD, planning, or fixed-agent dispatch input",
            "Key assumptions",
            "Scope boundary",
            "Recommended direction and rejected alternatives",
            "Acceptance criteria",
            "Open questions, risks, or blockers",
        )
        for path in (
            ROOT / ".agents" / "skills" / "brainstorming" / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / "brainstorming" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_start_skill_mentions_parallel_session_model(self) -> None:
        for path in (
            ROOT / ".agents" / "skills" / "start" / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / "start" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("parallel sessions", text)
            self.assertIn("separate `git worktree`", text)
            self.assertIn("low-conflict slices", text)
            self.assertIn("final integrated verification", text)

    def test_entry_boundary_skill_is_removed(self) -> None:
        for path in (
            ROOT / ".agents" / "skills" / ENTRY_BOUNDARY / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / ENTRY_BOUNDARY / "SKILL.md",
            ROOT / ".claude" / "skills" / ENTRY_BOUNDARY / "SKILL.md",
            ROOT / "template" / ".claude" / "skills" / ENTRY_BOUNDARY / "SKILL.md",
        ):
            self.assertFalse(path.exists(), str(path))

    def test_start_brainstorming_and_writing_plan_root_and_template_are_synced(self) -> None:
        for skill_name in ("start", "brainstorming", "writing-plans"):
            root_skill = (ROOT / ".agents" / "skills" / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            template_skill = (
                ROOT / "template" / ".agents" / "skills" / skill_name / "SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertEqual(root_skill, template_skill)

    def test_doctor_subagent_safety_matches_runtime_context_model(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".cowork-flow" / "scripts" / "commands" / "doctor.py"),
                "--subagent-safety",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_writing_plans_routes_to_fixed_agents(self) -> None:
        for path in (
            ROOT / ".agents" / "skills" / "writing-plans" / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / "writing-plans" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("cowork-implement", text)
            self.assertIn("cowork-check", text)
            self.assertIn("Host Adapter", text)
            self.assertIn(".cowork-flow/run subagent init", text)
            self.assertIn("cowork_runtime_context_id", text)
            self.assertNotIn("spawn_agent", text)
            self.assertNotIn("fork_turns=\"none\"", text)
            self.assertNotIn("subagent-driven-development", text)

    def test_template_workflow_matches_new_terms(self) -> None:
        text = (ROOT / "template" / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("cowork-implement", text)
        self.assertIn("runtime context", text)
        self.assertNotIn("agent" + "-team prepare", text)

    def test_workflow_documents_parallel_operations(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("并行会话", text)
            self.assertIn("用户无需在需求输入时声明是否并行", text)
            self.assertIn("计划阶段由主会话评估并行可行性", text)
            self.assertIn("开发计划必须明确执行策略", text)
            self.assertIn("git worktree", text)
            self.assertIn("低冲突切片", text)
            self.assertIn("文件归属", text)
            self.assertIn("依赖关系", text)
            self.assertIn("预期产物", text)
            self.assertIn("最终集成验证", text)

    def test_writing_plan_skills_require_parallel_scope_fields(self) -> None:
        for path in (
            ROOT / ".agents" / "skills" / "writing-plans" / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / "writing-plans" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("executable scope", text)
            self.assertIn("acceptance criteria", text)
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
