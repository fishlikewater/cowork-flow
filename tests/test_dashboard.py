from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
DASHBOARD = SCRIPTS / "dashboard" / "server.py"
ROOT_STATIC = ROOT / ".cowork-flow" / "scripts" / "dashboard" / "static"
TEMPLATE_STATIC = ROOT / "template" / ".cowork-flow" / "scripts" / "dashboard" / "static"


class DashboardTest(unittest.TestCase):
    def _cleanup_template_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "common.paths",
            "common.time_utils",
            "flow.store",
            "flow",
            "patterns.base",
            "patterns",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _create_flow_task(
        self,
        root: Path,
        task_id: str,
        artifact_dir: str,
        *,
        status: str = "planning",
        parent_id: str | None = None,
    ) -> None:
        (root / ".cowork-flow" / "tasks" / artifact_dir).mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(SCRIPTS))
        try:
            paths = importlib.import_module("common.paths")
            flow_store = importlib.import_module("flow.store")
            with flow_store.FlowStore(str(paths.get_db_path(root))) as store:
                store.create_task(
                    id=task_id,
                    artifact_dir=artifact_dir,
                    title=f"Task {task_id}",
                    status=status,
                    pattern="fan_out" if parent_id is None else "generic",
                    creator="test",
                    assignee="test",
                    parent_id=parent_id,
                )
        finally:
            self._cleanup_template_imports()

    def _start_dashboard(self, root: Path) -> tuple[subprocess.Popen, str]:
        process = subprocess.Popen(
            [sys.executable, str(DASHBOARD), "--host", "127.0.0.1", "--port", "0"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert process.stdout is not None
        line = process.stdout.readline().strip()
        if not line:
            stderr = process.stderr.read() if process.stderr else ""
            process.terminate()
            self.fail(f"dashboard did not start: {stderr}")
        return process, line.rsplit(" ", 1)[-1]

    def _stop_dashboard(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def _get_json(self, base_url: str, path: str) -> dict:
        with urllib.request.urlopen(f"{base_url}{path}", timeout=5) as response:
            self.assertEqual("application/json", response.headers.get_content_type())
            return json.loads(response.read().decode("utf-8"))

    def test_dashboard_static_assets_stay_in_sync(self) -> None:
        for asset in ("index.html", "app.js", "style.css"):
            self.assertEqual(
                (ROOT_STATIC / asset).read_text(encoding="utf-8"),
                (TEMPLATE_STATIC / asset).read_text(encoding="utf-8"),
                f"{asset} should match root/template dashboard assets",
            )

    def test_dashboard_shell_is_simplified_chinese(self) -> None:
        html = (ROOT_STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn('lang="zh-CN"', html)
        for text in ("cowork-flow 看板", "只读工作流控制台", "搜索任务", "显示归档", "刷新"):
            self.assertIn(text, html)

    def test_dashboard_filters_emphasize_active_tasks(self) -> None:
        script = (ROOT_STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('const DEFAULT_VISIBLE_STATUSES = ["planning", "in_progress", "review", "blocked", "completed"];', script)
        self.assertIn('showArchived.checked', script)
        self.assertIn('task.status === "archived"', script)
        self.assertIn("archivedTasks", script)
        for label in ("规划中", "执行中", "检查中", "已阻塞", "已完成", "已归档"):
            self.assertIn(label, script)

    def test_dashboard_uses_readable_pattern_labels(self) -> None:
        script = (ROOT_STATIC / "app.js").read_text(encoding="utf-8")
        for label in ("通用流程", "扇出协作", "流水线", "人工确认"):
            self.assertIn(label, script)

    def test_dashboard_detail_renders_inspection_sections(self) -> None:
        script = (ROOT_STATIC / "app.js").read_text(encoding="utf-8")
        for name in ("renderBasics", "renderAuditTrail", "renderChildren", "renderAgentRuns", "renderActiveBlock"):
            self.assertIn(f"function {name}", script)
        for label in ("基础信息", "审计记录", "子任务", "代理运行", "阻塞状态", "暂无阻塞", "创建"):
            self.assertIn(label, script)

    def test_run_dispatcher_registers_dashboard_command(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            run = importlib.import_module("run")
            self.assertEqual("dashboard/server.py", run.COMMAND_SCRIPTS["dashboard"])
        finally:
            sys.modules.pop("run", None)
            self._cleanup_template_imports()

    def test_dashboard_serves_read_only_board_and_task_apis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            self._create_flow_task(root, "parent", "05-29-parent")
            self._create_flow_task(root, "child-a", "05-29-child-a", parent_id="parent")

            process, base_url = self._start_dashboard(root)
            try:
                board = self._get_json(base_url, "/api/board")
                planning = [column for column in board["columns"] if column["status"] == "planning"][0]
                self.assertEqual(["parent", "child-a"], [task["id"] for task in planning["tasks"]])

                detail = self._get_json(base_url, "/api/task/parent")
                self.assertEqual("parent", detail["task"]["id"])
                self.assertEqual(["child-a"], [child["id"] for child in detail["children"]])
                self.assertGreaterEqual(len(detail["audit"]), 1)

                children = self._get_json(base_url, "/api/task/parent/children")
                self.assertEqual(["child-a"], [child["id"] for child in children["children"]])

                patterns = self._get_json(base_url, "/api/patterns")
                self.assertIn("fan_out", [item["name"] for item in patterns["patterns"]])

                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(
                        urllib.request.Request(f"{base_url}/api/board", method="POST"),
                        timeout=5,
                    )
                self.assertEqual(405, error.exception.code)
            finally:
                self._stop_dashboard(process)


if __name__ == "__main__":
    unittest.main()
