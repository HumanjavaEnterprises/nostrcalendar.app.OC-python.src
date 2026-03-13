"""Booking management — create, accept, decline, and cancel bookings over Nostr.

Privacy model: calendar event details (title, description, location) are
NIP-44 encrypted in the event content field. Only participants with the
right keys can decrypt. The public envelope (start/end times, participant
pubkeys) remains visible for relay filtering and discoverability.
"""

import json
import hashlib

from nostrkey import Identity
from nostrkey.relay import RelayClient
from nostrkey.crypto import encrypt, decrypt

from .types import BookingRequest, BookingStatus, CalendarEvent, RSVP

KIND_TIME_CALENDAR_EVENT = 31923
KIND_RSVP = 31925


async def create_booking(
    identity: Identity,
    calendar_owner_pubkey: str,
    start: int,
    end: int,
    title: str,
    message: str,
    relay_url: str,
) -> str:
    """Send a booking request as an encrypted DM to the calendar owner.

    Args:
        identity: The requester's NostrKey identity.
        calendar_owner_pubkey: Hex pubkey of the person being booked.
        start: Unix timestamp for meeting start.
        end: Unix timestamp for meeting end.
        title: Title for the booking.
        message: Optional message to include.
        relay_url: Relay to send the request through.

    Returns:
        The event ID of the sent booking request.
    """
    request = BookingRequest(
        requester_pubkey=identity.public_key_hex,
        requested_start=start,
        requested_end=end,
        title=title,
        message=message,
    )

    payload = json.dumps(request.to_dict())
    encrypted = encrypt(payload, identity.private_key_hex, calendar_owner_pubkey)

    signed = identity.sign_event(
        kind=4,  # NIP-04 encrypted DM (widely supported fallback)
        content=encrypted,
        tags=[["p", calendar_owner_pubkey]],
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed)

    return signed.id


async def accept_booking(
    identity: Identity,
    request: BookingRequest,
    relay_url: str,
) -> tuple[str, str]:
    """Accept a booking request — publish an encrypted calendar event and notify the requester.

    The calendar event's public tags contain only the time range and participant
    pubkeys. The private details (title, description, location) are NIP-44
    encrypted in the content field, readable only by participants.

    Args:
        identity: The calendar owner's identity.
        request: The booking request to accept.
        relay_url: Relay to publish on.

    Returns:
        Tuple of (calendar_event_id, confirmation_dm_id).
    """
    # Generate a deterministic d-tag from the booking details
    d_tag = hashlib.sha256(
        f"{request.requester_pubkey}:{request.requested_start}:{request.requested_end}".encode()
    ).hexdigest()[:32]

    cal_event = CalendarEvent(
        d_tag=d_tag,
        title=request.title,
        start=request.requested_start,
        end=request.requested_end,
        description=request.message,
        participants=[request.requester_pubkey],
    )

    # Encrypt private details (title, description, location) for the participant
    private_content = json.dumps(cal_event.to_private_content())
    encrypted_content = encrypt(
        private_content,
        identity.private_key_hex,
        request.requester_pubkey,
    )

    # Publish the calendar event with encrypted content + public time tags
    signed_event = identity.sign_event(
        kind=KIND_TIME_CALENDAR_EVENT,
        content=encrypted_content,
        tags=cal_event.to_tags(),
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed_event)

    # Send confirmation DM
    confirmation = {
        "type": "nostrcal:booking_confirmation",
        "status": "accepted",
        "event_d_tag": d_tag,
        "start": request.requested_start,
        "end": request.requested_end,
        "title": request.title,
    }
    encrypted = encrypt(
        json.dumps(confirmation),
        identity.private_key_hex,
        request.requester_pubkey,
    )

    signed_dm = identity.sign_event(
        kind=4,
        content=encrypted,
        tags=[["p", request.requester_pubkey]],
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed_dm)

    return signed_event.id, signed_dm.id


def decrypt_calendar_event(
    identity: Identity,
    event_pubkey: str,
    encrypted_content: str,
    tags: list[list[str]],
) -> CalendarEvent:
    """Decrypt a calendar event's private content using your identity.

    Use this when you receive a calendar event from a relay and want to
    read the private details (title, description, location).

    Args:
        identity: Your NostrKey identity (must be a participant).
        event_pubkey: The hex pubkey of the event author.
        encrypted_content: The encrypted content field from the event.
        tags: The public tags from the event.

    Returns:
        A CalendarEvent with both public and private fields populated.
    """
    decrypted = decrypt(encrypted_content, identity.private_key_hex, event_pubkey)
    try:
        private_content = json.loads(decrypted)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse decrypted calendar event content as JSON: {exc}"
        ) from exc
    return CalendarEvent.from_tags_and_content(tags, private_content)


async def decline_booking(
    identity: Identity,
    request: BookingRequest,
    reason: str,
    relay_url: str,
) -> str:
    """Decline a booking request — notify the requester via encrypted DM.

    Args:
        identity: The calendar owner's identity.
        request: The booking request to decline.
        reason: Reason for declining.
        relay_url: Relay to send through.

    Returns:
        The event ID of the decline notification.
    """
    decline = {
        "type": "nostrcal:booking_confirmation",
        "status": "declined",
        "start": request.requested_start,
        "end": request.requested_end,
        "title": request.title,
        "reason": reason,
    }
    encrypted = encrypt(
        json.dumps(decline),
        identity.private_key_hex,
        request.requester_pubkey,
    )

    signed = identity.sign_event(
        kind=4,
        content=encrypted,
        tags=[["p", request.requester_pubkey]],
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed)

    return signed.id


async def cancel_event(
    identity: Identity,
    event_d_tag: str,
    relay_url: str,
) -> str:
    """Cancel a calendar event by publishing a deletion event (NIP-09).

    Args:
        identity: The calendar owner's identity.
        event_d_tag: The d-tag of the event to cancel.
        relay_url: Relay to publish on.

    Returns:
        The event ID of the deletion event.
    """
    signed = identity.sign_event(
        kind=5,
        content="Cancelled",
        tags=[["a", f"{KIND_TIME_CALENDAR_EVENT}:{identity.public_key_hex}:{event_d_tag}"]],
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed)

    return signed.id


async def send_rsvp(
    identity: Identity,
    event_d_tag: str,
    event_pubkey: str,
    status: str,
    relay_url: str,
) -> str:
    """Send an RSVP response to a calendar event (NIP-52).

    Args:
        identity: The responder's identity.
        event_d_tag: The d-tag of the calendar event.
        event_pubkey: The pubkey of the calendar event author.
        status: "accepted", "declined", or "tentative".
        relay_url: Relay to publish on.

    Returns:
        The event ID of the RSVP.
    """
    rsvp = RSVP(
        event_d_tag=event_d_tag,
        event_pubkey=event_pubkey,
        status=status,
    )

    signed = identity.sign_event(
        kind=KIND_RSVP,
        content="",
        tags=rsvp.to_tags(),
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed)

    return signed.id
