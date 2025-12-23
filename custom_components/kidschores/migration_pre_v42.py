"""Migration logic for pre-v42 schema data.

This module handles one-time migrations from pre-v42 (legacy) data structures
to the v42+ storage-only architecture. These migrations are only executed
when upgrading from legacy configurations to the modern data model.

DEPRECATION NOTICE: This module can be removed in KC 5.0 when the vast majority
of users have upgraded past v42. The migration logic is frozen and will not be
modified further. Modern installations (KC 4.2+) skip this module entirely via
lazy import to avoid any runtime cost.
"""

import random
from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import const
from . import kc_helpers as kh

if TYPE_CHECKING:
    from .coordinator import KidsChoresDataCoordinator


class PreV42Migrator:
    """Handles all pre-v42 schema migrations.

    This class encapsulates the legacy migration logic that transforms
    pre-v42 data structures to the modern storage-only v42+ format.
    All migrations are one-time operations executed on first coordinator startup
    for users upgrading from older versions.

    Attributes:
        coordinator: Reference to the KidsChoresDataCoordinator instance.
    """

    # pylint: disable=protected-access
    # This migration class intentionally accesses coordinator private methods and data

    def __init__(self, coordinator: "KidsChoresDataCoordinator") -> None:
        """Initialize the migrator with coordinator reference.

        Args:
            coordinator: The KidsChoresDataCoordinator instance to migrate data for.
        """
        self.coordinator = coordinator

    def run_all_migrations(self) -> None:
        """Execute all pre-v42 migrations in the correct order.

        Migrations are run sequentially with proper error handling and logging.
        Each migration is idempotent - it can be run multiple times without
        causing data corruption or duplication.
        """
        const.LOGGER.info(
            "Starting pre-v42 schema migrations for upgrade to modern format"
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
        const.LOGGER.info("Migrating KC 3.x config data to storage")
        self._initialize_data_from_config()

        const.LOGGER.info("All pre-v42 migrations completed successfully")

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
            dt_obj_utc = kh.parse_datetime_to_utc(dt_str)
            if dt_obj_utc:
                return dt_obj_utc.isoformat()
            else:
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

    # pylint: disable=too-many-branches
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
        # Also, migrate timestamps in pending approvals
        for approval in self.coordinator._data.get(
            const.DATA_PENDING_CHORE_APPROVALS, []
        ):
            if approval.get(const.DATA_CHORE_TIMESTAMP):
                approval[const.DATA_CHORE_TIMESTAMP] = self._migrate_datetime(
                    approval[const.DATA_CHORE_TIMESTAMP]
                )
        for approval in self.coordinator._data.get(
            const.DATA_PENDING_REWARD_APPROVALS, []
        ):
            if approval.get(const.DATA_CHORE_TIMESTAMP):
                approval[const.DATA_CHORE_TIMESTAMP] = self._migrate_datetime(
                    approval[const.DATA_CHORE_TIMESTAMP]
                )

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
                const.CONF_APPLICABLE_DAYS, const.DEFAULT_APPLICABLE_DAYS
            )
            chore_info.setdefault(
                const.CONF_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
            )
            chore_info.setdefault(
                const.CONF_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            )
            chore_info.setdefault(
                const.CONF_NOTIFY_ON_DISAPPROVAL, const.DEFAULT_NOTIFY_ON_DISAPPROVAL
            )
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

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    def _migrate_legacy_kid_chore_data_and_streaks(self) -> None:
        """Migrate legacy streak and stats data to the new kid chores structure (period-based).

        This function will automatically run through all kids and all assigned chores.
        Data that only needs to be migrated once per kid is handled separately from per-chore data.
        """
        for kid_id, kid_info in self.coordinator.kids_data.items():
            # --- Per-kid migration (run once per kid) ---
            # Only migrate these once per kid, not per chore
            chore_stats = kid_info.setdefault(const.DATA_KID_CHORE_STATS, {})
            legacy_streaks = kid_info.get(const.DATA_KID_CHORE_STREAKS_DEPRECATED, {})
            legacy_max = 0
            last_longest_streak_date = None

            # Find the max streak and last date across all chores for this kid
            for chore_id, legacy_streak in legacy_streaks.items():
                max_streak = legacy_streak.get(const.DATA_KID_MAX_STREAK, 0)
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
                const.DATA_KID_COMPLETED_CHORES_TOTAL_DEPRECATED, 0
            )
            chore_stats[const.DATA_KID_CHORE_STATS_APPROVED_YEAR] = kid_info.get(
                const.DATA_KID_COMPLETED_CHORES_TOTAL_DEPRECATED, 0
            )

            # Migrate all-time claimed count from legacy (use max of any chore's claims or completed_chores_total)
            all_claims = [
                kid_info.get(const.DATA_KID_CHORE_CLAIMS_DEPRECATED, {}).get(
                    chore_id, 0
                )
                for chore_id in self.coordinator.chores_data.keys()
            ]
            all_claims.append(
                kid_info.get(const.DATA_KID_COMPLETED_CHORES_TOTAL_DEPRECATED, 0)
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

                if chore_id not in kid_info[const.DATA_KID_CHORE_DATA]:
                    chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
                    kid_info[const.DATA_KID_CHORE_DATA][chore_id] = {
                        const.DATA_KID_CHORE_DATA_NAME: chore_name,
                        const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
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

                kid_chore_data = kid_info[const.DATA_KID_CHORE_DATA][chore_id]
                periods = kid_chore_data[const.DATA_KID_CHORE_DATA_PERIODS]

                # --- Migrate legacy current streaks for this chore ---
                legacy_streak = legacy_streaks.get(chore_id, {})
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
                        ] = legacy_streak.get(const.DATA_KID_MAX_STREAK, 0)

                # --- Migrate claim/approval counts for this chore ---
                claims = kid_info.get(const.DATA_KID_CHORE_CLAIMS_DEPRECATED, {}).get(
                    chore_id, 0
                )
                approvals = kid_info.get(
                    const.DATA_KID_CHORE_APPROVALS_DEPRECATED, {}
                ).get(chore_id, 0)

                # --- Migrate period completion and claim counts for this chore ---
                now_local = kh.get_now_local_time()
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

    # pylint: disable=too-many-branches,too-many-statements
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
        for _, badge_info in badges_dict.items():
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
                        const.CONF_POINTS
                    )
                    badge_info[const.DATA_BADGE_THRESHOLD_VALUE_LEGACY] = new_threshold

                    # Also update the target structure immediately
                    badge_info.setdefault(const.DATA_BADGE_TARGET, {})
                    badge_info[const.DATA_BADGE_TARGET][
                        const.DATA_BADGE_TARGET_TYPE
                    ] = const.CONF_POINTS
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
        for _, kid_info in self.coordinator.kids_data.items():
            legacy_badge_names = kid_info.get(const.DATA_KID_BADGES_DEPRECATED, [])
            if not legacy_badge_names:
                continue

            # Find the highest-value cumulative badge earned by this kid
            highest_badge = None
            highest_points = -1
            for badge_name in legacy_badge_names:
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
                points = float(
                    badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                if points > highest_points:
                    highest_points = points
                    highest_badge = badge_info

            # Set the current cumulative badge progress for this kid
            if highest_badge:
                progress = kid_info.setdefault(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
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
        today_local_iso = kh.get_today_local_iso()

        for kid_id, kid_info in self.coordinator.kids_data.items():
            legacy_badge_names = kid_info.get(const.DATA_KID_BADGES_DEPRECATED, [])
            badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})

            for badge_name in legacy_badge_names:
                badge_id = kh.get_badge_id_by_name(self.coordinator, badge_name)

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
            if const.DATA_KID_BADGES_DEPRECATED in kid_info:
                del kid_info[const.DATA_KID_BADGES_DEPRECATED]

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    # pylint: disable=too-many-locals
    def _migrate_legacy_point_stats(self) -> None:
        """Migrate legacy rolling point stats into the new point_data period structure for each kid."""
        for _, kid_info in self.coordinator.kids_data.items():
            # Legacy values
            legacy_today = round(
                kid_info.get(const.DATA_KID_POINTS_EARNED_TODAY_DEPRECATED, 0.0), 1
            )
            legacy_week = round(
                kid_info.get(const.DATA_KID_POINTS_EARNED_WEEKLY_DEPRECATED, 0.0), 1
            )
            legacy_month = round(
                kid_info.get(const.DATA_KID_POINTS_EARNED_MONTHLY_DEPRECATED, 0.0), 1
            )
            legacy_max = round(kid_info.get(const.DATA_KID_MAX_POINTS_EVER, 0.0), 1)

            # Get or create point_data periods
            point_data = kid_info.setdefault(const.DATA_KID_POINT_DATA, {})
            periods = point_data.setdefault(const.DATA_KID_POINT_DATA_PERIODS, {})

            # Get period keys
            today_local_iso = kh.get_today_local_date().isoformat()
            now_local = kh.get_now_local_time()
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

            # Migrate legacy max points ever to point_stats highest balance if needed
            point_stats = kid_info.setdefault(const.DATA_KID_POINT_STATS, {})
            if legacy_max > 0 and legacy_max > point_stats.get(
                const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, 0.0
            ):
                point_stats[const.DATA_KID_POINT_STATS_HIGHEST_BALANCE] = legacy_max

            # Set points_earned_all_time to legacy_max if > 0
            if legacy_max > 0:
                point_stats[const.DATA_KID_POINT_STATS_EARNED_ALL_TIME] = legacy_max

            # --- Migrate all-time points by source ---
            if legacy_max > 0:
                point_stats[const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME] = {
                    const.POINTS_SOURCE_OTHER: legacy_max
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
        if not options or not options.get(const.CONF_KIDS):
            const.LOGGER.info(
                "No KC 3.x config data - skipping config sync (already using storage-only mode)"
            )
            return

        # Retrieve configuration dictionaries from config entry options (KC 3.x architecture)
        config_sections = {
            const.DATA_KIDS: options.get(const.CONF_KIDS, {}),
            const.DATA_PARENTS: options.get(const.CONF_PARENTS, {}),
            const.DATA_CHORES: options.get(const.CONF_CHORES, {}),
            const.DATA_BADGES: options.get(const.CONF_BADGES, {}),
            const.DATA_REWARDS: options.get(const.CONF_REWARDS, {}),
            const.DATA_PENALTIES: options.get(const.CONF_PENALTIES, {}),
            const.DATA_BONUSES: options.get(const.CONF_BONUSES, {}),
            const.DATA_ACHIEVEMENTS: options.get(const.CONF_ACHIEVEMENTS, {}),
            const.DATA_CHALLENGES: options.get(const.CONF_CHALLENGES, {}),
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

        # Recalculate Badges on reload
        self.coordinator._recalculate_all_badges()

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
            const.DATA_PENDING_CHORE_APPROVALS,
            const.DATA_PENDING_REWARD_APPROVALS,
        ]:
            if not isinstance(self.coordinator._data.get(key), list):
                self.coordinator._data[key] = []

    # -- Entity Type Wrappers (delegate to _sync_entities) --

    def _initialize_kids(self, kids_dict: dict[str, Any]) -> None:
        """Initialize kids from config data."""
        self._sync_entities(
            const.DATA_KIDS,
            kids_dict,
            self.coordinator._create_kid,
            self.coordinator._update_kid,
        )

    def _initialize_parents(self, parents_dict: dict[str, Any]) -> None:
        """Initialize parents from config data."""
        self._sync_entities(
            const.DATA_PARENTS,
            parents_dict,
            self.coordinator._create_parent,
            self.coordinator._update_parent,
        )

    def _initialize_chores(self, chores_dict: dict[str, Any]) -> None:
        """Initialize chores from config data."""
        self._sync_entities(
            const.DATA_CHORES,
            chores_dict,
            self.coordinator._create_chore,
            self.coordinator._update_chore,
        )

    def _initialize_badges(self, badges_dict: dict[str, Any]) -> None:
        """Initialize badges from config data."""
        self._sync_entities(
            const.DATA_BADGES,
            badges_dict,
            self.coordinator._create_badge,
            self.coordinator._update_badge,
        )

    def _initialize_rewards(self, rewards_dict: dict[str, Any]) -> None:
        """Initialize rewards from config data."""
        self._sync_entities(
            const.DATA_REWARDS,
            rewards_dict,
            self.coordinator._create_reward,
            self.coordinator._update_reward,
        )

    def _initialize_penalties(self, penalties_dict: dict[str, Any]) -> None:
        """Initialize penalties from config data."""
        self._sync_entities(
            const.DATA_PENALTIES,
            penalties_dict,
            self.coordinator._create_penalty,
            self.coordinator._update_penalty,
        )

    def _initialize_achievements(self, achievements_dict: dict[str, Any]) -> None:
        """Initialize achievements from config data."""
        self._sync_entities(
            const.DATA_ACHIEVEMENTS,
            achievements_dict,
            self.coordinator._create_achievement,
            self.coordinator._update_achievement,
        )

    def _initialize_challenges(self, challenges_dict: dict[str, Any]) -> None:
        """Initialize challenges from config data."""
        self._sync_entities(
            const.DATA_CHALLENGES,
            challenges_dict,
            self.coordinator._create_challenge,
            self.coordinator._update_challenge,
        )

    def _initialize_bonuses(self, bonuses_dict: dict[str, Any]) -> None:
        """Initialize bonuses from config data."""
        self._sync_entities(
            const.DATA_BONUSES,
            bonuses_dict,
            self.coordinator._create_bonus,
            self.coordinator._update_bonus,
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
            self.coordinator._remove_entities_in_ha(entity_id)
            if section == const.DATA_CHORES:
                for kid_id in self.coordinator.kids_data.keys():
                    self.coordinator._remove_kid_chore_entities(kid_id, entity_id)

            # Remove deleted kids from parents list (cleanup)
            self.coordinator._cleanup_parent_assignments()

            # Remove chore approvals on chore delete
            self.coordinator._cleanup_pending_chore_approvals()

            # Remove reward approvals on reward delete
            if section == const.DATA_REWARDS:
                self.coordinator._cleanup_pending_reward_approvals()

        # Add or update entities
        for entity_id, entity_body in config_data.items():
            if entity_id not in self.coordinator._data[section]:
                create_method(entity_id, entity_body)
            else:
                update_method(entity_id, entity_body)

        # Remove orphaned chore-related entities
        if section == const.DATA_CHORES:
            self.coordinator.hass.async_create_task(
                self.coordinator._remove_orphaned_shared_chore_sensors()
            )
            self.coordinator.hass.async_create_task(
                self.coordinator._remove_orphaned_kid_chore_entities()
            )

        # Remove orphaned achievement and challenges sensors
        self.coordinator.hass.async_create_task(
            self.coordinator._remove_orphaned_achievement_entities()
        )
        self.coordinator.hass.async_create_task(
            self.coordinator._remove_orphaned_challenge_entities()
        )

        # Remove deprecated sensors
        self.coordinator.hass.async_create_task(
            self.coordinator.remove_deprecated_entities(
                self.coordinator.hass, self.coordinator.config_entry
            )
        )

        # Remove deprecated/orphaned dynamic entities
        self.coordinator.remove_deprecated_button_entities()
        self.coordinator.remove_deprecated_sensor_entities()
