"""Tests for NostrCalendar data types."""

import pytest

from nostrcalendar.types import (
    AvailabilityRule,
    BookingRequest,
    BookingStatus,
    CalendarEvent,
    DayOfWeek,
    RSVP,
    TimeSlot,
    validate_pubkey_hex,
)

# Test pubkeys (valid 64-char hex strings)
PUB_A = "a" * 64
PUB_B = "b" * 64
PUB_C = "c" * 64


def test_timeslot_roundtrip():
    slot = TimeSlot(start="09:00", end="09:30")
    data = slot.to_dict()
    restored = TimeSlot.from_dict(data)
    assert restored.start == "09:00"
    assert restored.end == "09:30"


def test_availability_rule_roundtrip():
    rule = AvailabilityRule(
        slots={
            DayOfWeek.MONDAY: [TimeSlot("09:00", "12:00"), TimeSlot("14:00", "17:00")],
            DayOfWeek.FRIDAY: [TimeSlot("10:00", "15:00")],
        },
        slot_duration_minutes=30,
        buffer_minutes=10,
        max_per_day=5,
        timezone="America/Vancouver",
        title="Book me",
    )
    data = rule.to_dict()
    restored = AvailabilityRule.from_dict(data)

    assert len(restored.slots) == 2
    assert DayOfWeek.MONDAY in restored.slots
    assert DayOfWeek.FRIDAY in restored.slots
    assert len(restored.slots[DayOfWeek.MONDAY]) == 2
    assert restored.slot_duration_minutes == 30
    assert restored.buffer_minutes == 10
    assert restored.max_per_day == 5
    assert restored.timezone == "America/Vancouver"
    assert restored.title == "Book me"


def test_calendar_event_public_tags():
    """Public tags contain only time + participants, not private details."""
    event = CalendarEvent(
        d_tag="abc123",
        title="Team sync",
        start=1742054400,
        end=1742056200,
        location="Zoom",
        description="Weekly standup",
        participants=[PUB_A, PUB_B],
    )
    tags = event.to_tags()

    # Public envelope: d-tag, start, end, participants
    assert ["d", "abc123"] in tags
    assert ["start", "1742054400"] in tags
    assert ["end", "1742056200"] in tags
    assert ["p", PUB_A] in tags
    assert ["p", PUB_B] in tags

    # Private details NOT in tags
    tag_keys = [t[0] for t in tags]
    assert "title" not in tag_keys
    assert "description" not in tag_keys
    assert "location" not in tag_keys


def test_calendar_event_private_content():
    """Private content dict contains title, description, location."""
    event = CalendarEvent(
        d_tag="abc123",
        title="Team sync",
        start=1742054400,
        end=1742056200,
        location="Zoom",
        description="Weekly standup",
        participants=[PUB_A],
    )
    private = event.to_private_content()
    assert private["title"] == "Team sync"
    assert private["description"] == "Weekly standup"
    assert private["location"] == "Zoom"


def test_calendar_event_from_tags_and_content():
    """Reconstruct a full event from public tags + decrypted private content."""
    event = CalendarEvent(
        d_tag="abc123",
        title="Team sync",
        start=1742054400,
        end=1742056200,
        location="Zoom",
        description="Weekly standup",
        participants=[PUB_A, PUB_B],
    )
    tags = event.to_tags()
    private = event.to_private_content()

    restored = CalendarEvent.from_tags_and_content(tags, private)
    assert restored.d_tag == "abc123"
    assert restored.title == "Team sync"
    assert restored.start == 1742054400
    assert restored.end == 1742056200
    assert restored.location == "Zoom"
    assert restored.description == "Weekly standup"
    assert restored.participants == [PUB_A, PUB_B]


def test_calendar_event_from_tags_no_decryption():
    """Without decryption, private fields are empty strings."""
    tags = [
        ["d", "abc123"],
        ["start", "1742054400"],
        ["end", "1742056200"],
        ["p", PUB_A],
    ]
    restored = CalendarEvent.from_tags(tags)
    assert restored.d_tag == "abc123"
    assert restored.start == 1742054400
    assert restored.title == ""
    assert restored.description == ""
    assert restored.location == ""


def test_rsvp_tags():
    rsvp = RSVP(event_d_tag="abc123", event_pubkey=PUB_A, status="accepted")
    tags = rsvp.to_tags()

    assert ["d", "abc123"] in tags
    assert ["a", f"31923:{PUB_A}:abc123"] in tags
    assert ["status", "accepted"] in tags
    assert ["p", PUB_A] in tags


def test_booking_request_roundtrip():
    request = BookingRequest(
        requester_pubkey=PUB_A,
        requested_start=1742054400,
        requested_end=1742056200,
        title="Product review",
        message="Let's discuss the roadmap",
        status=BookingStatus.PENDING,
    )
    data = request.to_dict()

    assert data["type"] == "nostrcalendar:booking_request"

    restored = BookingRequest.from_dict(data)
    assert restored.requester_pubkey == PUB_A
    assert restored.requested_start == 1742054400
    assert restored.requested_end == 1742056200
    assert restored.title == "Product review"
    assert restored.message == "Let's discuss the roadmap"
    assert restored.status == BookingStatus.PENDING


def test_timeslot_validates_format():
    """TimeSlot rejects invalid time formats."""
    with pytest.raises(ValueError, match="HH:MM"):
        TimeSlot(start="9:00", end="10:00")
    with pytest.raises(ValueError, match="HH:MM"):
        TimeSlot(start="09:00", end="25:00")
    with pytest.raises(ValueError, match="HH:MM"):
        TimeSlot(start="09:00", end="noon")


def test_timeslot_validates_ordering():
    """TimeSlot rejects start >= end."""
    with pytest.raises(ValueError, match="must be before"):
        TimeSlot(start="12:00", end="09:00")
    with pytest.raises(ValueError, match="must be before"):
        TimeSlot(start="10:00", end="10:00")


def test_rsvp_validates_status():
    """RSVP rejects invalid status values."""
    with pytest.raises(ValueError, match="must be one of"):
        RSVP(event_d_tag="abc", event_pubkey=PUB_A, status="maybe")
    # Valid statuses should work
    for status in ("accepted", "declined", "tentative"):
        rsvp = RSVP(event_d_tag="abc", event_pubkey=PUB_A, status=status)
        assert rsvp.status == status


def test_rsvp_validates_pubkey():
    """RSVP rejects invalid pubkeys."""
    with pytest.raises(ValueError, match="64-character lowercase hex"):
        RSVP(event_d_tag="abc", event_pubkey="not-a-pubkey", status="accepted")


def test_pubkey_hex_validation():
    """validate_pubkey_hex accepts valid keys and rejects invalid ones."""
    validate_pubkey_hex(PUB_A)  # should not raise
    validate_pubkey_hex("0123456789abcdef" * 4)  # should not raise

    with pytest.raises(ValueError):
        validate_pubkey_hex("too_short")
    with pytest.raises(ValueError):
        validate_pubkey_hex("G" * 64)  # not hex
    with pytest.raises(ValueError):
        validate_pubkey_hex("A" * 64)  # uppercase rejected
    with pytest.raises(ValueError):
        validate_pubkey_hex("")
    with pytest.raises(ValueError):
        validate_pubkey_hex(123)  # not a string


def test_calendar_event_validates_time_ordering():
    """CalendarEvent rejects start >= end."""
    with pytest.raises(ValueError, match="must be before"):
        CalendarEvent(d_tag="x", title="t", start=1742056200, end=1742054400)
    with pytest.raises(ValueError, match="must be before"):
        CalendarEvent(d_tag="x", title="t", start=1742054400, end=1742054400)


def test_calendar_event_validates_participant_pubkeys():
    """CalendarEvent rejects invalid participant pubkeys."""
    with pytest.raises(ValueError, match="64-character lowercase hex"):
        CalendarEvent(
            d_tag="x", title="t", start=1742054400, end=1742056200,
            participants=["not-a-real-pubkey"],
        )


def test_booking_request_validates_time_ordering():
    """BookingRequest rejects start >= end."""
    with pytest.raises(ValueError, match="must be before"):
        BookingRequest(
            requester_pubkey=PUB_A,
            requested_start=1742056200,
            requested_end=1742054400,
        )


def test_booking_request_validates_pubkey():
    """BookingRequest rejects invalid requester pubkey."""
    with pytest.raises(ValueError, match="64-character lowercase hex"):
        BookingRequest(
            requester_pubkey="bad_key",
            requested_start=1742054400,
            requested_end=1742056200,
        )


def test_availability_rule_validates_window_count():
    """AvailabilityRule rejects too many windows per day."""
    too_many = [TimeSlot(f"{h:02d}:00", f"{h:02d}:01") for h in range(0, 24)]
    too_many += [TimeSlot(f"{h:02d}:10", f"{h:02d}:11") for h in range(0, 24)]
    too_many += [TimeSlot(f"{h:02d}:20", f"{h:02d}:21") for h in range(0, 1)]  # 49 total
    assert len(too_many) == 49
    with pytest.raises(ValueError, match="Too many availability windows"):
        AvailabilityRule(slots={DayOfWeek.MONDAY: too_many})
