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
    def test_workflow_uses_fixed_agent_mainline(self) -> None:
        text = (ROOT / "template" / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
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

    def test_workflow_names_obsolete_cleanup_without_compatibility_period(self) -> None:
        for path in (
            ROOT / "template" / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".zcode" / "scaffold" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("旧资产清理", text, str(path))
            self.assertIn("obsolete cleanup", text, str(path))
            self.assertIn("读取边界保留", text, str(path))
            self.assertNotIn("兼容迁移", text, str(path))

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("正式版旧资产清理", readme)
        self.assertNotIn("兼容升级", readme)

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

    def test_workflow_requires_brainstorming_clarification_gate(self) -> None:
        required_markers = (
            "需求澄清与头脑风暴门禁",
            "新需求先判断清晰度",
            "范围边界",
            "验收标准",
            "推荐方向",
            "开放问题/阻塞",
            "进入决策锚点、计划或固定代理派发",
        )
        for path in (
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
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_zcode_scaffold_uses_current_workflow_entrypoint(self) -> None:
        text = (
            ROOT / "template" / ".zcode" / "scaffold" / "AGENTS.md"
        ).read_text(encoding="utf-8")

        self.assertIn("./.cowork-flow/run task next", text)
        self.assertIn("task.json.status", text)
        self.assertIn("in_progress", text)
        self.assertIn("review", text)
        self.assertNotIn("before-dev", text)

    def test_zcode_scaffold_party_mode_contract_matches_formal_entrypoint(self) -> None:
        text = (
            ROOT
            / "template"
            / ".zcode"
            / "scaffold"
            / ".cowork-flow"
            / "spec"
            / "contracts"
            / "subagent-dispatch.md"
        ).read_text(encoding="utf-8")

        self.assertIn("communicate through the `party-v2` runtime board", text)
        self.assertIn("The public `party-mode` skill delegates discussion state", text)
        self.assertIn("host-neutral next actions", text)
        self.assertNotIn("party-mode-v2` entrypoint", text)

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
        workflow_markers = (
            "Party Mode 是用户手动触发的 runtime board advisory workflow",
            "通过 `party-mode` 入口启动 `party-v2` runtime",
            "Python runtime 控制看板",
            "当前轮视图",
            "子代理通过 board API 交流",
            "主持人只监控 runtime status",
            "Party Mode runtime 只输出 host-neutral next actions",
            "不能推进任务状态",
            "不能满足正式实现或检查完成条件",
            "宿主专属原语仍只在 `.cowork-flow/adapters/<host>/adapter.yaml` 和宿主资产中声明",
        )
        for path in (
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in workflow_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")
            self.assertNotIn("手动 Party Mode V2", text)

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

    def test_gate_runtime_common_modules_exist_in_template(self) -> None:
        required_markers = {
            "gates/coding_standards.py": ("validate_changed_files", "encoding=\"utf-8\"", "CS-UTF8"),
            "gates/gates.py": ("GateResult", "GateRunner", "GatePipeline"),
            "gates/models.py": ("class GateResult", "exit_code", "class Violation"),
            "gates/registry.py": ("class GateRegistry", "duplicate validator key", "GateLoadError"),
            "git/git_snapshot.py": ("collect_changed_files", "staged", "untracked"),
            "task/state_machine.py": ("transition_blockers", "task review", "completed"),
            "gates/tdd_evidence.py": ("validate_tdd_evidence", "tdd.jsonl", "redExitCode"),
            "gates/test_intent.py": ("validate_test_intent", "assert " + "True", "test_intent_review"),
            "gates/validate_coding_standards.py": ("validate_coding_standards", "collect_changed_files", "--validate"),
        }

        for file_name, markers in required_markers.items():
            template_text = (
                ROOT / "template" / ".cowork-flow" / "scripts" / "common" / Path(file_name)
            ).read_text(encoding="utf-8")

            for marker in markers:
                self.assertIn(marker, template_text)

    def test_local_bootstrap_files_match_template_when_present(self) -> None:
        local_root = ROOT / ".cowork-flow"
        if not local_root.exists():
            self.skipTest("local bootstrap .cowork-flow is not checked in")

        mirrored_files = (
            Path("workflow.md"),
            Path("spec/runtime/contract-registry.json"),
            Path("spec/references/definition-of-done.md"),
            Path("spec/contracts/workflow-state-templates.md"),
            Path("scripts/common/gates/tdd_evidence.py"),
        )

        for relative_path in mirrored_files:
            local_text = (local_root / relative_path).read_text(encoding="utf-8")
            template_text = (
                ROOT / "template" / ".cowork-flow" / relative_path
            ).read_text(encoding="utf-8")
            self.assertEqual(template_text, local_text, str(relative_path))

    def test_runtime_rule_metadata_is_synced_to_zcode_scaffold(self) -> None:
        template_spec = ROOT / "template" / ".cowork-flow" / "spec"
        zcode_spec = (
            ROOT
            / "template"
            / ".zcode"
            / "scaffold"
            / ".cowork-flow"
            / "spec"
        )
        for relative_path in (
            Path("runtime") / "rules.json",
            Path("schemas") / "rules.schema.json",
        ):
            template_data = json.loads(
                (template_spec / relative_path).read_text(encoding="utf-8")
            )
            zcode_data = json.loads(
                (zcode_spec / relative_path).read_text(encoding="utf-8")
            )
            self.assertEqual(template_data, zcode_data, str(relative_path))

    def test_tdd_internal_protocol_preserves_evidence_contract(self) -> None:
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
        tdd_text = (
            ROOT
            / "template"
            / ".cowork-flow"
            / "spec"
            / "protocols"
            / "tdd.md"
        ).read_text(encoding="utf-8")
        for marker in required_markers:
            self.assertIn(marker, tdd_text)

    def test_review_protocol_and_agent_require_test_intent_review(self) -> None:
        required_markers = (
            "test intent",
            "shallow tests",
            "test_intent_review",
        )
        for path in (
            ROOT / "template" / ".cowork-flow" / "spec" / "protocols" / "review.md",
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
        self.assertIn("internalProtocols", text)
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
        doctor = ROOT / "template" / ".cowork-flow" / "scripts" / "commands" / "doctor.py"
        text = doctor.read_text(encoding="utf-8")
        # Verify doctor.py contains the expected safety checks
        self.assertIn("REQUIRED_ROUTER_SNIPPETS", text)
        self.assertIn("cowork_runtime_context_id", text)
        self.assertIn("template/skills/cowork-flow/SKILL.md", text)
        self.assertIn("template/.codex/agents/cowork-research.toml", text)
        self.assertIn("template/.codex/agents/cowork-implement.toml", text)
        self.assertIn("template/.codex/agents/cowork-check.toml", text)

    def test_writing_plans_routes_to_fixed_agents(self) -> None:
        text = (ROOT / "template" / "skills" / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
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

    def test_zcode_scaffold_workflow_matches_template_workflow(self) -> None:
        template_workflow = (
            ROOT / "template" / ".cowork-flow" / "workflow.md"
        ).read_text(encoding="utf-8")
        scaffold_workflow = (
            ROOT / "template" / ".zcode" / "scaffold" / ".cowork-flow" / "workflow.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(template_workflow, scaffold_workflow)

    def test_workflow_documents_parallel_operations(self) -> None:
        for path in (
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
        text = (ROOT / "template" / "skills" / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
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
