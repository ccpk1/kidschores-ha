"""Tests for ChoreManager - stateful chore workflow orchestration.

Tests verify:
- Claim, approve, disapprove, undo, reset workflows
- Race condition protection via locks
- Event emission
- Integration with EconomyManager
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.kidschores import const
from custom_components.kidschores.managers.chore_manager import ChoreManager

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create mock Home Assistant instance."""
    hass = MagicMock()
    hass.async_create_task = MagicMock(side_effect=lambda coro: coro)
    return hass


@pytest.fixture
def mock_economy_manager() -> MagicMock:
    """Create mock EconomyManager."""
    manager = MagicMock()
    # deposit and withdraw are now async methods
    manager.deposit = AsyncMock(return_value=100.0)
    manager.withdraw = AsyncMock(return_value=90.0)
    return manager


@pytest.fixture
def sample_chore_data() -> dict[str, Any]:
    """Create sample chore data."""
    return {
        const.DATA_CHORE_NAME: "Wash Dishes",
        const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1", "kid-2"],
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        const.DATA_CHORE_AUTO_APPROVE: False,
        const.DATA_CHORE_LABELS: ["kitchen", "daily"],
    }


@pytest.fixture
def sample_kid_data() -> dict[str, Any]:
    """Create sample kid data."""
    return {
        const.DATA_KID_NAME: "Alice",
        const.DATA_KID_POINTS_MULTIPLIER: 1.0,
        const.DATA_KID_CHORE_DATA: {},
    }


@pytest.fixture
def mock_coordinator(sample_chore_data: dict, sample_kid_data: dict) -> MagicMock:
    """Create mock coordinator with sample data."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test-entry-123"
    coordinator.chores_data = {"chore-1": sample_chore_data}
    coordinator.kids_data = {
        "kid-1": sample_kid_data.copy(),
        "kid-2": {
            const.DATA_KID_NAME: "Bob",
            const.DATA_KID_POINTS_MULTIPLIER: 1.5,
            const.DATA_KID_CHORE_DATA: {},
        },
    }
    coordinator._persist = MagicMock()
    coordinator.async_set_updated_data = MagicMock()
    coordinator._data = {}

    # Mock chore_is_approved_in_period
    coordinator.chore_is_approved_in_period = MagicMock(return_value=False)

    return coordinator


@pytest.fixture
def chore_manager(
    mock_hass: MagicMock,
    mock_coordinator: MagicMock,
    mock_economy_manager: MagicMock,
) -> ChoreManager:
    """Create ChoreManager instance with mocks."""
    manager = ChoreManager(mock_hass, mock_coordinator, mock_economy_manager)
    # Mock the emit method to track events
    manager.emit = MagicMock()
    return manager


# ============================================================================
# Test Class: Basic Validation
# ============================================================================


class TestValidation:
    """Tests for entity validation."""

    def test_validate_kid_and_chore_success(self, chore_manager: ChoreManager) -> None:
        """Test validation passes for existing entities."""
        # Should not raise
        chore_manager._validate_kid_and_chore("kid-1", "chore-1")

    def test_validate_chore_not_found(self, chore_manager: ChoreManager) -> None:
        """Test validation fails for missing chore."""
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError) as exc_info:
            chore_manager._validate_kid_and_chore("kid-1", "invalid-chore")

        assert exc_info.value.translation_key == const.TRANS_KEY_ERROR_NOT_FOUND

    def test_validate_kid_not_found(self, chore_manager: ChoreManager) -> None:
        """Test validation fails for missing kid."""
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError) as exc_info:
            chore_manager._validate_kid_and_chore("invalid-kid", "chore-1")

        assert exc_info.value.translation_key == const.TRANS_KEY_ERROR_NOT_FOUND


# ============================================================================
# Test Class: Claim Workflow
# ============================================================================


class TestClaimWorkflow:
    """Tests for chore claim workflow."""

    @pytest.mark.asyncio
    async def test_claim_chore_success(self, chore_manager: ChoreManager) -> None:
        """Test successful chore claim."""
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Verify state changed to claimed
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_CLAIMED
        )

        # Verify pending count incremented
        assert kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] == 1

        # Verify event emitted
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_CLAIMED
        assert call_args[1]["kid_id"] == "kid-1"
        assert call_args[1]["chore_id"] == "chore-1"

        # Verify persist called
        chore_manager._coordinator._persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_claim_chore_not_assigned(self, chore_manager: ChoreManager) -> None:
        """Test claim fails when kid not assigned to chore."""
        from homeassistant.exceptions import HomeAssistantError

        # Kid-3 is not assigned
        chore_manager._coordinator.kids_data["kid-3"] = {
            const.DATA_KID_NAME: "Charlie",
            const.DATA_KID_CHORE_DATA: {},
        }

        with pytest.raises(HomeAssistantError) as exc_info:
            await chore_manager.claim_chore("kid-3", "chore-1", "Charlie")

        assert exc_info.value.translation_key == const.TRANS_KEY_ERROR_NOT_ASSIGNED

    @pytest.mark.asyncio
    async def test_claim_with_auto_approve(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test claim triggers auto-approve when enabled."""
        # Enable auto-approve
        mock_coordinator.chores_data["chore-1"][const.DATA_CHORE_AUTO_APPROVE] = True

        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Verify async_create_task was called for auto-approve
        chore_manager.hass.async_create_task.assert_called()


# ============================================================================
# Test Class: Approve Workflow
# ============================================================================


class TestApproveWorkflow:
    """Tests for chore approval workflow."""

    @pytest.mark.asyncio
    async def test_approve_chore_success(
        self,
        chore_manager: ChoreManager,
        mock_economy_manager: MagicMock,
    ) -> None:
        """Test successful chore approval."""
        # First claim the chore
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        # Now approve
        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        # Verify state changed to approved
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE]
            == const.CHORE_STATE_APPROVED
        )

        # Verify pending count decremented
        assert kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] == 0

        # Verify points deposited
        mock_economy_manager.deposit.assert_called_once()
        deposit_call = mock_economy_manager.deposit.call_args
        assert deposit_call[1]["kid_id"] == "kid-1"
        assert deposit_call[1]["source"] == const.POINTS_SOURCE_CHORES

        # Verify event emitted
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_APPROVED
        assert call_args[1]["kid_id"] == "kid-1"
        assert call_args[1]["parent_name"] == "Parent"

    @pytest.mark.asyncio
    async def test_approve_race_condition_protection(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Test that race condition is handled gracefully."""
        # Claim first
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Mark as already approved in period
        chore_manager._coordinator.chore_is_approved_in_period.return_value = True

        # Should return gracefully without error
        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        # No error raised, graceful exit


# ============================================================================
# Test Class: Disapprove Workflow
# ============================================================================


class TestDisapproveWorkflow:
    """Tests for chore disapproval workflow."""

    @pytest.mark.asyncio
    async def test_disapprove_chore_success(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Test successful chore disapproval."""
        # First claim the chore
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        # Now disapprove
        await chore_manager.disapprove_chore("Parent", "kid-1", "chore-1", "Try again")

        # Verify state changed back to pending
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
        )

        # Verify event emitted with reason
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_DISAPPROVED
        assert call_args[1]["reason"] == "Try again"


# ============================================================================
# Test Class: Reset and Overdue
# ============================================================================


class TestResetAndOverdue:
    """Tests for reset and overdue workflows."""

    @pytest.mark.asyncio
    async def test_reset_chore(self, chore_manager: ChoreManager) -> None:
        """Test chore reset."""
        # Claim and approve first
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        # Reset
        await chore_manager.reset_chore("kid-1", "chore-1")

        # Verify state reset to pending
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
        )

        # Verify event emitted
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_STATUS_RESET

    async def test_mark_overdue(self, chore_manager: ChoreManager) -> None:
        """Test marking chore as overdue."""
        await chore_manager.mark_overdue(
            "kid-1", "chore-1", days_overdue=2, due_date="2024-01-01"
        )

        # Verify state changed to overdue
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_OVERDUE
        )

        # Verify event emitted
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_OVERDUE
        assert call_args[1]["days_overdue"] == 2


# ============================================================================
# Test Class: Undo Workflow
# ============================================================================


class TestUndoWorkflow:
    """Tests for chore undo workflow."""

    @pytest.mark.asyncio
    async def test_undo_chore(self, chore_manager: ChoreManager) -> None:
        """Test chore undo."""
        # Set up approved state with points
        kid_data = chore_manager._coordinator.kids_data["kid-1"]
        kid_data[const.DATA_KID_CHORE_DATA] = {
            "chore-1": {
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_APPROVED,
                const.DATA_KID_CHORE_DATA_TOTAL_POINTS: 10.0,
            }
        }

        await chore_manager.undo_chore("kid-1", "chore-1", "Parent")

        # Verify state reset to pending
        kid_chore_data = kid_data[const.DATA_KID_CHORE_DATA]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
        )


# ============================================================================
# Test Class: Completion Criteria
# ============================================================================


class TestCompletionCriteria:
    """Tests for completion criteria handling."""

    @pytest.mark.asyncio
    async def test_independent_completion(self, chore_manager: ChoreManager) -> None:
        """Test INDEPENDENT completion sets completed_by for actor only."""
        # Claim and complete
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Set up for approval
        chore_manager._handle_completion_criteria("chore-1", "kid-1", "Alice")

        # Verify Alice's completed_by is set
        kid1_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert kid1_data.get(const.DATA_CHORE_COMPLETED_BY) == "Alice"

        # Verify Bob's completed_by is not affected
        kid2_chores = chore_manager._coordinator.kids_data["kid-2"].get(
            const.DATA_KID_CHORE_DATA, {}
        )
        kid2_chore_data = kid2_chores.get("chore-1", {})
        assert const.DATA_CHORE_COMPLETED_BY not in kid2_chore_data

    def test_shared_first_completion(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test SHARED_FIRST completion updates other kids' completed_by."""
        # Change to SHARED_FIRST
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_SHARED_FIRST

        # Initialize both kids' chore data
        chore_manager._get_kid_chore_data("kid-1", "chore-1")
        chore_manager._get_kid_chore_data("kid-2", "chore-1")

        # Handle completion
        chore_manager._handle_completion_criteria("chore-1", "kid-1", "Alice")

        # Bob's completed_by should show Alice
        kid2_data = mock_coordinator.kids_data["kid-2"][const.DATA_KID_CHORE_DATA][
            "chore-1"
        ]
        assert kid2_data.get(const.DATA_CHORE_COMPLETED_BY) == "Alice"

    def test_shared_completion_appends_to_list(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test SHARED completion appends to completed_by list."""
        # Change to SHARED
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_SHARED

        # Initialize both kids' chore data
        chore_manager._get_kid_chore_data("kid-1", "chore-1")
        chore_manager._get_kid_chore_data("kid-2", "chore-1")

        # First completion
        chore_manager._handle_completion_criteria("chore-1", "kid-1", "Alice")

        # Both kids should have Alice in their list
        kid1_data = mock_coordinator.kids_data["kid-1"][const.DATA_KID_CHORE_DATA][
            "chore-1"
        ]
        assert kid1_data.get(const.DATA_CHORE_COMPLETED_BY) == ["Alice"]

        kid2_data = mock_coordinator.kids_data["kid-2"][const.DATA_KID_CHORE_DATA][
            "chore-1"
        ]
        assert kid2_data.get(const.DATA_CHORE_COMPLETED_BY) == ["Alice"]

        # Second completion by Bob
        chore_manager._handle_completion_criteria("chore-1", "kid-2", "Bob")

        # Both should now have both names
        assert "Alice" in kid1_data.get(const.DATA_CHORE_COMPLETED_BY, [])
        assert "Bob" in kid1_data.get(const.DATA_CHORE_COMPLETED_BY, [])


# ============================================================================
# Test Class: Event Payloads
# ============================================================================


class TestEventPayloads:
    """Tests for event payload contents."""

    @pytest.mark.asyncio
    async def test_claim_event_has_labels(self, chore_manager: ChoreManager) -> None:
        """Test claim event includes chore labels."""
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        call_args = chore_manager.emit.call_args
        assert call_args[1]["chore_labels"] == ["kitchen", "daily"]

    @pytest.mark.asyncio
    async def test_approve_event_has_rich_payload(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Test approval event includes rich payload for gamification."""
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        call_args = chore_manager.emit.call_args
        payload = call_args[1]

        # Verify rich payload fields
        assert "points_awarded" in payload
        assert "is_shared" in payload
        assert "is_multi_claim" in payload
        assert "chore_labels" in payload
        assert "multiplier_applied" in payload
        assert "previous_state" in payload
        assert "update_stats" in payload


# ============================================================================
# Test Class: Lock Management
# ============================================================================


class TestLockManagement:
    """Tests for asyncio lock management."""

    def test_get_lock_creates_new_lock(self, chore_manager: ChoreManager) -> None:
        """Test that get_lock creates a new lock for new key."""
        lock = chore_manager._get_lock("kid-1", "chore-1")
        assert lock is not None

    def test_get_lock_returns_same_lock(self, chore_manager: ChoreManager) -> None:
        """Test that get_lock returns same lock for same key."""
        lock1 = chore_manager._get_lock("kid-1", "chore-1")
        lock2 = chore_manager._get_lock("kid-1", "chore-1")
        assert lock1 is lock2

    def test_different_kids_get_different_locks(
        self, chore_manager: ChoreManager
    ) -> None:
        """Test that different kid+chore pairs get different locks."""
        lock1 = chore_manager._get_lock("kid-1", "chore-1")
        lock2 = chore_manager._get_lock("kid-2", "chore-1")
        assert lock1 is not lock2
