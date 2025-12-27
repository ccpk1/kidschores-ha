# File: sensor.py
"""Sensors for the KidsChores integration.

This file defines modern sensor entities for each Kid, Chore, Reward, and Badge.
Legacy/optional sensors are imported from sensor_legacy.py.

Sensors Defined in This File (15):

# Modern Kid-Specific Sensors (11)
01. KidChoreStatusSensor
02. KidPointsSensor
03. KidChoresSensor
04. KidBadgeHighestSensor
05. KidBadgeProgressSensor
06. KidRewardStatusSensor
07. KidPenaltyAppliedSensor
08. KidBonusAppliedSensor
09. KidAchievementProgressSensor
10. KidChallengeProgressSensor
11. KidDashboardHelperSensor

# Modern System-Level Sensors (4)
12. SystemBadgeSensor
13. SystemChoreSharedStateSensor
14. SystemAchievementSensor
15. SystemChallengeSensor

Legacy Sensors Imported from sensor_legacy.py (11):
- KidMaxPointsEverSensor
- KidChoreStreakSensor
- KidPointsEarnedDailySensor
- KidPointsEarnedWeeklySensor
- KidPointsEarnedMonthlySensor
- SystemChoreApprovalsSensor
- SystemChoreApprovalsDailySensor
- SystemChoreApprovalsWeeklySensor
- SystemChoreApprovalsMonthlySensor
- SystemChoresPendingApprovalSensor
- SystemRewardsPendingApprovalSensor
"""

from datetime import datetime
from typing import Any, cast

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from . import const
from . import kc_helpers as kh
from .coordinator import KidsChoresDataCoordinator
from .entity import KidsChoresCoordinatorEntity
from .sensor_legacy import (
    KidChoreStreakSensor,
    KidPointsEarnedDailySensor,
    KidPointsEarnedMonthlySensor,
    KidPointsEarnedWeeklySensor,
    KidPointsMaxEverSensor,
    SystemChoreApprovalsDailySensor,
    SystemChoreApprovalsMonthlySensor,
    SystemChoreApprovalsSensor,
    SystemChoreApprovalsWeeklySensor,
    SystemChoresPendingApprovalSensor,
    SystemRewardsPendingApprovalSensor,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up sensors for KidsChores integration."""
    data = hass.data[const.DOMAIN][entry.entry_id]
    coordinator: KidsChoresDataCoordinator = data[const.DATA_COORDINATOR]

    points_label = entry.options.get(
        const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
    )
    points_icon = entry.options.get(const.CONF_POINTS_ICON, const.DEFAULT_POINTS_ICON)
    show_legacy_entities = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
    entities = []

    # Legacy pending approval sensors (optional)
    if show_legacy_entities:
        entities.append(SystemChoresPendingApprovalSensor(coordinator, entry))
        entities.append(SystemRewardsPendingApprovalSensor(coordinator, entry))

    # For each kid, add standard sensors
    for kid_id, kid_info in coordinator.kids_data.items():
        kid_name = kh.get_entity_name_or_log_error(
            "kid", kid_id, kid_info, const.DATA_KID_NAME
        )
        if not kid_name:
            continue

        # Points counter sensor
        entities.append(
            KidPointsSensor(
                coordinator, entry, kid_id, kid_name, points_label, points_icon
            )
        )
        # Chores sensor with all stats (like points sensor)
        entities.append(KidChoresSensor(coordinator, entry, kid_id, kid_name))

        # Legacy chore completion sensors (optional)
        if show_legacy_entities:
            entities.append(
                SystemChoreApprovalsSensor(coordinator, entry, kid_id, kid_name)
            )
            entities.append(
                SystemChoreApprovalsDailySensor(coordinator, entry, kid_id, kid_name)
            )
            entities.append(
                SystemChoreApprovalsWeeklySensor(coordinator, entry, kid_id, kid_name)
            )
            entities.append(
                SystemChoreApprovalsMonthlySensor(coordinator, entry, kid_id, kid_name)
            )

        # Kid Highest Badge
        entities.append(KidBadgeHighestSensor(coordinator, entry, kid_id, kid_name))

        # Legacy points earned sensors (optional)
        if show_legacy_entities:
            # Points obtained per Kid during the day
            entities.append(
                KidPointsEarnedDailySensor(
                    coordinator, entry, kid_id, kid_name, points_label, points_icon
                )
            )

            # Points obtained per Kid during the week
            entities.append(
                KidPointsEarnedWeeklySensor(
                    coordinator, entry, kid_id, kid_name, points_label, points_icon
                )
            )

            # Points obtained per Kid during the month
            entities.append(
                KidPointsEarnedMonthlySensor(
                    coordinator, entry, kid_id, kid_name, points_label, points_icon
                )
            )

        # Legacy maximum points sensor (optional)
        if show_legacy_entities:
            entities.append(
                KidPointsMaxEverSensor(
                    coordinator, entry, kid_id, kid_name, points_label, points_icon
                )
            )

        # Penalty Applies
        for penalty_id, penalty_info in coordinator.penalties_data.items():
            penalty_name = kh.get_entity_name_or_log_error(
                "penalty", penalty_id, penalty_info, const.DATA_PENALTY_NAME
            )
            if not penalty_name:
                continue
            entities.append(
                KidPenaltyAppliedSensor(
                    coordinator, entry, kid_id, kid_name, penalty_id, penalty_name
                )
            )

        # Bonus Applies
        for bonus_id, bonus_info in coordinator.bonuses_data.items():
            bonus_name = kh.get_entity_name_or_log_error(
                "bonus", bonus_id, bonus_info, const.DATA_BONUS_NAME
            )
            if not bonus_name:
                continue
            entities.append(
                KidBonusAppliedSensor(
                    coordinator, entry, kid_id, kid_name, bonus_id, bonus_name
                )
            )

        # KidBadgeProgressSensor Progress per Kid for each non-cumulative badge
        badge_progress_data = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
        for badge_id, progress_info in badge_progress_data.items():
            badge_type = progress_info.get(const.DATA_KID_BADGE_PROGRESS_TYPE)
            if badge_type != const.BADGE_TYPE_CUMULATIVE:
                badge_name = kh.get_entity_name_or_log_error(
                    "badge", badge_id, progress_info, const.DATA_KID_BADGE_PROGRESS_NAME
                )
                if not badge_name:
                    continue
                entities.append(
                    KidBadgeProgressSensor(
                        coordinator, entry, kid_id, kid_name, badge_id, badge_name
                    )
                )

        # Achivement Progress per Kid
        for achievement_id, achievement in coordinator.achievements_data.items():
            if kid_id in achievement.get(const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, []):
                achievement_name = kh.get_entity_name_or_log_error(
                    "achievement",
                    achievement_id,
                    achievement,
                    const.DATA_ACHIEVEMENT_NAME,
                )
                if not achievement_name:
                    continue
                entities.append(
                    KidAchievementProgressSensor(
                        coordinator,
                        entry,
                        kid_id,
                        kid_name,
                        achievement_id,
                        achievement_name,
                    )
                )

        # Challenge Progress per Kid
        for challenge_id, challenge in coordinator.challenges_data.items():
            if kid_id in challenge.get(const.DATA_CHALLENGE_ASSIGNED_KIDS, []):
                challenge_name = kh.get_entity_name_or_log_error(
                    "challenge", challenge_id, challenge, const.DATA_CHALLENGE_NAME
                )
                if not challenge_name:
                    continue
                entities.append(
                    KidChallengeProgressSensor(
                        coordinator,
                        entry,
                        kid_id,
                        kid_name,
                        challenge_id,
                        challenge_name,
                    )
                )

        # Highest Streak Sensor per Kid
        # Legacy streak sensor (optional)
        if show_legacy_entities:
            entities.append(KidChoreStreakSensor(coordinator, entry, kid_id, kid_name))

        # Dashboard helper sensor will be created after all individual entities

    # For each chore assigned to each kid, add a KidChoreStatusSensor
    for chore_id, chore_info in coordinator.chores_data.items():
        chore_name = kh.get_entity_name_or_log_error(
            "chore", chore_id, chore_info, const.DATA_CHORE_NAME
        )
        if not chore_name:
            continue
        assigned_kids_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        for kid_id in assigned_kids_ids:
            kid_data = coordinator.kids_data.get(kid_id, {})
            kid_name = kh.get_entity_name_or_log_error(
                "kid", kid_id, kid_data, const.DATA_KID_NAME
            )
            if not kid_name:
                continue
            entities.append(
                KidChoreStatusSensor(
                    coordinator, entry, kid_id, kid_name, chore_id, chore_name
                )
            )

    # For each shared chore, add a global state sensor
    for chore_id, chore_info in coordinator.chores_data.items():
        if chore_info.get(const.DATA_CHORE_SHARED_CHORE, False):
            chore_name = kh.get_entity_name_or_log_error(
                "chore", chore_id, chore_info, const.DATA_CHORE_NAME
            )
            if not chore_name:
                continue
            entities.append(
                SystemChoreSharedStateSensor(coordinator, entry, chore_id, chore_name)
            )

    # For each Reward, add a KidRewardStatusSensor
    for reward_id, reward_info in coordinator.rewards_data.items():
        reward_name = kh.get_entity_name_or_log_error(
            "reward", reward_id, reward_info, const.DATA_REWARD_NAME
        )
        if not reward_name:
            continue

        # For each kid, create the reward status sensor
        for kid_id, kid_info in coordinator.kids_data.items():
            kid_name = kh.get_entity_name_or_log_error(
                "kid", kid_id, kid_info, const.DATA_KID_NAME
            )
            if not kid_name:
                continue
            entities.append(
                KidRewardStatusSensor(
                    coordinator, entry, kid_id, kid_name, reward_id, reward_name
                )
            )

    # For each Badge, add a BadgeSensor
    for badge_id, badge_info in coordinator.badges_data.items():
        badge_name = kh.get_entity_name_or_log_error(
            "badge", badge_id, badge_info, const.DATA_BADGE_NAME
        )
        if not badge_name:
            continue
        entities.append(SystemBadgeSensor(coordinator, entry, badge_id, badge_name))

    # For each Achievement, add an AchievementSensor
    for achievement_id, achievement in coordinator.achievements_data.items():
        achievement_name = kh.get_entity_name_or_log_error(
            "achievement", achievement_id, achievement, const.DATA_ACHIEVEMENT_NAME
        )
        if not achievement_name:
            continue
        entities.append(
            SystemAchievementSensor(
                coordinator, entry, achievement_id, achievement_name
            )
        )

    # For each Challenge, add a ChallengeSensor
    for challenge_id, challenge in coordinator.challenges_data.items():
        challenge_name = kh.get_entity_name_or_log_error(
            "challenge", challenge_id, challenge, const.DATA_CHALLENGE_NAME
        )
        if not challenge_name:
            continue
        entities.append(
            SystemChallengeSensor(coordinator, entry, challenge_id, challenge_name)
        )

    # Dashboard helper sensors: Created last to ensure all referenced entities exist
    # This prevents entity ID lookup failures during initial setup
    for kid_id, kid_data in coordinator.kids_data.items():
        kid_name = kh.get_entity_name_or_log_error(
            "kid", kid_id, kid_data, const.DATA_KID_NAME
        )
        if not kid_name:
            continue
        entities.append(
            KidDashboardHelperSensor(coordinator, entry, kid_id, kid_name, points_label)
        )

    async_add_entities(entities)


# ------------------------------------------------------------------------------------------
class KidChoreStatusSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor for chore status: pending/claimed/approved/etc.

    Tracks individual kid's chore state independent of shared chore global state.
    Provides comprehensive attributes including per-chore statistics (claims, approvals,
    streaks, points earned), chore configuration, and button entity IDs for UI integration.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORE_STATUS_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        chore_id: str,
        chore_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
        """

        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_CHORE_STATUS_SENSOR}{chore_name}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_CHORE_NAME: chore_name,
        }
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> Any:
        """Return the chore's state based on shared or individual tracking.

        Priority order: approved > claimed > overdue > pending.
        Always returns kid's individual status, not shared chore global state.
        """
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})

        # The status of the kids chore should always be their own status.
        # It's only global status that would show independent or in-part
        if self._chore_id in kid_info.get(const.DATA_KID_APPROVED_CHORES, []):
            return const.CHORE_STATE_APPROVED
        elif self._chore_id in kid_info.get(const.DATA_KID_CLAIMED_CHORES, []):
            return const.CHORE_STATE_CLAIMED
        elif self._chore_id in kid_info.get(const.DATA_KID_OVERDUE_CHORES, []):
            return const.CHORE_STATE_OVERDUE
        else:
            return const.CHORE_STATE_PENDING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include points, description, etc. Uses new per-chore data where possible.

        Provides comprehensive chore metadata including:
        - Configuration: points, labels, assigned kids, recurrence, due date
        - Statistics: all-time and daily claims/approvals/streaks via periods data structure
        - UI Integration: button entity IDs for claim/approve/disapprove actions
        - State tracking: individual vs shared/global state differentiation
        """
        chore_info = self.coordinator.chores_data.get(self._chore_id, {})
        shared = chore_info.get(const.DATA_CHORE_SHARED_CHORE, False)
        global_state = chore_info.get(const.DATA_CHORE_STATE, const.CHORE_STATE_UNKNOWN)

        assigned_kids_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        assigned_kids_names = [
            kh.get_kid_name_by_id(self.coordinator, k_id)
            or f"{const.TRANS_KEY_LABEL_KID} {k_id}"
            for k_id in assigned_kids_ids
        ]

        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
            self._chore_id, {}
        )
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        all_time_stats = periods.get(
            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
        ).get(const.PERIOD_ALL_TIME, {})

        # Use new per-chore data for counts and streaks
        claims_count = all_time_stats.get(
            const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, const.DEFAULT_ZERO
        )
        approvals_count = all_time_stats.get(
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO
        )

        # Get today's and yesterday's ISO dates
        today_local_iso = kh.get_today_local_date().isoformat()
        yesterday_local_iso = kh.adjust_datetime_by_interval(
            today_local_iso,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=-1,
            require_future=False,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )

        daily_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})

        # Try to get the current streak from today's data; if not present, fallback to yesterday's
        current_streak = daily_periods.get(today_local_iso, {}).get(
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
        ) or daily_periods.get(yesterday_local_iso, {}).get(
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, const.DEFAULT_ZERO
        )

        highest_streak = all_time_stats.get(
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, const.DEFAULT_ZERO
        )
        points_earned = all_time_stats.get(
            const.DATA_KID_CHORE_DATA_PERIOD_POINTS, const.DEFAULT_ZERO
        )
        overdue_count = all_time_stats.get(
            const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, const.DEFAULT_ZERO
        )
        disapproved_count = all_time_stats.get(
            const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, const.DEFAULT_ZERO
        )
        last_longest_streak_date = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME
        )
        last_claimed = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_CLAIMED)
        last_completed = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)

        stored_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes = {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_DESCRIPTION: chore_info.get(
                const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_KIDS: assigned_kids_names,
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_DEFAULT_POINTS: chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
            ),
            const.ATTR_PARTIAL_ALLOWED: chore_info.get(
                const.DATA_CHORE_PARTIAL_ALLOWED, False
            ),
            const.ATTR_ALLOW_MULTIPLE_CLAIMS_PER_DAY: chore_info.get(
                const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY, False
            ),
            const.ATTR_CHORE_POINTS_EARNED: points_earned,
            const.ATTR_CHORE_APPROVALS_COUNT: approvals_count,
            const.ATTR_CHORE_CLAIMS_COUNT: claims_count,
            const.ATTR_CHORE_DISAPPROVED_COUNT: disapproved_count,
            const.ATTR_CHORE_OVERDUE_COUNT: overdue_count,
            const.ATTR_CHORE_CURRENT_STREAK: current_streak,
            const.ATTR_CHORE_HIGHEST_STREAK: highest_streak,
            const.ATTR_CHORE_LAST_LONGEST_STREAK_DATE: last_longest_streak_date,
            const.ATTR_LAST_CLAIMED: last_claimed,
            const.ATTR_LAST_COMPLETED: last_completed,
            const.ATTR_SHARED_CHORE: shared,
            const.ATTR_GLOBAL_STATE: global_state,
            const.ATTR_DUE_DATE: chore_info.get(
                const.DATA_CHORE_DUE_DATE, const.TRANS_KEY_DISPLAY_DUE_DATE_NOT_SET
            ),
            const.ATTR_RECURRING_FREQUENCY: chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.SENTINEL_NONE_TEXT
            ),
            const.ATTR_APPLICABLE_DAYS: chore_info.get(
                const.DATA_CHORE_APPLICABLE_DAYS, []
            ),
        }

        if (
            chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY)
            == const.FREQUENCY_CUSTOM
        ):
            attributes[const.ATTR_CUSTOM_FREQUENCY_INTERVAL] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL
            )
            attributes[const.ATTR_CUSTOM_FREQUENCY_UNIT] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT
            )

        # Show today's approvals if allowed
        if chore_info.get(const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY, False):
            today_approvals = (
                periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})
                .get(kh.get_today_local_date().isoformat(), {})
                .get(const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO)
            )
            attributes[const.ATTR_CHORE_APPROVALS_TODAY] = today_approvals

        # Add claim, approve, disapprove button entity ids to attributes for direct ui access.
        button_types = [
            (
                const.BUTTON_KC_UID_SUFFIX_APPROVE,
                const.ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
            ),
            (
                const.BUTTON_KC_UID_SUFFIX_DISAPPROVE,
                const.ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID,
            ),
            (const.BUTTON_KC_UID_SUFFIX_CLAIM, const.ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID),
        ]
        button_entity_ids = {}
        try:
            entity_registry = async_get(self.hass)
            for suffix, attr_name in button_types:
                unique_id = (
                    f"{self._entry.entry_id}_{self._kid_id}_{self._chore_id}{suffix}"
                )
                entity_id = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, unique_id
                )
                button_entity_ids[attr_name] = entity_id
        except (KeyError, ValueError, AttributeError):
            for _, attr_name in button_types:
                button_entity_ids[attr_name] = None

        # Add button entity IDs to the attributes
        attributes.update(button_entity_ids)

        return attributes

    @property
    def icon(self) -> str | None:
        """Return the icon based on chore state.

        Maps chore status to an appropriate Material Design Icon:
        - pending: checkbox-blank (not started)
        - claimed: clipboard-check (kid claims)
        - approved: checkbox-marked-circle (parent approves)
        - overdue: alert-circle (not done in time)
        - fallback: chore's custom icon or default
        """
        state = self.native_value
        if state == const.CHORE_STATE_PENDING:
            return "mdi:checkbox-blank-circle-outline"
        elif state == const.CHORE_STATE_CLAIMED:
            return "mdi:clipboard-check-outline"
        elif state == const.CHORE_STATE_APPROVED:
            return "mdi:checkbox-marked-circle-auto-outline"
        elif state == const.CHORE_STATE_OVERDUE:
            return "mdi:alert-circle-outline"

        # Fallback: use chore's custom icon or default
        chore_info = self.coordinator.chores_data.get(self._chore_id, {})
        return chore_info.get(const.DATA_CHORE_ICON, const.DEFAULT_CHORE_SENSOR_ICON)


# ------------------------------------------------------------------------------------------
class KidPointsSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor for a kid's total points balance.

    Primary currency sensor - tracks current spendable points balance. Uses
    MEASUREMENT state class for graphing. Exposes comprehensive point statistics
    in attributes including earnings, spending, bonuses, and penalties.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_POINTS_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: User-configured label for points (e.g., "Points", "Stars").
            points_icon: User-configured icon for points display.
        """

        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = (
            f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_SENSOR}"
        )
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_POINTS: self._points_label,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_POINTS_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> Any:
        """Return the kid's total points."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        return kid_info.get(const.DATA_KID_POINTS, const.DEFAULT_ZERO)

    @property
    def native_unit_of_measurement(self):
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str:
        """Return range-based icon based on current points.

        Maps point levels to icons:
        - 0-49 points: star-outline (starting out)
        - 50-99 points: star-half-full (making progress)
        - 100+ points: star (achieved!)
        - Custom config icon if set, otherwise defaults above
        """
        # Use custom icon if configured
        if self._points_icon:
            return self._points_icon

        # Range-based icon selection
        current_points = self.native_value or 0
        if current_points >= 100:
            return "mdi:star"
        elif current_points >= 50:
            return "mdi:star-half-full"
        else:
            return "mdi:star-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose all point stats as attributes.

        Dynamically includes all DATA_KID_POINT_STATS fields prefixed with
        'point_stat_' for frontend access to detailed breakdowns (earned, spent,
        bonuses, penalties, sources, etc.).
        """
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
        attributes = {
            const.ATTR_DESCRIPTION: "Current point balance - earn from chores, spend on rewards",
            const.ATTR_KID_NAME: self._kid_name,
        }
        # Add all point stats as attributes, prefixed for clarity and sorted alphabetically
        for key in sorted(point_stats.keys()):
            attributes[f"point_stat_{key}"] = point_stats[key]
        return dict(sorted(attributes.items()))


# ------------------------------------------------------------------------------------------
class KidChoresSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor showing chores count with all chore statistics as attributes.

    This sensor provides a central view of all chore-related metrics for a kid,
    similar to how KidPointsSensor works for points tracking.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = (
            f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_CHORES_SENSOR}"
        )
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        self._attr_icon = const.DEFAULT_COMPLETED_CHORES_TOTAL_SENSOR_ICON
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_CHORES_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> Any:
        """Return the total number of chores completed by the kid."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        return stats.get(
            const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, const.DEFAULT_ZERO
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose all chore stats as attributes.

        Dynamically includes all DATA_KID_CHORE_STATS fields prefixed with
        'chore_stat_' for frontend access (approved, claimed, overdue counts, etc.).
        """
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        attributes = {
            const.ATTR_KID_NAME: self._kid_name,
        }
        # Add all chore stats as attributes, prefixed for clarity and sorted alphabetically
        for key in sorted(stats.keys()):
            attributes[f"chore_stat_{key}"] = stats[key]
        return dict(sorted(attributes.items()))


# ------------------------------------------------------------------------------------------
class KidBadgeHighestSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor that returns the highest cumulative badge a kid currently has,
    and calculates how many points are needed to reach the next cumulative badge.

    Tracks cumulative badge progression including maintenance requirements, grace periods,
    baseline/cycle points, and provides comprehensive badge metadata in attributes.
    Icon dynamically reflects the current highest badge.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_KIDS_HIGHEST_BADGE_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_HIGHEST_BADGE_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_HIGHEST_BADGE_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> str:
        """Return the badge name of the highest-threshold badge the kid has earned."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        cumulative_badge_progress_info = kid_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        )
        highest_badge_name = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        return highest_badge_name

    @property
    def icon(self):
        """Return the icon for the highest badge."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        cumulative_badge_progress_info = kid_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        )
        highest_badge_id = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        highest_badge_info = self.coordinator.badges_data.get(highest_badge_id, {})
        highest_badge_icon = highest_badge_info.get(
            const.DATA_BADGE_ICON, const.DEFAULT_TROPHY_ICON
        )
        return highest_badge_icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Provide additional details about the highest cumulative badge,
        including the points needed to reach the next cumulative badge,
        reset schedule, maintenance rules, description, and awards if present.
        Also shows baseline points, cycle points, grace_end_date, and points to maintenance if applicable.
        """
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})

        # Defensive: Handle badges_earned as either dict (v42+) or list (legacy v41)
        badges_earned_data = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
        if isinstance(badges_earned_data, dict):
            # V42+ format: dict of badge_id -> badge_info
            earned_badge_list = [
                badge_info.get(const.DATA_KID_BADGES_EARNED_NAME)
                for badge_info in badges_earned_data.values()
            ]
        elif isinstance(badges_earned_data, list):
            # Legacy v41 format: list of badge name strings (e.g., ["Badge 1", "Badge 2"])
            earned_badge_list = badges_earned_data
        else:
            # Fallback: empty list
            earned_badge_list = []

        cumulative_badge_progress_info = kid_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        )
        current_badge_id = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        current_badge_name = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        highest_earned_badge_id = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        highest_earned_badge_name = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        next_higher_badge_id = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        next_higher_badge_name = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        next_lower_badge_id = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID,
            const.SENTINEL_NONE_TEXT,
        )
        next_lower_badge_name = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME,
            const.SENTINEL_NONE_TEXT,
        )
        badge_status = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.SENTINEL_NONE_TEXT,
        )
        highest_badge_threshold_value = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD,
            const.DEFAULT_ZERO,
        )
        points_to_next_badge = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED,
            const.DEFAULT_ZERO,
        )
        baseline_points = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE,
            const.DEFAULT_ZERO,
        )
        cycle_points = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS,
            const.DEFAULT_ZERO,
        )
        grace_end_date = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE,
            None,
        )

        current_badge_info = self.coordinator.badges_data.get(current_badge_id, {})

        stored_labels = current_badge_info.get(const.DATA_BADGE_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        # Get last awarded date and award count for the current badge (if earned)
        # Defensive: Handle badges_earned as either dict (v42+) or list (legacy v41)
        badges_earned_data = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
        if isinstance(badges_earned_data, dict):
            badge_earned = badges_earned_data.get(current_badge_id, {})
        else:
            # Legacy v41: list format, no per-badge metadata
            badge_earned = {}

        last_awarded_date = badge_earned.get(
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED, const.SENTINEL_NONE
        )
        award_count = badge_earned.get(
            const.DATA_KID_BADGES_EARNED_AWARD_COUNT, const.DEFAULT_ZERO
        )

        extra_attrs = {}
        # Add description if present
        description = current_badge_info.get(const.DATA_BADGE_DESCRIPTION, "")
        if description:
            extra_attrs[const.DATA_BADGE_DESCRIPTION] = description

        # Add baseline points, cycle points, and grace_end_date using constants
        extra_attrs[const.ATTR_BADGE_CUMULATIVE_BASELINE_POINTS] = baseline_points
        extra_attrs[const.ATTR_BADGE_CUMULATIVE_CYCLE_POINTS] = cycle_points

        target_info = current_badge_info.get(const.DATA_BADGE_TARGET, {})

        # maintenance_rules is an int inside target_info
        maintenance_rules = target_info.get(const.DATA_BADGE_MAINTENANCE_RULES, 0)
        maintenance_end_date = cumulative_badge_progress_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE, None
        )
        if maintenance_rules > 0 and maintenance_end_date:
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_MAINTENANCE_END_DATE] = (
                maintenance_end_date
            )
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_GRACE_END_DATE] = grace_end_date
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_MAINTENANCE_POINTS_REQUIRED] = (
                maintenance_rules
            )
            points_to_maintenance = max(0, maintenance_rules - cycle_points)
            extra_attrs[const.ATTR_BADGE_CUMULATIVE_POINTS_TO_MAINTENANCE] = (
                points_to_maintenance
            )

        # Add reset_schedule fields if recurring_frequency is present
        reset_schedule = current_badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        if reset_schedule:
            extra_attrs[const.DATA_BADGE_RESET_SCHEDULE] = reset_schedule

        # Add Target fields if present
        if target_info:
            extra_attrs[const.DATA_BADGE_TARGET] = target_info

        # Add awards if present
        awards_info = current_badge_info.get(const.DATA_BADGE_AWARDS, {})
        if awards_info:
            extra_attrs[const.DATA_BADGE_AWARDS] = awards_info

        return {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_ALL_EARNED_BADGES: earned_badge_list,
            const.ATTR_HIGHEST_BADGE_THRESHOLD_VALUE: highest_badge_threshold_value,
            const.ATTR_POINTS_TO_NEXT_BADGE: points_to_next_badge,
            const.ATTR_CURRENT_BADGE_ID: current_badge_id,
            const.ATTR_CURRENT_BADGE_NAME: current_badge_name,
            const.ATTR_HIGHEST_EARNED_BADGE_ID: highest_earned_badge_id,
            const.ATTR_HIGHEST_EARNED_BADGE_NAME: highest_earned_badge_name,
            const.ATTR_NEXT_HIGHER_BADGE_ID: next_higher_badge_id,
            const.ATTR_NEXT_HIGHER_BADGE_NAME: next_higher_badge_name,
            const.ATTR_NEXT_LOWER_BADGE_ID: next_lower_badge_id,
            const.ATTR_NEXT_LOWER_BADGE_NAME: next_lower_badge_name,
            const.ATTR_BADGE_STATUS: badge_status,
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED: last_awarded_date,
            const.DATA_KID_BADGES_EARNED_AWARD_COUNT: award_count,
            **extra_attrs,
        }


# ------------------------------------------------------------------------------------------
class KidBadgeProgressSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Badge Progress Sensor for a kid's progress on a specific non-cumulative badge.

    Tracks individual badge progress as percentage (0-100). Supports achievement,
    challenge, daily, and periodic badge types. Provides comprehensive progress
    metadata including criteria met, tracked chores, start/end dates, and award history.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "badge_progress_sensor"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        badge_id: str,
        badge_name: str,
    ):
        """Initialize the KidBadgeProgressSensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            badge_id: Unique identifier for the badge.
            badge_name: Display name of the badge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._badge_id = badge_id
        self._badge_name = badge_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_BADGE_NAME: badge_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_BADGE_PROGRESS_SENSOR}{badge_name}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> float:
        """Return the badge's overall progress as a percentage."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        badge_progress = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {}).get(
            self._badge_id, {}
        )
        progress = badge_progress.get(
            const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS, 0.0
        )
        return round(progress * 100, 1)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the badge progress details as attributes."""
        badge_info = self.coordinator.badges_data.get(self._badge_id, {})
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        badge_progress = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {}).get(
            self._badge_id, {}
        )

        # Defensive: Handle badges_earned as either dict (v42+) or list (legacy v41)
        badges_earned_data = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
        if isinstance(badges_earned_data, dict):
            badge_earned = badges_earned_data.get(self._badge_id, {})
        else:
            # Legacy v41: list format, no per-badge metadata
            badge_earned = {}

        last_awarded_date = badge_earned.get(
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED, const.SENTINEL_NONE
        )
        award_count = badge_earned.get(
            const.DATA_KID_BADGES_EARNED_AWARD_COUNT, const.DEFAULT_ZERO
        )

        # Build a dictionary with only the requested fields
        attributes = {
            const.ATTR_KID_NAME: self._kid_name,
            const.DATA_KID_BADGE_PROGRESS_NAME: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_NAME
            ),
            const.DATA_KID_BADGE_PROGRESS_TYPE: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_TYPE
            ),
            const.DATA_KID_BADGE_PROGRESS_STATUS: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_STATUS
            ),
            const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE
            ),
            const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE
            ),
            const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY
            ),
            const.DATA_KID_BADGE_PROGRESS_START_DATE: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_START_DATE
            ),
            const.DATA_KID_BADGE_PROGRESS_END_DATE: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_END_DATE
            ),
            const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY
            ),
            const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS
            ),
            const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET: badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET
            ),
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED: last_awarded_date,
            const.DATA_KID_BADGES_EARNED_AWARD_COUNT: award_count,
        }

        attributes[const.ATTR_DESCRIPTION] = badge_info.get(
            const.DATA_BADGE_DESCRIPTION, const.SENTINEL_EMPTY
        )

        # Convert tracked chore IDs to friendly names and add to attributes
        tracked_chore_ids = attributes.get(
            const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES, []
        )
        if tracked_chore_ids:
            chore_names = [
                self.coordinator.chores_data.get(chore_id, {}).get(
                    const.DATA_CHORE_NAME, chore_id
                )
                for chore_id in tracked_chore_ids
            ]
            attributes[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = chore_names

        return attributes

    @property
    def icon(self) -> str:
        """Return the icon for the badge."""
        badge_info = self.coordinator.badges_data.get(self._badge_id, {})
        return badge_info.get(const.DATA_BADGE_ICON, const.DEFAULT_BADGE_ICON)


# ------------------------------------------------------------------------------------------
class SystemBadgeSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor representing a single badge in KidsChores.

    Provides system-wide badge configuration and metadata including badge type
    (cumulative, achievement, challenge, daily, periodic, special), target values,
    associated achievements/challenges, tracked chores, and award items (points,
    rewards, bonuses, penalties, multipliers). Tracks which kids have earned the
    badge and which kids are assigned to it. Supports occasion-based badges for
    special events.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_BADGE_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        badge_id: str,
        badge_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            badge_id: Unique identifier for the badge.
            badge_name: Display name of the badge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._badge_id = badge_id
        self._badge_name = badge_name
        self._attr_unique_id = (
            f"{entry.entry_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_SENSOR}"
        )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_BADGE_NAME: badge_name
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{badge_name}{const.SENSOR_KC_EID_SUFFIX_BADGE_SENSOR}"
        self._attr_device_info = kh.create_system_device_info(entry)

    @property
    def native_value(self) -> int:
        """State: number of kids who have earned this badge."""
        badge_info = self.coordinator.badges_data.get(self._badge_id, {})
        kids_earned_ids = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
        return len(kids_earned_ids)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Full badge info, including per-kid earned stats and periods."""
        badge_info = self.coordinator.badges_data.get(self._badge_id, {})
        attributes = {}

        # Basic badge info
        attributes[const.ATTR_DESCRIPTION] = badge_info.get(
            const.DATA_BADGE_DESCRIPTION, const.SENTINEL_EMPTY
        )
        attributes[const.ATTR_BADGE_TYPE] = badge_info.get(
            const.DATA_BADGE_TYPE, const.BADGE_TYPE_CUMULATIVE
        )
        attributes[const.ATTR_LABELS] = [
            kh.get_friendly_label(self.hass, label)
            for label in badge_info.get(const.DATA_BADGE_LABELS, [])
        ]
        # Per-kid earned stats
        kids_earned_ids = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
        kids_earned = []
        for kid_id in kids_earned_ids:
            kid_info = self.coordinator.kids_data.get(kid_id)
            if not kid_info:
                continue
            kids_earned.append(kid_info.get(const.DATA_KID_NAME, kid_id))

        attributes[const.ATTR_KIDS_EARNED] = kids_earned

        # Per-kid assigned stats
        kids_assigned_ids = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
        kids_assigned = []
        for kid_id in kids_assigned_ids:
            kid_info = self.coordinator.kids_data.get(kid_id)
            if not kid_info:
                continue
            kids_assigned.append(kid_info.get(const.DATA_KID_NAME, kid_id))

        attributes[const.ATTR_KIDS_ASSIGNED] = kids_assigned

        attributes[const.ATTR_TARGET] = badge_info.get(const.DATA_BADGE_TARGET, None)
        attributes[const.ATTR_ASSOCIATED_ACHIEVEMENT] = badge_info.get(
            const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT, None
        )
        attributes[const.ATTR_ASSOCIATED_CHALLENGE] = badge_info.get(
            const.DATA_BADGE_ASSOCIATED_CHALLENGE, None
        )
        occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE, None)
        if occasion_type:
            attributes[const.ATTR_OCCASION_TYPE] = occasion_type

        # Get tracked chores from nested structure: tracked_chores.selected_chores
        tracked_chores = badge_info.get(const.DATA_BADGE_TRACKED_CHORES, {})
        selected_chore_ids = tracked_chores.get(
            const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
        )
        attributes[const.ATTR_REQUIRED_CHORES] = [
            self.coordinator.chores_data.get(chore_id, {}).get(
                const.DATA_CHORE_NAME, chore_id
            )
            for chore_id in selected_chore_ids
        ]

        # Awards info
        awards_data = badge_info.get(const.DATA_BADGE_AWARDS, {})

        # Add friendly names for award items
        award_items = awards_data.get(const.DATA_BADGE_AWARDS_AWARD_ITEMS, [])
        friendly_award_names = []
        for item in award_items:
            if item.startswith(const.AWARD_ITEMS_PREFIX_REWARD):
                reward_id = item.split(":", 1)[1]
                reward_info = self.coordinator.rewards_data.get(reward_id, {})
                friendly_name = reward_info.get(
                    const.DATA_REWARD_NAME, f"Reward: {reward_id}"
                )
                friendly_award_names.append(
                    f"{const.AWARD_ITEMS_PREFIX_REWARD}{friendly_name}"
                )
            elif item.startswith(const.AWARD_ITEMS_PREFIX_BONUS):
                bonus_id = item.split(":", 1)[1]
                bonus_info = self.coordinator.bonuses_data.get(bonus_id, {})
                friendly_name = bonus_info.get(
                    const.DATA_BONUS_NAME, f"Bonus: {bonus_id}"
                )
                friendly_award_names.append(
                    f"{const.AWARD_ITEMS_PREFIX_BONUS}{friendly_name}"
                )
            elif item.startswith(const.AWARD_ITEMS_PREFIX_PENALTY):
                penalty_id = item.split(":", 1)[1]
                penalty_info = self.coordinator.penalties_data.get(penalty_id, {})
                friendly_name = penalty_info.get(
                    const.DATA_PENALTY_NAME, f"Penalty: {penalty_id}"
                )
                friendly_award_names.append(
                    f"{const.AWARD_ITEMS_PREFIX_PENALTY}{friendly_name}"
                )
            elif item == const.AWARD_ITEMS_KEY_POINTS:
                award_points = awards_data.get(const.DATA_BADGE_AWARDS_AWARD_POINTS, 0)
                friendly_award_names.append(f"Points: {award_points}")
            elif item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER:
                points_multiplier = awards_data.get(
                    const.DATA_BADGE_AWARDS_POINT_MULTIPLIER, 1.0
                )
                friendly_award_names.append(f"Multiplier: {points_multiplier}")
        attributes[const.ATTR_BADGE_AWARDS] = friendly_award_names

        attributes[const.ATTR_RESET_SCHEDULE] = badge_info.get(
            const.DATA_BADGE_RESET_SCHEDULE, None
        )

        return attributes

    @property
    def icon(self) -> str:
        badge_info = self.coordinator.badges_data.get(self._badge_id, {})
        return badge_info.get(const.DATA_BADGE_ICON, const.DEFAULT_BADGE_ICON)


# ------------------------------------------------------------------------------------------
class SystemChoreSharedStateSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor that shows the global state of a shared chore.

    Tracks system-wide shared chore state independent of individual kid status.
    Provides comprehensive chore configuration including recurring frequency
    (daily/weekly/monthly/custom), applicable days, due dates, default points,
    partial completion settings, multiple claims per day allowance, and total
    approvals today across all assigned kids. Useful for monitoring chores that
    multiple kids can claim simultaneously.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_SHARED_CHORE_GLOBAL_STATUS_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        chore_id: str,
        chore_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            chore_id: Unique identifier for the shared chore.
            chore_name: Display name of the shared chore.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = f"{entry.entry_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_SHARED_CHORE_GLOBAL_STATE_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_CHORE_NAME: chore_name,
        }
        self._attr_device_info = kh.create_system_device_info(entry)
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_MIDFIX_SHARED_CHORE_GLOBAL_STATUS_SENSOR}{chore_name}"

    @property
    def native_value(self) -> str:
        """Return the global state for the chore."""
        chore_info = self.coordinator.chores_data.get(self._chore_id, {})
        return chore_info.get(const.DATA_CHORE_STATE, const.CHORE_STATE_UNKNOWN)

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes for the chore."""
        chore_info = self.coordinator.chores_data.get(self._chore_id, {})
        assigned_kids_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        assigned_kids_names = [
            name
            for k_id in assigned_kids_ids
            if (
                name := kh.get_entity_name_or_log_error(
                    "kid",
                    k_id,
                    self.coordinator.kids_data.get(k_id, {}),
                    const.DATA_KID_NAME,
                )
            )
        ]

        stored_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        total_approvals_today = const.DEFAULT_ZERO
        for kid_id in assigned_kids_ids:
            kid_data = self.coordinator.kids_data.get(kid_id, {})
            total_approvals_today += kid_data.get(
                const.DATA_KID_TODAY_CHORE_APPROVALS, {}
            ).get(self._chore_id, const.DEFAULT_ZERO)

        attributes = {
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_DESCRIPTION: chore_info.get(
                const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_RECURRING_FREQUENCY: chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.SENTINEL_NONE_TEXT
            ),
            const.ATTR_APPLICABLE_DAYS: chore_info.get(
                const.DATA_CHORE_APPLICABLE_DAYS, []
            ),
            const.ATTR_DUE_DATE: chore_info.get(
                const.DATA_CHORE_DUE_DATE, const.TRANS_KEY_DISPLAY_DUE_DATE_NOT_SET
            ),
            const.ATTR_DEFAULT_POINTS: chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
            ),
            const.ATTR_PARTIAL_ALLOWED: chore_info.get(
                const.DATA_CHORE_PARTIAL_ALLOWED, False
            ),
            const.ATTR_ALLOW_MULTIPLE_CLAIMS_PER_DAY: chore_info.get(
                const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY, False
            ),
            const.ATTR_CHORE_APPROVALS_TODAY: total_approvals_today,
            const.ATTR_ASSIGNED_KIDS: assigned_kids_names,
            const.ATTR_LABELS: friendly_labels,
        }

        if (
            chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY)
            == const.FREQUENCY_CUSTOM
        ):
            attributes[const.ATTR_CUSTOM_FREQUENCY_INTERVAL] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL
            )
            attributes[const.ATTR_CUSTOM_FREQUENCY_UNIT] = chore_info.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT
            )

        return attributes

    @property
    def icon(self) -> str:
        """Return the icon for the chore sensor."""
        chore_info = self.coordinator.chores_data.get(self._chore_id, {})
        return chore_info.get(const.DATA_CHORE_ICON, const.DEFAULT_CHORE_SENSOR_ICON)


# ------------------------------------------------------------------------------------------
class KidRewardStatusSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Shows the status of a reward for a particular kid.

    Tracks reward redemption lifecycle: Not Claimed → Claimed (pending approval) → Approved.
    Provides reward metadata including cost, claims/approvals counts, and button entity IDs
    for UI integration.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_REWARD_STATUS_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        reward_id: str,
        reward_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{reward_id}{const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_REWARD_NAME: reward_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_REWARD_STATUS_SENSOR}{reward_name}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> str:
        """Return the current reward status: 'Not Claimed', 'Claimed', or 'Approved'."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        if self._reward_id in kid_info.get(const.DATA_KID_PENDING_REWARDS, []):
            return const.REWARD_STATE_CLAIMED
        if self._reward_id in kid_info.get(const.DATA_KID_REDEEMED_REWARDS, []):
            return const.REWARD_STATE_APPROVED
        return const.REWARD_STATE_NOT_CLAIMED

    @property
    def extra_state_attributes(self) -> dict:
        """Provide extra attributes about the reward."""
        reward_info = self.coordinator.rewards_data.get(self._reward_id, {})
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})

        stored_labels = reward_info.get(const.DATA_REWARD_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        # Get claim, approve, and disapprove button entity IDs
        claim_button_eid = None
        approve_button_eid = None
        disapprove_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            # Claim button uses BUTTON_REWARD_PREFIX instead of a UID suffix
            claim_unique_id = f"{self._entry.entry_id}_{const.BUTTON_REWARD_PREFIX}{self._kid_id}_{self._reward_id}"
            claim_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, claim_unique_id
            )

            # Approve and disapprove buttons use UID suffixes
            approve_unique_id = f"{self._entry.entry_id}_{self._kid_id}_{self._reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
            approve_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, approve_unique_id
            )

            disapprove_unique_id = f"{self._entry.entry_id}_{self._kid_id}_{self._reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
            disapprove_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, disapprove_unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        attributes = {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_DESCRIPTION: reward_info.get(
                const.DATA_REWARD_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_COST: reward_info.get(
                const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST
            ),
            const.ATTR_REWARD_CLAIMS_COUNT: kid_info.get(
                const.DATA_KID_REWARD_CLAIMS, {}
            ).get(self._reward_id, const.DEFAULT_ZERO),
            const.ATTR_REWARD_APPROVALS_COUNT: kid_info.get(
                const.DATA_KID_REWARD_APPROVALS, {}
            ).get(self._reward_id, const.DEFAULT_ZERO),
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_REWARD_CLAIM_BUTTON_ENTITY_ID: claim_button_eid,
            const.ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID: approve_button_eid,
            const.ATTR_REWARD_DISAPPROVE_BUTTON_ENTITY_ID: disapprove_button_eid,
        }

        return attributes

    @property
    def icon(self) -> str:
        """Use the reward's custom icon if set, else fallback."""
        reward_info = self.coordinator.rewards_data.get(self._reward_id, {})
        return reward_info.get(const.DATA_REWARD_ICON, const.DEFAULT_REWARD_ICON)


# ------------------------------------------------------------------------------------------
class KidPenaltyAppliedSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor tracking how many times each penalty has been applied to a kid.

    Counts penalty applications for individual kid/penalty combinations. Provides penalty
    metadata including points deducted, description, and button entity ID for UI integration.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENALTY_APPLIES_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        penalty_id: str,
        penalty_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            penalty_id: Unique identifier for the penalty.
            penalty_name: Display name of the penalty.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._penalty_id = penalty_id
        self._penalty_name = penalty_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{penalty_id}{const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_PENALTY_NAME: penalty_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_PENALTY_APPLIES_SENSOR}{penalty_name}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> Any:
        """Return the number of times the penalty has been applied."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        return kid_info.get(const.DATA_KID_PENALTY_APPLIES, {}).get(
            self._penalty_id, const.DEFAULT_ZERO
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose additional details like penalty points and description."""
        penalty_info = self.coordinator.penalties_data.get(self._penalty_id, {})

        stored_labels = penalty_info.get(const.DATA_PENALTY_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        # Get the ParentPenaltyApplyButton entity_id
        penalty_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            unique_id = f"{self._entry.entry_id}_{const.BUTTON_PENALTY_PREFIX}{self._kid_id}_{self._penalty_id}"
            penalty_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        return {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_PENALTY_NAME: self._penalty_name,
            const.ATTR_DESCRIPTION: penalty_info.get(
                const.DATA_PENALTY_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_PENALTY_POINTS: penalty_info.get(
                const.DATA_PENALTY_POINTS, const.DEFAULT_PENALTY_POINTS
            ),
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_PENALTY_BUTTON_EID: penalty_button_eid,
        }

    @property
    def icon(self):
        """Return the chore's custom icon if set, else fallback."""
        penalty_info = self.coordinator.penalties_data.get(self._penalty_id, {})
        return penalty_info.get(const.DATA_PENALTY_ICON, const.DEFAULT_PENALTY_ICON)


# ------------------------------------------------------------------------------------------
class SystemAchievementSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor representing an achievement.

    Provides system-wide achievement definition and tracks aggregated progress
    across all assigned kids as a percentage (0-100). Supports three achievement
    types: TOTAL (cumulative completions with baselines), STREAK (consecutive
    completions), and DAILY_MIN (minimum daily requirements). Includes achievement
    metadata such as target values, reward points, criteria, associated chore,
    and list of kids who have earned the achievement.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_ACHIEVEMENT_STATE_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        achievement_id: str,
        achievement_name: str,
    ):
        """Initialize the SystemAchievementSensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            achievement_id: Unique identifier for the achievement.
            achievement_name: Display name of the achievement.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._achievement_id = achievement_id
        self._achievement_name = achievement_name
        self._attr_unique_id = f"{entry.entry_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ACHIEVEMENT_NAME: achievement_name,
        }
        self._attr_device_info = kh.create_system_device_info(entry)
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_MIDFIX_ACHIEVEMENT_SENSOR}{achievement_name}"

    @property
    def native_value(self) -> Any:
        """Return the overall progress percentage toward the achievement."""

        achievement = self.coordinator.achievements_data.get(self._achievement_id, {})
        target = achievement.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        assigned_kids = achievement.get(const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, [])

        if not assigned_kids:
            return const.DEFAULT_ZERO

        ach_type = achievement.get(const.DATA_ACHIEVEMENT_TYPE)
        if ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
            total_current = const.DEFAULT_ZERO
            total_effective_target = const.DEFAULT_ZERO

            for kid_id in assigned_kids:
                progress_data = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(kid_id, {})
                baseline = (
                    progress_data.get(
                        const.DATA_ACHIEVEMENT_BASELINE, const.DEFAULT_ZERO
                    )
                    if isinstance(progress_data, dict)
                    else const.DEFAULT_ZERO
                )
                current_total = self.coordinator.kids_data.get(kid_id, {}).get(
                    const.DATA_KID_COMPLETED_CHORES_TOTAL_DEPRECATED, const.DEFAULT_ZERO
                )
                total_current += current_total
                total_effective_target += baseline + target

            percent = (
                (total_current / total_effective_target * 100)
                if total_effective_target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_STREAK:
            total_current = const.DEFAULT_ZERO

            for kid_id in assigned_kids:
                progress_data = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(kid_id, {})
                total_current += (
                    progress_data.get(
                        const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                    )
                    if isinstance(progress_data, dict)
                    else const.DEFAULT_ZERO
                )

            global_target = target * len(assigned_kids)

            percent = (
                (total_current / global_target * 100)
                if global_target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_DAILY_MIN:
            total_progress = const.DEFAULT_ZERO

            for kid_id in assigned_kids:
                daily = self.coordinator.kids_data.get(kid_id, {}).get(
                    const.DATA_KID_COMPLETED_CHORES_TODAY_DEPRECATED, const.DEFAULT_ZERO
                )
                kid_progress = (
                    100
                    if daily >= target
                    else (daily / target * 100)
                    if target > const.DEFAULT_ZERO
                    else const.DEFAULT_ZERO
                )
                total_progress += kid_progress

            percent = total_progress / len(assigned_kids)

        else:
            percent = const.DEFAULT_ZERO

        return min(100, round(percent, 1))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for this achievement."""
        achievement = self.coordinator.achievements_data.get(self._achievement_id, {})
        progress = achievement.get(const.DATA_ACHIEVEMENT_PROGRESS, {})
        kids_progress = {}

        earned_by = []
        for kid_id, data in progress.items():
            if data.get(const.DATA_ACHIEVEMENT_AWARDED, False):
                kid_name = kh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
                earned_by.append(kid_name)

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = achievement.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = self.coordinator.chores_data.get(
                selected_chore_id, {}
            ).get(const.DATA_CHORE_NAME, const.SENTINEL_EMPTY)

        assigned_kids_ids = achievement.get(const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, [])
        assigned_kids_names = [
            name
            for k_id in assigned_kids_ids
            if (
                name := kh.get_entity_name_or_log_error(
                    "kid",
                    k_id,
                    self.coordinator.kids_data.get(k_id, {}),
                    const.DATA_KID_NAME,
                )
            )
        ]
        ach_type = achievement.get(const.DATA_ACHIEVEMENT_TYPE)
        for kid_id in assigned_kids_ids:
            kid_name = kh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
            progress_data = achievement.get(const.DATA_ACHIEVEMENT_PROGRESS, {}).get(
                kid_id, {}
            )
            if ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
                kids_progress[kid_name] = progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_VALUE, const.DEFAULT_ZERO
                )
            elif ach_type == const.ACHIEVEMENT_TYPE_STREAK:
                kids_progress[kid_name] = progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                )
            elif (
                achievement.get(const.DATA_ACHIEVEMENT_TYPE)
                == const.ACHIEVEMENT_TYPE_DAILY_MIN
            ):
                kids_progress[kid_name] = self.coordinator.kids_data.get(
                    kid_id, {}
                ).get(
                    const.DATA_KID_COMPLETED_CHORES_TODAY_DEPRECATED, const.DEFAULT_ZERO
                )
            else:
                kids_progress[kid_name] = const.DEFAULT_ZERO

        stored_labels = achievement.get(const.DATA_ACHIEVEMENT_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        return {
            const.ATTR_ACHIEVEMENT_NAME: self._achievement_name,
            const.ATTR_DESCRIPTION: achievement.get(
                const.DATA_ACHIEVEMENT_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_KIDS: assigned_kids_names,
            const.ATTR_TYPE: ach_type,
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: achievement.get(
                const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: achievement.get(
                const.DATA_ACHIEVEMENT_TARGET_VALUE
            ),
            const.ATTR_REWARD_POINTS: achievement.get(
                const.DATA_ACHIEVEMENT_REWARD_POINTS
            ),
            const.ATTR_KIDS_EARNED: earned_by,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self):
        """Return an icon; you could choose a trophy icon."""
        achievement_info = self.coordinator.achievements_data.get(
            self._achievement_id, {}
        )
        return achievement_info.get(
            const.DATA_ACHIEVEMENT_ICON, const.DEFAULT_ACHIEVEMENTS_ICON
        )


# ------------------------------------------------------------------------------------------
class SystemChallengeSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor representing a challenge.

    Provides system-wide challenge definition and tracks aggregated progress
    across all assigned kids as a percentage (0-100). Supports two challenge
    types: TOTAL_WITHIN_WINDOW (simple count toward target within date range)
    and DAILY_MIN (required daily minimum summed across all days in window).
    Includes challenge metadata such as start/end dates, target values, reward
    points, criteria, associated chore, and list of kids who have earned the
    challenge reward.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHALLENGE_STATE_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        challenge_id: str,
        challenge_name: str,
    ):
        """Initialize the ChallengeSensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            challenge_id: Unique identifier for the challenge.
            challenge_name: Display name of the challenge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._challenge_id = challenge_id
        self._challenge_name = challenge_name
        self._attr_unique_id = f"{entry.entry_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_CHALLENGE_NAME: challenge_name,
        }
        self._attr_device_info = kh.create_system_device_info(entry)
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_MIDFIX_CHALLENGE_SENSOR}{challenge_name}"

    @property
    def native_value(self) -> Any:
        """Return the overall progress percentage toward the challenge."""

        challenge = self.coordinator.challenges_data.get(self._challenge_id, {})
        target = challenge.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
        assigned_kids = challenge.get(const.DATA_CHALLENGE_ASSIGNED_KIDS, [])

        if not assigned_kids:
            return const.DEFAULT_ZERO

        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)
        total_progress = const.DEFAULT_ZERO

        for kid_id in assigned_kids:
            progress_data = challenge.get(const.DATA_CHALLENGE_PROGRESS, {}).get(
                kid_id, {}
            )

            if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                total_progress += progress_data.get(
                    const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO
                )

            elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                if isinstance(progress_data, dict):
                    daily_counts = progress_data.get(
                        const.DATA_CHALLENGE_DAILY_COUNTS, {}
                    )
                    total_progress += sum(daily_counts.values())

                else:
                    total_progress += const.DEFAULT_ZERO

            else:
                total_progress += const.DEFAULT_ZERO

        global_target = target * len(assigned_kids)

        percent = (
            (total_progress / global_target * 100)
            if global_target > const.DEFAULT_ZERO
            else const.DEFAULT_ZERO
        )

        return min(100, round(percent, 1))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for this challenge."""
        challenge = self.coordinator.challenges_data.get(self._challenge_id, {})
        progress = challenge.get(const.DATA_CHALLENGE_PROGRESS, {})
        kids_progress = {}
        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)

        earned_by = []
        for kid_id, data in progress.items():
            if data.get(const.DATA_CHALLENGE_AWARDED, False):
                kid_name = kh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
                earned_by.append(kid_name)

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = challenge.get(const.DATA_CHALLENGE_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = self.coordinator.chores_data.get(
                selected_chore_id, {}
            ).get(const.DATA_CHORE_NAME, const.SENTINEL_EMPTY)

        assigned_kids_ids = challenge.get(const.DATA_CHALLENGE_ASSIGNED_KIDS, [])
        assigned_kids_names = [
            name
            for k_id in assigned_kids_ids
            if (
                name := kh.get_entity_name_or_log_error(
                    "kid",
                    k_id,
                    self.coordinator.kids_data.get(k_id, {}),
                    const.DATA_KID_NAME,
                )
            )
        ]

        for kid_id in assigned_kids_ids:
            kid_name = kh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
            progress_data = challenge.get(const.DATA_CHALLENGE_PROGRESS, {}).get(
                kid_id, {}
            )
            if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                kids_progress[kid_name] = progress_data.get(
                    const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO
                )
            elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                if isinstance(progress_data, dict):
                    kids_progress[kid_name] = sum(
                        progress_data.get(
                            const.DATA_CHALLENGE_DAILY_COUNTS, {}
                        ).values()
                    )
                else:
                    kids_progress[kid_name] = const.DEFAULT_ZERO
            else:
                kids_progress[kid_name] = const.DEFAULT_ZERO

        stored_labels = challenge.get(const.DATA_CHALLENGE_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        return {
            const.ATTR_CHALLENGE_NAME: self._challenge_name,
            const.ATTR_DESCRIPTION: challenge.get(
                const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_KIDS: assigned_kids_names,
            const.ATTR_TYPE: challenge_type,
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: challenge.get(
                const.DATA_CHALLENGE_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: challenge.get(const.DATA_CHALLENGE_TARGET_VALUE),
            const.ATTR_REWARD_POINTS: challenge.get(const.DATA_CHALLENGE_REWARD_POINTS),
            const.ATTR_START_DATE: challenge.get(const.DATA_CHALLENGE_START_DATE),
            const.ATTR_END_DATE: challenge.get(const.DATA_CHALLENGE_END_DATE),
            const.ATTR_KIDS_EARNED: earned_by,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self):
        """Return an icon for challenges (you might want to choose one that fits your theme)."""
        challenge_info = self.coordinator.challenges_data.get(self._challenge_id, {})
        return challenge_info.get(
            const.DATA_CHALLENGE_ICON, const.DEFAULT_ACHIEVEMENTS_ICON
        )


# ------------------------------------------------------------------------------------------
class KidAchievementProgressSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor representing a kid's progress toward a specific achievement.

    Tracks achievement progress as a percentage (0-100) for individual kid/achievement
    combinations. Supports multiple achievement types: TOTAL (cumulative count with
    baseline), STREAK (consecutive completions), and DAILY_MIN (daily minimum
    requirements). Provides comprehensive metadata including target value, reward
    points, criteria, associated chore, and award status.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_ACHIEVEMENT_PROGRESS_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        achievement_id: str,
        achievement_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            achievement_id: Unique identifier for the achievement.
            achievement_name: Display name of the achievement.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._achievement_id = achievement_id
        self._achievement_name = achievement_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_ACHIEVEMENT_NAME: achievement_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_ACHIEVEMENT_PROGRESS_SENSOR}{achievement_name}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> float:
        """Return the progress percentage toward the achievement.

        Calculates percentage based on achievement type:
        - TOTAL: (current_value / (baseline + target)) * 100
        - STREAK: (current_streak / target) * 100
        - DAILY_MIN: (daily_completions / target) * 100

        Returns:
            Progress percentage capped at 100.0, rounded to 1 decimal place.
        """
        achievement = self.coordinator.achievements_data.get(self._achievement_id, {})
        target = achievement.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        ach_type = achievement.get(const.DATA_ACHIEVEMENT_TYPE)

        if ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
            progress_data = achievement.get(const.DATA_ACHIEVEMENT_PROGRESS, {}).get(
                self._kid_id, {}
            )

            baseline = (
                progress_data.get(const.DATA_ACHIEVEMENT_BASELINE, const.DEFAULT_ZERO)
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

            current_total = self.coordinator.kids_data.get(self._kid_id, {}).get(
                const.DATA_KID_COMPLETED_CHORES_TODAY_DEPRECATED, const.DEFAULT_ZERO
            )

            effective_target = baseline + target

            percent = (
                (current_total / effective_target * 100)
                if effective_target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_STREAK:
            progress_data = achievement.get(const.DATA_ACHIEVEMENT_PROGRESS, {}).get(
                self._kid_id, {}
            )

            progress = (
                progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                )
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

            percent = (
                (progress / target * 100)
                if target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        elif ach_type == const.ACHIEVEMENT_TYPE_DAILY_MIN:
            daily = self.coordinator.kids_data.get(self._kid_id, {}).get(
                const.DATA_KID_COMPLETED_CHORES_TOTAL_DEPRECATED, const.DEFAULT_ZERO
            )

            percent = (
                (daily / target * 100)
                if target > const.DEFAULT_ZERO
                else const.DEFAULT_ZERO
            )

        else:
            percent = const.DEFAULT_ZERO

        return min(100, round(percent, 1))

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes for the achievement progress."""
        achievement = self.coordinator.achievements_data.get(self._achievement_id, {})
        target = achievement.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        progress_data = achievement.get(const.DATA_ACHIEVEMENT_PROGRESS, {}).get(
            self._kid_id, {}
        )
        raw_progress = const.DEFAULT_ZERO

        awarded = (
            progress_data.get(const.DATA_ACHIEVEMENT_AWARDED, False)
            if isinstance(progress_data, dict)
            else False
        )

        if achievement.get(const.DATA_ACHIEVEMENT_TYPE) == const.ACHIEVEMENT_TYPE_TOTAL:
            raw_progress = (
                progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_VALUE, const.DEFAULT_ZERO
                )
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

        elif (
            achievement.get(const.DATA_ACHIEVEMENT_TYPE)
            == const.ACHIEVEMENT_TYPE_STREAK
        ):
            raw_progress = (
                progress_data.get(
                    const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                )
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

        elif (
            achievement.get(const.DATA_ACHIEVEMENT_TYPE)
            == const.ACHIEVEMENT_TYPE_DAILY_MIN
        ):
            raw_progress = self.coordinator.kids_data.get(self._kid_id, {}).get(
                const.DATA_KID_COMPLETED_CHORES_TODAY_DEPRECATED, const.DEFAULT_ZERO
            )

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = achievement.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = self.coordinator.chores_data.get(
                selected_chore_id, {}
            ).get(const.DATA_CHORE_NAME, const.SENTINEL_EMPTY)

        assigned_kids_ids = achievement.get(const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, [])
        assigned_kids_names = [
            name
            for k_id in assigned_kids_ids
            if (
                name := kh.get_entity_name_or_log_error(
                    "kid",
                    k_id,
                    self.coordinator.kids_data.get(k_id, {}),
                    const.DATA_KID_NAME,
                )
            )
        ]

        stored_labels = achievement.get(const.DATA_ACHIEVEMENT_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        return {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_ACHIEVEMENT_NAME: self._achievement_name,
            const.ATTR_DESCRIPTION: achievement.get(
                const.DATA_ACHIEVEMENT_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_KIDS: assigned_kids_names,
            const.ATTR_TYPE: achievement.get(const.DATA_ACHIEVEMENT_TYPE),
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: achievement.get(
                const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: target,
            const.ATTR_REWARD_POINTS: achievement.get(
                const.DATA_ACHIEVEMENT_REWARD_POINTS
            ),
            const.ATTR_RAW_PROGRESS: raw_progress,
            const.ATTR_AWARDED: awarded,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self) -> str:
        """Return the icon for the achievement."""
        achievement = self.coordinator.achievements_data.get(self._achievement_id, {})
        return achievement.get(
            const.DATA_ACHIEVEMENT_ICON, const.DEFAULT_ACHIEVEMENTS_ICON
        )


# ------------------------------------------------------------------------------------------
class KidChallengeProgressSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor representing a kid's progress toward a specific challenge.

    Tracks challenge progress as a percentage (0-100) for individual kid/challenge
    combinations. Supports two challenge types: TOTAL_WITHIN_WINDOW (simple count
    toward target) and DAILY_MIN (required daily minimums summed across date range).
    Includes comprehensive metadata such as start/end dates, target values, reward
    points, associated chore, and award status.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHALLENGE_PROGRESS_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        challenge_id: str,
        challenge_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            challenge_id: Unique identifier for the challenge.
            challenge_name: Display name of the challenge.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._challenge_id = challenge_id
        self._challenge_name = challenge_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_CHALLENGE_NAME: challenge_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_CHALLENGE_PROGRESS_SENSOR}{challenge_name}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> float:
        """Return the challenge progress percentage.

        Calculates percentage based on challenge type:
        - TOTAL_WITHIN_WINDOW: (count / target) * 100
        - DAILY_MIN: (sum_of_daily_counts / (required_daily * num_days)) * 100

        Returns:
            Progress percentage capped at 100.0, rounded to 1 decimal place.
        """
        challenge = self.coordinator.challenges_data.get(self._challenge_id, {})
        target = challenge.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)
        progress_data = challenge.get(const.DATA_CHALLENGE_PROGRESS, {}).get(
            self._kid_id
        )

        if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
            raw_progress = (
                progress_data.get(const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO)
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )

        elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
            if isinstance(progress_data, dict):
                daily_counts = progress_data.get(const.DATA_CHALLENGE_DAILY_COUNTS, {})
                raw_progress = sum(daily_counts.values())

                start_date = dt_util.parse_datetime(
                    challenge.get(const.DATA_CHALLENGE_START_DATE)
                )
                end_date = dt_util.parse_datetime(
                    challenge.get(const.DATA_CHALLENGE_END_DATE)
                )

                if start_date and end_date:
                    num_days = (end_date.date() - start_date.date()).days + 1

                else:
                    num_days = 1
                required_daily = challenge.get(const.DATA_CHALLENGE_REQUIRED_DAILY, 1)
                target = required_daily * num_days

            else:
                raw_progress = const.DEFAULT_ZERO

        else:
            raw_progress = const.DEFAULT_ZERO

        percent = (
            (raw_progress / target * 100)
            if target > const.DEFAULT_ZERO
            else const.DEFAULT_ZERO
        )

        return min(100, round(percent, 1))

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes for the challenge progress."""
        challenge = self.coordinator.challenges_data.get(self._challenge_id, {})
        target = challenge.get(const.DATA_CHALLENGE_TARGET_VALUE, 1)
        challenge_type = challenge.get(const.DATA_CHALLENGE_TYPE)
        progress_data = challenge.get(const.DATA_CHALLENGE_PROGRESS, {}).get(
            self._kid_id, {}
        )
        awarded = (
            progress_data.get(const.DATA_CHALLENGE_AWARDED, False)
            if isinstance(progress_data, dict)
            else False
        )

        if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
            raw_progress = (
                progress_data.get(const.DATA_CHALLENGE_COUNT, const.DEFAULT_ZERO)
                if isinstance(progress_data, dict)
                else const.DEFAULT_ZERO
            )
        elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
            if isinstance(progress_data, dict):
                daily_counts = progress_data.get(const.DATA_CHALLENGE_DAILY_COUNTS, {})
                raw_progress = sum(daily_counts.values())
            else:
                raw_progress = const.DEFAULT_ZERO
        else:
            raw_progress = const.DEFAULT_ZERO

        associated_chore = const.SENTINEL_EMPTY
        selected_chore_id = challenge.get(const.DATA_CHALLENGE_SELECTED_CHORE_ID)
        if selected_chore_id:
            associated_chore = self.coordinator.chores_data.get(
                selected_chore_id, {}
            ).get(const.DATA_CHORE_NAME, const.SENTINEL_EMPTY)

        assigned_kids_ids = challenge.get(const.DATA_CHALLENGE_ASSIGNED_KIDS, [])
        assigned_kids_names = [
            name
            for k_id in assigned_kids_ids
            if (
                name := kh.get_entity_name_or_log_error(
                    "kid",
                    k_id,
                    self.coordinator.kids_data.get(k_id, {}),
                    const.DATA_KID_NAME,
                )
            )
        ]

        stored_labels = challenge.get(const.DATA_CHALLENGE_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        return {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_CHALLENGE_NAME: self._challenge_name,
            const.ATTR_DESCRIPTION: challenge.get(
                const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_ASSIGNED_KIDS: assigned_kids_names,
            const.ATTR_TYPE: challenge_type,
            const.ATTR_ASSOCIATED_CHORE: associated_chore,
            const.ATTR_CRITERIA: challenge.get(
                const.DATA_CHALLENGE_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.ATTR_TARGET_VALUE: target,
            const.ATTR_REWARD_POINTS: challenge.get(const.DATA_CHALLENGE_REWARD_POINTS),
            const.ATTR_START_DATE: challenge.get(const.DATA_CHALLENGE_START_DATE),
            const.ATTR_END_DATE: challenge.get(const.DATA_CHALLENGE_END_DATE),
            const.ATTR_RAW_PROGRESS: raw_progress,
            const.ATTR_AWARDED: awarded,
            const.ATTR_LABELS: friendly_labels,
        }

    @property
    def icon(self) -> str:
        """Return the icon for the challenge.

        Use the icon provided in the challenge data if set, else fallback to default.
        """
        challenge = self.coordinator.challenges_data.get(self._challenge_id, {})
        return challenge.get(const.DATA_CHALLENGE_ICON, const.DEFAULT_CHALLENGES_ICON)


# ------------------------------------------------------------------------------------------
class KidBonusAppliedSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Sensor tracking how many times each bonus has been applied to a kid.

    Counts bonus applications for individual kid/bonus combinations. Provides bonus
    metadata including points awarded, description, and button entity ID for UI integration.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_BONUS_APPLIES_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        bonus_id: str,
        bonus_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            bonus_id: Unique identifier for the bonus.
            bonus_name: Display name of the bonus.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._bonus_id = bonus_id
        self._bonus_name = bonus_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{bonus_id}{const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_BONUS_NAME: bonus_name,
        }
        # Strip redundant "bonus" suffix from entity_id (bonus_name often ends with "Bonus")
        bonus_slug = bonus_name.lower().replace(" ", "_")
        if bonus_slug.endswith("_bonus"):
            bonus_slug = bonus_slug[:-6]  # Remove "_bonus" suffix
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_BONUS_APPLIES_SENSOR}{bonus_slug}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> Any:
        """Return the number of times the bonus has been applied."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        return kid_info.get(const.DATA_KID_BONUS_APPLIES, {}).get(
            self._bonus_id, const.DEFAULT_ZERO
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose additional details like bonus points and description."""
        bonus_info = self.coordinator.bonuses_data.get(self._bonus_id, {})

        stored_labels = bonus_info.get(const.DATA_BONUS_LABELS, [])
        friendly_labels = [
            kh.get_friendly_label(self.hass, label) for label in stored_labels
        ]

        # Get the ParentBonusApplyButton entity_id
        bonus_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            unique_id = f"{self._entry.entry_id}_{const.BUTTON_BONUS_PREFIX}{self._kid_id}_{self._bonus_id}"
            bonus_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        return {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_BONUS_NAME: self._bonus_name,
            const.ATTR_DESCRIPTION: bonus_info.get(
                const.DATA_BONUS_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_BONUS_POINTS: bonus_info.get(
                const.DATA_BONUS_POINTS, const.DEFAULT_BONUS_POINTS
            ),
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_BONUS_BUTTON_EID: bonus_button_eid,
        }

    @property
    def icon(self):
        """Return the bonus's custom icon if set, else fallback."""
        bonus_info = self.coordinator.bonuses_data.get(self._bonus_id, {})
        return bonus_info.get(const.DATA_BONUS_ICON, const.DEFAULT_BONUS_ICON)


# ------------------------------------------------------------------------------------------
class KidDashboardHelperSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Aggregated dashboard helper sensor for a kid.

    Provides a consolidated view of all kid-related entities including chores,
    rewards, badges, bonuses, penalties, achievements, challenges, and point buttons.
    Serves pre-sorted and pre-filtered entity lists to optimize dashboard template
    rendering performance. Also provides ui_translations dictionary containing all
    40+ localization keys from backend integration JSON for multilingual dashboard
    support without requiring language-specific YAML variants.

    This sensor is the single source of truth for the KidsChores dashboard,
    eliminating expensive frontend list iterations and sorting operations.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "dashboard_helper_sensor"

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency (e.g., 'Points', 'Stars').
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_ui_dashboard_helper"
        self.entity_id = (
            f"{const.SENSOR_KC_PREFIX}{kid_name}"
            f"{const.SENSOR_KC_EID_MIDFIX_UI_DASHBOARD}"
            f"{const.SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER}"
        )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

        # Translations cache - loaded async on entity add
        self._ui_translations = {}
        self._current_language = const.DEFAULT_DASHBOARD_LANGUAGE

    async def async_added_to_hass(self) -> None:
        """Load translations when entity is added to hass."""
        await super().async_added_to_hass()

        # Load translations for the current language
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        dashboard_language = kid_info.get(
            const.DATA_KID_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )

        self._ui_translations = await kh.load_dashboard_translation(
            self.hass, dashboard_language
        )
        self._current_language = dashboard_language

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check if language has changed
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        dashboard_language = kid_info.get(
            const.DATA_KID_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )

        # If language changed, schedule async translation reload
        if dashboard_language != self._current_language:
            self.hass.async_create_task(self._async_reload_translations())

        # Check if pending approvals changed - forces attribute rebuild
        # Flags are reset in extra_state_attributes after rebuild
        # pylint: disable=protected-access  # Intentional access to change flags
        if (
            self.coordinator._pending_chore_changed
            or self.coordinator._pending_reward_changed
        ):
            # Flag set - attributes will rebuild in next extra_state_attributes call
            pass

        super()._handle_coordinator_update()

    async def _async_reload_translations(self) -> None:
        """Reload translations asynchronously."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        dashboard_language = kid_info.get(
            const.DATA_KID_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )

        self._ui_translations = await kh.load_dashboard_translation(
            self.hass, dashboard_language
        )
        self._current_language = dashboard_language
        self.async_write_ha_state()

    def _get_next_monday_7am_local(self) -> datetime:
        """Calculate the next Monday at 7:00 AM local time.

        Uses kc_helpers.get_next_applicable_day with local return type.
        If currently Monday before 7am, returns today at 7am, otherwise next Monday.
        """
        now_local = kh.get_now_local_time()

        # If today is Monday and before 7am, return today at 7am
        if now_local.weekday() == 0 and now_local.hour < 7:
            return now_local.replace(hour=7, minute=0, second=0, microsecond=0)

        # Get next Monday in local time and set to 7am
        next_monday = cast(
            datetime,
            kh.get_next_applicable_day(
                dt_util.utcnow(),
                applicable_days=[0],
                return_type=const.HELPER_RETURN_DATETIME_LOCAL,
            ),
        )
        return next_monday.replace(hour=7, minute=0, second=0, microsecond=0)

    def _calculate_chore_attributes(
        self, chore_id: str, chore_info: dict, kid_info: dict, chore_eid
    ) -> dict | None:
        """Calculate all attributes for a single chore.

        Returns a dictionary with chore attributes including:
        - eid: entity_id
        - name: chore name
        - status: pending/claimed/approved/overdue
        - labels: list of label strings
        - due_date: UTC ISO 8601 string
        - is_today_am: boolean or None
        - primary_group: today/this_week/other

        Returns None if chore name is missing (data corruption).
        """
        chore_name = kh.get_entity_name_or_log_error(
            "chore", chore_id, chore_info, const.DATA_CHORE_NAME
        )
        if not chore_name:
            return None

        # Determine status
        if chore_id in kid_info.get(const.DATA_KID_APPROVED_CHORES, []):
            status = const.CHORE_STATE_APPROVED
        elif chore_id in kid_info.get(const.DATA_KID_CLAIMED_CHORES, []):
            status = const.CHORE_STATE_CLAIMED
        elif chore_id in kid_info.get(const.DATA_KID_OVERDUE_CHORES, []):
            status = const.CHORE_STATE_OVERDUE
        else:
            status = const.CHORE_STATE_PENDING

        # Get chore labels (always a list, even if empty)
        chore_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        if not isinstance(chore_labels, list):
            chore_labels = []

        # Parse due date using helper function
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        due_date_utc_iso = None
        due_date_local_dt = None

        if due_date_str:
            due_date_utc = kh.parse_datetime_to_utc(due_date_str)
            if due_date_utc:
                due_date_utc_iso = kh.format_datetime_with_return_type(
                    due_date_utc, const.HELPER_RETURN_ISO_DATETIME
                )
                # Get datetime object for local calculations
                due_date_local_dt = kh.format_datetime_with_return_type(
                    due_date_utc, const.HELPER_RETURN_DATETIME_LOCAL
                )

        # Calculate is_today_am (only if due date exists and is today)
        is_today_am = None
        if due_date_local_dt and isinstance(due_date_local_dt, datetime):
            today_local = kh.get_today_local_date()
            if due_date_local_dt.date() == today_local and due_date_local_dt.hour < 12:
                is_today_am = True
            elif due_date_local_dt.date() == today_local:
                is_today_am = False

        # Calculate primary_group
        recurring_frequency = chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) or ""
        primary_group = self._calculate_primary_group(
            status, due_date_local_dt, recurring_frequency
        )

        return {
            const.ATTR_EID: chore_eid,
            const.ATTR_NAME: chore_name,
            const.ATTR_STATUS: status,
            const.ATTR_CHORE_LABELS: chore_labels,
            const.ATTR_CHORE_DUE_DATE: due_date_utc_iso,
            const.ATTR_CHORE_IS_TODAY_AM: is_today_am,
            const.ATTR_CHORE_PRIMARY_GROUP: primary_group,
        }

    def _calculate_primary_group(
        self, status: str, due_date_local, recurring_frequency: str
    ) -> str:
        """Calculate the primary group for a chore.

        Returns: "today", "this_week", or "other"
        """
        # Overdue chores always go to today group
        if status == const.CHORE_STATE_OVERDUE:
            return const.PRIMARY_GROUP_TODAY

        # Check due date if available
        if due_date_local and isinstance(due_date_local, datetime):
            today_local = kh.get_today_local_date()

            # Due today -> today group
            if due_date_local.date() == today_local:
                return const.PRIMARY_GROUP_TODAY

            # Due before next Monday 7am -> this_week group
            next_monday_7am = self._get_next_monday_7am_local()
            if due_date_local < next_monday_7am:
                return const.PRIMARY_GROUP_THIS_WEEK

            # Due later -> other group
            return const.PRIMARY_GROUP_OTHER

        # No due date - check recurring frequency
        if recurring_frequency == const.FREQUENCY_DAILY:
            return const.PRIMARY_GROUP_TODAY
        if recurring_frequency == const.FREQUENCY_WEEKLY:
            return const.PRIMARY_GROUP_THIS_WEEK

        return const.PRIMARY_GROUP_OTHER

    @property
    def native_value(self) -> Any:
        """Return an overall summary string. Primary consumers should use attributes."""
        # Provide a short human-readable summary
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        # Count chores by status using existing chore data
        chores = []
        for chore_id, chore_info in self.coordinator.chores_data.items():
            if self._kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                continue
            chore_name = kh.get_entity_name_or_log_error(
                "chore", chore_id, chore_info, const.DATA_CHORE_NAME
            )
            if not chore_name:
                continue
            # Determine kid-specific status
            status = const.CHORE_STATE_PENDING
            if chore_id in kid_info.get(const.DATA_KID_APPROVED_CHORES, []):
                status = const.CHORE_STATE_APPROVED
            elif chore_id in kid_info.get(const.DATA_KID_CLAIMED_CHORES, []):
                status = const.CHORE_STATE_CLAIMED
            elif chore_id in kid_info.get(const.DATA_KID_OVERDUE_CHORES, []):
                status = const.CHORE_STATE_OVERDUE
            chores.append({"id": chore_id, "name": chore_name, "status": status})

        # Rewards: list name and cost
        rewards = []
        for reward_id, reward_info in self.coordinator.rewards_data.items():
            reward_name = kh.get_entity_name_or_log_error(
                "reward", reward_id, reward_info, const.DATA_REWARD_NAME
            )
            if not reward_name:
                continue
            cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST)
            rewards.append({"id": reward_id, "name": reward_name, "cost": cost})

        # Count badges, bonuses, penalties for this kid
        # Badge applies if: no kids assigned (applies to all) OR kid is in assigned list
        badges_count = len(
            [
                b
                for b in self.coordinator.badges_data.values()
                if not b.get(const.DATA_BADGE_ASSIGNED_TO, [])
                or self._kid_id in b.get(const.DATA_BADGE_ASSIGNED_TO, [])
            ]
        )
        bonuses_count = len(self.coordinator.bonuses_data)
        penalties_count = len(self.coordinator.penalties_data)

        # Count achievements and challenges assigned to this kid
        achievements_count = len(
            [
                a
                for a in self.coordinator.achievements_data.values()
                if self._kid_id in a.get(const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, [])
            ]
        )
        challenges_count = len(
            [
                c
                for c in self.coordinator.challenges_data.values()
                if self._kid_id in c.get(const.DATA_CHALLENGE_ASSIGNED_KIDS, [])
            ]
        )

        # Minimal native value summarizing counts
        return f"chores:{len(chores)} rewards:{len(rewards)} badges:{badges_count} bonuses:{bonuses_count} penalties:{penalties_count} achievements:{achievements_count} challenges:{challenges_count}"

    def _build_pending_approvals(self, entity_registry) -> dict:
        """Build pending approvals data with button entity IDs.

        Returns:
            dict: {
                "chores": [
                    {
                        "chore_id": "uuid",
                        "chore_name": "Take out Trash",
                        "timestamp": "2024-01-15T10:30:00+00:00",
                        "approve_button_eid": "button.kc_kid_a_chore_1_approve",
                        "disapprove_button_eid": "button.kc_kid_a_chore_1_disapprove"
                    }
                ],
                "rewards": [...]
            }
        """
        pending_chores = []
        pending_rewards = []

        # Get all pending approvals from coordinator
        # pylint: disable=protected-access  # Accessing coordinator internal data
        pending_chore_approvals = self.coordinator._data.get(
            const.DATA_PENDING_CHORE_APPROVALS, []
        )
        pending_reward_approvals = self.coordinator._data.get(
            const.DATA_PENDING_REWARD_APPROVALS, []
        )

        # Filter for this kid's pending chores
        for approval in pending_chore_approvals:
            if approval.get(const.DATA_KID_ID) != self._kid_id:
                continue

            chore_id = approval.get(const.DATA_CHORE_ID)
            chore_info = self.coordinator.chores_data.get(chore_id, {})
            chore_name = kh.get_entity_name_or_log_error(
                "chore", chore_id, chore_info, const.DATA_CHORE_NAME
            )
            if not chore_name:
                continue

            # Build button unique IDs and lookup entity IDs
            approve_uid = (
                f"{self._entry.entry_id}_{self._kid_id}_{chore_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
            )
            disapprove_uid = (
                f"{self._entry.entry_id}_{self._kid_id}_{chore_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"
            )

            approve_eid = None
            disapprove_eid = None
            if entity_registry:
                approve_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, approve_uid
                )
                disapprove_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, disapprove_uid
                )

            pending_chores.append(
                {
                    "chore_id": chore_id,
                    "chore_name": chore_name,
                    "timestamp": approval.get(const.DATA_CHORE_TIMESTAMP),
                    "approve_button_eid": approve_eid,
                    "disapprove_button_eid": disapprove_eid,
                }
            )

        # Filter for this kid's pending rewards
        for approval in pending_reward_approvals:
            if approval.get(const.DATA_KID_ID) != self._kid_id:
                continue

            reward_id = approval.get(const.DATA_REWARD_ID)
            reward_info = self.coordinator.rewards_data.get(reward_id, {})
            reward_name = kh.get_entity_name_or_log_error(
                "reward", reward_id, reward_info, const.DATA_REWARD_NAME
            )
            if not reward_name:
                continue

            # Build button unique IDs and lookup entity IDs
            approve_uid = (
                f"{self._entry.entry_id}_{self._kid_id}_{reward_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
            )
            disapprove_uid = (
                f"{self._entry.entry_id}_{self._kid_id}_{reward_id}"
                f"{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
            )

            approve_eid = None
            disapprove_eid = None
            if entity_registry:
                approve_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, approve_uid
                )
                disapprove_eid = entity_registry.async_get_entity_id(
                    "button", const.DOMAIN, disapprove_uid
                )

            pending_rewards.append(
                {
                    "reward_id": reward_id,
                    "reward_name": reward_name,
                    "timestamp": approval.get(const.DATA_REWARD_TIMESTAMP),
                    "approve_button_eid": approve_eid,
                    "disapprove_button_eid": disapprove_eid,
                }
            )

        return {"chores": pending_chores, "rewards": pending_rewards}

    @property
    def extra_state_attributes(self) -> dict:
        """Return detailed aggregated structure as attributes.

        Format:
        {
          "chores": [
            {"eid": "sensor.kid_a_chore_1", "name": "Take out Trash", "status": "overdue"},
            ...
          ],
          "rewards": [
            {"eid": "sensor.kid_a_reward_1", "name": "Ice Cream", "cost": "10 Points"},
            ...
          ],
        }
        """
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        chores_attr = []

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        for chore_id, chore_info in self.coordinator.chores_data.items():
            if self._kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                continue

            # Get the ChoreStatusSensor entity_id
            chore_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._kid_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
                chore_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )

            # Use helper method to calculate all chore attributes
            chore_attrs = self._calculate_chore_attributes(
                chore_id, chore_info, kid_info, chore_eid
            )
            if chore_attrs:  # Skip if name missing (data corruption)
                chores_attr.append(chore_attrs)

        # Sort chores by due date (ascending, earliest first)
        # Chores without due dates are placed at the end, sorted by entity_id
        chores_attr.sort(
            key=lambda c: (
                c.get(const.ATTR_CHORE_DUE_DATE) is None,  # None values go last
                c.get(const.ATTR_CHORE_DUE_DATE)
                or "",  # Sort by due_date (ISO format sorts correctly)
                c.get(const.ATTR_EID)
                or "",  # Then by entity_id for chores without due dates
            )
        )

        rewards_attr = []
        for reward_id, reward_info in self.coordinator.rewards_data.items():
            reward_name = kh.get_entity_name_or_log_error(
                "reward", reward_id, reward_info, const.DATA_REWARD_NAME
            )
            if not reward_name:
                continue

            # Get the RewardStatusSensor entity_id
            reward_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._kid_id}_{reward_id}{const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}"
                reward_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )

            # Get reward labels (always a list, even if empty)
            reward_labels = reward_info.get(const.DATA_REWARD_LABELS, [])
            if not isinstance(reward_labels, list):
                reward_labels = []

            # Get reward cost
            reward_cost = reward_info.get(const.DATA_REWARD_COST, 0)

            # Get claims and approvals counts for this reward for this kid
            # These are stored as dicts with reward_id keys and count values
            reward_claims = kid_info.get(const.DATA_KID_REWARD_CLAIMS, {})
            reward_approvals = kid_info.get(const.DATA_KID_REWARD_APPROVALS, {})

            claims_count = reward_claims.get(reward_id, 0)
            approvals_count = reward_approvals.get(reward_id, 0)

            rewards_attr.append(
                {
                    const.ATTR_EID: reward_eid,
                    const.ATTR_NAME: reward_name,
                    const.ATTR_LABELS: reward_labels,
                    const.ATTR_COST: reward_cost,
                    const.ATTR_CLAIMS: claims_count,
                    const.ATTR_APPROVALS: approvals_count,
                }
            )

        # Sort rewards by name (alphabetically)
        rewards_attr.sort(key=lambda r: r.get(const.ATTR_NAME, "").lower())

        # Badges assigned to this kid
        # Badge applies if: no kids assigned (applies to all) OR kid is in assigned list
        # Exclude cumulative badges as they are a special case
        badges_attr = []
        for badge_id, badge_info in self.coordinator.badges_data.items():
            assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            if assigned_to and self._kid_id not in assigned_to:
                continue
            badge_type = badge_info.get(const.DATA_BADGE_TYPE, const.SENTINEL_EMPTY)
            # Skip cumulative badges (special case)
            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                continue
            badge_name = kh.get_entity_name_or_log_error(
                "badge", badge_id, badge_info, const.DATA_BADGE_NAME
            )
            if not badge_name:
                continue
            # Get BadgeProgressSensor entity_id
            badge_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._kid_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}"
                badge_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )

            # Get badge status from kid's badge progress
            badge_progress = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {}).get(
                badge_id, {}
            )
            badge_status = badge_progress.get(
                const.DATA_KID_BADGE_PROGRESS_STATUS, const.SENTINEL_NONE
            )

            badges_attr.append(
                {
                    const.ATTR_EID: badge_eid,
                    const.ATTR_NAME: badge_name,
                    const.ATTR_BADGE_TYPE: badge_type,
                    const.ATTR_STATUS: badge_status,
                }
            )

        # Sort badges by name (alphabetically)
        badges_attr.sort(key=lambda b: b.get(const.ATTR_NAME, "").lower())

        # Bonuses for this kid
        bonuses_attr = []
        for bonus_id, bonus_info in self.coordinator.bonuses_data.items():
            bonus_name = kh.get_entity_name_or_log_error(
                "bonus", bonus_id, bonus_info, const.DATA_BONUS_NAME
            )
            if not bonus_name:
                continue
            # Get KidBonusAppliedSensor entity_id
            bonus_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._kid_id}_{bonus_id}{const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR}"
                bonus_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )

            # Get bonus points
            bonus_points = bonus_info.get(const.DATA_BONUS_POINTS, 0)

            # Get applied count for this bonus for this kid
            bonus_applies = kid_info.get(const.DATA_KID_BONUS_APPLIES, {})
            applied_count = bonus_applies.get(bonus_id, 0)

            bonuses_attr.append(
                {
                    const.ATTR_EID: bonus_eid,
                    const.ATTR_NAME: bonus_name,
                    const.ATTR_POINTS: bonus_points,
                    const.ATTR_APPLIED: applied_count,
                }
            )

        # Sort bonuses by name (alphabetically)
        bonuses_attr.sort(key=lambda b: b.get(const.ATTR_NAME, "").lower())

        # Penalties for this kid
        penalties_attr = []
        for penalty_id, penalty_info in self.coordinator.penalties_data.items():
            penalty_name = kh.get_entity_name_or_log_error(
                "penalty", penalty_id, penalty_info, const.DATA_PENALTY_NAME
            )
            if not penalty_name:
                continue
            # Get PenaltyAppliesSensor entity_id
            penalty_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._kid_id}_{penalty_id}{const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR}"
                penalty_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )

            # Get penalty points (stored as positive, represents points removed)
            penalty_points = penalty_info.get(const.DATA_PENALTY_POINTS, 0)

            # Get applied count for this penalty for this kid
            penalty_applies = kid_info.get(const.DATA_KID_PENALTY_APPLIES, {})
            applied_count = penalty_applies.get(penalty_id, 0)

            penalties_attr.append(
                {
                    const.ATTR_EID: penalty_eid,
                    const.ATTR_NAME: penalty_name,
                    const.ATTR_POINTS: penalty_points,
                    const.ATTR_APPLIED: applied_count,
                }
            )

        # Sort penalties by name (alphabetically)
        penalties_attr.sort(key=lambda p: p.get(const.ATTR_NAME, "").lower())

        # Achievements assigned to this kid
        achievements_attr = []
        for (
            achievement_id,
            achievement_info,
        ) in self.coordinator.achievements_data.items():
            if self._kid_id not in achievement_info.get(
                const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, []
            ):
                continue
            achievement_name = kh.get_entity_name_or_log_error(
                "achievement",
                achievement_id,
                achievement_info,
                const.DATA_ACHIEVEMENT_NAME,
            )
            if not achievement_name:
                continue
            # Get KidAchievementProgressSensor entity_id
            achievement_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._kid_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}"
                achievement_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )
            achievements_attr.append(
                {
                    const.ATTR_EID: achievement_eid,
                    const.ATTR_NAME: achievement_name,
                }
            )

        # Sort achievements by name (alphabetically)
        achievements_attr.sort(key=lambda a: a.get(const.ATTR_NAME, "").lower())

        # Challenges assigned to this kid
        challenges_attr = []
        for challenge_id, challenge_info in self.coordinator.challenges_data.items():
            if self._kid_id not in challenge_info.get(
                const.DATA_CHALLENGE_ASSIGNED_KIDS, []
            ):
                continue
            challenge_name = kh.get_entity_name_or_log_error(
                "challenge", challenge_id, challenge_info, const.DATA_CHALLENGE_NAME
            )
            if not challenge_name:
                continue
            # Get KidChallengeProgressSensor entity_id
            challenge_eid = None
            if entity_registry:
                unique_id = f"{self._entry.entry_id}_{self._kid_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}"
                challenge_eid = entity_registry.async_get_entity_id(
                    "sensor", const.DOMAIN, unique_id
                )
            challenges_attr.append(
                {
                    const.ATTR_EID: challenge_eid,
                    const.ATTR_NAME: challenge_name,
                }
            )

        # Sort challenges by name (alphabetically)
        challenges_attr.sort(key=lambda c: c.get(const.ATTR_NAME, "").lower())

        # Point adjustment buttons for this kid
        # NOTE: This section MUST iterate entity_registry because we need to find ALL buttons
        # matching a prefix pattern (not a single unique_id). This is acceptable O(n)
        # because it only runs once per dashboard refresh, not per-entity.
        points_buttons_attr = []
        if entity_registry:
            # Find all point adjustment buttons for this kid
            # They follow pattern: {entry_id}_{kid_id}_adjust_points_{delta}
            temp_buttons = []
            for entity in entity_registry.entities.values():
                if (
                    entity.unique_id.startswith(
                        f"{self._entry.entry_id}_{self._kid_id}{const.BUTTON_KC_UID_MIDFIX_ADJUST_POINTS}"
                    )
                    and entity.domain == "button"
                ):
                    # Extract delta from unique_id
                    delta_part = entity.unique_id.split(
                        const.BUTTON_KC_UID_MIDFIX_ADJUST_POINTS
                    )[1]
                    try:
                        delta_value = float(delta_part)
                    except ValueError:
                        delta_value = 0
                    temp_buttons.append(
                        {
                            "eid": entity.entity_id,
                            "name": f"Points {delta_part}",
                            "delta": delta_value,
                        }
                    )
            # Sort by delta value (negatives first, then positives, all ascending)
            temp_buttons.sort(key=lambda x: x["delta"])
            # Remove the delta key used for sorting
            points_buttons_attr = [
                {"eid": btn["eid"], "name": btn["name"]} for btn in temp_buttons
            ]

        # Get kid's preferred dashboard language (default to English)
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        dashboard_language = kid_info.get(
            const.DATA_KID_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
        )

        # Build chores_by_label dictionary
        # Group chores by label, with entity IDs sorted by due date
        chores_by_label = {}
        for chore in chores_attr:
            labels = chore.get(const.ATTR_CHORE_LABELS, [])
            chore_eid = chore.get(const.ATTR_EID)

            # Skip chores without entity IDs
            if not chore_eid:
                continue

            # Add this chore to each label group it belongs to
            for label in labels:
                if label not in chores_by_label:
                    chores_by_label[label] = []
                chores_by_label[label].append(chore)

        # Sort chores within each label by due date (ascending, earliest first)
        # Chores without due dates are placed at the end, sorted by entity_id
        for label, chore_list in chores_by_label.items():
            chore_list.sort(
                key=lambda c: (
                    c.get(const.ATTR_CHORE_DUE_DATE) is None,  # None values go last
                    c.get(const.ATTR_CHORE_DUE_DATE)
                    or "",  # Sort by due_date (ISO format sorts correctly)
                    c.get(const.ATTR_EID)
                    or "",  # Then by entity_id for chores without due dates
                )
            )
            # Convert to list of entity IDs only
            chores_by_label[label] = [c[const.ATTR_EID] for c in chore_list]

        # Sort labels alphabetically for consistent ordering
        chores_by_label = dict(sorted(chores_by_label.items()))

        # Build pending approvals data if flags indicate changes
        pending_approvals = self._build_pending_approvals(entity_registry)

        # Reset change flags after building attributes
        # pylint: disable=protected-access  # Intentional flag reset after rebuild
        self.coordinator._pending_chore_changed = False
        self.coordinator._pending_reward_changed = False

        return {
            "chores": chores_attr,
            const.ATTR_CHORES_BY_LABEL: chores_by_label,
            "rewards": rewards_attr,
            "badges": badges_attr,
            "bonuses": bonuses_attr,
            "penalties": penalties_attr,
            "achievements": achievements_attr,
            "challenges": challenges_attr,
            "points_buttons": points_buttons_attr,
            "pending_approvals": pending_approvals,
            const.ATTR_KID_NAME: self._kid_name,
            "ui_translations": self._ui_translations,
            "language": dashboard_language,
        }

    @property
    def icon(self) -> str:
        """Return a dashboard icon."""
        return "mdi:view-dashboard"
