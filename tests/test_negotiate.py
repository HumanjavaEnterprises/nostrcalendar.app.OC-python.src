"""Agent-to-agent negotiation tests with stubbed relay and availability.

Locks in the nostrkey.crypto argument order for the negotiation DMs:
    encrypt(sender_nsec, recipient_npub, plaintext)
"""

import json
from datetime import datetime

import pytest

from nostrkey.crypto import decrypt

from nostrcalendar.negotiate import propose_times, respond_to_proposal
from nostrcalendar.types import TimeSlot

RELAY_URL = "wss://relay.test"


@pytest.fixture
def stub_free_slots(monkeypatch):
    """Replace availability lookup — no live relay queries."""

    async def fake_get_free_slots(pubkey, relay_url, date):
        return [TimeSlot(start="09:00", end="10:00"), TimeSlot(start="14:00", end="15:00")]

    monkeypatch.setattr("nostrcalendar.negotiate.get_free_slots", fake_get_free_slots)


async def test_propose_times_sends_decryptable_proposal(
    alice, bob, fake_relay, stub_free_slots
):
    """propose_times sends a kind-4 DM the target agent can decrypt."""
    event_id = await propose_times(
        agent_identity=alice,
        target_pubkey=bob.public_key_hex,
        relay_url=RELAY_URL,
        dates=[datetime(2026, 8, 3), datetime(2026, 8, 4)],
        title="Planning sync",
        message="Two options this week.",
    )

    assert len(fake_relay.published) == 1
    dm = fake_relay.published[0]
    assert dm.id == event_id
    assert dm.kind == 4
    assert ["p", bob.public_key_hex] in dm.tags

    # Bob (recipient) decrypts with Alice's pubkey (sender)
    body = json.loads(decrypt(bob.private_key_hex, alice.public_key_hex, dm.content))
    assert body["type"] == "nostrcalendar:proposal"
    assert body["title"] == "Planning sync"
    assert body["proposer"] == alice.public_key_hex
    assert body["available_slots"]["2026-08-03"] == [
        {"start": "09:00", "end": "10:00"},
        {"start": "14:00", "end": "15:00"},
    ]
    assert "2026-08-04" in body["available_slots"]


async def test_respond_to_proposal_accept(alice, bob, fake_relay):
    """Accepting a proposal sends the selected slot back, decryptable by the proposer."""
    slot = TimeSlot(start="09:00", end="10:00")

    event_id = await respond_to_proposal(
        agent_identity=bob,
        proposer_pubkey=alice.public_key_hex,
        selected_date="2026-08-03",
        selected_slot=slot,
        title="Planning sync",
        relay_url=RELAY_URL,
        accept=True,
    )

    assert len(fake_relay.published) == 1
    dm = fake_relay.published[0]
    assert dm.id == event_id
    assert dm.kind == 4
    assert ["p", alice.public_key_hex] in dm.tags

    body = json.loads(decrypt(alice.private_key_hex, bob.public_key_hex, dm.content))
    assert body["type"] == "nostrcalendar:proposal_response"
    assert body["accepted"] is True
    assert body["selected_date"] == "2026-08-03"
    assert body["selected_slot"] == {"start": "09:00", "end": "10:00"}
    assert body["responder"] == bob.public_key_hex


async def test_respond_to_proposal_decline(alice, bob, fake_relay):
    """Declining a proposal nulls the slot fields and still decrypts cleanly."""
    slot = TimeSlot(start="09:00", end="10:00")

    await respond_to_proposal(
        agent_identity=bob,
        proposer_pubkey=alice.public_key_hex,
        selected_date="2026-08-03",
        selected_slot=slot,
        title="Planning sync",
        relay_url=RELAY_URL,
        accept=False,
    )

    dm = fake_relay.published[0]
    body = json.loads(decrypt(alice.private_key_hex, bob.public_key_hex, dm.content))
    assert body["accepted"] is False
    assert body["selected_date"] is None
    assert body["selected_slot"] is None
