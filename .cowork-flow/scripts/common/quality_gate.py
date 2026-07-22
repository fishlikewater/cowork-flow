#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quality gate kernel for lifecycle evidence validation.

Provides:
    GateResult                  - structured gate result with violations
    load_quality_evidence       - read quality.json from task directory
    validate_tdd_evidence       - validate testPlan, red, green per work_type
    validate_completion_evidence - validate green, standards, check evidence
    execute_red_test            - actually run red.command and verify exit code
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Gate result
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """Structured gate check result with rule violations.

    Attributes:
        ok: True when no blockers present.
        scope: Lifecycle phase that produced this result (e.g. "task_start").
        violations: Structured rule violations with rule_id/severity/fix_hint.
        errors: Legacy error messages (backward compatible).
        warnings: Legacy warning messages (backward compatible).
    """

    ok: bool
    scope: str = ""
    violations: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def blockers(self) -> list[dict]:
        """Return violations with severity == 'block'."""
        return [v for v in self.violations if v.get("severity") == "block"]

    @property
    def blocked(self) -> bool:
        """True when at least one blocker exists."""
        return len(self.blockers) > 0

    @property
    def exit_code(self) -> int:
        """1 if blocked, 0 otherwise — for sys.exit."""
        return 1 if self.blocked else 0

    def add_violation(
        self,
        rule_id: str,
        severity: str,
        message: str,
        fix_hint: str = "",
        file: str = "",
    ) -> None:
        """Add a structured rule violation."""
        self.violations.append({
            "rule_id": rule_id,
            "severity": severity,
            "message": message,
            "fix_hint": fix_hint,
            "file": file,
        })
        if severity == "block":
            self.ok = False


# ---------------------------------------------------------------------------
# Work type policy
# ---------------------------------------------------------------------------

BEHAVIOR_CHANGE = "behavior_change"
BUGFIX = "bugfix"
REFACTOR_NO_BEHAVIOR_CHANGE = "refactor_no_behavior_change"
DOCS_CHORE = "docs_chore"

TDD_REQUIRED_WORK_TYPES = frozenset({BEHAVIOR_CHANGE, BUGFIX})
VALID_WORK_TYPES = frozenset({
    BEHAVIOR_CHANGE,
    BUGFIX,
    REFACTOR_NO_BEHAVIOR_CHANGE,
    DOCS_CHORE,
})


# ---------------------------------------------------------------------------
# Evidence loading
# ---------------------------------------------------------------------------


def load_quality_evidence(task_dir: Path) -> dict:
    """Read quality.json from a task directory with explicit UTF-8 encoding.

    Returns an empty dict when the file is missing or unparseable.
    """
    quality_path = task_dir / "quality.json"
    if not quality_path.is_file():
        return {}
    try:
        return json.loads(quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# TDD evidence validation
# ---------------------------------------------------------------------------


def validate_tdd_evidence(task_dir: Path) -> GateResult:
    """Validate that TDD evidence meets the task's work_type policy.

    - behavior_change / bugfix: testPlan + failing red evidence required.
    - refactor_no_behavior_change: existing/characterization test evidence required.
    - docs_chore: TDD not required; check evidence expected later.
    - Unknown or missing work_type is treated as behavior_change (fail-closed).
    """
    evidence = load_quality_evidence(task_dir)
    errors: list[str] = []
    warnings: list[str] = []

    work_type = evidence.get("workType", BEHAVIOR_CHANGE)

    if work_type not in VALID_WORK_TYPES:
        errors.append(
            f"Unknown workType '{work_type}'. Must be one of: "
            f"{', '.join(sorted(VALID_WORK_TYPES))}"
        )
        return GateResult(ok=False, errors=errors, warnings=warnings)

    if work_type in TDD_REQUIRED_WORK_TYPES:
        _check_test_plan(evidence, work_type, errors)
        _check_red_evidence(evidence, errors)
    elif work_type == REFACTOR_NO_BEHAVIOR_CHANGE:
        _check_test_plan(evidence, work_type, errors)
    elif work_type == DOCS_CHORE:
        if not evidence.get("check"):
            warnings.append(
                "docs_chore does not require TDD,"
                " but a 'check' entry is still expected before completion."
            )

    return GateResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


def _check_test_plan(evidence: dict, work_type: str, errors: list[str]) -> None:
    test_plan = evidence.get("testPlan")
    if not isinstance(test_plan, list) or len(test_plan) == 0:
        errors.append(
            f"workType '{work_type}' requires a non-empty 'testPlan' in quality.json. "
            "Each entry must include 'acceptancePoint', 'testCommand', and 'breaksWhen'."
        )
        return
    for i, entry in enumerate(test_plan):
        if not isinstance(entry, dict):
            errors.append(f"testPlan[{i}] must be an object, got {type(entry).__name__}")
            continue
        for field in ("acceptancePoint", "testCommand", "breaksWhen"):
            if not entry.get(field):
                errors.append(f"testPlan[{i}] is missing required field '{field}'")


def _check_red_evidence(evidence: dict, errors: list[str]) -> None:
    red = evidence.get("red")
    if not isinstance(red, dict):
        errors.append(
            "TDD-required work requires a 'red' object in quality.json. "
            "Record the failing test command, non-zero exitCode, failingTests, and output excerpt."
        )
        return

    if not red.get("command"):
        errors.append(
            "red evidence is missing 'command'. Record the exact test command."
        )
    if "exitCode" not in red:
        errors.append(
            "red evidence is missing 'exitCode'. Record the actual exit code."
        )
    elif red["exitCode"] == 0:
        errors.append(
            "red evidence exitCode is 0, but the red phase requires at least one "
            "failing test. Write a failing test first, run it, and record the non-zero exit code."
        )


# ---------------------------------------------------------------------------
# Execution-backed red test verification
# ---------------------------------------------------------------------------

RED_TEST_TIMEOUT = 120  # seconds


def execute_red_test(task_dir: Path, repo_root: Path | None = None) -> GateResult:
    """Actually run the red command from quality.json and verify it fails.

    Returns ok=True only if:
    - quality.json exists and has a red.command
    - The command exits with a non-zero code
    - The actual exit code matches the claimed exit_code (if present)
    Returns ok=True with a warning when execution-based checking is disabled
    by config (quality_gate.execute_red_test != True).
    """
    from .config import _load_config

    config = _load_config(repo_root)
    if not config.get("quality_gate", {}).get("execute_red_test", False):
        return GateResult(ok=True, warnings=["execute_red_test disabled by config"])

    evidence = load_quality_evidence(task_dir)
    red = evidence.get("red")
    if not isinstance(red, dict) or not red.get("command"):
        return GateResult(ok=True, warnings=["No red.command to execute; skipping execution check"])

    command = red["command"]
    claimed_exit_code = red.get("exitCode")
    work_dir = str(task_dir)

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            timeout=RED_TEST_TIMEOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return GateResult(
            ok=False,
            errors=[
                f"Red test timed out after {RED_TEST_TIMEOUT}s: {command!r}. "
                "If the command is legitimately slow, increase quality_gate.execute_red_timeout."
            ],
        )
    except OSError as exc:
        return GateResult(
            ok=False,
            errors=[f"Failed to execute red test command {command!r}: {exc}"],
        )

    actual_exit = result.returncode
    errors: list[str] = []
    warnings: list[str] = []

    if actual_exit == 0:
        errors.append(
            f"Red test exited with 0 (expected non-zero) when run in {work_dir}: {command!r}. "
            "The test that should fail is passing — either the bug is already fixed or the test is wrong."
        )

    if claimed_exit_code is not None and actual_exit != claimed_exit_code:
        warnings.append(
            f"Red test actual exit code ({actual_exit}) differs from claimed ({claimed_exit_code}). "
            f"Command: {command!r}. Update quality.json to match reality."
        )

    return GateResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# Completion evidence validation
# ---------------------------------------------------------------------------


def validate_completion_evidence(task_dir: Path) -> GateResult:
    """Validate that completion evidence is present and passing.

    Requires (as applicable):
    - green evidence matching the red command family.
    - standards evidence with all scans passing.
    - check evidence with reviewer mode, commands, and scope review.
    """
    evidence = load_quality_evidence(task_dir)
    errors: list[str] = []
    warnings: list[str] = []

    work_type = evidence.get("workType", BEHAVIOR_CHANGE)

    if work_type in TDD_REQUIRED_WORK_TYPES:
        _check_green_evidence(evidence, errors)
        _check_green_matches_red_family(evidence, errors)
    elif work_type == REFACTOR_NO_BEHAVIOR_CHANGE:
        _check_green_evidence(evidence, errors)
    # docs_chore: no green requirement, but standards + check still apply

    _check_standards_evidence(task_dir, evidence, errors)
    _check_review_evidence(evidence, errors)

    return GateResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


def _check_green_evidence(evidence: dict, errors: list[str]) -> None:
    green = evidence.get("green")
    if not isinstance(green, dict):
        errors.append(
            "Completion requires 'green' evidence in quality.json. "
            "Record the passing test command, exitCode 0, and passingTests."
        )
        return

    if not green.get("command"):
        errors.append("green evidence is missing 'command' field.")
    if green.get("exitCode") != 0:
        errors.append(
            f"green evidence exitCode is {green.get('exitCode')}, expected 0. "
            "All tests must pass before marking the task completed."
        )


def _check_green_matches_red_family(evidence: dict, errors: list[str]) -> None:
    red = evidence.get("red", {})
    green = evidence.get("green", {})
    if not isinstance(red, dict) or not isinstance(green, dict):
        return
    red_cmd = red.get("command", "")
    green_cmd = green.get("command", "")
    if red_cmd and green_cmd and not _same_command_family(red_cmd, green_cmd):
        errors.append(
            f"green command '{green_cmd}' does not match the red command family "
            f"'{red_cmd}'. The same test command that failed in red must pass in green."
        )


def _check_standards_evidence(task_dir: Path, evidence: dict, errors: list[str]) -> None:
    """Run actual coding-standards scanners and reject on any failure.

    Does not trust the ``standards`` claim in ``quality.json`` — runs the
    scanners directly and compares with claimed results.
    """
    try:
        from .coding_standards import scan_standards
    except ImportError:
        errors.append("Cannot import coding_standards scanner.")
        return

    try:
        real = scan_standards(task_dir)
    except Exception as exc:
        errors.append(f"standards scan failed: {exc}")
        return

    for check_name in ("encodingScan", "bomScan", "whitespaceCheck", "shallowTestScan"):
        result = real.get(check_name, {})
        if not result.get("ok", False):
            violations = result.get("violations", [])
            errors.append(
                f"standards.{check_name} failed. Violations: {violations}"
            )

    # Also validate that quality.json claims match reality (warn on mismatch)
    claimed = evidence.get("standards")
    if isinstance(claimed, dict):
        for check_name in ("encodingScan", "bomScan", "whitespaceCheck", "shallowTestScan"):
            claim = claimed.get(check_name)
            real_result = real.get(check_name)
            if (
                isinstance(claim, dict)
                and isinstance(real_result, dict)
                and claim.get("ok") != real_result.get("ok")
            ):
                errors.append(
                    f"standards.{check_name} claimed ok={claim.get('ok')} "
                    f"but actual scan result is ok={real_result.get('ok')}."
                )


def _check_review_evidence(evidence: dict, errors: list[str]) -> None:
    check = evidence.get("check")
    if not isinstance(check, dict):
        errors.append(
            "Completion requires 'check' evidence in quality.json. "
            "Record reviewerMode, commands run, specSync decision, and scopeReview."
        )


# ---------------------------------------------------------------------------
# Command family comparison
# ---------------------------------------------------------------------------


def _same_command_family(red_cmd: str, green_cmd: str) -> bool:
    """Return True when green command matches the red command family.

    Two commands are the same family when their base (executable + target files)
    is identical after stripping verbosity/diagnostic flags.
    """
    return _command_base(red_cmd) == _command_base(green_cmd)


def _command_base(cmd: str) -> str:
    """Extract the base command, removing verbosity and diagnostic flags."""
    import shlex

    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()

    skip_exact = {"-q", "-v", "-vv", "-vvv", "--quiet", "--verbose", "-x", "--exitfirst"}
    skip_prefix = ("--tb=", "--color=", "--no-header", "-W")

    kept: list[str] = []
    for p in parts:
        if p in skip_exact:
            continue
        if any(p.startswith(prefix) for prefix in skip_prefix):
            continue
        kept.append(p)

    return " ".join(kept)
