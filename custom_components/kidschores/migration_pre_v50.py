"""Migration logic for pre-v50 schema data.

This module handles one-time migrations from pre-v50 (legacy) data structures
to the v50+ storage-only architecture. These migrations are only executed
when upgrading from legacy configurations to the modern data model.

DEPRECATION NOTICE: This module can be removed in the future when the vast majority
of users have upgraded past v50. The migration logic is frozen and will not be
modified further. Modern installations (KC-v0.5.0+) skip this module entirely via
lazy import to avoid any runtime cost.
"""

from collections import Counter
from datetime import datetime
import random
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from . import const, data_builders as db, kc_helpers as kh
from .helpers import backup_helpers as bh, entity_helpers as eh
from .store import KidsChoresStore
from .utils.dt_utils import dt_now_local, dt_to_utc, dt_today_iso, dt_today_local
from .utils.math_utils import parse_points_adjust_values

if TYPE_CHECKING:
    from .coordinator import KidsChoresDataCoordinator


# ================================================================================================
# KC 3.x → 4.x Config-to-Storage Migration (runs BEFORE coordinator init)
# ================================================================================================


async def migrate_config_to_storage(
    hass: HomeAssistant, entry: ConfigEntry, store: KidsChoresStore
) -> None:
    """One-time migration: Move entity data from config_entry.options to storage.

    This migration runs once to transition from the legacy KC 3.x "config as source of truth"
    architecture to the new KC 4.x "storage as source of truth" architecture.

    System settings (points_label, points_icon, update_interval) remain in config.
    All entity definitions (kids, chores, badges, etc.) move to storage.

    Args:
        hass: Home Assistant instance
        entry: Config entry to migrate
        store: Initialized store instance

    """
    storage_data = store.data

    # Check schema version - support both v41 (top-level) and v42+ (meta section)
    # v41 format: {"schema_version": 41, "kids": {...}}
    # v42+ format: {"meta": {"schema_version": 42}, "kids": {...}}
    meta_section = storage_data.get(const.DATA_META, {})
    storage_version = meta_section.get(
        const.DATA_META_SCHEMA_VERSION,
        storage_data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
    )

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
            const.CONF_KIDS_LEGACY,
            const.CONF_CHORES_LEGACY,
            const.CONF_BADGES_LEGACY,
            const.CONF_REWARDS_LEGACY,
            const.CONF_PARENTS_LEGACY,
            const.CONF_PENALTIES_LEGACY,
            const.CONF_BONUSES_LEGACY,
            const.CONF_ACHIEVEMENTS_LEGACY,
            const.CONF_CHALLENGES_LEGACY,
        ]
    )

    # Also check if storage already has entity data (handles storage-based v3.x installations)
    storage_has_entities = any(
        len(storage_data.get(key, {})) > 0
        for key in [
            const.DATA_KIDS,
            const.DATA_CHORES,
            const.DATA_BADGES,
            const.DATA_REWARDS,
        ]
    )

    # Only treat as clean install if BOTH config and storage are empty
    if not config_has_entities and not storage_has_entities:
        const.LOGGER.info(
            "INFO: No entity data in config or storage, setting storage version to %s (clean install)",
            const.SCHEMA_VERSION_STORAGE_ONLY,
        )
        # Clean install - set version in meta section and save
        from homeassistant.util import dt as dt_util

        storage_data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_LAST_MIGRATION_DATE: dt_util.utcnow().isoformat(),
            const.DATA_META_MIGRATIONS_APPLIED: [],
        }
        store.set_data(storage_data)
        await store.async_save()
        return

    # Storage-only data (Config Flow import path): let coordinator handle all migrations
    if not config_has_entities and storage_has_entities:
        const.LOGGER.info(
            "INFO: Storage has data but config is empty (schema v%s). Coordinator will handle migrations.",
            storage_version,
        )
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
        backup_name = await bh.create_timestamped_backup(
            hass, store, const.BACKUP_TAG_PRE_MIGRATION
        )
        if backup_name:
            const.LOGGER.info("INFO: Created pre-migration backup: %s", backup_name)
        else:
            const.LOGGER.warning("WARNING: No data available for pre-migration backup")
    except Exception as err:
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
        (const.CONF_KIDS_LEGACY, const.DATA_KIDS),
        (const.CONF_PARENTS_LEGACY, const.DATA_PARENTS),
        (const.CONF_CHORES_LEGACY, const.DATA_CHORES),
        (const.CONF_BADGES_LEGACY, const.DATA_BADGES),
        (const.CONF_REWARDS_LEGACY, const.DATA_REWARDS),
        (const.CONF_PENALTIES_LEGACY, const.DATA_PENALTIES),
        (const.CONF_BONUSES_LEGACY, const.DATA_BONUSES),
        (const.CONF_ACHIEVEMENTS_LEGACY, const.DATA_ACHIEVEMENTS),
        (const.CONF_CHALLENGES_LEGACY, const.DATA_CHALLENGES),
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

                # For kids, ensure each kid has the required v42 fields
                if config_key == const.CONF_KIDS_LEGACY:
                    # Add overdue_notifications field if missing
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

    # Set new schema version in meta section
    from homeassistant.util import dt as dt_util

    storage_data[const.DATA_META] = {
        const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
        const.DATA_META_LAST_MIGRATION_DATE: dt_util.utcnow().isoformat(),
        const.DATA_META_MIGRATIONS_APPLIED: ["config_to_storage"],
    }
    # Remove old top-level schema_version if present
    storage_data.pop(const.DATA_SCHEMA_VERSION, None)

    # Save merged data to storage
    store.set_data(storage_data)
    await store.async_save()

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
        const.CONF_SCHEMA_VERSION_LEGACY: const.SCHEMA_VERSION_STORAGE_ONLY,
    }

    # Update config entry with cleaned options
    hass.config_entries.async_update_entry(entry, options=new_options)

    const.LOGGER.info(
        "INFO: ✓ Config→storage migration complete! Entity data now in storage, system settings in config."
    )
    const.LOGGER.info("INFO: ========================================")


# ================================================================================================
# Coordinator Data Migrations (run AFTER coordinator init, when storage schema < 50)
# ================================================================================================


class PreV50Migrator:
    """Handles all pre-v50 schema migrations.

    This class encapsulates the legacy migration logic that transforms
    pre-v50 data structures to the modern storage-only v50+ format.
    All migrations are one-time operations executed on first coordinator startup
    for users upgrading from older versions.

    Attributes:
        coordinator: Reference to the KidsChoresDataCoordinator instance.
    """

    # This migration class intentionally accesses coordinator private methods and data

    def __init__(self, coordinator: "KidsChoresDataCoordinator") -> None:
        """Initialize the migrator with coordinator reference.

        Args:
            coordinator: The KidsChoresDataCoordinator instance to migrate data for.
        """
        self.coordinator = coordinator

    def run_all_migrations(self) -> None:
        """Execute all pre-v50 migrations in the correct order.

        Migrations are run sequentially with proper error handling and logging.
        Each migration is idempotent - it can be run multiple times without
        causing data corruption or duplication.
        """
        const.LOGGER.info(
            "Starting pre-v50 schema migrations for upgrade to modern format"
        )

        # Phase 1: Schema migrations (data structure transformations)
        self._migrate_datetime_wrapper()
        self._migrate_stored_datetimes()
        self._migrate_chore_data()
        self._migrate_kid_data()
        self._migrate_legacy_kid_chore_data_and_streaks()
        self._migrate_badges()
        self._migrate_kid_legacy_badges_to_cumulative_progress()
        self._migrate_kid_legacy_badges_to_badges_earned()
        self._migrate_legacy_point_stats()

        # Phase 2: Config sync (KC 3.x entity data from config → storage)
        # Phase 2: Independent chores migration (populate per-kid due dates)
        self._migrate_independent_chores()

        # Phase 2a: Per-kid applicable days migration (PKAD-2026-001)
        self._migrate_per_kid_applicable_days()

        # Phase 2b: Approval reset type migration (allow_multiple_claims_per_day → approval_reset_type)
        self._migrate_approval_reset_type()

        # Phase 2c: Timestamp-based chore tracking migration
        # - Initialize approval_period_start for chores
        # - Delete deprecated claimed_chores/approved_chores lists from kids
        self._migrate_to_timestamp_tracking()

        # Phase 2d: Reward data migration to period-based structure
        # - Migrate pending_rewards[] → reward_data[id].pending_count
        # - Migrate reward_claims{} → reward_data[id].total_claims
        # - Migrate reward_approvals{} → reward_data[id].total_approved
        self._migrate_reward_data_to_periods()

        # Phase 3: Config sync (KC 3.x entity data from config → storage)
        const.LOGGER.info("Migrating KC 3.x config data to storage")
        self._initialize_data_from_config()

        # Phase 4: Add new optional chore fields (defaults for existing chores)
        self._add_chore_optional_fields()

        # Phase 5: Clean up all legacy fields that have been migrated
        # This removes fields that were READ during migration but are no longer needed
        self._remove_legacy_fields()

        # Phase 6: Round all float values to standard precision
        # Fixes Python float arithmetic drift (e.g., 27.499999999999996 → 27.5)
        self._round_float_precision()

        # Phase 7: v50 cleanup - Remove legacy due_date fields from kid-level chore_data
        # for independent chores (single source of truth is now chore_info[per_kid_due_dates])
        storage_version = self.coordinator._data.get(const.DATA_META, {}).get(
            const.DATA_META_SCHEMA_VERSION, 42
        )
        if storage_version < 50:
            self._cleanup_kid_chore_data_due_dates_v50()

        # Phase 7a: v50 notification simplification - Migrate 3-field notification config
        # to single service selector (service presence = enabled, empty = disabled)
        self._simplify_notification_config_v50()

        # Phase 8: Clean up orphaned/deprecated dynamic entities
        # This is called unconditionally because _initialize_data_from_config() only
        # calls this for KC 3.x config migrations, leaving storage-only users with
        # orphaned entities from previous versions (e.g., integer-delta buttons).
        self.remove_deprecated_button_entities()
        self.remove_deprecated_sensor_entities()

        # Phase 9: Strip temporal stats from storage (Phase 7.5 - The Great Stripping)
        # Derivative Data is Ephemeral - clock-based stats MUST NOT be saved to JSON.
        # These fields are now derived on-demand from period buckets (point_data.periods).
        # Keep: earned_all_time, highest_balance, longest_streak_all_time (High-Water Marks)
        self._strip_temporal_stats()

        const.LOGGER.info("All pre-v50 migrations completed successfully")

    def _migrate_independent_chores(self) -> None:
        """Populate per_kid_due_dates for all INDEPENDENT chores (one-time migration).

        For each INDEPENDENT chore, populate per_kid_due_dates with template values
        for all assigned kids. SHARED chores don't need per-kid structure.
        This is a one-time migration during upgrade to v42+ schema.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        for chore_info in chores_data.values():
            # Ensure completion_criteria is set by reading legacy shared_chore field
            if const.DATA_CHORE_COMPLETION_CRITERIA not in chore_info:
                # Read legacy shared_chore boolean to determine criteria
                # Default to False (INDEPENDENT) for backward compatibility
                shared_chore = chore_info.get(
                    const.DATA_CHORE_SHARED_CHORE_LEGACY, False
                )
                if shared_chore:
                    chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = (
                        const.COMPLETION_CRITERIA_SHARED
                    )
                else:
                    chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = (
                        const.COMPLETION_CRITERIA_INDEPENDENT
                    )
                const.LOGGER.debug(
                    "Migrated chore '%s' from shared_chore=%s to completion_criteria=%s",
                    chore_info.get(const.DATA_CHORE_NAME),
                    shared_chore,
                    chore_info[const.DATA_CHORE_COMPLETION_CRITERIA],
                )

            # Remove legacy shared_chore field after migration
            if const.DATA_CHORE_SHARED_CHORE_LEGACY in chore_info:
                del chore_info[const.DATA_CHORE_SHARED_CHORE_LEGACY]
                const.LOGGER.debug(
                    "Removed legacy shared_chore field from chore '%s'",
                    chore_info.get(const.DATA_CHORE_NAME),
                )

            # For SHARED chores, no per_kid_due_dates needed
            # For INDEPENDENT chores, populate per_kid_due_dates if missing
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                if const.DATA_CHORE_PER_KID_DUE_DATES not in chore_info:
                    template_due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)
                    assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                    chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = dict.fromkeys(
                        assigned_kids, template_due_date
                    )
                    const.LOGGER.debug(
                        "Migrated INDEPENDENT chore '%s' with per-kid dates",
                        chore_info.get(const.DATA_CHORE_NAME),
                    )

                # Clean up legacy chore-level due_date for INDEPENDENT chores
                # The authoritative due_date is now per-kid in kid_chore_data
                if const.DATA_CHORE_DUE_DATE in chore_info:
                    del chore_info[const.DATA_CHORE_DUE_DATE]
                    const.LOGGER.debug(
                        "Removed legacy chore-level due_date from INDEPENDENT chore '%s'",
                        chore_info.get(const.DATA_CHORE_NAME),
                    )

    def _migrate_per_kid_applicable_days(self) -> None:
        """Populate per_kid_applicable_days for INDEPENDENT chores (one-time migration).

        For each INDEPENDENT chore with chore-level applicable_days:
        1. Create per_kid_applicable_days with same value for all assigned kids
        2. Clear chore-level applicable_days to None

        Empty list means "all days applicable" (not "never scheduled").
        SHARED chores keep chore-level applicable_days unchanged.

        PKAD-2026-001: Per-kid applicable days feature migration.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        migrated_count = 0

        for _chore_id, chore_info in chores_data.items():
            # Only INDEPENDENT chores need per-kid migration
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                continue

            # Skip if per_kid_applicable_days already exists
            if const.DATA_CHORE_PER_KID_APPLICABLE_DAYS in chore_info:
                continue

            # Get template from chore-level applicable_days
            template_days = chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

            # Populate per-kid structure (copy list for each kid)
            chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
                kid_id: template_days[:] if template_days else []
                for kid_id in assigned_kids
            }

            # Clear chore-level applicable_days (single source of truth)
            if const.DATA_CHORE_APPLICABLE_DAYS in chore_info:
                del chore_info[const.DATA_CHORE_APPLICABLE_DAYS]

            migrated_count += 1
            const.LOGGER.debug(
                "Migrated INDEPENDENT chore '%s' with per-kid applicable_days",
                chore_info.get(const.DATA_CHORE_NAME),
            )

        if migrated_count > 0:
            const.LOGGER.info(
                "Migrated %d INDEPENDENT chores to per-kid applicable_days",
                migrated_count,
            )

    def _migrate_approval_reset_type(self) -> None:
        """Migrate allow_multiple_claims_per_day boolean to approval_reset_type enum.

        Conversion:
        - allow_multiple_claims_per_day=True  → approval_reset_type=AT_MIDNIGHT_MULTI
        - allow_multiple_claims_per_day=False → approval_reset_type=AT_MIDNIGHT_ONCE
        - Missing field → approval_reset_type=AT_MIDNIGHT_ONCE (default)

        After migration, the deprecated field is removed from chore data.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        migrated_count = 0

        for chore_id, chore_info in chores_data.items():
            # Skip if already migrated (has approval_reset_type)
            if const.DATA_CHORE_APPROVAL_RESET_TYPE in chore_info:
                continue

            # Read legacy boolean field
            allow_multiple = chore_info.get(
                const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY, False
            )

            # Convert to new enum value
            if allow_multiple:
                new_value = const.APPROVAL_RESET_AT_MIDNIGHT_MULTI
            else:
                new_value = const.APPROVAL_RESET_AT_MIDNIGHT_ONCE

            chore_info[const.DATA_CHORE_APPROVAL_RESET_TYPE] = new_value
            migrated_count += 1

            const.LOGGER.debug(
                "Migrated chore '%s' (%s): allow_multiple=%s → approval_reset_type=%s",
                chore_info.get(const.DATA_CHORE_NAME),
                chore_id,
                allow_multiple,
                new_value,
            )

            # Remove deprecated field after migration
            if const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY in chore_info:
                del chore_info[const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY]

        if migrated_count > 0:
            const.LOGGER.info(
                "Migrated %s chores from allow_multiple_claims_per_day to approval_reset_type",
                migrated_count,
            )

    def _migrate_to_timestamp_tracking(self) -> None:
        """Migrate from list-based to timestamp-based chore claim/approval tracking.

        This migration:
        1. Initializes approval_period_start for INDEPENDENT chores (per-kid in kid_chore_data)
        2. Initializes approval_period_start for SHARED chores (at chore level)
        3. DELETES deprecated claimed_chores and approved_chores lists from kid data

        The new timestamp-based system uses:
        - last_claimed_time: When kid last claimed the chore
        - last_approved_time: When kid's claim was last approved
        - approval_period_start: Start of current approval window (reset changes this)

        Note: The deprecated lists are deleted because v0.4.0 uses timestamp-only tracking.
        """
        from homeassistant.util import dt as dt_util

        now_utc_iso = datetime.now(dt_util.UTC).isoformat()
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})

        # Phase 1: Initialize approval_period_start for chores
        chores_migrated = 0
        for chore_id, chore_info in chores_data.items():
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT chores: Initialize per-kid approval_period_start in kid_chore_data
                assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                for kid_id in assigned_kids:
                    kid_info = kids_data.get(kid_id, {})
                    kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
                    chore_tracking = kid_chore_data.get(chore_id, {})

                    # Only initialize if not already set
                    if (
                        const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
                        not in chore_tracking
                    ):
                        chore_tracking[
                            const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
                        ] = now_utc_iso
                        # Ensure the nested structure exists
                        if chore_id not in kid_chore_data:
                            kid_chore_data[chore_id] = chore_tracking
                        if const.DATA_KID_CHORE_DATA not in kid_info:
                            kid_info[const.DATA_KID_CHORE_DATA] = kid_chore_data
                        chores_migrated += 1
            # SHARED chores: Initialize approval_period_start at chore level
            elif const.DATA_CHORE_APPROVAL_PERIOD_START not in chore_info:
                chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_utc_iso
                chores_migrated += 1

        # Phase 2: DELETE deprecated lists from kid data
        kids_cleaned = 0
        deprecated_keys = [
            const.DATA_KID_CLAIMED_CHORES_LEGACY,
            const.DATA_KID_APPROVED_CHORES_LEGACY,
        ]

        for kid_id, kid_info in kids_data.items():
            removed_any = False
            for key in deprecated_keys:
                if key in kid_info:
                    del kid_info[key]
                    removed_any = True

            if removed_any:
                kids_cleaned += 1
                const.LOGGER.debug(
                    "Removed deprecated claim/approval lists from kid '%s' (%s)",
                    kid_info.get(const.DATA_KID_NAME),
                    kid_id,
                )

        if chores_migrated > 0 or kids_cleaned > 0:
            const.LOGGER.info(
                "Timestamp tracking migration: initialized %s chore periods, "
                "cleaned deprecated lists from %s kids",
                chores_migrated,
                kids_cleaned,
            )

    def _migrate_datetime(self, dt_str: str) -> str:
        """Convert a datetime string to a UTC-aware ISO string.

        Args:
            dt_str: The datetime string to convert.

        Returns:
            UTC-aware ISO format datetime string, or original string if conversion fails.
        """
        if not isinstance(dt_str, str):
            return dt_str

        try:
            dt_obj_utc = dt_to_utc(dt_str)
            if dt_obj_utc:
                return dt_obj_utc.isoformat()
            raise ValueError("Parsed datetime is None")
        except (ValueError, TypeError, AttributeError) as err:
            const.LOGGER.warning(
                "WARNING: Migrate DateTime - Error migrating datetime '%s': %s",
                dt_str,
                err,
            )
            return dt_str

    def _migrate_datetime_wrapper(self) -> None:
        """Wrapper to expose datetime migration as standalone step."""
        # This is a no-op in the context of run_all_migrations since datetime
        # conversion is called by _migrate_stored_datetimes

    def _migrate_stored_datetimes(self) -> None:
        """Walk through stored data and convert known datetime fields to UTC-aware ISO strings."""
        # For each chore, migrate due_date, last_completed, and last_claimed
        for chore_info in self.coordinator._data.get(const.DATA_CHORES, {}).values():
            if chore_info.get(const.DATA_CHORE_DUE_DATE):
                chore_info[const.DATA_CHORE_DUE_DATE] = self._migrate_datetime(
                    chore_info[const.DATA_CHORE_DUE_DATE]
                )
            if chore_info.get(const.DATA_CHORE_LAST_COMPLETED):
                chore_info[const.DATA_CHORE_LAST_COMPLETED] = self._migrate_datetime(
                    chore_info[const.DATA_CHORE_LAST_COMPLETED]
                )
            if chore_info.get(const.DATA_CHORE_LAST_CLAIMED):
                chore_info[const.DATA_CHORE_LAST_CLAIMED] = self._migrate_datetime(
                    chore_info[const.DATA_CHORE_LAST_CLAIMED]
                )
        # v0.4.0: Remove chore queue - now computed from timestamps
        # (skip timestamp migration, just delete the key)
        self.coordinator._data.pop(const.DATA_PENDING_CHORE_APPROVALS_LEGACY, None)

        # Migrate timestamps in pending REWARD approvals before deletion
        # These may contain historical approval data with timestamps that need proper format
        for approval in self.coordinator._data.get(
            const.DATA_PENDING_REWARD_APPROVALS_LEGACY, []
        ):
            if approval.get(const.DATA_CHORE_TIMESTAMP):
                approval[const.DATA_CHORE_TIMESTAMP] = self._migrate_datetime(
                    approval[const.DATA_CHORE_TIMESTAMP]
                )

        # v0.4.0: Remove reward queue - also now computed from per-kid reward_data
        # After migration, delete the legacy key since approvals are computed dynamically
        self.coordinator._data.pop(const.DATA_PENDING_REWARD_APPROVALS_LEGACY, None)

        # pre-v0.5.0: Remove orphaned linked_users key from early development
        # Feature was never implemented in production, clean up any test/dev data
        self.coordinator._data.pop(const.DATA_LINKED_USERS_LEGACY, None)

        # Migrate datetime on Challenges
        for challenge_info in self.coordinator._data.get(
            const.DATA_CHALLENGES, {}
        ).values():
            start_date = challenge_info.get(const.DATA_CHALLENGE_START_DATE)
            if not isinstance(start_date, str) or not start_date.strip():
                challenge_info[const.DATA_CHALLENGE_START_DATE] = None
            else:
                challenge_info[const.DATA_CHALLENGE_START_DATE] = (
                    self._migrate_datetime(start_date)
                )

            end_date = challenge_info.get(const.DATA_CHALLENGE_END_DATE)
            if not isinstance(end_date, str) or not end_date.strip():
                challenge_info[const.DATA_CHALLENGE_END_DATE] = None
            else:
                challenge_info[const.DATA_CHALLENGE_END_DATE] = self._migrate_datetime(
                    end_date
                )

    def _migrate_chore_data(self) -> None:
        """Migrate each chore's data to include new fields if missing."""
        chores = self.coordinator._data.get(const.DATA_CHORES, {})
        for chore_info in chores.values():
            chore_info.setdefault(
                const.CONF_APPLICABLE_DAYS_LEGACY, const.DEFAULT_APPLICABLE_DAYS
            )
            chore_info.setdefault(
                const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
            )
            chore_info.setdefault(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            )
            chore_info.setdefault(
                const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
            )
            # Remove legacy partial_allowed field (unused stub)
            chore_info.pop(const.DATA_CHORE_PARTIAL_ALLOWED_LEGACY, None)
        const.LOGGER.info("Chore data migration complete.")

    def _migrate_kid_data(self) -> None:
        """Migrate each kid's data to include new fields if missing."""
        kids = self.coordinator._data.get(const.DATA_KIDS, {})
        migrated_count = 0
        for kid_id, kid_info in kids.items():
            if const.DATA_KID_OVERDUE_NOTIFICATIONS not in kid_info:
                kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = {}
                migrated_count += 1
                const.LOGGER.debug(
                    "DEBUG: Added overdue_notifications field to kid '%s'", kid_id
                )
            # Ensure cumulative_badge_progress exists (initialized empty, populated later)
            if const.DATA_KID_CUMULATIVE_BADGE_PROGRESS not in kid_info:
                kid_info[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS] = {}
                const.LOGGER.debug(
                    "DEBUG: Added cumulative_badge_progress field to kid '%s'", kid_id
                )
        const.LOGGER.info(
            "INFO: Kid data migration complete. Migrated %s kids.", migrated_count
        )

    def _migrate_legacy_kid_chore_data_and_streaks(self) -> None:
        """Migrate legacy streak and stats data to the new kid chores structure (period-based).

        This function will automatically run through all kids and all assigned chores.
        Data that only needs to be migrated once per kid is handled separately from per-chore data.
        """
        for kid_id, kid_info in self.coordinator.kids_data.items():
            # --- Per-kid migration (run once per kid) ---
            # Only migrate these once per kid, not per chore
            chore_stats = kid_info.setdefault(const.DATA_KID_CHORE_STATS, {})
            legacy_streaks = kid_info.get(const.DATA_KID_CHORE_STREAKS_LEGACY, {})
            legacy_max = 0
            last_longest_streak_date = None

            # Find the max streak and last date across all chores for this kid
            for _chore_id, legacy_streak in legacy_streaks.items():  # type: ignore[attr-defined]
                max_streak = legacy_streak.get(const.DATA_KID_MAX_STREAK_LEGACY, 0)
                if max_streak > legacy_max:
                    legacy_max = max_streak
                    last_longest_streak_date = legacy_streak.get(
                        const.DATA_KID_LAST_STREAK_DATE
                    )

            if legacy_max > chore_stats.get(
                const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME, 0
            ):
                chore_stats[const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME] = (
                    legacy_max
                )
                # Store the date on any one chore (will be set per-chore below as well)
                if last_longest_streak_date:
                    for chore_data in kid_info.get(
                        const.DATA_KID_CHORE_DATA, {}
                    ).values():
                        chore_data[
                            const.DATA_KID_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME
                        ] = last_longest_streak_date

            # Migrate all-time and yearly completed counts from legacy (once per kid)
            chore_stats[const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME] = kid_info.get(
                const.DATA_KID_COMPLETED_CHORES_TOTAL_LEGACY, 0
            )
            chore_stats[const.DATA_KID_CHORE_STATS_APPROVED_YEAR] = kid_info.get(
                const.DATA_KID_COMPLETED_CHORES_TOTAL_LEGACY, 0
            )

            # Migrate all-time claimed count from legacy (use max of any chore's claims or completed_chores_total)
            all_claims = [
                kid_info.get(const.DATA_KID_CHORE_CLAIMS_LEGACY, {}).get(chore_id, 0)  # type: ignore[attr-defined]
                for chore_id in self.coordinator.chores_data
            ]
            all_claims.append(
                kid_info.get(const.DATA_KID_COMPLETED_CHORES_TOTAL_LEGACY, 0)
            )
            chore_stats[const.DATA_KID_CHORE_STATS_CLAIMED_ALL_TIME] = (
                max(all_claims) if all_claims else 0
            )

            # --- Per-chore migration (run for each assigned chore) ---
            for chore_id, chore_info in self.coordinator.chores_data.items():
                assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                if assigned_kids and kid_id not in assigned_kids:
                    continue

                # Ensure new structure exists
                if const.DATA_KID_CHORE_DATA not in kid_info:
                    kid_info[const.DATA_KID_CHORE_DATA] = {}

                chore_data_dict = kid_info.get(const.DATA_KID_CHORE_DATA, {})
                if chore_id not in chore_data_dict:
                    chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
                    chore_data_dict[chore_id] = {
                        const.DATA_KID_CHORE_DATA_NAME: chore_name,
                        const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
                        const.DATA_KID_CHORE_DATA_LAST_CLAIMED: None,
                        const.DATA_KID_CHORE_DATA_LAST_APPROVED: None,
                        const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED: None,
                        const.DATA_KID_CHORE_DATA_LAST_OVERDUE: None,
                        const.DATA_KID_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME: None,
                        const.DATA_KID_CHORE_DATA_PERIODS: {
                            const.DATA_KID_CHORE_DATA_PERIODS_DAILY: {},
                            const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY: {},
                            const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY: {},
                            const.DATA_KID_CHORE_DATA_PERIODS_YEARLY: {},
                            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME: {},
                        },
                        const.DATA_KID_CHORE_DATA_BADGE_REFS: [],
                    }

                kid_chore_data = chore_data_dict[chore_id]

                # Ensure pending_claim_count exists for existing records (added in v42)
                if const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT not in kid_chore_data:
                    kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

                periods = kid_chore_data[const.DATA_KID_CHORE_DATA_PERIODS]

                # --- Migrate legacy current streaks for this chore ---
                legacy_streak = legacy_streaks.get(chore_id, {})  # type: ignore[attr-defined]
                last_date = legacy_streak.get(const.DATA_KID_LAST_STREAK_DATE)
                if last_date:
                    # Daily
                    daily_data = periods[
                        const.DATA_KID_CHORE_DATA_PERIODS_DAILY
                    ].setdefault(
                        last_date,
                        {
                            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
                            const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
                            const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
                            const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
                            const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                        },
                    )
                    daily_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = (
                        legacy_streak.get(const.DATA_KID_CURRENT_STREAK, 0)
                    )

                for period_key, period_fmt in [
                    (const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY, "%Y-W%V"),
                    (const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, "%Y-%m"),
                    (const.DATA_KID_CHORE_DATA_PERIODS_YEARLY, "%Y"),
                    (const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, const.PERIOD_ALL_TIME),
                ]:
                    if last_date:
                        try:
                            dt = datetime.fromisoformat(last_date)
                            period_id = dt.strftime(period_fmt)
                        except (ValueError, TypeError):
                            period_id = None
                    else:
                        period_id = None

                    if period_id:
                        period_data_dict = periods[period_key].setdefault(
                            period_id,
                            {
                                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
                                const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
                                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
                                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
                                const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                                const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                            },
                        )
                        period_data_dict[
                            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
                        ] = legacy_streak.get(const.DATA_KID_MAX_STREAK_LEGACY, 0)

                # --- Migrate claim/approval counts for this chore ---
                claims = kid_info.get(const.DATA_KID_CHORE_CLAIMS_LEGACY, {}).get(  # type: ignore[attr-defined]
                    chore_id, 0
                )
                approvals = kid_info.get(const.DATA_KID_CHORE_APPROVALS_LEGACY, {}).get(  # type: ignore[attr-defined]
                    chore_id, 0
                )

                # --- Migrate period completion and claim counts for this chore ---
                now_local = dt_now_local()
                today_iso = now_local.date().isoformat()
                week_iso = now_local.strftime("%Y-W%V")
                month_iso = now_local.strftime("%Y-%m")
                year_iso = now_local.strftime("%Y")

                # Daily
                daily_data = periods[
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY
                ].setdefault(
                    today_iso,
                    {
                        const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                    },
                )
                # No per chore data available for daily period

                # Weekly
                _weekly_stats = periods[
                    const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY
                ].setdefault(
                    week_iso,
                    {
                        const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                    },
                )
                # No per chore data available for weekly period

                # Monthly
                _monthly_stats = periods[
                    const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY
                ].setdefault(
                    month_iso,
                    {
                        const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                    },
                )
                # No per chore data available for monthly period

                # Yearly
                yearly_stats = periods[
                    const.DATA_KID_CHORE_DATA_PERIODS_YEARLY
                ].setdefault(
                    year_iso,
                    {
                        const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                    },
                )
                # Mapping legacy totals to yearly stats
                yearly_stats[const.DATA_KID_CHORE_DATA_PERIOD_APPROVED] = approvals
                yearly_stats[const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED] = claims

                # --- Migrate legacy all-time stats into the new all_time period for this chore ---
                all_time_data = periods[
                    const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME
                ].setdefault(
                    const.PERIOD_ALL_TIME,
                    {
                        const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                    },
                )

                # Map legacy totals to all time data
                all_time_data[const.DATA_KID_CHORE_DATA_PERIOD_APPROVED] = approvals
                all_time_data[const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED] = claims

    def _migrate_badges(self) -> None:
        """Migrate legacy badges into cumulative badges and ensure all required fields exist.

        For badges whose threshold_type is set to the legacy value (e.g. BADGE_THRESHOLD_TYPE_CHORE_COUNT),
        compute the new threshold as the legacy count multiplied by the average default points across all chores.
        Also, set reset fields to empty and disable periodic resets.
        For any badge, ensure all required fields and nested structures exist using constants.
        """
        badges_dict = self.coordinator._data.get(const.DATA_BADGES, {})
        chores_dict = self.coordinator._data.get(const.DATA_CHORES, {})

        # Calculate the average default points over all chores.
        total_points = 0.0
        count = 0
        for chore_info in chores_dict.values():
            try:
                default_points = float(
                    chore_info.get(
                        const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS
                    )
                )
                total_points += default_points
                count += 1
            except (ValueError, TypeError, KeyError):
                continue

        # If there are no chores, we fallback to DEFAULT_POINTS.
        average_points = (total_points / count) if count > 0 else const.DEFAULT_POINTS

        # Process each badge.
        for badge_info in badges_dict.values():
            # --- Legacy migration logic ---
            if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE:
                # If the badge is already moved to cumulative, skip legacy migration.
                pass
            else:
                # Check if the badge uses the legacy "chore_count" threshold type if so estimate points and assign.
                if (
                    badge_info.get(const.DATA_BADGE_THRESHOLD_TYPE_LEGACY)
                    == const.BADGE_THRESHOLD_TYPE_CHORE_COUNT
                ):
                    old_threshold = badge_info.get(
                        const.DATA_BADGE_THRESHOLD_VALUE_LEGACY,
                        const.DEFAULT_BADGE_THRESHOLD_VALUE_LEGACY,
                    )
                    try:
                        # Multiply the legacy count by the average default points.
                        new_threshold = float(old_threshold) * average_points
                    except (ValueError, TypeError):
                        new_threshold = old_threshold

                    # Force to points type and set new value
                    badge_info[const.DATA_BADGE_THRESHOLD_TYPE_LEGACY] = (
                        const.CONF_POINTS_LEGACY
                    )
                    badge_info[const.DATA_BADGE_THRESHOLD_VALUE_LEGACY] = new_threshold

                    # Also update the target structure immediately
                    badge_info.setdefault(const.DATA_BADGE_TARGET, {})
                    badge_info[const.DATA_BADGE_TARGET][
                        const.DATA_BADGE_TARGET_TYPE
                    ] = const.CONF_POINTS_LEGACY
                    badge_info[const.DATA_BADGE_TARGET][
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE
                    ] = new_threshold

                    const.LOGGER.info(
                        "INFO: Legacy Chore Count Badge '%s' migrated: Old threshold %s -> New threshold %s (average_points=%.2f)",
                        badge_info.get(const.DATA_BADGE_NAME),
                        old_threshold,
                        new_threshold,
                        average_points,
                    )

                    # Remove legacy fields now so they can't overwrite later
                    badge_info.pop(const.DATA_BADGE_THRESHOLD_TYPE_LEGACY, None)
                    badge_info.pop(const.DATA_BADGE_THRESHOLD_VALUE_LEGACY, None)

                # Set badge type to cumulative if not already set
                if const.DATA_BADGE_TYPE not in badge_info:
                    badge_info[const.DATA_BADGE_TYPE] = const.BADGE_TYPE_CUMULATIVE

            # --- Ensure all required fields and nested structures exist using constants ---

            # assigned_to
            if const.DATA_BADGE_ASSIGNED_TO not in badge_info:
                badge_info[const.DATA_BADGE_ASSIGNED_TO] = []

            # reset_schedule
            if const.DATA_BADGE_RESET_SCHEDULE not in badge_info:
                badge_info[const.DATA_BADGE_RESET_SCHEDULE] = {
                    const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: const.FREQUENCY_NONE,
                    const.DATA_BADGE_RESET_SCHEDULE_START_DATE: None,
                    const.DATA_BADGE_RESET_SCHEDULE_END_DATE: None,
                    const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: 0,
                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: None,
                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: None,
                }

            # awards
            if const.DATA_BADGE_AWARDS not in badge_info or not isinstance(
                badge_info[const.DATA_BADGE_AWARDS], dict
            ):
                badge_info[const.DATA_BADGE_AWARDS] = {}
            # Preserve existing award_items if present, otherwise default to multiplier
            # (multiplier was the only award type in the original badges before award_items existed)
            if (
                const.DATA_BADGE_AWARDS_AWARD_ITEMS
                not in badge_info[const.DATA_BADGE_AWARDS]
            ):
                badge_info[const.DATA_BADGE_AWARDS][
                    const.DATA_BADGE_AWARDS_AWARD_ITEMS
                ] = [const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER]
            badge_info[const.DATA_BADGE_AWARDS].setdefault(
                const.DATA_BADGE_AWARDS_AWARD_POINTS, 0
            )
            badge_info[const.DATA_BADGE_AWARDS].setdefault(
                const.DATA_BADGE_AWARDS_AWARD_REWARD, ""
            )
            badge_info[const.DATA_BADGE_AWARDS].setdefault(
                const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
                badge_info.get(
                    const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY,
                    const.DEFAULT_POINTS_MULTIPLIER,
                ),
            )

            # target
            if const.DATA_BADGE_TARGET not in badge_info or not isinstance(
                badge_info[const.DATA_BADGE_TARGET], dict
            ):
                badge_info[const.DATA_BADGE_TARGET] = {}
            badge_info[const.DATA_BADGE_TARGET].setdefault(
                const.DATA_BADGE_TARGET_TYPE,
                badge_info.get(
                    const.DATA_BADGE_THRESHOLD_TYPE_LEGACY,
                    const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                ),
            )
            badge_info[const.DATA_BADGE_TARGET].setdefault(
                const.DATA_BADGE_TARGET_THRESHOLD_VALUE,
                badge_info.get(const.DATA_BADGE_THRESHOLD_VALUE_LEGACY, 0),
            )
            badge_info[const.DATA_BADGE_TARGET].setdefault(
                const.DATA_BADGE_MAINTENANCE_RULES, 0
            )

            # --- Migrate threshold_type/value to target if not already done ---
            if const.DATA_BADGE_THRESHOLD_TYPE_LEGACY in badge_info:
                badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE] = (
                    badge_info.get(const.DATA_BADGE_THRESHOLD_TYPE_LEGACY)
                )
            if const.DATA_BADGE_THRESHOLD_VALUE_LEGACY in badge_info:
                badge_info[const.DATA_BADGE_TARGET][
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE
                ] = badge_info.get(const.DATA_BADGE_THRESHOLD_VALUE_LEGACY)

            # Migrate points_multiplier to awards.points_multiplier if not already done
            if const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY in badge_info:
                badge_info[const.DATA_BADGE_AWARDS][
                    const.DATA_BADGE_AWARDS_POINT_MULTIPLIER
                ] = float(
                    badge_info.get(
                        const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY,
                        const.DEFAULT_POINTS_MULTIPLIER,
                    )
                )

            # --- Clean up any legacy fields that might exist outside the new nested structure ---
            legacy_fields = [
                const.DATA_BADGE_THRESHOLD_TYPE_LEGACY,
                const.DATA_BADGE_THRESHOLD_VALUE_LEGACY,
                const.DATA_BADGE_CHORE_COUNT_TYPE_LEGACY,
                const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY,
            ]
            for field in legacy_fields:
                if field in badge_info:
                    del badge_info[field]

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

        const.LOGGER.info(
            "INFO: Badge Migration - Completed migration of legacy badges to new structure"
        )

    def _migrate_kid_legacy_badges_to_cumulative_progress(self) -> None:
        """Set cumulative badge progress for each kid based on legacy badges earned.

        For each kid, set their current cumulative badge to the highest-value badge
        (by points threshold) from their legacy earned badges list.
        Also set their cumulative cycle points to their current points balance to avoid losing progress.
        """
        for kid_info in self.coordinator.kids_data.values():
            legacy_badge_names = kid_info.get(const.DATA_KID_BADGES_LEGACY, [])
            if not legacy_badge_names:
                continue

            # Find the highest-value cumulative badge earned by this kid
            highest_badge = None
            highest_points = -1
            for badge_name in legacy_badge_names:  # type: ignore[attr-defined]
                # Find badge_id by name and ensure it's cumulative
                badge_id = None
                for b_id, b_info in self.coordinator.badges_data.items():
                    if (
                        b_info.get(const.DATA_BADGE_NAME) == badge_name
                        and b_info.get(const.DATA_BADGE_TYPE)
                        == const.BADGE_TYPE_CUMULATIVE
                    ):
                        badge_id = b_id
                        break
                if not badge_id:
                    continue
                badge_info = self.coordinator.badges_data[badge_id]
                points = int(
                    float(
                        badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                )
                if points > highest_points:
                    highest_points = points
                    highest_badge = badge_info

            # Set the current cumulative badge progress for this kid
            if highest_badge:
                progress = kid_info.setdefault(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS,
                    {},  # type: ignore[typeddict-item]
                )
                progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID] = (
                    highest_badge.get(const.DATA_BADGE_INTERNAL_ID)
                )
                progress[
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME
                ] = highest_badge.get(const.DATA_BADGE_NAME)
                progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD] = (
                    highest_badge.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                # Set cycle points to current points balance to avoid losing progress
                progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = (
                    kid_info.get(const.DATA_KID_POINTS, 0.0)
                )

    def _migrate_kid_legacy_badges_to_badges_earned(self) -> None:
        """One-time migration from legacy 'badges' list to structured 'badges_earned' dict for each kid."""
        const.LOGGER.info(
            "INFO: Migration - Starting legacy badges to badges_earned migration"
        )
        today_local_iso = dt_today_iso()

        for kid_id, kid_info in self.coordinator.kids_data.items():
            legacy_badge_names = kid_info.get(const.DATA_KID_BADGES_LEGACY, [])
            badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})

            for badge_name in legacy_badge_names:  # type: ignore[attr-defined]
                badge_id = kh.get_entity_id_by_name(
                    self.coordinator, const.ENTITY_TYPE_BADGE, badge_name
                )

                if not badge_id:
                    badge_id = f"{const.MIGRATION_DATA_LEGACY_ORPHAN}_{random.randint(100000, 999999)}"
                    const.LOGGER.warning(
                        "WARNING: Migrate - Badge '%s' not found in badge data. Assigning legacy orphan ID '%s' for kid '%s'.",
                        badge_name,
                        badge_id,
                        kid_info.get(const.DATA_KID_NAME, kid_id),
                    )

                if badge_id in badges_earned:
                    const.LOGGER.debug(
                        "DEBUG: Migration - Badge '%s' (%s) already in badges_earned for kid '%s', skipping.",
                        badge_name,
                        badge_id,
                        kid_id,
                    )
                    continue

                badges_earned[badge_id] = {
                    const.DATA_KID_BADGES_EARNED_NAME: badge_name,
                    const.DATA_KID_BADGES_EARNED_LAST_AWARDED: today_local_iso,
                    const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1,
                }

                const.LOGGER.info(
                    "INFO: Migration - Migrated badge '%s' (%s) to badges_earned for kid '%s'.",
                    badge_name,
                    badge_id,
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

            # Cleanup: remove the legacy badges list after migration
            if const.DATA_KID_BADGES_LEGACY in kid_info:
                del kid_info[const.DATA_KID_BADGES_LEGACY]  # type: ignore[typeddict-item]

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    def _migrate_legacy_point_stats(self) -> None:
        """Migrate legacy rolling point stats into the new point_data period structure for each kid."""
        for kid_info in self.coordinator.kids_data.values():
            # Legacy values
            legacy_today = round(  # type: ignore[call-overload]
                kid_info.get(const.DATA_KID_POINTS_EARNED_TODAY_LEGACY, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            legacy_week = round(  # type: ignore[call-overload]
                kid_info.get(const.DATA_KID_POINTS_EARNED_WEEKLY_LEGACY, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            legacy_month = round(  # type: ignore[call-overload]
                kid_info.get(const.DATA_KID_POINTS_EARNED_MONTHLY_LEGACY, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            legacy_max = round(  # type: ignore[call-overload]
                kid_info.get(const.DATA_KID_MAX_POINTS_EVER_LEGACY, 0.0),
                const.DATA_FLOAT_PRECISION,
            )

            # Get or create point_data periods
            point_data = kid_info.setdefault(const.DATA_KID_POINT_DATA, {})  # type: ignore[typeddict-item]
            periods = point_data.setdefault(const.DATA_KID_POINT_DATA_PERIODS, {})

            # Get period keys
            today_local_iso = dt_today_local().isoformat()
            now_local = dt_now_local()
            week_local_iso = now_local.strftime("%Y-W%V")
            month_local_iso = now_local.strftime("%Y-%m")
            year_local_iso = now_local.strftime("%Y")

            # Helper to migrate if legacy > 0 and period is missing or zero
            def migrate_period(
                periods_dict: dict,
                period_key: str,
                period_id: str,
                legacy_value: float,
            ) -> None:
                """Migrate a single period if legacy value exists and period is empty."""
                if legacy_value > 0:
                    bucket = periods_dict.setdefault(period_key, {})
                    entry = bucket.setdefault(
                        period_id,
                        {
                            const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL: 0.0,
                            const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE: {},
                        },
                    )
                    if entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] == 0.0:
                        entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] = (
                            legacy_value
                        )
                        # Use a point source of other
                        entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][
                            const.POINTS_SOURCE_OTHER
                        ] = legacy_value

            migrate_period(
                periods,
                const.DATA_KID_POINT_DATA_PERIODS_DAILY,
                today_local_iso,
                legacy_today,
            )
            migrate_period(
                periods,
                const.DATA_KID_POINT_DATA_PERIODS_WEEKLY,
                week_local_iso,
                legacy_week,
            )
            migrate_period(
                periods,
                const.DATA_KID_POINT_DATA_PERIODS_MONTHLY,
                month_local_iso,
                legacy_month,
            )

            # Set yearly period points to legacy_max if > 0
            if legacy_max > 0:
                yearly_bucket = periods.setdefault(
                    const.DATA_KID_POINT_DATA_PERIODS_YEARLY, {}
                )
                yearly_entry = yearly_bucket.setdefault(
                    year_local_iso,
                    {
                        const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL: 0.0,
                        const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE: {},
                    },
                )
                yearly_entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] = legacy_max
                yearly_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][
                    const.POINTS_SOURCE_OTHER
                ] = legacy_max

            # Create all_time period bucket for points
            # Use max(max_points_ever_legacy, current_points) as best estimate
            current_points = round(
                kid_info.get(const.DATA_KID_POINTS, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            all_time_points = max(legacy_max, current_points)
            if all_time_points > 0:
                all_time_bucket = periods.setdefault(
                    const.DATA_KID_POINT_DATA_PERIODS_ALL_TIME, {}
                )
                all_time_entry = all_time_bucket.setdefault(
                    const.PERIOD_ALL_TIME,
                    {
                        const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL: 0.0,
                        const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE: {},
                    },
                )
                # Only set if not already populated (idempotent)
                if all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] == 0.0:
                    all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] = (
                        all_time_points
                    )
                    all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][
                        const.POINTS_SOURCE_OTHER
                    ] = all_time_points

            # Migrate legacy max points ever to point_stats highest balance if needed
            point_stats = kid_info.setdefault(const.DATA_KID_POINT_STATS, {})
            if legacy_max > 0 and legacy_max > point_stats.get(
                const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0
            ):
                point_stats[const.DATA_KID_POINT_STATS_HIGHEST_BALANCE] = legacy_max

            # Set points_earned_all_time using same logic as all_time period bucket
            # This ensures current balance is considered if higher than legacy max
            if all_time_points > 0:
                point_stats[const.DATA_KID_POINT_STATS_EARNED_ALL_TIME] = (
                    all_time_points
                )

            # --- Migrate all-time points by source ---
            if all_time_points > 0:
                point_stats[const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME] = {
                    const.POINTS_SOURCE_OTHER: all_time_points
                }

        const.LOGGER.info("Legacy point stats migration complete.")

    # -------------------------------------------------------------------------------------
    # KC 3.x Config Sync to Storage (v41→v42 Migration Compatibility)
    # -------------------------------------------------------------------------------------
    # These methods handle one-time migration of entity data from config_entry.options
    # to .storage/kidschores_data when upgrading from KC 3.x (schema <42) to KC 4.x (schema 42+).
    # NOTE: CRUD methods (_create_kid, _update_chore, etc.) remain in coordinator as they
    # are actively used by options_flow.py for v4.2+ entity management.

    def _initialize_data_from_config(self) -> None:
        """Migrate entity data from config_entry.options to storage (KC 3.x→4.x compatibility).

        This method is ONLY called once when storage_schema_version < 42.
        For v4.2+ users, entity data is already in storage and config contains only system settings.
        """
        options = self.coordinator.config_entry.options

        # Skip if no KC 3.x config data present (pure storage migration, no config sync needed)
        if not options or not options.get(const.CONF_KIDS_LEGACY):
            const.LOGGER.info(
                "No KC 3.x config data - skipping config sync (already using storage-only mode)"
            )
            return

        # Retrieve configuration dictionaries from config entry options (KC 3.x architecture)
        config_sections = {
            const.DATA_KIDS: options.get(const.CONF_KIDS_LEGACY, {}),
            const.DATA_PARENTS: options.get(const.CONF_PARENTS_LEGACY, {}),
            const.DATA_CHORES: options.get(const.CONF_CHORES_LEGACY, {}),
            const.DATA_BADGES: options.get(const.CONF_BADGES_LEGACY, {}),
            const.DATA_REWARDS: options.get(const.CONF_REWARDS_LEGACY, {}),
            const.DATA_PENALTIES: options.get(const.CONF_PENALTIES_LEGACY, {}),
            const.DATA_BONUSES: options.get(const.CONF_BONUSES_LEGACY, {}),
            const.DATA_ACHIEVEMENTS: options.get(const.CONF_ACHIEVEMENTS_LEGACY, {}),
            const.DATA_CHALLENGES: options.get(const.CONF_CHALLENGES_LEGACY, {}),
        }

        # Ensure minimal structure
        self._ensure_minimal_structure()

        # Initialize each section using private helper
        for section_key, data_dict in config_sections.items():
            init_func = getattr(self, f"_initialize_{section_key}", None)
            if init_func:  # pylint: disable=using-constant-test
                init_func(data_dict)
            else:
                self.coordinator._data.setdefault(section_key, data_dict)
                const.LOGGER.warning(
                    "WARNING: No initializer found for section '%s'", section_key
                )

        # Recalculate Badges on reload (marks all kids dirty for evaluation)
        self.coordinator.gamification_manager.recalculate_all_badges()

    def _ensure_minimal_structure(self) -> None:
        """Ensure that all necessary data sections are present in storage."""
        for key in [
            const.DATA_KIDS,
            const.DATA_PARENTS,
            const.DATA_CHORES,
            const.DATA_BADGES,
            const.DATA_REWARDS,
            const.DATA_PENALTIES,
            const.DATA_BONUSES,
            const.DATA_ACHIEVEMENTS,
            const.DATA_CHALLENGES,
        ]:
            self.coordinator._data.setdefault(key, {})

        for key in [
            const.DATA_PENDING_CHORE_APPROVALS_LEGACY,
            const.DATA_PENDING_REWARD_APPROVALS_LEGACY,
        ]:
            if not isinstance(self.coordinator._data.get(key), list):
                self.coordinator._data[key] = []

        # v0.4.0: Remove chore queue - computed from timestamps
        self.coordinator._data.pop(const.DATA_PENDING_CHORE_APPROVALS_LEGACY, None)

    # -- Entity Type Wrappers (delegate to _sync_entities) --

    def _initialize_kids(self, kids_dict: dict[str, Any]) -> None:
        """Initialize kids from config data."""
        self._sync_entities(
            const.DATA_KIDS,
            kids_dict,
            self._create_kid,
            self._update_kid,
        )

    def _initialize_parents(self, parents_dict: dict[str, Any]) -> None:
        """Initialize parents from config data."""
        self._sync_entities(
            const.DATA_PARENTS,
            parents_dict,
            self._create_parent,
            self._update_parent,
        )

    def _initialize_chores(self, chores_dict: dict[str, Any]) -> None:
        """Initialize chores from config data."""
        self._sync_entities(
            const.DATA_CHORES,
            chores_dict,
            self._create_chore,
            self._update_chore,
        )

    def _initialize_badges(self, badges_dict: dict[str, Any]) -> None:
        """Initialize badges from config data."""
        self._sync_entities(
            const.DATA_BADGES,
            badges_dict,
            self._create_badge,
            self._update_badge,
        )

    def _initialize_rewards(self, rewards_dict: dict[str, Any]) -> None:
        """Initialize rewards from config data."""
        self._sync_entities(
            const.DATA_REWARDS,
            rewards_dict,
            self._create_reward,
            self._update_reward,
        )

    def _initialize_penalties(self, penalties_dict: dict[str, Any]) -> None:
        """Initialize penalties from config data."""
        self._sync_entities(
            const.DATA_PENALTIES,
            penalties_dict,
            self._create_penalty,
            self._update_penalty,
        )

    def _initialize_achievements(self, achievements_dict: dict[str, Any]) -> None:
        """Initialize achievements from config data."""
        self._sync_entities(
            const.DATA_ACHIEVEMENTS,
            achievements_dict,
            self._create_achievement,
            self._update_achievement,
        )

    def _initialize_challenges(self, challenges_dict: dict[str, Any]) -> None:
        """Initialize challenges from config data."""
        self._sync_entities(
            const.DATA_CHALLENGES,
            challenges_dict,
            self._create_challenge,
            self._update_challenge,
        )

    def _initialize_bonuses(self, bonuses_dict: dict[str, Any]) -> None:
        """Initialize bonuses from config data."""
        self._sync_entities(
            const.DATA_BONUSES,
            bonuses_dict,
            self._create_bonus,
            self._update_bonus,
        )

    def _sync_entities(
        self,
        section: str,
        config_data: dict[str, Any],
        create_method,
        update_method,
    ) -> None:
        """Synchronize entities in a given data section based on config_data.

        Compares config data against storage, calling create/update methods as needed.
        This is the core sync engine for KC 3.x→4.x migration.
        """
        existing_ids = set(self.coordinator._data[section].keys())
        config_ids = set(config_data.keys())

        # Identify entities to remove
        entities_to_remove = existing_ids - config_ids
        for entity_id in entities_to_remove:
            # Remove entity from data
            del self.coordinator._data[section][entity_id]

            # Remove entity from HA registry
            eh.remove_entities_by_item_id(
                self.coordinator.hass,
                self.coordinator.config_entry.entry_id,
                entity_id,
            )

            # Cleanup references to deleted entity
            if section == const.DATA_KIDS:
                # Remove deleted kid from parents' kids lists
                for parent in self.coordinator._data.get(
                    const.DATA_PARENTS, {}
                ).values():
                    if entity_id in parent.get(const.DATA_PARENT_KIDS, []):
                        parent[const.DATA_PARENT_KIDS].remove(entity_id)

            if section == const.DATA_REWARDS:
                # Remove deleted reward from pending approvals
                for kid_data in self.coordinator._data.get(
                    const.DATA_KIDS, {}
                ).values():
                    approvals = kid_data.get(
                        const.DATA_KID_PENDING_REWARD_APPROVALS, []
                    )
                    kid_data[const.DATA_KID_PENDING_REWARD_APPROVALS] = [
                        a
                        for a in approvals
                        if a.get(const.DATA_KID_PENDING_REWARD_APPROVAL_REWARD_ID)
                        != entity_id
                    ]

        # Add or update entities
        for entity_id, entity_body in config_data.items():
            if entity_id not in self.coordinator._data[section]:
                create_method(entity_id, entity_body)
            else:
                update_method(entity_id, entity_body)

        # Remove orphaned chore-related entities (using entity_helpers directly)
        if section == const.DATA_CHORES:
            self.coordinator.hass.async_create_task(
                eh.remove_orphaned_shared_chore_sensors(
                    self.coordinator.hass,
                    self.coordinator.config_entry.entry_id,
                    self.coordinator.chores_data,
                )
            )
            self.coordinator.hass.async_create_task(
                eh.remove_orphaned_kid_chore_entities(
                    self.coordinator.hass,
                    self.coordinator.config_entry.entry_id,
                    self.coordinator.kids_data,
                    self.coordinator.chores_data,
                )
            )

        # Remove orphaned achievement and challenges sensors
        self.coordinator.hass.async_create_task(
            eh.remove_orphaned_progress_entities(
                self.coordinator.hass,
                self.coordinator.config_entry.entry_id,
                self.coordinator.achievements_data,
                entity_type="achievement",
                progress_suffix=const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX,
                assigned_kids_key=const.DATA_ACHIEVEMENT_ASSIGNED_KIDS,
            )
        )
        self.coordinator.hass.async_create_task(
            eh.remove_orphaned_progress_entities(
                self.coordinator.hass,
                self.coordinator.config_entry.entry_id,
                self.coordinator.challenges_data,
                entity_type="challenge",
                progress_suffix=const.DATA_CHALLENGE_PROGRESS_SUFFIX,
                assigned_kids_key=const.DATA_CHALLENGE_ASSIGNED_KIDS,
            )
        )

        # Remove deprecated sensors (sync method - no async_create_task needed)
        self.remove_deprecated_entities(
            self.coordinator.hass, self.coordinator.config_entry
        )

        # Remove deprecated/orphaned dynamic entities
        self.remove_deprecated_button_entities()
        self.remove_deprecated_sensor_entities()

    def _add_chore_optional_fields(self) -> None:
        """Add new optional fields to existing chores during migration.

        This adds default values for fields introduced in later versions:
        - show_on_calendar (defaults to True)
        - auto_approve (defaults to False)
        - overdue_handling_type (defaults to AT_DUE_DATE)
        - approval_reset_pending_claim_action (defaults to CLEAR_PENDING)

        These fields are added during pre-v42 migration. For v42+ data,
        they are already set by flow_helpers.py during entity creation.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        for chore_id, chore_data in chores_data.items():
            # Add show_on_calendar field (new optional field, defaults to True)
            if const.DATA_CHORE_SHOW_ON_CALENDAR not in chore_data:
                chore_data[const.DATA_CHORE_SHOW_ON_CALENDAR] = True
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added show_on_calendar field",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

            # Add auto_approve field (new optional field, defaults to False)
            if const.DATA_CHORE_AUTO_APPROVE not in chore_data:
                chore_data[const.DATA_CHORE_AUTO_APPROVE] = False
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added auto_approve field",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

            # Add overdue_handling_type field (defaults to AT_DUE_DATE)
            if const.DATA_CHORE_OVERDUE_HANDLING_TYPE not in chore_data:
                chore_data[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
                    const.DEFAULT_OVERDUE_HANDLING_TYPE
                )
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added overdue_handling_type field",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

            # Migrate old overdue_handling_type value string (v0.5.0 rename)
            # "at_due_date_then_reset" → "at_due_date_clear_at_approval_reset"
            if (
                chore_data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)
                == "at_due_date_then_reset"
            ):
                chore_data[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
                    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
                )
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): updated overdue_handling_type "
                    "from 'at_due_date_then_reset' to '%s'",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
                )

            # Add approval_reset_pending_claim_action field (defaults to CLEAR_PENDING)
            if const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION not in chore_data:
                chore_data[const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION] = (
                    const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION
                )
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added approval_reset_pending_claim_action",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

    def _migrate_reward_data_to_periods(self) -> None:
        """Migrate legacy reward tracking to period-based reward_data structure.

        Legacy fields (per kid):
        - pending_rewards: list[str]  (reward_ids waiting approval)
        - reward_claims: dict[str, int]  (reward_id → claim count)
        - reward_approvals: dict[str, int]  (reward_id → approval count)
        - redeemed_rewards: list[str]  (reward_ids approved, used for "approved today")

        Modern structure (per kid, per reward):
        - reward_data[reward_id].pending_count
        - reward_data[reward_id].total_claims
        - reward_data[reward_id].total_approved
        - reward_data[reward_id].total_points_spent
        - reward_data[reward_id].periods.{daily,weekly,monthly,yearly}

        This migration is idempotent - existing reward_data entries are preserved.
        Legacy fields are kept for backward compatibility during transition.
        """
        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})
        rewards_data = self.coordinator._data.get(const.DATA_REWARDS, {})
        migrated_kids = 0

        for kid_id, kid_info in kids_data.items():
            kid_migrated = False

            # Ensure reward_data dict exists
            if const.DATA_KID_REWARD_DATA not in kid_info:
                kid_info[const.DATA_KID_REWARD_DATA] = {}

            reward_data = kid_info[const.DATA_KID_REWARD_DATA]

            # Migrate pending_rewards[] → reward_data[id].pending_count
            pending_rewards = kid_info.get(const.DATA_KID_PENDING_REWARDS_LEGACY, [])
            if pending_rewards:
                # Count occurrences of each reward_id
                pending_counts = Counter(pending_rewards)
                for reward_id, count in pending_counts.items():
                    if reward_id not in reward_data:
                        reward_data[reward_id] = self._create_empty_reward_entry(
                            reward_id, rewards_data
                        )
                    # Only migrate if pending_count is 0 (not already set)
                    if (
                        reward_data[reward_id].get(
                            const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0
                        )
                        == 0
                    ):
                        reward_data[reward_id][
                            const.DATA_KID_REWARD_DATA_PENDING_COUNT
                        ] = count
                        kid_migrated = True

            # Migrate reward_claims{} → reward_data[id].total_claims
            reward_claims = kid_info.get(const.DATA_KID_REWARD_CLAIMS_LEGACY, {})
            for reward_id, claim_count in reward_claims.items():
                if reward_id not in reward_data:
                    reward_data[reward_id] = self._create_empty_reward_entry(
                        reward_id, rewards_data
                    )
                # Only migrate if total_claims is 0 (not already set)
                if (
                    reward_data[reward_id].get(
                        const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS, 0
                    )
                    == 0
                ):
                    reward_data[reward_id][const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS] = (
                        claim_count
                    )
                    kid_migrated = True

            # Migrate reward_approvals{} → reward_data[id].total_approved
            reward_approvals = kid_info.get(const.DATA_KID_REWARD_APPROVALS_LEGACY, {})
            for reward_id, approval_count in reward_approvals.items():
                if reward_id not in reward_data:
                    reward_data[reward_id] = self._create_empty_reward_entry(
                        reward_id, rewards_data
                    )
                # Only migrate if total_approved is 0 (not already set)
                if (
                    reward_data[reward_id].get(
                        const.DATA_KID_REWARD_DATA_TOTAL_APPROVED, 0
                    )
                    == 0
                ):
                    reward_data[reward_id][
                        const.DATA_KID_REWARD_DATA_TOTAL_APPROVED
                    ] = approval_count
                    # Estimate total_points_spent from approvals * reward cost
                    reward_info = rewards_data.get(reward_id, {})
                    cost = reward_info.get(const.DATA_REWARD_COST, 0)
                    if cost > 0:
                        reward_data[reward_id][
                            const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT
                        ] = approval_count * cost
                    kid_migrated = True

            if kid_migrated:
                migrated_kids += 1
                const.LOGGER.debug(
                    "Migrated reward data for kid '%s' (%s)",
                    kid_info.get(const.DATA_KID_NAME, ""),
                    kid_id,
                )

        if migrated_kids > 0:
            const.LOGGER.info(
                "Reward data migration complete. Migrated %d kids to period-based structure.",
                migrated_kids,
            )

    def _create_empty_reward_entry(
        self, reward_id: str, rewards_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create an empty reward_data entry with all fields initialized.

        Args:
            reward_id: The reward's internal ID
            rewards_data: The rewards data dict for looking up reward name

        Returns:
            A new reward_data entry dict with all fields initialized.
        """
        return {
            const.DATA_KID_REWARD_DATA_NAME: rewards_data.get(reward_id, {}).get(
                const.DATA_REWARD_NAME, ""
            ),
            const.DATA_KID_REWARD_DATA_PENDING_COUNT: 0,
            const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS: [],
            const.DATA_KID_REWARD_DATA_LAST_CLAIMED: None,
            const.DATA_KID_REWARD_DATA_LAST_APPROVED: None,
            const.DATA_KID_REWARD_DATA_LAST_DISAPPROVED: None,
            const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS: 0,
            const.DATA_KID_REWARD_DATA_TOTAL_APPROVED: 0,
            const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED: 0,
            const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT: 0,
            const.DATA_KID_REWARD_DATA_PERIODS: {
                const.DATA_KID_REWARD_DATA_PERIODS_DAILY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_YEARLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_ALL_TIME: {},
            },
        }

    def _remove_legacy_fields(self) -> None:
        """Remove all legacy fields from data after migration is complete.

        During migration, legacy fields are READ to populate new structures,
        but they must be REMOVED from the final v42+ data to ensure clean
        data structures and pass validation tests.

        This method removes ALL legacy fields that have been superseded by
        the new data model. Some individual migration methods already remove
        their specific fields (e.g., shared_chore, allow_multiple_claims_per_day),
        but this method provides comprehensive cleanup for fields that were
        only read during aggregation migrations.

        Legacy fields removed:
        - Kids: chore_claims, chore_streaks, chore_approvals, today_chore_approvals,
                completed_chores_*, points_earned_*, pending_rewards, redeemed_rewards,
                reward_claims, reward_approvals
        - Top-level: pending_chore_approvals, pending_reward_approvals (if legacy format)

        Fields NOT removed (still in use or not fully migrated):
        - Kids: max_streak (backward compat, used by legacy sensors)
        - Kids: badges (already removed by _migrate_kid_legacy_badges_to_cumulative_progress)
        - Chores: shared_chore, allow_multiple_claims_per_day (already removed inline)
        - Badges: threshold_type, threshold_value, etc. (already removed inline)
        """
        kids_cleaned = 0
        fields_removed_count = 0

        # Legacy kid fields to remove after migration
        kid_legacy_fields = [
            # Chore tracking (migrated to chore_data and chore_stats)
            const.DATA_KID_CHORE_CLAIMS_LEGACY,
            const.DATA_KID_CHORE_STREAKS_LEGACY,
            const.DATA_KID_CHORE_APPROVALS_LEGACY,
            # Chore approvals today (migrated to periods structure)
            const.DATA_KID_TODAY_CHORE_APPROVALS_LEGACY,
            # Completed chores counters (migrated to chore_stats)
            const.DATA_KID_COMPLETED_CHORES_TOTAL_LEGACY,
            const.DATA_KID_COMPLETED_CHORES_MONTHLY_LEGACY,
            const.DATA_KID_COMPLETED_CHORES_WEEKLY_LEGACY,
            const.DATA_KID_COMPLETED_CHORES_TODAY_LEGACY,
            const.DATA_KID_COMPLETED_CHORES_YEARLY_LEGACY,
            # Points earned tracking (migrated to point_stats)
            const.DATA_KID_POINTS_EARNED_TODAY_LEGACY,
            const.DATA_KID_POINTS_EARNED_WEEKLY_LEGACY,
            const.DATA_KID_POINTS_EARNED_MONTHLY_LEGACY,
            const.DATA_KID_POINTS_EARNED_YEARLY_LEGACY,
            # Reward tracking (migrated to reward_data)
            const.DATA_KID_PENDING_REWARDS_LEGACY,
            const.DATA_KID_REDEEMED_REWARDS_LEGACY,
            const.DATA_KID_REWARD_CLAIMS_LEGACY,
            const.DATA_KID_REWARD_APPROVALS_LEGACY,
            # Point statistics (max_points_ever migrated to point_stats.highest_balance)
            const.DATA_KID_MAX_POINTS_EVER_LEGACY,
        ]

        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})
        for kid_id, kid_info in kids_data.items():
            removed_any = False
            for field in kid_legacy_fields:
                if field in kid_info:
                    del kid_info[field]
                    removed_any = True
                    fields_removed_count += 1
                    const.LOGGER.debug(
                        "Removed legacy field '%s' from kid '%s'",
                        field,
                        kid_info.get(const.DATA_KID_NAME, kid_id),
                    )
            if removed_any:
                kids_cleaned += 1

        if kids_cleaned > 0:
            const.LOGGER.info(
                "Legacy field cleanup: removed %s fields from %s kids",
                fields_removed_count,
                kids_cleaned,
            )
        else:
            const.LOGGER.debug("Legacy field cleanup: no legacy fields found to remove")

    def _round_float_precision(self) -> None:
        """Round all stored float values to standard precision (DATA_FLOAT_PRECISION).

        Python float arithmetic can cause precision drift, e.g., 2.2 * 12.5 = 27.499999999999996
        instead of 27.5. This migration cleans up any existing drifted values by rounding
        to DATA_FLOAT_PRECISION (2 decimal places) for consistent storage.

        Affected fields per kid:
        - points: Current point balance
        - points_multiplier: Point earning multiplier
        - point_stats.*: All point statistics
        - point_data.periods.*: All period point values
        - chore_stats.*: All chore statistics (total_points_from_chores_*)
        - chore_data.*.periods.*: All chore period point values
        - cumulative_badge_progress.*: baseline, cycle_points, etc.
        """
        precision = const.DATA_FLOAT_PRECISION
        kids_cleaned = 0
        values_rounded = 0

        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})
        for kid_id, kid_info in kids_data.items():
            kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
            rounded_any = False

            # --- Top-level kid float fields ---
            for field in [
                const.DATA_KID_POINTS,
                const.DATA_KID_POINTS_MULTIPLIER,
            ]:
                if field in kid_info and isinstance(kid_info[field], (int, float)):
                    old_val = kid_info[field]
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        kid_info[field] = new_val
                        rounded_any = True
                        values_rounded += 1

            # --- point_stats fields ---
            point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
            for key, val in list(point_stats.items()):
                if isinstance(val, (int, float)):
                    old_val = val
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        point_stats[key] = new_val
                        rounded_any = True
                        values_rounded += 1
                elif isinstance(val, dict):
                    # Handle nested by_source dicts
                    for nested_key, nested_val in list(val.items()):
                        if isinstance(nested_val, (int, float)):
                            old_val = nested_val
                            new_val = round(float(old_val), precision)
                            if old_val != new_val:
                                val[nested_key] = new_val
                                rounded_any = True
                                values_rounded += 1

            # --- point_data.periods.*.* ---
            point_data = kid_info.get(const.DATA_KID_POINT_DATA, {})
            periods = point_data.get(const.DATA_KID_POINT_DATA_PERIODS, {})
            for period_type in list(periods.keys()):
                period_dict = periods.get(period_type, {})
                for _, period_data in list(period_dict.items()):
                    if isinstance(period_data, dict):
                        for field_key, field_val in list(period_data.items()):
                            if isinstance(field_val, (int, float)):
                                old_val = field_val
                                new_val = round(float(old_val), precision)
                                if old_val != new_val:
                                    period_data[field_key] = new_val
                                    rounded_any = True
                                    values_rounded += 1
                            elif isinstance(field_val, dict):
                                # by_source nested dict
                                for nested_key, nested_val in list(field_val.items()):
                                    if isinstance(nested_val, (int, float)):
                                        old_val = nested_val
                                        new_val = round(float(old_val), precision)
                                        if old_val != new_val:
                                            field_val[nested_key] = new_val
                                            rounded_any = True
                                            values_rounded += 1

            # --- chore_stats fields ---
            chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
            for key, val in list(chore_stats.items()):
                if isinstance(val, (int, float)) and "points" in key.lower():
                    old_val = val
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        chore_stats[key] = new_val
                        rounded_any = True
                        values_rounded += 1

            # --- chore_data.*.periods.*.* points fields ---
            chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            for _, chore_info in list(chore_data.items()):
                chore_periods = chore_info.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
                for _period_type, period_dict in list(chore_periods.items()):
                    for _, period_values in list(period_dict.items()):
                        if isinstance(period_values, dict):
                            points_val = period_values.get(
                                const.DATA_KID_CHORE_DATA_PERIOD_POINTS
                            )
                            if points_val is not None and isinstance(
                                points_val, (int, float)
                            ):
                                old_val = points_val
                                new_val = round(float(old_val), precision)
                                if old_val != new_val:
                                    period_values[
                                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS
                                    ] = new_val
                                    rounded_any = True
                                    values_rounded += 1

            # --- cumulative_badge_progress ---
            cumulative = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
            for field in [
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE,
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS,
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD,
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD,
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_THRESHOLD,
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED,
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_THRESHOLD,
            ]:
                if field in cumulative and isinstance(cumulative[field], (int, float)):
                    old_val = cumulative[field]
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        cumulative[field] = new_val
                        rounded_any = True
                        values_rounded += 1

            if rounded_any:
                kids_cleaned += 1
                const.LOGGER.debug("Rounded float precision for kid '%s'", kid_name)

        if values_rounded > 0:
            const.LOGGER.info(
                "Float precision cleanup: rounded %s values across %s kids to %s decimal places",
                values_rounded,
                kids_cleaned,
                precision,
            )
        else:
            const.LOGGER.debug("Float precision cleanup: no values needed rounding")

    def _cleanup_kid_chore_data_due_dates_v50(self) -> None:
        """Remove legacy due_date fields from kid-level chore_data for independent chores (v50 migration).

        In v50, the single source of truth for independent chore due dates is
        chore_info[per_kid_due_dates][kid_id]. The kid-level chore_data[chore_id][due_date]
        field is now deprecated and should be removed during migration.

        This migration:
        1. Iterates all kids and their chore_data entries
        2. Checks if the chore is INDEPENDENT (completion_criteria)
        3. Removes the due_date field from kid-level chore_data if present

        SHARED chores don't have per-kid due dates, so they're skipped.
        """
        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})

        cleaned_count = 0
        kids_affected = 0

        for kid_info in kids_data.values():
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            kid_had_cleanup = False

            for chore_id in list(kid_chore_data.keys()):
                # Get chore info to check completion criteria
                chore_info = chores_data.get(chore_id, {})
                completion_criteria = chore_info.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA
                )

                # Only clean up INDEPENDENT chores (SHARED chores don't have per-kid dates)
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # Check if legacy due_date field exists in kid-level chore_data
                    if (
                        const.DATA_KID_CHORE_DATA_DUE_DATE_LEGACY
                        in kid_chore_data[chore_id]
                    ):
                        del kid_chore_data[chore_id][
                            const.DATA_KID_CHORE_DATA_DUE_DATE_LEGACY
                        ]
                        cleaned_count += 1
                        kid_had_cleanup = True
                        const.LOGGER.debug(
                            "Removed legacy due_date from kid '%s' chore_data for chore '%s'",
                            kid_name,
                            chore_info.get(const.DATA_CHORE_NAME, chore_id),
                        )

            if kid_had_cleanup:
                kids_affected += 1

        if cleaned_count > 0:
            const.LOGGER.info(
                "v50 cleanup: Removed %s legacy due_date fields from kid-level chore_data across %s kids",
                cleaned_count,
                kids_affected,
            )
        else:
            const.LOGGER.debug(
                "v50 cleanup: No legacy due_date fields found in kid-level chore_data"
            )

    def _simplify_notification_config_v50(self) -> None:
        """Remove redundant enable_notifications field from kid and parent data.

        The enable_notifications field was always derived from bool(mobile_notify_service),
        making it redundant. This migration removes the field from storage data.

        Migration Actions:
        ————————————————————————————————————————————————————————————————————————
        1. Remove enable_notifications from all kids
        2. Remove enable_notifications from all parents

        The notification logic now checks mobile_notify_service directly:
        - If mobile_notify_service has value → send mobile notification
        - Else if use_persistent_notifications → send persistent notification
        - Else → no notification

        Refs: coordinator._notify_kid(), coordinator._notify_parents()
        """
        const.LOGGER.info("INFO: ==========================================")
        const.LOGGER.info(
            "INFO: Schema v50: Removing redundant enable_notifications field"
        )

        kids_data = self.coordinator.kids_data
        parents_data = self.coordinator.parents_data
        changes_made = False

        # Process all kids - just remove the field
        for _kid_id, kid_info in kids_data.items():
            # Cast to Any to bypass TypedDict strict key checking for legacy field removal
            kid_dict = cast("dict[str, Any]", kid_info)
            if "enable_notifications" in kid_dict:
                kid_dict.pop("enable_notifications")
                const.LOGGER.debug(
                    "DEBUG:   Kid '%s': Removed enable_notifications field",
                    kid_info.get(const.DATA_KID_NAME, "Unknown"),
                )
                changes_made = True

        # Process all parents - just remove the field
        for _parent_id, parent_info in parents_data.items():
            # Cast to Any to bypass TypedDict strict key checking for legacy field removal
            parent_dict = cast("dict[str, Any]", parent_info)
            if "enable_notifications" in parent_dict:
                parent_dict.pop("enable_notifications")
                const.LOGGER.debug(
                    "DEBUG:   Parent '%s': Removed enable_notifications field",
                    parent_info.get(const.DATA_PARENT_NAME, "Unknown"),
                )
                changes_made = True

        if changes_made:
            const.LOGGER.info(
                "INFO:   ✓ Removed enable_notifications field from entities"
            )
        else:
            const.LOGGER.info(
                "INFO:   ℹ No enable_notifications fields found (already clean)"
            )

        const.LOGGER.info("INFO: ==========================================")

    def _strip_temporal_stats(self) -> None:
        """Remove temporal (clock-derived) fields from point_stats and chore_stats (Phase 7.5).

        Phase 7.5 Directive: Derivative Data is Ephemeral
        Clock-based statistics (today, week, month) MUST NOT be persisted to JSON storage.
        These values are now derived on-demand from period buckets (point_data.periods).

        High-Water Marks to KEEP (require persistence):
        - points_earned_all_time: Cumulative total (bucket aggregate)
        - points_spent_all_time: Cumulative spent (bucket aggregate)
        - highest_balance: All-time peak balance (cannot be recalculated from buckets)
        - longest_streak_all_time: Peak streak (cannot be recalculated from buckets)
        - approved_all_time: Cumulative chore completions (bucket aggregate)

        Temporal fields to STRIP (now derived from buckets):
        - Point stats: earned/spent/net_today/week/month/year, avg_*, by_source_today/week/month
        - Chore stats: approved/claimed/overdue/disapproved_today/week/month/year, avg_*
        - Most completed: most_completed_chore_week/month/year (all-time kept)
        """
        const.LOGGER.info(
            "Phase 9: Stripping temporal stats from storage (Phase 7.5 - The Great Stripping)"
        )

        # Define temporal fields to strip from point_stats
        # Note: We use the raw string values to match what's actually in storage
        point_stats_temporal_fields = [
            # Earned (temporal periods - all-time stays)
            const.DATA_KID_POINT_STATS_EARNED_TODAY,
            const.DATA_KID_POINT_STATS_EARNED_WEEK,
            const.DATA_KID_POINT_STATS_EARNED_MONTH,
            const.DATA_KID_POINT_STATS_EARNED_YEAR,
            # Spent (temporal periods - all-time stays)
            const.DATA_KID_POINT_STATS_SPENT_TODAY,
            const.DATA_KID_POINT_STATS_SPENT_WEEK,
            const.DATA_KID_POINT_STATS_SPENT_MONTH,
            const.DATA_KID_POINT_STATS_SPENT_YEAR,
            # Net (temporal periods - all-time stays)
            const.DATA_KID_POINT_STATS_NET_TODAY,
            const.DATA_KID_POINT_STATS_NET_WEEK,
            const.DATA_KID_POINT_STATS_NET_MONTH,
            const.DATA_KID_POINT_STATS_NET_YEAR,
            # By-source breakdowns (temporal periods)
            const.DATA_KID_POINT_STATS_BY_SOURCE_TODAY,
            const.DATA_KID_POINT_STATS_BY_SOURCE_WEEK,
            const.DATA_KID_POINT_STATS_BY_SOURCE_MONTH,
            const.DATA_KID_POINT_STATS_BY_SOURCE_YEAR,
            # Averages (derived values)
            const.DATA_KID_POINT_STATS_AVG_PER_DAY_WEEK,
            const.DATA_KID_POINT_STATS_AVG_PER_DAY_MONTH,
            const.DATA_KID_POINT_STATS_AVG_PER_CHORE,
        ]

        # Define temporal fields to strip from chore_stats
        chore_stats_temporal_fields = [
            # Approved counts (temporal periods - all-time stays)
            const.DATA_KID_CHORE_STATS_APPROVED_TODAY,
            const.DATA_KID_CHORE_STATS_APPROVED_WEEK,
            const.DATA_KID_CHORE_STATS_APPROVED_MONTH,
            const.DATA_KID_CHORE_STATS_APPROVED_YEAR,
            # Claimed counts (temporal periods - all-time stays)
            const.DATA_KID_CHORE_STATS_CLAIMED_TODAY,
            const.DATA_KID_CHORE_STATS_CLAIMED_WEEK,
            const.DATA_KID_CHORE_STATS_CLAIMED_MONTH,
            const.DATA_KID_CHORE_STATS_CLAIMED_YEAR,
            # Overdue counts (temporal periods - all-time stays)
            const.DATA_KID_CHORE_STATS_OVERDUE_TODAY,
            const.DATA_KID_CHORE_STATS_OVERDUE_WEEK,
            const.DATA_KID_CHORE_STATS_OVERDUE_MONTH,
            const.DATA_KID_CHORE_STATS_OVERDUE_YEAR,
            # Disapproved counts (temporal periods - all-time stays)
            const.DATA_KID_CHORE_STATS_DISAPPROVED_TODAY,
            const.DATA_KID_CHORE_STATS_DISAPPROVED_WEEK,
            const.DATA_KID_CHORE_STATS_DISAPPROVED_MONTH,
            const.DATA_KID_CHORE_STATS_DISAPPROVED_YEAR,
            # Total points from chores (temporal periods - all-time stays)
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_TODAY,
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_WEEK,
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_MONTH,
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_YEAR,
            # Most completed chore (temporal periods - all-time stays)
            const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_WEEK,
            const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_MONTH,
            const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_YEAR,
            # Longest streaks (temporal periods - all-time stays)
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_WEEK,
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_MONTH,
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_YEAR,
            # Averages (derived values)
            const.DATA_KID_CHORE_STATS_AVG_PER_DAY_WEEK,
            const.DATA_KID_CHORE_STATS_AVG_PER_DAY_MONTH,
            # Current counts (live state, not historical)
            const.DATA_KID_CHORE_STATS_CURRENT_DUE_TODAY,
            const.DATA_KID_CHORE_STATS_CURRENT_OVERDUE,
            const.DATA_KID_CHORE_STATS_CURRENT_CLAIMED,
            const.DATA_KID_CHORE_STATS_CURRENT_APPROVED,
        ]

        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})
        kids_processed = 0
        point_fields_removed = 0
        chore_fields_removed = 0

        for kid_id, kid_info in kids_data.items():
            kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
            kid_had_changes = False

            # Strip temporal fields from point_stats
            point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
            for field in point_stats_temporal_fields:
                if field in point_stats:
                    del point_stats[field]
                    point_fields_removed += 1
                    kid_had_changes = True

            # Strip temporal fields from chore_stats
            chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
            for field in chore_stats_temporal_fields:
                if field in chore_stats:
                    del chore_stats[field]
                    chore_fields_removed += 1
                    kid_had_changes = True

            if kid_had_changes:
                kids_processed += 1
                const.LOGGER.debug(
                    "Stripped temporal stats from kid '%s'",
                    kid_name,
                )

        total_removed = point_fields_removed + chore_fields_removed
        if total_removed > 0:
            const.LOGGER.info(
                "Phase 9 complete: Removed %s temporal fields from %s kids "
                "(point_stats: %s, chore_stats: %s)",
                total_removed,
                kids_processed,
                point_fields_removed,
                chore_fields_removed,
            )
        else:
            const.LOGGER.debug(
                "Phase 9 complete: No temporal stats fields found to strip (already clean)"
            )

    # -------------------------------------------------------------------------------------
    # Migration-only methods (extracted from coordinator.py)
    # These methods are ONLY called during pre-v0.5.0 migrations
    # -------------------------------------------------------------------------------------

    def remove_deprecated_entities(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Remove old/deprecated sensor entities from the entity registry that are no longer used."""

        ent_reg = er.async_get(hass)

        for entity_id, entity_entry in list(ent_reg.entities.items()):
            if not entity_entry.unique_id.startswith(f"{entry.entry_id}_"):
                continue
            if any(
                entity_entry.unique_id.endswith(suffix)
                for suffix in const.ENTITY_SUFFIXES_LEGACY
            ):
                ent_reg.async_remove(entity_id)
                const.LOGGER.debug(
                    "DEBUG: Removed deprecated Entity '%s', UID '%s'",
                    entity_id,
                    entity_entry.unique_id,
                )

    def remove_deprecated_button_entities(self) -> None:
        """Remove dynamic button entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Chore Buttons ---
        # For each chore, create expected unique IDs for claim, approve, and disapprove buttons
        for chore_id, chore_info in self.coordinator.chores_data.items():
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                # Expected unique_id formats:
                uid_claim = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}"
                uid_approve = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
                uid_disapprove = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"
                allowed_uids.update({uid_claim, uid_approve, uid_disapprove})

        # --- Reward Buttons ---
        # For each kid and reward, add expected unique IDs for reward claim, approve, and disapprove buttons.
        for kid_id in self.coordinator.kids_data:
            for reward_id in self.coordinator.rewards_data:
                # The reward claim button might be built with a dedicated prefix:
                uid_claim = f"{self.coordinator.config_entry.entry_id}_{const.BUTTON_REWARD_PREFIX}{kid_id}_{reward_id}"
                uid_approve = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
                uid_disapprove = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
                allowed_uids.update({uid_claim, uid_approve, uid_disapprove})

        # --- Penalty Buttons ---
        for kid_id in self.coordinator.kids_data:
            for penalty_id in self.coordinator.penalties_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{const.BUTTON_PENALTY_PREFIX}{kid_id}_{penalty_id}"
                allowed_uids.add(uid)

        # --- Bonus Buttons ---
        for kid_id in self.coordinator.kids_data:
            for bonus_id in self.coordinator.bonuses_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{const.BUTTON_BONUS_PREFIX}{kid_id}_{bonus_id}"
                allowed_uids.add(uid)

        # --- Points Adjust Buttons ---
        # Determine the list of adjustment delta values from configuration or defaults.
        raw_values = self.coordinator.config_entry.options.get(
            const.CONF_POINTS_ADJUST_VALUES
        )
        if not raw_values:
            points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        elif isinstance(raw_values, str):
            points_adjust_values = parse_points_adjust_values(raw_values)
            if not points_adjust_values:
                points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        elif isinstance(raw_values, list):
            try:
                points_adjust_values = [float(v) for v in raw_values]
            except (ValueError, TypeError):
                points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        else:
            points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES

        for kid_id in self.coordinator.kids_data:
            for delta in points_adjust_values:
                uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.BUTTON_KC_UID_MIDFIX_ADJUST_POINTS_LEGACY}{delta}"
                allowed_uids.add(uid)

        # --- Now remove any button entity whose unique_id is not in allowed_uids ---
        for entity_entry in list(ent_reg.entities.values()):
            # Only check buttons from our platform (kidschores)
            if entity_entry.platform != const.DOMAIN or entity_entry.domain != "button":
                continue

            # If this button doesn't match our whitelist, remove it
            # This catches old entities from previous configs, migrations, or different entry_ids
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Button '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_sensor_entities(self) -> None:
        """Remove dynamic sensor entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Chore Status Sensors ---
        # For each chore, create expected unique IDs for chore status sensors
        for chore_id, chore_info in self.coordinator.chores_data.items():
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
                allowed_uids.add(uid)

        # --- Shared Chore Global State Sensors ---
        for chore_id, chore_info in self.coordinator.chores_data.items():
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED
            ):
                uid = f"{self.coordinator.config_entry.entry_id}_{chore_id}{const.DATA_GLOBAL_STATE_SUFFIX}"
                allowed_uids.add(uid)

        # --- Reward Status Sensors ---
        for reward_id in self.coordinator.rewards_data:
            for kid_id in self.coordinator.kids_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{reward_id}{const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}"
                allowed_uids.add(uid)

        # --- Penalty/Bonus Apply Sensors ---
        for kid_id in self.coordinator.kids_data:
            for penalty_id in self.coordinator.penalties_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{penalty_id}{const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR}"
                allowed_uids.add(uid)
            for bonus_id in self.coordinator.bonuses_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{bonus_id}{const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR}"
                allowed_uids.add(uid)

        # --- Achievement Progress Sensors ---
        for achievement_id, achievement in self.coordinator.achievements_data.items():
            for kid_id in achievement.get(const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, []):
                uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}"
                allowed_uids.add(uid)

        # --- Challenge Progress Sensors ---
        for challenge_id, challenge in self.coordinator.challenges_data.items():
            for kid_id in challenge.get(const.DATA_CHALLENGE_ASSIGNED_KIDS, []):
                uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}"
                allowed_uids.add(uid)

        # --- Kid-specific sensors (not dynamic based on chores/rewards) ---
        # These are created once per kid and don't need validation against dynamic data
        for kid_id in self.coordinator.kids_data:
            # Standard kid sensors
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_BADGES_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_MAX_POINTS_EVER_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_HIGHEST_STREAK_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER}"
            )

            # Badge progress sensors
            badge_progress_data = self.coordinator.kids_data[kid_id].get(
                const.DATA_KID_BADGE_PROGRESS, {}
            )
            for badge_id, progress_info in badge_progress_data.items():
                badge_type = progress_info.get(const.DATA_KID_BADGE_PROGRESS_TYPE)
                if badge_type != const.BADGE_TYPE_CUMULATIVE:
                    uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}"
                    allowed_uids.add(uid)

        # --- Global sensors (not kid-specific) ---
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}"
        )

        # --- Now remove any sensor entity whose unique_id is not in allowed_uids ---
        for entity_entry in list(ent_reg.entities.values()):
            # Only check sensors from our platform (kidschores)
            if entity_entry.platform != const.DOMAIN or entity_entry.domain != "sensor":
                continue

            # If this sensor doesn't match our whitelist, remove it
            # This catches old entities from previous configs, migrations, or different entry_ids
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Sensor '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_calendar_entities(self) -> None:
        """Remove dynamic calendar entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Kid Calendar Entities ---
        for kid_id in self.coordinator.kids_data:
            uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.CALENDAR_KC_UID_SUFFIX_CALENDAR}"
            allowed_uids.add(uid)

        # --- Now remove any calendar entity whose unique_id is not in allowed_uids ---
        for entity_entry in list(ent_reg.entities.values()):
            # Only check calendars from our platform (kidschores)
            if (
                entity_entry.platform != const.DOMAIN
                or entity_entry.domain != "calendar"
            ):
                continue

            # If this calendar doesn't match our whitelist, remove it
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Calendar '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_datetime_entities(self) -> None:
        """Remove dynamic datetime entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Kid Dashboard Date Helper Entities ---
        for kid_id in self.coordinator.kids_data:
            uid = f"{self.coordinator.config_entry.entry_id}_{kid_id}{const.DATETIME_KC_UID_SUFFIX_DATE_HELPER}"
            allowed_uids.add(uid)

        # --- Now remove any datetime entity whose unique_id is not in allowed_uids ---
        for entity_entry in list(ent_reg.entities.values()):
            # Only check datetime from our platform (kidschores)
            if (
                entity_entry.platform != const.DOMAIN
                or entity_entry.domain != "datetime"
            ):
                continue

            # If this datetime doesn't match our whitelist, remove it
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Datetime '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_select_entities(self) -> None:
        """Remove dynamic select entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Global Select Entities (system-level) ---
        # These are NOT kid-specific
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_CHORES_SELECT}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_REWARDS_SELECT}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_PENALTIES_SELECT}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_BONUSES_SELECT}"
        )

        # --- Kid-specific Dashboard Helper Select Entities ---
        for kid_id in self.coordinator.kids_data:
            uid = f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_MIDFIX_CHORES_SELECT_LEGACY}{kid_id}"
            allowed_uids.add(uid)

        # --- Now remove any select entity whose unique_id is not in allowed_uids ---
        for entity_entry in list(ent_reg.entities.values()):
            # Only check selects from our platform (kidschores)
            if entity_entry.platform != const.DOMAIN or entity_entry.domain != "select":
                continue

            # If this select doesn't match our whitelist, remove it
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Select '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def _create_kid(self, kid_id: str, kid_data: dict[str, Any]) -> None:
        """Create a new kid entity during migration.

        This is a local copy for migration only - production code uses
        data_builders.build_kid() + direct storage writes.
        """
        self.coordinator._data[const.DATA_KIDS][kid_id] = {
            const.DATA_KID_NAME: kid_data.get(
                const.DATA_KID_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_KID_POINTS: kid_data.get(
                const.DATA_KID_POINTS, const.DEFAULT_ZERO
            ),
            const.DATA_KID_BADGES_EARNED: kid_data.get(
                const.DATA_KID_BADGES_EARNED, {}
            ),
            const.DATA_KID_HA_USER_ID: kid_data.get(const.DATA_KID_HA_USER_ID),
            const.DATA_KID_INTERNAL_ID: kid_id,
            const.DATA_KID_POINTS_MULTIPLIER: kid_data.get(
                const.DATA_KID_POINTS_MULTIPLIER, const.DEFAULT_KID_POINTS_MULTIPLIER
            ),
            const.DATA_KID_PENALTY_APPLIES: kid_data.get(
                const.DATA_KID_PENALTY_APPLIES, {}
            ),
            const.DATA_KID_BONUS_APPLIES: kid_data.get(
                const.DATA_KID_BONUS_APPLIES, {}
            ),
            const.DATA_KID_REWARD_DATA: kid_data.get(const.DATA_KID_REWARD_DATA, {}),
            const.DATA_KID_ENABLE_NOTIFICATIONS_LEGACY: kid_data.get(
                const.DATA_KID_ENABLE_NOTIFICATIONS_LEGACY, True
            ),
            const.DATA_KID_MOBILE_NOTIFY_SERVICE: kid_data.get(
                const.DATA_KID_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            ),
            const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS: kid_data.get(
                const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS, True
            ),
            const.DATA_KID_OVERDUE_CHORES: [],
            const.DATA_KID_OVERDUE_NOTIFICATIONS: {},
        }

        const.LOGGER.debug(
            "DEBUG: Kid Added (migration) - '%s', ID '%s'",
            self.coordinator._data[const.DATA_KIDS][kid_id][const.DATA_KID_NAME],
            kid_id,
        )

    def _update_kid(self, kid_id: str, kid_data: dict[str, Any]):
        """Update an existing kid entity, only updating fields present in kid_data."""

        kids = self.coordinator._data.setdefault(const.DATA_KIDS, {})
        existing = kids.get(kid_id, {})
        # Only update fields present in kid_data, preserving all others
        existing.update(kid_data)
        kids[kid_id] = existing

        kid_name = existing.get(const.DATA_KID_NAME, const.SENTINEL_EMPTY)
        const.LOGGER.debug(
            "DEBUG: Kid Updated - '%s', ID '%s'",
            kid_name,
            kid_id,
        )

    def _create_parent(self, parent_id: str, parent_data: dict[str, Any]):
        associated_kids_ids = []
        for kid_id in parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            if kid_id in self.coordinator.kids_data:
                associated_kids_ids.append(kid_id)
            else:
                const.LOGGER.warning(
                    "WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent",
                    parent_data.get(const.DATA_PARENT_NAME, parent_id),
                    kid_id,
                )

        self.coordinator._data[const.DATA_PARENTS][parent_id] = {
            const.DATA_PARENT_NAME: parent_data.get(
                const.DATA_PARENT_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_PARENT_HA_USER_ID: parent_data.get(
                const.DATA_PARENT_HA_USER_ID, const.SENTINEL_EMPTY
            ),
            const.DATA_PARENT_ASSOCIATED_KIDS: associated_kids_ids,
            const.DATA_PARENT_ENABLE_NOTIFICATIONS_LEGACY: parent_data.get(
                const.DATA_PARENT_ENABLE_NOTIFICATIONS_LEGACY, True
            ),
            const.DATA_PARENT_MOBILE_NOTIFY_SERVICE: parent_data.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            ),
            const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS: parent_data.get(
                const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, True
            ),
            const.DATA_PARENT_INTERNAL_ID: parent_id,
            # Parent chore capability fields (v0.6.0+)
            const.DATA_PARENT_DASHBOARD_LANGUAGE: parent_data.get(
                const.DATA_PARENT_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            ),
            const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT: parent_data.get(
                const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT,
                const.DEFAULT_PARENT_ALLOW_CHORE_ASSIGNMENT,
            ),
            const.DATA_PARENT_ENABLE_CHORE_WORKFLOW: parent_data.get(
                const.DATA_PARENT_ENABLE_CHORE_WORKFLOW,
                const.DEFAULT_PARENT_ENABLE_CHORE_WORKFLOW,
            ),
            const.DATA_PARENT_ENABLE_GAMIFICATION: parent_data.get(
                const.DATA_PARENT_ENABLE_GAMIFICATION,
                const.DEFAULT_PARENT_ENABLE_GAMIFICATION,
            ),
            const.DATA_PARENT_LINKED_SHADOW_KID_ID: parent_data.get(
                const.DATA_PARENT_LINKED_SHADOW_KID_ID
            ),
        }
        const.LOGGER.debug(
            "DEBUG: Parent Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_PARENTS][parent_id][
                const.DATA_PARENT_NAME
            ],
            parent_id,
        )

    def _update_parent(self, parent_id: str, parent_data: dict[str, Any]):
        parent_info = self.coordinator._data[const.DATA_PARENTS][parent_id]
        parent_info[const.DATA_PARENT_NAME] = parent_data.get(
            const.DATA_PARENT_NAME, parent_info[const.DATA_PARENT_NAME]
        )
        parent_info[const.DATA_PARENT_HA_USER_ID] = parent_data.get(
            const.DATA_PARENT_HA_USER_ID, parent_info[const.DATA_PARENT_HA_USER_ID]
        )

        # Update associated_kids
        updated_kids = []
        for kid_id in parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            if kid_id in self.coordinator.kids_data:
                updated_kids.append(kid_id)
            else:
                const.LOGGER.warning(
                    "WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent",
                    parent_info[const.DATA_PARENT_NAME],
                    kid_id,
                )
        parent_info[const.DATA_PARENT_ASSOCIATED_KIDS] = updated_kids
        parent_info[const.DATA_PARENT_ENABLE_NOTIFICATIONS_LEGACY] = parent_data.get(
            const.DATA_PARENT_ENABLE_NOTIFICATIONS_LEGACY,
            parent_info.get(const.DATA_PARENT_ENABLE_NOTIFICATIONS_LEGACY, True),
        )
        parent_info[const.DATA_PARENT_MOBILE_NOTIFY_SERVICE] = parent_data.get(
            const.DATA_PARENT_MOBILE_NOTIFY_SERVICE,
            parent_info.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            ),
        )
        parent_info[const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS] = parent_data.get(
            const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS,
            parent_info.get(const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, True),
        )
        # Parent chore capability fields (v0.6.0+)
        parent_info[const.DATA_PARENT_DASHBOARD_LANGUAGE] = parent_data.get(
            const.DATA_PARENT_DASHBOARD_LANGUAGE,
            parent_info.get(
                const.DATA_PARENT_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            ),
        )
        parent_info[const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT] = parent_data.get(
            const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT,
            parent_info.get(
                const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT,
                const.DEFAULT_PARENT_ALLOW_CHORE_ASSIGNMENT,
            ),
        )
        parent_info[const.DATA_PARENT_ENABLE_CHORE_WORKFLOW] = parent_data.get(
            const.DATA_PARENT_ENABLE_CHORE_WORKFLOW,
            parent_info.get(
                const.DATA_PARENT_ENABLE_CHORE_WORKFLOW,
                const.DEFAULT_PARENT_ENABLE_CHORE_WORKFLOW,
            ),
        )
        parent_info[const.DATA_PARENT_ENABLE_GAMIFICATION] = parent_data.get(
            const.DATA_PARENT_ENABLE_GAMIFICATION,
            parent_info.get(
                const.DATA_PARENT_ENABLE_GAMIFICATION,
                const.DEFAULT_PARENT_ENABLE_GAMIFICATION,
            ),
        )
        # Update shadow kid link if provided (set by options_flow when toggling
        # allow_chore_assignment)
        if const.DATA_PARENT_LINKED_SHADOW_KID_ID in parent_data:
            parent_info[const.DATA_PARENT_LINKED_SHADOW_KID_ID] = parent_data.get(
                const.DATA_PARENT_LINKED_SHADOW_KID_ID
            )

        const.LOGGER.debug(
            "DEBUG: Parent Updated - '%s', ID '%s'",
            parent_info[const.DATA_PARENT_NAME],
            parent_id,
        )

    def _create_chore(self, chore_id: str, chore_data: dict[str, Any]):
        # Use data_builders to build complete chore structure with all defaults
        # For migration, we pass chore_data with internal_id already set
        chore_data[const.DATA_CHORE_INTERNAL_ID] = chore_id
        self.coordinator._data[const.DATA_CHORES][chore_id] = db.build_chore(
            chore_data, existing=None
        )
        const.LOGGER.debug(
            "DEBUG: Chore Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_CHORES][chore_id][const.DATA_CHORE_NAME],
            chore_id,
        )

    def _update_chore(self, chore_id: str, chore_data: dict[str, Any]):
        """Update chore data (simplified for migration - no notifications or reload detection)."""
        chore_info = self.coordinator._data[const.DATA_CHORES][chore_id]
        chore_info[const.DATA_CHORE_NAME] = chore_data.get(
            const.DATA_CHORE_NAME, chore_info[const.DATA_CHORE_NAME]
        )
        chore_info[const.DATA_CHORE_STATE] = chore_data.get(
            const.DATA_CHORE_STATE, chore_info[const.DATA_CHORE_STATE]
        )
        chore_info[const.DATA_CHORE_DEFAULT_POINTS] = chore_data.get(
            const.DATA_CHORE_DEFAULT_POINTS, chore_info[const.DATA_CHORE_DEFAULT_POINTS]
        )
        chore_info[const.DATA_CHORE_APPROVAL_RESET_TYPE] = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            chore_info.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE,
                const.DEFAULT_APPROVAL_RESET_TYPE,
            ),
        )
        chore_info[const.DATA_CHORE_DESCRIPTION] = chore_data.get(
            const.DATA_CHORE_DESCRIPTION, chore_info[const.DATA_CHORE_DESCRIPTION]
        )
        chore_info[const.DATA_CHORE_LABELS] = chore_data.get(
            const.DATA_CHORE_LABELS,
            chore_info.get(const.DATA_CHORE_LABELS, []),
        )
        chore_info[const.DATA_CHORE_ICON] = chore_data.get(
            const.DATA_CHORE_ICON, chore_info[const.DATA_CHORE_ICON]
        )

        # assigned_kids now contains UUIDs directly from flow helpers (no conversion needed)
        # Simplified for migration - just update the list directly (no entity cleanup needed)
        chore_info[const.DATA_CHORE_ASSIGNED_KIDS] = chore_data.get(
            const.DATA_CHORE_ASSIGNED_KIDS,
            chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []),
        )
        chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = chore_data.get(
            const.DATA_CHORE_RECURRING_FREQUENCY,
            chore_info[const.DATA_CHORE_RECURRING_FREQUENCY],
        )

        # Handle due_date based on completion criteria to avoid KeyError
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,  # Legacy default
        )
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # For INDEPENDENT chores: chore-level due_date should remain None
            # (per_kid_due_dates are authoritative)
            chore_info[const.DATA_CHORE_DUE_DATE] = None
        else:
            # For SHARED chores: update chore-level due_date normally
            chore_info[const.DATA_CHORE_DUE_DATE] = chore_data.get(
                const.DATA_CHORE_DUE_DATE, chore_info.get(const.DATA_CHORE_DUE_DATE)
            )

        chore_info[const.DATA_CHORE_LAST_COMPLETED] = chore_data.get(
            const.DATA_CHORE_LAST_COMPLETED,
            chore_info.get(const.DATA_CHORE_LAST_COMPLETED),
        )
        chore_info[const.DATA_CHORE_LAST_CLAIMED] = chore_data.get(
            const.DATA_CHORE_LAST_CLAIMED, chore_info.get(const.DATA_CHORE_LAST_CLAIMED)
        )
        chore_info[const.DATA_CHORE_APPLICABLE_DAYS] = chore_data.get(
            const.DATA_CHORE_APPLICABLE_DAYS,
            chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []),
        )
        chore_info[const.DATA_CHORE_NOTIFY_ON_CLAIM] = chore_data.get(
            const.DATA_CHORE_NOTIFY_ON_CLAIM,
            chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
            ),
        )
        chore_info[const.DATA_CHORE_NOTIFY_ON_APPROVAL] = chore_data.get(
            const.DATA_CHORE_NOTIFY_ON_APPROVAL,
            chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            ),
        )
        chore_info[const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL] = chore_data.get(
            const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
            chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
            ),
        )

        if chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] in (
            const.FREQUENCY_CUSTOM,
            const.FREQUENCY_CUSTOM_FROM_COMPLETE,
        ):
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL] = chore_data.get(
                const.DATA_CHORE_CUSTOM_INTERVAL
            )
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] = chore_data.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT
            )
        else:
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL] = None
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] = None

        # CFE-2026-001: Handle DAILY_MULTI times field
        if (
            chore_info[const.DATA_CHORE_RECURRING_FREQUENCY]
            == const.FREQUENCY_DAILY_MULTI
        ):
            chore_info[const.DATA_CHORE_DAILY_MULTI_TIMES] = chore_data.get(
                const.DATA_CHORE_DAILY_MULTI_TIMES,
                chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, ""),
            )
        else:
            # Clear times if frequency changed away from DAILY_MULTI
            chore_info[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

        # Component 8: Handle completion_criteria changes (INDEPENDENT ↔ SHARED)
        old_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,  # Legacy default
        )
        new_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            old_criteria,  # Keep existing if not provided
        )

        # Update completion_criteria
        chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = new_criteria

        # Update per_kid_due_dates if provided in chore_data (from flow)
        if const.DATA_CHORE_PER_KID_DUE_DATES in chore_data:
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = chore_data[
                const.DATA_CHORE_PER_KID_DUE_DATES
            ]

        # PKAD-2026-001: Update per_kid_applicable_days if provided (from flow)
        if const.DATA_CHORE_PER_KID_APPLICABLE_DAYS in chore_data:
            chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = chore_data[
                const.DATA_CHORE_PER_KID_APPLICABLE_DAYS
            ]

        # PKAD-2026-001: Update per_kid_daily_multi_times if provided (from flow)
        if const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES in chore_data:
            chore_info[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = chore_data[
                const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES
            ]

        const.LOGGER.debug(
            "DEBUG: Chore Updated - '%s', ID '%s'",
            chore_info[const.DATA_CHORE_NAME],
            chore_id,
        )

    def _create_badge(self, badge_id: str, badge_data: dict[str, Any]):
        """Create a new badge entity."""
        self.coordinator._data.setdefault(const.DATA_BADGES, {})[badge_id] = badge_data
        const.LOGGER.debug(
            "DEBUG: Badge Created - '%s', ID '%s'",
            badge_data.get(const.DATA_BADGE_NAME, const.SENTINEL_EMPTY),
            badge_id,
        )

    def _update_badge(self, badge_id: str, badge_data: dict[str, Any]):
        """Update an existing badge entity, only updating fields present in badge_data."""
        badges = self.coordinator._data.setdefault(const.DATA_BADGES, {})
        existing = badges.get(badge_id, {})
        existing.update(badge_data)
        badges[badge_id] = existing
        const.LOGGER.debug(
            "DEBUG: Badge Updated - '%s', ID '%s'",
            existing.get(const.DATA_BADGE_NAME, const.SENTINEL_EMPTY),
            badge_id,
        )

    def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
        self.coordinator._data[const.DATA_REWARDS][reward_id] = {
            const.DATA_REWARD_NAME: reward_data.get(
                const.DATA_REWARD_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_REWARD_COST: reward_data.get(
                const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST
            ),
            const.DATA_REWARD_DESCRIPTION: reward_data.get(
                const.DATA_REWARD_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_REWARD_LABELS: reward_data.get(const.DATA_REWARD_LABELS, []),
            const.DATA_REWARD_ICON: reward_data.get(
                const.DATA_REWARD_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_REWARD_INTERNAL_ID: reward_id,
        }
        const.LOGGER.debug(
            "DEBUG: Reward Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_REWARDS][reward_id][
                const.DATA_REWARD_NAME
            ],
            reward_id,
        )

    def _update_reward(self, reward_id: str, reward_data: dict[str, Any]):
        reward_info = self.coordinator._data[const.DATA_REWARDS][reward_id]
        reward_info[const.DATA_REWARD_NAME] = reward_data.get(
            const.DATA_REWARD_NAME, reward_info[const.DATA_REWARD_NAME]
        )
        reward_info[const.DATA_REWARD_COST] = reward_data.get(
            const.DATA_REWARD_COST, reward_info[const.DATA_REWARD_COST]
        )
        reward_info[const.DATA_REWARD_DESCRIPTION] = reward_data.get(
            const.DATA_REWARD_DESCRIPTION, reward_info[const.DATA_REWARD_DESCRIPTION]
        )
        reward_info[const.DATA_REWARD_LABELS] = reward_data.get(
            const.DATA_REWARD_LABELS, reward_info.get(const.DATA_REWARD_LABELS, [])
        )
        reward_info[const.DATA_REWARD_ICON] = reward_data.get(
            const.DATA_REWARD_ICON, reward_info[const.DATA_REWARD_ICON]
        )
        const.LOGGER.debug(
            "DEBUG: Reward Updated - '%s', ID '%s'",
            reward_info[const.DATA_REWARD_NAME],
            reward_id,
        )

    def _create_bonus(self, bonus_id: str, bonus_data: dict[str, Any]):
        self.coordinator._data[const.DATA_BONUSES][bonus_id] = {
            const.DATA_BONUS_NAME: bonus_data.get(
                const.DATA_BONUS_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_BONUS_POINTS: bonus_data.get(
                const.DATA_BONUS_POINTS, const.DEFAULT_BONUS_POINTS
            ),
            const.DATA_BONUS_DESCRIPTION: bonus_data.get(
                const.DATA_BONUS_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_BONUS_LABELS: bonus_data.get(const.DATA_BONUS_LABELS, []),
            const.DATA_BONUS_ICON: bonus_data.get(
                const.DATA_BONUS_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_BONUS_INTERNAL_ID: bonus_id,
        }
        const.LOGGER.debug(
            "DEBUG: Bonus Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_BONUSES][bonus_id][const.DATA_BONUS_NAME],
            bonus_id,
        )

    def _update_bonus(self, bonus_id: str, bonus_data: dict[str, Any]):
        bonus_info = self.coordinator._data[const.DATA_BONUSES][bonus_id]
        bonus_info[const.DATA_BONUS_NAME] = bonus_data.get(
            const.DATA_BONUS_NAME, bonus_info[const.DATA_BONUS_NAME]
        )
        bonus_info[const.DATA_BONUS_POINTS] = bonus_data.get(
            const.DATA_BONUS_POINTS, bonus_info[const.DATA_BONUS_POINTS]
        )
        bonus_info[const.DATA_BONUS_DESCRIPTION] = bonus_data.get(
            const.DATA_BONUS_DESCRIPTION, bonus_info[const.DATA_BONUS_DESCRIPTION]
        )
        bonus_info[const.DATA_BONUS_LABELS] = bonus_data.get(
            const.DATA_BONUS_LABELS, bonus_info.get(const.DATA_BONUS_LABELS, [])
        )
        bonus_info[const.DATA_BONUS_ICON] = bonus_data.get(
            const.DATA_BONUS_ICON, bonus_info[const.DATA_BONUS_ICON]
        )
        const.LOGGER.debug(
            "DEBUG: Bonus Updated - '%s', ID '%s'",
            bonus_info[const.DATA_BONUS_NAME],
            bonus_id,
        )

    def _create_penalty(self, penalty_id: str, penalty_data: dict[str, Any]):
        self.coordinator._data[const.DATA_PENALTIES][penalty_id] = {
            const.DATA_PENALTY_NAME: penalty_data.get(
                const.DATA_PENALTY_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_PENALTY_POINTS: penalty_data.get(
                const.DATA_PENALTY_POINTS, -const.DEFAULT_PENALTY_POINTS
            ),
            const.DATA_PENALTY_DESCRIPTION: penalty_data.get(
                const.DATA_PENALTY_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_PENALTY_LABELS: penalty_data.get(const.DATA_PENALTY_LABELS, []),
            const.DATA_PENALTY_ICON: penalty_data.get(
                const.DATA_PENALTY_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_PENALTY_INTERNAL_ID: penalty_id,
        }
        const.LOGGER.debug(
            "DEBUG: Penalty Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_PENALTIES][penalty_id][
                const.DATA_PENALTY_NAME
            ],
            penalty_id,
        )

    def _update_penalty(self, penalty_id: str, penalty_data: dict[str, Any]):
        penalty_info = self.coordinator._data[const.DATA_PENALTIES][penalty_id]
        penalty_info[const.DATA_PENALTY_NAME] = penalty_data.get(
            const.DATA_PENALTY_NAME, penalty_info[const.DATA_PENALTY_NAME]
        )
        penalty_info[const.DATA_PENALTY_POINTS] = penalty_data.get(
            const.DATA_PENALTY_POINTS, penalty_info[const.DATA_PENALTY_POINTS]
        )
        penalty_info[const.DATA_PENALTY_DESCRIPTION] = penalty_data.get(
            const.DATA_PENALTY_DESCRIPTION, penalty_info[const.DATA_PENALTY_DESCRIPTION]
        )
        penalty_info[const.DATA_PENALTY_LABELS] = penalty_data.get(
            const.DATA_PENALTY_LABELS, penalty_info.get(const.DATA_PENALTY_LABELS, [])
        )
        penalty_info[const.DATA_PENALTY_ICON] = penalty_data.get(
            const.DATA_PENALTY_ICON, penalty_info[const.DATA_PENALTY_ICON]
        )
        const.LOGGER.debug(
            "DEBUG: Penalty Updated - '%s', ID '%s'",
            penalty_info[const.DATA_PENALTY_NAME],
            penalty_id,
        )

    def _create_achievement(
        self, achievement_id: str, achievement_data: dict[str, Any]
    ):
        self.coordinator._data[const.DATA_ACHIEVEMENTS][achievement_id] = {
            const.DATA_ACHIEVEMENT_NAME: achievement_data.get(
                const.DATA_ACHIEVEMENT_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_DESCRIPTION: achievement_data.get(
                const.DATA_ACHIEVEMENT_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_LABELS: achievement_data.get(
                const.DATA_ACHIEVEMENT_LABELS, []
            ),
            const.DATA_ACHIEVEMENT_ICON: achievement_data.get(
                const.DATA_ACHIEVEMENT_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_ASSIGNED_KIDS: achievement_data.get(
                const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, []
            ),
            const.DATA_ACHIEVEMENT_TYPE: achievement_data.get(
                const.DATA_ACHIEVEMENT_TYPE, const.ACHIEVEMENT_TYPE_STREAK
            ),
            const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: achievement_data.get(
                const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_CRITERIA: achievement_data.get(
                const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_TARGET_VALUE: achievement_data.get(
                const.DATA_ACHIEVEMENT_TARGET_VALUE, const.DEFAULT_ACHIEVEMENT_TARGET
            ),
            const.DATA_ACHIEVEMENT_REWARD_POINTS: achievement_data.get(
                const.DATA_ACHIEVEMENT_REWARD_POINTS,
                const.DEFAULT_ACHIEVEMENT_REWARD_POINTS,
            ),
            const.DATA_ACHIEVEMENT_PROGRESS: achievement_data.get(
                const.DATA_ACHIEVEMENT_PROGRESS, {}
            ),
            const.DATA_ACHIEVEMENT_INTERNAL_ID: achievement_id,
        }
        const.LOGGER.debug(
            "DEBUG: Achievement Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_ACHIEVEMENTS][achievement_id][
                const.DATA_ACHIEVEMENT_NAME
            ],
            achievement_id,
        )

    def _update_achievement(
        self, achievement_id: str, achievement_data: dict[str, Any]
    ):
        achievement_info = self.coordinator._data[const.DATA_ACHIEVEMENTS][
            achievement_id
        ]
        achievement_info[const.DATA_ACHIEVEMENT_NAME] = achievement_data.get(
            const.DATA_ACHIEVEMENT_NAME, achievement_info[const.DATA_ACHIEVEMENT_NAME]
        )
        achievement_info[const.DATA_ACHIEVEMENT_DESCRIPTION] = achievement_data.get(
            const.DATA_ACHIEVEMENT_DESCRIPTION,
            achievement_info[const.DATA_ACHIEVEMENT_DESCRIPTION],
        )
        achievement_info[const.DATA_ACHIEVEMENT_LABELS] = achievement_data.get(
            const.DATA_ACHIEVEMENT_LABELS,
            achievement_info.get(const.DATA_ACHIEVEMENT_LABELS, []),
        )
        achievement_info[const.DATA_ACHIEVEMENT_ICON] = achievement_data.get(
            const.DATA_ACHIEVEMENT_ICON, achievement_info[const.DATA_ACHIEVEMENT_ICON]
        )
        achievement_info[const.DATA_ACHIEVEMENT_ASSIGNED_KIDS] = achievement_data.get(
            const.DATA_ACHIEVEMENT_ASSIGNED_KIDS,
            achievement_info[const.DATA_ACHIEVEMENT_ASSIGNED_KIDS],
        )
        achievement_info[const.DATA_ACHIEVEMENT_TYPE] = achievement_data.get(
            const.DATA_ACHIEVEMENT_TYPE, achievement_info[const.DATA_ACHIEVEMENT_TYPE]
        )
        achievement_info[const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID] = (
            achievement_data.get(
                const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID,
                achievement_info.get(
                    const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
                ),
            )
        )
        achievement_info[const.DATA_ACHIEVEMENT_CRITERIA] = achievement_data.get(
            const.DATA_ACHIEVEMENT_CRITERIA,
            achievement_info[const.DATA_ACHIEVEMENT_CRITERIA],
        )
        achievement_info[const.DATA_ACHIEVEMENT_TARGET_VALUE] = achievement_data.get(
            const.DATA_ACHIEVEMENT_TARGET_VALUE,
            achievement_info[const.DATA_ACHIEVEMENT_TARGET_VALUE],
        )
        achievement_info[const.DATA_ACHIEVEMENT_REWARD_POINTS] = achievement_data.get(
            const.DATA_ACHIEVEMENT_REWARD_POINTS,
            achievement_info[const.DATA_ACHIEVEMENT_REWARD_POINTS],
        )
        const.LOGGER.debug(
            "DEBUG: Achievement Updated - '%s', ID '%s'",
            achievement_info[const.DATA_ACHIEVEMENT_NAME],
            achievement_id,
        )

    def _create_challenge(self, challenge_id: str, challenge_data: dict[str, Any]):
        self.coordinator._data[const.DATA_CHALLENGES][challenge_id] = {
            const.DATA_CHALLENGE_NAME: challenge_data.get(
                const.DATA_CHALLENGE_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_DESCRIPTION: challenge_data.get(
                const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_LABELS: challenge_data.get(
                const.DATA_CHALLENGE_LABELS, []
            ),
            const.DATA_CHALLENGE_ICON: challenge_data.get(
                const.DATA_CHALLENGE_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_ASSIGNED_KIDS: challenge_data.get(
                const.DATA_CHALLENGE_ASSIGNED_KIDS, []
            ),
            const.DATA_CHALLENGE_TYPE: challenge_data.get(
                const.DATA_CHALLENGE_TYPE, const.CHALLENGE_TYPE_DAILY_MIN
            ),
            const.DATA_CHALLENGE_SELECTED_CHORE_ID: challenge_data.get(
                const.DATA_CHALLENGE_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_CRITERIA: challenge_data.get(
                const.DATA_CHALLENGE_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_TARGET_VALUE: challenge_data.get(
                const.DATA_CHALLENGE_TARGET_VALUE, const.DEFAULT_CHALLENGE_TARGET
            ),
            const.DATA_CHALLENGE_REWARD_POINTS: challenge_data.get(
                const.DATA_CHALLENGE_REWARD_POINTS,
                const.DEFAULT_CHALLENGE_REWARD_POINTS,
            ),
            const.DATA_CHALLENGE_START_DATE: (
                challenge_data.get(const.DATA_CHALLENGE_START_DATE)
                if challenge_data.get(const.DATA_CHALLENGE_START_DATE) not in [None, {}]
                else None
            ),
            const.DATA_CHALLENGE_END_DATE: (
                challenge_data.get(const.DATA_CHALLENGE_END_DATE)
                if challenge_data.get(const.DATA_CHALLENGE_END_DATE) not in [None, {}]
                else None
            ),
            const.DATA_CHALLENGE_PROGRESS: challenge_data.get(
                const.DATA_CHALLENGE_PROGRESS, {}
            ),
            const.DATA_CHALLENGE_INTERNAL_ID: challenge_id,
        }
        const.LOGGER.debug(
            "DEBUG: Challenge Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_CHALLENGES][challenge_id][
                const.DATA_CHALLENGE_NAME
            ],
            challenge_id,
        )

    def _update_challenge(self, challenge_id: str, challenge_data: dict[str, Any]):
        challenge_info = self.coordinator._data[const.DATA_CHALLENGES][challenge_id]
        challenge_info[const.DATA_CHALLENGE_NAME] = challenge_data.get(
            const.DATA_CHALLENGE_NAME, challenge_info[const.DATA_CHALLENGE_NAME]
        )
        challenge_info[const.DATA_CHALLENGE_DESCRIPTION] = challenge_data.get(
            const.DATA_CHALLENGE_DESCRIPTION,
            challenge_info[const.DATA_CHALLENGE_DESCRIPTION],
        )
        challenge_info[const.DATA_CHALLENGE_LABELS] = challenge_data.get(
            const.DATA_CHALLENGE_LABELS,
            challenge_info.get(const.DATA_CHALLENGE_LABELS, []),
        )
        challenge_info[const.DATA_CHALLENGE_ICON] = challenge_data.get(
            const.DATA_CHALLENGE_ICON, challenge_info[const.DATA_CHALLENGE_ICON]
        )
        challenge_info[const.DATA_CHALLENGE_ASSIGNED_KIDS] = challenge_data.get(
            const.DATA_CHALLENGE_ASSIGNED_KIDS,
            challenge_info[const.DATA_CHALLENGE_ASSIGNED_KIDS],
        )
        challenge_info[const.DATA_CHALLENGE_TYPE] = challenge_data.get(
            const.DATA_CHALLENGE_TYPE, challenge_info[const.DATA_CHALLENGE_TYPE]
        )
        challenge_info[const.DATA_CHALLENGE_SELECTED_CHORE_ID] = challenge_data.get(
            const.DATA_CHALLENGE_SELECTED_CHORE_ID,
            challenge_info.get(
                const.DATA_CHALLENGE_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
        )
        challenge_info[const.DATA_CHALLENGE_CRITERIA] = challenge_data.get(
            const.DATA_CHALLENGE_CRITERIA, challenge_info[const.DATA_CHALLENGE_CRITERIA]
        )
        challenge_info[const.DATA_CHALLENGE_TARGET_VALUE] = challenge_data.get(
            const.DATA_CHALLENGE_TARGET_VALUE,
            challenge_info[const.DATA_CHALLENGE_TARGET_VALUE],
        )
        challenge_info[const.DATA_CHALLENGE_REWARD_POINTS] = challenge_data.get(
            const.DATA_CHALLENGE_REWARD_POINTS,
            challenge_info[const.DATA_CHALLENGE_REWARD_POINTS],
        )
        challenge_info[const.DATA_CHALLENGE_START_DATE] = (
            challenge_data.get(const.DATA_CHALLENGE_START_DATE)
            if challenge_data.get(const.DATA_CHALLENGE_START_DATE) not in [None, {}]
            else None
        )
        challenge_info[const.DATA_CHALLENGE_END_DATE] = (
            challenge_data.get(const.DATA_CHALLENGE_END_DATE)
            if challenge_data.get(const.DATA_CHALLENGE_END_DATE) not in [None, {}]
            else None
        )
        const.LOGGER.debug(
            "DEBUG: Challenge Updated - '%s', ID '%s'",
            challenge_info[const.DATA_CHALLENGE_NAME],
            challenge_id,
        )


# ================================================================================================
# UID Suffix Migration (v0.5.0) - Standalone Entity Registry Update
# ================================================================================================


@callback
def async_migrate_uid_suffixes_v0_5_0(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Migrate entity unique_ids from generic to explicit suffixes (v0.5.1).

    This one-time migration updates entity unique_ids to use entity-type-scoped
    suffixes (e.g., '_status' → '_chore_status') to enable reliable pattern matching
    for shadow kid entity gating logic.

    The migration is idempotent - entities with new suffixes are skipped.
    Gated by schema version check in __init__.py (only runs if schema < 43).

    Args:
        hass: Home Assistant instance
        config_entry: KidsChores config entry

    """
    # Mapping of old UID suffixes → new UID suffixes (all hardcoded for migration)
    # CRITICAL: Old suffixes must be EXACT legacy patterns, not substrings of new ones
    uid_migration_map: dict[str, str] = {
        # BUTTONS - Chore/Reward/Entity actions
        # NOTE: These generic suffixes like "_approve" can match the end of new
        # suffixes like "_chore_approve", so we MUST check for new suffixes first
        "_approve": "_chore_approve",
        "_claim": "_chore_claim",
        "_unclaim": "_chore_unclaim",
        "_approve_reward": "_reward_approve",
        "_approve_all_rewards": "_kid_approve_all_rewards",
        "_remove_kid_rewards": "_kid_remove_all_rewards",
        "_claim_partial_reward": "_reward_claim_partial",
        "_delete_chore": "_chore_delete",
        "_delete_reward": "_reward_delete",
        "_delete_bonus": "_bonus_delete",
        "_delete_penalty": "_penalty_delete",
        "_delete_achievement": "_achievement_delete",
        "_delete_badge": "_badge_delete",
        "_delete_challenge": "_challenge_delete",
        "_reset_badge": "_badge_reset",
        # SENSORS - Entity status
        "_status": "_chore_status",
        "_reward_status": "_reward_status",
        "_bonus_status": "_bonus_status",
        "_penalty_status": "_penalty_status",
        "_achievement_status": "_achievement_status",
        "_badge_status": "_badge_status",
        "_challenge_status": "_challenge_status",
        # SENSORS - Kid aggregations
        "_chores": "_kid_chores_summary",
        "_points": "_kid_points",
        "_dashboard_helper": "_kid_dashboard_helper",
        # SELECTS
        "_chores_select": "_select_chores",
        "_rewards_select": "_select_rewards",
        # DATETIME
        "_date_helper": "_dashboard_datetime_picker",
        # CALENDAR
        "_calendar": "_kid_calendar",
    }

    # Build set of NEW suffixes (migration targets) for idempotency check
    # If entity already ends with a NEW suffix, it's already migrated - skip it
    new_suffixes: set[str] = set(uid_migration_map.values())

    const.LOGGER.info(
        "Starting UID suffix migration (v0.5.0) for config entry %s",
        config_entry.entry_id,
    )

    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    migration_count = 0
    skip_count = 0
    already_migrated_count = 0

    for entry in registry_entries:
        # IDEMPOTENCY CHECK: Skip if entity already has a NEW suffix
        # This prevents re-migrating already-migrated entities
        has_new_suffix = any(
            entry.unique_id.endswith(new_suffix) for new_suffix in new_suffixes
        )
        if has_new_suffix:
            already_migrated_count += 1
            continue

        # Check if unique_id ends with any old suffix
        old_suffix = None
        for old, _ in uid_migration_map.items():
            if entry.unique_id.endswith(old):
                old_suffix = old
                break

        if not old_suffix:
            skip_count += 1
            continue

        # Build new unique_id by replacing suffix
        new_unique_id = (
            entry.unique_id.removesuffix(old_suffix) + uid_migration_map[old_suffix]
        )

        const.LOGGER.debug(
            "Migrating entity '%s' unique_id from '%s' to '%s'",
            entry.entity_id,
            entry.unique_id,
            new_unique_id,
        )

        try:
            entity_registry.async_update_entity(
                entry.entity_id, new_unique_id=new_unique_id
            )
            migration_count += 1
        except ValueError as err:
            # Conflict: new unique_id already exists (shouldn't happen in practice)
            const.LOGGER.warning(
                "Cannot migrate entity '%s' from '%s' to '%s': %s",
                entry.entity_id,
                entry.unique_id,
                new_unique_id,
                err,
            )

    const.LOGGER.info(
        "UID suffix migration (v0.5.1) complete: %s migrated, %s already done, %s skipped",
        migration_count,
        already_migrated_count,
        skip_count,
    )
