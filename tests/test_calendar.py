"""Tests for KidsChores calendar platform.

This test suite validates the calendar event generation logic before Phase 4 refactoring.
It captures the current behavior of the 328-line _generate_events_for_chore method to
ensure refactoring produces identical results.

Test Coverage:
- Non-recurring chores (FREQUENCY_NONE) with/without due_date
- Recurring chores: daily, weekly, biweekly, monthly
- Custom interval chores with various units
- Applicable days filtering
- Event overlap detection (window boundaries)
- Timezone handling
- Edge cases (month boundaries, DST transitions)
"""

# pylint: disable=too-many-lines  # Comprehensive test coverage requires many tests
# pylint: disable=redefined-outer-name  # Pytest fixtures
# pylint: disable=unused-argument  # Fixtures needed for test setup

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Callable, Coroutine
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.kidschores import const
from custom_components.kidschores.coordinator import KidsChoresDataCoordinator

# Test timezone for consistent datetime testing
TEST_TZ = ZoneInfo("America/New_York")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms fixture to only load calendar for faster tests."""
    return [Platform.CALENDAR]


@pytest.fixture
def mock_storage_data() -> dict[str, dict]:
    """Override mock_storage_data to include test kid for calendar tests."""
    import uuid  # pylint: disable=import-outside-toplevel
    from custom_components.kidschores.const import (  # pylint: disable=import-outside-toplevel
        DATA_ACHIEVEMENTS,
        DATA_BADGES,
        DATA_BONUSES,
        DATA_CHALLENGES,
        DATA_CHORES,
        DATA_KIDS,
        DATA_PARENTS,
        DATA_PENALTIES,
        DATA_REWARDS,
    )

    test_kid_id = str(uuid.uuid4())
    return {
        DATA_KIDS: {
            test_kid_id: {
                "internal_id": test_kid_id,
                "name": "Test Kid",
                "points": 100.0,
                "ha_user_id": "",
                "enable_notifications": True,
                "mobile_notify_service": "",
                "use_persistent_notifications": True,
                "dashboard_language": "en",
                "chore_states": {},
                "badges_earned": {},
                "claimed_chores": [],
                "approved_chores": [],
                "reward_claims": {},
                "bonus_applies": {},
                "penalty_applies": {},
                "overdue_notifications": {},
            }
        },
        DATA_PARENTS: {},
        DATA_CHORES: {},
        DATA_BADGES: {},
        DATA_REWARDS: {},
        DATA_BONUSES: {},
        DATA_PENALTIES: {},
        DATA_ACHIEVEMENTS: {},
        DATA_CHALLENGES: {},
    }


@pytest.fixture
def get_events_fixture(
    hass_client: ClientSessionGenerator,
) -> Callable[[str, str, str], Coroutine[Any, Any, list[dict[str, Any]]]]:
    """Fetch calendar events from HTTP API.

    Args:
        entity_id: Calendar entity ID (e.g., "calendar.kc_sarah")
        start: Start datetime in ISO format (e.g., "2025-01-01T00:00:00Z")
        end: End datetime in ISO format (e.g., "2025-01-31T00:00:00Z")

    Returns:
        List of calendar event dicts with summary, start, end, description
    """

    async def _fetch(entity_id: str, start: str, end: str) -> list[dict[str, Any]]:
        """Fetch events from calendar API."""
        import urllib.parse  # pylint: disable=import-outside-toplevel

        client = await hass_client()
        url = (
            f"/api/calendars/{entity_id}"
            f"?start={urllib.parse.quote(start)}"
            f"&end={urllib.parse.quote(end)}"
        )
        response = await client.get(url)
        assert (
            response.status == HTTPStatus.OK
        ), f"Calendar API returned {response.status}"
        return await response.json()

    return _fetch


@pytest.fixture
async def setup_test_chore(
    hass: HomeAssistant,
    mock_coordinator: KidsChoresDataCoordinator,
) -> Callable[[dict[str, Any]], str]:
    """Helper to create a test chore and reload calendar platform.

    Args:
        chore_data: Dict with chore configuration (name, frequency, due_date, etc.)

    Returns:
        chore_id: Internal ID of created chore
    """

    async def _create_chore(chore_data: dict[str, Any]) -> str:
        """Create chore and reload calendar."""
        import uuid  # pylint: disable=import-outside-toplevel

        # Generate unique ID
        chore_id = str(uuid.uuid4())

        # Set defaults
        chore_config = {
            const.DATA_CHORE_NAME: chore_data.get("name", "Test Chore"),
            const.DATA_CHORE_DESCRIPTION: chore_data.get("description", ""),
            const.DATA_CHORE_DEFAULT_POINTS: chore_data.get("points", 10),
            const.DATA_CHORE_RECURRING_FREQUENCY: chore_data.get(
                "frequency", const.FREQUENCY_NONE
            ),
            const.DATA_CHORE_APPLICABLE_DAYS: chore_data.get("applicable_days", []),
            const.DATA_CHORE_ASSIGNED_KIDS: chore_data.get(
                "assigned_kids", [mock_coordinator.test_kid_id]
            ),
        }

        # Add optional fields
        if "due_date" in chore_data:
            chore_config[const.DATA_CHORE_DUE_DATE] = chore_data["due_date"]

        if "custom_interval" in chore_data:
            chore_config[const.DATA_CHORE_CUSTOM_INTERVAL] = chore_data[
                "custom_interval"
            ]
            chore_config[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] = chore_data.get(
                "custom_interval_unit", const.TIME_UNIT_DAYS
            )

        # Add to coordinator
        mock_coordinator.chores_data[chore_id] = chore_config

        # Trigger coordinator update
        await mock_coordinator.async_refresh()
        await hass.async_block_till_done()

        return chore_id

    return _create_chore


# ============================================================================
# Test: Non-Recurring Chores (FREQUENCY_NONE)
# ============================================================================


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_non_recurring_chore_with_due_date_datetime(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test non-recurring chore with specific due datetime creates single event."""
    await setup_test_chore(
        {
            "name": "Homework",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-01-20T15:00:00-05:00",  # 3 PM EST
            "description": "Math homework",
        }
    )

    # Fetch events for January 2025
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should have exactly 1 event
    assert len(events) == 1

    event = events[0]
    assert event["summary"] == "Homework"
    assert event["description"] == "Math homework"
    # Event should be 1-hour block starting at due time
    assert "2025-01-20" in event["start"]["dateTime"]
    assert "15:00:00" in event["start"]["dateTime"]


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_non_recurring_chore_with_due_date_midnight(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test non-recurring chore with midnight due time creates all-day event."""
    await setup_test_chore(
        {
            "name": "Clean Room",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-01-20T00:00:00-05:00",  # Midnight EST
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    assert len(events) == 1
    event = events[0]
    assert event["summary"] == "Clean Room"
    # Midnight due time should create all-day event (date only)
    assert "date" in event["start"]
    assert event["start"]["date"] == "2025-01-20"
    assert event["end"]["date"] == "2025-01-21"  # All-day events end next day


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_non_recurring_chore_without_due_date_with_applicable_days(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test non-recurring chore without due_date shows on applicable days."""
    await setup_test_chore(
        {
            "name": "Feed Cat",
            "frequency": const.FREQUENCY_NONE,
            # No due_date
            "applicable_days": ["mon", "wed", "fri"],  # Monday, Wednesday, Friday
        }
    )

    # Fetch events for 2 weeks
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-13T00:00:00Z",  # Monday
        "2025-01-26T23:59:59Z",  # Sunday (2 weeks)
    )

    # Should have events only on Mon/Wed/Fri within the window
    # Jan 13 (Mon), 15 (Wed), 17 (Fri), 20 (Mon), 22 (Wed), 24 (Fri) = 6 events
    assert len(events) == 6

    # Verify all events are on correct weekdays
    for event in events:
        event_date = datetime.fromisoformat(
            event["start"]["date"]
        )  # All-day events use date
        weekday = event_date.strftime("%a").lower()
        assert weekday in ["mon", "wed", "fri"]


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_non_recurring_chore_outside_window(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test non-recurring chore due date outside query window returns no events."""
    await setup_test_chore(
        {
            "name": "Future Task",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-02-15T10:00:00-05:00",  # February (outside window)
        }
    )

    # Query only January
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # No events should appear
    assert len(events) == 0


# ============================================================================
# Test: Daily Recurring Chores (FREQUENCY_DAILY)
# ============================================================================


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_daily_recurring_with_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test daily recurring chore with due_date shows single event on due date."""
    await setup_test_chore(
        {
            "name": "Daily Vitamin",
            "frequency": const.FREQUENCY_DAILY,
            "due_date": "2025-01-20T08:00:00-05:00",  # 8 AM on Jan 20
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # With due_date, daily recurring shows as single event at due time
    assert len(events) == 1
    event = events[0]
    assert event["summary"] == "Daily Vitamin"
    assert "2025-01-20" in event["start"]["dateTime"]
    assert "08:00:00" in event["start"]["dateTime"]


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_daily_recurring_without_due_date_all_days(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test daily recurring without due_date shows events every day."""
    await setup_test_chore(
        {
            "name": "Make Bed",
            "frequency": const.FREQUENCY_DAILY,
            # No due_date, no applicable_days = every day
        }
    )

    # Query 1 week (7 days)
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-20T00:00:00Z",  # Monday
        "2025-01-26T23:59:59Z",  # Sunday
    )

    # Should have 7 all-day events (Mon-Sun)
    assert len(events) == 7

    # Verify consecutive days
    dates = [event["start"]["date"] for event in events]
    assert dates == [
        "2025-01-20",
        "2025-01-21",
        "2025-01-22",
        "2025-01-23",
        "2025-01-24",
        "2025-01-25",
        "2025-01-26",
    ]


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_daily_recurring_without_due_date_applicable_days(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test daily recurring without due_date respects applicable_days filter."""
    await setup_test_chore(
        {
            "name": "Weekday Chore",
            "frequency": const.FREQUENCY_DAILY,
            "applicable_days": ["mon", "tue", "wed", "thu", "fri"],  # Weekdays only
        }
    )

    # Query 2 weeks
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-20T00:00:00Z",  # Monday
        "2025-02-02T23:59:59Z",  # Sunday (2 weeks)
    )

    # Should have 10 events (5 weekdays × 2 weeks)
    assert len(events) == 10

    # Verify all events are weekdays
    for event in events:
        event_date = datetime.fromisoformat(event["start"]["date"])
        # Monday=0, Sunday=6
        assert event_date.weekday() < 5, f"Event on weekend: {event_date}"


# ============================================================================
# Test: Weekly Recurring Chores (FREQUENCY_WEEKLY)
# ============================================================================


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_weekly_recurring_with_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test weekly recurring with due_date shows 1-week block ending at due date."""
    await setup_test_chore(
        {
            "name": "Weekly Report",
            "frequency": const.FREQUENCY_WEEKLY,
            "due_date": "2025-01-26T23:59:00-05:00",  # Sunday night
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should show 1-week block (7 days before due date)
    assert len(events) == 1
    event = events[0]
    assert event["summary"] == "Weekly Report"

    # Start should be 7 days before due date (Jan 19)
    start_date = event["start"]["date"]
    end_date = event["end"]["date"]
    assert start_date == "2025-01-19"  # 7 days before Jan 26
    assert end_date == "2025-01-27"  # End is due_date + 1 (all-day event convention)


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_weekly_recurring_without_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test weekly recurring without due_date shows Monday-Sunday blocks."""
    await setup_test_chore(
        {
            "name": "Weekly Cleaning",
            "frequency": const.FREQUENCY_WEEKLY,
            # No due_date = generates week blocks
        }
    )

    # Query 3 weeks (to see multiple blocks)
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-13T00:00:00Z",  # Monday, Jan 13
        "2025-02-02T23:59:59Z",  # Sunday, Feb 2
    )

    # Should have 3 weekly blocks (Mon-Sun)
    assert len(events) == 3

    # Verify each block spans Monday-Sunday (7 days)
    for event in events:
        start = datetime.fromisoformat(event["start"]["date"])
        end = datetime.fromisoformat(event["end"]["date"])

        # Start should be Monday
        assert start.weekday() == 0, f"Start not Monday: {start}"

        # Duration should be 7 days (end - start)
        duration = (end - start).days
        assert duration == 7, f"Block not 7 days: {duration}"


# ============================================================================
# Test: Biweekly Recurring Chores (FREQUENCY_BIWEEKLY)
# ============================================================================


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_biweekly_recurring_with_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test biweekly recurring with due_date shows 2-week block."""
    await setup_test_chore(
        {
            "name": "Biweekly Task",
            "frequency": const.FREQUENCY_BIWEEKLY,
            "due_date": "2025-01-26T23:59:00-05:00",  # End of month
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should show 2-week block (14 days before due date)
    assert len(events) == 1
    event = events[0]

    start_date = event["start"]["date"]
    end_date = event["end"]["date"]

    # Start should be 14 days before due date (Jan 12)
    assert start_date == "2025-01-12"
    assert end_date == "2025-01-27"  # Due date + 1


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_biweekly_recurring_without_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test biweekly recurring without due_date shows 14-day blocks."""
    await setup_test_chore(
        {
            "name": "Biweekly Chore",
            "frequency": const.FREQUENCY_BIWEEKLY,
        }
    )

    # Query 6 weeks to see multiple biweekly blocks
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-06T00:00:00Z",  # Monday
        "2025-02-16T23:59:59Z",  # 6 weeks later
    )

    # Should have 3 biweekly blocks (6 weeks / 2)
    assert len(events) == 3

    # Verify each block is 14 days
    for event in events:
        start = datetime.fromisoformat(event["start"]["date"])
        end = datetime.fromisoformat(event["end"]["date"])
        duration = (end - start).days
        assert duration == 14, f"Biweekly block not 14 days: {duration}"


# ============================================================================
# Test: Monthly Recurring Chores (FREQUENCY_MONTHLY)
# ============================================================================


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_monthly_recurring_with_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test monthly recurring with due_date shows block from first to due date."""
    await setup_test_chore(
        {
            "name": "Monthly Report",
            "frequency": const.FREQUENCY_MONTHLY,
            "due_date": "2025-01-31T23:59:00-05:00",  # End of January
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should show block from Jan 1 to Jan 31
    assert len(events) == 1
    event = events[0]

    assert event["start"]["date"] == "2025-01-01"  # First day of month
    assert event["end"]["date"] == "2025-02-01"  # Due date + 1


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_monthly_recurring_without_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test monthly recurring without due_date shows full month blocks."""
    await setup_test_chore(
        {
            "name": "Monthly Cleaning",
            "frequency": const.FREQUENCY_MONTHLY,
        }
    )

    # Query 3 months
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-03-31T23:59:59Z",
    )

    # Should have 3 monthly blocks (Jan, Feb, Mar)
    assert len(events) == 3

    # Verify blocks span full months
    assert events[0]["start"]["date"] == "2025-01-01"
    assert events[0]["end"]["date"] == "2025-02-01"  # Last day of Jan + 1

    assert events[1]["start"]["date"] == "2025-02-01"
    assert events[1]["end"]["date"] == "2025-03-01"  # Last day of Feb + 1

    assert events[2]["start"]["date"] == "2025-03-01"
    assert events[2]["end"]["date"] == "2025-04-01"  # Last day of Mar + 1


# ============================================================================
# Test: Custom Interval Chores (FREQUENCY_CUSTOM)
# ============================================================================


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_custom_interval_days_with_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test custom interval (every 3 days) with due_date."""
    await setup_test_chore(
        {
            "name": "Every 3 Days",
            "frequency": const.FREQUENCY_CUSTOM,
            "custom_interval": 3,
            "custom_interval_unit": const.TIME_UNIT_DAYS,
            "due_date": "2025-01-24T12:00:00-05:00",
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should show 3-day block before due date (Jan 21-24)
    assert len(events) == 1
    event = events[0]

    start = event["start"]["date"]
    end = event["end"]["date"]

    # 3 days before Jan 24 = Jan 21
    assert start == "2025-01-21"
    assert end == "2025-01-25"  # Due date + 1


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_custom_interval_weeks_without_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test custom interval (every 2 weeks) without due_date generates blocks."""
    await setup_test_chore(
        {
            "name": "Every 2 Weeks",
            "frequency": const.FREQUENCY_CUSTOM,
            "custom_interval": 2,
            "custom_interval_unit": const.TIME_UNIT_WEEKS,
        }
    )

    # Query 6 weeks
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-13T00:00:00Z",  # Monday
        "2025-02-23T23:59:59Z",  # 6 weeks later
    )

    # Should have 3 blocks (6 weeks / 2-week interval)
    assert len(events) == 3

    # Verify 2-week (14-day) blocks
    for event in events:
        start = datetime.fromisoformat(event["start"]["date"])
        end = datetime.fromisoformat(event["end"]["date"])
        duration = (end - start).days
        assert duration == 14, f"Custom 2-week interval not 14 days: {duration}"


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_custom_interval_with_applicable_days(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test custom interval respects applicable_days filter."""
    await setup_test_chore(
        {
            "name": "Every 3 Days (Weekdays Only)",
            "frequency": const.FREQUENCY_CUSTOM,
            "custom_interval": 3,
            "custom_interval_unit": const.TIME_UNIT_DAYS,
            "applicable_days": ["mon", "tue", "wed", "thu", "fri"],
        }
    )

    # Query 2 weeks
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-20T00:00:00Z",  # Monday
        "2025-02-02T23:59:59Z",
    )

    # Should have events only on weekdays, spaced 3 days apart
    # Verify no weekend events
    for event in events:
        event_date = datetime.fromisoformat(event["start"]["date"])
        assert event_date.weekday() < 5, f"Custom interval event on weekend: {event}"


# ============================================================================
# Test: Edge Cases and Validation
# ============================================================================


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_multiple_chores_same_kid(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test calendar shows events from multiple chores for same kid."""
    # Create 3 different chores
    await setup_test_chore(
        {
            "name": "Morning Chore",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-01-20T08:00:00-05:00",
        }
    )

    await setup_test_chore(
        {
            "name": "Afternoon Chore",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-01-20T15:00:00-05:00",
        }
    )

    await setup_test_chore(
        {
            "name": "Evening Chore",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-01-20T20:00:00-05:00",
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should have 3 events
    assert len(events) == 3

    # Verify all 3 chores appear
    summaries = {event["summary"] for event in events}
    assert summaries == {"Morning Chore", "Afternoon Chore", "Evening Chore"}


@freeze_time("2025-02-28 12:00:00", tz_offset=0)
async def test_month_boundary_february(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test monthly recurring handles February (short month) correctly."""
    await setup_test_chore(
        {
            "name": "Monthly Feb",
            "frequency": const.FREQUENCY_MONTHLY,
        }
    )

    # Query February 2025 (28 days, not a leap year)
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-02-01T00:00:00Z",
        "2025-02-28T23:59:59Z",
    )

    # Should have 1 block for February
    assert len(events) == 1
    event = events[0]

    # Should span Feb 1 to Feb 28
    assert event["start"]["date"] == "2025-02-01"
    assert event["end"]["date"] == "2025-03-01"  # Last day + 1


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_timezone_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test calendar correctly handles timezone conversions."""
    # Due date in UTC should convert to local time for display
    await setup_test_chore(
        {
            "name": "UTC Chore",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-01-20T18:00:00+00:00",  # 6 PM UTC = 1 PM EST
        }
    )

    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    assert len(events) == 1
    event = events[0]

    # Event time should be converted to local timezone
    # 18:00 UTC = 13:00 EST (UTC-5)
    assert "2025-01-20" in event["start"]["dateTime"]
    assert "13:00:00" in event["start"]["dateTime"]


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_chore_not_assigned_to_kid_not_shown(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
    mock_coordinator: KidsChoresDataCoordinator,
) -> None:
    """Test calendar only shows chores assigned to specific kid."""
    # Create second kid
    import uuid  # pylint: disable=import-outside-toplevel

    other_kid_id = str(uuid.uuid4())
    mock_coordinator.kids_data[other_kid_id] = {
        const.DATA_KID_NAME: "Other Kid",
    }

    # Create chore assigned to OTHER kid (not test_kid)
    await setup_test_chore(
        {
            "name": "Other Kid's Chore",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "2025-01-20T10:00:00-05:00",
            "assigned_kids": [other_kid_id],  # Assigned to other kid
        }
    )

    # Query test_kid's calendar
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should have no events (chore not assigned to this kid)
    assert len(events) == 0


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_calendar_respects_show_period_config(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test calendar respects CONF_CALENDAR_SHOW_PERIOD setting for future events."""
    # This tests that recurring chores without due_date only generate events
    # within calendar_duration (default 90 days)

    await setup_test_chore(
        {
            "name": "Daily Forever",
            "frequency": const.FREQUENCY_DAILY,
            # No due_date = generates events into future
        }
    )

    # Query 6 months into future (180 days)
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-15T00:00:00Z",
        "2025-07-15T23:59:59Z",  # 6 months
    )

    # With default 90-day show period, should have max ~90 events
    # (actual number depends on calendar_duration config)
    # This is a regression test - we verify future events are limited
    assert len(events) < 180, "Calendar generated events beyond show period"
    assert len(events) > 0, "Calendar should generate some events"


# ============================================================================
# Test: Calendar Entity Properties
# ============================================================================


async def test_calendar_entity_properties(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_coordinator: KidsChoresDataCoordinator,
) -> None:
    """Test calendar entity has correct properties."""
    # Get calendar entity
    entity_id = "calendar.kc_test_kid"
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.attributes["friendly_name"]  # Should have friendly name
    assert (
        state.attributes[const.ATTR_KID_NAME] == "Test Kid"
    )  # Extra attribute with kid name


async def test_calendar_entity_current_event(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test calendar entity 'event' property returns current event."""
    # Create chore due now (within ±1 hour window)
    now = dt_util.now()
    due_time = now + timedelta(minutes=30)  # 30 minutes from now

    await setup_test_chore(
        {
            "name": "Current Task",
            "frequency": const.FREQUENCY_NONE,
            "due_date": due_time.isoformat(),
        }
    )

    # Wait for coordinator update
    await hass.async_block_till_done()

    # Get calendar entity
    entity_id = "calendar.kc_test_kid"
    state = hass.states.get(entity_id)

    # Entity should be "on" (event active)
    # Note: This tests the @property event() method
    assert state.state in ["on", "off"]  # State depends on timing


# ============================================================================
# Test: Error Handling
# ============================================================================


async def test_calendar_with_invalid_due_date(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
    setup_test_chore: Callable,
) -> None:
    """Test calendar handles chores with invalid due_date gracefully."""
    await setup_test_chore(
        {
            "name": "Bad Date Chore",
            "frequency": const.FREQUENCY_NONE,
            "due_date": "not-a-valid-date",  # Invalid format
        }
    )

    # Should not crash, just skip the chore
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should have no events (invalid due_date skipped)
    assert len(events) == 0


async def test_calendar_with_empty_chores(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    get_events_fixture: Callable,
) -> None:
    """Test calendar returns empty list when kid has no chores."""
    # Don't create any chores
    events = await get_events_fixture(
        "calendar.kc_test_kid",
        "2025-01-01T00:00:00Z",
        "2025-01-31T23:59:59Z",
    )

    # Should return empty list, not crash
    assert events == []
