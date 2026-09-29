#!/usr/bin/env python3
"""Host policy contract shared by the workflow hook and the host adapters.

The policy object is the only thing host adapters contribute: the renderer in
workflow_state_hook.py stays neutral and checks callables instead of branching
on host names. Keeping the type here (rather than next to the renderer) lets
each host module import it without importing the renderer back.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Per-host contract fact (context-injection.md transport
# table): a host carries its own line in its policy module,
# unknown hosts fall back to the default below.
DEFAULT_DIGEST_POLICY = (
    "policy: repeat this short digest every hook; "
    "read full spec files only before listed actions."
)

Preamble = Callable[[Path], tuple[str, ...]]
RebindHints = Callable[[Path], str]
EssentialFilesWarning = Callable[[Path], str]
PostToolUse = Callable[[Path, dict[str, Any]], tuple[str, int]]
# Renders the user-visible one-line message a host shows next to an
# injection (root, hook_input, event_name) -> text.
SystemMessage = Callable[[Path, dict[str, Any], str], str]


@dataclass(eq=False)
class HostPolicy:
    """Per-host deltas consumed by the neutral renderer.

    Fields left at their defaults mean "no such behavior for this host".
    Identity semantics (`eq=False`) are deliberate: policies are module-level
    singletons, never compared by value.
    """

    host: str
    digest_policy: str = DEFAULT_DIGEST_POLICY
    digest_warning_silent: bool = False
    session_start_event: str | None = "SessionStart"
    preamble: Preamble | None = None
    rebind_hints: RebindHints | None = None
    essential_files_warning: EssentialFilesWarning | None = None
    fallback_for_unbound: bool = False
    post_tool_use: PostToolUse | None = None
    system_message: SystemMessage | None = None
    emit_indent: bool = False
    emit_not_initialized: bool = False
    emit_text: bool = False


def default_policy(host: str = "generic") -> HostPolicy:
    return HostPolicy(host=host)
