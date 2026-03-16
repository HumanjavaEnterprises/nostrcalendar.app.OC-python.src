"""Availability management — publish and query free/busy slots on Nostr relays."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from nostrkey import Identity
from nostrkey.relay import RelayClient

from .types import (
    AvailabilityRule,
    CalendarEvent,
    DayOfWeek,
    TimeSlot,
    KIND_APP_DATA,
    KIND_TIME_CALENDAR_EVENT,
    validate_pubkey_hex,
)

AVAILABILITY_D_TAG = "nostrcalendar/availability"


_MAX_EVENTS = 1000  # Safety limit to prevent memory exhaustion from malicious relays


async def _query_events(relay_url: str, filters: dict, max_events: int = _MAX_EVENTS) -> list:
    """Subscribe and collect all events until EOSE.

    Security note: Events returned here are NOT signature-verified by this SDK.
    Signature verification is the consumer's responsibility — the relay may
    return forged or replayed events. Consumers SHOULD call
    ``nostrkey.verify_event()`` on each event before trusting its content.

    Args:
        relay_url: The relay URL to query.
        filters: NIP-01 subscription filters.
        max_events: Maximum number of events to collect (default 1000).
            Prevents memory exhaustion from relays that return unbounded results.
    """
    events = []
    async with RelayClient(relay_url) as relay:
        async for event in relay.subscribe([filters]):
            events.append(event)
            if len(events) >= max_events:
                break
    return events


async def publish_availability(
    identity: Identity,
    rule: AvailabilityRule,
    relay_url: str,
) -> str:
    """Publish availability rules as a replaceable event on a relay.

    Args:
        identity: The NostrKey identity to sign with.
        rule: The availability rules to publish.
        relay_url: The relay URL to publish to.

    Returns:
        The event ID of the published availability event.
    """
    content = json.dumps(rule.to_dict())
    tags = [["d", AVAILABILITY_D_TAG]]

    signed = identity.sign_event(kind=KIND_APP_DATA, content=content, tags=tags)

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed)

    return signed.id


async def get_availability(
    pubkey_hex: str,
    relay_url: str,
) -> AvailabilityRule | None:
    """Fetch a user's published availability rules from a relay.

    Args:
        pubkey_hex: The hex public key of the user.
        relay_url: The relay URL to query.

    Returns:
        The AvailabilityRule if found, None otherwise.
    """
    validate_pubkey_hex(pubkey_hex, "pubkey_hex")
    filters = {
        "kinds": [KIND_APP_DATA],
        "authors": [pubkey_hex],
        "#d": [AVAILABILITY_D_TAG],
        "limit": 1,
    }

    events = await _query_events(relay_url, filters)

    if not events:
        return None

    try:
        data = json.loads(events[0].content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse availability event content as JSON: {exc}"
        ) from exc
    return AvailabilityRule.from_dict(data)


async def get_booked_events(
    pubkey_hex: str,
    relay_url: str,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
) -> list[CalendarEvent]:
    """Fetch existing calendar events (bookings) for a user.

    Args:
        pubkey_hex: The hex public key of the user.
        relay_url: The relay URL to query.
        start_timestamp: Only return events starting after this time.
        end_timestamp: Only return events starting before this time.

    Returns:
        List of CalendarEvent objects.
    """
    validate_pubkey_hex(pubkey_hex, "pubkey_hex")
    filters: dict = {
        "kinds": [KIND_TIME_CALENDAR_EVENT],
        "authors": [pubkey_hex],
    }
    if start_timestamp is not None:
        filters["since"] = start_timestamp
    if end_timestamp is not None:
        filters["until"] = end_timestamp

    events = await _query_events(relay_url, filters)

    return [CalendarEvent.from_tags(e.tags) for e in events]


def compute_free_slots(
    rule: AvailabilityRule,
    booked: list[CalendarEvent],
    date: datetime,
) -> list[TimeSlot]:
    """Compute available time slots for a given date.

    Takes availability rules and existing bookings, returns what's still open.
    Slot times are interpreted in the rule's timezone.

    Args:
        rule: The availability rules.
        booked: Existing calendar events for the date.
        date: The date to compute slots for.

    Returns:
        List of available TimeSlot objects.
    """
    day = DayOfWeek(date.weekday())
    day_slots = rule.slots.get(day, [])

    if not day_slots:
        return []

    # Use the rule's timezone for interpreting slot times
    tz = ZoneInfo(rule.timezone)
    day_start = datetime(date.year, date.month, date.day, tzinfo=tz)

    # Count existing bookings for the day
    day_end = day_start + timedelta(days=1)
    day_start_ts = int(day_start.timestamp())
    day_end_ts = int(day_end.timestamp())
    day_bookings = [
        b for b in booked
        if b.start >= day_start_ts and b.start < day_end_ts
    ]

    if len(day_bookings) >= rule.max_per_day:
        return []

    # Generate candidate slots from availability windows
    free: list[TimeSlot] = []
    for window in day_slots:
        start_h, start_m = map(int, window.start.split(":"))
        end_h, end_m = map(int, window.end.split(":"))

        cursor = day_start + timedelta(hours=start_h, minutes=start_m)
        window_end = day_start + timedelta(hours=end_h, minutes=end_m)

        while cursor + timedelta(minutes=rule.slot_duration_minutes) <= window_end:
            slot_start = int(cursor.timestamp())
            slot_end = int((cursor + timedelta(minutes=rule.slot_duration_minutes)).timestamp())

            # Check for conflicts with existing bookings (including buffer)
            conflict = False
            for booking in day_bookings:
                buffered_start = booking.start - (rule.buffer_minutes * 60)
                buffered_end = booking.end + (rule.buffer_minutes * 60)
                if slot_start < buffered_end and slot_end > buffered_start:
                    conflict = True
                    break

            if not conflict:
                free.append(TimeSlot(
                    start=cursor.strftime("%H:%M"),
                    end=(cursor + timedelta(minutes=rule.slot_duration_minutes)).strftime("%H:%M"),
                ))

            cursor += timedelta(minutes=rule.slot_duration_minutes + rule.buffer_minutes)

    return free


async def get_free_slots(
    pubkey_hex: str,
    relay_url: str,
    date: datetime,
) -> list[TimeSlot]:
    """High-level: fetch availability + bookings and compute free slots for a date.

    Args:
        pubkey_hex: The hex public key of the user.
        relay_url: The relay URL to query.
        date: The date to check availability for.

    Returns:
        List of available TimeSlot objects.
    """
    validate_pubkey_hex(pubkey_hex, "pubkey_hex")
    rule = await get_availability(pubkey_hex, relay_url)
    if rule is None:
        return []

    # Use the rule's timezone for day boundaries
    tz = ZoneInfo(rule.timezone)
    day_start = datetime(date.year, date.month, date.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)

    booked = await get_booked_events(
        pubkey_hex,
        relay_url,
        start_timestamp=int(day_start.timestamp()),
        end_timestamp=int(day_end.timestamp()),
    )

    return compute_free_slots(rule, booked, date)
