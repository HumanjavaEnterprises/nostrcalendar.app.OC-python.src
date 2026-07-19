"""End-to-end booking flow tests with a stubbed relay.

These lock in the nostrkey.crypto argument order:
    encrypt(sender_nsec, recipient_npub, plaintext)
    decrypt(recipient_nsec, sender_npub, ciphertext)
A regression that swaps the arguments makes every one of these fail.
"""

import json

from nostrkey.crypto import encrypt, decrypt

from nostrcalendar.booking import (
    accept_booking,
    cancel_event,
    create_booking,
    decline_booking,
    decrypt_calendar_event,
    send_rsvp,
)
from nostrcalendar.types import (
    BookingRequest,
    KIND_RSVP,
    KIND_TIME_CALENDAR_EVENT,
)

RELAY_URL = "wss://relay.test"
START = 1_780_000_000  # 2026-05-28
END = START + 3600


def _booking_request(alice) -> BookingRequest:
    return BookingRequest(
        requester_pubkey=alice.public_key_hex,
        requested_start=START,
        requested_end=END,
        title="Coffee chat",
        message="Let's sync on the Q3 plan.",
    )


def test_encrypt_decrypt_roundtrip(alice, bob):
    """A encrypts to B, B decrypts — the original JSON comes back intact."""
    payload = json.dumps({"type": "nostrcalendar:test", "answer": 42, "note": "héllo"})

    ciphertext = encrypt(alice.private_key_hex, bob.public_key_hex, payload)
    assert ciphertext != payload

    recovered = decrypt(bob.private_key_hex, alice.public_key_hex, ciphertext)
    assert recovered == payload
    assert json.loads(recovered)["answer"] == 42


async def test_create_booking_publishes_decryptable_dm(alice, bob, fake_relay):
    """create_booking sends a kind-4 DM the calendar owner can decrypt."""
    event_id = await create_booking(
        identity=alice,
        calendar_owner_pubkey=bob.public_key_hex,
        start=START,
        end=END,
        title="Coffee chat",
        message="Let's sync on the Q3 plan.",
        relay_url=RELAY_URL,
    )

    assert len(fake_relay.published) == 1
    dm = fake_relay.published[0]
    assert dm.id == event_id
    assert dm.kind == 4
    assert ["p", bob.public_key_hex] in dm.tags

    # Bob (recipient) decrypts using Alice's pubkey (sender)
    plaintext = decrypt(bob.private_key_hex, alice.public_key_hex, dm.content)
    body = json.loads(plaintext)
    assert body["type"] == "nostrcalendar:booking_request"
    assert body["requester"] == alice.public_key_hex
    assert body["start"] == START
    assert body["end"] == END
    assert body["title"] == "Coffee chat"


async def test_accept_booking_full_flow(alice, bob, fake_relay):
    """accept_booking publishes an encrypted calendar event + confirmation DM,
    and the requester can decrypt both — including via decrypt_calendar_event."""
    request = _booking_request(alice)

    cal_event_id, dm_id = await accept_booking(
        identity=bob,
        request=request,
        relay_url=RELAY_URL,
    )

    assert len(fake_relay.published) == 2
    cal_event, dm = fake_relay.published

    # Calendar event: NIP-52 kind, encrypted content, public time tags
    assert cal_event.id == cal_event_id
    assert cal_event.kind == KIND_TIME_CALENDAR_EVENT

    # Alice decrypts the private details through the library API
    parsed = decrypt_calendar_event(
        identity=alice,
        event_pubkey=bob.public_key_hex,
        encrypted_content=cal_event.content,
        tags=cal_event.tags,
    )
    assert parsed.title == "Coffee chat"
    assert parsed.description == "Let's sync on the Q3 plan."
    assert parsed.start == START
    assert parsed.end == END
    assert alice.public_key_hex in parsed.participants

    # Confirmation DM: kind 4, addressed to Alice, decryptable by Alice
    assert dm.id == dm_id
    assert dm.kind == 4
    assert ["p", alice.public_key_hex] in dm.tags
    confirmation = json.loads(
        decrypt(alice.private_key_hex, bob.public_key_hex, dm.content)
    )
    assert confirmation["type"] == "nostrcalendar:booking_confirmation"
    assert confirmation["status"] == "accepted"
    assert confirmation["start"] == START
    assert confirmation["end"] == END


async def test_decline_booking_dm_decrypts_with_reason(alice, bob, fake_relay):
    """decline_booking sends a DM the requester can decrypt, with the reason."""
    request = _booking_request(alice)

    event_id = await decline_booking(
        identity=bob,
        request=request,
        reason="Out of office that week",
        relay_url=RELAY_URL,
    )

    assert len(fake_relay.published) == 1
    dm = fake_relay.published[0]
    assert dm.id == event_id
    assert dm.kind == 4
    assert ["p", alice.public_key_hex] in dm.tags

    body = json.loads(decrypt(alice.private_key_hex, bob.public_key_hex, dm.content))
    assert body["status"] == "declined"
    assert body["reason"] == "Out of office that week"
    assert body["title"] == "Coffee chat"


async def test_cancel_event_publishes_deletion(bob, fake_relay):
    """cancel_event publishes a NIP-09 deletion referencing the event address."""
    event_id = await cancel_event(bob, "abc123", RELAY_URL)

    assert len(fake_relay.published) == 1
    deletion = fake_relay.published[0]
    assert deletion.id == event_id
    assert deletion.kind == 5
    assert ["a", f"{KIND_TIME_CALENDAR_EVENT}:{bob.public_key_hex}:abc123"] in deletion.tags


async def test_send_rsvp_publishes_rsvp_event(alice, bob, fake_relay):
    """send_rsvp publishes a NIP-52 RSVP event."""
    event_id = await send_rsvp(
        identity=alice,
        event_d_tag="abc123",
        event_pubkey=bob.public_key_hex,
        status="accepted",
        relay_url=RELAY_URL,
    )

    assert len(fake_relay.published) == 1
    rsvp = fake_relay.published[0]
    assert rsvp.id == event_id
    assert rsvp.kind == KIND_RSVP


def test_decrypt_calendar_event_rejects_garbage_plaintext(alice, bob):
    """Decrypted-but-not-JSON content raises a clear ValueError."""
    ciphertext = encrypt(bob.private_key_hex, alice.public_key_hex, "not json at all")
    try:
        decrypt_calendar_event(
            identity=alice,
            event_pubkey=bob.public_key_hex,
            encrypted_content=ciphertext,
            tags=[["d", "x"], ["start", str(START)], ["end", str(END)]],
        )
    except ValueError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-JSON plaintext")
