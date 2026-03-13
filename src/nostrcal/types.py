"""Data types for NostrCal — availability rules, calendar events, bookings."""

from dataclasses import dataclass, field
from enum import Enum


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
