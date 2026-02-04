"""Statistics Engine - Unified time-series tracking for period-based data.

This engine centralizes all period-based statistics tracking across KidsChores:
- Chore completions (claimed, approved, rejected, points)
- Point transactions (earned, spent, bonuses, penalties)
- Reward claims (claimed, redeemed)
- Badge earnings (daily/weekly/monthly/yearly counts)

Design Principles:
    - Stateless: No coordinator reference, operates on passed data structures
    - Consistent: Single source of truth for period key generation
    - Efficient: Batch updates with optional auto-pruning
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, cast

from .. import const
from ..utils.dt_utils import as_local, dt_now_utc

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..type_defs import KidData

# Default retention periods (can be overridden by config)
DEFAULT_RETENTION: Final[dict[str, int]] = {
    const.PERIOD_DAILY: const.DEFAULT_RETENTION_DAILY,
    const.PERIOD_WEEKLY: const.DEFAULT_RETENTION_WEEKLY,
    const.PERIOD_MONTHLY: const.DEFAULT_RETENTION_MONTHLY,
    const.PERIOD_YEARLY: const.DEFAULT_RETENTION_YEARLY,
}


class StatisticsEngine:
    """Unified engine for tracking period-based statistics.

    This class provides methods to:
    - Generate consistent period keys (daily/weekly/monthly/yearly)
    - Record transactions to multiple period buckets atomically
    - Update and calculate streaks
    - Prune historical data based on retention policies

    All methods are stateless - they operate on data structures passed as arguments.
    The engine does NOT persist data; the caller is responsible for persistence.

    Example:
        stats = StatisticsEngine()

        # Record a chore completion
        period_data = kid_chore_data["periods"]
        stats.record_transaction(
            period_data,
            increments={"approved": 1, "points": 10},
            include_all_time=True,
        )

        # Update streak
        stats.update_streak(kid_chore_data, "current_streak", "last_completed")

        # Prune old data
        stats.prune_history(period_data, retention_config)
    """

    # ────────────────────────────────────────────────────────────────
    # Period Key Generation
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _dt_today_local() -> date:
        """Return today's date in local timezone.

        Returns:
            Current date in local timezone.
        """
        return as_local(dt_now_utc()).date()

    @staticmethod
    def _dt_now_local() -> datetime:
        """Return current datetime in local timezone.

        Returns:
            Current datetime (timezone-aware) in local timezone.
        """
        return as_local(dt_now_utc())

    def get_period_keys(
        self, reference_date: date | datetime | None = None
    ) -> dict[str, str]:
        """Generate period keys for all time granularities.

        Creates consistent period identifiers for daily, weekly, monthly,
        and yearly tracking based on the reference date.

        Args:
            reference_date: Date to generate keys for. Defaults to today (local).
                           Accepts date, datetime, or None.

        Returns:
            Dictionary with keys: "daily", "weekly", "monthly", "yearly"
            Values are formatted strings suitable for use as dictionary keys.

        Example:
            >>> stats.get_period_keys()
            {
                "daily": "2026-01-19",
                "weekly": "2026-W03",
                "monthly": "2026-01",
                "yearly": "2026"
            }
        """
        if reference_date is None:
            ref = self._dt_today_local()
        elif isinstance(reference_date, datetime):
            ref = reference_date.date()
        else:
            ref = reference_date

        return {
            const.PERIOD_DAILY: ref.strftime(const.PERIOD_FORMAT_DAILY),
            const.PERIOD_WEEKLY: ref.strftime(const.PERIOD_FORMAT_WEEKLY),
            const.PERIOD_MONTHLY: ref.strftime(const.PERIOD_FORMAT_MONTHLY),
            const.PERIOD_YEARLY: ref.strftime(const.PERIOD_FORMAT_YEARLY),
        }

    # ────────────────────────────────────────────────────────────────
    # Transaction Recording
    # ────────────────────────────────────────────────────────────────

    def record_transaction(
        self,
        period_data: dict[str, Any],
        increments: Mapping[str, int | float],
        period_key_mapping: Mapping[str, str] | None = None,
        include_all_time: bool = True,
        reference_date: date | datetime | None = None,
    ) -> None:
        """Record a transaction across all period buckets.

        Updates daily, weekly, monthly, and yearly period data with the
        provided increments. Optionally updates all_time totals.

        Special handling:
        - streak_tally: ONLY written to daily buckets
        - longest_streak: NEVER written by this method (managed separately in all_time)

        This method mutates `period_data` in place. Caller is responsible
        for persistence after calling this method.

        Args:
            period_data: Dictionary containing nested period structures.
                        Expected format: {period_type: {period_key: {metric: value}}}
            increments: Metrics to increment and their values.
                       Example: {"approved": 1, "points": 10}
                       Note: streak_tally filtered to daily only, longest_streak skipped.
            period_key_mapping: Optional mapping from logical period names to
                               data structure keys. Defaults use const values:
                               {"daily": "daily", "weekly": "weekly", ...}
            include_all_time: If True (default), also update "all_time" totals.
                             Set to False only for legacy data without all_time bucket.
            reference_date: Date for period key generation. Defaults to today.

        Example:
            # Standard chore period update
            stats.record_transaction(
                chore_data["periods"],
                increments={"approved": 1, "points": 10},
                include_all_time=True,
            )

            # Point period update with custom key mapping
            stats.record_transaction(
                point_data["periods"],
                increments={"earned": 5},
                period_key_mapping={
                    "daily": const.DATA_KID_POINT_PERIODS_DAILY,
                    "weekly": const.DATA_KID_POINT_PERIODS_WEEKLY,
                    "monthly": const.DATA_KID_POINT_PERIODS_MONTHLY,
                    "yearly": const.DATA_KID_POINT_PERIODS_YEARLY,
                },
            )
        """
        # Generate period keys for current date
        keys = self.get_period_keys(reference_date)

        # Default key mapping if not provided
        if period_key_mapping is None:
            period_key_mapping = {
                const.PERIOD_DAILY: const.PERIOD_DAILY,
                const.PERIOD_WEEKLY: const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY: const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY: const.PERIOD_YEARLY,
            }

        # Update each period bucket with appropriate metrics
        for period_type, period_key in keys.items():
            data_key = period_key_mapping.get(period_type, period_type)

            # Ensure period type dict exists
            if data_key not in period_data:
                period_data[data_key] = {}

            # Ensure period key dict exists
            if period_key not in period_data[data_key]:
                period_data[data_key][period_key] = {}

            # Apply increments with period-specific filtering
            bucket = period_data[data_key][period_key]
            for metric, value in increments.items():
                # FILTER 1: streak_tally ONLY in daily buckets
                if (
                    metric == const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY
                    and period_type != const.PERIOD_DAILY
                ):
                    continue

                # FILTER 2: longest_streak NEVER written here (managed in all_time only)
                if metric == const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK:
                    continue

                # Write all other metrics to bucket
                current = bucket.get(metric, 0)
                if isinstance(value, float):
                    bucket[metric] = round(current + value, const.DATA_FLOAT_PRECISION)
                else:
                    bucket[metric] = current + value

        # Optionally update all_time totals with appropriate metrics
        # NOTE: all_time uses nested structure: periods["all_time"]["all_time"] = {data}
        # This matches point_periods structure and migration output
        if include_all_time:
            if const.PERIOD_ALL_TIME not in period_data:
                period_data[const.PERIOD_ALL_TIME] = {}

            all_time_container = period_data[const.PERIOD_ALL_TIME]
            if const.PERIOD_ALL_TIME not in all_time_container:
                all_time_container[const.PERIOD_ALL_TIME] = {}

            all_time_bucket = all_time_container[const.PERIOD_ALL_TIME]
            for metric, value in increments.items():
                # FILTER: streak_tally NEVER in all_time (daily only)
                if metric == const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY:
                    continue

                # longest_streak is managed separately in _on_chore_completed
                # (high-water mark logic, not simple increment)
                # Skip it here to avoid duplicate/incorrect writes
                if metric == const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK:
                    continue

                current = all_time_bucket.get(metric, 0)
                if isinstance(value, float):
                    all_time_bucket[metric] = round(
                        current + value, const.DATA_FLOAT_PRECISION
                    )
                else:
                    all_time_bucket[metric] = current + value

    # ────────────────────────────────────────────────────────────────
    # Streak Management
    # ────────────────────────────────────────────────────────────────

    def update_streak(
        self,
        container: dict[str, Any],
        streak_key: str,
        last_date_key: str | None = None,
        reference_date: date | datetime | None = None,
    ) -> int:
        """Update and return the current streak value.

        Streak logic:
        - Same day as last activity: No change (already counted)
        - Day after last activity (yesterday): Increment streak
        - Any other case: Reset streak to 1

        This method mutates `container` in place. If `last_date_key` is provided,
        it will also update the last activity date.

        Args:
            container: Dictionary containing streak data.
            streak_key: Key for the streak counter in container.
            last_date_key: Optional key for the last activity date.
                          If provided, will be updated to current date.
            reference_date: Date to use as "today". Defaults to actual today.

        Returns:
            Updated streak value.

        Example:
            # Update chore streak
            streak = stats.update_streak(
                chore_data,
                streak_key="current_streak",
                last_date_key="last_completed",
            )
            # streak = 5 (if continuing from yesterday)
        """
        if reference_date is None:
            today = self._dt_today_local()
        elif isinstance(reference_date, datetime):
            today = reference_date.date()
        else:
            today = reference_date

        today_iso = today.isoformat()
        yesterday = today - timedelta(days=1)
        yesterday_iso = yesterday.isoformat()

        # Get current state
        current_streak = container.get(streak_key, 0)
        last_date_str = container.get(last_date_key) if last_date_key else None

        # Determine new streak value
        if last_date_str == today_iso:
            # Same day - no change
            new_streak = current_streak
        elif last_date_str == yesterday_iso:
            # Consecutive day - increment
            new_streak = current_streak + 1
        else:
            # Gap or first time - reset to 1
            new_streak = 1

        # Update container
        container[streak_key] = new_streak
        if last_date_key is not None:
            container[last_date_key] = today_iso

        return new_streak

    def get_streak(
        self,
        container: Mapping[str, Any],
        streak_key: str,
    ) -> int:
        """Get current streak value without modifying container.

        Args:
            container: Dictionary containing streak data.
            streak_key: Key for the streak counter.

        Returns:
            Current streak value, or 0 if not set.
        """
        return container.get(streak_key, 0)

    # ────────────────────────────────────────────────────────────────
    # History Pruning
    # ────────────────────────────────────────────────────────────────

    def prune_history(
        self,
        period_data: dict[str, Any],
        retention_config: Mapping[str, int] | None = None,
        period_key_mapping: Mapping[str, str] | None = None,
        reference_date: date | datetime | None = None,
    ) -> int:
        """Remove old period data based on retention policies.

        Prunes entries older than the configured retention period for each
        time granularity. Does NOT prune all_time data.

        This method mutates `period_data` in place. Caller is responsible
        for persistence after calling this method.

        Args:
            period_data: Dictionary containing nested period structures.
            retention_config: Dict mapping period types to retention counts.
                            Example: {"daily": 90, "weekly": 52, ...}
                            Defaults to const.DEFAULT_RETENTION_* values.
            period_key_mapping: Optional mapping from logical period names to
                               data structure keys.
            reference_date: Date to calculate cutoffs from. Defaults to today.

        Returns:
            Total number of entries pruned.

        Example:
            pruned = stats.prune_history(
                chore_data["periods"],
                retention_config={"daily": 30, "weekly": 12, "monthly": 12, "yearly": 5},
            )
            # pruned = 15 (entries removed)
        """
        if reference_date is None:
            today = self._dt_today_local()
        elif isinstance(reference_date, datetime):
            today = reference_date.date()
        else:
            today = reference_date

        # Use defaults if not provided
        if retention_config is None:
            retention_config = DEFAULT_RETENTION

        # Default key mapping if not provided
        if period_key_mapping is None:
            period_key_mapping = {
                const.PERIOD_DAILY: const.PERIOD_DAILY,
                const.PERIOD_WEEKLY: const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY: const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY: const.PERIOD_YEARLY,
            }

        total_pruned = 0

        # Daily: keep configured days
        daily_key = period_key_mapping.get(
            const.PERIOD_DAILY,
            const.PERIOD_DAILY,
        )
        retention_days = retention_config.get(
            const.PERIOD_DAILY,
            DEFAULT_RETENTION[const.PERIOD_DAILY],
        )
        cutoff_daily = (today - timedelta(days=retention_days)).strftime(
            const.PERIOD_FORMAT_DAILY
        )
        daily_data = period_data.get(daily_key, {})
        for day in list(daily_data.keys()):
            if day < cutoff_daily:
                del daily_data[day]
                total_pruned += 1

        # Weekly: keep configured weeks
        weekly_key = period_key_mapping.get(
            const.PERIOD_WEEKLY,
            const.PERIOD_WEEKLY,
        )
        retention_weeks = retention_config.get(
            const.PERIOD_WEEKLY,
            DEFAULT_RETENTION[const.PERIOD_WEEKLY],
        )
        cutoff_weekly = (today - timedelta(weeks=retention_weeks)).strftime(
            const.PERIOD_FORMAT_WEEKLY
        )
        weekly_data = period_data.get(weekly_key, {})
        for week in list(weekly_data.keys()):
            if week < cutoff_weekly:
                del weekly_data[week]
                total_pruned += 1

        # Monthly: keep configured months
        monthly_key = period_key_mapping.get(
            const.PERIOD_MONTHLY,
            const.PERIOD_MONTHLY,
        )
        retention_months = retention_config.get(
            const.PERIOD_MONTHLY,
            DEFAULT_RETENTION[const.PERIOD_MONTHLY],
        )
        # Calculate cutoff month (approximate with 30 days per month)
        cutoff_date = today - timedelta(days=retention_months * 30)
        cutoff_monthly = cutoff_date.strftime(const.PERIOD_FORMAT_MONTHLY)
        monthly_data = period_data.get(monthly_key, {})
        for month in list(monthly_data.keys()):
            if month < cutoff_monthly:
                del monthly_data[month]
                total_pruned += 1

        # Yearly: keep configured years
        yearly_key = period_key_mapping.get(
            const.PERIOD_YEARLY,
            const.PERIOD_YEARLY,
        )
        retention_years = retention_config.get(
            const.PERIOD_YEARLY,
            DEFAULT_RETENTION[const.PERIOD_YEARLY],
        )
        cutoff_yearly = str(today.year - retention_years)
        yearly_data = period_data.get(yearly_key, {})
        for year in list(yearly_data.keys()):
            if year < cutoff_yearly:
                del yearly_data[year]
                total_pruned += 1

        return total_pruned

    # ────────────────────────────────────────────────────────────────
    # Utility Methods
    # ────────────────────────────────────────────────────────────────

    def get_period_total(
        self,
        period_data: Mapping[str, Any],
        period_type: str,
        metric: str,
        period_key: str | None = None,
        period_key_mapping: Mapping[str, str] | None = None,
    ) -> int | float:
        """Get total value for a metric in a specific period.

        Args:
            period_data: Dictionary containing nested period structures.
            period_type: One of "daily", "weekly", "monthly", "yearly", "all_time".
            metric: The metric to retrieve (e.g., "approved", "points").
            period_key: Specific period key to look up. If None, uses current period.
            period_key_mapping: Optional key mapping for data structure.

        Returns:
            Value of the metric, or 0 if not found.

        Example:
            # Get today's approved count
            approved = stats.get_period_total(
                chore_data["periods"],
                "daily",
                "approved",
            )
        """
        if period_key_mapping is None:
            period_key_mapping = {
                const.PERIOD_DAILY: const.PERIOD_DAILY,
                const.PERIOD_WEEKLY: const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY: const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY: const.PERIOD_YEARLY,
                const.PERIOD_ALL_TIME: const.PERIOD_ALL_TIME,
            }

        data_key = period_key_mapping.get(period_type, period_type)

        # Handle all_time specially (flat structure)
        if period_type == const.PERIOD_ALL_TIME:
            return period_data.get(data_key, {}).get(metric, 0)

        # Get period key if not provided
        if period_key is None:
            keys = self.get_period_keys()
            period_key = keys.get(period_type, "")

        return period_data.get(data_key, {}).get(period_key, {}).get(metric, 0)

    # ────────────────────────────────────────────────────────────────
    # Stats Generation (Read/Aggregation Layer)
    # ────────────────────────────────────────────────────────────────

    # NOTE: generate_chore_stats() DELETED in v0.5.0-beta3 (schema v43)
    # chore_stats storage bucket was deleted; all stats now derived from:
    # - chore_periods.all_time: Kid-level aggregated all-time stats
    # - chore_data[uuid].periods: Per-chore period buckets
    # Snapshot counts (current_overdue, etc.) computed inline in StatisticsManager

    def generate_reward_stats(
        self,
        kid_info: KidData | dict[str, Any],
        rewards_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Aggregate and return reward statistics for a kid.

        This method generates all reward_stats by aggregating period data
        across all rewards. It does NOT mutate kid_info - returns a new dict.

        Note: All-time stats are preserved from kid_info since old period data
        may be pruned. Period stats (today/week/month/year) are recalculated.

        Note: Reward stats are computed and stored but not yet exposed in the
        UI (sensors/dashboard helper). Ready for future integration.

        Args:
            kid_info: Kid data dictionary containing reward_data with periods.
            rewards_data: Global rewards dictionary for name lookups.

        Returns:
            Dictionary with all reward stat keys populated.
        """
        existing_stats = cast(
            "dict[str, Any]", kid_info.get(const.DATA_KID_REWARD_STATS, {})
        )

        # Initialize stats with defaults, preserving all-time values
        stats: dict[str, Any] = {
            # Claimed counts
            const.DATA_KID_REWARD_STATS_CLAIMED_TODAY: 0,
            const.DATA_KID_REWARD_STATS_CLAIMED_WEEK: 0,
            const.DATA_KID_REWARD_STATS_CLAIMED_MONTH: 0,
            const.DATA_KID_REWARD_STATS_CLAIMED_YEAR: 0,
            const.DATA_KID_REWARD_STATS_CLAIMED_ALL_TIME: existing_stats.get(
                const.DATA_KID_REWARD_STATS_CLAIMED_ALL_TIME, 0
            ),
            # Approved counts
            const.DATA_KID_REWARD_STATS_APPROVED_TODAY: 0,
            const.DATA_KID_REWARD_STATS_APPROVED_WEEK: 0,
            const.DATA_KID_REWARD_STATS_APPROVED_MONTH: 0,
            const.DATA_KID_REWARD_STATS_APPROVED_YEAR: 0,
            const.DATA_KID_REWARD_STATS_APPROVED_ALL_TIME: existing_stats.get(
                const.DATA_KID_REWARD_STATS_APPROVED_ALL_TIME, 0
            ),
            # Points spent on rewards
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_TODAY: 0.0,
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_WEEK: 0.0,
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_MONTH: 0.0,
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_YEAR: 0.0,
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_ALL_TIME: existing_stats.get(
                const.DATA_KID_REWARD_STATS_POINTS_SPENT_ALL_TIME, 0.0
            ),
            # Most redeemed reward
            const.DATA_KID_REWARD_STATS_MOST_REDEEMED_ALL_TIME: None,
            const.DATA_KID_REWARD_STATS_MOST_REDEEMED_WEEK: None,
            const.DATA_KID_REWARD_STATS_MOST_REDEEMED_MONTH: None,
        }

        # Get current period keys
        now_local = self._dt_now_local()
        today_local_iso = self._dt_today_local().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        # For most redeemed tracking
        most_redeemed: dict[str, int] = {}
        most_redeemed_week: dict[str, int] = {}
        most_redeemed_month: dict[str, int] = {}

        # Aggregate stats from all rewards
        for reward_id, reward_data in kid_info.get(
            const.DATA_KID_REWARD_DATA, {}
        ).items():
            periods = reward_data.get(const.DATA_KID_REWARD_DATA_PERIODS, {})

            # All-time totals for most redeemed
            total_approved = reward_data.get(
                const.DATA_KID_REWARD_DATA_TOTAL_APPROVED, 0
            )
            most_redeemed[reward_id] = total_approved

            # Get reward cost for points spent calculation
            reward_info = rewards_data.get(reward_id, {})
            reward_cost = reward_info.get(const.DATA_REWARD_COST, 0.0)

            # Daily
            daily = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_DAILY, {})
            today_stats = daily.get(today_local_iso, {})
            claimed_today = today_stats.get(
                const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0
            )
            approved_today = today_stats.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_REWARD_STATS_CLAIMED_TODAY] += claimed_today
            stats[const.DATA_KID_REWARD_STATS_APPROVED_TODAY] += approved_today
            stats[const.DATA_KID_REWARD_STATS_POINTS_SPENT_TODAY] += (
                approved_today * reward_cost
            )

            # Weekly
            weekly = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY, {})
            week_stats = weekly.get(week_local_iso, {})
            claimed_week = week_stats.get(const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0)
            approved_week = week_stats.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_REWARD_STATS_CLAIMED_WEEK] += claimed_week
            stats[const.DATA_KID_REWARD_STATS_APPROVED_WEEK] += approved_week
            stats[const.DATA_KID_REWARD_STATS_POINTS_SPENT_WEEK] += (
                approved_week * reward_cost
            )
            most_redeemed_week[reward_id] = approved_week

            # Monthly
            monthly = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY, {})
            month_stats = monthly.get(month_local_iso, {})
            claimed_month = month_stats.get(
                const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0
            )
            approved_month = month_stats.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_REWARD_STATS_CLAIMED_MONTH] += claimed_month
            stats[const.DATA_KID_REWARD_STATS_APPROVED_MONTH] += approved_month
            stats[const.DATA_KID_REWARD_STATS_POINTS_SPENT_MONTH] += (
                approved_month * reward_cost
            )
            most_redeemed_month[reward_id] = approved_month

            # Yearly
            yearly = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_YEARLY, {})
            year_stats = yearly.get(year_local_iso, {})
            claimed_year = year_stats.get(const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0)
            approved_year = year_stats.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )
            stats[const.DATA_KID_REWARD_STATS_CLAIMED_YEAR] += claimed_year
            stats[const.DATA_KID_REWARD_STATS_APPROVED_YEAR] += approved_year
            stats[const.DATA_KID_REWARD_STATS_POINTS_SPENT_YEAR] += (
                approved_year * reward_cost
            )

        # Round points spent
        for key in [
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_TODAY,
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_WEEK,
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_MONTH,
            const.DATA_KID_REWARD_STATS_POINTS_SPENT_YEAR,
        ]:
            stats[key] = round(stats[key], const.DATA_FLOAT_PRECISION)

        # Derive "most redeemed" reward names
        def _get_reward_name(reward_id: str) -> str:
            return rewards_data.get(reward_id, {}).get(
                const.DATA_REWARD_NAME, reward_id
            )

        if most_redeemed:
            best_id = max(most_redeemed, key=lambda x: most_redeemed.get(x, 0))
            if most_redeemed.get(best_id, 0) > 0:
                stats[const.DATA_KID_REWARD_STATS_MOST_REDEEMED_ALL_TIME] = (
                    _get_reward_name(best_id)
                )
        if most_redeemed_week:
            best_id = max(
                most_redeemed_week, key=lambda x: most_redeemed_week.get(x, 0)
            )
            if most_redeemed_week.get(best_id, 0) > 0:
                stats[const.DATA_KID_REWARD_STATS_MOST_REDEEMED_WEEK] = (
                    _get_reward_name(best_id)
                )
        if most_redeemed_month:
            best_id = max(
                most_redeemed_month, key=lambda x: most_redeemed_month.get(x, 0)
            )
            if most_redeemed_month.get(best_id, 0) > 0:
                stats[const.DATA_KID_REWARD_STATS_MOST_REDEEMED_MONTH] = (
                    _get_reward_name(best_id)
                )

        return stats

    @staticmethod
    def get_badge_award_count(badge_entry: Mapping[str, Any]) -> int:
        """Get badge award count from periods.all_time.all_time.

        Phase 4B: Lean Item pattern - award_count stored ONLY in periods, not at root.
        Matches Phase 2 (chores) and Phase 3 (rewards) consolidation.

        Args:
            badge_entry: badges_earned[badge_id] dict from kid_data

        Returns:
            Award count from periods.all_time.all_time, or 0 if not found

        Example:
            badge_entry = kid_info["badges_earned"]["uuid-1234"]
            count = StatisticsEngine.get_badge_award_count(badge_entry)
        """
        periods = badge_entry.get(const.DATA_KID_BADGES_EARNED_PERIODS, {})
        all_time_bucket = periods.get(const.DATA_KID_BADGES_EARNED_PERIODS_ALL_TIME, {})
        all_time_data = all_time_bucket.get(const.PERIOD_ALL_TIME, {})
        return all_time_data.get(const.DATA_KID_BADGES_EARNED_AWARD_COUNT, 0)

    @staticmethod
    def get_bonus_applies_count(
        bonus_entry: Mapping[str, Any], period_type: str = const.PERIOD_ALL_TIME
    ) -> int:
        """Get the number of times a bonus has been applied.

        Phase 4C: Bonus applies are tracked in periods structure.
        This method encapsulates the navigation logic to retrieve the count.

        Args:
            bonus_entry: The bonus entry dict from kid.bonus_applies[bonus_id]
            period_type: Period to query ("all_time", "daily", etc.)

        Returns:
            Number of times the bonus was applied, or 0 if not found

        Example:
            bonus_entry = kid_info["bonus_applies"]["uuid-1234"]
            count = StatisticsEngine.get_bonus_applies_count(bonus_entry)
        """
        periods = bonus_entry.get(const.DATA_KID_BONUS_PERIODS, {})
        if period_type == const.PERIOD_ALL_TIME:
            return (
                periods.get(const.PERIOD_ALL_TIME, {})
                .get(const.PERIOD_ALL_TIME, {})
                .get(const.DATA_KID_BONUS_PERIOD_APPLIES, 0)
            )
        # For other periods, would need period_key (not implemented yet)
        return 0

    @staticmethod
    def get_penalty_applies_count(
        penalty_entry: Mapping[str, Any], period_type: str = const.PERIOD_ALL_TIME
    ) -> int:
        """Get the number of times a penalty has been applied.

        Phase 4C: Penalty applies are tracked in periods structure.
        This method encapsulates the navigation logic to retrieve the count.

        Args:
            penalty_entry: The penalty entry dict from kid.penalty_applies[penalty_id]
            period_type: Period to query ("all_time", "daily", etc.)

        Returns:
            Number of times the penalty was applied, or 0 if not found

        Example:
            penalty_entry = kid_info["penalty_applies"]["uuid-5678"]
            count = StatisticsEngine.get_penalty_applies_count(penalty_entry)
        """
        periods = penalty_entry.get(const.DATA_KID_PENALTY_PERIODS, {})
        if period_type == const.PERIOD_ALL_TIME:
            return (
                periods.get(const.PERIOD_ALL_TIME, {})
                .get(const.PERIOD_ALL_TIME, {})
                .get(const.DATA_KID_PENALTY_PERIOD_APPLIES, 0)
            )
        # For other periods, would need period_key (not implemented yet)
        return 0
