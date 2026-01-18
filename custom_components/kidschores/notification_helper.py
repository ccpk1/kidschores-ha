# File: notification_helper.py
"""Sends notifications using Home Assistant's notify services.

This module implements a helper for sending notifications in the KidsChores integration.
It supports sending notifications via Home Assistant’s notify services (HA Companion notifications)
and includes an optional payload of actions. For actionable notifications, you must encode extra
context (like kid_id and chore_id) directly into the action string.
All texts and labels are referenced from constants.

Tag System (v0.5.0+):
Tags enable smart notification replacement - sending with the same tag replaces the
previous notification instead of stacking. Use build_notification_tag() to create
consistent tags for aggregated notifications.
ParsedAction (v0.5.0+):
Type-safe dataclass for parsed notification actions. Use parse_notification_action()
to convert pipe-separated action strings into structured ParsedAction objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import const

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# =============================================================================
# ParsedAction Dataclass (v0.5.0+)
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
# Notification Tag Helper
# =============================================================================


def build_notification_tag(tag_type: str, *identifiers: str) -> str:
    """Build a notification tag string for smart replacement.

    Tags allow subsequent notifications with the same tag to replace previous ones
    instead of stacking, reducing notification spam.

    CRITICAL: Apple's apns-collapse-id header has a 64-byte limit. Since identifiers
    are typically UUIDs (36 chars each), we truncate them to 8 chars to stay within
    the limit while maintaining sufficient uniqueness for tag matching.

    Args:
        tag_type: Type of notification (pending, rewards, system, status).
                  Use const.NOTIFY_TAG_TYPE_* constants.
        *identifiers: One or more identifiers to make tag unique.
                     For per-entity tags: (entity_id, kid_id)
                     For per-kid tags: (kid_id,)
                     Identifiers are truncated to first 8 characters.

    Returns:
        Tag string in format: kidschores-{tag_type}-{id1[:8]}-{id2[:8]}-...
        or kidschores-{tag_type} if no identifiers provided.
        Maximum length: ~40 bytes (well under Apple's 64-byte limit).

    Examples:
        build_notification_tag(const.NOTIFY_TAG_TYPE_STATUS, chore_id, kid_id)
        -> "kidschores-status-abc12345-def67890"

        build_notification_tag(const.NOTIFY_TAG_TYPE_SYSTEM, kid_id)
        -> "kidschores-system-abc12345"
    """
    if identifiers:
        # Truncate each identifier to 8 chars to stay under Apple's 64-byte limit
        # Full UUIDs = 91 bytes ("kidschores-status-" + 36 + "-" + 36)
        # Truncated = ~42 bytes ("kidschores-status-" + 8 + "-" + 8)
        truncated_ids = "-".join(identifier[:8] for identifier in identifiers)
        return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}-{truncated_ids}"
    return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}"


def build_claim_action(kid_id: str, chore_id: str) -> list[dict[str, str]]:
    """Build a claim action button for kid notifications.

    Returns a single action button for kids to claim a chore directly from
    a notification (e.g., overdue or due-soon reminders).

    Args:
        kid_id: The internal ID of the kid
        chore_id: The internal ID of the chore

    Returns:
        List containing one action dictionary with 'action' and 'title' keys.
        The 'action' is a pipe-separated string: "CLAIM_CHORE|kid_id|chore_id"

    Example:
        actions = build_claim_action("kid-123", "chore-456")
        # Returns:
        # [{"action": "CLAIM_CHORE|kid-123|chore-456", "title": "notif_action_claim"}]
    """
    return [
        {
            const.NOTIFY_ACTION: f"{const.ACTION_CLAIM_CHORE}|{kid_id}|{chore_id}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_CLAIM,
        },
    ]


def build_skip_action(kid_id: str, chore_id: str) -> list[dict[str, str]]:
    """Build skip action button for overdue chores.

    Skip action resets the chore to PENDING state and reschedules it to the
    next due date. Handles INDEPENDENT (per-kid) vs SHARED (all kids) logic.

    Args:
        kid_id: The internal ID of the kid
        chore_id: The internal ID of the chore

    Returns:
        List with single action dict for Skip button
    """
    return [
        {
            const.NOTIFY_ACTION: f"{const.ACTION_SKIP_CHORE}|{kid_id}|{chore_id}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_SKIP,
        },
    ]


def build_complete_action(kid_id: str, chore_id: str) -> list[dict[str, str]]:
    """Build complete action button for overdue chores.

    Complete action directly approves the chore for the kid without requiring
    a claim step first. Parent can mark overdue chores complete from notification.

    Args:
        kid_id: The internal ID of the kid
        chore_id: The internal ID of the chore

    Returns:
        List with single action dict for Complete button
    """
    return [
        {
            const.NOTIFY_ACTION: f"{const.ACTION_COMPLETE_FOR_KID}|{kid_id}|{chore_id}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_COMPLETE,
        },
    ]


def build_remind_action(kid_id: str, chore_id: str) -> list[dict[str, str]]:
    """Build remind action button for chore notifications.

    Remind action schedules a follow-up reminder notification in 30 minutes.

    Args:
        kid_id: The internal ID of the kid
        chore_id: The internal ID of the chore

    Returns:
        List with single action dict for Remind button
    """
    return [
        {
            const.NOTIFY_ACTION: f"{const.ACTION_REMIND_30}|{kid_id}|{chore_id}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_REMIND_30,
        },
    ]


def build_chore_actions(kid_id: str, chore_id: str) -> list[dict[str, str]]:
    """Build standard notification actions for chore workflows.

    Returns the three standard action buttons for chore notifications:
    - Approve: Marks the chore as approved and awards points
    - Disapprove: Rejects the chore claim, resetting to pending
    - Remind in 30: Schedules a follow-up reminder notification

    Args:
        kid_id: The internal ID of the kid
        chore_id: The internal ID of the chore

    Returns:
        List of action dictionaries with 'action' and 'title' keys.
        The 'action' is a pipe-separated string: "ACTION_TYPE|kid_id|chore_id"
        The 'title' is a translation key for localized button text.

    Example:
        actions = build_chore_actions("kid-123", "chore-456")
        # Returns:
        # [
        #     {"action": "approve_chore|kid-123|chore-456", "title": "notification_action_approve"},
        #     {"action": "disapprove_chore|kid-123|chore-456", "title": "notification_action_disapprove"},
        #     {"action": "remind_30|kid-123|chore-456", "title": "notification_action_remind_30"},
        # ]
    """
    return [
        {
            const.NOTIFY_ACTION: f"{const.ACTION_APPROVE_CHORE}|{kid_id}|{chore_id}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_APPROVE,
        },
        {
            const.NOTIFY_ACTION: f"{const.ACTION_DISAPPROVE_CHORE}|{kid_id}|{chore_id}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_DISAPPROVE,
        },
        {
            const.NOTIFY_ACTION: f"{const.ACTION_REMIND_30}|{kid_id}|{chore_id}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_REMIND_30,
        },
    ]


def build_reward_actions(
    kid_id: str, reward_id: str, notif_id: str | None = None
) -> list[dict[str, str]]:
    """Build standard notification actions for reward workflows.

    Returns the three standard action buttons for reward notifications:
    - Approve: Confirms the reward claim and deducts points
    - Disapprove: Rejects the reward claim, refunding any held points
    - Remind in 30: Schedules a follow-up reminder notification

    Args:
        kid_id: The internal ID of the kid
        reward_id: The internal ID of the reward
        notif_id: Optional notification tracking ID for deduplication.
                  When provided, appended to action string for tracking.

    Returns:
        List of action dictionaries with 'action' and 'title' keys.
        The 'action' is a pipe-separated string:
        - Without notif_id: "ACTION_TYPE|kid_id|reward_id"
        - With notif_id: "ACTION_TYPE|kid_id|reward_id|notif_id"

    Example:
        actions = build_reward_actions("kid-123", "reward-456", "notif-789")
        # Returns:
        # [
        #     {"action": "approve_reward|kid-123|reward-456|notif-789", ...},
        #     {"action": "disapprove_reward|kid-123|reward-456|notif-789", ...},
        #     {"action": "remind_30|kid-123|reward-456|notif-789", ...},
        # ]
    """
    # Build action suffix (notif_id is optional)
    suffix = f"|{notif_id}" if notif_id else ""

    return [
        {
            const.NOTIFY_ACTION: f"{const.ACTION_APPROVE_REWARD}|{kid_id}|{reward_id}{suffix}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_APPROVE,
        },
        {
            const.NOTIFY_ACTION: f"{const.ACTION_DISAPPROVE_REWARD}|{kid_id}|{reward_id}{suffix}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_DISAPPROVE,
        },
        {
            const.NOTIFY_ACTION: f"{const.ACTION_REMIND_30}|{kid_id}|{reward_id}{suffix}",
            const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_REMIND_30,
        },
    ]


def build_extra_data(
    kid_id: str,
    chore_id: str | None = None,
    reward_id: str | None = None,
    notif_id: str | None = None,
) -> dict[str, str]:
    """Build consistent extra_data dictionary for notification context.

    Extra data is included in the notification payload for deep-linking
    and context retrieval when processing action callbacks.

    Args:
        kid_id: The internal ID of the kid (always required)
        chore_id: Optional chore internal ID (for chore notifications)
        reward_id: Optional reward internal ID (for reward notifications)
        notif_id: Optional notification tracking ID

    Returns:
        Dictionary with relevant context keys. Only includes non-None values.

    Example:
        extra_data = build_extra_data("kid-123", chore_id="chore-456")
        # Returns: {"kid_id": "kid-123", "chore_id": "chore-456"}

        extra_data = build_extra_data("kid-123", reward_id="reward-456", notif_id="notif-789")
        # Returns: {"kid_id": "kid-123", "reward_id": "reward-456", "notification_id": "notif-789"}
    """
    data: dict[str, str] = {const.DATA_KID_ID: kid_id}

    if chore_id:
        data[const.DATA_CHORE_ID] = chore_id
    if reward_id:
        data[const.DATA_REWARD_ID] = reward_id
    if notif_id:
        data[const.NOTIFY_NOTIFICATION_ID] = notif_id

    return data


async def async_send_notification(
    hass: HomeAssistant,
    notify_service: str,
    title: str,
    message: str,
    actions: list[dict[str, str]] | None = None,
    extra_data: dict[str, str] | None = None,
) -> None:
    """Send a notification using the specified notify service.

    Gracefully handles missing notification services (common in fresh installs,
    migrations, or when mobile app isn't configured yet). If the service doesn't
    exist, logs a warning and returns without raising an exception.
    """

    # Parse service name into domain and service components
    if const.DISPLAY_DOT not in notify_service:
        domain = const.NOTIFY_DOMAIN
        service = notify_service
    else:
        domain, service = notify_service.split(".", 1)

    # Validate service exists before attempting to send
    if not hass.services.has_service(domain, service):
        const.LOGGER.warning(
            "Notification service '%s.%s' not available - skipping notification. "
            "This is normal during migration or if the mobile app/notification "
            "integration isn't configured yet. To enable notifications, configure "
            "the '%s' integration and set up the notification service.",
            domain,
            service,
            domain,
        )
        return  # Gracefully skip instead of raising

    # Build notification payload
    payload: dict[str, Any] = {const.NOTIFY_TITLE: title, const.NOTIFY_MESSAGE: message}

    if actions:
        data = payload.setdefault(const.NOTIFY_DATA, {})
        data[const.NOTIFY_ACTIONS] = actions

    if extra_data:
        data = payload.setdefault(const.NOTIFY_DATA, {})
        data.update(extra_data)

    # Log full payload for debugging (useful for testing translations)
    const.LOGGER.debug(
        "DEBUG: Notification payload for '%s.%s': title='%s', message='%s', actions=%s",
        domain,
        service,
        title,
        message,
        actions,
    )

    try:
        await hass.services.async_call(domain, service, payload, blocking=True)
        const.LOGGER.debug("DEBUG: Notification sent via '%s.%s'", domain, service)

    except Exception as err:
        # Broad exception allowed: This runs in fire-and-forget background tasks
        # per AGENTS.md guidelines. We must catch all exceptions to prevent
        # "Task exception was never retrieved" errors in logs.
        const.LOGGER.error(
            "ERROR: Unexpected error sending notification via '%s.%s': %s. Payload: %s",
            domain,
            service,
            err,
            payload,
        )
        # Don't re-raise - log and skip gracefully to prevent task exceptions
        # from cluttering logs during migration or service configuration issues
