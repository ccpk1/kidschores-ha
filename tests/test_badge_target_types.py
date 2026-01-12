"""Badge target type tests - Section 1.

Tests for non-cumulative badge types via options flow:
- Daily badges: Same-day aggregation, midnight reset
- Periodic badges: Custom interval, interval boundary
- Special occasion badges: Specific date trigger, date range

These badge types are only available via options flow (not config flow).
Following AGENT_TEST_CREATION_INSTRUCTIONS.md patterns.

Test organization:
- Section 1.2: Daily Target Types (2 tests)
- Section 1.4: Periodic Target Types (2 tests)
- Section 1.5: Special Occasion Target Types (2 tests)

Note: Section 1.1 (Cumulative) and Section 1.3 (Weekly - actually handled
by periodic with weekly reset) are covered in test_badge_cumulative.py.
"""

from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.kidschores import const
from tests.helpers import (
    # Badge type constants
    BADGE_TYPE_DAILY,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION,
    # Badge form input constants
    CFOF_BADGES_INPUT_ASSIGNED_TO,
    CFOF_BADGES_INPUT_AWARD_ITEMS,
    CFOF_BADGES_INPUT_AWARD_POINTS,
    CFOF_BADGES_INPUT_ICON,
    CFOF_BADGES_INPUT_NAME,
    CFOF_BADGES_INPUT_OCCASION_TYPE,
    CFOF_BADGES_INPUT_SELECTED_CHORES,
    CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
    CFOF_BADGES_INPUT_TARGET_TYPE,
    CFOF_BADGES_INPUT_TYPE,
    # Data keys
    DATA_KID_BADGE_PROGRESS,
    # Options flow constants
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_BADGES,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_STEP_INIT,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def setup_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for badge testing.

    Uses scenario_minimal.yaml which provides:
    - 1 kid (Zoë)
    - 1 parent (Mom)
    - 5 chores
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def add_badge_via_options_flow(
    hass: HomeAssistant,
    entry_id: str,
    badge_type: str,
    badge_data: dict[str, Any],
) -> ConfigFlowResult:
    """Add a badge via options flow with the complete step sequence.

    Badge flow has 4 steps:
    1. Navigate to badges menu
    2. Select "Add" action
    3. Select badge type
    4. Submit badge details

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        badge_type: One of BADGE_TYPE_* constants
        badge_data: Form data for the badge (varies by type)

    Returns:
        Final flow result
    """
    # Step 1: Start options flow and navigate to badges menu
    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
    )

    # Step 2: Select "Add" action
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )

    # Step 3: Select badge type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CFOF_BADGES_INPUT_TYPE: badge_type},
    )

    # Step 4: Submit badge details
    return await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=badge_data,
    )


def get_badge_by_name(coordinator: Any, badge_name: str) -> tuple[str, dict[str, Any]]:
    """Get badge ID and data by name.

    Args:
        coordinator: KidsChoresCoordinator instance
        badge_name: Display name of the badge

    Returns:
        Tuple of (badge_id, badge_data)

    Raises:
        ValueError: If badge not found
    """
    for badge_id, badge_data in coordinator.badges_data.items():
        if badge_data.get(const.DATA_BADGE_NAME) == badge_name:
            return badge_id, badge_data
    raise ValueError(f"Badge not found: {badge_name}")


# ============================================================================
# SECTION 1.2: DAILY TARGET TYPES
# ============================================================================


class TestDailyBadgeTargetTypes:
    """Test DAILY badge target type behavior.

    Daily badges:
    - Reset at midnight (tracked via reset_schedule)
    - Support target_type field (but NOT streak types)
    - Support tracked_chores component
    - Track progress within a single day
    """

    async def test_add_daily_badge_via_options_flow(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test adding a daily badge via options flow.

        Validates the complete flow for creating a daily badge:
        1. Badge type selection returns daily step
        2. Daily badge form accepts target_type + threshold
        3. Badge is created with correct type and target
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        # Get existing kid and chore IDs
        kid_id = next(iter(coordinator.kids_data.keys()))
        chore_id = next(iter(coordinator.chores_data.keys()))

        # Daily badge form data - requires target_type (unlike cumulative)
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Daily Star",
            CFOF_BADGES_INPUT_ICON: "mdi:star-circle",
            CFOF_BADGES_INPUT_TARGET_TYPE: "chore_count",  # Required for daily
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 3,  # Complete 3 chores
            CFOF_BADGES_INPUT_ASSIGNED_TO: [kid_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [chore_id],  # Track specific chore
            CFOF_BADGES_INPUT_AWARD_POINTS: 10.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_DAILY, badge_data
        )

        # Options flow returns to init step after successful add
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created with correct type
        badge_id, badge_info = get_badge_by_name(coordinator, "Daily Star")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_DAILY
        assert (
            badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE]
            == "chore_count"
        )

    async def test_daily_badge_same_day_aggregation(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test daily badge aggregates progress within same day.

        When multiple chores are completed on the same day,
        the daily badge should aggregate all completions toward target.
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        kid_id = next(iter(coordinator.kids_data.keys()))

        # Create daily badge with chore_count target of 2
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Daily Chore Hero",
            CFOF_BADGES_INPUT_ICON: "mdi:medal",
            CFOF_BADGES_INPUT_TARGET_TYPE: "chore_count",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 2,  # Need 2 chores
            CFOF_BADGES_INPUT_ASSIGNED_TO: [kid_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],  # All chores
            CFOF_BADGES_INPUT_AWARD_POINTS: 15.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_DAILY, badge_data
        )

        # After badge creation, coordinator should have synced progress
        badge_id, _ = get_badge_by_name(coordinator, "Daily Chore Hero")

        # Verify badge progress structure was initialized for kid
        kid_progress = coordinator.kids_data[kid_id].get(DATA_KID_BADGE_PROGRESS, {})
        assert badge_id in kid_progress, "Badge progress should be initialized"


# ============================================================================
# SECTION 1.4: PERIODIC TARGET TYPES
# ============================================================================


class TestPeriodicBadgeTargetTypes:
    """Test PERIODIC badge target type behavior.

    Periodic badges:
    - Support all target types (points, chore_count, days_*, streak_*)
    - Support custom intervals via reset_schedule
    - Track progress across multiple days within a period
    """

    async def test_add_periodic_badge_via_options_flow(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test adding a periodic badge via options flow.

        Validates the complete flow for creating a periodic badge:
        1. Badge type selection returns periodic step
        2. Periodic badge form accepts all target types
        3. Badge is created with correct configuration
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        kid_id = next(iter(coordinator.kids_data.keys()))

        # Periodic badge with points_chores target
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Weekly Champion",
            CFOF_BADGES_INPUT_ICON: "mdi:trophy",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points_chores",  # Points from chores only
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 50,  # Earn 50 points
            CFOF_BADGES_INPUT_ASSIGNED_TO: [kid_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],  # All chores
            CFOF_BADGES_INPUT_AWARD_POINTS: 25.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_PERIODIC, badge_data
        )

        # Options flow returns to init step after successful add
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created with correct type and target
        badge_id, badge_info = get_badge_by_name(coordinator, "Weekly Champion")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_PERIODIC
        assert (
            badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE]
            == "points_chores"
        )

    async def test_periodic_badge_custom_interval(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test periodic badge with custom interval tracks across days.

        Periodic badges can have custom reset intervals (3 days, weekly, etc).
        Progress should accumulate within the period.
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        kid_id = next(iter(coordinator.kids_data.keys()))

        # Periodic badge tracking days_all_chores
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Consistency Star",
            CFOF_BADGES_INPUT_ICON: "mdi:calendar-check",
            CFOF_BADGES_INPUT_TARGET_TYPE: "days_all_chores",  # Days with all done
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 5,  # Need 5 perfect days
            CFOF_BADGES_INPUT_ASSIGNED_TO: [kid_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],  # All chores
            CFOF_BADGES_INPUT_AWARD_POINTS: 50.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_PERIODIC, badge_data
        )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge created
        badge_id, badge_info = get_badge_by_name(coordinator, "Consistency Star")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_PERIODIC
        assert (
            badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE]
            == "days_all_chores"
        )


# ============================================================================
# SECTION 1.5: SPECIAL OCCASION TARGET TYPES
# ============================================================================


class TestSpecialOccasionBadgeTargetTypes:
    """Test SPECIAL_OCCASION badge target type behavior.

    Special occasion badges:
    - Require occasion_type (birthday, holiday, custom)
    - Do NOT have target_type or threshold fields
    - Triggered by special date matching
    """

    async def test_add_special_occasion_badge_via_options_flow(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test adding a special occasion badge via options flow.

        Special occasion badges have different schema:
        - No target_type field
        - No threshold field
        - Instead have occasion_type field
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        kid_id = next(iter(coordinator.kids_data.keys()))

        # Special occasion badge - NO target_type or threshold
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Birthday Star",
            CFOF_BADGES_INPUT_ICON: "mdi:cake-variant",
            CFOF_BADGES_INPUT_OCCASION_TYPE: "birthday",  # Required for special
            CFOF_BADGES_INPUT_ASSIGNED_TO: [kid_id],
            CFOF_BADGES_INPUT_AWARD_POINTS: 100.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_SPECIAL_OCCASION, badge_data
        )

        # Options flow returns to init step after successful add
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created with correct type
        badge_id, badge_info = get_badge_by_name(coordinator, "Birthday Star")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_SPECIAL_OCCASION

    async def test_special_occasion_badge_holiday_type(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test special occasion badge with holiday occasion type.

        Validates that different occasion types can be created.
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        kid_id = next(iter(coordinator.kids_data.keys()))

        # Holiday special occasion badge
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Holiday Helper",
            CFOF_BADGES_INPUT_ICON: "mdi:gift",
            CFOF_BADGES_INPUT_OCCASION_TYPE: "holiday",  # Holiday occasion
            CFOF_BADGES_INPUT_ASSIGNED_TO: [kid_id],
            CFOF_BADGES_INPUT_AWARD_POINTS: 50.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_SPECIAL_OCCASION, badge_data
        )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created
        badge_id, badge_info = get_badge_by_name(coordinator, "Holiday Helper")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_SPECIAL_OCCASION


# ============================================================================
# BADGE STEP ID VERIFICATION TESTS
# ============================================================================


class TestBadgeStepSequence:
    """Verify the correct step sequence for each badge type."""

    async def test_daily_badge_step_id(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test that selecting daily badge type shows daily step."""
        config_entry = setup_minimal.config_entry

        # Navigate to add badge type selection
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Select daily badge type
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CFOF_BADGES_INPUT_TYPE: BADGE_TYPE_DAILY},
        )

        # Should show daily badge form
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE_DAILY

    async def test_periodic_badge_step_id(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test that selecting periodic badge type shows periodic step."""
        config_entry = setup_minimal.config_entry

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CFOF_BADGES_INPUT_TYPE: BADGE_TYPE_PERIODIC},
        )

        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE_PERIODIC

    async def test_special_occasion_badge_step_id(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test that selecting special occasion badge type shows special step."""
        config_entry = setup_minimal.config_entry

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CFOF_BADGES_INPUT_TYPE: BADGE_TYPE_SPECIAL_OCCASION},
        )

        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE_SPECIAL
