# nostrcalendar

Nostr-native scheduling for OpenClaw AI agents. The Time pillar of the NSE platform.

## Build & Test

```bash
pip install -e ".[dev]"
pytest -v
```

## Structure

- `src/nostrcalendar/` — package source
  - `types.py` — AvailabilityRule, CalendarEvent, BookingRequest, RSVP, TimeSlot, DayOfWeek, BookingStatus, KIND constants, validators
  - `availability.py` — publish/query availability, compute free slots (timezone-aware)
  - `booking.py` — create/accept/decline bookings, cancel events, send RSVPs (NIP-04 encrypted DMs)
  - `negotiate.py` — agent-to-agent scheduling negotiation (propose times, respond, find mutual availability)
  - `enclave.py` — CalendarEnclave (NSE orchestrator integration — the Time pillar organ)
- `tests/` — pytest suite (29 tests)
- `clawhub/` — OpenClaw skill metadata
- `examples/` — runnable examples (publish, book, negotiate)

## Conventions

- Python 3.10+, hatchling build, ruff linter (100 char line length)
- Dependency: `nostrkey>=0.1.1` only
- Import matches package name: `pip install nostrcalendar` → `import nostrcalendar`
- All pubkeys validated as 64-char lowercase hex at every entry point
- All timestamps validated to 2020-2100 range, bools rejected
- TimeSlot, CalendarEvent, BookingRequest all enforce start < end
- RSVP status is whitelisted: accepted, declined, tentative
- AvailabilityRule: max 48 windows/day, slot_duration 1-1440, buffer 0-1440, max_per_day 1-1000
- Timezone: IANA validated, null bytes/backslash/path traversal blocked
- Relay queries capped at 1000 events (memory exhaustion prevention)
- `compute_free_slots` respects the rule's timezone (not hardcoded UTC)
- Privacy model: public envelope (times + participant pubkeys in tags) + NIP-44 encrypted content (title, description, location)
- Booking DMs use NIP-04 (kind=4) — widely supported fallback, not NIP-17
- Events from relays are NOT signature-verified — consumer responsibility (documented in _query_events)
- CalendarEnclave.create() takes no required args — matches NSE orchestrator's pillar detection pattern
- Message type tags use `nostrcalendar:` namespace (booking_request, booking_confirmation, proposal, proposal_response)
- d-tag for availability: `nostrcalendar/availability`
