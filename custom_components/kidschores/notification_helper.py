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
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import const

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def build_notification_tag(tag_type: str, identifier: str = "") -> str:
    """Build a notification tag string for smart replacement.

    Tags allow subsequent notifications with the same tag to replace previous ones
    instead of stacking, reducing notification spam.

    Args:
        tag_type: Type of notification (pending, rewards, system, status).
                  Use const.NOTIFY_TAG_TYPE_* constants.
        identifier: Optional identifier (usually kid_id) to make tag unique per entity.

    Returns:
        Tag string in format: kidschores-{tag_type}-{identifier}
        or kidschores-{tag_type} if no identifier provided.

    Example:
        build_notification_tag(const.NOTIFY_TAG_TYPE_PENDING, kid_id)
        -> "kidschores-pending-abc123"
    """
    if identifier:
        return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}-{identifier}"
    return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}"


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
