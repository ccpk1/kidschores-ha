# File: coordinator.py
"""Coordinator for the KidsChores integration.

Handles data synchronization, chore claiming and approval, badge tracking,
reward redemption, penalty application, and recurring chore handling.
Manages entities primarily using internal_id for consistency.
"""

# Pylint suppressions for valid coordinator architectural patterns:
# - too-many-lines: Complex coordinators legitimately need comprehensive logic
# - too-many-public-methods: Each service/feature requires its own public method

import asyncio
from calendar import monthrange
from datetime import date, datetime, timedelta
import sys
import time
from typing import Any, cast
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import const, flow_helpers as fh, kc_helpers as kh
from .notification_helper import (
    async_send_notification,
    build_chore_actions,
    build_extra_data,
    build_reward_actions,
)
from .storage_manager import KidsChoresStorageManager
from .type_defs import (
    AchievementProgress,
    AchievementsCollection,
    BadgeData,
    BadgesCollection,
    BonusData,
    BonusesCollection,
    ChallengeProgress,
    ChallengesCollection,
    ChoreData,
    ChoresCollection,
    KidChoreDataEntry,
    KidCumulativeBadgeProgress,
    KidData,
    KidsCollection,
    ParentsCollection,
    PenaltiesCollection,
    PenaltyData,
    RewardData,
    RewardsCollection,
)


class KidsChoresDataCoordinator(DataUpdateCoordinator):
    """Coordinator for KidsChores integration.

    Manages data primarily using internal_id for entities.
    """

    config_entry: ConfigEntry  # Override base class to enforce non-None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        storage_manager: KidsChoresStorageManager,
    ):
        """Initialize the KidsChoresDataCoordinator."""
        update_interval_minutes = config_entry.options.get(
            const.CONF_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
        )

        super().__init__(
            hass,
            const.LOGGER,
            name=f"{const.DOMAIN}{const.COORDINATOR_SUFFIX}",
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self.config_entry = config_entry
        self.storage_manager = storage_manager
        self._data: dict[str, Any] = {}

        # Test mode detection for reminder delays
        self._test_mode = "pytest" in sys.modules
        const.LOGGER.debug(
            "Coordinator initialized in %s mode",
            "TEST" if self._test_mode else "PRODUCTION",
        )

        # Change tracking for pending approvals (for dashboard helper optimization)
        self._pending_chore_changed: bool = True  # True on first load
        self._pending_reward_changed: bool = True  # True on first load

        # Debounced persist tracking (Phase 2 optimization)
        self._persist_task: asyncio.Task | None = None
        self._persist_debounce_seconds = 5

        # Race condition protection for approval methods (v0.5.0+)
        # Prevents duplicate point awards when multiple parents click approve simultaneously
        self._approval_locks: dict[str, asyncio.Lock] = {}

        # Due date reminder tracking (v0.5.0+)
        # Transient set tracking which chore+kid combos have been sent due-soon reminders
        # Key format: "{chore_id}:{kid_id}" - resets on HA restart (acceptable)
        self._due_soon_reminders_sent: set[str] = set()

        # Translation sensor lifecycle management
        # Tracks which language codes have translation sensors created
        self._translation_sensors_created: set[str] = set()
        # Callback for dynamically adding new translation sensors
        self._sensor_add_entities_callback: Any = None

    # -------------------------------------------------------------------------------------
    # Approval Lock Management (Race Condition Protection v0.5.0+)
    # -------------------------------------------------------------------------------------

    def _get_approval_lock(self, operation: str, *identifiers: str) -> asyncio.Lock:
        """Get or create a lock for approval operations.

        Creates unique locks per operation+entity combination to prevent race conditions
        when multiple parents click approve simultaneously, or when a user button-mashes.

        Args:
            operation: Type of operation (e.g., "approve_chore", "approve_reward")
            identifiers: Entity identifiers (e.g., kid_id, chore_id)

        Returns:
            asyncio.Lock for the specific operation+entity combination
        """
        lock_key = f"{operation}:{':'.join(identifiers)}"
        if lock_key not in self._approval_locks:
            self._approval_locks[lock_key] = asyncio.Lock()
        return self._approval_locks[lock_key]

    def _clear_due_soon_reminder(self, chore_id: str, kid_id: str) -> None:
        """Clear due-soon reminder tracking for a chore+kid combination (v0.5.0+).

        Called when chore is claimed, approved, or rescheduled to allow
        a fresh reminder for the next occurrence.

        Args:
            chore_id: The chore internal ID
            kid_id: The kid internal ID
        """
        reminder_key = f"{chore_id}:{kid_id}"
        self._due_soon_reminders_sent.discard(reminder_key)

    # -------------------------------------------------------------------------------------
    # Migrate Data and Converters
    # -------------------------------------------------------------------------------------

    def _run_pre_v50_migrations(self) -> None:
        """Run pre-v50 schema migrations if needed.

        Lazy-loads the migration module to avoid any cost for v50+ users.
        All migration methods are encapsulated in the PreV50Migrator class.
        """
        from .migration_pre_v50 import PreV50Migrator

        migrator = PreV50Migrator(self)
        migrator.run_all_migrations()

    def _assign_kid_to_independent_chores(self, kid_id: str) -> None:
        """Assign kid to all INDEPENDENT chores they're added to.

        When a kid is added, they inherit the template due date for all
        INDEPENDENT chores they're assigned to.
        """
        chores_data = self._data.get(const.DATA_CHORES, {})
        for chore_info in chores_data.values():
            # Only process INDEPENDENT chores
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                continue

            # If kid is assigned to this chore, add their per-kid due date
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if kid_id in assigned_kids:
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                template_due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)
                if kid_id not in per_kid_due_dates:
                    per_kid_due_dates[kid_id] = template_due_date
                    const.LOGGER.debug(
                        "Added kid '%s' to INDEPENDENT chore '%s' with due date: %s",
                        kid_id,
                        chore_info.get(const.DATA_CHORE_NAME),
                        template_due_date,
                    )

    def _remove_kid_from_independent_chores(self, kid_id: str) -> None:
        """Remove kid from per-kid due dates when they're removed.

        Template due date remains unchanged; only per-kid entry is deleted.
        """
        chores_data = self._data.get(const.DATA_CHORES, {})
        for chore_info in chores_data.values():
            # Only process INDEPENDENT chores
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                continue

            # Remove kid from per-kid due dates if present
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
                const.LOGGER.debug(
                    "Removed kid '%s' from INDEPENDENT chore '%s' per-kid dates",
                    kid_id,
                    chore_info.get(const.DATA_CHORE_NAME),
                )

    # Note: Migration methods (_migrate_datetime, _migrate_stored_datetimes, etc.)
    # have been extracted to migration_pre_v50.py and are no longer defined here.
    # They are now methods of the PreV50Migrator class.
    # This section previously contained 781 lines of migration code.
    # All migration methods have been extracted to migration_pre_v50.py.

    # -------------------------------------------------------------------------------------
    # Normalize Data Structures
    # -------------------------------------------------------------------------------------

    def _normalize_kid_reward_data(self, kid_info: KidData) -> None:
        """Ensure reward_data dict is properly initialized.

        Modern reward tracking uses reward_data dict with period-based counters.
        Legacy lists (pending_rewards, redeemed_rewards) are no longer used.
        """
        if not isinstance(kid_info.get(const.DATA_KID_REWARD_DATA), dict):
            kid_info[const.DATA_KID_REWARD_DATA] = {}

    # -------------------------------------------------------------------------------------
    # Periodic + First Refresh
    # -------------------------------------------------------------------------------------

    async def _async_update_data(self):
        """Periodic update."""
        try:
            # Check overdue chores
            await self._check_overdue_chores()

            # Check for due-soon reminders (v0.5.0+)
            await self._check_due_date_reminders()

            # Notify entities of changes
            self.async_update_listeners()

            return self._data
        except Exception as err:
            raise UpdateFailed(f"Error updating KidsChores data: {err}") from err

    async def async_config_entry_first_refresh(self):
        """Load from storage and merge config options."""
        const.LOGGER.debug(
            "DEBUG: Coordinator first refresh - requesting data from storage manager"
        )
        stored_data = self.storage_manager.data
        const.LOGGER.debug(
            "DEBUG: Coordinator received data from storage manager: %s entities",
            {
                "kids": len(stored_data.get(const.DATA_KIDS, {})),
                "chores": len(stored_data.get(const.DATA_CHORES, {})),
                "badges": len(stored_data.get(const.DATA_BADGES, {})),
                "schema_version": stored_data.get(const.DATA_META, {}).get(
                    const.DATA_META_SCHEMA_VERSION,
                    stored_data.get(const.DATA_SCHEMA_VERSION, "missing"),
                ),
            },
        )
        if stored_data:
            self._data = stored_data

            # Get schema version from meta section (v50+) or top-level (v42-)
            meta = self._data.get(const.DATA_META, {})
            storage_schema_version = meta.get(
                const.DATA_META_SCHEMA_VERSION,
                self._data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
            )

            if storage_schema_version < const.SCHEMA_VERSION_STORAGE_ONLY:
                const.LOGGER.info(
                    "INFO: Storage schema version %s < %s, running pre-v50 migrations",
                    storage_schema_version,
                    const.SCHEMA_VERSION_STORAGE_ONLY,
                )
                self._run_pre_v50_migrations()

                # Update to current schema version in meta section
                # Use module-level datetime and dt_util imports

                # DEBUG: Check DEFAULT_MIGRATIONS_APPLIED value
                const.LOGGER.debug(
                    "DEFAULT_MIGRATIONS_APPLIED constant: %s (type: %s, len: %d)",
                    const.DEFAULT_MIGRATIONS_APPLIED,
                    type(const.DEFAULT_MIGRATIONS_APPLIED),
                    len(const.DEFAULT_MIGRATIONS_APPLIED),
                )

                self._data[const.DATA_META] = {
                    const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
                    const.DATA_META_LAST_MIGRATION_DATE: datetime.now(
                        dt_util.UTC
                    ).isoformat(),
                    const.DATA_META_MIGRATIONS_APPLIED: const.DEFAULT_MIGRATIONS_APPLIED,
                }

                # DEBUG: Verify what got assigned
                const.LOGGER.debug(
                    "migrations_applied after assignment: %s (len: %d)",
                    self._data[const.DATA_META][const.DATA_META_MIGRATIONS_APPLIED],
                    len(
                        self._data[const.DATA_META][const.DATA_META_MIGRATIONS_APPLIED]
                    ),
                )

                # Remove old top-level schema_version if present (v42 → v50 migration)
                self._data.pop(const.DATA_SCHEMA_VERSION, None)

                const.LOGGER.info(
                    "Migrated storage from schema version %s to %s",
                    storage_schema_version,
                    const.SCHEMA_VERSION_STORAGE_ONLY,
                )
            else:
                const.LOGGER.debug(
                    "Storage already at schema version %s, skipping migration",
                    storage_schema_version,
                )

            # Clean up legacy migration keys from KC 4.x beta (schema v41)
            # These keys are redundant with schema_version and should be removed
            if const.MIGRATION_PERFORMED in self._data:
                const.LOGGER.debug("Cleaning up legacy key: migration_performed")
                del self._data[const.MIGRATION_PERFORMED]
            if const.MIGRATION_KEY_VERSION in self._data:
                const.LOGGER.debug("Cleaning up legacy key: migration_key_version")
                del self._data[const.MIGRATION_KEY_VERSION]

            # NOTE: Field migrations (show_on_calendar, auto_approve, overdue_handling_type,
            # approval_reset_pending_claim_action) are now handled in migration_pre_v50.py
            # via _add_chore_optional_fields(). For v50+ data, these fields are already
            # set by flow_helpers.py during entity creation via the UI.

        else:
            self._data = {
                const.DATA_KIDS: {},
                const.DATA_CHORES: {},
                const.DATA_BADGES: {},
                const.DATA_REWARDS: {},
                const.DATA_PARENTS: {},
                const.DATA_PENALTIES: {},
                const.DATA_BONUSES: {},
                const.DATA_ACHIEVEMENTS: {},
                const.DATA_CHALLENGES: {},
                # Chore and reward queues now computed dynamically from timestamps
                # Legacy fields DATA_PENDING_*_APPROVALS_DEPRECATED removed - computed from timestamps
            }
            self._data[const.DATA_SCHEMA_VERSION] = const.SCHEMA_VERSION_STORAGE_ONLY

        # Register daily/weekly/monthly resets
        async_track_time_change(
            self.hass,
            self._handle_recurring_chore_resets,
            **const.DEFAULT_DAILY_RESET_TIME,
        )
        async_track_time_change(
            self.hass, self._check_overdue_chores, **const.DEFAULT_DAILY_RESET_TIME
        )
        async_track_time_change(
            self.hass,
            self._bump_past_datetime_helpers,
            **const.DEFAULT_DAILY_RESET_TIME,
        )

        # Note: KC 3.x config sync is now handled by _run_pre_v50_migrations() above
        # (called when storage_schema_version < 42). No separate config sync needed here.

        # Normalize all kids list fields
        for kid in self._data.get(const.DATA_KIDS, {}).values():
            self._normalize_kid_reward_data(kid)

        # Initialize badge references in kid chore tracking
        self._update_chore_badge_references_for_kid()

        # Initialize chore and point stats
        for kid_id in self.kids_data:
            self._recalculate_chore_stats_for_kid(kid_id)
            self._recalculate_point_stats_for_kid(kid_id)

        self._persist(immediate=True)  # Startup persist should be immediate
        await super().async_config_entry_first_refresh()

    # -------------------------------------------------------------------------------------
    # Data Initialization from Config
    # -------------------------------------------------------------------------------------
    # NOTE: KC 3.x config sync code (~175 lines) has been extracted to migration_pre_v50.py
    # This includes:
    # - _initialize_data_from_config() - Main config sync wrapper
    # - _ensure_minimal_structure() - Data structure initialization
    # - _initialize_kids/parents/chores/etc() - Entity type wrappers (9 methods)
    # - _sync_entities() - Core sync engine comparing config vs storage
    #
    # These methods are ONLY used for v41→v50 migration (KC 3.x→4.x+ upgrade).
    # For v4.2+ users, entity data is already in storage; config contains only system settings.
    #
    # CRUD methods (_create_kid, _update_chore, etc.) remain below as they are actively
    # used by options_flow.py for v4.2+ entity management through the UI.

    # -------------------------------------------------------------------------------------
    # Entity CRUD Methods (Active Use by options_flow.py)
    # -------------------------------------------------------------------------------------

    def _remove_entities_in_ha(self, item_id: str):
        """Remove all platform entities whose unique_id references the given item_id."""
        ent_reg = er.async_get(self.hass)
        for entity_entry in list(ent_reg.entities.values()):
            if str(item_id) in str(entity_entry.unique_id):
                ent_reg.async_remove(entity_entry.entity_id)
                const.LOGGER.debug(
                    "DEBUG: Auto-removed entity '%s' with UID '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )

    async def _remove_orphaned_shared_chore_sensors(self):
        """Remove SystemChoreSharedStateSensor entities for chores no longer marked as shared."""
        ent_reg = er.async_get(self.hass)
        prefix = f"{self.config_entry.entry_id}_"
        suffix = const.DATA_GLOBAL_STATE_SUFFIX
        for entity_entry in list(ent_reg.entities.values()):
            unique_id = str(entity_entry.unique_id)
            if (
                entity_entry.domain == const.Platform.SENSOR
                and unique_id.startswith(prefix)
                and unique_id.endswith(suffix)
            ):
                chore_id = unique_id[len(prefix) : -len(suffix)]
                chore_info: ChoreData | None = self.chores_data.get(chore_id)
                if (
                    not chore_info
                    or chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                    != const.COMPLETION_CRITERIA_SHARED
                ):
                    ent_reg.async_remove(entity_entry.entity_id)
                    const.LOGGER.debug(
                        "DEBUG: Removed orphaned Shared Chore Global State Sensor: %s",
                        entity_entry.entity_id,
                    )

    async def _remove_orphaned_kid_chore_entities(self) -> None:
        """Remove kid-chore entities (sensors/buttons) for kids no longer assigned to chores."""
        # PERF: Measure entity registry cleanup duration
        perf_start = time.perf_counter()

        ent_reg = er.async_get(self.hass)
        prefix = f"{self.config_entry.entry_id}_"

        # Build a set of valid kid-chore combinations
        valid_combinations = set()
        for chore_id, chore_info in self.chores_data.items():
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            for kid_id in assigned_kids:
                valid_combinations.add((kid_id, chore_id))

        # Check all entities for orphaned kid-chore entities
        for entity_entry in list(ent_reg.entities.values()):
            # Only check our integration's entities
            if entity_entry.platform != const.DOMAIN:
                continue

            unique_id = str(entity_entry.unique_id)
            if not unique_id.startswith(prefix):
                continue

            # Extract the core part after entry_id prefix
            core = unique_id[len(prefix) :]

            # Check if this is a kid-chore entity by looking for kid_id and chore_id
            # Format is: {kid_id}_{chore_id}{suffix} where suffix could be various things
            # We need to check each chore to see if this entity matches
            is_kid_chore_entity = False
            entity_kid_id = None
            entity_chore_id = None

            for chore_id in self.chores_data:
                if chore_id in core:
                    # Found chore_id, now extract kid_id
                    parts = core.split(f"_{chore_id}")
                    if len(parts) >= 1 and parts[0]:
                        potential_kid_id = parts[0]
                        # Check if this is a valid kid
                        if potential_kid_id in self.kids_data:
                            is_kid_chore_entity = True
                            entity_kid_id = potential_kid_id
                            entity_chore_id = chore_id
                            break

            # If this is a kid-chore entity, check if it's still valid
            if is_kid_chore_entity:
                if (entity_kid_id, entity_chore_id) not in valid_combinations:
                    const.LOGGER.debug(
                        "DEBUG: Removing orphaned kid-chore entity '%s' (unique_id: %s) - Kid '%s' no longer assigned to Chore '%s'",
                        entity_entry.entity_id,
                        entity_entry.unique_id,
                        entity_kid_id,
                        entity_chore_id,
                    )
                    ent_reg.async_remove(entity_entry.entity_id)

        # PERF: Log entity registry cleanup duration
        perf_duration = time.perf_counter() - perf_start
        entity_count = len(ent_reg.entities)
        const.LOGGER.debug(
            "PERF: _remove_orphaned_kid_chore_entities() scanned %d entities in %.3fs",
            entity_count,
            perf_duration,
        )

    async def _remove_orphaned_achievement_entities(self) -> None:
        """Remove achievement progress entities for kids that are no longer assigned."""
        ent_reg = er.async_get(self.hass)
        prefix = f"{self.config_entry.entry_id}_"
        suffix = const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX
        for entity_entry in list(ent_reg.entities.values()):
            unique_id = str(entity_entry.unique_id)
            if (
                entity_entry.domain == const.Platform.SENSOR
                and unique_id.startswith(prefix)
                and unique_id.endswith(suffix)
            ):
                core_id = unique_id[len(prefix) : -len(suffix)]
                parts = core_id.split("_", 1)
                if len(parts) != 2:
                    continue

                kid_id, achievement_id = parts
                achievement_info = self._data.get(const.DATA_ACHIEVEMENTS, {}).get(
                    achievement_id
                )
                if not achievement_info or kid_id not in achievement_info.get(
                    const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, []
                ):
                    ent_reg.async_remove(entity_entry.entity_id)
                    const.LOGGER.debug(
                        "DEBUG: Removed orphaned Achievement Progress sensor '%s'. Kid ID '%s' is not assigned to Achievement '%s'",
                        entity_entry.entity_id,
                        kid_id,
                        achievement_id,
                    )

    async def _remove_orphaned_challenge_entities(self) -> None:
        """Remove challenge progress sensor entities for kids no longer assigned."""
        ent_reg = er.async_get(self.hass)
        prefix = f"{self.config_entry.entry_id}_"
        suffix = const.DATA_CHALLENGE_PROGRESS_SUFFIX
        for entity_entry in list(ent_reg.entities.values()):
            unique_id = str(entity_entry.unique_id)
            if (
                entity_entry.domain == const.Platform.SENSOR
                and unique_id.startswith(prefix)
                and unique_id.endswith(suffix)
            ):
                core_id = unique_id[len(prefix) : -len(suffix)]
                parts = core_id.split("_", 1)
                if len(parts) != 2:
                    continue

                kid_id, challenge_id = parts
                challenge_info = self._data.get(const.DATA_CHALLENGES, {}).get(
                    challenge_id
                )
                if not challenge_info or kid_id not in challenge_info.get(
                    const.DATA_CHALLENGE_ASSIGNED_KIDS, []
                ):
                    ent_reg.async_remove(entity_entry.entity_id)
                    const.LOGGER.debug(
                        "DEBUG: Removed orphaned Challenge Progress sensor '%s'. Kid ID '%s' is not assigned to Challenge '%s'",
                        entity_entry.entity_id,
                        kid_id,
                        challenge_id,
                    )

    def _remove_kid_chore_entities(self, kid_id: str, chore_id: str) -> None:
        """Remove all kid-specific chore entities for a given kid and chore."""
        ent_reg = er.async_get(self.hass)
        for entity_entry in list(ent_reg.entities.values()):
            # Only process entities from our integration
            if entity_entry.platform != const.DOMAIN:
                continue

            # Check if this entity belongs to this kid and chore
            # The unique_id format is: {entry_id}_{kid_id}_{chore_id}{suffix}
            if (kid_id in entity_entry.unique_id) and (
                chore_id in entity_entry.unique_id
            ):
                const.LOGGER.debug(
                    "DEBUG: Removing kid-chore entity '%s' (unique_id: %s) for Kid ID '%s' and Chore '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                    kid_id,
                    chore_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def _cleanup_chore_from_kid(self, kid_id: str, chore_id: str) -> None:
        """Remove references to a specific chore from a kid's data."""
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # Remove from kid_chore_data (timestamp-based tracking v0.4.0+)
        if const.DATA_KID_CHORE_DATA in kid_info:
            if chore_id in kid_info[const.DATA_KID_CHORE_DATA]:
                del kid_info[const.DATA_KID_CHORE_DATA][chore_id]
                const.LOGGER.debug(
                    "DEBUG: Removed Chore '%s' from Kid ID '%s' kid_chore_data",
                    chore_id,
                    kid_id,
                )
        # Queue filter removed - pending approvals now computed from timestamps
        # Chore data is already cleaned above via DATA_KID_CHORE_DATA removal
        self._pending_chore_changed = True

    def _cleanup_pending_reward_approvals(self) -> None:
        """Remove reward_data entries for rewards that no longer exist."""
        valid_reward_ids = set(self._data.get(const.DATA_REWARDS, {}).keys())
        cleaned = False
        for kid_info in self.kids_data.values():
            reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})
            invalid_ids = [rid for rid in reward_data if rid not in valid_reward_ids]
            for rid in invalid_ids:
                reward_data.pop(rid, None)
                cleaned = True
        if cleaned:
            self._pending_reward_changed = True

    def _cleanup_deleted_kid_references(self) -> None:
        """Remove references to kids that no longer exist from other sections."""
        valid_kid_ids = set(self.kids_data.keys())

        # Remove deleted kid IDs from all chore assignments
        for chore_info in self._data.get(const.DATA_CHORES, {}).values():
            if const.DATA_CHORE_ASSIGNED_KIDS in chore_info:
                original = chore_info[const.DATA_CHORE_ASSIGNED_KIDS]
                filtered = [kid for kid in original if kid in valid_kid_ids]
                if filtered != original:
                    chore_info[const.DATA_CHORE_ASSIGNED_KIDS] = filtered
                    const.LOGGER.debug(
                        "DEBUG: Removed Assigned Kids in Chore '%s'",
                        chore_info.get(const.DATA_CHORE_NAME),
                    )

        # Remove progress in achievements and challenges
        for section in [const.DATA_ACHIEVEMENTS, const.DATA_CHALLENGES]:
            for entity in self._data.get(section, {}).values():
                progress = entity.get(const.DATA_PROGRESS, {})
                keys_to_remove = [kid for kid in progress if kid not in valid_kid_ids]
                for kid in keys_to_remove:
                    del progress[kid]
                    const.LOGGER.debug(
                        "DEBUG: Removed Progress for deleted Kid ID '%s' in '%s'",
                        kid,
                        section,
                    )
                if const.DATA_ASSIGNED_KIDS in entity:
                    original_assigned = entity[const.DATA_ASSIGNED_KIDS]
                    filtered_assigned = [
                        kid for kid in original_assigned if kid in valid_kid_ids
                    ]
                    if filtered_assigned != original_assigned:
                        entity[const.DATA_ASSIGNED_KIDS] = filtered_assigned
                        const.LOGGER.debug(
                            "DEBUG: Removed Assigned Kids in '%s', '%s'",
                            section,
                            entity.get(const.DATA_NAME),
                        )

    def _cleanup_deleted_chore_references(self) -> None:
        """Remove references to chores that no longer exist from kid data."""
        valid_chore_ids = set(self.chores_data.keys())
        for kid_info in self.kids_data.values():
            # Clean up kid_chore_data (timestamp-based tracking v0.4.0+)
            if const.DATA_KID_CHORE_DATA in kid_info:
                kid_info[const.DATA_KID_CHORE_DATA] = {
                    chore: data
                    for chore, data in kid_info[const.DATA_KID_CHORE_DATA].items()
                    if chore in valid_chore_ids
                }

    def _cleanup_parent_assignments(self) -> None:
        """Remove any kid IDs from parent's 'associated_kids' that no longer exist."""
        valid_kid_ids = set(self.kids_data.keys())
        for parent_info in self._data.get(const.DATA_PARENTS, {}).values():
            original = parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, [])
            filtered = [kid_id for kid_id in original if kid_id in valid_kid_ids]
            if filtered != original:
                parent_info[const.DATA_PARENT_ASSOCIATED_KIDS] = filtered
                const.LOGGER.debug(
                    "DEBUG: Removed Associated Kids for Parent '%s'. Current Associated Kids: %s",
                    parent_info.get(const.DATA_PARENT_NAME),
                    filtered,
                )

    def _cleanup_deleted_chore_in_achievements(self) -> None:
        """Clear selected_chore_id in achievements if the chore no longer exists."""
        valid_chore_ids = set(self.chores_data.keys())
        for achievement_info in self._data.get(const.DATA_ACHIEVEMENTS, {}).values():
            selected = achievement_info.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID)
            if selected and selected not in valid_chore_ids:
                achievement_info[const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID] = ""
                const.LOGGER.debug(
                    "DEBUG: Removed Selected Chore ID in Achievement '%s'",
                    achievement_info.get(const.DATA_ACHIEVEMENT_NAME),
                )

    def _cleanup_deleted_chore_in_challenges(self) -> None:
        """Clear selected_chore_id in challenges if the chore no longer exists."""
        valid_chore_ids = set(self.chores_data.keys())
        for challenge_info in self._data.get(const.DATA_CHALLENGES, {}).values():
            selected = challenge_info.get(const.DATA_CHALLENGE_SELECTED_CHORE_ID)
            if selected and selected not in valid_chore_ids:
                challenge_info[const.DATA_CHALLENGE_SELECTED_CHORE_ID] = (
                    const.SENTINEL_EMPTY
                )
                const.LOGGER.debug(
                    "DEBUG: Removed Selected Chore ID in Challenge '%s'",
                    challenge_info.get(const.DATA_CHALLENGE_NAME),
                )

    async def remove_deprecated_entities(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Remove old/deprecated sensor entities from the entity registry that are no longer used."""

        ent_reg = er.async_get(hass)

        for entity_id, entity_entry in list(ent_reg.entities.items()):
            if not entity_entry.unique_id.startswith(f"{entry.entry_id}_"):
                continue
            if any(
                entity_entry.unique_id.endswith(suffix)
                for suffix in const.DEPRECATED_SUFFIXES
            ):
                ent_reg.async_remove(entity_id)
                const.LOGGER.debug(
                    "DEBUG: Removed deprecated Entity '%s', UID '%s'",
                    entity_id,
                    entity_entry.unique_id,
                )

    def remove_deprecated_button_entities(self) -> None:
        """Remove dynamic button entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Chore Buttons ---
        # For each chore, create expected unique IDs for claim, approve, and disapprove buttons
        for chore_id, chore_info in self.chores_data.items():
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                # Expected unique_id formats:
                uid_claim = f"{self.config_entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}"
                uid_approve = f"{self.config_entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
                uid_disapprove = f"{self.config_entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"
                allowed_uids.update({uid_claim, uid_approve, uid_disapprove})

        # --- Reward Buttons ---
        # For each kid and reward, add expected unique IDs for reward claim, approve, and disapprove buttons.
        for kid_id in self.kids_data:
            for reward_id in self.rewards_data:
                # The reward claim button might be built with a dedicated prefix:
                uid_claim = f"{self.config_entry.entry_id}_{const.BUTTON_REWARD_PREFIX}{kid_id}_{reward_id}"
                uid_approve = f"{self.config_entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
                uid_disapprove = f"{self.config_entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
                allowed_uids.update({uid_claim, uid_approve, uid_disapprove})

        # --- Penalty Buttons ---
        for kid_id in self.kids_data:
            for penalty_id in self.penalties_data:
                uid = f"{self.config_entry.entry_id}_{const.BUTTON_PENALTY_PREFIX}{kid_id}_{penalty_id}"
                allowed_uids.add(uid)

        # --- Bonus Buttons ---
        for kid_id in self.kids_data:
            for bonus_id in self.bonuses_data:
                uid = f"{self.config_entry.entry_id}_{const.BUTTON_BONUS_PREFIX}{kid_id}_{bonus_id}"
                allowed_uids.add(uid)

        # --- Points Adjust Buttons ---
        # Determine the list of adjustment delta values from configuration or defaults.
        raw_values = self.config_entry.options.get(const.CONF_POINTS_ADJUST_VALUES)
        if not raw_values:
            points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        elif isinstance(raw_values, str):
            points_adjust_values = kh.parse_points_adjust_values(raw_values)
            if not points_adjust_values:
                points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        elif isinstance(raw_values, list):
            try:
                points_adjust_values = [float(v) for v in raw_values]
            except (ValueError, TypeError):
                points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        else:
            points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES

        for kid_id in self.kids_data:
            for delta in points_adjust_values:
                uid = f"{self.config_entry.entry_id}_{kid_id}{const.BUTTON_KC_UID_MIDFIX_ADJUST_POINTS}{delta}"
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
        ent_reg = er.async_get(self.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Chore Status Sensors ---
        # For each chore, create expected unique IDs for chore status sensors
        for chore_id, chore_info in self.chores_data.items():
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                uid = f"{self.config_entry.entry_id}_{kid_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
                allowed_uids.add(uid)

        # --- Shared Chore Global State Sensors ---
        for chore_id, chore_info in self.chores_data.items():
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED
            ):
                uid = f"{self.config_entry.entry_id}_{chore_id}{const.DATA_GLOBAL_STATE_SUFFIX}"
                allowed_uids.add(uid)

        # --- Reward Status Sensors ---
        for reward_id in self.rewards_data:
            for kid_id in self.kids_data:
                uid = f"{self.config_entry.entry_id}_{kid_id}_{reward_id}{const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}"
                allowed_uids.add(uid)

        # --- Penalty/Bonus Apply Sensors ---
        for kid_id in self.kids_data:
            for penalty_id in self.penalties_data:
                uid = f"{self.config_entry.entry_id}_{kid_id}_{penalty_id}{const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR}"
                allowed_uids.add(uid)
            for bonus_id in self.bonuses_data:
                uid = f"{self.config_entry.entry_id}_{kid_id}_{bonus_id}{const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR}"
                allowed_uids.add(uid)

        # --- Achievement Progress Sensors ---
        for achievement_id, achievement in self.achievements_data.items():
            for kid_id in achievement.get(const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, []):
                uid = f"{self.config_entry.entry_id}_{kid_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}"
                allowed_uids.add(uid)

        # --- Challenge Progress Sensors ---
        for challenge_id, challenge in self.challenges_data.items():
            for kid_id in challenge.get(const.DATA_CHALLENGE_ASSIGNED_KIDS, []):
                uid = f"{self.config_entry.entry_id}_{kid_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}"
                allowed_uids.add(uid)

        # --- Kid-specific sensors (not dynamic based on chores/rewards) ---
        # These are created once per kid and don't need validation against dynamic data
        for kid_id in self.kids_data:
            # Standard kid sensors
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_BADGES_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_MAX_POINTS_EVER_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_HIGHEST_STREAK_SENSOR}"
            )
            allowed_uids.add(
                f"{self.config_entry.entry_id}_{kid_id}_ui_dashboard_helper"
            )  # Hardcoded in sensor.py

            # Badge progress sensors
            badge_progress_data = self.kids_data[kid_id].get(
                const.DATA_KID_BADGE_PROGRESS, {}
            )
            for badge_id, progress_info in badge_progress_data.items():
                badge_type = progress_info.get(const.DATA_KID_BADGE_PROGRESS_TYPE)
                if badge_type != const.BADGE_TYPE_CUMULATIVE:
                    uid = f"{self.config_entry.entry_id}_{kid_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}"
                    allowed_uids.add(uid)

        # --- Global sensors (not kid-specific) ---
        allowed_uids.add(
            f"{self.config_entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}"
        )
        allowed_uids.add(
            f"{self.config_entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}"
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

    # -------------------------------------------------------------------------------------
    # Create/Update Entities
    # (Kids, Parents, Chores, Badges, Rewards, Penalties, Bonus, Achievements and Challenges)
    # -------------------------------------------------------------------------------------

    # -- Kids
    def _create_kid(self, kid_id: str, kid_data: dict[str, Any]):
        self._data[const.DATA_KIDS][kid_id] = {
            const.DATA_KID_NAME: kid_data.get(
                const.DATA_KID_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_KID_POINTS: kid_data.get(
                const.DATA_KID_POINTS, const.DEFAULT_ZERO
            ),
            const.DATA_KID_BADGES_EARNED: kid_data.get(
                const.DATA_KID_BADGES_EARNED, {}
            ),
            # Note: claimed_chores and approved_chores lists removed in v0.4.0
            # Now using timestamp-based tracking (last_approved, approval_period_start)
            # Chore tracking now uses timestamps in kid_chore_data
            # Deprecated completed_chores counters removed - using chore_stats only
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
            # Modern reward tracking (v0.5.0+) - timestamp-based with multi-claim support
            # Legacy fields (pending_rewards, redeemed_rewards, reward_claims, reward_approvals)
            # have been removed - all reward tracking now uses reward_data structure
            const.DATA_KID_REWARD_DATA: kid_data.get(const.DATA_KID_REWARD_DATA, {}),
            # NOTE: max_points_ever is removed - use point_stats.highest_balance instead
            const.DATA_KID_ENABLE_NOTIFICATIONS: kid_data.get(
                const.DATA_KID_ENABLE_NOTIFICATIONS, True
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

        self._normalize_kid_reward_data(self._data[const.DATA_KIDS][kid_id])

        const.LOGGER.debug(
            "DEBUG: Kid Added - '%s', ID '%s'",
            self._data[const.DATA_KIDS][kid_id][const.DATA_KID_NAME],
            kid_id,
        )

    def _update_kid(self, kid_id: str, kid_data: dict[str, Any]):
        """Update an existing kid entity, only updating fields present in kid_data."""

        kids = self._data.setdefault(const.DATA_KIDS, {})
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

    # -- Parents
    def _create_parent(self, parent_id: str, parent_data: dict[str, Any]):
        associated_kids_ids = []
        for kid_id in parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            if kid_id in self.kids_data:
                associated_kids_ids.append(kid_id)
            else:
                const.LOGGER.warning(
                    "WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent",
                    parent_data.get(const.DATA_PARENT_NAME, parent_id),
                    kid_id,
                )

        self._data[const.DATA_PARENTS][parent_id] = {
            const.DATA_PARENT_NAME: parent_data.get(
                const.DATA_PARENT_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_PARENT_HA_USER_ID: parent_data.get(
                const.DATA_PARENT_HA_USER_ID, const.SENTINEL_EMPTY
            ),
            const.DATA_PARENT_ASSOCIATED_KIDS: associated_kids_ids,
            const.DATA_PARENT_ENABLE_NOTIFICATIONS: parent_data.get(
                const.DATA_PARENT_ENABLE_NOTIFICATIONS, True
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
            self._data[const.DATA_PARENTS][parent_id][const.DATA_PARENT_NAME],
            parent_id,
        )

    def _update_parent(self, parent_id: str, parent_data: dict[str, Any]):
        parent_info = self._data[const.DATA_PARENTS][parent_id]
        parent_info[const.DATA_PARENT_NAME] = parent_data.get(
            const.DATA_PARENT_NAME, parent_info[const.DATA_PARENT_NAME]
        )
        parent_info[const.DATA_PARENT_HA_USER_ID] = parent_data.get(
            const.DATA_PARENT_HA_USER_ID, parent_info[const.DATA_PARENT_HA_USER_ID]
        )

        # Update associated_kids
        updated_kids = []
        for kid_id in parent_data.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            if kid_id in self.kids_data:
                updated_kids.append(kid_id)
            else:
                const.LOGGER.warning(
                    "WARNING: Parent '%s': Kid ID '%s' not found. Skipping assignment to parent",
                    parent_info[const.DATA_PARENT_NAME],
                    kid_id,
                )
        parent_info[const.DATA_PARENT_ASSOCIATED_KIDS] = updated_kids
        parent_info[const.DATA_PARENT_ENABLE_NOTIFICATIONS] = parent_data.get(
            const.DATA_PARENT_ENABLE_NOTIFICATIONS,
            parent_info.get(const.DATA_PARENT_ENABLE_NOTIFICATIONS, True),
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

    def _create_shadow_kid_for_parent(
        self, parent_id: str, parent_info: dict[str, Any]
    ) -> str:
        """Create a shadow kid entity for a parent who enables chore assignment.

        Shadow kids are special kid entities that:
        - Use the parent's name and dashboard language
        - Are marked with is_shadow_kid=True
        - Link back to the parent via linked_parent_id
        - Have notifications disabled by default (editable via Manage Kids)
        - Inherit gamification setting from parent

        Uses shared build_shadow_kid_data() from flow_helpers for consistency
        between config flow and options flow shadow kid creation.

        Args:
            parent_id: The internal ID of the parent.
            parent_info: The parent's data dictionary.

        Returns:
            The internal_id of the newly created shadow kid.
        """
        # Use shared function for consistent shadow kid data structure
        shadow_kid_id, shadow_kid_data = fh.build_shadow_kid_data(
            parent_id, parent_info
        )

        # Use existing _create_kid to set up all standard kid fields
        self._create_kid(shadow_kid_id, shadow_kid_data)

        # Add shadow kid markers (after _create_kid, which doesn't know about them)
        self._data[const.DATA_KIDS][shadow_kid_id][const.DATA_KID_IS_SHADOW] = True
        self._data[const.DATA_KIDS][shadow_kid_id][const.DATA_KID_LINKED_PARENT_ID] = (
            parent_id
        )

        const.LOGGER.info(
            "Created shadow kid '%s' (ID: %s) for parent '%s' (ID: %s)",
            parent_info.get(const.DATA_PARENT_NAME),
            shadow_kid_id,
            parent_info.get(const.DATA_PARENT_NAME),
            parent_id,
        )

        return shadow_kid_id

    def _unlink_shadow_kid(self, shadow_kid_id: str) -> None:
        """Unlink a shadow kid from parent, converting to regular kid.

        This preserves all kid data (points, history, badges, etc.) while
        removing the shadow link. The kid is renamed with '_unlinked' suffix
        to prevent name conflicts with the parent.

        Used when:
        - Parent unchecks "Allow Chores" in options flow
        - Service call to unlink shadow kid

        Args:
            shadow_kid_id: The internal ID of the shadow kid to unlink.

        Raises:
            ServiceValidationError: If kid not found or not a shadow kid.
        """
        if shadow_kid_id not in self._data[const.DATA_KIDS]:
            const.LOGGER.warning(
                "Attempted to unlink non-existent shadow kid: %s", shadow_kid_id
            )
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": shadow_kid_id,
                },
            )

        kid_info = self._data[const.DATA_KIDS][shadow_kid_id]
        kid_name = kid_info.get(const.DATA_KID_NAME, shadow_kid_id)

        # Verify this is actually a shadow kid
        if not kid_info.get(const.DATA_KID_IS_SHADOW, False):
            const.LOGGER.error("Attempted to unlink non-shadow kid '%s'", kid_name)
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_KID_NOT_SHADOW,
                translation_placeholders={"name": kid_name},
            )

        # Get linked parent to clear their reference
        parent_id = kid_info.get(const.DATA_KID_LINKED_PARENT_ID)
        if parent_id and parent_id in self._data.get(const.DATA_PARENTS, {}):
            # Clear parent's link to this shadow kid
            self._data[const.DATA_PARENTS][parent_id][
                const.DATA_PARENT_LINKED_SHADOW_KID_ID
            ] = None
            const.LOGGER.debug(
                "Cleared parent '%s' link to shadow kid '%s'",
                self._data[const.DATA_PARENTS][parent_id].get(
                    const.DATA_PARENT_NAME, parent_id
                ),
                kid_name,
            )

        # Rename kid with _unlinked suffix to prevent conflicts
        new_name = f"{kid_name}_unlinked"

        # Remove shadow kid markers (convert to regular kid)
        kid_info[const.DATA_KID_IS_SHADOW] = False
        kid_info[const.DATA_KID_LINKED_PARENT_ID] = None
        kid_info[const.DATA_KID_NAME] = new_name

        # Update device registry to reflect new name immediately
        self._update_kid_device_name(shadow_kid_id, new_name)

        const.LOGGER.info(
            "Unlinked shadow kid '%s' → '%s' (ID: %s), preserved all data",
            kid_name,
            new_name,
            shadow_kid_id,
        )

    # -- Chores
    def _create_chore(self, chore_id: str, chore_data: dict[str, Any]):
        # Use shared helper to build complete chore structure with all defaults
        # This ensures config flow and coordinator use identical field initialization
        self._data[const.DATA_CHORES][chore_id] = kh.build_default_chore_data(
            chore_id, chore_data
        )
        const.LOGGER.debug(
            "DEBUG: Chore Added - '%s', ID '%s'",
            self._data[const.DATA_CHORES][chore_id][const.DATA_CHORE_NAME],
            chore_id,
        )

        # Notify Kids of new chore
        chore_info = self._data[const.DATA_CHORES][chore_id]
        new_name = chore_info[const.DATA_CHORE_NAME]
        due_date = chore_info[const.DATA_CHORE_DUE_DATE]
        assigned_kids_ids = chore_info[const.DATA_CHORE_ASSIGNED_KIDS]
        for kid_id in assigned_kids_ids:
            due_str = due_date if due_date else const.TRANS_KEY_NO_DUE_DATE
            extra_data = {const.DATA_KID_ID: kid_id, const.DATA_CHORE_ID: chore_id}
            self.hass.async_create_task(
                self._notify_kid_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_ASSIGNED,
                    message_data={"chore_name": new_name, "due_date": due_str},
                    extra_data=extra_data,
                )
            )

    def _update_chore(self, chore_id: str, chore_data: dict[str, Any]) -> bool:
        """Update chore data. Returns True if assigned kids changed (requiring reload)."""
        chore_info = self._data[const.DATA_CHORES][chore_id]
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
        assigned_kids_ids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        old_assigned = set(chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []))
        new_assigned = set(assigned_kids_ids)

        # Check if kids were ADDED (reload needed to create new entities)
        # Removed kids don't need reload - we just remove their entities
        added_kids = new_assigned - old_assigned
        assignments_changed = len(added_kids) > 0

        removed_kids = old_assigned - new_assigned
        for kid in removed_kids:
            self._remove_kid_chore_entities(kid, chore_id)
            self._cleanup_chore_from_kid(kid, chore_id)

        # Update the chore's assigned kids list with the new assignments
        chore_info[const.DATA_CHORE_ASSIGNED_KIDS] = list(new_assigned)
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

        # Detect criteria change and convert data accordingly
        if new_criteria != old_criteria:
            const.LOGGER.info(
                "INFO: Chore '%s' completion criteria changed: %s → %s",
                chore_info[const.DATA_CHORE_NAME],
                old_criteria,
                new_criteria,
            )
            if (
                old_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
                and new_criteria == const.COMPLETION_CRITERIA_SHARED
            ):
                # INDEPENDENT → SHARED: Remove per_kid_due_dates
                self._convert_independent_to_shared(chore_id, chore_info, chore_data)
            elif (
                old_criteria == const.COMPLETION_CRITERIA_SHARED
                and new_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                # SHARED → INDEPENDENT: Populate per_kid_due_dates from template
                self._convert_shared_to_independent(chore_id, chore_info, chore_data)

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

        self.hass.async_create_task(self._check_overdue_chores())
        return assignments_changed

    def _convert_independent_to_shared(
        self,
        chore_id: str,
        chore_info: dict[str, Any],
        chore_data: dict[str, Any],
    ) -> None:
        """Convert chore from INDEPENDENT to SHARED mode.

        Component 8: Handles data transformation when user changes completion_criteria.

        Scenario A (INDEPENDENT → SHARED):
        - Remove per_kid_due_dates (no longer needed)
        - Keep chore-level due_date as the single source of truth
        - The chore-level due_date already exists (template), no change needed

        PKAD-2026-001 Q4: Use first kid's applicable_days for chore-level
        """
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
        const.LOGGER.debug(
            "DEBUG: Converting chore '%s' from INDEPENDENT to SHARED mode",
            chore_name,
        )

        # PKAD-2026-001: Preserve first kid's applicable_days as chore-level
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        per_kid_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        if assigned_kids and assigned_kids[0] in per_kid_days:
            chore_info[const.DATA_CHORE_APPLICABLE_DAYS] = per_kid_days[
                assigned_kids[0]
            ]
            chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = per_kid_days[
                assigned_kids[0]
            ]

        # PKAD-2026-001: Preserve first kid's daily_multi_times as chore-level
        per_kid_times = chore_info.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
        if assigned_kids and assigned_kids[0] in per_kid_times:
            chore_info[const.DATA_CHORE_DAILY_MULTI_TIMES] = per_kid_times[
                assigned_kids[0]
            ]
            chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = per_kid_times[
                assigned_kids[0]
            ]

        # Clear per_kid_due_dates - no longer needed in SHARED mode
        if const.DATA_CHORE_PER_KID_DUE_DATES in chore_info:
            del chore_info[const.DATA_CHORE_PER_KID_DUE_DATES]

        # Also remove from incoming chore_data if present (prevent re-adding)
        if const.DATA_CHORE_PER_KID_DUE_DATES in chore_data:
            del chore_data[const.DATA_CHORE_PER_KID_DUE_DATES]

        # PKAD-2026-001: Clear per_kid_applicable_days - no longer needed
        if const.DATA_CHORE_PER_KID_APPLICABLE_DAYS in chore_info:
            del chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS]
        if const.DATA_CHORE_PER_KID_APPLICABLE_DAYS in chore_data:
            del chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS]

        # PKAD-2026-001: Clear per_kid_daily_multi_times - no longer needed
        if const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES in chore_info:
            del chore_info[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES]
        if const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES in chore_data:
            del chore_data[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES]

        const.LOGGER.debug(
            "DEBUG: Chore '%s' converted to SHARED - per_kid data removed",
            chore_name,
        )

    def _convert_shared_to_independent(
        self,
        chore_id: str,
        chore_info: dict[str, Any],
        chore_data: dict[str, Any],
    ) -> None:
        """Convert chore from SHARED to INDEPENDENT mode.

        Component 8: Handles data transformation when user changes completion_criteria.

        Scenario B (SHARED → INDEPENDENT):
        - Populate per_kid_due_dates from the chore-level template due_date
        - Each assigned kid gets the same initial due date (from template)
        - Future rescheduling will handle per-kid due dates independently

        PKAD-2026-001: Also populate per_kid_applicable_days and per_kid_daily_multi_times
        from chore-level values, then clear chore-level fields.
        """
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
        const.LOGGER.debug(
            "DEBUG: Converting chore '%s' from SHARED to INDEPENDENT mode",
            chore_name,
        )

        # Get template due_date from chore_data (new value) or chore_info (existing)
        template_due_date = chore_data.get(
            const.DATA_CHORE_DUE_DATE,
            chore_info.get(const.DATA_CHORE_DUE_DATE),
        )

        # Get assigned kids from chore_data (new) or chore_info (existing)
        assigned_kids = chore_data.get(
            const.DATA_CHORE_ASSIGNED_KIDS,
            chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []),
        )

        # Build per_kid_due_dates with template for all assigned kids
        per_kid_due_dates: dict[str, str | None] = {}
        for kid_id in assigned_kids:
            per_kid_due_dates[kid_id] = template_due_date

        # Set per_kid_due_dates on chore_info
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

        # Also update chore_data so the later update loop doesn't overwrite
        chore_data[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

        # PKAD-2026-001: Populate per_kid_applicable_days from chore-level
        template_applicable_days = chore_data.get(
            const.DATA_CHORE_APPLICABLE_DAYS,
            chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []),
        )
        if template_applicable_days:
            per_kid_applicable_days: dict[str, list[int]] = {}
            for kid_id in assigned_kids:
                # Ensure we store as list of integers
                if template_applicable_days and isinstance(
                    next(iter(template_applicable_days), None), str
                ):
                    order = list(const.WEEKDAY_OPTIONS.keys())
                    per_kid_applicable_days[kid_id] = [
                        order.index(d.lower())
                        for d in template_applicable_days
                        if d.lower() in order
                    ]
                else:
                    per_kid_applicable_days[kid_id] = list(template_applicable_days)
            chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = (
                per_kid_applicable_days
            )
            chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = (
                per_kid_applicable_days
            )
            # Clear chore-level (per-kid is now source of truth)
            chore_info[const.DATA_CHORE_APPLICABLE_DAYS] = None
            chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None

        # PKAD-2026-001: Populate per_kid_daily_multi_times from chore-level
        template_daily_times = chore_data.get(
            const.DATA_CHORE_DAILY_MULTI_TIMES,
            chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, ""),
        )
        if template_daily_times:
            per_kid_daily_times: dict[str, str] = {}
            for kid_id in assigned_kids:
                per_kid_daily_times[kid_id] = template_daily_times
            chore_info[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = per_kid_daily_times
            chore_data[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = per_kid_daily_times
            # Clear chore-level (per-kid is now source of truth)
            chore_info[const.DATA_CHORE_DAILY_MULTI_TIMES] = None
            chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

        const.LOGGER.debug(
            "DEBUG: Chore '%s' converted to INDEPENDENT - per_kid data "
            "populated from template for %d kids",
            chore_name,
            len(assigned_kids),
        )

    # -- Badges
    def _create_badge(self, badge_id: str, badge_data: dict[str, Any]):
        """Create a new badge entity."""

        # --- Simplified Logic ---
        # Directly assign badge_data to badge_info.
        # This assumes badge_data is already validated and contains all necessary fields.
        self._data.setdefault(const.DATA_BADGES, {})[badge_id] = badge_data

        badge_info = self._data[const.DATA_BADGES][badge_id]
        badge_name = badge_info.get(const.DATA_BADGE_NAME, const.SENTINEL_EMPTY)

        const.LOGGER.debug(
            "DEBUG: Badge Updated - '%s', ID '%s'",
            badge_name,
            badge_id,
        )

    def _update_badge(self, badge_id: str, badge_data: dict[str, Any]):
        """Update an existing badge entity, only updating fields present in badge_data."""

        badges = self._data.setdefault(const.DATA_BADGES, {})
        existing = badges.get(badge_id, {})
        # Only update fields present in badge_data, preserving all others
        existing.update(badge_data)
        badges[badge_id] = existing

        badge_name = existing.get(const.DATA_BADGE_NAME, const.SENTINEL_EMPTY)
        const.LOGGER.debug(
            "DEBUG: Badge Updated - '%s', ID '%s'",
            badge_name,
            badge_id,
        )

    # -- Rewards
    def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
        self._data[const.DATA_REWARDS][reward_id] = {
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
                const.DATA_REWARD_ICON, const.DEFAULT_REWARD_ICON
            ),
            const.DATA_REWARD_INTERNAL_ID: reward_id,
        }
        const.LOGGER.debug(
            "DEBUG: Reward Added - '%s', ID '%s'",
            self._data[const.DATA_REWARDS][reward_id][const.DATA_REWARD_NAME],
            reward_id,
        )

    def _update_reward(self, reward_id: str, reward_data: dict[str, Any]):
        reward_info = self._data[const.DATA_REWARDS][reward_id]

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

    # -- Bonuses
    def _create_bonus(self, bonus_id: str, bonus_data: dict[str, Any]):
        self._data[const.DATA_BONUSES][bonus_id] = {
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
                const.DATA_BONUS_ICON, const.DEFAULT_BONUS_ICON
            ),
            const.DATA_BONUS_INTERNAL_ID: bonus_id,
        }
        const.LOGGER.debug(
            "DEBUG: Bonus Added - '%s', ID '%s'",
            self._data[const.DATA_BONUSES][bonus_id][const.DATA_BONUS_NAME],
            bonus_id,
        )

    def _update_bonus(self, bonus_id: str, bonus_data: dict[str, Any]):
        bonus_info = self._data[const.DATA_BONUSES][bonus_id]
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

    # -- Penalties
    def _create_penalty(self, penalty_id: str, penalty_data: dict[str, Any]):
        self._data[const.DATA_PENALTIES][penalty_id] = {
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
                const.DATA_PENALTY_ICON, const.DEFAULT_PENALTY_ICON
            ),
            const.DATA_PENALTY_INTERNAL_ID: penalty_id,
        }
        const.LOGGER.debug(
            "DEBUG: Penalty Added - '%s', ID '%s'",
            self._data[const.DATA_PENALTIES][penalty_id][const.DATA_PENALTY_NAME],
            penalty_id,
        )

    def _update_penalty(self, penalty_id: str, penalty_data: dict[str, Any]):
        penalty_info = self._data[const.DATA_PENALTIES][penalty_id]
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

    # -- Achievements
    def _create_achievement(
        self, achievement_id: str, achievement_data: dict[str, Any]
    ):
        self._data[const.DATA_ACHIEVEMENTS][achievement_id] = {
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
            self._data[const.DATA_ACHIEVEMENTS][achievement_id][
                const.DATA_ACHIEVEMENT_NAME
            ],
            achievement_id,
        )

    def _update_achievement(
        self, achievement_id: str, achievement_data: dict[str, Any]
    ):
        achievement_info = self._data[const.DATA_ACHIEVEMENTS][achievement_id]
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

    # -- Challenges
    def _create_challenge(self, challenge_id: str, challenge_data: dict[str, Any]):
        self._data[const.DATA_CHALLENGES][challenge_id] = {
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
            self._data[const.DATA_CHALLENGES][challenge_id][const.DATA_CHALLENGE_NAME],
            challenge_id,
        )

    def _update_challenge(self, challenge_id: str, challenge_data: dict[str, Any]):
        challenge_info = self._data[const.DATA_CHALLENGES][challenge_id]
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

    # -------------------------------------------------------------------------------------
    # Public Entity Management Methods (for Options Flow - Phase 3)
    # These methods provide direct storage updates without triggering config reloads
    # -------------------------------------------------------------------------------------

    def _update_kid_device_name(self, kid_id: str, kid_name: str) -> None:
        """Update kid device name in device registry.

        When a kid's name changes, this function updates the corresponding
        device registry entry so the device name reflects immediately without
        requiring a reboot. This also cascades to entity friendly names.

        Args:
            kid_id: Internal UUID of the kid
            kid_name: New name for the kid

        """
        from homeassistant.helpers import device_registry as dr

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(identifiers={(const.DOMAIN, kid_id)})

        if device:
            new_device_name = f"{kid_name} ({self.config_entry.title})"
            device_registry.async_update_device(device.id, name=new_device_name)
            const.LOGGER.debug(
                "Updated device name for kid '%s' (ID: %s) to '%s'",
                kid_name,
                kid_id,
                new_device_name,
            )
        else:
            const.LOGGER.warning(
                "Device not found for kid '%s' (ID: %s), cannot update name",
                kid_name,
                kid_id,
            )

    def update_kid_entity(self, kid_id: str, kid_data: dict[str, Any]) -> None:
        """Update kid entity in storage (Options Flow - no reload).

        Args:
            kid_id: Internal ID of the kid
            kid_data: Dictionary with kid fields to update
        """
        if kid_id not in self._data.get(const.DATA_KIDS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Check if name is changing
        old_name = self._data[const.DATA_KIDS][kid_id].get(const.DATA_KID_NAME)
        new_name = kid_data.get(const.DATA_KID_NAME)

        self._update_kid(kid_id, kid_data)
        self._persist()

        # Update device registry if name changed
        if new_name and new_name != old_name:
            self._update_kid_device_name(kid_id, new_name)

        self.async_update_listeners()

    def delete_kid_entity(self, kid_id: str) -> None:
        """Delete kid from storage and cleanup references.

        For shadow kids (parent-linked profiles), this disables the parent's
        chore assignment flag and uses the existing shadow kid cleanup flow.

        Args:
            kid_id: Internal ID of the kid to delete
        """
        if kid_id not in self._data.get(const.DATA_KIDS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        kid_info = self._data[const.DATA_KIDS][kid_id]
        kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)

        # Shadow kid handling: disable parent flag and use existing cleanup
        if kid_info.get(const.DATA_KID_IS_SHADOW, False):
            parent_id = kid_info.get(const.DATA_KID_LINKED_PARENT_ID)
            if parent_id and parent_id in self._data.get(const.DATA_PARENTS, {}):
                # Disable chore assignment on parent and clear link
                self._data[const.DATA_PARENTS][parent_id][
                    const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT
                ] = False
                self._data[const.DATA_PARENTS][parent_id][
                    const.DATA_PARENT_LINKED_SHADOW_KID_ID
                ] = None
            # Unlink shadow kid (preserves kid + entities)
            self._unlink_shadow_kid(kid_id)
            # Cleanup unused translation sensors (if language no longer needed)
            self.cleanup_unused_translation_sensors()
            self._persist()
            self.async_update_listeners()
            const.LOGGER.info(
                "INFO: Deleted shadow kid '%s' (ID: %s) via parent flag disable",
                kid_name,
                kid_id,
            )
            return  # Done - don't continue to normal kid deletion

        # Normal kid deletion continues below
        del self._data[const.DATA_KIDS][kid_id]

        # Remove HA entities
        self._remove_entities_in_ha(kid_id)

        # Cleanup references
        self._cleanup_deleted_kid_references()
        self._cleanup_parent_assignments()
        self._cleanup_pending_reward_approvals()

        # Cleanup unused translation sensors (if language no longer needed)
        self.cleanup_unused_translation_sensors()

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted kid '%s' (ID: %s)", kid_name, kid_id)

    def update_parent_entity(self, parent_id: str, parent_data: dict[str, Any]) -> None:
        """Update parent entity in storage (Options Flow - no reload)."""
        if parent_id not in self._data.get(const.DATA_PARENTS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PARENT,
                    "name": parent_id,
                },
            )
        self._update_parent(parent_id, parent_data)
        self._persist()
        self.async_update_listeners()

    def delete_parent_entity(self, parent_id: str) -> None:
        """Delete parent from storage.

        Cascades deletion to any linked shadow kid before removing the parent.
        """
        if parent_id not in self._data.get(const.DATA_PARENTS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PARENT,
                    "name": parent_id,
                },
            )

        parent_data = self._data[const.DATA_PARENTS][parent_id]
        parent_name = parent_data.get(const.DATA_PARENT_NAME, parent_id)

        # Cascade unlink shadow kid if exists (preserves data)
        shadow_kid_id = parent_data.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID)
        if shadow_kid_id:
            self._unlink_shadow_kid(shadow_kid_id)
            const.LOGGER.info(
                "INFO: Cascade unlinked shadow kid for parent '%s'", parent_name
            )

        del self._data[const.DATA_PARENTS][parent_id]

        # Cleanup unused translation sensors (if language no longer needed)
        self.cleanup_unused_translation_sensors()

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted parent '%s' (ID: %s)", parent_name, parent_id)

    def update_chore_entity(self, chore_id: str, chore_data: dict[str, Any]) -> bool:
        """Update chore entity in storage (Options Flow).

        Returns True if assigned kids changed (indicating reload is needed).
        """
        if chore_id not in self._data.get(const.DATA_CHORES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )
        assignments_changed = self._update_chore(chore_id, chore_data)
        # Recalculate badges affected by chore changes
        self._recalculate_all_badges()
        self._persist()
        self.async_update_listeners()
        # Clean up any orphaned kid-chore entities after assignment changes
        self.hass.async_create_task(self._remove_orphaned_kid_chore_entities())
        return assignments_changed

    def delete_chore_entity(self, chore_id: str) -> None:
        """Delete chore from storage and cleanup references."""
        if chore_id not in self._data.get(const.DATA_CHORES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        chore_name = self._data[const.DATA_CHORES][chore_id].get(
            const.DATA_CHORE_NAME, chore_id
        )
        del self._data[const.DATA_CHORES][chore_id]

        # Remove HA entities
        self._remove_entities_in_ha(chore_id)

        # Cleanup references
        self._cleanup_deleted_chore_references()
        self._cleanup_deleted_chore_in_achievements()
        self._cleanup_deleted_chore_in_challenges()

        # Remove orphaned shared chore sensors
        self.hass.async_create_task(self._remove_orphaned_shared_chore_sensors())

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted chore '%s' (ID: %s)", chore_name, chore_id)

    def update_badge_entity(self, badge_id: str, badge_data: dict[str, Any]) -> None:
        """Update badge entity in storage (Options Flow - no reload)."""
        if badge_id not in self._data.get(const.DATA_BADGES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BADGE,
                    "name": badge_id,
                },
            )
        self._update_badge(badge_id, badge_data)
        # Phase 4: Sync badge_progress after badge update (handles assignment changes)
        for kid_id in self.kids_data:
            self._sync_badge_progress_for_kid(kid_id)
        # Recalculate badge progress for all kids
        self._recalculate_all_badges()
        self._persist()
        self.async_update_listeners()

    def delete_badge_entity(self, badge_id: str) -> None:
        """Delete badge from storage and cleanup references."""
        if badge_id not in self._data.get(const.DATA_BADGES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BADGE,
                    "name": badge_id,
                },
            )

        badge_name = self._data[const.DATA_BADGES][badge_id].get(
            const.DATA_BADGE_NAME, badge_id
        )
        del self._data[const.DATA_BADGES][badge_id]

        # Remove awarded badges from kids
        self._remove_awarded_badges_by_id(badge_id=badge_id)

        # Phase 4: Clean up badge_progress from all kids after badge deletion
        # Also recalculate cumulative badge progress since a cumulative badge may have been deleted
        for kid_id in self.kids_data:
            self._sync_badge_progress_for_kid(kid_id)
            # Refresh cumulative badge progress (handles case when cumulative badge is deleted)
            cumulative_progress = self._get_cumulative_badge_progress(kid_id)
            self.kids_data[kid_id][const.DATA_KID_CUMULATIVE_BADGE_PROGRESS] = cast(
                "KidCumulativeBadgeProgress", cumulative_progress
            )

        # Remove badge-related entities from Home Assistant registry
        self._remove_entities_in_ha(badge_id)

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted badge '%s' (ID: %s)", badge_name, badge_id)

    def update_reward_entity(self, reward_id: str, reward_data: dict[str, Any]) -> None:
        """Update reward entity in storage (Options Flow - no reload)."""
        if reward_id not in self._data.get(const.DATA_REWARDS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )
        self._update_reward(reward_id, reward_data)
        self._persist()
        self.async_update_listeners()

    def delete_reward_entity(self, reward_id: str) -> None:
        """Delete reward from storage and cleanup references."""
        if reward_id not in self._data.get(const.DATA_REWARDS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        reward_name = self._data[const.DATA_REWARDS][reward_id].get(
            const.DATA_REWARD_NAME, reward_id
        )
        del self._data[const.DATA_REWARDS][reward_id]

        # Remove HA entities
        self._remove_entities_in_ha(reward_id)

        # Cleanup pending reward approvals
        self._cleanup_pending_reward_approvals()

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted reward '%s' (ID: %s)", reward_name, reward_id)

    def update_penalty_entity(
        self, penalty_id: str, penalty_data: dict[str, Any]
    ) -> None:
        """Update penalty entity in storage (Options Flow - no reload)."""
        if penalty_id not in self._data.get(const.DATA_PENALTIES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PENALTY,
                    "name": penalty_id,
                },
            )
        self._update_penalty(penalty_id, penalty_data)
        self._persist()
        self.async_update_listeners()

    def delete_penalty_entity(self, penalty_id: str) -> None:
        """Delete penalty from storage."""
        if penalty_id not in self._data.get(const.DATA_PENALTIES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PENALTY,
                    "name": penalty_id,
                },
            )

        penalty_name = self._data[const.DATA_PENALTIES][penalty_id].get(
            const.DATA_PENALTY_NAME, penalty_id
        )
        del self._data[const.DATA_PENALTIES][penalty_id]

        # Remove HA entities
        self._remove_entities_in_ha(penalty_id)

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info(
            "INFO: Deleted penalty '%s' (ID: %s)", penalty_name, penalty_id
        )

    def update_bonus_entity(self, bonus_id: str, bonus_data: dict[str, Any]) -> None:
        """Update bonus entity in storage (Options Flow - no reload)."""
        if bonus_id not in self._data.get(const.DATA_BONUSES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BONUS,
                    "name": bonus_id,
                },
            )
        self._update_bonus(bonus_id, bonus_data)
        self._persist()
        self.async_update_listeners()

    def delete_bonus_entity(self, bonus_id: str) -> None:
        """Delete bonus from storage."""
        if bonus_id not in self._data.get(const.DATA_BONUSES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BONUS,
                    "name": bonus_id,
                },
            )

        bonus_name = self._data[const.DATA_BONUSES][bonus_id].get(
            const.DATA_BONUS_NAME, bonus_id
        )
        del self._data[const.DATA_BONUSES][bonus_id]

        # Remove HA entities
        self._remove_entities_in_ha(bonus_id)

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted bonus '%s' (ID: %s)", bonus_name, bonus_id)

    def update_achievement_entity(
        self, achievement_id: str, achievement_data: dict[str, Any]
    ) -> None:
        """Update achievement entity in storage (Options Flow - no reload)."""
        if achievement_id not in self._data.get(const.DATA_ACHIEVEMENTS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ACHIEVEMENT,
                    "name": achievement_id,
                },
            )
        self._update_achievement(achievement_id, achievement_data)
        self._persist()
        self.async_update_listeners()

    def delete_achievement_entity(self, achievement_id: str) -> None:
        """Delete achievement from storage and cleanup references."""
        if achievement_id not in self._data.get(const.DATA_ACHIEVEMENTS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ACHIEVEMENT,
                    "name": achievement_id,
                },
            )

        achievement_name = self._data[const.DATA_ACHIEVEMENTS][achievement_id].get(
            const.DATA_ACHIEVEMENT_NAME, achievement_id
        )
        del self._data[const.DATA_ACHIEVEMENTS][achievement_id]

        # Remove orphaned achievement entities
        self.hass.async_create_task(self._remove_orphaned_achievement_entities())

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info(
            "INFO: Deleted achievement '%s' (ID: %s)", achievement_name, achievement_id
        )

    def update_challenge_entity(
        self, challenge_id: str, challenge_data: dict[str, Any]
    ) -> None:
        """Update challenge entity in storage (Options Flow - no reload)."""
        if challenge_id not in self._data.get(const.DATA_CHALLENGES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHALLENGE,
                    "name": challenge_id,
                },
            )
        self._update_challenge(challenge_id, challenge_data)
        self._persist()
        self.async_update_listeners()

    def delete_challenge_entity(self, challenge_id: str) -> None:
        """Delete challenge from storage and cleanup references."""
        if challenge_id not in self._data.get(const.DATA_CHALLENGES, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHALLENGE,
                    "name": challenge_id,
                },
            )

        challenge_name = self._data[const.DATA_CHALLENGES][challenge_id].get(
            const.DATA_CHALLENGE_NAME, challenge_id
        )
        del self._data[const.DATA_CHALLENGES][challenge_id]

        # Remove orphaned challenge entities
        self.hass.async_create_task(self._remove_orphaned_challenge_entities())

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info(
            "INFO: Deleted challenge '%s' (ID: %s)", challenge_name, challenge_id
        )

    # -------------------------------------------------------------------------------------
    # Properties for Easy Access
    # -------------------------------------------------------------------------------------

    @property
    def kids_data(self) -> KidsCollection:
        """Return the kids data."""
        return self._data.get(const.DATA_KIDS, {})

    @property
    def parents_data(self) -> ParentsCollection:
        """Return the parents data."""
        return self._data.get(const.DATA_PARENTS, {})

    @property
    def chores_data(self) -> ChoresCollection:
        """Return the chores data."""
        return self._data.get(const.DATA_CHORES, {})

    @property
    def badges_data(self) -> BadgesCollection:
        """Return the badges data."""
        return self._data.get(const.DATA_BADGES, {})

    @property
    def rewards_data(self) -> RewardsCollection:
        """Return the rewards data."""
        return self._data.get(const.DATA_REWARDS, {})

    @property
    def penalties_data(self) -> PenaltiesCollection:
        """Return the penalties data."""
        return self._data.get(const.DATA_PENALTIES, {})

    @property
    def achievements_data(self) -> AchievementsCollection:
        """Return the achievements data."""
        return self._data.get(const.DATA_ACHIEVEMENTS, {})

    @property
    def challenges_data(self) -> ChallengesCollection:
        """Return the challenges data."""
        return self._data.get(const.DATA_CHALLENGES, {})

    @property
    def bonuses_data(self) -> BonusesCollection:
        """Return the bonuses data."""
        return self._data.get(const.DATA_BONUSES, {})

    # -------------------------------------------------------------------------
    # Chore Configuration Helpers
    # -------------------------------------------------------------------------

    def _get_effective_due_date(
        self,
        chore_id: str,
        kid_id: str | None = None,
    ) -> str | None:
        """Get the effective due date for a kid+chore combination.

        For INDEPENDENT chores: Returns per-kid due date from per_kid_due_dates
        For SHARED/SHARED_FIRST: Returns chore-level due date

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID (required for INDEPENDENT,
                    ignored for SHARED)

        Returns:
            ISO datetime string or None if no due date set
        """
        chore_info: ChoreData = cast("ChoreData", self.chores_data.get(chore_id, {}))
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and kid_id:
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            return per_kid_due_dates.get(kid_id)

        return chore_info.get(const.DATA_CHORE_DUE_DATE)

    def _allows_multiple_claims(self, chore_id: str) -> bool:
        """Check if chore allows multiple claims per approval period.

        Returns True for:
        - AT_MIDNIGHT_MULTI
        - AT_DUE_DATE_MULTI
        - UPON_COMPLETION

        Returns False for:
        - AT_MIDNIGHT_ONCE (default)
        - AT_DUE_DATE_ONCE
        """
        chore_info: ChoreData = cast("ChoreData", self.chores_data.get(chore_id, {}))
        approval_reset_type = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        return approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        )

    @property
    def pending_chore_approvals(self) -> list[dict[str, Any]]:
        """Return the list of pending chore approvals (computed from timestamps).

        Uses timestamp-based tracking instead of legacy queue. A chore is pending
        if it has been claimed but not yet approved or disapproved in the current
        approval period.
        """
        return self.get_pending_chore_approvals_computed()

    @property
    def pending_reward_approvals(self) -> list[dict[str, Any]]:
        """Return the list of pending reward approvals (computed from modern structure)."""
        return self.get_pending_reward_approvals_computed()

    @property
    def pending_chore_changed(self) -> bool:
        """Return whether pending chore approvals have changed since last reset."""
        return self._pending_chore_changed

    @property
    def pending_reward_changed(self) -> bool:
        """Return whether pending reward approvals have changed since last reset."""
        return self._pending_reward_changed

    def reset_pending_change_flags(self) -> None:
        """Reset the pending change flags after UI has processed the changes.

        Called by dashboard helper sensor after rebuilding attributes.
        """
        self._pending_chore_changed = False
        self._pending_reward_changed = False

    # -------------------------------------------------------------------------------------
    # Translation Sensor Lifecycle Management
    # -------------------------------------------------------------------------------------

    def register_translation_sensor_callback(self, async_add_entities) -> None:
        """Register the callback for dynamically adding translation sensors.

        Called by sensor.py during async_setup_entry to enable dynamic sensor creation.
        """
        self._sensor_add_entities_callback = async_add_entities

    def mark_translation_sensor_created(self, lang_code: str) -> None:
        """Mark that a translation sensor for this language has been created."""
        self._translation_sensors_created.add(lang_code)

    def is_translation_sensor_created(self, lang_code: str) -> bool:
        """Check if a translation sensor exists for the given language code."""
        return lang_code in self._translation_sensors_created

    def get_translation_sensor_eid(self, lang_code: str) -> str:
        """Get the entity ID for a translation sensor given a language code.

        Returns the entity ID whether or not the sensor exists yet.
        Format: sensor.kc_ui_dashboard_lang_{code}
        """
        return (
            f"{const.SENSOR_KC_PREFIX}"
            f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{lang_code}"
        )

    async def ensure_translation_sensor_exists(self, lang_code: str) -> str:
        """Ensure a translation sensor exists for the given language code.

        If the sensor doesn't exist, creates it dynamically using the stored
        async_add_entities callback. Returns the entity ID.

        This is called when a kid's dashboard language changes to a new language
        that doesn't have a translation sensor yet.
        """
        # Import here to avoid circular dependency
        from .sensor import SystemDashboardTranslationSensor

        eid = self.get_translation_sensor_eid(lang_code)

        # If sensor already exists, just return the entity ID
        if lang_code in self._translation_sensors_created:
            return eid

        # If no callback registered (shouldn't happen), log warning and return
        if self._sensor_add_entities_callback is None:
            const.LOGGER.warning(
                "Cannot create translation sensor for '%s': no callback registered",
                lang_code,
            )
            # Fallback to English if available, otherwise just return the expected EID
            if const.DEFAULT_DASHBOARD_LANGUAGE in self._translation_sensors_created:
                return self.get_translation_sensor_eid(const.DEFAULT_DASHBOARD_LANGUAGE)
            return eid

        # Create the new translation sensor
        const.LOGGER.info(
            "Creating translation sensor for newly-used language: %s", lang_code
        )
        new_sensor = SystemDashboardTranslationSensor(
            self, self.config_entry, lang_code
        )
        self._sensor_add_entities_callback([new_sensor])
        self._translation_sensors_created.add(lang_code)

        return eid

    def get_languages_in_use(self) -> set[str]:
        """Get all unique dashboard languages currently in use by kids and parents.

        Used to determine which translation sensors are needed.
        """
        languages: set[str] = set()
        for kid_info in self.kids_data.values():
            lang = kid_info.get(
                const.DATA_KID_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            )
            languages.add(lang)
        for parent_info in self.parents_data.values():
            lang = parent_info.get(
                const.DATA_PARENT_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            )
            languages.add(lang)
        # Always include English as fallback
        languages.add(const.DEFAULT_DASHBOARD_LANGUAGE)
        return languages

    def cleanup_unused_translation_sensors(self) -> None:
        """Remove translation sensors for languages no longer in use.

        This is an optimization to avoid keeping unused sensors in memory.
        Called when a kid/parent is deleted or their language is changed.

        Note: Entity removal is handled via entity registry; we just update tracking.
        """
        languages_in_use = self.get_languages_in_use()
        unused_languages = self._translation_sensors_created - languages_in_use

        if not unused_languages:
            return

        # Get entity registry and remove unused translation sensors
        entity_registry = er.async_get(self.hass)
        for lang_code in unused_languages:
            eid = self.get_translation_sensor_eid(lang_code)
            entity_entry = entity_registry.async_get(eid)
            if entity_entry:
                const.LOGGER.info(
                    "Removing unused translation sensor: %s (language: %s)",
                    eid,
                    lang_code,
                )
                entity_registry.async_remove(eid)
            self._translation_sensors_created.discard(lang_code)

    # -------------------------------------------------------------------------------------
    # Chores: Claim, Approve, Disapprove, Compute Global State for Shared Chores
    # -------------------------------------------------------------------------------------

    def _set_chore_claimed_completed_by(
        self, chore_id: str, kid_id: str, field_name: str, kid_name: str
    ) -> None:
        """Set claimed_by or completed_by field for a chore based on completion criteria.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid who claimed/completed the chore
            field_name: Either DATA_CHORE_CLAIMED_BY or DATA_CHORE_COMPLETED_BY
            kid_name: Display name of the kid
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            return

        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Store kid's own name in their kid_chore_data
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                return
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            if chore_id not in kid_chores_data:
                self._update_chore_data_for_kid(kid_id, chore_id, 0.0)
            kid_chores_data[chore_id][field_name] = kid_name
            const.LOGGER.debug(
                "INDEPENDENT: Set %s='%s' for kid '%s' on chore '%s'",
                field_name,
                kid_name,
                kid_name,
                chore_info.get(const.DATA_CHORE_NAME),
            )

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Store in other kids' data (not the claiming/completing kid)
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if other_kid_id == kid_id:
                    continue  # Skip the claiming/completing kid
                other_kid_info: KidData = cast(
                    "KidData", self.kids_data.get(other_kid_id, {})
                )
                self._update_chore_data_for_kid(other_kid_id, chore_id, 0.0)
                chore_data = other_kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
                chore_entry = chore_data[chore_id]
                chore_entry[field_name] = kid_name
                const.LOGGER.debug(
                    "SHARED_FIRST: Set %s='%s' in kid '%s' data for chore '%s'",
                    field_name,
                    kid_name,
                    other_kid_info.get(const.DATA_KID_NAME),
                    chore_info.get(const.DATA_CHORE_NAME),
                )

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            # SHARED_ALL: Append to list in all kids' data
            for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                assigned_kid_info: KidData = cast(
                    "KidData", self.kids_data.get(assigned_kid_id, {})
                )
                assigned_kid_chore_data = assigned_kid_info.setdefault(
                    const.DATA_KID_CHORE_DATA, {}
                )
                if chore_id not in assigned_kid_chore_data:
                    self._update_chore_data_for_kid(assigned_kid_id, chore_id, 0.0)
                chore_entry = assigned_kid_chore_data[chore_id]

                # Initialize as list if not present or if it's not a list
                if field_name not in chore_entry or not isinstance(
                    chore_entry[field_name], list
                ):
                    chore_entry[field_name] = []

                # Append kid's name if not already in list
                if kid_name not in chore_entry[field_name]:
                    chore_entry[field_name].append(kid_name)

            const.LOGGER.debug(
                "SHARED_ALL: Added '%s' to %s list for chore '%s'",
                kid_name,
                field_name,
                chore_info.get(const.DATA_CHORE_NAME),
            )

    def _clear_chore_claimed_completed_by(
        self, chore_id: str, kid_ids: list[str] | None = None
    ) -> None:
        """Clear claimed_by and completed_by fields for specified kids.

        Args:
            chore_id: The chore's internal ID
            kid_ids: List of kid IDs to clear fields for. If None, clears for all assigned kids.
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            return

        # If no specific kids provided, clear for all assigned kids
        kids_to_clear = (
            kid_ids
            if kid_ids is not None
            else chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        )

        for kid_id in kids_to_clear:
            kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
            chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            if chore_id in chore_data:
                chore_data[chore_id].pop(const.DATA_CHORE_CLAIMED_BY, None)
                chore_data[chore_id].pop(const.DATA_CHORE_COMPLETED_BY, None)

    def claim_chore(self, kid_id: str, chore_id: str, user_name: str):
        """Kid claims chore => state=claimed; parent must then approve."""
        perf_start = time.perf_counter()
        if chore_id not in self.chores_data:
            const.LOGGER.warning(
                "WARNING: Claim Chore - Chore ID '%s' not found", chore_id
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        chore_info = self.chores_data[chore_id]
        if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            const.LOGGER.warning(
                "WARNING: Claim Chore - Chore ID '%s' not assigned to kid ID '%s'",
                chore_id,
                kid_id,
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                translation_placeholders={
                    "entity": chore_info.get(const.DATA_CHORE_NAME),
                    "kid": self.kids_data[kid_id][const.DATA_KID_NAME],
                },
            )

        if kid_id not in self.kids_data:
            const.LOGGER.warning("Kid ID '%s' not found", kid_id)
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        kid_info = self.kids_data[kid_id]

        self._normalize_kid_reward_data(kid_info)

        # Phase 4: Use timestamp-based helpers instead of deprecated lists
        # This checks: completed_by_other, pending_claim, already_approved
        can_claim, error_key = self._can_claim_chore(kid_id, chore_id)
        if not can_claim:
            chore_name = chore_info[const.DATA_CHORE_NAME]
            const.LOGGER.warning(
                "WARNING: Claim Chore - Chore '%s' cannot be claimed by kid '%s': %s",
                chore_name,
                kid_info.get(const.DATA_KID_NAME),
                error_key,
            )

            # Determine the appropriate error message based on the error key
            if error_key == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER:
                # Get the name of who completed the chore
                kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
                claimed_by = kid_chore_data.get(
                    const.DATA_CHORE_CLAIMED_BY, "another kid"
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_CLAIMED_BY_OTHER,
                    translation_placeholders={"claimed_by": str(claimed_by)},
                )
            if error_key == const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM,
                    translation_placeholders={"entity": chore_name},
                )
            # else: TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_ALREADY_CLAIMED,
                translation_placeholders={"entity": chore_name},
            )

        # Increment pending_count counter BEFORE _process_chore_state so has_pending_claim()
        # returns the correct value during global state computation (v0.4.0+ counter-based tracking)
        # Use _update_chore_data_for_kid to ensure proper initialization
        chore_info = self.chores_data[chore_id]
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
        self._update_chore_data_for_kid(kid_id, chore_id, 0.0)  # Initialize properly
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
        kid_chore_data_entry = kid_chores_data[chore_id]  # Now guaranteed to exist
        current_count = kid_chore_data_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = (
            current_count + 1
        )

        self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_CLAIMED)

        # Set claimed_by for ALL chore types (helper handles INDEPENDENT/SHARED_FIRST/SHARED)
        claiming_kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        self._set_chore_claimed_completed_by(
            chore_id, kid_id, const.DATA_CHORE_CLAIMED_BY, claiming_kid_name
        )

        # For SHARED_FIRST, also set other kids to completed_by_other state
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if other_kid_id == kid_id:
                    continue
                self._process_chore_state(
                    other_kid_id, chore_id, const.CHORE_STATE_COMPLETED_BY_OTHER
                )

        # Check if auto_approve is enabled for this chore
        auto_approve = chore_info.get(
            const.DATA_CHORE_AUTO_APPROVE, const.DEFAULT_CHORE_AUTO_APPROVE
        )

        if auto_approve:
            # Auto-approve the chore immediately (using create_task since approve_chore is async)
            self.hass.async_create_task(
                self.approve_chore("auto_approve", kid_id, chore_id)
            )
        # Send a notification to the parents that a kid claimed a chore (awaiting approval)
        # Uses tag-based aggregation (v0.5.0+) to prevent notification spam
        elif chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
        ):
            # Count total pending chores for this kid (for aggregated notification)
            pending_count = self._count_pending_chores_for_kid(kid_id)
            chore_name = self.chores_data[chore_id][const.DATA_CHORE_NAME]
            kid_name = self.kids_data[kid_id][const.DATA_KID_NAME]
            chore_points = chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
            )

            # Build action buttons using helper (DRY refactor v0.5.0+)
            actions = build_chore_actions(kid_id, chore_id)
            extra_data = build_extra_data(kid_id, chore_id=chore_id)

            # Use aggregated notification if multiple pending, else standard single
            if pending_count > 1:
                # Aggregated notification: "Sarah: 3 chores pending (latest: Dishes +5pts)"
                self.hass.async_create_task(
                    self._notify_parents_translated(
                        kid_id,
                        title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES,
                        message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES,
                        message_data={
                            "kid_name": kid_name,
                            "count": pending_count,
                            "latest_chore": chore_name,
                            "points": int(chore_points),
                        },
                        actions=actions,
                        extra_data=extra_data,
                        tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                        tag_identifiers=(chore_id, kid_id),
                    )
                )
            else:
                # Single pending chore - use standard claim notification with tag
                self.hass.async_create_task(
                    self._notify_parents_translated(
                        kid_id,
                        title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED,
                        message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED,
                        message_data={
                            "kid_name": kid_name,
                            "chore_name": chore_name,
                        },
                        actions=actions,
                        extra_data=extra_data,
                        tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                        tag_identifiers=(chore_id, kid_id),
                    )
                )

        # Clear due-soon reminder tracking (v0.5.0+) - chore was acted upon
        self._clear_due_soon_reminder(chore_id, kid_id)

        self._persist()
        self.async_set_updated_data(self._data)

        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: claim_chore() took %.3fs for kid '%s' chore '%s'",
            perf_duration,
            kid_id,
            chore_id,
        )

    async def approve_chore(
        self,
        parent_name: str,  # Used for stale notification feedback
        kid_id: str,
        chore_id: str,
        points_awarded: float | None = None,  # Reserved for future feature
    ):
        """Approve a chore for kid_id if assigned.

        Thread-safe implementation using asyncio.Lock to prevent race conditions
        when multiple parents click approve simultaneously (v0.5.0+).
        """
        perf_start = time.perf_counter()

        # Acquire lock for this specific kid+chore combination to prevent race conditions
        # This ensures only one approval can process at a time per kid+chore pair
        lock = self._get_approval_lock("approve_chore", kid_id, chore_id)
        async with lock:
            # === RACE CONDITION PROTECTION (v0.5.0+) ===
            # Re-validate inside lock - second parent to arrive will hit this
            # and return gracefully with informative feedback instead of duplicate approval
            can_approve, error_key = self._can_approve_chore(kid_id, chore_id)
            if not can_approve:
                # Chore was already approved by another parent while we waited for lock
                # Return gracefully - this is expected behavior, not an error
                const.LOGGER.info(
                    "Race condition prevented: chore '%s' for kid '%s' already %s",
                    chore_id,
                    kid_id,
                    "approved"
                    if error_key == const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED
                    else "completed by another kid",
                )
                # TODO (Phase 1.4): Send stale notification feedback to parent_name
                # "Already approved by {other_parent}" or similar
                return  # Graceful exit - no error raised for race condition

            # === ORIGINAL VALIDATION (now inside lock) ===
            if chore_id not in self.chores_data:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_CHORE,
                        "name": chore_id,
                    },
                )

            chore_info = self.chores_data[chore_id]
            if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": chore_info.get(const.DATA_CHORE_NAME),
                        "kid": self.kids_data[kid_id][const.DATA_KID_NAME],
                    },
                )

            if kid_id not in self.kids_data:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info = self.kids_data[kid_id]

            # Phase 4: Use timestamp-based helpers instead of deprecated lists
            # This checks: completed_by_other, already_approved
            can_approve, error_key = self._can_approve_chore(kid_id, chore_id)
            if not can_approve:
                chore_name = chore_info[const.DATA_CHORE_NAME]
                const.LOGGER.warning(
                    "Approve Chore: Cannot approve '%s' for kid '%s': %s",
                    chore_name,
                    kid_info[const.DATA_KID_NAME],
                    error_key,
                )
                # Determine the appropriate error message based on the error key
                if error_key == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER:
                    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
                    claimed_by = kid_chore_data.get(
                        const.DATA_CHORE_CLAIMED_BY, "another kid"
                    )
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER,
                        translation_placeholders={
                            "chore_name": chore_name,
                            "claimed_by": str(claimed_by),
                        },
                    )
                # else: TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED,
                )

            default_points = chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS
            )

            # Phase 4: Check if gamification is enabled for shadow kids
            # Regular kids always get points; shadow kids only if gamification enabled
            enable_gamification = True  # Default for regular kids
            if kh.is_shadow_kid(self, kid_id):
                parent_data = kh.get_parent_for_shadow_kid(self, kid_id)
                if parent_data:
                    enable_gamification = parent_data.get(
                        const.DATA_PARENT_ENABLE_GAMIFICATION, False
                    )

            # Award points only if gamification is enabled
            points_to_award = default_points if enable_gamification else 0.0

            # Note - multiplier will be added in the _update_kid_points method called from _process_chore_state
            self._process_chore_state(
                kid_id,
                chore_id,
                const.CHORE_STATE_APPROVED,
                points_awarded=points_to_award,
            )

            # Decrement pending_count counter after approval (v0.4.0+ counter-based tracking)
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            # Use get() to avoid overwriting existing data that _process_chore_state just created
            kid_chore_data_entry = kid_chores_data[
                chore_id
            ]  # Should exist from _process_chore_state
            current_count = kid_chore_data_entry.get(
                const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
            )
            kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
                0, current_count - 1
            )

            # Set completed_by for ALL chore types
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
            )
            completing_kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT: Store completing kid's own name in their kid_chore_data
                kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
                if chore_id not in kid_chores_data:
                    self._update_chore_data_for_kid(kid_id, chore_id, 0.0)
                kid_chores_data[chore_id][const.DATA_CHORE_COMPLETED_BY] = (
                    completing_kid_name
                )
                const.LOGGER.debug(
                    "INDEPENDENT: Set completed_by='%s' for kid '%s' on chore '%s'",
                    completing_kid_name,
                    completing_kid_name,
                    chore_info.get(const.DATA_CHORE_NAME),
                )

            elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                # SHARED_FIRST: Update completed_by for other kids (they remain in completed_by_other state)
                for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if other_kid_id == kid_id:
                        continue  # Skip the completing kid
                    # Update the completed_by attribute
                    other_kid_info: KidData = cast(
                        "KidData", self.kids_data.get(other_kid_id, {})
                    )
                    chore_data = other_kid_info.setdefault(
                        const.DATA_KID_CHORE_DATA, {}
                    )
                    # Ensure proper chore data initialization
                    if chore_id not in chore_data:
                        self._update_chore_data_for_kid(other_kid_id, chore_id, 0.0)
                    chore_entry = chore_data[chore_id]
                    chore_entry[const.DATA_CHORE_COMPLETED_BY] = completing_kid_name
                    const.LOGGER.debug(
                        "SHARED_FIRST: Updated completed_by='%s' for kid '%s' on chore '%s'",
                        completing_kid_name,
                        other_kid_info.get(const.DATA_KID_NAME),
                        chore_info.get(const.DATA_CHORE_NAME),
                    )

            elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
                # SHARED_ALL: Append to list of completing kids in each kid's own kid_chore_data
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    assigned_kid_info: KidData = cast(
                        "KidData", self.kids_data.get(assigned_kid_id, {})
                    )
                    assigned_kid_chore_data = assigned_kid_info.setdefault(
                        const.DATA_KID_CHORE_DATA, {}
                    )
                    # Ensure proper initialization
                    if chore_id not in assigned_kid_chore_data:
                        self._update_chore_data_for_kid(assigned_kid_id, chore_id, 0.0)
                    chore_entry = assigned_kid_chore_data[chore_id]

                    # Initialize as list if not present or if it's not a list
                    if (
                        const.DATA_CHORE_COMPLETED_BY not in chore_entry
                        or not isinstance(
                            chore_entry[const.DATA_CHORE_COMPLETED_BY], list
                        )
                    ):
                        chore_entry[const.DATA_CHORE_COMPLETED_BY] = []

                    # Append completing kid's name if not already in list
                    completed_by_list = chore_entry.get(
                        const.DATA_CHORE_COMPLETED_BY, []
                    )
                    if (
                        isinstance(completed_by_list, list)
                        and completing_kid_name not in completed_by_list
                    ):
                        completed_by_list.append(completing_kid_name)
                        chore_entry[const.DATA_CHORE_COMPLETED_BY] = completed_by_list

                const.LOGGER.debug(
                    "SHARED_ALL: Added '%s' to completed_by list for chore '%s'",
                    completing_kid_name,
                    chore_info.get(const.DATA_CHORE_NAME),
                )

            # Manage Achievements
            today_local = kh.get_today_local_date()
            for achievement_info in self.achievements_data.values():
                if (
                    achievement_info.get(const.DATA_ACHIEVEMENT_TYPE)
                    == const.ACHIEVEMENT_TYPE_STREAK
                ):
                    selected_chore_id = achievement_info.get(
                        const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID
                    )
                    if selected_chore_id == chore_id:
                        # Get or create the progress dict for this kid
                        ach_progress_data: dict[str, AchievementProgress] = (
                            achievement_info.setdefault(  # type: ignore[assignment,call-overload,operator]
                                const.DATA_ACHIEVEMENT_PROGRESS, {}
                            )
                        )  # type: ignore[typeddict-item]
                        ach_progress: AchievementProgress = (
                            ach_progress_data.setdefault(
                                kid_id,
                                {
                                    const.DATA_KID_CURRENT_STREAK: const.DEFAULT_ZERO,
                                    const.DATA_KID_LAST_STREAK_DATE: None,
                                    const.DATA_ACHIEVEMENT_AWARDED: False,
                                },
                            )
                        )  # type: ignore[typeddict-item]
                        self._update_streak_progress(ach_progress, today_local)

            # Manage Challenges
            today_local_iso = kh.get_today_local_iso()
            for challenge_info in self.challenges_data.values():
                challenge_type = challenge_info.get(const.DATA_CHALLENGE_TYPE)

                if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                    selected_chore = challenge_info.get(
                        const.DATA_CHALLENGE_SELECTED_CHORE_ID
                    )
                    if selected_chore and selected_chore != chore_id:
                        continue

                    start_date_str = challenge_info.get(const.DATA_CHALLENGE_START_DATE)
                    end_date_str = challenge_info.get(const.DATA_CHALLENGE_END_DATE)
                    if not start_date_str or not end_date_str:
                        continue

                    start_date_utc = kh.parse_datetime_to_utc(start_date_str)
                    end_date_utc = kh.parse_datetime_to_utc(end_date_str)

                    now_utc = dt_util.utcnow()

                    if (
                        start_date_utc
                        and end_date_utc
                        and start_date_utc <= now_utc <= end_date_utc
                    ):
                        progress_data_ch1: dict[str, ChallengeProgress] = (
                            challenge_info.setdefault(  # type: ignore[assignment,call-overload,operator]
                                const.DATA_CHALLENGE_PROGRESS, {}
                            )
                        )  # type: ignore[typeddict-item]
                        ch1_progress: ChallengeProgress = progress_data_ch1.setdefault(
                            kid_id,
                            {
                                const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                                const.DATA_CHALLENGE_AWARDED: False,
                            },
                        )  # type: ignore[typeddict-item]
                        ch1_progress[const.DATA_CHALLENGE_COUNT] = (
                            ch1_progress.get(const.DATA_CHALLENGE_COUNT, 0) + 1
                        )

                elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                    selected_chore = challenge_info.get(
                        const.DATA_CHALLENGE_SELECTED_CHORE_ID
                    )
                    if not selected_chore:
                        const.LOGGER.warning(
                            "WARNING: Challenge '%s' of type daily minimum has no selected chore id. Skipping progress update.",
                            challenge_info.get(const.DATA_CHALLENGE_NAME),
                        )
                        continue

                    if selected_chore != chore_id:
                        continue

                    if kid_id in challenge_info.get(
                        const.DATA_CHALLENGE_ASSIGNED_KIDS, []
                    ):
                        progress_data_ch2: dict[str, ChallengeProgress] = (
                            challenge_info.setdefault(  # type: ignore[assignment,call-overload,operator]
                                const.DATA_CHALLENGE_PROGRESS, {}
                            )
                        )  # type: ignore[typeddict-item]
                        ch2_progress: ChallengeProgress = progress_data_ch2.setdefault(
                            kid_id,
                            {
                                const.DATA_CHALLENGE_DAILY_COUNTS: {},
                                const.DATA_CHALLENGE_AWARDED: False,
                            },
                        )  # type: ignore[typeddict-item]
                        daily_counts = ch2_progress.get(
                            const.DATA_CHALLENGE_DAILY_COUNTS, {}
                        )
                        daily_counts[today_local_iso] = (
                            daily_counts.get(today_local_iso, const.DEFAULT_ZERO) + 1
                        )
                        ch2_progress[const.DATA_CHALLENGE_DAILY_COUNTS] = daily_counts

            # For INDEPENDENT chores with UPON_COMPLETION reset type, reschedule per-kid due date after approval
            # Other reset types (at_midnight_*, at_due_date_*) should NOT reschedule on approval
            # UNLESS overdue_handling is immediate_on_late AND approval is late
            approval_reset_type = chore_info.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
            )
            overdue_handling = chore_info.get(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.DEFAULT_OVERDUE_HANDLING_TYPE,
            )

            # Check if this is a late approval (after reset boundary passed)
            is_late_approval = self._is_approval_after_reset_boundary(
                chore_info, kid_id
            )

            # Determine if immediate reschedule is needed
            should_reschedule_immediately = (
                approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
                or (
                    overdue_handling
                    == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
                    and is_late_approval
                )
            )

            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_INDEPENDENT
                and should_reschedule_immediately
            ):
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )

            # CFE-2026-002: For SHARED chores with UPON_COMPLETION, check if all kids approved
            # and reschedule chore-level due date immediately
            completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)  # type: ignore[assignment,call-overload,operator]
            if (
                completion_criteria
                in (
                    const.COMPLETION_CRITERIA_SHARED,
                    const.COMPLETION_CRITERIA_SHARED_FIRST,
                )
                and should_reschedule_immediately
            ):
                # Check if all assigned kids have approved in current period
                assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                all_approved = all(
                    self.is_approved_in_current_period(kid, chore_id)
                    for kid in assigned_kids
                )
                if all_approved:
                    const.LOGGER.debug(
                        "CFE-2026-002: All kids approved SHARED chore '%s', rescheduling immediately",
                        chore_info.get(const.DATA_CHORE_NAME),
                    )
                    self._reschedule_chore_next_due_date(chore_info)

            # Send a notification to the kid that chore was approved
            if chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            ):
                extra_data = {const.DATA_KID_ID: kid_id, const.DATA_CHORE_ID: chore_id}
                self.hass.async_create_task(
                    self._notify_kid_translated(
                        kid_id,
                        title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED,
                        message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED,
                        message_data={
                            "chore_name": chore_info[const.DATA_CHORE_NAME],
                            "points": default_points,
                        },
                        extra_data=extra_data,
                    )
                )

            # Replace parent pending notification with status update (v0.5.0+)
            # Check if there are more pending chores or clear with status
            remaining_pending = self._count_pending_chores_for_kid(kid_id)
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
            chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown")

            if remaining_pending > 0:
                # Still have pending chores - send updated aggregated notification
                # Get most recent pending chore for display
                latest_pending = self._get_latest_pending_chore(kid_id)
                if latest_pending:
                    latest_chore_id = latest_pending.get(const.DATA_CHORE_ID, "")
                    if latest_chore_id and latest_chore_id in self.chores_data:
                        latest_chore_info = self.chores_data[latest_chore_id]
                        latest_chore_name = latest_chore_info.get(
                            const.DATA_CHORE_NAME, "Unknown"
                        )
                        latest_points = latest_chore_info.get(
                            const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
                        )
                        # Use helpers for action buttons (DRY refactor v0.5.0+)
                        actions = build_chore_actions(kid_id, latest_chore_id)
                        self.hass.async_create_task(
                            self._notify_parents_translated(
                                kid_id,
                                title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES,
                                message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES,
                                message_data={
                                    "kid_name": kid_name,
                                    "count": remaining_pending,
                                    "latest_chore": latest_chore_name,
                                    "points": int(latest_points),
                                },
                                actions=actions,
                                extra_data=build_extra_data(
                                    kid_id, chore_id=latest_chore_id
                                ),
                                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                                tag_identifiers=(latest_chore_id, kid_id),
                            )
                        )

            # Clear the approved chore's notification (v0.5.0+ - handles dashboard approvals)
            self.hass.async_create_task(
                self.clear_notification_for_parents(
                    kid_id, const.NOTIFY_TAG_TYPE_STATUS, chore_id
                )
            )

            # Clear due-soon reminder tracking (v0.5.0+) - chore was completed
            self._clear_due_soon_reminder(chore_id, kid_id)

            # For UPON_COMPLETION chores, immediately reset to PENDING and check overdue
            # This ensures chore is ready for next completion and reflects accurate state
            if approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION:
                # Reset to PENDING with new approval period
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    self._process_chore_state(
                        assigned_kid_id,
                        chore_id,
                        const.CHORE_STATE_PENDING,
                        reset_approval_period=True,
                    )
                const.LOGGER.debug(
                    "UPON_COMPLETION: Reset chore '%s' to PENDING immediately after approval",
                    chore_info.get(const.DATA_CHORE_NAME),
                )

                # Immediately check if chore is now overdue (due date hasn't changed)
                await self._check_overdue_chores()

            self._persist()
            self.async_set_updated_data(self._data)

            perf_duration = time.perf_counter() - perf_start
            const.LOGGER.debug(
                "PERF: approve_chore() took %.3fs for kid '%s' chore '%s' (includes %.1f points addition)",
                perf_duration,
                kid_id,
                chore_id,
                default_points,
            )

    def disapprove_chore(self, parent_name: str, kid_id: str, chore_id: str):
        """Disapprove a chore for kid_id."""
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Decrement pending_count for the claimant ONLY (v0.4.0+ counter-based tracking)
        # This happens regardless of completion criteria - only the kid who claimed is affected
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
        # Ensure proper chore data initialization
        if chore_id not in kid_chores_data:
            self._update_chore_data_for_kid(kid_id, chore_id, 0.0)
        kid_chore_data_entry = kid_chores_data[chore_id]
        current_count = kid_chore_data_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current_count - 1
        )

        # SHARED_FIRST: Reset ALL kids to pending (everyone gets another chance)
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            const.LOGGER.info(
                "SHARED_FIRST: Disapproval - resetting all kids to pending for chore '%s'",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                self._process_chore_state(
                    other_kid_id, chore_id, const.CHORE_STATE_PENDING
                )
            # Clear claimed_by/completed_by for all assigned kids
            self._clear_chore_claimed_completed_by(chore_id)
        else:
            # Normal behavior: only reset the disapproved kid
            self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)

        # Send a notification to the kid that chore was disapproved
        if chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL, const.DEFAULT_NOTIFY_ON_DISAPPROVAL
        ):
            extra_data = {const.DATA_KID_ID: kid_id, const.DATA_CHORE_ID: chore_id}
            self.hass.async_create_task(
                self._notify_kid_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DISAPPROVED,
                    message_data={"chore_name": chore_info[const.DATA_CHORE_NAME]},
                    extra_data=extra_data,
                )
            )

        # Send notification to parents about disapproval with updated pending count
        remaining_pending = self._count_pending_chores_for_kid(kid_id)
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

        if remaining_pending > 0:
            # Still have pending chores - send updated aggregated notification
            latest_pending = self._get_latest_pending_chore(kid_id)
            if latest_pending:
                latest_chore_id = latest_pending.get(const.DATA_CHORE_ID, "")
                if latest_chore_id and latest_chore_id in self.chores_data:
                    latest_chore_info = self.chores_data[latest_chore_id]
                    latest_chore_name = latest_chore_info.get(
                        const.DATA_CHORE_NAME, "Unknown"
                    )
                    latest_points = latest_chore_info.get(
                        const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
                    )
                    # Use helpers for action buttons (DRY refactor v0.5.0+)
                    actions = build_chore_actions(kid_id, latest_chore_id)
                    self.hass.async_create_task(
                        self._notify_parents_translated(
                            kid_id,
                            title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES,
                            message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES,
                            message_data={
                                "kid_name": kid_name,
                                "count": remaining_pending,
                                "latest_chore": latest_chore_name,
                                "points": int(latest_points),
                            },
                            actions=actions,
                            extra_data=build_extra_data(
                                kid_id, chore_id=latest_chore_id
                            ),
                            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                            tag_identifiers=(latest_chore_id, kid_id),
                        )
                    )

        # Clear the disapproved chore's notification (v0.5.0+ - handles dashboard disapprovals)
        self.hass.async_create_task(
            self.clear_notification_for_parents(
                kid_id, const.NOTIFY_TAG_TYPE_STATUS, chore_id
            )
        )

        self._persist()
        self.async_set_updated_data(self._data)

    def undo_chore_claim(self, kid_id: str, chore_id: str):
        """Allow kid to undo their own chore claim (no stat tracking).

        This method provides a way for kids to remove their claim on a chore
        without it counting as a disapproval. Similar to disapprove_chore but:
        - Does NOT track disapproval stats (skip_stats=True)
        - Does NOT send notifications (silent undo)
        - Only resets the kid who is undoing (not all kids for SHARED_FIRST)

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Raises:
            HomeAssistantError: If kid or chore not found
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Decrement pending_count for the kid (v0.4.0+ counter-based tracking)
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
        # Ensure proper chore data initialization
        if chore_id not in kid_chores_data:
            self._update_chore_data_for_kid(kid_id, chore_id, 0.0)
        kid_chore_data_entry = kid_chores_data[chore_id]
        current_count = kid_chore_data_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current_count - 1
        )

        # SHARED_FIRST: For kid undo, reset ALL kids to pending (same as disapproval)
        # This maintains fairness - if one kid undoes, everyone gets another chance
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            const.LOGGER.info(
                "SHARED_FIRST: Kid undo - resetting all kids to pending for chore '%s'",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                # Use skip_stats=True to prevent stat tracking for all kids
                self._process_chore_state(
                    other_kid_id, chore_id, const.CHORE_STATE_PENDING, skip_stats=True
                )
                # Clear claimed_by/completed_by attributes
                other_kid_info: KidData = cast(
                    "KidData", self.kids_data.get(other_kid_id, {})
                )
                chore_data = other_kid_info.get(const.DATA_KID_CHORE_DATA, {})
                if chore_id in chore_data:
                    chore_data[chore_id].pop(const.DATA_CHORE_CLAIMED_BY, None)
                    chore_data[chore_id].pop(const.DATA_CHORE_COMPLETED_BY, None)
        else:
            # Normal behavior: only reset the kid who is undoing, skip stats
            self._process_chore_state(
                kid_id, chore_id, const.CHORE_STATE_PENDING, skip_stats=True
            )

        # No notification sent (silent undo)

        self._persist()
        self.async_set_updated_data(self._data)

    def update_chore_state(self, chore_id: str, state: str):
        """Manually override a chore's state."""
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            const.LOGGER.warning(
                "WARNING: Update Chore State -  Chore ID '%s' not found", chore_id
            )
            return
        # Set state for all kids assigned to the chore:
        for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            if kid_id:
                self._process_chore_state(
                    kid_id, chore_id, state, reset_approval_period=True
                )
        self._persist()
        self.async_set_updated_data(self._data)
        const.LOGGER.debug(
            "DEBUG: Chore ID '%s' manually updated to '%s'", chore_id, state
        )

    # -------------------------------------------------------------------------------------
    # Claim & Approval Eligibility Helpers (Phase 4: Approval Reset Timing)
    # These helpers use timestamp-based logic from kid_chore_data instead of the deprecated
    # deprecated claimed_chores/approved_chores lists (removed v0.4.0). They determine whether a kid can claim or
    # have a chore approved based on:
    # - Whether they have a pending claim (claimed but not yet approved/disapproved)
    # - Whether the chore was already approved in the current approval period
    # - Whether another kid completed the chore (SHARED_FIRST mode: completed_by_other)
    # -------------------------------------------------------------------------------------

    def _get_kid_chore_data(
        self, kid_id: str, chore_id: str
    ) -> KidChoreDataEntry | dict[str, Any]:
        """Get the chore data dict for a specific kid+chore combination.

        Returns an empty dict if the kid or chore data doesn't exist.
        """
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        return kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})

    def _get_kid_reward_data(
        self, kid_id: str, reward_id: str, create: bool = False
    ) -> dict[str, Any]:
        """Get the reward data dict for a specific kid+reward combination.

        Args:
            kid_id: The kid's internal ID
            reward_id: The reward's internal ID
            create: If True, create the entry if it doesn't exist

        Returns an empty dict if the kid or reward data doesn't exist and create=False.
        """
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        reward_data = kid_info.setdefault(const.DATA_KID_REWARD_DATA, {})
        if create and reward_id not in reward_data:
            reward_data[reward_id] = {
                const.DATA_KID_REWARD_DATA_NAME: self.rewards_data.get(  # type: ignore[assignment,call-overload,operator]
                    reward_id, {}
                ).get(const.DATA_REWARD_NAME, ""),
                const.DATA_KID_REWARD_DATA_PENDING_COUNT: 0,
                const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS: [],
                const.DATA_KID_REWARD_DATA_LAST_CLAIMED: "",
                const.DATA_KID_REWARD_DATA_LAST_APPROVED: "",
                const.DATA_KID_REWARD_DATA_LAST_DISAPPROVED: "",
                const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS: 0,
                const.DATA_KID_REWARD_DATA_TOTAL_APPROVED: 0,
                const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED: 0,
                const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT: 0,
                const.DATA_KID_REWARD_DATA_PERIODS: {
                    const.DATA_KID_REWARD_DATA_PERIODS_DAILY: {},
                    const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY: {},
                    const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY: {},
                    const.DATA_KID_REWARD_DATA_PERIODS_YEARLY: {},
                },
            }
        return reward_data.get(reward_id, {})  # type: ignore[return-value]

    def _increment_reward_period_counter(
        self,
        reward_entry: dict[str, Any],
        counter_key: str,
        amount: int = 1,
    ) -> None:
        """Increment a period counter for a reward entry across all period buckets.

        Args:
            reward_entry: The reward_data[reward_id] dict
            counter_key: Which counter to increment (claimed/approved/disapproved/points)
            amount: Amount to add (default 1)
        """
        now = dt_util.now()  # Local time for period keys

        # Get period IDs using same format as chore_data and point_data
        daily_key = now.strftime("%Y-%m-%d")
        weekly_key = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"
        monthly_key = now.strftime("%Y-%m")
        yearly_key = now.strftime("%Y")

        # Ensure periods structure exists
        periods = reward_entry.setdefault(
            const.DATA_KID_REWARD_DATA_PERIODS,
            {
                const.DATA_KID_REWARD_DATA_PERIODS_DAILY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_YEARLY: {},
            },
        )

        # Helper to get or create period entry with all counters
        def _get_period_entry(bucket: dict, period_id: str) -> dict:
            if period_id not in bucket:
                bucket[period_id] = {
                    const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED: 0,
                    const.DATA_KID_REWARD_DATA_PERIOD_APPROVED: 0,
                    const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED: 0,
                    const.DATA_KID_REWARD_DATA_PERIOD_POINTS: 0,
                }
            return bucket[period_id]

        # Increment counter in each period bucket
        daily = periods.setdefault(const.DATA_KID_REWARD_DATA_PERIODS_DAILY, {})
        _get_period_entry(daily, daily_key)[counter_key] = (
            _get_period_entry(daily, daily_key).get(counter_key, 0) + amount
        )

        weekly = periods.setdefault(const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY, {})
        _get_period_entry(weekly, weekly_key)[counter_key] = (
            _get_period_entry(weekly, weekly_key).get(counter_key, 0) + amount
        )

        monthly = periods.setdefault(const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY, {})
        _get_period_entry(monthly, monthly_key)[counter_key] = (
            _get_period_entry(monthly, monthly_key).get(counter_key, 0) + amount
        )

        yearly = periods.setdefault(const.DATA_KID_REWARD_DATA_PERIODS_YEARLY, {})
        _get_period_entry(yearly, yearly_key)[counter_key] = (
            _get_period_entry(yearly, yearly_key).get(counter_key, 0) + amount
        )

    def has_pending_claim(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore has a pending claim (claimed but not yet approved/disapproved).

        Uses the pending_count counter which is incremented on claim and
        decremented on approve/disapprove.

        Returns:
            True if there's a pending claim (pending_claim_count > 0), False otherwise.
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if not kid_chore_data:
            return False

        pending_claim_count = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        return pending_claim_count > 0

    def _count_pending_chores_for_kid(self, kid_id: str) -> int:
        """Count total pending chores awaiting approval for a specific kid.

        Used for tag-based notification aggregation (v0.5.0+) to show
        "Sarah: 3 chores pending" instead of individual notifications.

        Args:
            kid_id: The internal ID of the kid.

        Returns:
            Number of chores with pending claims for this kid.
        """
        count = 0
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        for chore_id in chore_data:
            # Skip chores that no longer exist
            if chore_id not in self.chores_data:
                continue
            if self.has_pending_claim(kid_id, chore_id):
                count += 1

        return count

    def _get_latest_pending_chore(self, kid_id: str) -> dict[str, Any] | None:
        """Get the most recently claimed pending chore for a kid.

        Used for tag-based notification aggregation (v0.5.0+) to show
        the latest chore details in aggregated notifications.

        Args:
            kid_id: The internal ID of the kid.

        Returns:
            Dict with kid_id and chore_id of latest pending chore, or None if none.
        """
        latest: dict[str, Any] | None = None
        latest_timestamp: str | None = None

        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        for chore_id, chore_entry in chore_data.items():
            # Skip chores that no longer exist
            if chore_id not in self.chores_data:
                continue
            if not self.has_pending_claim(kid_id, chore_id):
                continue

            last_claimed = chore_entry.get(const.DATA_KID_CHORE_DATA_LAST_CLAIMED)
            if last_claimed:
                if latest_timestamp is None or last_claimed > latest_timestamp:
                    latest_timestamp = last_claimed
                    latest = {
                        const.DATA_KID_ID: kid_id,
                        const.DATA_CHORE_ID: chore_id,
                    }

        return latest

    def is_overdue(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is in overdue state for a specific kid.

        Uses the per-kid chore state field (single source of truth).
        This replaces the legacy DATA_KID_OVERDUE_CHORES list.

        Returns:
            True if the chore is in overdue state, False otherwise.
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if not kid_chore_data:
            return False

        current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
        return current_state == const.CHORE_STATE_OVERDUE

    def get_pending_chore_approvals_computed(self) -> list[dict[str, Any]]:
        """Compute pending chore approvals dynamically from timestamp data.

        This replaces the legacy queue-based approach with dynamic computation
        from kid_chore_data timestamps. A chore has a pending approval if:
        - last_claimed timestamp exists AND
        - last_claimed > last_approved (or no approval) AND
        - last_claimed > last_disapproved (or no disapproval)

        Returns:
            List of dicts with keys: kid_id, chore_id, timestamp
            Format matches the legacy queue structure for compatibility.
        """
        pending: list[dict[str, Any]] = []
        for kid_id, kid_info in self.kids_data.items():
            chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            for chore_id, chore_entry in chore_data.items():
                # Skip chores that no longer exist
                if chore_id not in self.chores_data:
                    continue
                if self.has_pending_claim(kid_id, chore_id):
                    pending.append(
                        {
                            const.DATA_KID_ID: kid_id,
                            const.DATA_CHORE_ID: chore_id,
                            const.DATA_CHORE_TIMESTAMP: chore_entry.get(
                                const.DATA_KID_CHORE_DATA_LAST_CLAIMED, ""
                            ),
                        }
                    )
        return pending

    def get_pending_reward_approvals_computed(self) -> list[dict[str, Any]]:
        """Compute pending reward approvals dynamically from kid_reward_data.

        Unlike chores (which allow only one pending claim at a time), rewards
        support multiple pending claims via the pending_count field.

        Returns:
            List of dicts with keys: kid_id, reward_id, pending_count, timestamp
            One entry per kid+reward combination with pending_count > 0.
        """
        pending: list[dict[str, Any]] = []
        for kid_id, kid_info in self.kids_data.items():
            reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})
            for reward_id, entry in reward_data.items():
                # Skip rewards that no longer exist
                if reward_id not in self.rewards_data:
                    continue
                pending_count = entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)
                if pending_count > 0:
                    pending.append(
                        {
                            const.DATA_KID_ID: kid_id,
                            const.DATA_REWARD_ID: reward_id,
                            "pending_count": pending_count,
                            const.DATA_REWARD_TIMESTAMP: entry.get(
                                const.DATA_KID_REWARD_DATA_LAST_CLAIMED, ""
                            ),
                        }
                    )
        return pending

    def _get_approval_period_start(self, kid_id: str, chore_id: str) -> str | None:
        """Get the start of the current approval period for this kid+chore.

        For SHARED chores: Uses chore-level approval_period_start
        For INDEPENDENT chores: Uses per-kid approval_period_start in kid_chore_data

        Returns:
            ISO timestamp string of period start, or None if not set.
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            return None

        # Default to INDEPENDENT if completion_criteria not set (backward compatibility)
        # This ensures pre-migration chores without completion_criteria are treated as INDEPENDENT
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Period start is per-kid in kid_chore_data
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            return kid_chore_data.get(const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START)
        # SHARED/SHARED_FIRST/etc.: Period start is at chore level
        return chore_info.get(const.DATA_CHORE_APPROVAL_PERIOD_START)

    def is_approved_in_current_period(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is already approved in the current approval period.

        A chore is considered approved in the current period if:
        - last_approved timestamp exists, AND EITHER:
          a. approval_period_start doesn't exist (chore was never reset, approval is valid), OR
          b. last_approved >= approval_period_start

        Returns:
            True if approved in current period, False otherwise.
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if not kid_chore_data:
            return False

        last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if not last_approved:
            return False

        period_start = self._get_approval_period_start(kid_id, chore_id)
        if not period_start:
            # No period_start means chore was never reset after being created.
            # Since last_approved exists (checked above), the approval is still valid.
            return True

        approved_dt = kh.parse_datetime_to_utc(last_approved)
        period_start_dt = kh.parse_datetime_to_utc(period_start)

        if approved_dt is None or period_start_dt is None:
            return False

        return approved_dt >= period_start_dt

    def _can_claim_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
        """Check if a kid can claim a specific chore.

        This helper is dual-purpose: used for claim validation AND for providing
        status information to the dashboard helper sensor.

        Checks (in order):
        1. completed_by_other - Another kid already completed (SHARED_FIRST mode)
        2. pending_claim - Already has a claim awaiting approval
        3. already_approved - Already approved in current period (if not multi-claim)

        Returns:
            Tuple of (can_claim: bool, error_key: str | None)
            - (True, None) if claim is allowed
            - (False, translation_key) if claim is blocked
        """
        # Get current state for this kid+chore
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all claims
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Determine if this is a multi-claim mode (needed for checks 2 and 3)
        allow_multiple_claims = self._allows_multiple_claims(chore_id)

        # Check 2: pending claim blocks new claims (unless multi-claim allowed)
        # For MULTI modes, re-claiming is allowed even with a pending claim
        if not allow_multiple_claims and self.has_pending_claim(kid_id, chore_id):
            return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)

        # Check 3: already approved in current period (unless multi-claim allowed)
        if not allow_multiple_claims and self.is_approved_in_current_period(
            kid_id, chore_id
        ):
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    def _can_approve_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
        """Check if a chore can be approved for a specific kid.

        This helper is dual-purpose: used for approval validation AND for providing
        status information to the dashboard helper sensor.

        Checks (in order):
        1. completed_by_other - Another kid already completed (SHARED_FIRST mode)
        2. already_approved - Already approved in current period (if not multi-claim)

        Note: Unlike _can_claim_chore, this does NOT check for pending claims because
        we're checking if approval is possible, not if a new claim can be made.

        Returns:
            Tuple of (can_approve: bool, error_key: str | None)
            - (True, None) if approval is allowed
            - (False, translation_key) if approval is blocked
        """
        # Get current state for this kid+chore
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all approvals
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Check 2: already approved in current period (unless multi-claim allowed)
        allow_multiple_claims = self._allows_multiple_claims(chore_id)

        if not allow_multiple_claims and self.is_approved_in_current_period(
            kid_id, chore_id
        ):
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    # -------------------------------------------------------------------------------------
    # Chore State Processing: Centralized Function
    # The most critical thing to understand when working on this function is that
    # chore_info[const.DATA_CHORE_STATE] is actually the global state of the chore. The individual chore
    # state per kid is always calculated based on whether they have any claimed, approved, or
    # overdue chores listed for them.
    #
    # Global state will only match if a single kid is assigned to the chore, or all kids
    # assigned are in the same state.
    # -------------------------------------------------------------------------------------

    def _process_chore_state(
        self,
        kid_id: str,
        chore_id: str,
        new_state: str,
        *,
        points_awarded: float | None = None,
        reset_approval_period: bool = False,
        skip_stats: bool = False,
    ) -> None:
        """Centralized function to update a chore's state for a given kid.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            new_state: The new state to set (PENDING, CLAIMED, APPROVED, etc.)
            points_awarded: Points to award (only for APPROVED state)
            reset_approval_period: If True and new_state is PENDING, sets a new
                approval_period_start. Should be True for scheduled resets (midnight,
                due date) but False for disapproval (which only affects one kid's claim).
            skip_stats: If True, skip disapproval stat tracking (for kid undo).
        """

        # Add a flag to control debug messages
        debug_enabled = False

        if debug_enabled:
            const.LOGGER.debug(
                "DEBUG: Chore State - Processing - Kid ID '%s', Chore ID '%s', State '%s', Points Awarded '%s'",
                kid_id,
                chore_id,
                new_state,
                points_awarded,
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        chore_info: ChoreData | None = self.chores_data.get(chore_id)

        if not kid_info or not chore_info:
            const.LOGGER.warning(
                "WARNING: Chore State - Change skipped. Kid ID '%s' or Chore ID '%s' not found",
                kid_id,
                chore_id,
            )
            return

        # Update kid chore tracking data
        # Pass 0 for points_awarded if None and not in APPROVED state
        actual_points = points_awarded if points_awarded is not None else 0.0

        # Get due date to pass to kid chore data
        # For INDEPENDENT chores, use per-kid due date; for SHARED, use chore-level
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            due_date = per_kid_due_dates.get(kid_id)
        else:
            due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)

        # Update the kid's chore history
        self._update_chore_data_for_kid(
            kid_id=kid_id,
            chore_id=chore_id,
            points_awarded=actual_points,
            state=new_state,
            due_date=due_date,
            skip_stats=skip_stats,
        )

        # Clear overdue notification tracking when transitioning out of overdue state.
        # (State is now tracked via DATA_KID_CHORE_DATA_STATE, not a list)
        if new_state != const.CHORE_STATE_OVERDUE:
            overdue_notifs = kid_info.get(const.DATA_KID_OVERDUE_NOTIFICATIONS, {})
            if chore_id in overdue_notifs:
                overdue_notifs.pop(chore_id)
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = overdue_notifs  # type: ignore[typeddict-item]

        if new_state == const.CHORE_STATE_CLAIMED:
            # Update kid_chore_data with claim timestamp (v0.4.0+ timestamp-based tracking)
            now_iso = dt_util.utcnow().isoformat()
            # Use _update_chore_data_for_kid to ensure proper initialization
            self._update_chore_data_for_kid(
                kid_id, chore_id, 0.0
            )  # No points awarded for claim
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            kid_chore_data_entry = kid_chores_data[
                chore_id
            ]  # Now guaranteed to exist and be properly initialized
            kid_chore_data_entry[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = now_iso

            chore_info[const.DATA_CHORE_LAST_CLAIMED] = now_iso
            # Queue write removed - pending approvals now computed from timestamps
            self._pending_chore_changed = True

        elif new_state == const.CHORE_STATE_APPROVED:
            # Update kid_chore_data with approval timestamp (v0.4.0+ timestamp-based tracking)
            now_iso = dt_util.utcnow().isoformat()
            # Use _update_chore_data_for_kid to ensure proper initialization
            self._update_chore_data_for_kid(kid_id, chore_id, points_awarded or 0.0)
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            kid_chore_data_entry = kid_chores_data[
                chore_id
            ]  # Now guaranteed to exist and be properly initialized
            kid_chore_data_entry[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso
            # NOTE: last_claimed is intentionally preserved after approval
            # to maintain consistent behavior with other last_* fields

            chore_info[const.DATA_CHORE_LAST_COMPLETED] = now_iso

            if points_awarded is not None:
                self.update_kid_points(
                    kid_id, delta=points_awarded, source=const.POINTS_SOURCE_CHORES
                )
            # Queue filter removed - pending approvals now computed from timestamps
            self._pending_chore_changed = True

        elif new_state == const.CHORE_STATE_PENDING:
            # Remove the chore from claimed, approved, and completed_by_other lists.
            # Clear from completed_by_other list
            completed_by_other = kid_info.get(
                const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
            )
            kid_info[const.DATA_KID_COMPLETED_BY_OTHER_CHORES] = [  # type: ignore[typeddict-item]
                c for c in completed_by_other if c != chore_id
            ]

            # NOTE: last_approved is intentionally NEVER removed - it's for historical
            # tracking. Period-based approval validation uses approval_period_start
            # to determine if approval is valid for the current period.
            # is_approved_in_current_period() checks: last_approved >= approval_period_start

            # Only reset approval_period_start during scheduled resets (midnight, due date)
            # NOT during disapproval - disapproval only affects that kid's pending claim
            if reset_approval_period:
                now_iso = dt_util.utcnow().isoformat()
                kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
                completion_criteria = chore_info.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
                )
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # INDEPENDENT: Store per-kid approval_period_start in kid_chore_data
                    if chore_id not in kid_chores_data:
                        self._update_chore_data_for_kid(kid_id, chore_id, 0.0)
                    kid_chore_data_entry = kid_chores_data[chore_id]
                    kid_chore_data_entry[
                        const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
                    ] = now_iso
                else:
                    # SHARED/SHARED_FIRST: Store at chore level
                    chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso

                # Clear claimed_by and completed_by for all assigned kids
                # These fields represent current approval period state, not historical
                self._clear_chore_claimed_completed_by(chore_id)

            # Queue filter removed - pending approvals now computed from timestamps
            self._pending_chore_changed = True

        elif new_state == const.CHORE_STATE_OVERDUE:
            # Overdue state is now tracked via DATA_KID_CHORE_DATA_STATE
            # (set by _update_chore_data_for_kid above)
            pass

        elif new_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            # SHARED_FIRST: This kid didn't complete the chore, another kid did
            # Clear last_claimed in kid_chore_data (v0.4.0+ timestamp-based tracking)
            # NOTE: last_approved is intentionally NEVER removed - historical tracking
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            if chore_id in kid_chores_data:
                kid_chores_data[chore_id].pop(
                    const.DATA_KID_CHORE_DATA_LAST_CLAIMED, None
                )

            # State is now tracked via DATA_KID_CHORE_DATA_STATE (set above)
            # Add to completed_by_other list to track this state
            completed_by_other = kid_info.setdefault(
                const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
            )  # type: ignore[typeddict-item]
            if chore_id not in completed_by_other:
                completed_by_other.append(chore_id)

        # Compute and update the chore's global state.
        # Given the process above is handling everything properly for each kid, computing the global state straightforward.
        # This process needs run every time a chore state changes, so it no longer warrants a separate function.
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)  # type: ignore[assignment,call-overload,operator]

        if len(assigned_kids) == 1:
            # if only one kid is assigned to the chore, update the chore state to new state 1:1
            chore_info[const.DATA_CHORE_STATE] = new_state
        elif len(assigned_kids) > 1:
            # For chores assigned to multiple kids, you have to figure out the global state
            count_pending = count_claimed = count_approved = count_overdue = (
                const.DEFAULT_ZERO
            )
            count_completed_by_other = const.DEFAULT_ZERO
            for kid_id_iter in assigned_kids:
                kid_info_iter: KidData = cast(
                    "KidData", self.kids_data.get(kid_id_iter, {})
                )

                # For SHARED_FIRST: claims always win over overdue
                # Once someone claims, they're "claimed", others are "completed_by_other"
                # Overdue only applies when NO ONE has claimed yet
                if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                    if self.is_approved_in_current_period(kid_id_iter, chore_id):
                        count_approved += 1
                    elif self.has_pending_claim(kid_id_iter, chore_id):
                        count_claimed += 1
                    elif chore_id in kid_info_iter.get(
                        const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
                    ):
                        count_completed_by_other += 1
                    elif self.is_overdue(kid_id_iter, chore_id):
                        count_overdue += 1
                    else:
                        count_pending += 1
                # For non-SHARED_FIRST: original priority (overdue checked first)
                elif self.is_overdue(kid_id_iter, chore_id):
                    count_overdue += 1
                elif self.is_approved_in_current_period(kid_id_iter, chore_id):
                    count_approved += 1
                elif self.has_pending_claim(kid_id_iter, chore_id):
                    count_claimed += 1
                elif chore_id in kid_info_iter.get(
                    const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
                ):
                    count_completed_by_other += 1
                else:
                    count_pending += 1
            total = len(assigned_kids)

            # If all kids are in the same state, update the chore state to new state 1:1
            if total in (count_pending, count_claimed, count_approved, count_overdue):
                chore_info[const.DATA_CHORE_STATE] = new_state

            # For SHARED_FIRST chores, global state follows the single claimant's state
            # Other kids are in completed_by_other state but don't affect progression
            elif (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED_FIRST
            ):
                # SHARED_FIRST: global state tracks the claimant's progression
                # Once any kid claims/approves, their state drives the global state
                # Other kids' states (pending/overdue/completed_by_other) don't affect it
                if count_approved > const.DEFAULT_ZERO:
                    # Someone completed it - chore is done
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED
                elif count_claimed > const.DEFAULT_ZERO:
                    # Someone claimed it - waiting for approval
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED
                elif count_overdue > const.DEFAULT_ZERO:
                    # No one claimed yet, chore is overdue
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
                else:
                    # No one claimed yet, chore is pending
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING

            # For shared chores, recompute global state of a partial if they aren't all in the same state as checked above
            elif (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED
            ):
                if count_overdue > const.DEFAULT_ZERO:
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
                elif count_approved > const.DEFAULT_ZERO:
                    chore_info[const.DATA_CHORE_STATE] = (
                        const.CHORE_STATE_APPROVED_IN_PART
                    )
                elif count_claimed > const.DEFAULT_ZERO:
                    chore_info[const.DATA_CHORE_STATE] = (
                        const.CHORE_STATE_CLAIMED_IN_PART
                    )
                else:
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN

            # For independent chores assigned to multiple kids, set state to INDEPENDENT if not all in same state
            else:
                chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_INDEPENDENT

        else:
            chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN

        if debug_enabled:
            const.LOGGER.debug(
                "DEBUG: Chore State - Chore ID '%s' Global State changed to '%s'",
                chore_id,
                chore_info[const.DATA_CHORE_STATE],
            )

    def _update_chore_data_for_kid(
        self,
        kid_id: str,
        chore_id: str,
        points_awarded: float,
        *,
        state: str | None = None,
        due_date: str | None = None,
        skip_stats: bool = False,
    ):
        """
        Update a kid's chore data when a state change or completion occurs.

        Args:
            kid_id: The ID of the kid
            chore_id: The ID of the chore
            points_awarded: Points awarded for this chore
            state: New chore state (if state is changing)
            due_date: New due date (if due date is changing)
            skip_stats: If True, skip disapproval stat tracking (for kid undo).
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # Get chore name for reference
        chore_info: ChoreData = cast("ChoreData", self.chores_data.get(chore_id, {}))
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)

        # Initialize chore data structure if needed
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})

        # Initialize this chore's data if it doesn't exist yet
        kid_chore_data = kid_chores_data.setdefault(
            chore_id,
            {
                const.DATA_KID_CHORE_DATA_NAME: chore_name,
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
                const.DATA_KID_CHORE_DATA_LAST_CLAIMED: "",
                const.DATA_KID_CHORE_DATA_LAST_APPROVED: "",
                const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED: "",
                const.DATA_KID_CHORE_DATA_LAST_OVERDUE: "",
                const.DATA_KID_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME: 0,
                const.DATA_KID_CHORE_DATA_PERIODS: {
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_YEARLY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME: {},
                },
                const.DATA_KID_CHORE_DATA_BADGE_REFS: [],
            },
        )

        # --- Use a consistent default dict for all period stats ---
        period_default = {
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
            const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
        }

        # Get period keys using constants
        now_utc = dt_util.utcnow()
        now_iso = now_utc.isoformat()
        now_local = kh.get_now_local_time()
        today_local = kh.get_today_local_date()
        today_local_iso = today_local.isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        # For updating period stats - use setdefault to handle partial structures
        periods_data = kid_chore_data.setdefault(
            const.DATA_KID_CHORE_DATA_PERIODS,
            {  # type: ignore[typeddict-item]
                const.DATA_KID_CHORE_DATA_PERIODS_DAILY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_YEARLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME: {},
            },
        )
        period_keys = [
            (const.DATA_KID_CHORE_DATA_PERIODS_DAILY, today_local_iso),
            (const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY, week_local_iso),
            (const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, month_local_iso),
            (const.DATA_KID_CHORE_DATA_PERIODS_YEARLY, year_local_iso),
            (const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, const.PERIOD_ALL_TIME),
        ]

        previous_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
        points_awarded = (
            round(points_awarded, const.DATA_FLOAT_PRECISION)
            if points_awarded is not None
            else 0.0
        )

        # --- All-time stats update helpers ---
        chore_stats = kid_info.setdefault(const.DATA_KID_CHORE_STATS, {})  # type: ignore[typeddict-item]

        def inc_stat(key, amount):
            chore_stats[key] = chore_stats.get(key, 0) + amount

        # Helper to update period stats safely for all periods
        def update_periods(increments: dict, periods: list):
            for period_key, period_id in periods:
                period_data_dict = periods_data[period_key].setdefault(
                    period_id, period_default.copy()
                )
                for key, val in period_default.items():
                    period_data_dict.setdefault(key, val)
                for inc_key, inc_val in increments.items():
                    period_data_dict[inc_key] += inc_val

        if state is not None:
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = state

            # --- Handle CLAIMED state ---
            if state == const.CHORE_STATE_CLAIMED:
                kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = now_iso
                update_periods(
                    {const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 1},
                    period_keys,
                )
                # Increment all-time claimed count
                inc_stat(const.DATA_KID_CHORE_STATS_CLAIMED_ALL_TIME, 1)

            # --- Handle APPROVED state ---
            elif state == const.CHORE_STATE_APPROVED:
                # Deprecated counters removed - using chore_stats only

                kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso

                inc_stat(const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, 1)
                inc_stat(
                    const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_ALL_TIME,
                    points_awarded,
                )

                # Update period stats for count and points
                update_periods(
                    {
                        const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 1,
                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS: points_awarded,
                    },
                    period_keys,
                )

                # Calculate today's streak based on yesterday's daily period data
                yesterday_local_iso = kh.adjust_datetime_by_interval(
                    today_local_iso,
                    interval_unit=const.TIME_UNIT_DAYS,
                    delta=-1,
                    require_future=False,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )
                yesterday_chore_data = periods_data[
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY
                ].get(yesterday_local_iso, {})  # type: ignore[union-attr]
                yesterday_streak = yesterday_chore_data.get(
                    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                )
                today_streak = yesterday_streak + 1 if yesterday_streak > 0 else 1

                # Store today's streak as the daily longest streak
                daily_data = periods_data.get(
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                ).setdefault(today_local_iso, period_default.copy())  # type: ignore[union-attr]
                daily_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = (
                    today_streak
                )

                # --- All-time longest streak update (per-chore and per-kid) ---
                all_time_data = periods_data.get(
                    const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
                ).setdefault(const.PERIOD_ALL_TIME, period_default.copy())  # type: ignore[union-attr]
                prev_all_time_streak = all_time_data.get(
                    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                )
                if today_streak > prev_all_time_streak:
                    all_time_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = (
                        today_streak
                    )
                    kid_chore_data[
                        const.DATA_KID_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME
                    ] = today_local_iso  # type: ignore[typeddict-item]

                # Update streak for higher periods if needed (excluding all_time, already handled above)
                for period_key, period_id in [
                    (const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY, week_local_iso),
                    (const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, month_local_iso),
                    (const.DATA_KID_CHORE_DATA_PERIODS_YEARLY, year_local_iso),
                ]:
                    period_dict = periods_data.get(period_key, {})  # type: ignore[literal-required]
                    period_data_dict = period_dict.setdefault(
                        period_id, period_default.copy()
                    )  # type: ignore[union-attr]
                    if today_streak > period_data_dict.get(
                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                    ):
                        period_data_dict[
                            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
                        ] = today_streak

                # Still update the kid's global all-time longest streak if this is a new record
                longest_streak_all_time = chore_stats.get(
                    const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME, 0
                )
                if today_streak > longest_streak_all_time:
                    chore_stats[const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME] = (
                        today_streak
                    )

            # --- Handle OVERDUE state ---
            elif state == const.CHORE_STATE_OVERDUE:
                kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_OVERDUE] = now_iso
                daily_bucket = periods_data.get(
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                )
                daily_data = daily_bucket.setdefault(
                    today_local_iso,
                    period_default.copy(),  # type: ignore[arg-type]
                )
                for key, val in period_default.items():
                    daily_data.setdefault(key, val)  # type: ignore[literal-required]
                first_overdue_today = (
                    daily_data.get(const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0) < 1
                )
                if first_overdue_today:
                    daily_data[const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE] = 1
                    # Only increment higher periods if this is the first overdue for today
                    update_periods(
                        {const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 1},
                        period_keys[1:],  # skip daily
                    )
                    inc_stat(const.DATA_KID_CHORE_STATS_OVERDUE_ALL_TIME, 1)

            # --- Handle DISAPPROVED (claimed -> pending) state ---
            elif (
                state == const.CHORE_STATE_PENDING
                and previous_state == const.CHORE_STATE_CLAIMED
            ):
                # Only track disapproval stats if skip_stats is False (parent/admin disapproval)
                if not skip_stats:
                    kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = now_iso
                    daily_bucket_d = periods_data.get(
                        const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                    )
                    daily_data = daily_bucket_d.setdefault(
                        today_local_iso,
                        period_default.copy(),  # type: ignore[arg-type]
                    )
                    for key, val in period_default.items():
                        daily_data.setdefault(key, val)  # type: ignore[literal-required]
                    first_disapproved_today = (
                        daily_data.get(const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0)
                        < 1
                    )
                    if first_disapproved_today:
                        daily_data[const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED] = 1
                        update_periods(
                            {const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 1},
                            period_keys[1:],  # skip daily
                        )
                        inc_stat(const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME, 1)

        # Clean up old period data to keep storage manageable
        kh.cleanup_period_data(
            self,
            periods_data=periods_data,  # type: ignore[arg-type]
            period_keys={
                const.FREQUENCY_DAILY: const.DATA_KID_CHORE_DATA_PERIODS_DAILY,
                const.FREQUENCY_WEEKLY: const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY,
                const.FREQUENCY_MONTHLY: const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY,
                const.FREQUENCY_YEARLY: const.DATA_KID_CHORE_DATA_PERIODS_YEARLY,
            },
            retention_daily=self.config_entry.options.get(
                const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
            ),
            retention_weekly=self.config_entry.options.get(
                const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
            ),
            retention_monthly=self.config_entry.options.get(
                const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
            ),
            retention_yearly=self.config_entry.options.get(
                const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
            ),
        )

        # --- Update kid_chore_stats after all per-chore updates ---
        self._recalculate_chore_stats_for_kid(kid_id)

    def _recalculate_chore_stats_for_kid(self, kid_id: str):
        """Aggregate and update all kid_chore_stats for a given kid.

        This function always resets all stat keys to zero/default and then
        aggregates from the current state of all chore data. This ensures
        stats are never double-counted, even if this function is called
        multiple times per state change.

        Note: All-time stats (completed_all_time, total_points_all_time, longest_streak_all_time)
        must be stored incrementally and not reset here, since old period data may be pruned.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # --- Reset all stat keys (prevents double counting) Exception for All-time stats which are always kept and updated as necessary---
        # --- All-time stats could be calculated from individual chore all-time stats, but then deleted chore data would also need to be stored.
        stats = {
            const.DATA_KID_CHORE_STATS_APPROVED_TODAY: 0,
            const.DATA_KID_CHORE_STATS_APPROVED_WEEK: 0,
            const.DATA_KID_CHORE_STATS_APPROVED_MONTH: 0,
            const.DATA_KID_CHORE_STATS_APPROVED_YEAR: 0,
            # All-time stats are loaded from persistent storage, not recalculated
            const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME: kid_info.get(
                const.DATA_KID_CHORE_STATS, {}
            ).get(const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, 0),
            # --- Claimed counts ---
            const.DATA_KID_CHORE_STATS_CLAIMED_TODAY: 0,
            const.DATA_KID_CHORE_STATS_CLAIMED_WEEK: 0,
            const.DATA_KID_CHORE_STATS_CLAIMED_MONTH: 0,
            const.DATA_KID_CHORE_STATS_CLAIMED_YEAR: 0,
            # All-time stats are loaded from persistent storage, not recalculated
            const.DATA_KID_CHORE_STATS_CLAIMED_ALL_TIME: kid_info.get(
                const.DATA_KID_CHORE_STATS, {}
            ).get(const.DATA_KID_CHORE_STATS_CLAIMED_ALL_TIME, 0),
            # --- Overdue counts ---
            const.DATA_KID_CHORE_STATS_OVERDUE_TODAY: 0,
            const.DATA_KID_CHORE_STATS_OVERDUE_WEEK: 0,
            const.DATA_KID_CHORE_STATS_OVERDUE_MONTH: 0,
            const.DATA_KID_CHORE_STATS_OVERDUE_YEAR: 0,
            const.DATA_KID_CHORE_STATS_OVERDUE_ALL_TIME: kid_info.get(
                const.DATA_KID_CHORE_STATS, {}
            ).get(const.DATA_KID_CHORE_STATS_OVERDUE_ALL_TIME, 0),
            # --- Disapproved counts ---
            const.DATA_KID_CHORE_STATS_DISAPPROVED_TODAY: 0,
            const.DATA_KID_CHORE_STATS_DISAPPROVED_WEEK: 0,
            const.DATA_KID_CHORE_STATS_DISAPPROVED_MONTH: 0,
            const.DATA_KID_CHORE_STATS_DISAPPROVED_YEAR: 0,
            # All-time stats are loaded from persistent storage, not recalculated
            const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME: kid_info.get(
                const.DATA_KID_CHORE_STATS, {}
            ).get(const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME, 0),
            # --- Longest streaks ---
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_WEEK: 0,
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_MONTH: 0,
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_YEAR: 0,
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME: kid_info.get(
                const.DATA_KID_CHORE_STATS, {}
            ).get(const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME, 0),
            # --- Most completed chore ---
            const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_ALL_TIME: None,
            const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_WEEK: None,
            const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_MONTH: None,
            const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_YEAR: None,
            # --- Total points from chores ---
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_TODAY: 0.0,
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_WEEK: 0.0,
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_MONTH: 0.0,
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_YEAR: 0.0,
            # All-time stats are loaded from persistent storage, not recalculated
            const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_ALL_TIME: kid_info.get(
                const.DATA_KID_CHORE_STATS, {}
            ).get(const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_ALL_TIME, 0.0),
            # --- Average points per day ---
            const.DATA_KID_CHORE_STATS_AVG_PER_DAY_WEEK: 0.0,
            const.DATA_KID_CHORE_STATS_AVG_PER_DAY_MONTH: 0.0,
            # --- Current status stats ---
            const.DATA_KID_CHORE_STATS_CURRENT_DUE_TODAY: 0,
            const.DATA_KID_CHORE_STATS_CURRENT_OVERDUE: 0,
            const.DATA_KID_CHORE_STATS_CURRENT_CLAIMED: 0,
            const.DATA_KID_CHORE_STATS_CURRENT_APPROVED: 0,
        }

        # Get current period keys
        now_local = kh.get_now_local_time()
        today_local_iso = kh.get_today_local_date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        # For most completed chore
        most_completed = {}
        most_completed_week = {}
        most_completed_month = {}
        most_completed_year = {}

        # For longest streaks
        max_streak_week = 0
        max_streak_month = 0
        max_streak_year = 0

        # --- Aggregate stats from all chores (no double counting) ---
        for chore_id, chore_data in kid_info.get(const.DATA_KID_CHORE_DATA, {}).items():
            # All-time stats are incremented at event time, not recalculated here

            # Period stats
            periods = chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})

            # Most completed chore (all time)
            all_time = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
            total_count = all_time.get(const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0)
            most_completed[chore_id] = total_count

            # Daily
            daily = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})
            today_stats = daily.get(today_local_iso, {})
            stats[const.DATA_KID_CHORE_STATS_APPROVED_TODAY] += today_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_TODAY] += (  # type: ignore[assignment,call-overload,operator]
                today_stats.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0.0)
            )
            stats[const.DATA_KID_CHORE_STATS_OVERDUE_TODAY] += today_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0
            )
            stats[const.DATA_KID_CHORE_STATS_DISAPPROVED_TODAY] += today_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_CLAIMED_TODAY] += today_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )

            # Weekly
            weekly = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY, {})
            week_stats = weekly.get(week_local_iso, {})
            stats[const.DATA_KID_CHORE_STATS_APPROVED_WEEK] += week_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_WEEK] += (  # type: ignore[assignment,call-overload,operator]
                week_stats.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0.0)
            )
            stats[const.DATA_KID_CHORE_STATS_OVERDUE_WEEK] += week_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0
            )
            stats[const.DATA_KID_CHORE_STATS_DISAPPROVED_WEEK] += week_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_CLAIMED_WEEK] += week_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            most_completed_week[chore_id] = week_stats.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            max_streak_week = max(
                max_streak_week,
                week_stats.get(const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0),
            )

            # Monthly
            monthly = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, {})
            month_stats = monthly.get(month_local_iso, {})
            stats[const.DATA_KID_CHORE_STATS_APPROVED_MONTH] += month_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_MONTH] += (  # type: ignore[assignment,call-overload,operator]
                month_stats.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0.0)
            )
            stats[const.DATA_KID_CHORE_STATS_OVERDUE_MONTH] += month_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0
            )
            stats[const.DATA_KID_CHORE_STATS_DISAPPROVED_MONTH] += month_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_CLAIMED_MONTH] += month_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            most_completed_month[chore_id] = month_stats.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            max_streak_month = max(
                max_streak_month,
                month_stats.get(const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0),
            )

            # Yearly
            yearly = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_YEARLY, {})
            year_stats = yearly.get(year_local_iso, {})
            stats[const.DATA_KID_CHORE_STATS_APPROVED_YEAR] += year_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_YEAR] += (  # type: ignore[assignment,call-overload,operator]
                year_stats.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0.0)
            )
            stats[const.DATA_KID_CHORE_STATS_OVERDUE_YEAR] += year_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0
            )
            stats[const.DATA_KID_CHORE_STATS_DISAPPROVED_YEAR] += year_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0
            )
            stats[const.DATA_KID_CHORE_STATS_CLAIMED_YEAR] += year_stats.get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            most_completed_year[chore_id] = year_stats.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            max_streak_year = max(
                max_streak_year,
                year_stats.get(const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0),
            )

            # --- Current status counts ---
            state = chore_data.get(const.DATA_KID_CHORE_DATA_STATE)

            # Get due date based on completion_criteria:
            # - INDEPENDENT: read from per_kid_due_dates (source of truth)
            # - SHARED_*: read from chore-level due_date
            chore_info: ChoreData = cast(
                "ChoreData", self.chores_data.get(chore_id, {})
            )
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,  # Default for legacy
            )
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_datetime_iso = per_kid_due_dates.get(kid_id)
            else:
                # SHARED_ALL, SHARED_FIRST, ALTERNATING
                due_datetime_iso = chore_info.get(const.DATA_CHORE_DUE_DATE)

            if not due_datetime_iso:
                continue

            due_date_local = kh.normalize_datetime_input(
                due_datetime_iso, return_type=const.HELPER_RETURN_DATETIME_LOCAL
            )
            if due_date_local:
                try:
                    today_local = kh.get_today_local_date()
                    # due_date_local is a datetime, convert to date for comparison
                    if (
                        isinstance(due_date_local, datetime)
                        and due_date_local.date() == today_local
                    ):
                        stats[const.DATA_KID_CHORE_STATS_CURRENT_DUE_TODAY] += 1  # type: ignore[assignment,call-overload,operator]
                except (AttributeError, TypeError):
                    pass
            if state == const.CHORE_STATE_OVERDUE:
                stats[const.DATA_KID_CHORE_STATS_CURRENT_OVERDUE] += 1  # type: ignore[assignment,call-overload,operator]
            elif state == const.CHORE_STATE_CLAIMED:
                stats[const.DATA_KID_CHORE_STATS_CURRENT_CLAIMED] += 1  # type: ignore[assignment,call-overload,operator]
            elif state in (
                const.CHORE_STATE_APPROVED,
                const.CHORE_STATE_APPROVED_IN_PART,
            ):
                stats[const.DATA_KID_CHORE_STATS_CURRENT_APPROVED] += 1  # type: ignore[assignment,call-overload,operator]

        # --- Derived stats (no double counting, just pick max or calculate) ---
        if most_completed:
            most_completed_chore_id = max(
                most_completed, key=lambda x: most_completed.get(x, 0)
            )
            chore_name = self.chores_data.get(most_completed_chore_id, {}).get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_CHORE_NAME, most_completed_chore_id
            )
            stats[const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_ALL_TIME] = chore_name
        if most_completed_week:
            most_completed_week_id = max(
                most_completed_week, key=lambda x: most_completed_week.get(x, 0)
            )
            chore_name = self.chores_data.get(most_completed_week_id, {}).get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_CHORE_NAME, most_completed_week_id
            )
            stats[const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_WEEK] = chore_name
        if most_completed_month:
            most_completed_month_id = max(
                most_completed_month, key=lambda x: most_completed_month.get(x, 0)
            )
            chore_name = self.chores_data.get(most_completed_month_id, {}).get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_CHORE_NAME, most_completed_month_id
            )
            stats[const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_MONTH] = chore_name
        if most_completed_year:
            most_completed_year_id = max(
                most_completed_year, key=lambda x: most_completed_year.get(x, 0)
            )
            chore_name = self.chores_data.get(most_completed_year_id, {}).get(  # type: ignore[assignment,call-overload,operator]
                const.DATA_CHORE_NAME, most_completed_year_id
            )
            stats[const.DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_YEAR] = chore_name

        stats[const.DATA_KID_CHORE_STATS_LONGEST_STREAK_WEEK] = max_streak_week
        stats[const.DATA_KID_CHORE_STATS_LONGEST_STREAK_MONTH] = max_streak_month
        stats[const.DATA_KID_CHORE_STATS_LONGEST_STREAK_YEAR] = max_streak_year

        # Averages (no double counting, just divide)
        stats[const.DATA_KID_CHORE_STATS_AVG_PER_DAY_WEEK] = round(
            (
                stats[const.DATA_KID_CHORE_STATS_APPROVED_WEEK] / 7.0  # type: ignore[assignment,call-overload,operator]
                if stats[const.DATA_KID_CHORE_STATS_APPROVED_WEEK]
                else 0.0
            ),
            const.DATA_FLOAT_PRECISION,
        )
        now = kh.get_now_local_time()
        days_in_month = monthrange(now.year, now.month)[1]
        stats[const.DATA_KID_CHORE_STATS_AVG_PER_DAY_MONTH] = round(
            (
                stats[const.DATA_KID_CHORE_STATS_APPROVED_MONTH] / days_in_month  # type: ignore[assignment,call-overload,operator]
                if stats[const.DATA_KID_CHORE_STATS_APPROVED_MONTH]
                else 0.0
            ),
            const.DATA_FLOAT_PRECISION,
        )

        # --- Save back to kid_info ---
        kid_info[const.DATA_KID_CHORE_STATS] = stats  # type: ignore[typeddict-item]

    # -------------------------------------------------------------------------------------
    # Kids: Update Points
    # -------------------------------------------------------------------------------------

    def update_kid_points(
        self, kid_id: str, delta: float, *, source: str = const.POINTS_SOURCE_OTHER
    ):
        """
        Adjust a kid's points by delta (±), track by-source, update legacy stats,
        record into new point_data history, then recheck badges/achievements/challenges.
        Also updates all-time and highest balance stats using constants.
        If the source is chores, applies the kid's multiplier.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "WARNING: Update Kid Points - Kid ID '%s' not found", kid_id
            )
            return

        # 1) Sanitize delta
        try:
            delta_value = round(float(delta), const.DATA_FLOAT_PRECISION)
        except (ValueError, TypeError):
            const.LOGGER.warning(
                "WARNING: Update Kid Points - Invalid delta '%s' for Kid ID '%s'.",
                delta,
                kid_id,
            )
            return
        if delta_value == 0:
            const.LOGGER.debug(
                "DEBUG: Update Kid Points - No change (delta=0) for Kid ID '%s'", kid_id
            )
            return

        # If source is chores, apply multiplier
        if source == const.POINTS_SOURCE_CHORES:
            multiplier = kid_info.get(const.DATA_KID_POINTS_MULTIPLIER, 1.0)
            delta_value = round(
                delta_value * float(multiplier), const.DATA_FLOAT_PRECISION
            )

        # 2) Compute new balance
        try:
            old = round(
                float(kid_info.get(const.DATA_KID_POINTS, 0.0)),
                const.DATA_FLOAT_PRECISION,
            )
        except (ValueError, TypeError):
            const.LOGGER.warning(
                "WARNING: Update Kid Points - Invalid old_points for Kid ID '%s'. Defaulting to 0.0.",
                kid_id,
            )
            old = 0.0
        new = old + delta_value
        kid_info[const.DATA_KID_POINTS] = new

        # 3) Legacy cumulative badge logic
        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        if delta_value > 0:
            cycle_points = progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0.0
            )
            cycle_points += delta_value
            progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = round(
                cycle_points, const.DATA_FLOAT_PRECISION
            )  # type: ignore[typeddict-item]

        # 5) All-time and highest balance stats (handled incrementally)
        point_stats = kid_info.setdefault(const.DATA_KID_POINT_STATS, {})  # type: ignore[typeddict-item]
        point_stats.setdefault(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_SPENT_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_NET_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME, {})
        point_stats.setdefault(const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0)

        if delta_value > 0:
            earned = point_stats.get(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0)
            point_stats[const.DATA_KID_POINT_STATS_EARNED_ALL_TIME] = round(
                earned + delta_value, const.DATA_FLOAT_PRECISION
            )  # type: ignore[typeddict-item]
        elif delta_value < 0:
            spent = point_stats.get(const.DATA_KID_POINT_STATS_SPENT_ALL_TIME, 0.0)
            point_stats[const.DATA_KID_POINT_STATS_SPENT_ALL_TIME] = round(
                spent + delta_value, const.DATA_FLOAT_PRECISION
            )  # type: ignore[typeddict-item]
        net = point_stats.get(const.DATA_KID_POINT_STATS_NET_ALL_TIME, 0.0)
        point_stats[const.DATA_KID_POINT_STATS_NET_ALL_TIME] = round(  # type: ignore[typeddict-item]
            net + delta_value, const.DATA_FLOAT_PRECISION
        )

        # 6) Record into new point_data history (use same date logic as chore_data)
        periods_data = kid_info.setdefault(const.DATA_KID_POINT_DATA, {}).setdefault(  # type: ignore[typeddict-item]
            const.DATA_KID_POINT_DATA_PERIODS, {}
        )

        now_local = kh.get_now_local_time()
        today_local_iso = kh.get_today_local_date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        for period_key, period_id in [
            (const.DATA_KID_POINT_DATA_PERIODS_DAILY, today_local_iso),
            (const.DATA_KID_POINT_DATA_PERIODS_WEEKLY, week_local_iso),
            (const.DATA_KID_POINT_DATA_PERIODS_MONTHLY, month_local_iso),
            (const.DATA_KID_POINT_DATA_PERIODS_YEARLY, year_local_iso),
        ]:
            bucket = periods_data.setdefault(period_key, {})
            entry = bucket.setdefault(period_id, {})
            # Safely initialize fields if missing
            if const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL not in entry:
                entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] = 0.0
            if (
                const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE not in entry
                or not isinstance(
                    entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE], dict
                )
            ):
                entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE] = {}
            entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] += delta_value
            entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL] = round(
                entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL],
                const.DATA_FLOAT_PRECISION,
            )
            entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE].setdefault(source, 0.0)
            entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] += delta_value
            entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] = round(
                entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source],
                const.DATA_FLOAT_PRECISION,
            )

        # 7) Re‑evaluate everything and persist
        # Note: Call _recalculate_point_stats_for_kid BEFORE updating all-time stats
        # so that it preserves the incrementally-tracked all-time values
        self._recalculate_point_stats_for_kid(kid_id)

        # 8) Update all-time by-source stats (must be done AFTER recalculate to avoid being overwritten)
        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})  # type: ignore[typeddict-item]
        by_source_all_time = point_stats.get(
            const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME, {}
        )  # type: ignore[typeddict-item]
        by_source_all_time.setdefault(source, 0.0)
        by_source_all_time[source] += delta_value
        by_source_all_time[source] = round(
            by_source_all_time[source], const.DATA_FLOAT_PRECISION
        )

        highest = point_stats.get(const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0)
        point_stats[const.DATA_KID_POINT_STATS_HIGHEST_BALANCE] = max(  # type: ignore[typeddict-item]
            highest, new
        )
        kh.cleanup_period_data(
            self,
            periods_data=periods_data,
            period_keys={
                "daily": const.DATA_KID_POINT_DATA_PERIODS_DAILY,
                "weekly": const.DATA_KID_POINT_DATA_PERIODS_WEEKLY,
                "monthly": const.DATA_KID_POINT_DATA_PERIODS_MONTHLY,
                "yearly": const.DATA_KID_POINT_DATA_PERIODS_YEARLY,
            },
            retention_daily=self.config_entry.options.get(
                const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
            ),
            retention_weekly=self.config_entry.options.get(
                const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
            ),
            retention_monthly=self.config_entry.options.get(
                const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
            ),
            retention_yearly=self.config_entry.options.get(
                const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
            ),
        )
        self._check_badges_for_kid(kid_id)
        self._check_achievements_for_kid(kid_id)
        self._check_challenges_for_kid(kid_id)

        self._persist()
        self.async_set_updated_data(self._data)

        const.LOGGER.debug(
            "DEBUG: Update Kid Points - Kid ID '%s': delta=%.2f, old=%.2f, new=%.2f, source=%s",
            kid_id,
            delta_value,
            old,
            new,
            source,
        )

    def _recalculate_point_stats_for_kid(self, kid_id: str):
        """Aggregate and update all kid_point_stats for a given kid.

        This function always resets all stat keys to zero/default and then
        aggregates from the current state of all point data. This ensures
        stats are never double-counted, even if this function is called
        multiple times per state change.

        Note: All-time stats (earned_all_time, spent_all_time, net_all_time, by_source_all_time, highest_balance)
        must be stored incrementally and not reset here, since old period data may be pruned.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})

        stats = {
            # Per-period stats
            const.DATA_KID_POINT_STATS_EARNED_TODAY: 0.0,
            const.DATA_KID_POINT_STATS_EARNED_WEEK: 0.0,
            const.DATA_KID_POINT_STATS_EARNED_MONTH: 0.0,
            const.DATA_KID_POINT_STATS_EARNED_YEAR: 0.0,
            # All-time stats (handled incrementally in update_kid_points, not recalculated here)
            const.DATA_KID_POINT_STATS_EARNED_ALL_TIME: point_stats.get(
                const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0
            ),
            # By-source breakdowns
            const.DATA_KID_POINT_STATS_BY_SOURCE_TODAY: {},
            const.DATA_KID_POINT_STATS_BY_SOURCE_WEEK: {},
            const.DATA_KID_POINT_STATS_BY_SOURCE_MONTH: {},
            const.DATA_KID_POINT_STATS_BY_SOURCE_YEAR: {},
            # All-time by-source (handled incrementally)
            const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME: point_stats.get(  # type: ignore[attr-defined]
                const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME, {}
            ).copy(),
            # Spent (negative deltas)
            const.DATA_KID_POINT_STATS_SPENT_TODAY: 0.0,
            const.DATA_KID_POINT_STATS_SPENT_WEEK: 0.0,
            const.DATA_KID_POINT_STATS_SPENT_MONTH: 0.0,
            const.DATA_KID_POINT_STATS_SPENT_YEAR: 0.0,
            # All-time spent (handled incrementally)
            const.DATA_KID_POINT_STATS_SPENT_ALL_TIME: point_stats.get(
                const.DATA_KID_POINT_STATS_SPENT_ALL_TIME, 0.0
            ),
            # Net (earned - spent)
            const.DATA_KID_POINT_STATS_NET_TODAY: 0.0,
            const.DATA_KID_POINT_STATS_NET_WEEK: 0.0,
            const.DATA_KID_POINT_STATS_NET_MONTH: 0.0,
            const.DATA_KID_POINT_STATS_NET_YEAR: 0.0,
            # All-time net (This is calculated even though it is an all time stat)
            const.DATA_KID_POINT_STATS_NET_ALL_TIME: 0.0,
            # Highest balance ever (handled incrementally)
            const.DATA_KID_POINT_STATS_HIGHEST_BALANCE: point_stats.get(
                const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0
            ),
            # Averages (calculated below)
            const.DATA_KID_POINT_STATS_AVG_PER_DAY_WEEK: 0.0,
            const.DATA_KID_POINT_STATS_AVG_PER_DAY_MONTH: 0.0,
            # Streaks and avg per chore are optional, not implemented here
            # const.DATA_KID_POINT_STATS_EARNING_STREAK_CURRENT: 0,
            # const.DATA_KID_POINT_STATS_EARNING_STREAK_LONGEST: 0,
            # const.DATA_KID_POINT_STATS_AVG_PER_CHORE: 0.0,
        }

        pts_periods = kid_info.get(const.DATA_KID_POINT_DATA, {}).get(  # type: ignore[attr-defined]
            const.DATA_KID_POINT_DATA_PERIODS, {}
        )

        now_local = kh.get_now_local_time()
        today_local_iso = kh.get_today_local_date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        def get_period(period_key, period_id):
            period = pts_periods.get(period_key, {})
            entry = period.get(period_id, {})
            by_source = entry.get(const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE, {})
            earned = round(
                sum(v for v in by_source.values() if v > 0),
                const.DATA_FLOAT_PRECISION,
            )
            spent = round(
                sum(v for v in by_source.values() if v < 0),
                const.DATA_FLOAT_PRECISION,
            )
            net = round(
                entry.get(const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            return earned, spent, net, by_source.copy()

        # Daily
        earned, spent, net, by_source = get_period(
            const.DATA_KID_POINT_DATA_PERIODS_DAILY, today_local_iso
        )
        stats[const.DATA_KID_POINT_STATS_EARNED_TODAY] = earned
        stats[const.DATA_KID_POINT_STATS_SPENT_TODAY] = spent
        stats[const.DATA_KID_POINT_STATS_NET_TODAY] = net
        stats[const.DATA_KID_POINT_STATS_BY_SOURCE_TODAY] = by_source

        # Weekly
        earned, spent, net, by_source = get_period(
            const.DATA_KID_POINT_DATA_PERIODS_WEEKLY, week_local_iso
        )
        stats[const.DATA_KID_POINT_STATS_EARNED_WEEK] = earned
        stats[const.DATA_KID_POINT_STATS_SPENT_WEEK] = spent
        stats[const.DATA_KID_POINT_STATS_NET_WEEK] = net
        stats[const.DATA_KID_POINT_STATS_BY_SOURCE_WEEK] = by_source

        # Monthly
        earned, spent, net, by_source = get_period(
            const.DATA_KID_POINT_DATA_PERIODS_MONTHLY, month_local_iso
        )
        stats[const.DATA_KID_POINT_STATS_EARNED_MONTH] = earned
        stats[const.DATA_KID_POINT_STATS_SPENT_MONTH] = spent
        stats[const.DATA_KID_POINT_STATS_NET_MONTH] = net
        stats[const.DATA_KID_POINT_STATS_BY_SOURCE_MONTH] = by_source

        # Yearly
        earned, spent, net, by_source = get_period(
            const.DATA_KID_POINT_DATA_PERIODS_YEARLY, year_local_iso
        )
        stats[const.DATA_KID_POINT_STATS_EARNED_YEAR] = earned
        stats[const.DATA_KID_POINT_STATS_SPENT_YEAR] = spent
        stats[const.DATA_KID_POINT_STATS_NET_YEAR] = net
        stats[const.DATA_KID_POINT_STATS_BY_SOURCE_YEAR] = by_source

        # --- All-time Net stats ---
        stats[const.DATA_KID_POINT_STATS_NET_ALL_TIME] = round(
            stats[const.DATA_KID_POINT_STATS_EARNED_ALL_TIME]
            + stats[const.DATA_KID_POINT_STATS_SPENT_ALL_TIME],
            const.DATA_FLOAT_PRECISION,
        )

        # --- Averages ---
        stats[const.DATA_KID_POINT_STATS_AVG_PER_DAY_WEEK] = (
            round(
                stats[const.DATA_KID_POINT_STATS_EARNED_WEEK] / 7.0,
                const.DATA_FLOAT_PRECISION,
            )
            if stats[const.DATA_KID_POINT_STATS_EARNED_WEEK]
            else 0.0
        )
        now = kh.get_now_local_time()
        days_in_month = monthrange(now.year, now.month)[1]
        stats[const.DATA_KID_POINT_STATS_AVG_PER_DAY_MONTH] = (
            round(
                stats[const.DATA_KID_POINT_STATS_EARNED_MONTH] / days_in_month,
                const.DATA_FLOAT_PRECISION,
            )
            if stats[const.DATA_KID_POINT_STATS_EARNED_MONTH]
            else 0.0
        )

        # --- Save back to kid_info ---
        kid_info[const.DATA_KID_POINT_STATS] = stats  # type: ignore[typeddict-item]

    # -------------------------------------------------------------------------------------
    # Rewards: Redeem, Approve, Disapprove
    # -------------------------------------------------------------------------------------

    def redeem_reward(self, parent_name: str, kid_id: str, reward_id: str):
        """Kid claims a reward => mark as pending approval (no deduction yet)."""
        reward_info: RewardData | None = self.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_ZERO)
        if kid_info[const.DATA_KID_POINTS] < cost:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                translation_placeholders={
                    "kid": kid_info[const.DATA_KID_NAME],
                    "current": str(kid_info[const.DATA_KID_POINTS]),
                    "required": str(cost),
                },
            )

        # Update kid_reward_data structure
        reward_entry = self._get_kid_reward_data(kid_id, reward_id, create=True)
        reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = (
            reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) + 1
        )
        reward_entry[const.DATA_KID_REWARD_DATA_LAST_CLAIMED] = (
            dt_util.utcnow().isoformat()
        )
        reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS] = (
            reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS, 0) + 1
        )

        # Update period-based tracking for claimed
        self._increment_reward_period_counter(
            reward_entry, const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED
        )

        # Generate a unique notification ID for this claim.
        notif_id = uuid.uuid4().hex

        # Track notification ID for this claim
        reward_entry.setdefault(const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS, []).append(
            notif_id
        )

        # Send a notification to the parents using helpers (DRY refactor v0.5.0+)
        actions = build_reward_actions(kid_id, reward_id, notif_id)
        extra_data = build_extra_data(kid_id, reward_id=reward_id, notif_id=notif_id)
        self.hass.async_create_task(
            self._notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_PARENT,
                message_data={
                    "kid_name": kid_info[const.DATA_KID_NAME],
                    "reward_name": reward_info[const.DATA_REWARD_NAME],
                    "points": reward_info[const.DATA_REWARD_COST],
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(reward_id, kid_id),
            )
        )

        self._persist()
        self.async_set_updated_data(self._data)

    async def approve_reward(
        self,
        parent_name: str,  # Used for stale notification feedback
        kid_id: str,
        reward_id: str,
        notif_id: str | None = None,
    ):
        """Parent approves the reward => deduct points.

        Thread-safe implementation using asyncio.Lock to prevent race conditions
        when multiple parents click approve simultaneously (v0.5.0+).
        """
        # Acquire lock for this specific kid+reward combination to prevent race conditions
        lock = self._get_approval_lock("approve_reward", kid_id, reward_id)
        async with lock:
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            reward_info: RewardData | None = self.rewards_data.get(reward_id)
            if not reward_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_REWARD,
                        "name": reward_id,
                    },
                )

            cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_ZERO)

            # Get pending_count from kid_reward_data
            # Re-fetch inside lock for defensive race condition protection
            reward_entry = self._get_kid_reward_data(kid_id, reward_id, create=False)
            pending_count = reward_entry.get(
                const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0
            )

            if pending_count > 0:
                if kid_info[const.DATA_KID_POINTS] < cost:
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                        translation_placeholders={
                            "kid": kid_info[const.DATA_KID_NAME],
                            "current": str(kid_info[const.DATA_KID_POINTS]),
                            "required": str(cost),
                        },
                    )

                # Deduct points for one claim.
                if cost is not None:
                    self.update_kid_points(
                        kid_id, delta=-cost, source=const.POINTS_SOURCE_REWARDS
                    )

                # Update kid_reward_data structure
                if reward_entry:
                    reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = max(
                        0,
                        reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)
                        - 1,
                    )
                    reward_entry[const.DATA_KID_REWARD_DATA_LAST_APPROVED] = (
                        dt_util.utcnow().isoformat()
                    )
                    reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_APPROVED] = (
                        reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_APPROVED, 0)
                        + 1
                    )
                    reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT] = (
                        reward_entry.get(
                            const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT, 0
                        )
                        + cost
                    )

                    # Update period-based tracking for approved + points
                    self._increment_reward_period_counter(
                        reward_entry, const.DATA_KID_REWARD_DATA_PERIOD_APPROVED
                    )
                    self._increment_reward_period_counter(
                        reward_entry,
                        const.DATA_KID_REWARD_DATA_PERIOD_POINTS,
                        amount=int(cost),
                    )

                    # Remove notification ID if provided
                    if notif_id:
                        notif_ids = reward_entry.get(
                            const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS, []
                        )
                        if notif_id in notif_ids:
                            notif_ids.remove(notif_id)

                    # Cleanup old period data using retention settings
                    kh.cleanup_period_data(
                        self,
                        periods_data=reward_entry.get(
                            const.DATA_KID_REWARD_DATA_PERIODS, {}
                        ),
                        period_keys={
                            "daily": const.DATA_KID_REWARD_DATA_PERIODS_DAILY,
                            "weekly": const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY,
                            "monthly": const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY,
                            "yearly": const.DATA_KID_REWARD_DATA_PERIODS_YEARLY,
                        },
                        retention_daily=self.config_entry.options.get(
                            const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
                        ),
                        retention_weekly=self.config_entry.options.get(
                            const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
                        ),
                        retention_monthly=self.config_entry.options.get(
                            const.CONF_RETENTION_MONTHLY,
                            const.DEFAULT_RETENTION_MONTHLY,
                        ),
                        retention_yearly=self.config_entry.options.get(
                            const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
                        ),
                    )

            else:
                # Direct approval (no pending claim present).
                if kid_info[const.DATA_KID_POINTS] < cost:
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                        translation_placeholders={
                            "kid": kid_info[const.DATA_KID_NAME],
                            "current": str(kid_info[const.DATA_KID_POINTS]),
                            "required": str(cost),
                        },
                    )
                kid_info[const.DATA_KID_POINTS] -= cost

                # Update kid_reward_data structure for direct approval
                direct_entry = self._get_kid_reward_data(kid_id, reward_id, create=True)
                direct_entry[const.DATA_KID_REWARD_DATA_LAST_APPROVED] = (
                    dt_util.utcnow().isoformat()
                )
                direct_entry[const.DATA_KID_REWARD_DATA_TOTAL_APPROVED] = (
                    direct_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_APPROVED, 0) + 1
                )
                direct_entry[const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT] = (
                    direct_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT, 0)
                    + cost
                )

                # Update period-based tracking for approved + points
                self._increment_reward_period_counter(
                    direct_entry, const.DATA_KID_REWARD_DATA_PERIOD_APPROVED
                )
                self._increment_reward_period_counter(
                    direct_entry,
                    const.DATA_KID_REWARD_DATA_PERIOD_POINTS,
                    amount=int(cost),
                )

                # Cleanup old period data using retention settings
                kh.cleanup_period_data(
                    self,
                    periods_data=direct_entry.get(
                        const.DATA_KID_REWARD_DATA_PERIODS, {}
                    ),
                    period_keys={
                        "daily": const.DATA_KID_REWARD_DATA_PERIODS_DAILY,
                        "weekly": const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY,
                        "monthly": const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY,
                        "yearly": const.DATA_KID_REWARD_DATA_PERIODS_YEARLY,
                    },
                    retention_daily=self.config_entry.options.get(
                        const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
                    ),
                    retention_weekly=self.config_entry.options.get(
                        const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
                    ),
                    retention_monthly=self.config_entry.options.get(
                        const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
                    ),
                    retention_yearly=self.config_entry.options.get(
                        const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
                    ),
                )

            # Check badges
            self._check_badges_for_kid(kid_id)

            # Notify the kid that the reward has been approved
            extra_data = {const.DATA_KID_ID: kid_id, const.DATA_REWARD_ID: reward_id}
            self.hass.async_create_task(
                self._notify_kid_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED,
                    message_data={"reward_name": reward_info[const.DATA_REWARD_NAME]},
                    extra_data=extra_data,
                )
            )

            # Clear the original claim notification from parents' devices (v0.5.0+)
            self.hass.async_create_task(
                self.clear_notification_for_parents(
                    kid_id,
                    const.NOTIFY_TAG_TYPE_STATUS,
                    reward_id,
                )
            )

            self._persist()
            self.async_set_updated_data(self._data)

    def disapprove_reward(self, parent_name: str, kid_id: str, reward_id: str):
        """Disapprove a reward for kid_id."""

        reward_info: RewardData | None = self.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)

        # Update kid_reward_data structure
        if kid_info:
            reward_entry = self._get_kid_reward_data(kid_id, reward_id, create=False)
            if reward_entry:
                reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = max(
                    0, reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) - 1
                )
                reward_entry[const.DATA_KID_REWARD_DATA_LAST_DISAPPROVED] = (
                    dt_util.utcnow().isoformat()
                )
                reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED] = (
                    reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED, 0)
                    + 1
                )

                # Update period-based tracking for disapproved
                self._increment_reward_period_counter(
                    reward_entry, const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED
                )

        # Send a notification to the kid that reward was disapproved
        extra_data = {const.DATA_KID_ID: kid_id, const.DATA_REWARD_ID: reward_id}
        self.hass.async_create_task(
            self._notify_kid_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_DISAPPROVED,
                message_data={"reward_name": reward_info[const.DATA_REWARD_NAME]},
                extra_data=extra_data,
            )
        )

        # Clear the original claim notification from parents' devices (v0.5.0+)
        self.hass.async_create_task(
            self.clear_notification_for_parents(
                kid_id,
                const.NOTIFY_TAG_TYPE_STATUS,
                reward_id,
            )
        )

        self._persist()
        self.async_set_updated_data(self._data)

    def undo_reward_claim(self, kid_id: str, reward_id: str):
        """Allow kid to undo their own reward claim (no stat tracking).

        This method provides a way for kids to remove their pending reward claim
        without it counting as a disapproval. Similar to disapprove_reward but:
        - Does NOT track disapproval stats (no last_disapproved, no counters)
        - Does NOT send notifications (silent undo)
        - Only decrements pending_count

        Args:
            kid_id: The kid's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If kid or reward not found
        """
        reward_info: RewardData | None = self.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Update kid_reward_data structure - only decrement pending_count
        # Do NOT update last_disapproved, total_disapproved, or period counters
        reward_entry = self._get_kid_reward_data(kid_id, reward_id, create=False)
        if reward_entry:
            reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = max(
                0, reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) - 1
            )
            # Explicitly skip stat tracking - no last_disapproved, no total_disapproved, no period updates

        # No notification sent (silent undo)

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------------------
    # Badges: Check, Award
    # -------------------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    # Badge Data vs. Kid Badge Progress Data
    # -----------------------------------------------------------------------------
    # Badge data (badge_info): stores static configuration for each badge (name, type,
    # thresholds, tracked chores, reset schedule, etc.).
    # Kid badge progress data (progress): stores per-kid, per-badge progress (state,
    # cycle counts, points, start/end dates, etc.).
    # Always use badge data for config lookups and kid progress data for runtime state.
    # This separation ensures config changes are reflected and progress is tracked per kid.
    # -----------------------------------------------------------------------------

    def _check_badges_for_kid(self, kid_id: str):
        """Evaluate all badge thresholds for kid and update progress.

        This function:
        - Respects badge start/end dates.
        - Tracks daily progress and rolls it into the cycle count on day change.
        - Updates an overall progress field (DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS) for UI/logic.
        - Awards badges if criteria are met.
        """
        # PERF: Measure badge evaluation duration per kid
        perf_start = time.perf_counter()

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # Maintenance cycles to ensure badge progress is initialized and up-to-date
        self._manage_badge_maintenance(kid_id)
        self._manage_cumulative_badge_maintenance(kid_id)

        # OPTIMIZATION: Calculate today_local_iso once per kid instead of per badge
        today_local_iso = kh.get_today_local_iso()

        # OPTIMIZATION: Pre-compute kid's assigned chores once instead of per badge
        kid_assigned_chores = []
        for chore_id, chore_info in self.chores_data.items():
            chore_assigned_to = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if not chore_assigned_to or kid_id in chore_assigned_to:
                kid_assigned_chores.append(chore_id)

        # Mapping of target_type to handler and parameters
        target_type_handlers: dict[str, tuple[Any, dict[str, Any]]] = {
            const.BADGE_TARGET_THRESHOLD_TYPE_POINTS: (
                self._handle_badge_target_points,
                {},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES: (
                self._handle_badge_target_points,
                {const.BADGE_HANDLER_PARAM_FROM_CHORES_ONLY: True},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT: (
                self._handle_badge_target_chore_count,
                {},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES: (
                self._handle_badge_target_daily_completion,
                {const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 1.0},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES: (
                self._handle_badge_target_daily_completion,
                {const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 0.8},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES_NO_OVERDUE: (
                self._handle_badge_target_daily_completion,
                {
                    const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 1.0,
                    const.BADGE_HANDLER_PARAM_REQUIRE_NO_OVERDUE: True,
                },
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES: (
                self._handle_badge_target_daily_completion,
                {
                    const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 1.0,
                    const.BADGE_HANDLER_PARAM_ONLY_DUE_TODAY: True,
                },
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_DUE_CHORES: (
                self._handle_badge_target_daily_completion,
                {
                    const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 0.8,
                    const.BADGE_HANDLER_PARAM_ONLY_DUE_TODAY: True,
                },
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES_NO_OVERDUE: (
                self._handle_badge_target_daily_completion,
                {
                    const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 1.0,
                    const.BADGE_HANDLER_PARAM_ONLY_DUE_TODAY: True,
                    const.BADGE_HANDLER_PARAM_REQUIRE_NO_OVERDUE: True,
                },
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_3_CHORES: (
                self._handle_badge_target_daily_completion,
                {const.BADGE_HANDLER_PARAM_MIN_COUNT: 3},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES: (
                self._handle_badge_target_daily_completion,
                {const.BADGE_HANDLER_PARAM_MIN_COUNT: 5},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_7_CHORES: (
                self._handle_badge_target_daily_completion,
                {const.BADGE_HANDLER_PARAM_MIN_COUNT: 7},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES: (
                self._handle_badge_target_streak,
                {const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 1.0},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_CHORES: (
                self._handle_badge_target_streak,
                {const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 0.8},
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE: (
                self._handle_badge_target_streak,
                {
                    const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 1.0,
                    const.BADGE_HANDLER_PARAM_REQUIRE_NO_OVERDUE: True,
                },
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_DUE_CHORES: (
                self._handle_badge_target_streak,
                {
                    const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 0.8,
                    const.BADGE_HANDLER_PARAM_ONLY_DUE_TODAY: True,
                },
            ),
            const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_DUE_CHORES_NO_OVERDUE: (
                self._handle_badge_target_streak,
                {
                    const.BADGE_HANDLER_PARAM_PERCENT_REQUIRED: 1.0,
                    const.BADGE_HANDLER_PARAM_ONLY_DUE_TODAY: True,
                    const.BADGE_HANDLER_PARAM_REQUIRE_NO_OVERDUE: True,
                },
            ),
        }

        for badge_id, badge_info in self.badges_data.items():
            badge_type = badge_info.get(const.DATA_BADGE_TYPE)

            # Feature Change v4.2: Badges now require explicit assignment.
            # Empty assigned_to means badge is not assigned to any kid.
            assigned_to_list = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            is_assigned_to = kid_id in assigned_to_list
            if not is_assigned_to:
                continue

            # Note this process will only award a cumulative badge the first time.  Once
            # the badge is awarded, any future maintenance and awards associated with
            # maintenance periods will be handled by the _manage_cumulative_badge_maintenance
            # function.
            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                if kid_id in badge_info.get(const.DATA_BADGE_EARNED_BY, []):
                    # This badge has already been awarded, so skip it
                    continue

                cumulative_badge_progress = self._get_cumulative_badge_progress(kid_id)
                if cumulative_badge_progress:
                    stored_cumulative_badge_progress = self.kids_data[kid_id].get(
                        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
                    )
                    stored_cumulative_badge_progress.update(cumulative_badge_progress)  # type: ignore[typeddict-item]
                    self.kids_data[kid_id][  # type: ignore[typeddict-item]
                        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS
                    ] = stored_cumulative_badge_progress
                effective_badge_id = cumulative_badge_progress.get(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID, None
                )
                if effective_badge_id and effective_badge_id == badge_id:
                    # This badge matches with the calculated effective badge ID, so it should be awarded
                    progress = kid_info.get(  # type: ignore[typeddict-item]
                        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
                    )
                    try:
                        baseline_points = float(
                            progress.get(
                                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE,
                                const.DEFAULT_ZERO,
                            )
                        )
                        cycle_points = float(
                            progress.get(
                                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS,
                                const.DEFAULT_ZERO,
                            )
                        )
                    except (ValueError, TypeError) as err:
                        const.LOGGER.error(
                            "ERROR: Award Badge - Non-numeric values for cumulative points for kid '%s': %s",
                            kid_info.get(const.DATA_KID_NAME, kid_id),
                            err,
                        )
                        return
                    progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE] = (
                        baseline_points + cycle_points
                    )
                    progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = (
                        const.DEFAULT_ZERO
                    )

                    self._award_badge(kid_id, badge_id)

                # OPTIMIZATION: Defer persist to end (removed mid-loop persist)
                continue

            # Respect badge start/end dates
            badge_progress = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {}).get(
                badge_id, {}
            )
            start_date_iso = badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_START_DATE
            )
            end_date_iso = badge_progress.get(const.DATA_KID_BADGE_PROGRESS_END_DATE)
            # today_local_iso calculated once per kid (see line ~3973)
            in_effect = (not start_date_iso or today_local_iso >= start_date_iso) and (
                not end_date_iso or today_local_iso <= end_date_iso
            )
            const.LOGGER.debug(
                "DEBUG: Badge Progress - Badge '%s' for kid '%s': today_local_iso=%s, start_date_iso=%s, end_date_iso=%s, in_effect=%s",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, "Unknown Kid"),
                today_local_iso,
                start_date_iso,
                end_date_iso,
                in_effect,
            )

            if not in_effect:
                continue

            # Get chores tracked by this badge (using pre-computed kid chores)
            tracked_chores = self._get_badge_in_scope_chores_list(
                badge_info, kid_id, kid_assigned_chores
            )
            target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                const.DATA_BADGE_TARGET_TYPE
            )
            threshold_value = float(
                badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                )
            )

            # Copy progress dict for updates
            progress = badge_progress.copy() if badge_progress else {}  # type: ignore[assignment,call-overload,operator]

            handler_tuple = target_type_handlers.get(target_type)  # type: ignore[arg-type]
            if handler_tuple:
                handler, handler_kwargs = handler_tuple
                progress = handler(
                    kid_info,
                    badge_info,
                    badge_id,
                    tracked_chores,
                    progress,
                    today_local_iso,
                    threshold_value,
                    **handler_kwargs,
                )
            else:
                # Fallback for unknown types (could log or skip)
                continue

            # Store the updated progress data for this badge
            badge_progress_dict = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})  # type: ignore[typeddict-item]
            badge_progress_dict[badge_id] = progress

            # Award the badge if criteria are met and not already earned
            if progress.get(const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET, False):
                current_state = progress.get(
                    const.DATA_KID_BADGE_PROGRESS_STATUS,
                    const.BADGE_STATE_IN_PROGRESS,
                )
                if current_state != const.BADGE_STATE_EARNED:
                    badge_progress_dict[badge_id][
                        const.DATA_KID_BADGE_PROGRESS_STATUS
                    ] = const.BADGE_STATE_EARNED
                    badge_progress_dict[badge_id][
                        const.DATA_KID_BADGE_PROGRESS_LAST_AWARDED
                    ] = kh.get_today_local_iso()
                    self._award_badge(kid_id, badge_id)

        # Update badge references to reflect current badge tracking settings
        self._update_chore_badge_references_for_kid()

        self._persist()
        self.async_set_updated_data(self._data)

        # PERF: Log badge evaluation duration
        perf_duration = time.perf_counter() - perf_start
        badge_count = len(self.badges_data)
        const.LOGGER.debug(
            "PERF: _check_badges_for_kid() evaluated %d badges in %.3fs for kid '%s'",
            badge_count,
            perf_duration,
            kid_id,
        )

    def _get_badge_in_scope_chores_list(
        self,
        badge_info: BadgeData,
        kid_id: str,
        kid_assigned_chores: list | None = None,
    ) -> list:
        """
        Get the list of chore IDs that are in-scope for this badge evaluation.

        For badges with tracked chores:
        - Returns only those specific chore IDs that are also assigned to the kid
        For badges without tracked chores:
        - Returns all chore IDs assigned to the kid

        Args:
            badge_info: Badge configuration dictionary
            kid_id: Kid's internal ID
            kid_assigned_chores: Optional pre-computed list of chores assigned to kid
                                (optimization to avoid re-iterating all chores)
        """

        badge_type = badge_info.get(const.DATA_BADGE_TYPE, const.BADGE_TYPE_PERIODIC)
        include_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES

        # OPTIMIZATION: Use pre-computed list if provided, otherwise compute
        if kid_assigned_chores is None:
            kid_assigned_chores = []
            # Get all chores assigned to this kid
            for chore_id, chore_info in self.chores_data.items():
                chore_assigned_to = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                if not chore_assigned_to or kid_id in chore_assigned_to:
                    kid_assigned_chores.append(chore_id)

        # If badge does not include tracked chores, return empty list
        if include_tracked_chores:
            tracked_chores = badge_info.get(const.DATA_BADGE_TRACKED_CHORES, {})
            tracked_chore_ids = tracked_chores.get(
                const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
            )

            if tracked_chore_ids:
                # Badge has specific tracked chores, return only those that are also assigned to the kid
                return [
                    chore_id
                    for chore_id in tracked_chore_ids
                    if chore_id in kid_assigned_chores
                ]
            # Badge considers all chores, return all chores assigned to the kid
            return kid_assigned_chores
        # Badge does not include tracked chores component, return empty list
        return []

    def _handle_badge_target_points(
        self,
        kid_info,
        badge_info,  # Reserved for future feature
        badge_id,  # Reserved for future feature
        tracked_chores,
        progress,
        today_local_iso,
        threshold_value,
        from_chores_only=False,
    ):
        """Handle points-based badge targets (all points or from chores only)."""
        total_points_all_sources, total_points_chores, _, _, points_map, _, _ = (
            kh.get_today_chore_and_point_progress(kid_info, tracked_chores)
        )
        points_today = (
            total_points_chores if from_chores_only else total_points_all_sources
        )
        last_update_day = progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY)
        points_cycle_count = progress.get(
            const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0
        )

        if last_update_day and last_update_day != today_local_iso:
            points_cycle_count += progress.get(
                const.DATA_KID_BADGE_PROGRESS_POINTS_TODAY, 0
            )
            progress[const.DATA_KID_BADGE_PROGRESS_POINTS_TODAY] = 0

        progress[const.DATA_KID_BADGE_PROGRESS_POINTS_TODAY] = points_today
        progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = today_local_iso
        progress[const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT] = points_cycle_count
        progress[const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED] = points_map
        progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = tracked_chores

        progress[const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS] = round(
            min(
                (points_cycle_count + points_today) / threshold_value
                if threshold_value
                else 0,
                1.0,
            ),
            const.DATA_FLOAT_PRECISION,
        )
        progress[const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET] = (
            points_cycle_count + points_today
        ) >= threshold_value
        return progress

    def _handle_badge_target_chore_count(
        self,
        kid_info,
        badge_info,  # Reserved for future feature
        badge_id,  # Reserved for future feature
        tracked_chores,
        progress,
        today_local_iso,
        threshold_value,
        min_count=None,
    ):
        """Handle chore count-based badge targets (optionally with a minimum count per day)."""
        _, _, chore_count_today, _, _, count_map, _ = (
            kh.get_today_chore_and_point_progress(kid_info, tracked_chores)
        )
        if min_count is not None and chore_count_today < min_count:
            chore_count_today = 0  # Only count days meeting the minimum

        last_update_day = progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY)
        chores_cycle_count = progress.get(
            const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0
        )

        if last_update_day and last_update_day != today_local_iso:
            chores_cycle_count += progress.get(
                const.DATA_KID_BADGE_PROGRESS_CHORES_TODAY, 0
            )
            progress[const.DATA_KID_BADGE_PROGRESS_CHORES_TODAY] = 0

        progress[const.DATA_KID_BADGE_PROGRESS_CHORES_TODAY] = chore_count_today
        progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = today_local_iso
        progress[const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT] = chores_cycle_count
        progress[const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED] = count_map
        progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = tracked_chores

        progress[const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS] = round(
            min(
                (chores_cycle_count + chore_count_today) / threshold_value
                if threshold_value
                else 0,
                1.0,
            ),
            const.DATA_FLOAT_PRECISION,
        )
        progress[const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET] = (
            chores_cycle_count + chore_count_today
        ) >= threshold_value
        return progress

    def _handle_badge_target_daily_completion(
        self,
        kid_info,
        badge_info,  # Reserved for future feature
        badge_id,  # Reserved for future feature
        tracked_chores,
        progress,
        today_local_iso,
        threshold_value,
        percent_required=1.0,
        only_due_today=False,
        require_no_overdue=False,
        min_count=None,
    ):
        """Handle daily completion-based badge targets (all, percent, due, no overdue, min N)."""
        kid_id = kid_info.get(const.DATA_KID_INTERNAL_ID)
        criteria_met, approved_count, total_count = (
            kh.get_today_chore_completion_progress(
                kid_info,
                tracked_chores,
                kid_id=kid_id,
                all_chores=self.chores_data,
                percent_required=percent_required,
                require_no_overdue=require_no_overdue,
                only_due_today=only_due_today,
                count_required=min_count,
            )
        )
        days_completed = progress.get(const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED, {})
        last_update_day = progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY)
        days_cycle_count = progress.get(
            const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0
        )

        if last_update_day and last_update_day != today_local_iso:
            if progress.get(const.DATA_KID_BADGE_PROGRESS_TODAY_COMPLETED, False):
                days_cycle_count += 1
            progress[const.DATA_KID_BADGE_PROGRESS_TODAY_COMPLETED] = False

        progress[const.DATA_KID_BADGE_PROGRESS_TODAY_COMPLETED] = criteria_met
        progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = today_local_iso

        if criteria_met:
            days_completed[today_local_iso] = True
        progress[const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED] = days_completed
        progress[const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT] = days_cycle_count
        progress[const.DATA_KID_BADGE_PROGRESS_APPROVED_COUNT] = approved_count
        progress[const.DATA_KID_BADGE_PROGRESS_TOTAL_COUNT] = total_count
        progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = tracked_chores

        progress[const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS] = round(
            min(
                (days_cycle_count + (1 if criteria_met else 0)) / threshold_value
                if threshold_value
                else 0,
                1.0,
            ),
            const.DATA_FLOAT_PRECISION,
        )
        progress[const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET] = (
            days_cycle_count + (1 if criteria_met else 0)
        ) >= threshold_value
        return progress

    def _handle_badge_target_streak(
        self,
        kid_info,
        badge_info,  # Reserved for future feature
        badge_id,  # Reserved for future feature
        tracked_chores,
        progress,
        today_local_iso,
        threshold_value,
        percent_required=1.0,
        only_due_today=False,
        require_no_overdue=False,
        min_count=None,
    ):
        """Handle streak-based badge targets (consecutive days meeting criteria).

        Uses the same fields as daily completion, but interprets DAYS_CYCLE_COUNT as the current streak.
        """
        kid_id = kid_info.get(const.DATA_KID_INTERNAL_ID)
        criteria_met, approved_count, total_count = (
            kh.get_today_chore_completion_progress(
                kid_info,
                tracked_chores,
                kid_id=kid_id,
                all_chores=self.chores_data,
                percent_required=percent_required,
                require_no_overdue=require_no_overdue,
                only_due_today=only_due_today,
                count_required=min_count,
            )
        )
        last_update_day = progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY)
        streak = progress.get(const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0)
        days_completed = progress.get(const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED, {})

        if last_update_day and last_update_day != today_local_iso:
            if progress.get(const.DATA_KID_BADGE_PROGRESS_TODAY_COMPLETED, False):
                # Only increment streak if yesterday was completed
                yesterday_iso = kh.adjust_datetime_by_interval(
                    today_local_iso,
                    interval_unit=const.TIME_UNIT_DAYS,
                    delta=-1,
                    require_future=False,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )
                if days_completed.get(yesterday_iso):
                    streak += 1
                else:
                    streak = 1 if criteria_met else 0
            else:
                streak = 0
            progress[const.DATA_KID_BADGE_PROGRESS_TODAY_COMPLETED] = False

        # Update today's completion status and last_update_day
        progress[const.DATA_KID_BADGE_PROGRESS_TODAY_COMPLETED] = criteria_met
        progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = today_local_iso

        if criteria_met:
            days_completed[today_local_iso] = True
        progress[const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED] = days_completed
        progress[const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT] = streak
        progress[const.DATA_KID_BADGE_PROGRESS_APPROVED_COUNT] = approved_count
        progress[const.DATA_KID_BADGE_PROGRESS_TOTAL_COUNT] = total_count
        progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = tracked_chores

        progress[const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS] = round(
            min(
                streak / threshold_value if threshold_value else 0,
                1.0,
            ),
            const.DATA_FLOAT_PRECISION,
        )
        progress[const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET] = streak >= threshold_value
        return progress

    def _award_badge(self, kid_id: str, badge_id: str):
        """Add the badge to kid's 'earned_by' and kid's 'badges' list."""
        badge_info: BadgeData | None = self.badges_data.get(badge_id)
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        if not kid_info:
            const.LOGGER.error("Award Badge - Kid ID '%s' not found.", kid_id)
            return
        if not badge_info:
            const.LOGGER.error(
                "ERROR: Award Badge - Badge ID '%s' not found. Cannot be awarded to Kid ID '%s'",
                badge_id,
                kid_id,
            )
            return

        badge_type = badge_info.get(const.DATA_BADGE_TYPE, const.BADGE_TYPE_CUMULATIVE)
        badge_name = badge_info.get(const.DATA_BADGE_NAME)
        kid_name = kid_info[const.DATA_KID_NAME]

        # Award the badge (for all types, including special occasion).
        const.LOGGER.info(
            "INFO: Award Badge - Awarding badge '%s' (%s) to kid '%s' (%s).",
            badge_id,
            badge_name,
            kid_id,
            kid_name,
        )
        earned_by_list = badge_info.setdefault(const.DATA_BADGE_EARNED_BY, [])
        if kid_id not in earned_by_list:
            earned_by_list.append(kid_id)
        self._update_badges_earned_for_kid(kid_id, badge_id)

        # --- Unified Award Items Logic ---
        award_data = badge_info.get(const.DATA_BADGE_AWARDS, {})
        award_items = award_data.get(const.DATA_BADGE_AWARDS_AWARD_ITEMS, [])
        points_awarded = award_data.get(
            const.DATA_BADGE_AWARDS_AWARD_POINTS, const.DEFAULT_ZERO
        )
        multiplier = award_data.get(
            const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
            const.DEFAULT_KID_POINTS_MULTIPLIER,
        )

        # Process award_items using helper
        to_award, _ = self.process_award_items(
            award_items,
            self.rewards_data,
            self.bonuses_data,
            self.penalties_data,
        )

        # 1. Points
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS)
            for item in award_items
        ):
            if points_awarded > const.DEFAULT_ZERO:
                const.LOGGER.info(
                    "INFO: Award Badge - Awarding points: %s for kid '%s'.",
                    points_awarded,
                    kid_name,
                )
                self.update_kid_points(
                    kid_id,
                    delta=points_awarded,
                    source=const.POINTS_SOURCE_BADGES,
                )

        # 2. Multiplier (only for cumulative badges)
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS_MULTIPLIER)
            for item in award_items
        ):
            if multiplier > const.DEFAULT_ZERO:  # type: ignore[assignment,call-overload,operator]
                kid_info[const.DATA_KID_POINTS_MULTIPLIER] = multiplier  # type: ignore[typeddict-item]
                const.LOGGER.info(
                    "INFO: Award Badge - Set points multiplier to %.2f for kid '%s'.",
                    multiplier,
                    kid_name,
                )
            else:
                kid_info[const.DATA_KID_POINTS_MULTIPLIER] = (
                    const.DEFAULT_POINTS_MULTIPLIER
                )

        # 3. Rewards (multiple) - Badge awards grant rewards directly (no claim/approval flow)
        for reward_id in to_award.get(const.AWARD_ITEMS_KEY_REWARDS, []):
            if reward_id in self.rewards_data:
                # Update modern reward_data tracking
                reward_data = self._get_kid_reward_data(kid_id, reward_id)
                reward_data[const.DATA_KID_REWARD_DATA_TOTAL_APPROVED] = (
                    reward_data.get(const.DATA_KID_REWARD_DATA_TOTAL_APPROVED, 0) + 1
                )
                # Increment period counter for this approval
                self._increment_reward_period_counter(
                    reward_data, const.DATA_KID_REWARD_DATA_PERIOD_APPROVED
                )
                const.LOGGER.info(
                    "INFO: Award Badge - Granted reward '%s' to kid '%s'.",
                    self.rewards_data[reward_id].get(const.DATA_REWARD_NAME, reward_id),
                    kid_name,
                )

        # 4. Bonuses (multiple)
        for bonus_id in to_award.get(const.AWARD_ITEMS_KEY_BONUSES, []):
            if bonus_id in self.bonuses_data:
                self.apply_bonus(kid_name, kid_id, bonus_id)

        # --- Notification ---
        message = f"You earned a new badge: '{badge_name}'!"
        if to_award.get(const.AWARD_ITEMS_KEY_REWARDS):
            reward_names = [
                self.rewards_data[rid].get(const.DATA_REWARD_NAME, rid)
                for rid in to_award[const.AWARD_ITEMS_KEY_REWARDS]
            ]
            message += f" Rewards: {', '.join(reward_names)}."
        if to_award.get(const.AWARD_ITEMS_KEY_BONUSES):
            bonus_names = [
                self.bonuses_data[bid].get(const.DATA_BONUS_NAME, bid)
                for bid in to_award[const.AWARD_ITEMS_KEY_BONUSES]
            ]
            message += f" Bonuses: {', '.join(bonus_names)}."
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS)
            for item in award_items
        ):
            message += f" Points: {points_awarded}."
        if badge_type == const.BADGE_TYPE_CUMULATIVE and any(
            item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS_MULTIPLIER)
            for item in award_items
        ):
            message += f" Multiplier: {multiplier}x."

        parent_message = f"'{kid_name}' earned a new badge: '{badge_name}'."
        if to_award.get(const.AWARD_ITEMS_KEY_REWARDS):
            reward_names = [
                self.rewards_data[rid].get(const.DATA_REWARD_NAME, rid)
                for rid in to_award[const.AWARD_ITEMS_KEY_REWARDS]
            ]
            parent_message += f" Rewards: {', '.join(reward_names)}."
        if to_award.get(const.AWARD_ITEMS_KEY_BONUSES):
            bonus_names = [
                self.bonuses_data[bid].get(const.DATA_BONUS_NAME, bid)
                for bid in to_award[const.AWARD_ITEMS_KEY_BONUSES]
            ]
            parent_message += f" Bonuses: {', '.join(bonus_names)}."
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS)
            for item in award_items
        ):
            parent_message += f" Points: {points_awarded}."
        if badge_type == const.BADGE_TYPE_CUMULATIVE and any(
            item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS_MULTIPLIER)
            for item in award_items
        ):
            parent_message += f" Multiplier: {multiplier}x."

        extra_data = {const.DATA_KID_ID: kid_id, const.DATA_BADGE_ID: badge_id}
        self.hass.async_create_task(
            self._notify_kid_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_BADGE_EARNED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_KID,
                message_data={"badge_name": badge_info.get(const.DATA_BADGE_NAME)},
                extra_data=extra_data,
            )
        )
        self.hass.async_create_task(
            self._notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_BADGE_EARNED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_PARENT,
                message_data={
                    "kid_name": self.kids_data[kid_id][const.DATA_KID_NAME],
                    "badge_name": badge_info.get(const.DATA_BADGE_NAME),
                },
                extra_data=extra_data,
            )
        )

        self._persist()
        self.async_set_updated_data(self._data)
        self._check_badges_for_kid(kid_id)

    def process_award_items(
        self, award_items, rewards_dict, bonuses_dict, penalties_dict
    ):
        """Process award_items and return dicts of items to award or penalize."""
        to_award: dict[str, list[str]] = {
            const.AWARD_ITEMS_KEY_REWARDS: [],
            const.AWARD_ITEMS_KEY_BONUSES: [],
        }
        to_penalize = []
        for item in award_items:
            if item.startswith(const.AWARD_ITEMS_PREFIX_REWARD):
                reward_id = item.split(":", 1)[1]
                if reward_id in rewards_dict:
                    to_award[const.AWARD_ITEMS_KEY_REWARDS].append(reward_id)
            elif item.startswith(const.AWARD_ITEMS_PREFIX_BONUS):
                bonus_id = item.split(":", 1)[1]
                if bonus_id in bonuses_dict:
                    to_award[const.AWARD_ITEMS_KEY_BONUSES].append(bonus_id)
            elif item.startswith(const.AWARD_ITEMS_PREFIX_PENALTY):
                penalty_id = item.split(":", 1)[1]
                if penalty_id in penalties_dict:
                    to_penalize.append(penalty_id)
        return to_award, to_penalize

    def _update_point_multiplier_for_kid(self, kid_id: str):
        """Update the kid's points multiplier based on the current (effective) cumulative badge only."""

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        current_badge_id = progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID
        )

        if current_badge_id:
            current_badge_info: BadgeData = cast(
                "BadgeData", self.badges_data.get(current_badge_id, {})
            )
            badge_awards = current_badge_info.get(const.DATA_BADGE_AWARDS, {})
            multiplier = badge_awards.get(
                const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
                const.DEFAULT_KID_POINTS_MULTIPLIER,
            )
        else:
            multiplier = const.DEFAULT_KID_POINTS_MULTIPLIER

        kid_info[const.DATA_KID_POINTS_MULTIPLIER] = multiplier  # type: ignore[typeddict-item]

    def _update_badges_earned_for_kid(self, kid_id: str, badge_id: str) -> None:
        """Update the kid's badges-earned tracking for the given badge, including period stats."""
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.error(
                "ERROR: Update Kid Badges Earned - Kid ID '%s' not found.", kid_id
            )
            return

        badge_info: BadgeData | None = self.badges_data.get(badge_id)
        if not badge_info:
            const.LOGGER.error(
                "ERROR: Update Kid Badges Earned - Badge ID '%s' not found.", badge_id
            )
            return

        today_local_iso = kh.get_today_local_iso()
        now = kh.get_now_local_time()
        week = now.strftime("%Y-W%V")
        month = now.strftime("%Y-%m")
        year = now.strftime("%Y")

        badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})

        # Use new constants for periods
        periods_key = const.DATA_KID_BADGES_EARNED_PERIODS
        period_daily = const.DATA_KID_BADGES_EARNED_PERIODS_DAILY
        period_weekly = const.DATA_KID_BADGES_EARNED_PERIODS_WEEKLY
        period_monthly = const.DATA_KID_BADGES_EARNED_PERIODS_MONTHLY
        period_yearly = const.DATA_KID_BADGES_EARNED_PERIODS_YEARLY

        if badge_id not in badges_earned:
            badges_earned[badge_id] = {  # type: ignore[typeddict-item]
                const.DATA_KID_BADGES_EARNED_NAME: badge_info.get(
                    const.DATA_BADGE_NAME
                ),
                const.DATA_KID_BADGES_EARNED_LAST_AWARDED: today_local_iso,
                const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1,
                periods_key: {
                    period_daily: {today_local_iso: 1},
                    period_weekly: {week: 1},
                    period_monthly: {month: 1},
                    period_yearly: {year: 1},
                },
            }
            const.LOGGER.info(
                "INFO: Update Kid Badges Earned - Created new tracking for badge '%s' for kid '%s'.",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )
        else:
            tracking_entry = badges_earned[badge_id]
            tracking_entry[const.DATA_KID_BADGES_EARNED_NAME] = badge_info.get(  # type: ignore[typeddict-item]
                const.DATA_BADGE_NAME
            )
            tracking_entry[const.DATA_KID_BADGES_EARNED_LAST_AWARDED] = today_local_iso
            tracking_entry[const.DATA_KID_BADGES_EARNED_AWARD_COUNT] = (
                tracking_entry.get(const.DATA_KID_BADGES_EARNED_AWARD_COUNT, 0) + 1
            )
            # Ensure periods and sub-dicts exist
            periods = tracking_entry.setdefault(periods_key, {})  # type: ignore[typeddict-item]
            daily_dict: dict[str, int] = periods.setdefault(period_daily, {})  # type: ignore[typeddict-item]
            weekly_dict: dict[str, int] = periods.setdefault(period_weekly, {})  # type: ignore[typeddict-item]
            monthly_dict: dict[str, int] = periods.setdefault(period_monthly, {})  # type: ignore[typeddict-item]
            yearly_dict: dict[str, int] = periods.setdefault(period_yearly, {})  # type: ignore[typeddict-item]
            daily_dict[today_local_iso] = daily_dict.get(today_local_iso, 0) + 1
            weekly_dict[week] = weekly_dict.get(week, 0) + 1
            monthly_dict[month] = monthly_dict.get(month, 0) + 1
            yearly_dict[year] = yearly_dict.get(year, 0) + 1

            const.LOGGER.info(
                "INFO: Update Kid Badges Earned - Updated tracking for badge '%s' for kid '%s'.",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )
            # Cleanup old period data
            kh.cleanup_period_data(
                self,
                periods_data=periods,  # type: ignore[arg-type]
                period_keys={
                    "daily": const.DATA_KID_BADGES_EARNED_PERIODS_DAILY,
                    "weekly": const.DATA_KID_BADGES_EARNED_PERIODS_WEEKLY,
                    "monthly": const.DATA_KID_BADGES_EARNED_PERIODS_MONTHLY,
                    "yearly": const.DATA_KID_BADGES_EARNED_PERIODS_YEARLY,
                },
                retention_daily=self.config_entry.options.get(
                    const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
                ),
                retention_weekly=self.config_entry.options.get(
                    const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
                ),
                retention_monthly=self.config_entry.options.get(
                    const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
                ),
                retention_yearly=self.config_entry.options.get(
                    const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
                ),
            )

        self._persist()
        self.async_set_updated_data(self._data)

    def _update_chore_badge_references_for_kid(
        self, include_cumulative_badges: bool = False
    ):
        """Update badge reference lists in kid chore data.

        This maintains a list of which badges reference each chore,
        useful for quick lookups when evaluating badges.

        Args:
            include_cumulative_badges: Whether to include cumulative badges in the references.
                                    Default is False which excludes them since they are currently points only
        """
        # Clear existing badge references
        for _kid_id, kid_info in self.kids_data.items():
            if const.DATA_KID_CHORE_DATA not in kid_info:
                continue

            for chore_data in kid_info[const.DATA_KID_CHORE_DATA].values():
                chore_data[const.DATA_KID_CHORE_DATA_BADGE_REFS] = []

        # Add badge references to relevant chores
        for badge_id, badge_info in self.badges_data.items():
            # Skip cumulative badges if not explicitly included
            if (
                not include_cumulative_badges
                and badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE
            ):
                continue

            # For each kid this badge is assigned to
            assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            for kid_id in (
                assigned_to or self.kids_data.keys()
            ):  # If empty, apply to all kids
                kid_info: KidData | None = self.kids_data.get(kid_id)
                if not kid_info or const.DATA_KID_CHORE_DATA not in kid_info:
                    continue

                # Use the helper function to get the correct in-scope chores for this badge and kid
                in_scope_chores_list = self._get_badge_in_scope_chores_list(
                    badge_info, kid_id
                )

                # Add badge reference to each tracked chore
                for chore_id in in_scope_chores_list:
                    if chore_id in kid_info[const.DATA_KID_CHORE_DATA]:
                        chore_entry = kid_info[const.DATA_KID_CHORE_DATA][chore_id]
                        badge_refs: list[str] = chore_entry.get(  # type: ignore[typeddict-item]
                            const.DATA_KID_CHORE_DATA_BADGE_REFS, []
                        )
                        if badge_id not in badge_refs:
                            badge_refs.append(badge_id)
                            chore_entry[const.DATA_KID_CHORE_DATA_BADGE_REFS] = (
                                badge_refs  # type: ignore[typeddict-item]
                            )

    # -------------------------------------------------------------------------------------
    # Badges: Remove Awarded Badges
    # Removes awarded badges from kids based on provided kid name and/or badge name.
    # Converts kid name to kid ID and badge name to badge ID for targeted removal using
    # the _remove_awarded_badges_by_id method.
    # If badge_id is not found, it assumes the badge was deleted and removes it from the kid's data.
    # If neither is provided, it globally removes all awarded badges from all kids.
    # -------------------------------------------------------------------------------------
    def remove_awarded_badges(
        self, kid_name: str | None = None, badge_name: str | None = None
    ) -> None:
        """Remove awarded badges based on provided kid_name and badge_name."""
        # Convert kid_name to kid_id if provided.
        kid_id = None
        if kid_name:
            kid_id = kh.get_kid_id_by_name(self, kid_name)
            if kid_id is None:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid name '%s' not found.", kid_name
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_name,
                    },
                )
        else:
            kid_id = None

        # If badge_name is provided, try to find its corresponding badge_id.
        if badge_name:
            badge_id = kh.get_badge_id_by_name(self, badge_name)
            if not badge_id:
                # If the badge isn't found, assume the actual badge was deleted but still listed in kid data
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - Badge name '%s' not found in badges_data. Removing from kid data only.",
                    badge_name,
                )
                # Remove badge name from a specific kid if kid_id is provided,
                # or from all kids if not.
                if kid_id:
                    kid_info: KidData | None = self.kids_data.get(kid_id)
                    if kid_info:
                        # Remove badge from the kid's earned badges
                        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
                        to_remove = [
                            badge_id
                            for badge_id, entry in badges_earned.items()
                            if entry.get(const.DATA_KID_BADGES_EARNED_NAME)
                            == badge_name
                        ]
                        for badge_id in to_remove:
                            del badges_earned[badge_id]
                else:
                    for kid_info in self.kids_data.values():
                        # Remove badge from the kid's earned badges
                        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
                        to_remove = [
                            badge_id
                            for badge_id, entry in badges_earned.items()
                            if entry.get(const.DATA_KID_BADGES_EARNED_NAME)
                            == badge_name
                        ]
                        for badge_id in to_remove:
                            del badges_earned[badge_id]

                self._persist()
                self.async_set_updated_data(self._data)
                return
        else:
            badge_id = None

        self._remove_awarded_badges_by_id(kid_id, badge_id)

    def _remove_awarded_badges_by_id(
        self, kid_id: str | None = None, badge_id: str | None = None
    ) -> None:
        """Removes awarded badges based on provided kid_id and badge_id."""

        const.LOGGER.info("Remove Awarded Badges - Starting removal process.")
        found = False

        if badge_id and kid_id:
            # Reset a specific badge for a specific kid.
            kid_info: KidData | None = self.kids_data.get(kid_id)
            badge_info: BadgeData | None = self.badges_data.get(badge_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if not badge_info:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Badge ID '%s' not found.", badge_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_BADGE,
                        "name": badge_id,
                    },
                )
            badge_name = badge_info.get(const.DATA_BADGE_NAME, badge_id)
            kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
            # Remove the badge from the kid's badges_earned.
            badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})
            if badge_id in badges_earned:
                found = True
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - Removing badge '%s' from kid '%s'.",
                    badge_name,
                    kid_name,
                )
                del badges_earned[badge_id]

            # Remove the kid from the badge earned_by list.
            earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
            if kid_id in earned_by_list:
                earned_by_list.remove(kid_id)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - Badge '%s' ('%s') not found in kid '%s' ('%s') data.",
                    badge_id,
                    badge_name,
                    kid_id,
                    kid_name,
                )

        elif badge_id:
            # Remove a specific awarded badge for all kids.
            badge_info: BadgeData | None = self.badges_data.get(badge_id)
            if not badge_info:
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - Badge ID '%s' not found in badges data.",
                    badge_id,
                )
            else:
                badge_name = badge_info.get(const.DATA_BADGE_NAME, badge_id)
                for kid_id, kid_info in self.kids_data.items():
                    kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown Kid")
                    # Remove the badge from the kid's badges_earned.
                    badges_earned = kid_info.setdefault(
                        const.DATA_KID_BADGES_EARNED, {}
                    )
                    if badge_id in badges_earned:
                        found = True
                        const.LOGGER.warning(
                            "WARNING: Remove Awarded Badges - Removing badge '%s' from kid '%s'.",
                            badge_name,
                            kid_name,
                        )
                        del badges_earned[badge_id]

                    # Remove the kid from the badge earned_by list.
                    earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                    if kid_id in earned_by_list:
                        earned_by_list.remove(kid_id)

                # All kids should already be removed from the badge earned_by list, but in case of orphans, clear those fields
                if const.DATA_BADGE_EARNED_BY in badge_info:
                    badge_info[const.DATA_BADGE_EARNED_BY].clear()

                if not found:
                    const.LOGGER.warning(
                        "WARNING: Remove Awarded Badges - Badge '%s' ('%s') not found in any kid's data.",
                        badge_id,
                        badge_name,
                    )

        elif kid_id:
            # Remove all awarded badges for a specific kid.
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown Kid")
            for badge_id, badge_info in self.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME)  # type: ignore[assignment,call-overload,operator]
                earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})
                if kid_id in earned_by_list:
                    found = True
                    # Remove kid from badge earned_by list
                    earned_by_list.remove(kid_id)
                    # Remove the badge from the kid's badges_earned.
                    if badge_id in badges_earned:
                        found = True
                        const.LOGGER.warning(
                            "WARNING: Remove Awarded Badges - Removing badge '%s' from kid '%s'.",
                            badge_name,
                            kid_name,
                        )
                        del badges_earned[badge_id]

            # All badges should already be removed from the kid's badges list, but in case of orphans, clear those fields
            if const.DATA_KID_BADGES_EARNED in kid_info:
                kid_info[const.DATA_KID_BADGES_EARNED].clear()
            # CLS Should also clear all extra fields for all badge types later

            if not found:
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - No badge found for kid '%s'.",
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

        else:
            # Remove Awarded Badges for all kids.
            const.LOGGER.info(
                "INFO: Remove Awarded Badges - Removing all awarded badges for all kids."
            )
            for badge_id, badge_info in self.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME)  # type: ignore[assignment,call-overload,operator]
                for kid_id, kid_info in self.kids_data.items():
                    kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown Kid")
                    # Remove the badge from the kid's badges_earned.
                    badges_earned = kid_info.setdefault(
                        const.DATA_KID_BADGES_EARNED, {}
                    )
                    if badge_id in badges_earned:
                        found = True
                        const.LOGGER.warning(
                            "WARNING: Remove Awarded Badges - Removing badge '%s' from kid '%s'.",
                            badge_name,
                            kid_name,
                        )
                        del badges_earned[badge_id]

                    # Remove the kid from the badge earned_by list.
                    earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                    if kid_id in earned_by_list:
                        earned_by_list.remove(kid_id)

                    # All badges should already be removed from the kid's badges list, but in case of orphans, clear those fields
                    if const.DATA_KID_BADGES_EARNED in kid_info:
                        kid_info[const.DATA_KID_BADGES_EARNED].clear()
                    # CLS Should also clear all extra fields for all badge types later

                # All kids should already be removed from the badge earned_by list, but in case of orphans, clear those fields
                if const.DATA_BADGE_EARNED_BY in badge_info:
                    badge_info[const.DATA_BADGE_EARNED_BY].clear()

            if not found:
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - No awarded badges found in any kid's data."
                )

        const.LOGGER.info(
            "INFO: Remove Awarded Badges - Badge removal process completed."
        )
        self._persist()
        self.async_set_updated_data(self._data)

    def _recalculate_all_badges(self):
        """Global re-check of all badges for all kids."""
        const.LOGGER.info("Recalculate All Badges - Starting Recalculation")

        # Re-evaluate badge criteria for each kid.
        for kid_id in self.kids_data:
            self._check_badges_for_kid(kid_id)

        self._persist()
        self.async_set_updated_data(self._data)
        const.LOGGER.info("Recalculate All Badges - Recalculation Complete")

    def _get_cumulative_badge_progress(self, kid_id: str) -> dict[str, Any]:
        """
        Builds and returns the full cumulative badge progress block for a kid.
        Uses badge level logic, progress tracking, and next-tier metadata.
        Does not mutate state.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return {}

        # Make a copy of the existing progress so that we don't modify the stored data.
        stored_progress = kid_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        ).copy()

        # Compute values from badge level logic.
        (highest_earned, next_higher, next_lower, baseline, cycle_points) = (
            self._get_cumulative_badge_levels(kid_id)
        )
        total_points = baseline + cycle_points

        # Determine which badge should be considered current.
        # If the stored status is "demoted", then set current badge to next_lower; otherwise, use highest_earned.
        current_status = stored_progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.CUMULATIVE_BADGE_STATE_ACTIVE,
        )
        if current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED:
            current_badge_info = next_lower
        else:
            current_badge_info = highest_earned

        # Build a new dictionary with computed values.
        computed_progress = {
            # Maintenance tracking (we'll merge stored values below)
            # For keys like status we prefer the stored value, or the default.
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS: stored_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
                const.CUMULATIVE_BADGE_STATE_ACTIVE,
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE: baseline,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS: cycle_points,
            # Highest earned badge
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: highest_earned.get(
                const.DATA_BADGE_INTERNAL_ID
            )
            if highest_earned
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME: highest_earned.get(
                const.DATA_BADGE_NAME
            )
            if highest_earned
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD: float(
                highest_earned.get(const.DATA_BADGE_TARGET, {}).get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                )
            )
            if highest_earned
            else None,
            # Current badge in effect
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: current_badge_info.get(
                const.DATA_BADGE_INTERNAL_ID
            )
            if current_badge_info
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME: current_badge_info.get(
                const.DATA_BADGE_NAME
            )
            if current_badge_info
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD: float(
                current_badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                )
            )
            if current_badge_info
            else None,
            # Next higher tier
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID: next_higher.get(
                const.DATA_BADGE_INTERNAL_ID
            )
            if next_higher
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME: next_higher.get(
                const.DATA_BADGE_NAME
            )
            if next_higher
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_THRESHOLD: float(
                next_higher.get(const.DATA_BADGE_TARGET, {}).get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                )
            )
            if next_higher
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED: (
                max(
                    0.0,
                    float(
                        next_higher.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                    - total_points,
                )
                if next_higher
                else None
            ),
            # Next lower tier
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID: next_lower.get(
                const.DATA_BADGE_INTERNAL_ID
            )
            if next_lower
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME: next_lower.get(
                const.DATA_BADGE_NAME
            )
            if next_lower
            else None,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_THRESHOLD: float(
                next_lower.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)
            )
            if next_lower
            else None,
        }

        # Merge the computed values over the stored progress.
        stored_progress.update(computed_progress)  # type: ignore[typeddict-item]

        # Return the merged dictionary without modifying the underlying stored data.
        return stored_progress  # type: ignore[return-value]

    def _manage_badge_maintenance(self, kid_id: str) -> None:
        """
        Manages badge maintenance for a kid:
        - Initializes badge progress data for badges that don't have it yet
        - Checks if badges have reached their end dates
        - Resets progress for badges that have passed their end_date
        - Updates badge states based on the reset
        - Sets up new cycle dates for recurring badges
        - Ensures all required fields exist in badge progress data
        - Synchronizes badge configuration changes with progress data
        """
        # ===============================================================
        # SECTION 1: INITIALIZATION - Basic setup and validation
        # ===============================================================
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # First, ensure all badge progress entries have all required fields
        badge_progress = kid_info.setdefault(const.DATA_KID_BADGE_PROGRESS, {})
        today_local_iso = kh.get_today_local_iso()

        # ===============================================================
        # SECTION 2: BADGE INITIALIZATION & SYNC - Create or update badge progress data
        # ===============================================================
        self._sync_badge_progress_for_kid(kid_id)

        # ===============================================================
        # SECTION 3: BADGE RESET CYCLE - Manage recurring badges that reached end date
        # ===============================================================
        # Now perform badge reset maintenance
        for badge_id, progress in list(badge_progress.items()):
            badge_info: BadgeData | None = self.badges_data.get(badge_id)
            if not badge_info:
                continue

            recurring_frequency = progress.get(
                const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY
            )

            # ---------------------------------------------------------------
            # Check if badge has reached its end date
            # ---------------------------------------------------------------
            # Kid badge progress end date should always be populated for recurring badges.
            # If the user does not set a date, it will default to today.
            end_date_iso = progress.get(
                const.DATA_KID_BADGE_PROGRESS_END_DATE, today_local_iso
            )
            if not end_date_iso or today_local_iso <= end_date_iso:
                continue

            # --- Apply penalties if badge was NOT earned by end date, and not already applied ---
            if not progress.get(
                const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET, False
            ) and not progress.get(
                const.DATA_KID_BADGE_PROGRESS_PENALTY_APPLIED, False
            ):
                # Mark the penalty as applied to avoid reapplying it
                progress[const.DATA_KID_BADGE_PROGRESS_PENALTY_APPLIED] = True
                award_data = badge_info.get(const.DATA_BADGE_AWARDS, {})
                award_items = award_data.get(const.DATA_BADGE_AWARDS_AWARD_ITEMS, [])
                _, to_penalize = self.process_award_items(
                    award_items,
                    self.rewards_data,
                    self.bonuses_data,
                    self.penalties_data,
                )
                for penalty_id in to_penalize:
                    if penalty_id in self.penalties_data:
                        self.apply_penalty("system", kid_id, penalty_id)
                        const.LOGGER.info(
                            "INFO: Penalty Applied - Badge '%s' not earned by kid '%s'. Penalty '%s' applied.",
                            badge_info.get(const.DATA_BADGE_NAME, badge_id),
                            kid_info.get(const.DATA_KID_NAME, kid_id),
                            self.penalties_data[penalty_id].get(
                                const.DATA_PENALTY_NAME, penalty_id
                            ),
                        )

            # Now skip further reset logic if not recurring
            if recurring_frequency == const.FREQUENCY_NONE:
                continue

            # Debug: Log when the reset logic is triggered for this badge
            const.LOGGER.debug(
                "DEBUG: Badge Reset Triggered - Badge '%s' for kid '%s': today_local_iso=%s, end_date_iso=%s (reset logic will run)",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
                today_local_iso,
                end_date_iso,
            )

            # Increment the cycle count for this badge
            progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
                progress.get(const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT, 0) + 1
            )

            # ---------------------------------------------------------------
            # Calculate new dates for next badge cycle
            # ---------------------------------------------------------------
            # Get reset schedule from badge configuration
            reset_schedule = badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
            # Use the end date from the badge first, but if that isn't available, use the badge progress
            # from kid data which should always be populated for a recurring badge.
            prior_end_date_iso = badge_info.get(
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE, end_date_iso
            )

            # The following require special handling because resets will not happen until after the end date passes
            # Since the scheduling functions will always look for a future date, it would end up with an end date
            # for tomorrow (2 days) instead of just rescheduling the end date by 1 day.
            is_daily = recurring_frequency == const.FREQUENCY_DAILY
            is_custom_1_day = (
                recurring_frequency == const.FREQUENCY_CUSTOM
                and reset_schedule.get(const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL)
                == 1
                and reset_schedule.get(
                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                )
                == const.TIME_UNIT_DAYS
            )

            if is_daily or is_custom_1_day:
                # Use PERIOD_DAY_END to set end date to end of today - See detail above.
                new_end_date_iso = kh.get_next_scheduled_datetime(
                    str(prior_end_date_iso) if prior_end_date_iso else "",
                    interval_type=const.PERIOD_DAY_END,
                    require_future=True,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )

            # Calculate new end date based on recurring frequency
            elif recurring_frequency == const.FREQUENCY_CUSTOM:
                # Handle custom frequency
                custom_interval = reset_schedule.get(
                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                )
                custom_interval_unit = reset_schedule.get(
                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                )

                if custom_interval and custom_interval_unit:
                    new_end_date_iso = kh.adjust_datetime_by_interval(
                        str(prior_end_date_iso) if prior_end_date_iso else "",
                        interval_unit=custom_interval_unit,
                        delta=custom_interval,
                        require_future=True,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
                else:
                    # Default fallback to weekly
                    new_end_date_iso = kh.adjust_datetime_by_interval(
                        str(prior_end_date_iso) if prior_end_date_iso else "",
                        interval_unit=const.TIME_UNIT_WEEKS,
                        delta=1,
                        require_future=True,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
            else:
                # Use standard frequency helper
                new_end_date_iso = kh.get_next_scheduled_datetime(
                    str(prior_end_date_iso) if prior_end_date_iso else "",
                    interval_type=recurring_frequency,  # type: ignore[arg-type]
                    require_future=True,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )

            # ---------------------------------------------------------------
            # Calculate new start date based on badge type and previous cycle
            # ---------------------------------------------------------------
            # If there was no previous start date, don't set one (immediately effective)
            # If there was a previous start date, calculate the new one based on the duration
            existing_start_date_iso = progress.get(
                const.DATA_KID_BADGE_PROGRESS_START_DATE
            )

            if existing_start_date_iso:
                try:
                    # Handle special case where start and end dates are the same
                    if existing_start_date_iso == end_date_iso:
                        # For badges where start date equals end date (like special occasions)
                        # set the new start date equal to the new end date
                        new_start_date_iso = new_end_date_iso
                    else:
                        # Convert ISO dates to datetime objects
                        start_dt_utc = kh.parse_datetime_to_utc(existing_start_date_iso)
                        end_dt_utc = kh.parse_datetime_to_utc(end_date_iso)

                        if start_dt_utc and end_dt_utc:
                            # Calculate duration in days
                            duration = (end_dt_utc - start_dt_utc).days

                            # Set new start date by subtracting the same duration from new end date
                            # Cast ensures new_end_date_iso is str | date | datetime (not None)
                            new_start_date_iso = str(
                                kh.adjust_datetime_by_interval(
                                    cast("str | date | datetime", new_end_date_iso),
                                    interval_unit=const.TIME_UNIT_DAYS,
                                    delta=-duration,
                                    require_future=False,  # Allow past dates for calculation
                                    return_type=const.HELPER_RETURN_ISO_DATE,
                                )
                            )

                            # If new start date is in the past, use today
                            new_start_date_iso = max(
                                new_start_date_iso, today_local_iso
                            )
                        else:
                            # Fallback to today if date parsing fails
                            new_start_date_iso = today_local_iso
                except (ValueError, TypeError, AttributeError):
                    # Fallback to today if calculation fails
                    new_start_date_iso = today_local_iso
            else:
                # No existing start date - keep it unset (None)
                new_start_date_iso = None

            # ---------------------------------------------------------------
            # Reset badge progress for the new cycle
            # ---------------------------------------------------------------

            # Update badge state to active_cycle (working on next iteration)
            progress[const.DATA_KID_BADGE_PROGRESS_STATUS] = (
                const.BADGE_STATE_ACTIVE_CYCLE
            )
            progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = new_start_date_iso  # type: ignore[typeddict-item]
            progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = new_end_date_iso  # type: ignore[typeddict-item]

            # Reset fenalty applied flag
            progress[const.DATA_KID_BADGE_PROGRESS_PENALTY_APPLIED] = False

            # Reset all known progress tracking fields if present
            reset_fields = [
                (const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0.0),
                (const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0),
                (const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0),
                (const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED, {}),
                (const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED, {}),
            ]
            for field, default in reset_fields:
                if field in progress:
                    progress[field] = default

            const.LOGGER.debug(
                "DEBUG: Badge Maintenance - Reset badge '%s' for kid '%s'. New cycle: %s to %s",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
                new_start_date_iso if new_start_date_iso else "immediate",
                new_end_date_iso,
            )

            const.LOGGER.debug(
                "DEBUG: Badge Maintenance - Reset badge '%s' for kid '%s'. New cycle: %s to %s",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
                new_start_date_iso if new_start_date_iso else "immediate",
                new_end_date_iso,
            )

        # ===============================================================
        # SECTION 4: FINALIZATION - Save updates back to kid data
        # ===============================================================
        # Save the updated progress back to the kid data
        kid_info[const.DATA_KID_BADGE_PROGRESS] = badge_progress

        self._persist()
        self.async_set_updated_data(self._data)

    def _sync_badge_progress_for_kid(self, kid_id: str) -> None:
        """Sync badge progress for a specific kid."""
        # Initialize badge progress for any badges that don't have progress data yet

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # Phase 4: Clean up badge_progress for badges no longer assigned to this kid
        if const.DATA_KID_BADGE_PROGRESS in kid_info:
            badges_to_remove = []
            for progress_badge_id in kid_info[const.DATA_KID_BADGE_PROGRESS]:
                badge_info: BadgeData | None = self.badges_data.get(progress_badge_id)
                # Remove if badge deleted OR kid not in assigned_to list
                if not badge_info or kid_id not in badge_info.get(
                    const.DATA_BADGE_ASSIGNED_TO, []
                ):
                    badges_to_remove.append(progress_badge_id)

            for badge_id in badges_to_remove:
                del kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id]
                const.LOGGER.debug(
                    "DEBUG: Removed badge_progress for badge '%s' from kid '%s' (unassigned or deleted)",
                    badge_id,
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

        for badge_id, badge_info in self.badges_data.items():
            # Feature Change v4.2: Badges now require explicit assignment.
            # Empty assigned_to means badge is not assigned to any kid.
            assigned_to_list = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            is_assigned_to = kid_id in assigned_to_list
            if not is_assigned_to:
                continue

            # Skip cumulative badges (handled separately)
            if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE:
                continue

            # Initialize progress structure if it doesn't exist
            if const.DATA_KID_BADGE_PROGRESS not in kid_info:
                kid_info[const.DATA_KID_BADGE_PROGRESS] = {}

            badge_type = badge_info.get(const.DATA_BADGE_TYPE)

            # --- Set flags based on badge type ---
            has_target = badge_type in const.INCLUDE_TARGET_BADGE_TYPES
            has_special_occasion = (
                badge_type in const.INCLUDE_SPECIAL_OCCASION_BADGE_TYPES
            )
            has_achievement_linked = (
                badge_type in const.INCLUDE_ACHIEVEMENT_LINKED_BADGE_TYPES
            )
            has_challenge_linked = (
                badge_type in const.INCLUDE_CHALLENGE_LINKED_BADGE_TYPES
            )
            has_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES
            has_assigned_to = badge_type in const.INCLUDE_ASSIGNED_TO_BADGE_TYPES
            has_reset_schedule = badge_type in const.INCLUDE_RESET_SCHEDULE_BADGE_TYPES

            # ===============================================================
            # SECTION 1: NEW BADGE SETUP - Create initial progress structure
            # ===============================================================
            badge_progress_dict = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})  # type: ignore[typeddict-item]
            if badge_id not in badge_progress_dict:
                # Get badge details

                # --- Common fields ---
                progress: dict[str, Any] = {
                    const.DATA_KID_BADGE_PROGRESS_NAME: badge_info.get(
                        const.DATA_BADGE_NAME
                    ),
                    const.DATA_KID_BADGE_PROGRESS_TYPE: badge_type,
                    const.DATA_KID_BADGE_PROGRESS_STATUS: const.BADGE_STATE_IN_PROGRESS,
                }

                # --- Target fields ---
                if has_target:
                    target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_TYPE
                    )
                    threshold_value = float(
                        badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE] = target_type
                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE] = (
                        threshold_value
                    )

                    # Initialize all possible progress fields to their defaults if not present
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0.0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED, {}
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED, {}
                    )

                # --- Achievement Linked fields ---
                if has_achievement_linked:
                    # Store the associated achievement ID if present
                    achievement_id = badge_info.get(
                        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                    )
                    if achievement_id:
                        progress[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = (
                            achievement_id
                        )

                # --- Challenge Linked fields ---
                if has_challenge_linked:
                    # Store the associated challenge ID if present
                    challenge_id = badge_info.get(const.DATA_BADGE_ASSOCIATED_CHALLENGE)
                    if challenge_id:
                        progress[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = challenge_id

                # --- Tracked Chores fields ---
                if has_tracked_chores and not has_special_occasion:
                    progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = (
                        self._get_badge_in_scope_chores_list(badge_info, kid_id)  # type: ignore[assignment,call-overload,operator]
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress[const.DATA_BADGE_ASSIGNED_TO] = assigned_to  # type: ignore[assignment,call-overload,operator]

                # --- Awards fields --- Not required for now
                # if has_awards:
                #    awards = badge_info.get(const.DATA_BADGE_AWARDS, {})
                #    progress[const.DATA_BADGE_AWARDS] = awards

                # --- Reset Schedule fields ---
                if has_reset_schedule:
                    reset_schedule = badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
                    recurring_frequency = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        const.FREQUENCY_NONE,
                    )
                    start_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_START_DATE
                    )
                    end_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_END_DATE
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY] = (
                        recurring_frequency
                    )

                    # Set initial schedule if there is a frequency and no end date
                    if recurring_frequency != const.FREQUENCY_NONE:
                        if end_date_iso:
                            progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                                start_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                                end_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
                                const.DEFAULT_ZERO
                            )
                        else:
                            # ---------------------------------------------------------------
                            # Calculate initial end date from today since there is no end date
                            # ---------------------------------------------------------------
                            today_local_iso = kh.get_today_local_iso()
                            is_daily = recurring_frequency == const.FREQUENCY_DAILY
                            is_custom_1_day = (
                                recurring_frequency == const.FREQUENCY_CUSTOM
                                and reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                                )
                                == 1
                                and reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                                )
                                == const.TIME_UNIT_DAYS
                            )

                            if is_daily or is_custom_1_day:
                                # This is special case where if you set a daily badge, you don't want it to get scheduled with
                                # tomorrow as the end date.
                                new_end_date_iso: str | date | None = today_local_iso
                            elif recurring_frequency == const.FREQUENCY_CUSTOM:
                                # Handle other custom frequencies
                                custom_interval = reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                                )
                                custom_interval_unit = reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                                )
                                if custom_interval and custom_interval_unit:
                                    new_end_date_iso = kh.adjust_datetime_by_interval(
                                        today_local_iso,
                                        interval_unit=custom_interval_unit,
                                        delta=custom_interval,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                                else:
                                    # Default fallback to weekly
                                    new_end_date_iso = kh.adjust_datetime_by_interval(
                                        today_local_iso,
                                        interval_unit=const.TIME_UNIT_WEEKS,
                                        delta=1,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                            else:
                                # Use standard frequency helper
                                new_end_date_iso = kh.get_next_scheduled_datetime(
                                    today_local_iso,
                                    interval_type=recurring_frequency,
                                    require_future=True,
                                    return_type=const.HELPER_RETURN_ISO_DATE,
                                )

                            progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                                start_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                                new_end_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
                                const.DEFAULT_ZERO
                            )

                            # Set penalty applied to False
                            # This is to ensure that if the badge is not earned, the penalty will be applied
                            progress[const.DATA_KID_BADGE_PROGRESS_PENALTY_APPLIED] = (
                                False
                            )

                # --- Special Occasion fields ---
                if has_special_occasion:
                    # Add occasion type if present
                    occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE)
                    if occasion_type:
                        progress[const.DATA_BADGE_OCCASION_TYPE] = occasion_type

                # Store the progress data
                kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id] = progress  # type: ignore[assignment,call-overload,operator]

            # ===============================================================
            # SECTION 2: BADGE SYNC - Update existing badge progress data
            # ===============================================================
            else:
                # --- Remove badge progress if badge is no longer available or not assigned to this kid ---
                if badge_id not in self.badges_data or (
                    badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    and kid_id not in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                ):
                    if badge_id in badge_progress_dict:
                        del badge_progress_dict[badge_id]
                        const.LOGGER.info(
                            "INFO: Badge Maintenance - Removed badge progress for badge '%s' from kid '%s' (badge deleted or unassigned).",
                            badge_id,
                            kid_info.get(const.DATA_KID_NAME, kid_id),
                        )
                    continue

                # The badge already exists in progress data - sync configuration fields
                progress = badge_progress_dict[badge_id]  # type: ignore[typeddict-item]

                # --- Common fields ---
                progress[const.DATA_KID_BADGE_PROGRESS_NAME] = badge_info.get(
                    const.DATA_BADGE_NAME, "Unknown Badge"
                )
                progress[const.DATA_KID_BADGE_PROGRESS_TYPE] = badge_type

                # --- Target fields ---
                if has_target:
                    target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_TYPE,
                        const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE] = target_type

                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE] = (
                        badge_info.get(const.DATA_BADGE_TARGET, {}).get(  # type: ignore[assignment,call-overload,operator]
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )

                # --- Special Occasion fields ---
                if has_special_occasion:
                    # Add occasion type if present
                    occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE)
                    if occasion_type:
                        progress[const.DATA_BADGE_OCCASION_TYPE] = occasion_type

                # --- Achievement Linked fields ---
                if has_achievement_linked:
                    achievement_id = badge_info.get(
                        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                    )
                    if achievement_id:
                        progress[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = (
                            achievement_id
                        )

                # --- Challenge Linked fields ---
                if has_challenge_linked:
                    challenge_id = badge_info.get(const.DATA_BADGE_ASSOCIATED_CHALLENGE)
                    if challenge_id:
                        progress[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = challenge_id

                # --- Tracked Chores fields ---
                if has_tracked_chores and not has_special_occasion:
                    progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = (
                        self._get_badge_in_scope_chores_list(badge_info, kid_id)  # type: ignore[assignment,call-overload,operator]
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress[const.DATA_BADGE_ASSIGNED_TO] = assigned_to  # type: ignore[assignment,call-overload,operator]

                # --- Awards fields --- Not required for now
                # if has_awards:
                #    awards = badge_info.get(const.DATA_BADGE_AWARDS, {})
                #    progress[const.DATA_BADGE_AWARDS] = awards

                # --- Reset Schedule fields ---
                if has_reset_schedule:
                    reset_schedule = badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
                    recurring_frequency = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        const.FREQUENCY_NONE,
                    )
                    start_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_START_DATE
                    )
                    end_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_END_DATE
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY] = (
                        recurring_frequency
                    )
                    # Only update start and end dates if they have values
                    if start_date_iso:
                        progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                            start_date_iso
                        )
                    if end_date_iso:
                        progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = end_date_iso

    def _manage_cumulative_badge_maintenance(self, kid_id: str) -> None:
        """
        Manages cumulative badge maintenance for a kid:
        - Evaluates whether the maintenance or grace period has ended.
        - Updates badge status (active, grace, or demoted) based on cycle points.
        - Resets cycle points and updates maintenance windows if needed.
        - Updates the current badge information based on maintenance outcome.
        """

        # Retrieve kid-specific information from the kids_data dictionary.
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # Retrieve the cumulative badge progress data for the kid.
        cumulative_badge_progress = kid_info.setdefault(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS,
            {},  # type: ignore[typeddict-item]
        )

        # DEBUG: Log starting state for the kid.
        kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
        const.LOGGER.debug(
            "DEBUG: Manage Cumulative Badge Maintenance - Kid=%s, Initial Status=%s, Cycle Points=%.2f",
            kid_name,
            cumulative_badge_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS, "active"
            ),
            float(
                cumulative_badge_progress.get(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0
                )
            ),
        )

        # Extract current maintenance and grace end dates, status, and accumulated cycle points.
        end_date_iso = cumulative_badge_progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
        )
        grace_date_iso = cumulative_badge_progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
        )
        status = cumulative_badge_progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.CUMULATIVE_BADGE_STATE_ACTIVE,
        )
        cycle_points = float(
            cumulative_badge_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0
            )
        )

        # Get today's date in ISO format using the local timezone.
        today_local_iso = kh.get_today_local_iso()

        # Get badge level information: highest earned badge, next lower badge, baseline, etc.
        highest_earned, _, next_lower, baseline, _ = self._get_cumulative_badge_levels(
            kid_id
        )
        if not highest_earned:
            return

        # Determine the maintenance threshold, reset type, grace period duration, and whether reset is enabled.
        maintenance_required = float(
            highest_earned.get(const.DATA_BADGE_TARGET, {}).get(
                const.DATA_BADGE_MAINTENANCE_RULES, const.DEFAULT_ZERO
            )
        )
        reset_schedule = highest_earned.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        frequency = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY
        )
        grace_days = int(
            reset_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS, const.DEFAULT_ZERO
            )
        )
        reset_enabled = frequency is not None and frequency != const.FREQUENCY_NONE

        # DEBUG: Log the key parameters derived from today's date and the highest earned badge.
        const.LOGGER.debug(
            "DEBUG: Manage Cumulative Badge Maintenance - today_local=%s, "
            "highest_earned=%s, maintenance_required=%.2f, reset_type=%s, "
            "grace_days=%d, reset_enabled=%s",
            today_local_iso,
            highest_earned.get(const.DATA_BADGE_NAME),
            maintenance_required,
            frequency,
            grace_days,
            reset_enabled,
        )

        # If the badge is not recurring (reset not enabled):
        # clear any existing maintenance and grace dates and exit the function.
        if not reset_enabled:
            cumulative_badge_progress.update(
                {  # type: ignore[typeddict-item]
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE: None,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE: None,
                }
            )
            self.kids_data[kid_id][const.DATA_KID_CUMULATIVE_BADGE_PROGRESS] = (
                cumulative_badge_progress
            )
            self._persist()
            self.async_set_updated_data(self._data)
            return

        award_success = False
        demotion_required = False

        # Check if the maintenance period (or grace period) has ended based on the current status.
        if (
            status
            in (
                const.CUMULATIVE_BADGE_STATE_ACTIVE,
                const.CUMULATIVE_BADGE_STATE_DEMOTED,
            )
            and end_date_iso
            and today_local_iso >= end_date_iso
        ):
            # If cycle points meet or exceed the required maintenance threshold, the badge is maintained.
            if cycle_points >= maintenance_required:
                award_success = True
            # If it is already past the grace date, then a demotion is required (edge case)
            elif grace_date_iso and today_local_iso >= grace_date_iso:
                demotion_required = True
            # Otherwise, if a grace period is allowed, move the badge status into the grace state.
            elif grace_days > const.DEFAULT_ZERO:
                cumulative_badge_progress[
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS
                ] = const.CUMULATIVE_BADGE_STATE_GRACE
            # If neither condition is met, then a demotion is required.
            else:
                demotion_required = True

        elif status == const.CUMULATIVE_BADGE_STATE_GRACE:
            # While in the grace period, if the required cycle points are met, maintain the badge.
            if cycle_points >= maintenance_required:
                award_success = True
            # If the grace period has expired, then a demotion is required.
            elif grace_date_iso and today_local_iso >= grace_date_iso:
                demotion_required = True

        # Determine the frequency and custom fields before proceeding
        reset_schedule = highest_earned.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        frequency = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        )
        custom_interval = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
        )
        custom_interval_unit = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
        )
        # Use reference_dt if available; otherwise, default to today's date
        base_date_iso = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE, today_local_iso
        )

        # Fallback to today's date if reference_dt is None
        if not base_date_iso:
            base_date_iso = today_local_iso

        # If the base date is in the future, use it as the reference date so the next schedule is in the future of that date.
        # As an example if on June 5th I create a badge and give it an end date of July 7th and chooose frequency of Period End,
        # then the expectation would be a next scheduled date of Sept 30th, not June 30th.
        reference_datetime_iso = max(today_local_iso, base_date_iso)

        # Initialize the variables for the next maintenance end date and grace end date
        next_end: str | date | None = None
        next_grace = None

        # First-Time Assignment:
        # If the badge is reset-enabled but no maintenance end date is set (i.e., first-time award),
        # then calculate and set the maintenance and grace dates.
        is_first_time = reset_enabled and not cumulative_badge_progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
        )

        # Check if the maintenance period or grace period has ended
        if award_success or demotion_required or is_first_time:
            if frequency == const.FREQUENCY_CUSTOM:
                # If custom interval and unit are valid, calculate next_end make sure it is in the future and past the reference
                if custom_interval and custom_interval_unit:
                    next_end = kh.adjust_datetime_by_interval(
                        base_date=base_date_iso,
                        interval_unit=custom_interval_unit,  # Fix: change from custom_interval_unit to interval_unit
                        delta=custom_interval,  # Fix: change from custom_interval to delta
                        require_future=True,
                        reference_datetime=reference_datetime_iso,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
                else:
                    # Fallback to existing logic if custom interval/unit are invalid
                    next_end = kh.get_next_scheduled_datetime(
                        base_date_iso,
                        interval_type=frequency,
                        require_future=True,
                        reference_datetime=reference_datetime_iso,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
            else:
                # Default behavior for non-custom frequencies
                base_date_iso = today_local_iso
                next_end = kh.get_next_scheduled_datetime(
                    base_date_iso,
                    interval_type=frequency,
                    require_future=True,
                    reference_datetime=reference_datetime_iso,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )

            # Compute the grace period end date by adding the grace period (in days) to the maintenance end date
            # Cast ensures next_end is str | date (not None) for the interval calculation
            next_grace = kh.adjust_datetime_by_interval(
                cast("str | date", next_end),
                const.TIME_UNIT_DAYS,
                grace_days,
                require_future=True,
                return_type=const.HELPER_RETURN_ISO_DATE,
            )

        # If the badge maintenance requirements are met, update the badge as successfully maintained.
        if award_success:
            cumulative_badge_progress.update(
                {  # type: ignore[typeddict-item]
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE: next_end,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE: next_grace,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS: const.CUMULATIVE_BADGE_STATE_ACTIVE,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: highest_earned.get(
                        const.DATA_BADGE_INTERNAL_ID
                    ),
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME: highest_earned.get(
                        const.DATA_BADGE_NAME
                    ),
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD: highest_earned.get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE
                    ),
                }
            )
            # Award the badge through the helper function.
            badge_id = highest_earned.get(const.DATA_BADGE_INTERNAL_ID)
            if badge_id:
                self._award_badge(kid_id, badge_id)

        # If demotion is required due to failure to meet maintenance requirements:
        if demotion_required:
            cumulative_badge_progress.update(
                {  # type: ignore[typeddict-item]
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS: const.CUMULATIVE_BADGE_STATE_DEMOTED,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: next_lower.get(
                        const.DATA_BADGE_INTERNAL_ID
                    )
                    if next_lower
                    else None,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME: next_lower.get(
                        const.DATA_BADGE_NAME
                    )
                    if next_lower
                    else None,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD: next_lower.get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE
                    )
                    if next_lower
                    else None,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE: baseline
                    + cycle_points,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS: 0,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE: next_end,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE: next_grace,
                }
            )
            self._update_point_multiplier_for_kid(kid_id)

        # If is first_time, then set the end dates
        if is_first_time:
            cumulative_badge_progress.update(
                {  # type: ignore[typeddict-item]
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE: next_end,
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE: next_grace,
                }
            )

        # Simplified final debug: show only key maintenance info.
        const.LOGGER.debug(
            "DEBUG: Manage Cumulative Badge Maintenance - Final (Kid=%s): Status=%s, End=%s, Grace=%s, CyclePts=%.2f",
            kid_name,
            cumulative_badge_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS
            ),
            cumulative_badge_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
            ),
            cumulative_badge_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
            ),
            float(
                cumulative_badge_progress.get(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0
                )
            ),
        )

        # Save the updated progress and notify any listeners. The extra update here is to do a merge
        # as a precaution ensuring nothing gets lost if other keys have been changed during processign
        existing_progress = self.kids_data[kid_id].get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        )
        existing_progress.update(cumulative_badge_progress)
        self.kids_data[kid_id][const.DATA_KID_CUMULATIVE_BADGE_PROGRESS] = (
            existing_progress
        )

        self._persist()
        self.async_set_updated_data(self._data)

    def _get_cumulative_badge_levels(
        self, kid_id: str
    ) -> tuple[dict | None, dict | None, dict | None, float, float]:
        """
        Determines the highest earned cumulative badge for a kid, and the next higher/lower badge tiers.

        Returns:
            - highest_earned_badge_info (dict or None)
            - next_higher_badge_info (dict or None)
            - next_lower_badge_info (dict or None)
            - baseline (float)
            - cycle_points (float)
        """

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return None, None, None, 0.0, 0.0

        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        baseline = round(
            float(progress.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE, 0)),
            const.DATA_FLOAT_PRECISION,
        )
        cycle_points = round(
            float(
                progress.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0)
            ),
            const.DATA_FLOAT_PRECISION,
        )
        total_points = baseline + cycle_points

        # Get sorted list of cumulative badges (lowest to highest threshold)
        cumulative_badges = sorted(
            (
                (badge_id, badge_info)
                for badge_id, badge_info in self.badges_data.items()
                if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE
            ),
            key=lambda item: float(
                item[1]
                .get(const.DATA_BADGE_TARGET, {})
                .get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)
            ),
        )

        if not cumulative_badges:
            # No cumulative badges exist - reset tracking values to 0
            # When a new cumulative badge is added, tracking will start fresh
            return None, None, None, 0.0, 0.0

        highest_earned = None
        next_higher = None
        next_lower = None
        previous_badge_info = None

        for _badge_id, badge_info in cumulative_badges:
            threshold = float(
                badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                )
            )

            # Set the is_assigned_to flag: True if the list is empty or if kid_id is in the assigned list
            is_assigned_to = not badge_info.get(
                const.DATA_BADGE_ASSIGNED_TO, []
            ) or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])

            if is_assigned_to:
                if total_points >= threshold:
                    highest_earned = badge_info
                    next_lower = previous_badge_info
                else:
                    next_higher = badge_info
                    break

                previous_badge_info = badge_info

        return highest_earned, next_higher, next_lower, baseline, cycle_points  # type: ignore[return-value]

    # -------------------------------------------------------------------------------------
    # Penalties: Apply
    # -------------------------------------------------------------------------------------

    def apply_penalty(self, parent_name: str, kid_id: str, penalty_id: str):
        """Apply penalty => negative points to reduce kid's points."""
        penalty_info: PenaltyData | None = self.penalties_data.get(penalty_id)
        if not penalty_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PENALTY,
                    "name": penalty_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        penalty_pts = penalty_info.get(const.DATA_PENALTY_POINTS, const.DEFAULT_ZERO)
        self.update_kid_points(
            kid_id, delta=penalty_pts, source=const.POINTS_SOURCE_PENALTIES
        )

        # increment penalty_applies
        if penalty_id in kid_info[const.DATA_KID_PENALTY_APPLIES]:
            kid_info[const.DATA_KID_PENALTY_APPLIES][penalty_id] += 1  # type: ignore[assignment,call-overload,operator]
        else:
            kid_info[const.DATA_KID_PENALTY_APPLIES][penalty_id] = 1  # type: ignore[assignment,call-overload,operator]

        # Send a notification to the kid that a penalty was applied
        extra_data = {const.DATA_KID_ID: kid_id, const.DATA_PENALTY_ID: penalty_id}
        self.hass.async_create_task(
            self._notify_kid_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENALTY_APPLIED,
                message_data={
                    "penalty_name": penalty_info[const.DATA_PENALTY_NAME],
                    "points": penalty_pts,
                },
                extra_data=extra_data,
            )
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------
    # Bonuses: Apply
    # -------------------------------------------------------------------------

    def apply_bonus(self, parent_name: str, kid_id: str, bonus_id: str):
        """Apply bonus => positive points to increase kid's points."""
        bonus_info: BonusData | None = self.bonuses_data.get(bonus_id)
        if not bonus_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BONUS,
                    "name": bonus_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        bonus_pts = bonus_info.get(const.DATA_BONUS_POINTS, const.DEFAULT_ZERO)
        self.update_kid_points(
            kid_id, delta=bonus_pts, source=const.POINTS_SOURCE_BONUSES
        )

        # increment bonus_applies
        if bonus_id in kid_info[const.DATA_KID_BONUS_APPLIES]:
            kid_info[const.DATA_KID_BONUS_APPLIES][bonus_id] += 1  # type: ignore[assignment,call-overload,operator]
        else:
            kid_info[const.DATA_KID_BONUS_APPLIES][bonus_id] = 1  # type: ignore[assignment,call-overload,operator]

        # Send a notification to the kid that a bonus was applied
        extra_data = {const.DATA_KID_ID: kid_id, const.DATA_BONUS_ID: bonus_id}
        self.hass.async_create_task(
            self._notify_kid_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_BONUS_APPLIED,
                message_data={
                    "bonus_name": bonus_info[const.DATA_BONUS_NAME],
                    "points": bonus_pts,
                },
                extra_data=extra_data,
            )
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------
    # Achievements: Check, Award
    # -------------------------------------------------------------------------
    def _check_achievements_for_kid(self, kid_id: str):
        """Evaluate all achievement criteria for a given kid.

        For each achievement not already awarded, check its type and update progress accordingly.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        today_local = kh.get_today_local_date()

        for achievement_id, achievement_info in self._data[
            const.DATA_ACHIEVEMENTS
        ].items():
            progress = achievement_info.setdefault(const.DATA_ACHIEVEMENT_PROGRESS, {})
            if kid_id in progress and progress[kid_id].get(
                const.DATA_ACHIEVEMENT_AWARDED, False
            ):
                continue

            ach_type = achievement_info.get(const.DATA_ACHIEVEMENT_TYPE)
            target = achievement_info.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)

            # For a streak achievement, update a streak counter:
            if ach_type == const.ACHIEVEMENT_TYPE_STREAK:
                progress = progress.setdefault(
                    kid_id,
                    {
                        const.DATA_KID_CURRENT_STREAK: const.DEFAULT_ZERO,
                        const.DATA_KID_LAST_STREAK_DATE: None,
                        const.DATA_ACHIEVEMENT_AWARDED: False,
                    },
                )

                self._update_streak_progress(progress, today_local)
                if progress[const.DATA_KID_CURRENT_STREAK] >= target:
                    self._award_achievement(kid_id, achievement_id)

            # For a total achievement, simply compare total completed chores:
            elif ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
                # Get per–kid progress for this achievement.
                progress = achievement_info.setdefault(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).setdefault(
                    kid_id,
                    {
                        const.DATA_ACHIEVEMENT_BASELINE: None,
                        const.DATA_ACHIEVEMENT_CURRENT_VALUE: const.DEFAULT_ZERO,
                        const.DATA_ACHIEVEMENT_AWARDED: False,
                    },
                )

                # Set the baseline so that we only count chores done after deployment.
                if (
                    const.DATA_ACHIEVEMENT_BASELINE not in progress
                    or progress[const.DATA_ACHIEVEMENT_BASELINE] is None
                ):
                    chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
                    progress[const.DATA_ACHIEVEMENT_BASELINE] = chore_stats.get(
                        const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, const.DEFAULT_ZERO
                    )

                # Calculate progress as (current total minus baseline)
                chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
                current_total = chore_stats.get(
                    const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, const.DEFAULT_ZERO
                )

                progress[const.DATA_ACHIEVEMENT_CURRENT_VALUE] = current_total

                effective_target = progress[const.DATA_ACHIEVEMENT_BASELINE] + target

                if current_total >= effective_target:
                    self._award_achievement(kid_id, achievement_id)

            # For daily minimum achievement, compare total daily chores:
            elif ach_type == const.ACHIEVEMENT_TYPE_DAILY_MIN:
                # Initialize progress for this achievement if missing.
                progress = achievement_info.setdefault(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).setdefault(
                    kid_id,
                    {
                        const.DATA_ACHIEVEMENT_LAST_AWARDED_DATE: None,
                        const.DATA_ACHIEVEMENT_AWARDED: False,
                    },
                )

                today_local_iso = kh.get_today_local_iso()

                # Only award bonus if not awarded today AND the kid's daily count meets the threshold.
                chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
                daily_count = chore_stats.get(
                    const.DATA_KID_CHORE_STATS_APPROVED_TODAY, const.DEFAULT_ZERO
                )
                if (
                    progress.get(const.DATA_ACHIEVEMENT_LAST_AWARDED_DATE)
                    != today_local_iso
                    and daily_count >= target
                ):
                    self._award_achievement(kid_id, achievement_id)
                    progress[const.DATA_ACHIEVEMENT_LAST_AWARDED_DATE] = today_local_iso

    def _award_achievement(self, kid_id: str, achievement_id: str):
        """Award the achievement to the kid.

        Update the achievement progress to indicate it is earned,
        and send notifications to both the kid and their parents.
        """
        achievement_info = self.achievements_data.get(achievement_id)
        if not achievement_info:
            const.LOGGER.error(
                "ERROR: Achievement Award - Achievement ID '%s' not found.",
                achievement_id,
            )
            return

        # Get or create the existing progress dictionary for this kid
        progress_for_kid = achievement_info.setdefault(
            const.DATA_ACHIEVEMENT_PROGRESS, {}
        ).get(kid_id)
        if progress_for_kid is None:
            # If it doesn't exist, initialize it with baseline from the kid's current total.
            kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
            chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
            progress_dict = {
                const.DATA_ACHIEVEMENT_BASELINE: chore_stats.get(
                    const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, const.DEFAULT_ZERO
                ),
                const.DATA_ACHIEVEMENT_CURRENT_VALUE: const.DEFAULT_ZERO,
                const.DATA_ACHIEVEMENT_AWARDED: False,
            }
            achievement_info[const.DATA_ACHIEVEMENT_PROGRESS][kid_id] = progress_dict  # type: ignore[assignment,call-overload,operator]
            progress_for_kid = progress_dict  # type: ignore[assignment,call-overload,operator]

        # Mark achievement as earned for the kid by storing progress (e.g. set to target)
        progress_for_kid[const.DATA_ACHIEVEMENT_AWARDED] = True  # type: ignore[assignment,call-overload,operator]  # type: ignore[index]
        progress_for_kid[const.DATA_ACHIEVEMENT_CURRENT_VALUE] = achievement_info.get(  # type: ignore[assignment,call-overload,operator]  # type: ignore[index]
            const.DATA_ACHIEVEMENT_TARGET_VALUE, 1
        )

        # Award the extra reward points defined in the achievement
        extra_points = achievement_info.get(
            const.DATA_ACHIEVEMENT_REWARD_POINTS, const.DEFAULT_ZERO
        )
        kid_info_points: KidData | None = self.kids_data.get(kid_id)
        if kid_info_points is not None:
            self.update_kid_points(
                kid_id, delta=extra_points, source=const.POINTS_SOURCE_ACHIEVEMENTS
            )

        # Notify kid and parents
        extra_data = {
            const.DATA_KID_ID: kid_id,
            const.DATA_ACHIEVEMENT_ID: achievement_id,
        }
        self.hass.async_create_task(
            self._notify_kid_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_KID,
                message_data={
                    "achievement_name": achievement_info.get(
                        const.DATA_ACHIEVEMENT_NAME
                    ),
                },
                extra_data=extra_data,
            )
        )
        self.hass.async_create_task(
            self._notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_PARENT,
                message_data={
                    "kid_name": self.kids_data[kid_id][const.DATA_KID_NAME],
                    "achievement_name": achievement_info.get(
                        const.DATA_ACHIEVEMENT_NAME
                    ),
                },
                extra_data=extra_data,
            )
        )
        const.LOGGER.debug(
            "DEBUG: Achievement Award - Achievement ID '%s' to Kid ID '%s'",
            achievement_info.get(const.DATA_ACHIEVEMENT_NAME),
            kid_id,
        )
        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------
    # Challenges: Check, Award
    # -------------------------------------------------------------------------
    def _check_challenges_for_kid(self, kid_id: str):
        """Evaluate all challenge criteria for a given kid.

        Checks that the challenge is active and then updates progress.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        now_utc = dt_util.utcnow()
        for challenge_id, challenge_info in self.challenges_data.items():
            progress = challenge_info.setdefault(const.DATA_CHALLENGE_PROGRESS, {})
            if kid_id in progress and progress[kid_id].get(  # type: ignore[attr-defined]
                const.DATA_CHALLENGE_AWARDED, False
            ):
                continue

            # Check challenge window
            start_date_utc = kh.parse_datetime_to_utc(
                challenge_info.get(const.DATA_CHALLENGE_START_DATE)  # type: ignore[arg-type]
            )

            end_date_utc = kh.parse_datetime_to_utc(
                challenge_info.get(const.DATA_CHALLENGE_END_DATE)  # type: ignore[arg-type]
            )

            if start_date_utc and now_utc < start_date_utc:
                continue
            if end_date_utc and now_utc > end_date_utc:
                continue

            target = challenge_info.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
            challenge_type = challenge_info.get(const.DATA_CHALLENGE_TYPE)

            # For a total count challenge:
            if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                progress = progress.setdefault(  # type: ignore[assignment,call-overload,operator]
                    kid_id,
                    {  # type: ignore[arg-type]
                        const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                        const.DATA_CHALLENGE_AWARDED: False,
                    },
                )

                if progress.get(const.DATA_CHALLENGE_COUNT, 0) >= target:
                    self._award_challenge(kid_id, challenge_id)
            # For a daily minimum challenge, you might store per-day counts:
            elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                progress = progress.setdefault(  # type: ignore[assignment,call-overload,operator]
                    kid_id,
                    {  # type: ignore[arg-type]
                        const.DATA_CHALLENGE_DAILY_COUNTS: {},
                        const.DATA_CHALLENGE_AWARDED: False,
                    },
                )

                required_daily = challenge_info.get(
                    const.DATA_CHALLENGE_REQUIRED_DAILY, 1
                )

                if start_date_utc and end_date_utc:
                    num_days = (end_date_utc - start_date_utc).days + 1
                    # Verify for each day:
                    success = True
                    for n in range(num_days):
                        day = (start_date_utc + timedelta(days=n)).date().isoformat()
                        if (
                            progress[const.DATA_CHALLENGE_DAILY_COUNTS].get(  # type: ignore[attr-defined]
                                day, const.DEFAULT_ZERO
                            )
                            < required_daily
                        ):
                            success = False
                            break
                    if success:
                        self._award_challenge(kid_id, challenge_id)

    def _award_challenge(self, kid_id: str, challenge_id: str):
        """Award the challenge to the kid.

        Update progress and notify kid/parents.
        """
        challenge_info = self.challenges_data.get(challenge_id)
        if not challenge_info:
            const.LOGGER.error(
                "ERROR: Challenge Award - Challenge ID '%s' not found", challenge_id
            )
            return

        # Get or create the existing progress dictionary for this kid
        progress_for_kid = challenge_info.setdefault(
            const.DATA_CHALLENGE_PROGRESS, {}
        ).setdefault(
            kid_id,
            {  # type: ignore[arg-type]
                const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                const.DATA_CHALLENGE_AWARDED: False,
            },
        )

        # Mark challenge as earned for the kid by storing progress
        progress_for_kid[const.DATA_CHALLENGE_AWARDED] = True  # type: ignore[assignment,call-overload,operator]  # type: ignore[index]
        progress_for_kid[const.DATA_CHALLENGE_COUNT] = challenge_info.get(  # type: ignore[assignment,call-overload,operator]  # type: ignore[index]
            const.DATA_CHALLENGE_TARGET_VALUE, 1
        )

        # Award extra reward points from the challenge
        extra_points = challenge_info.get(
            const.DATA_CHALLENGE_REWARD_POINTS, const.DEFAULT_ZERO
        )
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if kid_info is not None:
            self.update_kid_points(
                kid_id, delta=extra_points, source=const.POINTS_SOURCE_CHALLENGES
            )

        # Notify kid and parents
        extra_data = {const.DATA_KID_ID: kid_id, const.DATA_CHALLENGE_ID: challenge_id}
        self.hass.async_create_task(
            self._notify_kid_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_KID,
                message_data={
                    "challenge_name": challenge_info.get(const.DATA_CHALLENGE_NAME),
                },
                extra_data=extra_data,
            )
        )
        self.hass.async_create_task(
            self._notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_PARENT,
                message_data={
                    "kid_name": self.kids_data[kid_id][const.DATA_KID_NAME],
                    "challenge_name": challenge_info.get(const.DATA_CHALLENGE_NAME),
                },
                extra_data=extra_data,
            )
        )
        const.LOGGER.debug(
            "DEBUG: Challenge Award - Challenge ID '%s' to Kid ID '%s'",
            challenge_info.get(const.DATA_CHALLENGE_NAME),
            kid_id,
        )
        self._persist()
        self.async_set_updated_data(self._data)

    def _update_streak_progress(
        self, progress: AchievementProgress, today: date
    ) -> None:
        """Update a streak progress dict.

        If the last approved date was yesterday, increment the streak.
        Otherwise, reset to 1.
        """
        last_date = None
        last_date_str = progress.get(const.DATA_KID_LAST_STREAK_DATE)
        if last_date_str:
            try:
                last_date = date.fromisoformat(last_date_str)
            except (ValueError, TypeError, KeyError):
                last_date = None

        # If already updated today, do nothing
        if last_date == today:
            return

        # If yesterday was the last update, increment the streak
        if last_date == today - timedelta(days=1):
            current_streak = progress.get(const.DATA_KID_CURRENT_STREAK, 0)
            progress[const.DATA_KID_CURRENT_STREAK] = current_streak + 1  # type: ignore[typeddict-item]

        # Reset to 1 if not done yesterday
        else:
            progress[const.DATA_KID_CURRENT_STREAK] = 1  # type: ignore[typeddict-item]

        progress[const.DATA_KID_LAST_STREAK_DATE] = today.isoformat()

    # -------------------------------------------------------------------------------------
    # Overdue Logic Helpers
    # -------------------------------------------------------------------------------------

    def _apply_overdue_if_due(
        self,
        kid_id: str,
        chore_id: str,
        due_date_iso: str | None,
        now_utc: datetime,
        chore_info: ChoreData,
    ) -> bool:
        """Check if chore is past due and apply overdue state if so.

        Consolidates common overdue logic shared across all completion criteria:
        - Phase 5 NEVER_OVERDUE handling
        - Due date parsing with error handling
        - "Not yet due" early exit with overdue clearing
        - Overdue state application via _process_chore_state
        - Notification via _notify_overdue_chore

        Args:
            kid_id: The kid to check/mark overdue
            chore_id: The chore to check
            due_date_iso: ISO format due date string (or None if no due date)
            now_utc: Current UTC datetime for comparison
            chore_info: Chore info dict for notification context

        Returns:
            True if overdue was applied, False if not (not yet due, no due date,
            NEVER_OVERDUE, or parse error)
        """
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))

        # Phase 5: Check overdue handling type
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        if overdue_handling == const.OVERDUE_HANDLING_NEVER_OVERDUE:
            return False

        # No due date means no overdue possible - clear if previously set
        if not due_date_iso:
            if chore_id in kid_info.get(const.DATA_KID_OVERDUE_CHORES, []):
                self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
            return False

        # Parse due date
        try:
            due_date_utc = kh.parse_datetime_to_utc(due_date_iso)
        except (ValueError, TypeError, AttributeError) as err:
            const.LOGGER.error(
                "ERROR: Overdue Check - Error parsing due date '%s' for Chore '%s', Kid '%s': %s",
                due_date_iso,
                chore_info.get(const.DATA_CHORE_NAME, chore_id),
                kid_id,
                err,
            )
            return False

        if not due_date_utc:
            return False

        # Not yet overdue - clear any existing overdue status
        if now_utc < due_date_utc:
            if chore_id in kid_info.get(const.DATA_KID_OVERDUE_CHORES, []):
                self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
            return False

        # Past due date - mark as overdue and notify
        self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_OVERDUE)
        self._notify_overdue_chore(
            kid_id, chore_id, dict(chore_info), due_date_utc, now_utc
        )
        return True

    def _check_overdue_for_chore(
        self,
        chore_id: str,
        chore_info: ChoreData,
        now_utc: datetime,
    ) -> None:
        """Check and apply overdue status for a chore (any completion criteria).

        Unified handler for INDEPENDENT, SHARED, and SHARED_FIRST completion criteria.
        Uses _apply_overdue_if_due() for core overdue application logic.
        Uses _get_effective_due_date() for due date resolution.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime for comparison
        """
        # Early exit for NEVER_OVERDUE
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        if overdue_handling == const.OVERDUE_HANDLING_NEVER_OVERDUE:
            return

        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # SHARED_FIRST special handling
        claimant_kid_id: str | None = None
        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Check if chore is already completed by any kid
            any_approved = any(
                self.is_approved_in_current_period(kid_id, chore_id)
                for kid_id in assigned_kids
            )
            # If any kid completed it, clear overdue for everyone and exit
            if any_approved:
                for kid_id in assigned_kids:
                    if self.is_overdue(kid_id, chore_id):
                        self._process_chore_state(
                            kid_id, chore_id, const.CHORE_STATE_PENDING
                        )
                return

            # Find claimant (if any) - only claimant can be overdue in SHARED_FIRST
            claimant_kid_id = next(
                (
                    kid_id
                    for kid_id in assigned_kids
                    if self.has_pending_claim(kid_id, chore_id)
                ),
                None,
            )

        # Check each assigned kid
        for kid_id in assigned_kids:
            if not kid_id:
                continue

            # Skip if already claimed or approved (applies to all criteria)
            if self.has_pending_claim(kid_id, chore_id):
                continue
            if self.is_approved_in_current_period(kid_id, chore_id):
                continue

            # SHARED_FIRST: Handle special states
            if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
                current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)

                # Kids in completed_by_other state should never be overdue
                if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
                    if self.is_overdue(kid_id, chore_id):
                        self._process_chore_state(
                            kid_id, chore_id, const.CHORE_STATE_COMPLETED_BY_OTHER
                        )
                    continue

                # If there's a claimant and this isn't them, clear overdue and skip
                if claimant_kid_id and kid_id != claimant_kid_id:
                    if self.is_overdue(kid_id, chore_id):
                        self._process_chore_state(
                            kid_id, chore_id, const.CHORE_STATE_PENDING
                        )
                    continue

            # Get effective due date and apply overdue check
            due_str = self._get_effective_due_date(chore_id, kid_id)
            self._apply_overdue_if_due(kid_id, chore_id, due_str, now_utc, chore_info)

    # -------------------------------------------------------------------------
    # Overdue Notifications
    # -------------------------------------------------------------------------

    def _notify_overdue_chore(
        self,
        kid_id: str,
        chore_id: str,
        chore_info: dict[str, Any],
        due_date_utc: datetime,
        now_utc: datetime,
    ) -> None:
        """Send overdue notification to kid and parents if not already notified in last 24 hours."""
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))

        # Check notification timestamp
        if const.DATA_KID_OVERDUE_NOTIFICATIONS not in kid_info:
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = {}  # type: ignore[typeddict-item]

        overdue_notifs: dict[str, str] = kid_info.get(
            const.DATA_KID_OVERDUE_NOTIFICATIONS, {}
        )  # type: ignore[typeddict-item]
        last_notif_str = overdue_notifs.get(chore_id)
        notify = False

        if last_notif_str:
            try:
                last_dt = kh.parse_datetime_to_utc(last_notif_str)
                if (
                    last_dt is None
                    or (last_dt < due_date_utc)
                    or (
                        (now_utc - last_dt)
                        >= timedelta(hours=const.DEFAULT_NOTIFY_DELAY_REMINDER)
                    )
                ):
                    notify = True
            except (ValueError, TypeError, AttributeError) as err:
                const.LOGGER.error(
                    "ERROR: Overdue Notification - Error parsing timestamp '%s' for Chore ID '%s', Kid ID '%s': %s",
                    last_notif_str,
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_id,
                    err,
                )
                notify = True
        else:
            notify = True

        if notify:
            overdue_notifs[chore_id] = now_utc.isoformat()
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = overdue_notifs  # type: ignore[typeddict-item]
            # Overdue notifications for KIDS include a Claim button (v0.5.0+)
            # Overdue notifications for PARENTS are informational only (no action buttons)
            # Approve/Disapprove only make sense for claimed chores awaiting approval
            from .notification_helper import build_claim_action

            # Get kid's language for date formatting
            kid_language = kid_info.get(
                const.DATA_KID_DASHBOARD_LANGUAGE, self.hass.config.language
            )
            self.hass.async_create_task(
                self._notify_kid_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE,
                    message_data={
                        "chore_name": chore_info.get(
                            const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                        ),
                        "due_date": kh.format_short_datetime(
                            due_date_utc, language=kid_language
                        ),
                    },
                    actions=build_claim_action(kid_id, chore_id),
                )
            )
            # Use system language for date formatting (parent-specific formatting
            # would require restructuring the notification loop)
            # Build action buttons: Complete (approve directly), Skip (reset/reschedule), Remind
            from .notification_helper import (
                build_complete_action,
                build_remind_action,
                build_skip_action,
            )

            parent_actions = []
            parent_actions.extend(build_complete_action(kid_id, chore_id))
            parent_actions.extend(build_skip_action(kid_id, chore_id))
            parent_actions.extend(build_remind_action(kid_id, chore_id))

            self.hass.async_create_task(
                self._notify_parents_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE,
                    message_data={
                        "chore_name": chore_info.get(
                            const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                        ),
                        "due_date": kh.format_short_datetime(
                            due_date_utc, language=self.hass.config.language
                        ),
                    },
                    actions=parent_actions,
                    tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                    tag_identifiers=(chore_id, kid_id),
                )
            )

    async def _check_overdue_chores(self, now: datetime | None = None):
        """Check and mark overdue chores if due date is passed.

        Branching logic based on completion criteria:
        - INDEPENDENT: Each kid can have different due dates (per-kid storage)
        - SHARED_*: All kids share same due date (chore-level storage)

        Send an overdue notification only if not sent in the last 24 hours.
        """
        # PERF: Measure overdue scan duration
        perf_start = time.perf_counter()

        now_utc = dt_util.utcnow()
        const.LOGGER.debug(
            "Overdue Chores - Starting check at %s",
            now_utc.isoformat(),
        )

        for chore_id, chore_info in self.chores_data.items():
            # Get the list of assigned kids
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

            # Check if all assigned kids have either claimed or approved the chore
            # v0.4.0+: Uses timestamp-based helpers instead of deprecated lists
            all_kids_claimed_or_approved = all(
                self.has_pending_claim(kid_id, chore_id)
                or self.is_approved_in_current_period(kid_id, chore_id)
                for kid_id in assigned_kids
            )

            # Only skip the chore if ALL assigned kids have acted on it
            if all_kids_claimed_or_approved:
                continue

            # Use unified overdue check handler (handles all completion criteria)
            self._check_overdue_for_chore(chore_id, chore_info, now_utc)

        const.LOGGER.debug("Overdue Chores - Check completed")

        # PERF: Log overdue scan duration
        perf_duration = time.perf_counter() - perf_start
        chore_count = len(self.chores_data)
        kid_count = len(self.kids_data)
        const.LOGGER.debug(
            "PERF: _check_overdue_chores() took %.3fs for %d chores × %d kids = %d operations",
            perf_duration,
            chore_count,
            kid_count,
            chore_count * kid_count,
        )

    async def _check_due_date_reminders(self) -> None:
        """Check for chores due soon and send reminder notifications to kids (v0.5.0+).

        Hooks into coordinator refresh cycle (typically every 5 min) to check for
        chores that are due within the next 30 minutes and haven't had reminders sent.

        Timing behavior:
        - Reminder window: 30 minutes before due date
        - Check frequency: Every coordinator refresh (~5 min)
        - Practical timing: Kids receive notification 25-35 min before due

        Tracking:
        - Uses transient `_due_soon_reminders_sent` set (resets on HA restart)
        - Key format: "{chore_id}:{kid_id}"
        - Acceptable behavior: One duplicate reminder per chore after HA restart
        """
        now_utc = dt_util.utcnow()
        reminder_window = timedelta(minutes=30)
        reminders_sent = 0

        const.LOGGER.debug(
            "Due date reminders - Starting check at %s",
            now_utc.isoformat(),
        )

        for chore_id, chore_info in self.chores_data.items():
            # Get assigned kids for this chore
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if not assigned_kids:
                continue

            # Check completion criteria to determine due date handling
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )

            # Skip if chore has reminders disabled (per-chore control v0.5.0+)
            if not chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_REMINDER, const.DEFAULT_NOTIFY_ON_REMINDER
            ):
                continue

            for kid_id in assigned_kids:
                # Build unique key for this chore+kid combination
                reminder_key = f"{chore_id}:{kid_id}"

                # Skip if already sent this reminder (transient tracking)
                if reminder_key in self._due_soon_reminders_sent:
                    continue

                # Skip if kid already claimed or completed this chore
                if self.has_pending_claim(kid_id, chore_id):
                    continue
                if self.is_approved_in_current_period(kid_id, chore_id):
                    continue

                # Get due date based on completion criteria
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # Independent chores: per-kid due date in per_kid_due_dates
                    per_kid_due_dates = chore_info.get(
                        const.DATA_CHORE_PER_KID_DUE_DATES, {}
                    )
                    due_date_str = per_kid_due_dates.get(kid_id, const.SENTINEL_EMPTY)
                else:
                    # Shared chores: single due date on chore level
                    due_date_str = chore_info.get(
                        const.DATA_CHORE_DUE_DATE, const.SENTINEL_EMPTY
                    )

                if not due_date_str:
                    continue

                # Parse due date and check if within reminder window
                due_dt = kh.parse_datetime_to_utc(due_date_str)
                if due_dt is None:
                    continue

                time_until_due = due_dt - now_utc

                # Check: due within 30 min AND not past due yet
                if timedelta(0) < time_until_due <= reminder_window:
                    # Send due-soon reminder to kid with claim button (v0.5.0+)
                    from .notification_helper import build_claim_action

                    minutes_remaining = int(time_until_due.total_seconds() / 60)
                    chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown Chore")
                    points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0)

                    await self._notify_kid_translated(
                        kid_id,
                        const.TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON,
                        const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_SOON,
                        message_data={
                            "chore_name": chore_name,
                            "minutes": minutes_remaining,
                            "points": points,
                        },
                        actions=build_claim_action(kid_id, chore_id),
                    )

                    # Mark as sent (transient - resets on HA restart)
                    self._due_soon_reminders_sent.add(reminder_key)
                    reminders_sent += 1

                    const.LOGGER.debug(
                        "Sent due-soon reminder for chore '%s' to kid '%s' (%d min remaining)",
                        chore_name,
                        kid_id,
                        minutes_remaining,
                    )

        if reminders_sent > 0:
            const.LOGGER.debug(
                "Due date reminders - Sent %d reminder(s)",
                reminders_sent,
            )

    async def _bump_past_datetime_helpers(self, now: datetime) -> None:
        """Advance all datetime helpers to tomorrow at 9 AM.

        Called during midnight processing to advance date/time pickers
        to the next day at 9 AM, regardless of current value.
        """
        if not self.hass:
            return

        # Get entity registry to find datetime helper entities by unique_id pattern
        entity_registry = er.async_get(self.hass)

        # Find all datetime helper entities using unique_id pattern
        for kid_id, kid_info in self.kids_data.items():
            kid_name = kid_info.get(const.DATA_KID_NAME, f"Kid {kid_id}")

            # Construct unique_id pattern (matches datetime.py)
            expected_unique_id = f"{self.config_entry.entry_id}_{kid_id}{const.DATETIME_KC_UID_SUFFIX_DATE_HELPER}"

            # Find entity by unique_id
            entity_entry = entity_registry.async_get_entity_id(
                "datetime", const.DOMAIN, expected_unique_id
            )

            if not entity_entry:
                continue

            # Set to tomorrow at 9 AM local time
            tomorrow = dt_util.now() + timedelta(days=1)
            tomorrow_9am = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

            await self.hass.services.async_call(
                "datetime",
                "set_datetime",
                {
                    "entity_id": entity_entry,
                    "datetime": tomorrow_9am.isoformat(),
                },
                blocking=False,
            )
            const.LOGGER.debug(
                "Advanced datetime helper for %s to %s",
                kid_name,
                tomorrow_9am.isoformat(),
            )

    async def _handle_recurring_chore_resets(self, now: datetime):
        """Handle recurring resets for daily, weekly, and monthly frequencies."""

        await self._reschedule_recurring_chores(now)

        # Daily
        if now.hour == const.DEFAULT_DAILY_RESET_TIME.get(
            const.TIME_UNIT_HOUR, const.DEFAULT_HOUR
        ):
            await self._reset_chore_counts(const.FREQUENCY_DAILY, now)

        # Weekly
        if now.weekday() == const.DEFAULT_WEEKLY_RESET_DAY:
            await self._reset_chore_counts(const.FREQUENCY_WEEKLY, now)

        # Monthly
        days_in_month = monthrange(now.year, now.month)[1]
        reset_day = min(const.DEFAULT_MONTHLY_RESET_DAY, days_in_month)
        if now.day == reset_day:
            await self._reset_chore_counts(const.FREQUENCY_MONTHLY, now)

    async def _reset_chore_counts(self, frequency: str, now: datetime):
        """Reset chore counts and statuses based on the recurring frequency."""
        # Note: Points earned tracking now handled by point_stats structure
        # Legacy points_earned_* counters removed - no longer needed

        const.LOGGER.debug(
            "DEBUG: Reset Chore Counts: %s chore counts have been reset",
            frequency.capitalize(),
        )

        # If daily reset -> reset statuses
        if frequency == const.FREQUENCY_DAILY:
            await self._reset_daily_chore_statuses([frequency])
        elif frequency == const.FREQUENCY_WEEKLY:
            await self._reset_daily_chore_statuses([frequency, const.FREQUENCY_WEEKLY])

    async def _reschedule_recurring_chores(self, now: datetime):
        """For chores with the given recurring frequency, reschedule due date if they are approved and past due.

        Handles both SHARED and INDEPENDENT completion criteria:
        - SHARED: Uses chore-level due_date and state (single due date for all kids)
        - INDEPENDENT: Uses per_kid_due_dates and per-kid state (each kid has own due date)
        """

        for chore_id, chore_info in self.chores_data.items():
            # Only consider chores with a recurring frequency
            if chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) not in (
                const.FREQUENCY_DAILY,
                const.FREQUENCY_WEEKLY,
                const.FREQUENCY_BIWEEKLY,
                const.FREQUENCY_MONTHLY,
                const.FREQUENCY_CUSTOM,
            ):
                continue

            # Branch on completion criteria
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT mode: Each kid has their own due date and state
                self._reschedule_independent_recurring_chore(chore_id, chore_info, now)
            else:
                # SHARED mode: Single due date and state for all kids
                self._reschedule_shared_recurring_chore(chore_id, chore_info, now)

        self._persist()
        self.async_set_updated_data(self._data)
        const.LOGGER.debug(
            "DEBUG: Chore Rescheduling - Daily recurring chores rescheduling complete"
        )

    def _reschedule_shared_recurring_chore(
        self, chore_id: str, chore_info: ChoreData, now: datetime
    ) -> None:
        """Reschedule a SHARED recurring chore if approved and past due.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now: Current UTC datetime
        """
        # SHARED mode uses chore-level due_date
        if not chore_info.get(const.DATA_CHORE_DUE_DATE):
            return

        due_date_utc = kh.parse_datetime_to_utc(chore_info[const.DATA_CHORE_DUE_DATE])  # type: ignore[arg-type]
        if due_date_utc is None:
            const.LOGGER.debug(
                "DEBUG: Chore Rescheduling - Error parsing due date for Chore ID '%s'.",
                chore_id,
            )
            return

        # If the due date is in the past and the chore is approved or approved_in_part
        if now > due_date_utc and chore_info.get(const.DATA_CHORE_STATE) in [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_APPROVED_IN_PART,
        ]:
            # Reschedule the chore (chore-level)
            self._reschedule_chore_next_due_date(chore_info)
            const.LOGGER.debug(
                "DEBUG: Chore Rescheduling - Rescheduled recurring SHARED Chore ID '%s'",
                chore_info.get(const.DATA_CHORE_NAME, chore_id),
            )

    def _reschedule_independent_recurring_chore(
        self, chore_id: str, chore_info: ChoreData, now: datetime
    ) -> None:
        """Reschedule an INDEPENDENT recurring chore for each kid if approved and past due.

        For INDEPENDENT chores, each kid has their own due date and state.
        Only reschedules for kids who have completed (approved) their instance.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now: Current UTC datetime
        """
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        for kid_id in assigned_kids:
            if not kid_id:
                continue

            # Get per-kid due date (source of truth for INDEPENDENT)
            kid_due_str = per_kid_due_dates.get(kid_id)
            if not kid_due_str:
                # No due date for this kid - skip
                continue

            kid_due_utc = kh.parse_datetime_to_utc(kid_due_str)
            if kid_due_utc is None:
                const.LOGGER.debug(
                    "DEBUG: Chore Rescheduling - Error parsing per-kid due date for Chore '%s', Kid '%s'.",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_id,
                )
                continue

            # Check per-kid state from kid's chore data
            kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                chore_id, {}
            )
            kid_state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )

            # If the due date is in the past and the kid's state is approved
            if now > kid_due_utc and kid_state in [
                const.CHORE_STATE_APPROVED,
                const.CHORE_STATE_APPROVED_IN_PART,
            ]:
                # Reschedule for this kid only
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                # Also reset state to PENDING (scheduled reset starts new approval period)
                self._process_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                )
                const.LOGGER.debug(
                    "DEBUG: Chore Rescheduling - Rescheduled recurring INDEPENDENT Chore '%s' for Kid '%s'",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

    async def _reset_daily_chore_statuses(self, target_freqs: list[str]):
        """Reset chore statuses and clear approved/claimed chores for chores with these freq.

        Handles both SHARED and INDEPENDENT completion criteria:
        - SHARED: Uses chore-level due_date to determine if reset needed
        - INDEPENDENT: Uses per_kid_due_dates for each kid's due date check

        For non-recurring chores (FREQUENCY_NONE), only processes if approval_reset_type
        is AT_MIDNIGHT_* (skips UPON_COMPLETION and AT_DUE_DATE_*).
        """

        now_utc = dt_util.utcnow()
        for chore_id, chore_info in self.chores_data.items():
            frequency = chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
            )

            # For non-recurring chores, only process if approval_reset_type is AT_MIDNIGHT_*
            if frequency == const.FREQUENCY_NONE:
                approval_reset_type = chore_info.get(
                    const.DATA_CHORE_APPROVAL_RESET_TYPE,
                    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                )
                # Skip if reset type is not midnight-based
                if approval_reset_type not in (
                    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                    const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
                ):
                    continue  # Skip this chore - doesn't reset at midnight
            elif frequency not in target_freqs:
                continue  # Skip recurring chores that don't match target frequency

            # Branch on completion criteria
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT mode: Check each kid's due date separately
                self._reset_independent_chore_status(chore_id, chore_info, now_utc)
            else:
                # SHARED mode: Use chore-level due_date
                self._reset_shared_chore_status(chore_id, chore_info, now_utc)

        # Queue filter removed - pending approvals computed from timestamps
        # The reset operations above clear timestamps, so computed list auto-updates
        self._pending_chore_changed = True

        self._persist()

    def _handle_pending_claim_at_reset(
        self,
        kid_id: str,
        chore_id: str,
        chore_info: ChoreData,
        kid_chore_data: KidChoreDataEntry,
    ) -> bool:
        """Handle pending claim based on approval reset pending claim action.

        Called during scheduled resets (midnight, due date) to determine
        how to handle claims that weren't approved before reset.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            kid_chore_data: The kid's chore data for clearing pending count

        Returns:
            True if reset should be SKIPPED for this kid (HOLD action)
            False if reset should CONTINUE (CLEAR or after AUTO_APPROVE)
        """
        # Check if kid has pending claim
        if not self.has_pending_claim(kid_id, chore_id):
            return False  # No pending claim, continue with reset

        pending_claim_action = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
        )

        if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_HOLD:
            # HOLD: Skip reset for this kid, leave claim pending
            const.LOGGER.debug(
                "Chore Reset - HOLD pending claim for Kid '%s' on Chore '%s'",
                kid_id,
                chore_id,
            )
            return True  # Skip reset for this kid

        if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE:
            # AUTO_APPROVE: Approve the pending claim before reset
            const.LOGGER.debug(
                "Chore Reset - AUTO_APPROVE pending claim for Kid '%s' on Chore '%s'",
                kid_id,
                chore_id,
            )
            chore_points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0.0)
            self._process_chore_state(
                kid_id,
                chore_id,
                const.CHORE_STATE_APPROVED,
                points_awarded=chore_points,
            )

        # CLEAR (default) or after AUTO_APPROVE: Clear pending_claim_count
        if kid_chore_data:
            kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

        return False  # Continue with reset

    def _reset_shared_chore_status(
        self, chore_id: str, chore_info: ChoreData, now_utc: datetime
    ) -> None:
        """Reset a SHARED chore status if due date has passed.

        Phase 5 - Approval Reset Pending Claim Action:
        - HOLD: Keep pending claim, skip reset for kids with pending claims
        - CLEAR: Clear pending claim, reset to fresh state (default/current behavior)
        - AUTO_APPROVE: Auto-approve pending claim, then reset to fresh state

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime
        """
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        if due_date_str:
            due_date_utc = kh.parse_datetime_to_utc(due_date_str)
            if due_date_utc is None:
                const.LOGGER.debug(
                    "Chore Reset - Failed to parse due date '%s' for Chore ID '%s'",
                    due_date_str,
                    chore_id,
                )
                return
            # If the due date has not yet been reached, skip resetting this chore.
            if now_utc < due_date_utc:
                return

        # Check if AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET should clear overdue status
        # This only applies with AT_MIDNIGHT_* reset types (validated in flow_helpers)
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        should_clear_overdue = (
            overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
        )

        # Determine which states should be reset
        # Default: Reset anything that's not PENDING or OVERDUE
        # With AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET: Also reset OVERDUE to PENDING
        states_to_skip = [const.CHORE_STATE_PENDING]
        if not should_clear_overdue:
            states_to_skip.append(const.CHORE_STATE_OVERDUE)

        # If no due date or the due date has passed, then reset the chore state
        if chore_info[const.DATA_CHORE_STATE] not in states_to_skip:
            previous_state = chore_info[const.DATA_CHORE_STATE]
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if kid_id:
                    # Get kid_chore_data for pending claim handling
                    kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
                    kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                        chore_id, {}
                    )

                    # Handle pending claims (HOLD, AUTO_APPROVE, or CLEAR)
                    if self._handle_pending_claim_at_reset(
                        kid_id, chore_id, chore_info, kid_chore_data
                    ):
                        continue  # HOLD action - skip reset for this kid

                    self._process_chore_state(
                        kid_id,
                        chore_id,
                        const.CHORE_STATE_PENDING,
                        reset_approval_period=True,
                    )
            const.LOGGER.debug(
                "DEBUG: Chore Reset - Resetting SHARED Chore '%s' from '%s' to '%s'",
                chore_id,
                previous_state,
                const.CHORE_STATE_PENDING,
            )

    def _reset_independent_chore_status(
        self, chore_id: str, chore_info: ChoreData, now_utc: datetime
    ) -> None:
        """Reset an INDEPENDENT chore status for each kid if their due date has passed.

        For INDEPENDENT chores, each kid has their own due date.
        Only reset for kids whose due date has passed.

        Phase 5 - Approval Reset Pending Claim Action:
        - HOLD: Keep pending claim, skip reset for kids with pending claims
        - CLEAR: Clear pending claim, reset to fresh state (default/current behavior)
        - AUTO_APPROVE: Auto-approve pending claim, then reset to fresh state

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime
        """
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Check if AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET should clear overdue status
        # This only applies with AT_MIDNIGHT_* reset types (validated in flow_helpers)
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        should_clear_overdue = (
            overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
        )

        # Determine which states should be skipped
        # Default: Skip PENDING or OVERDUE
        # With AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET: Only skip PENDING (reset OVERDUE to PENDING)
        states_to_skip = [const.CHORE_STATE_PENDING]
        if not should_clear_overdue:
            states_to_skip.append(const.CHORE_STATE_OVERDUE)

        for kid_id in assigned_kids:
            if not kid_id:
                continue

            # Get per-kid due date (source of truth for INDEPENDENT)
            kid_due_str = per_kid_due_dates.get(kid_id)
            if kid_due_str:
                kid_due_utc = kh.parse_datetime_to_utc(kid_due_str)
                if kid_due_utc is None:
                    const.LOGGER.debug(
                        "Chore Reset - Failed to parse per-kid due date '%s' for Chore '%s', Kid '%s'",
                        kid_due_str,
                        chore_id,
                        kid_id,
                    )
                    continue
                # If the due date has not yet been reached, skip resetting for this kid.
                if now_utc < kid_due_utc:
                    continue

            # Check per-kid state from kid's chore data
            kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                chore_id, {}
            )
            kid_state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )

            # Check if state should be reset based on overdue handling
            if kid_state not in states_to_skip:
                # Handle pending claims (HOLD, AUTO_APPROVE, or CLEAR)
                if self._handle_pending_claim_at_reset(
                    kid_id, chore_id, chore_info, kid_chore_data
                ):
                    continue  # HOLD action - skip reset for this kid

                self._process_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                )
                const.LOGGER.debug(
                    "Chore Reset - Resetting INDEPENDENT Chore '%s' for Kid '%s' from '%s' to '%s'",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                    kid_state,
                    const.CHORE_STATE_PENDING,
                )

    def _calculate_next_multi_daily_due(
        self,
        chore_info: ChoreData,
        current_due_utc: datetime,
    ) -> datetime | None:
        """Calculate next due datetime for DAILY_MULTI frequency.

        CFE-2026-001 Feature 2: Multiple times per day scheduling.

        Args:
            chore_info: Chore data containing daily_multi_times
            current_due_utc: Current due datetime (UTC)

        Returns:
            Next due datetime (UTC) - same day if before last slot,
            next day's first slot if past all slots today
        """
        times_raw = chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")
        # Normalize to str (could be list[str] from older data formats)
        times_str: str = (
            ",".join(times_raw) if isinstance(times_raw, list) else str(times_raw or "")
        )
        if not times_str:
            const.LOGGER.warning(
                "DAILY_MULTI frequency missing times string for chore: %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return None

        # Convert current due to local timezone for date reference
        current_local = dt_util.as_local(current_due_utc)
        current_date = current_local.date()

        # Parse times with timezone awareness (returns local-aware datetimes)
        time_slots_local = kh.parse_daily_multi_times(
            times_str,
            reference_date=current_date,
            timezone_info=const.DEFAULT_TIME_ZONE,
        )

        if not time_slots_local:
            const.LOGGER.warning(
                "DAILY_MULTI frequency has no valid times for chore: %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return None

        # Convert time slots to UTC for comparison
        time_slots_utc = [dt_util.as_utc(dt) for dt in time_slots_local]
        current_utc = dt_util.utcnow()

        # Find next available slot (must be strictly after current time)
        for slot_utc in time_slots_utc:
            if slot_utc > current_utc:
                return slot_utc

        # Past all slots today, wrap to first slot tomorrow
        tomorrow_date = current_date + timedelta(days=1)
        tomorrow_slots = kh.parse_daily_multi_times(
            times_str,
            reference_date=tomorrow_date,
            timezone_info=const.DEFAULT_TIME_ZONE,
        )
        if tomorrow_slots:
            return dt_util.as_utc(tomorrow_slots[0])

        const.LOGGER.warning(
            "DAILY_MULTI failed to calculate next slot for chore: %s",
            chore_info.get(const.DATA_CHORE_NAME),
        )
        return None

    def _calculate_next_due_date_from_info(
        self,
        current_due_utc: datetime | None,
        chore_info: ChoreData,
        completion_timestamp: datetime | None = None,
    ) -> datetime | None:
        """Calculate next due date for a chore based on frequency (pure calculation helper).

        Consolidated scheduling logic used by both chore-level and per-kid rescheduling.

        Args:
            current_due_utc: Current due date (UTC datetime, can be None)
            chore_info: Chore data dict containing frequency and configuration
            completion_timestamp: Optional completion timestamp (UTC) for
                FREQUENCY_CUSTOM_FROM_COMPLETE mode. If provided, rescheduling
                uses this as base instead of current_due_utc.

        Returns:
            datetime: Next due date (UTC) or None if calculation failed
        """
        freq = chore_info.get(
            const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        )

        # Initialize custom frequency parameters (used for FREQUENCY_CUSTOM and
        # FREQUENCY_CUSTOM_FROM_COMPLETE)
        custom_interval: int | None = None
        custom_unit: str | None = None

        # Validate custom frequency parameters for CUSTOM frequencies
        if freq in (const.FREQUENCY_CUSTOM, const.FREQUENCY_CUSTOM_FROM_COMPLETE):
            custom_interval = chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL)
            custom_unit = chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT)
            if custom_interval is None or custom_unit not in [
                const.TIME_UNIT_HOURS,  # CFE-2026-001: Support hours unit
                const.TIME_UNIT_DAYS,
                const.TIME_UNIT_WEEKS,
                const.TIME_UNIT_MONTHS,
            ]:
                const.LOGGER.warning(
                    "Consolidation Helper - Invalid custom frequency for chore: %s",
                    chore_info.get(const.DATA_CHORE_NAME),
                )
                return None

        # Skip if no frequency or no current due date
        if not freq or freq == const.FREQUENCY_NONE or current_due_utc is None:
            return None

        # Get applicable weekdays configuration
        raw_applicable = chore_info.get(
            const.DATA_CHORE_APPLICABLE_DAYS, const.DEFAULT_APPLICABLE_DAYS
        )
        applicable_days: list[int] = []
        if raw_applicable and isinstance(next(iter(raw_applicable), None), str):
            order = list(const.WEEKDAY_OPTIONS.keys())
            applicable_days = [
                order.index(day.lower())
                for day in raw_applicable
                if day.lower() in order
            ]
        elif raw_applicable:
            applicable_days = [int(d) for d in raw_applicable]

        now_local = kh.get_now_local_time()

        # Calculate next due date based on frequency
        if freq == const.FREQUENCY_CUSTOM:
            # FREQUENCY_CUSTOM: Always reschedule from current due date
            # Type narrowing: custom_unit and custom_interval are validated above
            assert custom_unit is not None
            assert custom_interval is not None
            next_due_utc = cast(
                "datetime",
                kh.adjust_datetime_by_interval(
                    base_date=current_due_utc,
                    interval_unit=custom_unit,
                    delta=custom_interval,
                    require_future=True,
                    return_type=const.HELPER_RETURN_DATETIME,
                ),
            )
        elif freq == const.FREQUENCY_CUSTOM_FROM_COMPLETE:
            # CFE-2026-001 Feature 1: Reschedule from completion timestamp
            # Use completion_timestamp if available, fallback to current_due_utc
            # This allows intervals like "every 3 days from when they actually completed"
            assert custom_unit is not None
            assert custom_interval is not None
            base_date = (
                completion_timestamp if completion_timestamp else current_due_utc
            )
            if base_date is None:
                const.LOGGER.warning(
                    "Consolidation Helper - No base date for CUSTOM_FROM_COMPLETE: %s",
                    chore_info.get(const.DATA_CHORE_NAME),
                )
                return None
            next_due_utc = cast(
                "datetime",
                kh.adjust_datetime_by_interval(
                    base_date=base_date,
                    interval_unit=custom_unit,
                    delta=custom_interval,
                    require_future=True,
                    return_type=const.HELPER_RETURN_DATETIME,
                ),
            )
        elif freq == const.FREQUENCY_DAILY_MULTI:
            # CFE-2026-001 Feature 2: Multiple times per day
            # Use dedicated helper for slot-based scheduling
            result = self._calculate_next_multi_daily_due(chore_info, current_due_utc)
            if result is None:
                return None
            next_due_utc = result
        else:
            next_due_utc = cast(
                "datetime",
                kh.get_next_scheduled_datetime(
                    base_date=current_due_utc,
                    interval_type=freq,
                    require_future=True,
                    reference_datetime=now_local,
                    return_type=const.HELPER_RETURN_DATETIME,
                ),
            )

        # Snap to applicable weekday if configured
        if applicable_days:
            next_due_local = cast(
                "datetime",
                kh.get_next_applicable_day(
                    next_due_utc,
                    applicable_days=applicable_days,
                    return_type=const.HELPER_RETURN_DATETIME,
                ),
            )
            next_due_utc = dt_util.as_utc(next_due_local)

        return next_due_utc

    def _reschedule_chore_next_due_date(self, chore_info: ChoreData) -> None:
        """Reschedule chore's next due date (chore-level). Uses consolidation helper."""
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        if not due_date_str:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Skipping (no due date for %s)",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Parse current due date
        original_due_utc = kh.parse_datetime_to_utc(due_date_str)
        if not original_due_utc:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Unable to parse due date for %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # CFE-2026-001: Extract completion timestamp for CUSTOM_FROM_COMPLETE
        # For SHARED chores, use chore-level last_completed
        completion_utc: datetime | None = None
        last_completed_str = chore_info.get(const.DATA_CHORE_LAST_COMPLETED)
        if last_completed_str:
            completion_utc = kh.parse_datetime_to_utc(last_completed_str)

        # Use consolidation helper for calculation
        next_due_utc = self._calculate_next_due_date_from_info(
            original_due_utc, chore_info, completion_timestamp=completion_utc
        )
        if not next_due_utc:
            const.LOGGER.warning(
                "Chore Due Date - Reschedule: Failed to calculate next due date for %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Update chore-level due date
        chore_info[const.DATA_CHORE_DUE_DATE] = next_due_utc.isoformat()
        chore_id = chore_info.get(const.DATA_CHORE_INTERNAL_ID)

        if not chore_id:
            const.LOGGER.error(
                "Chore Due Date - Reschedule: Missing chore_id for chore: %s",
                chore_info.get(const.DATA_CHORE_NAME, "Unknown"),
            )
            return

        # Only reset to PENDING for UPON_COMPLETION type
        # Other reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*) stay APPROVED until scheduled reset
        # This prevents the bug where approval_period_start > last_approved caused
        # is_approved_in_current_period() to return False immediately after approval
        # EXCEPTION: immediate_on_late option also resets to PENDING when triggered
        approval_reset = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )
        # Reset to PENDING for UPON_COMPLETION or immediate-on-late option
        should_reset_state = (
            approval_reset == const.APPROVAL_RESET_UPON_COMPLETION
            or overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
        )
        if should_reset_state:
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if kid_id:
                    self._process_chore_state(
                        kid_id,
                        chore_id,
                        const.CHORE_STATE_PENDING,
                        reset_approval_period=True,
                    )

        const.LOGGER.info(
            "Chore Due Date - Rescheduled (SHARED): %s, from %s to %s",
            chore_info.get(const.DATA_CHORE_NAME),
            dt_util.as_local(original_due_utc).isoformat(),
            dt_util.as_local(next_due_utc).isoformat(),
        )

    def _reschedule_chore_next_due_date_for_kid(
        self, chore_info: ChoreData, chore_id: str, kid_id: str
    ) -> None:
        """Reschedule per-kid due date (INDEPENDENT mode).

        Updates DATA_CHORE_PER_KID_DUE_DATES[kid_id]. Calls pure helper.
        Used for INDEPENDENT chores (each kid has own due date).

        Note: After migration, this method reads ONLY from DATA_CHORE_PER_KID_DUE_DATES.
        The migration populates per_kid_due_dates from the chore template (including None).
        """
        # Get kid info for logging
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))

        # Get per-kid current due date from canonical source (per_kid_due_dates ONLY)
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        current_due_str = per_kid_due_dates.get(kid_id)

        # Parse current due date
        # Per wiki Use Case 2: Chores with no due date but with recurrence should stay None
        # They reset by recurrence pattern only, never become overdue
        if not current_due_str:
            # No due date set - preserve None for recurring chores without explicit due dates
            const.LOGGER.debug(
                "Chore Due Date - No due date for chore %s, kid %s; preserving None (recurrence only)",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            # Clear per-kid override if it existed
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # Parse current due date that exists
        try:
            original_due_utc = kh.parse_datetime_to_utc(current_due_str)
        except (ValueError, TypeError, AttributeError):
            const.LOGGER.debug(
                "Chore Due Date - Reschedule (per-kid): Unable to parse due date for chore %s, kid %s; clearing due date",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            # Clear invalid due date instead of calculating one
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # CFE-2026-001: Extract per-kid completion timestamp for CUSTOM_FROM_COMPLETE
        # For INDEPENDENT chores, use per-kid last_approved from kid_chore_data
        completion_utc: datetime | None = None
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        last_approved_str = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if last_approved_str:
            completion_utc = kh.parse_datetime_to_utc(last_approved_str)

        # PKAD-2026-001: For INDEPENDENT chores, inject per-kid applicable_days
        # and daily_multi_times into a copy of chore_info before calculation.
        # This allows the helper to use per-kid values instead of chore-level.
        chore_info_for_calc = chore_info.copy()

        per_kid_applicable_days = chore_info.get(
            const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {}
        )
        if kid_id in per_kid_applicable_days:
            chore_info_for_calc[const.DATA_CHORE_APPLICABLE_DAYS] = (
                per_kid_applicable_days[kid_id]
            )

        per_kid_times = chore_info.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
        if kid_id in per_kid_times:
            chore_info_for_calc[const.DATA_CHORE_DAILY_MULTI_TIMES] = per_kid_times[
                kid_id
            ]

        # Use consolidation helper with per-kid overrides
        next_due_utc = self._calculate_next_due_date_from_info(
            original_due_utc, chore_info_for_calc, completion_timestamp=completion_utc
        )
        if not next_due_utc:
            const.LOGGER.warning(
                "Chore Due Date - Reschedule (per-kid): Failed to calculate next due date for %s, kid %s",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            return

        # Update per-kid storage (single source of truth)
        per_kid_due_dates[kid_id] = next_due_utc.isoformat()
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

        # Only reset to PENDING for UPON_COMPLETION type
        # Other reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*) stay APPROVED until scheduled reset
        # This prevents the bug where approval_period_start > last_approved caused
        # is_approved_in_current_period() to return False immediately after approval
        # EXCEPTION: immediate_on_late option also resets to PENDING when triggered
        approval_reset = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )
        # Reset to PENDING for UPON_COMPLETION or immediate-on-late option
        should_reset_state = (
            approval_reset == const.APPROVAL_RESET_UPON_COMPLETION
            or overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
        )
        if should_reset_state:
            self._process_chore_state(
                kid_id, chore_id, const.CHORE_STATE_PENDING, reset_approval_period=True
            )

        const.LOGGER.info(
            "Chore Due Date - Rescheduled (INDEPENDENT): chore %s, kid %s, from %s to %s",
            chore_info.get(const.DATA_CHORE_NAME),
            kid_info.get(const.DATA_KID_NAME),
            dt_util.as_local(original_due_utc).isoformat()
            if original_due_utc
            else "None",
            dt_util.as_local(next_due_utc).isoformat() if next_due_utc else "None",
        )

    def _is_approval_after_reset_boundary(
        self, chore_info: ChoreData, kid_id: str
    ) -> bool:
        """Check if approval is happening after the reset boundary has passed.

        For AT_MIDNIGHT types: Due date must be before last midnight
        For AT_DUE_DATE types: Current time must be past the due date

        Returns True if "late", False otherwise.
        """
        approval_reset_type = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
        )

        now_utc = dt_util.utcnow()

        # AT_MIDNIGHT types: Check if due date was before last midnight
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        ):
            # Get due date (per-kid for INDEPENDENT, chore-level for SHARED)
            completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)

            if not due_date_str:
                return False

            due_date = kh.parse_datetime_to_utc(due_date_str)
            if not due_date:
                return False

            # Calculate last midnight in local time, convert to UTC
            local_now = dt_util.as_local(now_utc)
            last_midnight_local = local_now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            last_midnight_utc = dt_util.as_utc(last_midnight_local)

            return due_date < last_midnight_utc

        # AT_DUE_DATE types: Check if past the due date
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
        ):
            completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)

            if not due_date_str:
                return False

            due_date = kh.parse_datetime_to_utc(due_date_str)
            if not due_date:
                return False

            return now_utc > due_date

        return False

    # Set Chore Due Date
    def set_chore_due_date(
        self,
        chore_id: str,
        due_date: datetime | None,
        kid_id: str | None = None,
    ) -> None:
        """Set the due date of a chore.

        Args:
            chore_id: Chore to update
            due_date: New due date (or None to clear)
            kid_id: If provided for INDEPENDENT chores, updates only this kid's due date.
                   For SHARED chores, this parameter is ignored.

        For SHARED chores: Updates the single chore-level due date.
        For INDEPENDENT chores:
            - Does NOT set chore-level due_date (respects post-migration structure)
            - If kid_id provided: Updates only that kid's due date
            - If kid_id None: Updates all per-kid due dates
        """
        # Retrieve the chore data; raise error if not found.
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if chore_info is None:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        # Convert the due_date to an ISO-formatted string if provided; otherwise use None.
        # IMPORTANT: Ensure UTC timezone to maintain consistency in storage
        # Bug fix: Previously stored local timezone which caused display issues
        new_due_date_iso = dt_util.as_utc(due_date).isoformat() if due_date else None

        # Get completion criteria to determine update strategy
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # For SHARED and SHARED_FIRST chores: Update chore-level due date (single source of truth)
        # For INDEPENDENT chores: Do NOT set chore-level due date (respects post-migration structure)
        if criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ):
            try:
                chore_info[const.DATA_CHORE_DUE_DATE] = new_due_date_iso
            except KeyError as err:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MISSING_FIELD,
                    translation_placeholders={
                        "field": "due_date",
                        "entity": f"chore '{chore_id}'",
                    },
                ) from err

        # For INDEPENDENT chores: Update per-kid due dates (single source of truth)
        elif criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            if kid_id:
                # Update only the specified kid's due date
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                # Update per-kid due dates dict
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                per_kid_due_dates[kid_id] = new_due_date_iso
                if kid_id in self.kids_data:
                    kid_info = self.kids_data[kid_id]
                    const.LOGGER.debug(
                        "Set due date for INDEPENDENT chore %s, kid %s only: %s",
                        chore_info.get(const.DATA_CHORE_NAME),
                        kid_info.get(const.DATA_KID_NAME),
                        new_due_date_iso,
                    )
            else:
                # Update all assigned kids' due dates
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    per_kid_due_dates[assigned_kid_id] = new_due_date_iso
                const.LOGGER.debug(
                    "Set due date for INDEPENDENT chore %s, all kids: %s",
                    chore_info.get(const.DATA_CHORE_NAME),
                    new_due_date_iso,
                )

        # If the due date is cleared (None), then remove any recurring frequency
        # and custom interval settings unless the frequency is none, daily, or weekly.
        if new_due_date_iso is None:
            # const.FREQUENCY_DAILY, const.FREQUENCY_WEEKLY, and const.FREQUENCY_NONE are all OK without a due_date
            current_frequency = chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY)
            if chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) not in (
                const.FREQUENCY_NONE,
                const.FREQUENCY_DAILY,
                const.FREQUENCY_WEEKLY,
            ):
                const.LOGGER.debug(
                    "DEBUG: Chore Due Date - Removing frequency for Chore ID '%s' - Current frequency '%s' does not work with a due date of None",
                    chore_id,
                    current_frequency,
                )
                chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_NONE
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL, None)
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, None)

        # Reset the chore state to Pending and clear pending_count for all kids
        for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            if kid_id:
                self._process_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                )
                # Clear pending_count when due date changes (v0.4.0+ counter-based tracking)
                kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
                kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                    chore_id, {}
                )
                if kid_chore_data:
                    kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

        const.LOGGER.info(
            "INFO: Chore Due Date - Due date set for Chore ID '%s'",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # Skip Chore Due Date
    def skip_chore_due_date(self, chore_id: str, kid_id: str | None = None) -> None:
        """Skip the current due date of a recurring chore and reschedule it.

        When a due date is skipped, the chore state is reset to PENDING for all affected kids,
        since the new due date creates a new completion period.

        Args:
            chore_id: Chore to skip
            kid_id: If provided for INDEPENDENT chores, skips only this kid's due date.
                   For SHARED chores, this parameter is ignored.

        For SHARED chores: Reschedules the single chore-level due date and resets state to PENDING for all kids.
        For INDEPENDENT chores:
            - If kid_id provided: Reschedules only that kid's due date and resets that kid's state to PENDING
            - If kid_id None: Reschedules template and all per-kid due dates, resets all kids' states to PENDING
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        if (
            chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE)
            == const.FREQUENCY_NONE
        ):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INVALID_FREQUENCY,
                translation_placeholders={
                    "frequency": "none",
                },
            )

        # Get completion criteria to determine due date validation strategy
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # Check if chore has due dates based on completion criteria
        if criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ):
            # SHARED and SHARED_FIRST chores use chore-level due date
            if not chore_info.get(const.DATA_CHORE_DUE_DATE):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MISSING_FIELD,
                    translation_placeholders={
                        "field": "due_date",
                        "entity": f"chore '{chore_info.get(const.DATA_CHORE_NAME, chore_id)}'",
                    },
                )
        else:
            # INDEPENDENT chores use per-kid due dates
            # Check if at least one assigned kid has a due date
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})

            has_any_due_date = False
            for assigned_kid_id in assigned_kids:
                if per_kid_due_dates.get(assigned_kid_id):
                    has_any_due_date = True
                    break

            if not has_any_due_date:
                # No due dates to skip - return early (no-op)
                const.LOGGER.debug(
                    "Skip request ignored: No kids have due dates for chore %s",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                )
                return

        # Apply skip logic based on completion criteria
        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT chore: skip per-kid due dates
            if kid_id:
                # Skip only the specified kid's due date
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                # Check if this specific kid has a due date to skip
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                kid_due_date = per_kid_due_dates.get(kid_id)
                if not kid_due_date:
                    # No due date for this kid - nothing to skip
                    const.LOGGER.debug(
                        "Skip request ignored: Kid %s has no due date for chore %s",
                        self.kids_data.get(kid_id, {}).get(const.DATA_KID_NAME, kid_id),  # type: ignore[assignment,call-overload,operator]
                        chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    )
                    return
                # Reschedule and reset chore state for this kid
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                # Reset chore state to PENDING for this kid
                self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
                const.LOGGER.info(
                    "Skipped due date for INDEPENDENT chore %s, kid %s - reset to PENDING",
                    chore_info.get(const.DATA_CHORE_NAME),
                    self.kids_data[kid_id].get(const.DATA_KID_NAME),
                )
            else:
                # Skip template and all assigned kids' due dates
                self._reschedule_chore_next_due_date(chore_info)
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    if assigned_kid_id and assigned_kid_id in self.kids_data:
                        self._reschedule_chore_next_due_date_for_kid(
                            chore_info, chore_id, assigned_kid_id
                        )
                        # Reset chore state to PENDING for each kid
                        self._process_chore_state(
                            assigned_kid_id, chore_id, const.CHORE_STATE_PENDING
                        )
                const.LOGGER.info(
                    "Skipped due date for INDEPENDENT chore %s, all kids - reset to PENDING",
                    chore_info.get(const.DATA_CHORE_NAME),
                )
        else:
            # SHARED chore: skip chore-level due date and reset state for all kids
            self._reschedule_chore_next_due_date(chore_info)
            # Reset chore state to PENDING for all assigned kids
            for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if assigned_kid_id and assigned_kid_id in self.kids_data:
                    self._process_chore_state(
                        assigned_kid_id, chore_id, const.CHORE_STATE_PENDING
                    )
            const.LOGGER.info(
                "Skipped due date for SHARED chore %s - reset to PENDING for all kids",
                chore_info.get(const.DATA_CHORE_NAME),
            )

        self._persist()
        self.async_set_updated_data(self._data)

    # Reset All Chores
    def reset_all_chores(self) -> None:
        """Reset all chores to pending state, clearing claims/approvals.

        This is a manual reset that:
        - Sets all chore states to PENDING
        - Resets approval_period_start for SHARED chores to now
        - Resets all kid chore tracking (pending_claim_count, state, approval_period_start)
        - Clears overdue notification tracking

        Note: last_claimed and last_approved are intentionally preserved for historical tracking.
        """
        now_utc_iso = datetime.now(dt_util.UTC).isoformat()

        # Loop over all chores, reset them to pending
        for chore_info in self.chores_data.values():
            chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING
            # Reset SHARED chore approval_period_start to now
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_utc_iso

        # Clear all chore tracking timestamps for each kid (v0.5.0+ timestamp-based)
        for kid_info in self.kids_data.values():
            # Clear timestamp-based tracking data
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            for chore_tracking in kid_chore_data.values():
                # NOTE: last_claimed is intentionally NEVER removed - historical tracking
                # NOTE: last_approved is intentionally NEVER removed - historical tracking
                # Reset pending_claim_count to 0 (v0.5.0+ counter-based tracking)
                chore_tracking[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0
                # Set approval_period_start to NOW to start fresh approval period
                # This ensures old last_approved timestamps are invalidated
                chore_tracking[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    now_utc_iso
                )
                # Reset state to PENDING (single source of truth for state)
                chore_tracking[const.DATA_KID_CHORE_DATA_STATE] = (
                    const.CHORE_STATE_PENDING
                )
            # Clear overdue notification tracking
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = {}

        self._persist()
        self.async_set_updated_data(self._data)
        const.LOGGER.info(
            "Manually reset all chores to pending, reset approval periods to now"
        )

    # Reset Overdue Chores
    def reset_overdue_chores(
        self, chore_id: str | None = None, kid_id: str | None = None
    ) -> None:
        """Reset overdue chore(s) to Pending state and reschedule.

        Branching logic:
        - INDEPENDENT chores: Reschedule per-kid due dates individually
        - SHARED chores: Reschedule chore-level due date (affects all kids)
        """

        if chore_id:
            # Specific chore reset (with or without kid_id)
            chore_info: ChoreData | None = self.chores_data.get(chore_id)
            if not chore_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_CHORE,
                        "name": chore_id,
                    },
                )

            # Get completion criteria to determine reset strategy
            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and kid_id:
                # INDEPENDENT + kid specified: Reset state to PENDING and reschedule per-kid due date
                const.LOGGER.info(
                    "Reset Overdue Chores: Rescheduling per-kid (INDEPENDENT) chore: %s, kid: %s",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_id,
                )
                self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
            else:
                # INDEPENDENT without kid_id OR SHARED: Reset all kids via chore-level
                const.LOGGER.info(
                    "Reset Overdue Chores: Rescheduling chore (SHARED or all kids): %s",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                )
                self._reschedule_chore_next_due_date(chore_info)

        elif kid_id:
            # Kid-only reset: reset all overdue chores for the specified kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            for chore_id, chore_info in self.chores_data.items():
                if kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if self.is_overdue(kid_id, chore_id):
                        # Get completion criteria to determine reset strategy
                        criteria = chore_info.get(
                            const.DATA_CHORE_COMPLETION_CRITERIA,
                            const.COMPLETION_CRITERIA_SHARED,
                        )

                        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                            # INDEPENDENT: Reset state to PENDING and reschedule per-kid due date
                            const.LOGGER.info(
                                "Reset Overdue Chores: Rescheduling per-kid (INDEPENDENT) chore: %s, kid: %s",
                                chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                kid_id,
                            )
                            self._process_chore_state(
                                kid_id, chore_id, const.CHORE_STATE_PENDING
                            )
                            self._reschedule_chore_next_due_date_for_kid(
                                chore_info, chore_id, kid_id
                            )
                        else:
                            # SHARED: Reset state for this kid only (don't affect global due date)
                            const.LOGGER.info(
                                "Reset Overdue Chores: Resetting SHARED chore state for kid only: %s, kid: %s",
                                chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                kid_id,
                            )
                            self._process_chore_state(
                                kid_id, chore_id, const.CHORE_STATE_PENDING
                            )
        else:
            # Global reset: Reset all overdue chores for all kids
            for kid_id_iter, _kid_info in self.kids_data.items():
                for chore_id, chore_info in self.chores_data.items():
                    if kid_id_iter in chore_info.get(
                        const.DATA_CHORE_ASSIGNED_KIDS, []
                    ):
                        if self.is_overdue(kid_id_iter, chore_id):
                            # Get completion criteria to determine reset strategy
                            criteria = chore_info.get(
                                const.DATA_CHORE_COMPLETION_CRITERIA,
                                const.COMPLETION_CRITERIA_SHARED,
                            )

                            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                                # INDEPENDENT: Reset state to PENDING and reschedule per-kid due date
                                const.LOGGER.info(
                                    "Reset Overdue Chores: Rescheduling per-kid (INDEPENDENT) chore: %s, kid: %s",
                                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                    kid_id_iter,
                                )
                                self._process_chore_state(
                                    kid_id_iter, chore_id, const.CHORE_STATE_PENDING
                                )
                                self._reschedule_chore_next_due_date_for_kid(
                                    chore_info, chore_id, kid_id_iter
                                )
                            else:
                                # SHARED: Reset chore-level (affects all kids)
                                const.LOGGER.info(
                                    "Reset Overdue Chores: Rescheduling chore (SHARED): %s for kid: %s",
                                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                    kid_id_iter,
                                )
                                self._reschedule_chore_next_due_date(chore_info)

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------------------
    # Penalties: Reset
    # -------------------------------------------------------------------------------------

    def reset_penalties(
        self, kid_id: str | None = None, penalty_id: str | None = None
    ) -> None:
        """Reset penalties based on provided kid_id and penalty_id."""

        if penalty_id and kid_id:
            # Reset a specific penalty for a specific kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if penalty_id not in kid_info.get(const.DATA_KID_PENALTY_APPLIES, {}):
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Penalty ID '%s' does not apply to Kid ID '%s'.",
                    penalty_id,
                    kid_id,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": f"penalty '{penalty_id}'",
                        "kid": kid_id,
                    },
                )

            kid_info[const.DATA_KID_PENALTY_APPLIES].pop(penalty_id, None)

        elif penalty_id:
            # Reset a specific penalty for all kids
            found = False
            for kid_info in self.kids_data.values():
                if penalty_id in kid_info.get(const.DATA_KID_PENALTY_APPLIES, {}):
                    found = True
                    kid_info[const.DATA_KID_PENALTY_APPLIES].pop(penalty_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Penalties - Penalty ID '%s' not found in any kid's data.",
                    penalty_id,
                )

        elif kid_id:
            # Reset all penalties for a specific kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info[const.DATA_KID_PENALTY_APPLIES].clear()

        else:
            # Reset all penalties for all kids
            const.LOGGER.info(
                "INFO: Reset Penalties - Resetting all penalties for all kids"
            )
            for kid_info in self.kids_data.values():
                kid_info[const.DATA_KID_PENALTY_APPLIES].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Penalties - Penalties reset completed - Kid ID '%s',  Penalty ID '%s'",
            kid_id,
            penalty_id,
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------------------
    # Bonuses: Reset
    # -------------------------------------------------------------------------------------

    def reset_bonuses(
        self, kid_id: str | None = None, bonus_id: str | None = None
    ) -> None:
        """Reset bonuses based on provided kid_id and bonus_id."""

        if bonus_id and kid_id:
            # Reset a specific bonus for a specific kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if bonus_id not in kid_info.get(const.DATA_KID_BONUS_APPLIES, {}):
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Bonus '%s' does not apply to Kid ID '%s'.",
                    bonus_id,
                    kid_id,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": f"bonus '{bonus_id}'",
                        "kid": kid_id,
                    },
                )

            kid_info[const.DATA_KID_BONUS_APPLIES].pop(bonus_id, None)

        elif bonus_id:
            # Reset a specific bonus for all kids
            found = False
            for kid_info in self.kids_data.values():
                if bonus_id in kid_info.get(const.DATA_KID_BONUS_APPLIES, {}):
                    found = True
                    kid_info[const.DATA_KID_BONUS_APPLIES].pop(bonus_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Bonuses - Bonus '%s' not found in any kid's data.",
                    bonus_id,
                )

        elif kid_id:
            # Reset all bonuses for a specific kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info[const.DATA_KID_BONUS_APPLIES].clear()

        else:
            # Reset all bonuses for all kids
            const.LOGGER.info(
                "INFO: Reset Bonuses - Resetting all bonuses for all kids."
            )
            for kid_info in self.kids_data.values():
                kid_info[const.DATA_KID_BONUS_APPLIES].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Bonuses - Bonuses reset completed - Kid ID '%s', Bonus ID '%s'",
            kid_id,
            bonus_id,
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------------------
    # Rewards: Reset
    # This function resets reward-related data for a specified kid and/or reward by
    # clearing the reward_data entries which track claims, approvals, and period stats.
    # -------------------------------------------------------------------------------------

    def reset_rewards(
        self, kid_id: str | None = None, reward_id: str | None = None
    ) -> None:
        """Reset rewards based on provided kid_id and reward_id."""

        if reward_id and kid_id:
            # Reset a specific reward for a specific kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Rewards - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            # Clear reward_data entry for this reward
            reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})
            reward_data.pop(reward_id, None)

        elif reward_id:
            # Reset a specific reward for all kids
            found = False
            for kid_info in self.kids_data.values():
                reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})
                if reward_id in reward_data:
                    found = True
                    reward_data.pop(reward_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Rewards - Reward '%s' not found in any kid's data.",
                    reward_id,
                )

        elif kid_id:
            # Reset all rewards for a specific kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Rewards - Kid ID '%s' not found.", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            # Clear all reward_data for this kid
            if const.DATA_KID_REWARD_DATA in kid_info:
                kid_info[const.DATA_KID_REWARD_DATA].clear()

        else:
            # Reset all rewards for all kids
            const.LOGGER.info(
                "INFO: Reset Rewards - Resetting all rewards for all kids."
            )
            for kid_info in self.kids_data.values():
                # Clear all reward_data for this kid
                if const.DATA_KID_REWARD_DATA in kid_info:
                    kid_info[const.DATA_KID_REWARD_DATA].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Rewards - Rewards reset completed - Kid ID '%s', Reward ID '%s'",
            kid_id,
            reward_id,
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------------------

    # --- Translation Helpers (shared by kid and parent notification methods) ---

    def _convert_notification_key(self, const_key: str) -> str:
        """Convert const translation key to JSON key.

        Removes notification prefix from const keys:
        - "notification_title_chore_assigned" -> "chore_assigned"
        - "notification_message_reward_claimed" -> "reward_claimed"

        Used by both kid and parent notification methods.
        """
        return const_key.replace("notification_title_", "").replace(
            "notification_message_", ""
        )

    def _format_notification_text(
        self,
        template: str,
        data: dict[str, Any] | None,
        json_key: str,
        text_type: str = "message",
    ) -> str:
        """Format notification text with placeholders, handling errors gracefully.

        Args:
            template: Template string with {placeholder} syntax
            data: Dictionary of placeholder values
            json_key: Notification key for logging
            text_type: "title" or "message" for error logging

        Returns:
            Formatted string, or original template if formatting fails

        Used by both kid and parent notification methods.
        """
        try:
            return template.format(**(data or {}))
        except KeyError as err:
            const.LOGGER.warning(
                "Missing placeholder %s in %s for notification '%s'",
                err,
                text_type,
                json_key,
            )
            return template

    def _translate_action_buttons(
        self, actions: list[dict[str, str]] | None, translations: dict
    ) -> list[dict[str, str]] | None:
        """Translate action button titles using loaded translations.

        Converts action keys like "notif_action_approve" to translation keys
        like "approve", then looks up translated text from the "actions" section
        of notification translations.

        Args:
            actions: List of action dicts with 'action' and 'title' keys
            translations: Loaded notification translations dict

        Returns:
            New list with translated action titles, or None if no actions

        Used by both kid and parent notification methods.
        """
        if not actions:
            return None

        action_translations = translations.get("actions", {})
        translated_actions = []

        for action in actions:
            translated_action = action.copy()
            action_title_key = action.get(const.NOTIFY_TITLE, "")
            # Convert "notif_action_approve" -> "approve"
            action_key = action_title_key.replace("notif_action_", "")
            # Look up translation, fallback to original key
            translated_title = action_translations.get(action_key, action_title_key)
            translated_action[const.NOTIFY_TITLE] = translated_title
            translated_actions.append(translated_action)

        const.LOGGER.debug(
            "Translated action buttons: %s -> %s",
            [a.get(const.NOTIFY_TITLE) for a in actions],
            [a.get(const.NOTIFY_TITLE) for a in translated_actions],
        )

        return translated_actions

    # --- Core Notification Methods ---

    async def send_kc_notification(
        self,
        user_id: str | None,
        title: str,
        message: str,
        notification_id: str,
    ) -> None:
        """Send a persistent notification to a user if possible.

        Fallback to a general persistent notification if the user is not found or not set.
        """

        hass = self.hass
        if not user_id:
            # If no user_id is provided, use a general notification
            const.LOGGER.debug(
                "DEBUG: Notification - No User ID provided. Sending a general persistent notification"
            )
            await hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )
            return

        try:
            user_obj = await hass.auth.async_get_user(user_id)
            if not user_obj:
                const.LOGGER.warning(
                    "WARNING: Notification - User ID '%s' not found. Sending fallback persistent notification",
                    user_id,
                )
                await hass.services.async_call(
                    const.NOTIFY_PERSISTENT_NOTIFICATION,
                    const.NOTIFY_CREATE,
                    {
                        const.NOTIFY_TITLE: title,
                        const.NOTIFY_MESSAGE: message,
                        const.NOTIFY_NOTIFICATION_ID: notification_id,
                    },
                    blocking=True,
                )
                return

            await hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )
        except Exception as err:
            const.LOGGER.warning(
                "WARNING: Notification - Failed to send notification to '%s': %s. Fallback to persistent notification",
                user_id,
                err,
            )
            await hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )

    async def _notify_kid(
        self,
        kid_id: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict | None = None,
    ) -> None:
        """Notify a kid using their configured notification settings."""

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return
        if not kid_info.get(const.DATA_KID_ENABLE_NOTIFICATIONS, True):
            const.LOGGER.debug(
                "DEBUG: Notification - Notifications disabled for Kid ID '%s'", kid_id
            )
            return
        mobile_enabled = kid_info.get(const.DATA_KID_ENABLE_NOTIFICATIONS, True)
        persistent_enabled = kid_info.get(
            const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS, True
        )
        mobile_notify_service = kid_info.get(
            const.DATA_KID_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
        )
        if mobile_enabled and mobile_notify_service:
            await async_send_notification(
                self.hass,
                mobile_notify_service,
                title,
                message,
                actions=actions,
                extra_data=extra_data,
            )
        elif persistent_enabled:
            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: f"kid_{kid_id}",
                },
                blocking=True,
            )
        else:
            const.LOGGER.debug(
                "DEBUG: Notification - No notification method configured for Kid ID '%s'",
                kid_id,
            )

    async def _notify_kid_translated(
        self,
        kid_id: str,
        title_key: str,
        message_key: str,
        message_data: dict[str, Any] | None = None,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict | None = None,
    ) -> None:
        """Notify a kid using translated title and message.

        Args:
            kid_id: The internal ID of the kid
            title_key: Translation key for the notification title
            message_key: Translation key for the notification message
            message_data: Dictionary of placeholder values for message formatting
            actions: Optional list of notification actions
            extra_data: Optional extra data for mobile notifications
        """
        # Get kid's preferred language (or fall back to system language)
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        language = kid_info.get(
            const.DATA_KID_DASHBOARD_LANGUAGE,
            self.hass.config.language,
        )
        const.LOGGER.debug(
            "Notification: kid_id=%s, language=%s, title_key=%s",
            kid_id,
            language,
            title_key,
        )

        # Load notification translations from custom translations directory
        translations = await kh.load_notification_translation(self.hass, language)
        const.LOGGER.debug(
            "Notification translations loaded: %d keys, language=%s",
            len(translations),
            language,
        )

        # Convert const key to JSON key and look up translations
        json_key = self._convert_notification_key(title_key)
        notification = translations.get(json_key, {})

        # Format title and message with placeholders
        title = self._format_notification_text(
            notification.get("title", title_key), message_data, json_key, "title"
        )
        message = self._format_notification_text(
            notification.get("message", message_key), message_data, json_key, "message"
        )

        # Translate action button titles
        translated_actions = self._translate_action_buttons(actions, translations)

        # Call original notification method
        await self._notify_kid(kid_id, title, message, translated_actions, extra_data)

    async def _notify_parents(
        self,
        kid_id: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict | None = None,
    ) -> None:
        """Notify all parents associated with a kid using their settings."""
        # PERF: Measure parent notification latency (sequential vs concurrent)
        perf_start = time.perf_counter()
        parent_count = 0

        for parent_id, parent_info in self.parents_data.items():
            if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
                continue
            if not parent_info.get(const.DATA_PARENT_ENABLE_NOTIFICATIONS, True):
                const.LOGGER.debug(
                    "DEBUG: Notification - Notifications disabled for Parent ID '%s'",
                    parent_id,
                )
                continue
            mobile_enabled = parent_info.get(
                const.DATA_PARENT_ENABLE_NOTIFICATIONS, True
            )
            persistent_enabled = parent_info.get(
                const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, True
            )
            mobile_notify_service = parent_info.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            )
            if mobile_enabled and mobile_notify_service:
                parent_count += 1
                await async_send_notification(
                    self.hass,
                    mobile_notify_service,
                    title,
                    message,
                    actions=actions,
                    extra_data=extra_data,
                )
            elif persistent_enabled:
                parent_count += 1
                await self.hass.services.async_call(
                    const.NOTIFY_PERSISTENT_NOTIFICATION,
                    const.NOTIFY_CREATE,
                    {
                        const.NOTIFY_TITLE: title,
                        const.NOTIFY_MESSAGE: message,
                        const.NOTIFY_NOTIFICATION_ID: f"parent_{parent_id}",
                    },
                    blocking=True,
                )
            else:
                const.LOGGER.debug(
                    "DEBUG: Notification - No notification method configured for Parent ID '%s'",
                    parent_id,
                )

        # PERF: Log parent notification latency
        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: _notify_parents() sent %d notifications in %.3fs (sequential, avg %.3fs/parent)",
            parent_count,
            perf_duration,
            perf_duration / parent_count if parent_count > 0 else 0,
        )

    async def _notify_parents_translated(
        self,
        kid_id: str,
        title_key: str,
        message_key: str,
        message_data: dict[str, Any] | None = None,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict | None = None,
        tag_type: str | None = None,
        tag_identifiers: tuple[str, ...] | None = None,
    ) -> None:
        """Notify parents using translated title and message.

        Each parent receives notifications in their own preferred language.
        Supports tag-based notification replacement (v0.5.0+).
        Uses concurrent notification sending for ~3x performance improvement (v0.5.0+).

        Args:
            kid_id: The internal ID of the kid (to find associated parents)
            title_key: Translation key for the notification title
            message_key: Translation key for the notification message
            message_data: Dictionary of placeholder values for message formatting
            actions: Optional list of notification actions
            extra_data: Optional extra data for mobile notifications
            tag_type: Optional tag type for smart notification replacement.
                      Use const.NOTIFY_TAG_TYPE_* constants.
            tag_identifiers: Optional tuple of identifiers for tag uniqueness.
                            When provided, generates tag "kidschores-{tag_type}-{id1}-{id2}".
                            If None, defaults to (kid_id,) for backwards compatibility.
        """
        import asyncio

        from .notification_helper import build_notification_tag

        # PERF: Measure parent notification latency
        perf_start = time.perf_counter()

        # Build notification tag if tag_type provided (v0.5.0+ smart replacement)
        notification_tag = None
        if tag_type:
            # Use provided identifiers or default to kid_id for backwards compatibility
            identifiers = tag_identifiers if tag_identifiers else (kid_id,)
            notification_tag = build_notification_tag(tag_type, *identifiers)
            const.LOGGER.debug(
                "Using notification tag '%s' for identifiers %s",
                notification_tag,
                identifiers,
            )

        # Phase 1: Prepare all parent notifications (translations, formatting)
        # This is done sequentially since translations may need I/O
        notification_tasks: list[tuple[str, Any]] = []

        for parent_id, parent_info in self.parents_data.items():
            if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
                continue
            if not parent_info.get(const.DATA_PARENT_ENABLE_NOTIFICATIONS, True):
                const.LOGGER.debug(
                    "DEBUG: Notification - Notifications disabled for Parent ID '%s'",
                    parent_id,
                )
                continue

            # Use parent's language preference (fallback to kid's language, then system language)
            parent_language = parent_info.get(
                const.DATA_PARENT_DASHBOARD_LANGUAGE,
                self.kids_data.get(kid_id, {}).get(  # type: ignore[assignment,call-overload,operator]
                    const.DATA_KID_DASHBOARD_LANGUAGE,
                    self.hass.config.language,
                ),
            )

            const.LOGGER.debug(
                "Parent notification: kid_id=%s, parent_id=%s, language=%s, title_key=%s",
                kid_id,
                parent_id,
                parent_language,
                title_key,
            )

            # Load notification translations for this parent's language (uses cache)
            translations = await kh.load_notification_translation(
                self.hass, parent_language
            )

            # Convert const key to JSON key and look up translations
            json_key = self._convert_notification_key(title_key)
            notification = translations.get(json_key, {})

            # Format both title and message with placeholders
            title = self._format_notification_text(
                notification.get("title", title_key), message_data, json_key, "title"
            )
            message = self._format_notification_text(
                notification.get("message", message_key),
                message_data,
                json_key,
                "message",
            )

            # Translate action button titles
            translated_actions = self._translate_action_buttons(actions, translations)

            # Build final extra_data with tag if provided (v0.5.0+ smart replacement)
            final_extra_data = dict(extra_data) if extra_data else {}
            if notification_tag:
                final_extra_data[const.NOTIFY_TAG] = notification_tag

            # Determine notification method and prepare coroutine
            mobile_enabled = parent_info.get(
                const.DATA_PARENT_ENABLE_NOTIFICATIONS, True
            )
            persistent_enabled = parent_info.get(
                const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, True
            )
            mobile_notify_service = parent_info.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            )

            if mobile_enabled and mobile_notify_service:
                # Prepare mobile notification coroutine
                notification_tasks.append(
                    (
                        parent_id,
                        async_send_notification(
                            self.hass,
                            mobile_notify_service,
                            title,
                            message,
                            actions=translated_actions,
                            extra_data=final_extra_data if final_extra_data else None,
                        ),
                    )
                )
            elif persistent_enabled:
                # Prepare persistent notification coroutine
                notification_tasks.append(
                    (
                        parent_id,
                        self.hass.services.async_call(
                            const.NOTIFY_PERSISTENT_NOTIFICATION,
                            const.NOTIFY_CREATE,
                            {
                                const.NOTIFY_TITLE: title,
                                const.NOTIFY_MESSAGE: message,
                                const.NOTIFY_NOTIFICATION_ID: f"parent_{parent_id}",
                            },
                            blocking=True,
                        ),
                    )
                )
            else:
                const.LOGGER.debug(
                    "DEBUG: Notification - No notification method configured for Parent ID '%s'",
                    parent_id,
                )

        # Phase 2: Send all notifications concurrently (v0.5.0+ performance improvement)
        parent_count = len(notification_tasks)
        if notification_tasks:
            # Use asyncio.gather with return_exceptions=True to prevent one failure
            # from blocking others
            results = await asyncio.gather(
                *[coro for _, coro in notification_tasks],
                return_exceptions=True,
            )

            # Log any errors (don't fail the whole operation)
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    parent_id = notification_tasks[idx][0]
                    const.LOGGER.warning(
                        "Failed to send notification to parent '%s': %s",
                        parent_id,
                        result,
                    )

        # PERF: Log parent notification latency (now concurrent)
        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: _notify_parents_translated() sent %d notifications in %.3fs "
            "(concurrent, avg %.3fs/parent)",
            parent_count,
            perf_duration,
            perf_duration / parent_count if parent_count > 0 else 0,
        )

    async def clear_notification_for_parents(
        self,
        kid_id: str,
        tag_type: str,
        entity_id: str,
    ) -> None:
        """Clear a notification for all parents of a kid.

        Sends "clear_notification" message to each parent's notification service
        with the appropriate tag. This allows dashboard approvals to dismiss
        stale mobile notifications.

        Args:
            kid_id: The internal ID of the kid (to find associated parents)
            tag_type: Tag type constant (e.g., NOTIFY_TAG_TYPE_STATUS)
            entity_id: The chore/reward ID to include in the tag
        """
        import asyncio

        from .notification_helper import build_notification_tag

        # Build the tag for this entity
        notification_tag = build_notification_tag(tag_type, entity_id, kid_id)

        const.LOGGER.debug(
            "Clearing notification with tag '%s' for kid '%s'",
            notification_tag,
            kid_id,
        )

        # Build clear tasks for all parents associated with this kid
        clear_tasks: list[tuple[str, Any]] = []

        for parent_id, parent_info in self.parents_data.items():
            # Skip parents not associated with this kid
            if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
                continue

            # Get notification service (mobile app)
            notify_service = parent_info.get(const.DATA_PARENT_MOBILE_NOTIFY_SERVICE)
            if not notify_service:
                continue

            # Strip "notify." prefix if present (services stored with prefix in v0.5.0+)
            # e.g., "notify.mobile_app_chads_phone" → "mobile_app_chads_phone"
            service_name = notify_service.removeprefix("notify.")

            # Build clear notification call
            service_data = {
                "message": "clear_notification",
                "data": {"tag": notification_tag},
            }
            coro = self.hass.services.async_call(
                "notify",
                service_name,  # Just "mobile_app_chads_phone" without "notify." prefix
                service_data,
            )
            clear_tasks.append((parent_id, coro))

        # Execute all clears concurrently
        if clear_tasks:
            results = await asyncio.gather(
                *[coro for _, coro in clear_tasks],
                return_exceptions=True,
            )
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    parent_id = clear_tasks[idx][0]
                    const.LOGGER.warning(
                        "Failed to clear notification for parent '%s': %s",
                        parent_id,
                        result,
                    )
        else:
            const.LOGGER.debug(
                "No parents with notification service found for kid '%s'",
                kid_id,
            )

    async def remind_in_minutes(
        self,
        kid_id: str,
        minutes: int,
        *,
        chore_id: str | None = None,
        reward_id: str | None = None,
    ) -> None:
        """
        Wait for the specified number of minutes and then resend the parent's
        notification if the chore or reward is still pending approval.

        If a chore_id is provided, the method checks the corresponding chore’s state.
        If a reward_id is provided, it checks whether that reward is still pending.
        """
        const.LOGGER.debug(
            "DEBUG: Notification - Scheduling reminder for Kid ID '%s', Chore ID '%s', Reward ID '%s' in %d minutes",
            kid_id,
            chore_id,
            reward_id,
            minutes,
        )
        # Use 5 seconds in test mode, convert minutes to seconds in production
        delay_seconds = 5 if self._test_mode else (minutes * 60)
        await asyncio.sleep(delay_seconds)

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "WARNING: Notification - Kid ID '%s' not found during reminder check",
                kid_id,
            )
            return

        if chore_id:
            chore_info: ChoreData | None = self.chores_data.get(chore_id)
            if not chore_info:
                const.LOGGER.warning(
                    "WARNING: Notification - Chore ID '%s' not found during reminder check",
                    chore_id,
                )
                return

            # Check if reminders are enabled for this chore (per-chore setting)
            if not chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_REMINDER, const.DEFAULT_NOTIFY_ON_REMINDER
            ):
                const.LOGGER.debug(
                    "DEBUG: Notification - Reminders disabled for Chore ID '%s'. Skipping reminder",
                    chore_id,
                )
                return

            # Get the PER-KID chore state (not the shared chore state)
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)

            # Only resend if the chore is still in a state that needs parent action:
            # - PENDING: Kid hasn't claimed yet (might need reminder about it)
            # - OVERDUE: Past due date, parent should review
            # Do NOT send for: claimed, approved, approved_in_part, completed_by_other
            if current_state not in [
                const.CHORE_STATE_PENDING,
                const.CHORE_STATE_OVERDUE,
            ]:
                const.LOGGER.info(
                    "INFO: Notification - Chore ID '%s' for Kid ID '%s' is in state '%s'. No reminder sent",
                    chore_id,
                    kid_id,
                    current_state,
                )
                return

            # Use helpers for action buttons (DRY refactor v0.5.0+)
            actions = build_chore_actions(kid_id, chore_id)
            extra_data = build_extra_data(kid_id, chore_id=chore_id)
            await self._notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_REMINDER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_REMINDER,
                message_data={
                    "chore_name": chore_info.get(
                        const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                    ),
                    "kid_name": kid_info.get(
                        const.DATA_KID_NAME, const.DISPLAY_UNNAMED_KID
                    ),
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(chore_id, kid_id),
            )
            const.LOGGER.info(
                "INFO: Notification - Resent reminder for Chore ID '%s' for Kid ID '%s'",
                chore_id,
                kid_id,
            )
        elif reward_id:
            # Check if the reward is still pending approval using modern reward_data
            reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {}).get(
                reward_id, {}
            )
            pending_count = reward_data.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)
            if pending_count <= 0:
                const.LOGGER.info(
                    "INFO: Notification - Reward ID '%s' is no longer pending approval for Kid ID '%s'. No reminder sent",
                    reward_id,
                    kid_id,
                )
                return
            # Use helpers for action buttons (DRY refactor v0.5.0+)
            actions = build_reward_actions(kid_id, reward_id)
            extra_data = build_extra_data(kid_id, reward_id=reward_id)
            reward_info: RewardData = cast(
                "RewardData", self.rewards_data.get(reward_id, {})
            )
            reward_name = reward_info.get(const.DATA_REWARD_NAME, "the reward")
            await self._notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_REMINDER,
                message_data={
                    "reward_name": reward_name,
                    "kid_name": kid_info.get(const.DATA_KID_NAME, "A kid"),
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(reward_id, kid_id),
            )
            const.LOGGER.info(
                "INFO: Notification - Resent reminder for Reward ID '%s' for Kid ID '%s'",
                reward_id,
                kid_id,
            )
        else:
            const.LOGGER.warning(
                "WARNING: Notification - No Chore ID or Reward ID provided for reminder action"
            )

    # -------------------------------------------------------------------------------------
    # Storage
    # -------------------------------------------------------------------------------------

    def _persist(self, immediate: bool = True):
        """Save coordinator data to persistent storage.

        Default behavior is immediate synchronous persistence to avoid race conditions
        between persist operations and config entry reload/unload. This is the safest
        and simplest approach for a system with frequent entity additions/deletions.

        Args:
            immediate: If True (default), save immediately without debouncing.
                      If False, schedule save with 5-second debouncing to batch multiple
                      updates (NOT currently used - kept for future optimization if needed).

        Philosophy:
            - Immediate=True is the default because:
              1. Most _persist() calls are NOT in loops
              2. Avoids race conditions with config reload timing
              3. Simplifies debugging and guarantees consistency
              4. Tests run efficiently without artificial delays
            - Debouncing (immediate=False) could be added in the future if profiling
              shows a specific high-frequency operation benefits from it
        """
        if immediate:
            # Cancel any pending debounced save
            if self._persist_task and not self._persist_task.done():
                self._persist_task.cancel()
                self._persist_task = None

            # Immediate synchronous save
            perf_start = time.perf_counter()
            self.storage_manager.set_data(self._data)
            self.hass.add_job(self.storage_manager.async_save)
            perf_duration = time.perf_counter() - perf_start
            const.LOGGER.debug(
                "PERF: _persist(immediate=True) took %.3fs (queued async save)",
                perf_duration,
            )
        else:
            # Debounced save - cancel existing task and schedule new one
            if self._persist_task and not self._persist_task.done():
                self._persist_task.cancel()

            self._persist_task = self.hass.async_create_task(
                self._persist_debounced_impl()
            )

    async def _persist_debounced_impl(self):
        """Implementation of debounced persist with delay."""
        try:
            # Wait for debounce period
            await asyncio.sleep(self._persist_debounce_seconds)

            # PERF: Track storage write frequency
            perf_start = time.perf_counter()

            self.storage_manager.set_data(self._data)
            await self.storage_manager.async_save()

            perf_duration = time.perf_counter() - perf_start
            const.LOGGER.debug(
                "PERF: _persist_debounced_impl() took %.3fs (async save completed)",
                perf_duration,
            )
        except asyncio.CancelledError:
            # Task was cancelled, new save scheduled
            const.LOGGER.debug("Debounced persist cancelled (replaced by new save)")
            raise
