# File: __init__.py
"""Initialization file for the KidsChores integration.

Handles setting up the integration, including loading configuration entries,
initializing data storage, and preparing the coordinator for data handling.

Key Features:
- Config entry setup and unload support.
- Coordinator initialization for data synchronization.
- Storage management for persistent data handling.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import const
from .coordinator import KidsChoresDataCoordinator
from .notification_action_handler import async_handle_notification_action
from .services import async_setup_services, async_unload_services
from .storage_manager import KidsChoresStorageManager


async def _migrate_config_to_storage(
    hass: HomeAssistant, entry: ConfigEntry, storage_manager: KidsChoresStorageManager
) -> None:
    """One-time migration: Move entity data from config_entry.options to storage.

    This migration runs once to transition from the legacy KC 3.x "config as source of truth"
    architecture to the new KC 4.x "storage as source of truth" architecture.

    System settings (points_label, points_icon, update_interval) remain in config.
    All entity definitions (kids, chores, badges, etc.) move to storage.

    Args:
        hass: Home Assistant instance
        entry: Config entry to migrate
        storage_manager: Initialized storage manager

    """
    storage_data = storage_manager.get_data()
    storage_version = storage_data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO)

    # Check if migration is needed
    if storage_version >= const.SCHEMA_VERSION_STORAGE_ONLY:
        const.LOGGER.info(
            "INFO: Storage schema version %s already >= %s, skipping config→storage migration",
            storage_version,
            const.SCHEMA_VERSION_STORAGE_ONLY,
        )
        return

    # Check if config has entity data to migrate
    config_has_entities = any(
        key in entry.options
        for key in [
            const.CONF_KIDS,
            const.CONF_CHORES,
            const.CONF_BADGES,
            const.CONF_REWARDS,
            const.CONF_PARENTS,
            const.CONF_PENALTIES,
            const.CONF_BONUSES,
            const.CONF_ACHIEVEMENTS,
            const.CONF_CHALLENGES,
        ]
    )

    if not config_has_entities:
        const.LOGGER.info(
            "INFO: No entity data in config_entry.options, setting storage version to %s (clean install)",
            const.SCHEMA_VERSION_STORAGE_ONLY,
        )
        # Clean install - just set version and save
        storage_data[const.DATA_SCHEMA_VERSION] = const.SCHEMA_VERSION_STORAGE_ONLY
        storage_manager.set_data(storage_data)
        await storage_manager.async_save()
        return

    # Migration needed: config has entities and storage version < 42
    const.LOGGER.info("INFO: ========================================")
    const.LOGGER.info(
        "INFO: Starting config→storage migration (schema version %s → %s)",
        storage_version,
        const.SCHEMA_VERSION_STORAGE_ONLY,
    )

    # Create backup of storage data before migration
    try:
        import shutil
        from datetime import datetime
        from pathlib import Path

        backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = Path(storage_manager.get_storage_path())
        backup_path = (
            storage_path.parent / f"{storage_path.name}_backup_{backup_timestamp}"
        )

        if storage_path.exists():
            shutil.copy2(str(storage_path), str(backup_path))
            const.LOGGER.info(
                "INFO: Created pre-migration backup: %s", backup_path.name
            )
    except Exception as err:  # pylint: disable=broad-exception-caught
        const.LOGGER.warning("WARNING: Failed to create pre-migration backup: %s", err)

    # Define fields that should NOT be migrated from config (relational/runtime fields)
    # IMPORTANT: These fields in OLD config data may have stale/incorrect data:
    # - Relational fields may contain entity NAMES instead of INTERNAL_IDS
    # - Runtime state fields should never come from config
    # By excluding these fields, we preserve the correct data already in storage
    excluded_fields_by_type = {
        const.DATA_CHORES: {
            "assigned_kids",  # May contain names instead of internal_ids
            "state",
            "last_completed",
            "last_claimed",
        },
        const.DATA_PARENTS: {
            "associated_kids",  # May contain names instead of internal_ids
        },
        const.DATA_BADGES: {
            "assigned_to",  # May contain names instead of internal_ids
        },
        const.DATA_ACHIEVEMENTS: {
            "assigned_kids",  # May contain names instead of internal_ids
            "selected_chore_id",  # May contain name instead of internal_id
            "progress",  # Runtime data
        },
        const.DATA_CHALLENGES: {
            "assigned_kids",  # May contain names instead of internal_ids
            "selected_chore_id",  # May contain name instead of internal_id
            "progress",  # Runtime data
        },
    }

    # Merge entity data from config into storage (preserving existing state)
    entity_sections = [
        (const.CONF_KIDS, const.DATA_KIDS),
        (const.CONF_PARENTS, const.DATA_PARENTS),
        (const.CONF_CHORES, const.DATA_CHORES),
        (const.CONF_BADGES, const.DATA_BADGES),
        (const.CONF_REWARDS, const.DATA_REWARDS),
        (const.CONF_PENALTIES, const.DATA_PENALTIES),
        (const.CONF_BONUSES, const.DATA_BONUSES),
        (const.CONF_ACHIEVEMENTS, const.DATA_ACHIEVEMENTS),
        (const.CONF_CHALLENGES, const.DATA_CHALLENGES),
    ]

    for config_key, data_key in entity_sections:
        config_entities = entry.options.get(config_key, {})
        if config_entities:
            # Merge config entities into storage (config is source of truth for definitions)
            if data_key not in storage_data:
                storage_data[data_key] = {}

            # Get excluded fields for this entity type
            excluded_fields = excluded_fields_by_type.get(data_key, set())

            # For each entity from config, merge with existing storage data
            # Preserve all existing runtime data, only update definition fields
            for entity_id, config_entity_data in config_entities.items():
                if entity_id in storage_data[data_key]:
                    # Entity exists in storage - update only definition fields, preserve runtime data
                    existing_entity = storage_data[data_key][entity_id]
                    # Only update fields that are not excluded
                    for field, value in config_entity_data.items():
                        if field not in excluded_fields:
                            existing_entity[field] = value
                else:
                    # New entity - add from config
                    storage_data[data_key][entity_id] = config_entity_data

                # For kids, ensure each kid has the overdue_notifications field
                if config_key == const.CONF_KIDS:
                    if (
                        const.DATA_KID_OVERDUE_NOTIFICATIONS
                        not in storage_data[data_key][entity_id]
                    ):
                        storage_data[data_key][entity_id][
                            const.DATA_KID_OVERDUE_NOTIFICATIONS
                        ] = {}

            const.LOGGER.debug(
                "DEBUG: Migrated %s %s from config to storage",
                len(config_entities),
                config_key,
            )

    # Set new schema version
    storage_data[const.DATA_SCHEMA_VERSION] = const.SCHEMA_VERSION_STORAGE_ONLY

    # Save merged data to storage
    storage_manager.set_data(storage_data)
    await storage_manager.async_save()

    # Build new config with ONLY system settings
    new_options = {
        const.CONF_POINTS_LABEL: entry.options.get(
            const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
        ),
        const.CONF_POINTS_ICON: entry.options.get(
            const.CONF_POINTS_ICON, const.DEFAULT_POINTS_ICON
        ),
        const.CONF_UPDATE_INTERVAL: entry.options.get(
            const.CONF_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
        ),
        const.CONF_POINTS_ADJUST_VALUES: entry.options.get(
            const.CONF_POINTS_ADJUST_VALUES, const.DEFAULT_POINTS_ADJUST_VALUES
        ),
        const.CONF_CALENDAR_SHOW_PERIOD: entry.options.get(
            const.CONF_CALENDAR_SHOW_PERIOD, const.DEFAULT_CALENDAR_SHOW_PERIOD
        ),
        const.CONF_RETENTION_DAILY: entry.options.get(
            const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
        ),
        const.CONF_RETENTION_WEEKLY: entry.options.get(
            const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
        ),
        const.CONF_RETENTION_MONTHLY: entry.options.get(
            const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
        ),
        const.CONF_RETENTION_YEARLY: entry.options.get(
            const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
        ),
        const.CONF_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
    }

    # Update config entry with cleaned options
    hass.config_entries.async_update_entry(entry, options=new_options)

    const.LOGGER.info(
        "INFO: ✓ Config→storage migration complete! Entity data now in storage, system settings in config."
    )
    const.LOGGER.info("INFO: ========================================")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    const.LOGGER.info("INFO: Starting setup for KidsChores entry: %s", entry.entry_id)

    # Set the home assistant configured timezone for date/time operations
    # Must be done early before any components that use datetime helpers
    const.set_default_timezone(hass)

    # Initialize the storage manager to handle persistent data.
    storage_manager = KidsChoresStorageManager(hass, const.STORAGE_KEY)
    # Initialize new file.
    await storage_manager.async_initialize()

    # PHASE 2: Migrate entity data from config to storage (one-time hand-off)
    # This must happen BEFORE coordinator initialization to ensure coordinator
    # loads from storage-only mode (schema_version >= 42)
    await _migrate_config_to_storage(hass, entry, storage_manager)

    # Create the data coordinator for managing updates and synchronization.
    coordinator = KidsChoresDataCoordinator(hass, entry, storage_manager)

    try:
        # Perform the first refresh to load data.
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as e:
        const.LOGGER.error("ERROR: Failed to refresh coordinator data: %s", e)
        raise ConfigEntryNotReady from e

    # Store the coordinator and data manager in hass.data.
    hass.data.setdefault(const.DOMAIN, {})[entry.entry_id] = {
        const.COORDINATOR: coordinator,
        const.STORAGE_MANAGER: storage_manager,
    }

    # Set up services required by the integration.
    async_setup_services(hass)

    # Forward the setup to supported platforms (sensors, buttons, etc.).
    await hass.config_entries.async_forward_entry_setups(entry, const.PLATFORMS)

    # Listen for notification actions from the companion app.
    async def handle_notification_event(event):
        """Handle notification action events."""
        await async_handle_notification_action(hass, event)

    hass.bus.async_listen(const.NOTIFICATION_EVENT, handle_notification_event)

    const.LOGGER.info("INFO: KidsChores setup complete for entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    const.LOGGER.info("INFO: Unloading KidsChores entry: %s", entry.entry_id)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, const.PLATFORMS)

    if unload_ok:
        hass.data[const.DOMAIN].pop(entry.entry_id)

        # Await service unloading
        await async_unload_services(hass)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a config entry."""
    const.LOGGER.info("INFO: Removing KidsChores entry: %s", entry.entry_id)

    # Safely check if data exists before attempting to access it
    if const.DOMAIN in hass.data and entry.entry_id in hass.data[const.DOMAIN]:
        storage_manager: KidsChoresStorageManager = hass.data[const.DOMAIN][
            entry.entry_id
        ][const.STORAGE_MANAGER]
        await storage_manager.async_delete_storage()

    const.LOGGER.info("INFO: KidsChores entry data cleared: %s", entry.entry_id)
