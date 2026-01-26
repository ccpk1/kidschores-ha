# File: coordinator_chore_operations.py
"""Chore lifecycle operations for KidsChoresDataCoordinator.

.. deprecated:: v0.5.0
    This mixin is being replaced by the layered architecture:
    - Pure logic: ``engines/chore_engine.py`` (ChoreEngine)
    - Workflows: ``managers/chore_manager.py`` (ChoreManager)

    The ChoreOperations mixin remains active during the transition period.
    Future phases will:
    1. Wire ChoreManager into coordinator workflows
    2. Replace method bodies with delegation to ChoreManager
    3. Remove this mixin entirely (target: Phase 6)

    New code should use ChoreEngine for calculations and ChoreManager for workflows.
    See docs/in-process/LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md for migration plan.

This module contains all chore-related coordinator methods extracted from
coordinator.py to improve code organization. Uses Python's multiple inheritance
pattern - ChoreOperations is inherited by KidsChoresDataCoordinator.

43 methods organized in 11 logical sections:
- §1 Service Entry Points (7): claim_chore, approve_chore, etc.
- §2 Coordinator Public API (7): chore_has_pending_claim, chore_is_overdue, etc.
- §3 Validation & Authorization (2): _can_claim_chore, _can_approve_chore
- §4-11: State machine, data management, queries, scheduling, recurring ops, reset, overdue, reminders

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

from homeassistant.util import dt as dt_util

from . import const, kc_helpers as kh
from .engines.schedule import RecurrenceEngine, calculate_next_due_date_from_chore_info
from .managers import NotificationManager

if TYPE_CHECKING:
    import asyncio

    from .managers.chore_manager import ChoreManager
    from .type_defs import (
        AchievementProgress,
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

    if TYPE_CHECKING:
        # ==============================================================================
        # MIXIN INTERFACE CONTRACT
        # ==============================================================================
        # Since this is a Mixin, 'self' at runtime will be the 'KidsChoresDataCoordinator'.
        # However, static type checkers (MyPy, Pylance) don't know that.
        #
        # This block explicitly declares the "Contract":
        # "I expect the class I am mixed into to provide these attributes and methods."
        # ==============================================================================

        # --- Section 1: Infrastructure & Core State -----------------------------------
        hass: Any
        config_entry: Any
        _test_mode: bool
        chore_manager: ChoreManager  # Phase 4.5: ChoreManager for delegated operations

        # Internal storage and locks
        _data: dict[str, Any]
        _approval_locks: dict[str, Any]
        _due_soon_reminders_sent: set[str]
        _pending_chore_changed: bool

        # --- Section 2: Data Access Properties ----------------------------------------
        # These provide typed access to the raw _data dict
        @property
        def kids_data(self) -> dict[str, KidData]: ...
        @property
        def chores_data(self) -> dict[str, ChoreData]: ...
        @property
        def achievements_data(self) -> dict[str, Any]: ...
        @property
        def challenges_data(self) -> dict[str, Any]: ...

        # --- Section 3: Persistence & State Updates -----------------------------------
        def _persist(self) -> None: ...
        def async_set_updated_data(self, data: dict[str, Any]) -> None: ...

        def _get_approval_lock(
            self, operation: str, *identifiers: str
        ) -> asyncio.Lock: ...

        # --- Section 4: Gamification & Stats ------------------------------------------
        stats: Any  # StatisticsEngine instance

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

        def _update_streak_progress(
            self, progress: AchievementProgress, today: date
        ) -> None: ...

        # --- Section 5: Notification Services -----------------------------------------
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

        # --- Section 6: Configuration Helpers -----------------------------------------
        def _get_retention_config(self) -> dict[str, int]: ...

    # =========================================================================
    # §1 SERVICE ENTRY POINTS (7 methods)
    # =========================================================================
    # Home Assistant service handlers - called from services.py
    # External API contract: Service names in services.yaml must remain stable
    # Internal naming: Method names can change without breaking external contracts

    def claim_chore(self, kid_id: str, chore_id: str, user_name: str):
        """Kid claims chore => state=claimed; parent must then approve.

        Phase 4.5: Delegates to ChoreManager for state transitions.
        Notification handling is done via event subscription in coordinator.
        """
        # Delegate to ChoreManager
        self.chore_manager.claim_chore(kid_id, chore_id, user_name)

    async def approve_chore(
        self,
        parent_name: str,  # Used for stale notification feedback
        kid_id: str,
        chore_id: str,
        points_awarded: float | None = None,  # Reserved for future feature
    ):
        """Approve a chore for kid_id if assigned.

        Phase 4.5: Delegates to ChoreManager for state transitions and points.
        Gamification triggers are handled via event subscription (loopback).
        """
        # Delegate to ChoreManager
        await self.chore_manager.approve_chore(
            parent_name, kid_id, chore_id, points_override=points_awarded
        )

    def disapprove_chore(self, parent_name: str, kid_id: str, chore_id: str):
        """Disapprove a chore for kid_id.

        Phase 4.5: Delegates to ChoreManager for state transitions and notifications.
        """
        # Delegate to ChoreManager (async method, so fire-and-forget via create_task)
        self.hass.async_create_task(
            self.chore_manager.disapprove_chore(parent_name, kid_id, chore_id)
        )

    def set_chore_due_date(
        self,
        chore_id: str,
        due_date: datetime | None,
        kid_id: str | None = None,
    ) -> None:
        """Set the due date of a chore.

        Delegates to ChoreManager which handles state reset and event emission.

        Args:
            chore_id: Chore to update
            due_date: New due date (or None to clear)
            kid_id: If provided for INDEPENDENT chores, updates only this kid's due date.
                   For SHARED chores, this parameter is ignored.
        """
        self.chore_manager.set_due_date(chore_id, due_date, kid_id)

    def skip_chore_due_date(self, chore_id: str, kid_id: str | None = None) -> None:
        """Skip the current due date of a recurring chore and reschedule it.

        Delegates to ChoreManager which handles rescheduling and event emission.

        Args:
            chore_id: Chore to skip
            kid_id: If provided for INDEPENDENT chores, skips only this kid's due date.
                   For SHARED chores, this parameter is ignored.
        """
        self.chore_manager.skip_due_date(chore_id, kid_id)

    def reset_all_chores(self) -> None:
        """Reset all chores to pending state, clearing claims/approvals.

        Delegates to ChoreManager which handles event emission.
        """
        self.chore_manager.reset_all_chores()

    def reset_overdue_chores(
        self, chore_id: str | None = None, kid_id: str | None = None
    ) -> None:
        """Reset overdue chore(s) to Pending state and reschedule.

        Delegates to ChoreManager which handles event emission.

        Args:
            chore_id: Specific chore to reset, or None for all
            kid_id: Specific kid's chores to reset, or None for all
        """
        self.chore_manager.reset_overdue_chores(chore_id, kid_id)

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
        kid_chore_data = self._get_chore_data_for_kid(kid_id, chore_id)
        if not kid_chore_data:
            return False

        pending_claim_count = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        return pending_claim_count > 0

    def chore_is_overdue(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is in overdue state for a specific kid.

        Uses the per-kid chore state field (single source of truth).
        This replaces the legacy DATA_KID_OVERDUE_CHORES list.

        Returns:
            True if the chore is in overdue state, False otherwise.
        """
        kid_chore_data = self._get_chore_data_for_kid(kid_id, chore_id)
        if not kid_chore_data:
            return False

        current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
        return current_state == const.CHORE_STATE_OVERDUE

    def chore_is_due(self, kid_id: str | None, chore_id: str) -> bool:
        """Check if a chore is in the due window (approaching due date).

        A chore is in the due window if:
        - It has a due_window_offset > 0 configured
        - Current time is within: (due_date - due_window_offset) <= now < due_date
        - The chore is not already overdue, claimed, or approved

        This method only determines if the chore is within the due window.
        The actual state priority (approved > claimed > due > overdue > pending)
        is handled by the sensor's native_value property.

        Args:
            kid_id: The internal ID of the kid, or None to use chore-level due date.
            chore_id: The internal ID of the chore.

        Returns:
            True if the chore is in the due window, False otherwise.
        """
        chore_info = self.chores_data.get(chore_id)
        if not chore_info:
            return False

        # Get due window offset (stored as duration string like "1d 6h 30m")
        due_window_offset_str = cast(
            "str | None",
            chore_info.get(
                const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
            ),
        )
        due_window_td = kh.dt_parse_duration(due_window_offset_str)

        # If no valid due window offset or disabled (0), not in due window
        if not due_window_td or due_window_td.total_seconds() <= 0:
            return False

        # Get due date: per-kid for INDEPENDENT (if kid_id provided), chore-level otherwise
        due_date_str: str | None = None
        if kid_id:
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        else:
            # No kid_id - use chore-level due date (for global sensor)
            due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)

        if not due_date_str:
            return False

        due_date_dt = kh.dt_to_utc(due_date_str)
        if not due_date_dt:
            return False

        # Calculate due window start: due_date - offset
        now = dt_util.utcnow()
        due_window_start = due_date_dt - due_window_td

        # In due window if: due_window_start <= now < due_date
        return due_window_start <= now < due_date_dt

    def get_chore_due_date(self, kid_id: str | None, chore_id: str) -> datetime | None:
        """Get the due date for a chore as a datetime.

        Handles INDEPENDENT vs SHARED completion criteria:
        - INDEPENDENT: Returns per-kid due date
        - SHARED/SHARED_FIRST: Returns chore-level due date
        - kid_id=None: Always returns chore-level due date

        Args:
            kid_id: The internal ID of the kid. If None, uses chore-level due date.
            chore_id: The internal ID of the chore.

        Returns:
            datetime of due date, or None if no due date configured.
        """
        chore_info = self.chores_data.get(chore_id)
        if not chore_info:
            return None

        # Get due date - if kid_id is None, use chore-level due date
        if kid_id is None:
            due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        else:
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)

        if not due_date_str:
            return None

        return kh.dt_to_utc(due_date_str)

    def get_chore_due_window_start(
        self, kid_id: str | None, chore_id: str
    ) -> datetime | None:
        """Calculate when the due window starts for a chore.

        Returns the datetime when the due window begins (due_date - offset),
        or None if the chore has no due date or no due window configured.
        Returns None if due window offset is 0 (disabled).

        Args:
            kid_id: The internal ID of the kid. If None, uses the chore-level
                due date (appropriate for SHARED chores or global sensor).
            chore_id: The internal ID of the chore.

        Returns:
            datetime when due window starts, or None if not applicable.
        """
        chore_info = self.chores_data.get(chore_id)
        if not chore_info:
            return None

        # Get due window offset - returns None if offset is "0" or missing
        due_window_offset_str = cast(
            "str | None",
            chore_info.get(
                const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
            ),
        )
        due_window_td = kh.dt_parse_duration(due_window_offset_str)

        # If no offset or offset is 0, due window is disabled
        if not due_window_td or due_window_td.total_seconds() <= 0:
            return None

        # Reuse get_chore_due_date to avoid duplicating INDEPENDENT vs SHARED logic
        due_date_dt = self.get_chore_due_date(kid_id, chore_id)
        if not due_date_dt:
            return None

        return due_date_dt - due_window_td

    def chore_is_approved_in_period(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is already approved in the current approval period.

        A chore is considered approved in the current period if:
        - last_approved timestamp exists, AND EITHER:
          a. approval_period_start doesn't exist (chore was never reset, approval is valid), OR
          b. last_approved >= approval_period_start

        Returns:
            True if approved in current period, False otherwise.
        """
        kid_chore_data = self._get_chore_data_for_kid(kid_id, chore_id)
        if not kid_chore_data:
            return False

        last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if not last_approved:
            return False

        period_start = self._get_chore_approval_period_start(kid_id, chore_id)
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

    def undo_chore_claim(self, kid_id: str, chore_id: str) -> None:
        """Allow kid to undo their own chore claim (no stat tracking).

        Delegates to ChoreManager which handles state transitions.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        self.chore_manager.undo_claim(kid_id, chore_id)

    # =========================================================================
    # §3 VALIDATION & AUTHORIZATION (2 methods)
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
        kid_chore_data = self._get_chore_data_for_kid(kid_id, chore_id)
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
        kid_chore_data = self._get_chore_data_for_kid(kid_id, chore_id)
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
    # §5 DATA MANAGEMENT (4 methods)
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

    def _get_chore_data_for_kid(
        self, kid_id: str, chore_id: str
    ) -> KidChoreDataEntry | dict[str, Any]:
        """Get the chore data dict for a specific kid+chore combination.

        Returns an empty dict if the kid or chore data doesn't exist.
        """
        kid_info: KidData = cast("KidData", self.kids_data.get(kid_id, {}))
        return kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})

    def _recalculate_chore_stats_for_kid(self, kid_id: str) -> None:
        """Delegate chore stats aggregation to StatisticsEngine.

        This method aggregates all kid_chore_stats for a given kid by
        delegating to the StatisticsEngine, which owns the period data
        structure knowledge.

        Args:
            kid_id: The internal ID of the kid.
        """
        kid_info: KidData | None = self.kids_data.get(kid_id)
        if not kid_info:
            return
        stats = self.stats.generate_chore_stats(kid_info, self.chores_data)
        kid_info[const.DATA_KID_CHORE_STATS] = stats

    def _assign_kid_to_independent_chores(self, kid_id: str) -> None:
        """Assign kid to all INDEPENDENT chores they're added to.

        When a kid is added, they inherit the template due date for all
        INDEPENDENT chores they're assigned to.
        """
        chores_data = self._data.get(const.DATA_CHORES, {})
        for chore_info in chores_data.values():
            # Only process INDEPENDENT chores
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                continue

            # If kid is assigned to this chore, add their per-kid due date
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if kid_id in assigned_kids:
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                template_due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)
                if kid_id not in per_kid_due_dates:
                    per_kid_due_dates[kid_id] = template_due_date
                    const.LOGGER.debug(
                        "Added kid '%s' to INDEPENDENT chore '%s' with due date: %s",
                        kid_id,
                        chore_info.get(const.DATA_CHORE_NAME),
                        template_due_date,
                    )

    def _remove_kid_from_independent_chores(self, kid_id: str) -> None:
        """Remove kid from per-kid due dates when they're removed.

        Template due date remains unchanged; only per-kid entry is deleted.
        """
        chores_data = self._data.get(const.DATA_CHORES, {})
        for chore_info in chores_data.values():
            # Only process INDEPENDENT chores
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                continue

            # Remove kid from per-kid due dates if present
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
                const.LOGGER.debug(
                    "Removed kid '%s' from INDEPENDENT chore '%s' per-kid dates",
                    kid_id,
                    chore_info.get(const.DATA_CHORE_NAME),
                )

    # =========================================================================
    # §6 QUERY & STATUS HELPERS (5 methods)
    # =========================================================================
    # Read-only state and data queries

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

    def _get_chore_approval_period_start(
        self, kid_id: str, chore_id: str
    ) -> str | None:
        """Get the start of the current approval period for this kid+chore.

        For SHARED chores: Uses chore-level approval_period_start
        For INDEPENDENT chores: Uses per-kid approval_period_start in kid_chore_data

        Returns:
            ISO timestamp string of period start, or None if not set.
        """
        chore_info: ChoreData | None = self.chores_data.get(chore_id)
        if not chore_info:
            return None

        # Default to INDEPENDENT if completion_criteria not set (backward compatibility)
        # This ensures pre-migration chores without completion_criteria are treated as INDEPENDENT
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Period start is per-kid in kid_chore_data
            kid_chore_data = self._get_chore_data_for_kid(kid_id, chore_id)
            return kid_chore_data.get(const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START)
        # SHARED/SHARED_FIRST/etc.: Period start is at chore level
        return chore_info.get(const.DATA_CHORE_APPROVAL_PERIOD_START)

    # =========================================================================
    # §7 SCHEDULING & RESCHEDULING
    # =========================================================================
    # Due date reminder notification processing (30-min advance window).
    # Called from coordinator refresh cycle to send timely reminders.

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
        # Pass explicit reference_time so caller owns the clock (determinism)
        next_due_utc = calculate_next_due_date_from_chore_info(
            original_due_utc,
            chore_info,
            completion_timestamp=completion_utc,
            reference_time=dt_util.utcnow(),
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
        # Pass explicit reference_time so caller owns the clock (determinism)
        next_due_utc = calculate_next_due_date_from_chore_info(
            original_due_utc,
            chore_info_for_calc,
            completion_timestamp=completion_utc,
            reference_time=dt_util.utcnow(),
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

    # =========================================================================
    # §8 RECURRING CHORE OPERATIONS
    # =========================================================================
    # Reset/reschedule logic for daily/weekly/monthly recurring chores.
    # Executed during coordinator refresh cycles at scheduled times.

    async def _process_recurring_chore_resets(self, now: datetime):
        """Handle recurring resets for daily, weekly, and monthly frequencies.

        v0.5.1+: Delegates to ChoreManager which emits SIGNAL_SUFFIX_CHORE_STATUS_RESET
        events for downstream consumers (GamificationManager, etc.).
        """
        # Delegate to ChoreManager which emits proper events
        reset_count = await self.chore_manager.update_recurring_chores(now)
        const.LOGGER.debug(
            "Recurring chore resets delegated to ChoreManager: %d chores reset",
            reset_count,
        )

    async def _process_recurring_chore_resets_legacy(self, now: datetime):
        """LEGACY: Handle recurring resets for daily, weekly, and monthly frequencies.

        .. deprecated:: v0.5.1
            Retained for reference and emergency fallback only.
            Use :meth:`_process_recurring_chore_resets` which delegates to
            :meth:`ChoreManager.update_recurring_chores` for proper event emission.

        Migration path:
            - Coordinator._process_recurring_chore_resets() → delegates to
            - ChoreManager.update_recurring_chores() → calls
            - ChoreManager.reset_chore() → emits SIGNAL_SUFFIX_CHORE_STATUS_RESET

        Removal planned: v0.6.0 (after Phase 5 event-driven architecture validated)
        """

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

    # =========================================================================
    # §10 OVERDUE DETECTION & HANDLING
    # =========================================================================
    # Periodic checks (coordinator refresh) to detect passed due dates.
    # Transitions chore state to OVERDUE and sends parent notifications.

    def _check_chore_overdue_status(
        self,
        chore_id: str,
        chore_info: ChoreData,
        now_utc: datetime,
    ) -> None:
        """Check and apply overdue status for a chore (any completion criteria).

        Unified handler for INDEPENDENT, SHARED, and SHARED_FIRST completion criteria.
        Uses _handle_overdue_chore_state() for core overdue application logic.
        Uses _get_chore_effective_due_date() for due date resolution.

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
                kid_chore_data = self._get_chore_data_for_kid(kid_id, chore_id)
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
                    actions=NotificationManager.build_claim_action(kid_id, chore_id),
                )
            )
            # Use system language for date formatting (parent-specific formatting
            # would require restructuring the notification loop)
            # Build action buttons: Complete (approve directly), Skip (reset/reschedule), Remind

            parent_actions = []
            parent_actions.extend(
                NotificationManager.build_complete_action(kid_id, chore_id)
            )
            parent_actions.extend(
                NotificationManager.build_skip_action(kid_id, chore_id)
            )
            parent_actions.extend(
                NotificationManager.build_remind_action(kid_id, chore_id)
            )

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

    async def _check_overdue_chores(self, now: datetime | None = None):
        """Check and mark overdue chores if due date is passed.

        v0.5.1+: Delegates to ChoreManager which emits SIGNAL_SUFFIX_CHORE_OVERDUE
        events for downstream consumers (GamificationManager, etc.).
        """
        now_utc = now or dt_util.utcnow()
        # Delegate to ChoreManager which emits proper events
        marked_overdue = await self.chore_manager.update_overdue_status(now_utc)
        const.LOGGER.debug(
            "Overdue check delegated to ChoreManager: %d chores marked overdue",
            len(marked_overdue),
        )

    async def _check_overdue_chores_legacy(self, now: datetime | None = None):
        """LEGACY: Check and mark overdue chores if due date is passed.

        .. deprecated:: v0.5.1
            Retained for reference and emergency fallback only.
            Use :meth:`_check_overdue_chores` which delegates to
            :meth:`ChoreManager.update_overdue_status` for proper event emission.

        Migration path:
            - Coordinator._check_overdue_chores() → delegates to
            - ChoreManager.update_overdue_status() → calls
            - ChoreManager.mark_overdue() → emits SIGNAL_SUFFIX_CHORE_OVERDUE

        Branching logic based on completion criteria:
            - INDEPENDENT: Each kid can have different due dates (per-kid storage)
            - SHARED_*: All kids share same due date (chore-level storage)

        Removal planned: v0.6.0 (after Phase 5 event-driven architecture validated)
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
    # §11 REMINDER SYSTEM
    # =========================================================================
    # Notification helpers for due date reminders and overdue status.
    # Called from §7 Scheduling & Rescheduling and §10 Overdue Detection.

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
                        actions=NotificationManager.build_claim_action(
                            kid_id, chore_id
                        ),
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

    def _clear_chore_due_reminder(self, chore_id: str, kid_id: str) -> None:
        """Clear due-soon reminder tracking for a chore+kid combination (v0.5.0+).

        Called when chore is claimed, approved, or rescheduled to allow
        a fresh reminder for the next occurrence.

        Args:
            chore_id: The chore internal ID
            kid_id: The kid internal ID
        """
        reminder_key = f"{chore_id}:{kid_id}"
        self._due_soon_reminders_sent.discard(reminder_key)
