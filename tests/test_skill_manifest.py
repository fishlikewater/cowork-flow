from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class SkillManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.module = importlib.import_module("infra.skill_manifest")

    @classmethod
    def tearDownClass(cls) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        sys.modules.pop("infra.skill_manifest", None)

    def _write_skill(
        self,
        root: Path,
        skill: str,
        *,
        command_name: str = "demo-command",
        aliases: object = None,
        script: object = "scripts/action.py",
        schema_version: object = 1,
        commands: object = None,
        script_content: str = "print('ok')\n",
    ) -> Path:
        skill_dir = root / skill
        skill_dir.mkdir(parents=True)
        if commands is None:
            commands = [
                {
                    "name": command_name,
                    "aliases": ["demo_alias"] if aliases is None else aliases,
                    "script": script,
                }
            ]
        manifest = {
            "schemaVersion": schema_version,
            "skill": skill,
            "commands": commands,
        }
        manifest_path = skill_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        if isinstance(script, str) and script and not Path(script).is_absolute():
            script_path = skill_dir / script
            try:
                script_path.resolve().relative_to(skill_dir.resolve())
            except ValueError:
                pass
            else:
                script_path.parent.mkdir(parents=True, exist_ok=True)
                script_path.write_text(script_content, encoding="utf-8")
        return manifest_path

    def _load_from(self, *roots: Path):
        with patch.object(self.module, "skill_roots", return_value=roots):
            return self.module.load_skill_manifests(Path("/unused"))

    def _commands_from(
        self,
        *roots: Path,
        reserved_names: tuple[str, ...] = (),
    ):
        with patch.object(self.module, "skill_roots", return_value=roots):
            return self.module.skill_command_scripts(
                Path("/unused"),
                reserved_names=reserved_names,
            )

    def test_commands_and_aliases_resolve_through_shared_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir) / "skills"
            self._write_skill(skills, "demo")

            commands = self._commands_from(skills)

        self.assertEqual({"demo-command", "demo_alias"}, set(commands))
        self.assertEqual(commands["demo-command"], commands["demo_alias"])

    def test_action_diagnostics_command_is_loaded_as_advisory_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir) / "skills"
            manifest_path = self._write_skill(skills, "demo")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["actions"] = [
                {
                    "id": "demo-action",
                    "label": "Demo action",
                    "lifecycleCheck": "demo_gate",
                    "mutatesState": True,
                    "command": "./.cowork-flow/run task next <task-dir> --run",
                    "diagnosticsCommand": "./.cowork-flow/run demo-check <task-dir> --json",
                }
            ]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(self.module, "skill_roots", return_value=(skills,)):
                owner = self.module.action_metadata(Path("/unused"), "demo-action")

        self.assertIsNotNone(owner)
        self.assertEqual(
            "./.cowork-flow/run demo-check <task-dir> --json",
            owner.diagnostics_command,
        )

    def test_schema_version_is_required_and_supported(self) -> None:
        for schema_version in (None, 2, "1", True):
            with self.subTest(schema_version=schema_version):
                with tempfile.TemporaryDirectory() as temp_dir:
                    skills = Path(temp_dir) / "skills"
                    self._write_skill(
                        skills,
                        "demo",
                        schema_version=schema_version,
                    )
                    with self.assertRaisesRegex(
                        self.module.SkillManifestError,
                        "schemaVersion",
                    ):
                        self._load_from(skills)

    def test_manifest_skill_must_match_its_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir) / "skills"
            manifest_path = self._write_skill(skills, "directory-name")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["skill"] = "different-name"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                self.module.SkillManifestError,
                "directory",
            ):
                self._load_from(skills)

    def test_context_fields_reject_invalid_list_values(self) -> None:
        invalid_rules = (
            {"contexts": "check", "devTypes": ["backend"]},
            {"contexts": ["check", 1], "devTypes": ["backend"]},
            {"contexts": ["check"], "devTypes": "backend"},
            {"contexts": ["check"], "pathPatterns": ["**/*.py", None]},
        )
        for context_rule in invalid_rules:
            with self.subTest(context_rule=context_rule):
                with tempfile.TemporaryDirectory() as temp_dir:
                    skills = Path(temp_dir) / "skills"
                    manifest_path = self._write_skill(skills, "demo")
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["context"] = [context_rule]
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    with self.assertRaisesRegex(
                        self.module.SkillManifestError,
                        "context",
                    ):
                        self._load_from(skills)

    def test_commands_must_be_a_list_of_objects(self) -> None:
        for commands in ({}, ["not-an-object"]):
            with self.subTest(commands=commands):
                with tempfile.TemporaryDirectory() as temp_dir:
                    skills = Path(temp_dir) / "skills"
                    self._write_skill(skills, "demo", commands=commands)
                    with self.assertRaises(self.module.SkillManifestError):
                        self._load_from(skills)

    def test_manifest_rejects_unknown_fields_at_every_schema_level(self) -> None:
        cases = (
            ("manifest", None),
            ("action", "actions"),
            ("context", "context"),
            ("command", "commands"),
        )
        for label, section in cases:
            with self.subTest(section=label):
                with tempfile.TemporaryDirectory() as temp_dir:
                    skills = Path(temp_dir) / "skills"
                    manifest_path = self._write_skill(skills, "demo")
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if section == "actions":
                        manifest[section] = [
                            {
                                "id": "demo-action",
                                "label": "Demo action",
                                "unexpected": True,
                            }
                        ]
                    elif section == "context":
                        manifest[section] = [
                            {
                                "contexts": ["check"],
                                "devTypes": ["*"],
                                "unexpected": True,
                            }
                        ]
                    elif section == "commands":
                        manifest[section][0]["unexpected"] = True
                    else:
                        manifest["commandz"] = manifest.pop("commands")
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                    with self.assertRaisesRegex(
                        self.module.SkillManifestError,
                        "unexpected.*field",
                    ):
                        self._load_from(skills)

    def test_manifest_requires_at_least_one_owned_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir) / "skills"
            manifest_path = self._write_skill(skills, "demo")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("commands")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                self.module.SkillManifestError,
                "at least one",
            ):
                self._load_from(skills)

    def test_command_aliases_must_be_unique_nonempty_strings(self) -> None:
        for aliases in ("alias", [""], ["same", "same"], ["demo-command"]):
            with self.subTest(aliases=aliases):
                with tempfile.TemporaryDirectory() as temp_dir:
                    skills = Path(temp_dir) / "skills"
                    self._write_skill(skills, "demo", aliases=aliases)
                    with self.assertRaisesRegex(
                        self.module.SkillManifestError,
                        "alias",
                    ):
                        self._load_from(skills)

    def test_command_script_must_exist_inside_skill_directory(self) -> None:
        cases = ("scripts/missing.py", "../escape.py", "/tmp/absolute.py")
        for script in cases:
            with self.subTest(script=script):
                with tempfile.TemporaryDirectory() as temp_dir:
                    skills = Path(temp_dir) / "skills"
                    self._write_skill(skills, "demo", script=script)
                    candidate = skills / "demo" / "scripts" / "missing.py"
                    candidate.unlink(missing_ok=True)
                    with self.assertRaisesRegex(
                        self.module.SkillManifestError,
                        "script",
                    ):
                        self._load_from(skills)

    def test_command_name_or_alias_conflict_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir) / "skills"
            self._write_skill(skills, "first", command_name="shared", aliases=[])
            self._write_skill(
                skills,
                "second",
                command_name="other",
                aliases=["shared"],
            )

            with self.assertRaisesRegex(
                self.module.SkillManifestError,
                "multiple owners",
            ):
                self._load_from(skills)

    def test_command_name_cannot_shadow_reserved_runtime_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir) / "skills"
            self._write_skill(
                skills,
                "demo",
                command_name="task",
                aliases=[],
            )

            with self.assertRaisesRegex(
                self.module.SkillManifestError,
                "reserved",
            ):
                self._commands_from(skills, reserved_names=("task", "python"))

    def test_command_metadata_replica_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            self._write_skill(first, "demo", aliases=["first-alias"])
            self._write_skill(second, "demo", aliases=["second-alias"])

            with self.assertRaisesRegex(
                self.module.SkillManifestError,
                "conflicting Skill manifest replicas",
            ):
                self._load_from(first, second)

    def test_command_script_replica_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            self._write_skill(first, "demo", script_content="print('first')\n")
            self._write_skill(second, "demo", script_content="print('second')\n")

            with self.assertRaisesRegex(
                self.module.SkillManifestError,
                "conflicting Skill manifest replicas",
            ):
                self._load_from(first, second)


if __name__ == "__main__":
    unittest.main()
