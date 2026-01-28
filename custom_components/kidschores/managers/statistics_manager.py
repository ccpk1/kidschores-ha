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

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback

from custom_components.kidschores import const
from custom_components.kidschores.engines.statistics_engine import (
    filter_persistent_stats,
)
from custom_components.kidschores.managers.base_manager import BaseManager
from custom_components.kidschores.utils.dt_utils import dt_now_local

if TYPE_CHECKING:
    from asyncio import TimerHandle

    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.engines.statistics_engine import StatisticsEngine


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
        - POINTS_CHANGED: Track point transactions
        - CHORE_APPROVED: Track chore completions
        - REWARD_APPROVED: Track reward redemptions

        Phase 7.5:
        - Midnight Rollover: Clear 'today' cache keys at midnight
        - Startup Hydration: Build cache for all existing kids
        """
        # Subscribe to point change events
        self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)

        # Subscribe to chore approval events
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)

        # Subscribe to reward approval events
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._on_reward_approved)

        # Phase 7.5.6: Midnight rollover listener
        # Clear 'today' cache keys at midnight so sensors show 0 immediately
        from homeassistant.helpers.event import async_track_time_change

        @callback
        def _on_midnight_rollover(now: Any) -> None:
            """Handle midnight rollover - invalidate all caches.

            At midnight, all 'today' values become stale. Rather than surgically
            removing only PRES_*_TODAY keys, we invalidate the entire cache.
            Lazy hydration will rebuild on next get_stats() call.
            """
            const.LOGGER.info("StatisticsManager: Midnight rollover - clearing cache")
            self.invalidate_cache()

        # Register the midnight listener (hour=0, minute=0, second=1 to avoid race)
        self.coordinator.config_entry.async_on_unload(
            async_track_time_change(
                self.hass, _on_midnight_rollover, hour=0, minute=0, second=1
            )
        )

        # Phase 7.5.7: Startup hydration
        # Build cache for all existing kids so sensors have data immediately
        await self._hydrate_cache_all_kids()

        const.LOGGER.debug("StatisticsManager: Event subscriptions initialized")

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

    def _recalculate_point_stats(self, kid_info: dict[str, Any]) -> None:
        """Recalculate aggregated point stats for a kid.

        Aggregates all kid_point_stats by delegating to the StatisticsEngine,
        which owns the period data structure knowledge.

        Note: Only persistent stats (all_time, highest, etc.) are written to
        storage. Temporal stats (today/week/month) live in the presentation
        cache (Phase 7.5 Architecture).

        Args:
            kid_info: The kid data dictionary to update.
        """
        stats = self._stats_engine.generate_point_stats(kid_info)
        # Only persist non-temporal stats (Phase 7.5: temporal lives in cache)
        kid_info[const.DATA_KID_POINT_STATS] = filter_persistent_stats(stats)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    @callback
    def _on_points_changed(self, payload: dict[str, Any]) -> None:
        """Handle POINTS_CHANGED event - update point statistics.

        This is called whenever EconomyManager.deposit() or .withdraw() is invoked.
        Updates:
        - Period-based point_data (daily/weekly/monthly/yearly)
        - All-time point_stats
        - Cumulative badge progress (for positive deltas)
        - Highest balance tracking

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

        # 1) Update all-time stats (incrementally)
        point_stats: dict[str, Any] = kid_info.setdefault(
            const.DATA_KID_POINT_STATS, {}
        )
        point_stats.setdefault(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_SPENT_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_NET_ALL_TIME, 0.0)
        point_stats.setdefault(const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME, {})
        point_stats.setdefault(const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0)

        if delta > 0:
            earned = point_stats.get(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0)
            point_stats[const.DATA_KID_POINT_STATS_EARNED_ALL_TIME] = round(
                earned + delta, const.DATA_FLOAT_PRECISION
            )
        elif delta < 0:
            spent = point_stats.get(const.DATA_KID_POINT_STATS_SPENT_ALL_TIME, 0.0)
            point_stats[const.DATA_KID_POINT_STATS_SPENT_ALL_TIME] = round(
                spent + delta, const.DATA_FLOAT_PRECISION
            )
        net = point_stats.get(const.DATA_KID_POINT_STATS_NET_ALL_TIME, 0.0)
        point_stats[const.DATA_KID_POINT_STATS_NET_ALL_TIME] = round(
            net + delta, const.DATA_FLOAT_PRECISION
        )

        # 3) Record in period-based point_data
        periods_data: dict[str, Any] = kid_info.setdefault(
            const.DATA_KID_POINT_DATA, {}
        ).setdefault(const.DATA_KID_POINT_DATA_PERIODS, {})

        now_local = dt_now_local()
        period_mapping = self._stats_engine.get_period_keys(now_local)

        # Record points_total using StatisticsEngine
        self._stats_engine.record_transaction(
            periods_data,
            {const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL: delta},
            period_key_mapping=period_mapping,
        )

        # Handle by_source tracking (nested structure not handled by engine)
        for period_key, period_id in period_mapping.items():
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

        # Also record by_source for all_time bucket
        all_time_bucket: dict[str, Any] = periods_data.setdefault(
            const.DATA_KID_POINT_DATA_PERIODS_ALL_TIME, {}
        )
        all_time_entry: dict[str, Any] = all_time_bucket.setdefault(
            const.PERIOD_ALL_TIME, {}
        )
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

        # 4) Recalculate aggregated stats (generates period summaries)
        self._recalculate_point_stats(kid_info)

        # 5) Update all-time by-source AFTER recalculate (to avoid being overwritten)
        by_source_all_time: dict[str, float] = point_stats.get(
            const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME, {}
        )
        by_source_all_time.setdefault(source, 0.0)
        by_source_all_time[source] = round(
            by_source_all_time[source] + delta, const.DATA_FLOAT_PRECISION
        )

        # Update highest balance
        highest = point_stats.get(const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0)
        point_stats[const.DATA_KID_POINT_STATS_HIGHEST_BALANCE] = max(
            highest, new_balance
        )

        # 6) Prune old period data
        self._stats_engine.prune_history(periods_data, self.get_retention_config())

        # 7) Persist changes
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_points_changed: kid=%s, delta=%.2f, source=%s",
            kid_id,
            delta,
            source,
        )

    @callback
    def _on_chore_approved(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_APPROVED event - update chore statistics.

        This is called when ChoreManager approves a chore claim.
        Updates period-based chore completion stats.

        Note: Point stats are handled separately by _on_points_changed
        when EconomyManager.deposit() is called for the chore points.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - chore_id: The chore's internal ID
                - points_awarded: Points given for completion
                - parent_name: Name of approving parent
        """
        # Extract payload values
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")
        points_awarded = payload.get("points_awarded", 0.0)

        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_chore_approved: Kid '%s' not found",
                kid_id,
            )
            return

        # The chore_data stats are already handled by ChoreManager during approval
        # This handler is for future expansion (e.g., aggregated chore analytics)
        const.LOGGER.debug(
            "StatisticsManager._on_chore_approved: kid=%s, chore=%s, points=%.2f",
            kid_id,
            chore_id,
            points_awarded,
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
        return kid_info.get(const.DATA_KID_POINT_STATS, {})

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
            """Extract earned, spent, net, and by_source from a period bucket."""
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

        Derives temporal chore stats from chore_data periods.
        Only runs on chore-related events.

        Args:
            kid_id: The kid's internal ID
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        cache = self._stats_cache.setdefault(kid_id, {})
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
            claimed_week += week_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0)
            points_week += week_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)

            # Monthly
            monthly_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, {})
            month_entry = monthly_periods.get(month_local_iso, {})
            approved_month += month_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
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
            claimed_year += year_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0)
            points_year += year_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)

        # Store in cache
        cache[const.PRES_KID_CHORES_APPROVED_TODAY] = approved_today
        cache[const.PRES_KID_CHORES_APPROVED_WEEK] = approved_week
        cache[const.PRES_KID_CHORES_APPROVED_MONTH] = approved_month
        cache[const.PRES_KID_CHORES_APPROVED_YEAR] = approved_year
        cache[const.PRES_KID_CHORES_CLAIMED_TODAY] = claimed_today
        cache[const.PRES_KID_CHORES_CLAIMED_WEEK] = claimed_week
        cache[const.PRES_KID_CHORES_CLAIMED_MONTH] = claimed_month
        cache[const.PRES_KID_CHORES_CLAIMED_YEAR] = claimed_year
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
