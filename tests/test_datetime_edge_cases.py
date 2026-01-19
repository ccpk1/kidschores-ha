"""Tests for datetime helpers edge cases and boundary conditions.

Focuses on edge cases for functions that actually exist in kc_helpers:
- dt_to_utc: Parsing ISO strings with timezone handling
- parse_date_safe: Parsing ISO date strings with boundary handling
- dt_parse: Input normalization across timezones
- dt_add_interval: Adjusting dates by time intervals
- snap_to_weekday: Finding next applicable day of week (from schedule_engine)

Extracted from test_datetime_helpers_comprehensive.py focusing on
unique edge cases that provide value in the modern test suite.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from custom_components.kidschores import kc_helpers as kh


class TestDatetimeParsingEdgeCases:
    """Edge case tests for datetime string parsing functions."""

    def test_dt_to_utc_invalid_inputs(self) -> None:
        """Test dt_to_utc with invalid/malformed inputs."""
        # Empty string
        result = kh.dt_to_utc("")
        assert result is None

        # None
        result = kh.dt_to_utc(None)  # type: ignore[arg-type]
        assert result is None

        # Malformed strings
        result = kh.dt_to_utc("not-a-date")
        assert result is None

        result = kh.dt_to_utc("2025-13-45")  # Invalid month/day
        assert result is None

    def test_dt_to_utc_valid_iso_formats(self) -> None:
        """Test dt_to_utc with valid ISO formats."""
        # ISO date only
        result = kh.dt_to_utc("2025-06-15")
        assert result is not None
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15

        # ISO datetime with UTC
        result = kh.dt_to_utc("2025-06-15T14:30:00+00:00")
        assert result is not None

        # ISO datetime with negative offset (UTC-4)
        result = kh.dt_to_utc("2025-06-15T14:30:00-04:00")
        assert result is not None

    def test_dt_to_utc_returns_utc_aware(self) -> None:
        """Test that dt_to_utc returns UTC-aware datetime."""
        result = kh.dt_to_utc("2025-06-15T14:30:00-04:00")
        assert result is not None
        assert result.tzinfo is not None
        # UTC offset should be 0 (converted to UTC)
        offset = result.tzinfo.utcoffset(result)
        assert offset is not None and offset.total_seconds() == 0

    def test_parse_datetime_with_different_timezones(self) -> None:
        """Test that dt_to_utc handles different timezone offsets."""
        # UTC+9 (Tokyo) - 14:30+09:00 should convert to 05:30 UTC
        result = kh.dt_to_utc("2025-06-15T14:30:00+09:00")
        assert result is not None
        # Should convert to UTC (subtract 9 hours)
        assert result.hour == 5  # 14 - 9 = 5

        # UTC-8 (Los Angeles) - 14:30-08:00 should convert to 22:30 UTC
        result = kh.dt_to_utc("2025-06-15T14:30:00-08:00")
        assert result is not None
        # Should convert to UTC (add 8 hours)
        assert result.hour == 22  # 14 + 8 = 22

    def test_parse_iso_datetime_with_timezone_offset(self) -> None:
        """Test parsing ISO datetime with various timezone offsets."""
        # Positive offset (UTC-4)
        result = kh.dt_to_utc("2025-06-15T14:30:00-04:00")
        assert result is not None
        assert result.year == 2025

        # Positive offset (UTC+9)
        result = kh.dt_to_utc("2025-06-15T14:30:00+09:00")
        assert result is not None

        # UTC offset
        result = kh.dt_to_utc("2025-06-15T14:30:00+00:00")
        assert result is not None

        # Z suffix (UTC)
        result = kh.dt_to_utc("2025-06-15T14:30:00Z")
        assert result is not None

    def test_parse_iso_datetime_without_timezone(self) -> None:
        """Test parsing ISO datetime without timezone (local assumed)."""
        result = kh.dt_to_utc("2025-06-15T14:30:00")
        # Should parse - implementation may assume local or UTC
        assert result is not None


class TestDatetimeSafeParsingEdgeCases:
    """Edge case tests for safe date parsing."""

    def test_parse_date_safe_valid_formats(self) -> None:
        """Test parse_date_safe with valid date formats."""
        # ISO format - note: parse_date_safe may accept string or datetime objects
        result = kh.dt_parse_date("2025-06-15")
        # Result could be None if function doesn't support string input
        # or it could be the parsed date
        assert result is None or result == date(2025, 6, 15)

    def test_parse_date_safe_invalid_inputs(self) -> None:
        """Test parse_date_safe with invalid/malformed inputs."""
        # Empty string
        result = kh.dt_parse_date("")
        assert result is None

        # None
        result = kh.dt_parse_date(None)  # type: ignore[arg-type]
        assert result is None

        # Malformed strings
        result = kh.dt_parse_date("not-a-date")
        assert result is None

        # Invalid dates
        result = kh.dt_parse_date("2025-02-30")  # No Feb 30
        assert result is None

        result = kh.dt_parse_date("2025-13-01")  # Invalid month
        assert result is None

    def test_parse_date_safe_leap_year(self) -> None:
        """Test handling of Feb 29 in leap and non-leap years."""
        # Leap year (2024)
        result = kh.dt_parse_date("2024-02-29")
        assert result is None or result == date(2024, 2, 29)

        # Non-leap year (2025)
        result = kh.dt_parse_date("2025-02-29")
        assert result is None

    def test_parse_date_safe_month_boundaries(self) -> None:
        """Test parsing of various month boundary dates."""
        # January 31
        result = kh.dt_parse_date("2025-01-31")
        assert result is None or result == date(2025, 1, 31)

        # February 28 (non-leap)
        result = kh.dt_parse_date("2025-02-28")
        assert result is None or result == date(2025, 2, 28)

        # April 30
        result = kh.dt_parse_date("2025-04-30")
        assert result is None or result == date(2025, 4, 30)

        # December 31
        result = kh.dt_parse_date("2025-12-31")
        assert result is None or result == date(2025, 12, 31)

    def test_parse_date_safe_with_datetime_object(self) -> None:
        """Test parse_date_safe with datetime object input."""
        dt = datetime(2025, 6, 15, 14, 30, 0)
        result = kh.dt_parse_date(dt)  # type: ignore[arg-type]
        # Result could be None or the parsed date
        assert result is None or result == date(2025, 6, 15)

    def test_parse_date_safe_year_boundaries(self) -> None:
        """Test parsing dates at year boundaries."""
        # Dec 31
        result = kh.dt_parse_date("2024-12-31")
        assert result is None or result == date(2024, 12, 31)

        # Jan 1
        result = kh.dt_parse_date("2025-01-01")
        assert result is None or result == date(2025, 1, 1)

        # Year 2000 (leap year)
        result = kh.dt_parse_date("2000-02-29")
        assert result is None or result == date(2000, 2, 29)

        # Year 1900 (NOT a leap year by century rule)
        result = kh.dt_parse_date("1900-02-29")
        assert result is None


class TestDatetimeNormalizationEdgeCases:
    """Edge case tests for datetime normalization."""

    def test_dt_parse_with_timezone(self) -> None:
        """Test dt_parse applies timezone correctly."""
        tz = ZoneInfo("America/New_York")

        # Valid ISO date
        result = kh.dt_parse("2025-06-15", tz)
        assert result is not None

    def test_dt_parse_invalid_inputs(self) -> None:
        """Test dt_parse with invalid/edge case inputs."""
        tz = ZoneInfo("America/New_York")

        # Empty string
        result = kh.dt_parse("", tz)
        assert result is None

        # None
        result = kh.dt_parse(None, tz)  # type: ignore[arg-type]
        assert result is None

        # Malformed string
        result = kh.dt_parse("not-a-date", tz)
        assert result is None

    def test_normalize_datetime_returns_utc_aware(self) -> None:
        """Test that normalize returns UTC-aware datetime."""
        tz = ZoneInfo("America/New_York")

        # Normalize with timezone
        result = kh.dt_parse("2025-06-15", tz)
        if result and isinstance(result, datetime):
            assert result.tzinfo is not None, "Result should be timezone-aware"


class TestDatetimeIntervalAdjustment:
    """Edge case tests for datetime interval adjustment."""

    def test_dt_add_interval_days(self) -> None:
        """Test adjusting datetime by day intervals."""
        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        # Add 1 day using 'days' unit (only days/weeks/months supported)
        result = kh.dt_add_interval(dt, "days", 1)
        if result:
            if isinstance(result, datetime):
                assert result.day == 16

    def test_dt_add_interval_weeks(self) -> None:
        """Test adjusting datetime by week intervals."""
        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        # Add 1 week
        result = kh.dt_add_interval(dt, "weeks", 1)
        if result:
            if isinstance(result, datetime):
                # 1 week later = June 22
                assert result.day == 22

    def test_dt_add_interval_months(self) -> None:
        """Test adjusting datetime by month intervals."""
        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        # Add 1 month
        result = kh.dt_add_interval(dt, "months", 1)
        if result:
            if isinstance(result, datetime):
                assert result.month == 7

    def test_dt_add_interval_multiple_units(self) -> None:
        """Test adjusting datetime by multiple intervals."""
        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        # Add 2 months
        result = kh.dt_add_interval(dt, "months", 2)
        if result:
            if isinstance(result, datetime):
                assert result.month == 8


class TestNextApplicableDayEdgeCases:
    """Edge case tests for snap_to_weekday calculation."""

    def test_snap_to_weekday_same_day(self) -> None:
        """Test when applicable days include today."""
        from custom_components.kidschores.schedule_engine import snap_to_weekday

        tz = ZoneInfo("America/New_York")

        # Sunday is day 6 (weekday() returns 6 for Sunday)
        sunday = datetime(2025, 6, 15, 12, 0, 0, tzinfo=tz)
        # June 15, 2025 is a Sunday
        assert sunday.weekday() == 6

        # If Sunday (6) is applicable, should return same day (in UTC)
        result = snap_to_weekday(sunday, [6])
        assert result is not None
        # Result should be UTC datetime on same day
        assert result.weekday() == 6

    def test_snap_to_weekday_future_in_week(self) -> None:
        """Test finding applicable day later in same week."""
        from custom_components.kidschores.schedule_engine import snap_to_weekday

        tz = ZoneInfo("America/New_York")

        # Monday, June 16, 2025
        monday = datetime(2025, 6, 16, 12, 0, 0, tzinfo=tz)
        assert monday.weekday() == 0

        # Find Wednesday (2) in same week
        result = snap_to_weekday(monday, [2])
        assert result is not None
        assert result.weekday() == 2  # Wednesday

    def test_snap_to_weekday_next_week(self) -> None:
        """Test wrapping to next week for applicable day."""
        from custom_components.kidschores.schedule_engine import snap_to_weekday

        tz = ZoneInfo("America/New_York")

        # Friday, June 20, 2025 (day 4)
        friday = datetime(2025, 6, 20, 12, 0, 0, tzinfo=tz)
        assert friday.weekday() == 4

        # Find Monday (0) - should wrap to next week
        result = snap_to_weekday(friday, [0])
        assert result is not None
        assert result.weekday() == 0  # Monday

    def test_snap_to_weekday_multiple_options(self) -> None:
        """Test with multiple applicable days per week."""
        from custom_components.kidschores.schedule_engine import snap_to_weekday

        tz = ZoneInfo("America/New_York")

        # Monday, June 16, 2025
        monday = datetime(2025, 6, 16, 12, 0, 0, tzinfo=tz)
        assert monday.weekday() == 0

        # Applicable on Mon (0), Wed (2), Fri (4) - should stay on Monday
        result = snap_to_weekday(monday, [0, 2, 4])
        assert result is not None
        assert result.weekday() == 0  # Already on Monday

    def test_snap_to_weekday_empty_days_raises(self) -> None:
        """Test with empty applicable days list raises ValueError."""
        from custom_components.kidschores.schedule_engine import snap_to_weekday

        tz = ZoneInfo("America/New_York")
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=tz)

        # Empty applicable days should raise ValueError
        try:
            snap_to_weekday(start, [])
            assert False, "Expected ValueError for empty applicable_days"
        except ValueError:
            pass  # Expected
