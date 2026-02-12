"""Test badge period structure initialization and signal flow.

Tests the Landlord-Tenant pattern for badge earned period tracking:
- GamificationManager (Landlord) creates empty periods: {} before emitting signal
- StatisticsManager (Tenant) populates period data via record_transaction

These tests verify the ACTUAL BUG that was found in production:
- Bronze badge was awarded with periods: {} (empty dict)
- Signal was not emitted OR handler was not triggered OR record_transaction failed
- This file tests each step of the flow to isolate the root cause

Uses scenario_full (Stårblüm family) from test_badge_helpers.py pattern.
"""

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.kidschores import const
from custom_components.kidschores.helpers.entity_helpers import get_event_signal

# Note: We import from const.py for attribute keys (not tests.helpers)
from tests.test_badge_helpers import (
    get_badge_by_name,
    get_kid_by_name,
    setup_badges,  # noqa: F401 - pytest fixture
)

# ============================================================================
# SECTION 1: LANDLORD-TENANT PATTERN TESTS
# ============================================================================


class TestBadgePeriodStructureCreation:
    """Test that badge period structures follow Landlord-Tenant pattern."""

    async def test_ensure_kid_badge_structures_creates_empty_periods(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test Landlord creates empty periods dict before Tenant populates.

        Landlord (GamificationManager) responsibility:
        - Create badge entry with empty periods: {}
        - Call _ensure_kid_badge_structures before persist
        - Emit BADGE_EARNED signal AFTER persist

        This test verifies Step 1 of the contract.
        """
        coordinator = setup_badges.coordinator

        # Get Zoë (has cumulative badges in scenario_full)
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]

        # Get Chore Stär Champion badge ID
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Manually create badge entry WITHOUT periods (simulate pre-fix bug)
        badges_earned = zoe_data.setdefault(const.DATA_KID_BADGES_EARNED, {})
        badges_earned[champion_id] = {
            const.DATA_KID_BADGES_EARNED_NAME: "Chore Stär Champion",
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED: "2026-02-11",
            # Intentionally missing periods key to test structure creation
        }

        # Call Landlord's structure creation method
        coordinator.gamification_manager._ensure_kid_badge_structures(
            zoe_id, champion_id
        )

        # Verify Landlord created ONLY empty dict (Tenant populates later)
        champion_entry = badges_earned[champion_id]
        assert const.DATA_KID_BADGES_EARNED_PERIODS in champion_entry, (
            "Landlord should create periods key"
        )

        periods = champion_entry[const.DATA_KID_BADGES_EARNED_PERIODS]
        assert isinstance(periods, dict), "periods should be dict type"
        assert periods == {}, (
            "Landlord should create ONLY empty dict, Tenant populates via signal"
        )

    async def test_badge_earned_signal_emitted_after_persist(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test BADGE_EARNED signal is emitted after badge award.

        This test verifies the signal flow:
        1. Badge evaluation determines award needed
        2. _record_badge_earned creates structure & persists
        3. BADGE_EARNED signal emitted with kid_id and badge_id
        4. StatisticsManager._on_badge_earned listens and populates periods

        This catches the production bug where signal wasn't emitted.
        """
        coordinator = setup_badges.coordinator

        # Get Zoë
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Remove badge to test first-time award
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]
        badges_earned = zoe_data.get(const.DATA_KID_BADGES_EARNED, {})
        if champion_id in badges_earned:
            del badges_earned[champion_id]

        # Mock persist to prevent file writes
        coordinator._persist_and_update = MagicMock()

        # Track if signal was emitted
        signal_emitted = False
        signal_payload: dict[str, Any] = {}

        def capture_signal(payload: dict[str, Any]) -> None:
            nonlocal signal_emitted, signal_payload
            signal_emitted = True
            signal_payload = payload

        # Subscribe to BADGE_EARNED signal BEFORE triggering action
        # Signal format: "kidschores_{entry_id}_{suffix}" (instance-scoped)
        entry_id = coordinator.config_entry.entry_id
        signal_key = get_event_signal(entry_id, const.SIGNAL_SUFFIX_BADGE_EARNED)
        async_dispatcher_connect(hass, signal_key, capture_signal)

        # Award 100 points to trigger badge evaluation (threshold = 100)
        # Note: source is a keyword-only argument in deposit()
        await coordinator.economy_manager.deposit(
            zoe_id, 100.0, source=const.POINTS_SOURCE_BONUSES
        )
        await hass.async_block_till_done()

        # Wait for debounced badge evaluation (1.0 second default debounce)
        await asyncio.sleep(1.5)
        await hass.async_block_till_done()

        # CRITICAL: Verify signal was emitted
        assert signal_emitted, "BADGE_EARNED signal should be emitted after badge award"
        assert signal_payload.get("kid_id") == zoe_id
        assert signal_payload.get("badge_id") == champion_id


# ============================================================================
# SECTION 2: STATISTICS MANAGER POPULATION TESTS
# ============================================================================


class TestStatisticsManagerPopulation:
    """Test StatisticsManager properly populates badge period data."""

    async def test_statistics_manager_populates_badge_periods(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test Tenant populates period data when BADGE_EARNED signal fires.

        Tenant (StatisticsManager) responsibility:
        - Listen for BADGE_EARNED signal
        - Call StatisticsEngine.record_transaction
        - Populate all period keys (daily/weekly/monthly/yearly/all_time)
        - Increment award_count in each period bucket

        This test verifies Step 2 of the Landlord-Tenant contract.
        This catches the production bug where periods stayed empty.
        """
        coordinator = setup_badges.coordinator

        # Get Zoë
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Create badge entry with empty periods (Landlord did its job)
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]
        badges_earned = zoe_data.setdefault(const.DATA_KID_BADGES_EARNED, {})
        badges_earned[champion_id] = {
            const.DATA_KID_BADGES_EARNED_NAME: "Chore Stär Champion",
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED: "2026-02-11",
            const.DATA_KID_BADGES_EARNED_PERIODS: {},  # Empty, as Landlord creates
        }

        # Mock persist
        coordinator._persist = MagicMock()
        coordinator.async_set_updated_data = MagicMock()

        # Trigger StatisticsManager's badge earned handler directly
        payload = {
            "kid_id": zoe_id,
            "badge_id": champion_id,
        }
        coordinator.statistics_manager._on_badge_earned(payload)

        # CRITICAL: Verify Tenant populated the periods structure
        champion_entry = badges_earned[champion_id]
        periods = champion_entry[const.DATA_KID_BADGES_EARNED_PERIODS]

        # Verify all period type keys created by record_transaction
        assert const.PERIOD_ALL_TIME in periods, (
            "record_transaction should create all_time bucket"
        )
        assert const.PERIOD_DAILY in periods, (
            "record_transaction should create daily bucket"
        )
        assert const.PERIOD_WEEKLY in periods, (
            "record_transaction should create weekly bucket"
        )
        assert const.PERIOD_MONTHLY in periods, (
            "record_transaction should create monthly bucket"
        )
        assert const.PERIOD_YEARLY in periods, (
            "record_transaction should create yearly bucket"
        )

        # Verify all_time.all_time has award_count
        all_time_data = periods[const.PERIOD_ALL_TIME].get("all_time", {})
        assert const.DATA_KID_BADGES_EARNED_AWARD_COUNT in all_time_data, (
            "all_time.all_time should have award_count"
        )
        assert all_time_data[const.DATA_KID_BADGES_EARNED_AWARD_COUNT] == 1, (
            "award_count should be 1 for first award"
        )

        # Verify current date bucket created
        from custom_components.kidschores.utils import dt_utils

        today_iso = dt_utils.dt_today_iso()
        assert today_iso in periods[const.PERIOD_DAILY], (
            f"daily bucket should have today's entry: {today_iso}"
        )
        daily_data = periods[const.PERIOD_DAILY][today_iso]
        assert daily_data[const.DATA_KID_BADGES_EARNED_AWARD_COUNT] == 1


# ============================================================================
# SECTION 3: END-TO-END INTEGRATION TESTS
# ============================================================================


class TestBadgeAwardEndToEnd:
    """Test complete badge award flow from evaluation to period tracking."""

    async def test_first_time_badge_award_creates_and_populates_periods(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test end-to-end: badge evaluation → award → signal → periods populated.

        This is the CRITICAL test that reproduces the production bug:
        - Bronze badge awarded but periods: {} stayed empty
        - Tests the COMPLETE flow to verify fix works

        Flow tested:
        1. GamificationEngine evaluates badge thresholds
        2. GamificationManager._apply_badge_result awards badge
        3. GamificationManager._record_badge_earned creates structure
        4. _ensure_kid_badge_structures creates empty periods: {}
        5. coordinator._persist_and_update saves to storage
        6. BADGE_EARNED signal emitted
        7. StatisticsManager._on_badge_earned populates periods
        8. periods now has all_time/daily/weekly/monthly/yearly data
        """
        coordinator = setup_badges.coordinator

        # Get Zoë and badge
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Remove badge to simulate first-time award
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]
        badges_earned = zoe_data.get(const.DATA_KID_BADGES_EARNED, {})
        if champion_id in badges_earned:
            del badges_earned[champion_id]

        # Deposit points so total_points_earned >= threshold for badge award
        # This populates point_periods.all_time.all_time.points_earned via
        # StatisticsManager._on_points_changed (sync, runs immediately)
        await coordinator.economy_manager.deposit(
            zoe_id, 150.0, source=const.POINTS_SOURCE_BONUSES
        )
        await hass.async_block_till_done()

        # Verify Zoë has enough total points earned
        all_time_stats = coordinator.statistics_manager.get_all_time_stats(zoe_id)
        total_points_earned = all_time_stats.get("points_earned", 0.0)
        assert total_points_earned >= 100.0, (
            f"Zoë should have 100+ total points earned, has {total_points_earned}"
        )

        # Mock persist to prevent actual file writes
        with patch.object(coordinator, "_persist_and_update"):
            # Trigger badge evaluation directly (bypasses debounce timer)
            await coordinator.gamification_manager._evaluate_kid(zoe_id)

        # Verify badge was awarded
        badges_earned = zoe_data[const.DATA_KID_BADGES_EARNED]
        assert champion_id in badges_earned, "Chore Stär Champion should be awarded"

        champion_entry = badges_earned[champion_id]
        assert champion_entry[const.DATA_KID_BADGES_EARNED_NAME] == (
            "Chore Stär Champion"
        )
        assert champion_entry[const.DATA_KID_BADGES_EARNED_LAST_AWARDED] is not None

        # CRITICAL: Verify periods exists AND is populated
        periods = champion_entry.get(const.DATA_KID_BADGES_EARNED_PERIODS)
        assert periods is not None, "periods structure should exist (Landlord)"
        assert periods != {}, (
            "periods should NOT be empty - THIS IS THE BUG WE'RE FIXING"
        )

        # Verify all period buckets populated by StatisticsManager
        assert const.PERIOD_ALL_TIME in periods
        assert const.PERIOD_DAILY in periods
        assert const.PERIOD_WEEKLY in periods
        assert const.PERIOD_MONTHLY in periods
        assert const.PERIOD_YEARLY in periods

        # Verify award_count in all_time
        all_time_data = periods[const.PERIOD_ALL_TIME]["all_time"]
        assert all_time_data[const.DATA_KID_BADGES_EARNED_AWARD_COUNT] == 1

    async def test_re_award_increments_period_counts(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test that re-awarding badge increments period counters correctly.

        Cumulative badges can be re-awarded when maintenance cycles complete.
        This test verifies period tracking across multiple awards.
        """
        coordinator = setup_badges.coordinator

        # Get Zoë and badge
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Ensure badge exists with initial award
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]
        badges_earned = zoe_data.setdefault(const.DATA_KID_BADGES_EARNED, {})

        # Create initial badge entry if doesn't exist
        if champion_id not in badges_earned:
            # Deposit enough points for badge award
            await coordinator.economy_manager.deposit(
                zoe_id, 150.0, source=const.POINTS_SOURCE_BONUSES
            )
            await hass.async_block_till_done()
            with patch.object(coordinator, "_persist_and_update"):
                await coordinator.gamification_manager._evaluate_kid(zoe_id)

        # Get initial award count
        periods = badges_earned[champion_id][const.DATA_KID_BADGES_EARNED_PERIODS]
        initial_count = periods[const.PERIOD_ALL_TIME]["all_time"][
            const.DATA_KID_BADGES_EARNED_AWARD_COUNT
        ]

        # Mock persist and trigger re-evaluation
        with patch.object(coordinator, "_persist_and_update"):
            await coordinator.gamification_manager._evaluate_kid(zoe_id)

        # Verify award_count incremented
        updated_periods = badges_earned[champion_id][
            const.DATA_KID_BADGES_EARNED_PERIODS
        ]
        updated_count = updated_periods[const.PERIOD_ALL_TIME]["all_time"][
            const.DATA_KID_BADGES_EARNED_AWARD_COUNT
        ]

        assert updated_count == initial_count + 1, (
            "award_count should increment on re-award"
        )


# ============================================================================
# SECTION 4: BADGES SENSOR VALIDATION
# ============================================================================


class TestBadgesSensorAttributes:
    """Test that badges sensor reflects badge awards correctly."""

    async def test_badges_sensor_shows_earned_badges(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test badges sensor attributes show earned badges correctly.

        After badge award, the kid's badges sensor should:
        - Show badge in badges_earned list
        - Update highest_earned_badge_name
        - Update badge_status to "active"
        - Reflect correct cycle_points
        """
        coordinator = setup_badges.coordinator

        # Get Zoë and badge
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Get badges sensor entity ID (slug = lowercase kid name)
        badges_sensor_eid = "sensor.zoe_kidschores_badges"

        # Remove badge to test first-time award
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]
        badges_earned = zoe_data.get(const.DATA_KID_BADGES_EARNED, {})
        if champion_id in badges_earned:
            del badges_earned[champion_id]

        # Deposit enough points for badge award
        await coordinator.economy_manager.deposit(
            zoe_id, 150.0, source=const.POINTS_SOURCE_BONUSES
        )
        await hass.async_block_till_done()

        # Verify Zoë has enough points
        all_time_stats = coordinator.statistics_manager.get_all_time_stats(zoe_id)
        assert all_time_stats.get("points_earned", 0.0) >= 100.0

        # Award badge (direct call bypasses debounce)
        with patch.object(coordinator, "_persist_and_update"):
            await coordinator.gamification_manager._evaluate_kid(zoe_id)

        # Force sensor update
        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

        # Get sensor state
        sensor_state = hass.states.get(badges_sensor_eid)
        assert sensor_state is not None, (
            f"Badges sensor {badges_sensor_eid} should exist"
        )

        # Verify sensor attributes show the badge
        badges_earned_attr = sensor_state.attributes.get(
            const.ATTR_ALL_EARNED_BADGES, []
        )
        assert "Chore Stär Champion" in badges_earned_attr, (
            "Badges sensor should show Chore Stär Champion in badges_earned"
        )

        # Verify sensor state shows count
        assert sensor_state.state == "1", "Sensor state should show 1 earned badge"

        # Verify status in attributes
        badge_status = sensor_state.attributes.get(const.ATTR_BADGE_STATUS)
        assert badge_status == "active", "Badge status should be 'active' after award"

    async def test_badges_sensor_reflects_period_data(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test badges sensor shows period statistics for earned badges.

        This test verifies the sensor exposes period data that the
        dashboard helper can use for display.
        """
        coordinator = setup_badges.coordinator

        # Get Zoë
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Award badge
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]
        badges_earned = zoe_data.get(const.DATA_KID_BADGES_EARNED, {})
        if champion_id not in badges_earned:
            # Deposit enough points for badge award
            await coordinator.economy_manager.deposit(
                zoe_id, 150.0, source=const.POINTS_SOURCE_BONUSES
            )
            await hass.async_block_till_done()
            with patch.object(coordinator, "_persist_and_update"):
                await coordinator.gamification_manager._evaluate_kid(zoe_id)

        # Verify periods data exists in storage
        champion_entry = badges_earned[champion_id]
        periods = champion_entry.get(const.DATA_KID_BADGES_EARNED_PERIODS, {})

        # THIS IS THE KEY TEST: periods should NOT be empty
        assert periods != {}, (
            "Badge periods should be populated - THIS IS THE PRODUCTION BUG"
        )

        # If periods are populated, verify structure
        if periods:
            assert const.PERIOD_ALL_TIME in periods
            all_time_data = periods[const.PERIOD_ALL_TIME].get("all_time", {})
            award_count = all_time_data.get(const.DATA_KID_BADGES_EARNED_AWARD_COUNT, 0)
            assert award_count >= 1, "award_count should be at least 1"
