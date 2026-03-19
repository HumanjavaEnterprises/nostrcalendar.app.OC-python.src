"""NostrCalendar — Nostr-native scheduling for OpenClaw AI agents."""

from .types import (
    AvailabilityRule,
    BookingRequest,
    BookingStatus,
    CalendarEvent,
    DayOfWeek,
    RSVP,
    TimeSlot,
    validate_pubkey_hex,
    validate_timestamp,
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
from .enclave import CalendarEnclave

__version__ = "0.2.2"

__all__ = [
    # Enclave (NSE orchestrator integration)
    "CalendarEnclave",
    # Types
    "AvailabilityRule",
    "BookingRequest",
    "BookingStatus",
    "CalendarEvent",
    "DayOfWeek",
    "RSVP",
    "TimeSlot",
    "validate_pubkey_hex",
    "validate_timestamp",
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
