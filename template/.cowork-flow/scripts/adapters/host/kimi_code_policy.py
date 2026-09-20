#!/usr/bin/env python3
"""kimi-code host policy: the Kimi Code behaviors of the workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only what Kimi
Code changes — the bare-text stdout contract (Kimi Code appends the
UserPromptSubmit hook's stdout to the prompt context, where the JSON-envelope
hosts return hookSpecificOutput) and the probe-based session-start detection:
Kimi Code registers UserPromptSubmit alone, because SessionStart and
PostToolUse are observe-only events whose stdout is discarded.
"""

from __future__ import annotations

from adapters.host.workflow_state_hook import HostPolicy


POLICY = HostPolicy(
    host="kimi-code",
    session_start_event=None,  # probe the session state file instead
    emit_text=True,
)
