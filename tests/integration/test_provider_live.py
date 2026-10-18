"""Live Git and Jira reads. They stay skipped unless credentials are supplied.

Set QA_MCP_LIVE_PROVIDERS=1 and the provider token variables to execute them.
This module does not set that variable.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("QA_MCP_LIVE_PROVIDERS") != "1",
    reason="live provider calls are not enabled",
)


def test_live_provider_placeholder() -> None:
    """A live run must call a provider. The default suite does not reach here."""
    pytest.fail("live provider execution is not configured in this environment")
