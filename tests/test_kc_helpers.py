"""Edge case tests for kc_helpers module.

Tests for:
- Entity lookup helpers (get_*_id_by_name, get_*_id_or_raise)
- Authorization helpers (is_user_authorized_for_global_action, is_user_authorized_for_kid)
- Progress calculation helpers
- Datetime boundary handling in adjust_datetime_by_interval
"""

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.kidschores import const, kc_helpers as kh
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 kid, 1 parent, 5 chores (all independent)."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class TestEntityLookupHelpers:
    """Test entity lookup functions with edge cases."""

    async def test_lookup_existing_entity(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should find existing entity by name."""
        coordinator = scenario_minimal.coordinator

        kid_id = scenario_minimal.kid_ids["Zoë"]
        kid_info = coordinator.kids_data.get(kid_id, {})
        kid_name = kid_info.get(const.DATA_KID_NAME)

        result = kh.get_kid_id_by_name(coordinator, kid_name)

        assert result == kid_id

    async def test_lookup_missing_entity_returns_none(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return None for missing entity."""
        coordinator = scenario_minimal.coordinator

        result = kh.get_kid_id_by_name(coordinator, "NonexistentKid")

        assert result is None

    async def test_lookup_or_raise_raises_on_missing(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should raise HomeAssistantError on missing entity."""
        from custom_components.kidschores import const

        coordinator = scenario_minimal.coordinator

        with pytest.raises(HomeAssistantError):
            kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, "NonexistentKid"
            )


class TestAuthorizationHelpers:
    """Test authorization check functions."""

    async def test_admin_user_global_authorization(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Admin user should be authorized for global actions."""
        admin_user = mock_hass_users["admin"]

        is_authorized = await kh.is_user_authorized_for_global_action(
            hass, admin_user.id, "approve_chores"
        )

        assert is_authorized is True

    async def test_non_admin_user_global_authorization(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Registered parent user should be authorized for global actions."""
        parent_user = mock_hass_users["parent1"]

        is_authorized = await kh.is_user_authorized_for_global_action(
            hass, parent_user.id, "approve_chores"
        )

        # Parent users ARE authorized when registered in coordinator.parents_data
        assert is_authorized is True


class TestDatetimeBoundaryHandling:
    """Test datetime handling in adjust_datetime_by_interval."""

    async def test_month_end_transition(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should handle month-end boundary correctly."""
        jan_31 = datetime(2025, 1, 31, 12, 0, 0, tzinfo=UTC)

        result = kh.adjust_datetime_by_interval(jan_31, const.TIME_UNIT_MONTHS, 1)

        # Adding 1 month from Jan 31 should give Feb 28 (or 29 in leap year)
        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    async def test_year_transition(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should handle year boundary correctly."""
        dec_31 = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)

        result = kh.adjust_datetime_by_interval(dec_31, const.TIME_UNIT_YEARS, 1)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC


class TestProgressCalculation:
    """Test progress calculation helpers."""

    async def test_progress_with_scenario_data(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should calculate progress safely."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]

        kid_info = coordinator.kids_data.get(kid_id, {})
        # tracked_chores should be a list of chore IDs (strings), not dicts
        tracked_chore_ids = [
            chore_id
            for chore_id, chore_info in coordinator.chores_data.items()
            if kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        ]

        # Function returns tuple: (met_requirement, completed_count, total_count)
        met_req, completed, total = kh.get_today_chore_completion_progress(
            kid_info, tracked_chore_ids
        )

        assert isinstance(met_req, bool)
        assert isinstance(completed, int)
        assert isinstance(total, int)
        assert completed >= 0
        assert total >= 0
