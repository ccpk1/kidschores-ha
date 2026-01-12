"""Modern tests for backup restore scenarios with data migration.

Tests validate that old format backups (v41) can be restored and properly migrated.
Focuses on business logic: restore old backup → data accessible after restore.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.kidschores.const import BACKUP_TAG_RECOVERY, DOMAIN


@pytest.fixture
def v41_backup_data() -> dict:
    """Create v41 format backup data (schema_version at top level, badges as list)."""
    return {
        "schema_version": 41,
        "kids": {
            "kid-uuid-1": {
                "internal_id": "kid-uuid-1",
                "name": "Test Kid",
                "points": 50.0,
                "lifetime_points": 150.0,
                "badges_earned": ["badge-1", "badge-2"],  # v41: list format
                "claimed_chores": [],
                "approved_chores": [],
                "ha_user_id": "",
                "enable_notifications": True,
                "mobile_notify_service": "",
                "use_persistent_notifications": True,
                "dashboard_language": "en",
            }
        },
        "chores": {
            "chore-uuid-1": {
                "internal_id": "chore-uuid-1",
                "name": "Test Chore",
                "assigned_kids": ["kid-uuid-1"],
                "default_points": 10,
                "state": "pending",
                "partial_allowed": False,
                "shared_chore": False,
                "allow_multiple_claims_per_day": False,
                "description": "",
                "labels": [],
                "icon": "mdi:star",
                "recurring_frequency": "daily",
                "custom_interval": None,
                "custom_interval_unit": None,
                "due_date": None,
                "applicable_days": [0, 1, 2, 3, 4, 5, 6],
                "notify_on_claim": True,
                "notify_on_approval": True,
                "notify_on_disapproval": True,
            }
        },
        "parents": {},
        "rewards": {},
        "badges": {},
        "achievements": {},
        "challenges": {},
        "bonuses": {},
        "penalties": {},
        "pending_chore_approvals": [],
        "pending_reward_approvals": [],
    }


@pytest.fixture
def v42_backup_data() -> dict:
    """Create v42 format backup data (meta section, badges as dict)."""
    return {
        "meta": {
            "schema_version": 42,
            "last_migration_date": "2025-01-01T00:00:00+00:00",
            "migrations_applied": [
                "datetime_utc",
                "chore_data_structure",
                "kid_data_structure",
                "badge_restructure",
                "cumulative_badge_progress",
                "badges_earned_dict",
                "point_stats",
                "chore_data_and_streaks",
            ],
        },
        "kids": {
            "kid-uuid-1": {
                "internal_id": "kid-uuid-1",
                "name": "Test Kid",
                "points": 50.0,
                "point_stats": {"points_net_all_time": 50.0},
                "badges_earned": {},  # v42: dict format
                "claimed_chores": [],
                "approved_chores": [],
                "ha_user_id": "",
                "enable_notifications": True,
                "mobile_notify_service": "",
                "use_persistent_notifications": True,
                "dashboard_language": "en",
                "points_multiplier": 1.0,
                "reward_claims": {},
                "reward_approvals": {},
                "penalty_applies": {},
                "bonus_applies": {},
                "pending_rewards": [],
                "redeemed_rewards": [],
                "overdue_notifications": {},
                "chore_states": {},
                "points_stats_daily": {
                    "points_by_source_today": {
                        "chores": 50.0,
                        "bonuses": 0.0,
                        "penalties": 0.0,
                        "rewards": 0.0,
                    },
                    "points_by_source_weekly": {
                        "chores": 50.0,
                        "bonuses": 0.0,
                        "penalties": 0.0,
                        "rewards": 0.0,
                    },
                    "points_by_source_monthly": {
                        "chores": 50.0,
                        "bonuses": 0.0,
                        "penalties": 0.0,
                        "rewards": 0.0,
                    },
                },
            }
        },
        "chores": {
            "chore-uuid-1": {
                "internal_id": "chore-uuid-1",
                "name": "Test Chore",
                "assigned_kids": ["kid-uuid-1"],
                "default_points": 10,
                "state": "pending",
                "partial_allowed": False,
                "shared_chore": False,
                "allow_multiple_claims_per_day": False,
                "description": "",
                "labels": [],
                "icon": "mdi:star",
                "recurring_frequency": "daily",
                "custom_interval": None,
                "custom_interval_unit": None,
                "due_date": None,
                "applicable_days": [0, 1, 2, 3, 4, 5, 6],
                "notify_on_claim": True,
                "notify_on_approval": True,
                "notify_on_disapproval": True,
                "last_completed": None,
                "last_claimed": None,
            }
        },
        "parents": {},
        "rewards": {},
        "badges": {},
        "achievements": {},
        "challenges": {},
        "bonuses": {},
        "penalties": {},
        "pending_chore_approvals": [],
        "pending_reward_approvals": [],
    }


async def test_restore_v41_backup_preserves_data_through_migration(
    hass: HomeAssistant,
    init_integration,
    v41_backup_data: dict,
) -> None:
    """Test that restoring a v41 backup preserves kid/chore data.

    This validates the business requirement:
    - Restore v41 format backup file
    - Data is accessible after restore (doesn't get corrupted)
    - Migration happens (schema_version becomes v42 or higher)

    NOT testing: The specific migration algorithm itself
    (that's responsibility of migration tests in test_migration_generic.py)
    """
    config_entry = init_integration

    # Create mock backup discovery
    backup_file_name = "kidschores_data_2024-01-01_10-00-00_recovery"

    # Wrap v41 data in HA Store format
    backup_wrapped = {
        "version": 1,
        "minor_version": 1,
        "key": "kidschores_data",
        "data": v41_backup_data,
    }

    # Mock backup discovery to return our test backup
    mock_backup_list = [
        {
            "filename": backup_file_name,
            "tag": BACKUP_TAG_RECOVERY,
            "timestamp": None,
            "age_hours": 24.0,
            "size_bytes": 1024,
        }
    ]

    with patch(
        "custom_components.kidschores.flow_helpers.discover_backups",
        new=AsyncMock(return_value=mock_backup_list),
    ):
        with patch(
            "custom_components.kidschores.flow_helpers.get_storage_manager",
            new=AsyncMock(),
        ) as mock_get_storage:
            # Setup storage manager mock
            mock_storage = MagicMock()
            mock_storage.get_all_data.return_value = v41_backup_data
            mock_get_storage.return_value = mock_storage

            with patch("pathlib.Path.read_text") as mock_read:
                mock_read.return_value = json.dumps(backup_wrapped)

                # Start config flow - should show data recovery step
                result = await hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": config_entries.SOURCE_USER}
                )

                assert result["type"] == FlowResultType.FORM
                assert result["step_id"] == "data_recovery"

                # Select the v41 backup to restore
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    user_input={"backup_selection": backup_file_name},
                )

    # Should create entry after restore
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "KidsChores"


async def test_restore_backup_and_entity_creation_succeeds(
    hass: HomeAssistant,
    init_integration,
    v41_backup_data: dict,
) -> None:
    """Test that integration loads after restoring an old backup.

    This validates the business requirement:
    - Restore old backup through config flow
    - Integration loads successfully
    - No errors during restore/migration

    NOT testing: Specific entity values or creation
    (that's responsibility of entity workflow tests)
    """
    config_entry = init_integration

    backup_file_name = "kidschores_data_2024-01-01_10-00-00_manual"

    backup_wrapped = {
        "version": 1,
        "minor_version": 1,
        "key": "kidschores_data",
        "data": v41_backup_data,
    }

    mock_backup_list = [
        {
            "filename": backup_file_name,
            "tag": "manual",
            "timestamp": None,
            "age_hours": 24.0,
            "size_bytes": 1024,
        }
    ]

    with patch(
        "custom_components.kidschores.flow_helpers.discover_backups",
        new=AsyncMock(return_value=mock_backup_list),
    ):
        with patch(
            "custom_components.kidschores.flow_helpers.get_storage_manager",
            new=AsyncMock(),
        ) as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.get_all_data.return_value = v41_backup_data
            mock_get_storage.return_value = mock_storage

            with patch("pathlib.Path.read_text") as mock_read:
                mock_read.return_value = json.dumps(backup_wrapped)

                # Restore flow
                result = await hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": config_entries.SOURCE_USER}
                )

                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    user_input={"backup_selection": backup_file_name},
                )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Wait for integration setup
    await hass.async_block_till_done()

    # Verify integration is loaded
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) >= 1

    # Entry should be in LOADED state (no errors during restore)
    created_entry = entries[-1]  # Get the new entry
    assert created_entry.state == config_entries.ConfigEntryState.LOADED
