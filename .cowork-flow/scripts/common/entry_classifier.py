"""Classify cowork-flow hook entries before workflow-state injection."""

from __future__ import annotations

from dataclasses import dataclass


class EntryKind:
    MAIN_SESSION = "MAIN_SESSION"
    DELEGATED_HARD = "DELEGATED_HARD"
    DELEGATED_SOFT = "DELEGATED_SOFT"
    READ_ONLY = "READ_ONLY"
    COMMAND_ONLY = "COMMAND_ONLY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Classification:
    entry_kind: str
    confidence: float
    source: str


PROMPT_KEYS = ("prompt", "user_prompt", "userPrompt", "message", "input")

HARD_DELEGATION_MARKERS = (
    "COWORK_DISPATCH_V1",
    "COWORK_DELEGATION_V1",
    "COWORK_DELEGATED_TASK_V1",
    "DELEGATED_HARD",
    "DELEGATED_SOFT",
    "DELEGATED_SUBTASK",
    "Active task: .cowork-flow/tasks/",
    "agent_type: worker",
    "agent_type: default",
    "agent_type: explorer",
)

DELEGATED_TERMS = (
    "delegated task",
    "delegated subtask",
    "bounded delegated",
    "subagent",
    "sub-agent",
    "reviewer",
    "explorer",
    "worker brief",
    "leaf executor",
    "spawn_agent",
    "agent_type",
    "best-effort",
    "委托任务",
    "委托 prompt",
    "子任务",
    "子线程",
)

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

BOUNDARY_TERMS = (
    "do not edit",
    "do not run",
    "do not spawn",
    "do not run start",
    "do not run resume",
    "do not run task-start",
    "do not run project start",
    "do not run the project start-session workflow",
    "return concise analysis only",
    "不要编辑",
    "不要运行",
    "不要派发",
    "不要只确认",
    "只输出",
    "不要改",
)

OUTPUT_TERMS = (
    "output:",
    "required output",
    "return in",
    "return exactly",
    "return only",
    "max ",
    "最多",
    "输出：",
    "输出:",
    "分为",
)

AGENT_DISPATCH_SIGNALS = (
    "spawn_agent(",
    'agent_type="worker"',
    "agent_type='worker'",
    'agent_type="default"',
    "agent_type='default'",
    'agent_type="explorer"',
    "agent_type='explorer'",
    "agent type: worker",
    "agent type: default",
    "agent type: explorer",
    "worker brief",
    "leaf executor",
    "best-effort",
)

READ_ONLY_TERMS = (
    "explain",
    "what does",
    "what is",
    "why does",
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
    "继续",
    "实现",
    "提交",
    "归档",
    "修复",
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

    if _contains_any(prompt, HARD_DELEGATION_MARKERS):
        return Classification(EntryKind.DELEGATED_HARD, 0.95, "hard_marker")

    lowered = prompt.lower()
    has_agent_dispatch = _contains_any(lowered, AGENT_DISPATCH_SIGNALS)
    has_task = _contains_any(lowered, TASK_TERMS)
    has_delegated_role = _contains_any(lowered, DELEGATED_TERMS)
    has_boundary = _contains_any(lowered, BOUNDARY_TERMS)
    has_output = _contains_any(lowered, OUTPUT_TERMS)

    if has_task and (has_delegated_role or has_boundary or has_agent_dispatch):
        if has_output or has_boundary or has_agent_dispatch:
            return Classification(EntryKind.DELEGATED_SOFT, 0.75, "prompt_shape")

    if _contains_any(lowered, READ_ONLY_TERMS) and not _contains_any(lowered, MAIN_SESSION_TERMS):
        return Classification(EntryKind.READ_ONLY, 0.6, "read_only")

    if _contains_any(lowered, COMMAND_ONLY_TERMS) and not has_task:
        return Classification(EntryKind.COMMAND_ONLY, 0.6, "command_only")

    if _contains_any(lowered, MAIN_SESSION_TERMS):
        return Classification(EntryKind.MAIN_SESSION, 0.55, "main_session_heuristic")

    return Classification(EntryKind.UNKNOWN, 0.3, "unclassified")


def should_use_delegated_bootstrap(entry_kind: str) -> bool:
    return entry_kind in {
        EntryKind.DELEGATED_HARD,
        EntryKind.DELEGATED_SOFT,
        EntryKind.UNKNOWN,
    }
