#!/usr/bin/env python3
"""Template-driven plan skeleton generation."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from infra.paths import DIR_WORKFLOW


PLAN_TEMPLATE_PATH = f"{DIR_WORKFLOW}/templates/plan-template.md"
PLAN_DIRECTORY = f"{DIR_WORKFLOW}/plans"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
H1_RE = re.compile(r"^#(?!#)\s+(.+?)\s*$")


class PlanScaffoldError(RuntimeError):
    """Raised when a plan skeleton cannot be generated."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


class PlanScaffoldService:
    """Create a plan file from the installed, localized plan template."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def create(
        self,
        title: str,
        slug: str,
        *,
        force: bool = False,
        date_prefix: str | None = None,
    ) -> Path:
        normalized_title = title.strip()
        normalized_slug = slug.strip()
        if not normalized_title:
            raise PlanScaffoldError(
                "PLAN-NEW-TITLE-001",
                self.repo_root,
                "plan title is required",
            )
        if not SLUG_RE.match(normalized_slug):
            raise PlanScaffoldError(
                "PLAN-NEW-SLUG-001",
                self.repo_root,
                "plan slug must contain lowercase ASCII letters, digits, and hyphens",
            )

        template = self.repo_root / PLAN_TEMPLATE_PATH
        if not template.is_file():
            raise PlanScaffoldError(
                "PLAN-NEW-TEMPLATE-001",
                template,
                "installed plan template is missing; run `cwf project sync .`",
            )

        plans_dir = self.repo_root / PLAN_DIRECTORY
        day = date_prefix or datetime.now().strftime("%Y-%m-%d")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise PlanScaffoldError(
                "PLAN-NEW-DATE-001",
                plans_dir,
                "plan date must use YYYY-MM-DD",
            )
        plan_path = plans_dir / f"{day}-{normalized_slug}.md"
        if plan_path.exists() and not force:
            raise PlanScaffoldError(
                "PLAN-NEW-EXISTS-001",
                plan_path,
                "plan already exists; pass --force to overwrite",
            )

        try:
            text = template.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise PlanScaffoldError(
                "PLAN-NEW-TEMPLATE-002",
                template,
                "installed plan template cannot be read as UTF-8",
            ) from error

        rendered = self._render_title(text, normalized_title, template)
        try:
            plans_dir.mkdir(parents=True, exist_ok=True)
            with plan_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
        except OSError as error:
            raise PlanScaffoldError(
                "PLAN-NEW-WRITE-001",
                plan_path,
                "plan file could not be written",
            ) from error
        return plan_path

    @staticmethod
    def _render_title(text: str, title: str, template: Path) -> str:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            match = H1_RE.match(line.strip())
            if match is None:
                continue
            heading = match.group(1)
            if "<功能>" in heading:
                if title.endswith("实施计划"):
                    lines[index] = f"# {title}"
                else:
                    lines[index] = f"# {heading.replace('<功能>', title)}"
                return "\n".join(lines) + "\n"
            if "<Feature>" in heading:
                if title.endswith("Implementation Plan"):
                    lines[index] = f"# {title}"
                else:
                    lines[index] = f"# {heading.replace('<Feature>', title)}"
                return "\n".join(lines) + "\n"
            raise PlanScaffoldError(
                "PLAN-NEW-TITLE-002",
                template,
                "plan template title is missing the <功能>/<Feature> placeholder",
            )
        raise PlanScaffoldError(
            "PLAN-NEW-TITLE-003",
            template,
            "plan template has no top-level title",
        )
