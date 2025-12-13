"""Shared fixtures for KidsChores tests."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kidschores.const import (
    CONF_POINTS_ICON,
    CONF_POINTS_LABEL,
    DATA_ACHIEVEMENTS,
    DATA_BADGES,
    DATA_BONUSES,
    DATA_CHALLENGES,
    DATA_CHORES,
    DATA_KIDS,
    DATA_PARENTS,
    DATA_PENALTIES,
    DATA_REWARDS,
    DEFAULT_POINTS_ICON,
    DEFAULT_POINTS_LABEL,
    DOMAIN,
    SCHEMA_VERSION_STORAGE_ONLY,
)

# pylint: disable=invalid-name
pytest_plugins = "pytest_homeassistant_custom_component"
# pylint: enable=invalid-name


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> Any:
    """Enable custom integrations in tests."""
    # pylint: disable=unused-argument
    yield


@pytest.fixture
async def mock_hass_users(hass: HomeAssistant) -> dict[str, Any]:
    """Create mock Home Assistant users for testing."""
    # Create admin user
    admin_user = await hass.auth.async_create_user(
        "Admin User",
        group_ids=["system-admin"],
    )

    # Create parent users
    parent1_user = await hass.auth.async_create_user(
        "Parent One",
        group_ids=["system-users"],
    )
    parent2_user = await hass.auth.async_create_user(
        "Parent Two",
        group_ids=["system-users"],
    )

    # Create kid users
    kid1_user = await hass.auth.async_create_user(
        "Kid One",
        group_ids=["system-users"],
    )
    kid2_user = await hass.auth.async_create_user(
        "Kid Two",
        group_ids=["system-users"],
    )

    return {
        "admin": admin_user,
        "parent1": parent1_user,
        "parent2": parent2_user,
        "kid1": kid1_user,
        "kid2": kid2_user,
    }


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="KidsChores",
        data={
            "schema_version": SCHEMA_VERSION_STORAGE_ONLY,
        },
        options={
            CONF_POINTS_LABEL: DEFAULT_POINTS_LABEL,
            CONF_POINTS_ICON: DEFAULT_POINTS_ICON,
        },
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )


@pytest.fixture
def mock_storage_data() -> dict[str, dict]:
    """Return mock storage data structure."""
    return {
        DATA_KIDS: {},
        DATA_PARENTS: {},
        DATA_CHORES: {},
        DATA_BADGES: {},
        DATA_REWARDS: {},
        DATA_BONUSES: {},
        DATA_PENALTIES: {},
        DATA_ACHIEVEMENTS: {},
        DATA_CHALLENGES: {},
    }


@pytest.fixture
def mock_storage_manager(
    mock_storage_data: dict[str, dict],  # pylint: disable=redefined-outer-name
) -> MagicMock:
    """Return a mock storage manager."""
    mock = MagicMock()
    mock.data = mock_storage_data
    mock.async_load = AsyncMock(return_value=mock_storage_data)
    mock.async_save = AsyncMock()
    return mock


@pytest.fixture
def mock_coordinator(
    mock_storage_data: dict[str, dict],  # pylint: disable=redefined-outer-name
) -> MagicMock:
    """Return a mock coordinator."""
    mock = MagicMock()
    mock.data = mock_storage_data
    mock.kids_data = mock_storage_data[DATA_KIDS]
    mock.parents_data = mock_storage_data[DATA_PARENTS]
    mock.chores_data = mock_storage_data[DATA_CHORES]
    mock.badges_data = mock_storage_data[DATA_BADGES]
    mock.rewards_data = mock_storage_data[DATA_REWARDS]
    mock.bonuses_data = mock_storage_data[DATA_BONUSES]
    mock.penalties_data = mock_storage_data[DATA_PENALTIES]
    mock.achievements_data = mock_storage_data[DATA_ACHIEVEMENTS]
    mock.challenges_data = mock_storage_data[DATA_CHALLENGES]
    mock.async_refresh = AsyncMock()
    mock.async_update_listeners = MagicMock()
    # pylint: disable=protected-access
    mock._persist = AsyncMock()

    # Mock CRUD methods
    mock._create_kid = MagicMock()
    mock._create_parent = MagicMock()
    mock._create_chore = MagicMock()
    mock._create_badge = MagicMock()
    mock._create_reward = MagicMock()
    mock._create_bonus = MagicMock()
    mock._create_penalty = MagicMock()
    mock._create_achievement = MagicMock()
    mock._create_challenge = MagicMock()
    # pylint: enable=protected-access

    mock.update_kid_entity = MagicMock()
    mock.update_parent_entity = MagicMock()
    mock.update_chore_entity = MagicMock()
    mock.update_badge_entity = MagicMock()
    mock.update_reward_entity = MagicMock()
    mock.update_bonus_entity = MagicMock()
    mock.update_penalty_entity = MagicMock()
    mock.update_achievement_entity = MagicMock()
    mock.update_challenge_entity = MagicMock()

    mock.delete_kid_entity = MagicMock()
    mock.delete_parent_entity = MagicMock()
    mock.delete_chore_entity = MagicMock()
    mock.delete_badge_entity = MagicMock()
    mock.delete_reward_entity = MagicMock()
    mock.delete_bonus_entity = MagicMock()
    mock.delete_penalty_entity = MagicMock()
    mock.delete_achievement_entity = MagicMock()
    mock.delete_challenge_entity = MagicMock()

    return mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,  # pylint: disable=redefined-outer-name
    mock_storage_data: dict[str, Any],  # pylint: disable=redefined-outer-name
) -> MockConfigEntry:
    """Set up the KidsChores integration for testing with mocked storage."""
    mock_config_entry.add_to_hass(hass)

    # Mock the Store's async_load to return our test data
    with patch(
        "homeassistant.helpers.storage.Store.async_load",
        return_value=mock_storage_data,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


def create_mock_kid_data(
    name: str = "Test Kid", points: float = 100.0
) -> dict[str, Any]:
    """Create mock kid data for testing."""
    kid_id = str(uuid.uuid4())
    return {
        "internal_id": kid_id,
        "name": name,
        "points": points,
        "ha_user_id": "",
        "enable_notifications": True,
        "mobile_notify_service": "",
        "use_persistent_notifications": True,
        "dashboard_language": "en",
        "chore_states": {},
        "badges_earned": [],
        "claimed_chores": [],
        "approved_chores": [],
        "reward_claims": {},
        "bonus_applies": {},
        "penalty_applies": {},
        "overdue_notifications": {},
    }


def create_mock_chore_data(
    name: str = "Test Chore",
    default_points: int | float = 10,
    assigned_kids: list[str] | None = None,
) -> dict[str, Any]:
    """Create mock chore data for testing."""
    chore_id = str(uuid.uuid4())
    return {
        "internal_id": chore_id,
        "name": name,
        "default_points": default_points,
        "assigned_kids": assigned_kids or [],
        "partial_allowed": False,
        "shared_chore": False,
        "allow_multiple_claims_per_day": False,
        "description": "",
        "labels": [],
        "icon": "mdi:broom",
        "recurring_frequency": "",
        "custom_interval": None,
        "custom_interval_unit": None,
        "due_date": None,
        "applicable_days": [0, 1, 2, 3, 4, 5, 6],
        "notify_on_claim": True,
        "notify_on_approval": True,
        "notify_on_disapproval": True,
    }


def create_mock_reward_data(
    name: str = "Test Reward", cost: int = 50
) -> dict[str, Any]:
    """Create mock reward data for testing."""
    reward_id = str(uuid.uuid4())
    return {
        "internal_id": reward_id,
        "name": name,
        "cost": cost,
        "description": "",
        "labels": [],
        "icon": "mdi:gift",
    }


@pytest.fixture
async def init_integration_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,  # pylint: disable=redefined-outer-name
    mock_hass_users: dict,  # pylint: disable=redefined-outer-name
) -> MockConfigEntry:
    """Set up a fully configured KidsChores integration with sample data."""
    # Create sample kid data
    kid1_id = str(uuid.uuid4())
    kid2_id = str(uuid.uuid4())

    sample_kids = {
        kid1_id: create_mock_kid_data("Test Kid 1", 100.0),
        kid2_id: create_mock_kid_data("Test Kid 2", 50.0),
    }
    sample_kids[kid1_id]["internal_id"] = kid1_id
    sample_kids[kid2_id]["internal_id"] = kid2_id
    sample_kids[kid1_id]["ha_user_id"] = mock_hass_users["kid1"].id
    sample_kids[kid2_id]["ha_user_id"] = mock_hass_users["kid2"].id

    # Create sample chore data
    chore1_id = str(uuid.uuid4())
    sample_chores = {
        chore1_id: create_mock_chore_data(
            "Test Chore",
            10,
            [kid1_id, kid2_id],
        ),
    }
    sample_chores[chore1_id]["internal_id"] = chore1_id

    # Create sample reward data
    reward1_id = str(uuid.uuid4())
    sample_rewards = {
        reward1_id: create_mock_reward_data("Test Reward", 50),
    }
    sample_rewards[reward1_id]["internal_id"] = reward1_id

    # Mock storage data
    storage_data = {
        DATA_KIDS: sample_kids,
        DATA_PARENTS: {},
        DATA_CHORES: sample_chores,
        DATA_BADGES: {},
        DATA_REWARDS: sample_rewards,
        DATA_BONUSES: {},
        DATA_PENALTIES: {},
        DATA_ACHIEVEMENTS: {},
        DATA_CHALLENGES: {},
    }

    mock_config_entry.add_to_hass(hass)

    # Patch storage to return our sample data
    with patch(
        "custom_components.kidschores.storage_manager.KidsChoresStorageManager.async_load",
        return_value=storage_data,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
