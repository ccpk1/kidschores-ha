"""Chore workflow tests using YAML scenarios.

These tests verify the complete claim → approve → points cycle
for all chore types using real config flow setup.

Test Organization:
- TestIndependentChores: Single-kid and multi-kid independent chores
- TestSharedFirstChores: Race-to-complete chores
- TestSharedAllChores: All-must-complete chores
- TestAutoApprove: Instant approval on claim

Coordinator API Reference:
- claim_chore(kid_id, chore_id, user_name)
- approve_chore(parent_name, kid_id, chore_id, points_awarded=None)
- disapprove_chore(parent_name, kid_id, chore_id)
"""

# pylint: disable=redefined-outer-name
# hass fixture required for HA test setup

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers import (
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_COMPLETED_BY_OTHER,
    CHORE_STATE_PENDING,
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_CUSTOM_INTERVAL,
    DATA_CHORE_CUSTOM_INTERVAL_UNIT,
    DATA_CHORE_DAILY_MULTI_TIMES,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_RECURRING_FREQUENCY,
    DATA_KID_CHORE_DATA,
    DATA_KID_CHORE_DATA_STATE,
    DATA_KID_POINTS,
    FREQUENCY_CUSTOM,
    FREQUENCY_CUSTOM_FROM_COMPLETE,
    FREQUENCY_DAILY,
    FREQUENCY_DAILY_MULTI,
    FREQUENCY_NONE,
    TIME_UNIT_HOURS,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 kid, 1 parent, 5 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.fixture
async def scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load shared scenario: 3 kids, 1 parent, 8 shared chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


@pytest.fixture
async def scenario_approval_reset_no_due_date(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scenario for testing approval reset with frequency=none, no due date."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_approval_reset_no_due_date.yaml",
    )


@pytest.fixture
async def scenario_enhanced_frequencies(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load enhanced frequencies scenario for Phase 5 tests.

    Contains chores with DAILY_MULTI, CUSTOM_FROM_COMPLETE, and CUSTOM hours.
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_enhanced_frequencies.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_kid_chore_state(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> str:
    """Get the current state of a chore for a specific kid.

    Args:
        coordinator: KidsChoresDataCoordinator
        kid_id: The kid's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        State string (e.g., 'pending', 'claimed', 'approved')
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.get(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    return per_chore.get(DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def get_kid_points(coordinator: Any, kid_id: str) -> float:
    """Get a kid's current point balance."""
    kid_data = coordinator.kids_data.get(kid_id, {})
    return kid_data.get(DATA_KID_POINTS, 0.0)


# =============================================================================
# INDEPENDENT CHORE TESTS
# =============================================================================


class TestIndependentChores:
    """Tests for chores with completion_criteria='independent'."""

    @pytest.mark.asyncio
    async def test_claim_changes_state_to_claimed(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Claiming a chore changes state from pending to claimed."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        # Initial state should be pending
        initial_state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert initial_state == CHORE_STATE_PENDING

        # Mock notifications to avoid side effects
        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim the chore (API: kid_id, chore_id, user_name)
            coordinator.claim_chore(kid_id, chore_id, "Zoë")

        # State should now be claimed
        new_state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert new_state == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_approve_grants_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Approving a claimed chore grants points to the kid."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]  # 5 points

        initial_points = get_kid_points(coordinator, kid_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim the chore (API: kid_id, chore_id, user_name)
            coordinator.claim_chore(kid_id, chore_id, "Zoë")

            # Approve the chore (API: parent_name, kid_id, chore_id)
            coordinator.approve_chore("Mom", kid_id, chore_id)

        # Points should increase by chore value (5 points)
        final_points = get_kid_points(coordinator, kid_id)
        assert final_points == initial_points + 5.0

        # State should be approved
        state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert state == CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_disapprove_resets_to_pending(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Disapproving a claimed chore resets it to pending state."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim the chore
            coordinator.claim_chore(kid_id, chore_id, "Zoë")

            # Verify claimed
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Disapprove (API: parent_name, kid_id, chore_id)
            coordinator.disapprove_chore("Mom", kid_id, chore_id)

        # State should be reset to pending
        state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_disapprove_does_not_grant_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Disapproving a chore does not change point balance."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        initial_points = get_kid_points(coordinator, kid_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            coordinator.disapprove_chore("Mom", kid_id, chore_id)

        # Points should be unchanged
        final_points = get_kid_points(coordinator, kid_id)
        assert final_points == initial_points


# =============================================================================
# AUTO-APPROVE TESTS
# =============================================================================


class TestAutoApprove:
    """Tests for chores with auto_approve=True."""

    @pytest.mark.asyncio
    async def test_claim_triggers_instant_approval(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Claiming an auto-approve chore immediately grants approval and points."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids[
            "Brush teeth"
        ]  # auto_approve=true, 3 points

        initial_points = get_kid_points(coordinator, kid_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim the auto-approve chore
            coordinator.claim_chore(kid_id, chore_id, "Zoë")

        # State should be approved (skipped claimed)
        state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert state == CHORE_STATE_APPROVED

        # Points should have increased
        final_points = get_kid_points(coordinator, kid_id)
        assert final_points == initial_points + 3.0


# =============================================================================
# SHARED_FIRST CHORE TESTS
# =============================================================================


class TestSharedFirstChores:
    """Tests for chores with completion_criteria='shared_first'.

    In shared_first chores:
    1. When one kid claims, all others immediately get 'completed_by_other'
    2. Only the claiming kid can be approved for points
    3. On disapproval, everyone resets to pending
    """

    @pytest.mark.asyncio
    async def test_claim_blocks_other_kids(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """First kid to claim blocks all other kids immediately."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        lila_id = scenario_shared.kid_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Take out trash"]  # shared_first, 3 kids

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Zoë claims first
            coordinator.claim_chore(zoe_id, chore_id, "Zoë")

        # Zoë should be claimed
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_CLAIMED

        # Max and Lila should immediately be completed_by_other
        assert (
            get_kid_chore_state(coordinator, max_id, chore_id)
            == CHORE_STATE_COMPLETED_BY_OTHER
        )
        assert (
            get_kid_chore_state(coordinator, lila_id, chore_id)
            == CHORE_STATE_COMPLETED_BY_OTHER
        )

    @pytest.mark.asyncio
    async def test_approve_grants_points_to_claimer_only(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Approving the claimer grants them points, others remain blocked."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        lila_id = scenario_shared.kid_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Take out trash"]  # shared_first, 5 points

        initial_zoe_points = get_kid_points(coordinator, zoe_id)
        initial_max_points = get_kid_points(coordinator, max_id)
        initial_lila_points = get_kid_points(coordinator, lila_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Zoë claims and gets approved
            coordinator.claim_chore(zoe_id, chore_id, "Zoë")
            coordinator.approve_chore("Mom", zoe_id, chore_id)

        # Zoë should be approved with points
        assert (
            get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_APPROVED
        )
        assert get_kid_points(coordinator, zoe_id) == initial_zoe_points + 5.0

        # Max and Lila remain completed_by_other, no points
        assert (
            get_kid_chore_state(coordinator, max_id, chore_id)
            == CHORE_STATE_COMPLETED_BY_OTHER
        )
        assert get_kid_points(coordinator, max_id) == initial_max_points

        assert (
            get_kid_chore_state(coordinator, lila_id, chore_id)
            == CHORE_STATE_COMPLETED_BY_OTHER
        )
        assert get_kid_points(coordinator, lila_id) == initial_lila_points

    @pytest.mark.asyncio
    async def test_disapprove_resets_all_kids(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Disapproving the claimer resets ALL kids to pending."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        chore_id = scenario_shared.chore_ids[
            "Organize garage"
        ]  # shared_first, Zoë + Max only

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Zoë claims (Max becomes completed_by_other)
            coordinator.claim_chore(zoe_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, max_id, chore_id)
                == CHORE_STATE_COMPLETED_BY_OTHER
            )

            # Disapprove Zoë
            coordinator.disapprove_chore("Mom", zoe_id, chore_id)

        # Both should be reset to pending
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_PENDING
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_PENDING


# =============================================================================
# SHARED_ALL CHORE TESTS
# =============================================================================


class TestSharedAllChores:
    """Tests for chores with completion_criteria='shared_all'.

    In shared_all chores:
    - Each kid can claim and be approved independently
    - Each kid gets their own points when approved
    - All kids share the same global state tracking
    """

    @pytest.mark.asyncio
    async def test_each_kid_gets_points_on_approval(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Each kid gets points when they individually get approved."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        chore_id = scenario_shared.chore_ids[
            "Walk the dog"
        ]  # shared_all, Zoë + Max, 8 pts

        initial_zoe = get_kid_points(coordinator, zoe_id)
        initial_max = get_kid_points(coordinator, max_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Zoë claims and gets approved
            coordinator.claim_chore(zoe_id, chore_id, "Zoë")
            coordinator.approve_chore("Mom", zoe_id, chore_id)

            # Zoë gets points immediately
            assert get_kid_points(coordinator, zoe_id) == initial_zoe + 8.0

            # Max claims and gets approved
            coordinator.claim_chore(max_id, chore_id, "Max")
            coordinator.approve_chore("Mom", max_id, chore_id)

            # Max gets points
            assert get_kid_points(coordinator, max_id) == initial_max + 8.0

    @pytest.mark.asyncio
    async def test_three_kid_shared_all(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Three-kid shared_all chore - each gets points independently."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        lila_id = scenario_shared.kid_ids["Lila"]
        chore_id = scenario_shared.chore_ids[
            "Family dinner cleanup"
        ]  # shared_all, 10 pts

        initial_zoe = get_kid_points(coordinator, zoe_id)
        initial_max = get_kid_points(coordinator, max_id)
        initial_lila = get_kid_points(coordinator, lila_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # All three claim and get approved one by one
            coordinator.claim_chore(zoe_id, chore_id, "Zoë")
            coordinator.approve_chore("Mom", zoe_id, chore_id)
            assert get_kid_points(coordinator, zoe_id) == initial_zoe + 10.0

            coordinator.claim_chore(max_id, chore_id, "Max")
            coordinator.approve_chore("Mom", max_id, chore_id)
            assert get_kid_points(coordinator, max_id) == initial_max + 10.0

            coordinator.claim_chore(lila_id, chore_id, "Lila")
            coordinator.approve_chore("Mom", lila_id, chore_id)
            assert get_kid_points(coordinator, lila_id) == initial_lila + 10.0

    @pytest.mark.asyncio
    async def test_approved_state_tracked_per_kid(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Each kid has independent state tracking."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        lila_id = scenario_shared.kid_ids["Lila"]
        chore_id = scenario_shared.chore_ids[
            "Family dinner cleanup"
        ]  # shared_all, 3 kids

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Only Zoë completes the chore
            coordinator.claim_chore(zoe_id, chore_id, "Zoë")
            coordinator.approve_chore("Mom", zoe_id, chore_id)

        # Zoë is approved
        assert (
            get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_APPROVED
        )

        # Max and Lila are still pending
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_PENDING
        assert (
            get_kid_chore_state(coordinator, lila_id, chore_id) == CHORE_STATE_PENDING
        )


# =============================================================================
# APPROVAL RESET WITH NO DUE DATE TESTS (frequency="none")
# =============================================================================


class TestApprovalResetNoDueDate:
    """Test approval reset for chores with frequency='none' and no due_date.

    Key Insight from coordinator.py:
    - Line 7876: frequency="none" chores are ALWAYS included in reset checks
    - Lines 7912-7923: If no due_date_str exists, no date check blocks reset
    - Result: These chores reset immediately when _reset_daily_chore_statuses() runs

    This tests all three completion criteria types to ensure consistent behavior.
    """

    @pytest.mark.asyncio
    async def test_independent_chore_resets_after_approval(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
    ) -> None:
        """INDEPENDENT chore with no due date resets from APPROVED to PENDING."""
        coordinator = scenario_approval_reset_no_due_date.coordinator
        kid1_id = scenario_approval_reset_no_due_date.kid_ids["Zoë"]
        kid2_id = scenario_approval_reset_no_due_date.kid_ids["Max!"]
        chore_id = scenario_approval_reset_no_due_date.chore_ids[
            "No Due Date Independent"
        ]

        # Verify chore has no due date and frequency="none"
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_NONE
        assert chore_info.get(DATA_CHORE_DUE_DATE) is None

        initial_kid1_points = get_kid_points(coordinator, kid1_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Kid1 claims and gets approved
            coordinator.claim_chore(kid1_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid1_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            coordinator.approve_chore("TestParent", kid1_id, chore_id)
            assert (
                get_kid_chore_state(coordinator, kid1_id, chore_id)
                == CHORE_STATE_APPROVED
            )
            assert get_kid_points(coordinator, kid1_id) == initial_kid1_points + 10.0

        # Kid2 remains pending (independent chore)
        assert (
            get_kid_chore_state(coordinator, kid2_id, chore_id) == CHORE_STATE_PENDING
        )

        # Trigger approval reset (frequency="none" chores always included per line 7876)
        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            await coordinator._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Kid1 should reset to PENDING (ready for next round)
        assert (
            get_kid_chore_state(coordinator, kid1_id, chore_id) == CHORE_STATE_PENDING
        )

        # Kid2 still pending (was never claimed)
        assert (
            get_kid_chore_state(coordinator, kid2_id, chore_id) == CHORE_STATE_PENDING
        )

        # Points remain (reset doesn't remove points)
        assert get_kid_points(coordinator, kid1_id) == initial_kid1_points + 10.0

    @pytest.mark.asyncio
    async def test_shared_first_chore_resets_after_approval(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
    ) -> None:
        """SHARED_FIRST chore with no due date resets all kids to PENDING."""
        coordinator = scenario_approval_reset_no_due_date.coordinator
        kid1_id = scenario_approval_reset_no_due_date.kid_ids["Zoë"]
        kid2_id = scenario_approval_reset_no_due_date.kid_ids["Max!"]
        chore_id = scenario_approval_reset_no_due_date.chore_ids[
            "No Due Date Shared First"
        ]

        # Verify chore configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_NONE
        assert chore_info.get(DATA_CHORE_DUE_DATE) is None
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )

        initial_kid1_points = get_kid_points(coordinator, kid1_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Kid1 claims (Kid2 becomes completed_by_other)
            coordinator.claim_chore(kid1_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid1_id, chore_id)
                == CHORE_STATE_CLAIMED
            )
            assert (
                get_kid_chore_state(coordinator, kid2_id, chore_id)
                == CHORE_STATE_COMPLETED_BY_OTHER
            )

            # Kid1 gets approved
            coordinator.approve_chore("TestParent", kid1_id, chore_id)
            assert (
                get_kid_chore_state(coordinator, kid1_id, chore_id)
                == CHORE_STATE_APPROVED
            )
            assert get_kid_points(coordinator, kid1_id) == initial_kid1_points + 15.0

        # Trigger approval reset
        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            await coordinator._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # BOTH kids should reset to PENDING (shared_first resets all)
        assert (
            get_kid_chore_state(coordinator, kid1_id, chore_id) == CHORE_STATE_PENDING
        )
        assert (
            get_kid_chore_state(coordinator, kid2_id, chore_id) == CHORE_STATE_PENDING
        )

        # Points remain
        assert get_kid_points(coordinator, kid1_id) == initial_kid1_points + 15.0

    @pytest.mark.asyncio
    async def test_shared_all_chore_resets_after_approval(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
    ) -> None:
        """SHARED_ALL chore with no due date resets each kid independently."""
        coordinator = scenario_approval_reset_no_due_date.coordinator
        kid1_id = scenario_approval_reset_no_due_date.kid_ids["Zoë"]
        kid2_id = scenario_approval_reset_no_due_date.kid_ids["Max!"]
        chore_id = scenario_approval_reset_no_due_date.chore_ids[
            "No Due Date Shared All"
        ]

        # Verify chore configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_NONE
        assert chore_info.get(DATA_CHORE_DUE_DATE) is None
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )

        initial_kid1_points = get_kid_points(coordinator, kid1_id)
        initial_kid2_points = get_kid_points(coordinator, kid2_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Kid1 claims and gets approved
            coordinator.claim_chore(kid1_id, chore_id, "Zoë")
            coordinator.approve_chore("TestParent", kid1_id, chore_id)
            assert (
                get_kid_chore_state(coordinator, kid1_id, chore_id)
                == CHORE_STATE_APPROVED
            )
            assert get_kid_points(coordinator, kid1_id) == initial_kid1_points + 20.0

            # Kid2 claims and gets approved
            coordinator.claim_chore(kid2_id, chore_id, "Max!")
            coordinator.approve_chore("TestParent", kid2_id, chore_id)
            assert (
                get_kid_chore_state(coordinator, kid2_id, chore_id)
                == CHORE_STATE_APPROVED
            )
            assert get_kid_points(coordinator, kid2_id) == initial_kid2_points + 20.0

        # Trigger approval reset
        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            await coordinator._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # BOTH kids should reset to PENDING
        assert (
            get_kid_chore_state(coordinator, kid1_id, chore_id) == CHORE_STATE_PENDING
        )
        assert (
            get_kid_chore_state(coordinator, kid2_id, chore_id) == CHORE_STATE_PENDING
        )

        # Points remain for both
        assert get_kid_points(coordinator, kid1_id) == initial_kid1_points + 20.0
        assert get_kid_points(coordinator, kid2_id) == initial_kid2_points + 20.0

    @pytest.mark.asyncio
    async def test_claimed_but_not_approved_also_resets(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
    ) -> None:
        """Chores in CLAIMED state (not approved) also reset to PENDING."""
        coordinator = scenario_approval_reset_no_due_date.coordinator
        kid1_id = scenario_approval_reset_no_due_date.kid_ids["Zoë"]
        chore_id = scenario_approval_reset_no_due_date.chore_ids[
            "No Due Date Independent"
        ]

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Kid1 claims but does NOT get approved
            coordinator.claim_chore(kid1_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid1_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

        # Trigger approval reset
        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            await coordinator._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Should reset to PENDING (default pending_claim_action is "clear")
        assert (
            get_kid_chore_state(coordinator, kid1_id, chore_id) == CHORE_STATE_PENDING
        )


# =============================================================================
# WORKFLOW INTEGRATION EDGE CASES
# =============================================================================


class TestWorkflowIntegrationEdgeCases:
    """Tests for edge cases in chore workflows from legacy test coverage.

    These tests cover scenarios that ensure the full workflow integration
    behaves correctly in edge cases.
    """

    @pytest.mark.asyncio
    async def test_claim_does_not_change_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test: Claiming a chore does NOT award points (only approval does).

        Legacy: test_chore_claim_points_unchanged
        """
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        initial_points = get_kid_points(coordinator, kid_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")

        # Points should NOT change on claim
        final_points = get_kid_points(coordinator, kid_id)
        assert final_points == initial_points, (
            "Points should not change on claim, only on approval"
        )

    @pytest.mark.asyncio
    async def test_multiple_claims_same_chore_different_kids_independent(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test: Independent chores allow multiple kids to claim.

        Each kid tracks their own state for independent chores.
        This is different from shared_first where only one can claim.
        """
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        chore_map = scenario_shared.chore_ids

        # "Walk the dog" is shared_all (acts like independent per-kid tracking)
        chore_id = chore_map["Walk the dog"]

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Both kids can claim the same chore
            coordinator.claim_chore(zoe_id, chore_id, "Zoë")
            coordinator.claim_chore(max_id, chore_id, "Max")

        # Both should be CLAIMED (independent tracking)
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_CLAIMED
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_approve_increments_chore_approval_count(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test: Approval increments the kid's chore approval count stats.

        Legacy: test_parent_approve_increments_count
        The chore_stats track approved_all_time which increments on each approval.
        """
        from custom_components.kidschores import const

        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        # Get initial approval count from chore stats
        kid_info = coordinator.kids_data.get(kid_id, {})
        chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        initial_count = chore_stats.get(const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, 0)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            coordinator.approve_chore("Mom", kid_id, chore_id)

        # Get final approval count
        kid_info = coordinator.kids_data.get(kid_id, {})
        chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        final_count = chore_stats.get(const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, 0)

        assert final_count == initial_count + 1, (
            f"Approval count should increment: {initial_count} -> {final_count}"
        )

    @pytest.mark.asyncio
    async def test_disapprove_increments_disapproval_count(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test: Disapproval increments disapproval count.

        Legacy: Validates that disapproval is tracked separately
        """
        from custom_components.kidschores import const

        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        # Get initial disapproval count from chore stats
        kid_info = coordinator.kids_data.get(kid_id, {})
        chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        initial_count = chore_stats.get(
            const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME, 0
        )

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            coordinator.disapprove_chore("Mom", kid_id, chore_id)

        # Get final disapproval count
        kid_info = coordinator.kids_data.get(kid_id, {})
        chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        final_count = chore_stats.get(
            const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME, 0
        )

        assert final_count == initial_count + 1, (
            f"Disapproval count should increment: {initial_count} -> {final_count}"
        )

    @pytest.mark.asyncio
    async def test_approve_awards_default_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test: Approval awards the chore's default points.

        Note: points_awarded parameter is reserved for future feature.
        Currently, approval always uses the chore's default_points value.
        """
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]  # Default: 5 points

        initial_points = get_kid_points(coordinator, kid_id)

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            # Approval uses default points (5) - points_awarded param is reserved
            coordinator.approve_chore("Mom", kid_id, chore_id)

        final_points = get_kid_points(coordinator, kid_id)
        assert final_points == initial_points + 5.0, (
            f"Should award default points (5): {initial_points} + 5 = {initial_points + 5.0}, got {final_points}"
        )


class TestWorkflowResetIntegration:
    """Tests for approval reset integration in workflows.

    Legacy: test_workflow_independent_approval_reset.py
    These tests verify that approval reset works correctly within
    the full workflow context.
    """

    @pytest.mark.asyncio
    async def test_approved_chore_resets_after_daily_cycle(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test: Approved daily chore resets to pending after reset cycle.

        Legacy: test_approve_advances_per_kid_due_date (partial)
        After approval and reset, the chore should be ready for next day.
        """
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]  # daily chore

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Complete the workflow: claim -> approve
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            coordinator.approve_chore("Mom", kid_id, chore_id)

            # Verify approved
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_APPROVED
            )

            # Trigger daily reset
            await coordinator._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Should be back to PENDING (ready for next day)
        assert get_kid_chore_state(coordinator, kid_id, chore_id) == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_claimed_not_approved_clears_on_reset(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test: Claimed but not approved chores clear on reset (default behavior).

        Legacy: test_claimed_but_not_approved_also_resets
        The default pending_claim_action is "clear", so claimed chores
        should reset to pending when the approval period resets.
        """
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim but don't approve
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Trigger daily reset
            await coordinator._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Should be reset to PENDING (claim cleared)
        assert get_kid_chore_state(coordinator, kid_id, chore_id) == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_points_preserved_after_reset(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test: Points are preserved after reset (reset doesn't remove points).

        Legacy: Validates that reset only affects chore states, not point balances.
        """
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            coordinator.approve_chore("Mom", kid_id, chore_id)

        # Record points after approval
        points_after_approval = get_kid_points(coordinator, kid_id)
        assert points_after_approval > 0

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Trigger reset
            await coordinator._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Points should be unchanged
        points_after_reset = get_kid_points(coordinator, kid_id)
        assert points_after_reset == points_after_approval, (
            "Reset should not affect point balance"
        )


# =============================================================================
# Enhanced Frequency Workflow Tests (CFE-2026-001, CFE-2026-002, CFE-2026-003)
# =============================================================================


class TestEnhancedFrequencyWorkflows:
    """Integration/workflow tests for Phase 5 enhanced frequency features.

    Tests the complete workflow for:
    - DAILY_MULTI: Multiple time slots per day
    - CUSTOM_FROM_COMPLETE: Reschedule from completion date
    - CUSTOM hours: Sub-daily intervals in hours

    These tests use the enhanced_frequencies scenario which contains chores
    configured with the Phase 5 frequency enhancements.
    """

    @pytest.mark.asyncio
    async def test_wf_01_daily_multi_claim_approve_workflow(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """WF-01: DAILY_MULTI chore claim/approve workflow.

        Tests that a DAILY_MULTI chore can be claimed and approved,
        verifying the complete workflow operates correctly.
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        kid_id = scenario_enhanced_frequencies.kid_ids["Zoë"]
        chore_id = scenario_enhanced_frequencies.chore_ids["Daily Multi Single Kid"]

        # Verify this is a DAILY_MULTI chore with correct configuration
        chore = coordinator.chores_data.get(chore_id, {})
        assert chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI
        assert chore.get(DATA_CHORE_DAILY_MULTI_TIMES) == "09:00|21:00"

        # Initial state should be PENDING
        assert get_kid_chore_state(coordinator, kid_id, chore_id) == CHORE_STATE_PENDING

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim the chore
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Approve the chore
            coordinator.approve_chore("Môm Astrid Stârblüm", kid_id, chore_id)

        # After approval, state should change (APPROVED or PENDING based on reset)
        final_state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert final_state in [CHORE_STATE_APPROVED, CHORE_STATE_PENDING]

    @pytest.mark.asyncio
    async def test_wf_02_custom_from_complete_claim_approve_workflow(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """WF-02: CUSTOM_FROM_COMPLETE chore claim/approve workflow.

        Tests that a CUSTOM_FROM_COMPLETE chore can be claimed and approved,
        verifying the frequency type is handled correctly.
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        kid_id = scenario_enhanced_frequencies.kid_ids["Zoë"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete Single"
        ]

        # Verify this is a CUSTOM_FROM_COMPLETE chore
        chore = coordinator.chores_data.get(chore_id, {})
        assert (
            chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_CUSTOM_FROM_COMPLETE
        )
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL) == 5

        # Initial state should be PENDING
        assert get_kid_chore_state(coordinator, kid_id, chore_id) == CHORE_STATE_PENDING

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim the chore
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Approve the chore
            coordinator.approve_chore("Môm Astrid Stârblüm", kid_id, chore_id)

        # After approval with UPON_COMPLETION reset, should be PENDING
        final_state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert final_state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_wf_03_custom_hours_claim_approve_workflow(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """WF-03: CUSTOM hours interval claim/approve workflow.

        Tests that a CUSTOM frequency chore with hours unit can be
        claimed and approved, verifying hourly intervals work correctly.
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        kid_id = scenario_enhanced_frequencies.kid_ids["Zoë"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom Hours 8h Cross Midnight"
        ]

        # Verify this is a CUSTOM chore with hours unit
        chore = coordinator.chores_data.get(chore_id, {})
        assert chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_CUSTOM
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL_UNIT) == TIME_UNIT_HOURS
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL) == 8

        # Initial state should be PENDING
        assert get_kid_chore_state(coordinator, kid_id, chore_id) == CHORE_STATE_PENDING

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Claim the chore
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Approve the chore
            coordinator.approve_chore("Môm Astrid Stârblüm", kid_id, chore_id)

        # After approval, state should change
        final_state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert final_state in [CHORE_STATE_APPROVED, CHORE_STATE_PENDING]

    @pytest.mark.asyncio
    async def test_wf_04_existing_daily_not_affected(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """WF-04: Regression test - standard DAILY chores unchanged.

        Verify that existing DAILY frequency chores still work correctly
        after Phase 5 enhancements. This is a regression test to ensure
        backwards compatibility with baseline chore types.
        """
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]  # DAILY chore

        # Verify this is indeed a DAILY chore
        chore = coordinator.chores_data.get(chore_id, {})
        assert chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY

        with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
            # Standard workflow: claim -> approve
            coordinator.claim_chore(kid_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            coordinator.approve_chore("Mom", kid_id, chore_id)

        # Should be APPROVED (standard behavior)
        assert (
            get_kid_chore_state(coordinator, kid_id, chore_id) == CHORE_STATE_APPROVED
        )
