"""Agent-to-agent scheduling negotiation over Nostr DMs.

Two AI agents, each with their own npub, negotiate a meeting time
for their humans by exchanging encrypted messages.
"""

import json
from datetime import datetime

from nostrkey import Identity
from nostrkey.relay import RelayClient
from nostrkey.crypto import encrypt

from .availability import get_free_slots
from .types import TimeSlot, validate_pubkey_hex


async def propose_times(
    agent_identity: Identity,
    target_pubkey: str,
    relay_url: str,
    dates: list[datetime],
    title: str = "Meeting",
    message: str = "",
) -> str:
    """Propose meeting times by checking the target's availability.

    The agent reads the target's published availability, finds free slots
    across the requested dates, and sends a proposal via encrypted DM.

    Args:
        agent_identity: The proposing agent's identity.
        target_pubkey: Hex pubkey of the person/agent to meet with.
        relay_url: Relay to communicate through.
        dates: List of dates to check for availability.
        title: Title for the proposed meeting.
        message: Optional context message.

    Returns:
        The event ID of the proposal DM.
    """
    validate_pubkey_hex(target_pubkey, "target_pubkey")
    # Gather free slots across all requested dates
    available: dict[str, list[dict]] = {}
    for date in dates:
        slots = await get_free_slots(target_pubkey, relay_url, date)
        if slots:
            date_key = date.strftime("%Y-%m-%d")
            available[date_key] = [s.to_dict() for s in slots]

    proposal = {
        "type": "nostrcalendar:proposal",
        "title": title,
        "message": message,
        "available_slots": available,
        "proposer": agent_identity.public_key_hex,
    }

    encrypted = encrypt(
        json.dumps(proposal),
        agent_identity.private_key_hex,
        target_pubkey,
    )

    signed = agent_identity.sign_event(
        kind=4,
        content=encrypted,
        tags=[["p", target_pubkey]],
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed)

    return signed.id


async def respond_to_proposal(
    agent_identity: Identity,
    proposer_pubkey: str,
    selected_date: str,
    selected_slot: TimeSlot,
    title: str,
    relay_url: str,
    accept: bool = True,
) -> str:
    """Respond to a meeting proposal by selecting a slot or declining.

    Args:
        agent_identity: The responding agent's identity.
        proposer_pubkey: Hex pubkey of the agent that proposed.
        selected_date: The date string (YYYY-MM-DD) of the selected slot.
        selected_slot: The TimeSlot that was selected.
        title: Meeting title.
        relay_url: Relay to communicate through.
        accept: Whether to accept or decline.

    Returns:
        The event ID of the response DM.
    """
    validate_pubkey_hex(proposer_pubkey, "proposer_pubkey")
    response = {
        "type": "nostrcalendar:proposal_response",
        "accepted": accept,
        "selected_date": selected_date if accept else None,
        "selected_slot": selected_slot.to_dict() if accept else None,
        "title": title,
        "responder": agent_identity.public_key_hex,
    }

    encrypted = encrypt(
        json.dumps(response),
        agent_identity.private_key_hex,
        proposer_pubkey,
    )

    signed = agent_identity.sign_event(
        kind=4,
        content=encrypted,
        tags=[["p", proposer_pubkey]],
    )

    async with RelayClient(relay_url) as relay:
        await relay.publish(signed)

    return signed.id


async def find_mutual_availability(
    agent_identity: Identity,
    other_pubkey: str,
    relay_url: str,
    dates: list[datetime],
) -> dict[str, list[TimeSlot]]:
    """Find mutually available time slots between two users.

    Both users must have published their availability rules. The agent
    computes the intersection of free slots.

    Args:
        agent_identity: The agent's identity (used to check its human's availability).
        other_pubkey: Hex pubkey of the other party.
        relay_url: Relay to query.
        dates: Dates to check.

    Returns:
        Dict mapping date strings to lists of mutually free TimeSlots.
    """
    validate_pubkey_hex(other_pubkey, "other_pubkey")
    mutual: dict[str, list[TimeSlot]] = {}

    for date in dates:
        own_slots = await get_free_slots(agent_identity.public_key_hex, relay_url, date)
        other_slots = await get_free_slots(other_pubkey, relay_url, date)

        if not own_slots or not other_slots:
            continue

        # Find intersection — slots that appear in both lists
        own_set = {(s.start, s.end) for s in own_slots}
        other_set = {(s.start, s.end) for s in other_slots}
        common = own_set & other_set

        if common:
            date_key = date.strftime("%Y-%m-%d")
            mutual[date_key] = [TimeSlot(start=s[0], end=s[1]) for s in sorted(common)]

    return mutual
