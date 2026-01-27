# File: coordinator.py
"""Coordinator for the KidsChores integration.

Handles data synchronization, chore claiming and approval, badge tracking,
reward redemption, penalty application, and recurring chore handling.
Manages entities primarily using internal_id for consistency.

Architecture (v0.5.0+):
    - Coordinator = Routing layer (handles persistence, routes to Managers)
    - Managers = Stateful workflows (ChoreManager, EconomyManager, etc.)
    - Engines = Pure logic (ChoreEngine, EconomyEngine, etc.)
"""

# Pylint suppressions for valid coordinator architectural patterns:
# - too-many-lines: Complex coordinators legitimately need comprehensive logic
# - too-many-public-methods: Each service/feature requires its own public method

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import re
import sys
import time
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import const, data_builders as db, kc_helpers as kh
from .engines.statistics import StatisticsEngine
from .managers import (
    ChoreManager,
    EconomyManager,
    GamificationManager,
    NotificationManager,
    RewardManager,
    StatisticsManager,
)
from .store import KidsChoresStore
from .type_defs import (
    AchievementsCollection,
    BadgesCollection,
    BonusesCollection,
    ChallengesCollection,
    ChoresCollection,
    KidCumulativeBadgeProgress,
    KidData,
    KidsCollection,
    ParentsCollection,
    PenaltiesCollection,
    RewardsCollection,
)

# Type alias for typed config entry access (modern HA pattern)
# Must be defined after imports but before class since it references the class
type KidsChoresConfigEntry = ConfigEntry["KidsChoresDataCoordinator"]


class KidsChoresDataCoordinator(DataUpdateCoordinator):
    """Coordinator for KidsChores integration.

    Manages data primarily using internal_id for entities.

    Architecture (v0.5.0+):
        - Coordinator = Routing layer (calls Managers, handles persistence)
        - Managers = Stateful workflows (ChoreManager, EconomyManager, etc.)
        - Engines = Pure logic (ChoreEngine, EconomyEngine, etc.)
    """

    config_entry: ConfigEntry  # Override base class to enforce non-None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        store: KidsChoresStore,
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
        self.store = store
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

        # Statistics engine for unified period-based tracking (v0.5.0+)
        self.stats = StatisticsEngine()

        # Economy manager for point transactions and ledger (v0.5.0+)
        self.economy_manager = EconomyManager(hass, self)

        # Notification manager for all outgoing notifications (v0.5.0+)
        self.notification_manager = NotificationManager(hass, self)

        # Chore manager for chore workflow orchestration (v0.5.0+)
        # Phase 4: Initialized but not yet wired - ChoreOperations mixin remains active
        # Future phases will delegate ChoreOperations methods to this manager
        self.chore_manager = ChoreManager(hass, self, self.economy_manager)

        # Reward manager for reward redemption lifecycle (v0.5.0+)
        # Phase 6: Owns redeem/approve/disapprove/undo/reset workflows
        self.reward_manager = RewardManager(
            hass, self, self.economy_manager, self.notification_manager
        )

        # Gamification manager for badge/achievement/challenge evaluation (v0.5.x+)
        # Uses debounced evaluation triggered by coordinator events
        self.gamification_manager = GamificationManager(hass, self)

        # Statistics manager for event-driven stats aggregation (v0.5.0+)
        # Listens to POINTS_CHANGED, CHORE_APPROVED, REWARD_APPROVED events
        self.statistics_manager = StatisticsManager(hass, self)

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

    # -------------------------------------------------------------------------------------
    # Periodic + First Refresh
    # -------------------------------------------------------------------------------------

    async def _async_update_data(self):
        """Periodic update."""
        try:
            # Check overdue chores
            await self.chore_manager.check_overdue_chores()

            # Check for due-soon reminders (v0.5.0+)
            await self.chore_manager.check_chore_due_reminders()

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
        stored_data = self.store.data
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
            self.chore_manager.process_recurring_chore_resets,
            **const.DEFAULT_DAILY_RESET_TIME,
        )
        async_track_time_change(
            self.hass,
            self.chore_manager.check_overdue_chores,
            **const.DEFAULT_DAILY_RESET_TIME,
        )
        async_track_time_change(
            self.hass,
            self._bump_past_datetime_helpers,
            **const.DEFAULT_DAILY_RESET_TIME,
        )

        # Note: KC 3.x config sync is now handled by _run_pre_v50_migrations() above
        # (called when storage_schema_version < 42). No separate config sync needed here.

        # Initialize badge references in kid chore tracking
        self.gamification_manager.update_chore_badge_references_for_kid()

        # Initialize chore and point stats
        for kid_id, kid_info in self.kids_data.items():
            self.chore_manager.recalculate_chore_stats_for_kid(kid_id)
            stats = self.stats.generate_point_stats(kid_info)
            kid_info[const.DATA_KID_POINT_STATS] = stats

        # Note: CHORE_CLAIMED notifications now handled by NotificationManager
        # via event subscription in async_setup()

        self._persist(immediate=True)  # Startup persist should be immediate
        await super().async_config_entry_first_refresh()

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
            self.store.set_data(self._data)
            self.hass.add_job(self.store.async_save)
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

            self.store.set_data(self._data)
            await self.store.async_save()

            perf_duration = time.perf_counter() - perf_start
            const.LOGGER.debug(
                "PERF: _persist_debounced_impl() took %.3fs (async save completed)",
                perf_duration,
            )
        except asyncio.CancelledError:
            # Task was cancelled, new save scheduled
            const.LOGGER.debug("Debounced persist cancelled (replaced by new save)")
            raise

    # -------------------------------------------------------------------------------------
    # Approval Lock Management
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

    # -------------------------------------------------------------------------------------
    # Statistics Retention Configuration
    # -------------------------------------------------------------------------------------

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
        """Return the list of pending reward approvals (computed via RewardManager)."""
        return self.reward_manager.get_pending_approvals()

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
    # Home Assistant Registry Device and Entity Removal
    # -------------------------------------------------------------------------------------

    def _remove_entities_in_ha(self, item_id: str) -> int:
        """Remove all entities whose unique_id references the given item_id.

        Delegates to kc_helpers.remove_entities_by_item_id() for the actual work.
        Called when deleting kids, chores, rewards, penalties, bonuses, badges.

        Args:
            item_id: The UUID of the deleted item.

        Returns:
            Count of removed entities.
        """
        return kh.remove_entities_by_item_id(
            self.hass,
            self.config_entry.entry_id,
            item_id,
        )

    def _remove_device_from_registry(self, kid_id: str) -> None:
        """Remove kid device from device registry.

        When a kid is deleted, this function removes the corresponding device
        registry entry so the device no longer appears in the device list.

        Args:
            kid_id: Internal UUID of the kid to remove
        """
        from homeassistant.helpers import device_registry as dr

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(identifiers={(const.DOMAIN, kid_id)})

        if device:
            device_registry.async_remove_device(device.id)
            const.LOGGER.debug(
                "Removed device from registry for kid ID: %s",
                kid_id,
            )
        else:
            const.LOGGER.debug(
                "Device not found for kid ID: %s, nothing to remove",
                kid_id,
            )

    async def _remove_entities_by_validator(
        self,
        *,
        platforms: list[const.Platform] | None = None,
        suffix: str | None = None,
        midfix: str | None = None,
        is_valid: Callable[[str], bool],
        entity_type: str = "entity",
    ) -> int:
        """Core helper for removing entities that fail validation.

        Core method for removing entities whose underlying data relationship
        no longer exists. Uses efficient platform filtering and consistent
        logging patterns.

        Args:
            platforms: Platforms to scan (None = all platforms for this entry).
            suffix: Only check entities with this UID suffix.
            midfix: Only check entities containing this string.
            is_valid: Callback(unique_id) → True if entity should be kept.
            entity_type: Display name for logging.

        Returns:
            Count of removed entities.
        """
        perf_start = time.perf_counter()
        prefix = f"{self.config_entry.entry_id}_"
        removed_count = 0
        scanned_count = 0

        ent_reg = er.async_get(self.hass)

        # Get entities to scan (platform-filtered or all for this entry)
        if platforms:
            entities_to_scan = []
            for platform in platforms:
                entities_to_scan.extend(
                    kh.get_integration_entities(
                        self.hass, self.config_entry.entry_id, platform
                    )
                )
        else:
            entities_to_scan = [
                e
                for e in ent_reg.entities.values()
                if e.config_entry_id == self.config_entry.entry_id
            ]

        for entity_entry in list(entities_to_scan):
            unique_id = str(entity_entry.unique_id)

            # Apply prefix filter
            if not unique_id.startswith(prefix):
                continue

            # Apply suffix filter if specified
            if suffix and not unique_id.endswith(suffix):
                continue

            # Apply midfix filter if specified
            if midfix and midfix not in unique_id:
                continue

            scanned_count += 1

            # Check validity - remove if not valid
            if not is_valid(unique_id):
                const.LOGGER.debug(
                    "Removing orphaned %s: %s (uid: %s)",
                    entity_type,
                    entity_entry.entity_id,
                    unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)
                removed_count += 1

        perf_elapsed = time.perf_counter() - perf_start
        if removed_count > 0:
            const.LOGGER.info(
                "Removed %d orphaned %s(s) in %.3fs",
                removed_count,
                entity_type,
                perf_elapsed,
            )
        else:
            const.LOGGER.debug(
                "PERF: orphan scan for %s: %d checked in %.3fs, none removed",
                entity_type,
                scanned_count,
                perf_elapsed,
            )

        return removed_count

    async def _remove_orphaned_shared_chore_sensors(self) -> int:
        """Remove shared chore sensors for chores no longer marked as shared."""
        prefix = f"{self.config_entry.entry_id}_"
        suffix = const.DATA_GLOBAL_STATE_SUFFIX

        def is_valid(unique_id: str) -> bool:
            chore_id = unique_id[len(prefix) : -len(suffix)]
            chore_info = self.chores_data.get(chore_id)
            return bool(
                chore_info
                and chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED
            )

        return await self._remove_entities_by_validator(
            platforms=[const.Platform.SENSOR],
            suffix=suffix,
            is_valid=is_valid,
            entity_type="shared chore sensor",
        )

    # ------------------- Has assigned kid relationship -------------------------------------
    async def _remove_orphaned_kid_chore_entities(self) -> int:
        """Remove kid-chore entities for kids no longer assigned to chores."""
        if not self.kids_data or not self.chores_data:
            return 0

        prefix = f"{self.config_entry.entry_id}_"

        # Build valid kid-chore combinations
        valid_combinations: set[tuple[str, str]] = set()
        for chore_id, chore_info in self.chores_data.items():
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                valid_combinations.add((kid_id, chore_id))

        # Build regex for efficient extraction
        kid_ids = "|".join(re.escape(kid_id) for kid_id in self.kids_data)
        chore_ids = "|".join(re.escape(chore_id) for chore_id in self.chores_data)
        pattern = re.compile(rf"^({kid_ids})_({chore_ids})")

        def is_valid(unique_id: str) -> bool:
            core = unique_id[len(prefix) :]
            match = pattern.match(core)
            if not match:
                return True  # Not a kid-chore entity, keep it
            return (match.group(1), match.group(2)) in valid_combinations

        return await self._remove_entities_by_validator(
            platforms=[const.Platform.SENSOR, const.Platform.BUTTON],
            is_valid=is_valid,
            entity_type="kid-chore entity",
        )

    # ------------------- Has assigned kid relationship -------------------------------------
    async def _remove_orphaned_badge_entities(self) -> int:
        """Remove badge progress entities for unassigned kids."""
        return await self._remove_orphaned_progress_entities(
            entity_type="badge",
            entity_list_key=const.DATA_BADGES,
            progress_suffix=const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR,
            assigned_kids_key=const.DATA_BADGE_ASSIGNED_TO,
        )

    async def _remove_orphaned_progress_entities(
        self,
        entity_type: str,
        entity_list_key: str,
        progress_suffix: str,
        assigned_kids_key: str,
    ) -> int:
        """Remove progress entities for kids no longer assigned (generic)."""
        prefix = f"{self.config_entry.entry_id}_"

        def is_valid(unique_id: str) -> bool:
            core_id = unique_id[len(prefix) : -len(progress_suffix)]
            parts = core_id.split("_", 1)
            if len(parts) != 2:
                return True  # Can't parse, keep it

            kid_id, parent_entity_id = parts
            parent_info = self._data.get(entity_list_key, {}).get(parent_entity_id)
            return bool(
                parent_info and kid_id in parent_info.get(assigned_kids_key, [])
            )

        return await self._remove_entities_by_validator(
            platforms=[const.Platform.SENSOR],
            suffix=progress_suffix,
            is_valid=is_valid,
            entity_type=f"{entity_type} progress sensor",
        )

    async def _remove_orphaned_manual_adjustment_buttons(self) -> int:
        """Remove manual adjustment buttons with obsolete delta values."""
        # Get current configured deltas
        raw_values = self.config_entry.options.get(const.CONF_POINTS_ADJUST_VALUES)
        if not raw_values:
            current_deltas = set(const.DEFAULT_POINTS_ADJUST_VALUES)
        elif isinstance(raw_values, str):
            current_deltas = set(kh.parse_points_adjust_values(raw_values))
        elif isinstance(raw_values, list):
            try:
                current_deltas = {float(v) for v in raw_values}
            except (ValueError, TypeError):
                current_deltas = set(const.DEFAULT_POINTS_ADJUST_VALUES)
        else:
            current_deltas = set(const.DEFAULT_POINTS_ADJUST_VALUES)

        if not current_deltas:
            current_deltas = set(const.DEFAULT_POINTS_ADJUST_VALUES)

        button_suffix = const.BUTTON_KC_UID_SUFFIX_PARENT_POINTS_ADJUST

        def is_valid(unique_id: str) -> bool:
            # New format: {entry_id}_{kid_id}_{slugified_delta}_parent_points_adjust_button
            if button_suffix not in unique_id:
                return False
            try:
                # Extract the part before the suffix
                prefix_part = unique_id.split(button_suffix)[0]
                # Get last segment which is the slugified delta
                delta_slug = prefix_part.split("_")[-1]
                # Convert slugified delta back to float (replace 'neg' prefix and 'p' decimal)
                delta_str = delta_slug.replace("neg", "-").replace("p", ".")
                delta = float(delta_str)
                return delta in current_deltas
            except (ValueError, IndexError):
                const.LOGGER.warning(
                    "Could not parse delta from adjustment button uid: %s", unique_id
                )
                return True  # Can't parse, keep it

        return await self._remove_entities_by_validator(
            platforms=[const.Platform.BUTTON],
            midfix=button_suffix,
            is_valid=is_valid,
            entity_type="manual adjustment button",
        )

    async def _remove_orphaned_achievement_entities(self) -> int:
        """Remove achievement progress entities for unassigned kids."""
        return await self._remove_orphaned_progress_entities(
            entity_type="achievement",
            entity_list_key=const.DATA_ACHIEVEMENTS,
            progress_suffix=const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX,
            assigned_kids_key=const.DATA_ACHIEVEMENT_ASSIGNED_KIDS,
        )

    async def _remove_orphaned_challenge_entities(self) -> int:
        """Remove challenge progress entities for unassigned kids."""
        return await self._remove_orphaned_progress_entities(
            entity_type="challenge",
            entity_list_key=const.DATA_CHALLENGES,
            progress_suffix=const.DATA_CHALLENGE_PROGRESS_SUFFIX,
            assigned_kids_key=const.DATA_CHALLENGE_ASSIGNED_KIDS,
        )

    async def remove_all_orphaned_entities(self) -> int:
        """Run all orphan cleanup methods. Called on startup.

        Consolidates all data-driven orphan removal into a single call.
        Each method checks if underlying data relationships still exist.

        Returns:
            Total count of removed entities.
        """
        perf_start = time.perf_counter()
        total_removed = 0

        # Run all orphan cleanup methods
        total_removed += await self._remove_orphaned_kid_chore_entities()
        total_removed += await self._remove_orphaned_shared_chore_sensors()
        total_removed += await self._remove_orphaned_badge_entities()
        total_removed += await self._remove_orphaned_achievement_entities()
        total_removed += await self._remove_orphaned_challenge_entities()
        total_removed += await self._remove_orphaned_manual_adjustment_buttons()

        perf_elapsed = time.perf_counter() - perf_start
        if total_removed > 0:
            const.LOGGER.info(
                "Startup orphan cleanup: removed %d entities in %.3fs",
                total_removed,
                perf_elapsed,
            )
        else:
            const.LOGGER.debug(
                "PERF: startup orphan cleanup completed in %.3fs, no orphans found",
                perf_elapsed,
            )

        return total_removed

    async def remove_conditional_entities(
        self,
        *,
        kid_ids: list[str] | None = None,
    ) -> int:
        """Remove entities no longer allowed by feature flags.

        Removes entities that are no longer allowed based on current flag settings.
        Uses should_create_entity() from kc_helpers as single source of truth.

        This consolidates:
        - Extra entity cleanup (show_legacy_entities flag)
        - Shadow kid workflow entity cleanup
        - Shadow kid gamification entity cleanup

        Args:
            kid_ids: List of kid IDs to check, or None for all kids.
                     Use targeted kid_ids when a specific kid's flags change.
                     Use None for bulk cleanup (fresh startup, post-migration).

        Returns:
            Count of removed entities.

        Call patterns:
            - Options flow (extra flag changes): kid_ids=None (affects all)
            - Options flow (parent flags change): kid_ids=[shadow_kid_id]
            - Unlink service: kid_ids=[shadow_kid_id]
            - Fresh HA startup (not reload): kid_ids=None
            - Post-migration: kid_ids=None
        """
        perf_start = time.perf_counter()
        ent_reg = er.async_get(self.hass)
        prefix = f"{self.config_entry.entry_id}_"
        removed_count = 0

        # Get system-wide extra flag
        extra_enabled = self.config_entry.options.get(
            const.CONF_SHOW_LEGACY_ENTITIES, False
        )

        # Build kid filter set (None = check all)
        target_kids = set(kid_ids) if kid_ids else None

        for entity_entry in list(ent_reg.entities.values()):
            if entity_entry.config_entry_id != self.config_entry.entry_id:
                continue

            unique_id = str(entity_entry.unique_id)
            if not unique_id.startswith(prefix):
                continue

            # Extract kid_id from unique_id using helper
            parts = kh.parse_entity_reference(unique_id, prefix)
            if not parts:
                continue
            kid_id = parts[0]

            # Skip if not in target list (when targeted)
            if target_kids and kid_id not in target_kids:
                continue

            # Determine kid context
            is_shadow = kh.is_shadow_kid(self, kid_id)
            workflow_enabled = kh.should_create_workflow_buttons(self, kid_id)
            gamification_enabled = kh.should_create_gamification_entities(self, kid_id)

            # Check if entity should exist using unified filter
            if not kh.should_create_entity(
                unique_id,
                is_shadow_kid=is_shadow,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
                extra_enabled=extra_enabled,
            ):
                const.LOGGER.debug(
                    "Removing conditional entity for kid %s: %s (shadow=%s)",
                    kid_id,
                    entity_entry.entity_id,
                    is_shadow,
                )
                ent_reg.async_remove(entity_entry.entity_id)
                removed_count += 1

        perf_elapsed = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: remove_conditional_entities() scanned in %.3fs, removed %d",
            perf_elapsed,
            removed_count,
        )
        if removed_count > 0:
            const.LOGGER.info(
                "Cleaned up %d conditional entit(y/ies) based on current settings",
                removed_count,
            )
        return removed_count

    # -------------------------------------------------------------------------------------
    # KidsChores Entity Management Methods (for Options Flow and some Services)
    # These methods provide direct storage updates without triggering config reloads
    # -------------------------------------------------------------------------------------

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
            # Remove unused translation sensors (if language no longer needed)
            self.remove_unused_translation_sensors()
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

        # Remove device from device registry
        self._remove_device_from_registry(kid_id)

        # Cleanup references
        self._cleanup_deleted_kid_references()
        self._cleanup_parent_assignments()
        self._cleanup_pending_reward_approvals()

        # Remove unused translation sensors (if language no longer needed)
        self.remove_unused_translation_sensors()

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted kid '%s' (ID: %s)", kid_name, kid_id)

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

        # Remove unused translation sensors (if language no longer needed)
        self.remove_unused_translation_sensors()

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted parent '%s' (ID: %s)", parent_name, parent_id)

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

        # Remove awarded badges from kids via GamificationManager
        self.gamification_manager.remove_awarded_badges_by_id(badge_id=badge_id)

        # Phase 4: Clean up badge_progress from all kids after badge deletion
        # Also recalculate cumulative badge progress since a cumulative badge may have been deleted
        for kid_id in self.kids_data:
            self.gamification_manager.sync_badge_progress_for_kid(kid_id)
            # Refresh cumulative badge progress (handles case when cumulative badge is deleted)
            cumulative_progress = (
                self.gamification_manager.get_cumulative_badge_progress(kid_id)
            )
            self.kids_data[kid_id][const.DATA_KID_CUMULATIVE_BADGE_PROGRESS] = cast(
                "KidCumulativeBadgeProgress", cumulative_progress
            )

        # Remove badge-related entities from Home Assistant registry
        self._remove_entities_in_ha(badge_id)

        self._persist()
        self.async_update_listeners()
        const.LOGGER.info("INFO: Deleted badge '%s' (ID: %s)", badge_name, badge_id)

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
    # Data Cleanup
    # -------------------------------------------------------------------------------------

    def _cleanup_chore_from_kid(self, kid_id: str, chore_id: str) -> None:
        """Remove references to a specific chore from a kid's data."""
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # cast() for mypy: KidData is a TypedDict which is a dict[str, Any] at runtime
        if kh.cleanup_chore_from_kid_data(cast("dict[str, Any]", kid_info), chore_id):
            self._pending_chore_changed = True

    def _cleanup_pending_reward_approvals(self) -> None:
        """Remove reward_data entries for rewards that no longer exist."""
        valid_reward_ids = set(self._data.get(const.DATA_REWARDS, {}).keys())
        # cast() for mypy: dict[str, KidData] → dict[str, dict[str, Any]] at runtime
        if kh.cleanup_orphaned_reward_data(
            cast("dict[str, dict[str, Any]]", self.kids_data), valid_reward_ids
        ):
            self._pending_reward_changed = True

    def _cleanup_deleted_kid_references(self) -> None:
        """Remove references to kids that no longer exist from other sections."""
        valid_kid_ids = set(self.kids_data.keys())

        # Remove deleted kid IDs from all chore assignments
        kh.cleanup_orphaned_kid_refs_in_chores(
            self._data.get(const.DATA_CHORES, {}),
            valid_kid_ids,
        )

        # Remove progress in achievements and challenges
        kh.cleanup_orphaned_kid_refs_in_gamification(
            self._data.get(const.DATA_ACHIEVEMENTS, {}),
            valid_kid_ids,
            "achievements",
        )
        kh.cleanup_orphaned_kid_refs_in_gamification(
            self._data.get(const.DATA_CHALLENGES, {}),
            valid_kid_ids,
            "challenges",
        )

    def _cleanup_deleted_chore_references(self) -> None:
        """Remove references to chores that no longer exist from kid data."""
        valid_chore_ids = set(self.chores_data.keys())
        # cast() for mypy: dict[str, KidData] → dict[str, dict[str, Any]] at runtime
        kh.cleanup_orphaned_chore_refs_in_kids(
            cast("dict[str, dict[str, Any]]", self.kids_data), valid_chore_ids
        )

    def _cleanup_parent_assignments(self) -> None:
        """Remove any kid IDs from parent's 'associated_kids' that no longer exist."""
        valid_kid_ids = set(self.kids_data.keys())
        kh.cleanup_orphaned_kid_refs_in_parents(
            self._data.get(const.DATA_PARENTS, {}),
            valid_kid_ids,
        )

    def _cleanup_deleted_chore_in_achievements(self) -> None:
        """Clear selected_chore_id in achievements if the chore no longer exists."""
        valid_chore_ids = set(self.chores_data.keys())
        kh.cleanup_deleted_chore_in_gamification(
            self._data.get(const.DATA_ACHIEVEMENTS, {}),
            valid_chore_ids,
            const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID,
            "",
            "achievement",
        )

    def _cleanup_deleted_chore_in_challenges(self) -> None:
        """Clear selected_chore_id in challenges if the chore no longer exists."""
        valid_chore_ids = set(self.chores_data.keys())
        kh.cleanup_deleted_chore_in_gamification(
            self._data.get(const.DATA_CHALLENGES, {}),
            valid_chore_ids,
            const.DATA_CHALLENGE_SELECTED_CHORE_ID,
            const.SENTINEL_EMPTY,
            "challenge",
        )

    # -------------------------------------------------------------------------------------
    # Shadow Kid: Creation and Unlinking Methods
    # -------------------------------------------------------------------------------------

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

        Uses data_builders.build_kid() with is_shadow=True for consistent
        shadow kid creation across config flow and options flow.

        Args:
            parent_id: The internal ID of the parent.
            parent_info: The parent's data dictionary.

        Returns:
            The internal_id of the newly created shadow kid.
        """
        parent_name = parent_info.get(const.DATA_PARENT_NAME, const.SENTINEL_EMPTY)

        # Build shadow kid input from parent data
        shadow_input = {
            const.CFOF_KIDS_INPUT_KID_NAME: parent_name,
            const.CFOF_KIDS_INPUT_HA_USER: parent_info.get(
                const.DATA_PARENT_HA_USER_ID, ""
            ),
            const.CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE: parent_info.get(
                const.DATA_PARENT_DASHBOARD_LANGUAGE,
                const.DEFAULT_DASHBOARD_LANGUAGE,
            ),
            # Shadow kids have notifications disabled by default
            const.CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE: const.SENTINEL_EMPTY,
        }

        # Use unified db.build_kid() with shadow markers
        shadow_kid_data = dict(
            db.build_kid(shadow_input, is_shadow=True, linked_parent_id=parent_id)
        )
        shadow_kid_id = str(shadow_kid_data[const.DATA_KID_INTERNAL_ID])

        # Direct storage write
        self._data[const.DATA_KIDS][shadow_kid_id] = shadow_kid_data

        const.LOGGER.info(
            "Created shadow kid '%s' (ID: %s) for parent '%s' (ID: %s)",
            parent_name,
            shadow_kid_id,
            parent_name,
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
        # Regular kids always have full workflow and gamification features
        kid_info[const.DATA_KID_IS_SHADOW] = False
        kid_info[const.DATA_KID_LINKED_PARENT_ID] = None
        kid_info[const.DATA_KID_NAME] = new_name

        # Update device registry to reflect new name immediately
        self._update_kid_device_name(shadow_kid_id, new_name)

        # Note: No need to explicitly enable workflow/gamification flags here
        # Regular kids are implicitly full-featured (kc_helpers checks is_shadow_kid)

        const.LOGGER.info(
            "Unlinked shadow kid '%s' → '%s' (ID: %s), preserved all data",
            kid_name,
            new_name,
            shadow_kid_id,
        )

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

    def get_translation_sensor_eid(self, lang_code: str) -> str | None:
        """Get the entity ID for a translation sensor given a language code.

        Looks up the entity ID from the registry using the unique_id.
        Falls back to English ('en') if the requested language isn't found.
        Returns None only if neither the requested language nor English exist.

        Args:
            lang_code: ISO language code (e.g., 'en', 'es', 'de')

        Returns:
            Entity ID if found in registry (requested or fallback), None otherwise
        """
        from homeassistant.helpers.entity_registry import async_get

        entity_registry = async_get(self.hass)
        unique_id = f"{self.config_entry.entry_id}_{lang_code}{const.SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG}"
        entity_id = entity_registry.async_get_entity_id(
            "sensor", const.DOMAIN, unique_id
        )

        # If requested language not found and it's not already English, fall back to English
        if entity_id is None and lang_code != "en":
            unique_id_en = f"{self.config_entry.entry_id}_en{const.SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG}"
            entity_id = entity_registry.async_get_entity_id(
                "sensor", const.DOMAIN, unique_id_en
            )

        return entity_id

    async def ensure_translation_sensor_exists(self, lang_code: str) -> str:
        """Ensure a translation sensor exists for the given language code.

        If the sensor doesn't exist, creates it dynamically using the stored
        async_add_entities callback. Returns the entity ID.

        This is called when a kid's dashboard language changes to a new language
        that doesn't have a translation sensor yet.
        """
        # Import here to avoid circular dependency
        from .sensor import SystemDashboardTranslationSensor

        # Try to get entity ID from registry
        eid = self.get_translation_sensor_eid(lang_code)

        # If sensor already exists in registry, return the entity ID
        if eid:
            return eid

        # If sensor was marked as created but not in registry, use constructed entity_id
        if lang_code in self._translation_sensors_created:
            # Construct expected entity_id (sensor exists but not yet in registry)
            return (
                f"{const.SENSOR_KC_PREFIX}"
                f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{lang_code}"
            )

        # If no callback registered (shouldn't happen), log warning and return fallback
        if self._sensor_add_entities_callback is None:
            const.LOGGER.warning(
                "Cannot create translation sensor for '%s': no callback registered",
                lang_code,
            )
            # Fallback to English if available
            if const.DEFAULT_DASHBOARD_LANGUAGE in self._translation_sensors_created:
                fallback_eid = self.get_translation_sensor_eid(
                    const.DEFAULT_DASHBOARD_LANGUAGE
                )
                if fallback_eid:
                    return fallback_eid
            # Last resort: construct expected entity_id
            return (
                f"{const.SENSOR_KC_PREFIX}"
                f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{lang_code}"
            )

        # Create the new translation sensor
        const.LOGGER.info(
            "Creating translation sensor for newly-used language: %s", lang_code
        )
        new_sensor = SystemDashboardTranslationSensor(
            self, self.config_entry, lang_code
        )
        self._sensor_add_entities_callback([new_sensor])
        self._translation_sensors_created.add(lang_code)

        # Return expected entity_id (sensor not yet in registry)
        return (
            f"{const.SENSOR_KC_PREFIX}"
            f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{lang_code}"
        )

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

    def remove_unused_translation_sensors(self) -> None:
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
            if eid:  # Only try to remove if entity exists in registry
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
    # Utilities
    # -------------------------------------------------------------------------------------

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
