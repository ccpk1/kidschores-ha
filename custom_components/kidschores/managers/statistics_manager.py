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
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback

from custom_components.kidschores import const
from custom_components.kidschores.managers.base_manager import BaseManager
from custom_components.kidschores.utils.dt_utils import dt_now_local

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.engines.statistics_engine import StatisticsEngine


__all__ = ["StatisticsManager"]


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

    @property
    def _stats_engine(self) -> StatisticsEngine:
        """Get the StatisticsEngine from coordinator."""
        return self._coordinator.stats

    async def async_setup(self) -> None:
        """Set up event subscriptions for statistics tracking.

        Subscribe to:
        - POINTS_CHANGED: Track point transactions
        - CHORE_APPROVED: Track chore completions
        - REWARD_APPROVED: Track reward redemptions
        """
        # Subscribe to point change events
        self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)

        # Subscribe to chore approval events
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)

        # Subscribe to reward approval events
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._on_reward_approved)

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

        Args:
            kid_info: The kid data dictionary to update.
        """
        stats = self._stats_engine.generate_point_stats(kid_info)
        kid_info[const.DATA_KID_POINT_STATS] = stats

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
        self._stats_engine.prune_history(
            periods_data, self._coordinator._get_retention_config()
        )

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
