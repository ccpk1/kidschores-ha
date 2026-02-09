"""Test Phase 1: Pipeline Ordering Fix (CHORE_STATE_ARCHITECTURE_REVIEW Phase 1).

Tests the Reset-Before-Overdue processing order, non-recurring past-due guard,
auto-approve atomicity, and persist batching.

Validates fixes for:
- Gremlin #4 (Re-Overdue Loop / Issue #237)
- Gremlin #5 (Phantom Overdue After Reset)
- Gremlin #6 (Auto-Approve Race)

Reference:
- CHORE_STATE_ARCHITECTURE_REVIEW_SUP_TECH_SPEC.md § Phase 1
- CHORE_STATE_ARCHITECTURE_REVIEW_IN-PROCESS.md § Section B
"""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.kidschores import const
from custom_components.kidschores.utils import dt_utils

from .helpers.constants import DATA_CHORE_NAME, DATA_KID_NAME
from .helpers.setup import setup_from_yaml

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_kid_by_name(coordinator: Any, name: str) -> str | None:
    """Find a kid by name and return their internal_id."""
    for kid_id, kid_info in coordinator.kids_data.items():
        if kid_info.get(DATA_KID_NAME) == name:
            return kid_id
    return None


def get_chore_by_name(coordinator: Any, name: str) -> str | None:
    """Find a chore by name and return its internal_id."""
    for chore_id, chore_info in coordinator.chores_data.items():
        if chore_info.get(DATA_CHORE_NAME) == name:
            return chore_id
    return None


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def minimal_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
):
    """Load minimal scenario for Phase 1 tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class TestPipelineOrdering:
    """Test that reset processes before overdue (Phase 1.1, 1.2)."""

    async def test_midnight_processes_reset_before_overdue(
        self,
        hass: HomeAssistant,
        minimal_scenario,
    ) -> None:
        """T1.1: Midnight handler processes resets before overdue checks."""
        coordinator = minimal_scenario.coordinator

        # Setup: Create chore with AT_MIDNIGHT_ONCE reset + past due
        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Create APPROVED chore with past due date + AT_MIDNIGHT_ONCE reset
        chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Reset Before Overdue Test",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
                const.SERVICE_FIELD_POINTS: 10,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() - timedelta(days=1)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        chore_id = chore_response["chore_id"]

        # Approve the chore
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # Verify chore is APPROVED
        chore = coordinator.chores_data[chore_id]
        assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_APPROVED

        # Trigger midnight rollover
        await coordinator.chore_manager._on_midnight_rollover()

        # Assert: Chore should be PENDING (reset), not OVERDUE
        # The reset should process FIRST, clearing the APPROVED state
        # Then overdue check sees PENDING but should NOT mark it overdue immediately
        # because it just reset
        chore = coordinator.chores_data[chore_id]
        assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING
        assert const.DATA_CHORE_OVERDUE_SINCE not in chore

    async def test_periodic_processes_reset_before_overdue(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.2: Periodic handler processes resets before overdue checks."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Create APPROVED chore with past due date + AT_DUE_DATE_ONCE reset
        chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Periodic Reset Before Overdue",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_WEEKLY,
                const.SERVICE_FIELD_POINTS: 15,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() - timedelta(hours=1)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        chore_id = chore_response["chore_id"]

        # Approve the chore
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # Trigger periodic update
        await coordinator.chore_manager._on_periodic_update()

        # Assert: Chore should be PENDING (reset), not OVERDUE
        chore = coordinator.chores_data[chore_id]
        assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING
        assert const.DATA_CHORE_OVERDUE_SINCE not in chore

    async def test_overdue_excluded_when_chore_just_reset(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.3: Filtered overdue list excludes reset pairs."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Create two chores:
        # 1. APPROVED + AT_MIDNIGHT_ONCE (should reset)
        # 2. PENDING + past due (should go overdue)

        reset_chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Reset Chore",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
                const.SERVICE_FIELD_POINTS: 10,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() - timedelta(days=1)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        reset_chore_id = reset_chore_response["chore_id"]

        overdue_chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Overdue Chore",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_WEEKLY,
                const.SERVICE_FIELD_POINTS: 20,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() - timedelta(hours=2)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        overdue_chore_id = overdue_chore_response["chore_id"]

        # Approve reset_chore (so it's in APPROVED state for reset)
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: reset_chore_id,
            },
            blocking=True,
        )

        # Trigger midnight - reset_chore should reset, overdue_chore should go overdue
        await coordinator.chore_manager._on_midnight_rollover()

        # Assert: reset_chore is PENDING (not overdue), overdue_chore is OVERDUE
        reset_chore = coordinator.chores_data[reset_chore_id]
        overdue_chore = coordinator.chores_data[overdue_chore_id]

        assert reset_chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING
        assert const.DATA_CHORE_OVERDUE_SINCE not in reset_chore

        assert overdue_chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_OVERDUE
        assert const.DATA_CHORE_OVERDUE_SINCE in overdue_chore


class TestNonRecurringPastDueGuard:
    """Test non-recurring past-due guard (Phase 1.4, 1.5)."""

    async def test_upon_completion_freq_none_clears_due_date(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.4: UPON_COMPLETION + FREQUENCY_NONE clears past due date on reset."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Create non-recurring chore with UPON_COMPLETION + past due date
        chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "One-Time Task",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_NONE,
                const.SERVICE_FIELD_POINTS: 50,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() - timedelta(days=2)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        chore_id = chore_response["chore_id"]

        # Claim and approve the chore
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # Assert: Due date should be cleared (non-recurring guard)
        chore = coordinator.chores_data[chore_id]
        per_kid_due_dates = chore.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})

        # For INDEPENDENT chores, per-kid due date should be removed
        assert zoe_id not in per_kid_due_dates or per_kid_due_dates[zoe_id] is None

    async def test_upon_completion_freq_none_no_re_overdue(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.5: Full cycle - approve → reset → no re-overdue (Issue #237 regression test)."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Reproduce Issue #237 scenario:
        # 1. Non-recurring chore (FREQUENCY_NONE)
        # 2. UPON_COMPLETION reset
        # 3. Past due date
        chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Issue #237 Regression",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_NONE,
                const.SERVICE_FIELD_POINTS: 100,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() - timedelta(days=5)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        chore_id = chore_response["chore_id"]

        # Claim and approve (triggers UPON_COMPLETION immediate reset)
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # Chore should now be PENDING with NO due date
        chore = coordinator.chores_data[chore_id]
        assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING

        # Trigger periodic update (simulate next scan)
        await coordinator.chore_manager._on_periodic_update()

        # Assert: Chore should STILL be PENDING (not re-marked OVERDUE)
        chore = coordinator.chores_data[chore_id]
        assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING
        assert const.DATA_CHORE_OVERDUE_SINCE not in chore


class TestAutoApproveAtomicity:
    """Test auto-approve atomicity fix (Phase 1.6)."""

    async def test_auto_approve_is_atomic_with_claim(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.6: Auto-approve runs inline (await), not as background task."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Create chore with AUTO_APPROVE pending claim action
        chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Auto-Approve Test",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
                const.SERVICE_FIELD_POINTS: 10,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_PENDING_CLAIM_ACTION: const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() + timedelta(days=1)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        chore_id = chore_response["chore_id"]

        # Approve (to set up for reset)
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # Claim it (puts it in CLAIMED state)
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # Trigger midnight reset
        await coordinator.chore_manager._on_midnight_rollover()

        # With AUTO_APPROVE + HOLD action:
        # Reset should process HOLD (retain CLAIMED) → auto-approve inline
        # State should be PENDING (after auto-approve + UPON_COMPLETION would reset)
        # OR APPROVED if reset type doesn't immediate-reset
        chore = coordinator.chores_data[chore_id]

        # After auto-approve with AT_MIDNIGHT_ONCE, chore resets at next midnight
        # So immediately after midnight with a pending claim auto-approve:
        # 1. Reset processes (AT_MIDNIGHT_ONCE boundary reached)
        # 2. Pending claim = CLAIMED → AUTO_APPROVE kicks in
        # 3. Auto-approve runs INLINE (not background task)
        # Result: APPROVED state (atomically transitioned)
        assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_APPROVED

    async def test_auto_approve_shared_first_no_race(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.7: SHARED_FIRST + auto-approve has no intermediate state leak."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")
        alice_id = get_kid_by_name(coordinator, "Alice")

        # Create SHARED_FIRST chore with AUTO_APPROVE
        chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Shared Auto-Approve",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id, alice_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_WEEKLY,
                const.SERVICE_FIELD_POINTS: 20,
                const.SERVICE_FIELD_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_PENDING_CLAIM_ACTION: const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() + timedelta(days=1)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        chore_id = chore_response["chore_id"]

        # Zoe claims first
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # With auto-approve, Zoe should be APPROVED immediately (atomic)
        chore = coordinator.chores_data[chore_id]
        zoe_chore_data = coordinator._data[const.DATA_KIDS][zoe_id][
            const.DATA_KID_CHORE_DATA
        ][chore_id]

        # Auto-approve should have run inline - Zoe's state should be APPROVED
        assert (
            zoe_chore_data[const.DATA_KID_CHORE_DATA_STATE]
            == const.CHORE_STATE_APPROVED
        )

        # Alice should NOT be able to claim (SHARED_FIRST + Zoe already approved)
        with pytest.raises(Exception):  # ServiceValidationError expected
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_CLAIM_CHORE,
                {
                    const.SERVICE_FIELD_KID_ID: alice_id,
                    const.SERVICE_FIELD_CHORE_ID: chore_id,
                },
                blocking=True,
            )


class TestPersistBatching:
    """Test persist batching (Phase 1.5)."""

    async def test_pipeline_single_persist_per_tick(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.8: Verify persist called once per pipeline, not per entry."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Create 3 chores that will reset at midnight
        chore_ids = []
        for i in range(3):
            chore_response = await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_ADD_CHORE,
                {
                    const.SERVICE_FIELD_NAME: f"Batch Test Chore {i + 1}",
                    const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                    const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
                    const.SERVICE_FIELD_POINTS: 10 * (i + 1),
                    const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                    const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                    const.SERVICE_FIELD_DUE_DATE: (
                        dt_utils.dt_now() + timedelta(days=1)
                    ).isoformat(),
                },
                blocking=True,
                return_response=True,
            )
            chore_ids.append(chore_response["chore_id"])

            # Approve each chore
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_CLAIM_CHORE,
                {
                    const.SERVICE_FIELD_KID_ID: zoe_id,
                    const.SERVICE_FIELD_CHORE_ID: chore_response["chore_id"],
                },
                blocking=True,
            )
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_APPROVE_CHORE,
                {
                    const.SERVICE_FIELD_KID_ID: zoe_id,
                    const.SERVICE_FIELD_CHORE_ID: chore_response["chore_id"],
                },
                blocking=True,
            )

        # Mock _persist to count calls
        with patch.object(coordinator, "_persist", new=AsyncMock()) as mock_persist:
            # Trigger midnight rollover (should reset all 3 chores)
            await coordinator.chore_manager._on_midnight_rollover()

            # Assert: _persist called exactly ONCE (batch pattern)
            assert mock_persist.call_count == 1

        # Verify all chores were reset
        for chore_id in chore_ids:
            chore = coordinator.chores_data[chore_id]
            assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING


class TestPhase1ReturnTypes:
    """Test Phase 1 API changes."""

    async def test_process_approval_reset_returns_pairs(
        self,
        hass: HomeAssistant,
        minimal_scenario,
        # scenario_medium removed - using minimal_scenario
    ) -> None:
        """T1.9: Return type is tuple[int, set[tuple[str, str]]]."""
        coordinator = minimal_scenario.coordinator

        zoe_id = get_kid_by_name(coordinator, "Zoe")

        # Create chore with AT_MIDNIGHT_ONCE reset
        chore_response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_ADD_CHORE,
            {
                const.SERVICE_FIELD_NAME: "Return Type Test",
                const.SERVICE_FIELD_ASSIGNED_KIDS: [zoe_id],
                const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
                const.SERVICE_FIELD_POINTS: 10,
                const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
                const.SERVICE_FIELD_DUE_DATE: (
                    dt_utils.dt_now() + timedelta(days=1)
                ).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        chore_id = chore_response["chore_id"]

        # Approve chore
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_KID_ID: zoe_id,
                const.SERVICE_FIELD_CHORE_ID: chore_id,
            },
            blocking=True,
        )

        # Call process_time_checks to get scan
        now_utc = dt_utils.dt_now()
        scan = coordinator.chore_manager.process_time_checks(
            now_utc, trigger="midnight"
        )

        # Call _process_approval_reset_entries directly
        (
            reset_count,
            reset_pairs,
        ) = await coordinator.chore_manager._process_approval_reset_entries(
            scan, now_utc, "midnight", persist=False
        )

        # Assert: Return type is tuple with count + set of pairs
        assert isinstance(reset_count, int)
        assert isinstance(reset_pairs, set)
        assert reset_count == 1
        assert (zoe_id, chore_id) in reset_pairs
