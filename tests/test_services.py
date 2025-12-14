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
