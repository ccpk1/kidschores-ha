"""Test specific user migration data."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kidschores.const import (
    CONF_POINTS_ICON,
    CONF_POINTS_LABEL,
    COORDINATOR,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_SHARED_CHORE_LEGACY,
    DEFAULT_POINTS_ICON,
    DEFAULT_POINTS_LABEL,
    DOMAIN,
)


async def setup_integration_with_migration_sample(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sample_data: dict,
) -> MockConfigEntry:
    """Set up integration with migration sample data."""
    config_entry.add_to_hass(hass)

    # Mock storage to return sample data (will trigger migration)
    with patch(
        "homeassistant.helpers.storage.Store.async_load",
        return_value=sample_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture
def migration_sample_user_ad_ha() -> dict:
    """Load user's actual migration data file (kidschores_data_ad-ha)."""
    sample_path = Path(__file__).parent / "migration_samples" / "kidschores_data_ad-ha"
    with open(sample_path, encoding="utf-8") as f:
        raw_data = json.load(f)
    return raw_data["data"]


@pytest.fixture
def mock_config_entry_for_migration() -> MockConfigEntry:
    """Create a config entry for migration testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="KidsChores Migration Test",
        data={},
        options={
            CONF_POINTS_LABEL: DEFAULT_POINTS_LABEL,
            CONF_POINTS_ICON: DEFAULT_POINTS_ICON,
        },
        entry_id="test_migration_entry",
        version=1,
        minor_version=1,
    )


async def test_user_migration_completion_criteria_conversion(
    hass: HomeAssistant,
    mock_config_entry_for_migration: MockConfigEntry,
    migration_sample_user_ad_ha: dict,
) -> None:
    """Test that user's data properly converts shared_chore to completion_criteria.

    This test uses the actual user's migration file (kidschores_data_ad-ha) which
    shows the issue where:
    - migration_key_version: 40 (should trigger migration)
    - No meta section exists
    - All chores have shared_chore boolean fields
    - No chores have completion_criteria fields

    After migration, all chores should have completion_criteria and no shared_chore.
    """
    # Verify the issue exists in the sample data
    assert "meta" not in migration_sample_user_ad_ha, (
        "User data should not have meta section"
    )
    assert "migration_key_version" in migration_sample_user_ad_ha, (
        "User data should have migration_key_version"
    )
    assert migration_sample_user_ad_ha["migration_key_version"] == 40, (
        "Should be version 40"
    )

    # Check that all chores have the old shared_chore field
    chores_data = migration_sample_user_ad_ha.get("chores", {})
    assert len(chores_data) > 0, "Should have some chores in test data"

    for chore_id, chore_data in chores_data.items():
        assert DATA_CHORE_SHARED_CHORE_LEGACY in chore_data, (
            f"Chore {chore_id} should have shared_chore field before migration"
        )
        assert DATA_CHORE_COMPLETION_CRITERIA not in chore_data, (
            f"Chore {chore_id} should NOT have completion_criteria field before migration"
        )

    # Setup integration (triggers migration)
    config_entry = await setup_integration_with_migration_sample(
        hass, mock_config_entry_for_migration, migration_sample_user_ad_ha
    )

    # Access coordinator
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Verify migration worked - all chores should now have completion_criteria
    for chore_id, chore_data in coordinator.chores_data.items():
        assert DATA_CHORE_COMPLETION_CRITERIA in chore_data, (
            f"Chore {chore_id} ('{chore_data.get('name')}') missing completion_criteria after migration"
        )
        assert DATA_CHORE_SHARED_CHORE_LEGACY not in chore_data, (
            f"Chore {chore_id} ('{chore_data.get('name')}') still has legacy shared_chore field after migration"
        )

    print(f"✅ Migration successful: {len(coordinator.chores_data)} chores converted")

    # Test specific chores mentioned in the issue
    declutter_chore = None
    brushteeth_chore = None

    for chore_id, chore_data in coordinator.chores_data.items():
        if chore_data.get("name") == "Declutter & Organize":
            declutter_chore = chore_data
        elif chore_data.get("name") == "Brushteeth - Night":
            brushteeth_chore = chore_data

    assert declutter_chore is not None, "Should find 'Declutter & Organize' chore"
    assert brushteeth_chore is not None, "Should find 'Brushteeth - Night' chore"

    # Declutter was shared_chore: true, should become "shared_all"
    assert declutter_chore[DATA_CHORE_COMPLETION_CRITERIA] == "shared_all", (
        "Declutter chore should be converted to shared_all"
    )

    # Brushteeth was shared_chore: false, should become "independent"
    assert brushteeth_chore[DATA_CHORE_COMPLETION_CRITERIA] == "independent", (
        "Brushteeth chore should be converted to independent"
    )

    print("✅ Specific chore conversions verified:")
    print(
        f"  Declutter & Organize: shared_chore=true → completion_criteria={declutter_chore[DATA_CHORE_COMPLETION_CRITERIA]}"
    )
    print(
        f"  Brushteeth - Night: shared_chore=false → completion_criteria={brushteeth_chore[DATA_CHORE_COMPLETION_CRITERIA]}"
    )
