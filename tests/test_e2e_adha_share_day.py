"""End-to-end test: Restore ad-ha backup and test Share Day chore workflow.

This test validates the complete workflow using a real production backup:
1. Restore kidschores_data-adha backup via migration (frequency="none", no due_date)
2. Claim "Share Day" chore for Martim
3. Approve "Share Day" chore (Papa as approver)
4. Trigger approval reset
5. Verify state transitions: pending → claimed → approved → pending (after reset)

Key Properties of "Share Day" chore in backup:
- Chore ID: a63c4ee1-8256-4cf9-ae1c-997ff5eb663c
- Name: "Share Day"
- recurring_frequency: "none" (FREQUENCY_NONE)
- due_date: null (no due date)
- default_points: 5.0
- assigned_kids: ["5dd1a770-cef8-481b-996c-c1e36ecb8956" (Martim), "c9d77c66..." (Victoria)]
- completion_criteria: "independent" (default, not stored in v41 data)

This tests the specific scenario from test_approval_reset_no_due_date but with
real production data and the full migration path.

Testing Approach:
    This test uses the migration test pattern from test_migration_samples_validation.py
    rather than the modern YAML scenario pattern. This is intentional because:
    1. We're testing backup restoration (migration path)
    2. We're validating against real production data structure
    3. The migration fixtures already exist and are maintained

    For new workflow tests without migration concerns, prefer the YAML scenario
    pattern documented in AGENT_TEST_CREATION_INSTRUCTIONS.md.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kidschores.const import (
    CHORE_STATE_INDEPENDENT,
    CONF_POINTS_ICON,
    CONF_POINTS_LABEL,
    COORDINATOR,
    DATA_CHORE_STATE,
    DEFAULT_POINTS_ICON,
    DEFAULT_POINTS_LABEL,
    DOMAIN,
)
from tests.helpers import (
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_PENDING,
    DATA_KID_CHORE_DATA,
    DATA_KID_CHORE_DATA_STATE,
    FREQUENCY_NONE,
)


@pytest.fixture
def adha_backup_data() -> dict:
    """Load kidschores_data-adha backup file."""
    sample_path = (
        Path(__file__).parent / "legacy" / "migration_samples" / "kidschores_data-adha"
    )
    with open(sample_path, encoding="utf-8") as f:
        raw_data = json.load(f)
    return raw_data["data"]  # Return just the data section


@pytest.fixture
def mock_config_entry_adha() -> MockConfigEntry:
    """Create config entry for ad-ha backup restoration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="KidsChores (ad-ha backup)",
        data={},
        options={
            CONF_POINTS_LABEL: DEFAULT_POINTS_LABEL,
            CONF_POINTS_ICON: DEFAULT_POINTS_ICON,
        },
        entry_id="test_adha_backup",
        version=1,
        minor_version=1,
    )


async def setup_integration_with_adha_backup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    backup_data: dict,
) -> MockConfigEntry:
    """Set up integration with ad-ha backup data (triggers migration).

    Args:
        hass: Home Assistant instance
        config_entry: Mock config entry
        backup_data: Storage data from kidschores_data-adha

    Returns:
        Config entry after setup and migration
    """
    config_entry.add_to_hass(hass)

    # Mock storage to return backup data (triggers migration on async_setup)
    with patch(
        "homeassistant.helpers.storage.Store.async_load",
        return_value=backup_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.mark.asyncio
async def test_adha_share_day_chore_approval_reset_workflow(
    hass: HomeAssistant,
    mock_config_entry_adha: MockConfigEntry,
    adha_backup_data: dict,
) -> None:
    """Test Share Day chore claim → approve → reset workflow using real ad-ha data.

    Validates that:
    1. Backup restoration succeeds (migration v41 → v42)
    2. "Share Day" chore exists with frequency="none" and no due_date
    3. Chore can be claimed by Martim
    4. Chore can be approved by Papa
    5. Approval reset works correctly (resets to pending despite frequency="none")
    6. State transitions are correct throughout workflow

    This is an end-to-end test that exercises the full stack from backup
    restoration through workflow operations, using production data.
    """
    # Setup integration with backup data (triggers migration)
    config_entry = await setup_integration_with_adha_backup(
        hass, mock_config_entry_adha, adha_backup_data
    )

    # Access coordinator
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Mock notifications to avoid delays
    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        with patch.object(coordinator, "_notify_parents", new=AsyncMock()):
            # ============================================================
            # Phase 1: Verify backup restoration
            # ============================================================

            # Known UUIDs from kidschores_data-adha
            martim_id = "5dd1a770-cef8-481b-996c-c1e36ecb8956"
            victoria_id = "c9d77c66-f787-49e0-9fd9-f35b88f9623b"
            share_day_chore_id = "a63c4ee1-8256-4cf9-ae1c-997ff5eb663c"
            papa_id = "84f7fedc-483c-402b-8db3-075591e3adf4"

            # Verify kids exist
            assert martim_id in coordinator.kids_data
            assert victoria_id in coordinator.kids_data
            martim_data = coordinator.kids_data[martim_id]
            assert martim_data["name"] == "Martim"

            # Verify "Share Day" chore exists
            assert share_day_chore_id in coordinator.chores_data
            share_day_chore = coordinator.chores_data[share_day_chore_id]
            assert share_day_chore["name"] == "Share Day"
            assert share_day_chore["recurring_frequency"] == FREQUENCY_NONE
            assert share_day_chore.get("due_date") is None
            assert share_day_chore["default_points"] == 5.0

            # Verify parent exists
            assert papa_id in coordinator.parents_data
            papa_data = coordinator.parents_data[papa_id]
            assert papa_data["name"] == "Papá"

            # ============================================================
            # Phase 2: Claim chore (Martim claims Share Day)
            # ============================================================

            # Initial state should be pending
            martim_chore_data = martim_data.get(DATA_KID_CHORE_DATA, {})
            share_day_per_kid = martim_chore_data.get(share_day_chore_id, {})
            initial_state = share_day_per_kid.get(
                DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING
            )
            assert initial_state == CHORE_STATE_PENDING, (
                f"Expected initial state 'pending', got '{initial_state}'"
            )

            # Claim chore
            coordinator.claim_chore(martim_id, share_day_chore_id, "Martim")

            # Verify state changed to claimed
            martim_data = coordinator.kids_data[martim_id]
            martim_chore_data = martim_data.get(DATA_KID_CHORE_DATA, {})
            share_day_per_kid = martim_chore_data.get(share_day_chore_id, {})
            claimed_state = share_day_per_kid.get(DATA_KID_CHORE_DATA_STATE)
            assert claimed_state == CHORE_STATE_CLAIMED, (
                f"After claim, expected state 'claimed', got '{claimed_state}'"
            )

            # ============================================================
            # Phase 3: Approve chore (Papa approves)
            # ============================================================

            # Approve chore
            coordinator.approve_chore("Papá", martim_id, share_day_chore_id)

            # Verify state changed to approved
            martim_data = coordinator.kids_data[martim_id]
            martim_chore_data = martim_data.get(DATA_KID_CHORE_DATA, {})
            share_day_per_kid = martim_chore_data.get(share_day_chore_id, {})
            approved_state = share_day_per_kid.get(DATA_KID_CHORE_DATA_STATE)
            assert approved_state == CHORE_STATE_APPROVED, (
                f"After approval, expected state 'approved', got '{approved_state}'"
            )

            # Verify global_state for INDEPENDENT chore with mixed states
            # Expected: global_state = "independent" because Victoria is still pending
            chore_global_state = coordinator.chores_data[share_day_chore_id].get(
                DATA_CHORE_STATE
            )
            victoria_data = coordinator.kids_data[victoria_id]
            victoria_chore_data = victoria_data.get(DATA_KID_CHORE_DATA, {})
            victoria_share_day = victoria_chore_data.get(share_day_chore_id, {})
            victoria_state = victoria_share_day.get(DATA_KID_CHORE_DATA_STATE)

            # For INDEPENDENT chore: if kids have different states, global_state = "independent"
            if victoria_state != approved_state:
                assert chore_global_state == CHORE_STATE_INDEPENDENT, (
                    f"INDEPENDENT chore with mixed states should have global_state='independent', "
                    f"got '{chore_global_state}' (Martim={approved_state}, Victoria={victoria_state})"
                )

            # ============================================================
            # Phase 4: Trigger approval reset
            # ============================================================

            # Call reset method with empty list (FREQUENCY_NONE chores are always included)
            # From coordinator.py line 7876: chores with frequency="none" are processed
            # regardless of target_freqs, so we can pass an empty list
            await coordinator._reset_daily_chore_statuses(target_freqs=[])

            # Verify state reset to pending
            martim_data = coordinator.kids_data[martim_id]
            martim_chore_data = martim_data.get(DATA_KID_CHORE_DATA, {})
            share_day_per_kid = martim_chore_data.get(share_day_chore_id, {})
            final_state = share_day_per_kid.get(DATA_KID_CHORE_DATA_STATE)
            assert final_state == CHORE_STATE_PENDING, (
                f"After reset, expected state 'pending', got '{final_state}'. "
                f"Chores with frequency='none' should reset when in approved state."
            )

            # ============================================================
            # Phase 5: Summary verification
            # ============================================================

            # Full workflow verified:
            # 1. ✅ Backup restored and migrated successfully
            # 2. ✅ Share Day chore found with frequency="none" and no due_date
            # 3. ✅ Claim succeeded: pending → claimed
            # 4. ✅ Approval succeeded: claimed → approved
            # 5. ✅ Reset succeeded: approved → pending

            # This confirms the fix for the approval reset bug:
            # Chores with frequency="none" and no due_date DO reset correctly
            # because coordinator._reset_daily_chore_statuses() includes
            # FREQUENCY_NONE in the reset logic (line 7876 in coordinator.py)
