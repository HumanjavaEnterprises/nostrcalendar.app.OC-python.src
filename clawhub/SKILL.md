---
name: nostrcalendar
description: Nostr-native scheduling — manage availability, book meetings, negotiate times over relay
version: 0.2.0
metadata:
  openclaw:
    requires:
      bins:
        - pip
    install:
      - kind: uv
        package: nostrcalendar
        bins: []
    homepage: https://github.com/HumanjavaEnterprises/nostrcalendar.app.OC-python.src
---

# NostrCalendar -- Sovereign Scheduling for AI Agents

Give your AI agent the ability to manage calendars, publish availability, accept bookings, and negotiate meeting times -- all over Nostr relays with no centralized server. Built on NIP-52 calendar events and NIP-04 encrypted DMs. Every scheduling operation is a signed Nostr event, so agents and humans share the same protocol with full cryptographic accountability.

## Install

```bash
pip install nostrcalendar
```

Depends on `nostrkey` for all cryptographic operations (signing, encryption, identity). The `nostrkey` package is installed automatically as a dependency.

## Quickstart

Shortest path: publish your availability, then check free slots.

```python
import asyncio, os
from nostrkey import Identity
from nostrcalendar import (
    AvailabilityRule, DayOfWeek, TimeSlot,
    publish_availability, get_free_slots,
)
from datetime import datetime

identity = Identity.from_nsec(os.environ["NOSTR_NSEC"])
relay = os.environ.get("NOSTR_RELAY", "wss://relay.nostrkeep.com")

async def main():
    # 1. Publish availability
    rule = AvailabilityRule(
        slots={DayOfWeek.MONDAY: [TimeSlot("09:00", "12:00")]},
        timezone="America/Vancouver",
    )
    event_id = await publish_availability(identity, rule, relay)
    print(f"Published: {event_id}")

    # 2. Check free slots
    slots = await get_free_slots(
        pubkey_hex=identity.public_key_hex,
        relay_url=relay,
        date=datetime(2026, 3, 17),
    )
    for slot in slots:
        print(f"{slot.start} - {slot.end}")

asyncio.run(main())
```

## Core Capabilities

### 1. Publish Availability

Set your human's available hours. Stored as a replaceable Nostr event on their relay.

```python
from nostrcalendar import AvailabilityRule, DayOfWeek, TimeSlot, publish_availability
from nostrkey import Identity
import os

identity = Identity.from_nsec(os.environ["NOSTR_NSEC"])  # never hardcode
rule = AvailabilityRule(
    slots={
        DayOfWeek.MONDAY: [TimeSlot("09:00", "12:00"), TimeSlot("14:00", "17:00")],
        DayOfWeek.WEDNESDAY: [TimeSlot("10:00", "16:00")],
        DayOfWeek.FRIDAY: [TimeSlot("09:00", "12:00")],
    },
    slot_duration_minutes=30,
    buffer_minutes=15,
    max_per_day=6,
    timezone="America/Vancouver",
    title="Book a call with Vergel",
)

event_id = await publish_availability(identity, rule, "wss://relay.nostrkeep.com")
```

### 2. Check Free Slots

Query available time slots for any user on any date.

```python
from nostrcalendar import get_free_slots
from datetime import datetime

slots = await get_free_slots(
    pubkey_hex="abc123...",
    relay_url="wss://relay.nostrkeep.com",
    date=datetime(2026, 3, 15),
)
for slot in slots:
    print(f"{slot.start} - {slot.end}")
```

### 3. Create a Booking

Send a booking request as an encrypted DM to the calendar owner.

```python
from nostrcalendar import create_booking

event_id = await create_booking(
    identity=agent_identity,
    calendar_owner_pubkey="abc123...",
    start=1742054400,
    end=1742056200,
    title="Product sync",
    message="Let's review the Q1 roadmap",
    relay_url="wss://relay.nostrkeep.com",
)
```

### 4. Accept or Decline Bookings

```python
from nostrcalendar import accept_booking, decline_booking

# Accept -- publishes a calendar event + sends confirmation DM
cal_id, dm_id = await accept_booking(identity, request, relay_url)

# Decline -- sends a decline DM with reason
dm_id = await decline_booking(identity, request, "Conflict with another meeting", relay_url)
```

### 5. Agent-to-Agent Negotiation

Two AI agents find mutual availability and agree on a time -- no humans needed.

```python
from nostrcalendar import find_mutual_availability, propose_times
from datetime import datetime, timedelta

# Find overlapping free slots
dates = [datetime(2026, 3, d) for d in range(15, 20)]
mutual = await find_mutual_availability(my_agent, other_pubkey, relay_url, dates)

# Or send a proposal with available times
await propose_times(my_agent, other_pubkey, relay_url, dates, title="Collab sync")
```

### When to Use Each Module

| Task | Module | Function |
|------|--------|----------|
| Set available hours | `availability` | `publish_availability` |
| Check someone's openings | `availability` | `get_free_slots` |
| Request a meeting | `booking` | `create_booking` |
| Confirm a meeting | `booking` | `accept_booking` |
| Decline a meeting | `booking` | `decline_booking` |
| Cancel a meeting | `booking` | `cancel_event` |
| RSVP to an event | `booking` | `send_rsvp` |
| Find mutual free time | `negotiate` | `find_mutual_availability` |
| Propose times to another agent | `negotiate` | `propose_times` |
| Respond to a proposal | `negotiate` | `respond_to_proposal` |

## Response Format

### TimeSlot (returned by `get_free_slots()`)

| Field | Type | Description |
|-------|------|-------------|
| `start` | `str` | Start time in HH:MM format |
| `end` | `str` | End time in HH:MM format |

### BookingRequest (from DMs)

| Field | Type | Description |
|-------|------|-------------|
| `requester_pubkey` | `str` | Hex pubkey of the person requesting |
| `requested_start` | `int` | Unix timestamp |
| `requested_end` | `int` | Unix timestamp |
| `title` | `str` | Meeting title |
| `message` | `str` | Optional message from requester |
| `status` | `BookingStatus` | PENDING, ACCEPTED, DECLINED, or CANCELLED |

### CalendarEvent (from `accept_booking()`)

| Field | Type | Description |
|-------|------|-------------|
| `d_tag` | `str` | Unique replaceable event identifier |
| `title` | `str` | Event title (encrypted in content) |
| `start` | `int` | Unix timestamp |
| `end` | `int` | Unix timestamp |
| `location` | `str` | Optional (encrypted) |
| `description` | `str` | Optional (encrypted) |
| `participants` | `list[str]` | Hex pubkeys of invited participants |

### Return Types by Function

| Function | Returns | Description |
|----------|---------|-------------|
| `publish_availability()` | `str` | Event ID |
| `get_free_slots()` | `list[TimeSlot]` | Available slots (empty if none) |
| `get_availability()` | `AvailabilityRule \| None` | Published rules, or None |
| `create_booking()` | `str` | Event ID of booking request DM |
| `accept_booking()` | `tuple[str, str]` | (calendar_event_id, confirmation_dm_id) |
| `decline_booking()` | `str` | Event ID of decline DM |
| `cancel_event()` | `str` | Event ID of deletion (NIP-09) |
| `find_mutual_availability()` | `dict[str, list[TimeSlot]]` | Date string -> free slots |
| `propose_times()` | `str` | Event ID of proposal DM |

## Common Patterns

### Async Usage

All network functions are async. Wrap in `asyncio.run()` for scripts, or `await` directly inside an async context.

```python
import asyncio

async def schedule():
    slots = await get_free_slots(pubkey, relay, date)
    if slots:
        await create_booking(identity, pubkey, slots[0].start, slots[0].end,
                             title="Sync", relay_url=relay)

asyncio.run(schedule())
```

### Error Handling

```python
try:
    event_id = await create_booking(identity, pubkey, start, end,
                                    title="Sync", relay_url=relay)
except ValueError as e:
    print(f"Validation failed: {e}")  # bad pubkey, timestamps, etc.
except ConnectionError as e:
    print(f"Relay unreachable: {e}")
```

### Environment Variable for nsec

```python
import os
from nostrkey import Identity

# Preferred: load from environment
identity = Identity.from_nsec(os.environ["NOSTR_NSEC"])

# The agent needs its own Nostr keypair (mutual recognition principle)
```

### Timezone Handling

Slot times are interpreted in the AvailabilityRule's timezone (defaults to UTC). Use IANA timezone strings.

```python
rule = AvailabilityRule(
    slots={DayOfWeek.MONDAY: [TimeSlot("09:00", "17:00")]},
    timezone="America/Vancouver",  # IANA timezone
)
```

`compute_free_slots` respects the rule's timezone -- it is not hardcoded to UTC.

## Security

- **Never hardcode an nsec in your code.** Load it from an environment variable or encrypted file using `Identity.load()`. Any `nsec1...` values in examples are placeholders.
- **Booking requests are encrypted.** They are sent as NIP-04 encrypted DMs (kind=4) -- only the calendar owner can read them.
- **Calendar event privacy model:** The public envelope (times and participant pubkeys in tags) is visible for relay filtering. The content (title, description, location) is NIP-44 encrypted -- only participants can decrypt it.
- **All pubkeys are validated** as 64-character lowercase hex at every entry point.
- **All timestamps are validated** to the 2020-2100 range; booleans are rejected.
- **Relay queries are capped** at 1000 events to prevent memory exhaustion.

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOSTR_NSEC` | Yes | Your nsec private key (bech32 or hex) |
| `NOSTR_RELAY` | No | Relay URL (default: `wss://relay.nostrkeep.com`) |

### AvailabilityRule Defaults

| Parameter | Default | Range |
|-----------|---------|-------|
| `slot_duration_minutes` | 30 | 1--1440 |
| `buffer_minutes` | 15 | 0--1440 |
| `max_per_day` | 8 | 1--1000 |
| `timezone` | `UTC` | Any valid IANA timezone |

Maximum 48 time windows per day.

## Nostr NIPs Used

| NIP | Purpose |
|-----|---------|
| NIP-01 | Basic event structure and relay protocol |
| NIP-04 | Encrypted direct messages (booking requests) |
| NIP-09 | Event deletion (cancellations) |
| NIP-52 | Calendar events (kind 31923) and RSVPs (kind 31925) |
| NIP-78 | App-specific data (kind 30078 for availability rules) |

## Links

- **PyPI:** https://pypi.org/project/nostrcalendar/
- **GitHub:** https://github.com/HumanjavaEnterprises/nostrcalendar.app.OC-python.src
- **ClawHub:** https://clawhub.com/skills/nostrcalendar
- **License:** MIT
