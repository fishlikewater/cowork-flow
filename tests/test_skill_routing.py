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
)
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
INTENT_REGISTRY_KEYS = {
    "question": None,
    "clarify": "clarify_requirement",
    "plan": "write_plan",
    "implement": "route_workflow",
    "archive": "route_workflow",
    "review": "route_workflow",
    "doubt_review": "doubt_review",
    "debug": "analyze_repeated_failure",
    "discuss": "discuss_options",
    "batch": "batch_execute_plan",
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
            "common.core.skill_registry",
            "common.core",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _navigation(self):
        return importlib.import_module("commands.task_navigation")

    def _registry(self):
        module = importlib.import_module("common.core.skill_registry")
        return module.load_skill_registry(TEMPLATE)

    def test_active_public_skill_set_is_consolidated(self) -> None:
        public_ids = set(self._registry().public_skill_ids)

        self.assertLessEqual(public_ids.__len__(), 10)
        self.assertEqual(
            {
                "batch-mode",
                "brainstorming",
                "break-loop",
                "cowork-flow",
                "doubt-review",
                "game-design",
                "party-mode",
                "review",
                "tdd",
                "writing-plans",
            },
            public_ids,
        )

    def test_state_intent_context_matrix_has_at_most_one_public_skill(self) -> None:
        navigation = self._navigation()
        registry = self._registry()

        for status, intent, context in itertools.product(
            WORKFLOW_STATUSES,
            USER_INTENTS,
            EXECUTION_CONTEXTS,
        ):
            with self.subTest(status=status, intent=intent, context=context):
                route = navigation.route_request(
                    registry,
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
                        "internalProtocols",
                        "blockers",
                    },
                    set(route),
                )
                registry_intent = INTENT_REGISTRY_KEYS[intent]
                matches = [
                    entry.id
                    for entry in registry.public_entries
                    if registry_intent in entry.intents
                    and status in entry.statuses
                ] if registry_intent is not None else []
                self.assertLessEqual(len(matches), 1)
                if route["recommendedSkill"] is not None:
                    self.assertIn(route["recommendedSkill"], matches)

    def test_read_only_question_never_loads_implementation_protocols(self) -> None:
        navigation = self._navigation()
        registry = self._registry()

        for status, context in itertools.product(
            WORKFLOW_STATUSES,
            EXECUTION_CONTEXTS,
        ):
            with self.subTest(status=status, context=context):
                route = navigation.route_request(
                    registry,
                    status=status,
                    intent="question",
                    context=context,
                    blockers=(),
                    active_target=False,
                )
                self.assertEqual([], route["internalProtocols"])
                self.assertIsNone(route["recommendedSkill"])
                self.assertIn("answer_questions", route["allowedOperations"])

    def test_delegated_context_cannot_mutate_main_lifecycle(self) -> None:
        navigation = self._navigation()
        registry = self._registry()
        forbidden = {"create_task", "start_task", "complete_task", "archive_task"}

        for status in WORKFLOW_STATUSES:
            route = navigation.route_request(
                registry,
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
        registry = self._registry()

        for status in ("no_task", "completed"):
            route = navigation.route_request(
                registry,
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

    def test_removed_entry_skills_have_no_registry_or_source_presence(self) -> None:
        registry = self._registry()

        for skill_id in REMOVED_ENTRY_SKILLS:
            with self.subTest(skill_id=skill_id):
                with self.assertRaisesRegex(
                    ValueError,
                    f"unknown Skill Registry entry: {skill_id}",
                ):
                    registry.entry(skill_id)
                self.assertFalse(
                    (TEMPLATE / "skills" / skill_id).exists(),
                    skill_id,
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
            "internalProtocols",
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
