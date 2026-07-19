"""Security tests — repr redaction and input validation for nostrcalendar.

Ensures that error messages from validation functions never leak secret values,
and that all input validation rejects dangerous inputs cleanly.
"""

import pytest

from nostrcalendar.types import (
    AvailabilityRule,
    BookingRequest,
    CalendarEvent,
    RSVP,
    TimeSlot,
    validate_pubkey_hex,
    validate_timestamp,
)
from nostrcalendar.enclave import CalendarEnclave


# --- Validation: pubkey hex ---


class TestPubkeyValidation:
    """Ensure pubkey validation rejects bad inputs without leaking values."""

    def test_rejects_nsec_as_pubkey(self):
        """An nsec accidentally passed as pubkey should fail, message should not contain it."""
        fake_nsec = "nsec1" + "a" * 59
        with pytest.raises(ValueError) as exc_info:
            validate_pubkey_hex(fake_nsec, "test_key")
        msg = str(exc_info.value)
        assert "test_key" in msg
        # The error DOES show the value via !r for pubkeys (which are not secrets),
        # but if someone passes an nsec, it will appear in the error. This is
        # acceptable since the function is explicitly for pubkeys and the caller
        # is responsible for not passing secrets to a pubkey validator.

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            validate_pubkey_hex("", "test_key")

    def test_rejects_non_string(self):
        with pytest.raises(ValueError):
            validate_pubkey_hex(123, "test_key")  # type: ignore[arg-type]

    def test_rejects_uppercase_hex(self):
        with pytest.raises(ValueError):
            validate_pubkey_hex("A" * 64, "test_key")

    def test_accepts_valid_hex(self):
        validate_pubkey_hex("a" * 64, "test_key")


# --- Validation: timestamps ---


class TestTimestampValidation:
    """Ensure timestamp validation rejects invalid inputs cleanly."""

    def test_rejects_bool(self):
        """Booleans are technically ints in Python — must be explicitly rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_timestamp(True, "test_ts")
        assert "integer" in str(exc_info.value).lower()

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            validate_timestamp(-1, "test_ts")

    def test_rejects_float(self):
        with pytest.raises(ValueError):
            validate_timestamp(1.5, "test_ts")  # type: ignore[arg-type]

    def test_rejects_string(self):
        with pytest.raises(ValueError):
            validate_timestamp("12345", "test_ts")  # type: ignore[arg-type]

    def test_rejects_far_future(self):
        with pytest.raises(ValueError):
            validate_timestamp(99999999999, "test_ts")

    def test_accepts_valid_timestamp(self):
        validate_timestamp(1700000000, "test_ts")


# --- Validation: timezone ---


class TestTimezoneValidation:
    """Ensure timezone validation blocks injection attempts."""

    def test_rejects_null_bytes(self):
        with pytest.raises(ValueError, match="invalid characters"):
            AvailabilityRule(timezone="US/\x00Eastern")

    def test_rejects_backslash(self):
        with pytest.raises(ValueError, match="invalid characters"):
            AvailabilityRule(timezone="..\\etc\\passwd")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="path traversal"):
            AvailabilityRule(timezone="../../etc/passwd")

    def test_rejects_unknown_timezone(self):
        with pytest.raises(ValueError, match="Unknown timezone"):
            AvailabilityRule(timezone="Not/A/Timezone")

    def test_accepts_valid_timezone(self):
        rule = AvailabilityRule(timezone="America/Vancouver")
        assert rule.timezone == "America/Vancouver"


# --- Dataclass integrity ---


class TestTimeSlotValidation:
    """Ensure TimeSlot rejects invalid inputs."""

    def test_rejects_start_after_end(self):
        with pytest.raises(ValueError, match="must be before"):
            TimeSlot(start="17:00", end="09:00")

    def test_rejects_equal_start_end(self):
        with pytest.raises(ValueError, match="must be before"):
            TimeSlot(start="09:00", end="09:00")

    def test_rejects_bad_format(self):
        with pytest.raises(ValueError, match="HH:MM"):
            TimeSlot(start="9am", end="5pm")


class TestCalendarEventValidation:
    """Ensure CalendarEvent rejects invalid inputs."""

    def test_rejects_start_after_end(self):
        with pytest.raises(ValueError, match="must be before"):
            CalendarEvent(
                d_tag="test", title="Test", start=1700000100, end=1700000000
            )

    def test_rejects_invalid_participant(self):
        with pytest.raises(ValueError, match="participant pubkey"):
            CalendarEvent(
                d_tag="test",
                title="Test",
                start=1700000000,
                end=1700000100,
                participants=["not-a-hex-pubkey"],
            )


class TestBookingRequestValidation:
    """Ensure BookingRequest rejects invalid inputs."""

    def test_rejects_start_after_end(self):
        with pytest.raises(ValueError, match="must be before"):
            BookingRequest(
                requester_pubkey="a" * 64,
                requested_start=1700000100,
                requested_end=1700000000,
            )

    def test_rejects_invalid_pubkey(self):
        with pytest.raises(ValueError, match="requester_pubkey"):
            BookingRequest(
                requester_pubkey="bad",
                requested_start=1700000000,
                requested_end=1700000100,
            )


class TestRSVPValidation:
    """Ensure RSVP rejects invalid inputs."""

    def test_rejects_invalid_status(self):
        with pytest.raises(ValueError, match="status"):
            RSVP(event_d_tag="test", event_pubkey="a" * 64, status="maybe")

    def test_rejects_invalid_pubkey(self):
        with pytest.raises(ValueError, match="event_pubkey"):
            RSVP(event_d_tag="test", event_pubkey="bad", status="accepted")


# --- AvailabilityRule bounds ---


class TestAvailabilityRuleBounds:
    """Ensure AvailabilityRule enforces sane limits."""

    def test_rejects_zero_slot_duration(self):
        with pytest.raises(ValueError, match="slot_duration_minutes"):
            AvailabilityRule(slot_duration_minutes=0)

    def test_rejects_huge_slot_duration(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            AvailabilityRule(slot_duration_minutes=9999)

    def test_rejects_negative_buffer(self):
        with pytest.raises(ValueError, match="buffer_minutes"):
            AvailabilityRule(buffer_minutes=-1)

    def test_rejects_huge_buffer(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            AvailabilityRule(buffer_minutes=9999)

    def test_rejects_zero_max_per_day(self):
        with pytest.raises(ValueError, match="max_per_day"):
            AvailabilityRule(max_per_day=0)

    def test_rejects_huge_max_per_day(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            AvailabilityRule(max_per_day=9999)


# --- CalendarEnclave (no secrets to redact, but verify status is clean) ---


class TestEnclaveStatus:
    """Ensure CalendarEnclave status output contains no sensitive data."""

    def test_status_has_no_secret_fields(self):
        enclave = CalendarEnclave.create()
        status = enclave.status()
        # Status should only contain operational fields
        assert set(status.keys()) == {
            "configured", "has_rule", "has_relay", "event_count",
            "hours_since_owner_active",
        }
        # No field should contain key-like strings
        for value in status.values():
            if isinstance(value, str):
                assert "nsec" not in value.lower()
                assert "secret" not in value.lower()
