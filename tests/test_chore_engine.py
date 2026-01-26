"""Tests for ChoreEngine - pure logic, no HA fixtures needed.

These tests validate the ChoreEngine's pure Python functions without
requiring any Home Assistant mocking or integration setup.
"""

from __future__ import annotations

from custom_components.kidschores import const
from custom_components.kidschores.engines.chore_engine import (
    CHORE_ACTION_APPROVE,
    CHORE_ACTION_CLAIM,
    CHORE_ACTION_DISAPPROVE,
    CHORE_ACTION_OVERDUE,
    CHORE_ACTION_RESET,
    CHORE_ACTION_UNDO,
    ChoreEngine,
)

# =============================================================================
# TEST: STATE TRANSITION VALIDATION
# =============================================================================


class TestStateTransitions:
    """Test state transition validation."""

    def test_pending_to_claimed_allowed(self) -> None:
        """PENDING → CLAIMED is a valid transition."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_PENDING, const.CHORE_STATE_CLAIMED
        )

    def test_pending_to_overdue_allowed(self) -> None:
        """PENDING → OVERDUE is a valid transition."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_PENDING, const.CHORE_STATE_OVERDUE
        )

    def test_pending_to_completed_by_other_allowed(self) -> None:
        """PENDING → COMPLETED_BY_OTHER is valid (for SHARED_FIRST)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_PENDING, const.CHORE_STATE_COMPLETED_BY_OTHER
        )

    def test_claimed_to_approved_allowed(self) -> None:
        """CLAIMED → APPROVED is a valid transition."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_CLAIMED, const.CHORE_STATE_APPROVED
        )

    def test_claimed_to_pending_allowed(self) -> None:
        """CLAIMED → PENDING is valid (disapproval or undo)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_CLAIMED, const.CHORE_STATE_PENDING
        )

    def test_claimed_to_overdue_allowed(self) -> None:
        """CLAIMED → OVERDUE is valid (due date passed while claimed)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_CLAIMED, const.CHORE_STATE_OVERDUE
        )

    def test_approved_to_pending_allowed(self) -> None:
        """APPROVED → PENDING is valid (reset for recurrence)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_APPROVED, const.CHORE_STATE_PENDING
        )

    def test_approved_to_claimed_not_allowed(self) -> None:
        """APPROVED → CLAIMED is NOT valid."""
        assert not ChoreEngine.can_transition(
            const.CHORE_STATE_APPROVED, const.CHORE_STATE_CLAIMED
        )

    def test_overdue_to_claimed_allowed(self) -> None:
        """OVERDUE → CLAIMED is valid (kid claims overdue chore)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_OVERDUE, const.CHORE_STATE_CLAIMED
        )

    def test_overdue_to_approved_allowed(self) -> None:
        """OVERDUE → APPROVED is valid (parent completes on behalf)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_OVERDUE, const.CHORE_STATE_APPROVED
        )

    def test_completed_by_other_to_pending_allowed(self) -> None:
        """COMPLETED_BY_OTHER → PENDING is valid (scheduled reset)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_COMPLETED_BY_OTHER, const.CHORE_STATE_PENDING
        )

    def test_completed_by_other_to_claimed_not_allowed(self) -> None:
        """COMPLETED_BY_OTHER → CLAIMED is NOT valid."""
        assert not ChoreEngine.can_transition(
            const.CHORE_STATE_COMPLETED_BY_OTHER, const.CHORE_STATE_CLAIMED
        )

    def test_unknown_state_has_no_transitions(self) -> None:
        """UNKNOWN state has no valid outgoing transitions."""
        assert not ChoreEngine.can_transition(
            const.CHORE_STATE_UNKNOWN, const.CHORE_STATE_PENDING
        )


# =============================================================================
# TEST: CALCULATE_TRANSITION - CLAIM ACTION
# =============================================================================


class TestCalculateTransitionClaim:
    """Test transition effect planning for claim actions."""

    def test_claim_independent_affects_only_actor(self) -> None:
        """INDEPENDENT: Claim only affects the claiming kid."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_CLAIM,
            kids_assigned=["kid-1", "kid-2", "kid-3"],
            kid_name="Sarah",
        )

        assert len(effects) == 1
        assert effects[0].kid_id == "kid-1"
        assert effects[0].new_state == const.CHORE_STATE_CLAIMED
        assert effects[0].update_stats is True
        assert effects[0].set_claimed_by == "Sarah"

    def test_claim_shared_affects_only_actor(self) -> None:
        """SHARED: Claim only affects the claiming kid."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_CLAIM,
            kids_assigned=["kid-1", "kid-2"],
            kid_name="Sarah",
        )

        assert len(effects) == 1
        assert effects[0].kid_id == "kid-1"
        assert effects[0].new_state == const.CHORE_STATE_CLAIMED

    def test_claim_shared_first_affects_all_kids(self) -> None:
        """SHARED_FIRST: Claiming kid → CLAIMED, others → COMPLETED_BY_OTHER."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_CLAIM,
            kids_assigned=["kid-1", "kid-2", "kid-3"],
            kid_name="Sarah",
        )

        assert len(effects) == 3

        # Actor kid
        actor_effect = next(e for e in effects if e.kid_id == "kid-1")
        assert actor_effect.new_state == const.CHORE_STATE_CLAIMED
        assert actor_effect.update_stats is True
        assert actor_effect.set_claimed_by == "Sarah"

        # Other kids
        for kid_id in ["kid-2", "kid-3"]:
            effect = next(e for e in effects if e.kid_id == kid_id)
            assert effect.new_state == const.CHORE_STATE_COMPLETED_BY_OTHER
            assert effect.update_stats is False
            assert effect.set_claimed_by == "Sarah"


# =============================================================================
# TEST: CALCULATE_TRANSITION - APPROVE ACTION
# =============================================================================


class TestCalculateTransitionApprove:
    """Test transition effect planning for approve actions."""

    def test_approve_independent_awards_points(self) -> None:
        """INDEPENDENT: Approve awards points to actor only."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_DEFAULT_POINTS: 15.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_APPROVE,
            kids_assigned=["kid-1", "kid-2"],
            kid_name="Sarah",
        )

        assert len(effects) == 1
        assert effects[0].kid_id == "kid-1"
        assert effects[0].new_state == const.CHORE_STATE_APPROVED
        assert effects[0].update_stats is True
        assert effects[0].points == 15.0
        assert effects[0].set_completed_by == "Sarah"

    def test_approve_shared_first_updates_all(self) -> None:
        """SHARED_FIRST: Approve updates completed_by for all."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.DATA_CHORE_DEFAULT_POINTS: 20.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_APPROVE,
            kids_assigned=["kid-1", "kid-2"],
            kid_name="Sarah",
        )

        assert len(effects) == 2

        actor_effect = next(e for e in effects if e.kid_id == "kid-1")
        assert actor_effect.new_state == const.CHORE_STATE_APPROVED
        assert actor_effect.points == 20.0
        assert actor_effect.update_stats is True

        other_effect = next(e for e in effects if e.kid_id == "kid-2")
        assert other_effect.new_state == const.CHORE_STATE_COMPLETED_BY_OTHER
        assert other_effect.points == 0.0
        assert other_effect.update_stats is False
        assert other_effect.set_completed_by == "Sarah"


# =============================================================================
# TEST: CALCULATE_TRANSITION - DISAPPROVE ACTION
# =============================================================================


class TestCalculateTransitionDisapprove:
    """Test transition effect planning for disapprove actions."""

    def test_disapprove_independent_resets_actor_only(self) -> None:
        """INDEPENDENT: Disapprove only resets the actor."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_DISAPPROVE,
            kids_assigned=["kid-1", "kid-2"],
        )

        assert len(effects) == 1
        assert effects[0].kid_id == "kid-1"
        assert effects[0].new_state == const.CHORE_STATE_PENDING
        assert effects[0].update_stats is True

    def test_disapprove_shared_first_resets_all(self) -> None:
        """SHARED_FIRST: Disapprove resets ALL kids to pending."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_DISAPPROVE,
            kids_assigned=["kid-1", "kid-2", "kid-3"],
        )

        assert len(effects) == 3

        for effect in effects:
            assert effect.new_state == const.CHORE_STATE_PENDING
            assert effect.clear_claimed_by is True
            assert effect.clear_completed_by is True

        # Only actor gets stat update
        actor_effect = next(e for e in effects if e.kid_id == "kid-1")
        assert actor_effect.update_stats is True

        other_effects = [e for e in effects if e.kid_id != "kid-1"]
        for effect in other_effects:
            assert effect.update_stats is False


# =============================================================================
# TEST: CALCULATE_TRANSITION - UNDO ACTION
# =============================================================================


class TestCalculateTransitionUndo:
    """Test transition effect planning for undo actions."""

    def test_undo_never_updates_stats(self) -> None:
        """Undo action should always set update_stats=False."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_UNDO,
            kids_assigned=["kid-1"],
        )

        assert all(e.update_stats is False for e in effects)

    def test_undo_shared_first_resets_all(self) -> None:
        """SHARED_FIRST: Undo resets ALL kids."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_UNDO,
            kids_assigned=["kid-1", "kid-2"],
        )

        assert len(effects) == 2
        for effect in effects:
            assert effect.new_state == const.CHORE_STATE_PENDING
            assert effect.update_stats is False
            assert effect.clear_claimed_by is True


# =============================================================================
# TEST: CALCULATE_TRANSITION - RESET ACTION
# =============================================================================


class TestCalculateTransitionReset:
    """Test transition effect planning for reset actions."""

    def test_reset_affects_all_kids(self) -> None:
        """Reset transitions all assigned kids to pending."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",  # Actor doesn't matter for reset
            action=CHORE_ACTION_RESET,
            kids_assigned=["kid-1", "kid-2", "kid-3"],
        )

        assert len(effects) == 3
        for effect in effects:
            assert effect.new_state == const.CHORE_STATE_PENDING
            assert effect.update_stats is False
            assert effect.clear_claimed_by is True
            assert effect.clear_completed_by is True


# =============================================================================
# TEST: CALCULATE_TRANSITION - OVERDUE ACTION
# =============================================================================


class TestCalculateTransitionOverdue:
    """Test transition effect planning for overdue actions."""

    def test_overdue_affects_only_actor(self) -> None:
        """Overdue only marks the specified kid as overdue."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_OVERDUE,
            kids_assigned=["kid-1", "kid-2"],
        )

        assert len(effects) == 1
        assert effects[0].kid_id == "kid-1"
        assert effects[0].new_state == const.CHORE_STATE_OVERDUE
        assert effects[0].update_stats is True


# =============================================================================
# TEST: SKIP_STATS FLAG
# =============================================================================


class TestSkipStatsFlag:
    """Test the skip_stats parameter."""

    def test_skip_stats_overrides_all_effects(self) -> None:
        """When skip_stats=True, all effects have update_stats=False."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=CHORE_ACTION_APPROVE,
            kids_assigned=["kid-1", "kid-2"],
            skip_stats=True,
        )

        assert all(e.update_stats is False for e in effects)


# =============================================================================
# TEST: VALIDATION - CAN CLAIM
# =============================================================================


class TestCanClaimChore:
    """Test claim validation logic."""

    def test_completed_by_other_blocks_claim(self) -> None:
        """Kid in COMPLETED_BY_OTHER state cannot claim."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_COMPLETED_BY_OTHER,
        }
        chore_data: dict[str, object] = {}

        can_claim, error = ChoreEngine.can_claim_chore(
            kid_chore_data,
            chore_data,
            has_pending_claim=False,
            is_approved_in_period=False,
        )

        assert can_claim is False
        assert error == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER

    def test_pending_claim_blocks_new_claim(self) -> None:
        """Cannot claim if there's already a pending claim (single-claim)."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            kid_chore_data,
            chore_data,
            has_pending_claim=True,
            is_approved_in_period=False,
        )

        assert can_claim is False
        assert error == const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM

    def test_already_approved_blocks_claim(self) -> None:
        """Cannot claim if already approved in period (single-claim)."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            kid_chore_data,
            chore_data,
            has_pending_claim=False,
            is_approved_in_period=True,
        )

        assert can_claim is False
        assert error == const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED

    def test_multi_claim_allows_pending(self) -> None:
        """Multi-claim chore allows claiming even with pending claim."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            kid_chore_data,
            chore_data,
            has_pending_claim=True,
            is_approved_in_period=False,
        )

        assert can_claim is True
        assert error is None

    def test_upon_completion_allows_pending(self) -> None:
        """UPON_COMPLETION chore allows claiming even with pending."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            kid_chore_data,
            chore_data,
            has_pending_claim=True,
            is_approved_in_period=True,
        )

        assert can_claim is True
        assert error is None

    def test_valid_claim_succeeds(self) -> None:
        """Normal claim with no blockers succeeds."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data: dict[str, object] = {}

        can_claim, error = ChoreEngine.can_claim_chore(
            kid_chore_data,
            chore_data,
            has_pending_claim=False,
            is_approved_in_period=False,
        )

        assert can_claim is True
        assert error is None


# =============================================================================
# TEST: VALIDATION - CAN APPROVE
# =============================================================================


class TestCanApproveChore:
    """Test approve validation logic."""

    def test_completed_by_other_blocks_approve(self) -> None:
        """Kid in COMPLETED_BY_OTHER state cannot be approved."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_COMPLETED_BY_OTHER,
        }
        chore_data: dict[str, object] = {}

        can_approve, error = ChoreEngine.can_approve_chore(
            kid_chore_data, chore_data, is_approved_in_period=False
        )

        assert can_approve is False
        assert error == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER

    def test_already_approved_blocks_single_claim(self) -> None:
        """Single-claim chore cannot be approved twice in period."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        }

        can_approve, error = ChoreEngine.can_approve_chore(
            kid_chore_data, chore_data, is_approved_in_period=True
        )

        assert can_approve is False
        assert error == const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED

    def test_multi_claim_allows_multiple_approvals(self) -> None:
        """Multi-claim chore allows multiple approvals in period."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }

        can_approve, error = ChoreEngine.can_approve_chore(
            kid_chore_data, chore_data, is_approved_in_period=True
        )

        assert can_approve is True
        assert error is None

    def test_valid_approve_succeeds(self) -> None:
        """Normal approval with no blockers succeeds."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
        }
        chore_data: dict[str, object] = {}

        can_approve, error = ChoreEngine.can_approve_chore(
            kid_chore_data, chore_data, is_approved_in_period=False
        )

        assert can_approve is True
        assert error is None


# =============================================================================
# TEST: QUERY FUNCTIONS
# =============================================================================


class TestQueryFunctions:
    """Test query/lookup functions."""

    def test_chore_has_pending_claim_true(self) -> None:
        """Returns True when pending_claim_count > 0."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 2,
        }
        assert ChoreEngine.chore_has_pending_claim(kid_chore_data) is True

    def test_chore_has_pending_claim_false(self) -> None:
        """Returns False when pending_claim_count is 0 or missing."""
        assert ChoreEngine.chore_has_pending_claim({}) is False
        assert (
            ChoreEngine.chore_has_pending_claim(
                {const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0}
            )
            is False
        )

    def test_chore_is_overdue_true(self) -> None:
        """Returns True when state is OVERDUE."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_OVERDUE,
        }
        assert ChoreEngine.chore_is_overdue(kid_chore_data) is True

    def test_chore_is_overdue_false(self) -> None:
        """Returns False when state is not OVERDUE."""
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        assert ChoreEngine.chore_is_overdue(kid_chore_data) is False

    def test_chore_allows_multiple_claims_midnight_multi(self) -> None:
        """AT_MIDNIGHT_MULTI allows multiple claims."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }
        assert ChoreEngine.chore_allows_multiple_claims(chore_data) is True

    def test_chore_allows_multiple_claims_due_date_multi(self) -> None:
        """AT_DUE_DATE_MULTI allows multiple claims."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
        }
        assert ChoreEngine.chore_allows_multiple_claims(chore_data) is True

    def test_chore_allows_multiple_claims_upon_completion(self) -> None:
        """UPON_COMPLETION allows multiple claims."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
        }
        assert ChoreEngine.chore_allows_multiple_claims(chore_data) is True

    def test_chore_allows_multiple_claims_once_types(self) -> None:
        """ONCE types do not allow multiple claims."""
        for reset_type in [
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
        ]:
            chore_data = {const.DATA_CHORE_APPROVAL_RESET_TYPE: reset_type}
            assert ChoreEngine.chore_allows_multiple_claims(chore_data) is False

    def test_is_shared_chore_shared(self) -> None:
        """SHARED criteria is a shared chore."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        assert ChoreEngine.is_shared_chore(chore_data) is True

    def test_is_shared_chore_shared_first(self) -> None:
        """SHARED_FIRST criteria is a shared chore."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }
        assert ChoreEngine.is_shared_chore(chore_data) is True

    def test_is_shared_chore_independent(self) -> None:
        """INDEPENDENT criteria is NOT a shared chore."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }
        assert ChoreEngine.is_shared_chore(chore_data) is False

    def test_get_chore_data_for_kid_exists(self) -> None:
        """Returns chore data when it exists."""
        kid_data = {
            const.DATA_KID_CHORE_DATA: {
                "chore-123": {"state": "claimed", "streak": 5},
            }
        }
        result = ChoreEngine.get_chore_data_for_kid(kid_data, "chore-123")
        assert result == {"state": "claimed", "streak": 5}

    def test_get_chore_data_for_kid_not_exists(self) -> None:
        """Returns empty dict when chore data doesn't exist."""
        kid_data = {const.DATA_KID_CHORE_DATA: {}}
        result = ChoreEngine.get_chore_data_for_kid(kid_data, "chore-999")
        assert result == {}

    def test_get_chore_data_for_kid_no_tracking(self) -> None:
        """Returns empty dict when kid has no chore_data."""
        kid_data: dict[str, object] = {}
        result = ChoreEngine.get_chore_data_for_kid(kid_data, "chore-123")
        assert result == {}


# =============================================================================
# TEST: POINT CALCULATIONS
# =============================================================================


class TestPointCalculations:
    """Test point calculation functions."""

    def test_calculate_points_no_multiplier(self) -> None:
        """Calculate points with default multiplier (1.0)."""
        chore_data = {const.DATA_CHORE_DEFAULT_POINTS: 10.0}
        result = ChoreEngine.calculate_points(chore_data)
        assert result == 10.0

    def test_calculate_points_with_multiplier(self) -> None:
        """Calculate points with custom multiplier."""
        chore_data = {const.DATA_CHORE_DEFAULT_POINTS: 10.0}
        result = ChoreEngine.calculate_points(chore_data, multiplier=1.5)
        assert result == 15.0

    def test_calculate_points_uses_default_when_missing(self) -> None:
        """Uses DEFAULT_POINTS when chore has no points defined."""
        chore_data: dict[str, object] = {}
        result = ChoreEngine.calculate_points(chore_data)
        assert result == const.DEFAULT_POINTS

    def test_calculate_points_rounds_to_precision(self) -> None:
        """Points are rounded to DATA_FLOAT_PRECISION."""
        chore_data = {const.DATA_CHORE_DEFAULT_POINTS: 10.0}
        result = ChoreEngine.calculate_points(chore_data, multiplier=0.333)
        # 10.0 * 0.333 = 3.33, rounded to 2 decimal places
        assert result == 3.33


# =============================================================================
# TEST: GLOBAL STATE CALCULATION
# =============================================================================


class TestComputeGlobalChoreState:
    """Test global state calculation from per-kid states."""

    def test_empty_states_returns_unknown(self) -> None:
        """Empty kid_states returns UNKNOWN."""
        result = ChoreEngine.compute_global_chore_state({}, {})
        assert result == const.CHORE_STATE_UNKNOWN

    def test_single_kid_returns_their_state(self) -> None:
        """Single kid: global state is their state."""
        kid_states = {"kid-1": const.CHORE_STATE_CLAIMED}
        result = ChoreEngine.compute_global_chore_state({}, kid_states)
        assert result == const.CHORE_STATE_CLAIMED

    def test_all_pending_returns_pending(self) -> None:
        """All kids pending: global state is PENDING."""
        kid_states = {
            "kid-1": const.CHORE_STATE_PENDING,
            "kid-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state({}, kid_states)
        assert result == const.CHORE_STATE_PENDING

    def test_all_approved_returns_approved(self) -> None:
        """All kids approved: global state is APPROVED."""
        kid_states = {
            "kid-1": const.CHORE_STATE_APPROVED,
            "kid-2": const.CHORE_STATE_APPROVED,
        }
        result = ChoreEngine.compute_global_chore_state({}, kid_states)
        assert result == const.CHORE_STATE_APPROVED

    def test_shared_first_with_claimed_returns_claimed(self) -> None:
        """SHARED_FIRST: One claimed, others completed_by_other → CLAIMED."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }
        kid_states = {
            "kid-1": const.CHORE_STATE_CLAIMED,
            "kid-2": const.CHORE_STATE_COMPLETED_BY_OTHER,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, kid_states)
        assert result == const.CHORE_STATE_CLAIMED

    def test_shared_first_with_approved_returns_approved(self) -> None:
        """SHARED_FIRST: One approved, others completed_by_other → APPROVED."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }
        kid_states = {
            "kid-1": const.CHORE_STATE_APPROVED,
            "kid-2": const.CHORE_STATE_COMPLETED_BY_OTHER,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, kid_states)
        assert result == const.CHORE_STATE_APPROVED

    def test_shared_partial_claimed_returns_claimed_in_part(self) -> None:
        """SHARED: Some claimed, some pending → CLAIMED_IN_PART."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        kid_states = {
            "kid-1": const.CHORE_STATE_CLAIMED,
            "kid-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, kid_states)
        assert result == const.CHORE_STATE_CLAIMED_IN_PART

    def test_shared_partial_approved_returns_approved_in_part(self) -> None:
        """SHARED: Some approved, some pending → APPROVED_IN_PART."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        kid_states = {
            "kid-1": const.CHORE_STATE_APPROVED,
            "kid-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, kid_states)
        assert result == const.CHORE_STATE_APPROVED_IN_PART

    def test_independent_mixed_returns_independent(self) -> None:
        """INDEPENDENT: Mixed states → INDEPENDENT."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }
        kid_states = {
            "kid-1": const.CHORE_STATE_APPROVED,
            "kid-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, kid_states)
        assert result == const.CHORE_STATE_INDEPENDENT

    def test_overdue_takes_precedence_in_shared(self) -> None:
        """SHARED: If any kid is overdue, global is OVERDUE."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        kid_states = {
            "kid-1": const.CHORE_STATE_OVERDUE,
            "kid-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, kid_states)
        assert result == const.CHORE_STATE_OVERDUE
