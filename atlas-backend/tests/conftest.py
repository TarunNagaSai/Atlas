from __future__ import annotations

import logfire
import pytest


@pytest.fixture(autouse=True, scope="session")
def _quiet_logfire():
    """Keep logfire fully offline during tests.

    ``agent.run_agent`` opens spans and emits info/warn logs; configuring with
    ``send_to_logfire=False`` makes those no-ops (no token, no network, no
    console spam) while still exercising the real span/attribute code paths.
    """
    logfire.configure(send_to_logfire=False, console=False)
    yield
