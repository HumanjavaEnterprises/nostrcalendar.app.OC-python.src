"""NostrCal — Nostr-native scheduling for OpenClaw AI agents."""

from .types import (
    AvailabilityRule,
    BookingRequest,
    BookingStatus,
    CalendarEvent,
    DayOfWeek,
    RSVP,
    TimeSlot,
)
from .availability import (
    compute_free_slots,
    get_availability,
    get_booked_events,
    get_free_slots,
    publish_availability,
)
from .booking import (
    accept_booking,
    cancel_event,
    create_booking,
    decline_booking,
    decrypt_calendar_event,
    send_rsvp,
)
from .negotiate import (
    find_mutual_availability,
    propose_times,
    respond_to_proposal,
)

__version__ = "0.1.0"

__all__ = [
    # Types
    "AvailabilityRule",
    "BookingRequest",
    "BookingStatus",
    "CalendarEvent",
    "DayOfWeek",
    "RSVP",
    "TimeSlot",
    # Availability
    "compute_free_slots",
    "get_availability",
    "get_booked_events",
    "get_free_slots",
    "publish_availability",
    # Booking
    "accept_booking",
    "cancel_event",
    "create_booking",
    "decline_booking",
    "decrypt_calendar_event",
    "send_rsvp",
    # Negotiation
    "find_mutual_availability",
    "propose_times",
    "respond_to_proposal",
]
