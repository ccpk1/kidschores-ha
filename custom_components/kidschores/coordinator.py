# File: coordinator.py
"""Coordinator for the KidsChores integration.

Handles data synchronization, chore claiming and approval, badge tracking,
reward redemption, penalty application, and recurring chore handling.
Manages entities primarily using internal_id for consistency.

Code Organization: Uses multiple inheritance to organize features by domain:
- ChoreOperations (coordinator_chore_operations.py): 43 chore lifecycle methods
- Future: RewardOperations, BadgeOperations, etc.
"""

# Pylint suppressions for valid coordinator architectural patterns:
# - too-many-lines: Complex coordinators legitimately need comprehensive logic
# - too-many-public-methods: Each service/feature requires its own public method

import asyncio
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
from .coordinator_chore_operations import ChoreOperations
from .notification_helper import (
    async_send_notification,
    build_chore_actions,
    build_extra_data,
    build_reward_actions,
)
from .statistics_engine import StatisticsEngine
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
    KidBadgeProgress,
    KidCumulativeBadgeProgress,
    KidData,
    KidsCollection,
    ParentsCollection,
    PenaltiesCollection,
    PenaltyData,
    RewardData,
    RewardsCollection,
)


class KidsChoresDataCoordinator(ChoreOperations, DataUpdateCoordinator):
    """Coordinator for KidsChores integration.

    Manages data primarily using internal_id for entities.

    Inherits from:
        - ChoreOperations: Chore lifecycle methods (claim, approve, etc.)
        - DataUpdateCoordinator: HA coordinator base class
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

        # Statistics engine for unified period-based tracking (v0.6.0+)
        self.stats = StatisticsEngine()

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

    def _get_retention_config(self) -> dict[str, int]:
        """Get retention configuration for period data pruning.

        Returns:
            Dict mapping period types to retention counts.
        """
        return {
            "daily": self.config_entry.options.get(
                const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
            ),
            "weekly": self.config_entry.options.get(
                const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
            ),
            "monthly": self.config_entry.options.get(
                const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
            ),
            "yearly": self.config_entry.options.get(
                const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
            ),
        }

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
            await self._check_chore_due_reminders()

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
            self._process_recurring_chore_resets,
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

    @property
    def pending_reward_approvals(self) -> list[dict[str, Any]]:
        """Return the list of pending reward approvals (computed from modern structure)."""
        return self.get_pending_reward_approvals_computed()

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
                const.DATA_KID_REWARD_DATA_NAME: cast(
                    "RewardData", self.rewards_data.get(reward_id, {})
                ).get(const.DATA_REWARD_NAME)
                or "",
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
        return cast("dict[str, Any]", reward_data.get(reward_id, {}))

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
        now_local = kh.dt_now_local()

        # Ensure periods structure exists with all_time bucket
        periods = reward_entry.setdefault(
            const.DATA_KID_REWARD_DATA_PERIODS,
            {
                const.DATA_KID_REWARD_DATA_PERIODS_DAILY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_YEARLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_ALL_TIME: {},
            },
        )

        # Get period mapping from StatisticsEngine
        period_mapping = self.stats.get_period_keys(now_local)

        # Record transaction using StatisticsEngine
        self.stats.record_transaction(
            periods,
            {counter_key: amount},
            period_key_mapping=period_mapping,
        )

        # Clean up old period data (NEW: rewards now have retention!)
        self.stats.prune_history(periods, self._get_retention_config())

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

    def _recalculate_chore_stats_for_kid(self, kid_id: str) -> None:
        """Delegate chore stats aggregation to StatisticsEngine.

        This method aggregates all kid_chore_stats for a given kid by
        delegating to the StatisticsEngine, which owns the period data
        structure knowledge.

        Args:
            kid_id: The internal ID of the kid.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return
        stats = self.stats.generate_chore_stats(kid_info, self.chores_data)
        kid_info[const.DATA_KID_CHORE_STATS] = stats

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
            )

        # 5) All-time and highest balance stats (handled incrementally)
        point_stats = kid_info.setdefault(const.DATA_KID_POINT_STATS, {})
        point_stats.setdefault(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_SPENT_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_NET_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME, {})
        point_stats.setdefault(const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0)

        if delta_value > 0:
            earned = point_stats.get(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0)
            point_stats[const.DATA_KID_POINT_STATS_EARNED_ALL_TIME] = round(
                earned + delta_value, const.DATA_FLOAT_PRECISION
            )
        elif delta_value < 0:
            spent = point_stats.get(const.DATA_KID_POINT_STATS_SPENT_ALL_TIME, 0.0)
            point_stats[const.DATA_KID_POINT_STATS_SPENT_ALL_TIME] = round(
                spent + delta_value, const.DATA_FLOAT_PRECISION
            )
        net = point_stats.get(const.DATA_KID_POINT_STATS_NET_ALL_TIME, 0.0)
        point_stats[const.DATA_KID_POINT_STATS_NET_ALL_TIME] = round(
            net + delta_value, const.DATA_FLOAT_PRECISION
        )

        # 6) Record into new point_data history (use same date logic as chore_data)
        periods_data = kid_info.setdefault(const.DATA_KID_POINT_DATA, {}).setdefault(  # type: ignore[typeddict-item]
            const.DATA_KID_POINT_DATA_PERIODS, {}
        )

        now_local = kh.dt_now_local()
        period_mapping = self.stats.get_period_keys(now_local)

        # Record points_total using StatisticsEngine
        self.stats.record_transaction(
            periods_data,
            {const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL: delta_value},
            period_key_mapping=period_mapping,
        )

        # Handle by_source tracking separately (nested structure not handled by engine)
        for period_key, period_id in period_mapping.items():
            bucket = periods_data.setdefault(period_key, {})
            entry = bucket.setdefault(period_id, {})
            if (
                const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE not in entry
                or not isinstance(
                    entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE], dict
                )
            ):
                entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE] = {}
            entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE].setdefault(source, 0.0)
            entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] = round(
                entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] + delta_value,
                const.DATA_FLOAT_PRECISION,
            )

        # Also record by_source for all_time bucket
        all_time_bucket = periods_data.setdefault(
            const.DATA_KID_POINT_DATA_PERIODS_ALL_TIME, {}
        )
        all_time_entry = all_time_bucket.setdefault(const.PERIOD_ALL_TIME, {})
        if (
            const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE not in all_time_entry
            or not isinstance(
                all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE], dict
            )
        ):
            all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE] = {}
        all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE].setdefault(
            source, 0.0
        )
        all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] = round(
            all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source]
            + delta_value,
            const.DATA_FLOAT_PRECISION,
        )

        # 7) Re‑evaluate everything and persist
        # Note: Call _recalculate_point_stats_for_kid BEFORE updating all-time stats
        # so that it preserves the incrementally-tracked all-time values
        self._recalculate_point_stats_for_kid(kid_id)

        # 8) Update all-time by-source stats (must be done AFTER recalculate to avoid being overwritten)
        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
        by_source_all_time = point_stats.get(
            const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME, {}
        )
        by_source_all_time.setdefault(source, 0.0)
        by_source_all_time[source] += delta_value
        by_source_all_time[source] = round(
            by_source_all_time[source], const.DATA_FLOAT_PRECISION
        )

        highest = point_stats.get(const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0)
        point_stats[const.DATA_KID_POINT_STATS_HIGHEST_BALANCE] = max(highest, new)

        # Clean up old period data to keep storage manageable
        self.stats.prune_history(periods_data, self._get_retention_config())

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

    def _recalculate_point_stats_for_kid(self, kid_id: str) -> None:
        """Delegate point stats aggregation to StatisticsEngine.

        This method aggregates all kid_point_stats for a given kid by
        delegating to the StatisticsEngine, which owns the period data
        structure knowledge.

        Args:
            kid_id: The internal ID of the kid.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return
        stats = self.stats.generate_point_stats(kid_info)
        kid_info[const.DATA_KID_POINT_STATS] = stats

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

        # Recalculate aggregated reward stats
        self._recalculate_reward_stats_for_kid(kid_id)

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

            # Recalculate aggregated reward stats (after either branch)
            self._recalculate_reward_stats_for_kid(kid_id)

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

            # Recalculate aggregated reward stats
            self._recalculate_reward_stats_for_kid(kid_id)

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

        # Recalculate aggregated reward stats (pending count changed)
        self._recalculate_reward_stats_for_kid(kid_id)

        # No notification sent (silent undo)

        self._persist()
        self.async_set_updated_data(self._data)

    def _recalculate_reward_stats_for_kid(self, kid_id: str) -> None:
        """Delegate reward stats aggregation to StatisticsEngine.

        This method aggregates all kid_reward_stats for a given kid by
        delegating to the StatisticsEngine, which owns the period data
        structure knowledge.

        Note: Reward stats are computed and stored in kid_info but not yet
        exposed in the UI. Ready for future entity integration.

        Args:
            kid_id: The internal ID of the kid.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return
        stats = self.stats.generate_reward_stats(kid_info, self.rewards_data)
        kid_info[const.DATA_KID_REWARD_STATS] = stats

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
        today_local_iso = kh.dt_today_iso()

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
                    self.kids_data[kid_id][const.DATA_KID_CUMULATIVE_BADGE_PROGRESS] = (  # pyright: ignore[reportGeneralTypeIssues]
                        stored_cumulative_badge_progress
                    )
                effective_badge_id = cumulative_badge_progress.get(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID, None
                )
                if effective_badge_id and effective_badge_id == badge_id:
                    # This badge matches with the calculated effective badge ID, so it should be awarded
                    progress = kid_info.get(
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
            progress_update: KidCumulativeBadgeProgress = cast(
                "KidCumulativeBadgeProgress",
                badge_progress.copy() if badge_progress else {},
            )

            handler_tuple = target_type_handlers.get(target_type or "")
            if handler_tuple:
                handler, handler_kwargs = handler_tuple
                progress_update = handler(
                    kid_info,
                    badge_info,
                    badge_id,
                    tracked_chores,
                    progress_update,
                    today_local_iso,
                    threshold_value,
                    **handler_kwargs,
                )
            else:
                # Fallback for unknown types (could log or skip)
                continue

            # Store the updated progress data for this badge
            badge_progress_dict = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
            badge_progress_dict[badge_id] = cast("KidBadgeProgress", progress_update)

            # Award the badge if criteria are met and not already earned
            if progress_update.get(const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET, False):
                current_state = progress_update.get(
                    const.DATA_KID_BADGE_PROGRESS_STATUS,
                    const.BADGE_STATE_IN_PROGRESS,
                )
                if current_state != const.BADGE_STATE_EARNED:
                    badge_progress_dict[badge_id][
                        const.DATA_KID_BADGE_PROGRESS_STATUS
                    ] = const.BADGE_STATE_EARNED
                    badge_progress_dict[badge_id][
                        const.DATA_KID_BADGE_PROGRESS_LAST_AWARDED
                    ] = kh.dt_today_iso()
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
                yesterday_iso = kh.dt_add_interval(
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
            if float(cast("float", multiplier)) > const.DEFAULT_ZERO:
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

        today_local_iso = kh.dt_today_iso()
        now_local = kh.dt_now_local()

        badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})

        # Get period mapping from StatisticsEngine
        period_mapping = self.stats.get_period_keys(now_local)

        # Declare periods variable for use in both branches
        periods: dict[str, Any]

        if badge_id not in badges_earned:
            # Create new badge tracking entry with all_time bucket
            badges_earned[badge_id] = {  # pyright: ignore[reportArgumentType]
                const.DATA_KID_BADGES_EARNED_NAME: badge_info.get(
                    const.DATA_BADGE_NAME, ""
                ),
                const.DATA_KID_BADGES_EARNED_LAST_AWARDED: today_local_iso,
                const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1,
                const.DATA_KID_BADGES_EARNED_PERIODS: {
                    const.DATA_KID_BADGES_EARNED_PERIODS_DAILY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_WEEKLY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_MONTHLY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_YEARLY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_ALL_TIME: {},
                },
            }
            # Record initial award using StatisticsEngine
            periods = badges_earned[badge_id][  # type: ignore[assignment]
                const.DATA_KID_BADGES_EARNED_PERIODS
            ]
            self.stats.record_transaction(
                periods,
                {const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1},
                period_key_mapping=period_mapping,
            )
            const.LOGGER.info(
                "INFO: Update Kid Badges Earned - Created new tracking for badge '%s' for kid '%s'.",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )
        else:
            tracking_entry = badges_earned[badge_id]
            tracking_entry[const.DATA_KID_BADGES_EARNED_NAME] = badge_info.get(
                const.DATA_BADGE_NAME, ""
            )
            tracking_entry[const.DATA_KID_BADGES_EARNED_LAST_AWARDED] = today_local_iso
            tracking_entry[const.DATA_KID_BADGES_EARNED_AWARD_COUNT] = (
                tracking_entry.get(const.DATA_KID_BADGES_EARNED_AWARD_COUNT, 0) + 1
            )

            # Ensure periods structure exists with all_time bucket
            periods = tracking_entry.setdefault(
                const.DATA_KID_BADGES_EARNED_PERIODS,
                {},  # type: ignore[typeddict-item]
            )
            periods.setdefault(const.DATA_KID_BADGES_EARNED_PERIODS_ALL_TIME, {})

            # Record award using StatisticsEngine
            self.stats.record_transaction(
                periods,
                {const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1},
                period_key_mapping=period_mapping,
            )

            const.LOGGER.info(
                "INFO: Update Kid Badges Earned - Updated tracking for badge '%s' for kid '%s'.",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )

            # Cleanup old period data using StatisticsEngine
            self.stats.prune_history(periods, self._get_retention_config())

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
                kid_info_loop: KidData | None = self.kids_data.get(kid_id)
                if not kid_info_loop or const.DATA_KID_CHORE_DATA not in kid_info_loop:
                    continue

                # Use the helper function to get the correct in-scope chores for this badge and kid
                in_scope_chores_list = self._get_badge_in_scope_chores_list(
                    badge_info, kid_id
                )

                # Add badge reference to each tracked chore
                for chore_id in in_scope_chores_list:
                    if chore_id in kid_info_loop[const.DATA_KID_CHORE_DATA]:
                        chore_entry = kid_info_loop[const.DATA_KID_CHORE_DATA][chore_id]
                        badge_refs: list[str] = chore_entry.get(
                            const.DATA_KID_CHORE_DATA_BADGE_REFS, []
                        )
                        if badge_id not in badge_refs:
                            badge_refs.append(badge_id)
                            chore_entry[const.DATA_KID_CHORE_DATA_BADGE_REFS] = (
                                badge_refs
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
            kid_id = kh.get_entity_id_by_name(self, const.ENTITY_TYPE_KID, kid_name)
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
            badge_id = kh.get_entity_id_by_name(
                self, const.ENTITY_TYPE_BADGE, badge_name
            )
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
            badge_info_elif: BadgeData | None = self.badges_data.get(badge_id)
            if not badge_info_elif:
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - Badge ID '%s' not found in badges data.",
                    badge_id,
                )
            else:
                badge_name = badge_info_elif.get(const.DATA_BADGE_NAME, badge_id)
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
                    earned_by_list = badge_info_elif.get(const.DATA_BADGE_EARNED_BY, [])
                    if kid_id in earned_by_list:
                        earned_by_list.remove(kid_id)

                # All kids should already be removed from the badge earned_by list, but in case of orphans, clear those fields
                if const.DATA_BADGE_EARNED_BY in badge_info_elif:
                    badge_info_elif[const.DATA_BADGE_EARNED_BY].clear()

                if not found:
                    const.LOGGER.warning(
                        "WARNING: Remove Awarded Badges - Badge '%s' ('%s') not found in any kid's data.",
                        badge_id,
                        badge_name,
                    )

        elif kid_id:
            # Remove all awarded badges for a specific kid.
            kid_info_elif: KidData | None = self.kids_data.get(kid_id)
            if not kid_info_elif:
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
            kid_name = kid_info_elif.get(const.DATA_KID_NAME, "Unknown Kid")
            for badge_id, badge_info in self.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME, "")
                earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                badges_earned = kid_info_elif.setdefault(
                    const.DATA_KID_BADGES_EARNED, {}
                )
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
            if const.DATA_KID_BADGES_EARNED in kid_info_elif:
                kid_info_elif[const.DATA_KID_BADGES_EARNED].clear()
            # CLS Should also clear all extra fields for all badge types later

            if not found:
                const.LOGGER.warning(
                    "WARNING: Remove Awarded Badges - No badge found for kid '%s'.",
                    kid_info_elif.get(const.DATA_KID_NAME, kid_id),
                )

        else:
            # Remove Awarded Badges for all kids.
            const.LOGGER.info(
                "INFO: Remove Awarded Badges - Removing all awarded badges for all kids."
            )
            for badge_id, badge_info in self.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME, "")
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
        return cast("dict[str, Any]", stored_progress)

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
        today_local_iso = kh.dt_today_iso()

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
                new_end_date_iso = kh.dt_next_schedule(
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
                    new_end_date_iso = kh.dt_add_interval(
                        str(prior_end_date_iso) if prior_end_date_iso else "",
                        interval_unit=custom_interval_unit,
                        delta=custom_interval,
                        require_future=True,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
                else:
                    # Default fallback to weekly
                    new_end_date_iso = kh.dt_add_interval(
                        str(prior_end_date_iso) if prior_end_date_iso else "",
                        interval_unit=const.TIME_UNIT_WEEKS,
                        delta=1,
                        require_future=True,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
            else:
                # Use standard frequency helper
                new_end_date_iso = kh.dt_next_schedule(
                    str(prior_end_date_iso) if prior_end_date_iso else "",
                    interval_type=recurring_frequency or "",
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
                        start_dt_utc = kh.dt_to_utc(existing_start_date_iso)
                        end_dt_utc = kh.dt_to_utc(end_date_iso)

                        if start_dt_utc and end_dt_utc:
                            # Calculate duration in days
                            duration = (end_dt_utc - start_dt_utc).days

                            # Set new start date by subtracting the same duration from new end date
                            # Cast ensures new_end_date_iso is str | date | datetime (not None)
                            new_start_date_iso = str(
                                kh.dt_add_interval(
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
                    progress[field] = default  # type: ignore[literal-required]

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
            badge_progress_dict = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
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
                        self._get_badge_in_scope_chores_list(badge_info, kid_id)
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress[const.DATA_BADGE_ASSIGNED_TO] = assigned_to

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
                            today_local_iso = kh.dt_today_iso()
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
                                    new_end_date_iso = kh.dt_add_interval(
                                        today_local_iso,
                                        interval_unit=custom_interval_unit,
                                        delta=custom_interval,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                                else:
                                    # Default fallback to weekly
                                    new_end_date_iso = kh.dt_add_interval(
                                        today_local_iso,
                                        interval_unit=const.TIME_UNIT_WEEKS,
                                        delta=1,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                            else:
                                # Use standard frequency helper
                                new_end_date_iso = kh.dt_next_schedule(
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
                kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id] = cast(  # pyright: ignore[reportTypedDictNotRequiredAccess]
                    "KidBadgeProgress", progress
                )

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
                progress_sync: dict[str, Any] = cast(
                    "dict[str, Any]", badge_progress_dict[badge_id]
                )

                # --- Common fields ---
                progress_sync[const.DATA_KID_BADGE_PROGRESS_NAME] = badge_info.get(
                    const.DATA_BADGE_NAME, "Unknown Badge"
                )
                progress_sync[const.DATA_KID_BADGE_PROGRESS_TYPE] = badge_type

                # --- Target fields ---
                if has_target:
                    target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_TYPE,
                        const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                    )
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE] = (
                        target_type
                    )

                    progress_sync[
                        const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE
                    ] = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )

                # --- Special Occasion fields ---
                if has_special_occasion:
                    # Add occasion type if present
                    occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE)
                    if occasion_type:
                        progress_sync[const.DATA_BADGE_OCCASION_TYPE] = occasion_type

                # --- Achievement Linked fields ---
                if has_achievement_linked:
                    achievement_id = badge_info.get(
                        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                    )
                    if achievement_id:
                        progress_sync[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = (
                            achievement_id
                        )

                # --- Challenge Linked fields ---
                if has_challenge_linked:
                    challenge_id = badge_info.get(const.DATA_BADGE_ASSOCIATED_CHALLENGE)
                    if challenge_id:
                        progress_sync[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = (
                            challenge_id
                        )

                # --- Tracked Chores fields ---
                if has_tracked_chores and not has_special_occasion:
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = (
                        self._get_badge_in_scope_chores_list(badge_info, kid_id)
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress_sync[const.DATA_BADGE_ASSIGNED_TO] = assigned_to

                # --- Awards fields --- Not required for now
                # if has_awards:
                #    awards = badge_info.get(const.DATA_BADGE_AWARDS, {})
                #    progress_sync[const.DATA_BADGE_AWARDS] = awards

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
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY] = (
                        recurring_frequency
                    )
                    # Only update start and end dates if they have values
                    if start_date_iso:
                        progress_sync[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                            start_date_iso
                        )
                    if end_date_iso:
                        progress_sync[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                            end_date_iso
                        )

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
        today_local_iso = kh.dt_today_iso()

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
            cumulative_badge_progress.update(  # pyright: ignore[reportArgumentType]
                {
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
                    next_end = kh.dt_add_interval(
                        base_date=base_date_iso,
                        interval_unit=custom_interval_unit,  # Fix: change from custom_interval_unit to interval_unit
                        delta=custom_interval,  # Fix: change from custom_interval to delta
                        require_future=True,
                        reference_datetime=reference_datetime_iso,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
                else:
                    # Fallback to existing logic if custom interval/unit are invalid
                    next_end = kh.dt_next_schedule(
                        base_date_iso,
                        interval_type=frequency,
                        require_future=True,
                        reference_datetime=reference_datetime_iso,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
            else:
                # Default behavior for non-custom frequencies
                base_date_iso = today_local_iso
                next_end = kh.dt_next_schedule(
                    base_date_iso,
                    interval_type=frequency,
                    require_future=True,
                    reference_datetime=reference_datetime_iso,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )

            # Compute the grace period end date by adding the grace period (in days) to the maintenance end date
            # Cast ensures next_end is str | date (not None) for the interval calculation
            next_grace = kh.dt_add_interval(
                cast("str | date", next_end),
                const.TIME_UNIT_DAYS,
                grace_days,
                require_future=True,
                return_type=const.HELPER_RETURN_ISO_DATE,
            )

        # If the badge maintenance requirements are met, update the badge as successfully maintained.
        if award_success:
            cumulative_badge_progress.update(  # pyright: ignore[reportCallIssue]
                {  # pyright: ignore[reportArgumentType]
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
            cumulative_badge_progress.update(  # pyright: ignore[reportCallIssue]
                {  # pyright: ignore[reportArgumentType]
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
            cumulative_badge_progress.update(  # pyright: ignore[reportCallIssue]
                {  # pyright: ignore[reportArgumentType]
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

        return (
            cast("dict[Any, Any] | None", highest_earned),
            cast("dict[Any, Any] | None", next_higher),
            cast("dict[Any, Any] | None", next_lower),
            baseline,
            cycle_points,
        )

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
        penalty_applies = kid_info[const.DATA_KID_PENALTY_APPLIES]
        if penalty_id in penalty_applies:
            penalty_applies[penalty_id] = int(penalty_applies[penalty_id]) + 1  # type: ignore[assignment]
        else:
            penalty_applies[penalty_id] = 1  # type: ignore[assignment]

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
        bonus_applies = kid_info[const.DATA_KID_BONUS_APPLIES]
        if bonus_id in bonus_applies:
            bonus_applies[bonus_id] = int(bonus_applies[bonus_id]) + 1  # type: ignore[assignment]
        else:
            bonus_applies[bonus_id] = 1  # type: ignore[assignment]

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

        today_local = kh.dt_today_local()

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

                today_local_iso = kh.dt_today_iso()

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
            achievement_info[const.DATA_ACHIEVEMENT_PROGRESS][kid_id] = cast(
                "AchievementProgress", progress_dict
            )
            progress_for_kid = cast("AchievementProgress", progress_dict)

        # Type narrow: progress_for_kid is now guaranteed to be AchievementProgress (not None)
        progress_for_kid_checked: AchievementProgress = progress_for_kid

        # Mark achievement as earned for the kid by storing progress (e.g. set to target)
        progress_for_kid_checked[const.DATA_ACHIEVEMENT_AWARDED] = True
        progress_for_kid_checked[const.DATA_ACHIEVEMENT_CURRENT_VALUE] = (  # type: ignore[typeddict-unknown-key]
            achievement_info.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
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
            if kid_id in progress and progress[kid_id].get(
                const.DATA_CHALLENGE_AWARDED, False
            ):
                continue

            # Check challenge window
            start_date_utc = kh.dt_to_utc(
                challenge_info.get(const.DATA_CHALLENGE_START_DATE) or ""
            )

            end_date_utc = kh.dt_to_utc(
                challenge_info.get(const.DATA_CHALLENGE_END_DATE) or ""
            )

            if start_date_utc and now_utc < start_date_utc:
                continue
            if end_date_utc and now_utc > end_date_utc:
                continue

            target = challenge_info.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
            challenge_type = challenge_info.get(const.DATA_CHALLENGE_TYPE)

            # For a total count challenge:
            if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                progress_item: ChallengeProgress = progress.setdefault(
                    kid_id,
                    {
                        const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                        const.DATA_CHALLENGE_AWARDED: False,
                    },
                )

                if progress_item.get(const.DATA_CHALLENGE_COUNT, 0) >= target:
                    self._award_challenge(kid_id, challenge_id)
            # For a daily minimum challenge, you might store per-day counts:
            elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                progress_item = progress.setdefault(
                    kid_id,
                    {
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
                        if int(  # type: ignore[call-overload]
                            progress[const.DATA_CHALLENGE_DAILY_COUNTS].get(
                                day, const.DEFAULT_ZERO
                            )
                        ) < int(required_daily):
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
            {
                const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                const.DATA_CHALLENGE_AWARDED: False,
            },
        )

        # Mark challenge as earned for the kid by storing progress
        progress_for_kid[const.DATA_CHALLENGE_AWARDED] = True
        progress_for_kid[const.DATA_CHALLENGE_COUNT] = challenge_info.get(
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
            progress[const.DATA_KID_CURRENT_STREAK] = current_streak + 1

        # Reset to 1 if not done yesterday
        else:
            progress[const.DATA_KID_CURRENT_STREAK] = 1

        progress[const.DATA_KID_LAST_STREAK_DATE] = today.isoformat()

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
            for kid_info_loop in self.kids_data.values():
                if penalty_id in kid_info_loop.get(const.DATA_KID_PENALTY_APPLIES, {}):
                    found = True
                    kid_info_loop[const.DATA_KID_PENALTY_APPLIES].pop(penalty_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Penalties - Penalty ID '%s' not found in any kid's data.",
                    penalty_id,
                )

        elif kid_id:
            # Reset all penalties for a specific kid
            kid_info_elif: KidData | None = self.kids_data.get(kid_id)
            if not kid_info_elif:
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

            kid_info_elif[const.DATA_KID_PENALTY_APPLIES].clear()

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
            for kid_info_loop in self.kids_data.values():
                if bonus_id in kid_info_loop.get(const.DATA_KID_BONUS_APPLIES, {}):
                    found = True
                    kid_info_loop[const.DATA_KID_BONUS_APPLIES].pop(bonus_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Bonuses - Bonus '%s' not found in any kid's data.",
                    bonus_id,
                )

        elif kid_id:
            # Reset all bonuses for a specific kid
            kid_info_elif: KidData | None = self.kids_data.get(kid_id)
            if not kid_info_elif:
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

            kid_info_elif[const.DATA_KID_BONUS_APPLIES].clear()

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
            for kid_info_loop in self.kids_data.values():
                reward_data = kid_info_loop.get(const.DATA_KID_REWARD_DATA, {})
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
            kid_info_elif: KidData | None = self.kids_data.get(kid_id)
            if not kid_info_elif:
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
            if const.DATA_KID_REWARD_DATA in kid_info_elif:
                kid_info_elif[const.DATA_KID_REWARD_DATA].clear()

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
            parent_language = (
                parent_info.get(const.DATA_PARENT_DASHBOARD_LANGUAGE)
                or cast("KidData", self.kids_data.get(kid_id, {})).get(
                    const.DATA_KID_DASHBOARD_LANGUAGE
                )
                or self.hass.config.language
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
