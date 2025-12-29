"""Example test demonstrating manual migration invocation pattern.

This test validates that we can manually invoke the migration to convert
legacy `is_shared` (boolean) → `completion_criteria` (enum) after loading
data through config flow.

Since Option B fully deprecated shared_chore, this test simulates legacy
storage by injecting the old is_shared field into coordinator data.
"""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.kidschores import const
from custom_components.kidschores.const import DOMAIN
from custom_components.kidschores.migration_pre_v42 import PreV42Migrator

# pylint: disable=protected-access
# pylint: disable=unused-argument
# Tests need to access coordinator private methods and data


@pytest.mark.asyncio
async def test_manual_migration_converts_is_shared_to_completion_criteria(
    hass: HomeAssistant,
    scenario_minimal,
    mock_hass_users,  # pylint: disable=unused-argument
) -> None:
    """Test manual migration invocation converts is_shared to completion_criteria.

    Validates workaround for schema v42+ test data where automatic migration
    is skipped. This pattern simulates legacy pre-v42 storage.
    """
    # STEP 1: Load data via config flow
    config_entry, name_to_id_map = scenario_minimal
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Get chore ID (using correct chore name from scenario_minimal)
    feed_cats_id = name_to_id_map["chore:Feed the cåts"]

    # STEP 2: Manually inject legacy is_shared field (simulating pre-v42 storage)
    # Modern v42+ data does NOT include shared_chore field, so we inject it
    chore_info = coordinator.chores_data[feed_cats_id]
    chore_info[const.DATA_CHORE_SHARED_CHORE_DEPRECATED] = False  # Legacy boolean

    # Remove completion_criteria to simulate legacy state
    if const.DATA_CHORE_COMPLETION_CRITERIA in chore_info:
        del chore_info[const.DATA_CHORE_COMPLETION_CRITERIA]

    # Verify legacy format is now present
    assert const.DATA_CHORE_SHARED_CHORE_DEPRECATED in chore_info
    assert const.DATA_CHORE_COMPLETION_CRITERIA not in chore_info

    # STEP 3: Manually invoke migration
    migrator = PreV42Migrator(coordinator)
    migrator._migrate_independent_chores()
    coordinator._persist()

    # STEP 4: Verify conversion completed
    chore_info = coordinator.chores_data[feed_cats_id]

    # Check completion_criteria field now exists
    assert const.DATA_CHORE_COMPLETION_CRITERIA in chore_info
    assert (
        chore_info[const.DATA_CHORE_COMPLETION_CRITERIA]
        == const.COMPLETION_CRITERIA_INDEPENDENT
    )

    # Check shared_chore field is REMOVED (Option B behavior)
    assert const.DATA_CHORE_SHARED_CHORE_DEPRECATED not in chore_info

    # Check per_kid_due_dates initialized
    assert const.DATA_CHORE_PER_KID_DUE_DATES in chore_info
    assert isinstance(chore_info[const.DATA_CHORE_PER_KID_DUE_DATES], dict)

    # Verify per_kid_due_dates has entry for assigned kid
    zoe_id = name_to_id_map["kid:Zoë"]
    assert zoe_id in chore_info[const.DATA_CHORE_PER_KID_DUE_DATES]

    # STEP 5: Verify coordinator can now use INDEPENDENT logic
    # Mock notifications to avoid errors
    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # This should work with INDEPENDENT chore logic
        await coordinator._check_overdue_chores()

    # No errors = migration successful!
