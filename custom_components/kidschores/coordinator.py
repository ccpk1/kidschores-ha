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
from datetime import datetime, timedelta
import sys
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import const, kc_helpers as kh
from .engines.statistics_engine import StatisticsEngine, filter_persistent_stats
from .helpers.entity_helpers import (
    parse_entity_reference,
    remove_orphaned_kid_chore_entities,
    remove_orphaned_manual_adjustment_buttons,
    remove_orphaned_progress_entities,
    remove_orphaned_shared_chore_sensors,
)
from .managers import (
    ChoreManager,
    EconomyManager,
    GamificationManager,
    NotificationManager,
    RewardManager,
    StatisticsManager,
    SystemManager,
    UserManager,
)
from .store import KidsChoresStore
from .type_defs import (
    AchievementsCollection,
    BadgesCollection,
    BonusesCollection,
    ChallengesCollection,
    ChoresCollection,
    KidsCollection,
    ParentsCollection,
    PenaltiesCollection,
    RewardsCollection,
)
from .utils.math_utils import parse_points_adjust_values

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

        # User manager for Kid/Parent CRUD operations (v0.5.0+)
        # Phase 7.3b: Centralized create/update/delete with proper event signaling
        self.user_manager = UserManager(hass, self)

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

        # System manager for reactive entity registry cleanup (v0.5.0+)
        # Listens to DELETED signals, runs startup safety net
        self.system_manager = SystemManager(hass, self)

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
                    const.DATA_META_PENDING_EVALUATIONS: [],
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

            # Ensure pending_evaluations field exists in meta (added in Phase 7.4)
            if const.DATA_META in self._data:
                if (
                    const.DATA_META_PENDING_EVALUATIONS
                    not in self._data[const.DATA_META]
                ):
                    self._data[const.DATA_META][
                        const.DATA_META_PENDING_EVALUATIONS
                    ] = []

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
            # Only persist non-temporal stats (Phase 7.5: temporal lives in cache)
            kid_info[const.DATA_KID_POINT_STATS] = filter_persistent_stats(stats)

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

    # -------------------------------------------------------------------------------------
    # Orphan Entity Removal (delegates to entity_helpers)
    # -------------------------------------------------------------------------------------

    async def remove_all_orphaned_entities(self) -> int:
        """Run all orphan cleanup methods. Called on startup.

        Consolidates all data-driven orphan removal into a single call.
        Delegates to entity_helpers functions for the actual cleanup.

        Returns:
            Total count of removed entities.
        """
        perf_start = time.perf_counter()
        total_removed = 0
        entry_id = self.config_entry.entry_id

        # Kid-chore assignment orphans
        total_removed += await remove_orphaned_kid_chore_entities(
            self.hass, entry_id, self.kids_data, self.chores_data
        )

        # Shared chore sensor orphans
        total_removed += await remove_orphaned_shared_chore_sensors(
            self.hass, entry_id, self.chores_data
        )

        # Badge progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.badges_data,
            entity_type="badge",
            progress_suffix=const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR,
            assigned_kids_key=const.DATA_BADGE_ASSIGNED_TO,
        )

        # Achievement progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.achievements_data,
            entity_type="achievement",
            progress_suffix=const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX,
            assigned_kids_key=const.DATA_ACHIEVEMENT_ASSIGNED_KIDS,
        )

        # Challenge progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.challenges_data,
            entity_type="challenge",
            progress_suffix=const.DATA_CHALLENGE_PROGRESS_SUFFIX,
            assigned_kids_key=const.DATA_CHALLENGE_ASSIGNED_KIDS,
        )

        # Manual adjustment button orphans
        current_deltas = self._get_current_adjustment_deltas()
        total_removed += await remove_orphaned_manual_adjustment_buttons(
            self.hass, entry_id, current_deltas
        )

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

    def _get_current_adjustment_deltas(self) -> set[float]:
        """Get current configured adjustment delta values.

        Returns:
            Set of valid adjustment delta floats.
        """
        raw_values = self.config_entry.options.get(const.CONF_POINTS_ADJUST_VALUES)
        if not raw_values:
            return set(const.DEFAULT_POINTS_ADJUST_VALUES)

        if isinstance(raw_values, str):
            return set(parse_points_adjust_values(raw_values))

        if isinstance(raw_values, list):
            try:
                return {float(v) for v in raw_values}
            except (ValueError, TypeError):
                return set(const.DEFAULT_POINTS_ADJUST_VALUES)

        return set(const.DEFAULT_POINTS_ADJUST_VALUES)

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
            parts = parse_entity_reference(unique_id, prefix)
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
