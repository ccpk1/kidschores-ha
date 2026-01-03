#!/usr/bin/env python3
"""Debug migration issue for user's data file."""

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


async def debug_user_migration(hass: HomeAssistant):
    """Test migration with user's actual data."""
    # Load user's data
    sample_path = Path("tests/migration_samples/kidschores_data_ad-ha")
    with open(sample_path, encoding="utf-8") as f:
        raw_data = json.load(f)

    sample_data = raw_data["data"]

    print("=== BEFORE MIGRATION ===")
    print(
        f"Version fields: migration_key_version={sample_data.get('migration_key_version')}"
    )
    print(f"Has schema_version: {'schema_version' in sample_data}")
    print(f"Has meta: {'meta' in sample_data}")

    # Check sample chore
    sample_chore_id = list(sample_data["chores"].keys())[0]
    sample_chore = sample_data["chores"][sample_chore_id]
    print(f"Sample chore '{sample_chore['name']}':")
    print(f"  Has shared_chore: {DATA_CHORE_SHARED_CHORE_LEGACY in sample_chore}")
    print(f"  shared_chore value: {sample_chore.get(DATA_CHORE_SHARED_CHORE_LEGACY)}")
    print(
        f"  Has completion_criteria: {DATA_CHORE_COMPLETION_CRITERIA in sample_chore}"
    )

    # Create config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="KidsChores Debug",
        data={},
        options={
            CONF_POINTS_LABEL: DEFAULT_POINTS_LABEL,
            CONF_POINTS_ICON: DEFAULT_POINTS_ICON,
        },
        entry_id="debug_migration",
    )
    config_entry.add_to_hass(hass)

    # Mock storage to return user's data
    with patch(
        "homeassistant.helpers.storage.Store.async_load",
        return_value=sample_data,
    ):
        # Setup integration (should trigger migration)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Check results
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    print("\n=== AFTER MIGRATION ===")
    print(f"Total chores: {len(coordinator.chores_data)}")

    # Check the same sample chore after migration
    if sample_chore_id in coordinator.chores_data:
        migrated_chore = coordinator.chores_data[sample_chore_id]
        print(f"Sample chore '{migrated_chore.get('name')}':")
        print(f"  Has shared_chore: {DATA_CHORE_SHARED_CHORE_LEGACY in migrated_chore}")
        print(
            f"  Has completion_criteria: {DATA_CHORE_COMPLETION_CRITERIA in migrated_chore}"
        )
        if DATA_CHORE_COMPLETION_CRITERIA in migrated_chore:
            print(
                f"  completion_criteria value: {migrated_chore[DATA_CHORE_COMPLETION_CRITERIA]}"
            )
    else:
        print("ERROR: Sample chore not found in migrated data!")

    # Check all chores for field conversion
    shared_chore_count = 0
    completion_criteria_count = 0
    for chore_id, chore_data in coordinator.chores_data.items():
        if DATA_CHORE_SHARED_CHORE_LEGACY in chore_data:
            shared_chore_count += 1
        if DATA_CHORE_COMPLETION_CRITERIA in chore_data:
            completion_criteria_count += 1

    print(f"\nField conversion summary:")
    print(f"  Chores with shared_chore: {shared_chore_count}")
    print(f"  Chores with completion_criteria: {completion_criteria_count}")
    print(f"  Total chores: {len(coordinator.chores_data)}")

    if shared_chore_count > 0:
        print("❌ MIGRATION FAILED: Some chores still have shared_chore field")
    else:
        print("✅ MIGRATION SUCCESS: All shared_chore fields removed")

    if completion_criteria_count == len(coordinator.chores_data):
        print("✅ MIGRATION SUCCESS: All chores have completion_criteria field")
    else:
        print("❌ MIGRATION FAILED: Some chores missing completion_criteria field")


# Convert to pytest test
@pytest.mark.asyncio
async def test_debug_user_migration(hass: HomeAssistant):
    """Test user migration as a pytest test."""
    await debug_user_migration(hass)


if __name__ == "__main__":
    print(
        "Run with: python -m pytest test_debug_migration.py::test_debug_user_migration -v -s"
    )
