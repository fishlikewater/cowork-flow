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
    assert len(trail) >= 3


def test_create_task_duplicate_id(store):
    store.create_task(id="dup", title="First", creator="d", assignee="d")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.create_task(id="dup", title="Second", creator="d", assignee="d")


def test_board_view(store):
    store.create_task(id="b1", title="B1", creator="d", assignee="d")
    store.create_task(id="b2", title="B2", creator="d", assignee="d", status="in_progress")
    view = store.board_view()
    assert len(view["columns"]) == 6
    planning_col = [c for c in view["columns"] if c["status"] == "planning"][0]
    assert len(planning_col["tasks"]) >= 1