"""Statistics Manager - Event-driven statistics aggregation.

This manager handles all period-based and all-time statistics:
- Point stats (earned/spent by period and source)
- Chore stats (completions by period)
- Reward stats (claims/approvals by period)

ARCHITECTURE (v0.5.0+ "Clean Break"):
- StatisticsManager LISTENS to domain events (POINTS_CHANGED, CHORE_APPROVED, etc.)
- Domain managers (EconomyManager, ChoreManager, RewardManager) emit events ONLY
- This decouples business logic from historical reporting

Event subscriptions:
- SIGNAL_SUFFIX_POINTS_CHANGED → _on_points_changed()
- SIGNAL_SUFFIX_CHORE_APPROVED → _on_chore_approved()
- SIGNAL_SUFFIX_CHORE_COMPLETED → _on_chore_completed()
- SIGNAL_SUFFIX_CHORE_CLAIMED → _on_chore_claimed()
- SIGNAL_SUFFIX_CHORE_DISAPPROVED → _on_chore_disapproved()
- SIGNAL_SUFFIX_CHORE_OVERDUE → _on_chore_overdue()
- SIGNAL_SUFFIX_REWARD_APPROVED → _on_reward_approved()

PHASE 7.5 ARCHITECTURE (Statistics Presenter & Data Sanitization):
- Directive 1: Derivative Data is Ephemeral - temporal stats MUST NOT be persisted
- Directive 2: Manager-Controlled Time - StatisticsManager owns the "Financial Calendar"
- Directive 3: Cache is Presentation, not Database - must be recreatable from buckets

Cache Architecture:
- _stats_cache[kid_id] contains PRES_* keys for presentation (memory-only)
- Persistent data lives in point_data.periods (buckets) and high-water marks
- Cache is rebuilt from buckets on startup and on-demand (get_stats API)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from homeassistant.core import callback

from .. import const
from ..utils.dt_utils import dt_now_local, dt_parse
from .base_manager import BaseManager

if TYPE_CHECKING:
    from asyncio import TimerHandle
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator
    from ..engines.statistics_engine import StatisticsEngine


__all__ = ["StatisticsManager"]

# Phase 7.5: Cache refresh debounce delay (500ms)
# Prevents thundering herd on rapid events (e.g., bulk approvals)
CACHE_REFRESH_DEBOUNCE_SECONDS = 0.5


class StatisticsManager(BaseManager):
    """Manager for event-driven statistics aggregation.

    Responsibilities:
    - Listen to domain events (POINTS_CHANGED, CHORE_APPROVED, REWARD_APPROVED)
    - Update period-based statistics (daily/weekly/monthly/yearly/all_time)
    - Maintain all-time aggregates
    - Prune old history data

    NOT responsible for:
    - Computing point balances (EconomyManager)
    - Business logic (domain managers)
    - Gamification triggers (GamificationManager)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize the StatisticsManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main KidsChores coordinator
        """
        super().__init__(hass, coordinator)
        self._coordinator = coordinator

        # Phase 7.5: Presentation cache (memory-only, PRES_* keys)
        # Cache structure: {kid_id: {PRES_KID_POINTS_EARNED_TODAY: ..., ...}}
        # This cache holds derived/temporal values that are NOT persisted to storage.
        # All values can be regenerated from period buckets (point_data.periods).
        self._stats_cache: dict[str, dict[str, Any]] = {}

        # Phase 7.5: Debounce timers for cache refreshes (500ms per-kid)
        # Prevents thundering herd on rapid events (e.g., bulk approvals)
        self._cache_timers: dict[str, TimerHandle] = {}

    @property
    def _stats_engine(self) -> StatisticsEngine:
        """Get the StatisticsEngine from coordinator."""
        return self._coordinator.stats

    def get_retention_config(self) -> dict[str, int]:
        """Get retention configuration for period data pruning.

        Reads from config_entry.options for user-configurable retention limits.

        Returns:
            Dict mapping period types to retention counts.
        """
        return {
            "daily": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
            ),
            "weekly": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
            ),
            "monthly": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
            ),
            "yearly": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
            ),
        }

    async def async_setup(self) -> None:
        """Set up event subscriptions for statistics tracking.

        Subscribe to:
        - CHORES_READY: Startup cascade - hydrate stats → emit STATS_READY
        - POINTS_CHANGED: Track point transactions
        - CHORE_APPROVED: Track chore completions
        - REWARD_APPROVED: Track reward redemptions

        Phase 7.5:
        - Midnight Rollover: Clear 'today' cache keys at midnight
        - Startup Hydration: Now triggered by CHORES_READY signal (cascade)
        """
        # Startup cascade - wait for chores to be ready before hydrating stats
        self.listen(const.SIGNAL_SUFFIX_CHORES_READY, self._on_chores_ready)

        # Subscribe to point change events
        self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)

        # Subscribe to chore events
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_AUTO_APPROVED, self._on_chore_approved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_COMPLETED, self._on_chore_completed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_CLAIMED, self._on_chore_claimed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DISAPPROVED, self._on_chore_disapproved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_OVERDUE, self._on_chore_overdue)

        # Quiet transitions - state changes without bucket writes (snapshot only)
        self.listen(const.SIGNAL_SUFFIX_CHORE_STATUS_RESET, self._on_chore_status_reset)
        self.listen(const.SIGNAL_SUFFIX_CHORE_UNDONE, self._on_chore_undone)

        # Subscribe to reward approval events
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._on_reward_approved)

        # Midnight rollover - listen to SystemManager's signal (Timer Owner pattern)
        # Clears 'today' cache keys at midnight so sensors show 0 immediately
        self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)

        # Data reset completion signals - invalidate caches when data is reset
        # Each domain manager emits completion signal after reset; we listen to all
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_POINTS_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_BADGE_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHALLENGE_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_REWARD_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_PENALTY_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_BONUS_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )

        # Note: Startup hydration is now triggered by CHORES_READY signal (cascade)
        # See _on_chores_ready() handler below

        const.LOGGER.debug("StatisticsManager: Event subscriptions initialized")

    @callback
    def _on_midnight_rollover(self, payload: dict[str, Any]) -> None:
        """Handle midnight rollover - invalidate all caches.

        At midnight, all 'today' values become stale. Rather than surgically
        removing only PRES_*_TODAY keys, we invalidate the entire cache.
        Lazy hydration will rebuild on next get_stats() call.

        Args:
            payload: Event data (unused)
        """
        const.LOGGER.info("StatisticsManager: Midnight rollover - clearing cache")
        self.invalidate_cache()

    @callback
    def _on_data_reset_complete(self, payload: dict[str, Any]) -> None:
        """Handle data reset completion - invalidate affected caches.

        When any domain manager completes a data reset operation, we need to
        invalidate statistics caches so derived values are recalculated from
        the updated source data.

        Payload format (standard across all *_DATA_RESET_COMPLETE signals):
            scope: "global" | "kid" | "item_type" | "item"
            kid_id: str | None - specific kid for kid scope
            item_id: str | None - specific item for item scope

        Args:
            payload: Event data with scope, kid_id, item_id
        """
        scope = payload.get("scope", "global")
        kid_id = payload.get("kid_id")

        const.LOGGER.debug(
            "StatisticsManager: Data reset complete - scope=%s, kid_id=%s",
            scope,
            kid_id,
        )

        if scope in {"global", "item_type"}:
            # Full reset - invalidate all caches
            self.invalidate_cache()
        elif scope == "kid" and kid_id:
            # Kid-specific reset - only invalidate that kid's cache
            self.invalidate_cache(kid_id)
        elif scope == "item":
            # Item-specific reset - may affect stats, invalidate all for safety
            if kid_id:
                self.invalidate_cache(kid_id)
            else:
                self.invalidate_cache()

    async def _on_chores_ready(self, payload: dict[str, Any]) -> None:
        """Handle startup cascade - hydrate stats after chores are ready.

        Cascade Position: CHORES_READY → StatisticsManager → STATS_READY

        Hydrates the statistics cache for all kids, then signals downstream
        managers (GamificationManager) to continue their initialization.

        Args:
            payload: Event data (unused)
        """
        const.LOGGER.debug(
            "StatisticsManager: Processing CHORES_READY - hydrating cache"
        )

        # Phase 7.5.7: Startup hydration
        # Build cache for all existing kids so sensors have data immediately
        await self._hydrate_cache_all_kids()

        # Signal cascade continues
        self.emit(const.SIGNAL_SUFFIX_STATS_READY)

    def _get_kid(self, kid_id: str) -> dict[str, Any] | None:
        """Get kid data by ID.

        Returns dict[str, Any] instead of KidData because StatisticsManager
        accesses dynamic keys like 'point_data' that aren't in the TypedDict.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            Kid data dict or None if not found
        """
        return self._coordinator.kids_data.get(kid_id)  # type: ignore[return-value]

    # NOTE: _recalculate_point_stats() DELETED in Phase 7G.1
    # All point stats now live in point_data.periods - no separate aggregation needed

    # =========================================================================
    # Event Handlers
    # =========================================================================

    @callback
    def _on_points_changed(self, payload: dict[str, Any]) -> None:
        """Handle POINTS_CHANGED event - update point statistics.

        This is called whenever EconomyManager.deposit() or .withdraw() is invoked.
        Updates period-based point_data (daily/weekly/monthly/yearly/all_time):
        - points_earned (positive deltas)
        - points_spent (negative deltas)
        - by_source breakdown
        - highest_balance (all_time only)

        Phase 7G.1 Architecture: All point stats live in point_data.periods.
        No separate point_stats dict - data is single source of truth.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - old_balance: Balance before transaction
                - new_balance: Balance after transaction
                - delta: The point change (positive or negative)
                - source: Transaction source (POINTS_SOURCE_*)
                - reference_id: Optional related entity ID
        """
        # Extract payload values
        kid_id = payload.get("kid_id", "")
        old_balance = payload.get("old_balance", 0.0)  # noqa: F841 - future use
        new_balance = payload.get("new_balance", 0.0)
        delta = payload.get("delta", 0.0)
        source = payload.get("source", "")

        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_points_changed: Kid '%s' not found",
                kid_id,
            )
            return

        # Phase 3B Tenant Rule: Guard against missing point_data
        # EconomyManager (Landlord) creates point_data on-demand before emitting POINTS_CHANGED
        point_data: dict[str, Any] | None = kid_info.get(const.DATA_KID_POINT_DATA)
        if point_data is None:
            const.LOGGER.warning(
                "StatisticsManager._on_points_changed: point_data missing for kid '%s' - "
                "skipping (EconomyManager should have created it before emitting signal)",
                kid_id,
            )
            return

        # === 1) Record earned/spent to period buckets ===
        periods_data: dict[str, Any] = point_data.setdefault(
            const.DATA_KID_POINT_DATA_PERIODS, {}
        )

        now_local = dt_now_local()

        # Determine earned vs spent based on delta sign
        # Positive delta → points_earned, Negative delta → points_spent
        if delta > 0:
            increment_key = const.DATA_KID_POINT_DATA_PERIOD_POINTS_EARNED
        else:
            increment_key = const.DATA_KID_POINT_DATA_PERIOD_POINTS_SPENT

        # Record earned OR spent using StatisticsEngine (handles daily/weekly/monthly/yearly)
        # NOTE: all_time is handled manually below due to nested bucket structure (all_time.all_time)
        self._stats_engine.record_transaction(
            periods_data,
            {increment_key: delta},
            reference_date=now_local,
            include_all_time=False,
        )

        # === 2) Record by_source to period buckets (nested structure) ===
        period_ids = self._stats_engine.get_period_keys(now_local)
        for period_key, period_id in period_ids.items():
            bucket: dict[str, Any] = periods_data.setdefault(period_key, {})
            entry: dict[str, Any] = bucket.setdefault(period_id, {})
            if (
                const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE not in entry
                or not isinstance(
                    entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE], dict
                )
            ):
                entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE] = {}
            entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE].setdefault(source, 0.0)
            entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] = round(
                entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] + delta,
                const.DATA_FLOAT_PRECISION,
            )

        # === 3) Record by_source and highest_balance to all_time bucket ===
        all_time_bucket: dict[str, Any] = periods_data.setdefault(
            const.DATA_KID_POINT_DATA_PERIODS_ALL_TIME, {}
        )
        all_time_entry: dict[str, Any] = all_time_bucket.setdefault(
            const.PERIOD_ALL_TIME, {}
        )

        # by_source for all_time
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
            all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE][source] + delta,
            const.DATA_FLOAT_PRECISION,
        )

        # points_earned/spent tracking (all_time only - nested bucket requires manual handling)
        # record_transaction() writes to periods["all_time"] directly, but we need
        # periods["all_time"]["all_time"] for consistency with other period structures
        if delta > 0:
            current_earned = all_time_entry.get(
                const.DATA_KID_POINT_DATA_PERIOD_POINTS_EARNED, 0.0
            )
            all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_EARNED] = round(
                current_earned + delta, const.DATA_FLOAT_PRECISION
            )
        else:
            current_spent = all_time_entry.get(
                const.DATA_KID_POINT_DATA_PERIOD_POINTS_SPENT, 0.0
            )
            all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_POINTS_SPENT] = round(
                current_spent + delta, const.DATA_FLOAT_PRECISION
            )

        # highest_balance tracking (all_time only)
        highest = all_time_entry.get(
            const.DATA_KID_POINT_DATA_PERIOD_HIGHEST_BALANCE, 0.0
        )
        all_time_entry[const.DATA_KID_POINT_DATA_PERIOD_HIGHEST_BALANCE] = max(
            highest, new_balance
        )

        # === 4) Prune old period data ===
        self._stats_engine.prune_history(periods_data, self.get_retention_config())

        # === 5) Persist changes ===
        self._coordinator._persist()

        # === 6) Refresh presentation cache (BEFORE notifying sensors) ===
        # Must refresh cache synchronously before async_set_updated_data() triggers sensor reads
        self._refresh_point_cache(kid_id)

        # === 7) Notify Home Assistant of data update ===
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_points_changed: kid=%s, delta=%.2f, source=%s",
            kid_id,
            delta,
            source,
        )

    # ────────────────────────────────────────────────────────────────
    # Chore Transaction Helper
    # ────────────────────────────────────────────────────────────────

    def _record_chore_transaction(
        self,
        kid_id: str,
        chore_id: str,
        increments: dict[str, int | float],
        effective_date: str | None = None,
        persist: bool = True,
    ) -> bool:
        """Record a chore transaction to period buckets.

        Common helper for CHORE_APPROVED, CHORE_CLAIMED, CHORE_DISAPPROVED,
        CHORE_OVERDUE, and CHORE_COMPLETED signals. Handles:
        - Getting/creating kid_chore_data.periods structure
        - Recording increments to period buckets via StatisticsEngine
        - Pruning old period data
        - Optionally persisting and refreshing cache

        Args:
            kid_id: The kid's internal ID.
            chore_id: The chore's internal ID.
            increments: Dict of metric keys to increment values.
            effective_date: ISO timestamp for parent-lag-proof bucketing.
                           If None, uses current time.
            persist: If True, calls _persist() and _refresh_chore_cache().
                    Set to False when batching multiple kids.

        Returns:
            True if successful, False if kid not found.
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: Kid '%s' not found",
                kid_id,
            )
            return False

        # Phase 3B Tenant Rule: Guard against missing landlord-owned structures
        # ChoreManager (Landlord) creates chore_data on-demand via _get_kid_chore_data()
        chore_data: dict[str, Any] | None = kid_info.get(const.DATA_KID_CHORE_DATA)
        if chore_data is None:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: chore_data missing for kid '%s' - "
                "skipping (ChoreManager should have created it before emitting signal)",
                kid_id,
            )
            return False

        # Phase 3B Tenant Rule: Guard against missing per-chore entry
        # ChoreManager creates per-chore entries on-demand via _get_kid_chore_data()
        kid_chore_data: dict[str, Any] | None = chore_data.get(chore_id)
        if kid_chore_data is None:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: chore_data entry missing for "
                "kid '%s', chore '%s' - skipping (ChoreManager should create on assignment)",
                kid_id,
                chore_id,
            )
            return False

        # Get or create periods (StatisticsManager owns these sub-keys within chore_data entry)
        periods = kid_chore_data.setdefault(
            const.DATA_KID_CHORE_DATA_PERIODS,
            {
                const.DATA_KID_CHORE_DATA_PERIODS_DAILY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_YEARLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME: {},
            },
        )

        # Use effective_date for parent-lag-proof bucketing
        # dt_parse defaults to HELPER_RETURN_DATETIME, returns datetime | None
        bucket_dt = (
            cast("datetime | None", dt_parse(effective_date))
            if effective_date
            else None
        )

        # Record transaction to period buckets
        # NOTE: Do NOT pass period_mapping as period_key_mapping!
        # period_mapping contains date strings like '2026-01-31'
        # period_key_mapping expects structure keys like DATA_KID_CHORE_DATA_PERIODS_DAILY
        # Engine will use default mapping which is correct for chore periods
        self._stats_engine.record_transaction(
            periods,
            increments,
            reference_date=bucket_dt,
        )

        # Prune old period data
        self._stats_engine.prune_history(periods, self.get_retention_config())

        # Optionally persist and refresh cache
        if persist:
            self._coordinator._persist()
            self._refresh_chore_cache(kid_id)

        return True

    # ────────────────────────────────────────────────────────────────
    # Chore Event Listeners
    # ────────────────────────────────────────────────────────────────

    @callback
    def _on_chore_approved(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_APPROVED event - update approval statistics.

        Records approved count and points to period buckets.
        Note: Completion and streaks are tracked separately via CHORE_COMPLETED signal.
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")
        points_awarded = payload.get("points_awarded", 0.0)
        effective_date = payload.get("effective_date")

        increments: dict[str, int | float] = {
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 1,
        }
        if points_awarded > 0:
            increments[const.DATA_KID_CHORE_DATA_PERIOD_POINTS] = points_awarded

        if self._record_chore_transaction(kid_id, chore_id, increments, effective_date):
            const.LOGGER.debug(
                "StatisticsManager._on_chore_approved: kid=%s, chore=%s, points=%.2f",
                kid_id,
                chore_id,
                points_awarded,
            )

    @callback
    def _on_chore_completed(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_COMPLETED event - update completion and streak statistics.

        Called when completion criteria is satisfied:
        - INDEPENDENT: Immediately on approval (one kid)
        - SHARED_FIRST: First approving kid only
        - SHARED (all): All kids when last is approved

        Records:
        - Completion count (always)
        - Streak tally (if provided, max 1 per day per kid)
        - Longest streak in all_time bucket
        """
        chore_id = payload.get("chore_id", "")
        kid_ids = payload.get("kid_ids", [])
        effective_date = payload.get("effective_date")
        streak_tallies = payload.get("streak_tallies", {})  # dict: kid_id -> streak

        if not kid_ids:
            const.LOGGER.warning(
                "StatisticsManager._on_chore_completed: No kid_ids for chore=%s",
                chore_id,
            )
            return

        # Record completion for each kid (batch mode - persist once at end)
        for kid_id in kid_ids:
            # Build increments for this kid
            increments: dict[str, int | float] = {
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED: 1,
            }

            # Handle streak_tally with max-1-per-day enforcement
            streak_tally = streak_tallies.get(kid_id)
            if streak_tally is not None:
                # Get periods structure to check today's bucket
                kid_info = self._get_kid(kid_id)
                if kid_info:
                    chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
                    kid_chore_data = chore_data.get(chore_id, {})
                    periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
                    daily_buckets = periods.get(
                        const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                    )

                    # Get today's bucket key
                    today_key = self._stats_engine.get_period_keys().get("daily")

                    # Check if already set today (max 1 update per day)
                    should_write_streak = True
                    if today_key and today_key in daily_buckets:
                        if (
                            const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY
                            in daily_buckets[today_key]
                        ):
                            should_write_streak = False
                            const.LOGGER.debug(
                                "StatisticsManager._on_chore_completed: SKIP streak_tally "
                                "(already set today) kid=%s, chore=%s, date=%s",
                                kid_id,
                                chore_id,
                                today_key,
                            )

                    # Add to increments if not already set today
                    if should_write_streak:
                        increments[const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY] = (
                            streak_tally
                        )

                        # Update longest_streak in all_time bucket if new high
                        all_time = periods.get(
                            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
                        )
                        current_longest = all_time.get(
                            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                        )
                        if streak_tally > current_longest:
                            all_time[
                                const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
                            ] = streak_tally

            if self._record_chore_transaction(
                kid_id,
                chore_id,
                increments,
                effective_date,
                persist=False,  # Batch: persist once after loop
            ):
                self._refresh_chore_cache(kid_id)

        # Persist once after all kids updated
        self._coordinator._persist()

        const.LOGGER.debug(
            "StatisticsManager._on_chore_completed: chore=%s, kids=%s",
            chore_id,
            kid_ids,
        )

    @callback
    def _on_chore_claimed(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_CLAIMED event - record claim count to period buckets."""
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if self._record_chore_transaction(
            kid_id, chore_id, {const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 1}
        ):
            const.LOGGER.debug(
                "StatisticsManager._on_chore_claimed: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    @callback
    def _on_chore_disapproved(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DISAPPROVED event - record disapproval to period buckets."""
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if self._record_chore_transaction(
            kid_id, chore_id, {const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 1}
        ):
            const.LOGGER.debug(
                "StatisticsManager._on_chore_disapproved: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    @callback
    def _on_chore_overdue(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_OVERDUE event - record overdue to period buckets.

        Enforces max 1 overdue per day by checking today's bucket value before
        incrementing. This ensures daily buckets never exceed 1 for overdue count.
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        # Get periods structure to check today's bucket
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
        kid_chore_data = chore_data.get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        daily_buckets = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})

        # Get today's bucket key
        today_key = self._stats_engine.get_period_keys().get("daily")

        # Check if today's bucket already has overdue >= 1 (max 1 per day rule)
        if today_key and today_key in daily_buckets:
            existing_overdue = daily_buckets[today_key].get(
                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0
            )
            if existing_overdue >= 1:
                const.LOGGER.debug(
                    "StatisticsManager._on_chore_overdue: SKIP (already at max 1) "
                    "kid=%s, chore=%s, date=%s, current=%d",
                    kid_id,
                    chore_id,
                    today_key,
                    existing_overdue,
                )
                return

        # Proceed with increment (will create bucket if needed)
        if self._record_chore_transaction(
            kid_id, chore_id, {const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 1}
        ):
            const.LOGGER.debug(
                "StatisticsManager._on_chore_overdue: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    @callback
    def _on_chore_status_reset(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_STATUS_RESET event - refresh snapshot counts.

        STATUS_RESET is a quiet transition (no bucket writes needed).
        We only need to refresh the chore cache to update current_* counts.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - chore_id: The chore's internal ID
                - chore_name: The chore's display name
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if kid_id:
            self._schedule_cache_refresh(kid_id, "chore")
            const.LOGGER.debug(
                "StatisticsManager._on_chore_status_reset: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    @callback
    def _on_chore_undone(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_UNDONE event - refresh snapshot counts.

        UNDONE is a quiet transition (no bucket writes needed).
        We only need to refresh the chore cache to update current_* counts.

        Note: Point reclamation is handled by EconomyManager via
        POINTS_CHANGED signal; this handler only refreshes counts.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - chore_id: The chore's internal ID
                - points_to_reclaim: Points that were reclaimed
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if kid_id:
            self._schedule_cache_refresh(kid_id, "chore")
            const.LOGGER.debug(
                "StatisticsManager._on_chore_undone: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    @callback
    def _on_reward_approved(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_APPROVED event - update reward statistics.

        This is called when RewardManager approves a reward redemption.

        Note: Point stats are handled separately by _on_points_changed
        when EconomyManager.withdraw() is called for the reward cost.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - reward_id: The reward's internal ID
                - cost_deducted: Points deducted for reward
                - parent_name: Name of approving parent
        """
        # Extract payload values
        kid_id = payload.get("kid_id", "")
        reward_id = payload.get("reward_id", "")
        cost_deducted = payload.get("cost_deducted", 0.0)

        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_reward_approved: Kid '%s' not found",
                kid_id,
            )
            return

        # The reward_data stats are already handled by RewardManager during approval
        # This handler is for future expansion (e.g., aggregated reward analytics)
        const.LOGGER.debug(
            "StatisticsManager._on_reward_approved: kid=%s, reward=%s, cost=%.2f",
            kid_id,
            reward_id,
            cost_deducted,
        )

    # =========================================================================
    # Query Methods (for future use)
    # =========================================================================

    def get_point_stats_for_kid(self, kid_id: str) -> dict[str, Any]:
        """Get aggregated point statistics for a kid.

        Args:
            kid_id: The kid's internal ID

        Returns:
            Point stats dictionary or empty dict if not found
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return {}
        return kid_info.get(const.DATA_KID_POINT_STATS_LEGACY, {})

    def get_period_stats_for_kid(self, kid_id: str, period_type: str) -> dict[str, Any]:
        """Get period-based statistics for a kid.

        Args:
            kid_id: The kid's internal ID
            period_type: Period type (daily, weekly, monthly, yearly, all_time)

        Returns:
            Period stats dictionary or empty dict if not found
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return {}

        point_data = kid_info.get(const.DATA_KID_POINT_DATA, {})
        periods = point_data.get(const.DATA_KID_POINT_DATA_PERIODS, {})
        return periods.get(period_type, {})

    # =========================================================================
    # Phase 7.5: Presentation Cache Methods
    # =========================================================================

    def get_stats(self, kid_id: str) -> dict[str, Any]:
        """Get presentation statistics for a kid (Phase 7.5 Cache API).

        This is the primary API for sensors and dashboard helpers.
        Returns cached PRES_* values derived from period buckets.
        If cache miss, rebuilds from buckets (lazy hydration).

        Args:
            kid_id: The kid's internal ID

        Returns:
            Dict with PRES_* keys for presentation, or empty dict if kid not found.
        """
        if kid_id not in self._stats_cache:
            # Cache miss - rebuild from buckets
            self._refresh_all_cache(kid_id)

        return self._stats_cache.get(kid_id, {})

    async def _hydrate_cache_all_kids(self) -> None:
        """Hydrate presentation cache for all existing kids at startup (Phase 7.5.7).

        Called during async_setup() to ensure sensors have data immediately.
        Runs synchronously since this is startup-time work.
        """
        kids_data = self._coordinator.kids_data
        kid_count = len(kids_data)

        if kid_count == 0:
            const.LOGGER.debug("StatisticsManager: No kids to hydrate cache for")
            return

        for kid_id in kids_data:
            self._refresh_all_cache(kid_id)

        const.LOGGER.info(
            "StatisticsManager: Hydrated stats cache for %s kids", kid_count
        )

    def _refresh_all_cache(self, kid_id: str) -> None:
        """Refresh all cache domains for a kid.

        Called on cache miss or startup hydration.
        Delegates to domain-specific refresh methods.

        Args:
            kid_id: The kid's internal ID
        """
        self._refresh_point_cache(kid_id)
        self._refresh_chore_cache(kid_id)
        self._refresh_reward_cache(kid_id)

        # Set last updated timestamp
        cache = self._stats_cache.setdefault(kid_id, {})
        cache[const.PRES_KID_LAST_UPDATED] = dt_now_local().isoformat()

    def _refresh_point_cache(self, kid_id: str) -> None:
        """Refresh point statistics cache for a kid.

        Derives temporal point stats from period buckets (point_data.periods).
        Only runs on point-related events.

        Args:
            kid_id: The kid's internal ID
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        cache = self._stats_cache.setdefault(kid_id, {})
        pts_periods = kid_info.get(const.DATA_KID_POINT_DATA, {}).get(
            const.DATA_KID_POINT_DATA_PERIODS, {}
        )

        now_local = dt_now_local()
        today_local_iso = now_local.date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        def get_period_values(
            period_key: str, period_id: str
        ) -> tuple[float, float, float, dict[str, float]]:
            """Extract earned, spent, net, and by_source from a period bucket.

            Phase 7G.1: Now reads earned/spent directly from period entry,
            derives net as (earned + spent). No longer reads points_total.
            """
            period = pts_periods.get(period_key, {})
            entry = period.get(period_id, {})
            by_source = entry.get(const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE, {})

            # Read earned/spent directly from period entry (v44+ structure)
            earned = round(
                entry.get(const.DATA_KID_POINT_DATA_PERIOD_POINTS_EARNED, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            spent = round(
                entry.get(const.DATA_KID_POINT_DATA_PERIOD_POINTS_SPENT, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            # Net is DERIVED (earned + spent, where spent is negative)
            net = round(earned + spent, const.DATA_FLOAT_PRECISION)
            return earned, spent, net, dict(by_source)

        # Daily
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_DATA_PERIODS_DAILY, today_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_TODAY] = earned
        cache[const.PRES_KID_POINTS_SPENT_TODAY] = spent
        cache[const.PRES_KID_POINTS_NET_TODAY] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_TODAY] = by_source

        # Weekly
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_DATA_PERIODS_WEEKLY, week_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_WEEK] = earned
        cache[const.PRES_KID_POINTS_SPENT_WEEK] = spent
        cache[const.PRES_KID_POINTS_NET_WEEK] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_WEEK] = by_source

        # Monthly
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_DATA_PERIODS_MONTHLY, month_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_MONTH] = earned
        cache[const.PRES_KID_POINTS_SPENT_MONTH] = spent
        cache[const.PRES_KID_POINTS_NET_MONTH] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_MONTH] = by_source

        # Yearly
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_DATA_PERIODS_YEARLY, year_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_YEAR] = earned
        cache[const.PRES_KID_POINTS_SPENT_YEAR] = spent
        cache[const.PRES_KID_POINTS_NET_YEAR] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_YEAR] = by_source

        # Averages (derived from period aggregates)
        days_in_week = 7
        days_in_month = 30  # Approximate
        week_earned = cache.get(const.PRES_KID_POINTS_EARNED_WEEK, 0.0)
        month_earned = cache.get(const.PRES_KID_POINTS_EARNED_MONTH, 0.0)
        cache[const.PRES_KID_POINTS_AVG_PER_DAY_WEEK] = round(
            week_earned / days_in_week if week_earned else 0.0,
            const.DATA_FLOAT_PRECISION,
        )
        cache[const.PRES_KID_POINTS_AVG_PER_DAY_MONTH] = round(
            month_earned / days_in_month if month_earned else 0.0,
            const.DATA_FLOAT_PRECISION,
        )

    def _refresh_chore_cache(self, kid_id: str) -> None:
        """Refresh chore statistics cache for a kid.

        Derives temporal chore stats from chore_data periods and extracts
        snapshot counts (current_overdue, current_claimed, etc.) from Engine.
        Only runs on chore-related events.

        Args:
            kid_id: The kid's internal ID
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        cache = self._stats_cache.setdefault(kid_id, {})

        # === Snapshot counts from Engine (single source of truth) ===
        # Engine iterates all chores to count current states
        full_stats = self.coordinator.stats.generate_chore_stats(
            kid_info, self.coordinator.chores_data
        )
        cache[const.PRES_KID_CHORES_CURRENT_OVERDUE] = full_stats.get(
            const.DATA_KID_CHORE_STATS_CURRENT_OVERDUE, 0
        )
        cache[const.PRES_KID_CHORES_CURRENT_CLAIMED] = full_stats.get(
            const.DATA_KID_CHORE_STATS_CURRENT_CLAIMED, 0
        )
        cache[const.PRES_KID_CHORES_CURRENT_APPROVED] = full_stats.get(
            const.DATA_KID_CHORE_STATS_CURRENT_APPROVED, 0
        )
        cache[const.PRES_KID_CHORES_CURRENT_DUE_TODAY] = full_stats.get(
            const.DATA_KID_CHORE_STATS_CURRENT_DUE_TODAY, 0
        )

        # === Temporal aggregates from period buckets ===
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        now_local = dt_now_local()
        today_local_iso = now_local.date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        # Aggregate chore stats from all chore_data entries
        approved_today = 0
        approved_week = 0
        approved_month = 0
        approved_year = 0
        completed_today = 0
        completed_week = 0
        completed_month = 0
        completed_year = 0
        claimed_today = 0
        claimed_week = 0
        claimed_month = 0
        claimed_year = 0
        points_today = 0.0
        points_week = 0.0
        points_month = 0.0
        points_year = 0.0

        for _chore_id, chore_info in chore_data.items():
            periods = chore_info.get(const.DATA_KID_CHORE_DATA_PERIODS, {})

            # Daily
            daily_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})
            today_entry = daily_periods.get(today_local_iso, {})
            approved_today += today_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_today += today_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            claimed_today += today_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            points_today += today_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)

            # Weekly
            weekly_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY, {})
            week_entry = weekly_periods.get(week_local_iso, {})
            approved_week += week_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_week += week_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            claimed_week += week_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0)
            points_week += week_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)

            # Monthly
            monthly_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, {})
            month_entry = monthly_periods.get(month_local_iso, {})
            approved_month += month_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_month += month_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            claimed_month += month_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            points_month += month_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)

            # Yearly
            yearly_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_YEARLY, {})
            year_entry = yearly_periods.get(year_local_iso, {})
            approved_year += year_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_year += year_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            claimed_year += year_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0)
            points_year += year_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)

        # Aggregate all_time stats from all chore period buckets
        approved_all_time = 0
        completed_all_time = 0
        claimed_all_time = 0
        points_all_time = 0.0

        for _chore_id, chore_info in chore_data.items():
            periods = chore_info.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
            all_time_periods = periods.get(
                const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
            )

            # All-time bucket stores cumulative totals
            approved_all_time += all_time_periods.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_all_time += all_time_periods.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            claimed_all_time += all_time_periods.get(
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            points_all_time += all_time_periods.get(
                const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0
            )

        # Store in cache
        cache[const.PRES_KID_CHORES_APPROVED_TODAY] = approved_today
        cache[const.PRES_KID_CHORES_APPROVED_WEEK] = approved_week
        cache[const.PRES_KID_CHORES_APPROVED_MONTH] = approved_month
        cache[const.PRES_KID_CHORES_APPROVED_YEAR] = approved_year
        cache[const.PRES_KID_CHORES_APPROVED_ALL_TIME] = approved_all_time
        cache[const.PRES_KID_CHORES_COMPLETED_TODAY] = completed_today
        cache[const.PRES_KID_CHORES_COMPLETED_WEEK] = completed_week
        cache[const.PRES_KID_CHORES_COMPLETED_MONTH] = completed_month
        cache[const.PRES_KID_CHORES_COMPLETED_YEAR] = completed_year
        cache[const.PRES_KID_CHORES_COMPLETED_ALL_TIME] = completed_all_time
        cache[const.PRES_KID_CHORES_CLAIMED_TODAY] = claimed_today
        cache[const.PRES_KID_CHORES_CLAIMED_WEEK] = claimed_week
        cache[const.PRES_KID_CHORES_CLAIMED_MONTH] = claimed_month
        cache[const.PRES_KID_CHORES_CLAIMED_YEAR] = claimed_year
        cache[const.PRES_KID_CHORES_CLAIMED_ALL_TIME] = claimed_all_time
        cache[const.PRES_KID_CHORES_POINTS_TODAY] = round(
            points_today, const.DATA_FLOAT_PRECISION
        )
        cache[const.PRES_KID_CHORES_POINTS_WEEK] = round(
            points_week, const.DATA_FLOAT_PRECISION
        )
        cache[const.PRES_KID_CHORES_POINTS_MONTH] = round(
            points_month, const.DATA_FLOAT_PRECISION
        )
        cache[const.PRES_KID_CHORES_POINTS_YEAR] = round(
            points_year, const.DATA_FLOAT_PRECISION
        )
        cache[const.PRES_KID_CHORES_POINTS_ALL_TIME] = round(
            points_all_time, const.DATA_FLOAT_PRECISION
        )

    def _refresh_reward_cache(self, kid_id: str) -> None:
        """Refresh reward statistics cache for a kid.

        Derives temporal reward stats from reward_data periods.
        Only runs on reward-related events.

        Args:
            kid_id: The kid's internal ID
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        cache = self._stats_cache.setdefault(kid_id, {})
        reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})

        now_local = dt_now_local()
        today_local_iso = now_local.date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")

        # Aggregate reward stats from all reward_data entries
        claimed_today = 0
        claimed_week = 0
        claimed_month = 0
        approved_today = 0
        approved_week = 0
        approved_month = 0

        for _reward_id, reward_info in reward_data.items():
            periods = reward_info.get(const.DATA_KID_REWARD_DATA_PERIODS, {})

            # Daily
            daily_periods = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_DAILY, {})
            today_entry = daily_periods.get(today_local_iso, {})
            claimed_today += today_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0
            )
            approved_today += today_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )

            # Weekly
            weekly_periods = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY, {})
            week_entry = weekly_periods.get(week_local_iso, {})
            claimed_week += week_entry.get(const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0)
            approved_week += week_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )

            # Monthly
            monthly_periods = periods.get(
                const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY, {}
            )
            month_entry = monthly_periods.get(month_local_iso, {})
            claimed_month += month_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0
            )
            approved_month += month_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )

        # Store in cache
        cache[const.PRES_KID_REWARDS_CLAIMED_TODAY] = claimed_today
        cache[const.PRES_KID_REWARDS_CLAIMED_WEEK] = claimed_week
        cache[const.PRES_KID_REWARDS_CLAIMED_MONTH] = claimed_month
        cache[const.PRES_KID_REWARDS_APPROVED_TODAY] = approved_today
        cache[const.PRES_KID_REWARDS_APPROVED_WEEK] = approved_week
        cache[const.PRES_KID_REWARDS_APPROVED_MONTH] = approved_month

    def invalidate_cache(self, kid_id: str | None = None) -> None:
        """Invalidate presentation cache (Phase 7.5).

        Call when kid is deleted or on midnight rollover.

        Args:
            kid_id: Specific kid to invalidate, or None to clear all.
        """
        if kid_id is None:
            self._stats_cache.clear()
            # Cancel all pending timers
            for timer in self._cache_timers.values():
                timer.cancel()
            self._cache_timers.clear()
            const.LOGGER.debug("StatisticsManager: Cleared all cache entries")
        elif kid_id in self._stats_cache:
            del self._stats_cache[kid_id]
            # Cancel any pending timer for this kid
            if kid_id in self._cache_timers:
                self._cache_timers[kid_id].cancel()
                del self._cache_timers[kid_id]
            const.LOGGER.debug(
                "StatisticsManager: Invalidated cache for kid %s", kid_id
            )

    def _schedule_cache_refresh(self, kid_id: str, domain: str = "all") -> None:
        """Schedule a debounced cache refresh for a kid (Phase 7.5).

        Uses a 500ms debounce per kid to prevent thundering herd on rapid events.
        If a refresh is already scheduled, it's cancelled and rescheduled.

        Args:
            kid_id: The kid's internal ID
            domain: Which domain to refresh: "point", "chore", "reward", or "all"
        """
        # Cancel existing timer if present
        if kid_id in self._cache_timers:
            self._cache_timers[kid_id].cancel()

        # Create the refresh callback based on domain
        @callback
        def _do_refresh() -> None:
            """Execute the cache refresh after debounce delay."""
            # Remove timer reference
            self._cache_timers.pop(kid_id, None)

            # Refresh based on domain
            if domain == "point":
                self._refresh_point_cache(kid_id)
            elif domain == "chore":
                self._refresh_chore_cache(kid_id)
            elif domain == "reward":
                self._refresh_reward_cache(kid_id)
            else:
                self._refresh_all_cache(kid_id)

            const.LOGGER.debug(
                "StatisticsManager: Refreshed %s cache for kid %s (debounced)",
                domain,
                kid_id,
            )

        # Schedule the refresh
        self._cache_timers[kid_id] = self.hass.loop.call_later(
            CACHE_REFRESH_DEBOUNCE_SECONDS, _do_refresh
        )
