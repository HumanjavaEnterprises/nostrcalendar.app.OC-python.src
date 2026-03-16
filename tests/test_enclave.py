"""Tests for CalendarEnclave — NSE orchestrator integration."""

import time

from nostrcalendar.enclave import CalendarEnclave
from nostrcalendar.types import (
    AvailabilityRule,
    CalendarEvent,
    DayOfWeek,
    TimeSlot,
)


def test_create_default():
    """CalendarEnclave.create() works with no arguments."""
    enclave = CalendarEnclave.create()
    assert enclave.rule is None
    assert enclave.relay_url == ""
    assert not enclave.is_configured
    assert enclave.event_count == 0


def test_create_with_config():
    """CalendarEnclave.create() accepts rule and relay_url."""
    rule = AvailabilityRule(
        slots={DayOfWeek.MONDAY: [TimeSlot("09:00", "12:00")]},
        timezone="America/Vancouver",
    )
    enclave = CalendarEnclave.create(rule=rule, relay_url="wss://relay.example.com")
    assert enclave.is_configured
    assert enclave.rule is rule
    assert enclave.relay_url == "wss://relay.example.com"


def test_configure_after_create():
    """Configuration can be updated after creation."""
    enclave = CalendarEnclave.create()
    assert not enclave.is_configured

    rule = AvailabilityRule(
        slots={DayOfWeek.FRIDAY: [TimeSlot("10:00", "15:00")]},
    )
    enclave.configure(rule=rule, relay_url="wss://relay.test.com")
    assert enclave.is_configured
    assert enclave.rule.timezone == "UTC"


def test_owner_activity_tracking():
    """Touch updates last active, hours_since calculates correctly."""
    enclave = CalendarEnclave.create()
    enclave.touch()
    assert enclave.hours_since_owner_active() < 0.01  # just touched

    # Simulate stale activity
    enclave._owner_last_active = time.time() - (48 * 3600)
    assert enclave.hours_since_owner_active() >= 47.9


def test_event_management():
    """Events can be added and removed by d-tag."""
    enclave = CalendarEnclave.create()

    event = CalendarEvent(
        d_tag="meeting-123",
        title="Sync",
        start=1742054400,
        end=1742056200,
    )
    enclave.add_event(event)
    assert enclave.event_count == 1
    assert enclave.events[0].d_tag == "meeting-123"

    # Remove by d-tag
    assert enclave.remove_event("meeting-123") is True
    assert enclave.event_count == 0

    # Remove nonexistent
    assert enclave.remove_event("no-such-event") is False


def test_status_summary():
    """Status returns a useful dict for the orchestrator."""
    enclave = CalendarEnclave.create()
    status = enclave.status()

    assert status["configured"] is False
    assert status["has_rule"] is False
    assert status["has_relay"] is False
    assert status["event_count"] == 0
    assert isinstance(status["hours_since_owner_active"], float)


def test_events_returns_copy():
    """Events property returns a copy, not the internal list."""
    enclave = CalendarEnclave.create()
    event = CalendarEvent(d_tag="x", title="t", start=1742054400, end=1742056200)
    enclave.add_event(event)

    events = enclave.events
    events.clear()
    assert enclave.event_count == 1  # internal list unchanged
