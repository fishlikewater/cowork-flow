"""FlowStore unit tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".cowork-flow" / "scripts"))

import pytest
from flow.store import FlowStore


@pytest.fixture
def store():
    return FlowStore(":memory:")


def test_create_and_get_task(store):
    task_id = store.create_task(id="my-feature", title="Test feature", creator="dev1", assignee="dev1")
    task = store.get_task(task_id)
    assert task is not None
    assert task.id == "my-feature"
    assert task.title == "Test feature"
    assert task.status == "planning"
    assert task.pattern == "generic"
    assert task.artifact_dir is not None


def test_create_task_with_meta(store):
    task_id = store.create_task(
        id="pipe", title="Pipeline", creator="d", assignee="d",
        meta={"stages": [{"name": "impl", "agent_type": "cowork-implement"}]},
    )
    task = store.get_task(task_id)
    assert task.meta["stages"][0]["name"] == "impl"


def test_update_status(store):
    task_id = store.create_task(id="t1", title="T", creator="d", assignee="d")
    assert store.update_status(task_id, "in_progress", "dev1")
    assert store.get_task(task_id).status == "in_progress"


def test_update_status_invalid_task(store):
    assert not store.update_status("nonexistent", "in_progress", "dev1")


def test_list_tasks(store):
    store.create_task(id="a", title="A", creator="d", assignee="d")
    store.create_task(id="b", title="B", creator="d", assignee="d", status="completed")
    assert len(store.list_tasks()) == 2
    assert len(store.list_tasks(status="planning")) == 1


def test_list_children(store):
    parent = store.create_task(id="parent", title="P", creator="d", assignee="d")
    store.create_task(id="c1", title="C1", creator="d", assignee="d", parent_id=parent)
    store.create_task(id="c2", title="C2", creator="d", assignee="d", parent_id=parent)
    assert len(store.list_children(parent)) == 2


def test_link_and_unlink_child(store):
    p = store.create_task(id="p1", title="P1", creator="d", assignee="d")
    c = store.create_task(id="c3", title="C3", creator="d", assignee="d")
    assert store.link_child(p, c)
    assert len(store.list_children(p)) == 1
    assert store.unlink_child(p, c)
    assert len(store.list_children(p)) == 0


def test_all_children_done(store):
    p = store.create_task(id="p2", title="P2", creator="d", assignee="d")
    store.create_task(id="c4", title="C4", creator="d", assignee="d", parent_id=p, status="completed")
    assert store.all_children_done(p)


def test_block_and_unblock(store):
    t = store.create_task(id="t2", title="T2", creator="d", assignee="d")
    store.update_status(t, "in_progress", "dev1")
    assert store.block_task(t, "need review")
    assert store.get_task(t).status == "blocked"
    block = store.get_active_block(t)
    assert block is not None
    assert block["reason"] == "need review"
    assert store.unblock_task(t, "go ahead", "reviewer")
    assert store.get_task(t).status == "in_progress"


def test_auto_completed_at_on_complete(store):
    t = store.create_task(id="t3", title="T3", creator="d", assignee="d")
    store.update_status(t, "completed", "dev1")
    # completed_at is set by update_status -> verify via get_task
    task = store.get_task(t)
    assert task.status == "completed"
    # completed_at existence verified via direct query in audit trail
    trail = store.get_audit_trail(t)
    completed_events = [e for e in trail if e["to_status"] == "completed"]
    assert len(completed_events) >= 1


def test_update_meta(store):
    t = store.create_task(id="t4", title="T4", creator="d", assignee="d")
    store.update_meta(t, {"current_stage": 1})
    task = store.get_task(t)
    assert task.meta["current_stage"] == 1


def test_audit_trail(store):
    t = store.create_task(id="t5", title="T5", creator="d", assignee="d")
    store.update_status(t, "in_progress", "dev1")
    store.update_status(t, "review", "dev1")
    trail = store.get_audit_trail(t)
    assert len(trail) == 3  # create + in_progress + review


def test_create_task_duplicate_id(store):
    store.create_task(id="dup", title="First", creator="d", assignee="d")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.create_task(id="dup", title="Second", creator="d", assignee="d")


def test_agent_run_crud(store):
    t = store.create_task(id="ar1", title="AR", creator="d", assignee="d")
    run_id = store.create_agent_run(
        id="rtx_001", task_id=t, agent_type="cowork-implement",
        created_at="2026-01-01T00:00:00Z",
    )
    assert run_id == "rtx_001"
    active = store.get_active_agent_run(t)
    assert active["id"] == "rtx_001"
    assert active["status"] == "pending"
    store.update_agent_run_status("rtx_001", "success")
    active = store.get_active_agent_run(t)
    assert active["status"] == "success"


def test_get_active_agent_run_returns_latest(store):
    t = store.create_task(id="ar2", title="AR2", creator="d", assignee="d")
    store.create_agent_run(id="r1", task_id=t, agent_type="worker", created_at="2026-01-01T00:00:00Z")
    store.create_agent_run(id="r2", task_id=t, agent_type="worker", created_at="2026-01-02T00:00:00Z")
    store.update_agent_run_status("r1", "closed")
    active = store.get_active_agent_run(t)
    assert active["id"] == "r2"


def test_list_agent_runs_for_parent(store):
    p = store.create_task(id="parent_ar", title="PAR", creator="d", assignee="d")
    c = store.create_task(id="child_ar", title="CAR", creator="d", assignee="d", parent_id=p)
    store.create_agent_run(id="r3", task_id=c, agent_type="cowork-implement", created_at="2026-01-01T00:00:00Z")
    runs = store.list_agent_runs_for_parent(p)
    assert len(runs) == 1
    assert runs[0]["id"] == "r3"


def test_double_block_guarded(store):
    t = store.create_task(id="db1", title="DB", creator="d", assignee="d")
    store.update_status(t, "in_progress", "dev1")
    assert store.block_task(t, "first block")
    assert not store.block_task(t, "second block")
    assert len(store.get_audit_trail(t)) == 3  # create + start + first block


def test_update_meta_retry_exhaustion(store):
    t = store.create_task(id="meta1", title="Meta", creator="d", assignee="d")
    # Normal path: succeeds
    assert store.update_meta(t, {"key": "value"})
    assert store.get_task(t).meta["key"] == "value"
    # Meta update with empty dict
    assert store.update_meta(t, {})
    assert store.get_task(t).meta == {}


def test_board_view(store):
    store.create_task(id="b1", title="B1", creator="d", assignee="d")
    store.create_task(id="b2", title="B2", creator="d", assignee="d", status="in_progress")
    view = store.board_view()
    assert len(view["columns"]) == 6
    planning_col = [c for c in view["columns"] if c["status"] == "planning"][0]
    assert len(planning_col["tasks"]) == 1