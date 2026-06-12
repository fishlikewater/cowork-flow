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
from patterns.fan_out import FanOut
from patterns.generic import Generic
from patterns.human_loop import HumanLoop
from patterns.pipeline import Pipeline
from patterns.registry import create_registry


def make_task(
    status: str = "planning",
    pattern: str = "generic",
    *,
    id: str = "task-1",
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
        parent_id=None,
        children=children or [],
        meta=meta or {},
        block_reason=None,
    )


def test_flow_store_reuses_pattern_task_view_contract():
    assert StoreTaskView is TaskView


def test_action_and_context_contracts_are_explicit():
    action = Action(
        kind=StepKind.WAIT_CHILDREN,
        description="Waiting",
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

    assert action.kind.value == "wait_children"
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


def test_fan_out_requires_generic_children_and_waits_for_pending_children():
    pattern = FanOut()
    parent = make_task("in_progress", "fan_out", children=["child-a", "child-b"])
    child_a = make_task("completed", id="child-a")
    child_b = make_task("in_progress", id="child-b")
    ctx = TaskContext(task=parent, children=[child_a, child_b], active_block=None)

    assert pattern.validate(TaskContext(task=parent, children=[], active_block=None)) == [
        "Fan-out task must have child tasks"
    ]
    assert pattern.validate(
        TaskContext(
            task=parent,
            children=[make_task("planning", "pipeline", id="child-c")],
            active_block=None,
        )
    ) == ["Child 'child-c' pattern must be 'generic'"]

    action = pattern.next_action(ctx)
    assert action is not None
    assert action.kind is StepKind.WAIT_CHILDREN
    assert action.children == ["child-b"]
    assert not pattern.can_transition(ctx, "review")


def test_fan_out_allows_review_and_reports_complete_when_children_done():
    pattern = FanOut()
    parent = make_task("in_progress", "fan_out", children=["child-a"])
    child = make_task("archived", id="child-a")
    ctx = TaskContext(task=parent, children=[child], active_block=None)

    assert pattern.validate(ctx) == []
    assert pattern.can_transition(ctx, "review")
    action = pattern.next_action(ctx)
    assert action is not None
    assert action.kind is StepKind.COMPLETE
    assert action.task_id == "task-1"


def test_pipeline_requires_stages_and_blocks_early_completion():
    pattern = Pipeline()
    invalid_ctx = TaskContext(
        task=make_task("review", "pipeline", meta={}),
        children=[],
        active_block=None,
    )
    ready_ctx = TaskContext(
        task=make_task(
            "review",
            "pipeline",
            meta={"stages": [{"name": "implement"}], "current_stage": 1},
        ),
        children=[],
        active_block=None,
    )
    blocked_ctx = TaskContext(
        task=make_task(
            "review",
            "pipeline",
            meta={"stages": [{"name": "implement"}], "current_stage": 0},
        ),
        children=[],
        active_block=None,
    )

    assert pattern.validate(invalid_ctx) == ["Pipeline task must define stages"]
    assert not pattern.can_transition(blocked_ctx, "completed")
    assert pattern.can_transition(ready_ctx, "completed")
    assert pattern.can_transition(blocked_ctx, "in_progress")


def test_pipeline_next_action_mentions_current_stage():
    pattern = Pipeline()
    ctx = TaskContext(
        task=make_task(
            "in_progress",
            "pipeline",
            meta={
                "stages": [{"name": "implement"}, {"name": "check"}],
                "current_stage": 1,
            },
        ),
        children=[],
        active_block=None,
    )

    action = pattern.next_action(ctx)
    assert action is not None
    assert action.kind is StepKind.REVIEW
    assert "check" in action.description
    assert "2/2" in action.description


def test_human_loop_requires_decision_points_and_decision_for_unblock():
    pattern = HumanLoop()
    invalid_ctx = TaskContext(
        task=make_task("blocked", "human_loop", meta={}),
        children=[],
        active_block=None,
    )
    undecided_ctx = TaskContext(
        task=make_task(
            "blocked",
            "human_loop",
            meta={"decision_points": [{"question": "Choose"}]},
        ),
        children=[],
        active_block=BlockView(
            id=1,
            task_id="task-1",
            reason="Choose",
            blocked_at="2026-06-12T00:00:00+00:00",
            decision=None,
            decided_by=None,
            resolved_at=None,
        ),
    )
    decided_ctx = TaskContext(
        task=undecided_ctx.task,
        children=[],
        active_block=BlockView(
            id=1,
            task_id="task-1",
            reason="Choose",
            blocked_at="2026-06-12T00:00:00+00:00",
            decision="Use A",
            decided_by="user",
            resolved_at=None,
        ),
    )

    assert pattern.validate(invalid_ctx) == [
        "Human-loop task must define decision_points"
    ]
    assert not pattern.can_transition(undecided_ctx, "in_progress")
    assert pattern.can_transition(decided_ctx, "in_progress")
    action = pattern.next_action(undecided_ctx)
    assert action is not None
    assert action.kind is StepKind.HUMAN_DECISION


def test_registry_resolves_and_selects_patterns_from_task_shape():
    registry = create_registry()

    assert isinstance(registry.get("generic"), Generic)
    assert isinstance(registry.resolve(make_task(pattern="unknown")), Generic)
    assert isinstance(registry.select(make_task(children=["child-a"])), FanOut)
    assert isinstance(registry.select(make_task(meta={"stages": []})), Pipeline)
    assert isinstance(
        registry.select(make_task(meta={"decision_points": []})),
        HumanLoop,
    )


def test_pattern_runtime_files_are_synced_to_template():
    paths = (
        "patterns/__init__.py",
        "patterns/base.py",
        "patterns/fan_out.py",
        "patterns/generic.py",
        "patterns/human_loop.py",
        "patterns/pipeline.py",
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
        "patterns/fan-out.md",
        "patterns/pipeline.md",
        "patterns/human-loop.md",
    )

    for rel in paths:
        root_file = ROOT / ".cowork-flow" / "spec" / rel
        template_file = ROOT / "template" / ".cowork-flow" / "spec" / rel
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

    assert contract["path"] == ".cowork-flow/spec/patterns/index.md"
    digest = " ".join(contract["digest"])
    assert "TaskContext" in digest
    assert "fan_out" in digest
    assert "pipeline" in digest
    assert "human_loop" in digest
    assert "before changing task lifecycle transitions" in contract["readWhen"]
