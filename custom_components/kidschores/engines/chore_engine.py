"""Chore Engine - Pure logic for chore state transitions and calculations.

This engine provides stateless, pure Python functions for:
- State transition validation and calculation
- TransitionEffect planning for multi-kid scenarios
- Point calculations with multipliers
- Completion criteria logic (SHARED, INDEPENDENT, SHARED_FIRST)
- Query functions for chore status checks

ARCHITECTURE: This is a pure logic engine with NO Home Assistant dependencies.
All functions are static methods that operate on passed-in data.
State management belongs in ChoreManager.

See docs/ARCHITECTURE.md for the Engine vs Manager distinction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import const
from ..utils.dt_utils import dt_parse_duration, dt_to_utc

if TYPE_CHECKING:
    from datetime import datetime

    from ..type_defs import ChoreData, KidData, ScheduleConfig


# =============================================================================
# CHORE ACTION CONSTANTS
# =============================================================================

# Actions that can be performed on a chore (used by calculate_transition)
CHORE_ACTION_CLAIM = "claim"
CHORE_ACTION_APPROVE = "approve"
CHORE_ACTION_DISAPPROVE = "disapprove"
CHORE_ACTION_UNDO = "undo"
CHORE_ACTION_RESET = "reset"
CHORE_ACTION_OVERDUE = "overdue"


# =============================================================================
# TRANSITION EFFECT DATA STRUCTURE
# =============================================================================


@dataclass
class TransitionEffect:
    """Effect of a chore state transition for a single kid.

    Returned by ChoreEngine.calculate_transition() to describe
    what should happen for each affected kid.

    Attributes:
        kid_id: The kid affected by this transition
        new_state: Target chore state for this kid
        update_stats: Whether this transition counts toward stats (streaks, totals)
                     True for normal actions, False for undo/corrections
        points: Points to award (positive) or deduct (negative), 0 for no change
        clear_claimed_by: Whether to clear claimed_by field
        clear_completed_by: Whether to clear completed_by field
        set_claimed_by: Name to set as claimed_by (or None)
        set_completed_by: Name to set as completed_by (or None)
    """

    kid_id: str
    new_state: str
    update_stats: bool = True
    points: float = 0.0
    clear_claimed_by: bool = False
    clear_completed_by: bool = False
    set_claimed_by: str | None = None
    set_completed_by: str | None = None


# =============================================================================
# CHORE ENGINE
# =============================================================================


class ChoreEngine:
    """Pure logic engine for chore state transitions and calculations.

    All methods are static - no instance state. This enables easy unit testing
    without any Home Assistant mocking.
    """

    # Valid state transitions matrix
    VALID_TRANSITIONS: dict[str, list[str]] = {
        # From PENDING: Can be claimed, go overdue, or completed by other
        const.CHORE_STATE_PENDING: [
            const.CHORE_STATE_CLAIMED,
            const.CHORE_STATE_OVERDUE,
            const.CHORE_STATE_COMPLETED_BY_OTHER,
        ],
        # From CLAIMED: Awaiting parent decision
        const.CHORE_STATE_CLAIMED: [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_PENDING,  # Disapproved or undo
            const.CHORE_STATE_OVERDUE,  # Due date passed while claimed
        ],
        # From APPROVED: Reset for next occurrence
        const.CHORE_STATE_APPROVED: [
            const.CHORE_STATE_PENDING,  # Scheduled reset
        ],
        # From OVERDUE: Can still be claimed or reset
        const.CHORE_STATE_OVERDUE: [
            const.CHORE_STATE_CLAIMED,  # Kid claims overdue chore
            const.CHORE_STATE_PENDING,  # Manual/scheduled reset
            const.CHORE_STATE_APPROVED,  # Parent completes on behalf
        ],
        # From COMPLETED_BY_OTHER: Reset at scheduled time
        const.CHORE_STATE_COMPLETED_BY_OTHER: [
            const.CHORE_STATE_PENDING,  # Scheduled reset
        ],
        # Global states (multi-kid aggregation)
        const.CHORE_STATE_CLAIMED_IN_PART: [
            const.CHORE_STATE_APPROVED_IN_PART,
            const.CHORE_STATE_CLAIMED,
            const.CHORE_STATE_PENDING,
        ],
        const.CHORE_STATE_APPROVED_IN_PART: [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_PENDING,
        ],
    }

    # =========================================================================
    # STATE TRANSITION LOGIC
    # =========================================================================

    @staticmethod
    def can_transition(current_state: str, target_state: str) -> bool:
        """Validate if a state transition is allowed.

        Args:
            current_state: Current chore state
            target_state: Desired new state

        Returns:
            True if transition is valid, False otherwise
        """
        valid_targets = ChoreEngine.VALID_TRANSITIONS.get(current_state, [])
        return target_state in valid_targets

    @staticmethod
    def calculate_transition(
        chore_data: ChoreData | dict[str, Any],
        actor_kid_id: str,
        action: str,
        kids_assigned: list[str],
        kid_name: str = "Unknown",
        skip_stats: bool = False,
    ) -> list[TransitionEffect]:
        """Calculate transition effects for ALL kids based on ONE action.

        This is the core planning method. It determines what state changes
        and side effects should occur for each assigned kid when one kid
        performs an action.

        Args:
            chore_data: The chore being acted upon
            actor_kid_id: The kid performing the action
            action: One of CHORE_ACTION_* values
            kids_assigned: All kids assigned to this chore
            kid_name: Display name of actor kid (for claimed_by/completed_by)
            skip_stats: If True, mark effects as update_stats=False

        Returns:
            List of TransitionEffect describing changes for each affected kid
        """
        effects: list[TransitionEffect] = []
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        points = float(chore_data.get(const.DATA_CHORE_DEFAULT_POINTS, 0.0))

        # === CLAIM ACTION ===
        if action == CHORE_ACTION_CLAIM:
            effects = ChoreEngine._plan_claim_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
                kid_name,
            )

        # === APPROVE ACTION ===
        elif action == CHORE_ACTION_APPROVE:
            effects = ChoreEngine._plan_approve_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
                kid_name,
                points,
            )

        # === DISAPPROVE ACTION ===
        elif action == CHORE_ACTION_DISAPPROVE:
            effects = ChoreEngine._plan_disapprove_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
            )

        # === UNDO ACTION ===
        elif action == CHORE_ACTION_UNDO:
            effects = ChoreEngine._plan_undo_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
            )
            # Undo never updates stats
            skip_stats = True

        # === RESET ACTION (scheduled) ===
        elif action == CHORE_ACTION_RESET:
            effects = ChoreEngine._plan_reset_effects(kids_assigned)

        # === OVERDUE ACTION ===
        elif action == CHORE_ACTION_OVERDUE:
            effects.append(
                TransitionEffect(
                    kid_id=actor_kid_id,
                    new_state=const.CHORE_STATE_OVERDUE,
                    update_stats=True,
                )
            )

        # Apply skip_stats flag if set
        if skip_stats:
            for effect in effects:
                effect.update_stats = False

        return effects

    @staticmethod
    def _plan_claim_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
        kid_name: str,
    ) -> list[TransitionEffect]:
        """Plan effects for a claim action."""
        effects: list[TransitionEffect] = []

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Actor claims, others become completed_by_other
            effects.append(
                TransitionEffect(
                    kid_id=actor_kid_id,
                    new_state=const.CHORE_STATE_CLAIMED,
                    update_stats=True,
                    set_claimed_by=kid_name,
                )
            )
            for other_kid_id in kids_assigned:
                if other_kid_id != actor_kid_id:
                    effects.append(
                        TransitionEffect(
                            kid_id=other_kid_id,
                            new_state=const.CHORE_STATE_COMPLETED_BY_OTHER,
                            update_stats=False,
                            set_claimed_by=kid_name,
                        )
                    )
        else:
            # INDEPENDENT or SHARED: Only actor transitions
            effects.append(
                TransitionEffect(
                    kid_id=actor_kid_id,
                    new_state=const.CHORE_STATE_CLAIMED,
                    update_stats=True,
                    set_claimed_by=kid_name,
                )
            )

        return effects

    @staticmethod
    def _plan_approve_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
        kid_name: str,
        points: float,
    ) -> list[TransitionEffect]:
        """Plan effects for an approve action."""
        effects: list[TransitionEffect] = []

        effects.append(
            TransitionEffect(
                kid_id=actor_kid_id,
                new_state=const.CHORE_STATE_APPROVED,
                update_stats=True,
                points=points,
                set_completed_by=kid_name,
            )
        )

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Update completed_by for other kids (who are in completed_by_other state)
            for other_kid_id in kids_assigned:
                if other_kid_id != actor_kid_id:
                    effects.append(
                        TransitionEffect(
                            kid_id=other_kid_id,
                            new_state=const.CHORE_STATE_COMPLETED_BY_OTHER,
                            update_stats=False,
                            set_completed_by=kid_name,
                        )
                    )

        return effects

    @staticmethod
    def _plan_disapprove_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
    ) -> list[TransitionEffect]:
        """Plan effects for a disapprove action."""
        effects: list[TransitionEffect] = []

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Reset ALL kids to pending
            for kid_id in kids_assigned:
                effects.append(
                    TransitionEffect(
                        kid_id=kid_id,
                        new_state=const.CHORE_STATE_PENDING,
                        update_stats=(kid_id == actor_kid_id),  # Only actor gets stat
                        clear_claimed_by=True,
                        clear_completed_by=True,
                    )
                )
        else:
            # INDEPENDENT or SHARED: Only actor transitions
            effects.append(
                TransitionEffect(
                    kid_id=actor_kid_id,
                    new_state=const.CHORE_STATE_PENDING,
                    update_stats=True,
                )
            )

        return effects

    @staticmethod
    def _plan_undo_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
    ) -> list[TransitionEffect]:
        """Plan effects for an undo (kid self-undo) action."""
        effects: list[TransitionEffect] = []

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Reset ALL kids to pending (same as disapproval)
            for kid_id in kids_assigned:
                effects.append(
                    TransitionEffect(
                        kid_id=kid_id,
                        new_state=const.CHORE_STATE_PENDING,
                        update_stats=False,  # Undo never updates stats
                        clear_claimed_by=True,
                        clear_completed_by=True,
                    )
                )
        else:
            effects.append(
                TransitionEffect(
                    kid_id=actor_kid_id,
                    new_state=const.CHORE_STATE_PENDING,
                    update_stats=False,
                )
            )

        return effects

    @staticmethod
    def _plan_reset_effects(kids_assigned: list[str]) -> list[TransitionEffect]:
        """Plan effects for a scheduled reset."""
        return [
            TransitionEffect(
                kid_id=kid_id,
                new_state=const.CHORE_STATE_PENDING,
                update_stats=False,
                clear_claimed_by=True,
                clear_completed_by=True,
            )
            for kid_id in kids_assigned
        ]

    # =========================================================================
    # VALIDATION LOGIC
    # =========================================================================

    @staticmethod
    def can_claim_chore(
        kid_chore_data: dict[str, Any],
        chore_data: ChoreData | dict[str, Any],
        has_pending_claim: bool,
        is_approved_in_period: bool,
    ) -> tuple[bool, str | None]:
        """Check if a kid can claim a specific chore.

        Args:
            kid_chore_data: The kid's tracking data for this chore
            chore_data: The chore definition
            has_pending_claim: Result of chore_has_pending_claim()
            is_approved_in_period: Result of chore_is_approved_in_period()

        Returns:
            Tuple of (can_claim: bool, error_key: str | None)
        """
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all claims
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Check multi-claim allowed
        allow_multiple = ChoreEngine.chore_allows_multiple_claims(chore_data)

        # Check 2: pending claim blocks new claims (unless multi-claim)
        if not allow_multiple and has_pending_claim:
            return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)

        # Check 3: already approved in current period (unless multi-claim)
        if not allow_multiple and is_approved_in_period:
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    @staticmethod
    def can_approve_chore(
        kid_chore_data: dict[str, Any],
        chore_data: ChoreData | dict[str, Any],
        is_approved_in_period: bool,
    ) -> tuple[bool, str | None]:
        """Check if a chore can be approved for a specific kid.

        Args:
            kid_chore_data: The kid's tracking data for this chore
            chore_data: The chore definition
            is_approved_in_period: Result of chore_is_approved_in_period()

        Returns:
            Tuple of (can_approve: bool, error_key: str | None)
        """
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all approvals
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Check 2: already approved (unless multi-claim)
        allow_multiple = ChoreEngine.chore_allows_multiple_claims(chore_data)
        if not allow_multiple and is_approved_in_period:
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    # =========================================================================
    # QUERY FUNCTIONS
    # =========================================================================

    @staticmethod
    def chore_has_pending_claim(
        kid_chore_data: dict[str, Any],
    ) -> bool:
        """Check if a chore has a pending claim.

        Uses the pending_count counter which is incremented on claim and
        decremented on approve/disapprove.
        """
        pending_count = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        return pending_count > 0

    @staticmethod
    def chore_is_overdue(
        kid_chore_data: dict[str, Any],
    ) -> bool:
        """Check if a chore is in overdue state for a specific kid."""
        current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
        return current_state == const.CHORE_STATE_OVERDUE

    @staticmethod
    def chore_allows_multiple_claims(chore_data: ChoreData | dict[str, Any]) -> bool:
        """Check if chore allows multiple claims per approval period."""
        approval_reset_type = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        return approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        )

    @staticmethod
    def is_shared_chore(chore_data: ChoreData | dict[str, Any]) -> bool:
        """Check if chore uses shared completion criteria."""
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        return criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        )

    @staticmethod
    def get_chore_data_for_kid(
        kid_data: KidData | dict[str, Any],
        chore_id: str,
    ) -> dict[str, Any]:
        """Get the chore data dict for a specific kid+chore combination."""
        chore_tracking = kid_data.get(const.DATA_KID_CHORE_DATA, {})
        return (
            chore_tracking.get(chore_id, {}) if isinstance(chore_tracking, dict) else {}
        )

    # =========================================================================
    # DUE DATE & SCHEDULING QUERIES
    # =========================================================================

    @staticmethod
    def get_due_date_for_kid(
        chore_data: ChoreData | dict[str, Any],
        kid_id: str | None,
    ) -> str | None:
        """Get the due date ISO string for a chore, handling completion criteria.

        For SHARED/SHARED_FIRST chores: Returns chore-level due date.
        For INDEPENDENT chores: Returns per-kid due date if kid_id provided.
        If kid_id is None: Always returns chore-level due date.

        Args:
            chore_data: The chore definition
            kid_id: The kid's internal ID, or None for chore-level due date

        Returns:
            ISO timestamp string of due date, or None if not configured.
        """
        if kid_id is None:
            # No kid specified - use chore-level due date
            return chore_data.get(const.DATA_CHORE_DUE_DATE)

        # Check completion criteria
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Use per-kid due dates
            per_kid_due_dates = chore_data.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            return per_kid_due_dates.get(kid_id)

        # SHARED or SHARED_FIRST: Use chore-level due date
        return chore_data.get(const.DATA_CHORE_DUE_DATE)

    @staticmethod
    def chore_is_due(
        due_date_iso: str | None,
        due_window_offset_str: str | None,
        now: datetime,
    ) -> bool:
        """Check if a chore is in the due window (approaching due date).

        A chore is in the due window if:
        - It has a due_window_offset > 0 configured
        - Current time is within: (due_date - due_window_offset) <= now < due_date
        - This method only checks timing, not chore state

        Args:
            due_date_iso: ISO timestamp of the due date, or None
            due_window_offset_str: Duration string like "1d 6h 30m", or None
            now: Current UTC datetime

        Returns:
            True if the chore is in the due window, False otherwise.
        """

        if not due_date_iso:
            return False

        # Parse due window offset
        due_window_td = dt_parse_duration(due_window_offset_str)
        if not due_window_td or due_window_td.total_seconds() <= 0:
            return False

        # Parse due date
        due_date_dt = dt_to_utc(due_date_iso)
        if not due_date_dt:
            return False

        # Calculate due window start
        due_window_start = due_date_dt - due_window_td

        # In due window if: due_window_start <= now < due_date
        return due_window_start <= now < due_date_dt

    @staticmethod
    def get_due_window_start(
        due_date_iso: str | None,
        due_window_offset_str: str | None,
    ) -> datetime | None:
        """Calculate when the due window starts for a chore.

        Returns the datetime when the due window begins (due_date - offset),
        or None if the chore has no due date or no due window configured.
        Returns None if due window offset is 0 (disabled).

        Args:
            due_date_iso: ISO timestamp of the due date, or None
            due_window_offset_str: Duration string like "1d 6h 30m", or None

        Returns:
            datetime when due window starts, or None if not applicable.
        """

        if not due_date_iso:
            return None

        # Parse due window offset
        due_window_td = dt_parse_duration(due_window_offset_str)
        if not due_window_td or due_window_td.total_seconds() <= 0:
            return None

        # Parse due date
        due_date_dt = dt_to_utc(due_date_iso)
        if not due_date_dt:
            return None

        return due_date_dt - due_window_td

    @staticmethod
    def is_approved_in_period(
        kid_chore_data: dict[str, Any],
        period_start_iso: str | None,
    ) -> bool:
        """Check if a chore is already approved in the current approval period.

        A chore is considered approved in the current period if:
        - last_approved timestamp exists, AND EITHER:
          a. period_start doesn't exist (chore was never reset, approval is valid), OR
          b. last_approved >= period_start

        Args:
            kid_chore_data: The kid's tracking data for this chore
            period_start_iso: ISO timestamp of approval period start, or None

        Returns:
            True if approved in current period, False otherwise.
        """

        last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if not last_approved:
            return False

        if not period_start_iso:
            # No period_start means chore was never reset after being created.
            # Since last_approved exists (checked above), the approval is still valid.
            return True

        approved_dt = dt_to_utc(last_approved)
        period_start_dt = dt_to_utc(period_start_iso)

        if approved_dt is None or period_start_dt is None:
            return False

        return approved_dt >= period_start_dt

    # =========================================================================
    # POINT CALCULATIONS
    # =========================================================================

    @staticmethod
    def calculate_points(
        chore_data: ChoreData | dict[str, Any],
        multiplier: float = 1.0,
    ) -> float:
        """Calculate points for chore completion with optional multiplier.

        Args:
            chore_data: The chore definition
            multiplier: Point multiplier (default 1.0)

        Returns:
            Calculated points, rounded to DATA_FLOAT_PRECISION
        """
        base_points = float(
            chore_data.get(const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS)
        )
        result = base_points * multiplier
        return round(result, const.DATA_FLOAT_PRECISION)

    # =========================================================================
    # GLOBAL STATE CALCULATION
    # =========================================================================

    @staticmethod
    def compute_global_chore_state(
        chore_data: ChoreData | dict[str, Any],
        kid_states: dict[str, str],
    ) -> str:
        """Compute the aggregate chore state from per-kid states.

        Args:
            chore_data: The chore definition
            kid_states: Dict mapping kid_id to their current state

        Returns:
            The global chore state string
        """
        if not kid_states:
            return const.CHORE_STATE_UNKNOWN

        assigned_kids = list(kid_states.keys())
        total = len(assigned_kids)

        if total == 1:
            return next(iter(kid_states.values()))

        # Count states
        count_pending = sum(
            1 for s in kid_states.values() if s == const.CHORE_STATE_PENDING
        )
        count_claimed = sum(
            1 for s in kid_states.values() if s == const.CHORE_STATE_CLAIMED
        )
        count_approved = sum(
            1 for s in kid_states.values() if s == const.CHORE_STATE_APPROVED
        )
        count_overdue = sum(
            1 for s in kid_states.values() if s == const.CHORE_STATE_OVERDUE
        )

        # All same state
        if count_pending == total:
            return const.CHORE_STATE_PENDING
        if count_claimed == total:
            return const.CHORE_STATE_CLAIMED
        if count_approved == total:
            return const.CHORE_STATE_APPROVED
        if count_overdue == total:
            return const.CHORE_STATE_OVERDUE

        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # SHARED_FIRST: Global state tracks the claimant's progression
        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            if count_approved > 0:
                return const.CHORE_STATE_APPROVED
            if count_claimed > 0:
                return const.CHORE_STATE_CLAIMED
            if count_overdue > 0:
                return const.CHORE_STATE_OVERDUE
            return const.CHORE_STATE_PENDING

        # SHARED: Partial states
        if criteria == const.COMPLETION_CRITERIA_SHARED:
            if count_overdue > 0:
                return const.CHORE_STATE_OVERDUE
            if count_approved > 0:
                return const.CHORE_STATE_APPROVED_IN_PART
            if count_claimed > 0:
                return const.CHORE_STATE_CLAIMED_IN_PART
            return const.CHORE_STATE_UNKNOWN

        # INDEPENDENT: Different states
        return const.CHORE_STATE_INDEPENDENT

    # =========================================================================
    # STREAK CALCULATION (Schedule-Aware)
    # =========================================================================

    @staticmethod
    def calculate_streak(
        current_streak: int,
        previous_last_completed_iso: str | None,
        current_work_date_iso: str,
        chore_data: ChoreData | dict[str, Any],
    ) -> int:
        """Calculate new streak value based on schedule-aware logic.

        Must be called BEFORE updating last_completed timestamp, using the
        previous value to determine if the schedule gap was missed.

        Args:
            current_streak: The streak value from the previous day (or 0)
            previous_last_completed_iso: ISO timestamp of LAST completion (work date)
            current_work_date_iso: ISO timestamp of THIS completion (effective_date)
            chore_data: Chore definition containing frequency/schedule info

        Returns:
            New streak value: 1 if first completion or streak broken,
                             current_streak + 1 if on-time
        """
        from custom_components.kidschores.engines.schedule_engine import (
            RecurrenceEngine,
        )

        # First completion ever = streak of 1
        if not previous_last_completed_iso:
            return 1

        # Get schedule configuration from chore
        frequency = chore_data.get(
            const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        )

        # No schedule (manual/one-time chore) = simple daily logic
        if frequency == const.FREQUENCY_NONE:
            # Check if previous completion was yesterday (simple streak)
            prev_dt = dt_to_utc(previous_last_completed_iso)
            current_dt = dt_to_utc(current_work_date_iso)
            if prev_dt and current_dt:
                days_diff = (current_dt.date() - prev_dt.date()).days
                if days_diff <= 1:
                    return current_streak + 1
            return 1  # Broke streak

        # Build schedule config for RecurrenceEngine
        applicable_days = chore_data.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
        # Convert day names to integers if needed (RecurrenceEngine expects ints)
        day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        applicable_days_int: list[int] = []
        for d in applicable_days:
            if isinstance(d, str):
                day_int = day_map.get(d.lower())
                if day_int is not None:
                    applicable_days_int.append(day_int)
            elif isinstance(d, int):
                applicable_days_int.append(d)

        # Build config dict - use explicit values to satisfy type checker
        interval_raw = chore_data.get(const.DATA_CHORE_CUSTOM_INTERVAL)
        interval_unit_raw = chore_data.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT)
        daily_multi_raw = chore_data.get(const.DATA_CHORE_DAILY_MULTI_TIMES)

        schedule_config: ScheduleConfig = {
            "frequency": str(frequency),
            "interval": int(interval_raw) if interval_raw else 1,
            "interval_unit": str(interval_unit_raw)
            if interval_unit_raw
            else const.TIME_UNIT_DAYS,
            "base_date": previous_last_completed_iso,
            "applicable_days": applicable_days_int,
            "daily_multi_times": str(daily_multi_raw) if daily_multi_raw else "",
        }

        try:
            engine = RecurrenceEngine(schedule_config)

            # Parse timestamps to datetime for engine
            prev_dt = dt_to_utc(previous_last_completed_iso)
            current_dt = dt_to_utc(current_work_date_iso)

            if not prev_dt or not current_dt:
                return 1  # Can't calculate, reset streak

            # Check if any scheduled occurrences were missed
            if engine.has_missed_occurrences(prev_dt, current_dt):
                return 1  # Broke streak

            return current_streak + 1  # On-time, continue streak

        except Exception:
            # If schedule calculation fails, fallback to simple daily logic
            return 1
