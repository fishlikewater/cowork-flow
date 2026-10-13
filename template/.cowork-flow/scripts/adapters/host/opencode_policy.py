#!/usr/bin/env python3
"""opencode host policy: the OpenCode behaviors of the workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only what OpenCode
changes. The opencode plugin is a transport shim (like the zcode hook shim):
it forwards each system-transform event to inject.py and pushes stdout into
`output.system`, so the injection travels as bare text (emit_text) rather than
a JSON envelope. The transform fires on every prompt assembly, never as a
distinct session-start event, so the slim/full digest decision comes from the
session file probe (session_start_event=None), as with codex.
"""

from __future__ import annotations

from adapters.host.policy_base import HostPolicy

OPENCODE_DIGEST_POLICY = (
    "policy: repeat this short digest every plugin transform; "
    "read full spec files only before listed actions."
)


POLICY = HostPolicy(
    host="opencode",
    digest_policy=OPENCODE_DIGEST_POLICY,
    session_start_event=None,
    # The payload's cached runtime copy renders the not-initialized context
    # outside any cowork-flow project (zcode parity).
    emit_not_initialized=True,
    # stdout is the injection itself: the shim forwards it verbatim.
    emit_text=True,
)
