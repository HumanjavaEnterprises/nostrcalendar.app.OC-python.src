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

# NostrCalendar — Sovereign Scheduling for AI Agents

Give your AI agent the ability to manage calendars, publish availability, accept bookings, and negotiate meeting times — all over Nostr relays with no centralized server.

## Install

```bash
pip install nostrcalendar
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

# Accept — publishes a calendar event + sends confirmation DM
cal_id, dm_id = await accept_booking(identity, request, relay_url)

# Decline — sends a decline DM with reason
dm_id = await decline_booking(identity, request, "Conflict with another meeting", relay_url)
```

### 5. Agent-to-Agent Negotiation

Two AI agents find mutual availability and agree on a time — no humans needed.

```python
from nostrcalendar import find_mutual_availability, propose_times
from datetime import datetime, timedelta

# Find overlapping free slots
dates = [datetime(2026, 3, d) for d in range(15, 20)]
mutual = await find_mutual_availability(my_agent, other_pubkey, relay_url, dates)

# Or send a proposal with available times
await propose_times(my_agent, other_pubkey, relay_url, dates, title="Collab sync")
```

## When to Use Each Module

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
| `find_mutual_availability()` | `dict[str, list[TimeSlot]]` | Date string → free slots |
| `propose_times()` | `str` | Event ID of proposal DM |

## Nostr NIPs Used

| NIP | Purpose |
|-----|---------|
| NIP-01 | Basic event structure and relay protocol |
| NIP-04 | Encrypted direct messages (booking requests) |
| NIP-09 | Event deletion (cancellations) |
| NIP-52 | Calendar events (kind 31923) and RSVPs (kind 31925) |
| NIP-78 | App-specific data (kind 30078 for availability rules) |

## Important Notes

- **Never hardcode an nsec in your code.** Load it from an environment variable or encrypted file using `Identity.load()`. The `nsec1...` in examples above is a placeholder.
- Slot times are interpreted in the AvailabilityRule's timezone (defaults to UTC)
- Booking requests are encrypted — only the calendar owner can read them
- Calendar event details (title, description, location) are NIP-44 encrypted — only participants can read them. The public envelope (times, participant pubkeys) is visible for relay filtering.
- The agent needs its own Nostr keypair (mutual recognition principle)
- Depends on `nostrkey` for all cryptographic operations
