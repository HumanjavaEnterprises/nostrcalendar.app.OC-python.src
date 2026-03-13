"""Tests for NostrCalendar data types."""

from nostrcal.types import (
    AvailabilityRule,
    BookingRequest,
    BookingStatus,
    CalendarEvent,
    DayOfWeek,
    RSVP,
    TimeSlot,
)


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
        participants=["pubkey1", "pubkey2"],
    )
    tags = event.to_tags()

    # Public envelope: d-tag, start, end, participants
    assert ["d", "abc123"] in tags
    assert ["start", "1742054400"] in tags
    assert ["end", "1742056200"] in tags
    assert ["p", "pubkey1"] in tags
    assert ["p", "pubkey2"] in tags

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
        participants=["pubkey1"],
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
        participants=["pubkey1", "pubkey2"],
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
    assert restored.participants == ["pubkey1", "pubkey2"]


def test_calendar_event_from_tags_no_decryption():
    """Without decryption, private fields are empty strings."""
    tags = [
        ["d", "abc123"],
        ["start", "1742054400"],
        ["end", "1742056200"],
        ["p", "pubkey1"],
    ]
    restored = CalendarEvent.from_tags(tags)
    assert restored.d_tag == "abc123"
    assert restored.start == 1742054400
    assert restored.title == ""
    assert restored.description == ""
    assert restored.location == ""


def test_rsvp_tags():
    rsvp = RSVP(event_d_tag="abc123", event_pubkey="pubkey1", status="accepted")
    tags = rsvp.to_tags()

    assert ["d", "abc123"] in tags
    assert ["a", "31923:pubkey1:abc123"] in tags
    assert ["status", "accepted"] in tags
    assert ["p", "pubkey1"] in tags


def test_booking_request_roundtrip():
    request = BookingRequest(
        requester_pubkey="requester_hex",
        requested_start=1742054400,
        requested_end=1742056200,
        title="Product review",
        message="Let's discuss the roadmap",
        status=BookingStatus.PENDING,
    )
    data = request.to_dict()

    assert data["type"] == "nostrcal:booking_request"

    restored = BookingRequest.from_dict(data)
    assert restored.requester_pubkey == "requester_hex"
    assert restored.requested_start == 1742054400
    assert restored.requested_end == 1742056200
    assert restored.title == "Product review"
    assert restored.message == "Let's discuss the roadmap"
    assert restored.status == BookingStatus.PENDING
