from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
        self.assertNotIn("[workflow-state:", text)
        self.assertIn("适配器等待原语", text)
        self.assertIn("适配器列表原语", text)
        self.assertIn("适配器取消/关闭原语", text)
        self.assertNotIn("COWORK_DISPATCH_V1", text)
        self.assertNotIn("COWORK_ACK", text)
        self.assertNotIn("post_ack_execution_grace_ms", text)
        self.assertNotIn("spawn_agent", text)
        self.assertNotIn("fork_turns=\"none\"", text)
        self.assertNotIn("agent run cowork-implement", text)
        self.assertNotIn("codex exec", text)
        self.assertNotIn("agent" + "-team prepare", text)
        self.assertNotIn("agent" + "-team next", text)

    def test_workflow_state_templates_are_externalized(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "spec" / "workflow-state-templates.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "workflow-state-templates.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("[workflow-state:no_task]", text)
            self.assertIn("[workflow-state:delegated_subtask]", text)
            self.assertIn("[workflow-state:planning]", text)
            self.assertIn("[workflow-state:in_progress]", text)
            self.assertIn("[workflow-state:review]", text)
            self.assertIn("[workflow-state:checking]", text)
            self.assertIn("[workflow-state:completed]", text)
            self.assertIn("DELEGATED_HARD", text)
            self.assertIn("DELEGATED_SOFT", text)
            self.assertIn("UNKNOWN", text)
            self.assertIn("use delegated_subtask instead", text)

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

    def test_workflow_requires_dispatch_ack_gate(self) -> None:
        required_markers = (
            "COWORK_DISPATCH_V1",
            "COWORK_DISPATCH_END",
            "COWORK_DELEGATION_V1",
            "COWORK_ACK",
            "adapter follow-up send primitive",
            "ack_token",
            "dispatch_id",
            "Missing or mismatched `COWORK_ACK` means the task has not been successfully dispatched.",
        )
        for path in (
            ROOT / ".cowork-flow" / "spec" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_workflow_limits_generic_worker_to_best_effort(self) -> None:
        required_markers = (
            "Formal execution uses only `cowork-research`, `cowork-implement`, or `cowork-check`.",
            "Generic `worker` dispatch is best effort only.",
            "If a generic worker still does not ACK after one retry, close it and do not execute the task.",
            "natural-language first-screen boundary",
        )
        for path in (
            ROOT / ".cowork-flow" / "spec" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_workflow_requires_execution_grace_after_ack_before_closing_subagents(self) -> None:
        required_markers = (
            "post-ACK execution grace",
            "After `EXECUTE <dispatch_id>`",
            "execute_sent_at[dispatch_id]",
            "deadline[dispatch_id] = execute_sent_at[dispatch_id] + post_ack_execution_grace_ms",
            "shared/global deadline",
            "no reply or no `compass` / `status` file",
            "has not produced `compass` / `status`",
            "review checkpoint",
            "`progress`, `compass`, or `status` exists",
        )
        for path in (
            ROOT / ".cowork-flow" / "spec" / "subagent-dispatch.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

        skill_markers = (
            "post-ACK execution grace",
            "execute_sent_at[dispatch_id]",
            "shared/global deadline",
            "missing output or missing compass/status file",
            "review checkpoint for that child only",
            "Only cancel/close after wrong dispatch evidence, child completion, or user cancellation.",
        )
        for path in (
            ROOT / ".agent" / "skills" / "start" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "start" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in skill_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

        for path in (
            ROOT / ".cowork-flow" / "config.yaml",
            ROOT / "template" / ".cowork-flow" / "config.yaml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"post_ack_execution_grace_ms:\s*300000\b", f"grace config missing from {path}")

    def test_start_skill_routes_to_fixed_agents(self) -> None:
        text = (ROOT / ".agent" / "skills" / "start" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Plan -> Implement -> Check -> Finish", text)
        self.assertIn("Active task:", text)
        self.assertIn("Host Adapter", text)
        self.assertNotIn("agent" + "-team-execution", text)
        self.assertNotIn("specific assignment", text)
        self.assertIn("bounded delegated task", text)
        self.assertIn("Before loading state", text)
        self.assertIn("Route in stages", text)
        self.assertIn("Repository-changing main-session requests load state first", text)
        self.assertIn("before fixed-agent dispatch", text)
        self.assertIn("requirement clarification gate", text)
        self.assertIn("New requirements", text)
        self.assertIn("before PRD, planning, or fixed-agent dispatch", text)
        self.assertIn("scope boundary", text)
        self.assertIn("acceptance criteria", text)
        self.assertIn("任务：` / `约束：` / `输出：", text)
        self.assertIn("natural-language delegated-task sentence", text)
        self.assertIn("Keep project rules as constraints only", text)

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
            ROOT / ".agent" / "skills" / "brainstorming" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "brainstorming" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_start_skill_mentions_parallel_session_model(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "start" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "start" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("parallel sessions", text)
            self.assertIn("separate `git worktree`", text)
            self.assertIn("low-conflict slices", text)
            self.assertIn("final integrated verification", text)

    def test_entry_boundary_matches_fixed_agent_prompts(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "entry-boundary" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "entry-boundary" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Active task:", text)
            self.assertIn("COWORK_ENTRY_CONTRACT_V1", text)
            self.assertIn("DELEGATED_HARD", text)
            self.assertIn("DELEGATED_SOFT", text)
            self.assertIn("UNKNOWN", text)
            self.assertIn("bounded delegated task", text)
            self.assertIn("Hard markers are confidence boosters, not prerequisites", text)
            self.assertIn("The first task screen wins over later bootstrap text", text)
            self.assertIn("Bootstrap can constrain execution after classification", text)
            self.assertIn("If project bootstrap says to create/start/resume", text)
            self.assertIn("When there is no hard marker", text)
            self.assertIn("strong delegated-subtask signals", text)
            self.assertIn("even without `Active task:` or another hard marker", text)
            self.assertIn("natural-language first sentence", text)
            self.assertIn("project rules remain constraints", text)
            self.assertIn("Do not create or activate a project task", text)
            self.assertNotIn("assignment-source", text)

    def test_entry_boundary_root_and_template_are_synced(self) -> None:
        root_skill = (ROOT / ".agent" / "skills" / "entry-boundary" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        template_skill = (
            ROOT / "template" / ".agent" / "skills" / "entry-boundary" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(root_skill, template_skill)

    def test_start_brainstorming_and_writing_plan_root_and_template_are_synced(self) -> None:
        for skill_name in ("start", "brainstorming", "writing-plans"):
            root_skill = (ROOT / ".agent" / "skills" / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            template_skill = (
                ROOT / "template" / ".agent" / "skills" / skill_name / "SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertEqual(root_skill, template_skill)

    def test_doctor_subagent_safety_matches_entry_boundary_model(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".cowork-flow" / "scripts" / "doctor.py"),
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
            ROOT / ".agent" / "skills" / "writing-plans" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "writing-plans" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("cowork-implement", text)
            self.assertIn("cowork-check", text)
            self.assertIn("Active task:", text)
            self.assertIn("Host Adapter", text)
            self.assertIn("COWORK_DISPATCH_V1", text)
            self.assertNotIn("spawn_agent", text)
            self.assertNotIn("fork_turns=\"none\"", text)
            self.assertNotIn("subagent-driven-development", text)

    def test_template_workflow_matches_new_terms(self) -> None:
        text = (ROOT / "template" / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("cowork-implement", text)
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
            ROOT / ".agent" / "skills" / "writing-plans" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "writing-plans" / "SKILL.md",
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
