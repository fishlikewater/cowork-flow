#!/usr/bin/env python3
import json, sys, importlib, os
from pathlib import Path

data = json.loads(sys.stdin.read())
root = Path(data['cwd'])
SCRIPT_DIR = Path('E:\\Projects\\IdeaProjects\\person\\cowork-flow\\template\\.cowork-flow\\scripts')

sys.path.insert(0, str(SCRIPT_DIR))
try:
    paths = importlib.import_module('common.paths')
    fs = importlib.import_module('flow.store')

    db_path = paths.get_db_path(root)
    print(f'HOOK_DB: {db_path}', file=sys.stderr)
    print(f'HOOK_DB_EXISTS: {db_path.exists()}', file=sys.stderr)

    try:
        with fs.FlowStore(str(db_path)) as store:
            session = store.get_runtime_session('claude_demo-session')
            print(f'HOOK_SESSION: {session}', file=sys.stderr)
    except Exception as e:
        print(f'HOOK_ERROR: {e}', file=sys.stderr)

    # Also test resolve_context_key
    at = importlib.import_module('common.active_task')
    key = at.resolve_context_key(data)
    print(f'HOOK_CONTEXT_KEY: {key}', file=sys.stderr)
finally:
    pass

print(json.dumps({'worked': True}))
