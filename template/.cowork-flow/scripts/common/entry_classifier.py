"""Classify cowork-flow hook entries before workflow-state injection.

Dual-channel classifier:
  Channel 1 (structured): Read adapter.yaml entrySignals declarations from
    hook_input, then map signal values to EntryKind.
  Channel 2 (legacy fallback): Keyword text heuristics from prompt text.
    Enabled during transition window; controlled by config.yaml
    ``entry.legacy_text_fallback.enabled`` (default false).

Structured signals take priority. If both channels produce a result, the
structured signal wins. If structured signal is absent and fallback is
disabled, the result is UNKNOWN (fail-closed).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class EntryKind:
    MAIN_SESSION = "MAIN_SESSION"
    READ_ONLY = "READ_ONLY"
    COMMAND_ONLY = "COMMAND_ONLY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Classification:
    entry_kind: str
    confidence: float
    source: str


# Legacy keyword lists — preserved during compat window.
# Removed in P3-B when spec language is unified and fallback is permanently off.
PROMPT_KEYS = ("prompt", "user_prompt", "userPrompt", "message", "input")

TASK_TERMS = (
    "task:",
    "topic:",
    "focus:",
    "任务：",
    "任务:",
    "主题：",
    "目标：",
    "审视",
    "讨论",
    "review",
    "inspect",
)

READ_ONLY_TERMS = (
    "explain",
    "what does",
    "what is",
    "why does",
    "为什么",
    "原因",
    "解释",
    "说明",
    "read-only",
    "inspect only",
    "analysis only",
    "只看",
    "只读",
    "分析一下",
)

COMMAND_ONLY_TERMS = (
    "git status",
    "git diff",
    "npm run",
    ".cowork-flow/run",
    ".cowork-flow\\run.cmd",
)

MAIN_SESSION_TERMS = (
    "main session",
    "main agent",
    "not a subagent",
    "not a sub-agent",
    "run full cowork-flow start",
    "run full project start",
    "继续",
    "实现",
    "提交",
    "归档",
    "修复",
    "主会话",
    "主 agent",
    "主代理",
    "不是子代理",
    "不是子任务",
    "start task",
    "resume",
    "implement",
    "commit",
    "archive",
    "fix",
)


# ---------------------------------------------------------------------------
# Structured signal extraction
# ---------------------------------------------------------------------------

def _read_config_bool(key: str, default: bool = True) -> bool:
    """Read a boolean from environment variables (used as a lightweight config
    override during the compat window).  The canonical config.yaml path
    ``entry.legacy_text_fallback.enabled`` is read by the host hook; this
    function provides a runtime override for testing and emergency control."""
    env_val = os.environ.get(key.upper())
    if env_val is None:
        return default
    return env_val.lower() in ("1", "true", "yes")


LEGACY_FALLBACK_ENABLED = False  # Mutable for testing; overridden by config/env


def _config_default_fallback_enabled() -> bool:
    try:
        from .config import get_entry_legacy_text_fallback_enabled
    except Exception:
        return LEGACY_FALLBACK_ENABLED

    try:
        return get_entry_legacy_text_fallback_enabled()
    except Exception:
        return LEGACY_FALLBACK_ENABLED


def _is_legacy_fallback_enabled() -> bool:
    """Return whether the legacy text classifier is active."""
    return _read_config_bool(
        "COWORK_FLOW_LEGACY_FALLBACK",
        default=_config_default_fallback_enabled(),
    )


def _extract_structured_signal(hook_input: dict, signal_key: str) -> str | None:
    """Extract a single structured signal from hook_input.

    Checks env var first, then hook_input keys in order.
    Returns None if the signal is not present.
    """
    # 1. Environment variable (highest priority)
    env_key = signal_key.upper()
    env_val = os.environ.get(env_key)
    if env_val and env_val.strip():
        return env_val.strip()

    # 2. Direct key in hook_input
    for key in (signal_key, signal_key.lower(), signal_key.title()):
        val = hook_input.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # 3. Nested under "entrySignals" key
    es = hook_input.get("entrySignals")
    if isinstance(es, dict):
        val = es.get(signal_key) or es.get(signal_key.lower()) or es.get(signal_key.title())
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None


def _classify_structured(hook_input: dict) -> Classification | None:
    """Attempt classification via structured signals from adapter.yaml entrySignals.

    Returns a Classification if a signal was found and mapped, otherwise None.
    """
    # session_role: main | subagent | command
    session_role = _extract_structured_signal(hook_input, "sessionRole")
    if session_role:
        if session_role in ("main", "main_session", "coordinator"):
            return Classification(EntryKind.MAIN_SESSION, 0.9, "structured_session_role")
        if session_role in ("command", "command_wrapper", "cli"):
            return Classification(EntryKind.COMMAND_ONLY, 0.9, "structured_session_role")

    # invocation_kind: interactive | command_wrapper | hook | read_only
    invocation_kind = _extract_structured_signal(hook_input, "invocationKind")
    if invocation_kind:
        if invocation_kind == "read_only":
            return Classification(EntryKind.READ_ONLY, 0.9, "structured_invocation_kind")
        if invocation_kind in ("hook", "command_wrapper", "cli"):
            return Classification(EntryKind.COMMAND_ONLY, 0.9, "structured_invocation_kind")
        if invocation_kind == "interactive":
            # Interactive without session_role → MAIN_SESSION (default for main session)
            return Classification(EntryKind.MAIN_SESSION, 0.85, "structured_invocation_kind")

    # hook_event_name (claude-code approximation)
    hook_event = _extract_structured_signal(hook_input, "hookEventName") or _extract_structured_signal(hook_input, "hook_event_name")
    if hook_event:
        if hook_event == "SessionStart":
            return Classification(EntryKind.MAIN_SESSION, 0.7, "structured_hook_event")

    # dispatch_mode (codex approximation)
    dispatch_mode = _extract_structured_signal(hook_input, "dispatchMode") or _extract_structured_signal(hook_input, "dispatch_mode")
    if dispatch_mode:
        if dispatch_mode == "sub-agent":
            return Classification(EntryKind.COMMAND_ONLY, 0.85, "structured_dispatch_mode")

    return None


# ---------------------------------------------------------------------------
# Legacy text heuristic (preserved during compat window)
# ---------------------------------------------------------------------------


def extract_prompt(hook_input: dict) -> str:
    values: list[str] = []
    for key in PROMPT_KEYS:
        value = hook_input.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    return "\n".join(values)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _legacy_text_fallback(hook_input: dict) -> Classification:
    """Legacy keyword-based classification. Preserved during compat window."""
    prompt = extract_prompt(hook_input)
    if not prompt.strip():
        return Classification(EntryKind.UNKNOWN, 0.0, "empty_prompt")

    lowered = prompt.lower()
    has_task = _contains_any(lowered, TASK_TERMS)

    if _contains_any(lowered, READ_ONLY_TERMS) and not _contains_any(lowered, MAIN_SESSION_TERMS):
        return Classification(EntryKind.READ_ONLY, 0.6, "read_only")

    if _contains_any(lowered, COMMAND_ONLY_TERMS) and not has_task:
        return Classification(EntryKind.COMMAND_ONLY, 0.6, "command_only")

    if _contains_any(lowered, MAIN_SESSION_TERMS):
        return Classification(EntryKind.MAIN_SESSION, 0.55, "main_session_heuristic")

    if has_task:
        return Classification(EntryKind.UNKNOWN, 0.35, "task_prompt_unbound")

    return Classification(EntryKind.UNKNOWN, 0.3, "unclassified")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_entry(hook_input: dict) -> Classification:
    """Classify a hook input into an EntryKind using dual-channel classification.

    Priority:
      1. Structured signals (channel 1) — if present, always used.
      2. Legacy text heuristic (channel 2) — if fallback enabled and structured
         signal absent.
      3. UNKNOWN — if neither channel produces a result.
    """
    # Channel 1: structured signal
    structured_result = _classify_structured(hook_input)
    if structured_result is not None:
        return structured_result

    # Channel 2: legacy fallback (only if enabled)
    if _is_legacy_fallback_enabled():
        return _legacy_text_fallback(hook_input)

    # Fail-closed: no signal, fallback disabled
    return Classification(EntryKind.UNKNOWN, 0.0, "no_signal_fallback_disabled")
