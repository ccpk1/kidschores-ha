# File: notification_action_handler.py
"""Handle notification actions from HA companion notifications.

This module processes notification action callbacks from the HA Companion app.
When a user taps an action button on a notification, this handler routes the
action to the appropriate coordinator method.

Separation of concerns (v0.5.0+):
- notification_action_handler.py = "The Router" (INCOMING action button callbacks)
- NotificationManager = "The Voice" (OUTGOING notifications)

ParsedAction dataclass and parse_notification_action() live here because they
are used for INCOMING action parsing, not outgoing notification building.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from homeassistant.exceptions import HomeAssistantError

from . import const

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

    from .coordinator import KidsChoresDataCoordinator
    from .type_defs import KidData


# =============================================================================
# ParsedAction Dataclass
# =============================================================================


@dataclass
class ParsedAction:
    """Type-safe parsed notification action.

    Represents a notification action string parsed into its components.
    Action strings are pipe-separated: "action_type|kid_id|entity_id[|notif_id]"

    Attributes:
        action_type: The action constant (e.g., ACTION_APPROVE_CHORE)
        kid_id: The internal ID of the kid
        entity_id: The chore_id or reward_id depending on action type
        notif_id: Optional notification tracking ID (rewards only)

    Example:
        # Chore action: "approve_chore|kid-123|chore-456"
        parsed = ParsedAction(
            action_type="approve_chore",
            kid_id="kid-123",
            entity_id="chore-456",
        )

        # Reward action: "approve_reward|kid-123|reward-456|notif-789"
        parsed = ParsedAction(
            action_type="approve_reward",
            kid_id="kid-123",
            entity_id="reward-456",
            notif_id="notif-789",
        )
    """

    action_type: str
    kid_id: str
    entity_id: str  # chore_id or reward_id
    notif_id: str | None = None

    @property
    def is_chore_action(self) -> bool:
        """Check if this is a chore-related action."""
        return self.action_type in (
            const.ACTION_APPROVE_CHORE,
            const.ACTION_CLAIM_CHORE,
            const.ACTION_DISAPPROVE_CHORE,
        )

    @property
    def is_reward_action(self) -> bool:
        """Check if this is a reward-related action."""
        return self.action_type in (
            const.ACTION_APPROVE_REWARD,
            const.ACTION_DISAPPROVE_REWARD,
        )

    @property
    def is_reminder_action(self) -> bool:
        """Check if this is a reminder action."""
        return self.action_type == const.ACTION_REMIND_30

    @property
    def chore_id(self) -> str | None:
        """Get chore_id if this is a chore action, else None."""
        if self.is_chore_action or (self.is_reminder_action and self.notif_id is None):
            return self.entity_id
        return None

    @property
    def reward_id(self) -> str | None:
        """Get reward_id if this is a reward action, else None."""
        if self.is_reward_action or (
            self.is_reminder_action and self.notif_id is not None
        ):
            return self.entity_id
        return None


def parse_notification_action(action_field: str) -> ParsedAction | None:
    """Parse a notification action string into a structured ParsedAction.

    Handles both chore actions (3 parts) and reward actions (4 parts).
    Returns None for invalid or unrecognized action formats.

    Action string formats:
    - Chore: "action_type|kid_id|chore_id"
    - Reward: "action_type|kid_id|reward_id|notif_id"
    - Reminder (chore): "remind_30|kid_id|chore_id"
    - Reminder (reward): "remind_30|kid_id|reward_id|notif_id"

    Args:
        action_field: Pipe-separated action string from notification callback

    Returns:
        ParsedAction object if valid, None if invalid/malformed

    Example:
        parsed = parse_notification_action("approve_chore|kid-123|chore-456")
        if parsed:
            print(parsed.kid_id)  # "kid-123"
            print(parsed.chore_id)  # "chore-456"
    """
    if not action_field:
        const.LOGGER.warning("Empty action field provided to parse_notification_action")
        return None

    parts = action_field.split("|")

    if len(parts) < 3:
        const.LOGGER.warning(
            "Invalid action format (expected at least 3 parts): %s", action_field
        )
        return None

    action_type = parts[0]
    kid_id = parts[1]
    entity_id = parts[2]
    notif_id = parts[3] if len(parts) >= 4 else None

    # Validate action type is recognized
    valid_actions = (
        const.ACTION_APPROVE_CHORE,
        const.ACTION_CLAIM_CHORE,
        const.ACTION_COMPLETE_FOR_KID,
        const.ACTION_DISAPPROVE_CHORE,
        const.ACTION_APPROVE_REWARD,
        const.ACTION_DISAPPROVE_REWARD,
        const.ACTION_REMIND_30,
        const.ACTION_SKIP_CHORE,
    )

    if action_type not in valid_actions:
        const.LOGGER.warning(
            "Unrecognized action type '%s' in: %s", action_type, action_field
        )
        return None

    # Reward actions require notif_id
    if action_type in (const.ACTION_APPROVE_REWARD, const.ACTION_DISAPPROVE_REWARD):
        if not notif_id:
            const.LOGGER.warning("Reward action missing notif_id: %s", action_field)
            return None

    return ParsedAction(
        action_type=action_type,
        kid_id=kid_id,
        entity_id=entity_id,
        notif_id=notif_id,
    )


# =============================================================================
# Action Handler
# =============================================================================


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
            await coordinator.chore_manager.approve_chore(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_CLAIM_CHORE:
            # Kid claiming chore from notification (e.g., overdue reminder)
            kid_info: KidData = cast(
                "KidData", coordinator.kids_data.get(parsed.kid_id, {})
            )
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
            # Async method with lock protection
            await coordinator.chore_manager.claim_chore(
                kid_id=parsed.kid_id,
                chore_id=parsed.entity_id,
                user_name=kid_name,
            )
        elif parsed.action_type == const.ACTION_COMPLETE_FOR_KID:
            # Parent completes chore directly (no claim needed)
            await coordinator.chore_manager.approve_chore(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_DISAPPROVE_CHORE:
            await coordinator.chore_manager.disapprove_chore(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_SKIP_CHORE:
            # Reset overdue chore to pending and reschedule
            await coordinator.chore_manager.reset_overdue_chores(
                chore_id=parsed.entity_id,
                kid_id=parsed.kid_id,
            )
        elif parsed.action_type == const.ACTION_APPROVE_REWARD:
            await coordinator.reward_manager.approve(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                reward_id=parsed.entity_id,
                notif_id=parsed.notif_id,
            )
        elif parsed.action_type == const.ACTION_DISAPPROVE_REWARD:
            # Async method with lock protection
            await coordinator.reward_manager.disapprove(
                parent_name=parent_name,
                kid_id=parsed.kid_id,
                reward_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_REMIND_30:
            # Reminder can be for chore or reward - use computed properties
            await coordinator.notification_manager.remind_in_minutes(
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
