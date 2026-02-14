# File: helpers/dashboard_helpers.py
"""Dashboard generation helper functions for KidsChores.

Provides context building and template rendering support for generating
Lovelace dashboards via the KidsChores Options Flow.

All functions here require a `hass` object or interact with HA APIs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.helpers import selector
from homeassistant.util import slugify
import voluptuous as vol

from .. import const

if TYPE_CHECKING:
    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import KidData


# ==============================================================================
# Dashboard Context TypedDicts
# ==============================================================================


class DashboardKidContext(TypedDict):
    """Minimal context for a kid in dashboard generation.

    The dashboard templates only need these two values - all other data
    (entity IDs, points, chores) is discovered at runtime via HA Jinja2
    using the `name` to find the dashboard_helper sensor.
    """

    name: str  # Exact display name (used in `{%- set name = '...' -%}`)
    slug: str  # URL-safe slug (used in `path:` only)


class DashboardContext(TypedDict):
    """Full context for dashboard template rendering.

    Passed to the Python Jinja2 environment with << >> delimiters.
    For kid dashboards, only `kid` is used.
    For admin dashboard, no context is needed (fully dynamic).
    """

    kid: DashboardKidContext


class DashboardKidTemplateProfiles(TypedDict, total=False):
    """Optional per-kid template profile map.

    Keys are kid display names, values are style/profile identifiers.
    """


# ==============================================================================
# Context Builder Functions
# ==============================================================================


def build_kid_context(kid_name: str) -> DashboardKidContext:
    """Build minimal context for a single kid dashboard.

    Args:
        kid_name: The kid's exact display name from storage.

    Returns:
        DashboardKidContext with name and URL-safe slug.

    Example:
        >>> build_kid_context("Alice")
        {"name": "Alice", "slug": "alice"}
        >>> build_kid_context("María José")
        {"name": "María José", "slug": "maria_jose"}
    """
    return DashboardKidContext(
        name=kid_name,
        slug=slugify(kid_name),
    )


def build_dashboard_context(
    kid_name: str,
    *,
    template_profile: str | None = None,
) -> DashboardContext:
    """Build full context for dashboard template rendering.

    This is the dict passed to the Jinja2 template engine with << >> delimiters.

    Args:
        kid_name: The kid's exact display name from storage.
        template_profile: Optional template profile for future granular flows.
            Phase 2 scaffolding keeps context shape unchanged.

    Returns:
        DashboardContext ready for template rendering.

    Example:
        >>> ctx = build_dashboard_context("Alice")
        >>> ctx["kid"]["name"]
        'Alice'
        >>> ctx["kid"]["slug"]
        'alice'
    """
    _ = template_profile

    return DashboardContext(
        kid=build_kid_context(kid_name),
    )


def resolve_kid_template_profile(
    kid_name: str,
    default_style: str,
    kid_template_profiles: dict[str, str] | None = None,
) -> str:
    """Resolve template profile for a kid with safe fallback.

    Args:
        kid_name: Kid display name.
        default_style: Default selected style.
        kid_template_profiles: Optional per-kid profile mapping.

    Returns:
        Resolved style/profile for this kid.
    """
    if not kid_template_profiles:
        return default_style

    resolved = kid_template_profiles.get(kid_name, default_style)
    if resolved in const.DASHBOARD_STYLES:
        return resolved

    return default_style


def get_all_kid_names(coordinator: KidsChoresDataCoordinator) -> list[str]:
    """Get list of all kid names from coordinator.

    Args:
        coordinator: KidsChoresDataCoordinator instance.

    Returns:
        List of kid display names, sorted alphabetically.
    """
    kids_data = coordinator.kids_data
    names: list[str] = []
    for kid_info in kids_data.values():
        kid_info_typed: KidData = kid_info
        name = kid_info_typed.get(const.DATA_KID_NAME, "")
        if name:
            names.append(name)
    return sorted(names)


def get_dashboard_url_path(kid_name: str, style: str) -> str:
    """Generate the URL path for a kid's dashboard.

    Args:
        kid_name: The kid's display name.
        style: Dashboard style (full, minimal, compact, admin).

    Returns:
        URL path like "kcd-alice" or "kcd-alice-compact".

    Examples:
        >>> get_dashboard_url_path("Alice", "full")
        'kcd-alice'
        >>> get_dashboard_url_path("Alice", "compact")
        'kcd-alice-compact'
        >>> get_dashboard_url_path("", "admin")
        'kcd-admin'
    """
    if style == const.DASHBOARD_STYLE_ADMIN:
        return f"{const.DASHBOARD_URL_PATH_PREFIX}admin"

    slug = slugify(kid_name)
    base_path = f"{const.DASHBOARD_URL_PATH_PREFIX}{slug}"

    # Full style uses base path, others get suffix
    if style == const.DASHBOARD_STYLE_FULL:
        return base_path
    return f"{base_path}-{style}"


def get_dashboard_title(kid_name: str, style: str) -> str:
    """Generate the display title for a kid's dashboard.

    Args:
        kid_name: The kid's display name.
        style: Dashboard style (full, minimal, compact, admin).

    Returns:
        Human-readable title like "Alice Chores" or "KidsChores Admin".
    """
    if style == const.DASHBOARD_STYLE_ADMIN:
        return "KidsChores Admin"

    base_title = f"{kid_name} Chores"
    if style == const.DASHBOARD_STYLE_COMPACT:
        return f"{base_title} (Compact)"
    if style == const.DASHBOARD_STYLE_MINIMAL:
        return f"{base_title} (Minimal)"
    return base_title


# ==============================================================================
# Options Flow Schema Builders
# ==============================================================================


def build_dashboard_style_options() -> list[selector.SelectOptionDict]:
    """Build style selection options for dashboard generator form.

    Admin is now a checkbox, not a style option.

    Returns:
        List of SelectOptionDict for style selector.
    """
    return [
        selector.SelectOptionDict(
            value=const.DASHBOARD_STYLE_FULL,
            label=const.DASHBOARD_STYLE_FULL,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_STYLE_MINIMAL,
            label=const.DASHBOARD_STYLE_MINIMAL,
        ),
        # selector.SelectOptionDict(
        #    value=const.DASHBOARD_STYLE_COMPACT,
        #    label=const.TRANS_KEY_CFOF_DASHBOARD_STYLE_COMPACT,
        # ),
    ]


def build_dashboard_generation_mode_options() -> list[selector.SelectOptionDict]:
    """Build generation mode selection options for granular dashboard flow."""
    return [
        selector.SelectOptionDict(
            value=const.DASHBOARD_GENERATION_MODE_SINGLE_MULTI_VIEW,
            label=const.DASHBOARD_GENERATION_MODE_SINGLE_MULTI_VIEW,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_GENERATION_MODE_PER_KID_DASHBOARD,
            label=const.DASHBOARD_GENERATION_MODE_PER_KID_DASHBOARD,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_GENERATION_MODE_TARGETED_VIEW_UPDATE,
            label=const.DASHBOARD_GENERATION_MODE_TARGETED_VIEW_UPDATE,
        ),
    ]


def build_dashboard_target_scope_options() -> list[selector.SelectOptionDict]:
    """Build target scope options for granular dashboard updates."""
    return [
        selector.SelectOptionDict(
            value=const.DASHBOARD_TARGET_SCOPE_ALL_SELECTED_KIDS,
            label=const.DASHBOARD_TARGET_SCOPE_ALL_SELECTED_KIDS,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_TARGET_SCOPE_SINGLE_KID,
            label=const.DASHBOARD_TARGET_SCOPE_SINGLE_KID,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_TARGET_SCOPE_ADMIN_ONLY,
            label=const.DASHBOARD_TARGET_SCOPE_ADMIN_ONLY,
        ),
    ]


def build_dashboard_template_profile_options() -> list[selector.SelectOptionDict]:
    """Build template profile options.

    Admin profile is excluded because it is managed by include-admin toggle.
    """
    return [
        selector.SelectOptionDict(
            value=const.DASHBOARD_STYLE_FULL,
            label=const.DASHBOARD_STYLE_FULL,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_STYLE_MINIMAL,
            label=const.DASHBOARD_STYLE_MINIMAL,
        ),
    ]


def build_dashboard_kid_options(
    coordinator: KidsChoresDataCoordinator,
) -> list[selector.SelectOptionDict]:
    """Build kid selection options for dashboard generator form.

    Args:
        coordinator: KidsChoresDataCoordinator instance.

    Returns:
        List of SelectOptionDict for kid multi-selector.
    """
    kid_names = get_all_kid_names(coordinator)
    return [selector.SelectOptionDict(value=name, label=name) for name in kid_names]


def build_dashboard_generator_schema(
    coordinator: KidsChoresDataCoordinator,
    *,
    include_granular_controls: bool = False,
) -> vol.Schema:
    """Build the schema for dashboard generator options flow step.

    Creates a multi-view dashboard with one tab per kid plus optional admin tab.

    Args:
        coordinator: KidsChoresDataCoordinator instance.

    Returns:
        Voluptuous schema for the form.
    """
    style_options = build_dashboard_style_options()
    kid_options = build_dashboard_kid_options(coordinator)
    kid_names = get_all_kid_names(coordinator)

    schema_fields: dict[vol.Marker, Any] = {
        # Dashboard name (user-specified, suggest "Chores")
        vol.Required(
            const.CFOF_DASHBOARD_INPUT_NAME,
            default=const.DASHBOARD_DEFAULT_NAME,
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
    }

    if include_granular_controls:
        schema_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_GENERATION_MODE,
                default=const.DASHBOARD_GENERATION_MODE_SINGLE_MULTI_VIEW,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_generation_mode_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_GENERATION_MODE,
            )
        )
        schema_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_TARGET_SCOPE,
                default=const.DASHBOARD_TARGET_SCOPE_ALL_SELECTED_KIDS,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_target_scope_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_TARGET_SCOPE,
            )
        )
        schema_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE,
                default=const.DASHBOARD_STYLE_FULL,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_template_profile_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_TEMPLATE_PROFILE,
            )
        )
        if kid_options:
            schema_fields[vol.Optional(const.CFOF_DASHBOARD_INPUT_SINGLE_KID)] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=kid_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=const.TRANS_KEY_CFOF_DASHBOARD_SINGLE_KID,
                    )
                )
            )

    # Style selection
    schema_fields[
        vol.Required(
            const.CFOF_DASHBOARD_INPUT_STYLE,
            default=const.DASHBOARD_STYLE_FULL,
        )
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=style_options,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key=const.TRANS_KEY_CFOF_DASHBOARD_STYLE,
        )
    )

    # Kid selection (multi-select, pre-select all)
    if kid_options:
        schema_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_KID_SELECTION,
                default=kid_names,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=kid_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_KID_SELECTION,
            )
        )

    # Include admin view checkbox
    schema_fields[
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_INCLUDE_ADMIN,
            default=True,
        )
    ] = selector.BooleanSelector()

    return vol.Schema(schema_fields)


def format_dashboard_confirm_summary(
    dashboard_name: str,
    style: str,
    selected_kids: list[str],
    include_admin: bool,
) -> str:
    """Build the summary text for dashboard generation confirmation.

    Args:
        dashboard_name: User-specified dashboard name.
        style: Selected dashboard style.
        selected_kids: List of selected kid names.
        include_admin: Whether admin view is included.

    Returns:
        Formatted summary string for display.
    """
    from .dashboard_builder import get_multi_view_url_path

    url_path = get_multi_view_url_path(dashboard_name)

    lines = [
        f"Dashboard: {dashboard_name} ({url_path})",
        f"Style: {style}",
        "",
        "Views (tabs):",
    ]

    for kid in selected_kids:
        lines.append(f"  • {kid}")

    if include_admin:
        lines.append("  • Admin")

    return "\n".join(lines)


class DashboardGenerationResult(TypedDict):
    """Result of a single dashboard generation attempt."""

    name: str
    success: bool
    url_path: str | None
    error: str | None


def format_dashboard_results(results: list[dict[str, Any]]) -> str:
    """Format dashboard generation results for display.

    Args:
        results: List of generation results (DashboardGenerationResult dicts).

    Returns:
        Formatted result string.
    """
    success_items = [
        f"✓ {r['name']} → {r.get('url_path', 'N/A')}"
        for r in results
        if r.get("success")
    ]
    failure_items = [
        f"✗ {r['name']}: {r.get('error', 'Unknown error')}"
        for r in results
        if not r.get("success")
    ]

    result_text = ""
    if success_items:
        result_text += "\n".join(success_items)
    if failure_items:
        if result_text:
            result_text += "\n\n"
        result_text += "\n".join(failure_items)

    return result_text


# ==============================================================================
# Dashboard Discovery Functions
# ==============================================================================


def get_existing_kidschores_dashboards(
    hass: Any,
) -> list[dict[str, str]]:
    """Get list of existing KidsChores dashboards.

    Scans the lovelace dashboards collection for dashboards
    with url_path starting with 'kcd-' (our namespace).

    Args:
        hass: Home Assistant instance.

    Returns:
        List of dicts with 'value' (url_path) and 'label' (title).
    """
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    dashboards: list[dict[str, str]] = []

    if LOVELACE_DATA not in hass.data:
        return dashboards

    lovelace_data = hass.data[LOVELACE_DATA]

    # Check dashboards dict for kcd-* entries
    for url_path in lovelace_data.dashboards:
        # Skip None or non-string keys
        if not url_path or not isinstance(url_path, str):
            continue
        if url_path.startswith("kcd-"):
            # Try to get the title from the panel
            title = url_path  # Fallback
            if hasattr(lovelace_data.dashboards[url_path], "config"):
                config = lovelace_data.dashboards[url_path].config
                if config and isinstance(config, dict):
                    # Get title from views if available
                    views = config.get("views", [])
                    if views and isinstance(views, list) and len(views) > 0:
                        title = views[0].get("title", url_path)

            dashboards.append(
                {
                    "value": url_path,
                    "label": f"{title} ({url_path})",
                }
            )

    return dashboards


def build_dashboard_action_schema(
    check_cards_default: bool = True,
) -> vol.Schema:
    """Build schema for dashboard action selection (create/delete).

    Args:
        check_cards_default: Default value for the check cards checkbox.

    Returns:
        Voluptuous schema for action selection.
    """
    action_options = [
        selector.SelectOptionDict(
            value=const.DASHBOARD_ACTION_CREATE,
            label=const.DASHBOARD_ACTION_CREATE,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ACTION_UPDATE,
            label=const.DASHBOARD_ACTION_UPDATE,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ACTION_DELETE,
            label=const.DASHBOARD_ACTION_DELETE,
        ),
    ]

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_DASHBOARD_INPUT_ACTION,
                default=const.DASHBOARD_ACTION_CREATE,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=action_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ACTION,
                )
            ),
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS,
                default=check_cards_default,
            ): selector.BooleanSelector(),
        }
    )


def build_dashboard_update_selection_schema(
    hass: Any,
) -> vol.Schema | None:
    """Build schema for selecting one existing dashboard to update."""
    dashboards = get_existing_kidschores_dashboards(hass)

    if not dashboards:
        return None

    dashboard_options = [
        selector.SelectOptionDict(value=d["value"], label=d["label"])
        for d in dashboards
    ]

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=dashboard_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=False,
                    translation_key=const.TRANS_KEY_CFOF_DASHBOARD_UPDATE_SELECTION,
                )
            ),
        }
    )


def build_dashboard_update_schema(
    coordinator: KidsChoresDataCoordinator,
) -> vol.Schema:
    """Build minimal schema for updating views on an existing dashboard."""
    kid_options = build_dashboard_kid_options(coordinator)
    kid_names = get_all_kid_names(coordinator)

    schema_fields: dict[vol.Marker, Any] = {
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE,
            default=const.DASHBOARD_STYLE_FULL,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_template_profile_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_TEMPLATE_PROFILE,
            )
        ),
    }

    if kid_options:
        schema_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_KID_SELECTION,
                default=kid_names,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=kid_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_KID_SELECTION,
            )
        )

    schema_fields[
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_INCLUDE_ADMIN,
            default=True,
        )
    ] = selector.BooleanSelector()

    return vol.Schema(schema_fields)


def build_dashboard_delete_schema(
    hass: Any,
) -> vol.Schema | None:
    """Build schema for dashboard deletion selection.

    Args:
        hass: Home Assistant instance.

    Returns:
        Voluptuous schema for deletion, or None if no dashboards exist.
    """
    dashboards = get_existing_kidschores_dashboards(hass)

    if not dashboards:
        return None

    dashboard_options = [
        selector.SelectOptionDict(value=d["value"], label=d["label"])
        for d in dashboards
    ]

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_DASHBOARD_INPUT_DELETE_SELECTION,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=dashboard_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                    translation_key=const.TRANS_KEY_CFOF_DASHBOARD_DELETE_SELECTION,
                )
            ),
        }
    )


async def check_custom_cards_installed(hass: Any) -> dict[str, bool]:
    """Check if required custom Lovelace cards are installed.

    Args:
        hass: Home Assistant instance.

    Returns:
        Dict mapping card type to installation status.
        Example: {"mushroom": True, "auto_entities": False, "mini_graph": True}
    """
    # Card URL patterns to detect
    card_patterns = {
        "mushroom": "mushroom",
        "auto_entities": "auto-entities",
        "mini_graph": "mini-graph-card",
    }

    # Initialize all as not installed
    installed = dict.fromkeys(card_patterns, False)

    # Try to check lovelace resources
    try:
        # Try to get lovelace resources collection from data
        lovelace_resources = hass.data.get("lovelace_resources")

        if lovelace_resources is None:
            lovelace_resources = hass.data.get("lovelace")

        if lovelace_resources is None:
            const.LOGGER.debug("No lovelace data found in hass.data")
            return installed

        # Get all resources
        resources = []
        if hasattr(lovelace_resources, "resources"):
            # Try direct resources attribute (LovelaceData.resources)
            resources_obj = lovelace_resources.resources
            if hasattr(resources_obj, "async_items"):
                # ResourceStorageCollection.async_items() returns list directly (not coroutine)
                resources = resources_obj.async_items()
            elif hasattr(resources_obj, "items"):
                resources = list(resources_obj.items())
        elif hasattr(lovelace_resources, "async_items"):
            resources = lovelace_resources.async_items()
        elif hasattr(lovelace_resources, "items"):
            resources = lovelace_resources.items()

        const.LOGGER.debug(
            "Checking %d lovelace resources for custom cards", len(resources)
        )

        for resource in resources:
            resource_url = ""
            if isinstance(resource, dict):
                resource_url = str(resource.get("url", "")).lower()
            elif hasattr(resource, "url"):
                resource_url = str(resource.url).lower()

            for card_type, pattern in card_patterns.items():
                if pattern in resource_url:
                    installed[card_type] = True

    except (AttributeError, KeyError, TypeError) as ex:
        const.LOGGER.warning("Unable to check custom card installation: %s", ex)

    const.LOGGER.debug("Custom card status: %s", installed)
    return installed
