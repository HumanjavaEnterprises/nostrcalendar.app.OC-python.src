"""Shared fixtures for the booking/negotiate test suite.

No live network: RelayClient is replaced by a stub that records
published events in memory.
"""

import pytest

from nostrkey import Identity


class FakeRelay:
    """In-memory stand-in for nostrkey.relay.RelayClient.

    Records every published event so tests can inspect exactly what
    would have gone out over the wire.
    """

    published: list = []

    def __init__(self, relay_url: str):
        self.relay_url = relay_url

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def publish(self, event):
        FakeRelay.published.append(event)


@pytest.fixture
def fake_relay(monkeypatch):
    """Patch RelayClient in every module that publishes, and return the stub."""
    FakeRelay.published = []
    monkeypatch.setattr("nostrcalendar.booking.RelayClient", FakeRelay)
    monkeypatch.setattr("nostrcalendar.negotiate.RelayClient", FakeRelay)
    return FakeRelay


@pytest.fixture
def alice():
    """The requester / proposing agent."""
    return Identity.generate()


@pytest.fixture
def bob():
    """The calendar owner / responding agent."""
    return Identity.generate()
