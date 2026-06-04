"""Classify cowork-flow hook entries before workflow-state injection."""

from __future__ import annotations

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


def extract_prompt(hook_input: dict) -> str:
    values: list[str] = []
    for key in PROMPT_KEYS:
        value = hook_input.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    return "\n".join(values)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def classify_entry(hook_input: dict) -> Classification:
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
