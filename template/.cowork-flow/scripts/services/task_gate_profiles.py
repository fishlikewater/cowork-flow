"""Task gate profiles: which start gate holds a task, and the facts it reads.

A task created today carries `meta.gateProfile = "strict"`; a task without the
marker keeps the historical gate (legacy), so nothing that already exists is
retroactively re-gated.

The strict gate exists because the old one only checked that the `## 验收标准`
heading was present. An anchor with an empty acceptance section passed, the
acceptance/evidence gates then found no AC rows to check, and the whole chain
silently did nothing.
"""

from __future__ import annotations

import re

from services.fact_view import ACCEPTANCE_RE

GATE_PROFILE_STRICT = "strict"
GATE_PROFILE_LEGACY = "legacy"

LIGHT_TASK_TYPE = "tiny"

ACCEPTANCE_HEADING = "验收标准"

_HEADING_RE = re.compile(r"^##\s*(.+?)\s*$")
_LIST_ITEM_RE = re.compile(r"^\s*[-*]\s")


def resolve_gate_profile(task_data: dict) -> str:
    """The gate a task is held to; an unmarked task is legacy."""
    meta = task_data.get("meta") if isinstance(task_data, dict) else None
    marker = meta.get("gateProfile") if isinstance(meta, dict) else None
    if isinstance(marker, str) and marker.strip().lower() == GATE_PROFILE_STRICT:
        return GATE_PROFILE_STRICT
    return GATE_PROFILE_LEGACY


def declares_light_profile(task_data: dict) -> bool:
    """Whether the metadata carries the `tiny` task type.

    Field semantics only, and deliberately loose: existing data writes
    `taskType` or `task_type`, at the top level or under `meta`. This is the
    single reading of those fields; `is_light_task` adds the gate-profile
    half of the definition, and the start preflight keeps using this half
    alone so pre-strict tiny tasks behave exactly as they did.
    """
    if not isinstance(task_data, dict):
        return False
    meta = task_data.get("meta")
    candidates = [
        task_data.get("taskType"),
        task_data.get("task_type"),
        meta.get("taskType") if isinstance(meta, dict) else None,
        meta.get("task_type") if isinstance(meta, dict) else None,
    ]
    return any(
        str(candidate).lower() == LIGHT_TASK_TYPE for candidate in candidates
    )


def is_light_task(task_data: dict) -> bool:
    """Whether a strict task opted into the light profile at creation.

    A light task still runs under the strict profile: it skips the review
    receipt, the acceptance-evidence and the dev_type gates, and nothing
    else. The spec-check, file-scope and acceptance-row gates stay in force,
    so this is a narrower reading list rather than an exemption channel.
    """
    if resolve_gate_profile(task_data) != GATE_PROFILE_STRICT:
        return False
    return declares_light_profile(task_data)


def acceptance_section_lines(anchor_text: str) -> list[str]:
    """Raw lines under `## 验收标准`, up to the next heading."""
    lines: list[str] = []
    inside = False
    for raw in anchor_text.splitlines():
        heading = _HEADING_RE.match(raw.strip())
        if heading:
            inside = heading.group(1) == ACCEPTANCE_HEADING
            continue
        if inside:
            lines.append(raw)
    return lines


def acceptance_row_blockers(anchor_text: str) -> list[str]:
    """Why the acceptance section cannot start a strict task.

    Only facts: whether any AC row parses, whether ids repeat, and which list
    rows in the section are not AC rows. A non-list line is prose and ignored.
    """
    ids: list[str] = []
    malformed: list[str] = []
    for raw in acceptance_section_lines(anchor_text):
        if not raw.strip():
            continue
        match = ACCEPTANCE_RE.match(raw)
        if match:
            ids.append(match.group(2))
            continue
        if _LIST_ITEM_RE.match(raw):
            malformed.append(raw.strip()[:80])
    blockers: list[str] = []
    if not ids:
        blockers.append(
            "decision-anchor.md declares no acceptance criterion; a strict "
            "task needs at least one `- [ ] AC-xxx: ...` row"
        )
    duplicates = sorted({ac_id for ac_id in ids if ids.count(ac_id) > 1})
    if duplicates:
        blockers.append(
            f"duplicate acceptance criterion id(s): {', '.join(duplicates)}"
        )
    if malformed:
        blockers.append(
            "acceptance section has list row(s) that are not AC rows: "
            + "; ".join(malformed[:3])
        )
    return blockers


def dev_type_blocker(task_data: dict) -> list[str]:
    """A strict task must declare its dev type.

    `dev_type` is what `task specs` uses to dispatch the dev-type spec
    pointers and the narrow `devTypes` skill rules; a strict task that leaves
    it empty is created into a silently shorter reading list. A light task
    declares no dev type by design, so it is exempt.
    """
    if is_light_task(task_data):
        return []
    dev_type = task_data.get("dev_type") if isinstance(task_data, dict) else None
    if isinstance(dev_type, str) and dev_type.strip():
        return []
    return [
        "strict task declares no dev_type; pass --type <dev-type> at creation "
        "(or backfill it on a planning task)"
    ]
