"""Pattern engine contract tests."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from flow.store import TaskView as StoreTaskView
from patterns.base import Action, BlockView, Pattern, StepKind, TaskContext, TaskView
from patterns.generic import Generic
from patterns.registry import create_registry


def make_task(
    status: str = "planning",
    pattern: str = "generic",
    *,
    id: str = "task-1",
    level: str = "L1",
    children: list[str] | None = None,
    meta: dict | None = None,
) -> TaskView:
    return TaskView(
        id=id,
        artifact_dir=f"06-12-{id}",
        title=id,
        status=status,
        pattern=pattern,
        priority="P2",
        creator="codex",
        assignee="codex",
        level=level,
        parent_id=None,
        children=children or [],
        meta=meta or {},
        block_reason=None,
    )


def test_flow_store_reuses_pattern_task_view_contract():
    assert StoreTaskView is TaskView


def test_action_and_context_contracts_are_explicit():
    action = Action(
        kind=StepKind.REVIEW,
        description="Reviewing",
        task_id="parent",
        children=["child-a"],
    )
    block = BlockView(
        id=1,
        task_id="task-1",
        reason="Need decision",
        blocked_at="2026-06-12T00:00:00+00:00",
        decision=None,
        decided_by=None,
        resolved_at=None,
    )
    ctx = TaskContext(task=make_task("blocked"), children=[], active_block=block)

    assert action.kind.value == "review"
    assert action.children == ["child-a"]
    assert ctx.active_block.reason == "Need decision"


def test_base_pattern_transition_helpers():
    class ReviewOnly(Pattern):
        name = "review_only"
        valid_transitions = {"in_progress": {"review"}}

        def validate(self, ctx: TaskContext) -> list[str]:
            return []

        def next_action(self, ctx: TaskContext) -> Action | None:
            return None

    pattern = ReviewOnly()
    ctx = TaskContext(task=make_task("in_progress"), children=[], active_block=None)

    assert pattern.transition_allowed("in_progress", "review")
    assert not pattern.transition_allowed("in_progress", "completed")
    assert pattern.can_transition(ctx, "review")
    assert not pattern.can_transition(ctx, "completed")


def test_base_pattern_conditional_transition_override_still_uses_whitelist():
    class ReadyForReview(Pattern):
        name = "ready_for_review"
        valid_transitions = {"in_progress": {"review"}}

        def validate(self, ctx: TaskContext) -> list[str]:
            return []

        def next_action(self, ctx: TaskContext) -> Action | None:
            return None

        def can_transition(self, ctx: TaskContext, to_status: str) -> bool:
            return super().can_transition(ctx, to_status) and bool(
                ctx.task.meta.get("ready_for_review")
            )

    pattern = ReadyForReview()
    blocked_ctx = TaskContext(task=make_task("in_progress"), children=[], active_block=None)
    ready_ctx = TaskContext(
        task=make_task("in_progress"),
        children=[],
        active_block=None,
    )
    ready_ctx.task.meta["ready_for_review"] = True

    assert pattern.transition_allowed("in_progress", "review")
    assert not pattern.can_transition(blocked_ctx, "review")
    assert pattern.can_transition(ready_ctx, "review")
    assert not pattern.can_transition(ready_ctx, "completed")


def test_generic_pattern_matches_phase1_plus_blocked_flow():
    pattern = Generic()
    allowed = {
        "planning": {"in_progress"},
        "in_progress": {"blocked", "review"},
        "blocked": {"in_progress"},
        "review": {"completed"},
        "completed": {"archived"},
    }

    assert pattern.name == "generic"
    assert pattern.valid_transitions == allowed
    for source, targets in allowed.items():
        ctx = TaskContext(task=make_task(source), children=[], active_block=None)
        for target in targets:
            assert pattern.can_transition(ctx, target)

    assert not pattern.can_transition(
        TaskContext(task=make_task("planning"), children=[], active_block=None),
        "completed",
    )


def test_generic_has_no_extra_validation_or_next_action():
    pattern = Generic()
    ctx = TaskContext(task=make_task("in_progress"), children=[], active_block=None)

    assert pattern.validate(ctx) == []
    assert pattern.next_action(ctx) is None


def test_registry_resolves_unknown_pattern_to_generic():
    registry = create_registry()

    assert isinstance(registry.get("generic"), Generic)
    assert isinstance(registry.resolve(make_task(pattern="unknown")), Generic)
    assert isinstance(registry.resolve(make_task(pattern="generic")), Generic)


def test_pattern_runtime_files_are_synced_to_template():
    paths = (
        "patterns/__init__.py",
        "patterns/base.py",
        "patterns/generic.py",
        "patterns/registry.py",
        "flow/store.py",
    )

    for rel in paths:
        root_file = ROOT / ".cowork-flow" / "scripts" / rel
        template_file = ROOT / "template" / ".cowork-flow" / "scripts" / rel
        assert root_file.read_text(encoding="utf-8") == template_file.read_text(
            encoding="utf-8"
        )

def test_pattern_spec_files_are_synced_to_template():
    paths = (
        "patterns/index.md",
    )

    for rel in paths:
        root_file = ROOT / ".cowork-flow" / "spec" / "reference" / rel
        template_file = ROOT / "template" / ".cowork-flow" / "spec" / "reference" / rel
        assert root_file.read_text(encoding="utf-8") == template_file.read_text(
            encoding="utf-8"
        )

def test_pattern_specs_are_registered_in_contract_registry():
    root_registry = json.loads(
        (ROOT / ".cowork-flow" / "spec" / "registry.json").read_text(
            encoding="utf-8"
        )
    )
    template_registry = json.loads(
        (ROOT / "template" / ".cowork-flow" / "spec" / "registry.json").read_text(
            encoding="utf-8"
        )
    )

    assert root_registry == template_registry
    contracts = {contract["id"]: contract for contract in root_registry["contracts"]}
    contract = contracts["FLOW_PATTERN_CONTRACTS_V1"]

    assert contract["path"] == ".cowork-flow/spec/reference/patterns/index.md"
    digest = " ".join(contract["digest"])
    assert "TaskContext" in digest
    assert "before changing task lifecycle transitions" in contract["readWhen"]
