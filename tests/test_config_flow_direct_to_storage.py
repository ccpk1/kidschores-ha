"""Test config flow direct-to-storage functionality.

Validates that fresh installations (KC 4.0) write entities directly to
.storage/kidschores_data with schema_version 42, bypassing migration.

Uses testdata_storyline.yaml character names (Zoë, Môm Astrid, "Feed the cåts").
"""

# pylint: disable=protected-access  # Accessing internal methods for testing

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.kidschores.const import (
    CONF_POINTS_ICON,
    CONF_POINTS_LABEL,
    COORDINATOR,
    DATA_CHORES,
    DATA_KIDS,
    DATA_PARENTS,
    DATA_SCHEMA_VERSION,
    DOMAIN,
    SCHEMA_VERSION_STORAGE_ONLY,
)


@pytest.mark.asyncio
async def test_direct_storage_creates_one_parent_one_kid_one_chore(
    hass: HomeAssistant, scenario_minimal
) -> None:
    """Test that direct-to-storage creates exactly 1 parent, 1 kid, 1 chore.

    Uses scenario_minimal fixture which loads testdata_scenario_minimal.yaml:
    - 1 parent: Môm Astrid Stârblüm
    - 1 kid: Zoë
    - 2 chores: Feed the cåts, Wåter the plänts

    Validates entities are in storage (not config entry) and schema_version is 41.
    """
    config_entry, name_to_id_map = scenario_minimal

    # Scenario fixture loads from YAML which may have minimal config data
    # In KC 4.0+, config_entry.data should be empty or only have schema_version
    # Entity data (kids, parents, chores) should NOT be in config entry
    assert "kids" not in config_entry.data
    assert "parents" not in config_entry.data
    assert "chores" not in config_entry.data

    # Check options also has no entity data
    assert "kids" not in config_entry.options
    assert "parents" not in config_entry.options
    assert "chores" not in config_entry.options

    # Verify coordinator loaded the data from storage
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Check schema version is 42 (storage-only mode)
    assert coordinator.data[DATA_SCHEMA_VERSION] == SCHEMA_VERSION_STORAGE_ONLY
    assert SCHEMA_VERSION_STORAGE_ONLY == 42

    # Verify exactly 1 parent from storyline
    parents = coordinator.data[DATA_PARENTS]
    assert len(parents) == 1
    parent_id = name_to_id_map["parent:Môm Astrid Stârblüm"]
    assert parent_id in parents
    assert parents[parent_id]["name"] == "Môm Astrid Stârblüm"

    # Verify exactly 1 kid from storyline
    kids = coordinator.data[DATA_KIDS]
    assert len(kids) == 1
    kid_id = name_to_id_map["kid:Zoë"]
    assert kid_id in kids
    assert kids[kid_id]["name"] == "Zoë"

    # Verify chores exist from storyline (scenario_minimal has 2)
    chores = coordinator.data[DATA_CHORES]
    assert len(chores) == 2
    chore_id = name_to_id_map["chore:Feed the cåts"]
    assert chore_id in chores
    assert chores[chore_id]["name"] == "Feed the cåts"


@pytest.mark.asyncio
# pylint: disable=too-many-statements  # Test setup requires many steps
async def test_fresh_config_flow_creates_storage_only_entry(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test complete config flow creates storage-only entry with 1 parent, 1 kid, 1 chore.

    Simulates user going through entire config flow UI:
    - Step 1: Intro (welcome screen)
    - Step 2: Points label configuration
    - Step 3: Kid count selection (1 kid)
    - Step 4: Kid details (Zoë from storyline)
    - Step 5: Parent details (Môm Astrid from storyline)
    - Step 6: Chore details (Feed the cåts from storyline)

    Validates that resulting config entry has:
    - Empty data dict (no entity data)
    - Empty options dict (no entity data)
    - All entities stored in coordinator.data with schema_version 41
    """
    # Step 1: Start config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "intro"

    # Step 2: Submit intro (empty user_input progresses to points_label)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "points_label"

    # Step 3: Configure points label
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_POINTS_LABEL: "Stars",
            CONF_POINTS_ICON: "mdi:star",
        },
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "kid_count"

    # Step 4: Specify 1 kid
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"kid_count": 1}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "kids"

    # Step 5: Add kid details (Zoë from storyline)
    kid1_user = mock_hass_users["kid1"]  # Use kid1 mock user
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "kid_name": "Zoë",
            "ha_user": kid1_user.id,
            "enable_mobile_notifications": True,
            "mobile_notify_service": "",
            "enable_persistent_notifications": True,
        },
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "parent_count"

    # Step 6: Specify 1 parent
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"parent_count": 1}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "parents"

    # Step 7: Add parent details (Môm Astrid from storyline)
    parent_user = mock_hass_users["parent1"]  # Use parent1 mock user
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "parent_name": "Môm Astrid Stârblüm",
            "ha_user_id": parent_user.id,
            "associated_kids": [],
            "enable_mobile_notifications": False,
            "mobile_notify_service": "",
            "enable_persistent_notifications": False,
        },
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "chore_count"

    # Step 8: Specify 1 chore
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"chore_count": 1}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "chores"

    # Step 9: Add chore details (Feed the cåts from storyline)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "chore_name": "Feed the cåts",
            "default_points": 10,
            "icon": "mdi:cat",
            "assigned_kids": ["Zoë"],
            "recurring_frequency": "daily",
        },
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "badge_count"

    # Step 10: Skip badges (set count to 0)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"badge_count": 0}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reward_count"

    # Step 11: Skip rewards (set count to 0)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"reward_count": 0}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "penalty_count"

    # Step 12: Skip penalties (set count to 0)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"penalty_count": 0}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "bonus_count"

    # Step 13: Skip bonuses (set count to 0)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"bonus_count": 0}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "achievement_count"

    # Step 14: Skip achievements (set count to 0)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"achievement_count": 0}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "challenge_count"

    # Step 15: Skip challenges (set count to 0)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"challenge_count": 0}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "finish"

    # Step 16: Finish configuration
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "KidsChores"

    config_entry = result.get("result")
    assert config_entry is not None, "Config entry creation failed"

    # Validate config entry structure (KC 4.0 storage-only mode)
    # Config entry data should be empty or only contain non-entity system settings
    assert "kids" not in config_entry.data
    assert "parents" not in config_entry.data
    assert "chores" not in config_entry.data

    # Options should also not contain entity data
    assert "kids" not in config_entry.options
    assert "parents" not in config_entry.options
    assert "chores" not in config_entry.options

    # Verify coordinator loaded data from storage
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Check schema version is 42 (storage-only)
    assert coordinator.data[DATA_SCHEMA_VERSION] == SCHEMA_VERSION_STORAGE_ONLY
    assert SCHEMA_VERSION_STORAGE_ONLY == 42

    # Verify exactly 1 parent created
    parents = coordinator.data[DATA_PARENTS]
    assert len(parents) == 1, f"Expected 1 parent, found {len(parents)}"
    parent_id = list(parents.keys())[0]
    assert len(parent_id) > 10, "Parent ID should be UUID"
    assert parents[parent_id]["name"] == "Môm Astrid Stârblüm"

    # Verify exactly 1 kid created
    kids = coordinator.data[DATA_KIDS]
    assert len(kids) == 1, f"Expected 1 kid, found {len(kids)}"
    kid_id = list(kids.keys())[0]
    assert len(kid_id) > 10, "Kid ID should be UUID"
    kid_data = kids[kid_id]
    assert kid_data["name"] == "Zoë"

    # Verify kid is linked to correct HA user (kid1)
    assert kid_data.get("ha_user_id") == mock_hass_users["kid1"].id

    # Note: Point data structures get initialized on first use.
    # For a fresh install, kid starts with 0 points (stored in nested point_data structure).
    # The DATA_KID_POINTS key might not exist until first point transaction.
    assert kid_data.get("internal_id") == kid_id

    # Verify exactly 1 chore created
    chores = coordinator.data[DATA_CHORES]
    assert len(chores) == 1, f"Expected 1 chore, found {len(chores)}"
    chore_id = list(chores.keys())[0]
    assert len(chore_id) > 10, "Chore ID should be UUID"
    assert chores[chore_id]["name"] == "Feed the cåts"
    assert chores[chore_id]["default_points"] == 10
    assert chores[chore_id]["icon"] == "mdi:cat"

    # Verify chore is assigned to the kid (config flow stores names initially)
    assigned_kids = chores[chore_id]["assigned_kids"]
    assert kid_data["name"] in assigned_kids or kid_id in assigned_kids

    # Validate that entities are keyed by internal_id (not name)
    assert all(isinstance(kid_id, str) and len(kid_id) > 10 for kid_id in kids.keys())
    assert all(
        isinstance(parent_id, str) and len(parent_id) > 10
        for parent_id in parents.keys()
    )
    assert all(
        isinstance(chore_id, str) and len(chore_id) > 10 for chore_id in chores.keys()
    )
