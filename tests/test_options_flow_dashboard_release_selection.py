"""Options flow tests for dashboard release selection UX."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.data_entry_flow import FlowResultType
import pytest
import voluptuous as vol

from custom_components.kidschores import const
from custom_components.kidschores.helpers import dashboard_helpers as dh
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for options flow tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


def _schema_field_names(schema: vol.Schema) -> set[str]:
    """Return field names from a voluptuous schema, including section fields."""
    names: set[str] = set()

    def _collect_fields(schema_obj: Any) -> None:
        if isinstance(schema_obj, vol.Schema):
            _collect_fields(schema_obj.schema)
            return

        if isinstance(schema_obj, dict):
            for marker, value in schema_obj.items():
                marker_schema = getattr(marker, "schema", marker)
                if isinstance(marker_schema, str):
                    names.add(marker_schema)
                _collect_fields(value)
            return

        nested_schema = getattr(schema_obj, "schema", None)
        if nested_schema is not None and nested_schema is not schema_obj:
            _collect_fields(nested_schema)

    _collect_fields(schema)
    return names


def test_dashboard_template_labels_are_human_friendly() -> None:
    """Template selector labels use metadata/humanized values instead of raw keys."""
    kid_options = {
        str(option["value"]): str(option["label"])
        for option in dh.build_dashboard_template_profile_options()
    }
    admin_options = {
        str(option["value"]): str(option["label"])
        for option in dh.build_dashboard_admin_template_options()
    }

    assert kid_options[const.DASHBOARD_STYLE_FULL] == "Full"
    assert kid_options[const.DASHBOARD_STYLE_MINIMAL] == "Minimal"
    assert admin_options[const.DASHBOARD_STYLE_ADMIN] == "Admin"


@pytest.mark.asyncio
async def test_dashboard_update_step_shows_release_controls(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update path Step 2 includes release controls while create path does not."""
    config_entry = scenario_minimal.config_entry

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.kidschores.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

    fields = _schema_field_names(result["data_schema"])
    assert const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION in fields
    assert const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES in fields
    assert const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY in fields


@pytest.mark.asyncio
async def test_dashboard_create_parent_visibility_passes_linked_parent_users(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create path passes linked parent HA users when admin visibility uses parent scope."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.create_kidschores_dashboard",
            mock_create_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_CREATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_create"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_NAME: "Chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: const.DASHBOARD_STYLE_ADMIN,
                const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_KID: const.DASHBOARD_STYLE_ADMIN,
                const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS,
                const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert mock_create_dashboard.await_count == 1
    kwargs = mock_create_dashboard.await_args.kwargs
    assert kwargs["admin_view_visibility"] == (
        const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS
    )
    admin_visible_user_ids = kwargs.get("admin_visible_user_ids")
    assert isinstance(admin_visible_user_ids, list)
    assert len(admin_visible_user_ids) > 0


@pytest.mark.asyncio
async def test_dashboard_update_accepts_sectioned_configure_payload(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update configure accepts sectioned payload and forwards normalized values."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.kidschores.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: const.DASHBOARD_STYLE_ADMIN,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert mock_update_dashboard.await_count == 1
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["kid_names"] == ["Zoë"]
    assert kwargs["admin_view_visibility"] == const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL


@pytest.mark.asyncio
async def test_dashboard_update_reveals_per_kid_admin_template_on_mode_change(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update schema conditionally reveals admin template fields by selected admin mode."""
    config_entry = scenario_minimal.config_entry

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.kidschores.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        initial_fields = _schema_field_names(result["data_schema"])
        assert const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL in initial_fields
        assert const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_KID not in initial_fields

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_PER_KID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
                },
            },
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    revealed_fields = _schema_field_names(result["data_schema"])
    assert const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL not in revealed_fields
    assert const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_KID in revealed_fields


@pytest.mark.asyncio
async def test_dashboard_update_non_default_release_selection_passes_pinned_tag(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Explicit release selection forwards pinned release tag to update builder."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.kidschores.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.kidschores.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: const.DASHBOARD_STYLE_ADMIN,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "KCD_v0.5.3",
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["pinned_release_tag"] == "KCD_v0.5.3"


@pytest.mark.asyncio
async def test_dashboard_configure_validation_no_kids_and_no_admin(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Step 2 blocks submit when no kids and admin mode none."""
    config_entry = scenario_minimal.config_entry

    with patch(
        "custom_components.kidschores.helpers.dashboard_builder.create_kidschores_dashboard",
        return_value="kcd-chores",
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_CREATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_NAME: "Chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                const.CFOF_DASHBOARD_INPUT_KID_SELECTION: [],
                const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
            },
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    assert result.get("errors") == {
        const.CFOP_ERROR_BASE: const.TRANS_KEY_CFOF_DASHBOARD_NO_KIDS_WITHOUT_ADMIN
    }
