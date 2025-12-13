"""Tests for KidsChores services."""

import uuid
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kidschores.const import (
    ATTR_BONUS_NAME,
    ATTR_CHORE_NAME,
    ATTR_KID_NAME,
    ATTR_PENALTY_NAME,
    CHORE_STATE_CLAIMED,
    COORDINATOR,
    DOMAIN,
    FIELD_PARENT_NAME,
    SERVICE_APPLY_BONUS,
    SERVICE_APPLY_PENALTY,
    SERVICE_APPROVE_CHORE,
    SERVICE_CLAIM_CHORE,
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
        kid_name = "Alice"
        kid_data = create_mock_kid_data(name=kid_name, points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create a chore (pass kid name, not ID)
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Dishes",
            default_points=10.0,
            assigned_kids=[kid_name],  # Pass name, not ID
        )
        chore_data["internal_id"] = chore_id
        coordinator._create_chore(chore_id, chore_data)
        # pylint: enable=protected-access

        # Call the service with names
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLAIM_CHORE,
            {ATTR_KID_NAME: "Alice", ATTR_CHORE_NAME: "Dishes"},
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
        kid_name = "Bob"
        kid_data = create_mock_kid_data(name=kid_name, points=0.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)

        # Create and claim a chore (pass kid name, not ID)
        chore_id = str(uuid.uuid4())
        chore_data = create_mock_chore_data(
            name="Vacuum",
            default_points=15.0,
            assigned_kids=[kid_name],  # Pass name, not ID
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
                FIELD_PARENT_NAME: "Test Parent",
                ATTR_KID_NAME: "Bob",
                ATTR_CHORE_NAME: "Vacuum",
            },
            blocking=True,
        )

        # Verify approval and points awarded
        assert coordinator.kids_data[kid_id]["points"] == 15.0


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
        kid_data = create_mock_kid_data(name="Charlie", points=50.0)
        kid_data["internal_id"] = kid_id
        # pylint: disable=protected-access
        coordinator._create_kid(kid_id, kid_data)
        # pylint: enable=protected-access

        # Create a bonus
        bonus_id = str(uuid.uuid4())
        bonus_data = {
            "internal_id": bonus_id,
            "name": "Good Behavior",
            "points": 10.0,
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
                FIELD_PARENT_NAME: "Test Parent",
                ATTR_KID_NAME: "Charlie",
                ATTR_BONUS_NAME: "Good Behavior",
            },
            blocking=True,
        )

        # Verify bonus applied
        assert coordinator.kids_data[kid_id]["points"] == 60.0

        # Create a penalty
        penalty_id = str(uuid.uuid4())
        penalty_data = {
            "internal_id": penalty_id,
            "name": "Broke Rule",
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
                FIELD_PARENT_NAME: "Test Parent",
                ATTR_KID_NAME: "Charlie",
                ATTR_PENALTY_NAME: "Broke Rule",
            },
            blocking=True,
        )

        # Verify penalty applied
        assert coordinator.kids_data[kid_id]["points"] == 55.0
