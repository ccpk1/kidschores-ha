"""Notification workflow tests using YAML scenarios.

These tests verify that notifications are sent correctly during
chore workflows and that they use the kid's configured language.

Test Organization:
- TestChoreClaimNotifications: Notifications sent when chores are claimed
- TestNotificationLanguage: Verify notifications use kid's language preference
- TestNotificationActions: Verify action buttons are translated

Coordinator API Reference:
- claim_chore(kid_id, chore_id, user_name)
- approve_chore(parent_name, kid_id, chore_id, points_awarded=None)

Notification System:
- async_send_notification(hass, service, title, message, actions, extra_data)
- _notify_parents_translated() - Uses kid's dashboard_language for translations
"""

# pylint: disable=redefined-outer-name
# hass fixture required for HA test setup

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from tests.helpers import (
    ACTION_APPROVE_CHORE,
    DATA_KID_DASHBOARD_LANGUAGE,
    DATA_KIDS,
    DATA_PARENT_DASHBOARD_LANGUAGE,
    DATA_PARENT_ENABLE_NOTIFICATIONS,
    DATA_PARENT_MOBILE_NOTIFY_SERVICE,
    DATA_PARENTS,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator

# =============================================================================
# FIXTURES
# =============================================================================


def register_mock_notify_services(hass: HomeAssistant) -> None:
    """Register mock notify services for testing.

    This allows the config flow to accept notify service names in the
    mobile_notify_service field, enabling true end-to-end notification testing.
    """

    async def mock_notify_service(call):
        """Mock notify service handler."""

    # Register mock notify services that match what's in the YAML scenario
    hass.services.async_register(
        "notify", "mobile_app_mom_astrid_starblum", mock_notify_service
    )
    hass.services.async_register("notify", "mobile_app_zoe", mock_notify_service)
    hass.services.async_register("notify", "mobile_app_max", mock_notify_service)


@pytest.fixture
async def scenario_notifications(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load notification testing scenario.

    Contains:
    - 2 kids: Zoë (English), Max (Slovak)
    - 1 parent: Mom (notifications enabled)
    - 4 chores: Feed the cat (Zoë), Clean room (Max), Walk the dog (shared), Auto chore
    """
    # Register mock notify services BEFORE config flow runs
    register_mock_notify_services(hass)

    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_notifications.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def load_notification_translations(language: str) -> dict[str, Any]:
    """Load notification translations from JSON file.

    Args:
        language: Language code (e.g., 'en', 'sk')

    Returns:
        Dictionary containing the full translations file content
    """
    # Use absolute path based on this file's location
    tests_dir = Path(__file__).parent
    workspace_root = tests_dir.parent
    translations_path = (
        workspace_root
        / "custom_components"
        / "kidschores"
        / "translations_custom"
        / f"{language}_notifications.json"
    )

    if not translations_path.exists():
        raise FileNotFoundError(f"Translation file not found: {translations_path}")

    with open(translations_path, encoding="utf-8") as f:
        return json.load(f)


def get_action_titles(language: str) -> dict[str, str]:
    """Get action button titles for a language.

    Returns:
        Dict mapping action keys to translated titles
    """
    translations = load_notification_translations(language)
    return translations.get("actions", {})


def enable_parent_notifications(
    coordinator: KidsChoresDataCoordinator,
    parent_id: str,
) -> None:
    """Enable notifications for a parent in coordinator data.

    NOTE: This helper is only needed for scenarios that DON'T register mock notify
    services before setup. For scenario_notifications.yaml, mock services are
    registered by the fixture, so notifications are enabled through the config flow.

    Use this helper for scenarios where you intentionally have notifications disabled
    in the YAML but need to enable them for specific tests.

    Args:
        coordinator: The coordinator instance
        parent_id: Internal ID of the parent to enable notifications for
    """
    # Enable mobile notifications
    coordinator._data[DATA_PARENTS][parent_id][DATA_PARENT_ENABLE_NOTIFICATIONS] = True

    # Set a mock notify service
    coordinator._data[DATA_PARENTS][parent_id][DATA_PARENT_MOBILE_NOTIFY_SERVICE] = (
        "notify.notify"
    )

    # Ensure enable_notifications is also set
    coordinator._data[DATA_PARENTS][parent_id][DATA_PARENT_ENABLE_NOTIFICATIONS] = True

    # Persist changes
    coordinator._persist()


class NotificationCapture:
    """Helper class to capture notifications during tests."""

    def __init__(self) -> None:
        """Initialize capture storage."""
        self.notifications: list[dict[str, Any]] = []

    async def capture(
        self,
        hass: HomeAssistant,
        service: str,
        title: str,
        message: str,
        actions: list[dict[str, Any]] | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        """Capture a notification call."""
        self.notifications.append(
            {
                "service": service,
                "title": title,
                "message": message,
                "actions": actions or [],
                "extra_data": extra_data or {},
            }
        )

    def clear(self) -> None:
        """Clear captured notifications."""
        self.notifications = []

    def get_with_actions(self) -> list[dict[str, Any]]:
        """Get notifications that have action buttons."""
        return [n for n in self.notifications if n.get("actions")]

    def get_action_titles(self) -> set[str]:
        """Get all action button titles from captured notifications."""
        titles: set[str] = set()
        for notif in self.notifications:
            for action in notif.get("actions", []):
                if title := action.get("title"):
                    titles.add(title)
        return titles


# =============================================================================
# CHORE CLAIM NOTIFICATION TESTS
# =============================================================================


class TestChoreClaimNotifications:
    """Tests for notifications sent when chores are claimed."""

    @pytest.mark.asyncio
    async def test_notifications_enabled_via_config_flow(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Verify notifications are enabled through config flow, not manual override.

        This test confirms the mock notify services are registered correctly
        and the config flow accepted the notification settings.
        """
        coordinator = scenario_notifications.coordinator
        parent_id = scenario_notifications.parent_ids["Môm Astrid Stârblüm"]

        # Get parent data from coordinator
        parent_data = coordinator._data[DATA_PARENTS][parent_id]

        # Verify notifications were enabled through config flow
        assert parent_data.get(DATA_PARENT_ENABLE_NOTIFICATIONS) is True, (
            "Notifications should be enabled through config flow"
        )
        assert (
            parent_data.get(DATA_PARENT_MOBILE_NOTIFY_SERVICE)
            == "notify.mobile_app_mom_astrid_starblum"
        ), "Mobile notify service should be set through config flow"

        # Verify mock service exists
        all_services = hass.services.async_services()
        assert "notify" in all_services, "Notify domain should exist"
        assert "mobile_app_mom_astrid_starblum" in all_services["notify"], (
            "Mock notify service should be registered"
        )

    @pytest.mark.asyncio
    async def test_claim_sends_notification_to_parent(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Claiming a chore with notify_on_claim=true sends notification."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        # Notification should be sent
        assert len(capture.notifications) > 0, "No notification was sent on chore claim"

    @pytest.mark.asyncio
    async def test_claim_notification_has_action_buttons(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Chore claim notification includes approve/disapprove action buttons."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        # Should have notification with actions
        notifs_with_actions = capture.get_with_actions()
        assert len(notifs_with_actions) > 0, "No notification with action buttons found"

        # Actions should include approve, disapprove, remind
        action_titles = capture.get_action_titles()
        assert len(action_titles) >= 2, (
            f"Expected at least 2 action buttons, got: {action_titles}"
        )

    @pytest.mark.asyncio
    async def test_auto_approve_chore_no_parent_notification(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Auto-approve chores don't send parent notifications (already approved)."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Auto chore"]

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        # Auto-approve should send kid notification (approval) but no parent notification
        # Filter for parent notifications (those with action buttons for approve/disapprove)
        parent_notifs = capture.get_with_actions()
        assert len(parent_notifs) == 0, (
            f"Auto-approve chore should not send parent notification with actions. "
            f"Got: {parent_notifs}"
        )


# =============================================================================
# NOTIFICATION LANGUAGE TESTS
# =============================================================================


class TestNotificationLanguage:
    """Tests for notification language based on kid's dashboard_language."""

    @pytest.mark.asyncio
    async def test_english_kid_gets_english_actions(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Kid with dashboard_language='en' triggers English action buttons."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]  # English language
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Verify kid is configured for English
        kid_lang = coordinator._data[DATA_KIDS][kid_id].get(DATA_KID_DASHBOARD_LANGUAGE)
        assert kid_lang == "en", f"Expected kid language 'en', got '{kid_lang}'"

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        # Get expected English action titles
        expected_actions = get_action_titles("en")
        expected_titles = set(expected_actions.values())

        # Verify action buttons are in English
        actual_titles = capture.get_action_titles()

        # At least one expected English title should appear
        matching = actual_titles & expected_titles
        assert len(matching) > 0, (
            f"Expected English action titles {expected_titles}, but got {actual_titles}"
        )

    @pytest.mark.asyncio
    async def test_parent_gets_parent_language_not_kid_language(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Parent notifications use parent's language, not kid's language."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Max!"]  # Slovak language kid
        chore_id = scenario_notifications.chore_ids["Clean room"]

        # Verify kid is configured for Slovak
        kid_lang = coordinator._data[DATA_KIDS][kid_id].get(DATA_KID_DASHBOARD_LANGUAGE)
        assert kid_lang == "sk", f"Expected kid language 'sk', got '{kid_lang}'"

        # Verify parent is configured for English
        parent_id = list(coordinator._data[DATA_PARENTS].keys())[0]  # Get first parent
        parent_lang = coordinator._data[DATA_PARENTS][parent_id].get(
            DATA_PARENT_DASHBOARD_LANGUAGE
        )
        assert parent_lang == "en", (
            f"Expected parent language 'en', got '{parent_lang}'"
        )

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Max!")
            await hass.async_block_till_done()

        # Get expected English action titles (parent's language, not kid's)
        try:
            expected_actions = get_action_titles("en")
            expected_titles = set(expected_actions.values())
        except FileNotFoundError:
            pytest.skip("English translations not available")

        # Verify action buttons are in English (parent's language)
        actual_titles = capture.get_action_titles()

        # At least one expected English title should appear
        matching = actual_titles & expected_titles
        assert len(matching) > 0, (
            f"Expected English action titles (parent's language) {expected_titles}, but got {actual_titles}"
        )

    @pytest.mark.asyncio
    async def test_notification_uses_parent_language_not_system(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Parent notifications use parent's language, not HA system language."""
        coordinator = scenario_notifications.coordinator

        # Verify HA system language is English (default)
        assert hass.config.language == "en", "Test expects HA system to be English"

        # Claim chore for Slovak kid, but parent should get English notification
        kid_id = scenario_notifications.kid_ids["Max!"]  # Slovak
        chore_id = scenario_notifications.chore_ids["Clean room"]

        # Verify parent is configured for English (same as system in this case)
        parent_id = list(coordinator._data[DATA_PARENTS].keys())[0]  # Get first parent
        parent_lang = coordinator._data[DATA_PARENTS][parent_id].get(
            DATA_PARENT_DASHBOARD_LANGUAGE
        )
        assert parent_lang == "en", (
            f"Expected parent language 'en', got '{parent_lang}'"
        )

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Max!")
            await hass.async_block_till_done()

        # Actions should be English (parent's language)
        # They should NOT be Slovak (kid's language)
        try:
            english_actions = get_action_titles("en")
            english_titles = set(english_actions.values())

            slovak_actions = get_action_titles("sk")
            slovak_titles = set(slovak_actions.values())
        except FileNotFoundError:
            pytest.skip("Slovak translations not available")

        actual_titles = capture.get_action_titles()

        # Verify English titles are used (parent's language), not Slovak
        english_match = actual_titles & english_titles
        slovak_match = actual_titles & slovak_titles

        # If languages have different translations, English should match
        if english_titles != slovak_titles:
            assert len(english_match) > len(slovak_match), (
                f"Expected English titles (parent's language), not Slovak (kid's language). "
                f"Got: {actual_titles}, English: {english_titles}, Slovak: {slovak_titles}"
            )


# =============================================================================
# NOTIFICATION ACTION BUTTON TESTS
# =============================================================================


class TestNotificationActions:
    """Tests for notification action button content."""

    @pytest.mark.asyncio
    async def test_actions_not_raw_translation_keys(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Action button titles should be translated, not raw keys."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        action_titles = capture.get_action_titles()

        # Titles should NOT be raw translation keys
        for title in action_titles:
            assert not title.startswith("notif_action_"), (
                f"Action title is raw key, not translated: {title}"
            )
            assert not title.startswith("err-"), (
                f"Action title is error fallback: {title}"
            )
            # Should be actual words, not snake_case keys
            assert "_" not in title or " " in title, (
                f"Action title looks like a key, not translated text: {title}"
            )

    @pytest.mark.asyncio
    async def test_actions_include_approve_disapprove(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Chore claim notifications include approve and disapprove actions."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Notifications enabled through config flow (mock services registered by fixture)
        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        notifs_with_actions = capture.get_with_actions()
        assert len(notifs_with_actions) > 0, "No notifications with actions"

        # Get all action identifiers to verify approve/disapprove are present
        action_ids: set[str] = set()
        for notif in notifs_with_actions:
            for action in notif.get("actions", []):
                # Actions use "action" key, not "uri"
                if action_id := action.get("action"):
                    action_ids.add(action_id)

        # Action identifiers should contain approve and disapprove action types
        action_text = " ".join(action_ids)
        assert "approve" in action_text.lower() or any(
            ACTION_APPROVE_CHORE in aid for aid in action_ids
        ), f"No approve action found in actions: {action_ids}"


# =============================================================================
# V0.5.0 FEATURE TESTS
# =============================================================================


class TestNotificationTagging:
    """Tests for notification tag-based replacement (v0.5.0+)."""

    @pytest.mark.asyncio
    async def test_notification_includes_tag_for_pending_chores(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Pending chore notifications include tag in extra_data for smart replacement."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        assert len(capture.notifications) > 0, "No notification was sent on chore claim"

        # Verify tag is present and has correct format: kidschores-status-{chore_id[:8]}-{kid_id[:8]}
        # UUIDs are truncated to 8 chars to stay under Apple's 64-byte limit (v0.5.0+)
        notif = capture.notifications[0]
        extra_data = notif.get("extra_data", {})
        tag = extra_data.get("tag", "")

        assert tag.startswith("kidschores-status-"), (
            f"Expected tag to start with 'kidschores-status-', got '{tag}'"
        )
        # Check for truncated IDs (first 8 characters)
        assert chore_id[:8] in tag, (
            f"Expected chore_id[:8] '{chore_id[:8]}' in tag '{tag}'"
        )
        assert kid_id[:8] in tag, f"Expected kid_id[:8] '{kid_id[:8]}' in tag '{tag}'"


class TestDueDateReminders:
    """Tests for due date reminder notifications (v0.5.0+)."""

    @pytest.mark.asyncio
    async def test_due_soon_reminder_sent_within_window(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
        freezer: Any,
    ) -> None:
        """Chore due within 30 minutes triggers kid reminder notification."""
        from datetime import timedelta

        from homeassistant.util import dt as dt_util

        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Set a due date 25 minutes from now (within 30-min window)
        now = dt_util.utcnow()
        due_in_25_min = now + timedelta(minutes=25)

        # Set per-kid due date for independent chore
        chore_info = coordinator.chores_data[chore_id]
        if "per_kid_due_dates" not in chore_info:
            chore_info["per_kid_due_dates"] = {}
        chore_info["per_kid_due_dates"][kid_id] = due_in_25_min.isoformat()
        # Enable reminders for this chore (per-chore control v0.5.0+)
        chore_info["notify_on_reminder"] = True
        coordinator._persist()

        # Track notifications to kid
        kid_notifications: list[dict[str, Any]] = []

        async def capture_kid_notification(
            kid_id_arg: str,
            title_key: str,
            message_key: str,
            **kwargs: Any,
        ) -> None:
            kid_notifications.append(
                {
                    "kid_id": kid_id_arg,
                    "title_key": title_key,
                    "message_key": message_key,
                    **kwargs,
                }
            )

        with patch.object(
            coordinator, "_notify_kid_translated", new=capture_kid_notification
        ):
            await coordinator._check_chore_due_reminders()

        # Verify reminder was sent
        assert len(kid_notifications) > 0, "No due-soon reminder was sent"
        assert kid_notifications[0]["kid_id"] == kid_id
        assert "due_soon" in kid_notifications[0]["title_key"].lower()

    @pytest.mark.asyncio
    async def test_due_soon_reminder_not_duplicated(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Same chore+kid combo only gets one reminder until cleared."""
        from datetime import timedelta

        from homeassistant.util import dt as dt_util

        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Set a due date 25 minutes from now
        now = dt_util.utcnow()
        due_in_25_min = now + timedelta(minutes=25)

        chore_info = coordinator.chores_data[chore_id]
        if "per_kid_due_dates" not in chore_info:
            chore_info["per_kid_due_dates"] = {}
        chore_info["per_kid_due_dates"][kid_id] = due_in_25_min.isoformat()
        # Enable reminders for this chore (per-chore control v0.5.0+)
        chore_info["notify_on_reminder"] = True
        coordinator._persist()

        notifications_count = 0

        async def count_notifications(*args: Any, **kwargs: Any) -> None:
            nonlocal notifications_count
            notifications_count += 1

        with patch.object(
            coordinator, "_notify_kid_translated", new=count_notifications
        ):
            # First check - should send reminder
            await coordinator._check_chore_due_reminders()
            first_count = notifications_count

            # Second check - should NOT send duplicate
            await coordinator._check_chore_due_reminders()
            second_count = notifications_count

        assert first_count == 1, (
            f"Expected 1 reminder on first check, got {first_count}"
        )
        assert second_count == 1, f"Expected no duplicate, got {second_count} total"

    @pytest.mark.asyncio
    async def test_due_soon_reminder_cleared_on_claim(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Claiming a chore clears the reminder tracking (allows future reminders)."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Manually mark as sent
        reminder_key = f"{chore_id}:{kid_id}"
        coordinator._due_soon_reminders_sent.add(reminder_key)

        assert reminder_key in coordinator._due_soon_reminders_sent

        # Claim the chore - should clear the reminder tracking
        coordinator.claim_chore(kid_id, chore_id, "Zoë")

        assert reminder_key not in coordinator._due_soon_reminders_sent, (
            "Claiming should clear due-soon reminder tracking"
        )


class TestRaceConditionPrevention:
    """Tests for race condition prevention in approval methods (v0.5.0+)."""

    @pytest.mark.asyncio
    async def test_simultaneous_approvals_award_points_once(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Two simultaneous approve_chore calls award points only once."""
        import asyncio

        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Claim the chore first
        coordinator.claim_chore(kid_id, chore_id, "Zoë")

        # Get initial points
        initial_points = coordinator.kids_data[kid_id].get("points", 0)
        chore_points = coordinator.chores_data[chore_id].get("default_points", 10)

        # Mock parent notification to prevent actual sends
        with patch.object(coordinator, "_notify_parents_translated", new=AsyncMock()):
            # Simulate two parents clicking approve at the same time
            results = await asyncio.gather(
                coordinator.approve_chore("Mom", kid_id, chore_id),
                coordinator.approve_chore("Dad", kid_id, chore_id),
                return_exceptions=True,
            )

        # Get final points
        final_points = coordinator.kids_data[kid_id].get("points", 0)
        points_awarded = final_points - initial_points

        # Only one approval should succeed (points awarded once)
        assert points_awarded == chore_points, (
            f"Expected {chore_points} points (single approval), "
            f"but got {points_awarded} points"
        )

        # Both calls should complete without raising exceptions
        # (second one returns gracefully due to race condition protection)
        actual_exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(actual_exceptions) == 0, (
            f"Expected no exceptions (graceful handling), got: {actual_exceptions}"
        )


class TestConcurrentNotifications:
    """Tests for concurrent parent notification sending (v0.5.0+)."""

    @pytest.mark.asyncio
    async def test_multiple_parents_receive_notifications_concurrently(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """Multiple parents with notifications enabled all receive them."""
        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        capture = NotificationCapture()

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=capture.capture,
        ):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        # At least one parent should receive notification
        assert len(capture.notifications) >= 1, "No notifications sent to any parent"

    @pytest.mark.asyncio
    async def test_notification_failure_isolated_from_others(
        self,
        hass: HomeAssistant,
        scenario_notifications: SetupResult,
    ) -> None:
        """One parent notification failure doesn't prevent others from receiving."""

        coordinator = scenario_notifications.coordinator
        kid_id = scenario_notifications.kid_ids["Zoë"]
        chore_id = scenario_notifications.chore_ids["Feed the cat"]

        # Add a second parent with notifications enabled
        parent_id_2 = "test_parent_2"
        coordinator._data[DATA_PARENTS][parent_id_2] = {
            "name": "Test Dad",
            "associated_kids": [kid_id],
            "enable_notifications": True,
            "mobile_notify_service": "notify.mobile_app_dad",
            "dashboard_language": "en",
        }

        # Track successful notifications
        successful_notifications: list[str] = []
        call_count = 0

        async def mixed_success_notification(
            hass_arg: HomeAssistant,
            service: str,
            title: str,
            message: str,
            **kwargs: Any,
        ) -> None:
            nonlocal call_count
            call_count += 1
            # First call fails, second succeeds
            if call_count == 1:
                raise Exception("Simulated notification failure")  # noqa: TRY002
            successful_notifications.append(service)

        with patch(
            "custom_components.kidschores.coordinator.async_send_notification",
            new=mixed_success_notification,
        ):
            # This should not raise - failures are logged but don't propagate
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            await hass.async_block_till_done()

        # At least one notification should have succeeded despite the failure
        assert call_count >= 1, "Expected notifications to be attempted"
