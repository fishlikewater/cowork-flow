#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared assertion helpers for integration tests."""

from __future__ import annotations

import json
from pathlib import Path


def assert_task_created(task_dir: Path, msg: str = ""):
    """Assert task directory exists with prd.md."""
    assert task_dir.is_dir(), f"Task dir not created: {task_dir} {msg}"
    prd = task_dir / "prd.md"
    assert prd.is_file(), f"prd.md missing in {task_dir} {msg}"
    assert prd.stat().st_size > 0, f"prd.md empty in {task_dir} {msg}"


def assert_change_created(change_dir: Path, msg: str = ""):
    """Assert change directory exists with change.yaml."""
    assert change_dir.is_dir(), f"Change dir not created: {change_dir} {msg}"
    cy = change_dir / "change.yaml"
    assert cy.is_file(), f"change.yaml missing in {change_dir} {msg}"


def read_task_json(task_dir: Path) -> dict:
    """Read task.json from a task directory."""
    path = task_dir / "task.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_change_yaml(change_dir: Path) -> dict:
    """Read flat metadata from change.yaml."""
    path = change_dir / "change.yaml"
    if not path.is_file():
        return {}
    meta: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return meta
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta
