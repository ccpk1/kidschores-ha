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

import asyncio
from datetime import datetime, timedelta
import sys
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import const
from .engines.statistics_engine import StatisticsEngine, filter_persistent_stats
from .managers import (
    ChoreManager,
    EconomyManager,
    GamificationManager,
    NotificationManager,
    RewardManager,
    StatisticsManager,
    SystemManager,
    UIManager,
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
        self._due_reminder_notif_sent: set[str] = set()  # Was: _due_soon_reminders_sent
        self._due_window_notif_sent: set[str] = (
            set()
        )  # NEW: Track due window notifications

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

        # UI manager for translation sensors and dashboard features (v0.5.0+)
        # Phase 7.7: Extracted from Coordinator to achieve < 500 line target
        self.ui_manager = UIManager(hass, self)

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

            # Check for due window transitions (v0.6.0+)
            await self.chore_manager.check_chore_due_window_transitions()

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
            self.ui_manager.bump_past_datetime_helpers,
            **const.DEFAULT_DAILY_RESET_TIME,
        )

        # Initialize badge references in kid chore tracking
        self.gamification_manager.update_chore_badge_references_for_kid()

        # Initialize chore and point stats
        for kid_id, kid_info in self.kids_data.items():
            self.chore_manager.recalculate_chore_stats_for_kid(kid_id)
            stats = self.stats.generate_point_stats(kid_info)
            # Only persist non-temporal stats (Phase 7.5: temporal lives in cache)
            kid_info[const.DATA_KID_POINT_STATS] = filter_persistent_stats(stats)

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
