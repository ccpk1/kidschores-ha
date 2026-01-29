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
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .. import const, data_builders as db
from ..engines.chore_engine import (
    CHORE_ACTION_APPROVE,
    CHORE_ACTION_CLAIM,
    CHORE_ACTION_DISAPPROVE,
    CHORE_ACTION_OVERDUE,
    CHORE_ACTION_RESET,
    CHORE_ACTION_UNDO,
    ChoreEngine,
    TransitionEffect,
)
from ..engines.schedule_engine import calculate_next_due_date_from_chore_info
from ..engines.statistics_engine import filter_persistent_stats
from ..helpers.entity_helpers import (
    remove_entities_by_item_id,
    remove_orphaned_kid_chore_entities,
    remove_orphaned_shared_chore_sensors,
)
from ..utils.dt_utils import (
    dt_add_interval,
    dt_format_short,
    dt_now_iso,
    dt_parse_duration,
    dt_to_utc,
    dt_today_local,
)
from .base_manager import BaseManager

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import ChoreData, KidChoreDataEntry, KidData
    from .economy_manager import EconomyManager


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

        Subscribes to cross-domain events for cleanup coordination.
        """
        # Listen for kid deletion to remove orphaned assignments
        self.listen(const.SIGNAL_SUFFIX_KID_DELETED, self._on_kid_deleted)
        const.LOGGER.debug("ChoreManager initialized for entry %s", self.entry_id)

    def _on_kid_deleted(self, payload: dict[str, Any]) -> None:
        """Remove deleted kid from all chore assignments.

        Follows Platinum Architecture (Choreography): ChoreManager reacts
        to KID_DELETED signal and cleans its own domain data (chore assignments).

        Args:
            payload: Event data containing kid_id
        """
        kid_id = payload.get("kid_id", "")
        if not kid_id:
            return

        # Clean own domain: remove deleted kid from chore assigned_kids
        chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
        cleaned = False
        for chore_info in chores_data.values():
            assigned_kids = chore_info.get(const.DATA_ASSIGNED_KIDS, [])
            if kid_id in assigned_kids:
                chore_info[const.DATA_ASSIGNED_KIDS] = [
                    k for k in assigned_kids if k != kid_id
                ]
                const.LOGGER.debug(
                    "Removed deleted kid %s from chore '%s' assigned_kids",
                    kid_id,
                    chore_info.get(const.DATA_CHORE_NAME),
                )
                cleaned = True

        if cleaned:
            self._coordinator._persist()
            const.LOGGER.debug(
                "ChoreManager: Cleaned chore assignments for deleted kid %s",
                kid_id,
            )

    # =========================================================================
    # §1 WORKFLOW METHODS (public API)
    # =========================================================================

    async def claim_chore(
        self,
        kid_id: str,
        chore_id: str,
        user_name: str,
    ) -> None:
        """Process a chore claim request with race condition protection.

        Uses asyncio.Lock to ensure only one claim processes at a time
        per kid+chore combination, preventing duplicate claims.

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            user_name: Who initiated the claim (for notification context)

        Raises:
            HomeAssistantError: If claim validation fails
        """
        # Acquire lock for this kid+chore pair
        lock = self._get_lock(kid_id, chore_id)
        async with lock:
            await self._claim_chore_locked(kid_id, chore_id, user_name)

    async def _claim_chore_locked(
        self,
        kid_id: str,
        chore_id: str,
        user_name: str,
    ) -> None:
        """Internal claim logic executed under lock protection.

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
        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = dt_now_iso()

        # Clear notification tracking (allows fresh notifications for next period)
        self.clear_chore_notifications(chore_id, kid_id)

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

    async def undo_chore(
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
                await self._economy_manager.withdraw(
                    kid_id=kid_id,
                    amount=previous_points,
                    source=const.POINTS_SOURCE_OTHER,  # "other" for corrections
                    reference_id=chore_id,
                )
            except Exception:
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

    async def reset_chore(
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
        # force_update=True ensures SHARED/SHARED_FIRST chore-level approval_period_start
        # is updated even if already set, invalidating previous approvals
        if reset_approval_period:
            self._reset_approval_period(kid_id, chore_id, force_update=True)

        # Emit status reset event
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_STATUS_RESET,
            kid_id=kid_id,
            chore_id=chore_id,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
        )

        # Clear notification tracking (both due window and reminder)
        self.clear_chore_notifications(chore_id, kid_id)

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    async def mark_overdue(
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
                self.chore_has_pending_claim(kid_id, chore_id)
                or self.chore_is_approved_in_period(kid_id, chore_id)
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
                if self.chore_has_pending_claim(kid_id, chore_id):
                    continue
                if self.chore_is_approved_in_period(kid_id, chore_id):
                    continue

                # SHARED_FIRST special handling
                if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
                    # Find if there's a claimant
                    claimant_kid_id = next(
                        (
                            k
                            for k in assigned_kids
                            if self.chore_has_pending_claim(k, chore_id)
                        ),
                        None,
                    )
                    # If someone else claimed, skip this kid
                    if claimant_kid_id and kid_id != claimant_kid_id:
                        continue

                # Get effective due date
                due_str = self.get_chore_effective_due_date(chore_id, kid_id)
                if not due_str:
                    continue

                # Parse due date
                due_date_utc = dt_to_utc(due_str)
                if due_date_utc is None:
                    continue

                # Check if past due
                if now_utc <= due_date_utc:
                    continue

                # Calculate days overdue
                days_overdue = (now_utc - due_date_utc).days

                # Mark as overdue via Manager method (emits event)
                try:
                    await self.mark_overdue(
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

        # Delegate rescheduling (handles SHARED vs INDEPENDENT)
        await self._reschedule_recurring_chores(now)

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
                reset_count += await self._reset_independent_chore(
                    chore_id, chore_info, now_utc
                )
            else:
                # SHARED: Use chore-level due date
                reset_count += await self._reset_shared_chore(
                    chore_id, chore_info, now_utc
                )

        const.LOGGER.debug(
            "ChoreManager.update_recurring_chores - Completed, reset %d chores",
            reset_count,
        )

        return reset_count

    async def _reset_daily_chore_statuses(
        self,
        target_freqs: list[str],
    ) -> int:
        """Reset chore statuses for chores matching target frequencies.

        This method is primarily used by tests to directly trigger resets
        for specific frequencies without time-based checks.

        Args:
            target_freqs: List of frequency constants to reset (e.g., [FREQUENCY_DAILY])

        Returns:
            Count of chores reset.
        """
        reset_count = 0
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
                reset_count += await self._reset_independent_chore(
                    chore_id, chore_info, now_utc
                )
            else:
                reset_count += await self._reset_shared_chore(
                    chore_id, chore_info, now_utc
                )

        # Mark pending changed for UI updates
        self._coordinator._pending_chore_changed = True
        self._coordinator._persist()

        return reset_count

    async def _handle_pending_chore_claim_at_reset(
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
            # Award points directly via EconomyManager (mimics approval without full workflow)
            await self._coordinator.economy_manager.deposit(
                kid_id=kid_id,
                amount=chore_points,
                source=const.POINTS_SOURCE_CHORES,
                apply_multiplier=True,
            )

        # CLEAR (default) or after AUTO_APPROVE: Clear pending_claim_count
        if kid_chore_data:
            kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

        return False  # Continue with reset

    async def _reset_shared_chore(
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
            due_date_utc = dt_to_utc(due_date_str)
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

            # Get kid chore data for pending claim handling
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

            # Handle pending claims before reset
            if await self._handle_pending_chore_claim_at_reset(
                kid_id, chore_id, chore_info, kid_chore_data
            ):
                continue  # HOLD action - skip reset for this kid

            try:
                await self.reset_chore(
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

    async def _reset_independent_chore(
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
            due_str = self.get_chore_effective_due_date(chore_id, kid_id)
            if due_str:
                due_date_utc = dt_to_utc(due_str)
                if due_date_utc is None:
                    continue
                if now_utc < due_date_utc:
                    continue  # Not yet due for this kid

            # Check if chore needs reset using timestamp-based checks (Option A)
            # A chore needs reset if any of these are true:
            # - Approved in current period (needs to become claimable again)
            # - Has pending claim (needs claim handling)
            # - Is overdue (needs overdue status cleared for AT_DUE_DATE_THEN_RESET)
            is_approved = self.chore_is_approved_in_period(kid_id, chore_id)
            has_pending_claim = self.chore_has_pending_claim(kid_id, chore_id)
            is_overdue = self.chore_is_overdue(kid_id, chore_id)
            if not is_approved and not has_pending_claim and not is_overdue:
                continue  # Already in pending state - no reset needed

            # Handle pending claims before reset
            # Use _get_kid_chore_data for mutable access
            mutable_kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            if await self._handle_pending_chore_claim_at_reset(
                kid_id, chore_id, chore_info, mutable_kid_chore_data
            ):
                continue  # HOLD action - skip reset for this kid

            try:
                await self.reset_chore(
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

    async def set_due_date(
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
                    await self.reset_chore(
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

    async def skip_due_date(self, chore_id: str, kid_id: str | None = None) -> None:
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

                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                await self.reset_chore(kid_id, chore_id, reset_approval_period=True)
            else:
                # Skip all assigned kids
                self._reschedule_chore_next_due(chore_info)
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    if (
                        assigned_kid_id
                        and assigned_kid_id in self._coordinator.kids_data
                    ):
                        self._reschedule_chore_next_due_date_for_kid(
                            chore_info, chore_id, assigned_kid_id
                        )
                        await self.reset_chore(
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
            self._reschedule_chore_next_due(chore_info)
            for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if assigned_kid_id and assigned_kid_id in self._coordinator.kids_data:
                    await self.reset_chore(
                        assigned_kid_id, chore_id, reset_approval_period=True
                    )

        const.LOGGER.info(
            "Skipped due date for chore '%s'",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    async def reset_all_chores(self) -> None:
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
                        await self.reset_chore(
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

    async def reset_overdue_chores(
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
                await self.reset_chore(kid_id, chore_id, reset_approval_period=True)
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
            else:
                # SHARED or INDEPENDENT without kid
                self._reschedule_chore_next_due(chore_info)

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
                    if self.chore_is_overdue(kid_id, chore_id_iter):
                        criteria = chore_info.get(
                            const.DATA_CHORE_COMPLETION_CRITERIA,
                            const.COMPLETION_CRITERIA_SHARED,
                        )

                        await self.reset_chore(
                            kid_id, chore_id_iter, reset_approval_period=True
                        )

                        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                            self._reschedule_chore_next_due_date_for_kid(
                                chore_info, chore_id_iter, kid_id
                            )
        else:
            # Global reset: Reset all overdue chores for all kids
            for kid_id_iter in self._coordinator.kids_data:
                for chore_id_iter, chore_info in self._coordinator.chores_data.items():
                    if kid_id_iter in chore_info.get(
                        const.DATA_CHORE_ASSIGNED_KIDS, []
                    ):
                        if self.chore_is_overdue(kid_id_iter, chore_id_iter):
                            criteria = chore_info.get(
                                const.DATA_CHORE_COMPLETION_CRITERIA,
                                const.COMPLETION_CRITERIA_SHARED,
                            )

                            await self.reset_chore(
                                kid_id_iter, chore_id_iter, reset_approval_period=True
                            )

                            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                                self._reschedule_chore_next_due_date_for_kid(
                                    chore_info, chore_id_iter, kid_id_iter
                                )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    async def undo_claim(self, kid_id: str, chore_id: str) -> None:
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
        kid_chore_entry = self._get_kid_chore_data(kid_id, chore_id)
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
                # Clear claimed_by/completed_by using helper
                other_kid_info: KidData | dict[str, Any] = (
                    self._coordinator.kids_data.get(other_kid_id, {})
                )
                other_kid_chore = ChoreEngine.get_chore_data_for_kid(
                    other_kid_info, chore_id
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
    # §1.55 CRUD METHODS (Manager-owned create/update/delete)
    # =========================================================================
    # These methods own the write operations for chore entities.
    # Called by options_flow.py and services.py - they must NOT write directly.

    def create_chore(
        self,
        user_input: dict[str, Any],
        internal_id: str | None = None,
        prebuilt: bool = False,
    ) -> dict[str, Any]:
        """Create a new chore in storage.

        Args:
            user_input: Chore data with DATA_* keys.
            internal_id: Optional pre-generated UUID (for form resubmissions).
            prebuilt: If True, user_input is already a complete ChoreData dict.

        Returns:
            Complete ChoreData dict ready for use.

        Emits:
            SIGNAL_SUFFIX_CHORE_CREATED with chore_id and chore_name.
        """
        # Build complete chore data structure (or use pre-built)
        if prebuilt:
            chore_data = dict(user_input)
        else:
            chore_data = dict(db.build_chore(user_input))

        # Override internal_id if provided (for form resubmission consistency)
        if internal_id:
            chore_data[const.DATA_CHORE_INTERNAL_ID] = internal_id

        final_id = str(chore_data[const.DATA_CHORE_INTERNAL_ID])
        chore_name = str(chore_data.get(const.DATA_CHORE_NAME, ""))

        # Store in coordinator data
        self._coordinator._data[const.DATA_CHORES][final_id] = chore_data
        self._coordinator._persist()
        self._coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_CREATED,
            chore_id=final_id,
            chore_name=chore_name,
        )

        const.LOGGER.info(
            "Created chore '%s' (ID: %s)",
            chore_name,
            final_id,
        )

        return chore_data

    def update_chore(self, chore_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update an existing chore in storage.

        Args:
            chore_id: Internal UUID of the chore to update.
            updates: Partial chore data with DATA_* keys to merge.

        Returns:
            Updated ChoreData dict.

        Raises:
            HomeAssistantError: If chore not found.

        Emits:
            SIGNAL_SUFFIX_CHORE_UPDATED with chore_id and chore_name.
        """
        chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
        if chore_id not in chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        existing = chores_data[chore_id]
        # Build updated chore (merge existing with updates)
        updated_chore = dict(db.build_chore(updates, existing=existing))

        # Store updated chore
        self._coordinator._data[const.DATA_CHORES][chore_id] = updated_chore

        # NOTE: Badge recalculation is handled by GamificationManager via
        # SIGNAL_SUFFIX_CHORE_UPDATED event (Platinum Architecture: event-driven)

        self._coordinator._persist()
        self._coordinator.async_update_listeners()

        # Clean up any orphaned kid-chore entities after assignment changes
        self._coordinator.hass.async_create_task(
            remove_orphaned_kid_chore_entities(
                self.hass,
                self._coordinator.config_entry.entry_id,
                self._coordinator.kids_data,
                self._coordinator.chores_data,
            )
        )

        chore_name = str(updated_chore.get(const.DATA_CHORE_NAME, ""))

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            chore_id=chore_id,
            chore_name=chore_name,
        )

        const.LOGGER.debug(
            "Updated chore '%s' (ID: %s)",
            chore_name,
            chore_id,
        )

        return updated_chore

    def delete_chore(self, chore_id: str) -> None:
        """Delete a chore from storage and cleanup references.

        Follows Platinum Architecture (Choreography over Orchestration):
        - ChoreManager cleans its own domain data (kid chore_data)
        - Emits CHORE_DELETED signal for cross-domain cleanup
        - GamificationManager reacts to signal for achievement/challenge cleanup
        - SystemManager reacts to signal for entity registry cleanup

        Args:
            chore_id: Internal UUID of the chore to delete.

        Raises:
            HomeAssistantError: If chore not found.

        Emits:
            SIGNAL_SUFFIX_CHORE_DELETED with chore_id and chore_name.
        """
        chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
        if chore_id not in chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        chore_info = chores_data[chore_id]
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
        # Capture assigned_kids before deletion for notification cleanup
        assigned_kids = list(chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []))

        # Delete from storage
        del self._coordinator._data[const.DATA_CHORES][chore_id]

        # Remove HA entities (targeted cleanup)
        remove_entities_by_item_id(
            self.hass,
            self._coordinator.config_entry.entry_id,
            chore_id,
        )

        # Clean own domain: remove deleted chore refs from kid chore_data
        # (This is chore-tracking data that lives in kid records)
        for kid_data in self._coordinator.kids_data.values():
            kid_chore_data = kid_data.get(const.DATA_KID_CHORE_DATA, {})
            if chore_id in kid_chore_data:
                del kid_chore_data[chore_id]
                const.LOGGER.debug("Removed chore '%s' from kid chore_data", chore_id)

        # Remove orphaned shared chore sensors
        self.hass.async_create_task(
            remove_orphaned_shared_chore_sensors(
                self.hass,
                self._coordinator.config_entry.entry_id,
                self._coordinator.chores_data,
            )
        )

        self._coordinator._persist()
        self._coordinator.async_update_listeners()

        # Emit lifecycle event (triggers GamificationManager, SystemManager, NotificationManager)
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_DELETED,
            chore_id=chore_id,
            chore_name=chore_name,
            assigned_kids=assigned_kids,
        )

        const.LOGGER.info(
            "Deleted chore '%s' (ID: %s)",
            chore_name,
            chore_id,
        )

    # =========================================================================
    # §1.6 QUERY METHODS (read-only state queries)
    # =========================================================================
    # These methods provide chore state queries used by sensors and dashboards.
    # They are read-only and do not modify state.

    def _get_chore_approval_period_start(
        self, kid_id: str, chore_id: str
    ) -> str | None:
        """Get the start of the current approval period for this kid+chore.

        For SHARED chores: Uses chore-level approval_period_start
        For INDEPENDENT chores: Uses per-kid approval_period_start in kid_chore_data

        Returns:
            ISO timestamp string of period start, or None if not set.
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return None

        # Default to INDEPENDENT if completion_criteria not set (backward compatibility)
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Period start is per-kid in kid_chore_data
            kid_data: KidData | dict[str, Any] = self._coordinator.kids_data.get(
                kid_id, {}
            )
            kid_chore_data = ChoreEngine.get_chore_data_for_kid(kid_data, chore_id)
            return kid_chore_data.get(const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START)
        # SHARED/SHARED_FIRST/etc.: Period start is at chore level
        return chore_info.get(const.DATA_CHORE_APPROVAL_PERIOD_START)

    def chore_has_pending_claim(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore has a pending claim (claimed but not yet approved/disapproved).

        Uses the pending_count counter which is incremented on claim and
        decremented on approve/disapprove.

        Returns:
            True if there's a pending claim (pending_claim_count > 0), False otherwise.
        """
        kid_data: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})
        kid_chore_data = ChoreEngine.get_chore_data_for_kid(kid_data, chore_id)
        if not kid_chore_data:
            return False

        pending_claim_count = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        return pending_claim_count > 0

    def chore_is_overdue(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is in overdue state for a specific kid.

        Uses the per-kid chore state field (single source of truth).

        Returns:
            True if the chore is in overdue state, False otherwise.
        """
        kid_data: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})
        kid_chore_data = ChoreEngine.get_chore_data_for_kid(kid_data, chore_id)
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

        Args:
            kid_id: The internal ID of the kid, or None to use chore-level due date.
            chore_id: The internal ID of the chore.

        Returns:
            True if the chore is in the due window, False otherwise.
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return False

        # Get due window offset (stored as duration string like "1d 6h 30m")
        due_window_offset_str = chore_info.get(
            const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
        )
        due_window_td = dt_parse_duration(cast("str | None", due_window_offset_str))

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

        due_date_dt = dt_to_utc(due_date_str)
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
        chore_info = self._coordinator.chores_data.get(chore_id)
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

        return dt_to_utc(due_date_str)

    def get_chore_due_window_start(
        self, kid_id: str | None, chore_id: str
    ) -> datetime | None:
        """Calculate when the due window starts for a chore.

        Returns the datetime when the due window begins (due_date - offset),
        or None if the chore has no due date or no due window configured.

        Args:
            kid_id: The internal ID of the kid. If None, uses the chore-level
                due date (appropriate for SHARED chores or global sensor).
            chore_id: The internal ID of the chore.

        Returns:
            datetime when due window starts, or None if not applicable.
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return None

        # Get due window offset - returns None if offset is "0" or missing
        due_window_offset_str = chore_info.get(
            const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
        )
        due_window_td = dt_parse_duration(cast("str | None", due_window_offset_str))

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
        - last_approved timestamp exists, AND
        - approval_period_start exists, AND
        - last_approved >= approval_period_start

        When approval_period_start is None, the chore has been reset to pending
        (e.g., UPON_COMPLETION reset), so return False.

        Returns:
            True if approved in current period, False otherwise.
        """
        kid_data: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})
        kid_chore_data = ChoreEngine.get_chore_data_for_kid(kid_data, chore_id)
        if not kid_chore_data:
            return False

        last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if not last_approved:
            return False

        period_start = self._get_chore_approval_period_start(kid_id, chore_id)
        if not period_start:
            # approval_period_start is None when chore has been reset to pending
            # (e.g., UPON_COMPLETION reset). Return False to indicate not approved.
            return False

        approved_dt = dt_to_utc(last_approved)
        period_start_dt = dt_to_utc(period_start)

        if approved_dt is None or period_start_dt is None:
            return False

        return approved_dt >= period_start_dt

    def get_pending_chore_approvals(self) -> list[dict[str, Any]]:
        """Compute pending chore approvals dynamically from timestamp data.

        A chore has a pending approval if pending_claim_count > 0.

        Returns:
            List of dicts with keys: kid_id, chore_id, timestamp
        """
        pending: list[dict[str, Any]] = []
        for kid_id, kid_info in self._coordinator.kids_data.items():
            chore_data_map = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            for chore_id, chore_entry in chore_data_map.items():
                # Skip chores that no longer exist
                if chore_id not in self._coordinator.chores_data:
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
        """Return the list of pending chore approvals (computed from timestamps)."""
        return self.get_pending_chore_approvals()

    @property
    def pending_chore_changed(self) -> bool:
        """Return whether pending chore approvals have changed since last reset."""
        return self._coordinator._pending_chore_changed

    def count_chores_pending_for_kid(self, kid_id: str) -> int:
        """Count total pending chores awaiting approval for a specific kid.

        Used for tag-based notification aggregation (v0.5.0+) to show
        "Sarah: 3 chores pending" instead of individual notifications.

        Args:
            kid_id: The internal ID of the kid.

        Returns:
            Number of chores with pending claims for this kid.
        """
        count = 0
        kid_info: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        for chore_id in chore_data:
            # Skip chores that no longer exist
            if chore_id not in self._coordinator.chores_data:
                continue
            if self.chore_has_pending_claim(kid_id, chore_id):
                count += 1

        return count

    def can_claim_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
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

    def can_approve_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
        """Check if a chore can be approved for a specific kid.

        This helper is dual-purpose: used for approval validation AND for providing
        status information to the dashboard helper sensor.

        Checks (in order):
        1. completed_by_other - Another kid already completed (SHARED_FIRST mode)
        2. already_approved - Already approved in current period (if not multi-claim)

        Note: Unlike can_claim_chore, this does NOT check for pending claims because
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

    def get_chore_effective_due_date(
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
        chore_info: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and kid_id:
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            return per_kid_due_dates.get(kid_id)

        return chore_info.get(const.DATA_CHORE_DUE_DATE)

    def clear_chore_notifications(self, chore_id: str, kid_id: str) -> None:
        """Clear ALL notification tracking for a chore+kid combination (v0.6.0+).

        Clears both due window and due reminder tracking to allow fresh
        notifications in next period.

        Called when:
        - Chore claimed
        - Chore approved/disapproved
        - Chore skipped
        - Chore reset

        Args:
            chore_id: The chore internal ID
            kid_id: The kid internal ID
        """
        reminder_key = f"{chore_id}:{kid_id}"
        self._coordinator._due_window_notif_sent.discard(reminder_key)
        self._coordinator._due_reminder_notif_sent.discard(reminder_key)

    def recalculate_chore_stats_for_kid(self, kid_id: str) -> None:
        """Delegate chore stats aggregation to StatisticsEngine.

        This method aggregates all kid_chore_stats for a given kid by
        delegating to the StatisticsEngine, which owns the period data
        structure knowledge.

        Note: Only persistent stats (all_time, highest, etc.) are written to
        storage. Temporal stats (today/week/month) live in the presentation
        cache (Phase 7.5 Architecture).

        Args:
            kid_id: The internal ID of the kid.
        """
        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            return
        stats = self._coordinator.stats.generate_chore_stats(
            kid_info, self._coordinator.chores_data
        )
        # Only persist non-temporal stats (Phase 7.5: temporal lives in cache)
        kid_info[const.DATA_KID_CHORE_STATS] = filter_persistent_stats(stats)

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
        chore_info: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )
        approval_reset_type = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        return approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        )

    def get_chore_data_for_kid(
        self, kid_id: str, chore_id: str
    ) -> KidChoreDataEntry | dict[str, Any]:
        """Get the chore data dict for a specific kid+chore combination.

        Returns an empty dict if the kid or chore data doesn't exist.
        """
        kid_info: KidData = cast("KidData", self._coordinator.kids_data.get(kid_id, {}))
        return kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})

    def is_chore_approval_after_reset(self, chore_info: ChoreData, kid_id: str) -> bool:
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

            due_date = dt_to_utc(due_date_str)
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

            due_date = dt_to_utc(due_date_str)
            if not due_date:
                return False

            return now_utc > due_date

        return False

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

        previous_last_approved = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_LAST_APPROVED
        )

        # Get yesterday's streak for continuation check
        today_iso = dt_today_local().isoformat()
        yesterday_iso = dt_add_interval(
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
        now_iso = dt_now_iso()

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
                # Set kid-level approval_period_start for INDEPENDENT
                # Use FRESH timestamp to ensure it's AFTER last_approved
                reset_period_start = dt_now_iso()
                kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
                kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    reset_period_start
                )
                self._update_global_state(chore_id)
                self._reschedule_due_dates_upon_completion(chore_id, [kid_id])

            # SHARED/SHARED_FIRST: Only reset when ALL assigned kids have approved
            elif self._all_kids_approved(chore_id, kids_assigned):
                # Set chore-level approval_period_start ONCE for SHARED/SHARED_FIRST
                # Use FRESH timestamp to ensure it's AFTER last_approved
                reset_period_start = dt_now_iso()
                chore_data[const.DATA_CHORE_APPROVAL_PERIOD_START] = reset_period_start
                for assigned_kid_id in kids_assigned:
                    if assigned_kid_id:
                        self._reset_kid_chore_to_pending(assigned_kid_id, chore_id)
                self._update_global_state(chore_id)
                self._reschedule_due_dates_upon_completion(chore_id, kids_assigned)
        # For non-UPON_COMPLETION reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*):
        # Do NOT set approval_period_start here. It is ONLY set on RESET events.
        # The chore remains approved until the scheduled reset updates approval_period_start.
        # approval_period_start was set at: initial creation, or last reset.
        # last_approved was just set above, so:
        #   is_approved = (last_approved >= approval_period_start) = True

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

        # Clear notification tracking (both due window and reminder)
        self.clear_chore_notifications(chore_id, kid_id)

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

        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = dt_now_iso()

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

        # Clear notification tracking (both due window and reminder)
        self.clear_chore_notifications(chore_id, kid_id)

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
            default_data: dict[str, Any] = {
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                const.DATA_KID_CHORE_DATA_TOTAL_POINTS: 0.0,
                const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
            }
            # Only set kid-level approval_period_start for INDEPENDENT chores
            # SHARED chores use chore-level approval_period_start instead
            chore_info: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
                chore_id, {}
            )
            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                default_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    dt_now_iso()
                )
            kid_chores[chore_id] = default_data

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
        return self.chore_is_approved_in_period(kid_id, chore_id)

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

            due_date = dt_to_utc(due_date_str)
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

            due_date = dt_to_utc(due_date_str)
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

    def _reset_approval_period(
        self,
        kid_id: str,
        chore_id: str,
        timestamp: str | None = None,
        *,
        force_update: bool = False,
    ) -> None:
        """Reset the approval period tracking for a kid+chore.

        Sets approval_period_start to mark the start of a new approval period.
        The chore_is_approved_in_period() check compares:
            last_approved >= approval_period_start

        So after calling this, if last_approved was from before the period start,
        the chore becomes claimable again because it's not approved in the current period.

        For INDEPENDENT chores: stores approval_period_start in kid_chore_data
        For SHARED chores: stores at chore level

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            timestamp: Optional timestamp to use. If None, uses current time.
                      Pass same timestamp as last_approved to ensure consistency.
            force_update: If True, always update approval_period_start even if
                         already set. Use this for scheduled resets.
                         If False (default), only set if not already set
                         (for tracking first approval in period).
        """

        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return

        now_iso = timestamp if timestamp else dt_now_iso()
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_SHARED
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Store per-kid approval_period_start in kid_chore_data
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = now_iso
        # SHARED/SHARED_FIRST: Store at chore level
        # Only set if not already set OR force_update is True
        # - force_update=False (default): preserves period start for all kids
        #   when multiple kids are approved in the same period
        # - force_update=True: used by scheduled resets to invalidate previous approvals
        elif force_update or not chore_info.get(const.DATA_CHORE_APPROVAL_PERIOD_START):
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
                    self._reschedule_chore_next_due_date_for_kid(
                        chore_data, chore_id, kid_id
                    )
        else:
            # SHARED: Reschedule chore-level due date (affects all kids uniformly)
            # Use coordinator's method for shared chore rescheduling
            self._reschedule_chore_next_due(chore_data)

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

        # NOTE: Does NOT set approval_period_start here.
        # Caller handles this based on completion criteria:
        # - INDEPENDENT: caller sets kid-level approval_period_start
        # - SHARED/SHARED_FIRST: caller sets chore-level approval_period_start ONCE

    # =========================================================================
    # §4 SCHEDULING METHODS (due date rescheduling)
    # =========================================================================
    # Handle due date recalculation after approvals and scheduled resets.
    # Called from workflow methods and timer-driven operations.

    def _transition_chore_state(
        self,
        kid_id: str,
        chore_id: str,
        new_state: str,
        *,
        reset_approval_period: bool = False,
    ) -> None:
        """Minimal state transition for scheduling operations.

        This is a simplified version for scheduling reset operations.
        For full workflow transitions, use the workflow methods (claim, approve, etc.)

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            new_state: The new state to set (typically PENDING for resets)
            reset_approval_period: If True, sets a new approval_period_start
        """
        kid_info = self._coordinator.kids_data.get(kid_id)
        chore_info = self._coordinator.chores_data.get(chore_id)

        if not kid_info or not chore_info:
            return

        # Get or initialize kid chore data
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Update state
        kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = new_state

        # Clear pending claim count on reset
        if new_state == const.CHORE_STATE_PENDING:
            kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

            if reset_approval_period:
                now_iso = dt_now_iso()
                completion_criteria = chore_info.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
                )
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                        now_iso
                    )
                else:
                    chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso

        # Clear overdue notification tracking
        if new_state != const.CHORE_STATE_OVERDUE:
            overdue_notifs = kid_info.get(const.DATA_KID_OVERDUE_NOTIFICATIONS, {})
            if chore_id in overdue_notifs:
                overdue_notifs.pop(chore_id)
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = overdue_notifs

        # Flag pending changes for UI refresh
        self._coordinator._pending_chore_changed = True

    def _reschedule_chore_next_due(self, chore_info: ChoreData) -> None:
        """Reschedule chore's next due date (chore-level for SHARED chores)."""
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        if not due_date_str:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Skipping (no due date for %s)",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Parse current due date
        original_due_utc = dt_to_utc(due_date_str)
        if not original_due_utc:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Unable to parse due date for %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Extract completion timestamp for CUSTOM_FROM_COMPLETE
        completion_utc = None
        last_completed_str = chore_info.get(const.DATA_CHORE_LAST_COMPLETED)
        if last_completed_str:
            completion_utc = dt_to_utc(last_completed_str)

        # Use schedule engine for calculation
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
        approval_reset = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )
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

        Updates DATA_CHORE_PER_KID_DUE_DATES[kid_id].
        Used for INDEPENDENT chores (each kid has own due date).
        """
        kid_info: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})

        # Get per-kid current due date
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        current_due_str = per_kid_due_dates.get(kid_id)

        if not current_due_str:
            const.LOGGER.debug(
                "Chore Due Date - No due date for chore %s, kid %s; preserving None",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # Parse current due date
        try:
            original_due_utc = dt_to_utc(current_due_str)
        except (ValueError, TypeError, AttributeError):
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Unable to parse due date for %s, kid %s",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # Extract per-kid completion timestamp
        completion_utc = None
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        last_approved_str = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if last_approved_str:
            completion_utc = dt_to_utc(last_approved_str)

        # Build chore info for calculation with per-kid overrides
        chore_info_for_calc = dict(chore_info)
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

        # Use schedule engine
        next_due_utc = calculate_next_due_date_from_chore_info(
            original_due_utc,
            cast("ChoreData", chore_info_for_calc),
            completion_timestamp=completion_utc,
            reference_time=dt_util.utcnow(),
        )
        if not next_due_utc:
            const.LOGGER.warning(
                "Chore Due Date - Reschedule: Failed to calculate next due for %s, kid %s",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            return

        # Update per-kid storage
        per_kid_due_dates[kid_id] = next_due_utc.isoformat()
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

        # Only reset to PENDING for UPON_COMPLETION type
        approval_reset = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_info.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )
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
            "Chore Due Date - Rescheduled (INDEPENDENT): chore %s, kid %s, to %s",
            chore_info.get(const.DATA_CHORE_NAME),
            kid_info.get(const.DATA_KID_NAME),
            dt_util.as_local(next_due_utc).isoformat() if next_due_utc else "None",
        )

    async def _reschedule_recurring_chores(self, now: Any) -> None:
        """Reschedule recurring chores that are approved and past due.

        Handles both SHARED and INDEPENDENT completion criteria:
        - SHARED: Uses chore-level due_date and state
        - INDEPENDENT: Uses per_kid_due_dates and per-kid state

        Args:
            now: Current datetime (UTC)
        """
        for chore_id, chore_info in self._coordinator.chores_data.items():
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
                self._reschedule_independent_recurring_chore(chore_id, chore_info, now)
            else:
                self._reschedule_shared_recurring_chore(chore_id, chore_info, now)

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)
        const.LOGGER.debug(
            "Chore Rescheduling - Daily recurring chores rescheduling complete"
        )

    def _reschedule_shared_recurring_chore(
        self, chore_id: str, chore_info: ChoreData, now: Any
    ) -> None:
        """Reschedule a SHARED recurring chore if approved and past due."""
        if not chore_info.get(const.DATA_CHORE_DUE_DATE):
            return

        due_date_utc = dt_to_utc(chore_info.get(const.DATA_CHORE_DUE_DATE) or "")
        if due_date_utc is None:
            return

        # If the due date is in the past and the chore is approved
        if now > due_date_utc and chore_info.get(const.DATA_CHORE_STATE) in [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_APPROVED_IN_PART,
        ]:
            self._reschedule_chore_next_due(chore_info)
            const.LOGGER.debug(
                "Chore Rescheduling - Rescheduled recurring SHARED Chore '%s'",
                chore_info.get(const.DATA_CHORE_NAME, chore_id),
            )

    def _reschedule_independent_recurring_chore(
        self, chore_id: str, chore_info: ChoreData, now: Any
    ) -> None:
        """Reschedule INDEPENDENT recurring chore for each kid if approved and past due."""
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        for kid_id in assigned_kids:
            if not kid_id:
                continue

            kid_due_str = per_kid_due_dates.get(kid_id)
            if not kid_due_str:
                continue

            kid_due_utc = dt_to_utc(kid_due_str)
            if kid_due_utc is None:
                continue

            # Check per-kid state from kid's chore data
            kid_info: KidData | dict[str, Any] = self._coordinator.kids_data.get(
                kid_id, {}
            )
            kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(
                chore_id, {}
            )
            kid_state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )

            # If past due and approved, reschedule and reset
            if now > kid_due_utc and kid_state in [
                const.CHORE_STATE_APPROVED,
                const.CHORE_STATE_APPROVED_IN_PART,
            ]:
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                self._transition_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                )
                const.LOGGER.debug(
                    "Chore Rescheduling - Rescheduled INDEPENDENT Chore '%s' for kid '%s'",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

    # =========================================================================
    # §5 TIMER METHODS (recurring resets, overdue checks, due-soon reminders)
    # =========================================================================

    async def process_recurring_chore_resets(self, now: datetime) -> None:
        """Handle recurring resets for daily, weekly, and monthly frequencies.

        Called by coordinator timer registration (async_track_time_change).
        Delegates to update_recurring_chores which handles both:
        - Rescheduling due dates for approved recurring chores
        - Resetting chore statuses for daily/weekly/monthly frequencies

        Args:
            now: Current UTC datetime (passed by Home Assistant scheduler)
        """
        await self.update_recurring_chores(now)

    async def check_overdue_chores(self, now: datetime | None = None) -> None:
        """Check and mark overdue chores if due date is passed.

        Called by coordinator refresh cycle (_async_update_data) and daily timer.
        Delegates to update_overdue_status() for the actual processing.

        Args:
            now: Optional override for current time (uses UTC now if not provided)
        """
        # Delegate to the unified update_overdue_status method
        await self.update_overdue_status(now=now)

    async def check_chore_due_reminders(self) -> None:
        """Check for chores within due reminder window and send reminder notifications.

        Hooks into coordinator refresh cycle (typically every 5 min) to check for
        chores that are due within their configured reminder offset and haven't
        had reminders sent.

        Uses per-chore `due_reminder_offset` field (default "30m").
        Respects per-chore `notify_due_reminder` setting.

        Tracking uses coordinator's transient _due_reminder_notif_sent set.
        """
        from datetime import timedelta

        now_utc = dt_util.utcnow()
        reminders_sent = 0

        const.LOGGER.debug(
            "Due date reminders - Starting check at %s",
            now_utc.isoformat(),
        )

        for chore_id, chore_info in self._coordinator.chores_data.items():
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
                const.DATA_CHORE_NOTIFY_DUE_REMINDER, const.DEFAULT_NOTIFY_DUE_REMINDER
            ):
                continue

            # Get configurable reminder offset (replaces hardcoded 30 minutes)
            reminder_offset_str = chore_info.get(
                const.DATA_CHORE_DUE_REMINDER_OFFSET,
                const.DEFAULT_DUE_REMINDER_OFFSET,
            )
            reminder_offset = dt_parse_duration(cast("str | None", reminder_offset_str))
            if not reminder_offset or reminder_offset.total_seconds() <= 0:
                continue

            for kid_id in assigned_kids:
                # Build unique key for this chore+kid combination
                reminder_key = f"{chore_id}:{kid_id}"

                # Skip if already sent this reminder (transient tracking)
                if reminder_key in self._coordinator._due_reminder_notif_sent:
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
                due_dt = dt_to_utc(due_date_str)
                if due_dt is None:
                    continue

                time_until_due = due_dt - now_utc

                # Check: due within reminder offset AND not past due yet
                if timedelta(0) < time_until_due <= reminder_offset:
                    # Send due-soon reminder to kid with claim button
                    minutes_remaining = int(time_until_due.total_seconds() / 60)
                    chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown Chore")
                    points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0)

                    # Emit event for NotificationManager
                    self.emit(
                        const.SIGNAL_SUFFIX_CHORE_DUE_REMINDER,
                        kid_id=kid_id,
                        chore_id=chore_id,
                        chore_name=chore_name,
                        minutes=minutes_remaining,
                        points=points,
                    )

                    # Mark as sent (transient - resets on HA restart)
                    self._coordinator._due_reminder_notif_sent.add(reminder_key)
                    reminders_sent += 1

                    const.LOGGER.debug(
                        "Sent due-reminder notification for chore '%s' to kid '%s' (%d min remaining)",
                        chore_name,
                        kid_id,
                        minutes_remaining,
                    )

        if reminders_sent > 0:
            const.LOGGER.debug(
                "Due date reminders - Sent %d reminder(s)",
                reminders_sent,
            )

    async def check_chore_due_window_transitions(self) -> None:
        """Check for chores entering due window and send notifications (v0.6.0+).

        Hooks into coordinator refresh cycle to check for chores that have
        transitioned from PENDING to DUE state (entered their due window).

        Uses per-chore `due_window_offset` field to determine when due window starts.
        Respects per-chore `notify_on_due_window` setting.

        Tracking uses coordinator's transient _due_window_notif_sent set.
        """
        now_utc = dt_util.utcnow()
        notifications_sent = 0

        const.LOGGER.debug(
            "Due window transitions - Starting check at %s",
            now_utc.isoformat(),
        )

        for chore_id, chore_info in self._coordinator.chores_data.items():
            # Get assigned kids for this chore
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if not assigned_kids:
                continue

            # Skip if chore has due window notifications disabled
            if not chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW,
                const.DEFAULT_NOTIFY_ON_DUE_WINDOW,
            ):
                continue

            # Get due window offset
            due_window_offset_str = chore_info.get(
                const.DATA_CHORE_DUE_WINDOW_OFFSET,
                const.DEFAULT_DUE_WINDOW_OFFSET,
            )
            due_window_offset = dt_parse_duration(
                cast("str | None", due_window_offset_str)
            )
            if not due_window_offset or due_window_offset.total_seconds() <= 0:
                continue

            for kid_id in assigned_kids:
                # Build unique key for this chore+kid combination
                window_key = f"{chore_id}:{kid_id}"

                # Skip if already sent this notification
                if window_key in self._coordinator._due_window_notif_sent:
                    continue

                # Skip if kid already claimed or completed this chore
                if self.chore_has_pending_claim(kid_id, chore_id):
                    continue
                if self.chore_is_approved_in_period(kid_id, chore_id):
                    continue

                # Check if chore is in due window
                if self.chore_is_due(kid_id, chore_id):
                    # Calculate time remaining until due
                    due_dt = self.get_chore_due_date(kid_id, chore_id)
                    if not due_dt:
                        continue

                    time_until_due = due_dt - now_utc
                    hours_remaining = max(0, int(time_until_due.total_seconds() / 3600))

                    chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown Chore")
                    points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0)

                    # Emit event for NotificationManager
                    self.emit(
                        const.SIGNAL_SUFFIX_CHORE_DUE_WINDOW,
                        kid_id=kid_id,
                        chore_id=chore_id,
                        chore_name=chore_name,
                        hours=hours_remaining,
                        points=points,
                        due_date=due_dt.isoformat(),
                    )

                    # Mark as sent (transient - resets on HA restart)
                    self._coordinator._due_window_notif_sent.add(window_key)
                    notifications_sent += 1

                    const.LOGGER.debug(
                        "Sent due window notification for chore '%s' to kid '%s' (%d hrs remaining)",
                        chore_name,
                        kid_id,
                        hours_remaining,
                    )

        if notifications_sent > 0:
            const.LOGGER.debug(
                "Due window transitions - Sent %d notification(s)",
                notifications_sent,
            )

    def _check_chore_overdue_status(
        self,
        chore_id: str,
        chore_info: ChoreData,
        now_utc: datetime,
    ) -> None:
        """Check and apply overdue status for a chore (any completion criteria).

        Unified handler for INDEPENDENT, SHARED, and SHARED_FIRST completion criteria.

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
                kid_chore_data = ChoreEngine.get_chore_data_for_kid(
                    cast("KidData", self._coordinator.kids_data.get(kid_id, {})),
                    chore_id,
                )
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
            due_str = self.get_chore_effective_due_date(chore_id, kid_id)
            self._handle_overdue_chore_state(
                kid_id, chore_id, due_str, now_utc, chore_info
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

        Args:
            kid_id: The kid to check/mark overdue
            chore_id: The chore to check
            due_date_iso: ISO format due date string (or None if no due date)
            now_utc: Current UTC datetime for comparison
            chore_info: Chore info dict for notification context

        Returns:
            True if overdue was applied, False if not
        """
        kid_info: KidData = cast("KidData", self._coordinator.kids_data.get(kid_id, {}))

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
        due_date_utc = dt_to_utc(due_date_iso)
        if not due_date_utc:
            const.LOGGER.error(
                "Overdue Check - Error parsing due date '%s' for Chore '%s', Kid '%s'",
                due_date_iso,
                chore_info.get(const.DATA_CHORE_NAME, chore_id),
                kid_id,
            )
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

    def _notify_overdue_chore(
        self,
        kid_id: str,
        chore_id: str,
        chore_info: dict[str, Any],
        due_date_utc: datetime,
        now_utc: datetime,
    ) -> None:
        """Send overdue notification to kid and parents if not recently sent."""
        from datetime import timedelta

        kid_info: KidData = cast("KidData", self._coordinator.kids_data.get(kid_id, {}))

        # Check notification timestamp
        if const.DATA_KID_OVERDUE_NOTIFICATIONS not in kid_info:
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = {}

        overdue_notifs: dict[str, str] = kid_info.get(
            const.DATA_KID_OVERDUE_NOTIFICATIONS, {}
        )
        last_notif_str = overdue_notifs.get(chore_id)
        notify = False

        if last_notif_str:
            last_dt = dt_to_utc(last_notif_str)
            if (
                last_dt is None
                or (last_dt < due_date_utc)
                or (
                    (now_utc - last_dt)
                    >= timedelta(hours=const.DEFAULT_NOTIFY_DELAY_REMINDER)
                )
            ):
                notify = True
        else:
            notify = True

        if notify:
            overdue_notifs[chore_id] = now_utc.isoformat()
            kid_info[const.DATA_KID_OVERDUE_NOTIFICATIONS] = overdue_notifs

            # Get languages for date formatting
            kid_language = kid_info.get(
                const.DATA_KID_DASHBOARD_LANGUAGE, self.hass.config.language
            )

            # Emit event for NotificationManager
            self.emit(
                const.SIGNAL_SUFFIX_CHORE_OVERDUE,
                kid_id=kid_id,
                chore_id=chore_id,
                chore_name=chore_info.get(
                    const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                ),
                due_date=dt_format_short(due_date_utc, language=kid_language),
                kid_language=kid_language,
                parent_language=self.hass.config.language,
            )
