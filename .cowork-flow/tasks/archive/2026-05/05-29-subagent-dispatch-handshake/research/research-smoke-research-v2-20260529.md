# Research smoke run: cowork-research

- Role: cowork-research
- Dispatch ID: smoke-research-v2-20260529
- Python version: Python 3.12.1
- Search command: `rtk rg -n "COWORK_DISPATCH_V1|COWORK_ACK|agent_type" .codex/agents .cowork-flow/scripts tests`
- Search hit line count: 50
- First 5 search hit lines:

```text
tests\test_cowork_agents.py:72:                    "COWORK_DISPATCH_V1",
tests\test_cowork_agents.py:74:                    "COWORK_ACK",
tests\test_cowork_agents.py:79:                    f"agent_type: {agent_name}",
tests\test_cowork_agents.py:81:                    f"agent_type is not `{agent_name}`",
tests\test_cowork_agents.py:92:            "COWORK_DISPATCH_V1",
```

- Git status: has uncommitted changes.

