# File: coordinator_chore_operations.py
"""Chore lifecycle operations for KidsChoresDataCoordinator.

This module contains all chore-related coordinator methods extracted from
coordinator.py to improve code organization. Uses Python's multiple inheritance
pattern - ChoreOperations is inherited by KidsChoresDataCoordinator.

IMPORTANT: This is a SURGICAL CODE EXTRACTION, not a refactor.
- All logic remains IDENTICAL to the original coordinator.py methods
- No behavior changes, no optimizations, no "improvements"
- Success criteria: All 852 tests pass UNCHANGED

Methods access coordinator state through `self` (the parent coordinator instance).
This file should NOT be instantiated directly.

Architecture: See docs/ARCHITECTURE.md and the extraction plan at
docs/in-process/COORDINATOR_CHORE_OPERATIONS_IN-PROCESS.md
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
import time
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import const, kc_helpers as kh
from .notification_helper import build_chore_actions, build_extra_data
from .schedule_engine import RecurrenceEngine, calculate_next_due_date_from_chore_info

if TYPE_CHECKING:
    import asyncio

    from .type_defs import (
        AchievementProgress,
        ChallengeProgress,
        ChoreData,
        KidChoreDataEntry,
        KidData,
        ScheduleConfig,
    )


class ChoreOperations:
    """Chore lifecycle operations: claim, approve, disapprove, scheduling.

    This class provides all chore-related coordinator methods via multiple
    inheritance. Methods access coordinator state through `self` (parent
    coordinator instance).

    Extracted from coordinator.py to improve code organization without
    changing behavior. All logic remains identical to original.

    File Organization:
        §1  Service Entry Points (7 methods) - HA service handlers
        §2  Coordinator Public API (7 methods) - Called by sensor.py, button.py
        §3  Validation Logic (2 methods) - Pre-condition checks
        §4  State Machine (2 methods) - Core state transitions
        §5  Data Management (2 methods) - Kid chore data updates
        §6  Query & Lookup (5 methods) - State/data queries
        §7  Scheduling Logic (1 method) - Due date reminder processing
        §8  Recurring Chore Operations (5 methods) - Recurring lifecycle
        §9  Daily Reset Operations (4 methods) - Midnight resets
        §10 Overdue Detection & Handling (4 methods) - Overdue processing
        §11 Reminder Operations (1 method) - Due date notifications
    """

    # =========================================================================
    # TYPE HINTS FOR COORDINATOR ATTRIBUTES
    # =========================================================================
    # These are accessed via self (the coordinator instance) at runtime.
    # TYPE_CHECKING block provides IDE support without runtime overhead.

    if TYPE_CHECKING:
        # Coordinator attributes accessed by chore operations
        # NOTE: chores_data and kids_data are @property in coordinator.py
        # but we declare them as attributes here for simpler type hints
        _data: dict[str, Any]
        _test_mode: bool
        _pending_chore_changed: bool
        _approval_locks: dict[str, Any]
        _due_soon_reminders_sent: set[str]
        config_entry: Any
        hass: Any

        # Coordinator properties (declared as methods returning values)
        @property
        def chores_data(self) -> dict[str, ChoreData]: ...
        @property
        def kids_data(self) -> dict[str, KidData]: ...

        # Coordinator methods called by chore operations
        # NOTE: Signatures must match actual coordinator.py methods
        def _persist(self) -> None: ...
        def _normalize_kid_reward_data(self, kid_info: KidData) -> None: ...
        def update_kid_points(
            self, kid_id: str, delta: float, *, source: str = ...
        ) -> Any: ...
        def _check_badges_for_kid(self, kid_id: str) -> None: ...
        def _update_challenge_progress(
            self, kid_id: str, chore_id: str, points: float
        ) -> None: ...
        def _update_achievement_progress(
            self, kid_id: str, action: str, value: int = 1
        ) -> None: ...
        def async_set_updated_data(self, data: dict[str, Any]) -> None: ...
        def _clear_chore_due_reminder(self, chore_id: str, kid_id: str) -> None: ...
        async def _notify_parents_translated(
            self,
            kid_id: str,
            title_key: str,
            message_key: str,
            message_data: dict[str, Any] | None = None,
            actions: list[dict[str, Any]] | None = None,
            extra_data: dict[str, Any] | None = None,
            tag_type: str | None = None,
            tag_identifiers: tuple[str, ...] | None = None,
        ) -> None: ...
        async def _notify_kid_translated(
            self,
            kid_id: str,
            title_key: str,
            message_key: str,
            message_data: dict[str, Any] | None = None,
            actions: list[dict[str, str]] | None = None,
            extra_data: dict[str, Any] | None = None,
        ) -> None: ...
        async def clear_notification_for_parents(
            self,
            kid_id: str,
            tag_type: str,
            entity_id: str,
        ) -> None: ...
        # Methods still in coordinator.py (not yet extracted)
        def _get_approval_lock(
            self, operation: str, *identifiers: str
        ) -> asyncio.Lock: ...
        def _get_retention_config(self) -> dict[str, int]: ...
        def _recalculate_chore_stats_for_kid(self, kid_id: str) -> None: ...
        def _update_streak_progress(
            self, progress: AchievementProgress, today: date
        ) -> None: ...
        def _get_approval_period_start(
            self, kid_id: str, chore_id: str
        ) -> str | None: ...

        # Additional attributes
        stats: Any  # StatisticsEngine

        @property
        def achievements_data(self) -> dict[str, Any]: ...
        @property
        def challenges_data(self) -> dict[str, Any]: ...

    # =========================================================================
    # CHORE OPERATIONS METHODS
    # =========================================================================
    # CHORE OPERATIONS - EXTRACTED FROM COORDINATOR.PY
    # =========================================================================
    # Methods extracted following Phase 0 protocol (Jan 2026).
    # All logic copied verbatim - no changes to behavior, formatting, or comments.
    #
    # This file is organized into 11 logical sections (§1-§11) for clarity.
    # Each section groups related operations by purpose and calling context.
    # =========================================================================

    # =========================================================================
    # §1 SERVICE ENTRY POINTS (7 methods)
    # =========================================================================
    # Home Assistant service handlers - called from services.py
    # External API contract: Service names in services.yaml must remain stable
    # Internal naming: Method names can change without breaking external contracts

    def claim_chore(self, kid_id: str, chore_id: str, user_name: str):
        """Kid claims chore => state=claimed; parent must then approve."""
        perf_start = time.perf_counter()
        if chore_id not in self.chores_data:
            const.LOGGER.warning(
                "WARNING: Claim Chore - Chore ID '%s' not found", chore_id
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        chore_info = self.chores_data[chore_id]
        if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            const.LOGGER.warning(
                "WARNING: Claim Chore - Chore ID '%s' not assigned to kid ID '%s'",
                chore_id,
                kid_id,
            )
            chore_name = chore_info.get(const.DATA_CHORE_NAME) or ""
            kid_name = self.kids_data[kid_id][const.DATA_KID_NAME]
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                translation_placeholders={
                    "entity": chore_name,
                    "kid": kid_name,
                },
            )

        if kid_id not in self.kids_data:
            const.LOGGER.warning("Kid ID '%s' not found", kid_id)
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        kid_info = self.kids_data[kid_id]

        self._normalize_kid_reward_data(kid_info)

        # Phase 4: Use timestamp-based helpers instead of deprecated lists
        # This checks: completed_by_other, pending_claim, already_approved
        can_claim, error_key = self._can_claim_chore(kid_id, chore_id)
        if not can_claim:
            chore_name = chore_info[const.DATA_CHORE_NAME]
            const.LOGGER.warning(
                "WARNING: Claim Chore - Chore '%s' cannot be claimed by kid '%s': %s",
                chore_name,
                kid_info.get(const.DATA_KID_NAME),
                error_key,
            )

            # Determine the appropriate error message based on the error key
            if error_key == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER:
                # Get the name of who completed the chore
                kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
                claimed_by = kid_chore_data.get(
                    const.DATA_CHORE_CLAIMED_BY, "another kid"
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_CLAIMED_BY_OTHER,
                    translation_placeholders={"claimed_by": str(claimed_by)},
                )
            if error_key == const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM,
                    translation_placeholders={"entity": chore_name},
                )
            # else: TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_ALREADY_CLAIMED,
                translation_placeholders={"entity": chore_name},
            )

        # Increment pending_count counter BEFORE _transition_chore_state so chore_has_pending_claim()
        # returns the correct value during global state computation (v0.4.0+ counter-based tracking)
        # Use _update_kid_chore_data to ensure proper initialization
        chore_info = self.chores_data[chore_id]
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
        self._update_kid_chore_data(kid_id, chore_id, 0.0)  # Initialize properly
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
        kid_chore_data_entry = kid_chores_data[chore_id]  # Now guaranteed to exist
        current_count = kid_chore_data_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = (
            current_count + 1
        )

        self._transition_chore_state(kid_id, chore_id, const.CHORE_STATE_CLAIMED)

        # Set claimed_by for ALL chore types (helper handles INDEPENDENT/SHARED_FIRST/SHARED)
        claiming_kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        self._set_chore_claimed_completed_by(
            chore_id, kid_id, const.DATA_CHORE_CLAIMED_BY, claiming_kid_name
        )

        # For SHARED_FIRST, also set other kids to completed_by_other state
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if other_kid_id == kid_id:
                    continue
                self._transition_chore_state(
                    other_kid_id, chore_id, const.CHORE_STATE_COMPLETED_BY_OTHER
                )

        # Check if auto_approve is enabled for this chore
        auto_approve = chore_info.get(
            const.DATA_CHORE_AUTO_APPROVE, const.DEFAULT_CHORE_AUTO_APPROVE
        )

        if auto_approve:
            # Auto-approve the chore immediately (using create_task since approve_chore is async)
            self.hass.async_create_task(
                self.approve_chore("auto_approve", kid_id, chore_id)
            )
        # Send a notification to the parents that a kid claimed a chore (awaiting approval)
        # Uses tag-based aggregation (v0.5.0+) to prevent notification spam
        elif chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
        ):
            # Count total pending chores for this kid (for aggregated notification)
            pending_count = self._count_chores_pending_for_kid(kid_id)
            chore_name = self.chores_data[chore_id][const.DATA_CHORE_NAME]
            kid_name = self.kids_data[kid_id][const.DATA_KID_NAME]
            chore_points = chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
            )

            # Build action buttons using helper (DRY refactor v0.5.0+)
            actions = build_chore_actions(kid_id, chore_id)
            extra_data = build_extra_data(kid_id, chore_id=chore_id)

            # Use aggregated notification if multiple pending, else standard single
            if pending_count > 1:
                # Aggregated notification: "Sarah: 3 chores pending (latest: Dishes +5pts)"
                self.hass.async_create_task(
                    self._notify_parents_translated(
                        kid_id,
                        title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES,
                        message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES,
                        message_data={
                            "kid_name": kid_name,
                            "count": pending_count,
                            "latest_chore": chore_name,
                            "points": int(chore_points),
                        },
                        actions=actions,
                        extra_data=extra_data,
                        tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                        tag_identifiers=(chore_id, kid_id),
                    )
                )
            else:
                # Single pending chore - use standard claim notification with tag
                self.hass.async_create_task(
                    self._notify_parents_translated(
                        kid_id,
                        title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED,
                        message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED,
                        message_data={
                            "kid_name": kid_name,
                            "chore_name": chore_name,
                        },
                        actions=actions,
                        extra_data=extra_data,
                        tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                        tag_identifiers=(chore_id, kid_id),
                    )
                )

        # Clear due-soon reminder tracking (v0.5.0+) - chore was acted upon
        self._clear_chore_due_reminder(chore_id, kid_id)

        self._persist()
        self.async_set_updated_data(self._data)

        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: claim_chore() took %.3fs for kid '%s' chore '%s'",
            perf_duration,
            kid_id,
            chore_id,
        )

    def disapprove_chore(self, parent_name: str, kid_id: str, chore_id: str):
        """Disapprove a chore for kid_id."""
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Decrement pending_count for the claimant ONLY (v0.4.0+ counter-based tracking)
        # This happens regardless of completion criteria - only the kid who claimed is affected
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
        # Ensure proper chore data initialization
        if chore_id not in kid_chores_data:
            self._update_kid_chore_data(kid_id, chore_id, 0.0)
        kid_chore_data_entry = kid_chores_data[chore_id]
        current_count = kid_chore_data_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current_count - 1
        )

        # SHARED_FIRST: Reset ALL kids to pending (everyone gets another chance)
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            const.LOGGER.info(
                "SHARED_FIRST: Disapproval - resetting all kids to pending for chore '%s'",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                self._transition_chore_state(
                    other_kid_id, chore_id, const.CHORE_STATE_PENDING
                )
            # Clear claimed_by/completed_by for all assigned kids
            self._clear_chore_claimed_completed_by(chore_id)
        else:
            # Normal behavior: only reset the disapproved kid
            self._transition_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)

        # Send a notification to the kid that chore was disapproved
        if chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL, const.DEFAULT_NOTIFY_ON_DISAPPROVAL
        ):
            extra_data = {const.DATA_KID_ID: kid_id, const.DATA_CHORE_ID: chore_id}
            self.hass.async_create_task(
                self._notify_kid_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DISAPPROVED,
                    message_data={"chore_name": chore_info[const.DATA_CHORE_NAME]},
                    extra_data=extra_data,
                )
            )

        # Send notification to parents about disapproval with updated pending count
        remaining_pending = self._count_chores_pending_for_kid(kid_id)
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

        if remaining_pending > 0:
            # Still have pending chores - send updated aggregated notification
            latest_pending = self._get_latest_chore_pending(kid_id)
            if latest_pending:
                latest_chore_id = latest_pending.get(const.DATA_CHORE_ID, "")
                if latest_chore_id and latest_chore_id in self.chores_data:
                    latest_chore_info = self.chores_data[latest_chore_id]
                    latest_chore_name = latest_chore_info.get(
                        const.DATA_CHORE_NAME, "Unknown"
                    )
                    latest_points = latest_chore_info.get(
                        const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
                    )
                    # Use helpers for action buttons (DRY refactor v0.5.0+)
                    actions = build_chore_actions(kid_id, latest_chore_id)
                    self.hass.async_create_task(
                        self._notify_parents_translated(
                            kid_id,
                            title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES,
                            message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES,
                            message_data={
                                "kid_name": kid_name,
                                "count": remaining_pending,
                                "latest_chore": latest_chore_name,
                                "points": int(latest_points),
                            },
                            actions=actions,
                            extra_data=build_extra_data(
                                kid_id, chore_id=latest_chore_id
                            ),
                            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                            tag_identifiers=(latest_chore_id, kid_id),
                        )
                    )

        # Clear the disapproved chore's notification (v0.5.0+ - handles dashboard disapprovals)
        self.hass.async_create_task(
            self.clear_notification_for_parents(
                kid_id, const.NOTIFY_TAG_TYPE_STATUS, chore_id
            )
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # =========================================================================
    # §3 VALIDATION LOGIC (2 methods)
    # =========================================================================
    # Pre-condition checks for chore operations

    def _can_claim_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
        """Check if a kid can claim a specific chore.

        This helper is dual-purpose: used for claim validation AND for providing
        status information to the dashboard helper sensor.

        Checks (in order):
        1. completed_by_other - Another kid already completed (SHARED_FIRST mode)
        2. pending_claim - Already has a claim awaiting approval
        3. already_approved - Already approved in current period (if not multi-claim)

        Returns:
            Tuple of (can_claim: bool, error_key: str | None)
            - (True, None) if claim is allowed
            - (False, translation_key) if claim is blocked
        """
        # Get current state for this kid+chore
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all claims
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Determine if this is a multi-claim mode (needed for checks 2 and 3)
        allow_multiple_claims = self._chore_allows_multiple_claims(chore_id)

        # Check 2: pending claim blocks new claims (unless multi-claim allowed)
        # For MULTI modes, re-claiming is allowed even with a pending claim
        if not allow_multiple_claims and self.chore_has_pending_claim(kid_id, chore_id):
            return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)

        # Check 3: already approved in current period (unless multi-claim allowed)
        if not allow_multiple_claims and self.chore_is_approved_in_period(
            kid_id, chore_id
        ):
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    def _can_approve_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
        """Check if a chore can be approved for a specific kid.

        This helper is dual-purpose: used for approval validation AND for providing
        status information to the dashboard helper sensor.

        Checks (in order):
        1. completed_by_other - Another kid already completed (SHARED_FIRST mode)
        2. already_approved - Already approved in current period (if not multi-claim)

        Note: Unlike _can_claim_chore, this does NOT check for pending claims because
        we're checking if approval is possible, not if a new claim can be made.

        Returns:
            Tuple of (can_approve: bool, error_key: str | None)
            - (True, None) if approval is allowed
            - (False, translation_key) if approval is blocked
        """
        # Get current state for this kid+chore
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all approvals
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Check 2: already approved in current period (unless multi-claim allowed)
        allow_multiple_claims = self._chore_allows_multiple_claims(chore_id)

        if not allow_multiple_claims and self.chore_is_approved_in_period(
            kid_id, chore_id
        ):
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    def undo_chore_claim(self, kid_id: str, chore_id: str):
        """Allow kid to undo their own chore claim (no stat tracking).

        This method provides a way for kids to remove their claim on a chore
        without it counting as a disapproval. Similar to disapprove_chore but:
        - Does NOT track disapproval stats (skip_stats=True)
        - Does NOT send notifications (silent undo)
        - Only resets the kid who is undoing (not all kids for SHARED_FIRST)

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Raises:
            HomeAssistantError: If kid or chore not found
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Decrement pending_count for the kid (v0.4.0+ counter-based tracking)
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
        # Ensure proper chore data initialization
        if chore_id not in kid_chores_data:
            self._update_kid_chore_data(kid_id, chore_id, 0.0)
        kid_chore_data_entry = kid_chores_data[chore_id]
        current_count = kid_chore_data_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current_count - 1
        )

        # SHARED_FIRST: For kid undo, reset ALL kids to pending (same as disapproval)
        # This maintains fairness - if one kid undoes, everyone gets another chance
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            const.LOGGER.info(
                "SHARED_FIRST: Kid undo - resetting all kids to pending for chore '%s'",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                # Use skip_stats=True to prevent stat tracking for all kids
                self._transition_chore_state(
                    other_kid_id, chore_id, const.CHORE_STATE_PENDING, skip_stats=True
                )
                # Clear claimed_by/completed_by attributes
                other_kid_info: KidData = cast(
                    "KidData", self.kids_data.get(other_kid_id, {})
                )
                chore_data = other_kid_info.get(const.DATA_KID_CHORE_DATA, {})
                if chore_id in chore_data:
                    chore_data[chore_id].pop(const.DATA_CHORE_CLAIMED_BY, None)
                    chore_data[chore_id].pop(const.DATA_CHORE_COMPLETED_BY, None)
        else:
            # Normal behavior: only reset the kid who is undoing, skip stats
            self._transition_chore_state(
                kid_id, chore_id, const.CHORE_STATE_PENDING, skip_stats=True
            )

        # No notification sent (silent undo)

        self._persist()
        self.async_set_updated_data(self._data)

    # =========================================================================
    # §4 STATE MACHINE (2 methods)
    # =========================================================================
    # Core state transition logic - central orchestration of chore lifecycle
    # Timestamp-based approval tracking (removed deprecated lists in v0.4.0)

    def _transition_chore_state(
        self,
        kid_id: str,
        chore_id: str,
        new_state: str,
        *,
        points_awarded: float | None = None,
        reset_approval_period: bool = False,
        skip_stats: bool = False,
    ) -> None:
        """Centralized function to update a chore's state for a given kid.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            new_state: The new state to set (PENDING, CLAIMED, APPROVED, etc.)
            points_awarded: Points to award (only for APPROVED state)
            reset_approval_period: If True and new_state is PENDING, sets a new
                approval_period_start. Should be True for scheduled resets (midnight,
                due date) but False for disapproval (which only affects one kid's claim).
            skip_stats: If True, skip disapproval stat tracking (for kid undo).
        """

        # Add a flag to control debug messages
        debug_enabled = False

        if debug_enabled:
            const.LOGGER.debug(
                "DEBUG: Chore State - Processing - Kid ID '%s', Chore ID '%s', State '%s', Points Awarded '%s'",
                kid_id,
                chore_id,
                new_state,
                points_awarded,
            )

        kid_info: KidData | None = self.kids_data.get(kid_id)
        chore_info: ChoreData | None = self.chores_data.get(chore_id)

        if not kid_info or not chore_info:
            const.LOGGER.warning(
                "WARNING: Chore State - Change skipped. Kid ID '%s' or Chore ID '%s' not found",
                kid_id,
                chore_id,
            )
            return

        # Update kid chore tracking data
        # Pass 0 for points_awarded if None and not in APPROVED state
        actual_points = points_awarded if points_awarded is not None else 0.0

        # Get due date to pass to kid chore data
        # For INDEPENDENT chores, use per-kid due date; for SHARED, use chore-level
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            due_date = per_kid_due_dates.get(kid_id)
        else:
            due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)

        # Update the kid's chore history
        self._update_kid_chore_data(
            kid_id=kid_id,
            chore_id=chore_id,
            points_awarded=actual_points,
            state=new_state,
            due_date=due_date,
            skip_stats=skip_stats,
        )

        # Clear overdue notification tracking when transitioning out of overdue state.
        # (State is now tracked via DATA_KID_CHORE_DATA_STATE, not a list)
        if new_state != const.CHORE_STATE_OVERDUE:
            overdue_notifs = kid_info.get(const.DATA_KID_OVERDUE_NOTIFICATIONS, {})
            if chore_id in overdue_notifs:
                overdue_notifs.pop(chore_id)
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = overdue_notifs

        if new_state == const.CHORE_STATE_CLAIMED:
            # Update kid_chore_data with claim timestamp (v0.4.0+ timestamp-based tracking)
            now_iso = dt_util.utcnow().isoformat()
            # Use _update_kid_chore_data to ensure proper initialization
            self._update_kid_chore_data(
                kid_id, chore_id, 0.0
            )  # No points awarded for claim
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            kid_chore_data_entry = kid_chores_data[
                chore_id
            ]  # Now guaranteed to exist and be properly initialized
            kid_chore_data_entry[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = now_iso

            chore_info[const.DATA_CHORE_LAST_CLAIMED] = now_iso
            # Queue write removed - pending approvals now computed from timestamps
            self._pending_chore_changed = True

        elif new_state == const.CHORE_STATE_APPROVED:
            # Update kid_chore_data with approval timestamp (v0.4.0+ timestamp-based tracking)
            now_iso = dt_util.utcnow().isoformat()
            # Use _update_kid_chore_data to ensure proper initialization
            self._update_kid_chore_data(kid_id, chore_id, points_awarded or 0.0)
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            kid_chore_data_entry = kid_chores_data[
                chore_id
            ]  # Now guaranteed to exist and be properly initialized
            kid_chore_data_entry[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso
            # NOTE: last_claimed is intentionally preserved after approval
            # to maintain consistent behavior with other last_* fields

            chore_info[const.DATA_CHORE_LAST_COMPLETED] = now_iso

            if points_awarded is not None:
                self.update_kid_points(
                    kid_id, delta=points_awarded, source=const.POINTS_SOURCE_CHORES
                )
            # Queue filter removed - pending approvals now computed from timestamps
            self._pending_chore_changed = True

        elif new_state == const.CHORE_STATE_PENDING:
            # Remove the chore from claimed, approved, and completed_by_other lists.
            # Clear from completed_by_other list
            completed_by_other = kid_info.get(
                const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
            )
            kid_info[const.DATA_KID_COMPLETED_BY_OTHER_CHORES] = [
                c for c in completed_by_other if c != chore_id
            ]

            # NOTE: last_approved is intentionally NEVER removed - it's for historical
            # tracking. Period-based approval validation uses approval_period_start
            # to determine if approval is valid for the current period.
            # chore_is_approved_in_period() checks: last_approved >= approval_period_start

            # Only reset approval_period_start during scheduled resets (midnight, due date)
            # NOT during disapproval - disapproval only affects that kid's pending claim
            if reset_approval_period:
                now_iso = dt_util.utcnow().isoformat()
                kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
                completion_criteria = chore_info.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
                )
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # INDEPENDENT: Store per-kid approval_period_start in kid_chore_data
                    if chore_id not in kid_chores_data:
                        self._update_kid_chore_data(kid_id, chore_id, 0.0)
                    kid_chore_data_entry = kid_chores_data[chore_id]
                    kid_chore_data_entry[
                        const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
                    ] = now_iso
                else:
                    # SHARED/SHARED_FIRST: Store at chore level
                    chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso

                # Clear claimed_by and completed_by for all assigned kids
                # These fields represent current approval period state, not historical
                self._clear_chore_claimed_completed_by(chore_id)

            # Queue filter removed - pending approvals now computed from timestamps
            self._pending_chore_changed = True

        elif new_state == const.CHORE_STATE_OVERDUE:
            # Overdue state is now tracked via DATA_KID_CHORE_DATA_STATE
            # (set by _update_kid_chore_data above)
            pass

        elif new_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            # SHARED_FIRST: This kid didn't complete the chore, another kid did
            # Clear last_claimed in kid_chore_data (v0.4.0+ timestamp-based tracking)
            # NOTE: last_approved is intentionally NEVER removed - historical tracking
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            if chore_id in kid_chores_data:
                kid_chores_data[chore_id].pop(
                    const.DATA_KID_CHORE_DATA_LAST_CLAIMED, None
                )

            # State is now tracked via DATA_KID_CHORE_DATA_STATE (set above)
            # Add to completed_by_other list to track this state
            completed_by_other = kid_info.setdefault(
                const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
            )
            if chore_id not in completed_by_other:
                completed_by_other.append(chore_id)

        # Compute and update the chore's global state.
        # Given the process above is handling everything properly for each kid, computing the global state straightforward.
        # This process needs run every time a chore state changes, so it no longer warrants a separate function.
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        if len(assigned_kids) == 1:
            # if only one kid is assigned to the chore, update the chore state to new state 1:1
            chore_info[const.DATA_CHORE_STATE] = new_state
        elif len(assigned_kids) > 1:
            # For chores assigned to multiple kids, you have to figure out the global state
            count_pending = count_claimed = count_approved = count_overdue = (
                const.DEFAULT_ZERO
            )
            count_completed_by_other = const.DEFAULT_ZERO
            for kid_id_iter in assigned_kids:
                kid_info_iter: KidData = cast(
                    "KidData", self.kids_data.get(kid_id_iter, {})
                )

                # For SHARED_FIRST: claims always win over overdue
                # Once someone claims, they're "claimed", others are "completed_by_other"
                # Overdue only applies when NO ONE has claimed yet
                if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                    if self.chore_is_approved_in_period(kid_id_iter, chore_id):
                        count_approved += 1
                    elif self.chore_has_pending_claim(kid_id_iter, chore_id):
                        count_claimed += 1
                    elif chore_id in kid_info_iter.get(
                        const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
                    ):
                        count_completed_by_other += 1
                    elif self.chore_is_overdue(kid_id_iter, chore_id):
                        count_overdue += 1
                    else:
                        count_pending += 1
                # For non-SHARED_FIRST: original priority (overdue checked first)
                elif self.chore_is_overdue(kid_id_iter, chore_id):
                    count_overdue += 1
                elif self.chore_is_approved_in_period(kid_id_iter, chore_id):
                    count_approved += 1
                elif self.chore_has_pending_claim(kid_id_iter, chore_id):
                    count_claimed += 1
                elif chore_id in kid_info_iter.get(
                    const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
                ):
                    count_completed_by_other += 1
                else:
                    count_pending += 1
            total = len(assigned_kids)

            # If all kids are in the same state, update the chore state to new state 1:1
            if total in (count_pending, count_claimed, count_approved, count_overdue):
                chore_info[const.DATA_CHORE_STATE] = new_state

            # For SHARED_FIRST chores, global state follows the single claimant's state
            # Other kids are in completed_by_other state but don't affect progression
            elif (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED_FIRST
            ):
                # SHARED_FIRST: global state tracks the claimant's progression
                # Once any kid claims/approves, their state drives the global state
                # Other kids' states (pending/overdue/completed_by_other) don't affect it
                if count_approved > const.DEFAULT_ZERO:
                    # Someone completed it - chore is done
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED
                elif count_claimed > const.DEFAULT_ZERO:
                    # Someone claimed it - waiting for approval
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED
                elif count_overdue > const.DEFAULT_ZERO:
                    # No one claimed yet, chore is overdue
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
                else:
                    # No one claimed yet, chore is pending
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING

            # For shared chores, recompute global state of a partial if they aren't all in the same state as checked above
            elif (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED
            ):
                if count_overdue > const.DEFAULT_ZERO:
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
                elif count_approved > const.DEFAULT_ZERO:
                    chore_info[const.DATA_CHORE_STATE] = (
                        const.CHORE_STATE_APPROVED_IN_PART
                    )
                elif count_claimed > const.DEFAULT_ZERO:
                    chore_info[const.DATA_CHORE_STATE] = (
                        const.CHORE_STATE_CLAIMED_IN_PART
                    )
                else:
                    chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN

            # For independent chores assigned to multiple kids, set state to INDEPENDENT if not all in same state
            else:
                chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_INDEPENDENT

        else:
            chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN

        if debug_enabled:
            const.LOGGER.debug(
                "DEBUG: Chore State - Chore ID '%s' Global State changed to '%s'",
                chore_id,
                chore_info[const.DATA_CHORE_STATE],
            )

    # =========================================================================
    # §5 DATA MANAGEMENT (2 methods)
    # =========================================================================
    # Kid-specific chore data tracking and updates

    def _update_kid_chore_data(
        self,
        kid_id: str,
        chore_id: str,
        points_awarded: float,
        *,
        state: str | None = None,
        due_date: str | None = None,
        skip_stats: bool = False,
    ):
        """
        Update a kid's chore data when a state change or completion occurs.

        Args:
            kid_id: The ID of the kid
            chore_id: The ID of the chore
            points_awarded: Points awarded for this chore
            state: New chore state (if state is changing)
            due_date: New due date (if due date is changing)
            skip_stats: If True, skip disapproval stat tracking (for kid undo).
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return

        # Get chore name for reference
        chore_info: ChoreData = cast("ChoreData", self.chores_data.get(chore_id, {}))
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)

        # Initialize chore data structure if needed
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})

        # Initialize this chore's data if it doesn't exist yet
        kid_chore_data = kid_chores_data.setdefault(
            chore_id,
            {
                const.DATA_KID_CHORE_DATA_NAME: chore_name,
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
                const.DATA_KID_CHORE_DATA_LAST_CLAIMED: "",
                const.DATA_KID_CHORE_DATA_LAST_APPROVED: "",
                const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED: "",
                const.DATA_KID_CHORE_DATA_LAST_OVERDUE: "",
                const.DATA_KID_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME: 0,
                const.DATA_KID_CHORE_DATA_PERIODS: {
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_YEARLY: {},
                    const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME: {},
                },
                const.DATA_KID_CHORE_DATA_BADGE_REFS: [],
            },
        )

        # --- Use a consistent default dict for all period stats ---
        period_default = {
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 0.0,
            const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 0,
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
        }

        # Get period keys using constants
        now_utc = dt_util.utcnow()
        now_iso = now_utc.isoformat()
        now_local = kh.dt_now_local()
        today_local = kh.dt_today_local()
        today_local_iso = today_local.isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        # For updating period stats - use setdefault to handle partial structures
        periods_data = kid_chore_data.setdefault(
            const.DATA_KID_CHORE_DATA_PERIODS,
            {
                const.DATA_KID_CHORE_DATA_PERIODS_DAILY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_YEARLY: {},
                const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME: {},
            },
        )
        # Build period mapping for StatisticsEngine
        period_mapping = self.stats.get_period_keys(now_local)
        # Non-daily mapping for overdue/disapproved (daily handled separately)
        period_mapping_no_daily = {
            k: v
            for k, v in period_mapping.items()
            if k != const.DATA_KID_CHORE_DATA_PERIODS_DAILY
        }
        previous_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
        points_awarded = (
            round(points_awarded, const.DATA_FLOAT_PRECISION)
            if points_awarded is not None
            else 0.0
        )

        # --- All-time stats update helpers ---
        chore_stats = kid_info.setdefault(const.DATA_KID_CHORE_STATS, {})

        def inc_stat(key: str, amount: float) -> None:
            chore_stats[key] = chore_stats.get(key, 0) + amount

        if state is not None:
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = state

            # --- Handle CLAIMED state ---
            if state == const.CHORE_STATE_CLAIMED:
                kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = now_iso
                self.stats.record_transaction(
                    periods_data,
                    {const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 1},
                    period_key_mapping=period_mapping,
                )
                # Increment all-time claimed count
                inc_stat(const.DATA_KID_CHORE_STATS_CLAIMED_ALL_TIME, 1)

            # --- Handle APPROVED state ---
            elif state == const.CHORE_STATE_APPROVED:
                # Deprecated counters removed - using chore_stats only

                # Get last approved time BEFORE updating it (for streak calculation)
                previous_last_approved_str = kid_chore_data.get(
                    const.DATA_KID_CHORE_DATA_LAST_APPROVED
                )

                kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso

                inc_stat(const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, 1)
                inc_stat(
                    const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_ALL_TIME,
                    points_awarded,
                )

                # Update period stats for count and points
                self.stats.record_transaction(
                    periods_data,
                    {
                        const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 1,
                        const.DATA_KID_CHORE_DATA_PERIOD_POINTS: points_awarded,
                    },
                    period_key_mapping=period_mapping,
                )

                # Calculate today's streak using schedule-aware logic
                yesterday_local_iso = kh.dt_add_interval(
                    today_local_iso,
                    interval_unit=const.TIME_UNIT_DAYS,
                    delta=-1,
                    require_future=False,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )
                yesterday_chore_data = periods_data[
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY
                ].get(yesterday_local_iso, {})
                yesterday_streak = yesterday_chore_data.get(
                    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                )

                # Get frequency for schedule-aware check
                # (use previous_last_approved_str captured above, not the updated value)
                frequency = chore_info.get(
                    const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
                )

                # Calculate streak based on schedule
                if not previous_last_approved_str:
                    # First approval ever
                    today_streak = 1
                elif not frequency or frequency == const.FREQUENCY_NONE:
                    # No schedule configured - use legacy day-gap logic
                    today_streak = yesterday_streak + 1 if yesterday_streak > 0 else 1
                else:
                    # Schedule-aware: check if any occurrences were missed
                    try:
                        # Build ScheduleConfig with proper types
                        raw_interval = chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL)
                        raw_unit = chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT)
                        raw_days = chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, [])

                        # For streak calculation, base_date should be last_approved
                        # so we can detect occurrences between then and now
                        schedule_config: ScheduleConfig = {
                            "frequency": frequency,
                            "interval": int(raw_interval) if raw_interval else 1,
                            "interval_unit": str(raw_unit)
                            if raw_unit
                            else const.TIME_UNIT_DAYS,
                            "applicable_days": [
                                int(d) for d in raw_days if d is not None
                            ],
                            "base_date": previous_last_approved_str,
                        }
                        engine = RecurrenceEngine(schedule_config)
                        last_approved_dt = kh.dt_to_utc(previous_last_approved_str)

                        if last_approved_dt and engine.has_missed_occurrences(
                            last_approved_dt, now_utc
                        ):
                            today_streak = 1  # Broke streak
                        else:
                            today_streak = (
                                yesterday_streak + 1 if yesterday_streak > 0 else 1
                            )
                    except Exception:  # pylint: disable=broad-except
                        # Fallback to legacy day-gap logic on any error
                        const.LOGGER.debug(
                            "Schedule-aware streak check failed for %s, using legacy",
                            chore_name,
                        )
                        today_streak = (
                            yesterday_streak + 1 if yesterday_streak > 0 else 1
                        )

                # Store today's streak as the daily longest streak
                daily_data = periods_data.get(
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                ).setdefault(today_local_iso, period_default.copy())
                daily_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = (
                    today_streak
                )

                # --- All-time longest streak update (per-chore and per-kid) ---
                all_time_data = periods_data.get(
                    const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
                ).setdefault(const.PERIOD_ALL_TIME, period_default.copy())
                prev_all_time_streak = all_time_data.get(
                    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                )
                if today_streak > prev_all_time_streak:
                    all_time_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = (
                        today_streak
                    )
                    kid_chore_data[
                        const.DATA_KID_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME
                    ] = today_local_iso

                # Update streak for higher periods if needed (excluding all_time, already handled above)
                for period_key, period_id in [
                    (const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY, week_local_iso),
                    (const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, month_local_iso),
                    (const.DATA_KID_CHORE_DATA_PERIODS_YEARLY, year_local_iso),
                ]:
                    period_dict = periods_data.get(period_key, {})
                    period_data_dict = period_dict.setdefault(
                        period_id, period_default.copy()
                    )
                    if today_streak > period_data_dict.get(
                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                    ):
                        period_data_dict[
                            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
                        ] = today_streak

                # Still update the kid's global all-time longest streak if this is a new record
                longest_streak_all_time = chore_stats.get(
                    const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME, 0
                )
                if today_streak > longest_streak_all_time:
                    chore_stats[const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME] = (
                        today_streak
                    )

            # --- Handle OVERDUE state ---
            elif state == const.CHORE_STATE_OVERDUE:
                kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_OVERDUE] = now_iso
                daily_bucket = periods_data.setdefault(
                    const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                )
                daily_data = daily_bucket.setdefault(
                    today_local_iso,
                    period_default.copy(),
                )
                for key, val in period_default.items():
                    daily_data.setdefault(key, val)
                first_overdue_today = (
                    daily_data.get(const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0) < 1
                )
                if first_overdue_today:
                    daily_data[const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE] = 1
                    # Only increment higher periods if this is the first overdue for today
                    self.stats.record_transaction(
                        periods_data,
                        {const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 1},
                        period_key_mapping=period_mapping_no_daily,
                    )
                    inc_stat(const.DATA_KID_CHORE_STATS_OVERDUE_ALL_TIME, 1)

            # --- Handle DISAPPROVED (claimed -> pending) state ---
            elif (
                state == const.CHORE_STATE_PENDING
                and previous_state == const.CHORE_STATE_CLAIMED
            ):
                # Only track disapproval stats if skip_stats is False (parent/admin disapproval)
                if not skip_stats:
                    kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = now_iso
                    daily_bucket_d = periods_data.setdefault(
                        const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                    )
                    daily_data = daily_bucket_d.setdefault(
                        today_local_iso,
                        period_default.copy(),
                    )
                    for key, val in period_default.items():
                        daily_data.setdefault(key, val)
                    first_disapproved_today = (
                        daily_data.get(const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0)
                        < 1
                    )
                    if first_disapproved_today:
                        daily_data[const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED] = 1
                        self.stats.record_transaction(
                            periods_data,
                            {const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 1},
                            period_key_mapping=period_mapping_no_daily,
                        )
                        inc_stat(const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME, 1)

        # Clean up old period data to keep storage manageable
        self.stats.prune_history(periods_data, self._get_retention_config())

        # --- Update kid_chore_stats after all per-chore updates ---
        self._recalculate_chore_stats_for_kid(kid_id)

    async def approve_chore(
        self,
        parent_name: str,  # Used for stale notification feedback
        kid_id: str,
        chore_id: str,
        points_awarded: float | None = None,  # Reserved for future feature
    ):
        """Approve a chore for kid_id if assigned.

        Thread-safe implementation using asyncio.Lock to prevent race conditions
        when multiple parents click approve simultaneously (v0.5.0+).
        """
        perf_start = time.perf_counter()

        # Acquire lock for this specific kid+chore combination to prevent race conditions
        # This ensures only one approval can process at a time per kid+chore pair
        lock = self._get_approval_lock("approve_chore", kid_id, chore_id)
        async with lock:
            # === RACE CONDITION PROTECTION (v0.5.0+) ===
            # Re-validate inside lock - second parent to arrive will hit this
            # and return gracefully with informative feedback instead of duplicate approval
            can_approve, error_key = self._can_approve_chore(kid_id, chore_id)
            if not can_approve:
                # Chore was already approved by another parent while we waited for lock
                # Return gracefully - this is expected behavior, not an error
                const.LOGGER.info(
                    "Race condition prevented: chore '%s' for kid '%s' already %s",
                    chore_id,
                    kid_id,
                    "approved"
                    if error_key == const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED
                    else "completed by another kid",
                )
                # TODO (Phase 1.4): Send stale notification feedback to parent_name
                # "Already approved by {other_parent}" or similar
                return  # Graceful exit - no error raised for race condition

            # === ORIGINAL VALIDATION (now inside lock) ===
            if chore_id not in self.chores_data:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_CHORE,
                        "name": chore_id,
                    },
                )

            chore_info = self.chores_data[chore_id]
            if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                chore_name = chore_info.get(const.DATA_CHORE_NAME) or ""
                kid_name = self.kids_data[kid_id][const.DATA_KID_NAME]
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": chore_name,
                        "kid": kid_name,
                    },
                )

            if kid_id not in self.kids_data:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info = self.kids_data[kid_id]

            # Phase 4: Use timestamp-based helpers instead of deprecated lists
            # This checks: completed_by_other, already_approved
            can_approve, error_key = self._can_approve_chore(kid_id, chore_id)
            if not can_approve:
                chore_name = chore_info[const.DATA_CHORE_NAME]
                const.LOGGER.warning(
                    "Approve Chore: Cannot approve '%s' for kid '%s': %s",
                    chore_name,
                    kid_info[const.DATA_KID_NAME],
                    error_key,
                )
                # Determine the appropriate error message based on the error key
                if error_key == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER:
                    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
                    claimed_by = kid_chore_data.get(
                        const.DATA_CHORE_CLAIMED_BY, "another kid"
                    )
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER,
                        translation_placeholders={
                            "chore_name": chore_name,
                            "claimed_by": str(claimed_by),
                        },
                    )
                # else: TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED,
                )

            default_points = chore_info.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS
            )

            # Phase 4: Check if gamification is enabled for shadow kids
            # Regular kids always get points; shadow kids only if gamification enabled
            enable_gamification = True  # Default for regular kids
            if kh.is_shadow_kid(self, kid_id):  # type: ignore[arg-type]
                parent_data = kh.get_parent_for_shadow_kid(self, kid_id)  # type: ignore[arg-type]
                if parent_data:
                    enable_gamification = parent_data.get(
                        const.DATA_PARENT_ENABLE_GAMIFICATION, False
                    )

            # Award points only if gamification is enabled
            points_to_award = default_points if enable_gamification else 0.0

            # Note - multiplier will be added in the _update_kid_points method called from _transition_chore_state
            self._transition_chore_state(
                kid_id,
                chore_id,
                const.CHORE_STATE_APPROVED,
                points_awarded=points_to_award,
            )

            # Decrement pending_count counter after approval (v0.4.0+ counter-based tracking)
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            # Use get() to avoid overwriting existing data that _transition_chore_state just created
            kid_chore_data_entry = kid_chores_data[
                chore_id
            ]  # Should exist from _transition_chore_state
            current_count = kid_chore_data_entry.get(
                const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
            )
            kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
                0, current_count - 1
            )

            # Set completed_by for ALL chore types
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
            )
            completing_kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT: Store completing kid's own name in their kid_chore_data
                kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
                if chore_id not in kid_chores_data:
                    self._update_kid_chore_data(kid_id, chore_id, 0.0)
                kid_chores_data[chore_id][const.DATA_CHORE_COMPLETED_BY] = (
                    completing_kid_name
                )
                const.LOGGER.debug(
                    "INDEPENDENT: Set completed_by='%s' for kid '%s' on chore '%s'",
                    completing_kid_name,
                    completing_kid_name,
                    chore_info.get(const.DATA_CHORE_NAME),
                )

            elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                # SHARED_FIRST: Update completed_by for other kids (they remain in completed_by_other state)
                for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if other_kid_id == kid_id:
                        continue  # Skip the completing kid
                    # Update the completed_by attribute
                    other_kid_info: KidData = cast(
                        "KidData", self.kids_data.get(other_kid_id, {})
                    )
                    chore_data = other_kid_info.setdefault(
                        const.DATA_KID_CHORE_DATA, {}
                    )
                    # Ensure proper chore data initialization
                    if chore_id not in chore_data:
                        self._update_kid_chore_data(other_kid_id, chore_id, 0.0)
                    chore_entry = chore_data[chore_id]
                    chore_entry[const.DATA_CHORE_COMPLETED_BY] = completing_kid_name
                    const.LOGGER.debug(
                        "SHARED_FIRST: Updated completed_by='%s' for kid '%s' on chore '%s'",
                        completing_kid_name,
                        other_kid_info.get(const.DATA_KID_NAME),
                        chore_info.get(const.DATA_CHORE_NAME),
                    )

            elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
                # SHARED_ALL: Append to list of completing kids in each kid's own kid_chore_data
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    assigned_kid_info: KidData = cast(
                        "KidData", self.kids_data.get(assigned_kid_id, {})
                    )
                    assigned_kid_chore_data = assigned_kid_info.setdefault(
                        const.DATA_KID_CHORE_DATA, {}
                    )
                    # Ensure proper initialization
                    if chore_id not in assigned_kid_chore_data:
                        self._update_kid_chore_data(assigned_kid_id, chore_id, 0.0)
                    chore_entry = assigned_kid_chore_data[chore_id]

                    # Initialize as list if not present or if it's not a list
                    if (
                        const.DATA_CHORE_COMPLETED_BY not in chore_entry
                        or not isinstance(
                            chore_entry[const.DATA_CHORE_COMPLETED_BY], list
                        )
                    ):
                        chore_entry[const.DATA_CHORE_COMPLETED_BY] = []

                    # Append completing kid's name if not already in list
                    completed_by_list = chore_entry.get(
                        const.DATA_CHORE_COMPLETED_BY, []
                    )
                    if (
                        isinstance(completed_by_list, list)
                        and completing_kid_name not in completed_by_list
                    ):
                        completed_by_list.append(completing_kid_name)
                        chore_entry[const.DATA_CHORE_COMPLETED_BY] = completed_by_list

                const.LOGGER.debug(
                    "SHARED_ALL: Added '%s' to completed_by list for chore '%s'",
                    completing_kid_name,
                    chore_info.get(const.DATA_CHORE_NAME),
                )

            # Manage Achievements
            today_local = kh.dt_today_local()
            for achievement_info in self.achievements_data.values():
                if (
                    achievement_info.get(const.DATA_ACHIEVEMENT_TYPE)
                    == const.ACHIEVEMENT_TYPE_STREAK
                ):
                    selected_chore_id = achievement_info.get(
                        const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID
                    )
                    if selected_chore_id == chore_id:
                        # Get or create the progress dict for this kid
                        ach_progress_data: dict[str, AchievementProgress] = (
                            achievement_info.setdefault(
                                const.DATA_ACHIEVEMENT_PROGRESS, {}
                            )
                        )
                        ach_progress: AchievementProgress = (
                            ach_progress_data.setdefault(
                                kid_id,
                                {
                                    const.DATA_KID_CURRENT_STREAK: const.DEFAULT_ZERO,
                                    const.DATA_KID_LAST_STREAK_DATE: None,
                                    const.DATA_ACHIEVEMENT_AWARDED: False,
                                },
                            )
                        )
                        self._update_streak_progress(ach_progress, today_local)

            # Manage Challenges
            today_local_iso = kh.dt_today_iso()
            for challenge_info in self.challenges_data.values():
                challenge_type = challenge_info.get(const.DATA_CHALLENGE_TYPE)

                if challenge_type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                    selected_chore = challenge_info.get(
                        const.DATA_CHALLENGE_SELECTED_CHORE_ID
                    )
                    if selected_chore and selected_chore != chore_id:
                        continue

                    start_date_str = challenge_info.get(const.DATA_CHALLENGE_START_DATE)
                    end_date_str = challenge_info.get(const.DATA_CHALLENGE_END_DATE)
                    if not start_date_str or not end_date_str:
                        continue

                    start_date_utc = kh.dt_to_utc(start_date_str)
                    end_date_utc = kh.dt_to_utc(end_date_str)

                    now_utc = dt_util.utcnow()

                    if (
                        start_date_utc
                        and end_date_utc
                        and start_date_utc <= now_utc <= end_date_utc
                    ):
                        progress_data_ch1: dict[str, ChallengeProgress] = (
                            challenge_info.setdefault(const.DATA_CHALLENGE_PROGRESS, {})
                        )
                        ch1_progress: ChallengeProgress = progress_data_ch1.setdefault(
                            kid_id,
                            {
                                const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                                const.DATA_CHALLENGE_AWARDED: False,
                            },
                        )
                        ch1_progress[const.DATA_CHALLENGE_COUNT] = (
                            ch1_progress.get(const.DATA_CHALLENGE_COUNT, 0) + 1
                        )

                elif challenge_type == const.CHALLENGE_TYPE_DAILY_MIN:
                    selected_chore = challenge_info.get(
                        const.DATA_CHALLENGE_SELECTED_CHORE_ID
                    )
                    if not selected_chore:
                        const.LOGGER.warning(
                            "WARNING: Challenge '%s' of type daily minimum has no selected chore id. Skipping progress update.",
                            challenge_info.get(const.DATA_CHALLENGE_NAME),
                        )
                        continue

                    if selected_chore != chore_id:
                        continue

                    if kid_id in challenge_info.get(
                        const.DATA_CHALLENGE_ASSIGNED_KIDS, []
                    ):
                        progress_data_ch2: dict[str, ChallengeProgress] = (
                            challenge_info.setdefault(const.DATA_CHALLENGE_PROGRESS, {})
                        )
                        ch2_progress: ChallengeProgress = progress_data_ch2.setdefault(
                            kid_id,
                            {
                                const.DATA_CHALLENGE_DAILY_COUNTS: {},
                                const.DATA_CHALLENGE_AWARDED: False,
                            },
                        )
                        daily_counts = ch2_progress.get(
                            const.DATA_CHALLENGE_DAILY_COUNTS, {}
                        )
                        daily_counts[today_local_iso] = (
                            daily_counts.get(today_local_iso, const.DEFAULT_ZERO) + 1
                        )
                        ch2_progress[const.DATA_CHALLENGE_DAILY_COUNTS] = daily_counts

            # For INDEPENDENT chores with UPON_COMPLETION reset type, reschedule per-kid due date after approval
            # Other reset types (at_midnight_*, at_due_date_*) should NOT reschedule on approval
            # UNLESS overdue_handling is immediate_on_late AND approval is late
            approval_reset_type = chore_info.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
            )
            overdue_handling = chore_info.get(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.DEFAULT_OVERDUE_HANDLING_TYPE,
            )

            # Check if this is a late approval (after reset boundary passed)
            is_late_approval = self._is_chore_approval_after_reset(chore_info, kid_id)

            # Determine if immediate reschedule is needed
            should_reschedule_immediately = (
                approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
                or (
                    overdue_handling
                    == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
                    and is_late_approval
                )
            )

            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_INDEPENDENT
                and should_reschedule_immediately
            ):
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )

            # CFE-2026-002: For SHARED chores with UPON_COMPLETION, check if all kids approved
            # and reschedule chore-level due date immediately
            completion_criteria_check: str = (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) or ""
            )
            if (
                completion_criteria_check
                in (
                    const.COMPLETION_CRITERIA_SHARED,
                    const.COMPLETION_CRITERIA_SHARED_FIRST,
                )
                and should_reschedule_immediately
            ):
                # Check if all assigned kids have approved in current period
                assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                all_approved = all(
                    self.chore_is_approved_in_period(kid, chore_id)
                    for kid in assigned_kids
                )
                if all_approved:
                    const.LOGGER.debug(
                        "CFE-2026-002: All kids approved SHARED chore '%s', rescheduling immediately",
                        chore_info.get(const.DATA_CHORE_NAME),
                    )
                    self._reschedule_chore_next_due(chore_info)

            # Send a notification to the kid that chore was approved
            if chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            ):
                extra_data = {const.DATA_KID_ID: kid_id, const.DATA_CHORE_ID: chore_id}
                self.hass.async_create_task(
                    self._notify_kid_translated(
                        kid_id,
                        title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED,
                        message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED,
                        message_data={
                            "chore_name": chore_info[const.DATA_CHORE_NAME],
                            "points": default_points,
                        },
                        extra_data=extra_data,
                    )
                )

            # Replace parent pending notification with status update (v0.5.0+)
            # Check if there are more pending chores or clear with status
            remaining_pending = self._count_chores_pending_for_kid(kid_id)
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
            chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown")

            if remaining_pending > 0:
                # Still have pending chores - send updated aggregated notification
                # Get most recent pending chore for display
                latest_pending = self._get_latest_chore_pending(kid_id)
                if latest_pending:
                    latest_chore_id = latest_pending.get(const.DATA_CHORE_ID, "")
                    if latest_chore_id and latest_chore_id in self.chores_data:
                        latest_chore_info = self.chores_data[latest_chore_id]
                        latest_chore_name = latest_chore_info.get(
                            const.DATA_CHORE_NAME, "Unknown"
                        )
                        latest_points = latest_chore_info.get(
                            const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
                        )
                        # Use helpers for action buttons (DRY refactor v0.5.0+)
                        actions = build_chore_actions(kid_id, latest_chore_id)
                        self.hass.async_create_task(
                            self._notify_parents_translated(
                                kid_id,
                                title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES,
                                message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES,
                                message_data={
                                    "kid_name": kid_name,
                                    "count": remaining_pending,
                                    "latest_chore": latest_chore_name,
                                    "points": int(latest_points),
                                },
                                actions=actions,
                                extra_data=build_extra_data(
                                    kid_id, chore_id=latest_chore_id
                                ),
                                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                                tag_identifiers=(latest_chore_id, kid_id),
                            )
                        )

            # Clear the approved chore's notification (v0.5.0+ - handles dashboard approvals)
            self.hass.async_create_task(
                self.clear_notification_for_parents(
                    kid_id, const.NOTIFY_TAG_TYPE_STATUS, chore_id
                )
            )

            # Clear due-soon reminder tracking (v0.5.0+) - chore was completed
            self._clear_chore_due_reminder(chore_id, kid_id)

            # For UPON_COMPLETION chores, immediately reset to PENDING and check overdue
            # This ensures chore is ready for next completion and reflects accurate state
            if approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION:
                # Reset to PENDING with new approval period
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    self._transition_chore_state(
                        assigned_kid_id,
                        chore_id,
                        const.CHORE_STATE_PENDING,
                        reset_approval_period=True,
                    )
                const.LOGGER.debug(
                    "UPON_COMPLETION: Reset chore '%s' to PENDING immediately after approval",
                    chore_info.get(const.DATA_CHORE_NAME),
                )

                # Immediately check if chore is now overdue (due date hasn't changed)
                await self._check_overdue_chores()

            self._persist()
            self.async_set_updated_data(self._data)

            perf_duration = time.perf_counter() - perf_start
            const.LOGGER.debug(
                "PERF: approve_chore() took %.3fs for kid '%s' chore '%s' (includes %.1f points addition)",
                perf_duration,
                kid_id,
                chore_id,
                default_points,
            )

    # =========================================================================
    # QUERY HELPERS & SCHEDULING METHODS
    # =========================================================================
    def _chore_allows_multiple_claims(self, chore_id: str) -> bool:
        """Check if chore allows multiple claims per approval period.

        Returns True for:
        - AT_MIDNIGHT_MULTI
        - AT_DUE_DATE_MULTI
        - UPON_COMPLETION

        Returns False for:
        - AT_MIDNIGHT_ONCE (default)
        - AT_DUE_DATE_ONCE
        """
        chore_info: ChoreData = cast("ChoreData", self.chores_data.get(chore_id, {}))
        approval_reset_type = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        return approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        )

    # =========================================================================
    # §2 COORDINATOR PUBLIC API (7 methods)
    # =========================================================================
    # Public methods called from sensor.py, button.py
    # Part of internal Python API but external to this operations class

    def chore_has_pending_claim(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore has a pending claim (claimed but not yet approved/disapproved).

        Uses the pending_count counter which is incremented on claim and
        decremented on approve/disapprove.

        Returns:
            True if there's a pending claim (pending_claim_count > 0), False otherwise.
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if not kid_chore_data:
            return False

        pending_claim_count = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        return pending_claim_count > 0

    def _count_chores_pending_for_kid(self, kid_id: str) -> int:
        """Count total pending chores awaiting approval for a specific kid.

        Used for tag-based notification aggregation (v0.5.0+) to show
        "Sarah: 3 chores pending" instead of individual notifications.

        Args:
            kid_id: The internal ID of the kid.

        Returns:
            Number of chores with pending claims for this kid.
        """
        count = 0
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        for chore_id in chore_data:
            # Skip chores that no longer exist
            if chore_id not in self.chores_data:
                continue
            if self.chore_has_pending_claim(kid_id, chore_id):
                count += 1

        return count

    def _get_latest_chore_pending(self, kid_id: str) -> dict[str, Any] | None:
        """Get the most recently claimed pending chore for a kid.

        Used for tag-based notification aggregation (v0.5.0+) to show
        the latest chore details in aggregated notifications.

        Args:
            kid_id: The internal ID of the kid.

        Returns:
            Dict with kid_id and chore_id of latest pending chore, or None if none.
        """
        latest: dict[str, Any] | None = None
        latest_timestamp: str | None = None

        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        for chore_id, chore_entry in chore_data.items():
            # Skip chores that no longer exist
            if chore_id not in self.chores_data:
                continue
            if not self.chore_has_pending_claim(kid_id, chore_id):
                continue

            last_claimed = chore_entry.get(const.DATA_KID_CHORE_DATA_LAST_CLAIMED)
            if last_claimed:
                if latest_timestamp is None or last_claimed > latest_timestamp:
                    latest_timestamp = last_claimed
                    latest = {
                        const.DATA_KID_ID: kid_id,
                        const.DATA_CHORE_ID: chore_id,
                    }

        return latest

    def chore_is_overdue(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is in overdue state for a specific kid.

        Uses the per-kid chore state field (single source of truth).
        This replaces the legacy DATA_KID_OVERDUE_CHORES list.

        Returns:
            True if the chore is in overdue state, False otherwise.
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if not kid_chore_data:
            return False

        current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
        return current_state == const.CHORE_STATE_OVERDUE

    def get_pending_chore_approvals(self) -> list[dict[str, Any]]:
        """Compute pending chore approvals dynamically from timestamp data.

        This replaces the legacy queue-based approach with dynamic computation
        from kid_chore_data timestamps. A chore has a pending approval if:
        - last_claimed timestamp exists AND
        - last_claimed > last_approved (or no approval) AND
        - last_claimed > last_disapproved (or no disapproval)

        Returns:
            List of dicts with keys: kid_id, chore_id, timestamp
            Format matches the legacy queue structure for compatibility.
        """
        pending: list[dict[str, Any]] = []
        for kid_id, kid_info in self.kids_data.items():
            chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            for chore_id, chore_entry in chore_data.items():
                # Skip chores that no longer exist
                if chore_id not in self.chores_data:
                    continue
                if self.chore_has_pending_claim(kid_id, chore_id):
                    pending.append(
                        {
                            const.DATA_KID_ID: kid_id,
                            const.DATA_CHORE_ID: chore_id,
                            const.DATA_CHORE_TIMESTAMP: chore_entry.get(
                                const.DATA_KID_CHORE_DATA_LAST_CLAIMED, ""
                            ),
                        }
                    )
        return pending

    def chore_is_approved_in_period(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is already approved in the current approval period.

        A chore is considered approved in the current period if:
        - last_approved timestamp exists, AND EITHER:
          a. approval_period_start doesn't exist (chore was never reset, approval is valid), OR
          b. last_approved >= approval_period_start

        Returns:
            True if approved in current period, False otherwise.
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if not kid_chore_data:
            return False

        last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if not last_approved:
            return False

        period_start = self._get_approval_period_start(kid_id, chore_id)
        if not period_start:
            # No period_start means chore was never reset after being created.
            # Since last_approved exists (checked above), the approval is still valid.
            return True

        approved_dt = kh.dt_to_utc(last_approved)
        # period_start is ISO string, convert to datetime
        period_start_dt = kh.dt_to_utc(period_start)

        if approved_dt is None or period_start_dt is None:
            return False

        return approved_dt >= period_start_dt

    # -------------------------------------------------------------------------------------
    # Chore State Processing: Centralized Function
    # The most critical thing to understand when working on this function is that
    # chore_info[const.DATA_CHORE_STATE] is actually the global state of the chore. The individual chore
    # state per kid is always calculated based on whether they have any claimed, approved, or
    # overdue chores listed for them.
    #
    # Global state will only match if a single kid is assigned to the chore, or all kids
    # assigned are in the same state.
    # -------------------------------------------------------------------------------------

    def _check_chore_overdue_status(
        self,
        chore_id: str,
        chore_info: ChoreData,
        now_utc: datetime,
    ) -> None:
        """Check and apply overdue status for a chore (any completion criteria).

        Unified handler for INDEPENDENT, SHARED, and SHARED_FIRST completion criteria.
        Uses _handle_overdue_chore_state() for core overdue application logic.
        Uses _get_effective_due_date() for due date resolution.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime for comparison
        """
        # Early exit for NEVER_OVERDUE
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        if overdue_handling == const.OVERDUE_HANDLING_NEVER_OVERDUE:
            return

        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # SHARED_FIRST special handling
        claimant_kid_id: str | None = None
        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Check if chore is already completed by any kid
            any_approved = any(
                self.chore_is_approved_in_period(kid_id, chore_id)
                for kid_id in assigned_kids
            )
            # If any kid completed it, clear overdue for everyone and exit
            if any_approved:
                for kid_id in assigned_kids:
                    if self.chore_is_overdue(kid_id, chore_id):
                        self._transition_chore_state(
                            kid_id, chore_id, const.CHORE_STATE_PENDING
                        )
                return

            # Find claimant (if any) - only claimant can be overdue in SHARED_FIRST
            claimant_kid_id = next(
                (
                    kid_id
                    for kid_id in assigned_kids
                    if self.chore_has_pending_claim(kid_id, chore_id)
                ),
                None,
            )

        # Check each assigned kid
        for kid_id in assigned_kids:
            if not kid_id:
                continue

            # Skip if already claimed or approved (applies to all criteria)
            if self.chore_has_pending_claim(kid_id, chore_id):
                continue
            if self.chore_is_approved_in_period(kid_id, chore_id):
                continue

            # SHARED_FIRST: Handle special states
            if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
                current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)

                # Kids in completed_by_other state should never be overdue
                if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
                    if self.chore_is_overdue(kid_id, chore_id):
                        self._transition_chore_state(
                            kid_id, chore_id, const.CHORE_STATE_COMPLETED_BY_OTHER
                        )
                    continue

                # If there's a claimant and this isn't them, clear overdue and skip
                if claimant_kid_id and kid_id != claimant_kid_id:
                    if self.chore_is_overdue(kid_id, chore_id):
                        self._transition_chore_state(
                            kid_id, chore_id, const.CHORE_STATE_PENDING
                        )
                    continue

            # Get effective due date and apply overdue check
            due_str = self._get_chore_effective_due_date(chore_id, kid_id)
            self._handle_overdue_chore_state(
                kid_id, chore_id, due_str, now_utc, chore_info
            )

    # =========================================================================
    # §11 REMINDER OPERATIONS
    # =========================================================================
    # Notification helpers for due date reminders and overdue status.
    # Called from §7 Scheduling Logic and §10 Overdue Detection.

    # -------------------------------------------------------------------------
    # Overdue Notifications
    # -------------------------------------------------------------------------

    def _notify_overdue_chore(
        self,
        kid_id: str,
        chore_id: str,
        chore_info: dict[str, Any],
        due_date_utc: datetime,
        now_utc: datetime,
    ) -> None:
        """Send overdue notification to kid and parents if not already notified in last 24 hours."""
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))

        # Check notification timestamp
        if const.DATA_KID_OVERDUE_NOTIFICATIONS not in kid_info:
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = {}

        overdue_notifs: dict[str, str] = kid_info.get(
            const.DATA_KID_OVERDUE_NOTIFICATIONS, {}
        )
        last_notif_str = overdue_notifs.get(chore_id)
        notify = False

        if last_notif_str:
            try:
                last_dt = kh.dt_to_utc(last_notif_str)
                if (
                    last_dt is None
                    or (last_dt < due_date_utc)
                    or (
                        (now_utc - last_dt)
                        >= timedelta(hours=const.DEFAULT_NOTIFY_DELAY_REMINDER)
                    )
                ):
                    notify = True
            except (ValueError, TypeError, AttributeError) as err:
                const.LOGGER.error(
                    "ERROR: Overdue Notification - Error parsing timestamp '%s' for Chore ID '%s', Kid ID '%s': %s",
                    last_notif_str,
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_id,
                    err,
                )
                notify = True
        else:
            notify = True

        if notify:
            overdue_notifs[chore_id] = now_utc.isoformat()
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = overdue_notifs
            # Overdue notifications for KIDS include a Claim button (v0.5.0+)
            # Overdue notifications for PARENTS are informational only (no action buttons)
            # Approve/Disapprove only make sense for claimed chores awaiting approval
            from .notification_helper import build_claim_action

            # Get kid's language for date formatting
            kid_language = kid_info.get(
                const.DATA_KID_DASHBOARD_LANGUAGE, self.hass.config.language
            )
            self.hass.async_create_task(
                self._notify_kid_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE,
                    message_data={
                        "chore_name": chore_info.get(
                            const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                        ),
                        "due_date": kh.dt_format_short(
                            due_date_utc, language=kid_language
                        ),
                    },
                    actions=build_claim_action(kid_id, chore_id),
                )
            )
            # Use system language for date formatting (parent-specific formatting
            # would require restructuring the notification loop)
            # Build action buttons: Complete (approve directly), Skip (reset/reschedule), Remind
            from .notification_helper import (
                build_complete_action,
                build_remind_action,
                build_skip_action,
            )

            parent_actions = []
            parent_actions.extend(build_complete_action(kid_id, chore_id))
            parent_actions.extend(build_skip_action(kid_id, chore_id))
            parent_actions.extend(build_remind_action(kid_id, chore_id))

            self.hass.async_create_task(
                self._notify_parents_translated(
                    kid_id,
                    title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE,
                    message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE,
                    message_data={
                        "chore_name": chore_info.get(
                            const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                        ),
                        "due_date": kh.dt_format_short(
                            due_date_utc, language=self.hass.config.language
                        ),
                    },
                    actions=parent_actions,
                    tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                    tag_identifiers=(chore_id, kid_id),
                )
            )

    # =========================================================================
    # §10 OVERDUE DETECTION & HANDLING
    # =========================================================================
    # Periodic checks (coordinator refresh) to detect passed due dates.
    # Transitions chore state to OVERDUE and sends parent notifications.

    async def _check_overdue_chores(self, now: datetime | None = None):
        """Check and mark overdue chores if due date is passed.

        Branching logic based on completion criteria:
        - INDEPENDENT: Each kid can have different due dates (per-kid storage)
        - SHARED_*: All kids share same due date (chore-level storage)

        Send an overdue notification only if not sent in the last 24 hours.
        """
        # PERF: Measure overdue scan duration
        perf_start = time.perf_counter()

        now_utc = dt_util.utcnow()
        const.LOGGER.debug(
            "Overdue Chores - Starting check at %s",
            now_utc.isoformat(),
        )

        for chore_id, chore_info in self.chores_data.items():
            # Get the list of assigned kids
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

            # Check if all assigned kids have either claimed or approved the chore
            # v0.4.0+: Uses timestamp-based helpers instead of deprecated lists
            all_kids_claimed_or_approved = all(
                self.chore_has_pending_claim(kid_id, chore_id)
                or self.chore_is_approved_in_period(kid_id, chore_id)
                for kid_id in assigned_kids
            )

            # Only skip the chore if ALL assigned kids have acted on it
            if all_kids_claimed_or_approved:
                continue

            # Use unified overdue check handler (handles all completion criteria)
            self._check_chore_overdue_status(chore_id, chore_info, now_utc)

        const.LOGGER.debug("Overdue Chores - Check completed")

        # PERF: Log overdue scan duration
        perf_duration = time.perf_counter() - perf_start
        chore_count = len(self.chores_data)
        kid_count = len(self.kids_data)
        const.LOGGER.debug(
            "PERF: _check_overdue_chores() took %.3fs for %d chores × %d kids = %d operations",
            perf_duration,
            chore_count,
            kid_count,
            chore_count * kid_count,
        )

    # =========================================================================
    # §8 RECURRING CHORE OPERATIONS
    # =========================================================================
    # Reset/reschedule logic for daily/weekly/monthly recurring chores.
    # Executed during coordinator refresh cycles at scheduled times.

    async def _process_recurring_chore_resets(self, now: datetime):
        """Handle recurring resets for daily, weekly, and monthly frequencies."""

        await self._reschedule_recurring_chores(now)

        # Daily
        if now.hour == const.DEFAULT_DAILY_RESET_TIME.get(
            const.TIME_UNIT_HOUR, const.DEFAULT_HOUR
        ):
            await self._reset_chore_counts(const.FREQUENCY_DAILY, now)

        # Weekly
        if now.weekday() == const.DEFAULT_WEEKLY_RESET_DAY:
            await self._reset_chore_counts(const.FREQUENCY_WEEKLY, now)

        # Monthly
        days_in_month = monthrange(now.year, now.month)[1]
        reset_day = min(const.DEFAULT_MONTHLY_RESET_DAY, days_in_month)
        if now.day == reset_day:
            await self._reset_chore_counts(const.FREQUENCY_MONTHLY, now)

    async def _reset_chore_counts(self, frequency: str, now: datetime):
        """Reset chore counts and statuses based on the recurring frequency."""
        # Note: Points earned tracking now handled by point_stats structure
        # Legacy points_earned_* counters removed - no longer needed

        const.LOGGER.debug(
            "DEBUG: Reset Chore Counts: %s chore counts have been reset",
            frequency.capitalize(),
        )

        # If daily reset -> reset statuses
        if frequency == const.FREQUENCY_DAILY:
            await self._reset_daily_chore_statuses([frequency])
        elif frequency == const.FREQUENCY_WEEKLY:
            await self._reset_daily_chore_statuses([frequency, const.FREQUENCY_WEEKLY])

    async def _reschedule_recurring_chores(self, now: datetime):
        """For chores with the given recurring frequency, reschedule due date if they are approved and past due.

        Handles both SHARED and INDEPENDENT completion criteria:
        - SHARED: Uses chore-level due_date and state (single due date for all kids)
        - INDEPENDENT: Uses per_kid_due_dates and per-kid state (each kid has own due date)
        """

        for chore_id, chore_info in self.chores_data.items():
            # Only consider chores with a recurring frequency
            if chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) not in (
                const.FREQUENCY_DAILY,
                const.FREQUENCY_WEEKLY,
                const.FREQUENCY_BIWEEKLY,
                const.FREQUENCY_MONTHLY,
                const.FREQUENCY_CUSTOM,
            ):
                continue

            # Branch on completion criteria
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT mode: Each kid has their own due date and state
                self._reschedule_independent_recurring_chore(chore_id, chore_info, now)
            else:
                # SHARED mode: Single due date and state for all kids
                self._reschedule_shared_recurring_chore(chore_id, chore_info, now)

        self._persist()
        self.async_set_updated_data(self._data)
        const.LOGGER.debug(
            "DEBUG: Chore Rescheduling - Daily recurring chores rescheduling complete"
        )

    def _reschedule_shared_recurring_chore(
        self, chore_id: str, chore_info: ChoreData, now: datetime
    ) -> None:
        """Reschedule a SHARED recurring chore if approved and past due.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now: Current UTC datetime
        """
        # SHARED mode uses chore-level due_date
        if not chore_info.get(const.DATA_CHORE_DUE_DATE):
            return

        due_date_utc = kh.dt_to_utc(chore_info.get(const.DATA_CHORE_DUE_DATE) or "")
        if due_date_utc is None:
            const.LOGGER.debug(
                "DEBUG: Chore Rescheduling - Error parsing due date for Chore ID '%s'.",
                chore_id,
            )
            return

        # If the due date is in the past and the chore is approved or approved_in_part
        if now > due_date_utc and chore_info.get(const.DATA_CHORE_STATE) in [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_APPROVED_IN_PART,
        ]:
            # Reschedule the chore (chore-level)
            self._reschedule_chore_next_due(chore_info)
            const.LOGGER.debug(
                "DEBUG: Chore Rescheduling - Rescheduled recurring SHARED Chore ID '%s'",
                chore_info.get(const.DATA_CHORE_NAME, chore_id),
            )

    def _reschedule_independent_recurring_chore(
        self, chore_id: str, chore_info: ChoreData, now: datetime
    ) -> None:
        """Reschedule an INDEPENDENT recurring chore for each kid if approved and past due.

        For INDEPENDENT chores, each kid has their own due date and state.
        Only reschedules for kids who have completed (approved) their instance.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now: Current UTC datetime
        """
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        for kid_id in assigned_kids:
            if not kid_id:
                continue

            # Get per-kid due date (source of truth for INDEPENDENT)
            kid_due_str = per_kid_due_dates.get(kid_id)
            if not kid_due_str:
                # No due date for this kid - skip
                continue

            kid_due_utc = kh.dt_to_utc(kid_due_str)
            if kid_due_utc is None:
                const.LOGGER.debug(
                    "DEBUG: Chore Rescheduling - Error parsing per-kid due date for Chore '%s', Kid '%s'.",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_id,
                )
                continue

            # Check per-kid state from kid's chore data
            kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                chore_id, {}
            )
            kid_state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )

            # If the due date is in the past and the kid's state is approved
            if now > kid_due_utc and kid_state in [
                const.CHORE_STATE_APPROVED,
                const.CHORE_STATE_APPROVED_IN_PART,
            ]:
                # Reschedule for this kid only
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                # Also reset state to PENDING (scheduled reset starts new approval period)
                self._transition_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                )
                const.LOGGER.debug(
                    "DEBUG: Chore Rescheduling - Rescheduled recurring INDEPENDENT Chore '%s' for Kid '%s'",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

    # =========================================================================
    # §9 DAILY RESET OPERATIONS
    # =========================================================================
    # Midnight (and frequency-specific) chore status reset logic.
    # Handles SHARED/INDEPENDENT completion criteria, approval reset types.

    async def _reset_daily_chore_statuses(self, target_freqs: list[str]):
        """Reset chore statuses and clear approved/claimed chores for chores with these freq.

        Handles both SHARED and INDEPENDENT completion criteria:
        - SHARED: Uses chore-level due_date to determine if reset needed
        - INDEPENDENT: Uses per_kid_due_dates for each kid's due date check

        For non-recurring chores (FREQUENCY_NONE), only processes if approval_reset_type
        is AT_MIDNIGHT_* (skips UPON_COMPLETION and AT_DUE_DATE_*).
        """

        now_utc = dt_util.utcnow()
        for chore_id, chore_info in self.chores_data.items():
            frequency = chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
            )

            # For non-recurring chores, only process if approval_reset_type is AT_MIDNIGHT_*
            if frequency == const.FREQUENCY_NONE:
                approval_reset_type = chore_info.get(
                    const.DATA_CHORE_APPROVAL_RESET_TYPE,
                    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                )
                # Skip if reset type is not midnight-based
                if approval_reset_type not in (
                    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                    const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
                ):
                    continue  # Skip this chore - doesn't reset at midnight
            elif frequency not in target_freqs:
                continue  # Skip recurring chores that don't match target frequency

            # Branch on completion criteria
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT mode: Check each kid's due date separately
                self._reset_independent_chore_status(chore_id, chore_info, now_utc)
            else:
                # SHARED mode: Use chore-level due_date
                self._reset_shared_chore_status(chore_id, chore_info, now_utc)

        # Queue filter removed - pending approvals computed from timestamps
        # The reset operations above clear timestamps, so computed list auto-updates
        self._pending_chore_changed = True

        self._persist()

    def _reset_shared_chore_status(
        self, chore_id: str, chore_info: ChoreData, now_utc: datetime
    ) -> None:
        """Reset a SHARED chore status if due date has passed.

        Phase 5 - Approval Reset Pending Claim Action:
        - HOLD: Keep pending claim, skip reset for kids with pending claims
        - CLEAR: Clear pending claim, reset to fresh state (default/current behavior)
        - AUTO_APPROVE: Auto-approve pending claim, then reset to fresh state

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime
        """
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        if due_date_str:
            due_date_utc = kh.dt_to_utc(due_date_str)
            if due_date_utc is None:
                const.LOGGER.debug(
                    "Chore Reset - Failed to parse due date '%s' for Chore ID '%s'",
                    due_date_str,
                    chore_id,
                )
                return
            # If the due date has not yet been reached, skip resetting this chore.
            if now_utc < due_date_utc:
                return

        # Check if AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET should clear overdue status
        # This only applies with AT_MIDNIGHT_* reset types (validated in flow_helpers)
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        should_clear_chore_overdue_state = (
            overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
        )

        # Determine which states should be reset
        # Default: Reset anything that's not PENDING or OVERDUE
        # With AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET: Also reset OVERDUE to PENDING
        states_to_skip = [const.CHORE_STATE_PENDING]
        if not should_clear_chore_overdue_state:
            states_to_skip.append(const.CHORE_STATE_OVERDUE)

        # If no due date or the due date has passed, then reset the chore state
        if chore_info[const.DATA_CHORE_STATE] not in states_to_skip:
            previous_state = chore_info[const.DATA_CHORE_STATE]
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if kid_id:
                    # Get kid_chore_data for pending claim handling
                    kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
                    kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                        chore_id, {}
                    )

                    # Handle pending claims (HOLD, AUTO_APPROVE, or CLEAR)
                    if self._handle_pending_chore_claim_at_reset(
                        kid_id, chore_id, chore_info, kid_chore_data
                    ):
                        continue  # HOLD action - skip reset for this kid

                    self._transition_chore_state(
                        kid_id,
                        chore_id,
                        const.CHORE_STATE_PENDING,
                        reset_approval_period=True,
                    )
            const.LOGGER.debug(
                "DEBUG: Chore Reset - Resetting SHARED Chore '%s' from '%s' to '%s'",
                chore_id,
                previous_state,
                const.CHORE_STATE_PENDING,
            )

    def _reset_independent_chore_status(
        self, chore_id: str, chore_info: ChoreData, now_utc: datetime
    ) -> None:
        """Reset an INDEPENDENT chore status for each kid if their due date has passed.

        For INDEPENDENT chores, each kid has their own due date.
        Only reset for kids whose due date has passed.

        Phase 5 - Approval Reset Pending Claim Action:
        - HOLD: Keep pending claim, skip reset for kids with pending claims
        - CLEAR: Clear pending claim, reset to fresh state (default/current behavior)
        - AUTO_APPROVE: Auto-approve pending claim, then reset to fresh state

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime
        """
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Check if AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET should clear overdue status
        # This only applies with AT_MIDNIGHT_* reset types (validated in flow_helpers)
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        should_clear_chore_overdue_state = (
            overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
        )

        # Determine which states should be skipped
        # Default: Skip PENDING or OVERDUE
        # With AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET: Only skip PENDING (reset OVERDUE to PENDING)
        states_to_skip = [const.CHORE_STATE_PENDING]
        if not should_clear_chore_overdue_state:
            states_to_skip.append(const.CHORE_STATE_OVERDUE)

        for kid_id in assigned_kids:
            if not kid_id:
                continue

            # Get per-kid due date (source of truth for INDEPENDENT)
            kid_due_str = per_kid_due_dates.get(kid_id)
            if kid_due_str:
                kid_due_utc = kh.dt_to_utc(kid_due_str)
                if kid_due_utc is None:
                    const.LOGGER.debug(
                        "Chore Reset - Failed to parse per-kid due date '%s' for Chore '%s', Kid '%s'",
                        kid_due_str,
                        chore_id,
                        kid_id,
                    )
                    continue
                # If the due date has not yet been reached, skip resetting for this kid.
                if now_utc < kid_due_utc:
                    continue

            # Check per-kid state from kid's chore data
            kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                chore_id, {}
            )
            kid_state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )

            # Check if state should be reset based on overdue handling
            if kid_state not in states_to_skip:
                # Handle pending claims (HOLD, AUTO_APPROVE, or CLEAR)
                if self._handle_pending_chore_claim_at_reset(
                    kid_id, chore_id, chore_info, kid_chore_data
                ):
                    continue  # HOLD action - skip reset for this kid

                self._transition_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                )
                const.LOGGER.debug(
                    "Chore Reset - Resetting INDEPENDENT Chore '%s' for Kid '%s' from '%s' to '%s'",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                    kid_state,
                    const.CHORE_STATE_PENDING,
                )

    def _reschedule_chore_next_due(self, chore_info: ChoreData) -> None:
        """Reschedule chore's next due date (chore-level). Uses consolidation helper."""
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        if not due_date_str:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Skipping (no due date for %s)",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Parse current due date
        original_due_utc = kh.dt_to_utc(due_date_str)
        if not original_due_utc:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Unable to parse due date for %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # CFE-2026-001: Extract completion timestamp for CUSTOM_FROM_COMPLETE
        # For SHARED chores, use chore-level last_completed
        completion_utc: datetime | None = None
        last_completed_str = chore_info.get(const.DATA_CHORE_LAST_COMPLETED)
        if last_completed_str:
            completion_utc = kh.dt_to_utc(last_completed_str)

        # Use consolidation helper for calculation
        next_due_utc = calculate_next_due_date_from_chore_info(
            original_due_utc, chore_info, completion_timestamp=completion_utc
        )
        if not next_due_utc:
            const.LOGGER.warning(
                "Chore Due Date - Reschedule: Failed to calculate next due date for %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Update chore-level due date
        chore_info[const.DATA_CHORE_DUE_DATE] = next_due_utc.isoformat()
        chore_id = chore_info.get(const.DATA_CHORE_INTERNAL_ID)

        if not chore_id:
            const.LOGGER.error(
                "Chore Due Date - Reschedule: Missing chore_id for chore: %s",
                chore_info.get(const.DATA_CHORE_NAME, "Unknown"),
            )
            return

        # Only reset to PENDING for UPON_COMPLETION type
        # Other reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*) stay APPROVED until scheduled reset
        # This prevents the bug where approval_period_start > last_approved caused
        # chore_is_approved_in_period() to return False immediately after approval
        # EXCEPTION: immediate_on_late option also resets to PENDING when triggered
        approval_reset = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )
        # Reset to PENDING for UPON_COMPLETION or immediate-on-late option
        should_reset_state = (
            approval_reset == const.APPROVAL_RESET_UPON_COMPLETION
            or overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
        )
        if should_reset_state:
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if kid_id:
                    self._transition_chore_state(
                        kid_id,
                        chore_id,
                        const.CHORE_STATE_PENDING,
                        reset_approval_period=True,
                    )

        const.LOGGER.info(
            "Chore Due Date - Rescheduled (SHARED): %s, from %s to %s",
            chore_info.get(const.DATA_CHORE_NAME),
            dt_util.as_local(original_due_utc).isoformat(),
            dt_util.as_local(next_due_utc).isoformat(),
        )

    def _reschedule_chore_next_due_date_for_kid(
        self, chore_info: ChoreData, chore_id: str, kid_id: str
    ) -> None:
        """Reschedule per-kid due date (INDEPENDENT mode).

        Updates DATA_CHORE_PER_KID_DUE_DATES[kid_id]. Calls pure helper.
        Used for INDEPENDENT chores (each kid has own due date).

        Note: After migration, this method reads ONLY from DATA_CHORE_PER_KID_DUE_DATES.
        The migration populates per_kid_due_dates from the chore template (including None).
        """
        # Get kid info for logging
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))

        # Get per-kid current due date from canonical source (per_kid_due_dates ONLY)
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        current_due_str = per_kid_due_dates.get(kid_id)

        # Parse current due date
        # Per wiki Use Case 2: Chores with no due date but with recurrence should stay None
        # They reset by recurrence pattern only, never become overdue
        if not current_due_str:
            # No due date set - preserve None for recurring chores without explicit due dates
            const.LOGGER.debug(
                "Chore Due Date - No due date for chore %s, kid %s; preserving None (recurrence only)",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            # Clear per-kid override if it existed
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # Parse current due date that exists
        try:
            original_due_utc = kh.dt_to_utc(current_due_str)
        except (ValueError, TypeError, AttributeError):
            const.LOGGER.debug(
                "Chore Due Date - Reschedule (per-kid): Unable to parse due date for chore %s, kid %s; clearing due date",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            # Clear invalid due date instead of calculating one
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # CFE-2026-001: Extract per-kid completion timestamp for CUSTOM_FROM_COMPLETE
        # For INDEPENDENT chores, use per-kid last_approved from kid_chore_data
        completion_utc: datetime | None = None
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        last_approved_str = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if last_approved_str:
            completion_utc = kh.dt_to_utc(last_approved_str)

        # PKAD-2026-001: For INDEPENDENT chores, inject per-kid applicable_days
        # and daily_multi_times into a copy of chore_info before calculation.
        # This allows the helper to use per-kid values instead of chore-level.
        chore_info_for_calc = chore_info.copy()

        per_kid_applicable_days = chore_info.get(
            const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {}
        )
        if kid_id in per_kid_applicable_days:
            chore_info_for_calc[const.DATA_CHORE_APPLICABLE_DAYS] = (
                per_kid_applicable_days[kid_id]
            )

        per_kid_times = chore_info.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
        if kid_id in per_kid_times:
            chore_info_for_calc[const.DATA_CHORE_DAILY_MULTI_TIMES] = per_kid_times[
                kid_id
            ]

        # Use consolidation helper with per-kid overrides
        next_due_utc = calculate_next_due_date_from_chore_info(
            original_due_utc, chore_info_for_calc, completion_timestamp=completion_utc
        )
        if not next_due_utc:
            const.LOGGER.warning(
                "Chore Due Date - Reschedule (per-kid): Failed to calculate next due date for %s, kid %s",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            return

        # Update per-kid storage (single source of truth)
        per_kid_due_dates[kid_id] = next_due_utc.isoformat()
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

        # Only reset to PENDING for UPON_COMPLETION type
        # Other reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*) stay APPROVED until scheduled reset
        # This prevents the bug where approval_period_start > last_approved caused
        # chore_is_approved_in_period() to return False immediately after approval
        # EXCEPTION: immediate_on_late option also resets to PENDING when triggered
        approval_reset = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )
        # Reset to PENDING for UPON_COMPLETION or immediate-on-late option
        should_reset_state = (
            approval_reset == const.APPROVAL_RESET_UPON_COMPLETION
            or overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
        )
        if should_reset_state:
            self._transition_chore_state(
                kid_id, chore_id, const.CHORE_STATE_PENDING, reset_approval_period=True
            )

        const.LOGGER.info(
            "Chore Due Date - Rescheduled (INDEPENDENT): chore %s, kid %s, from %s to %s",
            chore_info.get(const.DATA_CHORE_NAME),
            kid_info.get(const.DATA_KID_NAME),
            dt_util.as_local(original_due_utc).isoformat()
            if original_due_utc
            else "None",
            dt_util.as_local(next_due_utc).isoformat() if next_due_utc else "None",
        )

    def _is_chore_approval_after_reset(
        self, chore_info: ChoreData, kid_id: str
    ) -> bool:
        """Check if approval is happening after the reset boundary has passed.

        For AT_MIDNIGHT types: Due date must be before last midnight
        For AT_DUE_DATE types: Current time must be past the due date

        Returns True if "late", False otherwise.
        """
        approval_reset_type = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
        )

        now_utc = dt_util.utcnow()

        # AT_MIDNIGHT types: Check if due date was before last midnight
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        ):
            # Get due date (per-kid for INDEPENDENT, chore-level for SHARED)
            completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)

            if not due_date_str:
                return False

            due_date = kh.dt_to_utc(due_date_str)
            if not due_date:
                return False

            # Calculate last midnight in local time, convert to UTC
            local_now = dt_util.as_local(now_utc)
            last_midnight_local = local_now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            last_midnight_utc = dt_util.as_utc(last_midnight_local)

            return due_date < last_midnight_utc

        # AT_DUE_DATE types: Check if past the due date
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
        ):
            completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)

            if not due_date_str:
                return False

            due_date = kh.dt_to_utc(due_date_str)
            if not due_date:
                return False

            return now_utc > due_date

        return False

    # Set Chore Due Date

    # -------------------------------------------------------------------------
    # CHORE DATA HELPERS
    # -------------------------------------------------------------------------

    def _set_chore_claimed_completed_by(
        self, chore_id: str, kid_id: str, field_name: str, kid_name: str
    ) -> None:
        """Set claimed_by or completed_by field for a chore based on completion criteria.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid who claimed/completed the chore
            field_name: Either DATA_CHORE_CLAIMED_BY or DATA_CHORE_COMPLETED_BY
            kid_name: Display name of the kid
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            return

        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Store kid's own name in their kid_chore_data
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                return
            kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
            if chore_id not in kid_chores_data:
                self._update_kid_chore_data(kid_id, chore_id, 0.0)
            kid_chores_data[chore_id][field_name] = kid_name
            const.LOGGER.debug(
                "INDEPENDENT: Set %s='%s' for kid '%s' on chore '%s'",
                field_name,
                kid_name,
                kid_name,
                chore_info.get(const.DATA_CHORE_NAME),
            )

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Store in other kids' data (not the claiming/completing kid)
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if other_kid_id == kid_id:
                    continue  # Skip the claiming/completing kid
                other_kid_info: KidData = cast(
                    "KidData", self.kids_data.get(other_kid_id, {})
                )
                self._update_kid_chore_data(other_kid_id, chore_id, 0.0)
                chore_data = other_kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
                chore_entry = chore_data[chore_id]
                chore_entry[field_name] = kid_name
                const.LOGGER.debug(
                    "SHARED_FIRST: Set %s='%s' in kid '%s' data for chore '%s'",
                    field_name,
                    kid_name,
                    other_kid_info.get(const.DATA_KID_NAME),
                    chore_info.get(const.DATA_CHORE_NAME),
                )

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            # SHARED_ALL: Append to list in all kids' data
            for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                assigned_kid_info: KidData = cast(
                    "KidData", self.kids_data.get(assigned_kid_id, {})
                )
                assigned_kid_chore_data = assigned_kid_info.setdefault(
                    const.DATA_KID_CHORE_DATA, {}
                )
                if chore_id not in assigned_kid_chore_data:
                    self._update_kid_chore_data(assigned_kid_id, chore_id, 0.0)
                chore_entry = assigned_kid_chore_data[chore_id]

                # Initialize as list if not present or if it's not a list
                if field_name not in chore_entry or not isinstance(
                    chore_entry[field_name], list
                ):
                    chore_entry[field_name] = []

                # Append kid's name if not already in list
                if kid_name not in chore_entry[field_name]:
                    chore_entry[field_name].append(kid_name)

            const.LOGGER.debug(
                "SHARED_ALL: Added '%s' to %s list for chore '%s'",
                kid_name,
                field_name,
                chore_info.get(const.DATA_CHORE_NAME),
            )

    def _clear_chore_claimed_completed_by(
        self, chore_id: str, kid_ids: list[str] | None = None
    ) -> None:
        """Clear claimed_by and completed_by fields for specified kids.

        Args:
            chore_id: The chore's internal ID
            kid_ids: List of kid IDs to clear fields for. If None, clears for all assigned kids.
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            return

        # If no specific kids provided, clear for all assigned kids
        kids_to_clear = (
            kid_ids
            if kid_ids is not None
            else chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        )

        for kid_id in kids_to_clear:
            kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
            chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            if chore_id in chore_data:
                chore_data[chore_id].pop(const.DATA_CHORE_CLAIMED_BY, None)
                chore_data[chore_id].pop(const.DATA_CHORE_COMPLETED_BY, None)

    # =========================================================================
    # §6 QUERY & LOOKUP (5 methods)
    # =========================================================================
    # Read-only state and data queries

    def _get_kid_chore_data(
        self, kid_id: str, chore_id: str
    ) -> KidChoreDataEntry | dict[str, Any]:
        """Get the chore data dict for a specific kid+chore combination.

        Returns an empty dict if the kid or chore data doesn't exist.
        """
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        return kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})

    def _get_chore_effective_due_date(
        self,
        chore_id: str,
        kid_id: str | None = None,
    ) -> str | None:
        """Get the effective due date for a kid+chore combination.

        For INDEPENDENT chores: Returns per-kid due date from per_kid_due_dates
        For SHARED/SHARED_FIRST: Returns chore-level due date

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID (required for INDEPENDENT,
                    ignored for SHARED)

        Returns:
            ISO datetime string or None if no due date set
        """
        chore_info: ChoreData = cast("ChoreData", self.chores_data.get(chore_id, {}))
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and kid_id:
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            return per_kid_due_dates.get(kid_id)

        return chore_info.get(const.DATA_CHORE_DUE_DATE)

    @property
    def pending_chore_approvals(self) -> list[dict[str, Any]]:
        """Return the list of pending chore approvals (computed from timestamps).

        Uses timestamp-based tracking instead of legacy queue. A chore is pending
        if it has been claimed but not yet approved or disapproved in the current
        approval period.
        """
        return self.get_pending_chore_approvals()

    @property
    def pending_chore_changed(self) -> bool:
        """Return whether pending chore approvals have changed since last reset."""
        return self._pending_chore_changed

    # -------------------------------------------------------------------------
    # Overdue Logic & Due Date Reminders
    # -------------------------------------------------------------------------

    def _handle_overdue_chore_state(
        self,
        kid_id: str,
        chore_id: str,
        due_date_iso: str | None,
        now_utc: datetime,
        chore_info: ChoreData,
    ) -> bool:
        """Check if chore is past due and apply overdue state if so.

        Consolidates common overdue logic shared across all completion criteria:
        - Phase 5 NEVER_OVERDUE handling
        - Due date parsing with error handling
        - "Not yet due" early exit with overdue clearing
        - Overdue state application via _transition_chore_state
        - Notification via _notify_overdue_chore

        Args:
            kid_id: The kid to check/mark overdue
            chore_id: The chore to check
            due_date_iso: ISO format due date string (or None if no due date)
            now_utc: Current UTC datetime for comparison
            chore_info: Chore info dict for notification context

        Returns:
            True if overdue was applied, False if not (not yet due, no due date,
            NEVER_OVERDUE, or parse error)
        """
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))

        # Phase 5: Check overdue handling type
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        if overdue_handling == const.OVERDUE_HANDLING_NEVER_OVERDUE:
            return False

        # No due date means no overdue possible - clear if previously set
        if not due_date_iso:
            if chore_id in kid_info.get(const.DATA_KID_OVERDUE_CHORES, []):
                self._transition_chore_state(
                    kid_id, chore_id, const.CHORE_STATE_PENDING
                )
            return False

        # Parse due date
        try:
            due_date_utc = kh.dt_to_utc(due_date_iso)
        except (ValueError, TypeError, AttributeError) as err:
            const.LOGGER.error(
                "ERROR: Overdue Check - Error parsing due date '%s' for Chore '%s', Kid '%s': %s",
                due_date_iso,
                chore_info.get(const.DATA_CHORE_NAME, chore_id),
                kid_id,
                err,
            )
            return False

        if not due_date_utc:
            return False

        # Not yet overdue - clear any existing overdue status
        if now_utc < due_date_utc:
            if chore_id in kid_info.get(const.DATA_KID_OVERDUE_CHORES, []):
                self._transition_chore_state(
                    kid_id, chore_id, const.CHORE_STATE_PENDING
                )
            return False

        # Past due date - mark as overdue and notify
        self._transition_chore_state(kid_id, chore_id, const.CHORE_STATE_OVERDUE)
        self._notify_overdue_chore(
            kid_id, chore_id, dict(chore_info), due_date_utc, now_utc
        )
        return True

    # =========================================================================
    # §7 SCHEDULING LOGIC
    # =========================================================================
    # Due date reminder notification processing (30-min advance window).
    # Called from coordinator refresh cycle to send timely reminders.

    async def _check_chore_due_reminders(self) -> None:
        """Check for chores due soon and send reminder notifications to kids (v0.5.0+).

        Hooks into coordinator refresh cycle (typically every 5 min) to check for
        chores that are due within the next 30 minutes and haven't had reminders sent.

        Timing behavior:
        - Reminder window: 30 minutes before due date
        - Check frequency: Every coordinator refresh (~5 min)
        - Practical timing: Kids receive notification 25-35 min before due

        Tracking:
        - Uses transient `_due_soon_reminders_sent` set (resets on HA restart)
        - Key format: "{chore_id}:{kid_id}"
        - Acceptable behavior: One duplicate reminder per chore after HA restart
        """
        now_utc = dt_util.utcnow()
        reminder_window = timedelta(minutes=30)
        reminders_sent = 0

        const.LOGGER.debug(
            "Due date reminders - Starting check at %s",
            now_utc.isoformat(),
        )

        for chore_id, chore_info in self.chores_data.items():
            # Get assigned kids for this chore
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if not assigned_kids:
                continue

            # Check completion criteria to determine due date handling
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )

            # Skip if chore has reminders disabled (per-chore control v0.5.0+)
            if not chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_REMINDER, const.DEFAULT_NOTIFY_ON_REMINDER
            ):
                continue

            for kid_id in assigned_kids:
                # Build unique key for this chore+kid combination
                reminder_key = f"{chore_id}:{kid_id}"

                # Skip if already sent this reminder (transient tracking)
                if reminder_key in self._due_soon_reminders_sent:
                    continue

                # Skip if kid already claimed or completed this chore
                if self.chore_has_pending_claim(kid_id, chore_id):
                    continue
                if self.chore_is_approved_in_period(kid_id, chore_id):
                    continue

                # Get due date based on completion criteria
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # Independent chores: per-kid due date in per_kid_due_dates
                    per_kid_due_dates = chore_info.get(
                        const.DATA_CHORE_PER_KID_DUE_DATES, {}
                    )
                    due_date_str = per_kid_due_dates.get(kid_id, const.SENTINEL_EMPTY)
                else:
                    # Shared chores: single due date on chore level
                    due_date_str = chore_info.get(
                        const.DATA_CHORE_DUE_DATE, const.SENTINEL_EMPTY
                    )

                if not due_date_str:
                    continue

                # Parse due date and check if within reminder window
                due_dt = kh.dt_to_utc(due_date_str)
                if due_dt is None:
                    continue

                time_until_due = due_dt - now_utc

                # Check: due within 30 min AND not past due yet
                if timedelta(0) < time_until_due <= reminder_window:
                    # Send due-soon reminder to kid with claim button (v0.5.0+)
                    from .notification_helper import build_claim_action

                    minutes_remaining = int(time_until_due.total_seconds() / 60)
                    chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown Chore")
                    points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0)

                    await self._notify_kid_translated(
                        kid_id,
                        const.TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON,
                        const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_SOON,
                        message_data={
                            "chore_name": chore_name,
                            "minutes": minutes_remaining,
                            "points": points,
                        },
                        actions=build_claim_action(kid_id, chore_id),
                    )

                    # Mark as sent (transient - resets on HA restart)
                    self._due_soon_reminders_sent.add(reminder_key)
                    reminders_sent += 1

                    const.LOGGER.debug(
                        "Sent due-soon reminder for chore '%s' to kid '%s' (%d min remaining)",
                        chore_name,
                        kid_id,
                        minutes_remaining,
                    )

        if reminders_sent > 0:
            const.LOGGER.debug(
                "Due date reminders - Sent %d reminder(s)",
                reminders_sent,
            )

    # -------------------------------------------------------------------------
    # Chore Management & Reset Operations
    # -------------------------------------------------------------------------

    def set_chore_due_date(
        self,
        chore_id: str,
        due_date: datetime | None,
        kid_id: str | None = None,
    ) -> None:
        """Set the due date of a chore.

        Args:
            chore_id: Chore to update
            due_date: New due date (or None to clear)
            kid_id: If provided for INDEPENDENT chores, updates only this kid's due date.
                   For SHARED chores, this parameter is ignored.

        For SHARED chores: Updates the single chore-level due date.
        For INDEPENDENT chores:
            - Does NOT set chore-level due_date (respects post-migration structure)
            - If kid_id provided: Updates only that kid's due date
            - If kid_id None: Updates all per-kid due dates
        """
        # Retrieve the chore data; raise error if not found.
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if chore_info is None:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        # Convert the due_date to an ISO-formatted string if provided; otherwise use None.
        # IMPORTANT: Ensure UTC timezone to maintain consistency in storage
        # Bug fix: Previously stored local timezone which caused display issues
        new_due_date_iso = dt_util.as_utc(due_date).isoformat() if due_date else None

        # Get completion criteria to determine update strategy
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # For SHARED and SHARED_FIRST chores: Update chore-level due date (single source of truth)
        # For INDEPENDENT chores: Do NOT set chore-level due date (respects post-migration structure)
        if criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ):
            try:
                chore_info[const.DATA_CHORE_DUE_DATE] = new_due_date_iso
            except KeyError as err:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MISSING_FIELD,
                    translation_placeholders={
                        "field": "due_date",
                        "entity": f"chore '{chore_id}'",
                    },
                ) from err

        # For INDEPENDENT chores: Update per-kid due dates (single source of truth)
        elif criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            if kid_id:
                # Update only the specified kid's due date
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                # Update per-kid due dates dict
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                per_kid_due_dates[kid_id] = new_due_date_iso
                if kid_id in self.kids_data:
                    kid_info = self.kids_data[kid_id]
                    const.LOGGER.debug(
                        "Set due date for INDEPENDENT chore %s, kid %s only: %s",
                        chore_info.get(const.DATA_CHORE_NAME),
                        kid_info.get(const.DATA_KID_NAME),
                        new_due_date_iso,
                    )
            else:
                # Update all assigned kids' due dates
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    per_kid_due_dates[assigned_kid_id] = new_due_date_iso
                const.LOGGER.debug(
                    "Set due date for INDEPENDENT chore %s, all kids: %s",
                    chore_info.get(const.DATA_CHORE_NAME),
                    new_due_date_iso,
                )

        # If the due date is cleared (None), then remove any recurring frequency
        # and custom interval settings unless the frequency is none, daily, or weekly.
        if new_due_date_iso is None:
            # const.FREQUENCY_DAILY, const.FREQUENCY_WEEKLY, and const.FREQUENCY_NONE are all OK without a due_date
            current_frequency = chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY)
            if chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) not in (
                const.FREQUENCY_NONE,
                const.FREQUENCY_DAILY,
                const.FREQUENCY_WEEKLY,
            ):
                const.LOGGER.debug(
                    "DEBUG: Chore Due Date - Removing frequency for Chore ID '%s' - Current frequency '%s' does not work with a due date of None",
                    chore_id,
                    current_frequency,
                )
                chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_NONE
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL, None)
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, None)

        # Reset the chore state to Pending and clear pending_count for all kids
        for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            if kid_id:
                self._transition_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                )
                # Clear pending_count when due date changes (v0.4.0+ counter-based tracking)
                kid_info_cast: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
                kid_chore_data = kid_info_cast.get(const.DATA_KID_CHORE_DATA, {}).get(
                    chore_id, {}
                )
                if kid_chore_data:
                    kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

        const.LOGGER.info(
            "INFO: Chore Due Date - Due date set for Chore ID '%s'",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
        )

        self._persist()
        self.async_set_updated_data(self._data)

    # Skip Chore Due Date

    def skip_chore_due_date(self, chore_id: str, kid_id: str | None = None) -> None:
        """Skip the current due date of a recurring chore and reschedule it.

        When a due date is skipped, the chore state is reset to PENDING for all affected kids,
        since the new due date creates a new completion period.

        Args:
            chore_id: Chore to skip
            kid_id: If provided for INDEPENDENT chores, skips only this kid's due date.
                   For SHARED chores, this parameter is ignored.

        For SHARED chores: Reschedules the single chore-level due date and resets state to PENDING for all kids.
        For INDEPENDENT chores:
            - If kid_id provided: Reschedules only that kid's due date and resets that kid's state to PENDING
            - If kid_id None: Reschedules template and all per-kid due dates, resets all kids' states to PENDING
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        if (
            chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE)
            == const.FREQUENCY_NONE
        ):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INVALID_FREQUENCY,
                translation_placeholders={
                    "frequency": "none",
                },
            )

        # Get completion criteria to determine due date validation strategy
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # Check if chore has due dates based on completion criteria
        if criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ):
            # SHARED and SHARED_FIRST chores use chore-level due date
            if not chore_info.get(const.DATA_CHORE_DUE_DATE):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MISSING_FIELD,
                    translation_placeholders={
                        "field": "due_date",
                        "entity": f"chore '{chore_info.get(const.DATA_CHORE_NAME, chore_id)}'",
                    },
                )
        else:
            # INDEPENDENT chores use per-kid due dates
            # Check if at least one assigned kid has a due date
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})

            has_any_due_date = False
            for assigned_kid_id in assigned_kids:
                if per_kid_due_dates.get(assigned_kid_id):
                    has_any_due_date = True
                    break

            if not has_any_due_date:
                # No due dates to skip - return early (no-op)
                const.LOGGER.debug(
                    "Skip request ignored: No kids have due dates for chore %s",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                )
                return

        # Apply skip logic based on completion criteria
        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT chore: skip per-kid due dates
            if kid_id:
                # Skip only the specified kid's due date
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                # Check if this specific kid has a due date to skip
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                kid_due_date = per_kid_due_dates.get(kid_id)
                if not kid_due_date:
                    # No due date for this kid - nothing to skip
                    const.LOGGER.debug(
                        "Skip request ignored: Kid %s has no due date for chore %s",
                        cast("KidData", self.kids_data.get(kid_id, {})).get(
                            const.DATA_KID_NAME
                        )
                        or kid_id,
                        chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    )
                    return
                # Reschedule and reset chore state for this kid
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                # Reset chore state to PENDING for this kid
                self._transition_chore_state(
                    kid_id, chore_id, const.CHORE_STATE_PENDING
                )
                const.LOGGER.info(
                    "Skipped due date for INDEPENDENT chore %s, kid %s - reset to PENDING",
                    chore_info.get(const.DATA_CHORE_NAME),
                    self.kids_data[kid_id].get(const.DATA_KID_NAME),
                )
            else:
                # Skip template and all assigned kids' due dates
                self._reschedule_chore_next_due(chore_info)
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    if assigned_kid_id and assigned_kid_id in self.kids_data:
                        self._reschedule_chore_next_due_date_for_kid(
                            chore_info, chore_id, assigned_kid_id
                        )
                        # Reset chore state to PENDING for each kid
                        self._transition_chore_state(
                            assigned_kid_id, chore_id, const.CHORE_STATE_PENDING
                        )
                const.LOGGER.info(
                    "Skipped due date for INDEPENDENT chore %s, all kids - reset to PENDING",
                    chore_info.get(const.DATA_CHORE_NAME),
                )
        else:
            # SHARED chore: skip chore-level due date and reset state for all kids
            self._reschedule_chore_next_due(chore_info)
            # Reset chore state to PENDING for all assigned kids
            for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if assigned_kid_id and assigned_kid_id in self.kids_data:
                    self._transition_chore_state(
                        assigned_kid_id, chore_id, const.CHORE_STATE_PENDING
                    )
            const.LOGGER.info(
                "Skipped due date for SHARED chore %s - reset to PENDING for all kids",
                chore_info.get(const.DATA_CHORE_NAME),
            )

        self._persist()
        self.async_set_updated_data(self._data)

    # Reset All Chores

    def reset_all_chores(self) -> None:
        """Reset all chores to pending state, clearing claims/approvals.

        This is a manual reset that:
        - Sets all chore states to PENDING
        - Resets approval_period_start for SHARED chores to now
        - Resets all kid chore tracking (pending_claim_count, state, approval_period_start)
        - Clears overdue notification tracking

        Note: last_claimed and last_approved are intentionally preserved for historical tracking.
        """
        now_utc_iso = datetime.now(dt_util.UTC).isoformat()

        # Loop over all chores, reset them to pending
        for chore_info in self.chores_data.values():
            chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING
            # Reset SHARED chore approval_period_start to now
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_utc_iso

        # Clear all chore tracking timestamps for each kid (v0.5.0+ timestamp-based)
        for kid_info in self.kids_data.values():
            # Clear timestamp-based tracking data
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            for chore_tracking in kid_chore_data.values():
                # NOTE: last_claimed is intentionally NEVER removed - historical tracking
                # NOTE: last_approved is intentionally NEVER removed - historical tracking
                # Reset pending_claim_count to 0 (v0.5.0+ counter-based tracking)
                chore_tracking[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0
                # Set approval_period_start to NOW to start fresh approval period
                # This ensures old last_approved timestamps are invalidated
                chore_tracking[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    now_utc_iso
                )
                # Reset state to PENDING (single source of truth for state)
                chore_tracking[const.DATA_KID_CHORE_DATA_STATE] = (
                    const.CHORE_STATE_PENDING
                )
            # Clear overdue notification tracking
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = {}

        self._persist()
        self.async_set_updated_data(self._data)
        const.LOGGER.info(
            "Manually reset all chores to pending, reset approval periods to now"
        )

    # Reset Overdue Chores

    def reset_overdue_chores(
        self, chore_id: str | None = None, kid_id: str | None = None
    ) -> None:
        """Reset overdue chore(s) to Pending state and reschedule.

        Branching logic:
        - INDEPENDENT chores: Reschedule per-kid due dates individually
        - SHARED chores: Reschedule chore-level due date (affects all kids)
        """

        if chore_id:
            # Specific chore reset (with or without kid_id)
            chore_info: ChoreData | None = self.chores_data.get(chore_id)
            if not chore_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_CHORE,
                        "name": chore_id,
                    },
                )

            # Get completion criteria to determine reset strategy
            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and kid_id:
                # INDEPENDENT + kid specified: Reset state to PENDING and reschedule per-kid due date
                const.LOGGER.info(
                    "Reset Overdue Chores: Rescheduling per-kid (INDEPENDENT) chore: %s, kid: %s",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_id,
                )
                self._transition_chore_state(
                    kid_id, chore_id, const.CHORE_STATE_PENDING
                )
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
            else:
                # INDEPENDENT without kid_id OR SHARED: Reset all kids via chore-level
                const.LOGGER.info(
                    "Reset Overdue Chores: Rescheduling chore (SHARED or all kids): %s",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                )
                self._reschedule_chore_next_due(chore_info)

        elif kid_id:
            # Kid-only reset: reset all overdue chores for the specified kid
            kid_info: KidData | None = self.kids_data.get(kid_id)
            if not kid_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            for chore_id, chore_info in self.chores_data.items():
                if kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if self.chore_is_overdue(kid_id, chore_id):
                        # Get completion criteria to determine reset strategy
                        criteria = chore_info.get(
                            const.DATA_CHORE_COMPLETION_CRITERIA,
                            const.COMPLETION_CRITERIA_SHARED,
                        )

                        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                            # INDEPENDENT: Reset state to PENDING and reschedule per-kid due date
                            const.LOGGER.info(
                                "Reset Overdue Chores: Rescheduling per-kid (INDEPENDENT) chore: %s, kid: %s",
                                chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                kid_id,
                            )
                            self._transition_chore_state(
                                kid_id, chore_id, const.CHORE_STATE_PENDING
                            )
                            self._reschedule_chore_next_due_date_for_kid(
                                chore_info, chore_id, kid_id
                            )
                        else:
                            # SHARED: Reset state for this kid only (don't affect global due date)
                            const.LOGGER.info(
                                "Reset Overdue Chores: Resetting SHARED chore state for kid only: %s, kid: %s",
                                chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                kid_id,
                            )
                            self._transition_chore_state(
                                kid_id, chore_id, const.CHORE_STATE_PENDING
                            )
        else:
            # Global reset: Reset all overdue chores for all kids
            for kid_id_iter, _kid_info in self.kids_data.items():
                for chore_id, chore_info in self.chores_data.items():
                    if kid_id_iter in chore_info.get(
                        const.DATA_CHORE_ASSIGNED_KIDS, []
                    ):
                        if self.chore_is_overdue(kid_id_iter, chore_id):
                            # Get completion criteria to determine reset strategy
                            criteria = chore_info.get(
                                const.DATA_CHORE_COMPLETION_CRITERIA,
                                const.COMPLETION_CRITERIA_SHARED,
                            )

                            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                                # INDEPENDENT: Reset state to PENDING and reschedule per-kid due date
                                const.LOGGER.info(
                                    "Reset Overdue Chores: Rescheduling per-kid (INDEPENDENT) chore: %s, kid: %s",
                                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                    kid_id_iter,
                                )
                                self._transition_chore_state(
                                    kid_id_iter, chore_id, const.CHORE_STATE_PENDING
                                )
                                self._reschedule_chore_next_due_date_for_kid(
                                    chore_info, chore_id, kid_id_iter
                                )
                            else:
                                # SHARED: Reset chore-level (affects all kids)
                                const.LOGGER.info(
                                    "Reset Overdue Chores: Rescheduling chore (SHARED): %s for kid: %s",
                                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                                    kid_id_iter,
                                )
                                self._reschedule_chore_next_due(chore_info)

        self._persist()
        self.async_set_updated_data(self._data)

    # -------------------------------------------------------------------------------------
    # Penalties: Reset
    # -------------------------------------------------------------------------------------

    def _handle_pending_chore_claim_at_reset(
        self,
        kid_id: str,
        chore_id: str,
        chore_info: ChoreData,
        kid_chore_data: KidChoreDataEntry,
    ) -> bool:
        """Handle pending claim based on approval reset pending claim action.

        Called during scheduled resets (midnight, due date) to determine
        how to handle claims that weren't approved before reset.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            kid_chore_data: The kid's chore data for clearing pending count

        Returns:
            True if reset should be SKIPPED for this kid (HOLD action)
            False if reset should CONTINUE (CLEAR or after AUTO_APPROVE)
        """
        # Check if kid has pending claim
        if not self.chore_has_pending_claim(kid_id, chore_id):
            return False  # No pending claim, continue with reset

        pending_claim_action = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
        )

        if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_HOLD:
            # HOLD: Skip reset for this kid, leave claim pending
            const.LOGGER.debug(
                "Chore Reset - HOLD pending claim for Kid '%s' on Chore '%s'",
                kid_id,
                chore_id,
            )
            return True  # Skip reset for this kid

        if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE:
            # AUTO_APPROVE: Approve the pending claim before reset
            const.LOGGER.debug(
                "Chore Reset - AUTO_APPROVE pending claim for Kid '%s' on Chore '%s'",
                kid_id,
                chore_id,
            )
            chore_points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0.0)
            self._transition_chore_state(
                kid_id,
                chore_id,
                const.CHORE_STATE_APPROVED,
                points_awarded=chore_points,
            )

        # CLEAR (default) or after AUTO_APPROVE: Clear pending_claim_count
        if kid_chore_data:
            kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

        return False  # Continue with reset
