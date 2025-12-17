"""Legacy sensors for the KidsChores integration.

This file contains optional legacy sensors that are maintained for backward compatibility.
These sensors are only created when CONF_SHOW_LEGACY_ENTITIES is enabled in config options.

Legacy sensors are candidates for deprecation in future versions as their data is now
available as attributes on modern sensor entities, providing better data organization
without entity clutter.

Available Legacy Sensors (11 total):

System Chore Approval Sensors (4):
1. SystemChoreApprovalsSensor - Total chores completed (data in KidChoresSensor attributes)
2. SystemChoreApprovalsDailySensor - Daily chores completed (data in SystemChoreApprovalsSensor attributes)
3. SystemChoreApprovalsWeeklySensor - Weekly chores completed (data in SystemChoreApprovalsSensor attributes)
4. SystemChoreApprovalsMonthlySensor - Monthly chores completed (data in SystemChoreApprovalsSensor attributes)

Pending Approval Sensors (2):
5. SystemChoresPendingApprovalSensor - Pending chore approvals (global)
6. SystemRewardsPendingApprovalSensor - Pending reward approvals (global)

Kid Points Earned Sensors (3):
7. KidPointsEarnedDailySensor - Daily points earned (data in KidPointsSensor attributes)
8. KidPointsEarnedWeeklySensor - Weekly points earned (data in KidPointsSensor attributes)
9. KidPointsEarnedMonthlySensor - Monthly points earned (data in KidPointsSensor attributes)

Streak Sensor (1):
10. KidChoreStreakSensor - Highest chore streak (data in KidPointsSensor attributes)

Max Points Sensor (1):
11. KidMaxPointsEverSensor - Maximum points ever reached (data in KidPointsSensor attributes)
"""

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_registry import async_get

from . import const
from . import kc_helpers as kh
from .coordinator import KidsChoresDataCoordinator
from .entity import KidsChoresCoordinatorEntity

# ------------------------------------------------------------------------------------------
# KID MAX POINTS SENSOR
# ------------------------------------------------------------------------------------------


class KidMaxPointsEverSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor showing the maximum points a kid has ever reached.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_highest_balance'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_MAX_POINTS_EVER_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the legacy max points sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_MAX_POINTS_EVER_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_POINTS: points_label,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_MAX_POINTS_EARNED_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return the highest points total the kid has ever reached."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
        return point_stats.get(
            const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, const.DEFAULT_ZERO
        )

    @property
    def icon(self) -> str:
        """Use the same icon as points or any custom icon you prefer."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def native_unit_of_measurement(self) -> str:
        """Optionally display the same points label for consistency."""
        return self._points_label or const.LABEL_POINTS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


# ------------------------------------------------------------------------------------------
# SYSTEM CHORE APPROVAL SENSORS
# ------------------------------------------------------------------------------------------


class SystemChoreApprovalsSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking total chores completed by kid since integration start.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_approved_all_time'
    attribute on the KidChoresSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_TOTAL_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy total chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        self._attr_icon = const.DEFAULT_COMPLETED_CHORES_TOTAL_SENSOR_ICON
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_TOTAL_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return the total number of chores completed by the kid."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        return stats.get(
            const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, const.DEFAULT_ZERO
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


class SystemChoreApprovalsDailySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed today.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_approved_today'
    attribute on the SystemChoreApprovalsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_DAILY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy daily chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        self._attr_icon = const.DEFAULT_COMPLETED_CHORES_DAILY_SENSOR_ICON
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_DAILY_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return the number of chores completed today."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        return stats.get(const.DATA_KID_CHORE_STATS_APPROVED_TODAY, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


class SystemChoreApprovalsWeeklySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed this week.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_approved_week'
    attribute on the SystemChoreApprovalsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_WEEKLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy weekly chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        self._attr_icon = const.DEFAULT_COMPLETED_CHORES_WEEKLY_SENSOR_ICON
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_WEEKLY_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return the number of chores completed this week."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        return stats.get(const.DATA_KID_CHORE_STATS_APPROVED_WEEK, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


class SystemChoreApprovalsMonthlySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed this month.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_approved_month'
    attribute on the SystemChoreApprovalsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_MONTHLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy monthly chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        self._attr_icon = const.DEFAULT_COMPLETED_CHORES_MONTHLY_SENSOR_ICON
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_MONTHLY_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return the number of chores completed this month."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        return stats.get(const.DATA_KID_CHORE_STATS_APPROVED_MONTH, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


# ------------------------------------------------------------------------------------------
# PENDING APPROVAL SENSORS
# ------------------------------------------------------------------------------------------


class SystemChoresPendingApprovalSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor listing all pending chore approvals."""

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENDING_CHORES_APPROVALS_SENSOR

    def __init__(
        self, coordinator: KidsChoresDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}"
        self._attr_icon = const.DEFAULT_PENDING_CHORE_APPROVALS_SENSOR_ICON
        self._attr_native_unit_of_measurement = const.DEFAULT_PENDING_CHORES_UNIT
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}"
        self._attr_device_info = kh.create_system_device_info(entry)

    @property
    def native_value(self) -> str:
        """Return a summary of pending chore approvals."""
        approvals = self.coordinator.pending_chore_approvals
        return f"{len(approvals)}"

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, Any]]]:
        """Return detailed pending chores."""
        approvals = self.coordinator.pending_chore_approvals
        grouped_by_kid: dict[str, list[dict[str, Any]]] = {}

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        for approval in approvals:
            kid_id = approval[const.DATA_KID_ID]
            chore_id = approval[const.DATA_CHORE_ID]
            kid_name = (
                kh.get_kid_name_by_id(self.coordinator, kid_id)
                or const.TRANS_KEY_DISPLAY_UNKNOWN_KID
            )
            chore_info = self.coordinator.chores_data.get(chore_id, {})
            chore_name = chore_info.get(
                const.DATA_CHORE_NAME, const.TRANS_KEY_DISPLAY_UNKNOWN_CHORE
            )

            timestamp = approval[const.DATA_CHORE_TIMESTAMP]

            # Get approve and disapprove button entity IDs using direct lookup
            approve_button_eid = None
            disapprove_button_eid = None
            if entity_registry:
                try:
                    approve_unique_id = f"{self._entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
                    disapprove_unique_id = f"{self._entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"

                    approve_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, approve_unique_id
                    )
                    disapprove_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, disapprove_unique_id
                    )
                except (KeyError, ValueError, AttributeError):
                    pass

            if kid_name not in grouped_by_kid:
                grouped_by_kid[kid_name] = []

            grouped_by_kid[kid_name].append(
                {
                    const.ATTR_CHORE_NAME: chore_name,
                    const.ATTR_CLAIMED_ON: timestamp,
                    const.ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID: approve_button_eid,
                    const.ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID: disapprove_button_eid,
                }
            )

        return grouped_by_kid


class SystemRewardsPendingApprovalSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor listing all pending reward approvals."""

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENDING_REWARDS_APPROVALS_SENSOR

    def __init__(
        self, coordinator: KidsChoresDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}"
        self._attr_icon = const.DEFAULT_PENDING_REWARD_APPROVALS_SENSOR_ICON
        self._attr_native_unit_of_measurement = const.DEFAULT_PENDING_REWARDS_UNIT
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}"
        self._attr_device_info = kh.create_system_device_info(entry)

    @property
    def native_value(self) -> str:
        """Return a summary of pending reward approvals."""
        approvals = self.coordinator.pending_reward_approvals
        return f"{len(approvals)}"

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, Any]]]:
        """Return detailed pending rewards."""
        approvals = self.coordinator.pending_reward_approvals
        grouped_by_kid: dict[str, list[dict[str, Any]]] = {}

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        for approval in approvals:
            kid_id = approval[const.DATA_KID_ID]
            reward_id = approval[const.DATA_REWARD_ID]
            kid_name = (
                kh.get_kid_name_by_id(self.coordinator, kid_id)
                or const.TRANS_KEY_DISPLAY_UNKNOWN_KID
            )
            reward_info = self.coordinator.rewards_data.get(reward_id, {})
            reward_name = reward_info.get(
                const.DATA_REWARD_NAME, const.TRANS_KEY_DISPLAY_UNKNOWN_REWARD
            )

            timestamp = approval[const.DATA_REWARD_TIMESTAMP]

            # Get approve and disapprove button entity IDs using direct lookup
            approve_button_eid = None
            disapprove_button_eid = None
            if entity_registry:
                try:
                    approve_unique_id = f"{self._entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
                    disapprove_unique_id = f"{self._entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"

                    approve_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, approve_unique_id
                    )
                    disapprove_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, disapprove_unique_id
                    )
                except (KeyError, ValueError, AttributeError):
                    pass

            if kid_name not in grouped_by_kid:
                grouped_by_kid[kid_name] = []

            grouped_by_kid[kid_name].append(
                {
                    const.ATTR_REWARD_NAME: reward_name,
                    const.ATTR_REDEEMED_ON: timestamp,
                    const.ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID: approve_button_eid,
                    const.ATTR_REWARD_DISAPPROVE_BUTTON_ENTITY_ID: disapprove_button_eid,
                }
            )

        return grouped_by_kid


# ------------------------------------------------------------------------------------------
# KID POINTS EARNED SENSORS
# ------------------------------------------------------------------------------------------


class KidPointsEarnedDailySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points a kid earned today.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_today'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_POINTS_EARNED_DAILY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return how many net points the kid has earned so far today."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
        return point_stats.get(const.DATA_KID_POINT_STATS_NET_TODAY, const.DEFAULT_ZERO)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str:
        """Use the points' custom icon if set, else fallback."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidPointsEarnedWeeklySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points a kid earned this week.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_week'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_POINTS_EARNED_WEEKLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return how many net points the kid has earned this week."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
        return point_stats.get(const.DATA_KID_POINT_STATS_NET_WEEK, const.DEFAULT_ZERO)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str:
        """Use the points' custom icon if set, else fallback."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidPointsEarnedMonthlySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points a kid earned this month.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_month'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_POINTS_EARNED_MONTHLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return how many net points the kid has earned this month."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
        return point_stats.get(const.DATA_KID_POINT_STATS_NET_MONTH, const.DEFAULT_ZERO)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str:
        """Use the points' custom icon if set, else fallback."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_KID_NAME: self._kid_name,
        }


# ------------------------------------------------------------------------------------------
# STREAK SENSOR
# ------------------------------------------------------------------------------------------


class KidChoreStreakSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor returning the highest current streak among streak-type achievements for a kid.

    NOTE: This sensor is legacy/optional. Data is now available as chore_stats attributes
    on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_HIGHEST_STREAK_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
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
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_HIGHEST_STREAK_SENSOR}"
        # No unit of measurement - streak is a count, not a duration
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_HIGHEST_STREAK_SENSOR}"
        self._attr_device_info = kh.create_kid_device_info(kid_id, kid_name, entry)

    @property
    def native_value(self) -> int:
        """Return the highest current streak among all streak achievements for the kid."""
        kid_info = self.coordinator.kids_data.get(self._kid_id, {})
        chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        return chore_stats.get(
            const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME, const.DEFAULT_ZERO
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes including individual streaks per achievement."""
        streaks: dict[str, int] = {}
        for achievement in self.coordinator.achievements_data.values():
            if (
                achievement.get(const.DATA_ACHIEVEMENT_TYPE)
                == const.ACHIEVEMENT_TYPE_STREAK
            ):
                achievement_name = achievement.get(
                    const.DATA_ACHIEVEMENT_NAME, const.DISPLAY_UNKNOWN
                )
                progress_for_kid = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(self._kid_id)

                if isinstance(progress_for_kid, dict):
                    streaks[achievement_name] = progress_for_kid.get(
                        const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                    )

                elif isinstance(progress_for_kid, int):
                    streaks[achievement_name] = progress_for_kid

        return {
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_STREAKS_BY_ACHIEVEMENT: streaks,
        }

    @property
    def icon(self) -> str:
        """Return an icon for 'highest streak'."""
        return const.DEFAULT_STREAK_ICON
