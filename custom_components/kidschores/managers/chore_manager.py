"""Chore Manager - Stateful chore operations and workflow orchestration.

This manager handles all chore state transitions and workflow coordination:
- Claiming, approving, disapproving chores
- Race condition protection via asyncio.Lock
- Event emission for downstream systems (notifications, gamification)
- Coordination with EconomyManager for point transactions

ARCHITECTURE (v0.5.0+):
- ChoreManager = "The Job" (STATEFUL workflow orchestration)
- ChoreEngine = Pure state machine logic (STATELESS)
- EconomyManager = Point transactions (injected dependency)
- NotificationManager = Notifications (wired via Coordinator events)

The manager delegates pure logic to ChoreEngine and uses events
for cross-domain communication (notifications, achievements).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.kidschores import const, kc_helpers as kh
from custom_components.kidschores.engines.chore_engine import (
    CHORE_ACTION_APPROVE,
    CHORE_ACTION_CLAIM,
    CHORE_ACTION_DISAPPROVE,
    CHORE_ACTION_OVERDUE,
    CHORE_ACTION_RESET,
    CHORE_ACTION_UNDO,
    ChoreEngine,
    TransitionEffect,
)
from custom_components.kidschores.managers.base_manager import BaseManager

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.managers.economy_manager import EconomyManager
    from custom_components.kidschores.type_defs import ChoreData


__all__ = ["ChoreManager"]


class ChoreManager(BaseManager):
    """Manager for chore state transitions and workflow orchestration.

    Responsibilities:
    - Execute claim/approve/disapprove/undo/reset workflows
    - Protect against race conditions (asyncio locks)
    - Emit events for cross-domain communication
    - Coordinate with EconomyManager for point deposits

    NOT responsible for:
    - Pure state machine logic (delegated to ChoreEngine)
    - Direct notification sending (events handled by Coordinator)
    - Achievement/badge tracking (events handled by GamificationManager)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
        economy_manager: EconomyManager,
    ) -> None:
        """Initialize ChoreManager with dependencies.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator managing this integration
            economy_manager: Injected dependency for point transactions
        """
        super().__init__(hass, coordinator)
        self._coordinator = coordinator
        self._economy_manager = economy_manager

        # Locks for race condition protection (keyed by kid_id:chore_id)
        self._approval_locks: dict[str, asyncio.Lock] = {}

    async def async_setup(self) -> None:
        """Set up the ChoreManager.

        Phase 4: No event subscriptions needed - receives direct calls from Coordinator.
        Future: May subscribe to timer events for scheduled resets.
        """
        const.LOGGER.debug("ChoreManager initialized for entry %s", self.entry_id)

    # =========================================================================
    # §1 WORKFLOW METHODS (public API)
    # =========================================================================

    def claim_chore(
        self,
        kid_id: str,
        chore_id: str,
        user_name: str,
    ) -> None:
        """Process a chore claim request.

        Validates the claim is allowed, applies state transitions, and emits events.
        This is a synchronous method that delegates to ChoreEngine for pure logic.

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            user_name: Who initiated the claim (for notification context)

        Raises:
            HomeAssistantError: If claim validation fails
        """
        # Validate entities exist
        self._validate_kid_and_chore(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Validate assignment
        if kid_id not in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            chore_name = chore_data.get(const.DATA_CHORE_NAME, "")
            kid_name = kid_info.get(const.DATA_KID_NAME, "")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                translation_placeholders={"entity": chore_name, "kid": kid_name},
            )

        # Get validation inputs for engine
        has_pending = ChoreEngine.chore_has_pending_claim(kid_chore_data)
        is_approved = self._is_approved_in_period(kid_id, chore_id)

        # Delegate validation to engine (stateless pure logic)
        can_claim, error_key = ChoreEngine.can_claim_chore(
            kid_chore_data=kid_chore_data,
            chore_data=chore_data,
            has_pending_claim=has_pending,
            is_approved_in_period=is_approved,
        )

        if not can_claim:
            self._raise_claim_error(kid_id, chore_id, error_key)

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Calculate state transitions
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_CLAIM,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        # Apply effects to coordinator data
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Set last_claimed timestamp for the claiming kid
        from custom_components.kidschores import kc_helpers as kh

        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = kh.dt_now_iso()

        # Clear due-soon reminder tracking (allows fresh reminder for next period)
        self._coordinator._clear_chore_due_reminder(chore_id, kid_id)

        # Update global chore state
        self._update_global_state(chore_id)

        # Increment pending claim counter
        self._increment_pending_count(kid_id, chore_id)

        # Check auto-approve
        auto_approve = chore_data.get(
            const.DATA_CHORE_AUTO_APPROVE, const.DEFAULT_CHORE_AUTO_APPROVE
        )
        if auto_approve:
            self.hass.async_create_task(
                self.approve_chore("auto_approve", kid_id, chore_id)
            )

        # Emit event for notification system
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_CLAIMED,
            kid_id=kid_id,
            chore_id=chore_id,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            user_name=user_name,
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
            update_stats=True,
        )

        # Persist and update state
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "Claim processed: kid=%s chore=%s user=%s",
            kid_id,
            chore_id,
            user_name,
        )

    async def approve_chore(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        points_override: float | None = None,
    ) -> None:
        """Approve a chore with race condition protection.

        Uses asyncio.Lock to ensure only one approval processes at a time
        per kid+chore combination.

        Args:
            parent_name: Who is approving (for audit and notification)
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            points_override: Optional override for points (future feature)
        """
        # Acquire lock for this kid+chore pair
        lock = self._get_lock(kid_id, chore_id)
        async with lock:
            await self._approve_chore_locked(
                parent_name, kid_id, chore_id, points_override
            )

    async def disapprove_chore(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        reason: str | None = None,
    ) -> None:
        """Disapprove a chore (return to pending state).

        Args:
            parent_name: Who is disapproving (for audit)
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            reason: Optional reason for disapproval
        """
        lock = self._get_lock(kid_id, chore_id)
        async with lock:
            await self._disapprove_chore_locked(parent_name, kid_id, chore_id, reason)

    def undo_chore(
        self,
        kid_id: str,
        chore_id: str,
        parent_name: str,
    ) -> None:
        """Undo a chore approval (reclaim points, reset state).

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            parent_name: Who is undoing (for audit)
        """
        self._validate_kid_and_chore(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Get previous points to reclaim
        previous_points = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_TOTAL_POINTS, 0.0
        )

        # Calculate effects with skip_stats=True (undo doesn't count for stats)
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_UNDO,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
            skip_stats=True,
        )

        # Apply effects
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Update global chore state
        self._update_global_state(chore_id)

        # Reclaim points via EconomyManager (use withdrawal)
        # Note: NSF may occur if kid spent points - that's expected behavior
        if previous_points > 0:
            try:
                self.hass.async_create_task(
                    self._economy_manager.withdraw(
                        kid_id=kid_id,
                        amount=previous_points,
                        source=const.POINTS_SOURCE_OTHER,  # "other" for corrections
                        reference_id=chore_id,
                    )
                )
            except Exception:  # pylint: disable=broad-except
                # NSF or other error - log but don't fail the undo
                const.LOGGER.warning(
                    "Could not reclaim points for undo: kid=%s points=%.2f",
                    kid_id,
                    previous_points,
                )

        # Persist
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.info(
            "Chore undone: chore=%s kid=%s by=%s points_reclaimed=%.2f",
            chore_data.get(const.DATA_CHORE_NAME),
            kid_info.get(const.DATA_KID_NAME),
            parent_name,
            previous_points,
        )

    def reset_chore(
        self,
        kid_id: str,
        chore_id: str,
        *,
        reset_approval_period: bool = False,
    ) -> None:
        """Reset a chore to pending state.

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            reset_approval_period: If True, also resets the approval period tracking
        """
        self._validate_kid_and_chore(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]

        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_RESET,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Update global chore state
        self._update_global_state(chore_id)

        # Handle approval period reset if requested
        if reset_approval_period:
            self._reset_approval_period(kid_id, chore_id)

        # Emit status reset event
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_STATUS_RESET,
            kid_id=kid_id,
            chore_id=chore_id,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    def mark_overdue(
        self,
        kid_id: str,
        chore_id: str,
        days_overdue: int,
        due_date: str,
    ) -> None:
        """Mark a chore as overdue.

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            days_overdue: Number of days past due
            due_date: ISO format due date string
        """
        self._validate_kid_and_chore(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]

        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_OVERDUE,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Update global chore state
        self._update_global_state(chore_id)

        # Emit overdue event
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_OVERDUE,
            kid_id=kid_id,
            chore_id=chore_id,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            days_overdue=days_overdue,
            due_date=due_date,
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    async def update_overdue_status(
        self,
        now: datetime | None = None,
    ) -> list[tuple[str, str]]:
        """Check all chores and mark overdue if due date has passed.

        This is the Manager entry point for scheduled overdue detection.
        Delegates to existing coordinator helper methods for the complex
        completion criteria logic (SHARED, INDEPENDENT, SHARED_FIRST),
        but emits events via mark_overdue() for downstream consumers.

        Args:
            now: Current datetime (UTC). If None, uses current time.

        Returns:
            List of (chore_id, kid_id) tuples that were marked overdue.
        """
        import time

        perf_start = time.perf_counter()
        now_utc = now or dt_util.utcnow()
        marked_overdue: list[tuple[str, str]] = []

        const.LOGGER.debug(
            "ChoreManager.update_overdue_status - Starting at %s",
            now_utc.isoformat(),
        )

        for chore_id, chore_info in self._coordinator.chores_data.items():
            # Get the list of assigned kids
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if not assigned_kids:
                continue

            # Skip if all kids have already acted
            all_kids_acted = all(
                self._coordinator.chore_has_pending_claim(kid_id, chore_id)
                or self._coordinator.chore_is_approved_in_period(kid_id, chore_id)
                for kid_id in assigned_kids
            )
            if all_kids_acted:
                continue

            # Check overdue handling type - skip NEVER_OVERDUE
            overdue_handling = chore_info.get(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.OVERDUE_HANDLING_AT_DUE_DATE,
            )
            if overdue_handling == const.OVERDUE_HANDLING_NEVER_OVERDUE:
                continue

            # Get completion criteria
            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            # Process each assigned kid
            for kid_id in assigned_kids:
                if not kid_id:
                    continue

                # Skip if already claimed or approved
                if self._coordinator.chore_has_pending_claim(kid_id, chore_id):
                    continue
                if self._coordinator.chore_is_approved_in_period(kid_id, chore_id):
                    continue

                # SHARED_FIRST special handling
                if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                    # Find if there's a claimant
                    claimant_kid_id = next(
                        (
                            k
                            for k in assigned_kids
                            if self._coordinator.chore_has_pending_claim(k, chore_id)
                        ),
                        None,
                    )
                    # If someone else claimed, skip this kid
                    if claimant_kid_id and kid_id != claimant_kid_id:
                        continue

                # Get effective due date
                due_str = self._coordinator._get_chore_effective_due_date(
                    chore_id, kid_id
                )
                if not due_str:
                    continue

                # Parse due date
                due_date_utc = kh.dt_to_utc(due_str)
                if due_date_utc is None:
                    continue

                # Check if past due
                if now_utc <= due_date_utc:
                    continue

                # Calculate days overdue
                days_overdue = (now_utc - due_date_utc).days

                # Mark as overdue via Manager method (emits event)
                try:
                    self.mark_overdue(
                        kid_id=kid_id,
                        chore_id=chore_id,
                        days_overdue=days_overdue,
                        due_date=due_str,
                    )
                    marked_overdue.append((chore_id, kid_id))
                except HomeAssistantError as err:
                    const.LOGGER.warning(
                        "Failed to mark chore overdue: chore=%s kid=%s error=%s",
                        chore_id,
                        kid_id,
                        err,
                    )

        # Performance logging
        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "ChoreManager.update_overdue_status - Completed in %.3fs, marked %d overdue",
            perf_duration,
            len(marked_overdue),
        )

        return marked_overdue

    async def update_recurring_chores(
        self,
        now: datetime,
    ) -> int:
        """Process recurring chore resets and reschedules.

        This is the Manager entry point for scheduled recurring operations.
        Handles daily/weekly/monthly reset cycles and emits events for
        each chore that gets reset.

        Args:
            now: Current datetime (UTC)

        Returns:
            Count of chores reset.
        """
        from calendar import monthrange

        reset_count = 0

        const.LOGGER.debug(
            "ChoreManager.update_recurring_chores - Starting at %s",
            now.isoformat(),
        )

        # Delegate rescheduling to coordinator (handles SHARED vs INDEPENDENT)
        await self._coordinator._reschedule_recurring_chores(now)

        # Determine which frequencies should reset now
        target_freqs: list[str] = []

        # Daily reset at configured hour
        if now.hour == const.DEFAULT_DAILY_RESET_TIME.get(
            const.TIME_UNIT_HOUR, const.DEFAULT_HOUR
        ):
            target_freqs.append(const.FREQUENCY_DAILY)

            # Weekly reset on configured day
            if now.weekday() == const.DEFAULT_WEEKLY_RESET_DAY:
                target_freqs.append(const.FREQUENCY_WEEKLY)

            # Monthly reset on configured day
            days_in_month = monthrange(now.year, now.month)[1]
            reset_day = min(const.DEFAULT_MONTHLY_RESET_DAY, days_in_month)
            if now.day == reset_day:
                target_freqs.append(const.FREQUENCY_MONTHLY)

        if not target_freqs:
            const.LOGGER.debug(
                "ChoreManager.update_recurring_chores - No frequencies to reset at hour=%d",
                now.hour,
            )
            return 0

        const.LOGGER.debug(
            "ChoreManager.update_recurring_chores - Resetting frequencies: %s",
            target_freqs,
        )

        # Process each chore that matches the target frequencies
        now_utc = dt_util.utcnow()
        for chore_id, chore_info in self._coordinator.chores_data.items():
            frequency = chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
            )

            # For non-recurring chores, only process if approval_reset_type is AT_MIDNIGHT_*
            if frequency == const.FREQUENCY_NONE:
                approval_reset_type = chore_info.get(
                    const.DATA_CHORE_APPROVAL_RESET_TYPE,
                    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                )
                if approval_reset_type not in (
                    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                    const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
                ):
                    continue
            elif frequency not in target_freqs:
                continue

            # Get completion criteria
            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            # Check if chore is ready for reset based on due date
            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT: Check each kid's due date
                reset_count += self._reset_independent_chore(
                    chore_id, chore_info, now_utc
                )
            else:
                # SHARED: Use chore-level due date
                reset_count += self._reset_shared_chore(chore_id, chore_info, now_utc)

        const.LOGGER.debug(
            "ChoreManager.update_recurring_chores - Completed, reset %d chores",
            reset_count,
        )

        return reset_count

    def _reset_shared_chore(
        self,
        chore_id: str,
        chore_info: ChoreData,
        now_utc: datetime,
    ) -> int:
        """Reset a SHARED chore if due date has passed.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime

        Returns:
            Count of kids reset (0 or len(assigned_kids))
        """
        # Check due date
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        if due_date_str:
            due_date_utc = kh.dt_to_utc(due_date_str)
            if due_date_utc is None:
                return 0
            if now_utc < due_date_utc:
                return 0  # Not yet due

        # Check if already in PENDING state
        current_state = chore_info.get(const.DATA_CHORE_STATE)
        if current_state == const.CHORE_STATE_PENDING:
            return 0  # Already reset

        # Reset each assigned kid
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        reset_count = 0

        for kid_id in assigned_kids:
            if not kid_id:
                continue

            try:
                self.reset_chore(
                    kid_id=kid_id,
                    chore_id=chore_id,
                    reset_approval_period=True,
                )
                reset_count += 1
            except HomeAssistantError as err:
                const.LOGGER.warning(
                    "Failed to reset SHARED chore: chore=%s kid=%s error=%s",
                    chore_id,
                    kid_id,
                    err,
                )

        return reset_count

    def _reset_independent_chore(
        self,
        chore_id: str,
        chore_info: ChoreData,
        now_utc: datetime,
    ) -> int:
        """Reset an INDEPENDENT chore for kids whose due date has passed.

        Args:
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            now_utc: Current UTC datetime

        Returns:
            Count of kids reset
        """
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        reset_count = 0

        for kid_id in assigned_kids:
            if not kid_id:
                continue

            # Get this kid's effective due date
            due_str = self._coordinator._get_chore_effective_due_date(chore_id, kid_id)
            if due_str:
                due_date_utc = kh.dt_to_utc(due_str)
                if due_date_utc is None:
                    continue
                if now_utc < due_date_utc:
                    continue  # Not yet due for this kid

            # Check if already in PENDING state
            kid_chore_data = self._coordinator._get_chore_data_for_kid(kid_id, chore_id)
            current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
            if current_state == const.CHORE_STATE_PENDING:
                continue  # Already reset

            try:
                self.reset_chore(
                    kid_id=kid_id,
                    chore_id=chore_id,
                    reset_approval_period=True,
                )
                reset_count += 1
            except HomeAssistantError as err:
                const.LOGGER.warning(
                    "Failed to reset INDEPENDENT chore: chore=%s kid=%s error=%s",
                    chore_id,
                    kid_id,
                    err,
                )

        return reset_count

    # =========================================================================
    # §1.5 SERVICE METHODS (public API for Coordinator delegation)
    # =========================================================================

    def set_due_date(
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
        from homeassistant.util import dt as dt_util

        chore_info = self._coordinator.chores_data.get(chore_id)
        if chore_info is None:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        # Convert due_date to UTC ISO string
        new_due_date_iso = dt_util.as_utc(due_date).isoformat() if due_date else None

        # Get completion criteria
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # Apply based on completion criteria
        if criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ):
            chore_info[const.DATA_CHORE_DUE_DATE] = new_due_date_iso
        elif criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            if kid_id:
                # Update only specified kid's due date
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                per_kid_due_dates[kid_id] = new_due_date_iso
            else:
                # Update all assigned kids' due dates
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    per_kid_due_dates[assigned_kid_id] = new_due_date_iso

        # If due date cleared, reset frequency if needed
        if new_due_date_iso is None:
            if chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) not in (
                const.FREQUENCY_NONE,
                const.FREQUENCY_DAILY,
                const.FREQUENCY_WEEKLY,
            ):
                chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_NONE
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL, None)
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, None)

        # Reset chore state to PENDING for all assigned kids
        for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            if assigned_kid_id:
                try:
                    self.reset_chore(
                        kid_id=assigned_kid_id,
                        chore_id=chore_id,
                        reset_approval_period=True,
                    )
                except HomeAssistantError:
                    # Log but continue (don't fail the whole operation)
                    const.LOGGER.warning(
                        "Failed to reset state for kid %s when setting due date",
                        assigned_kid_id,
                    )

        const.LOGGER.info(
            "Due date set for chore '%s'",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    def skip_due_date(self, chore_id: str, kid_id: str | None = None) -> None:
        """Skip the current due date of a recurring chore and reschedule it.

        Args:
            chore_id: Chore to skip
            kid_id: If provided for INDEPENDENT chores, skips only this kid's due date.
                   For SHARED chores, this parameter is ignored.
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
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
                translation_placeholders={"frequency": "none"},
            )

        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: skip per-kid due dates
            if kid_id:
                # Skip only specified kid
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                if not per_kid_due_dates.get(kid_id):
                    return  # No due date to skip

                self._coordinator._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                self.reset_chore(kid_id, chore_id, reset_approval_period=True)
            else:
                # Skip all assigned kids
                self._coordinator._reschedule_chore_next_due(chore_info)
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    if (
                        assigned_kid_id
                        and assigned_kid_id in self._coordinator.kids_data
                    ):
                        self._coordinator._reschedule_chore_next_due_date_for_kid(
                            chore_info, chore_id, assigned_kid_id
                        )
                        self.reset_chore(
                            assigned_kid_id, chore_id, reset_approval_period=True
                        )
        else:
            # SHARED: skip chore-level due date
            if not chore_info.get(const.DATA_CHORE_DUE_DATE):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MISSING_FIELD,
                    translation_placeholders={
                        "field": "due_date",
                        "entity": f"chore '{chore_info.get(const.DATA_CHORE_NAME, chore_id)}'",
                    },
                )
            self._coordinator._reschedule_chore_next_due(chore_info)
            for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if assigned_kid_id and assigned_kid_id in self._coordinator.kids_data:
                    self.reset_chore(
                        assigned_kid_id, chore_id, reset_approval_period=True
                    )

        const.LOGGER.info(
            "Skipped due date for chore '%s'",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    def reset_all_chores(self) -> None:
        """Reset all chores to pending state, clearing claims/approvals.

        This is a manual reset that:
        - Sets all chore states to PENDING
        - Resets approval_period_start for all chores
        - Emits SIGNAL_SUFFIX_CHORE_STATUS_RESET for each chore
        """
        now_utc_iso = dt_util.utcnow().isoformat()

        # Reset each chore using Manager method (emits events)
        for chore_id, chore_info in self._coordinator.chores_data.items():
            # Update chore-level state
            chore_info[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING

            # Reset SHARED chore approval_period_start
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_utc_iso

            # Reset each assigned kid
            for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if kid_id and kid_id in self._coordinator.kids_data:
                    try:
                        self.reset_chore(
                            kid_id=kid_id,
                            chore_id=chore_id,
                            reset_approval_period=True,
                        )
                    except HomeAssistantError:
                        const.LOGGER.warning(
                            "Failed to reset chore %s for kid %s",
                            chore_id,
                            kid_id,
                        )

        # Clear overdue notifications for all kids
        for kid_info in self._coordinator.kids_data.values():
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = {}

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.info("Manually reset all chores to pending")

    def reset_overdue_chores(
        self, chore_id: str | None = None, kid_id: str | None = None
    ) -> None:
        """Reset overdue chore(s) to Pending state and reschedule.

        Branching logic:
        - INDEPENDENT chores: Reschedule per-kid due dates individually
        - SHARED chores: Reschedule chore-level due date (affects all kids)
        """
        if chore_id:
            # Specific chore reset
            chore_info = self._coordinator.chores_data.get(chore_id)
            if not chore_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_CHORE,
                        "name": chore_id,
                    },
                )

            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and kid_id:
                # INDEPENDENT + kid: Reset this kid only
                self.reset_chore(kid_id, chore_id, reset_approval_period=True)
                self._coordinator._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
            else:
                # SHARED or INDEPENDENT without kid
                self._coordinator._reschedule_chore_next_due(chore_info)

        elif kid_id:
            # Kid-only reset: reset all overdue chores for this kid
            kid_info = self._coordinator.kids_data.get(kid_id)
            if not kid_info:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            for chore_id_iter, chore_info in self._coordinator.chores_data.items():
                if kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if self._coordinator.chore_is_overdue(kid_id, chore_id_iter):
                        criteria = chore_info.get(
                            const.DATA_CHORE_COMPLETION_CRITERIA,
                            const.COMPLETION_CRITERIA_SHARED,
                        )

                        self.reset_chore(
                            kid_id, chore_id_iter, reset_approval_period=True
                        )

                        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                            self._coordinator._reschedule_chore_next_due_date_for_kid(
                                chore_info, chore_id_iter, kid_id
                            )
        else:
            # Global reset: Reset all overdue chores for all kids
            for kid_id_iter in self._coordinator.kids_data:
                for chore_id_iter, chore_info in self._coordinator.chores_data.items():
                    if kid_id_iter in chore_info.get(
                        const.DATA_CHORE_ASSIGNED_KIDS, []
                    ):
                        if self._coordinator.chore_is_overdue(
                            kid_id_iter, chore_id_iter
                        ):
                            criteria = chore_info.get(
                                const.DATA_CHORE_COMPLETION_CRITERIA,
                                const.COMPLETION_CRITERIA_SHARED,
                            )

                            self.reset_chore(
                                kid_id_iter, chore_id_iter, reset_approval_period=True
                            )

                            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                                self._coordinator._reschedule_chore_next_due_date_for_kid(
                                    chore_info, chore_id_iter, kid_id_iter
                                )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    def undo_claim(self, kid_id: str, chore_id: str) -> None:
        """Allow kid to undo their own chore claim (no stat tracking).

        This provides a way for kids to remove their claim without counting
        as a disapproval. Does NOT track stats and does NOT send notifications.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Decrement pending_count
        kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
        if chore_id not in kid_chores_data:
            self._coordinator._update_kid_chore_data(kid_id, chore_id, 0.0)
        kid_chore_entry = kid_chores_data[chore_id]
        current_count = kid_chore_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current_count - 1
        )

        # Handle SHARED_FIRST: Reset ALL kids to pending
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            const.LOGGER.info(
                "SHARED_FIRST: Kid undo - resetting all kids to pending for chore '%s'",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                # Use skip_stats via undo action through Engine
                effects = ChoreEngine.calculate_transition(
                    chore_data=chore_info,
                    actor_kid_id=other_kid_id,
                    action=CHORE_ACTION_UNDO,
                    kids_assigned=chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []),
                    skip_stats=True,
                )
                for effect in effects:
                    self._apply_effect(effect, chore_id)
                # Clear claimed_by/completed_by using coordinator helper
                other_kid_chore = self._coordinator._get_chore_data_for_kid(
                    other_kid_id, chore_id
                )
                if other_kid_chore:
                    other_kid_chore.pop(const.DATA_CHORE_CLAIMED_BY, None)
                    other_kid_chore.pop(const.DATA_CHORE_COMPLETED_BY, None)
        else:
            # Normal: only reset the kid who is undoing
            effects = ChoreEngine.calculate_transition(
                chore_data=chore_info,
                actor_kid_id=kid_id,
                action=CHORE_ACTION_UNDO,
                kids_assigned=chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []),
                skip_stats=True,
            )
            for effect in effects:
                self._apply_effect(effect, chore_id)

        # Update global state
        self._update_global_state(chore_id)

        # No notification (silent undo)
        # No event emission needed for undo

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    # =========================================================================
    # §2 LOCKED WORKFLOW IMPLEMENTATIONS
    # =========================================================================

    async def _approve_chore_locked(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        points_override: float | None = None,
    ) -> None:
        """Approve chore implementation (called inside lock).

        Args:
            parent_name: Who is approving
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            points_override: Optional point override
        """
        # Validate entities exist
        self._validate_kid_and_chore(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Get previous state for event payload
        previous_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Get validation inputs
        is_approved = self._is_approved_in_period(kid_id, chore_id)

        # Re-validate inside lock (race condition protection)
        can_approve, error_key = ChoreEngine.can_approve_chore(
            kid_chore_data=kid_chore_data,
            chore_data=chore_data,
            is_approved_in_period=is_approved,
        )

        if not can_approve:
            # Race condition: another parent already approved
            const.LOGGER.info(
                "Race condition prevented: chore '%s' for kid '%s' already processed",
                chore_data.get(const.DATA_CHORE_NAME),
                kid_info.get(const.DATA_KID_NAME),
            )
            return  # Graceful exit - expected behavior

        # Calculate points
        base_points = points_override or float(
            chore_data.get(const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS)
        )
        multiplier = float(kid_info.get(const.DATA_KID_POINTS_MULTIPLIER, 1.0))
        points_to_award = ChoreEngine.calculate_points(chore_data, multiplier)

        # Use override if specified
        if points_override is not None:
            points_to_award = round(
                points_override * multiplier, const.DATA_FLOAT_PRECISION
            )

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # =====================================================================
        # CAPTURE OLD STATE (Required for streak calculation)
        # Must happen BEFORE applying effects or updating timestamps
        # =====================================================================
        from custom_components.kidschores import kc_helpers as kh

        previous_last_approved = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_LAST_APPROVED
        )

        # Get yesterday's streak for continuation check
        today_iso = kh.dt_today_local().isoformat()
        yesterday_iso = kh.dt_add_interval(
            today_iso,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=-1,
            require_future=False,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )

        periods_data = kid_chore_data.setdefault(const.DATA_KID_CHORE_DATA_PERIODS, {})
        daily_periods = periods_data.setdefault(
            const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
        )
        yesterday_data = daily_periods.get(yesterday_iso, {})
        previous_streak = yesterday_data.get(
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
        )

        # Calculate effects
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_APPROVE,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        # Apply effects
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # =====================================================================
        # UPDATE TIMESTAMPS AND CALCULATE STREAK
        # =====================================================================
        now_iso = kh.dt_now_iso()

        # Set last_approved timestamp
        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso

        # Calculate streak using schedule-aware logic
        new_streak = ChoreEngine.calculate_streak(
            current_streak=previous_streak,
            previous_last_approved_iso=previous_last_approved,
            now_iso=now_iso,
            chore_data=chore_data,
        )

        # Store streak in today's period data
        today_data = daily_periods.setdefault(today_iso, {})
        today_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = new_streak

        # Update all-time longest streak if this is a new record
        all_time_data = periods_data.setdefault(
            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
        )
        all_time_streak = all_time_data.get(
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
        )
        if new_streak > all_time_streak:
            all_time_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = new_streak

        # Update global chore state
        self._update_global_state(chore_id)

        # Update chore stats (approved count + points)
        self._update_chore_stats(kid_id, "approved", points_to_award)

        # Decrement pending count
        self._decrement_pending_count(kid_id, chore_id)

        # Set completed_by based on completion criteria
        self._handle_completion_criteria(chore_id, kid_id, kid_name)

        # Handle UPON_COMPLETION reset type: immediately reset to PENDING
        # Other reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*) stay APPROVED until
        # scheduled reset
        # EXCEPTION: immediate_on_late option resets to PENDING when approval is late
        approval_reset = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_data.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )

        # Determine if we should reset immediately
        should_reset_immediately = False

        if approval_reset == const.APPROVAL_RESET_UPON_COMPLETION:
            should_reset_immediately = True
        elif (
            overdue_handling
            == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
            and self._is_approval_after_reset_boundary(chore_data, kid_id)
        ):
            # immediate_on_late: Reset to PENDING if approval is after reset boundary
            should_reset_immediately = True

        if should_reset_immediately:
            # Set chore-level last_completed BEFORE rescheduling
            # This is used by FREQUENCY_CUSTOM_FROM_COMPLETE to calculate
            # next due date from completion timestamp instead of original due date
            chore_data[const.DATA_CHORE_LAST_COMPLETED] = now_iso

            # Get completion criteria to determine reset strategy
            completion_criteria = chore_data.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )

            # INDEPENDENT: Reset only the current kid, reschedule only their due date
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                self._reset_kid_chore_to_pending(kid_id, chore_id)
                self._update_global_state(chore_id)
                self._reschedule_due_dates_upon_completion(chore_id, [kid_id])

            # SHARED/SHARED_FIRST: Only reset when ALL assigned kids have approved
            elif self._all_kids_approved(chore_id, kids_assigned):
                for assigned_kid_id in kids_assigned:
                    if assigned_kid_id:
                        self._reset_kid_chore_to_pending(assigned_kid_id, chore_id)
                self._update_global_state(chore_id)
                self._reschedule_due_dates_upon_completion(chore_id, kids_assigned)

        # Award points via EconomyManager
        if points_to_award > 0:
            await self._economy_manager.deposit(
                kid_id=kid_id,
                amount=base_points,  # Base points - multiplier applied by EconomyManager
                source=const.POINTS_SOURCE_CHORES,
                reference_id=chore_id,
                apply_multiplier=True,
            )

        # Determine if shared/multi-claim for event payload
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )
        is_shared = completion_criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        )
        is_multi_claim = ChoreEngine.chore_allows_multiple_claims(chore_data)

        # Emit approval event with rich payload
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_APPROVED,
            kid_id=kid_id,
            chore_id=chore_id,
            parent_name=parent_name,
            points_awarded=points_to_award,
            is_shared=is_shared,
            is_multi_claim=is_multi_claim,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
            multiplier_applied=multiplier,
            previous_state=previous_state,
            update_stats=True,
        )

        # Persist
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "Approval processed: kid=%s chore=%s points=%.2f by=%s",
            kid_id,
            chore_id,
            points_to_award,
            parent_name,
        )

    async def _disapprove_chore_locked(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        reason: str | None = None,
    ) -> None:
        """Disapprove chore implementation (called inside lock).

        Args:
            parent_name: Who is disapproving
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            reason: Optional disapproval reason
        """
        self._validate_kid_and_chore(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        previous_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Calculate effects
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_DISAPPROVE,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        # Apply effects
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Set last_disapproved timestamp for the disapproved kid
        from custom_components.kidschores import kc_helpers as kh

        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = kh.dt_now_iso()

        # Update global chore state
        self._update_global_state(chore_id)

        # Update chore stats (disapproval count)
        self._update_chore_stats(kid_id, "disapproved")

        # Clear claimed_by
        self._clear_claimed_completed_by(chore_id, kid_id, const.DATA_CHORE_CLAIMED_BY)

        # Decrement pending count
        self._decrement_pending_count(kid_id, chore_id)

        # Emit disapproval event
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_DISAPPROVED,
            kid_id=kid_id,
            chore_id=chore_id,
            parent_name=parent_name,
            reason=reason,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
            previous_state=previous_state,
            update_stats=True,
        )

        # Persist
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "Disapproval processed: kid=%s chore=%s by=%s reason=%s",
            kid_id,
            chore_id,
            parent_name,
            reason or "none",
        )

    # =========================================================================
    # §3 HELPER METHODS (private)
    # =========================================================================

    def _get_lock(self, kid_id: str, chore_id: str) -> asyncio.Lock:
        """Get or create a lock for kid+chore combination.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Returns:
            asyncio.Lock for this kid+chore pair
        """
        lock_key = f"{kid_id}:{chore_id}"
        if lock_key not in self._approval_locks:
            self._approval_locks[lock_key] = asyncio.Lock()
        return self._approval_locks[lock_key]

    def _validate_kid_and_chore(self, kid_id: str, chore_id: str) -> None:
        """Validate kid and chore exist.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Raises:
            HomeAssistantError: If either entity not found
        """
        if chore_id not in self._coordinator.chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        if kid_id not in self._coordinator.kids_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

    def _get_kid_chore_data(self, kid_id: str, chore_id: str) -> dict[str, Any]:
        """Get or create kid's chore data entry.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Returns:
            The kid_chore_data dict for this kid+chore
        """
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chores: dict[str, dict[str, Any]] = kid_info.setdefault(
            const.DATA_KID_CHORE_DATA, {}
        )

        if chore_id not in kid_chores:
            kid_chores[chore_id] = {
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                const.DATA_KID_CHORE_DATA_TOTAL_POINTS: 0.0,
                const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
            }

        return kid_chores[chore_id]

    def _is_approved_in_period(self, kid_id: str, chore_id: str) -> bool:
        """Check if chore is already approved in current period.

        Delegates to coordinator's existing method.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Returns:
            True if already approved in current period
        """
        # Delegate to coordinator's existing implementation
        return self._coordinator.chore_is_approved_in_period(kid_id, chore_id)

    def _all_kids_approved(self, chore_id: str, assigned_kids: list[str]) -> bool:
        """Check if all assigned kids have approved the chore.

        Used for SHARED chores to determine if immediate reset should trigger.
        Only triggers reset when ALL kids have reached APPROVED state.

        Args:
            chore_id: The chore's internal ID
            assigned_kids: List of assigned kid IDs

        Returns:
            True if all kids have approved state, False otherwise
        """
        if not assigned_kids:
            return False

        for kid_id in assigned_kids:
            if not kid_id:
                continue
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )
            if state != const.CHORE_STATE_APPROVED:
                return False

        return True

    def _is_approval_after_reset_boundary(
        self,
        chore_data: ChoreData,
        kid_id: str,
    ) -> bool:
        """Check if approval is happening after the reset boundary has passed.

        For AT_MIDNIGHT types: Due date must be before last midnight
        For AT_DUE_DATE types: Current time must be past the due date

        This is used for immediate_on_late functionality - when a chore is
        approved "late", it immediately resets to PENDING instead of waiting
        for the scheduled reset.

        Args:
            chore_data: The chore's data dict
            kid_id: The kid's internal ID

        Returns:
            True if approval is "late" (after reset boundary), False otherwise.
        """
        approval_reset_type = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.DEFAULT_APPROVAL_RESET_TYPE,
        )

        now_utc = dt_util.utcnow()

        # AT_MIDNIGHT types: Check if due date was before last midnight
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        ):
            # Get due date (per-kid for INDEPENDENT, chore-level for SHARED)
            completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_data.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_data.get(const.DATA_CHORE_DUE_DATE)

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
            completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_data.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_date_str = per_kid_due_dates.get(kid_id)
            else:
                due_date_str = chore_data.get(const.DATA_CHORE_DUE_DATE)

            if not due_date_str:
                return False

            due_date = kh.dt_to_utc(due_date_str)
            if not due_date:
                return False

            return now_utc > due_date

        return False

    def _apply_effect(self, effect: TransitionEffect, chore_id: str) -> None:
        """Apply a single TransitionEffect to coordinator data.

        Args:
            effect: The effect to apply
            chore_id: The chore's internal ID
        """
        kid_id = effect.kid_id
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Apply state change
        if effect.new_state:
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = effect.new_state

            # Manage completed_by_other_chores list for backward compatibility
            # Sensors check this list for COMPLETED_BY_OTHER state display
            completed_by_other_list = kid_info.setdefault(
                const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
            )
            if effect.new_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
                # Add to list if not already present
                if chore_id not in completed_by_other_list:
                    completed_by_other_list.append(chore_id)
            # Remove from list if transitioning to any other state
            elif chore_id in completed_by_other_list:
                completed_by_other_list.remove(chore_id)

        # Apply points (store in total_points field)
        if effect.points is not None:
            kid_chore_data[const.DATA_KID_CHORE_DATA_TOTAL_POINTS] = effect.points

        # Clear claimed_by
        if effect.clear_claimed_by:
            kid_chore_data.pop(const.DATA_CHORE_CLAIMED_BY, None)

        # Clear completed_by
        if effect.clear_completed_by:
            kid_chore_data.pop(const.DATA_CHORE_COMPLETED_BY, None)

        # Set claimed_by
        if effect.set_claimed_by:
            kid_chore_data[const.DATA_CHORE_CLAIMED_BY] = effect.set_claimed_by

        # Set completed_by
        if effect.set_completed_by:
            kid_chore_data[const.DATA_CHORE_COMPLETED_BY] = effect.set_completed_by

    def _update_global_state(self, chore_id: str) -> None:
        """Update the chore-level global state based on all assigned kids' states.

        This mirrors the logic from coordinator's _transition_chore_state to ensure
        the chore-level state (chores_data[chore_id][DATA_CHORE_STATE]) is consistent
        with the per-kid states (kid_chore_data[chore_id][DATA_KID_CHORE_DATA_STATE]).

        Args:
            chore_id: The chore's internal ID
        """
        chore_data = self._coordinator.chores_data.get(chore_id)
        if not chore_data:
            return

        assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        if not assigned_kids:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN
            return

        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_SHARED
        )

        # Single kid - use their state directly
        if len(assigned_kids) == 1:
            kid_chore_data = self._get_kid_chore_data(assigned_kids[0], chore_id)
            state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )
            chore_data[const.DATA_CHORE_STATE] = state
            return

        # Multiple kids - count states
        count_pending = 0
        count_claimed = 0
        count_approved = 0
        count_overdue = 0
        count_completed_by_other = 0

        for kid_id in assigned_kids:
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )

            if state == const.CHORE_STATE_APPROVED:
                count_approved += 1
            elif state == const.CHORE_STATE_CLAIMED:
                count_claimed += 1
            elif state == const.CHORE_STATE_OVERDUE:
                count_overdue += 1
            elif state == const.CHORE_STATE_COMPLETED_BY_OTHER:
                count_completed_by_other += 1
            else:
                count_pending += 1

        total = len(assigned_kids)

        # If all kids are in the same state
        if count_pending == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING
        elif count_claimed == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED
        elif count_approved == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED
        elif count_overdue == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE

        # SHARED_FIRST: global state tracks the claimant's progression
        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            if count_approved > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED
            elif count_claimed > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED
            elif count_overdue > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
            else:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING

        # SHARED: partial states
        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            if count_overdue > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
            elif count_approved > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED_IN_PART
            elif count_claimed > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED_IN_PART
            else:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN

        # INDEPENDENT: multiple kids with different states
        else:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_INDEPENDENT

    def _raise_claim_error(
        self, kid_id: str, chore_id: str, error_key: str | None
    ) -> None:
        """Raise appropriate HomeAssistantError for claim failure.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            error_key: The translation key for the error

        Raises:
            HomeAssistantError: With appropriate translation
        """
        chore_data = self._coordinator.chores_data[chore_id]
        chore_name = chore_data.get(const.DATA_CHORE_NAME, "")

        if error_key == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER:
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            claimed_by = kid_chore_data.get(const.DATA_CHORE_CLAIMED_BY, "another kid")
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

        # Default: already approved
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_ALREADY_CLAIMED,
            translation_placeholders={"entity": chore_name},
        )

    def _increment_pending_count(self, kid_id: str, chore_id: str) -> None:
        """Increment pending claim counter for kid+chore.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0)
        kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = current + 1

    def _decrement_pending_count(self, kid_id: str, chore_id: str) -> None:
        """Decrement pending claim counter for kid+chore.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0)
        kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current - 1
        )

    def _set_claimed_completed_by(
        self,
        chore_id: str,
        kid_id: str,
        field: str,
        value: str,
    ) -> None:
        """Set claimed_by or completed_by field.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID
            field: DATA_CHORE_CLAIMED_BY or DATA_CHORE_COMPLETED_BY
            value: The kid name to set
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        kid_chore_data[field] = value

    def _clear_claimed_completed_by(
        self,
        chore_id: str,
        kid_id: str,
        field: str,
    ) -> None:
        """Clear claimed_by or completed_by field.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID
            field: DATA_CHORE_CLAIMED_BY or DATA_CHORE_COMPLETED_BY
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        kid_chore_data.pop(field, None)

    def _handle_completion_criteria(
        self,
        chore_id: str,
        kid_id: str,
        completing_kid_name: str,
    ) -> None:
        """Handle completed_by based on chore completion criteria.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid who completed
            completing_kid_name: Name of the completing kid
        """
        chore_data = self._coordinator.chores_data[chore_id]
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # Store in kid's own chore data
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_CHORE_COMPLETED_BY] = completing_kid_name

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Update other kids' completed_by
            for other_kid_id in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if other_kid_id == kid_id:
                    continue
                other_chore_data = self._get_kid_chore_data(other_kid_id, chore_id)
                other_chore_data[const.DATA_CHORE_COMPLETED_BY] = completing_kid_name

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            # Append to list for all assigned kids
            for assigned_kid_id in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                assigned_chore_data = self._get_kid_chore_data(
                    assigned_kid_id, chore_id
                )

                # Initialize as list if needed
                if (
                    const.DATA_CHORE_COMPLETED_BY not in assigned_chore_data
                    or not isinstance(
                        assigned_chore_data.get(const.DATA_CHORE_COMPLETED_BY), list
                    )
                ):
                    assigned_chore_data[const.DATA_CHORE_COMPLETED_BY] = []

                # Append if not already present
                completed_list = assigned_chore_data[const.DATA_CHORE_COMPLETED_BY]
                if (
                    isinstance(completed_list, list)
                    and completing_kid_name not in completed_list
                ):
                    completed_list.append(completing_kid_name)

    def _reset_approval_period(self, kid_id: str, chore_id: str) -> None:
        """Reset the approval period tracking for a kid+chore.

        Sets approval_period_start to current time, which marks the start of a new
        approval period. The chore_is_approved_in_period() check compares:
            last_approved >= approval_period_start

        So after calling this, if last_approved was from before now, the chore
        becomes claimable again because it's not approved in the current period.

        For INDEPENDENT chores: stores approval_period_start in kid_chore_data
        For SHARED chores: stores at chore level

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        from custom_components.kidschores import kc_helpers as kh

        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return

        now_iso = kh.dt_now_iso()
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_SHARED
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Store per-kid approval_period_start in kid_chore_data
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = now_iso
        else:
            # SHARED/SHARED_FIRST: Store at chore level
            chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso

    def _update_chore_stats(
        self,
        kid_id: str,
        stat_type: str,
        points: float = 0.0,
    ) -> None:
        """Update kid's chore statistics for approval/disapproval/claim events.

        Args:
            kid_id: The kid's internal ID
            stat_type: One of 'approved', 'disapproved', 'claimed'
            points: Points to add for 'approved' stat type (default 0.0)
        """
        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        chore_stats = kid_info.setdefault(const.DATA_KID_CHORE_STATS, {})

        # Mapping stat_type to the all-time counter key
        stat_key_map = {
            "approved": const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME,
            "disapproved": const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME,
            "claimed": const.DATA_KID_CHORE_STATS_CLAIMED_ALL_TIME,
        }

        key = stat_key_map.get(stat_type)
        if key:
            chore_stats[key] = chore_stats.get(key, 0) + 1

        # For approvals, also track points
        if stat_type == "approved" and points > 0:
            points_key = const.DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_ALL_TIME
            chore_stats[points_key] = chore_stats.get(points_key, 0.0) + points

    def _reschedule_due_dates_upon_completion(
        self, chore_id: str, assigned_kids: list[str]
    ) -> None:
        """Reschedule due dates after UPON_COMPLETION approval.

        For INDEPENDENT chores, reschedules each kid's due date separately.
        For SHARED chores, reschedules the chore-level due date.

        Args:
            chore_id: The chore's internal ID
            assigned_kids: List of assigned kid IDs
        """
        chore_data = self._coordinator.chores_data.get(chore_id)
        if not chore_data:
            return

        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Reschedule per-kid due dates
            for kid_id in assigned_kids:
                if kid_id:
                    self._coordinator._reschedule_chore_next_due_date_for_kid(
                        chore_data, chore_id, kid_id
                    )
        else:
            # SHARED: Reschedule chore-level due date (affects all kids uniformly)
            # Use coordinator's method for shared chore rescheduling
            self._coordinator._reschedule_chore_next_due(chore_data)

    def _reset_kid_chore_to_pending(self, kid_id: str, chore_id: str) -> None:
        """Reset a single kid's chore state to PENDING.

        Used for UPON_COMPLETION reset type after approval.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = const.CHORE_STATE_PENDING

        # Clear claimed_by and completed_by for fresh cycle
        kid_chore_data.pop(const.DATA_CHORE_CLAIMED_BY, None)
        kid_chore_data.pop(const.DATA_CHORE_COMPLETED_BY, None)

        # Reset approval period for new cycle
        kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = None
