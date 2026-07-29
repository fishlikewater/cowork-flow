#!/usr/bin/env python3
"""Structured cowork-flow distribution and runtime health checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _add_runtime_scripts_path() -> None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".cowork-flow" / "scripts"
        if candidate.is_dir():
            value = str(candidate)
            if value not in sys.path:
                sys.path.insert(0, value)
            return


_add_runtime_scripts_path()

from adapters.host.host_manifest import (
    HostManifestError,
    detect_installed_platforms,
    load_host_manifest,
    validate_host_assets,
)
from infra.paths import get_repo_root
from infra.skill_manifest import SkillManifestError, action_owners, load_skill_manifests


def _same_file(left: Path, right: Path, errors: list[str]) -> None:
    if not left.is_file():
        errors.append(f"missing template asset: {left}")
        return
    if not right.is_file():
        errors.append(f"missing installed asset: {right}")
        return
    if left.read_bytes() != right.read_bytes():
        errors.append(f"distribution drift: {left} != {right}")


def _distribution_root(repo_root: Path) -> Path:
    template = repo_root / "template"
    if (
        (template / ".cowork-flow/spec/runtime/host-assets.json").is_file()
        and (template / ".cowork-flow/scripts/kernel/workflow_route.py").is_file()
        and (template / "skills").is_dir()
    ):
        return template
    return repo_root


def _host_errors(repo_root: Path) -> list[str]:
    distribution_root = _distribution_root(repo_root)
    if distribution_root != repo_root:
        return validate_host_assets(distribution_root)
    try:
        platform_ids = detect_installed_platforms(distribution_root)
    except HostManifestError as error:
        return [str(error)]
    if not platform_ids:
        return ["no installed host platform detected"]
    return validate_host_assets(distribution_root, platform_ids=platform_ids)


def _distribution_files(root: Path) -> tuple[Path, ...]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]
    return tuple(sorted(files))


def check_distribution(repo_root: Path) -> list[str]:
    errors: list[str] = []
    template = repo_root / "template"
    if _distribution_root(repo_root) == repo_root:
        return errors
    runtime_root = template / ".cowork-flow" / "scripts"
    for source in _distribution_files(runtime_root):
        relative = source.relative_to(template)
        _same_file(source, repo_root / relative, errors)
    for relative in (Path(".cowork-flow/run"), Path(".cowork-flow/run.cmd")):
        source = template / relative
        if source.is_file():
            _same_file(source, repo_root / relative, errors)
    try:
        host_manifest = load_host_manifest(template)
        installed_platforms = detect_installed_platforms(repo_root)
    except HostManifestError as error:
        errors.append(str(error))
        return errors
    skill_targets = {
        host_manifest.platform(platform_id).skill_target
        for platform_id in installed_platforms
        if host_manifest.platform(platform_id).skill_target
    }
    skill_root = template / "skills"
    for source in _distribution_files(skill_root):
        relative = source.relative_to(skill_root)
        for skill_target in sorted(skill_targets):
            _same_file(source, repo_root / skill_target / relative, errors)
    return errors


def check_runtime(repo_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        load_skill_manifests(repo_root)
        action_owners(repo_root)
    except SkillManifestError as error:
        errors.append(f"Skill manifest error: {error}")

    distribution_root = _distribution_root(repo_root)
    kernel_path = distribution_root / ".cowork-flow/scripts/kernel/workflow_route.py"
    if not kernel_path.is_file():
        errors.append(f"missing kernel route: {kernel_path}")
    else:
        source = kernel_path.read_text(encoding="utf-8")
        for forbidden in ("activatedSkill", "recommendedSkill", "./.cowork-flow/run", "label"):
            if forbidden in source:
                errors.append(f"kernel contains delivery concern: {forbidden}")

    workflow_template = distribution_root / ".cowork-flow/spec/contracts/workflow-state-templates.md"
    if not workflow_template.is_file():
        errors.append(f"missing workflow-state contract: {workflow_template}")
    else:
        text = workflow_template.read_text(encoding="utf-8")
        for status in ("no_task", "delegated_subtask", "planning", "in_progress", "review", "completed"):
            if f"[workflow-state:{status}]" not in text:
                errors.append(f"workflow-state contract missing status: {status}")
    return errors


def _run_checks(repo_root: Path) -> int:
    errors = []
    errors.extend(_host_errors(repo_root))
    errors.extend(check_runtime(repo_root))
    errors.extend(check_distribution(repo_root))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("runtime health checks passed")
    return 0


def _run_host_checks(repo_root: Path) -> int:
    errors = _host_errors(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("host adapter checks passed")
    return 0


def _run_runtime_checks(repo_root: Path) -> int:
    errors = check_runtime(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("runtime safety checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cowork-flow diagnostics")
    parser.add_argument("--all", action="store_true", help="Run all structured health checks")
    parser.add_argument("--subagent-safety", action="store_true", help="Run runtime safety checks")
    parser.add_argument("--host-adapters", action="store_true", help="Run host asset checks")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = get_repo_root()
    if args.all:
        return _run_checks(repo_root)
    if args.host_adapters:
        return _run_host_checks(repo_root)
    if args.subagent_safety:
        return _run_runtime_checks(repo_root)
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
