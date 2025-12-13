"""Tests for KidsChores options flow."""

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kidschores.const import (
    CFOF_KIDS_INPUT_KID_NAME,
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_ACTIONS_BACK,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_KIDS,
    OPTIONS_FLOW_STEP_ADD_KID,
    OPTIONS_FLOW_STEP_INIT,
    OPTIONS_FLOW_STEP_MANAGE_ENTITY,
)


async def test_options_flow_init(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test options flow initialization shows main menu."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT


async def test_options_flow_add_kid_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test adding a kid via options flow."""
    # Navigate to kids management
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_KIDS},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY

    # Select "Add" action
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_ADD_KID

    # Add the kid
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={CFOF_KIDS_INPUT_KID_NAME: "Test Kid"},
    )

    # Should return to main menu after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT


async def test_options_flow_add_kid_duplicate_name(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test adding a kid with duplicate name shows error."""
    # First, add a kid
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_KIDS},
    )
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={CFOF_KIDS_INPUT_KID_NAME: "Existing Kid"},
    )

    # Navigate to add kid form
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_KIDS},
    )
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )

    # Try to add kid with duplicate name
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={CFOF_KIDS_INPUT_KID_NAME: "Existing Kid"},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_ADD_KID
    errors = result.get("errors")
    assert errors is not None
    assert "kid_name" in errors


async def test_options_flow_back_to_main_menu(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test navigating back to main menu."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_KIDS},
    )

    # Go back to main menu
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_BACK},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT
