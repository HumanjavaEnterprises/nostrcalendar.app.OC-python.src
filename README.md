# NostrCalendar for OpenClaw

**Give your AI agent a calendar.**

Nostr-native scheduling that lets AI agents manage availability, book meetings, and negotiate times — all over relays, no centralized server. Think Calendly, but sovereign.

## Why?

Scheduling is one of the most common things humans delegate. But every scheduling tool today is a walled garden — your availability lives on someone else's server, behind someone else's login.

NostrCalendar stores availability as Nostr events on your relay. Your AI agent reads and writes these events with its own keypair. Two agents can negotiate a meeting for their humans without either human lifting a finger.

**What your agent can do:**
- Publish and update availability schedules
- Check anyone's free slots on any relay
- Send encrypted booking requests via DM
- Accept, decline, or cancel meetings
- Negotiate times with other agents (agent-to-agent)
- Find mutual availability across multiple days

## Install

```bash
pip install nostrcalendar
```

## Quick Start

```python
import asyncio
from nostrkey import Identity
from nostrcal import (
    AvailabilityRule, DayOfWeek, TimeSlot,
    publish_availability, get_free_slots, create_booking,
)
from datetime import datetime

async def main():
    identity = Identity.generate()
    relay = "wss://relay.nostrkeep.com"

    # Publish availability
    rule = AvailabilityRule(
        slots={
            DayOfWeek.MONDAY: [TimeSlot("09:00", "12:00"), TimeSlot("14:00", "17:00")],
            DayOfWeek.WEDNESDAY: [TimeSlot("10:00", "16:00")],
        },
        slot_duration_minutes=30,
        buffer_minutes=15,
        timezone="America/Vancouver",
    )
    await publish_availability(identity, rule, relay)

    # Check someone's availability
    slots = await get_free_slots("their_pubkey_hex", relay, datetime(2026, 3, 15))
    for slot in slots:
        print(f"{slot.start} - {slot.end}")

asyncio.run(main())
```

## Agent-to-Agent Negotiation

```python
from nostrcal import find_mutual_availability
from datetime import datetime, timedelta

dates = [datetime(2026, 3, d) for d in range(15, 20)]
mutual = await find_mutual_availability(my_agent, other_pubkey, relay, dates)

for date, slots in mutual.items():
    print(f"{date}: {', '.join(f'{s.start}-{s.end}' for s in slots)}")
```

## NIPs Implemented

| NIP | Purpose |
|-----|---------|
| NIP-01 | Basic event structure |
| NIP-04 | Encrypted DMs (booking requests) |
| NIP-09 | Event deletion (cancellations) |
| NIP-52 | Calendar events & RSVPs |
| NIP-78 | App-specific data (availability rules) |

## OpenClaw Skill

NostrCalendar is published on [ClawHub](https://loginwithnostr.com/openclaw) as the `nostrcalendar` skill. Install it in your OpenClaw agent to give it scheduling capabilities.

## License

MIT — Humanjava Enterprises Inc.
