# File: services.py
"""Defines custom services for the KidsChores integration.

These services allow direct actions through scripts or automations.
Includes UI editor support with selectors for dropdowns and text inputs.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.util import dt as dt_util
import voluptuous as vol

from . import backup_helpers as bh, const, kc_helpers as kh

if TYPE_CHECKING:
    from .coordinator import KidsChoresDataCoordinator
    from .type_defs import ChoreData


def _get_coordinator_by_entry_id(
    hass: HomeAssistant, entry_id: str
) -> "KidsChoresDataCoordinator":
    """Get coordinator from config entry ID using runtime_data.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID string

    Returns:
        KidsChoresDataCoordinator instance

    Raises:
        HomeAssistantError: If entry not found or not loaded
    """
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
        )
    return cast("KidsChoresDataCoordinator", entry.runtime_data)


# --- Service Schemas ---

# Common schema base patterns for DRY principle
_KID_CHORE_BASE = {
    vol.Required(const.FIELD_KID_NAME): cv.string,
    vol.Required(const.FIELD_CHORE_NAME): cv.string,
}

_PARENT_KID_CHORE_BASE = {
    vol.Required(const.FIELD_PARENT_NAME): cv.string,
    vol.Required(const.FIELD_KID_NAME): cv.string,
    vol.Required(const.FIELD_CHORE_NAME): cv.string,
}

_PARENT_KID_REWARD_BASE = {
    vol.Required(const.FIELD_PARENT_NAME): cv.string,
    vol.Required(const.FIELD_KID_NAME): cv.string,
    vol.Required(const.FIELD_REWARD_NAME): cv.string,
}

_PARENT_KID_PENALTY_BASE = {
    vol.Required(const.FIELD_PARENT_NAME): cv.string,
    vol.Required(const.FIELD_KID_NAME): cv.string,
    vol.Required(const.FIELD_PENALTY_NAME): cv.string,
}

_PARENT_KID_BONUS_BASE = {
    vol.Required(const.FIELD_PARENT_NAME): cv.string,
    vol.Required(const.FIELD_KID_NAME): cv.string,
    vol.Required(const.FIELD_BONUS_NAME): cv.string,
}

# Service schemas using base patterns
CLAIM_CHORE_SCHEMA = vol.Schema(_KID_CHORE_BASE)

APPROVE_CHORE_SCHEMA = vol.Schema(
    {
        **_PARENT_KID_CHORE_BASE,  # type: ignore[misc]
        vol.Optional(const.FIELD_POINTS_AWARDED): vol.Coerce(float),
    }
)

DISAPPROVE_CHORE_SCHEMA = vol.Schema(_PARENT_KID_CHORE_BASE)

REDEEM_REWARD_SCHEMA = vol.Schema(_PARENT_KID_REWARD_BASE)

APPROVE_REWARD_SCHEMA = vol.Schema(
    {
        **_PARENT_KID_REWARD_BASE,  # type: ignore[misc]
        vol.Optional(const.FIELD_COST_OVERRIDE): vol.Coerce(float),
    }
)

DISAPPROVE_REWARD_SCHEMA = vol.Schema(_PARENT_KID_REWARD_BASE)

APPLY_PENALTY_SCHEMA = vol.Schema(_PARENT_KID_PENALTY_BASE)

APPLY_BONUS_SCHEMA = vol.Schema(_PARENT_KID_BONUS_BASE)

# Optional filter base patterns for reset operations
_OPTIONAL_KID_FILTER = {vol.Optional(const.FIELD_KID_NAME): cv.string}

_OPTIONAL_KID_PENALTY_FILTER = {
    vol.Optional(const.FIELD_KID_NAME): cv.string,
    vol.Optional(const.FIELD_PENALTY_NAME): cv.string,
}

_OPTIONAL_KID_BONUS_FILTER = {
    vol.Optional(const.FIELD_KID_NAME): cv.string,
    vol.Optional(const.FIELD_BONUS_NAME): cv.string,
}

_OPTIONAL_KID_REWARD_FILTER = {
    vol.Optional(const.FIELD_KID_NAME): cv.string,
    vol.Optional(const.FIELD_REWARD_NAME): cv.string,
}

RESET_OVERDUE_CHORES_SCHEMA = vol.Schema(
    {
        vol.Optional(const.FIELD_CHORE_ID): cv.string,
        vol.Optional(const.FIELD_CHORE_NAME): cv.string,
        vol.Optional(const.FIELD_KID_NAME): cv.string,
    }
)

RESET_PENALTIES_SCHEMA = vol.Schema(_OPTIONAL_KID_PENALTY_FILTER)

RESET_BONUSES_SCHEMA = vol.Schema(_OPTIONAL_KID_BONUS_FILTER)

RESET_REWARDS_SCHEMA = vol.Schema(_OPTIONAL_KID_REWARD_FILTER)

REMOVE_AWARDED_BADGES_SCHEMA = vol.Schema(
    {
        vol.Optional(const.FIELD_KID_NAME): vol.Any(cv.string, None),
        vol.Optional(const.FIELD_BADGE_NAME): vol.Any(cv.string, None),
    }
)

RESET_ALL_DATA_SCHEMA = vol.Schema({})

RESET_ALL_CHORES_SCHEMA = vol.Schema({})

SET_CHORE_DUE_DATE_SCHEMA = vol.Schema(
    {
        vol.Required(const.FIELD_CHORE_NAME): cv.string,
        vol.Optional(const.FIELD_DUE_DATE): vol.Any(cv.string, None),
        vol.Optional(const.FIELD_KID_NAME): cv.string,
        vol.Optional(const.FIELD_KID_ID): cv.string,
    }
)

SKIP_CHORE_DUE_DATE_SCHEMA = vol.Schema(
    {
        vol.Optional(const.FIELD_CHORE_ID): cv.string,
        vol.Optional(const.FIELD_CHORE_NAME): cv.string,
        vol.Optional(const.FIELD_KID_NAME): cv.string,
        vol.Optional(const.FIELD_KID_ID): cv.string,
    }
)

MANAGE_SHADOW_LINK_SCHEMA = vol.Schema(
    {
        vol.Required(const.FIELD_NAME): cv.string,
        vol.Required(const.FIELD_ACTION): vol.In(
            [const.ACTION_LINK, const.ACTION_UNLINK]
        ),
    }
)

# ==============================================================================
# REWARD CRUD SCHEMAS (using data_builders pattern)
# ==============================================================================

# NOTE: cost is REQUIRED for create_reward - no invisible defaults for automations
CREATE_REWARD_SCHEMA = vol.Schema(
    {
        vol.Required(const.SERVICE_FIELD_REWARD_NAME): cv.string,
        vol.Required(const.SERVICE_FIELD_REWARD_COST): vol.Coerce(float),
        vol.Optional(const.SERVICE_FIELD_REWARD_DESCRIPTION, default=""): cv.string,
        vol.Optional(
            const.SERVICE_FIELD_REWARD_ICON, default=const.SENTINEL_EMPTY
        ): vol.Any(None, "", cv.icon),
        vol.Optional(const.SERVICE_FIELD_REWARD_LABELS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

# NOTE: Either reward_id OR reward_name must be provided (resolved in handler)
# reward_name is user-friendly; reward_id is for advanced automation use
UPDATE_REWARD_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_REWARD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_COST): vol.Coerce(float),
        vol.Optional(const.SERVICE_FIELD_REWARD_DESCRIPTION): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_ICON): cv.icon,
        vol.Optional(const.SERVICE_FIELD_REWARD_LABELS): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

# NOTE: Either reward_id OR reward_name must be provided (resolved in handler)
DELETE_REWARD_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_REWARD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_NAME): cv.string,
    }
)

# ============================================================================
# CHORE CRUD SCHEMAS
# ============================================================================
# NOTE: Chore services use DATA_* keys directly (unlike rewards which use CFOF_* keys)
# because build_chore() in data_builders expects pre-processed DATA_* keys.
#
# Field validation:
# - name: required for create, optional for update
# - assigned_kids: required for create (list of kid names resolved to UUIDs)
# - completion_criteria: CREATE ONLY (immutable after creation)
# - Other fields use defaults from const.DEFAULT_*

# Enum validators for select fields
_CHORE_FREQUENCY_VALUES = [
    const.FREQUENCY_NONE,
    const.FREQUENCY_DAILY,
    const.FREQUENCY_WEEKLY,
    const.FREQUENCY_BIWEEKLY,
    const.FREQUENCY_MONTHLY,
    const.FREQUENCY_QUARTERLY,
    const.FREQUENCY_YEARLY,
    const.FREQUENCY_CUSTOM,
    const.FREQUENCY_CUSTOM_FROM_COMPLETE,
    # Period-end frequencies
    const.PERIOD_WEEK_END,
    const.PERIOD_MONTH_END,
    const.PERIOD_QUARTER_END,
    const.PERIOD_YEAR_END,
]

_COMPLETION_CRITERIA_VALUES = [
    const.COMPLETION_CRITERIA_INDEPENDENT,
    const.COMPLETION_CRITERIA_SHARED_FIRST,
    const.COMPLETION_CRITERIA_SHARED,
]

_APPROVAL_RESET_VALUES = [
    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
    const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
    const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
    const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
    const.APPROVAL_RESET_UPON_COMPLETION,
]

_PENDING_CLAIMS_VALUES = [
    const.APPROVAL_RESET_PENDING_CLAIM_HOLD,
    const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
    const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
]

_OVERDUE_HANDLING_VALUES = [
    const.OVERDUE_HANDLING_AT_DUE_DATE,
    const.OVERDUE_HANDLING_NEVER_OVERDUE,
    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
]

# Days of week - using raw values since there are no individual DAY_* constants
_DAY_OF_WEEK_VALUES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

CREATE_CHORE_SCHEMA = vol.Schema(
    {
        vol.Required(const.SERVICE_FIELD_CHORE_CRUD_NAME): cv.string,
        vol.Required(const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_KIDS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_POINTS): vol.Coerce(float),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DESCRIPTION, default=""): cv.string,
        vol.Optional(
            const.SERVICE_FIELD_CHORE_CRUD_ICON, default=const.SENTINEL_EMPTY
        ): vol.Any(None, "", cv.icon),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_LABELS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_FREQUENCY): vol.In(
            _CHORE_FREQUENCY_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPLICABLE_DAYS): vol.All(
            cv.ensure_list, [vol.In(_DAY_OF_WEEK_VALUES)]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA): vol.In(
            _COMPLETION_CRITERIA_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET): vol.In(
            _APPROVAL_RESET_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_PENDING_CLAIMS): vol.In(
            _PENDING_CLAIMS_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING): vol.In(
            _OVERDUE_HANDLING_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_AUTO_APPROVE): cv.boolean,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE): cv.datetime,
    }
)

# NOTE: Either chore_id OR name must be provided (resolved in handler)
# completion_criteria is NOT allowed in update (immutable after creation)
UPDATE_CHORE_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_KIDS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_POINTS): vol.Coerce(float),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DESCRIPTION): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ICON): vol.Any(None, "", cv.icon),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_LABELS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_FREQUENCY): vol.In(
            _CHORE_FREQUENCY_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPLICABLE_DAYS): vol.All(
            cv.ensure_list, [vol.In(_DAY_OF_WEEK_VALUES)]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET): vol.In(
            _APPROVAL_RESET_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_PENDING_CLAIMS): vol.In(
            _PENDING_CLAIMS_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING): vol.In(
            _OVERDUE_HANDLING_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_AUTO_APPROVE): cv.boolean,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE): cv.datetime,
    }
)

# NOTE: Either chore_id OR name must be provided (resolved in handler)
DELETE_CHORE_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_NAME): cv.string,
    }
)

# Map service fields to DATA_* storage keys
# This bridges user-friendly service API → internal storage keys
# NOTE: Chores use DATA_* keys (unlike rewards which use CFOF_* keys)
_SERVICE_TO_CHORE_DATA_MAPPING: dict[str, str] = {
    const.SERVICE_FIELD_CHORE_CRUD_NAME: const.DATA_CHORE_NAME,
    const.SERVICE_FIELD_CHORE_CRUD_POINTS: const.DATA_CHORE_DEFAULT_POINTS,
    const.SERVICE_FIELD_CHORE_CRUD_DESCRIPTION: const.DATA_CHORE_DESCRIPTION,
    const.SERVICE_FIELD_CHORE_CRUD_ICON: const.DATA_CHORE_ICON,
    const.SERVICE_FIELD_CHORE_CRUD_LABELS: const.DATA_CHORE_LABELS,
    const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_KIDS: const.DATA_CHORE_ASSIGNED_KIDS,
    const.SERVICE_FIELD_CHORE_CRUD_FREQUENCY: const.DATA_CHORE_RECURRING_FREQUENCY,
    const.SERVICE_FIELD_CHORE_CRUD_APPLICABLE_DAYS: const.DATA_CHORE_APPLICABLE_DAYS,
    const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA: const.DATA_CHORE_COMPLETION_CRITERIA,
    const.SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET: const.DATA_CHORE_APPROVAL_RESET_TYPE,
    const.SERVICE_FIELD_CHORE_CRUD_PENDING_CLAIMS: const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    const.SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING: const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
    const.SERVICE_FIELD_CHORE_CRUD_AUTO_APPROVE: const.DATA_CHORE_AUTO_APPROVE,
    # NOTE: due_date is handled specially via set_chore_due_date() hook
}

# Map service fields to DATA_* storage keys for rewards
# This bridges user-friendly service API → internal storage keys
# NOTE: Now matches chore pattern (DATA_* keys directly)
_SERVICE_TO_REWARD_DATA_MAPPING: dict[str, str] = {
    const.SERVICE_FIELD_REWARD_NAME: const.DATA_REWARD_NAME,
    const.SERVICE_FIELD_REWARD_COST: const.DATA_REWARD_COST,
    const.SERVICE_FIELD_REWARD_DESCRIPTION: const.DATA_REWARD_DESCRIPTION,
    const.SERVICE_FIELD_REWARD_ICON: const.DATA_REWARD_ICON,
    const.SERVICE_FIELD_REWARD_LABELS: const.DATA_REWARD_LABELS,
}


def _map_service_to_data_keys(
    service_data: dict[str, Any],
    mapping: dict[str, str],
) -> dict[str, Any]:
    """Convert service field names to DATA_* storage keys.

    Args:
        service_data: Data from service call with user-friendly field names
        mapping: Dict mapping service field names to DATA_* constants

    Returns:
        Dict with DATA_* keys for data_builders consumption
    """
    return {
        mapping[key]: value for key, value in service_data.items() if key in mapping
    }


# --- Setup Services ---
def async_setup_services(hass: HomeAssistant):
    """Register KidsChores services."""

    # ==========================================================================
    # RESET SERVICE HANDLERS
    # ==========================================================================

    async def handle_manage_shadow_link(call: ServiceCall):
        """Handle linking or unlinking a shadow kid."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Manage Shadow Link: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        name = call.data[const.FIELD_NAME]
        action = call.data[const.FIELD_ACTION]

        # Resolve name to IDs (case-insensitive)
        kid_id = kh.get_entity_id_by_name(coordinator, const.ENTITY_TYPE_KID, name)
        parent_id = kh.get_entity_id_by_name(
            coordinator, const.ENTITY_TYPE_PARENT, name
        )

        if action == const.ACTION_LINK:
            # LINK: Validate kid and parent exist with matching names
            if not kid_id:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_KID_NOT_FOUND_BY_NAME,
                    translation_placeholders={"name": name},
                )
            if not parent_id:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_PARENT_NOT_FOUND_BY_NAME,
                    translation_placeholders={"name": name},
                )

            kid_info = coordinator.kids_data.get(kid_id)
            parent_info = coordinator.parents_data.get(parent_id)

            if not kid_info or not parent_info:
                const.LOGGER.error(
                    "Data mismatch: kid_id=%s, parent_id=%s", kid_id, parent_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
                )

            # Validate kid is not already a shadow kid
            if kid_info.get(const.DATA_KID_IS_SHADOW, False):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_KID_ALREADY_SHADOW,
                    translation_placeholders={"name": name},
                )

            # Validate parent doesn't already have a different shadow kid
            existing_shadow_id = parent_info.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID)
            if existing_shadow_id and existing_shadow_id != kid_id:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_PARENT_HAS_DIFFERENT_SHADOW,
                    translation_placeholders={"name": name},
                )

            # Link: Update kid to shadow status (direct storage update)
            coordinator._data[const.DATA_KIDS][kid_id].update(
                {
                    const.DATA_KID_IS_SHADOW: True,
                    const.DATA_KID_LINKED_PARENT_ID: parent_id,
                }
            )

            # Link: Update parent (enable all chore features for shadow kid)
            coordinator._data[const.DATA_PARENTS][parent_id].update(
                {
                    const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT: True,
                    const.DATA_PARENT_LINKED_SHADOW_KID_ID: kid_id,
                    # Always enable workflow and gamification when linking
                    # This gives the parent full chore functionality through their shadow kid
                    # User can disable these later in options flow if desired
                    const.DATA_PARENT_ENABLE_CHORE_WORKFLOW: True,
                    const.DATA_PARENT_ENABLE_GAMIFICATION: True,
                }
            )

            const.LOGGER.info("Linked kid '%s' to parent '%s' as shadow", name, name)

        elif action == const.ACTION_UNLINK:
            # UNLINK: Validate kid exists
            if not kid_id:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_KID_NOT_FOUND_BY_NAME,
                    translation_placeholders={"name": name},
                )

            kid_info = coordinator.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error("Data mismatch: kid_id=%s", kid_id)
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
                )

            # Validate kid IS a shadow kid
            if not kid_info.get(const.DATA_KID_IS_SHADOW, False):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_KID_NOT_SHADOW,
                    translation_placeholders={"name": name},
                )

            # Use coordinator helper (reusable code)
            coordinator._unlink_shadow_kid(kid_id)

            const.LOGGER.info(
                "Unlinked shadow kid '%s' (renamed to '%s_unlinked')", name, name
            )

        # Persist changes and wait for storage write to complete
        coordinator.store.set_data(coordinator._data)
        await coordinator.store.async_save()

        # Reload config entry to update device info (model changes from Kid/Parent Profile)
        # This ensures device descriptions update immediately after storage write completes
        await hass.config_entries.async_reload(coordinator.config_entry.entry_id)

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_MANAGE_SHADOW_LINK,
        handle_manage_shadow_link,
        schema=MANAGE_SHADOW_LINK_SCHEMA,
    )

    # ========================================================================
    # CHORE SERVICE HANDLERS
    # ========================================================================

    async def handle_create_chore(call: ServiceCall) -> dict[str, Any]:
        """Handle kidschores.create_chore service call.

        Creates a new chore using data_builders.build_chore() for consistent
        field handling with the Options Flow UI.

        Args:
            call: Service call with name, assigned_kids, and optional fields

        Returns:
            Dict with chore_id of the created chore

        Raises:
            HomeAssistantError: If no coordinator available or validation fails
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Create Chore: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve kid names to UUIDs
        kid_names = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_KIDS, [])
        kid_ids = []
        for kid_name in kid_names:
            try:
                kid_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_KID, kid_name
                )
                kid_ids.append(kid_id)
            except HomeAssistantError as err:
                const.LOGGER.warning("Create Chore - kid lookup failed: %s", err)
                raise

        # Map service fields to DATA_* keys
        data_input = _map_service_to_data_keys(
            dict(call.data), _SERVICE_TO_CHORE_DATA_MAPPING
        )
        # Override assigned_kids with resolved UUIDs
        data_input[const.DATA_CHORE_ASSIGNED_KIDS] = kid_ids

        # Extract due_date for special handling (not passed to build_chore)
        due_date_input = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE)

        # Include due_date in validation if provided
        if due_date_input:
            data_input[const.DATA_CHORE_DUE_DATE] = due_date_input

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_chore_data(
            data_input,
            coordinator.chores_data,
            is_update=False,
            current_chore_id=None,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # build_chore(input) - create mode (no existing)
            chore_dict = db.build_chore(data_input)
            internal_id = chore_dict[const.DATA_CHORE_INTERNAL_ID]

            coordinator._data[const.DATA_CHORES][internal_id] = dict(chore_dict)
            coordinator._persist()

            # Handle due_date via set_chore_due_date hook (respects SHARED/INDEPENDENT)
            if due_date_input:
                coordinator.set_chore_due_date(internal_id, due_date_input, kid_id=None)
                coordinator._persist()

            # Create chore status sensor entities for all assigned kids
            from .sensor import create_chore_entities

            create_chore_entities(coordinator, internal_id)

            coordinator.async_update_listeners()

            const.LOGGER.info(
                "Service created chore '%s' with ID: %s",
                chore_dict[const.DATA_CHORE_NAME],
                internal_id,
            )

            return {const.SERVICE_FIELD_CHORE_CRUD_ID: internal_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
                translation_placeholders=err.placeholders,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_CREATE_CHORE,
        handle_create_chore,
        schema=CREATE_CHORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_update_chore(call: ServiceCall) -> dict[str, Any]:
        """Handle kidschores.update_chore service call.

        Updates an existing chore using data_builders.build_chore() for consistent
        field handling with the Options Flow UI. Only provided fields are updated.

        Accepts either chore_id OR name to identify the chore:
        - name: User-friendly, looks up ID by name (recommended)
        - id: Direct UUID for advanced automation use

        IMPORTANT: completion_criteria cannot be changed after creation.

        Args:
            call: Service call with chore identifier and optional update fields

        Returns:
            Dict with chore_id of the updated chore

        Raises:
            HomeAssistantError: If chore not found, validation fails, or neither
                chore_id nor name provided
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve chore: either chore_id or name must be provided
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_NAME)

        # If name provided without chore_id, look up the ID
        if not chore_id and chore_name:
            try:
                chore_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Update Chore: %s", err)
                raise

        # Validate we have a chore_id at this point
        if not chore_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_CHORE_IDENTIFIER,
            )

        if chore_id not in coordinator.chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_CHORE_NOT_FOUND,
                translation_placeholders={const.SERVICE_FIELD_CHORE_CRUD_ID: chore_id},
            )

        existing_chore = coordinator.chores_data[chore_id]

        # Block completion_criteria changes (immutable after creation)
        if const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA in call.data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_COMPLETION_CRITERIA_IMMUTABLE,
            )

        # Build data input, excluding name if it was used for lookup
        service_data = dict(call.data)
        if not call.data.get(const.SERVICE_FIELD_CHORE_CRUD_ID) and chore_name:
            # name was used for lookup, not for renaming
            service_data.pop(const.SERVICE_FIELD_CHORE_CRUD_NAME, None)

        # Resolve kid names to UUIDs if assigned_kids is being updated
        if const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_KIDS in service_data:
            kid_names = service_data[const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_KIDS]
            kid_ids = []
            for kid_name in kid_names:
                try:
                    kid_id = kh.get_entity_id_or_raise(
                        coordinator, const.ENTITY_TYPE_KID, kid_name
                    )
                    kid_ids.append(kid_id)
                except HomeAssistantError as err:
                    const.LOGGER.warning("Update Chore - kid lookup failed: %s", err)
                    raise
            service_data[const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_KIDS] = kid_ids

        # Map service fields to DATA_* keys
        data_input = _map_service_to_data_keys(
            service_data, _SERVICE_TO_CHORE_DATA_MAPPING
        )

        # Extract due_date for special handling
        due_date_input = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE)

        # Include due_date in validation if provided
        if due_date_input is not None:
            data_input[const.DATA_CHORE_DUE_DATE] = due_date_input

        # For update: merge with existing data for accurate validation
        # (assigned_kids may not be in data_input if not being updated)
        validation_data = dict(data_input)
        if const.DATA_CHORE_ASSIGNED_KIDS not in validation_data:
            validation_data[const.DATA_CHORE_ASSIGNED_KIDS] = existing_chore.get(
                const.DATA_CHORE_ASSIGNED_KIDS, []
            )
        # Similarly for other fields needed for combination validation
        for key in (
            const.DATA_CHORE_RECURRING_FREQUENCY,
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DATA_CHORE_COMPLETION_CRITERIA,
        ):
            if key not in validation_data:
                validation_data[key] = existing_chore.get(key)

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_chore_data(
            validation_data,
            coordinator.chores_data,
            is_update=True,
            current_chore_id=chore_id,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # build_chore(input, existing) - update mode
            chore_dict = db.build_chore(data_input, existing=existing_chore)

            coordinator._data[const.DATA_CHORES][chore_id] = dict(chore_dict)
            coordinator._persist()

            # Handle due_date via set_chore_due_date hook (respects SHARED/INDEPENDENT)
            if due_date_input is not None:
                coordinator.set_chore_due_date(chore_id, due_date_input, kid_id=None)
                coordinator._persist()

            coordinator.async_update_listeners()

            const.LOGGER.info(
                "Service updated chore '%s' with ID: %s",
                chore_dict[const.DATA_CHORE_NAME],
                chore_id,
            )

            return {const.SERVICE_FIELD_CHORE_CRUD_ID: chore_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_UPDATE_CHORE,
        handle_update_chore,
        schema=UPDATE_CHORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_delete_chore(call: ServiceCall) -> dict[str, Any]:
        """Handle kidschores.delete_chore service call.

        Deletes a chore and cleans up all references.

        Accepts either chore_id OR name to identify the chore:
        - name: User-friendly, looks up ID by name (recommended)
        - id: Direct UUID for advanced automation use

        Args:
            call: Service call with chore identifier

        Returns:
            Dict with chore_id of the deleted chore

        Raises:
            HomeAssistantError: If chore not found or neither
                chore_id nor name provided
        """
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve chore: either chore_id or name must be provided
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_NAME)

        # If name provided without chore_id, look up the ID
        if not chore_id and chore_name:
            try:
                chore_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Delete Chore: %s", err)
                raise

        # Validate we have a chore_id at this point
        if not chore_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_CHORE_IDENTIFIER,
            )

        # Use coordinator's delete method (handles cleanup and persistence)
        coordinator.delete_chore_entity(chore_id)

        const.LOGGER.info("Service deleted chore with ID: %s", chore_id)

        return {const.SERVICE_FIELD_CHORE_CRUD_ID: chore_id}

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DELETE_CHORE,
        handle_delete_chore,
        schema=DELETE_CHORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_claim_chore(call: ServiceCall):
        """Handle claiming a chore."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Claim Chore: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        user_id = call.context.user_id
        kid_name = call.data[const.FIELD_KID_NAME]
        chore_name = call.data[const.FIELD_CHORE_NAME]

        # Map kid_name and chore_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            chore_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_CHORE, chore_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Claim Chore: %s", err)
            raise

        # Check if user is authorized
        if user_id and not await kh.is_user_authorized_for_kid(hass, user_id, kid_id):
            const.LOGGER.warning(
                "Claim Chore: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_CLAIM_CHORES},
            )

        # Process chore claim
        coordinator.claim_chore(
            kid_id=kid_id, chore_id=chore_id, user_name=f"user:{user_id}"
        )

        const.LOGGER.info(
            "Chore '%s' claimed by kid '%s' by user '%s'",
            chore_name,
            kid_name,
            user_id,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        handle_claim_chore,
        schema=CLAIM_CHORE_SCHEMA,
    )

    async def handle_approve_chore(call: ServiceCall):
        """Handle approving a claimed chore."""
        entry_id = kh.get_first_kidschores_entry(hass)

        if not entry_id:
            const.LOGGER.warning(
                "Approve Chore: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        user_id = call.context.user_id
        parent_name = call.data[const.FIELD_PARENT_NAME]
        kid_name = call.data[const.FIELD_KID_NAME]
        chore_name = call.data[const.FIELD_CHORE_NAME]
        points_awarded = call.data.get(const.FIELD_POINTS_AWARDED)

        # Map kid_name and chore_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            chore_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_CHORE, chore_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Approve Chore: %s", err)
            raise

        # Check if user is authorized
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_APPROVE_CHORE
        ):
            const.LOGGER.warning(
                "Approve Chore: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPROVE_CHORES},
            )

        # Approve chore and assign points
        try:
            await coordinator.approve_chore(
                parent_name=parent_name,
                kid_id=kid_id,
                chore_id=chore_id,
                points_awarded=points_awarded,
            )
            const.LOGGER.info(
                "Chore '%s' approved for kid '%s' by parent '%s'. Points Awarded: %s",
                chore_name,
                kid_name,
                parent_name,
                points_awarded,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPROVE_CHORE,
        handle_approve_chore,
        schema=APPROVE_CHORE_SCHEMA,
    )

    async def handle_disapprove_chore(call: ServiceCall):
        """Handle disapproving a chore."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Disapprove Chore: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        parent_name = call.data[const.FIELD_PARENT_NAME]
        kid_name = call.data[const.FIELD_KID_NAME]
        chore_name = call.data[const.FIELD_CHORE_NAME]

        # Map kid_name and chore_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            chore_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_CHORE, chore_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Disapprove Chore: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_DISAPPROVE_CHORE
        ):
            const.LOGGER.warning(
                "Disapprove Chore: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={
                    "action": const.ERROR_ACTION_DISAPPROVE_CHORES
                },
            )

        # Disapprove the chore
        coordinator.disapprove_chore(
            parent_name=parent_name,
            kid_id=kid_id,
            chore_id=chore_id,
        )
        const.LOGGER.info(
            "Chore '%s' disapproved for kid '%s' by parent '%s'",
            chore_name,
            kid_name,
            parent_name,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DISAPPROVE_CHORE,
        handle_disapprove_chore,
        schema=DISAPPROVE_CHORE_SCHEMA,
    )

    async def handle_set_chore_due_date(call: ServiceCall):
        """Handle setting (or clearing) the due date of a chore.

        For INDEPENDENT chores, optionally specify kid_id or kid_name.
        For SHARED chores, kid_id is ignored (single due date for all kids).
        """
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Set Chore Due Date: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        chore_name = call.data[const.FIELD_CHORE_NAME]
        due_date_input = call.data.get(const.FIELD_DUE_DATE)
        kid_name = call.data.get(const.FIELD_KID_NAME)
        kid_id = call.data.get(const.FIELD_KID_ID)

        # Look up the chore by name:
        try:
            chore_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_CHORE, chore_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Set Chore Due Date: %s", err)
            raise

        # If kid_name is provided, resolve it to kid_id
        if kid_name and not kid_id:
            try:
                kid_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_KID, kid_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Set Chore Due Date: %s", err)
                raise

        # Validate that if kid_id is provided, the chore is INDEPENDENT and kid is assigned
        if kid_id:
            chore_info: ChoreData = cast(
                "ChoreData", coordinator.chores_data.get(chore_id, {})
            )
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            # Reject kid_id for SHARED and SHARED_FIRST chores
            # (they use chore-level due dates, not per-kid)
            if completion_criteria in (
                const.COMPLETION_CRITERIA_SHARED,
                const.COMPLETION_CRITERIA_SHARED_FIRST,
            ):
                const.LOGGER.warning(
                    "Set Chore Due Date: Cannot specify kid_id for %s chore '%s'",
                    completion_criteria,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_SHARED_CHORE_KID,
                    translation_placeholders={"chore_name": str(chore_name)},
                )

            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if kid_id not in assigned_kids:
                const.LOGGER.warning(
                    "Set Chore Due Date: Kid '%s' not assigned to chore '%s'",
                    kid_id,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": str(kid_name or kid_id),
                        "kid": str(chore_name),
                    },
                )

        if due_date_input:
            try:
                # Convert the provided date to UTC-aware datetime
                due_dt_raw = kh.dt_parse(
                    due_date_input,
                    return_type=const.HELPER_RETURN_DATETIME_UTC,
                )
                # Ensure due_dt is a datetime object (not date or str)
                if due_dt_raw and not isinstance(due_dt_raw, datetime):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_INVALID_DATE_FORMAT,
                    )
                due_dt: datetime | None = due_dt_raw  # type: ignore[assignment]
                if (
                    due_dt
                    and isinstance(due_dt, datetime)
                    and due_dt < dt_util.utcnow()
                ):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_DATE_IN_PAST,
                    )

            except HomeAssistantError as err:
                const.LOGGER.error(
                    "Set Chore Due Date: Invalid due date '%s': %s",
                    due_date_input,
                    err,
                )
                raise

            # Update the chore’s due_date:
            coordinator.set_chore_due_date(chore_id, due_dt, kid_id)
            const.LOGGER.info(
                "Set due date for chore '%s' (ID: %s) to %s",
                chore_name,
                chore_id,
                due_date_input,
            )
        else:
            # Clear the due date by setting it to None
            coordinator.set_chore_due_date(chore_id, None, kid_id)
            const.LOGGER.info(
                "Cleared due date for chore '%s' (ID: %s)", chore_name, chore_id
            )

        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SET_CHORE_DUE_DATE,
        handle_set_chore_due_date,
        schema=SET_CHORE_DUE_DATE_SCHEMA,
    )

    async def handle_skip_chore_due_date(call: ServiceCall) -> None:
        """Handle skipping the due date on a chore by rescheduling it to the next due date.

        For INDEPENDENT chores, you can optionally specify kid_name or kid_id.
        For SHARED chores, you must not specify a kid.
        """
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Skip Chore Due Date: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Get parameters: either chore_id or chore_name must be provided.
        chore_id = call.data.get(const.FIELD_CHORE_ID)
        chore_name = call.data.get(const.FIELD_CHORE_NAME)

        try:
            if not chore_id and chore_name:
                chore_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_CHORE, chore_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Skip Chore Due Date: %s", err)
            raise

        if not chore_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_CHORE,
            )

        # Get kid parameters (for INDEPENDENT chores only)
        kid_name = call.data.get(const.FIELD_KID_NAME)
        kid_id = call.data.get(const.FIELD_KID_ID)

        # Resolve kid_name to kid_id if provided
        if kid_name and not kid_id:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )

        # Validate kid_id (if provided)
        if kid_id:
            chore_info: ChoreData = cast(
                "ChoreData", coordinator.chores_data.get(chore_id, {})
            )
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            # Reject kid_id for SHARED and SHARED_FIRST chores
            # (they use chore-level due dates, not per-kid)
            if completion_criteria in (
                const.COMPLETION_CRITERIA_SHARED,
                const.COMPLETION_CRITERIA_SHARED_FIRST,
            ):
                const.LOGGER.warning(
                    "Skip Chore Due Date: Cannot specify kid_id for %s chore '%s'",
                    completion_criteria,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_SHARED_CHORE_KID,
                    translation_placeholders={"chore_name": str(chore_name)},
                )

            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if kid_id not in assigned_kids:
                const.LOGGER.warning(
                    "Skip Chore Due Date: Kid '%s' not assigned to chore '%s'",
                    kid_id,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": str(kid_name or kid_id),
                        "kid": str(chore_name),
                    },
                )

        coordinator.skip_chore_due_date(chore_id, kid_id)
        kid_context = f" for kid '{kid_name or kid_id}'" if kid_id else ""
        const.LOGGER.info(
            "Skipped due date for chore '%s' (ID: %s)%s",
            chore_name or chore_id,
            chore_id,
            kid_context,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SKIP_CHORE_DUE_DATE,
        handle_skip_chore_due_date,
        schema=SKIP_CHORE_DUE_DATE_SCHEMA,
    )

    # ==========================================================================
    # REWARD SERVICE HANDLERS
    # ==========================================================================

    async def handle_create_reward(call: ServiceCall) -> dict[str, Any]:
        """Handle kidschores.create_reward service call.

        Creates a new reward using data_builders.build_reward() for consistent
        field handling with the Options Flow UI.

        Args:
            call: Service call with name, cost, description, icon, labels

        Returns:
            Dict with reward_id of the created reward

        Raises:
            HomeAssistantError: If no coordinator available or validation fails
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Create Reward: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Map service fields to DATA_* keys for data_builders
        data_input = _map_service_to_data_keys(
            dict(call.data), _SERVICE_TO_REWARD_DATA_MAPPING
        )

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_reward_data(
            data_input,
            coordinator.rewards_data,
            is_update=False,
            current_reward_id=None,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # build_reward(input) - create mode (no existing)
            reward_dict = db.build_reward(data_input)
            internal_id = reward_dict[const.DATA_REWARD_INTERNAL_ID]

            coordinator._data[const.DATA_REWARDS][internal_id] = dict(reward_dict)
            coordinator._persist()
            coordinator.async_update_listeners()

            const.LOGGER.info(
                "Service created reward '%s' with ID: %s",
                reward_dict[const.DATA_REWARD_NAME],
                internal_id,
            )

            return {const.SERVICE_FIELD_REWARD_ID: internal_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
                translation_placeholders=err.placeholders,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_CREATE_REWARD,
        handle_create_reward,
        schema=CREATE_REWARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_update_reward(call: ServiceCall) -> dict[str, Any]:
        """Handle kidschores.update_reward service call.

        Updates an existing reward using data_builders.build_reward() for consistent
        field handling with the Options Flow UI. Only provided fields are updated.

        Accepts either reward_id OR reward_name to identify the reward:
        - reward_name: User-friendly, looks up ID by name (recommended)
        - reward_id: Direct UUID for advanced automation use

        Args:
            call: Service call with reward identifier and optional update fields

        Returns:
            Dict with reward_id of the updated reward

        Raises:
            HomeAssistantError: If reward not found, validation fails, or neither
                reward_id nor reward_name provided
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve reward: either reward_id or reward_name must be provided
        reward_id = call.data.get(const.SERVICE_FIELD_REWARD_ID)
        reward_name = call.data.get(const.SERVICE_FIELD_REWARD_NAME)

        # If reward_name provided without reward_id, look up the ID
        if not reward_id and reward_name:
            try:
                reward_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_REWARD, reward_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Update Reward: %s", err)
                raise

        # Validate we have a reward_id at this point
        if not reward_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_REWARD_IDENTIFIER,
            )

        if reward_id not in coordinator.rewards_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_REWARD_NOT_FOUND,
                translation_placeholders={const.SERVICE_FIELD_REWARD_ID: reward_id},
            )

        existing_reward = coordinator.rewards_data[reward_id]

        # Build data input, excluding reward_name if it was used for lookup
        # (don't treat lookup name as a rename request)
        service_data = dict(call.data)
        if not call.data.get(const.SERVICE_FIELD_REWARD_ID) and reward_name:
            # reward_name was used for lookup, not for renaming
            # Only include it in data_input if there's ALSO a reward_id (explicit rename)
            service_data.pop(const.SERVICE_FIELD_REWARD_NAME, None)

        data_input = _map_service_to_data_keys(
            service_data, _SERVICE_TO_REWARD_DATA_MAPPING
        )

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_reward_data(
            data_input,
            coordinator.rewards_data,
            is_update=True,
            current_reward_id=reward_id,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # build_reward(input, existing) - update mode
            reward_dict = db.build_reward(data_input, existing=existing_reward)

            coordinator._data[const.DATA_REWARDS][reward_id] = dict(reward_dict)
            coordinator._persist()
            coordinator.async_update_listeners()

            const.LOGGER.info(
                "Service updated reward '%s' with ID: %s",
                reward_dict[const.DATA_REWARD_NAME],
                reward_id,
            )

            return {const.SERVICE_FIELD_REWARD_ID: reward_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_UPDATE_REWARD,
        handle_update_reward,
        schema=UPDATE_REWARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_delete_reward(call: ServiceCall) -> dict[str, Any]:
        """Handle kidschores.delete_reward service call.

        Deletes a reward and cleans up all references.

        Accepts either reward_id OR reward_name to identify the reward:
        - reward_name: User-friendly, looks up ID by name (recommended)
        - reward_id: Direct UUID for advanced automation use

        Args:
            call: Service call with reward identifier

        Returns:
            Dict with reward_id of the deleted reward

        Raises:
            HomeAssistantError: If reward not found or neither
                reward_id nor reward_name provided
        """
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve reward: either reward_id or reward_name must be provided
        reward_id = call.data.get(const.SERVICE_FIELD_REWARD_ID)
        reward_name = call.data.get(const.SERVICE_FIELD_REWARD_NAME)

        # If reward_name provided without reward_id, look up the ID
        if not reward_id and reward_name:
            try:
                reward_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_REWARD, reward_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Delete Reward: %s", err)
                raise

        # Validate we have a reward_id at this point
        if not reward_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_REWARD_IDENTIFIER,
            )

        # Use coordinator's delete method (handles cleanup and persistence)
        coordinator.delete_reward_entity(reward_id)

        const.LOGGER.info("Service deleted reward with ID: %s", reward_id)

        return {const.SERVICE_FIELD_REWARD_ID: reward_id}

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DELETE_REWARD,
        handle_delete_reward,
        schema=DELETE_REWARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_redeem_reward(call: ServiceCall):
        """Handle redeeming a reward (claiming without deduction)."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Redeem Reward: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        parent_name = call.data[const.FIELD_PARENT_NAME]
        kid_name = call.data[const.FIELD_KID_NAME]
        reward_name = call.data[const.FIELD_REWARD_NAME]

        # Map kid_name and reward_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            reward_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_REWARD, reward_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Redeem Reward: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_kid(hass, user_id, kid_id):
            const.LOGGER.warning(
                "Redeem Reward: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_REDEEM_REWARDS},
            )

        # Check if kid has enough points
        kid_info = coordinator.kids_data.get(kid_id)
        reward_info = coordinator.rewards_data.get(reward_id)
        if not kid_info:
            const.LOGGER.warning("Redeem Reward: Kid not found")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_name or "unknown",
                },
            )
        if not reward_info:
            const.LOGGER.warning("Redeem Reward: Reward not found")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_name or "unknown",
                },
            )

        if kid_info[const.DATA_KID_POINTS] < reward_info.get(
            const.DATA_REWARD_COST, const.DEFAULT_ZERO
        ):
            const.LOGGER.warning(
                "Redeem Reward: %s", const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                translation_placeholders={
                    "kid_name": kid_name,
                    "reward_name": reward_name,
                },
            )

        # Process reward claim without deduction
        try:
            coordinator.redeem_reward(
                parent_name=parent_name, kid_id=kid_id, reward_id=reward_id
            )
            const.LOGGER.info(
                "Reward '%s' claimed by kid '%s' and pending approval by parent '%s'",
                reward_name,
                kid_name,
                parent_name,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_REDEEM_REWARD,
        handle_redeem_reward,
        schema=REDEEM_REWARD_SCHEMA,
    )

    async def handle_approve_reward(call: ServiceCall):
        """Handle approving a reward claimed by a kid."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Approve Reward: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        user_id = call.context.user_id
        parent_name = call.data[const.FIELD_PARENT_NAME]
        kid_name = call.data[const.FIELD_KID_NAME]
        reward_name = call.data[const.FIELD_REWARD_NAME]

        # Map kid_name and reward_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            reward_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_REWARD, reward_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Approve Reward: %s", err)
            raise

        # Check if user is authorized
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_APPROVE_REWARD
        ):
            const.LOGGER.warning(
                "Approve Reward: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPROVE_REWARDS},
            )

        # Approve reward redemption and deduct points
        # Extract optional cost_override (None if not provided)
        cost_override = call.data.get(const.FIELD_COST_OVERRIDE)

        try:
            await coordinator.approve_reward(
                parent_name=parent_name,
                kid_id=kid_id,
                reward_id=reward_id,
                cost_override=cost_override,
            )
            const.LOGGER.info(
                "Reward '%s' approved for kid '%s' by parent '%s'%s",
                reward_name,
                kid_name,
                parent_name,
                f" (cost override: {cost_override})"
                if cost_override is not None
                else "",
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPROVE_REWARD,
        handle_approve_reward,
        schema=APPROVE_REWARD_SCHEMA,
    )

    async def handle_disapprove_reward(call: ServiceCall):
        """Handle disapproving a reward."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Disapprove Reward: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        parent_name = call.data[const.FIELD_PARENT_NAME]
        kid_name = call.data[const.FIELD_KID_NAME]
        reward_name = call.data[const.FIELD_REWARD_NAME]

        # Map kid_name and reward_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            reward_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_REWARD, reward_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Disapprove Reward: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_DISAPPROVE_REWARD
        ):
            const.LOGGER.warning(
                "Disapprove Reward: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={
                    "action": const.ERROR_ACTION_DISAPPROVE_REWARDS
                },
            )

        # Disapprove the reward
        coordinator.disapprove_reward(
            parent_name=parent_name,
            kid_id=kid_id,
            reward_id=reward_id,
        )
        const.LOGGER.info(
            "Reward '%s' disapproved for kid '%s' by parent '%s'",
            reward_name,
            kid_name,
            parent_name,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DISAPPROVE_REWARD,
        handle_disapprove_reward,
        schema=DISAPPROVE_REWARD_SCHEMA,
    )

    async def handle_reset_rewards(call: ServiceCall):
        """Handle resetting rewards counts."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Reset Rewards: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        kid_name = call.data.get(const.FIELD_KID_NAME)
        reward_name = call.data.get(const.FIELD_REWARD_NAME)

        # Map names to IDs (optional parameters)
        kid_id = None
        reward_id = None
        try:
            if kid_name:
                kid_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_KID, kid_name
                )
            if reward_name:
                reward_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_REWARD, reward_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Reset Rewards: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_RESET_REWARDS
        ):
            const.LOGGER.warning(
                "Reset Rewards: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                translation_placeholders={"action": const.ERROR_ACTION_RESET_REWARDS},
            )

        # Log action based on parameters provided
        if kid_id is None and reward_id is None:
            const.LOGGER.info("Resetting all rewards for all kids.")
        elif kid_id is None:
            const.LOGGER.info("Resetting reward '%s' for all kids.", reward_name)
        elif reward_id is None:
            const.LOGGER.info("Resetting all rewards for kid '%s'.", kid_name)
        else:
            const.LOGGER.info(
                "Resetting reward '%s' for kid '%s'.", reward_name, kid_name
            )

        # Reset rewards
        coordinator.reset_rewards(kid_id=kid_id, reward_id=reward_id)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_REWARDS,
        handle_reset_rewards,
        schema=RESET_REWARDS_SCHEMA,
    )

    # ==========================================================================
    # PENALTY SERVICE HANDLERS
    # ==========================================================================

    async def handle_apply_penalty(call: ServiceCall):
        """Handle applying a penalty."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Apply Penalty: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        parent_name = call.data[const.FIELD_PARENT_NAME]
        kid_name = call.data[const.FIELD_KID_NAME]
        penalty_name = call.data[const.FIELD_PENALTY_NAME]

        # Map kid_name and penalty_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            penalty_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_PENALTY, penalty_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Apply Penalty: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_APPLY_PENALTY
        ):
            const.LOGGER.warning(
                "Apply Penalty: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPLY_PENALTIES},
            )

        # Apply penalty
        try:
            coordinator.apply_penalty(
                parent_name=parent_name, kid_id=kid_id, penalty_id=penalty_id
            )
            const.LOGGER.info(
                "Penalty '%s' applied for kid '%s' by parent '%s'",
                penalty_name,
                kid_name,
                parent_name,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPLY_PENALTY,
        handle_apply_penalty,
        schema=APPLY_PENALTY_SCHEMA,
    )

    async def handle_reset_penalties(call: ServiceCall):
        """Handle resetting penalties."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Reset Penalties: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        kid_name = call.data.get(const.FIELD_KID_NAME)
        penalty_name = call.data.get(const.FIELD_PENALTY_NAME)

        # Map names to IDs (optional parameters)
        kid_id = None
        penalty_id = None
        try:
            if kid_name:
                kid_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_KID, kid_name
                )
            if penalty_name:
                penalty_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_PENALTY, penalty_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Reset Penalties: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_RESET_PENALTIES
        ):
            const.LOGGER.warning(
                "Reset Penalties: %s",
                const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                translation_placeholders={"action": const.ERROR_ACTION_RESET_PENALTIES},
            )

        # Log action based on parameters provided
        if kid_id is None and penalty_id is None:
            const.LOGGER.info("Resetting all penalties for all kids.")
        elif kid_id is None:
            const.LOGGER.info("Resetting penalty '%s' for all kids.", penalty_name)
        elif penalty_id is None:
            const.LOGGER.info("Resetting all penalties for kid '%s'.", kid_name)
        else:
            const.LOGGER.info(
                "Resetting penalty '%s' for kid '%s'.", penalty_name, kid_name
            )

        # Reset penalties
        coordinator.reset_penalties(kid_id=kid_id, penalty_id=penalty_id)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_PENALTIES,
        handle_reset_penalties,
        schema=RESET_PENALTIES_SCHEMA,
    )

    # ==========================================================================
    # BONUS SERVICE HANDLERS
    # ==========================================================================

    async def handle_apply_bonus(call: ServiceCall):
        """Handle applying a bonus."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Apply Bonus: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        parent_name = call.data[const.FIELD_PARENT_NAME]
        kid_name = call.data[const.FIELD_KID_NAME]
        bonus_name = call.data[const.FIELD_BONUS_NAME]

        # Map kid_name and bonus_name to internal_ids
        try:
            kid_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            bonus_id = kh.get_entity_id_or_raise(
                coordinator, const.ENTITY_TYPE_BONUS, bonus_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Apply Bonus: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_APPLY_BONUS
        ):
            const.LOGGER.warning("Apply Bonus: User not authorized")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPLY_BONUSES},
            )

        # Apply bonus
        try:
            coordinator.apply_bonus(
                parent_name=parent_name, kid_id=kid_id, bonus_id=bonus_id
            )
            const.LOGGER.info(
                "Bonus '%s' applied for kid '%s' by parent '%s'",
                bonus_name,
                kid_name,
                parent_name,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPLY_BONUS,
        handle_apply_bonus,
        schema=APPLY_BONUS_SCHEMA,
    )

    async def handle_reset_bonuses(call: ServiceCall):
        """Handle resetting bonuses."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Reset Bonuses: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        kid_name = call.data.get(const.FIELD_KID_NAME)
        bonus_name = call.data.get(const.FIELD_BONUS_NAME)

        # Map names to IDs (optional parameters)
        kid_id = None
        bonus_id = None
        try:
            if kid_name:
                kid_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_KID, kid_name
                )
            if bonus_name:
                bonus_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_BONUS, bonus_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Reset Bonuses: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_RESET_BONUSES
        ):
            const.LOGGER.warning(
                "Reset Bonuses: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                translation_placeholders={"action": const.ERROR_ACTION_RESET_BONUSES},
            )

        # Log action based on parameters provided
        if kid_id is None and bonus_id is None:
            const.LOGGER.info("Resetting all bonuses for all kids.")
        elif kid_id is None:
            const.LOGGER.info("Resetting bonus '%s' for all kids.", bonus_name)
        elif bonus_id is None:
            const.LOGGER.info("Resetting all bonuses for kid '%s'.", kid_name)
        else:
            const.LOGGER.info(
                "Resetting bonus '%s' for kid '%s'.", bonus_name, kid_name
            )

        # Reset bonuses
        coordinator.reset_bonuses(kid_id=kid_id, bonus_id=bonus_id)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_BONUSES,
        handle_reset_bonuses,
        schema=RESET_BONUSES_SCHEMA,
    )

    # ==========================================================================
    # BADGE SERVICE HANDLERS
    # ==========================================================================

    async def handle_remove_awarded_badges(call: ServiceCall):
        """Handle removing awarded badges."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Remove Awarded Badges: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        kid_name = call.data.get(const.FIELD_KID_NAME)
        badge_name = call.data.get(const.FIELD_BADGE_NAME)

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await kh.is_user_authorized_for_global_action(
            hass, user_id, const.SERVICE_REMOVE_AWARDED_BADGES
        ):
            const.LOGGER.warning("Remove Awarded Badges: User not authorized.")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                translation_placeholders={"action": const.ERROR_ACTION_REMOVE_BADGES},
            )

        # Log action based on parameters provided
        if kid_name is None and badge_name is None:
            const.LOGGER.info("Removing all badges for all kids.")
        elif kid_name is None:
            const.LOGGER.info("Removing badge '%s' for all kids.", badge_name)
        elif badge_name is None:
            const.LOGGER.info("Removing all badges for kid '%s'.", kid_name)
        else:
            const.LOGGER.info("Removing badge '%s' for kid '%s'.", badge_name, kid_name)

        # Remove awarded badges
        coordinator.remove_awarded_badges(kid_name=kid_name, badge_name=badge_name)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_REMOVE_AWARDED_BADGES,
        handle_remove_awarded_badges,
        schema=REMOVE_AWARDED_BADGES_SCHEMA,
    )

    # ==========================================================================
    # RESET SERVICE HANDLERS
    # ==========================================================================

    async def handle_reset_all_data(_call: ServiceCall):
        """Handle manually resetting ALL data in KidsChores (factory reset)."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning("Reset All Data: No KidsChores entry found")
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Step 1: Create backup before factory reset
        try:
            backup_name = await bh.create_timestamped_backup(
                hass,
                coordinator.store,
                const.BACKUP_TAG_RESET,
                coordinator.config_entry,
            )
            if backup_name:
                const.LOGGER.info("Created pre-reset backup: %s", backup_name)
            else:
                const.LOGGER.warning("No data available to include in pre-reset backup")
        except Exception as err:
            const.LOGGER.warning("Failed to create pre-reset backup: %s", err)

        # Step 2: Clean up entity registry BEFORE clearing storage
        # This prevents orphaned registry entries that cause _2 suffixes when re-adding entities
        ent_reg = er.async_get(hass)
        entity_count = 0
        for entity_entry in er.async_entries_for_config_entry(ent_reg, entry_id):
            ent_reg.async_remove(entity_entry.entity_id)
            entity_count += 1
            const.LOGGER.debug(
                "Removed entity registry entry: %s (unique_id: %s)",
                entity_entry.entity_id,
                entity_entry.unique_id,
            )

        const.LOGGER.info("Removed %d entity registry entries", entity_count)

        # Step 3: Clear everything from storage (resets to empty kids/chores/badges structure)
        await coordinator.store.async_clear_data()

        # Step 4: Reload config entry to clean up platforms and reinitialize
        # This ensures all internal state is properly reset
        await hass.config_entries.async_reload(entry_id)

        coordinator.async_set_updated_data(coordinator.data)
        const.LOGGER.info(
            "Factory reset complete. Backup created, entity registry cleaned, all data cleared."
        )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_ALL_DATA,
        handle_reset_all_data,
        schema=RESET_ALL_DATA_SCHEMA,
    )

    async def handle_reset_all_chores(_call: ServiceCall):
        """Handle manually resetting all chores to pending, clearing claims/approvals."""
        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning("Reset All Chores: No KidsChores entry found")
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Delegate to coordinator method
        coordinator.reset_all_chores()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_ALL_CHORES,
        handle_reset_all_chores,
        schema=RESET_ALL_CHORES_SCHEMA,
    )

    async def handle_reset_overdue_chores(call: ServiceCall) -> None:
        """Handle resetting overdue chores."""

        entry_id = kh.get_first_kidschores_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Reset Overdue Chores: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Get parameters
        chore_id = call.data.get(const.FIELD_CHORE_ID)
        chore_name = call.data.get(const.FIELD_CHORE_NAME)
        kid_name = call.data.get(const.FIELD_KID_NAME)

        # Map names to IDs (optional parameters)
        try:
            if not chore_id and chore_name:
                chore_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_CHORE, chore_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Reset Overdue Chores: %s", err)
            raise

        kid_id: str | None = None
        try:
            if kid_name:
                kid_id = kh.get_entity_id_or_raise(
                    coordinator, const.ENTITY_TYPE_KID, kid_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Reset Overdue Chores: %s", err)
            raise

        coordinator.reset_overdue_chores(chore_id=chore_id, kid_id=kid_id)

        const.LOGGER.info(
            "Reset overdue chores (chore_id=%s, kid_id=%s)", chore_id, kid_id
        )

        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_OVERDUE_CHORES,
        handle_reset_overdue_chores,
        schema=RESET_OVERDUE_CHORES_SCHEMA,
    )

    const.LOGGER.info("KidsChores services have been registered successfully")


async def async_unload_services(hass: HomeAssistant):
    """Unregister KidsChores services when unloading the integration."""
    services = [
        const.SERVICE_CLAIM_CHORE,
        const.SERVICE_APPROVE_CHORE,
        const.SERVICE_CREATE_CHORE,
        const.SERVICE_CREATE_REWARD,
        const.SERVICE_DELETE_CHORE,
        const.SERVICE_DELETE_REWARD,
        const.SERVICE_DISAPPROVE_CHORE,
        const.SERVICE_MANAGE_SHADOW_LINK,
        const.SERVICE_REDEEM_REWARD,
        const.SERVICE_DISAPPROVE_REWARD,
        const.SERVICE_APPLY_PENALTY,
        const.SERVICE_APPLY_BONUS,
        const.SERVICE_APPROVE_REWARD,
        const.SERVICE_RESET_ALL_DATA,
        const.SERVICE_RESET_ALL_CHORES,
        const.SERVICE_RESET_OVERDUE_CHORES,
        const.SERVICE_RESET_PENALTIES,
        const.SERVICE_RESET_BONUSES,
        const.SERVICE_RESET_REWARDS,
        const.SERVICE_UPDATE_CHORE,
        const.SERVICE_UPDATE_REWARD,
        const.SERVICE_REMOVE_AWARDED_BADGES,
        const.SERVICE_SET_CHORE_DUE_DATE,
        const.SERVICE_SKIP_CHORE_DUE_DATE,
    ]

    for service in services:
        if hass.services.has_service(const.DOMAIN, service):
            hass.services.async_remove(const.DOMAIN, service)

    const.LOGGER.info("KidsChores services have been unregistered")
