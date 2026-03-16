"""Tests for availability computation (no relay needed)."""

from datetime import datetime, timezone

from nostrcalendar.types import AvailabilityRule, CalendarEvent, DayOfWeek, TimeSlot
from nostrcalendar.availability import compute_free_slots


def test_compute_free_slots_no_bookings():
    """All slots should be free when there are no bookings."""
    rule = AvailabilityRule(
        slots={
            DayOfWeek.MONDAY: [TimeSlot("09:00", "11:00")],
        },
        slot_duration_minutes=30,
        buffer_minutes=15,
        max_per_day=8,
    )
    # 2026-03-16 is a Monday
    date = datetime(2026, 3, 16, tzinfo=timezone.utc)
    slots = compute_free_slots(rule, [], date)

    # 09:00-11:00 with 30min slots + 15min buffer = 09:00, 09:45, 10:30
    assert len(slots) == 3
    assert slots[0].start == "09:00"
    assert slots[0].end == "09:30"
    assert slots[1].start == "09:45"
    assert slots[1].end == "10:15"
    assert slots[2].start == "10:30"
    assert slots[2].end == "11:00"


def test_compute_free_slots_with_booking():
    """Slots conflicting with existing bookings should be excluded."""
    rule = AvailabilityRule(
        slots={
            DayOfWeek.MONDAY: [TimeSlot("09:00", "11:00")],
        },
        slot_duration_minutes=30,
        buffer_minutes=15,
        max_per_day=8,
    )

    # Existing booking at 09:45-10:15 (blocks the second slot)
    date = datetime(2026, 3, 16, tzinfo=timezone.utc)
    booking_start = int(datetime(2026, 3, 16, 9, 45, tzinfo=timezone.utc).timestamp())
    booking_end = int(datetime(2026, 3, 16, 10, 15, tzinfo=timezone.utc).timestamp())

    booked = [CalendarEvent(
        d_tag="existing",
        title="Existing meeting",
        start=booking_start,
        end=booking_end,
    )]

    slots = compute_free_slots(rule, booked, date)

    # The 09:45 slot is taken, buffer blocks adjacent slots too
    slot_starts = [s.start for s in slots]
    assert "09:45" not in slot_starts


def test_compute_free_slots_wrong_day():
    """No slots on days not in the availability rules."""
    rule = AvailabilityRule(
        slots={
            DayOfWeek.MONDAY: [TimeSlot("09:00", "11:00")],
        },
    )
    # 2026-03-17 is a Tuesday
    date = datetime(2026, 3, 17, tzinfo=timezone.utc)
    slots = compute_free_slots(rule, [], date)
    assert slots == []


def test_compute_free_slots_max_per_day():
    """No slots when max bookings per day is reached."""
    rule = AvailabilityRule(
        slots={
            DayOfWeek.MONDAY: [TimeSlot("09:00", "17:00")],
        },
        slot_duration_minutes=30,
        buffer_minutes=0,
        max_per_day=2,
    )

    date = datetime(2026, 3, 16, tzinfo=timezone.utc)
    base = int(datetime(2026, 3, 16, 9, 0, tzinfo=timezone.utc).timestamp())

    booked = [
        CalendarEvent(d_tag="a", title="A", start=base, end=base + 1800),
        CalendarEvent(d_tag="b", title="B", start=base + 3600, end=base + 5400),
    ]

    slots = compute_free_slots(rule, booked, date)
    assert slots == []
