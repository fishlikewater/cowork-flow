from __future__ import annotations

import os
from unittest.mock import patch

from tests.flow_test_support import (
    HOST_SESSION_ENV,
    FlowScriptTestCase,
    restore_host_session_env,
    scrub_host_session_env,
)


class HostSessionEnvTest(FlowScriptTestCase):
    def test_scrub_removes_workflow_and_host_session_vars_then_restores(self) -> None:
        seeded = {
            "COWORK_FLOW_HOST": "zcode",
            "COWORK_FLOW_CONTEXT_ID": "main",
            "ZCODE_SESSION_ID": "sess",
            "ZCODE_PROJECT_DIR": "E:/host/project",
            "CLAUDE_PROJECT_DIR": "E:/host/project",
            "QODER_PROJECT_DIR": "E:/host/project",
            "QODER_WORKING_DIR": "E:/host/project",
        }
        with patch.dict(os.environ, seeded, clear=False):
            saved = scrub_host_session_env()

            for name in seeded:
                self.assertNotIn(name, os.environ)
            # Unrelated environment is not the scrubber's business.
            self.assertIn("PATH", os.environ)

            restore_host_session_env(saved)

            for name, value in seeded.items():
                self.assertEqual(value, os.environ[name])

    def test_restore_drops_host_variables_set_after_the_scrub(self) -> None:
        # Restoring means the pre-scrub environment, not saved values merged
        # over whatever the test left behind.
        with patch.dict(os.environ, {"ZCODE_SESSION_ID": "host"}, clear=False):
            saved = scrub_host_session_env()
            os.environ["DSH_SESSION_ID"] = "test-created"

            restore_host_session_env(saved)

            self.assertEqual("host", os.environ["ZCODE_SESSION_ID"])
            self.assertNotIn("DSH_SESSION_ID", os.environ)

    def test_every_declared_host_session_variable_is_covered(self) -> None:
        # The scrub list must not drift from the runtime's host table: a host
        # added there without a matching entry here would leak its live session
        # into every fixture.
        from runtime.host_identity import HOST_IDENTITIES

        declared = {
            name
            for identity in HOST_IDENTITIES
            for name in identity.session_env
        }
        self.assertEqual(set(), declared - set(HOST_SESSION_ENV))
