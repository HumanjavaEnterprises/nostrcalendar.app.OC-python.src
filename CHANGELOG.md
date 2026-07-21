# Changelog

## 0.2.5 — 2026-07-21

### Security

- **Transitive `cryptography` CVE fix.** `cryptography` reaches this package
  only via `nostrkey`, which previously capped `cryptography<45.0` and shipped
  the vulnerable 44.0.3 (four advisories: PYSEC-2026-35, PYSEC-2026-2141,
  GHSA-537c-gmf6-5ccf, and a related OpenSSL fix). The `nostrkey` floor is
  raised to `>=0.3.5`, whose lifted ceiling resolves `cryptography` 49.0.0.

### Changed

- Runtime dependency floor raised from `nostrkey>=0.3.4` to `nostrkey>=0.3.5`.
  Verified against the local nostrkey 0.3.5 build: full suite and `pip-audit`
  green on `cryptography` 49.

## 0.2.4 — 2026-07-19

Version-drift reconciliation. PyPI published 0.2.3 from another machine
*without* the 0.2.2 encrypt/decrypt argument-order fix, so 0.2.3 shipped the
old (broken) call order while also bumping the runtime to `nostrkey>=0.3.0`
(whose `encrypt`/`decrypt` take the key first). This release supersedes 0.2.3:
it keeps the corrected argument order from 0.2.2 and folds in the good parts of
0.2.3.

### Fixed

- Superseded PyPI 0.2.3, which regressed `booking.py`/`negotiate.py` to the
  pre-0.2.2 argument order (plaintext passed where the private key belongs).
  The corrected order — `encrypt(sender_nsec, recipient_npub, plaintext)` /
  `decrypt(recipient_nsec, sender_npub, ciphertext)` — is retained.

### Added

- `tests/test_security.py` — repr redaction, input validation, and dataclass
  bounds coverage (carried forward from 0.2.3).

### Changed

- Runtime dependency pinned to `nostrkey>=0.3.0` (matches the key-first
  `nostrkey.crypto` signatures the fixed call sites rely on).
- ClawHub metadata refreshed to the 0.2.3 wording (summary, `time-awareness`
  tag, `NOSTR_NSEC`/`NOSTR_RELAY` env descriptors, `identity` category).

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
