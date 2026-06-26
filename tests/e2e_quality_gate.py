#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end verification of quality gate lifecycle.
Runs real CLI commands, not just unit tests.
"""
import json, os, sys, io, contextlib, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / ".cowork-flow" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common.paths import get_db_path
from flow.store import FlowStore

import importlib
task_mod = importlib.import_module("task")
quality = importlib.import_module("common.quality_gate")
test_quality = importlib.import_module("common.test_quality")
coding_standards = importlib.import_module("common.coding_standards")
agent_policy = importlib.import_module("common.agent_policy")

FAIL = 0
PASS = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✅ {name}")
    else:
        FAIL += 1; print(f"  ❌ {name}  -- {detail}")

def call_cmd(func, dir_path, **kwargs):
    ns = argparse.Namespace(dir=dir_path, **kwargs)
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        # patch active task resolution...
        result = func(ns)
    return result, out.getvalue(), err.getvalue()

def write_q(task_dir, data):
    (task_dir / "quality.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")

# Convert DB artifact_dir to full path
def task_path(slug):
    with FlowStore(str(get_db_path(ROOT))) as s:
        t = s.get_task(slug)
        return ROOT / ".cowork-flow" / "tasks" / t.artifact_dir if t else None

print("=" * 60)
print("E2E QUALITY GATE VERIFICATION")
print("=" * 60)

# ============================================================================
# 1. NO quality.json → review must FAIL
# ============================================================================
print("\n--- 1. No quality.json → review FAIL ---")
d = task_path("verify-a")
if (d / "quality.json").exists():
    (d / "quality.json").unlink()
rc, _, err = call_cmd(task_mod.cmd_review, str(d))
check("review returns 1", rc == 1, f"got {rc}")
check("stderr mentions TDD evidence", "TDD evidence gate failed" in err, err[:200])

# ============================================================================
# 2. behavior_change with red exitCode=0 → review FAIL
# ============================================================================
print("\n--- 2. red exitCode=0 → review FAIL ---")
d = task_path("verify-b")
write_q(d, {
    "workType": "behavior_change",
    "testPlan": [{"acceptancePoint": "x", "testCommand": "pytest", "breaksWhen": "fails"}],
    "red": {"command": "pytest -q", "exitCode": 0}
})
rc, _, err = call_cmd(task_mod.cmd_review, str(d))
check("review returns 1", rc == 1, f"got {rc}")
check("stderr mentions exitCode is 0", "exitCode is 0" in err, err[:300])

# ============================================================================
# 3. Valid red evidence → review PASS
# ============================================================================
print("\n--- 3. Valid red evidence → review PASS ---")
d = task_path("verify-c")
write_q(d, {
    "workType": "behavior_change",
    "testPlan": [{"acceptancePoint": "x", "testCommand": "pytest", "breaksWhen": "fails"}],
    "red": {"command": "pytest -q", "exitCode": 1, "failingTests": ["test_x"]}
})
rc, out, err = call_cmd(task_mod.cmd_review, str(d))
check("review returns 0", rc == 0, f"got {rc}, err={err[:200]}")
check("prints OK", "[OK]" in out, out[:200])

# ============================================================================
# 4. behavior_change complete WITHOUT green → FAIL
# ============================================================================
print("\n--- 4. Complete without green → FAIL ---")
d = task_path("verify-d")
write_q(d, {
    "workType": "behavior_change",
    "testPlan": [{"acceptancePoint": "x", "testCommand": "pytest", "breaksWhen": "fails"}],
    "red": {"command": "pytest -q", "exitCode": 1}
})
rc, _, err = call_cmd(task_mod.cmd_complete, str(d))
check("complete returns 1", rc == 1, f"got {rc}")
check("stderr mentions Completion evidence", "Completion evidence gate failed" in err, err[:300])

# ============================================================================
# 5. GREEN command MISMATCH with RED → complete FAIL
# ============================================================================
print("\n--- 5. Green command mismatch → complete FAIL ---")
d = task_path("verify-e")
write_q(d, {
    "workType": "behavior_change",
    "testPlan": [{"acceptancePoint": "x", "testCommand": "pytest", "breaksWhen": "fails"}],
    "red": {"command": "pytest tests/test_a.py -q", "exitCode": 1},
    "green": {"command": "pytest tests/test_b.py -q", "exitCode": 0},
    "standards": {"encodingScan": {"ok": True}, "bomScan": {"ok": True}, "whitespaceCheck": {"ok": True}, "shallowTestScan": {"ok": True}},
    "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"}
})
rc, _, err = call_cmd(task_mod.cmd_complete, str(d))
check("complete returns 1", rc == 1, f"got {rc}")
check("stderr mentions command family mismatch", "command family" in err, err[:300])

# ============================================================================
# 6. FULL valid evidence → complete PASS
# ============================================================================
print("\n--- 6. Full valid evidence → complete PASS ---")
d = task_path("verify-d")
write_q(d, {
    "workType": "behavior_change",
    "testPlan": [{"acceptancePoint": "x", "testCommand": "pytest -q", "breaksWhen": "fails"}],
    "red": {"command": "pytest -q", "exitCode": 1},
    "green": {"command": "pytest -q", "exitCode": 0},
    "standards": {"encodingScan": {"ok": True}, "bomScan": {"ok": True}, "whitespaceCheck": {"ok": True}, "shallowTestScan": {"ok": True}},
    "check": {"reviewerMode": "code-review", "commands": ["pytest -q"], "specSync": "no-changes", "scopeReview": "matched"}
})
rc, out, err = call_cmd(task_mod.cmd_complete, str(d))
check("complete returns 0", rc == 0, f"got {rc}, err={err[:200]}")
check("prints OK", "[OK]" in out, out[:200])

# ============================================================================
# 7. docs_chore → review PASS (no TDD required)
# ============================================================================
print("\n--- 7. docs_chore → review PASS ---")
d = task_path("verify-g")
write_q(d, {"workType": "docs_chore"})
rc, out, _ = call_cmd(task_mod.cmd_review, str(d))
check("review returns 0", rc == 0, f"got {rc}")
check("prints OK for docs_chore", "[OK]" in out, out[:200])

# ============================================================================
# 8. Missing standards key → complete FAIL
# ============================================================================
print("\n--- 8. Missing standards sub-key → complete FAIL ---")
d = task_path("verify-h")
write_q(d, {
    "workType": "docs_chore",
    "standards": {
        "encodingScan": {"ok": True},
        "bomScan": {"ok": True},
        "whitespaceCheck": {"ok": True}
        # shallowTestScan intentionally missing
    },
    "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"}
})
rc, _, err = call_cmd(task_mod.cmd_complete, str(d))
check("complete returns 1", rc == 1, f"got {rc}")
check("stderr mentions shallowTestScan is missing", "shallowTestScan" in err, err[:300])

# ============================================================================
# 9. Shallow test scanner — real file scan
# ============================================================================
print("\n--- 9. Shallow test scanner — real file scan ---")
import tempfile
with tempfile.TemporaryDirectory() as td:
    task_dir = Path(td)
    # Write a clean test file
    (task_dir / "test_ok.py").write_text("def test_add():\n    assert add(1,2) == 3\n", encoding="utf-8")
    # Write a bad test file
    (task_dir / "test_bad.py").write_text("def test_nothing():\n    assert True\n", encoding="utf-8")
    result = test_quality.scan_test_files(task_dir)
    check("scan_test_files fails with shallow test", not result["ok"], f"ok={result['ok']}")
    check("violations mention shallow assertion", any("shallow" in v for v in result["violations"]), str(result["violations"]))

# ============================================================================
# 10. BOM scan — real file with BOM bytes
# ============================================================================
print("\n--- 10. BOM scan — real file with BOM ---")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "with_bom.py"
    p.write_bytes(b"\xef\xbb\xbf# -*- coding: utf-8 -*-\nprint('hi')\n")
    result = coding_standards.scan_bom([p])
    check("BOM scan detects BOM", not result["ok"], f"ok={result['ok']}")
    check("violations mention BOM", any("BOM" in v for v in result["violations"]), str(result["violations"]))

# ============================================================================
# 11. Encoding scan — missing UTF-8 in read_text
# ============================================================================
print("\n--- 11. Encoding scan — missing UTF-8 ---")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "reader.py"
    p.write_text("from pathlib import Path\ndef read():\n    return Path('f.txt').read_text()\n", encoding="utf-8")
    result = coding_standards.scan_encoding([p])
    check("encoding scan detects missing UTF-8", not result["ok"], f"ok={result['ok']}")
    check("violations mention read_text", any("read_text" in v for v in result["violations"]), str(result["violations"]))

# ============================================================================
# 12. Agent policy — advisory agent drift detection
# ============================================================================
print("\n--- 12. Agent policy — drift detection ---")
bad_text = "[features]\nmulti_agent = true\n\n[features.multi_agent_v2]\nenabled = true\n"
errors = agent_policy.check_advisory_agent(Path("test.toml"), bad_text)
check("detects multi_agent=true", any("multi_agent must be false" in e for e in errors), str(errors))
check("detects enabled=true", any("enabled must be false" in e for e in errors), str(errors))

# ============================================================================
# 13. green exitCode != 0 → complete FAIL
# ============================================================================
print("\n--- 13. green exitCode != 0 → complete FAIL ---")
d = task_path("verify-d2")
write_q(d, {
    "workType": "behavior_change",
    "testPlan": [{"acceptancePoint": "x", "testCommand": "pytest -q", "breaksWhen": "fails"}],
    "red": {"command": "pytest -q", "exitCode": 1},
    "green": {"command": "pytest -q", "exitCode": 1},
    "standards": {"encodingScan": {"ok": True}, "bomScan": {"ok": True}, "whitespaceCheck": {"ok": True}, "shallowTestScan": {"ok": True}},
    "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"}
})
rc, _, err = call_cmd(task_mod.cmd_complete, str(d))
check("complete with green exitCode=1 returns 1", rc == 1, f"got {rc}")
check("stderr mentions exitCode", "exitCode" in err, err[:300])

# ============================================================================
# 14. invalid JSON → treated as empty → review FAIL (fail-closed)
# ============================================================================
print("\n--- 14. Malformed quality.json → review FAIL (fail-closed) ---")
d = task_path("verify-a")
(d / "quality.json").write_text("{not valid json!!!", encoding="utf-8")
rc, _, err = call_cmd(task_mod.cmd_review, str(d))
check("malformed JSON → review returns 1", rc == 1, f"got {rc}")
check("stderr mentions TDD evidence", "TDD evidence gate failed" in err, err[:200])

# ============================================================================
# 15. empty quality.json {} → default behavior_change → review FAIL
# ============================================================================
print("\n--- 15. Empty quality.json → review FAIL (fail-closed) ---")
d = task_path("verify-a")
write_q(d, {})
rc, _, err = call_cmd(task_mod.cmd_review, str(d))
check("empty {} → review returns 1", rc == 1, f"got {rc}")
check("stderr mentions testPlan", "testPlan" in err, err[:200])

# ============================================================================
# 16. unknown workType → review FAIL
# ============================================================================
print("\n--- 16. Unknown workType → review FAIL ---")
d = task_path("verify-a")
write_q(d, {"workType": "garbage_type"})
rc, _, err = call_cmd(task_mod.cmd_review, str(d))
check("unknown workType → review returns 1", rc == 1, f"got {rc}")
check("stderr mentions Unknown workType", "Unknown workType" in err, err[:200])

# ============================================================================
# 17. Command base normalization: verbosity flags stripped
# ============================================================================
print("\n--- 17. Command family matching ---")
base1 = quality._command_base("pytest tests/x.py -q --tb=short -vv")
base2 = quality._command_base("pytest tests/x.py -v")
check("command_base strips flags", base1 == "pytest tests/x.py" and base2 == "pytest tests/x.py",
      f"got {base1!r} vs {base2!r}")
check("same_family matches", quality._same_command_family("pytest tests/x.py -q", "pytest tests/x.py -v --tb=long"))
check("same_family rejects different files", not quality._same_command_family("pytest a.py", "pytest b.py"))
check("same_family rejects different exec", not quality._same_command_family("pytest a.py", "npm test a.py"))

# ============================================================================
# 18. scan_standards integration (full pipeline)
# ============================================================================
print("\n--- 18. scan_standards full pipeline ---")
with tempfile.TemporaryDirectory() as td:
    task_dir = Path(td)
    (task_dir / "clean.py").write_text("# ok\n", encoding="utf-8")
    result = coding_standards.scan_standards(task_dir, ROOT)
    check("has encodingScan", "encodingScan" in result)
    check("has bomScan", "bomScan" in result)
    check("has whitespaceCheck", "whitespaceCheck" in result)
    check("has shallowTestScan", "shallowTestScan" in result)
    check("all 4 results are dicts with 'ok' key",
          all(isinstance(result[k], dict) and "ok" in result[k]
              for k in ("encodingScan", "bomScan", "whitespaceCheck", "shallowTestScan")))

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
if FAIL > 0:
    print("❌ SOME CHECKS FAILED")
    sys.exit(1)
else:
    print("✅ ALL CHECKS PASSED")
    sys.exit(0)
