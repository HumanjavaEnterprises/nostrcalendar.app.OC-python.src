# Changelog

## 0.2.2 — 2026-07-17

### Fixed

- **Critical:** `encrypt()`/`decrypt()` were called with arguments in the wrong
  order everywhere in `booking.py` and `negotiate.py`. `nostrkey.crypto` expects
  `encrypt(sender_nsec, recipient_npub, plaintext)` and
  `decrypt(recipient_nsec, sender_npub, ciphertext)`, but the plaintext/ciphertext
  was being passed as the private key. Every encrypted operation —
  `create_booking`, `accept_booking`, `decline_booking`, `decrypt_calendar_event`,
  `propose_times`, `respond_to_proposal` — crashed with `ValueError` on first use
  and never published. All seven call sites reordered to match the nostrkey
  signatures.

### Added

- Test coverage for the previously untested booking and negotiation flows:
  - A→B encrypt/decrypt round-trip with two identities.
  - End-to-end `create_booking` / `accept_booking` / `decline_booking` /
    `cancel_event` / `send_rsvp` against a stubbed relay, asserting the recipient
    can actually decrypt each published payload.
  - `propose_times` / `respond_to_proposal` (accept and decline) with stubbed
    relay and availability — no live network anywhere in the suite.

## 0.2.1

- Previous release (no changelog kept before 0.2.2).
