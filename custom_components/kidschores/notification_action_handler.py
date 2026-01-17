# File: notification_action_handler.py
"""Handle notification actions from HA companion notifications.

This module processes notification action callbacks from the HA Companion app.
When a user taps an action button on a notification, this handler routes the
action to the appropriate coordinator method.

Refactored in v0.5.0 to use ParsedAction for type-safe action parsing.
"""

from typing import TYPE_CHECKING

from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import const
from .notification_helper import parse_notification_action

if TYPE_CHECKING:
    from .coordinator import KidsChoresDataCoordinator


async def async_handle_notification_action(hass: HomeAssistant, event: Event) -> None:
    """Handle notification actions from HA companion notifications.

    Parses the action string from the event, validates it using ParsedAction,
    and routes to the appropriate coordinator method.

    Args:
        hass: Home Assistant instance
        event: Event containing the notification action data
    """
    action_field = event.data.get(const.NOTIFY_ACTION)
    if not action_field:
        const.LOGGER.error("No action found in event data: %s", event.data)
        return

    # Parse action string into typed ParsedAction object (v0.5.0+)
    parsed = parse_notification_action(action_field)
    if parsed is None:
        # parse_notification_action already logs warnings for invalid formats
        const.LOGGER.error("Failed to parse notification action: %s", action_field)
        return

    # Parent name may be provided in the event data or use a default
    parent_name = event.data.get(
        const.NOTIFY_PARENT_NAME, const.NOTIFY_DEFAULT_PARENT_NAME
    )

    # Retrieve the coordinator
    domain_data = hass.data.get(const.DOMAIN, {})
    if not domain_data:
        const.LOGGER.error("KidsChores data not found")
        return

    entry_id = next(iter(domain_data))
    coordinator: KidsChoresDataCoordinator = domain_data[entry_id].get(
        const.COORDINATOR
    )
    if not coordinator:
        const.LOGGER.error("KidsChores coordinator not found")
        return

    try:
        if parsed.action_type == const.ACTION_APPROVE_CHORE:
            await coordinator.approve_chore(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_CLAIM_CHORE:
            # Kid claiming chore from notification (e.g., overdue reminder)
            kid_info = coordinator.kids_data.get(parsed.kid_id, {})
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
            coordinator.claim_chore(
                kid_id=parsed.kid_id,
                chore_id=parsed.entity_id,
                user_name=kid_name,
            )
        elif parsed.action_type == const.ACTION_DISAPPROVE_CHORE:
            coordinator.disapprove_chore(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_APPROVE_REWARD:
            await coordinator.approve_reward(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                reward_id=parsed.entity_id,
                notif_id=parsed.notif_id,
            )
        elif parsed.action_type == const.ACTION_DISAPPROVE_REWARD:
            coordinator.disapprove_reward(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                reward_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_REMIND_30:
            # Reminder can be for chore or reward - use computed properties
            await coordinator.remind_in_minutes(
                kid_id=parsed.kid_id,
                chore_id=parsed.chore_id,
                reward_id=parsed.reward_id,
                minutes=const.DEFAULT_REMINDER_DELAY,
            )
        else:
            # This shouldn't happen - parse_notification_action validates action types
            const.LOGGER.error(
                "Received unknown notification action: %s", parsed.action_type
            )
    except HomeAssistantError as err:
        const.LOGGER.error(
            "Failed processing notification action %s: %s", parsed.action_type, err
        )
