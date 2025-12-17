"""Tests for legacy sensor toggle functionality."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.kidschores import const

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_legacy_sensors_created_when_enabled(
    hass: HomeAssistant,
    mock_config_entry,  # pylint: disable=unused-argument
    mock_coordinator,  # pylint: disable=unused-argument
):
    """Test that legacy sensors are created when show_legacy_entities is True."""
    # The mock_config_entry fixture has show_legacy_entities = True by default
    entity_registry = er.async_get(hass)

    # Count legacy sensor entities
    legacy_sensors = []
    for entity in entity_registry.entities.values():
        if entity.domain == "sensor" and const.DOMAIN in entity.platform:
            # Legacy sensor patterns
            if any(
                pattern in entity.unique_id
                for pattern in [
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_HIGHEST_STREAK_SENSOR,
                ]
            ):
                legacy_sensors.append(entity.entity_id)

    # With no kids, expect only 2 global legacy sensors:
    # - pending_chore_approvals
    # - pending_reward_approvals
    # Per-kid legacy sensors only created when kids exist
    assert len(legacy_sensors) == 2, (
        f"Expected exactly 2 global legacy sensors (no kids configured), "
        f"found {len(legacy_sensors)}: {legacy_sensors}"
    )

    # Verify the specific sensors present
    assert any("pending" in s and "chore" in s for s in legacy_sensors), (
        "Missing pending chore approvals sensor"
    )
    assert any("pending" in s and "reward" in s for s in legacy_sensors), (
        "Missing pending reward approvals sensor"
    )


@pytest.mark.skip(reason="Need to implement fixture with disabled legacy sensors")
async def test_legacy_sensors_not_created_when_disabled(hass: HomeAssistant):
    """Test that legacy sensors are NOT created when show_legacy_entities is False."""
    entity_registry = er.async_get(hass)

    # Count legacy sensor entities
    legacy_sensors = []
    for entity in entity_registry.entities.values():
        if entity.domain == "sensor" and const.DOMAIN in entity.platform:
            # Legacy sensor patterns
            if any(
                pattern in entity.unique_id
                for pattern in [
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR,
                    const.SENSOR_KC_UID_SUFFIX_KID_HIGHEST_STREAK_SENSOR,
                ]
            ):
                legacy_sensors.append(entity.entity_id)

    assert len(legacy_sensors) == 0, (
        f"Expected 0 legacy sensors when disabled, "
        f"found {len(legacy_sensors)}: {legacy_sensors}"
    )


@pytest.mark.skip(reason="Need to implement proper reload test")
async def test_legacy_sensors_removed_when_option_changed(
    hass: HomeAssistant,  # pylint: disable=unused-argument
):
    """Test that legacy sensors are removed when show_legacy_entities changes from True to False."""
    # This test requires implementing proper config entry reload logic
    pass
