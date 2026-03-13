"""Data types for NostrCalendar — availability rules, calendar events, bookings."""

from dataclasses import dataclass, field
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Timestamp boundaries: 2020-01-01 00:00:00 UTC and 2100-01-01 00:00:00 UTC
_MIN_TIMESTAMP = 1_577_836_800
_MAX_TIMESTAMP = 4_102_444_800


def validate_timestamp(value: int, name: str = "timestamp") -> None:
    """Validate that a Unix timestamp is a positive integer within a reasonable range.

    Args:
        value: The timestamp to validate.
        name: Human-readable name for error messages.

    Raises:
        ValueError: If the timestamp is out of range.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, got {type(value).__name__}")
    if value < _MIN_TIMESTAMP or value > _MAX_TIMESTAMP:
        raise ValueError(
            f"{name} ({value}) is out of range. "
            f"Must be between {_MIN_TIMESTAMP} (2020-01-01) and {_MAX_TIMESTAMP} (2100-01-01)."
        )


def _validate_timezone(tz_str: str) -> None:
    """Validate a timezone string against the IANA tz database.

    Rejects strings with null bytes or path separators that could be used for
    injection attacks against file-system-backed timezone lookups.

    Args:
        tz_str: The timezone string to validate.

    Raises:
        ValueError: If the timezone is invalid or contains dangerous characters.
    """
    if not isinstance(tz_str, str) or not tz_str:
        raise ValueError("timezone must be a non-empty string")
    # Block null bytes and backslashes (path separator injection)
    if "\x00" in tz_str or "\\" in tz_str:
        raise ValueError(f"timezone contains invalid characters: {tz_str!r}")
    # Block strings that look like path traversal
    if ".." in tz_str:
        raise ValueError(f"timezone contains path traversal: {tz_str!r}")
    # Validate against the IANA tz database
    try:
        ZoneInfo(tz_str)
    except (ZoneInfoNotFoundError, KeyError):
        raise ValueError(f"Unknown timezone: {tz_str!r}")


class DayOfWeek(Enum):
    """Days of the week for availability rules."""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass
class TimeSlot:
    """A window of availability within a day.

    Times are in 24-hour format, e.g. "09:00", "17:30".
    """
    start: str
    end: str

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, data: dict) -> "TimeSlot":
        return cls(start=data["start"], end=data["end"])


@dataclass
class AvailabilityRule:
    """Defines when someone is available for bookings.

    Stored as a replaceable event (kind 30078) with d-tag "nostrcal/availability".
    """
    slots: dict[DayOfWeek, list[TimeSlot]] = field(default_factory=dict)
    slot_duration_minutes: int = 30
    buffer_minutes: int = 15
    max_per_day: int = 8
    timezone: str = "UTC"
    title: str = "Available for booking"

    # Upper bounds for integer fields to prevent memory/overflow issues
    _MAX_SLOT_DURATION = 1440  # 24 hours in minutes
    _MAX_BUFFER = 1440
    _MAX_PER_DAY = 1000

    def __post_init__(self) -> None:
        _validate_timezone(self.timezone)
        if not isinstance(self.slot_duration_minutes, int) or self.slot_duration_minutes < 1:
            raise ValueError(
                f"slot_duration_minutes must be a positive integer, got {self.slot_duration_minutes}"
            )
        if self.slot_duration_minutes > self._MAX_SLOT_DURATION:
            raise ValueError(
                f"slot_duration_minutes ({self.slot_duration_minutes}) exceeds maximum "
                f"of {self._MAX_SLOT_DURATION}"
            )
        if not isinstance(self.buffer_minutes, int) or self.buffer_minutes < 0:
            raise ValueError(
                f"buffer_minutes must be a non-negative integer, got {self.buffer_minutes}"
            )
        if self.buffer_minutes > self._MAX_BUFFER:
            raise ValueError(
                f"buffer_minutes ({self.buffer_minutes}) exceeds maximum of {self._MAX_BUFFER}"
            )
        if not isinstance(self.max_per_day, int) or self.max_per_day < 1:
            raise ValueError(
                f"max_per_day must be a positive integer, got {self.max_per_day}"
            )
        if self.max_per_day > self._MAX_PER_DAY:
            raise ValueError(
                f"max_per_day ({self.max_per_day}) exceeds maximum of {self._MAX_PER_DAY}"
            )

    def to_dict(self) -> dict:
        return {
            "slots": {
                day.name.lower(): [s.to_dict() for s in day_slots]
                for day, day_slots in self.slots.items()
            },
            "slot_duration_minutes": self.slot_duration_minutes,
            "buffer_minutes": self.buffer_minutes,
            "max_per_day": self.max_per_day,
            "timezone": self.timezone,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AvailabilityRule":
        slots = {}
        for day_name, day_slots in data.get("slots", {}).items():
            day = DayOfWeek[day_name.upper()]
            slots[day] = [TimeSlot.from_dict(s) for s in day_slots]
        return cls(
            slots=slots,
            slot_duration_minutes=data.get("slot_duration_minutes", 30),
            buffer_minutes=data.get("buffer_minutes", 15),
            max_per_day=data.get("max_per_day", 8),
            timezone=data.get("timezone", "UTC"),
            title=data.get("title", "Available for booking"),
        )


class BookingStatus(Enum):
    """Status of a booking request."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"


@dataclass
class CalendarEvent:
    """A time-based calendar event (NIP-52 kind 31923).

    Privacy model: start/end times and participant pubkeys are in public tags
    (so relays can filter and participants can discover events). The private
    details (title, description, location) go into the event content field,
    encrypted per-participant using NIP-44.

    What observers see: "pubkey A has something at time X with pubkey B"
    What participants see: "Product roadmap review — Q2 planning — Zoom link"

    Attributes:
        d_tag: Unique identifier for the event (replaceable).
        title: Human-readable title (encrypted in content).
        start: Unix timestamp of event start (public tag).
        end: Unix timestamp of event end (public tag).
        location: Optional location string (encrypted in content).
        description: Optional description (encrypted in content).
        participants: List of pubkeys (hex) invited to the event (public tags).
    """
    d_tag: str
    title: str
    start: int
    end: int
    location: str = ""
    description: str = ""
    participants: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_timestamp(self.start, "start")
        validate_timestamp(self.end, "end")

    def to_tags(self) -> list[list[str]]:
        """Convert to NIP-52 event tags (public envelope only).

        Title, description, and location are NOT included — they go into
        encrypted content via CalendarEvent.to_private_content().
        """
        tags = [
            ["d", self.d_tag],
            ["start", str(self.start)],
            ["end", str(self.end)],
        ]
        for pubkey in self.participants:
            tags.append(["p", pubkey])
        return tags

    def to_private_content(self) -> dict:
        """The private details that get encrypted into the event content."""
        return {
            "title": self.title,
            "description": self.description,
            "location": self.location,
        }

    @classmethod
    def from_tags_and_content(
        cls, tags: list[list[str]], private_content: dict | None = None,
    ) -> "CalendarEvent":
        """Parse from NIP-52 tags + decrypted private content.

        Args:
            tags: The public event tags.
            private_content: The decrypted content dict, or None if
                the viewer doesn't have the key to decrypt.
        """
        fields: dict = {}
        participants: list[str] = []
        for tag in tags:
            if len(tag) < 2:
                continue
            if tag[0] == "d":
                fields["d_tag"] = tag[1]
            elif tag[0] == "start":
                fields["start"] = int(tag[1])
            elif tag[0] == "end":
                fields["end"] = int(tag[1])
            elif tag[0] == "p":
                participants.append(tag[1])
        fields["participants"] = participants

        # Fill in private details if decrypted
        if private_content:
            fields["title"] = private_content.get("title", "")
            fields["description"] = private_content.get("description", "")
            fields["location"] = private_content.get("location", "")
        else:
            fields["title"] = ""
            fields["description"] = ""
            fields["location"] = ""

        return cls(**fields)

    @classmethod
    def from_tags(cls, tags: list[list[str]]) -> "CalendarEvent":
        """Parse from NIP-52 event tags (public data only, no decryption)."""
        return cls.from_tags_and_content(tags, None)


@dataclass
class RSVP:
    """An RSVP response to a calendar event (NIP-52 kind 31925).

    Attributes:
        event_d_tag: The d-tag of the calendar event being responded to.
        event_pubkey: The pubkey of the calendar event author.
        status: accepted, declined, or tentative.
    """
    event_d_tag: str
    event_pubkey: str
    status: str = "accepted"

    def to_tags(self) -> list[list[str]]:
        return [
            ["d", self.event_d_tag],
            ["a", f"31923:{self.event_pubkey}:{self.event_d_tag}"],
            ["status", self.status],
            ["p", self.event_pubkey],
        ]


@dataclass
class BookingRequest:
    """A request to book a time slot, sent as an encrypted DM (NIP-17).

    The agent receives these and can accept/decline based on availability rules.
    """
    requester_pubkey: str
    requested_start: int
    requested_end: int
    title: str = "Meeting"
    message: str = ""
    status: BookingStatus = BookingStatus.PENDING

    def __post_init__(self) -> None:
        validate_timestamp(self.requested_start, "requested_start")
        validate_timestamp(self.requested_end, "requested_end")

    def to_dict(self) -> dict:
        return {
            "type": "nostrcal:booking_request",
            "requester": self.requester_pubkey,
            "start": self.requested_start,
            "end": self.requested_end,
            "title": self.title,
            "message": self.message,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BookingRequest":
        return cls(
            requester_pubkey=data["requester"],
            requested_start=data["start"],
            requested_end=data["end"],
            title=data.get("title", "Meeting"),
            message=data.get("message", ""),
            status=BookingStatus(data.get("status", "pending")),
        )
