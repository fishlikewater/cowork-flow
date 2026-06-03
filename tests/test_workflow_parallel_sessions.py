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
        self.assertIn("[workflow-state:no_task]", text)
        self.assertIn("[workflow-state:delegated_subtask]", text)
        self.assertIn("[workflow-state:planning]", text)
        self.assertIn("[workflow-state:in_progress]", text)
        self.assertIn("[workflow-state:completed]", text)
        self.assertIn("适配器等待原语", text)
        self.assertIn("适配器列表原语", text)
        self.assertIn("适配器取消/关闭原语", text)
        self.assertNotIn("spawn_agent", text)
        self.assertNotIn("fork_turns=\"none\"", text)
        self.assertNotIn("agent run cowork-implement", text)
        self.assertNotIn("codex exec", text)
        self.assertNotIn("agent" + "-team prepare", text)
        self.assertNotIn("agent" + "-team next", text)

    def test_workflow_requires_dispatch_ack_gate(self) -> None:
        required_markers = (
            "COWORK_DISPATCH_V1",
            "COWORK_DISPATCH_END",
            "COWORK_DELEGATION_V1",
            "COWORK_ACK",
            "适配器后续发送原语",
            "ack_token",
            "dispatch_id",
            "缺失或不匹配的 `COWORK_ACK` 表示任务尚未成功派发。",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_workflow_limits_generic_worker_to_best_effort(self) -> None:
        required_markers = (
            "正式执行只使用 `cowork-research`、`cowork-implement` 或 `cowork-check`。",
            "通用 `worker` 派发只视为尽力而为。",
            "如果通用 worker 重试一次后仍未 ACK，关闭它且不要执行该任务。",
            "自然语言首屏边界",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_workflow_requires_execution_grace_after_ack_before_closing_subagents(self) -> None:
        required_markers = (
            "ACK 后执行宽限期",
            "`EXECUTE <dispatch_id>` 后",
            "execute_sent_at[dispatch_id]",
            "deadline[dispatch_id] = execute_sent_at[dispatch_id] + post_ack_execution_grace_ms",
            "共享/全局截止时间",
            "没有回复或没有 `compass` / `status` 文件",
            "不得因为执行中的子任务尚未产出",
            "复核点",
            "`progress`、`compass` 或 `status` 文件",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
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
        self.assertIn("任务：` / `约束：` / `输出：", text)
        self.assertIn("natural-language delegated-task sentence", text)
        self.assertIn("Keep project rules as constraints only", text)

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

    def test_start_and_writing_plan_root_and_template_are_synced(self) -> None:
        for skill_name in ("start", "writing-plans"):
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
