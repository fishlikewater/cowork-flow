from __future__ import annotations

import importlib
import itertools
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SCRIPTS = TEMPLATE / ".cowork-flow" / "scripts"
REMOVED_ENTRY_SKILLS = (
    "using-cowork-flow",
    "start",
    "before-dev",
    "continue",
    "finish-work",
    "batch-mode",
    "break-loop",
    "decision-review",
    "doubt-review",
    "meta",
    "python-design",
    "review",
    "runtime-diagnostics",
    "spec-maintenance",
    "tdd",
    "writing-plans",
)
EXPECTED_SKILLS = {
    "adversarial-review",
    "agent-dispatch",
    "batch-execution",
    "brainstorming",
    "cowork-flow",
    "cowork-flow-maintenance",
    "decision-audit",
    "failure-analysis",
    "game-design",
    "party-mode",
    "python-runtime-design",
    "runtime-health",
    "spec-sync",
    "task-planning",
    "task-review",
    "test-first",
}
WORKFLOW_STATUSES = (
    "no_task",
    "planning",
    "in_progress",
    "review",
    "completed",
    "delegated_subtask",
)
USER_INTENTS = (
    "question",
    "clarify",
    "plan",
    "implement",
    "archive",
    "review",
    "doubt_review",
    "debug",
    "discuss",
    "batch",
)
EXECUTION_CONTEXTS = ("main", "delegated")


def template_skill_ids() -> set[str]:
    return {
        path.parent.name
        for path in (TEMPLATE / "skills").glob("*/SKILL.md")
    }


class SkillRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "commands.task_navigation",
            "commands",
            "common.core",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _navigation(self):
        return importlib.import_module("commands.task_navigation")

    def test_skill_directory_set_is_filesystem_authority(self) -> None:
        self.assertEqual(EXPECTED_SKILLS, template_skill_ids())
        for skill_id in REMOVED_ENTRY_SKILLS:
            with self.subTest(skill_id=skill_id):
                self.assertFalse((TEMPLATE / "skills" / skill_id).exists())
        self.assertFalse(
            (TEMPLATE / ".cowork-flow/spec/runtime/skill-registry.json").exists()
        )
        self.assertFalse(
            (TEMPLATE / ".cowork-flow/spec/schemas/skill-registry.schema.json").exists()
        )

    def test_state_intent_context_matrix_has_one_action_skill(self) -> None:
        navigation = self._navigation()

        for status, intent, context in itertools.product(
            WORKFLOW_STATUSES,
            USER_INTENTS,
            EXECUTION_CONTEXTS,
        ):
            with self.subTest(status=status, intent=intent, context=context):
                route = navigation.route_request(
                    status=status,
                    intent=intent,
                    context=context,
                    blockers=(),
                    active_target=status != "planning",
                )
                self.assertEqual(
                    {
                        "status",
                        "allowedOperations",
                        "requiredArtifacts",
                        "recommendedSkill",
                        "blockers",
                        "nextAction",
                        "activatedSkill",
                        "actionCommand",
                        "mutatesState",
                        "runtimeGate",
                        "action",
                    },
                    set(route),
                )
                self.assertEqual(route["nextAction"], route["action"]["id"])
                self.assertEqual(route["activatedSkill"], route["action"]["activatedSkill"])
                self.assertEqual(route["actionCommand"], route["action"]["command"])
                self.assertEqual(route["mutatesState"], route["action"]["mutatesState"])
                self.assertEqual(route["runtimeGate"], route["action"]["runtimeGate"])
                if route["recommendedSkill"] is not None:
                    self.assertEqual(route["recommendedSkill"], route["activatedSkill"])
                    self.assertIn(route["recommendedSkill"], EXPECTED_SKILLS)

    def test_read_only_question_never_loads_implementation_skills(self) -> None:
        navigation = self._navigation()

        for status, context in itertools.product(
            WORKFLOW_STATUSES,
            EXECUTION_CONTEXTS,
        ):
            with self.subTest(status=status, context=context):
                route = navigation.route_request(
                    status=status,
                    intent="question",
                    context=context,
                    blockers=(),
                    active_target=False,
                )
                self.assertNotIn("internalProtocols", route)
                self.assertIsNone(route["recommendedSkill"])
                self.assertIn("answer_questions", route["allowedOperations"])

    def test_delegated_context_cannot_mutate_main_lifecycle(self) -> None:
        navigation = self._navigation()
        forbidden = {"create_task", "start_task", "complete_task", "archive_task"}

        for status in WORKFLOW_STATUSES:
            route = navigation.route_request(
                status=status,
                intent="implement",
                context="delegated",
                blockers=(),
                active_target=True,
            )
            self.assertTrue(
                forbidden.isdisjoint(route["allowedOperations"]),
                (status, route),
            )
            if status == "delegated_subtask":
                self.assertIn("execute_delegated_work", route["allowedOperations"])

    def test_implementation_intent_requires_active_implementation_state(self) -> None:
        navigation = self._navigation()

        for status in ("no_task", "completed"):
            route = navigation.route_request(
                status=status,
                intent="implement",
                context="main",
                blockers=(),
                active_target=True,
            )
            self.assertIsNone(route["recommendedSkill"])
            self.assertIn(
                f"intent implement is not allowed while status is {status}",
                route["blockers"],
            )

    def test_cowork_flow_skill_owns_the_single_read_only_fallback(self) -> None:
        path = TEMPLATE / "skills" / "cowork-flow" / "SKILL.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")

        self.assertEqual(
            1,
            text.count("./.cowork-flow/run task next --json"),
        )
        self.assertNotIn("deprecated alias", text.lower())
        self.assertNotIn("Registry", text)
        for marker in (
            "<workflow-state>",
            "question",
            "clarify",
            "plan",
            "implement",
            "review",
            "doubt_review",
            "debug",
            "discuss",
            "batch",
            "allowedOperations",
            "recommendedSkill",
            "Runtime Gates carry hard enforcement",
        ):
            self.assertIn(marker, text)

    def test_root_and_template_navigation_runtime_match_when_present(self) -> None:
        relative_paths = (
            Path("scripts/commands/task_navigation.py"),
            Path("scripts/commands/task_parser.py"),
        )
        missing_paths = [
            str(relative_path)
            for relative_path in relative_paths
            if not (ROOT / ".cowork-flow" / relative_path).is_file()
        ]
        if missing_paths:
            self.skipTest(
                "local bootstrap .cowork-flow script files are absent: "
                + ", ".join(missing_paths)
            )

        for relative_path in relative_paths:
            root_path = ROOT / ".cowork-flow" / relative_path
            template_path = TEMPLATE / ".cowork-flow" / relative_path
            self.assertEqual(
                template_path.read_text(encoding="utf-8"),
                root_path.read_text(encoding="utf-8"),
                str(relative_path),
            )


if __name__ == "__main__":
    unittest.main()
