"""Type definitions for KidsChores data structures.

Uses TypedDict for type-safe dictionary access without changing runtime behavior.
All entity data is persisted in .storage/kidschores_data as dicts; these types
document the expected structure for IDE autocomplete and mypy validation.

IMPORTANT: This file must NOT import from coordinator.py, kc_helpers.py, or
any file that imports coordinator to avoid circular dependencies.
Only import from const.py (constants) and typing (type machinery).

NOTE: TypedDict is STATIC ANALYSIS ONLY. All runtime error handling
(null checks, .get() defaults, try/except) must remain in coordinator.py.
TypedDict does NOT enforce types at runtime.
"""

from typing import Any, NotRequired, TypedDict

# =============================================================================
# Type Aliases (for readability)
# =============================================================================

KidId = str  # UUID string
ChoreId = str  # UUID string
BadgeId = str  # UUID string
RewardId = str  # UUID string
ISODatetime = str  # ISO 8601 datetime string "2026-01-18T12:30:00+00:00"
ISODate = str  # ISO 8601 date string (no time) "2026-01-18"


# =============================================================================
# Simple Entity Types (no nesting)
# =============================================================================


class ParentData(TypedDict):
    """Type definition for a parent entity.

    Parent fields are all required once created via _create_parent().
    """

    internal_id: str  # Always present (set in _create_parent)
    name: str
    ha_user_id: str
    associated_kids: list[str]  # List of kid UUIDs
    enable_notifications: bool
    mobile_notify_service: str
    use_persistent_notifications: bool
    dashboard_language: str
    allow_chore_assignment: bool
    enable_chore_workflow: bool
    enable_gamification: bool
    linked_shadow_kid_id: NotRequired[str | None]  # Only set if shadow kid created


class RewardData(TypedDict):
    """Type definition for a reward entity."""

    internal_id: str
    name: str
    cost: float
    description: str
    icon: str
    labels: list[str]


class PenaltyData(TypedDict):
    """Type definition for a penalty entity."""

    internal_id: str
    name: str
    points: float
    description: str
    icon: str
    labels: list[str]


class BonusData(TypedDict):
    """Type definition for a bonus entity."""

    internal_id: str
    name: str
    points: float
    description: str
    icon: str
    labels: list[str]


# =============================================================================
# Chore Types (with nested structures)
# =============================================================================


class ChorePerKidDueDates(TypedDict, total=False):
    """Per-kid due date mapping.

    Keys are kid_id (UUID string), values are ISO datetime string or None.
    Using total=False because keys are dynamic (kid UUIDs).
    """


class ChorePerKidApplicableDays(TypedDict, total=False):
    """Per-kid applicable weekdays.

    Keys are kid_id (UUID string), values are list of weekday ints (0=Mon, 6=Sun).
    Using total=False because keys are dynamic (kid UUIDs).
    """


class ChorePerKidDailyMultiTimes(TypedDict, total=False):
    """Per-kid daily multi times.

    Keys are kid_id (UUID string), values are list of time strings "HH:MM".
    Using total=False because keys are dynamic (kid UUIDs).
    """


class ChoreData(TypedDict):
    """Type definition for a chore entity.

    Created via build_default_chore_data() in kc_helpers.py or _create_chore().
    See kc_helpers.py:588 for canonical field list.
    """

    # Core identification
    internal_id: str
    name: str
    state: str  # PENDING, CLAIMED, APPROVED, OVERDUE

    # Points and configuration
    default_points: float
    approval_reset_type: str
    overdue_handling_type: str
    approval_reset_pending_claim_action: str

    # Description and display
    description: str
    labels: list[str]
    icon: str

    # Assignment
    assigned_kids: list[str]  # List of kid UUIDs

    # Scheduling
    recurring_frequency: str
    custom_interval: NotRequired[int | None]
    custom_interval_unit: NotRequired[str | None]
    daily_multi_times: NotRequired[list[str]]  # For DAILY_MULTI frequency

    # Due dates
    due_date: NotRequired[str | None]  # ISO datetime
    per_kid_due_dates: dict[str, str | None]  # kid_id -> ISO datetime
    applicable_days: list[str]  # Weekday names or ints
    per_kid_applicable_days: NotRequired[dict[str, list[str]]]
    per_kid_daily_multi_times: NotRequired[dict[str, list[str]]]

    # Runtime tracking (set during chore lifecycle)
    last_completed: NotRequired[str | None]  # ISO datetime
    last_claimed: NotRequired[str | None]  # ISO datetime
    approval_period_start: NotRequired[str | None]  # ISO datetime
    claimed_by: NotRequired[list[str]]  # List of kid UUIDs
    completed_by: NotRequired[list[str]]  # List of kid UUIDs (for shared chores)

    # Notifications
    notify_on_claim: bool
    notify_on_approval: bool
    notify_on_disapproval: bool
    notify_on_reminder: NotRequired[bool]

    # Calendar and features
    show_on_calendar: NotRequired[bool]
    auto_approve: NotRequired[bool]

    # Completion criteria
    completion_criteria: str  # SHARED, SHARED_FIRST, INDEPENDENT


# =============================================================================
# Badge Types (with nested structures)
# =============================================================================


class BadgeTarget(TypedDict, total=False):
    """Badge target/threshold configuration."""

    threshold_value: float
    target_type: str  # POINTS, CHORE_COUNT, DAYS_*, STREAK_*
    maintenance_rules: NotRequired[float]  # For cumulative badges


class BadgeResetSchedule(TypedDict, total=False):
    """Badge reset/recurrence schedule."""

    recurring_frequency: str
    custom_interval: NotRequired[int]
    custom_interval_unit: NotRequired[str]
    start_date: NotRequired[str]  # ISO date
    end_date: NotRequired[str]  # ISO date
    grace_period_days: NotRequired[int]


class BadgeAwards(TypedDict, total=False):
    """Badge award configuration."""

    award_points: NotRequired[float]
    point_multiplier: NotRequired[float]
    award_items: NotRequired[list[str]]  # Future: physical rewards


class BadgeData(TypedDict):
    """Type definition for a badge entity."""

    internal_id: str
    name: str
    badge_type: str  # PERIODIC, CUMULATIVE
    occasion_type: NotRequired[str]

    # Assignment
    assigned_to: list[str]  # List of kid UUIDs
    earned_by: list[str]  # List of kid UUIDs who earned it

    # Configuration
    target: BadgeTarget
    reset_schedule: NotRequired[BadgeResetSchedule]
    awards: NotRequired[BadgeAwards]
    tracked_chores: NotRequired[dict[str, list[str]]]  # selected_chores key

    # Linkage
    associated_achievement: NotRequired[str]  # Achievement UUID
    associated_challenge: NotRequired[str]  # Challenge UUID


# =============================================================================
# Kid Nested Types (chore tracking - deepest nesting)
# =============================================================================


class KidChoreDataPeriodEntry(TypedDict, total=False):
    """Period-level stats for a single chore (daily/weekly/monthly/yearly/all_time)."""

    approved: int
    claimed: int
    disapproved: int
    overdue: int
    points: float
    longest_streak: int


class KidChoreDataPeriods(TypedDict, total=False):
    """Period containers for chore tracking.

    Keys within each period dict are date strings "2026-01-18" or "all_time".
    """

    daily: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    weekly: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    monthly: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    yearly: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    all_time: NotRequired[KidChoreDataPeriodEntry]


class KidChoreDataEntry(TypedDict, total=False):
    """Per-chore tracking data for a single kid-chore combination.

    Created dynamically via setdefault() in coordinator methods.
    Key fields are added incrementally as chore is claimed/approved.
    """

    # State tracking (primary)
    state: str  # PENDING, CLAIMED, APPROVED, OVERDUE
    pending_claim_count: NotRequired[int]  # For multi-claim chores
    name: NotRequired[str]  # Denormalized chore name

    # Timestamps
    last_approved: NotRequired[str]  # ISO datetime
    last_claimed: NotRequired[str]  # ISO datetime
    last_disapproved: NotRequired[str]  # ISO datetime
    last_overdue: NotRequired[str]  # ISO datetime
    approval_period_start: NotRequired[str]  # ISO datetime

    # Statistics
    total_count: NotRequired[int]
    total_points: NotRequired[float]

    # Period tracking
    periods: NotRequired[KidChoreDataPeriods]

    # Badge references (which badges track this chore for this kid)
    badge_refs: NotRequired[list[str]]  # List of badge UUIDs

    # Streak tracking
    last_longest_streak_all_time: NotRequired[int]

    # Shared/multi-claim chore tracking (per-kid view)
    claimed_by: NotRequired[
        str | list[str]
    ]  # Who claimed: str for INDEPENDENT/SHARED_FIRST, list for SHARED_ALL
    completed_by: NotRequired[
        str | list[str]
    ]  # Who completed: str for INDEPENDENT/SHARED_FIRST, list for SHARED_ALL


# =============================================================================
# Kid Nested Types (badge progress)
# =============================================================================


class KidBadgeProgress(TypedDict, total=False):
    """Per-badge progress tracking for a kid.

    Created dynamically in _manage_badge_maintenance().
    """

    name: NotRequired[str]  # Denormalized badge name
    badge_type: NotRequired[str]  # PERIODIC or CUMULATIVE
    status: NotRequired[str]  # active, grace, demoted, earned

    # Progress counters
    cycle_count: NotRequired[int]
    days_cycle_count: NotRequired[int]
    days_completed: NotRequired[int]
    chores_completed: NotRequired[int]
    chores_cycle_count: NotRequired[int]
    chores_today: NotRequired[int]
    points_cycle_count: NotRequired[float]
    points_today: NotRequired[float]
    approved_count: NotRequired[int]
    total_count: NotRequired[int]

    # Target info (denormalized from badge)
    target_type: NotRequired[str]
    threshold_value: NotRequired[float]
    overall_progress: NotRequired[float]  # 0.0 to 1.0
    criteria_met: NotRequired[bool]

    # Schedule info
    recurring_frequency: NotRequired[str]
    start_date: NotRequired[str]  # ISO date
    end_date: NotRequired[str]  # ISO date
    last_update_day: NotRequired[str]  # ISO date
    last_awarded: NotRequired[str]  # ISO datetime

    # Chore tracking
    tracked_chores: NotRequired[list[str]]  # Chore UUIDs
    today_completed: NotRequired[list[str]]  # Chore UUIDs completed today
    penalty_applied: NotRequired[bool]

    # Special occasion fields
    occasion_type: NotRequired[str]  # Birthday, holiday, etc.

    # Linked entity fields
    associated_achievement: NotRequired[str]  # Achievement UUID
    associated_challenge: NotRequired[str]  # Challenge UUID


class KidCumulativeBadgeProgress(TypedDict, total=False):
    """Cumulative badge progress tracking for a kid.

    Single structure per kid (not per-badge).
    """

    status: str  # active, grace, demoted
    cycle_points: float
    maintenance_end_date: NotRequired[str]  # ISO date
    maintenance_grace_end_date: NotRequired[str]  # ISO date
    baseline: NotRequired[float]

    # Current badge info (denormalized)
    current_badge_id: NotRequired[str]
    current_badge_name: NotRequired[str]
    current_threshold: NotRequired[float]

    # Next badge info
    next_higher_badge_id: NotRequired[str]
    next_higher_badge_name: NotRequired[str]
    next_higher_threshold: NotRequired[float]
    next_higher_points_needed: NotRequired[float]

    # Demotion info
    next_lower_badge_id: NotRequired[str]
    next_lower_badge_name: NotRequired[str]
    next_lower_threshold: NotRequired[float]

    # Highest earned
    highest_earned_badge_id: NotRequired[str]
    highest_earned_badge_name: NotRequired[str]
    highest_earned_threshold: NotRequired[float]


# =============================================================================
# Kid Nested Types (reward/point tracking)
# =============================================================================


class PeriodicStatsEntry(TypedDict, total=False):
    """Stats entry for a single period (day/week/month/year).

    Used as values in the daily/weekly/monthly/yearly period dicts.
    """

    claimed: int
    approved: int
    disapproved: NotRequired[int]


class KidRewardDataPeriods(TypedDict, total=False):
    """Period containers for reward tracking.

    Keys within each period dict are date strings.
    """

    daily: NotRequired[dict[str, PeriodicStatsEntry]]  # date -> stats
    weekly: NotRequired[dict[str, PeriodicStatsEntry]]
    monthly: NotRequired[dict[str, PeriodicStatsEntry]]
    yearly: NotRequired[dict[str, PeriodicStatsEntry]]


class KidRewardDataEntry(TypedDict, total=False):
    """Per-reward tracking data for a single kid-reward combination."""

    name: NotRequired[str]  # Denormalized reward name
    pending_count: int
    total_claims: NotRequired[int]
    total_approved: NotRequired[int]
    total_disapproved: NotRequired[int]
    total_points_spent: NotRequired[float]
    last_claimed: NotRequired[str]  # ISO datetime
    last_approved: NotRequired[str]  # ISO datetime
    last_disapproved: NotRequired[str]  # ISO datetime
    notification_ids: NotRequired[list[str]]  # For persistent notifications
    periods: NotRequired[KidRewardDataPeriods]


class KidPointStats(TypedDict, total=False):
    """Point earning/spending statistics."""

    # All-time totals (use points_ prefix to match const.py DATA_KID_POINT_STATS_* values)
    points_earned_all_time: float
    points_spent_all_time: float
    points_net_all_time: float
    highest_balance: NotRequired[float]

    # Period breakdowns
    earned_today: NotRequired[float]
    earned_week: NotRequired[float]
    earned_month: NotRequired[float]
    earned_year: NotRequired[float]
    spent_today: NotRequired[float]
    spent_week: NotRequired[float]
    spent_month: NotRequired[float]
    spent_year: NotRequired[float]
    net_today: NotRequired[float]
    net_week: NotRequired[float]
    net_month: NotRequired[float]
    net_year: NotRequired[float]

    # Averages
    avg_per_day_week: NotRequired[float]
    avg_per_day_month: NotRequired[float]
    avg_per_chore: NotRequired[float]

    # Streaks
    earning_streak_current: NotRequired[int]
    earning_streak_longest: NotRequired[int]

    # By source (chores, badges, bonuses, penalties)
    by_source_today: NotRequired[dict[str, float]]
    by_source_week: NotRequired[dict[str, float]]
    by_source_month: NotRequired[dict[str, float]]
    by_source_year: NotRequired[dict[str, float]]
    points_by_source_all_time: NotRequired[dict[str, float]]


class KidChoreStats(TypedDict, total=False):
    """Chore completion statistics."""

    # Totals by period
    approved_today: int
    approved_week: int
    approved_month: int
    approved_year: int
    approved_all_time: int
    claimed_today: NotRequired[int]
    claimed_week: NotRequired[int]
    claimed_month: NotRequired[int]
    claimed_year: NotRequired[int]
    claimed_all_time: NotRequired[int]
    disapproved_today: NotRequired[int]
    disapproved_week: NotRequired[int]
    disapproved_month: NotRequired[int]
    disapproved_year: NotRequired[int]
    disapproved_all_time: NotRequired[int]
    overdue_today: NotRequired[int]
    overdue_week: NotRequired[int]
    overdue_month: NotRequired[int]
    overdue_year: NotRequired[int]
    overdue_all_time: NotRequired[int]

    # Current state counts
    current_approved: NotRequired[int]
    current_claimed: NotRequired[int]
    current_overdue: NotRequired[int]
    current_due_today: NotRequired[int]

    # Points from chores
    total_points_from_chores_today: NotRequired[float]
    total_points_from_chores_week: NotRequired[float]
    total_points_from_chores_month: NotRequired[float]
    total_points_from_chores_year: NotRequired[float]
    total_points_from_chores_all_time: NotRequired[float]

    # Streaks
    longest_streak_all_time: NotRequired[int]
    longest_streak_week: NotRequired[int]
    longest_streak_month: NotRequired[int]
    longest_streak_year: NotRequired[int]

    # Most completed
    most_completed_chore_all_time: NotRequired[str]
    most_completed_chore_week: NotRequired[str]
    most_completed_chore_month: NotRequired[str]
    most_completed_chore_year: NotRequired[str]

    # Averages
    avg_per_day_week: NotRequired[float]
    avg_per_day_month: NotRequired[float]


class BadgesEarnedEntry(TypedDict, total=False):
    """Entry in badges_earned dict."""

    badge_name: str
    last_awarded_date: NotRequired[str]  # ISO datetime
    award_count: int
    periods: NotRequired[KidRewardDataPeriods]  # Reuse structure


# =============================================================================
# KidData Main Type (the largest one)
# =============================================================================


class KidData(TypedDict):
    """Type definition for a kid entity.

    Created via _create_kid() in coordinator.py.
    Many fields are added incrementally via setdefault() during runtime.
    """

    # Core identification
    internal_id: str
    name: str

    # Points
    points: float
    points_multiplier: float

    # Linkage
    ha_user_id: NotRequired[str | None]
    is_shadow: NotRequired[bool]
    linked_parent_id: NotRequired[str | None]

    # Notifications
    enable_notifications: bool
    mobile_notify_service: str
    use_persistent_notifications: bool
    dashboard_language: NotRequired[str]

    # Badge tracking
    badges_earned: dict[str, BadgesEarnedEntry]  # badge_id -> entry
    badge_progress: NotRequired[dict[str, KidBadgeProgress]]  # badge_id -> progress
    cumulative_badge_progress: NotRequired[KidCumulativeBadgeProgress]

    # Chore tracking (the big nested structure)
    chore_data: NotRequired[dict[str, KidChoreDataEntry]]  # chore_id -> entry
    chore_stats: NotRequired[KidChoreStats]

    # Reward tracking
    reward_data: dict[str, KidRewardDataEntry]  # reward_id -> entry

    # Penalty/bonus application tracking
    penalty_applies: dict[str, bool]  # penalty_id -> applied?
    bonus_applies: dict[str, bool]  # bonus_id -> applied?

    # Point statistics
    point_stats: NotRequired[KidPointStats]

    # Current streak (daily approval streak)
    current_streak: NotRequired[int]
    last_streak_date: NotRequired[str]  # ISO date

    # Overdue tracking
    overdue_chores: NotRequired[list[str]]  # Chore UUIDs
    overdue_notifications: NotRequired[dict[str, str]]  # chore_id -> notification_id
    completed_by_other_chores: NotRequired[
        list[str]
    ]  # Shared chores completed by others


# =============================================================================
# Achievement Types
# =============================================================================


class AchievementProgress(TypedDict, total=False):
    """Per-kid achievement progress tracking.

    Stored in achievement_info["progress"][kid_id].
    Used for streak-based and count-based achievements.
    """

    # For streak achievements
    current_streak: int  # Current streak count
    last_date: str | None  # ISO date of last streak contribution

    # For total/count achievements
    count: int  # Total count towards achievement

    # Award status
    awarded: bool  # Whether achievement has been awarded


class AchievementData(TypedDict):
    """Type definition for an achievement entity."""

    internal_id: str
    name: str
    achievement_type: str  # CHORE_COUNT, STREAK, etc.
    criteria: str  # Description of criteria
    description: str
    icon: str
    labels: list[str]

    # Target
    target_value: int
    baseline: NotRequired[int]
    selected_chore_id: NotRequired[str]  # Chore UUID for chore-specific

    # Assignment
    assigned_kids: list[str]  # Kid UUIDs

    # Progress tracking (per-kid)
    progress: dict[str, AchievementProgress]  # kid_id -> progress data
    current_value: NotRequired[dict[str, int]]  # kid_id -> current value

    # Award status
    awarded: dict[str, bool]  # kid_id -> awarded?
    last_awarded_date: NotRequired[dict[str, str]]  # kid_id -> ISO datetime
    reward_points: float


# =============================================================================
# Challenge Types
# =============================================================================


class ChallengeDailyCounts(TypedDict, total=False):
    """Per-kid daily counts for challenges.

    Keys are kid_id (UUID string), values are dict[date_str, int].
    Using total=False because keys are dynamic.
    """


class ChallengeProgress(TypedDict, total=False):
    """Per-kid challenge progress tracking.

    Stored in challenge_info["progress"][kid_id].
    Used for count-based and daily minimum challenges.
    """

    # For count-based challenges
    count: int  # Total count towards challenge target

    # For daily minimum challenges
    daily_counts: dict[str, int]  # ISO date -> count for that day

    # Award status
    awarded: bool  # Whether challenge has been awarded


class ChallengeData(TypedDict):
    """Type definition for a challenge entity."""

    internal_id: str
    name: str
    challenge_type: str  # CHORE_COUNT, DAILY_MIN, etc.
    criteria: str
    description: str
    icon: str
    labels: list[str]

    # Target
    target_value: int
    required_daily: NotRequired[int]  # For daily minimum challenges
    selected_chore_id: NotRequired[str]  # Chore UUID

    # Assignment
    assigned_kids: list[str]

    # Schedule
    start_date: str  # ISO date
    end_date: str  # ISO date

    # Progress tracking
    progress: dict[str, ChallengeProgress]  # kid_id -> progress data
    count: NotRequired[dict[str, int]]  # kid_id -> count
    daily_counts: NotRequired[dict[str, dict[str, int]]]  # kid_id -> date -> count

    # Award status
    awarded: dict[str, bool]  # kid_id -> awarded?
    reward_points: float


# =============================================================================
# Schedule Engine Configuration
# =============================================================================


class ScheduleConfig(TypedDict, total=False):
    """Configuration for RecurrenceEngine in schedule_engine.py.

    Used to calculate next occurrences for chores, badges, and challenges.
    All fields are optional (total=False) to support partial configuration.
    """

    frequency: str  # FREQUENCY_* or PERIOD_*_END constant from const.py
    interval: int  # Interval count for FREQUENCY_CUSTOM (default: 1)
    interval_unit: str  # TIME_UNIT_* constant (days, weeks, months, etc.)
    base_date: str  # ISO datetime string - starting point for calculations
    applicable_days: list[int]  # Weekday integers (0=Mon, 6=Sun) for filtering
    reference_datetime: str  # ISO datetime - "after" reference for next occurrence


# =============================================================================
# Collection Type Aliases (for coordinator data properties)
# =============================================================================

KidsCollection = dict[KidId, KidData]
ChoresCollection = dict[ChoreId, ChoreData]
BadgesCollection = dict[BadgeId, BadgeData]
RewardsCollection = dict[RewardId, RewardData]
PenaltiesCollection = dict[str, PenaltyData]
BonusesCollection = dict[str, BonusData]
ParentsCollection = dict[str, ParentData]
AchievementsCollection = dict[str, AchievementData]
ChallengesCollection = dict[str, ChallengeData]

# Per-kid progress type aliases (used in sensor.py for type annotations)
# These are the per-kid progress entries from the progress dict
# Using union with dict[str, Any] to handle empty dict {} default values
AchievementProgressData = AchievementProgress | dict[str, Any]
ChallengeProgressData = ChallengeProgress | dict[str, Any]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AchievementData",
    # Achievement/Challenge nested types
    "AchievementProgress",
    "AchievementProgressData",
    "AchievementsCollection",
    "BadgeAwards",
    "BadgeData",
    "BadgeId",
    "BadgeResetSchedule",
    # Badge nested types
    "BadgeTarget",
    "BadgesCollection",
    "BadgesEarnedEntry",
    "BonusData",
    "BonusesCollection",
    "ChallengeDailyCounts",
    "ChallengeData",
    "ChallengeProgress",
    "ChallengeProgressData",
    "ChallengesCollection",
    "ChoreData",
    "ChoreId",
    "ChorePerKidApplicableDays",
    "ChorePerKidDailyMultiTimes",
    # Chore nested types
    "ChorePerKidDueDates",
    "ChoresCollection",
    "ISODate",
    "ISODatetime",
    "KidBadgeProgress",
    # Kid nested types
    "KidChoreDataEntry",
    "KidChoreDataPeriodEntry",
    "KidChoreDataPeriods",
    "KidChoreStats",
    "KidCumulativeBadgeProgress",
    # Main entity types
    "KidData",
    # ID type aliases
    "KidId",
    "KidPointStats",
    "KidRewardDataEntry",
    "KidRewardDataPeriods",
    # Collection aliases
    "KidsCollection",
    "ParentData",
    "ParentsCollection",
    "PenaltiesCollection",
    "PenaltyData",
    "PeriodicStatsEntry",
    "RewardData",
    "RewardId",
    "RewardsCollection",
    # Schedule Engine
    "ScheduleConfig",
]
