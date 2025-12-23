"""Tests for KidsChores services."""

import uuid
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kidschores.const import (
    ATTR_BONUS_NAME,
    ATTR_CHORE_NAME,
    ATTR_KID_NAME,
    ATTR_PENALTY_NAME,
    ATTR_REWARD_NAME,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_PENDING,
    COORDINATOR,
    DOMAIN,
    FIELD_PARENT_NAME,
    SERVICE_APPLY_BONUS,
    SERVICE_APPLY_PENALTY,
    SERVICE_APPROVE_CHORE,
    SERVICE_APPROVE_REWARD,
    SERVICE_CLAIM_CHORE,
    SERVICE_DISAPPROVE_CHORE,
    SERVICE_DISAPPROVE_REWARD,
    SERVICE_REDEEM_REWARD,
    SERVICE_REMOVE_AWARDED_BADGES,
    SERVICE_RESET_BONUSES,
    SERVICE_RESET_OVERDUE_CHORES,
    SERVICE_RESET_PENALTIES,
    SERVICE_RESET_REWARDS,
    SERVICE_SET_CHORE_DUE_DATE,
    SERVICE_SKIP_CHORE_DUE_DATE,
)

from .conftest import create_mock_chore_data, create_mock_kid_data


async def test_service_claim_chore_with_names(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test claim_chore service with kid_name and chore_name resolution."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    # Mock notifications to prevent ServiceNotFound errors
    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_name = "Zoë Stårblüm"
        kid_data = create_mock_kid_data(name=kid_name, points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create a chore (pass kid ID, not name)
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Feed the cåts",
            default_points=5.0,
            assigned_kids=[kid_id],  # Pass UUID, not name
        )
        chore_data["internal_id"] = chore_id
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access

        # Call the service with names
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLAIM_CHORE,
            {ATTR_KID_NAME: "Zoë Stårblüm", ATTR_CHORE_NAME: "Feed the cåts"},
            blocking=True,
        )

        # Verify chore was claimed - chore in kid's claimed list
        assert coordinator.chores_data[chore_id]["state"] == CHORE_STATE_CLAIMED
        assert chore_id in coordinator.kids_data[kid_id]["claimed_chores"]


async def test_service_approve_chore_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test approve_chore service workflow."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    # Mock notifications to prevent ServiceNotFound errors
    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_name = "Max! Stårblüm"
        kid_data = create_mock_kid_data(name=kid_name, points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create and claim a chore (pass kid ID, not name)
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Wåter the Plånts",
            default_points=7.0,
            assigned_kids=[kid_id],  # Pass UUID, not name
        )
        chore_data["internal_id"] = chore_id
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access
        coordinator.claim_chore(kid_id, chore_id, "Test User")

        # Approve via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_APPROVE_CHORE,
            {
                FIELD_PARENT_NAME: "Môm Astrid",
                ATTR_KID_NAME: "Max! Stårblüm",
                ATTR_CHORE_NAME: "Wåter the Plånts",
            },
            blocking=True,
        )

        # Verify approval and points awarded
        assert coordinator.kids_data[kid_id]["points"] == 7.0


async def test_service_apply_bonus_and_penalty(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test bonus and penalty services."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    # Mock notifications to prevent ServiceNotFound errors
    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Lila Stårblüm", points=50.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Create a bonus
        bonus_id = str(uuid.uuid4())
        bonus_data = {
            "internal_id": bonus_id,
            "name": "Stär Sprïnkle Bonus",
            "points": 15.0,
            "assigned_kids": [kid_id],
        }
        # pylint: disable=protected-access
        coordinator._data["bonuses"] = {bonus_id: bonus_data}
        # pylint: enable=protected-access

        # Apply bonus via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_APPLY_BONUS,
            {
                FIELD_PARENT_NAME: "Dad Leo",
                ATTR_KID_NAME: "Lila Stårblüm",
                ATTR_BONUS_NAME: "Stär Sprïnkle Bonus",
            },
            blocking=True,
        )

        # Verify bonus applied (50 + 15 = 65)
        assert coordinator.kids_data[kid_id]["points"] == 65.0

        # Create a penalty
        penalty_id = str(uuid.uuid4())
        penalty_data = {
            "internal_id": penalty_id,
            "name": "Førget Chöre",
            "points": -5.0,
            "assigned_kids": [kid_id],
        }
        # pylint: disable=protected-access
        coordinator._data["penalties"] = {penalty_id: penalty_data}
        # pylint: enable=protected-access

        # Apply penalty via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_APPLY_PENALTY,
            {
                FIELD_PARENT_NAME: "Môm Astrid",
                ATTR_KID_NAME: "Lila Stårblüm",
                ATTR_PENALTY_NAME: "Førget Chöre",
            },
            blocking=True,
        )

        # Verify penalty applied (65 - 5 = 60)
        assert coordinator.kids_data[kid_id]["points"] == 60.0


# =============================================================================
# ERROR SCENARIO TESTS (Phase 3a - Prerequisite Coverage)
# =============================================================================


async def test_service_claim_chore_invalid_kid_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test claim_chore service with invalid kid_name raises HomeAssistantError."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a chore (no kid needed for this test)
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Test Chore",
            default_points=5.0,
            assigned_kids=[],
        )
        chore_data["internal_id"] = chore_id
        # pylint: disable=protected-access
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access

        # Call service with invalid kid name
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CLAIM_CHORE,
                {ATTR_KID_NAME: "Nonexistent Kid", ATTR_CHORE_NAME: "Test Chore"},
                blocking=True,
            )
            assert False, "Expected HomeAssistantError to be raised"
        except HomeAssistantError as e:
            assert "Nonexistent Kid" in str(e)
            assert "not found" in str(e).lower()


async def test_service_claim_chore_invalid_chore_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test claim_chore service with invalid chore_name raises HomeAssistantError."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Call service with invalid chore name
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CLAIM_CHORE,
                {ATTR_KID_NAME: "Test Kid", ATTR_CHORE_NAME: "Nonexistent Chore"},
                blocking=True,
            )
            assert False, "Expected HomeAssistantError to be raised"
        except HomeAssistantError as e:
            assert "Nonexistent Chore" in str(e)
            assert "not found" in str(e).lower()


async def test_service_approve_chore_invalid_kid_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test approve_chore service with invalid kid_name raises HomeAssistantError."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a chore (no kid needed for this test)
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Test Chore",
            default_points=5.0,
            assigned_kids=[],
        )
        chore_data["internal_id"] = chore_id
        # pylint: disable=protected-access
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access

        # Call service with invalid kid name
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPROVE_CHORE,
                {
                    FIELD_PARENT_NAME: "Test Parent",
                    ATTR_KID_NAME: "Invalid Kid",
                    ATTR_CHORE_NAME: "Test Chore",
                },
                blocking=True,
            )
            assert False, "Expected HomeAssistantError to be raised"
        except HomeAssistantError as e:
            assert "Invalid Kid" in str(e)
            assert "not found" in str(e).lower()


async def test_service_approve_chore_invalid_chore_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test approve_chore service with invalid chore_name raises HomeAssistantError."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Call service with invalid chore name
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPROVE_CHORE,
                {
                    FIELD_PARENT_NAME: "Test Parent",
                    ATTR_KID_NAME: "Test Kid",
                    ATTR_CHORE_NAME: "Invalid Chore",
                },
                blocking=True,
            )
            assert False, "Expected HomeAssistantError to be raised"
        except HomeAssistantError as e:
            assert "Invalid Chore" in str(e)
            assert "not found" in str(e).lower()


async def test_service_apply_bonus_invalid_kid_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test apply_bonus service with invalid kid_name raises HomeAssistantError."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a bonus (no kid needed for this test)
        bonus_id = str(uuid.uuid4())
        bonus_data = {
            "internal_id": bonus_id,
            "name": "Test Bonus",
            "points": 10.0,
            "assigned_kids": [],
        }
        # pylint: disable=protected-access
        coordinator._data["bonuses"] = {bonus_id: bonus_data}
        # pylint: enable=protected-access

        # Call service with invalid kid name
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPLY_BONUS,
                {
                    FIELD_PARENT_NAME: "Test Parent",
                    ATTR_KID_NAME: "Invalid Kid",
                    ATTR_BONUS_NAME: "Test Bonus",
                },
                blocking=True,
            )
            assert False, "Expected HomeAssistantError to be raised"
        except HomeAssistantError as e:
            assert "Invalid Kid" in str(e)
            assert "not found" in str(e).lower()


async def test_service_apply_bonus_invalid_bonus_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test apply_bonus service with invalid bonus_name raises HomeAssistantError."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Call service with invalid bonus name
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPLY_BONUS,
                {
                    FIELD_PARENT_NAME: "Test Parent",
                    ATTR_KID_NAME: "Test Kid",
                    ATTR_BONUS_NAME: "Invalid Bonus",
                },
                blocking=True,
            )
            assert False, "Expected HomeAssistantError to be raised"
        except HomeAssistantError as e:
            assert "Invalid Bonus" in str(e)
            assert "not found" in str(e).lower()


async def test_service_apply_penalty_invalid_penalty_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test apply_penalty service with invalid penalty_name raises HomeAssistantError."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=50.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Call service with invalid penalty name
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_APPLY_PENALTY,
                {
                    FIELD_PARENT_NAME: "Test Parent",
                    ATTR_KID_NAME: "Test Kid",
                    ATTR_PENALTY_NAME: "Invalid Penalty",
                },
                blocking=True,
            )
            assert False, "Expected HomeAssistantError to be raised"
        except HomeAssistantError as e:
            assert "Invalid Penalty" in str(e)
            assert "not found" in str(e).lower()


# =============================================================================
# UNTESTED HANDLER SUCCESS TESTS (Phase 3a - Prerequisite Coverage)
# =============================================================================


async def test_service_disapprove_chore_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test disapprove_chore service workflow."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_name = "Test Kid"
        kid_data = create_mock_kid_data(name=kid_name, points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create and claim a chore
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Test Chore",
            default_points=10.0,
            assigned_kids=[kid_id],
        )
        chore_data["internal_id"] = chore_id
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access
        coordinator.claim_chore(kid_id, chore_id, "Test User")

        # Verify chore is claimed
        assert coordinator.chores_data[chore_id]["state"] == CHORE_STATE_CLAIMED

        # Disapprove via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISAPPROVE_CHORE,
            {
                FIELD_PARENT_NAME: "Test Parent",
                ATTR_KID_NAME: kid_name,
                ATTR_CHORE_NAME: "Test Chore",
            },
            blocking=True,
        )

        # Verify chore returned to pending state and not in claimed list
        assert coordinator.chores_data[chore_id]["state"] == CHORE_STATE_PENDING
        assert chore_id not in coordinator.kids_data[kid_id]["claimed_chores"]
        assert coordinator.kids_data[kid_id]["points"] == 0.0  # No points awarded


async def test_service_redeem_reward_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test redeem_reward service workflow."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid with points
        kid_id = str(uuid.uuid4())
        kid_name = "Rich Kid"
        kid_data = create_mock_kid_data(name=kid_name, points=100.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create a reward
        reward_id = str(uuid.uuid4())
        reward_data = {
            "internal_id": reward_id,
            "name": "Ice Cream",
            "cost": 25.0,
            "assigned_kids": [kid_id],
        }
        coordinator._data["rewards"] = {reward_id: reward_data}
        # pylint: enable=protected-access

        # Redeem reward via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REDEEM_REWARD,
            {
                FIELD_PARENT_NAME: "Test Parent",
                ATTR_KID_NAME: kid_name,
                ATTR_REWARD_NAME: "Ice Cream",
            },
            blocking=True,
        )

        # Verify reward is in pending approvals
        pending = coordinator._data.get("pending_reward_approvals", [])  # pylint: disable=protected-access
        assert len(pending) > 0
        assert any(
            p.get("kid_id") == kid_id and p.get("reward_id") == reward_id
            for p in pending
        )


async def test_service_disapprove_reward_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test disapprove_reward service workflow."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid with points
        kid_id = str(uuid.uuid4())
        kid_name = "Test Kid"
        kid_data = create_mock_kid_data(name=kid_name, points=100.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create a reward
        reward_id = str(uuid.uuid4())
        reward_data = {
            "internal_id": reward_id,
            "name": "Test Reward",
            "cost": 25.0,
            "assigned_kids": [kid_id],
        }
        coordinator._data["rewards"] = {reward_id: reward_data}

        # Add to pending approvals
        coordinator._data["pending_approvals"] = [
            {
                "kid_id": kid_id,
                "reward_id": reward_id,
                "request_date": "2025-01-01T12:00:00+00:00",
            }
        ]
        # pylint: enable=protected-access

        initial_points = coordinator.kids_data[kid_id]["points"]

        # Disapprove reward via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISAPPROVE_REWARD,
            {
                FIELD_PARENT_NAME: "Test Parent",
                ATTR_KID_NAME: kid_name,
                ATTR_REWARD_NAME: "Test Reward",
            },
            blocking=True,
        )

        # Verify reward removed from pending and points not deducted
        pending = coordinator._data.get("pending_reward_approvals", [])  # pylint: disable=protected-access
        assert not any(
            p.get("kid_id") == kid_id and p.get("reward_id") == reward_id
            for p in pending
        )
        assert coordinator.kids_data[kid_id]["points"] == initial_points


async def test_service_reset_overdue_chores_all(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test reset_overdue_chores service resets all overdue chores."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create an overdue chore with recurring frequency and due date
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Overdue Chore",
            default_points=5.0,
            assigned_kids=[kid_id],
        )
        chore_data["internal_id"] = chore_id
        chore_data["state"] = "overdue"
        chore_data["recurring_frequency"] = "daily"  # Must be recurring to reschedule
        chore_data["due_date"] = "2025-01-01T12:00:00+00:00"  # Must have due date
        coordinator._create_chore(chore_id, chore_data)

        # Add chore to kid's overdue list so reset_overdue_chores finds it
        coordinator.kids_data[kid_id]["overdue_chores"] = [chore_id]
        # pylint: enable=protected-access

        # Reset all overdue chores via service (no parameters)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_OVERDUE_CHORES,
            {},
            blocking=True,
        )

        # Verify chore state reset to pending
        assert coordinator.chores_data[chore_id]["state"] == CHORE_STATE_PENDING


async def test_service_reset_penalties_all(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test reset_penalties service resets all kid penalties."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid with applied penalty
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=50.0)
        kid_data["internal_id"] = kid_id
        kid_data["penalty_applies"] = {"penalty1": {"applied_date": "2025-01-01"}}
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Verify penalty exists
        assert len(coordinator.kids_data[kid_id]["penalty_applies"]) > 0

        # Reset all penalties via service (no parameters)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_PENALTIES,
            {},
            blocking=True,
        )

        # Verify penalty cleared
        assert len(coordinator.kids_data[kid_id]["penalty_applies"]) == 0


async def test_service_reset_bonuses_all(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test reset_bonuses service resets all kid bonuses."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid with applied bonus
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=50.0)
        kid_data["internal_id"] = kid_id
        kid_data["bonus_applies"] = {"bonus1": {"applied_date": "2025-01-01"}}
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Verify bonus exists
        assert len(coordinator.kids_data[kid_id]["bonus_applies"]) > 0

        # Reset all bonuses via service (no parameters)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_BONUSES,
            {},
            blocking=True,
        )

        # Verify bonus cleared
        assert len(coordinator.kids_data[kid_id]["bonus_applies"]) == 0


async def test_service_approve_reward_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test approve_reward service deducts points."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid with points
        kid_id = str(uuid.uuid4())
        kid_name = "Test Kid"
        kid_data = create_mock_kid_data(name=kid_name, points=100.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create a reward
        reward_id = str(uuid.uuid4())
        reward_data = {
            "internal_id": reward_id,
            "name": "Test Reward",
            "cost": 25.0,
            "assigned_kids": [kid_id],
        }
        coordinator._data["rewards"] = {reward_id: reward_data}

        # Redeem the reward first to create pending approval
        coordinator.redeem_reward("Test Parent", kid_id, reward_id)
        # pylint: enable=protected-access

        initial_points = coordinator.kids_data[kid_id]["points"]
        assert initial_points == 100.0

        # Approve reward via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_APPROVE_REWARD,
            {
                FIELD_PARENT_NAME: "Test Parent",
                ATTR_KID_NAME: kid_name,
                ATTR_REWARD_NAME: "Test Reward",
            },
            blocking=True,
        )

        # Verify points deducted and reward removed from pending
        assert coordinator.kids_data[kid_id]["points"] == 75.0  # 100 - 25
        assert reward_id not in coordinator.kids_data[kid_id].get("pending_rewards", [])


async def test_service_reset_rewards_all(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test reset_rewards service resets reward claim counts."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid with reward claims
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=50.0)
        kid_data["internal_id"] = kid_id
        kid_data["reward_claims"] = {"reward1": 3, "reward2": 5}
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Verify reward claims exist
        assert len(coordinator.kids_data[kid_id]["reward_claims"]) == 2

        # Reset all rewards via service (no parameters)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_REWARDS,
            {},
            blocking=True,
        )

        # Verify reward claims cleared
        assert len(coordinator.kids_data[kid_id]["reward_claims"]) == 0


async def test_service_remove_awarded_badges_all(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test remove_awarded_badges service removes badges."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create badge entities first (coordinator only clears badges that exist in badges_data)
        badge1_id = str(uuid.uuid4())
        badge2_id = str(uuid.uuid4())
        badge1_data = {
            "name": "Badge 1",
            "badge_type": "achievement",
            "internal_id": badge1_id,
        }
        badge2_data = {
            "name": "Badge 2",
            "badge_type": "achievement",
            "internal_id": badge2_id,
        }
        # pylint: disable=protected-access
        coordinator._create_badge(badge1_id, badge1_data)
        coordinator._create_badge(badge2_id, badge2_data)

        # Create a kid with earned badges
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid", points=50.0)
        kid_data["internal_id"] = kid_id
        kid_data["badges_earned"] = {
            badge1_id: {"internal_id": badge1_id, "last_awarded_date": "2025-01-01"},
            badge2_id: {"internal_id": badge2_id, "last_awarded_date": "2025-01-02"},
        }
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Verify badges exist
        assert len(coordinator.kids_data[kid_id]["badges_earned"]) == 2

        # Remove all badges via service (no parameters)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_AWARDED_BADGES,
            {},
            blocking=True,
        )

        # Verify badges removed
        assert len(coordinator.kids_data[kid_id]["badges_earned"]) == 0


async def test_service_set_chore_due_date_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test set_chore_due_date service sets due date."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid")
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create a chore without due date
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Test Chore",
            default_points=5.0,
            assigned_kids=[kid_id],
        )
        chore_data["internal_id"] = chore_id
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access

        # Verify no due date initially
        assert coordinator.chores_data[chore_id].get("due_date") is None

        # Set due date via service (future date)
        future_date = "2026-12-31T23:59:00+00:00"
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CHORE_DUE_DATE,
            {
                ATTR_CHORE_NAME: "Test Chore",
                "due_date": future_date,
            },
            blocking=True,
        )

        # Verify due date is set
        assert coordinator.chores_data[chore_id].get("due_date") is not None


async def test_service_skip_chore_due_date_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test skip_chore_due_date service reschedules recurring chore."""
    coordinator = hass.data[DOMAIN][init_integration.entry_id][COORDINATOR]

    with patch.object(coordinator, "_notify_kid", new=AsyncMock()):
        # Create a kid
        kid_id = str(uuid.uuid4())
        kid_data = create_mock_kid_data(name="Test Kid")
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create a recurring chore with due date
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Weekly Chore",
            default_points=5.0,
            assigned_kids=[kid_id],
        )
        chore_data["internal_id"] = chore_id
        chore_data["recurring_frequency"] = "weekly"
        chore_data["due_date"] = "2025-12-25T12:00:00+00:00"
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access

        original_due_date = coordinator.chores_data[chore_id]["due_date"]

        # Skip due date via service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SKIP_CHORE_DUE_DATE,
            {
                ATTR_CHORE_NAME: "Weekly Chore",
            },
            blocking=True,
        )

        # Verify due date was rescheduled (changed from original)
        new_due_date = coordinator.chores_data[chore_id]["due_date"]
        assert new_due_date != original_due_date
        assert coordinator.chores_data[chore_id]["state"] == CHORE_STATE_PENDING


# ============================================================================
# HELPER FUNCTION DEMONSTRATIONS - Testing Standards Maturity Initiative
# ============================================================================
# Added: 2025-12-20 (Phase 1)
# Purpose: Demonstrate new helper functions for cleaner test code
# See: tests/conftest.py for helper implementations
# ============================================================================


async def test_helper_construct_entity_id_demonstration(
    hass: HomeAssistant,
    scenario_minimal: tuple[MockConfigEntry, dict[str, str]],
) -> None:
    """Demonstrate construct_entity_id() helper - eliminates entity ID construction.

    BEFORE (old pattern):
        kid_slug = kid_name.lower().replace(" ", "_")
        entity_id = f"sensor.kc_{kid_slug}_points"

    AFTER (new helper):
        entity_id = construct_entity_id("sensor", kid_name, "points")
    """
    from tests.conftest import construct_entity_id

    # Get existing kid from scenario
    entry, name_map = scenario_minimal  # pylint: disable=unused-variable
    kid_name = "Zoë"

    # OLD PATTERN: Manual entity ID construction (6+ lines of boilerplate)
    # kid_slug = kid_name.lower().replace(" ", "_").replace("ë", "e")
    # entity_id = f"sensor.kc_{kid_slug}_points"

    # NEW PATTERN: Use helper for clean entity ID construction (1 line)
    entity_id = construct_entity_id("sensor", kid_name, "points")

    # Verify entity ID is correctly formatted (HA normalizes diacritics: ë → e)
    assert entity_id == "sensor.kc_zoe_points"

    # Verify state exists (entity was created by integration)
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} should exist"


async def test_helper_assert_entity_state_demonstration(
    hass: HomeAssistant,
    scenario_minimal: tuple[MockConfigEntry, dict[str, str]],
) -> None:
    """Demonstrate assert_entity_state() helper - one-line entity verification.

    BEFORE (old pattern):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "85"
        assert state.attributes.get("unit_of_measurement") == "points"

    AFTER (new helper):
        await assert_entity_state(hass, entity_id, "85", {"unit_of_measurement": "points"})
    """
    from tests.conftest import assert_entity_state, construct_entity_id

    # Get existing kid from scenario
    entry, name_map = scenario_minimal  # pylint: disable=unused-variable
    kid_name = "Zoë"
    entity_id = construct_entity_id("sensor", kid_name, "points")

    # OLD PATTERN: Multiple lines to verify entity state (4+ lines)
    # state = hass.states.get(entity_id)
    # assert state is not None, f"Entity {entity_id} not found"
    # assert state.state == "85", f"Expected 85, got {state.state}"
    # assert state.attributes.get("unit_of_measurement") == "points"

    # NEW PATTERN: One-line entity state verification
    # Note: scenario_minimal fixture loads Zoë with 10 points
    await assert_entity_state(
        hass,
        entity_id,
        "10.0",  # Expected state from scenario_minimal fixture
        {"unit_of_measurement": "Points"},  # Note: Capital P in integration
    )

    # Helper returns state object for additional assertions if needed
    state = await assert_entity_state(hass, entity_id, "10.0")
    assert float(state.state) >= 0.0, "Points should be non-negative"
