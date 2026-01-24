# File: notification_manager.py
"""Notification Manager for KidsChores integration.

This manager handles all outgoing notification logic:
- Sending notifications to kids and parents
- Translation and localization
- Action button building
- Notification tag management for smart replacement

Separation of concerns (v0.5.0+):
- NotificationManager = "The Voice" (OUTGOING notifications)
- notification_action_handler.py = "The Router" (INCOMING action button callbacks)
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

from custom_components.kidschores import const, kc_helpers as kh

from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.type_defs import ChoreData, KidData, RewardData


# =============================================================================
# Module-level helper for testability
# =============================================================================


async def async_send_notification(
    hass: HomeAssistant,
    service: str,
    title: str,
    message: str,
    actions: list[dict[str, Any]] | None = None,
    extra_data: dict[str, Any] | None = None,
) -> None:
    """Send a notification via Home Assistant service call.

    This is a module-level function that can be easily mocked in tests.
    It wraps the raw hass.services.async_call for notification services.

    Args:
        hass: Home Assistant instance
        service: Notification service in format "notify.service_name" or just service name
        title: Notification title
        message: Notification message
        actions: Optional list of action button dictionaries
        extra_data: Optional extra data (e.g., tag, notification_id)
    """
    # Parse domain/service
    if "." in service:
        domain, svc = service.split(".", 1)
    else:
        domain = const.NOTIFY_DOMAIN
        svc = service

    # Build payload
    payload: dict[str, Any] = {
        const.NOTIFY_TITLE: title,
        const.NOTIFY_MESSAGE: message,
    }

    if actions:
        data = payload.setdefault(const.NOTIFY_DATA, {})
        data[const.NOTIFY_ACTIONS] = actions

    if extra_data:
        data = payload.setdefault(const.NOTIFY_DATA, {})
        data.update(extra_data)

    const.LOGGER.debug(
        "async_send_notification: %s.%s - title='%s', message='%s'",
        domain,
        svc,
        title,
        message,
    )

    await hass.services.async_call(domain, svc, payload, blocking=True)


class NotificationManager(BaseManager):
    """Manager for sending notifications to kids and parents.

    Responsibilities:
    - Send translated notifications to kids
    - Send translated notifications to parents
    - Build notification action buttons
    - Handle notification tag generation for smart replacement
    - Clear notifications via tag

    Uses coordinator for:
    - kids_data, parents_data, chores_data, rewards_data lookups
    - Test mode detection (_test_mode flag)
    """

    # =========================================================================
    # Initialization
    # =========================================================================

    def __init__(
        self, hass: HomeAssistant, coordinator: KidsChoresDataCoordinator
    ) -> None:
        """Initialize notification manager.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator for data access
        """
        super().__init__(hass, coordinator)
        # No additional state needed - manager delegates to coordinator data

    async def async_setup(self) -> None:
        """Set up the notification manager.

        Currently no event subscriptions needed. Notifications are fire-and-forget.
        """
        const.LOGGER.debug(
            "NotificationManager initialized for entry %s", self.entry_id
        )

    # =========================================================================
    # Notification Tag Helper
    # =========================================================================

    @staticmethod
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
            truncated_ids = "-".join(identifier[:8] for identifier in identifiers)
            return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}-{truncated_ids}"
        return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}"

    # =========================================================================
    # Action Button Builders
    # =========================================================================

    @staticmethod
    def build_claim_action(kid_id: str, chore_id: str) -> list[dict[str, str]]:
        """Build a claim action button for kid notifications.

        Returns a single action button for kids to claim a chore directly from
        a notification (e.g., overdue or due-soon reminders).

        Args:
            kid_id: The internal ID of the kid
            chore_id: The internal ID of the chore

        Returns:
            List containing one action dictionary with 'action' and 'title' keys.
        """
        return [
            {
                const.NOTIFY_ACTION: f"{const.ACTION_CLAIM_CHORE}|{kid_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_CLAIM,
            },
        ]

    @staticmethod
    def build_skip_action(kid_id: str, chore_id: str) -> list[dict[str, str]]:
        """Build skip action button for overdue chores.

        Skip action resets the chore to PENDING state and reschedules it to the
        next due date.

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

    @staticmethod
    def build_complete_action(kid_id: str, chore_id: str) -> list[dict[str, str]]:
        """Build complete action button for overdue chores.

        Complete action directly approves the chore for the kid without requiring
        a claim step first.

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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

        Returns:
            List of action dictionaries with 'action' and 'title' keys.
        """
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

    @staticmethod
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
        """
        data: dict[str, str] = {const.DATA_KID_ID: kid_id}

        if chore_id:
            data[const.DATA_CHORE_ID] = chore_id
        if reward_id:
            data[const.DATA_REWARD_ID] = reward_id
        if notif_id:
            data[const.NOTIFY_NOTIFICATION_ID] = notif_id

        return data

    # =========================================================================
    # Translation Helpers
    # =========================================================================

    def _convert_notification_key(self, const_key: str) -> str:
        """Convert const translation key to JSON key.

        Removes notification prefix from const keys:
        - "notification_title_chore_assigned" -> "chore_assigned"
        - "notification_message_reward_claimed" -> "reward_claimed"
        """
        return const_key.replace("notification_title_", "").replace(
            "notification_message_", ""
        )

    def _format_notification_text(
        self,
        template: str,
        data: dict[str, Any] | None,
        json_key: str,
        text_type: str = "message",
    ) -> str:
        """Format notification text with placeholders, handling errors gracefully.

        Args:
            template: Template string with {placeholder} syntax
            data: Dictionary of placeholder values
            json_key: Notification key for logging
            text_type: "title" or "message" for error logging

        Returns:
            Formatted string, or original template if formatting fails
        """
        try:
            return template.format(**(data or {}))
        except KeyError as err:
            const.LOGGER.warning(
                "Missing placeholder %s in %s for notification '%s'",
                err,
                text_type,
                json_key,
            )
            return template

    def _translate_action_buttons(
        self, actions: list[dict[str, str]] | None, translations: dict[str, Any]
    ) -> list[dict[str, str]] | None:
        """Translate action button titles using loaded translations.

        Converts action keys like "notif_action_approve" to translation keys
        like "approve", then looks up translated text from the "actions" section
        of notification translations.

        Args:
            actions: List of action dicts with 'action' and 'title' keys
            translations: Loaded notification translations dict

        Returns:
            New list with translated action titles, or None if no actions
        """
        if not actions:
            return None

        action_translations = translations.get("actions", {})
        translated_actions = []

        for action in actions:
            translated_action = action.copy()
            action_title_key = action.get(const.NOTIFY_TITLE, "")
            # Convert "notif_action_approve" -> "approve"
            action_key = action_title_key.replace("notif_action_", "")
            # Look up translation, fallback to original key
            translated_title = action_translations.get(action_key, action_title_key)
            translated_action[const.NOTIFY_TITLE] = translated_title
            translated_actions.append(translated_action)

        const.LOGGER.debug(
            "Translated action buttons: %s -> %s",
            [a.get(const.NOTIFY_TITLE) for a in actions],
            [a.get(const.NOTIFY_TITLE) for a in translated_actions],
        )

        return translated_actions

    # =========================================================================
    # Core Notification Send Method
    # =========================================================================

    async def _send_notification(
        self,
        notify_service: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
    ) -> None:
        """Send a notification using the specified notify service.

        Gracefully handles missing notification services (common in fresh installs,
        migrations, or when mobile app isn't configured yet).

        Uses the module-level async_send_notification function which can be
        easily mocked in tests.
        """
        # Parse service name into domain and service components
        if const.DISPLAY_DOT not in notify_service:
            domain = const.NOTIFY_DOMAIN
            service = notify_service
        else:
            domain, service = notify_service.split(".", 1)

        # Validate service exists before attempting to send
        if not self.hass.services.has_service(domain, service):
            const.LOGGER.warning(
                "Notification service '%s.%s' not available - skipping notification. "
                "This is normal during migration or if the mobile app/notification "
                "integration isn't configured yet",
                domain,
                service,
            )
            return

        const.LOGGER.debug(
            "Sending notification via '%s.%s': title='%s', message='%s', actions=%s",
            domain,
            service,
            title,
            message,
            actions,
        )

        try:
            # Use module-level function for testability
            await async_send_notification(
                self.hass,
                notify_service,
                title,
                message,
                actions,
                extra_data,
            )
            const.LOGGER.debug("Notification sent via '%s.%s'", domain, service)

        except Exception as err:
            # Broad exception allowed: This runs in fire-and-forget background tasks
            # per AGENTS.md guidelines. We must catch all exceptions to prevent
            # "Task exception was never retrieved" errors in logs.
            const.LOGGER.error(
                "Unexpected error sending notification via '%s.%s': %s",
                domain,
                service,
                err,
            )

    # =========================================================================
    # Persistent Notification (System)
    # =========================================================================

    async def send_persistent_notification(
        self,
        user_id: str | None,
        title: str,
        message: str,
        notification_id: str,
    ) -> None:
        """Send a persistent notification to a user if possible.

        Fallback to a general persistent notification if the user is not found.
        """
        if not user_id:
            const.LOGGER.debug(
                "No User ID provided. Sending a general persistent notification"
            )
            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )
            return

        try:
            user_obj = await self.hass.auth.async_get_user(user_id)
            if not user_obj:
                const.LOGGER.warning(
                    "User ID '%s' not found. Sending fallback persistent notification",
                    user_id,
                )
                await self.hass.services.async_call(
                    const.NOTIFY_PERSISTENT_NOTIFICATION,
                    const.NOTIFY_CREATE,
                    {
                        const.NOTIFY_TITLE: title,
                        const.NOTIFY_MESSAGE: message,
                        const.NOTIFY_NOTIFICATION_ID: notification_id,
                    },
                    blocking=True,
                )
                return

            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )
        except Exception as err:
            # Broad exception allowed: Background task
            const.LOGGER.warning(
                "Failed to send notification to '%s': %s. Fallback to persistent notification",
                user_id,
                err,
            )
            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )

    # =========================================================================
    # Kid Notifications
    # =========================================================================

    async def notify_kid(
        self,
        kid_id: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
    ) -> None:
        """Notify a kid using their configured notification settings."""
        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        mobile_notify_service = kid_info.get(
            const.DATA_KID_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
        )
        persistent_enabled = kid_info.get(
            const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS, True
        )

        if mobile_notify_service:
            await self._send_notification(
                mobile_notify_service,
                title,
                message,
                actions=actions,
                extra_data=extra_data,
            )
        elif persistent_enabled:
            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: f"kid_{kid_id}",
                },
                blocking=True,
            )
        else:
            const.LOGGER.debug(
                "No notification method configured for Kid ID '%s'",
                kid_id,
            )

    async def notify_kid_translated(
        self,
        kid_id: str,
        title_key: str,
        message_key: str,
        message_data: dict[str, Any] | None = None,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
    ) -> None:
        """Notify a kid using translated title and message.

        Args:
            kid_id: The internal ID of the kid
            title_key: Translation key for the notification title
            message_key: Translation key for the notification message
            message_data: Dictionary of placeholder values for message formatting
            actions: Optional list of notification actions
            extra_data: Optional extra data for mobile notifications
        """
        # Get kid's preferred language (or fall back to system language)
        kid_info: KidData = cast("KidData", self.coordinator.kids_data.get(kid_id, {}))
        language = kid_info.get(
            const.DATA_KID_DASHBOARD_LANGUAGE,
            self.hass.config.language,
        )
        const.LOGGER.debug(
            "Notification: kid_id=%s, language=%s, title_key=%s",
            kid_id,
            language,
            title_key,
        )

        # Load notification translations from custom translations directory
        translations = await kh.load_notification_translation(self.hass, language)
        const.LOGGER.debug(
            "Notification translations loaded: %d keys, language=%s",
            len(translations),
            language,
        )

        # Convert const key to JSON key and look up translations
        json_key = self._convert_notification_key(title_key)
        notification = translations.get(json_key, {})

        # Format title and message with placeholders
        title = self._format_notification_text(
            notification.get("title", title_key), message_data, json_key, "title"
        )
        message = self._format_notification_text(
            notification.get("message", message_key), message_data, json_key, "message"
        )

        # Translate action button titles
        translated_actions = self._translate_action_buttons(actions, translations)

        # Call notification method
        await self.notify_kid(kid_id, title, message, translated_actions, extra_data)

    # =========================================================================
    # Parent Notifications
    # =========================================================================

    async def notify_parents(
        self,
        kid_id: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
    ) -> None:
        """Notify all parents associated with a kid using their settings."""
        perf_start = time.perf_counter()
        parent_count = 0

        for parent_id, parent_info in self.coordinator.parents_data.items():
            if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
                continue

            mobile_notify_service = parent_info.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            )
            persistent_enabled = parent_info.get(
                const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, True
            )

            if mobile_notify_service:
                parent_count += 1
                await self._send_notification(
                    mobile_notify_service,
                    title,
                    message,
                    actions=actions,
                    extra_data=extra_data,
                )
            elif persistent_enabled:
                parent_count += 1
                await self.hass.services.async_call(
                    const.NOTIFY_PERSISTENT_NOTIFICATION,
                    const.NOTIFY_CREATE,
                    {
                        const.NOTIFY_TITLE: title,
                        const.NOTIFY_MESSAGE: message,
                        const.NOTIFY_NOTIFICATION_ID: f"parent_{parent_id}",
                    },
                    blocking=True,
                )
            else:
                const.LOGGER.debug(
                    "No notification method configured for Parent ID '%s'",
                    parent_id,
                )

        # PERF: Log parent notification latency
        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: notify_parents() sent %d notifications in %.3fs (sequential)",
            parent_count,
            perf_duration,
        )

    async def notify_parents_translated(
        self,
        kid_id: str,
        title_key: str,
        message_key: str,
        message_data: dict[str, Any] | None = None,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
        tag_type: str | None = None,
        tag_identifiers: tuple[str, ...] | None = None,
    ) -> None:
        """Notify parents using translated title and message.

        Each parent receives notifications in their own preferred language.
        Supports tag-based notification replacement (v0.5.0+).
        Uses concurrent notification sending for ~3x performance improvement.

        Args:
            kid_id: The internal ID of the kid (to find associated parents)
            title_key: Translation key for the notification title
            message_key: Translation key for the notification message
            message_data: Dictionary of placeholder values for message formatting
            actions: Optional list of notification actions
            extra_data: Optional extra data for mobile notifications
            tag_type: Optional tag type for smart notification replacement.
            tag_identifiers: Optional tuple of identifiers for tag uniqueness.
        """
        perf_start = time.perf_counter()

        # Build notification tag if tag_type provided
        notification_tag = None
        if tag_type:
            identifiers = tag_identifiers if tag_identifiers else (kid_id,)
            notification_tag = self.build_notification_tag(tag_type, *identifiers)
            const.LOGGER.debug(
                "Using notification tag '%s' for identifiers %s",
                notification_tag,
                identifiers,
            )

        # Phase 1: Prepare all parent notifications (translations, formatting)
        notification_tasks: list[tuple[str, Any]] = []

        for parent_id, parent_info in self.coordinator.parents_data.items():
            if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
                continue

            # Use parent's language preference
            parent_language = (
                parent_info.get(const.DATA_PARENT_DASHBOARD_LANGUAGE)
                or cast("KidData", self.coordinator.kids_data.get(kid_id, {})).get(
                    const.DATA_KID_DASHBOARD_LANGUAGE
                )
                or self.hass.config.language
            )

            const.LOGGER.debug(
                "Parent notification: kid_id=%s, parent_id=%s, language=%s, title_key=%s",
                kid_id,
                parent_id,
                parent_language,
                title_key,
            )

            # Load notification translations for this parent's language
            translations = await kh.load_notification_translation(
                self.hass, parent_language
            )

            # Convert const key to JSON key and look up translations
            json_key = self._convert_notification_key(title_key)
            notification = translations.get(json_key, {})

            # Format both title and message with placeholders
            title = self._format_notification_text(
                notification.get("title", title_key), message_data, json_key, "title"
            )
            message = self._format_notification_text(
                notification.get("message", message_key),
                message_data,
                json_key,
                "message",
            )

            # Translate action button titles
            translated_actions = self._translate_action_buttons(actions, translations)

            # Build final extra_data with tag if provided
            final_extra_data = dict(extra_data) if extra_data else {}
            if notification_tag:
                final_extra_data[const.NOTIFY_TAG] = notification_tag

            # Determine notification method and prepare coroutine
            persistent_enabled = parent_info.get(
                const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, True
            )
            mobile_notify_service = parent_info.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            )

            if mobile_notify_service:
                notification_tasks.append(
                    (
                        parent_id,
                        self._send_notification(
                            mobile_notify_service,
                            title,
                            message,
                            actions=translated_actions,
                            extra_data=final_extra_data if final_extra_data else None,
                        ),
                    )
                )
            elif persistent_enabled:
                notification_tasks.append(
                    (
                        parent_id,
                        self.hass.services.async_call(
                            const.NOTIFY_PERSISTENT_NOTIFICATION,
                            const.NOTIFY_CREATE,
                            {
                                const.NOTIFY_TITLE: title,
                                const.NOTIFY_MESSAGE: message,
                                const.NOTIFY_NOTIFICATION_ID: f"parent_{parent_id}",
                            },
                            blocking=True,
                        ),
                    )
                )
            else:
                const.LOGGER.debug(
                    "No notification method configured for Parent ID '%s'",
                    parent_id,
                )

        # Phase 2: Send all notifications concurrently
        parent_count = len(notification_tasks)
        if notification_tasks:
            results = await asyncio.gather(
                *[coro for _, coro in notification_tasks],
                return_exceptions=True,
            )

            # Log any errors
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    parent_id = notification_tasks[idx][0]
                    const.LOGGER.warning(
                        "Failed to send notification to parent '%s': %s",
                        parent_id,
                        result,
                    )

        # PERF: Log parent notification latency
        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: notify_parents_translated() sent %d notifications in %.3fs (concurrent)",
            parent_count,
            perf_duration,
        )

    # =========================================================================
    # Notification Management
    # =========================================================================

    async def clear_notification_for_parents(
        self,
        kid_id: str,
        tag_type: str,
        entity_id: str,
    ) -> None:
        """Clear a notification for all parents of a kid.

        Sends "clear_notification" message to each parent's notification service
        with the appropriate tag.

        Args:
            kid_id: The internal ID of the kid (to find associated parents)
            tag_type: Tag type constant (e.g., NOTIFY_TAG_TYPE_STATUS)
            entity_id: The chore/reward ID to include in the tag
        """
        # Build the tag for this entity
        notification_tag = self.build_notification_tag(tag_type, entity_id, kid_id)

        const.LOGGER.debug(
            "Clearing notification with tag '%s' for kid '%s'",
            notification_tag,
            kid_id,
        )

        # Build clear tasks for all parents associated with this kid
        clear_tasks: list[tuple[str, Any]] = []

        for parent_id, parent_info in self.coordinator.parents_data.items():
            if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
                continue

            notify_service = parent_info.get(const.DATA_PARENT_MOBILE_NOTIFY_SERVICE)
            if not notify_service:
                continue

            # Strip "notify." prefix if present
            service_name = notify_service.removeprefix("notify.")

            service_data = {
                "message": "clear_notification",
                "data": {"tag": notification_tag},
            }
            coro = self.hass.services.async_call(
                "notify",
                service_name,
                service_data,
            )
            clear_tasks.append((parent_id, coro))

        # Execute all clears concurrently
        if clear_tasks:
            results = await asyncio.gather(
                *[coro for _, coro in clear_tasks],
                return_exceptions=True,
            )
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    parent_id = clear_tasks[idx][0]
                    const.LOGGER.warning(
                        "Failed to clear notification for parent '%s': %s",
                        parent_id,
                        result,
                    )
        else:
            const.LOGGER.debug(
                "No parents with notification service found for kid '%s'",
                kid_id,
            )

    async def remind_in_minutes(
        self,
        kid_id: str,
        minutes: int,
        *,
        chore_id: str | None = None,
        reward_id: str | None = None,
    ) -> None:
        """Schedule a reminder notification after specified minutes.

        If a chore_id is provided, checks the chore's state before sending.
        If a reward_id is provided, checks whether that reward is still pending.
        """
        const.LOGGER.debug(
            "Scheduling reminder for Kid ID '%s', Chore ID '%s', Reward ID '%s' in %d minutes",
            kid_id,
            chore_id,
            reward_id,
            minutes,
        )
        # Use 5 seconds in test mode, convert minutes to seconds in production
        delay_seconds = 5 if self.coordinator._test_mode else (minutes * 60)
        await asyncio.sleep(delay_seconds)

        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "Kid ID '%s' not found during reminder check",
                kid_id,
            )
            return

        if chore_id:
            chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
            if not chore_info:
                const.LOGGER.warning(
                    "Chore ID '%s' not found during reminder check",
                    chore_id,
                )
                return

            # Check if reminders are enabled for this chore
            if not chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_REMINDER, const.DEFAULT_NOTIFY_ON_REMINDER
            ):
                const.LOGGER.debug(
                    "Reminders disabled for Chore ID '%s'. Skipping",
                    chore_id,
                )
                return

            # Get the per-kid chore state
            kid_chore_data = self.coordinator._get_chore_data_for_kid(kid_id, chore_id)
            current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)

            # Only resend if still pending/overdue
            if current_state not in [
                const.CHORE_STATE_PENDING,
                const.CHORE_STATE_OVERDUE,
            ]:
                const.LOGGER.info(
                    "Chore ID '%s' for Kid ID '%s' is in state '%s'. No reminder sent",
                    chore_id,
                    kid_id,
                    current_state,
                )
                return

            # Build actions and send reminder
            actions = self.build_chore_actions(kid_id, chore_id)
            extra_data = self.build_extra_data(kid_id, chore_id=chore_id)
            await self.notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_REMINDER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_REMINDER,
                message_data={
                    "chore_name": chore_info.get(
                        const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                    ),
                    "kid_name": kid_info.get(
                        const.DATA_KID_NAME, const.DISPLAY_UNNAMED_KID
                    ),
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(chore_id, kid_id),
            )
            const.LOGGER.info(
                "Resent reminder for Chore ID '%s' for Kid ID '%s'",
                chore_id,
                kid_id,
            )

        elif reward_id:
            # Check if the reward is still pending
            reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {}).get(
                reward_id, {}
            )
            pending_count = reward_data.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)
            if pending_count <= 0:
                const.LOGGER.info(
                    "Reward ID '%s' is no longer pending for Kid ID '%s'. No reminder sent",
                    reward_id,
                    kid_id,
                )
                return

            # Build actions and send reminder
            actions = self.build_reward_actions(kid_id, reward_id)
            extra_data = self.build_extra_data(kid_id, reward_id=reward_id)
            reward_info: RewardData = cast(
                "RewardData", self.coordinator.rewards_data.get(reward_id, {})
            )
            reward_name = reward_info.get(const.DATA_REWARD_NAME, "the reward")
            await self.notify_parents_translated(
                kid_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_REMINDER,
                message_data={
                    "reward_name": reward_name,
                    "kid_name": kid_info.get(const.DATA_KID_NAME, "A kid"),
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(reward_id, kid_id),
            )
            const.LOGGER.info(
                "Resent reminder for Reward ID '%s' for Kid ID '%s'",
                reward_id,
                kid_id,
            )
        else:
            const.LOGGER.warning(
                "No Chore ID or Reward ID provided for reminder action"
            )
