"""Debug script to check entity name attributes."""

import asyncio
import sys

sys.path.insert(0, "/workspaces/core")

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.conftest import load_scenario_yaml


async def main():
    """Check entity attributes for name/device configuration."""
    hass = HomeAssistant("/tmp/test_ha")
    await hass.async_start()

    # Load test scenario
    from tests.conftest import load_scenario_yaml

    scenario_data = load_scenario_yaml("testdata_scenario_minimal.yaml")

    # Set up the integration with scenario data
    await async_setup_component(hass, "kidschores", {})

    # Get config entry
    from custom_components.kidschores import const

    entries = hass.config_entries.async_entries(const.DOMAIN)

    if not entries:
        print("❌ No config entry found")
        return

    entry = entries[0]
    print(f"✅ Config entry: {entry.title}")

    # Load coordinator
    if const.DOMAIN not in hass.data or entry.entry_id not in hass.data[const.DOMAIN]:
        print("❌ Coordinator not loaded")
        return

    coordinator = hass.data[const.DOMAIN][entry.entry_id][const.COORDINATOR]

    # Check entity states
    print("\n📊 Entity Registry Check:")
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)

    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    print(f"Total entities registered: {len(entities)}")

    # Check a few sample entities
    for entity in list(entities)[:5]:
        print(f"\n🔍 Entity: {entity.entity_id}")
        print(f"   Unique ID: {entity.unique_id}")
        print(f"   Original Name: {entity.original_name}")
        print(f"   Name: {entity.name}")
        print(f"   Translation Key: {entity.translation_key}")
        print(f"   Device ID: {entity.device_id}")

        # Check actual entity object
        state = hass.states.get(entity.entity_id)
        if state:
            print(f"   Friendly Name: {state.attributes.get('friendly_name', 'N/A')}")
            print(f"   State: {state.state}")

    # Check device registry
    print("\n🖥️  Device Registry Check:")
    from homeassistant.helpers import device_registry as dr

    dev_registry = dr.async_get(hass)

    devices = dr.async_entries_for_config_entry(dev_registry, entry.entry_id)
    print(f"Total devices: {len(devices)}")

    for device in devices:
        print(f"\n🔧 Device: {device.name}")
        print(f"   Model: {device.model}")
        print(f"   Identifiers: {device.identifiers}")

    await hass.async_stop()


if __name__ == "__main__":
    asyncio.run(main())
