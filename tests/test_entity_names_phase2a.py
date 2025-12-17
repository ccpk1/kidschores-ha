"""Test entity names and translations after Phase 2A fixes."""

import pytest
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from custom_components.kidschores import const


@pytest.fixture
def platforms():
    """Platforms to load for this test."""
    return [Platform.SENSOR, Platform.BUTTON, Platform.SELECT, Platform.CALENDAR]


@pytest.mark.asyncio
async def test_entity_names_with_translations(scenario_minimal, entity_registry):
    """Test that entities show proper friendly names via translation system."""
    config_entry, _ = scenario_minimal

    # Get all entities for config entry
    all_entities = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    # Verify we have entities
    assert len(all_entities) > 0, "Should have entities registered"

    # Count entities with translation keys
    entities_with_translations = [
        e for e in all_entities if e.translation_key is not None
    ]

    print(f"\n✅ Total entities: {len(all_entities)}")
    print(f"✅ Entities with translation_key: {len(entities_with_translations)}")

    # Verify most entities have translation keys (should be high percentage)
    translation_percentage = (len(entities_with_translations) / len(all_entities)) * 100
    assert translation_percentage > 80, (
        f"Only {translation_percentage:.1f}% of entities have translation_key"
    )
    print(f"✅ Translation coverage: {translation_percentage:.1f}%")


@pytest.mark.asyncio
async def test_calendar_has_translation_attributes(hass, scenario_minimal):
    """Test calendar entity has proper translation setup."""
    config_entry, _ = scenario_minimal
    _ = hass.data[const.DOMAIN][config_entry.entry_id][const.COORDINATOR]

    # Get calendar entity
    calendar_entities = []
    for entity_id in hass.states.async_entity_ids("calendar"):
        if "kidschores" in entity_id or "kc_" in entity_id:
            calendar_entities.append(entity_id)

    assert len(calendar_entities) > 0, "Should have at least one calendar entity"

    calendar_entity_id = calendar_entities[0]
    state = hass.states.get(calendar_entity_id)

    assert state is not None, f"Calendar entity {calendar_entity_id} should have state"
    assert state.attributes.get("friendly_name") is not None, (
        "Should have friendly_name attribute"
    )
    print(f"✅ Calendar friendly_name: {state.attributes['friendly_name']}")


@pytest.mark.asyncio
async def test_select_has_translation_attributes(hass, scenario_minimal):
    """Test select entity has proper translation setup."""
    _, _ = scenario_minimal  # config_entry not needed for this test

    # Get select entities
    select_entities = []
    for entity_id in hass.states.async_entity_ids("select"):
        if "kidschores" in entity_id or "kc_" in entity_id:
            select_entities.append(entity_id)

    assert len(select_entities) > 0, "Should have at least one select entity"

    select_entity_id = select_entities[0]
    state = hass.states.get(select_entity_id)

    assert state is not None, f"Select entity {select_entity_id} should have state"
    assert state.attributes.get("friendly_name") is not None, (
        "Should have friendly_name attribute"
    )
    print(f"✅ Select friendly_name: {state.attributes['friendly_name']}")
