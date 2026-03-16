"""CalendarEnclave — stateful scheduling manager for the NSE orchestrator.

This is the Time pillar's organ. The NerveCenter holds a reference to it
and uses it to query calendar state. Cross-pillar checks (e.g., scheduling
while owner is absent) use parameters from the caller, not methods here —
the enclave's job is to hold state and execute actions.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .types import AvailabilityRule, CalendarEvent, TimeSlot


class CalendarEnclave:
    """High-level calendar manager for an AI agent.

    Holds the agent's availability rule, relay URL, and tracks
    owner activity for cross-pillar checks.
    """

    def __init__(
        self,
        rule: Optional[AvailabilityRule] = None,
        relay_url: str = "",
        events: Optional[list[CalendarEvent]] = None,
    ) -> None:
        self._rule = rule
        self._relay_url = relay_url
        self._events: list[CalendarEvent] = events or []
        self._owner_last_active: float = time.time()

    @classmethod
    def create(
        cls,
        rule: Optional[AvailabilityRule] = None,
        relay_url: str = "",
    ) -> CalendarEnclave:
        """Create a new CalendarEnclave.

        Args:
            rule: The agent's availability rules. Can be set later via configure().
            relay_url: The relay to publish/query events on. Can be set later.

        Returns:
            A new CalendarEnclave instance.
        """
        return cls(rule=rule, relay_url=relay_url)

    def configure(
        self,
        rule: Optional[AvailabilityRule] = None,
        relay_url: Optional[str] = None,
    ) -> None:
        """Update the enclave's configuration after creation."""
        if rule is not None:
            self._rule = rule
        if relay_url is not None:
            self._relay_url = relay_url

    # --- Owner activity tracking (used by cross-pillar checks) ---

    def touch(self) -> None:
        """Record that the owner interacted with the calendar.

        Call this whenever the owner views, modifies, or acknowledges
        their schedule. The orchestrator uses hours_since_owner_active()
        in cross-pillar checks.
        """
        self._owner_last_active = time.time()

    @property
    def owner_last_active(self) -> float:
        """Unix timestamp of the owner's last calendar interaction."""
        return self._owner_last_active

    def hours_since_owner_active(self) -> float:
        """Hours since the owner last interacted with the calendar."""
        return (time.time() - self._owner_last_active) / 3600.0

    # --- Local event management ---

    def add_event(self, event: CalendarEvent) -> None:
        """Track a calendar event locally."""
        self._events.append(event)

    def remove_event(self, d_tag: str) -> bool:
        """Remove an event by d-tag. Returns True if found."""
        before = len(self._events)
        self._events = [e for e in self._events if e.d_tag != d_tag]
        return len(self._events) < before

    @property
    def events(self) -> list[CalendarEvent]:
        """All locally tracked events."""
        return list(self._events)

    @property
    def event_count(self) -> int:
        """Number of locally tracked events."""
        return len(self._events)

    # --- State ---

    @property
    def rule(self) -> Optional[AvailabilityRule]:
        """The current availability rule, or None if not configured."""
        return self._rule

    @property
    def relay_url(self) -> str:
        """The relay URL for publishing/querying."""
        return self._relay_url

    @property
    def is_configured(self) -> bool:
        """Whether the enclave has both a rule and relay URL set."""
        return self._rule is not None and bool(self._relay_url)

    def status(self) -> dict:
        """Return a status summary for the orchestrator."""
        return {
            "configured": self.is_configured,
            "has_rule": self._rule is not None,
            "has_relay": bool(self._relay_url),
            "event_count": self.event_count,
            "hours_since_owner_active": round(self.hours_since_owner_active(), 1),
        }
