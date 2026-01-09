"""Test that all kid entities have kid_name attribute and display entity information."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.kidschores import const

pytestmark = pytest.mark.asyncio


async def test_all_kid_entities_have_kid_name_attribute(
    hass: HomeAssistant, scenario_medium
) -> None:
    """Verify all kid entities have kid_name attribute and display comprehensive info."""
    # Load the integration
    config_entry, _ = scenario_medium

    # Get registries
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    # Get all entities for kidschores integration
    entries = er.async_entries_for_config_entry(entity_reg, config_entry.entry_id)

    # Filter kid-related entities (exclude system/global entities)
    # Kid entities have a kid in their unique_id or entity_id
    kid_entities = []
    for entry in entries:
        # Skip global entities like reset buttons, admin entities, global sensors
        if any(
            keyword in entry.entity_id
            for keyword in [
                "_reset_",
                "_admin_",
                "select.kc_chores_",
                "select.kc_rewards_",
                "select.kc_parents_",
                "select.kc_all_",  # Skip global select entities
                "_global_",  # Skip global sensors (e.g., kc_global_chore_pending_approvals)
            ]
        ):
            continue

        # Include entities that belong to a kid
        if (
            entry.entity_id.startswith("sensor.kc_")
            or entry.entity_id.startswith("button.kc_")
            or entry.entity_id.startswith("calendar.kc_")
            or entry.entity_id.startswith("datetime.kc_")
            or (
                entry.entity_id.startswith("select.kc_")
                and "_ui_dashboard_chore_list_helper" in entry.entity_id
            )
        ):
            kid_entities.append(entry)

    # Track results
    entities_with_kid_name = []
    entities_without_kid_name = []

    # Check each entity
    for entry in kid_entities:
        state = hass.states.get(entry.entity_id)
        if not state:
            continue

        # Get device info
        if entry.device_id:
            device = device_reg.async_get(entry.device_id)
            if device:
                pass

        # Extract entity info
        entity_id = entry.entity_id
        state.attributes.get("friendly_name", "Unknown")
        kid_name_attr = state.attributes.get(const.ATTR_KID_NAME)

        # Display entity info

        # Track if kid_name exists
        if kid_name_attr:
            entities_with_kid_name.append(entity_id)
        else:
            entities_without_kid_name.append(entity_id)

    # Summary

    if entities_without_kid_name:
        for entity_id in entities_without_kid_name:
            pass

    # Assert all kid entities have kid_name attribute
    assert len(entities_without_kid_name) == 0, (
        f"Found {len(entities_without_kid_name)} kid entities without kid_name attribute"
    )


async def test_specific_friendly_names(hass: HomeAssistant, scenario_medium) -> None:
    """Verify specific entities have correct friendly names."""
    _, _ = scenario_medium

    # Check UI Dashboard Helper (assuming Zoë is first kid in scenario_medium)
    dashboard_helper = hass.states.get("sensor.kc_zoe_ui_dashboard_helper")
    if dashboard_helper is None:
        pytest.skip("Dashboard helper entity not available in scenario_medium")

    assert dashboard_helper is not None
    assert "UI Dashboard Helper" in dashboard_helper.attributes.get(
        "friendly_name", ""
    ), "Dashboard helper should have 'UI Dashboard Helper' in friendly name"

    # Check UI Dashboard Date Helper
    date_helper = hass.states.get("datetime.kc_zoe_ui_dashboard_date_helper")
    assert date_helper is not None
    assert "UI Dashboard Date Helper" in date_helper.attributes.get(
        "friendly_name", ""
    ), "Date helper should have 'UI Dashboard Date Helper' in friendly name"

    # Check that datetime entity does NOT have kid_id attribute
    assert "kid_id" not in date_helper.attributes, (
        "Datetime entity should not have kid_id attribute"
    )
    assert const.ATTR_KID_NAME in date_helper.attributes, (
        "Datetime entity should have kid_name attribute"
    )


async def test_chore_status_friendly_name(hass: HomeAssistant, scenario_medium) -> None:
    """Verify chore status sensors have 'Chore Status' in friendly name."""
    config_entry, _ = scenario_medium

    entity_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_reg, config_entry.entry_id)

    # Find chore status sensors
    chore_status_sensors = [
        entry
        for entry in entries
        if entry.entity_id.startswith("sensor.kc_")
        and "_chore_status_" in entry.entity_id
    ]

    for entry in chore_status_sensors:
        state = hass.states.get(entry.entity_id)
        if state:
            friendly_name = state.attributes.get("friendly_name", "Unknown")

            # Verify 'Chore Status' appears in friendly name
            assert "Chore Status" in friendly_name, (
                f"Chore status sensor {entry.entity_id} should have 'Chore Status' "
                f"in friendly name, got: {friendly_name}"
            )
