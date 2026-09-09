#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spec check executor: user-declared checks in spec frontmatter.

Mechanism consumes declarations, never spec prose. Each spec file may carry a
`checks:` list in its YAML frontmatter; this module parses that minimal subset,
matches declarations against changed files (directory-prefix or extension
forms only), and executes the commands with a three-state outcome:

- ``pass``       exit code 0
- ``violation``  exit code != 0
- ``unchecked``  command missing / interpreter missing / timeout — never
  reported as pass (lifecycle gates treat it as its own blocking state)

Editor-phase runs are clamped to a short timeout and only touch declarations
whose ``files`` match the edited path; slow or unfiltered commands belong to
the lifecycle phase. Output passed back to agents is normalized to one line;
full command output is only shown on an explicit ``--file`` query.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# os.name == "nt" covers Windows without importing sys: the services layer
# is kept free of CLI/process plumbing concerns by architecture tests.
IS_WINDOWS = os.name == "nt"

# Editor-phase budget: the zcode/claude PostToolUse hook runs on a ~5s hard
# budget including interpreter startup, so edit-phase commands get 2.5s —
# leaving room for Python startup plus cmd.exe wrapper overhead on slow
# machines. Slow or unfiltered commands belong to the lifecycle phase.
EDIT_PHASE_TIMEOUT = 2.5
DEFAULT_TIMEOUT = 30.0
MAX_TIMEOUT = 120.0
MAX_FIRST_LINE_CHARS = 200

# Machine-owned spec subtrees; user-declared checks never scan these.
EXCLUDED_SPEC_SUBDIRS = ("contracts", "runtime", "schemas")

SCHEMA_VERSION = 1


class SpecCheckError(Exception):
    """Raised for structural failures that callers must surface."""


@dataclass(frozen=True)
class CheckDecl:
    """One user-declared check from a spec frontmatter block."""

    cmd: str
    files: tuple[str, ...] = ()
    timeout: float = DEFAULT_TIMEOUT
    when: str = "both"
    cmd_win: str | None = None


@dataclass(frozen=True)
class SpecDeclarations:
    spec: str
    decls: tuple[CheckDecl, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass
class CheckResult:
    spec: str
    cmd: str
    status: str  # pass | violation | unchecked
    exit_code: int | None = None
    first_violation_line: str = ""
    reason: str = ""
    output: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        payload = {
            "spec": self.spec,
            "cmd": self.cmd,
            "status": self.status,
        }
        if self.exit_code is not None:
            payload["exitCode"] = self.exit_code
        if self.first_violation_line:
            payload["firstViolationLine"] = self.first_violation_line
        if self.reason:
            payload["reason"] = self.reason
        return payload


def _strip_quotes(value: str) -> str:
    value = value.strip()
    # Only unwrap a true single-pair quoting ("src/"); a command value like
    # "python" -c "..." quotes twice and must pass through intact.
    for quote in ("\"", "'"):
        if (
            len(value) >= 2
            and value[0] == quote
            and value[-1] == quote
            and value.count(quote) == 2
        ):
            return value[1:-1].strip()
    return value


def parse_frontmatter_checks(text: str) -> tuple[list[CheckDecl], list[str]]:
    """Parse the minimal frontmatter subset this contract supports.

    Returns (declarations, errors). A missing frontmatter block or a block
    without ``checks:`` is not an error; malformed content inside a declared
    block is, so doctor can point at the offending spec.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], []
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return [], ["frontmatter block not closed"]

    decls: list[CheckDecl] = []
    errors: list[str] = []
    in_checks = False
    current: dict[str, str] | None = None

    for raw in lines[1:end]:
        stripped = raw.strip()
        if not stripped:
            continue
        if not in_checks:
            if stripped == "checks:":
                in_checks = True
            elif stripped.endswith(":") and not stripped.startswith("#"):
                # Another frontmatter key; ignore its body silently.
                in_checks = False
            continue
        if stripped.startswith("- "):
            if current is not None:
                parsed = _decl_from_pairs(current, errors)
                if parsed is not None:
                    decls.append(parsed)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None:
            errors.append(f"unexpected line outside a check item: {stripped!r}")
            in_checks = False
            continue
        if ":" not in stripped:
            errors.append(f"malformed check line: {stripped!r}")
            current = None
            in_checks = False
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        if not key:
            errors.append(f"malformed check line: {stripped!r}")
            continue
        current[key] = _strip_quotes(value)
    parsed = _decl_from_pairs(current, errors)
    if parsed is not None:
        decls.append(parsed)
    return decls, errors


def _decl_from_pairs(pairs: dict[str, str], errors: list[str]) -> CheckDecl | None:
    cmd = pairs.pop("cmd", "")
    if not cmd:
        errors.append("check item without cmd")
        return None
    when = pairs.pop("when", "both") or "both"
    if when not in {"edit", "lifecycle", "both"}:
        errors.append(f"unknown when value: {when!r}")
        when = "both"
    timeout_raw = pairs.pop("timeout", "")
    try:
        timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT
    except ValueError:
        errors.append(f"non-numeric timeout: {timeout_raw!r}")
        timeout = DEFAULT_TIMEOUT
    timeout = min(max(timeout, 0.5), MAX_TIMEOUT)
    files_raw = pairs.pop("files", "")
    files, file_errors = _parse_files(files_raw)
    errors.extend(file_errors)
    if file_errors:
        # A declaration whose files filter cannot be honored must not fall
        # back to "matches everything"; drop it and let doctor surface it.
        return None
    cmd_win = pairs.pop("cmd.win", None)
    unknown = sorted(pairs)
    if unknown:
        errors.append(f"unknown check keys ignored: {', '.join(unknown)}")
    return CheckDecl(
        cmd=cmd,
        files=files,
        timeout=timeout,
        when=when,
        cmd_win=cmd_win,
    )


def _parse_files(raw: str) -> tuple[tuple[str, ...], list[str]]:
    if not raw:
        return (), []
    errors: list[str] = []
    matched: list[str] = []
    for part in raw.split(","):
        token = _strip_quotes(part).replace("\\", "/")
        while token.startswith("./"):
            token = token[2:]
        if not token:
            continue
        if token.endswith("/**"):
            token = token[:-2]
        if token.startswith("*."):
            if "*" in token[2:] or "?" in token:
                errors.append(f"unsupported files form (use dir/ or *.ext): {token!r}")
                continue
            matched.append(token)
            continue
        if "*" in token or "?" in token or "[" in token:
            errors.append(f"unsupported files form (use dir/ or *.ext): {token!r}")
            continue
        matched.append(token if token.endswith("/") else f"{token}/")
    return tuple(matched), errors


def path_matches_decl_files(relative_path: str, decl: CheckDecl) -> bool:
    if not decl.files:
        return True
    normalized = relative_path.replace("\\", "/")
    for token in decl.files:
        if token.startswith("*."):
            if normalized.endswith(token[1:]):
                return True
        elif normalized.startswith(token):
            return True
    return False


def collect_spec_declarations(repo_root: Path) -> list[SpecDeclarations]:
    spec_dir = repo_root / ".cowork-flow" / "spec"
    if not spec_dir.is_dir():
        return []
    collected: list[SpecDeclarations] = []
    for path in sorted(spec_dir.rglob("*.md")):
        relative = path.relative_to(spec_dir).as_posix()
        parts = Path(relative).parts
        if parts and parts[0] in EXCLUDED_SPEC_SUBDIRS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            collected.append(
                SpecDeclarations(relative, (), (f"unreadable spec file: {relative}",))
            )
            continue
        decls, errors = parse_frontmatter_checks(text)
        collected.append(SpecDeclarations(relative, tuple(decls), tuple(errors)))
    return collected


def _decl_for_platform(decl: CheckDecl) -> str:
    if IS_WINDOWS and decl.cmd_win:
        return decl.cmd_win
    return decl.cmd


def _first_violation_line(output: Iterable[str]) -> str:
    for line in output:
        line = line.strip()
        if line:
            return line[:MAX_FIRST_LINE_CHARS]
    return ""


def _run_command(decl: CheckDecl, repo_root: Path) -> tuple[str, int | None, str, list[str]]:
    """Execute one declaration. Returns (status, exit_code, reason, output)."""
    command = _decl_for_platform(decl)
    tokens: list[str] = []
    if IS_WINDOWS:
        # Windows: newer runtimes refuse to spawn .cmd shims directly
        # (EINVAL), so the command goes through cmd.exe. Passing an argv list
        # makes list2cmdline escape an already-quoted command into `\"...\"`
        # — cmd then strips the outer quotes and fails to parse — so the
        # raw string runs via shell=True, exactly the way npm shims launch.
        # The entry check keeps "missing command" as unchecked instead of a
        # cmd.exe rc=1 masquerading as a violation.
        try:
            tokens = shlex.split(command, posix=False)
        except ValueError:
            tokens = []
        first_token = tokens[0].strip('"') if tokens else ""
        if not first_token or shutil.which(first_token) is None:
            return "unchecked", None, f"command not found: {first_token}", []
        argv: str | list[str] = command
        popen_kwargs: dict = {"shell": True}
    else:
        try:
            argv = shlex.split(command)
        except ValueError as error:
            return "unchecked", None, f"unparsable command: {error}", []
        if not argv:
            return "unchecked", None, "empty command", []
        resolved = shutil.which(argv[0])
        if resolved is None:
            return "unchecked", None, f"command not found: {argv[0]}", []
        popen_kwargs = {}
    try:
        completed = subprocess.run(
            argv,
            cwd=str(repo_root),
            capture_output=True,
            # Explicit UTF-8 with replacement: command output is process
            # noise (first violation line only), never allowed to crash the
            # reader thread or masquerade as a check outcome.
            encoding="utf-8",
            errors="replace",
            timeout=decl.timeout,
            check=False,
            **popen_kwargs,
        )
    except subprocess.TimeoutExpired:
        return "unchecked", None, f"timed out after {decl.timeout:g}s", []
    except OSError as error:
        # PATH-stripped or otherwise degraded environments degrade to
        # unchecked; they must never read as a passing check.
        return "unchecked", None, f"failed to launch: {error}", []

    merged = list(completed.stdout.splitlines()) + list(completed.stderr.splitlines())
    if completed.returncode == 0:
        return "pass", 0, "", []
    return "violation", completed.returncode, "", merged


def run_checks(
    repo_root: Path,
    *,
    phase: str,
    changed_files: Iterable[str] | None = None,
    file_filter: str | None = None,
) -> dict:
    """Run declared checks for one phase and return a JSON-ready report.

    phase: "edit" runs only edit-eligible declarations whose ``files`` match
    ``changed_files`` (3s clamp); "lifecycle" runs every declaration honoring
    each ``files`` scope. Parse errors are reported but never block as
    violations — they surface through doctor.
    """
    if phase not in {"edit", "lifecycle"}:
        raise SpecCheckError(f"unknown phase: {phase!r}")
    changed = [c.replace("\\", "/") for c in (changed_files or [])]
    if file_filter:
        changed = [file_filter.replace("\\", "/")]

    results: list[CheckResult] = []
    parse_errors: list[dict[str, str]] = []
    for spec_decls in collect_spec_declarations(repo_root):
        for message in spec_decls.errors:
            parse_errors.append({"spec": spec_decls.spec, "error": message})
        for decl in spec_decls.decls:
            if phase == "edit":
                if decl.when == "lifecycle":
                    continue
                if not changed:
                    continue
                if not any(
                    path_matches_decl_files(path, decl) for path in changed
                ):
                    continue
                effective = CheckDecl(
                    cmd=decl.cmd,
                    files=decl.files,
                    timeout=min(decl.timeout, EDIT_PHASE_TIMEOUT),
                    when=decl.when,
                    cmd_win=decl.cmd_win,
                )
            else:
                if decl.when == "edit":
                    continue
                effective = decl
            status, exit_code, reason, output = _run_command(effective, repo_root)
            result = CheckResult(
                spec=spec_decls.spec,
                cmd=_decl_for_platform(effective),
                status=status,
                exit_code=exit_code,
                first_violation_line=_first_violation_line(output) if output else "",
                reason=reason,
            )
            if output:
                result.output = output[:20]
            results.append(result)

    summary = {
        "pass": sum(1 for r in results if r.status == "pass"),
        "violation": sum(1 for r in results if r.status == "violation"),
        "unchecked": sum(1 for r in results if r.status == "unchecked"),
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "phase": phase,
        "changedFiles": changed,
        "results": [r.to_json() for r in results],
        "parseErrors": parse_errors,
        "summary": summary,
    }


def normalized_one_line(report: dict) -> str:
    """Single-line summary for hook injection; never multi-line output."""
    results = report.get("results") or []
    for item in results:
        if item.get("status") == "violation":
            spec = item.get("spec", "?")
            line = item.get("firstViolationLine") or item.get("reason") or ""
            return f"spec-check[{spec}] violation: {line}"
    for item in results:
        if item.get("status") == "unchecked":
            return f"spec-check[{item.get('spec', '?')}] unchecked: {item.get('reason', '')}"
    return ""


# Per-file throttle for editor-phase runs: an edit storm must not multiply
# the command cost. State lives in the workflow runtime directory because
# every hook invocation is a fresh process — in-memory maps cannot throttle
# across invocations. The slot is recorded only after a completed run: an
# executor crash must not consume the interval, so the next edit within it
# still runs its checks.
EDIT_THROTTLE_INTERVAL_SECONDS = 10.0
EDIT_THROTTLE_FILE = ".cowork-flow" / Path(".runtime") / "spec-edit-throttle.json"


def _read_throttle(root: Path) -> dict:
    try:
        data = json.loads((root / EDIT_THROTTLE_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_throttle(root: Path, file_path: str, timestamp: float) -> None:
    path = root / EDIT_THROTTLE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"file": file_path, "ts": timestamp}, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        # Throttle state is best-effort; a failed write just means the next
        # edit runs its checks again.
        pass


def run_edit_checks(
    repo_root: Path,
    file_path: str,
    *,
    throttled: bool = True,
    now: float | None = None,
) -> str:
    """Editor-phase single-line result for one changed file.

    Empty string means "nothing to report": no declaration matched, the file
    was throttled, or checks passed. Violations and unchecked degradations
    return the normalized one-line summary. Never raises for expected
    operating conditions — the editor path must not break edits.
    """
    import time

    normalized = file_path.replace("\\", "/").strip()
    if not normalized:
        return ""
    # Hosts pass absolute edit paths; declaration filters are repo-relative.
    try:
        normalized = (
            Path(normalized).resolve().relative_to(repo_root.resolve()).as_posix()
        )
    except (ValueError, OSError):
        pass
    if throttled:
        state = _read_throttle(repo_root)
        current = time.time() if now is None else now
        if (
            state.get("file") == normalized
            and isinstance(state.get("ts"), (int, float))
            and current - state["ts"] < EDIT_THROTTLE_INTERVAL_SECONDS
        ):
            return ""
    try:
        report = run_checks(repo_root, phase="edit", changed_files=[normalized])
    except Exception:
        # Executor crash (not a check failure): leave the throttle untouched
        # so a retry within the interval is not silently swallowed.
        return ""
    if throttled:
        _write_throttle(repo_root, normalized, time.time() if now is None else now)
    return normalized_one_line(report)


def summary_has(report: dict, key: str) -> bool:
    return bool((report.get("summary") or {}).get(key))
