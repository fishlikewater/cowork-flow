#!/usr/bin/env python3
"""Task context JSONL codec."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class ContextValidationIssue:
    context_file: str
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class ContextJsonlEntry:
    context_file: str
    line: int
    data: object
    text: str
    line_ending: str


@dataclass(frozen=True)
class ContextJsonlReadResult:
    context_file: str
    exists: bool
    entry_count: int
    entries: tuple[ContextJsonlEntry, ...]
    issues: tuple[ContextValidationIssue, ...]


def write_jsonl(path: Path, entries: list[dict]) -> None:
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def iter_jsonl_lines(path: Path) -> Iterator[tuple[int, str]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            yield line_number, line.rstrip("\n")


def read_context_jsonl_entries(context_file: Path) -> ContextJsonlReadResult:
    """Parse a context JSONL file into reusable line-level facts."""
    context_file = Path(context_file)
    if not context_file.is_file():
        return ContextJsonlReadResult(
            context_file=context_file.name,
            exists=False,
            entry_count=0,
            entries=(),
            issues=(),
        )

    entries: list[ContextJsonlEntry] = []
    issues: list[ContextValidationIssue] = []
    entry_count = 0
    try:
        lines: list[tuple[int, str, str]] = []
        with context_file.open("r", encoding="utf-8", newline="") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                text = raw_line.rstrip("\r\n")
                line_ending = raw_line[len(text):]
                lines.append((line_number, text, line_ending))
    except (OSError, UnicodeDecodeError) as error:
        return ContextJsonlReadResult(
            context_file=context_file.name,
            exists=True,
            entry_count=0,
            entries=(),
            issues=(
                ContextValidationIssue(
                    context_file=context_file.name,
                    line=0,
                    code="read_error",
                    message=f"Cannot read {context_file.name}: {error}",
                ),
            ),
        )

    for line_number, line, line_ending in lines:
        if not line.strip():
            continue
        entry_count += 1
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            issues.append(
                ContextValidationIssue(
                    context_file=context_file.name,
                    line=line_number,
                    code="invalid_json",
                    message="Invalid JSON",
                )
            )
            continue
        entries.append(
            ContextJsonlEntry(
                context_file=context_file.name,
                line=line_number,
                data=data,
                text=line,
                line_ending=line_ending,
            )
        )

    return ContextJsonlReadResult(
        context_file=context_file.name,
        exists=True,
        entry_count=entry_count,
        entries=tuple(entries),
        issues=tuple(issues),
    )
