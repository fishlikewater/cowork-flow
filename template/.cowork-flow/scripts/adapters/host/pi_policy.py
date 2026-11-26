#!/usr/bin/env python3
"""Pi host policy: the Pi-specific behaviors of the workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only the Pi
transport specifics — the runtime preamble that tells the model which
extension is injecting and how this host names its session.
"""

from __future__ import annotations

from pathlib import Path

from adapters.host.policy_base import HostPolicy

PI_PREAMBLE = (
    (
        "<pi-runtime>\n"
        "injection: before_agent_start via the cowork-flow Pi extension\n"
        "session: PI_SESSION_ID identifies this session to the CLI\n"
        "</pi-runtime>"
    ),
)


def preamble(root: Path) -> tuple[str, ...]:
    return PI_PREAMBLE


POLICY = HostPolicy(
    host="pi",
    preamble=preamble,
    # The extension is machine-level and loads in every Pi project. A session
    # outside a cowork-flow project still gets the fixed not_initialized body;
    # the extension injects it directly because there is no project inject.py
    # to call there.
    emit_not_initialized=True,
)
