# File: options_flow.py
"""Options Flow for the KidsChores integration, managing entities by internal_id.

Handles add/edit/delete operations with entities referenced internally by internal_id.
Ensures consistency and reloads the integration upon changes.
"""
# pylint: disable=import-outside-toplevel
# protected-access: Options flow is tightly coupled to coordinator and needs direct access
# to internal creation/persistence methods (_create_* and _persist).
# broad-exception-caught: Reload operations use broad catch to ensure robustness per HA guidelines.
# too-many-lines: Options flow inherently large (2862 lines) due to menu-driven architecture
# import-outside-toplevel: Backup operations conditionally import to avoid circular deps/performance

import asyncio
import contextlib
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
import uuid

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util
import voluptuous as vol

from . import const, entity_helpers as eh, flow_helpers as fh, kc_helpers as kh
from .entity_helpers import EntityValidationError

if TYPE_CHECKING:
    from .type_defs import BadgeData

# ----------------------------------------------------------------------------------
# INITIALIZATION & HELPERS
# ----------------------------------------------------------------------------------


def _ensure_str(value):
    """Convert anything to string safely."""
    if isinstance(value, dict):
        # Attempt to get a known key or fallback
        return str(value.get("value", next(iter(value.values()), const.SENTINEL_EMPTY)))
    return str(value)


class KidsChoresOptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for adding/editing/deleting configuration elements."""

    def __init__(self, _config_entry: config_entries.ConfigEntry):
        """Initialize the options flow."""
        self._entry_options: dict[str, Any] = {}
        self._action = None
        self._entity_type = None
        self._reload_needed = False  # Track if reload is needed
        self._delete_confirmed = False  # Track backup deletion confirmation
        self._restore_confirmed = False  # Track backup restoration confirmation
        self._backup_to_delete: str | None = None  # Track backup filename to delete
        self._backup_to_restore: str | None = None  # Track backup filename to restore
        self._chore_being_edited: dict[str, Any] | None = (
            None  # For per-kid date editing
        )
        self._chore_template_date_raw: Any = None  # Template date for per-kid helper

    def _get_coordinator(self):
        """Get the coordinator from hass.data."""
        return self.hass.data[const.DOMAIN][self.config_entry.entry_id][
            const.COORDINATOR
        ]

    # ----------------------------------------------------------------------------------
    # MAIN MENU
    # ----------------------------------------------------------------------------------

    async def async_step_init(self, user_input=None):
        """Display the main menu for the Options Flow."""
        # Check if reload is needed from previous entity add/edit operations
        if self._reload_needed and user_input is None:
            const.LOGGER.debug("Performing deferred reload after entity changes")
            self._reload_needed = False
            # Wait briefly to ensure storage writes complete before reload
            await asyncio.sleep(0.1)
            await self._reload_entry_after_entity_change()
            # Note: After reload, the flow might be invalidated, but that's expected
            # The user will need to reopen the options flow to see new sensors

        self._entry_options = dict(self.config_entry.options)

        if user_input is not None:
            selection = user_input[const.OPTIONS_FLOW_INPUT_MENU_SELECTION]

            if selection == const.OPTIONS_FLOW_POINTS:
                return await self.async_step_manage_points()

            if selection == const.OPTIONS_FLOW_GENERAL_OPTIONS:
                return await self.async_step_manage_general_options()

            if selection.startswith(const.OPTIONS_FLOW_MENU_MANAGE_PREFIX):
                self._entity_type = selection.replace(
                    const.OPTIONS_FLOW_MENU_MANAGE_PREFIX, const.SENTINEL_EMPTY
                )
                return await self.async_step_manage_entity()

            if selection == const.OPTIONS_FLOW_FINISH:
                return self.async_abort(reason=const.TRANS_KEY_CFOF_SETUP_COMPLETE)

        main_menu = [
            const.OPTIONS_FLOW_POINTS,
            const.OPTIONS_FLOW_KIDS,
            const.OPTIONS_FLOW_PARENTS,
            const.OPTIONS_FLOW_CHORES,
            const.OPTIONS_FLOW_BADGES,
            const.OPTIONS_FLOW_REWARDS,
            const.OPTIONS_FLOW_BONUSES,
            const.OPTIONS_FLOW_PENALTIES,
            const.OPTIONS_FLOW_ACHIEVEMENTS,
            const.OPTIONS_FLOW_CHALLENGES,
            const.OPTIONS_FLOW_GENERAL_OPTIONS,
            const.OPTIONS_FLOW_FINISH,
        ]

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_INIT,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.OPTIONS_FLOW_INPUT_MENU_SELECTION
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=main_menu,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_MAIN_MENU,
                        )
                    )
                }
            ),
        )

    async def async_step_manage_points(self, user_input=None):
        """Let user edit the points label/icon after initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_points_inputs(user_input)

            if not errors:
                # Build points configuration
                points_data = fh.build_points_data(user_input)

                # Update options
                self._entry_options = dict(self.config_entry.options)
                self._entry_options.update(points_data)
                const.LOGGER.debug(
                    "Configured points with name %s and icon %s",
                    points_data[const.CONF_POINTS_LABEL],
                    points_data[const.CONF_POINTS_ICON],
                )
                await self._update_system_settings_and_reload()

                return await self.async_step_init()

        # Get existing values from entry options
        current_label = self._entry_options.get(
            const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
        )
        current_icon = self._entry_options.get(
            const.CONF_POINTS_ICON, const.DEFAULT_POINTS_ICON
        )

        # Build the form
        points_schema = fh.build_points_schema(
            default_label=current_label, default_icon=current_icon
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_MANAGE_POINTS,
            data_schema=points_schema,
            description_placeholders={},
        )

    async def async_step_manage_entity(self, user_input=None):
        """Handle the management actions for a selected entity type.

        Presents add/edit/delete options for the selected entity.
        """
        if user_input is not None:
            self._action = user_input[const.OPTIONS_FLOW_INPUT_MANAGE_ACTION]
            # Route to the corresponding step based on action
            if self._action == const.OPTIONS_FLOW_ACTIONS_ADD:
                return await getattr(
                    self,
                    f"{const.OPTIONS_FLOW_ASYNC_STEP_ADD_PREFIX}{self._entity_type}",
                )()
            if self._action in [
                const.OPTIONS_FLOW_ACTIONS_EDIT,
                const.OPTIONS_FLOW_ACTIONS_DELETE,
            ]:
                return await self.async_step_select_entity()
            if self._action == const.OPTIONS_FLOW_ACTIONS_BACK:
                return await self.async_step_init()

        # Define manage action choices
        manage_action_choices = [
            const.OPTIONS_FLOW_ACTIONS_ADD,
            const.OPTIONS_FLOW_ACTIONS_EDIT,
            const.OPTIONS_FLOW_ACTIONS_DELETE,
            const.OPTIONS_FLOW_ACTIONS_BACK,  # Option to go back to the main menu
        ]

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_MANAGE_ENTITY,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.OPTIONS_FLOW_INPUT_MANAGE_ACTION
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=manage_action_choices,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_MANAGE_ACTIONS,
                        )
                    )
                }
            ),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE: self._entity_type or ""
            },
        )

    async def async_step_select_entity(self, user_input=None):
        """Select an entity (kid, chore, badge, etc.) to edit or delete based on internal_id."""
        if self._action not in [
            const.OPTIONS_FLOW_ACTIONS_EDIT,
            const.OPTIONS_FLOW_ACTIONS_DELETE,
        ]:
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACTION)

        entity_dict = self._get_entity_dict()
        entity_names = [
            data.get(
                const.OPTIONS_FLOW_DATA_ENTITY_NAME,
                const.TRANS_KEY_DISPLAY_UNKNOWN_ENTITY,
            )
            for data in entity_dict.values()
        ]

        if user_input is not None:
            selected_name = _ensure_str(
                user_input[const.OPTIONS_FLOW_INPUT_ENTITY_NAME]
            )
            internal_id = next(
                (
                    eid
                    for eid, data in entity_dict.items()
                    if data[const.OPTIONS_FLOW_DATA_ENTITY_NAME] == selected_name
                ),
                None,
            )
            if not internal_id:
                const.LOGGER.error("Selected entity '%s' not found", selected_name)
                return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ENTITY)

            # Store internal_id in context for later use
            cast("dict[str, Any]", self.context)[
                const.OPTIONS_FLOW_INPUT_INTERNAL_ID
            ] = internal_id

            # Route based on action
            if self._action == const.OPTIONS_FLOW_ACTIONS_EDIT:
                # Intercept for badges to route to the correct edit function
                if self._entity_type == const.OPTIONS_FLOW_DIC_BADGE:
                    badge_data = entity_dict[internal_id]
                    badge_type = badge_data.get(const.DATA_BADGE_TYPE)

                    # Route to the correct edit function based on badge type
                    if badge_type == const.BADGE_TYPE_CUMULATIVE:
                        return await self.async_step_edit_badge_cumulative(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_DAILY:
                        return await self.async_step_edit_badge_daily(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_PERIODIC:
                        return await self.async_step_edit_badge_periodic(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_ACHIEVEMENT_LINKED:
                        return await self.async_step_edit_badge_achievement(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_CHALLENGE_LINKED:
                        return await self.async_step_edit_badge_challenge(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_SPECIAL_OCCASION:
                        return await self.async_step_edit_badge_special(
                            default_data=badge_data
                        )
                    const.LOGGER.error(
                        "Unknown badge type '%s' for badge ID '%s'",
                        badge_type,
                        internal_id,
                    )
                    return self.async_abort(
                        reason=const.TRANS_KEY_CFOF_INVALID_BADGE_TYPE
                    )
                # For other entity types, route to their specific edit step
                return await getattr(
                    self,
                    f"async_step_edit_{self._entity_type}",
                )()

            if self._action == const.OPTIONS_FLOW_ACTIONS_DELETE:
                # Route to the delete step for the selected entity type
                return await getattr(
                    self,
                    f"async_step_delete_{self._entity_type}",
                )()

        if not entity_names:
            return self.async_abort(
                reason=const.TRANS_KEY_CFOF_NO_ENTITY_TYPE.format(self._entity_type)
            )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_SELECT_ENTITY,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.OPTIONS_FLOW_INPUT_ENTITY_NAME
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=entity_names,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    )
                }
            ),
            description_placeholders=cast(
                "dict[str, str]",
                {
                    const.OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE: self._entity_type,
                    const.OPTIONS_FLOW_PLACEHOLDER_ACTION: self._action,
                },
            ),
        )

    def _get_entity_dict(self):
        """Retrieve appropriate entity dict based on entity_type."""
        coordinator = self._get_coordinator()

        entity_type_to_data = {
            const.OPTIONS_FLOW_DIC_KID: const.DATA_KIDS,
            const.OPTIONS_FLOW_DIC_PARENT: const.DATA_PARENTS,
            const.OPTIONS_FLOW_DIC_CHORE: const.DATA_CHORES,
            const.OPTIONS_FLOW_DIC_BADGE: const.DATA_BADGES,
            const.OPTIONS_FLOW_DIC_REWARD: const.DATA_REWARDS,
            const.OPTIONS_FLOW_DIC_BONUS: const.DATA_BONUSES,
            const.OPTIONS_FLOW_DIC_PENALTY: const.DATA_PENALTIES,
            const.OPTIONS_FLOW_DIC_ACHIEVEMENT: const.DATA_ACHIEVEMENTS,
            const.OPTIONS_FLOW_DIC_CHALLENGE: const.DATA_CHALLENGES,
        }
        key = entity_type_to_data.get(self._entity_type or "", "")
        if not key:
            const.LOGGER.error(
                "Unknown entity type '%s'. Cannot retrieve entity dictionary",
                self._entity_type,
            )
            return {}
        return coordinator.data.get(key, {})

    # ----------------------------------------------------------------------------------
    # KIDS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_kid(self, user_input=None):
        """Add a new kid."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        kids_dict = coordinator.kids_data

        if user_input is not None:
            # Validate inputs (check against both existing kids and parents)
            parents_dict = coordinator.parents_data
            errors = fh.validate_kids_inputs(user_input, kids_dict, parents_dict)

            if not errors:
                try:
                    # Use unified eh.build_kid() pattern
                    kid_data = eh.build_kid(user_input)
                    internal_id = kid_data[const.DATA_KID_INTERNAL_ID]
                    kid_name = kid_data[const.DATA_KID_NAME]

                    # Direct storage write (no _create_kid needed)
                    coordinator._data[const.DATA_KIDS][internal_id] = dict(kid_data)
                    coordinator._persist()
                    coordinator.async_update_listeners()

                    const.LOGGER.debug(
                        "Added Kid '%s' with ID: %s", kid_name, internal_id
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()
        schema = await fh.build_kid_schema(
            self.hass,
            users=users,
            default_kid_name=const.SENTINEL_EMPTY,
            default_ha_user_id=None,
            default_mobile_notify_service=None,
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_KID, data_schema=schema, errors=errors
        )

    # ----------------------------------------------------------------------------------
    # PARENTS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_parent(self, user_input=None):
        """Add a new parent."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        parents_dict = coordinator.parents_data

        if user_input is not None:
            # Validate inputs (check against both existing parents and kids)
            kids_dict = coordinator.kids_data
            errors = fh.validate_parents_inputs(user_input, parents_dict, kids_dict)

            if not errors:
                try:
                    # Use unified eh.build_parent() pattern
                    parent_data = dict(eh.build_parent(user_input))
                    internal_id = str(parent_data[const.DATA_PARENT_INTERNAL_ID])
                    parent_name = str(parent_data[const.DATA_PARENT_NAME])

                    # Direct storage write
                    coordinator._data[const.DATA_PARENTS][internal_id] = parent_data

                    # Create shadow kid if chore assignment is enabled
                    if parent_data.get(const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, False):
                        # Build shadow kid input from parent data
                        shadow_input = {
                            const.CFOF_KIDS_INPUT_KID_NAME: parent_name,
                            const.CFOF_KIDS_INPUT_HA_USER: parent_data.get(
                                const.DATA_PARENT_HA_USER_ID, ""
                            ),
                            const.CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE: parent_data.get(
                                const.DATA_PARENT_DASHBOARD_LANGUAGE,
                                const.DEFAULT_DASHBOARD_LANGUAGE,
                            ),
                            const.CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE: const.SENTINEL_EMPTY,
                        }
                        shadow_kid_data = dict(
                            eh.build_kid(
                                shadow_input,
                                is_shadow=True,
                                linked_parent_id=internal_id,
                            )
                        )
                        shadow_kid_id = str(shadow_kid_data[const.DATA_KID_INTERNAL_ID])

                        # Direct storage write for shadow kid
                        coordinator._data[const.DATA_KIDS][shadow_kid_id] = (
                            shadow_kid_data
                        )

                        # Link shadow kid to parent
                        coordinator._data[const.DATA_PARENTS][internal_id][
                            const.DATA_PARENT_LINKED_SHADOW_KID_ID
                        ] = shadow_kid_id

                        const.LOGGER.info(
                            "Created shadow kid '%s' (ID: %s) for parent '%s' (ID: %s)",
                            parent_name,
                            shadow_kid_id,
                            parent_name,
                            internal_id,
                        )

                    coordinator._persist()
                    coordinator.async_update_listeners()
                    self._mark_reload_needed()

                    const.LOGGER.debug(
                        "Added Parent '%s' with ID: %s", parent_name, internal_id
                    )
                    return await self.async_step_init()

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

        # Retrieve HA users and existing kids for linking
        users = await self.hass.auth.async_get_users()
        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }

        parent_schema = await fh.build_parent_schema(
            self.hass,
            users=users,
            kids_dict=kids_dict,
            default_parent_name=const.SENTINEL_EMPTY,
            default_ha_user_id=None,
            default_associated_kids=[],
            default_mobile_notify_service=None,
            default_dashboard_language=None,
            default_allow_chore_assignment=False,
            default_enable_chore_workflow=False,
            default_enable_gamification=False,
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_PARENT,
            data_schema=parent_schema,
            errors=errors,
        )

    # ----------------------------------------------------------------------------------
    # CHORES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_chore(self, user_input=None):
        """Add a new chore."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        chores_dict = coordinator.chores_data

        if user_input is not None:
            # Build kids_dict for name→UUID conversion
            kids_dict = {
                data[const.DATA_KID_NAME]: eid
                for eid, data in coordinator.kids_data.items()
            }

            # Build and validate chore data
            chore_data, errors = fh.build_chores_data(
                user_input, kids_dict, chores_dict
            )

            if errors:
                schema = fh.build_chore_schema(kids_dict, default=user_input)
                return self.async_show_form(
                    step_id=const.OPTIONS_FLOW_STEP_ADD_CHORE,
                    data_schema=schema,
                    errors=errors,
                )

            # Get internal_id and the chore data dict
            internal_id = list(chore_data.keys())[0]
            new_chore_data = chore_data[internal_id]
            chore_name = new_chore_data[const.DATA_CHORE_NAME]
            due_date_str = new_chore_data[const.DATA_CHORE_DUE_DATE]

            # Get completion criteria and assigned kids for routing logic
            completion_criteria = new_chore_data.get(
                const.DATA_CHORE_COMPLETION_CRITERIA
            )
            assigned_kids = new_chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            recurring_frequency = new_chore_data.get(
                const.DATA_CHORE_RECURRING_FREQUENCY
            )

            # For INDEPENDENT chores with assigned kids, handle per-kid details
            # (mirrors edit_chore logic for consistency)
            if (
                completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
                and assigned_kids
            ):
                # Capture template values from user input before they're cleared
                clear_due_date = user_input.get(
                    const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE, False
                )
                raw_template_date = (
                    None
                    if clear_due_date
                    else user_input.get(const.CFOF_CHORES_INPUT_DUE_DATE)
                )
                template_applicable_days = user_input.get(
                    const.CFOF_CHORES_INPUT_APPLICABLE_DAYS, []
                )
                template_daily_multi_times = user_input.get(
                    const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES, ""
                )

                # Single kid optimization: apply values directly, skip helper
                if len(assigned_kids) == 1:
                    kid_id = assigned_kids[0]
                    per_kid_due_dates: dict[str, str | None] = {}

                    if clear_due_date:
                        per_kid_due_dates[kid_id] = None
                    elif raw_template_date:
                        try:
                            utc_dt = kh.dt_parse(
                                raw_template_date,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                per_kid_due_dates[kid_id] = utc_dt.isoformat()
                        except ValueError as e:
                            const.LOGGER.warning(
                                "Failed to parse date for single kid: %s", e
                            )

                    if per_kid_due_dates:
                        new_chore_data[const.DATA_CHORE_PER_KID_DUE_DATES] = (
                            per_kid_due_dates
                        )

                    # Apply template applicable_days to single kid
                    if template_applicable_days:
                        weekday_keys = list(const.WEEKDAY_OPTIONS.keys())
                        days_as_strings = [
                            d for d in template_applicable_days if d in weekday_keys
                        ]
                        new_chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
                            kid_id: days_as_strings
                        }
                        new_chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None

                    # Apply daily_multi_times to single kid (if DAILY_MULTI)
                    if (
                        recurring_frequency == const.FREQUENCY_DAILY_MULTI
                        and template_daily_multi_times
                    ):
                        new_chore_data[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = {
                            kid_id: template_daily_multi_times
                        }
                        new_chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

                    # Create chore using entity_helpers (direct storage pattern)
                    chore_entity = eh.build_chore(new_chore_data)
                    coordinator._data[const.DATA_CHORES][internal_id] = chore_entity
                    coordinator._persist()
                    coordinator.async_update_listeners()

                    # CFE-2026-001 FIX: Single-kid DAILY_MULTI without times
                    # needs to route to times helper (main form doesn't have times field)
                    if (
                        recurring_frequency == const.FREQUENCY_DAILY_MULTI
                        and not template_daily_multi_times
                    ):
                        self._chore_being_edited = new_chore_data
                        new_chore_data[const.DATA_INTERNAL_ID] = internal_id
                        const.LOGGER.debug(
                            "Added single-kid INDEPENDENT DAILY_MULTI Chore '%s' "
                            "- routing to times helper",
                            chore_name,
                        )
                        return await self.async_step_chores_daily_multi()

                    const.LOGGER.debug(
                        "Added single-kid INDEPENDENT Chore '%s' with ID: %s",
                        chore_name,
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                # Multiple kids: create chore, then show per-kid details helper
                chore_entity = eh.build_chore(new_chore_data)
                coordinator._data[const.DATA_CHORES][internal_id] = chore_entity
                coordinator._persist()
                coordinator.async_update_listeners()

                # Store chore data and template values for helper form
                new_chore_data[const.DATA_INTERNAL_ID] = internal_id
                self._chore_being_edited = new_chore_data
                self._chore_template_date_raw = raw_template_date
                self._chore_template_applicable_days = template_applicable_days
                self._chore_template_daily_multi_times = template_daily_multi_times

                const.LOGGER.debug(
                    "Added multi-kid INDEPENDENT Chore '%s' - routing to per-kid helper",
                    chore_name,
                )
                return await self.async_step_edit_chore_per_kid_details()

            # CFE-2026-001: Check if DAILY_MULTI needs times collection
            # (non-INDEPENDENT chores with DAILY_MULTI frequency)
            if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
                # Create chore using entity_helpers (direct storage pattern)
                chore_entity = eh.build_chore(new_chore_data)
                coordinator._data[const.DATA_CHORES][internal_id] = chore_entity
                coordinator._persist()
                coordinator.async_update_listeners()

                # Store chore data for helper step
                new_chore_data[const.DATA_INTERNAL_ID] = internal_id
                self._chore_being_edited = new_chore_data

                const.LOGGER.debug(
                    "Added DAILY_MULTI Chore '%s' - routing to times helper",
                    chore_name,
                )
                return await self.async_step_chores_daily_multi()

            # Standard chore creation (SHARED/SHARED_FIRST or no special handling)
            chore_entity = eh.build_chore(new_chore_data)
            coordinator._data[const.DATA_CHORES][internal_id] = chore_entity
            coordinator._persist()
            coordinator.async_update_listeners()

            const.LOGGER.debug(
                "Added Chore '%s' with ID: %s and Due Date %s",
                chore_name,
                internal_id,
                due_date_str,
            )
            self._mark_reload_needed()
            return await self.async_step_init()

        # Use flow_helpers.build_chore_schema, passing current kids
        kids_dict = {
            data[const.DATA_KID_NAME]: eid
            for eid, data in coordinator.kids_data.items()
        }
        schema = fh.build_chore_schema(kids_dict)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_CHORE, data_schema=schema, errors=errors
        )

    # ----------------------------------------------------------------------------------
    # BADGES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_badge(self, user_input=None):
        """Entry point to add a new badge."""
        if user_input is not None:
            badge_type = user_input[const.CFOF_BADGES_INPUT_TYPE]
            cast("dict[str, Any]", self.context)[const.CFOF_BADGES_INPUT_TYPE] = (
                badge_type
            )

            # Redirect to the appropriate step based on badge type
            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                return await self.async_step_add_badge_cumulative()
            if badge_type == const.BADGE_TYPE_DAILY:
                return await self.async_step_add_badge_daily()
            if badge_type == const.BADGE_TYPE_PERIODIC:
                return await self.async_step_add_badge_periodic()
            if badge_type == const.BADGE_TYPE_ACHIEVEMENT_LINKED:
                return await self.async_step_add_badge_achievement()
            if badge_type == const.BADGE_TYPE_CHALLENGE_LINKED:
                return await self.async_step_add_badge_challenge()
            if badge_type == const.BADGE_TYPE_SPECIAL_OCCASION:
                return await self.async_step_add_badge_special()
            # Fallback to cumulative if unknown.
            return await self.async_step_add_badge_cumulative()

        badge_type_options = [
            const.BADGE_TYPE_CUMULATIVE,
            const.BADGE_TYPE_DAILY,
            const.BADGE_TYPE_PERIODIC,
            const.BADGE_TYPE_ACHIEVEMENT_LINKED,
            const.BADGE_TYPE_CHALLENGE_LINKED,
            const.BADGE_TYPE_SPECIAL_OCCASION,
        ]
        schema = vol.Schema(
            {
                vol.Required(const.CFOF_BADGES_INPUT_TYPE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=badge_type_options,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_TYPE,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_BADGE, data_schema=schema
        )

    # ----- Add Achievement-Linked Badge -----
    async def async_step_add_badge_achievement(self, user_input=None):
        """Handle adding an achievement-linked badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for achievement-linked badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_ACHIEVEMENT_LINKED,
            is_edit=False,
        )

    # ----- Add Challenge-Linked Badge -----
    async def async_step_add_badge_challenge(self, user_input=None):
        """Handle adding a challenge-linked badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for challenge-linked badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CHALLENGE_LINKED,
            is_edit=False,
        )

    # ----- Add Cumulative Badge (Points-only) -----
    async def async_step_add_badge_cumulative(self, user_input=None):
        """Handle adding a cumulative badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for cumulative badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CUMULATIVE,
            is_edit=False,
        )

    # ----- Add Daily Badge -----
    async def async_step_add_badge_daily(self, user_input=None):
        """Handle adding a daily badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for daily badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_DAILY,
            is_edit=False,
        )

    # ----- Add Periodic Badge -----
    async def async_step_add_badge_periodic(self, user_input=None):
        """Handle adding a periodic badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for periodic badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_PERIODIC,
            is_edit=False,
        )

    # ----- Add Special Occasion Badge -----
    async def async_step_add_badge_special(self, user_input=None):
        """Handle adding a special occasion badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for special occasion badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_SPECIAL_OCCASION,
            is_edit=False,
        )

    # ----- Add Badge Centralized Function for All Types -----
    async def async_add_edit_badge_common(
        self,
        user_input: dict[str, Any] | None = None,
        badge_type: str = const.BADGE_TYPE_CUMULATIVE,
        default_data: dict[str, Any] | None = None,
        is_edit: bool = False,
    ):
        """Handle adding or editing a badge."""
        coordinator = self._get_coordinator()
        badges_dict = coordinator.badges_data
        chores_dict = coordinator.chores_data
        kids_dict = coordinator.kids_data
        rewards_dict = coordinator.rewards_data
        achievements_dict = coordinator.achievements_data
        challenges_dict = coordinator.challenges_data
        bonuses_dict = coordinator.bonuses_data
        penalties_dict = coordinator.penalties_data

        errors: dict[str, str] = {}

        # Determine internal_id (UUID-based primary key, persists across renames)
        if is_edit:
            # Edit mode: retrieve internal_id from context (set when user selected badge to edit)
            # Cast from context dict which returns object type
            internal_id: str | None = cast(
                "str | None", self.context.get(const.CFOF_GLOBAL_INPUT_INTERNAL_ID)
            )
            # Validate that the badge still exists (defensive: could have been deleted by another process)
            if not internal_id or internal_id not in badges_dict:
                const.LOGGER.error("Invalid Internal ID for editing badge.")
                return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE)
        else:
            # Add mode: generate new UUID and store in context for form resubmissions
            # Context persists across form validation errors (same internal_id on retry)
            internal_id = str(uuid.uuid4())
            # Cast context to dict[str, Any] since HA's ConfigFlowContext doesn't allow arbitrary keys
            # but we need to store internal_id for form resubmission across validation errors
            cast("dict[str, Any]", self.context)[
                const.CFOF_GLOBAL_INPUT_INTERNAL_ID
            ] = internal_id

        if user_input is not None:
            # --- Validate Inputs ---
            # Badge validation is complex: checks name uniqueness, reward/bonus/penalty
            # existence, and type-specific rules (e.g., periodic requires repeat_interval)
            errors = fh.validate_badge_common_inputs(
                user_input=user_input,
                internal_id=internal_id,
                existing_badges=badges_dict,
                rewards_dict=rewards_dict,
                bonuses_dict=bonuses_dict,
                penalties_dict=penalties_dict,
                badge_type=badge_type,
            )

            badge_dict: BadgeData | None = None
            if not errors:
                # --- Build Data using entity_helpers (modern pattern) ---
                try:
                    if is_edit:
                        existing_badge = badges_dict.get(internal_id)
                        badge_dict = eh.build_badge(
                            user_input,
                            existing=existing_badge,
                            badge_type=badge_type,
                        )
                    else:
                        badge_dict = eh.build_badge(
                            user_input,
                            badge_type=badge_type,
                        )
                        # Override internal_id with the one from context
                        badge_dict[const.DATA_BADGE_INTERNAL_ID] = internal_id
                except eh.EntityValidationError as err:
                    errors[err.field] = err.translation_key
                    badge_dict = None

            if not errors and badge_dict is not None:
                # --- Save Data (direct storage write) ---
                if is_edit:
                    # Edit: update existing badge
                    coordinator._data[const.DATA_BADGES][internal_id] = dict(badge_dict)
                    # Phase 4: Sync badge_progress after badge update
                    for kid_id in coordinator.kids_data:
                        coordinator._sync_badge_progress_for_kid(kid_id)
                    coordinator._recalculate_all_badges()
                    coordinator._persist()
                    coordinator.async_update_listeners()
                else:
                    # Add: create new badge + persist + notify listeners
                    coordinator._data.setdefault(const.DATA_BADGES, {})[internal_id] = (
                        dict(badge_dict)
                    )
                    # Sync badge progress for all kids (creates progress sensors)
                    for kid_id in coordinator.kids_data:
                        coordinator._sync_badge_progress_for_kid(kid_id)
                    # Recalculate badges to trigger initial evaluation
                    coordinator._recalculate_all_badges()
                    coordinator._persist()
                    coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "%s Badge '%s' with ID: %s. Data: %s",
                    "Updated" if is_edit else "Added",
                    badge_dict[const.DATA_BADGE_NAME],
                    internal_id,
                    badge_dict,
                )

                self._mark_reload_needed()
                return await self.async_step_init()

        # --- Build Schema ---
        badge_schema_data = user_input if user_input else default_data or {}
        schema_fields = fh.build_badge_common_schema(
            default=badge_schema_data,
            kids_dict=kids_dict,
            chores_dict=chores_dict,
            rewards_dict=rewards_dict,
            achievements_dict=achievements_dict,
            challenges_dict=challenges_dict,
            bonuses_dict=bonuses_dict,
            penalties_dict=penalties_dict,
            badge_type=badge_type,
        )
        data_schema = vol.Schema(schema_fields)

        # Determine step name dynamically
        step_name = (
            const.OPTIONS_FLOW_EDIT_STEP.get(badge_type)
            if is_edit
            else const.OPTIONS_FLOW_ADD_STEP.get(badge_type)
        )
        if not step_name:
            const.LOGGER.error("Invalid badge type '%s'.", badge_type)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE_TYPE)

        return self.async_show_form(
            step_id=step_name,
            data_schema=data_schema,
            errors=errors,
            description_placeholders=None,
            last_step=False,
        )

    # ----------------------------------------------------------------------------------
    # REWARDS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_reward(self, user_input=None):
        """Add a new reward."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        rewards_dict = coordinator.rewards_data

        if user_input is not None:
            # Layer 2: UI validation (uniqueness check)
            errors = fh.validate_rewards_inputs(user_input, rewards_dict)

            if not errors:
                try:
                    # Layer 3: Entity helper builds complete structure
                    # Convert CFOF_* form keys to DATA_* keys, then build reward
                    data_input = eh.map_cfof_to_reward_data(user_input)
                    reward_data = eh.build_reward(data_input)
                    internal_id = reward_data[const.DATA_REWARD_INTERNAL_ID]

                    # Layer 4: Coordinator stores (thin wrapper)
                    coordinator._data[const.DATA_REWARDS][internal_id] = dict(
                        reward_data
                    )
                    coordinator._persist()
                    coordinator.async_update_listeners()

                    const.LOGGER.debug(
                        "Added Reward '%s' with ID: %s",
                        reward_data[const.DATA_REWARD_NAME],
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    # Map field-specific error for form highlighting
                    errors[err.field] = err.translation_key

        schema = fh.build_reward_schema()
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_REWARD,
            data_schema=schema,
            errors=errors,
        )

    # ----------------------------------------------------------------------------------
    # BONUSES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_bonus(self, user_input=None):
        """Add a new bonus."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        bonuses_dict = coordinator.bonuses_data

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_bonuses_inputs(user_input, bonuses_dict)

            if not errors:
                # Transform form input keys to DATA_* keys
                transformed_input = {
                    const.DATA_BONUS_NAME: user_input[const.CFOF_BONUSES_INPUT_NAME],
                    const.DATA_BONUS_DESCRIPTION: user_input.get(const.CFOF_BONUSES_INPUT_DESCRIPTION, const.SENTINEL_EMPTY),
                    const.DATA_BONUS_POINTS: user_input.get(const.CFOF_BONUSES_INPUT_POINTS, const.DEFAULT_BONUS_POINTS),
                    const.DATA_BONUS_ICON: user_input.get(const.CFOF_BONUSES_INPUT_ICON, const.DEFAULT_BONUS_ICON),
                }
                # Build bonus data using unified helper
                new_bonus_data = eh.build_bonus_or_penalty(transformed_input, "bonus")
                internal_id = new_bonus_data[const.DATA_BONUS_INTERNAL_ID]

                # Direct storage write
                coordinator._data[const.DATA_BONUSES][internal_id] = new_bonus_data
                coordinator._persist()
                coordinator.async_update_listeners()

                bonus_name = user_input[const.CFOF_BONUSES_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "Added Bonus '%s' with ID: %s", bonus_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_bonus_schema()
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_BONUS, data_schema=schema, errors=errors
        )

    # ----------------------------------------------------------------------------------
    # PENALTIES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_penalty(self, user_input=None):
        """Add a new penalty."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        penalties_dict = coordinator.penalties_data

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_penalties_inputs(user_input, penalties_dict)

            if not errors:
                # Transform form input keys to DATA_* keys
                transformed_input = {
                    const.DATA_PENALTY_NAME: user_input[const.CFOF_PENALTIES_INPUT_NAME],
                    const.DATA_PENALTY_DESCRIPTION: user_input.get(const.CFOF_PENALTIES_INPUT_DESCRIPTION, const.SENTINEL_EMPTY),
                    const.DATA_PENALTY_POINTS: user_input.get(const.CFOF_PENALTIES_INPUT_POINTS, const.DEFAULT_PENALTY_POINTS),
                    const.DATA_PENALTY_ICON: user_input.get(const.CFOF_PENALTIES_INPUT_ICON, const.DEFAULT_PENALTY_ICON),
                }
                # Build penalty data using unified helper
                new_penalty_data = eh.build_bonus_or_penalty(transformed_input, "penalty")
                internal_id = new_penalty_data[const.DATA_PENALTY_INTERNAL_ID]

                # Direct storage write
                coordinator._data[const.DATA_PENALTIES][internal_id] = new_penalty_data
                coordinator._persist()
                coordinator.async_update_listeners()

                penalty_name = user_input[const.CFOF_PENALTIES_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "Added Penalty '%s' with ID: %s", penalty_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_penalty_schema()
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_PENALTY,
            data_schema=schema,
            errors=errors,
        )

    # ----------------------------------------------------------------------------------
    # ACHIEVEMENTS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_achievement(self, user_input=None):
        """Add a new achievement."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        achievements_dict = coordinator.achievements_data
        chores_dict = coordinator.chores_data

        if user_input is not None:
            # Build kids name to ID mapping for options flow
            kids_name_to_id = {
                kid[const.DATA_KID_NAME]: kid[const.DATA_KID_INTERNAL_ID]
                for kid in coordinator.data.get(const.DATA_KIDS, {}).values()
            }

            # Build achievement data with integrated validation
            achievement_data, errors = fh.build_achievements_data(
                user_input, achievements_dict, kids_name_to_id
            )

            if not errors:
                internal_id, new_achievement_data = next(iter(achievement_data.items()))

                coordinator._create_achievement(internal_id, new_achievement_data)
                coordinator._persist()
                coordinator.async_update_listeners()

                achievement_name = user_input[
                    const.CFOF_ACHIEVEMENTS_INPUT_NAME
                ].strip()
                const.LOGGER.debug(
                    "Added Achievement '%s' with ID: %s",
                    achievement_name,
                    internal_id,
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }
        achievement_schema = fh.build_achievement_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=None
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_ACHIEVEMENT,
            data_schema=achievement_schema,
            errors=errors,
        )

    # ----------------------------------------------------------------------------------
    # CHALLENGES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_challenge(self, user_input=None):
        """Add a new challenge."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        chores_dict = coordinator.chores_data

        if user_input is not None:
            # Use helper to build and validate challenge data
            challenge_data, errors = fh.build_challenges_data(
                user_input,
                coordinator.kids_data,
                existing_challenges=coordinator.challenges_data,
                current_id=None,  # New challenge
            )

            if not errors and challenge_data:
                # Additional validation for options flow: dates must be in the future
                internal_id = list(challenge_data.keys())[0]
                start_date_str = challenge_data[internal_id][
                    const.DATA_CHALLENGE_START_DATE
                ]
                end_date_str = challenge_data[internal_id][
                    const.DATA_CHALLENGE_END_DATE
                ]

                start_dt = dt_util.parse_datetime(start_date_str)
                end_dt = dt_util.parse_datetime(end_date_str)

                if start_dt and start_dt < dt_util.utcnow():
                    errors = {
                        const.CFOP_ERROR_START_DATE: const.TRANS_KEY_CFOF_START_DATE_IN_PAST
                    }
                elif end_dt and end_dt <= dt_util.utcnow():
                    errors = {
                        const.CFOP_ERROR_END_DATE: const.TRANS_KEY_CFOF_END_DATE_IN_PAST
                    }

            if not errors and challenge_data:
                internal_id = list(challenge_data.keys())[0]
                coordinator._create_challenge(internal_id, challenge_data[internal_id])
                coordinator._persist()
                coordinator.async_update_listeners()

                challenge_name = user_input[const.CFOF_CHALLENGES_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "Added Challenge '%s' with ID: %s",
                    challenge_name,
                    internal_id,
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        kids_dict = {
            data[const.DATA_KID_NAME]: eid
            for eid, data in coordinator.kids_data.items()
        }
        challenge_schema = fh.build_challenge_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=user_input
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_CHALLENGE,
            data_schema=challenge_schema,
            errors=errors,
        )

    # ----------------------------------------------------------------------------------
    # EDIT METHODS (Cross-Entity - Keep Together)
    # ----------------------------------------------------------------------------------

    # --- Kids ---

    async def async_step_edit_kid(self, user_input=None):
        """Edit an existing kid."""
        coordinator = self._get_coordinator()

        errors: dict[str, str] = {}
        kids_dict = coordinator.kids_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in kids_dict:
            const.LOGGER.error("Edit Kid - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_KID)

        kid_data = kids_dict[internal_id]

        if user_input is not None:
            # Build temporary dict for duplicate checking (excludes current kid)
            kids_for_validation = {
                kid_id: kdata
                for kid_id, kdata in kids_dict.items()
                if kid_id != internal_id
            }

            # Layer 2: UI validation (uniqueness check)
            errors = fh.validate_kids_inputs(user_input, kids_for_validation)

            if not errors:
                try:
                    # Layer 3: Entity helper builds complete structure
                    # build_kid(user_input, existing) - with existing = update mode
                    updated_kid = eh.build_kid(user_input, existing=kid_data)

                    # Layer 4: Store updated kid (preserves internal_id)
                    coordinator._data[const.DATA_KIDS][internal_id] = dict(updated_kid)
                    coordinator._persist()
                    coordinator.async_update_listeners()

                    const.LOGGER.debug(
                        "Edited Kid '%s' with ID: %s",
                        updated_kid[const.DATA_KID_NAME],
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    # Map field-specific error for form highlighting
                    errors[err.field] = err.translation_key

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()

        # Check if this is a shadow kid to show appropriate warnings
        is_shadow_kid = kid_data.get(const.DATA_KID_IS_SHADOW, False)

        schema = await fh.build_kid_schema(
            self.hass,
            users=users,
            default_kid_name=kid_data[const.DATA_KID_NAME],
            default_ha_user_id=kid_data.get(const.DATA_KID_HA_USER_ID),
            default_mobile_notify_service=kid_data.get(
                const.DATA_KID_MOBILE_NOTIFY_SERVICE
            ),
            default_dashboard_language=kid_data.get(
                const.DATA_KID_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            ),
            default_enable_due_date_reminders=kid_data.get(
                const.DATA_KID_ENABLE_DUE_DATE_REMINDERS, True
            ),
        )

        # Use different step_id for shadow kids (shows appropriate warnings)
        if is_shadow_kid:
            return self.async_show_form(
                step_id=const.OPTIONS_FLOW_STEP_EDIT_KID_SHADOW,
                data_schema=schema,
                errors=errors,
            )

        # Regular kid (no warnings)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_KID,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_edit_kid_shadow(self, user_input=None):
        """Edit a shadow kid - delegates to edit_kid handler.

        Shadow kids use a different translation key to show warnings,
        but the processing logic is identical to regular kids.
        """
        return await self.async_step_edit_kid(user_input)

    # --- Parents ---

    async def async_step_edit_parent(self, user_input=None):
        """Edit an existing parent."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        parents_dict = coordinator.parents_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in parents_dict:
            const.LOGGER.error("Edit Parent - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PARENT)

        parent_data = parents_dict[internal_id]

        if user_input is not None:
            # Build temporary dict for duplicate checking (excludes current parent)
            parents_for_validation = {
                pid: pdata for pid, pdata in parents_dict.items() if pid != internal_id
            }

            # Layer 2: UI validation (uniqueness check)
            errors = fh.validate_parents_inputs(user_input, parents_for_validation)

            # Additional validation: when enabling chore assignment, check shadow kid name conflict
            allow_chore_assignment = user_input.get(
                const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT, False
            )
            was_enabled = parent_data.get(
                const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, False
            )

            if not errors and allow_chore_assignment and not was_enabled:
                # Only check when ENABLING chore assignment (not already enabled)
                new_name = user_input.get(const.CFOF_PARENTS_INPUT_NAME, "").strip()
                existing_kid_names = {
                    data.get(const.DATA_KID_NAME, "").lower()
                    for data in coordinator.kids_data.values()
                    # Exclude shadow kids - they'll be replaced anyway
                    if not data.get(const.DATA_KID_IS_SHADOW, False)
                }
                if new_name.lower() in existing_kid_names:
                    errors[const.CFOP_ERROR_PARENT_NAME] = (
                        const.TRANS_KEY_CFOF_DUPLICATE_NAME
                    )

            if not errors:
                try:
                    # Layer 3: Entity helper builds complete structure
                    # build_parent(user_input, existing) - with existing = update mode
                    updated_parent = eh.build_parent(user_input, existing=parent_data)

                    # Handle shadow kid creation/deletion based on allow_chore_assignment
                    existing_shadow_kid_id = parent_data.get(
                        const.DATA_PARENT_LINKED_SHADOW_KID_ID
                    )

                    if allow_chore_assignment and not was_enabled:
                        # Enabling chore assignment - create shadow kid
                        shadow_kid_id = coordinator._create_shadow_kid_for_parent(
                            internal_id, dict(updated_parent)
                        )
                        updated_parent[const.DATA_PARENT_LINKED_SHADOW_KID_ID] = (
                            shadow_kid_id
                        )
                    elif (
                        not allow_chore_assignment
                        and was_enabled
                        and existing_shadow_kid_id
                    ):
                        # Disabling chore assignment - unlink shadow kid (preserves data)
                        coordinator._unlink_shadow_kid(existing_shadow_kid_id)
                        updated_parent[const.DATA_PARENT_LINKED_SHADOW_KID_ID] = None

                    # Layer 4: Store updated parent (preserves internal_id)
                    coordinator._data[const.DATA_PARENTS][internal_id] = dict(
                        updated_parent
                    )
                    coordinator._persist()
                    coordinator.async_update_listeners()

                    const.LOGGER.debug(
                        "Edited Parent '%s' with ID: %s",
                        updated_parent[const.DATA_PARENT_NAME],
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    # Map field-specific error for form highlighting
                    errors[err.field] = err.translation_key

        # Retrieve HA users and existing kids for linking
        users = await self.hass.auth.async_get_users()
        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }

        parent_schema = await fh.build_parent_schema(
            self.hass,
            users=users,
            kids_dict=kids_dict,
            default_parent_name=parent_data[const.DATA_PARENT_NAME],
            default_ha_user_id=parent_data.get(const.DATA_PARENT_HA_USER_ID),
            default_associated_kids=parent_data.get(
                const.DATA_PARENT_ASSOCIATED_KIDS, []
            ),
            default_mobile_notify_service=parent_data.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE
            ),
            default_dashboard_language=parent_data.get(
                const.DATA_PARENT_DASHBOARD_LANGUAGE
            ),
            default_allow_chore_assignment=parent_data.get(
                const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, False
            ),
            default_enable_chore_workflow=parent_data.get(
                const.DATA_PARENT_ENABLE_CHORE_WORKFLOW, False
            ),
            default_enable_gamification=parent_data.get(
                const.DATA_PARENT_ENABLE_GAMIFICATION, False
            ),
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_PARENT,
            data_schema=parent_schema,
            errors=errors,
        )

    # --- Chores ---

    async def async_step_edit_chore(self, user_input=None):
        """Edit an existing chore."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        chores_dict = coordinator.chores_data
        internal_id = cast("str | None", self.context.get(const.DATA_INTERNAL_ID))

        if not internal_id or internal_id not in chores_dict:
            const.LOGGER.error("Edit Chore - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHORE)

        chore_data = chores_dict[internal_id]

        if user_input is not None:
            # Build kids_dict for name→UUID conversion
            kids_dict = {
                data[const.DATA_KID_NAME]: eid
                for eid, data in coordinator.kids_data.items()
            }

            # Add internal_id for validation
            # (to exclude current chore from duplicate check)
            user_input[const.CFOF_GLOBAL_INPUT_INTERNAL_ID] = internal_id

            # Build a temporary dict for duplicate checking that excludes current chore
            chores_for_validation = {
                cid: cdata for cid, cdata in chores_dict.items() if cid != internal_id
            }

            # Get existing per-kid due dates to preserve during edit
            existing_per_kid_due_dates = chore_data.get(
                const.DATA_CHORE_PER_KID_DUE_DATES, {}
            )

            # Build and validate chore data using helper function
            # Pass existing per-kid dates to preserve them for INDEPENDENT chores
            chore_data_dict, errors = fh.build_chores_data(
                user_input,
                kids_dict,
                chores_for_validation,
                existing_per_kid_due_dates,
            )

            # Extract chore data (must be before error check to avoid E0606)
            updated_chore_data = chore_data_dict.get(internal_id, {})

            if errors:
                default_data = user_input.copy()
                return self.async_show_form(
                    step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE,
                    data_schema=fh.build_chore_schema(
                        kids_dict, default={**chore_data, **default_data}
                    ),
                    errors=errors,
                )

            # Check if assigned kids changed (for reload decision)
            old_assigned = set(chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []))
            new_assigned = set(
                updated_chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            )
            assignments_changed = old_assigned != new_assigned

            # Update chore using entity_helpers (direct storage pattern)
            # build_chore() merges updated_chore_data with existing chore_data
            merged_chore = eh.build_chore(updated_chore_data, existing=chore_data)
            coordinator._data[const.DATA_CHORES][internal_id] = merged_chore
            # Recalculate badges affected by chore changes
            coordinator._recalculate_all_badges()
            coordinator._persist()
            coordinator.async_update_listeners()
            # Clean up any orphaned kid-chore entities after assignment changes
            coordinator.hass.async_create_task(
                coordinator._remove_orphaned_kid_chore_entities()
            )

            new_name = merged_chore.get(
                const.DATA_CHORE_NAME,
                chore_data.get(const.DATA_CHORE_NAME),
            )
            const.LOGGER.debug("Edited Chore '%s' with ID: %s", new_name, internal_id)

            # Only reload if assignments changed (entities added/removed)
            if assignments_changed:
                const.LOGGER.debug("Chore assignments changed, marking reload needed")
                self._mark_reload_needed()

            # For INDEPENDENT chores with assigned kids, handle per-kid date editing
            completion_criteria = updated_chore_data.get(
                const.DATA_CHORE_COMPLETION_CRITERIA
            )
            assigned_kids = updated_chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if (
                completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
                and assigned_kids
            ):
                # Check if user explicitly cleared the date via checkbox
                clear_due_date = user_input.get(
                    const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE, False
                )

                # Capture the raw user-entered date BEFORE build_chores_data clears it
                # (build_chores_data sets due_date to None for INDEPENDENT chores)
                # If clear checkbox is selected, don't pass template date to helper
                raw_template_date = (
                    None
                    if clear_due_date
                    else user_input.get(const.CFOF_CHORES_INPUT_DUE_DATE)
                )

                # PKAD-2026-001: Capture template applicable_days and daily_multi_times
                template_applicable_days = user_input.get(
                    const.CFOF_CHORES_INPUT_APPLICABLE_DAYS, []
                )
                template_daily_multi_times = user_input.get(
                    const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES, ""
                )

                # Single kid optimization: skip per-kid popup if only one kid
                if len(assigned_kids) == 1:
                    kid_id = assigned_kids[0]
                    per_kid_due_dates = updated_chore_data.get(
                        const.DATA_CHORE_PER_KID_DUE_DATES, {}
                    )

                    if clear_due_date:
                        # User explicitly cleared the date
                        per_kid_due_dates[kid_id] = None
                        const.LOGGER.debug(
                            "Single kid INDEPENDENT chore: cleared due date for %s",
                            kid_id,
                        )
                    elif raw_template_date:
                        # User set a date - apply it directly to the single kid
                        try:
                            utc_dt = kh.dt_parse(
                                raw_template_date,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                per_kid_due_dates[kid_id] = utc_dt.isoformat()
                                const.LOGGER.debug(
                                    "Single kid INDEPENDENT chore: applied date %s directly to %s",
                                    utc_dt.isoformat(),
                                    kid_id,
                                )
                        except ValueError as e:
                            const.LOGGER.warning(
                                "Failed to parse date for single kid: %s", e
                            )
                    # else: date was blank, preserve existing per-kid date (already done)

                    # Update per_kid_due_dates in chore data (single source of truth)
                    updated_chore_data[const.DATA_CHORE_PER_KID_DUE_DATES] = (
                        per_kid_due_dates
                    )

                    # PKAD-2026-001: Apply template applicable_days to single kid
                    if template_applicable_days:
                        weekday_keys = list(const.WEEKDAY_OPTIONS.keys())
                        days_as_ints = [
                            weekday_keys.index(d)
                            for d in template_applicable_days
                            if d in weekday_keys
                        ]
                        updated_chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
                            kid_id: days_as_ints
                        }
                        # Clear chore-level (per-kid is now source of truth)
                        updated_chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None

                    # PKAD-2026-001: Apply daily_multi_times to single kid (if DAILY_MULTI)
                    recurring_freq = updated_chore_data.get(
                        const.DATA_CHORE_RECURRING_FREQUENCY
                    )
                    if (
                        recurring_freq == const.FREQUENCY_DAILY_MULTI
                        and template_daily_multi_times
                    ):
                        updated_chore_data[
                            const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES
                        ] = {kid_id: template_daily_multi_times}
                        # Clear chore-level (per-kid is now source of truth)
                        updated_chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

                    # Update storage using entity_helpers (direct storage pattern)
                    merged_chore = eh.build_chore(
                        updated_chore_data, existing=chore_data
                    )
                    coordinator._data[const.DATA_CHORES][internal_id] = merged_chore
                    coordinator._recalculate_all_badges()
                    coordinator._persist()
                    coordinator.async_update_listeners()
                    coordinator.hass.async_create_task(
                        coordinator._remove_orphaned_kid_chore_entities()
                    )

                    # CFE-2026-001 FIX: Single-kid DAILY_MULTI without times
                    # needs to route to times helper (check per-kid times too)
                    existing_per_kid_times = updated_chore_data.get(
                        const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {}
                    )
                    kid_has_times = existing_per_kid_times.get(kid_id)
                    if (
                        recurring_freq == const.FREQUENCY_DAILY_MULTI
                        and not template_daily_multi_times
                        and not kid_has_times
                    ):
                        updated_chore_data[const.DATA_INTERNAL_ID] = internal_id
                        self._chore_being_edited = updated_chore_data
                        const.LOGGER.debug(
                            "Edited single-kid INDEPENDENT chore to DAILY_MULTI "
                            "- routing to times helper"
                        )
                        return await self.async_step_chores_daily_multi()

                    self._mark_reload_needed()
                    return await self.async_step_init()

                # Multiple kids: show unified per-kid details step (PKAD-2026-001)
                # Store chore data AND template values for the helper form
                self._chore_being_edited = updated_chore_data
                # Type guard: updated_chore_data is always dict from chore_data_dict.get()
                assert self._chore_being_edited is not None
                self._chore_being_edited[const.DATA_INTERNAL_ID] = internal_id
                # Store template values (cleared by build_chores_data for INDEPENDENT)
                self._chore_template_date_raw = raw_template_date
                self._chore_template_applicable_days = template_applicable_days
                self._chore_template_daily_multi_times = template_daily_multi_times
                return await self.async_step_edit_chore_per_kid_details()

            # CFE-2026-001: Check if DAILY_MULTI needs times collection/update
            recurring_frequency = updated_chore_data.get(
                const.DATA_CHORE_RECURRING_FREQUENCY
            )
            existing_times = updated_chore_data.get(
                const.DATA_CHORE_DAILY_MULTI_TIMES, ""
            )
            if (
                recurring_frequency == const.FREQUENCY_DAILY_MULTI
                and not existing_times
            ):
                # DAILY_MULTI selected but no times yet - route to helper
                # Update using entity_helpers (direct storage pattern)
                merged_chore = eh.build_chore(updated_chore_data, existing=chore_data)
                coordinator._data[const.DATA_CHORES][internal_id] = merged_chore
                coordinator._recalculate_all_badges()
                coordinator._persist()
                coordinator.async_update_listeners()
                coordinator.hass.async_create_task(
                    coordinator._remove_orphaned_kid_chore_entities()
                )

                updated_chore_data[const.DATA_INTERNAL_ID] = internal_id
                self._chore_being_edited = updated_chore_data

                const.LOGGER.debug(
                    "Edited chore to DAILY_MULTI - routing to times helper"
                )
                return await self.async_step_chores_daily_multi()

            return await self.async_step_init()

        # Use flow_helpers.fh.build_chore_schema, passing current kids
        kids_dict = {
            data[const.DATA_KID_NAME]: eid
            for eid, data in coordinator.kids_data.items()
        }

        # Create reverse mapping from internal_id to name
        id_to_name = {
            eid: data[const.DATA_KID_NAME]
            for eid, data in coordinator.kids_data.items()
        }

        # Convert stored string to datetime for DateTimeSelector
        existing_due_str = chore_data.get(const.DATA_CHORE_DUE_DATE)
        existing_due_date = None

        # For INDEPENDENT chores, check if all per-kid dates are the same
        # If they differ, show blank (None) since the per-kid dates take precedence
        completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        per_kid_due_dates = chore_data.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        assigned_kids_ids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        if (
            completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            and assigned_kids_ids
        ):
            # Get all date values for assigned kids (including None)
            # Use a set to check uniqueness, treating None as a distinct value
            all_kid_dates = set()
            for kid_id in assigned_kids_ids:
                kid_date = per_kid_due_dates.get(kid_id)
                all_kid_dates.add(kid_date)

            if len(all_kid_dates) == 1:
                # All assigned kids have the same date (or all None) - show it
                common_date = next(iter(all_kid_dates))
                if common_date:  # Only show if not None
                    try:
                        existing_due_date = kh.dt_parse(
                            common_date,
                            default_tzinfo=const.DEFAULT_TIME_ZONE,
                            return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                        )
                        const.LOGGER.debug(
                            "INDEPENDENT chore: all kids have same date: %s",
                            existing_due_date,
                        )
                    except ValueError as e:
                        const.LOGGER.error(
                            "Failed to parse common per-kid date '%s': %s",
                            common_date,
                            e,
                        )
                else:
                    # All kids have None - show blank
                    const.LOGGER.debug(
                        "INDEPENDENT chore: all kids have no date, showing blank"
                    )
                    existing_due_date = None
            else:
                # Kids have different dates (including mix of dates and None) - show blank
                const.LOGGER.debug(
                    "INDEPENDENT chore: kids have different dates (%d unique), "
                    "showing blank due date field",
                    len(all_kid_dates),
                )
                existing_due_date = None
        elif existing_due_str:
            try:
                # Parse to local datetime string for DateTimeSelector
                # Storage is UTC ISO; display is local timezone
                existing_due_date = kh.dt_parse(
                    existing_due_str,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                )
                const.LOGGER.debug(
                    "Processed existing_due_date for DateTimeSelector: %s",
                    existing_due_date,
                )
            except ValueError as e:
                const.LOGGER.error(
                    "Failed to parse existing_due_date '%s': %s",
                    existing_due_str,
                    e,
                )

        # Convert assigned_kids from internal_ids to names for display
        # (assigned_kids_ids already set above for per-kid date check)
        assigned_kids_names = [
            id_to_name.get(kid_id, kid_id) for kid_id in assigned_kids_ids
        ]

        schema = fh.build_chore_schema(
            kids_dict,
            default={
                **chore_data,
                const.DATA_CHORE_DUE_DATE: existing_due_date,
                const.DATA_CHORE_ASSIGNED_KIDS: assigned_kids_names,
            },
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE,
            data_schema=schema,
            errors=errors,
        )

    # ----- Edit Per-Kid Due Dates for INDEPENDENT Chores -----
    async def async_step_edit_chore_per_kid_dates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow editing per-kid due dates for INDEPENDENT chores.

        Features:
        - Shows template date from main form (if set) with "Apply to All" option
        - Each kid's current due date shown as default (editable)
        - Supports bulk application of template date to all or selected kids
        """
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}

        # Get chore data from stored state
        chore_data = getattr(self, "_chore_being_edited", None)
        if not chore_data:
            const.LOGGER.error("Per-kid dates step called without chore data")
            return await self.async_step_init()

        internal_id = chore_data.get(const.DATA_INTERNAL_ID)
        if not internal_id:
            const.LOGGER.error("Per-kid dates step: missing internal_id")
            return await self.async_step_init()

        # Only allow for INDEPENDENT chores
        completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        if completion_criteria != const.COMPLETION_CRITERIA_INDEPENDENT:
            const.LOGGER.debug(
                "Per-kid dates step skipped - not INDEPENDENT (criteria: %s)",
                completion_criteria,
            )
            return await self.async_step_init()

        assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        if not assigned_kids:
            const.LOGGER.debug("Per-kid dates step skipped - no assigned kids")
            return await self.async_step_init()

        # Get fresh per-kid dates from storage (not from _chore_being_edited)
        stored_chore = coordinator.chores_data.get(internal_id, {})
        existing_per_kid_dates = stored_chore.get(
            const.DATA_CHORE_PER_KID_DUE_DATES, {}
        )

        # Get template date from main form (if set)
        # Use the raw template date stored before build_chores_data cleared it
        # (build_chores_data sets due_date to None for INDEPENDENT chores)
        raw_template_date = getattr(self, "_chore_template_date_raw", None)
        template_date_str = None
        template_date_display = None
        if raw_template_date:
            try:
                # Convert to UTC ISO for storage/comparison
                utc_dt = kh.dt_parse(
                    raw_template_date,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_DATETIME_UTC,
                )
                if utc_dt and isinstance(utc_dt, datetime):
                    template_date_str = utc_dt.isoformat()
                # Also get display format for UI
                template_date_display = kh.dt_parse(
                    raw_template_date,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                )
            except (ValueError, TypeError):
                pass

        # Build name-to-id mapping for assigned kids
        name_to_id: dict[str, str] = {}
        for kid_id in assigned_kids:
            kid_info = coordinator.kids_data.get(kid_id, {})
            kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
            name_to_id[kid_name] = kid_id

        if user_input is not None:
            # Check if "Apply to All" was selected
            apply_template_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, False
            )

            # Process per-kid dates from user input
            # Field keys use kid names for readability; map back to IDs for storage
            per_kid_due_dates: dict[str, str | None] = {}
            for kid_name, kid_id in name_to_id.items():
                # Check if user wants to clear this kid's date
                clear_field_name = f"clear_due_date_{kid_name}"
                clear_this_kid = user_input.get(clear_field_name, False)

                # If "Apply to All" is selected and we have a template date, use it
                if apply_template_to_all and template_date_str:
                    per_kid_due_dates[kid_id] = template_date_str
                    const.LOGGER.debug(
                        "Applied template date to %s: %s", kid_name, template_date_str
                    )
                elif clear_this_kid:
                    # User explicitly cleared this kid's date
                    per_kid_due_dates[kid_id] = None
                    const.LOGGER.debug("Cleared date for %s", kid_name)
                else:
                    # Use individual date from form
                    date_value = user_input.get(kid_name)
                    if date_value:
                        # Convert to UTC datetime, then to ISO string for storage
                        # Per quality specs: dates stored in UTC ISO format
                        try:
                            utc_dt = kh.dt_parse(
                                date_value,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                per_kid_due_dates[kid_id] = utc_dt.isoformat()
                        except ValueError as e:
                            const.LOGGER.warning("Invalid date for %s: %s", kid_name, e)
                            errors[kid_name] = const.TRANS_KEY_CFOF_INVALID_DUE_DATE

            # Validate: If ALL dates are cleared, check recurring frequency compatibility
            # Only none, daily, weekly frequencies work without due dates
            if not errors and not per_kid_due_dates:
                stored_chore = coordinator.chores_data.get(internal_id, {})
                recurring_frequency = stored_chore.get(
                    const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
                )
                if recurring_frequency not in (
                    const.FREQUENCY_NONE,
                    const.FREQUENCY_DAILY,
                    const.FREQUENCY_WEEKLY,
                ):
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_DATE_REQUIRED_FOR_FREQUENCY
                    )
                    const.LOGGER.debug(
                        "Cannot clear all dates: frequency '%s' requires due dates",
                        recurring_frequency,
                    )

            if not errors:
                # Update the chore's per_kid_due_dates in storage (single source of truth)
                chores_data = coordinator.chores_data
                if internal_id in chores_data:
                    chores_data[internal_id][const.DATA_CHORE_PER_KID_DUE_DATES] = (
                        per_kid_due_dates
                    )

                    coordinator._persist()
                    coordinator.async_update_listeners()
                    const.LOGGER.debug(
                        "Updated per-kid due dates for chore %s: %s",
                        internal_id,
                        per_kid_due_dates,
                    )

                # Clear stored state
                self._chore_being_edited = None
                self._chore_template_date_raw = None
                self._mark_reload_needed()
                return await self.async_step_init()

        # Build dynamic schema with kid names as field keys (for readable labels)
        chore_name = chore_data.get(const.DATA_CHORE_NAME, "Unknown")
        schema_fields: dict[Any, Any] = {}
        kid_names_list: list[str] = []

        # Add "Apply template to all" checkbox if template date exists
        if template_date_display:
            schema_fields[
                vol.Optional(
                    const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, default=False
                )
            ] = selector.BooleanSelector()

        for kid_name, kid_id in name_to_id.items():
            kid_names_list.append(kid_name)

            # Get existing date for this kid from storage
            existing_date = existing_per_kid_dates.get(kid_id)

            # Convert to local datetime string for DateTimeSelector display
            # Storage is UTC ISO; display is local timezone
            default_value = None
            if existing_date:
                with contextlib.suppress(ValueError, TypeError):
                    default_value = kh.dt_parse(
                        existing_date,
                        default_tzinfo=const.DEFAULT_TIME_ZONE,
                        return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                    )

            # Use kid name as field key - HA will display it as the label
            # (field keys without translations are shown as-is)
            schema_fields[vol.Optional(kid_name, default=default_value)] = vol.Any(
                None, selector.DateTimeSelector()
            )

            # Add clear checkbox for this kid if they have an existing date
            if existing_date:
                clear_field_name = f"clear_due_date_{kid_name}"
                schema_fields[
                    vol.Optional(clear_field_name, default=False, description="🗑️")
                ] = selector.BooleanSelector()

        # Build description with kid names in order
        kid_list_text = ", ".join(kid_names_list)

        # Build description placeholders
        description_placeholders = {
            "chore_name": chore_name,
            "kid_names": kid_list_text,
        }

        # Add template date info if available (shows in description)
        if template_date_display:
            description_placeholders["template_date"] = (
                f"\n\nTemplate date from main form: **{template_date_display}**. "
                "Check 'Apply template date to all kids' to use this date for everyone."
            )
        else:
            description_placeholders["template_date"] = ""

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DATES,
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    # ----- PKAD-2026-001: Unified Per-Kid Details Helper -----
    async def async_step_edit_chore_per_kid_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Unified helper: per-kid days + times + due dates with templating.

        PKAD-2026-001: Consolidates configuration for INDEPENDENT chores.

        Features:
        - Applicable days multi-select per kid (always shown for INDEPENDENT)
        - Daily multi times text input per kid (if frequency = DAILY_MULTI)
        - Due date picker per kid (existing functionality)
        - Template section with "Apply to All" buttons
        - Pre-populates from main form values
        """
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}

        # Get chore data from stored state
        chore_data = getattr(self, "_chore_being_edited", None)
        if not chore_data:
            const.LOGGER.error("Per-kid details step called without chore data")
            return await self.async_step_init()

        internal_id = chore_data.get(const.DATA_INTERNAL_ID)
        if not internal_id:
            const.LOGGER.error("Per-kid details step: missing internal_id")
            return await self.async_step_init()

        # Only for INDEPENDENT chores
        completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        if completion_criteria != const.COMPLETION_CRITERIA_INDEPENDENT:
            const.LOGGER.debug(
                "Per-kid details step skipped - not INDEPENDENT (criteria: %s)",
                completion_criteria,
            )
            return await self.async_step_init()

        assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        if not assigned_kids:
            const.LOGGER.debug("Per-kid details step skipped - no assigned kids")
            return await self.async_step_init()

        # Get frequency to determine if DAILY_MULTI times are needed
        recurring_frequency = chore_data.get(
            const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        )
        is_daily_multi = recurring_frequency == const.FREQUENCY_DAILY_MULTI

        # Get template values from stored state (set before routing here)
        template_applicable_days = getattr(self, "_chore_template_applicable_days", [])
        template_daily_multi_times = getattr(
            self, "_chore_template_daily_multi_times", ""
        )
        raw_template_date = getattr(self, "_chore_template_date_raw", None)

        # Convert template date to display format
        template_date_str = None
        template_date_display = None
        if raw_template_date:
            with contextlib.suppress(ValueError, TypeError):
                utc_dt = kh.dt_parse(
                    raw_template_date,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_DATETIME_UTC,
                )
                if utc_dt and isinstance(utc_dt, datetime):
                    template_date_str = utc_dt.isoformat()
                template_date_display = kh.dt_parse(
                    raw_template_date,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                )

        # Build name-to-id mapping for assigned kids
        name_to_id: dict[str, str] = {}
        for kid_id in assigned_kids:
            kid_info = coordinator.kids_data.get(kid_id, {})
            kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
            name_to_id[kid_name] = kid_id

        # Get existing per-kid data from storage
        stored_chore = coordinator.chores_data.get(internal_id, {})
        existing_per_kid_days = stored_chore.get(
            const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {}
        )
        existing_per_kid_times = stored_chore.get(
            const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {}
        )
        existing_per_kid_dates = stored_chore.get(
            const.DATA_CHORE_PER_KID_DUE_DATES, {}
        )

        if user_input is not None:
            # Process "Apply to All" actions
            apply_days_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL, False
            )
            apply_times_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL, False
            )
            apply_date_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, False
            )

            per_kid_applicable_days: dict[str, list[int]] = {}
            per_kid_daily_multi_times: dict[str, str] = {}
            per_kid_due_dates: dict[str, str | None] = {}

            for kid_name, kid_id in name_to_id.items():
                # Process applicable days
                if apply_days_to_all and template_applicable_days:
                    # Convert string day keys to integers for storage
                    per_kid_applicable_days[kid_id] = [
                        list(const.WEEKDAY_OPTIONS.keys()).index(d)
                        for d in template_applicable_days
                        if d in const.WEEKDAY_OPTIONS
                    ]
                else:
                    days_field = f"applicable_days_{kid_name}"
                    raw_days = user_input.get(days_field, [])
                    # Convert string day keys (mon, tue...) to integers (0-6)
                    per_kid_applicable_days[kid_id] = [
                        list(const.WEEKDAY_OPTIONS.keys()).index(d)
                        for d in raw_days
                        if d in const.WEEKDAY_OPTIONS
                    ]

                # Process daily multi times (if applicable)
                if is_daily_multi:
                    if apply_times_to_all and template_daily_multi_times:
                        per_kid_daily_multi_times[kid_id] = template_daily_multi_times
                    else:
                        times_field = f"daily_multi_times_{kid_name}"
                        per_kid_daily_multi_times[kid_id] = user_input.get(
                            times_field, ""
                        )

                # Process due dates
                clear_field_name = f"clear_due_date_{kid_name}"
                clear_this_kid = user_input.get(clear_field_name, False)

                if apply_date_to_all and template_date_str:
                    per_kid_due_dates[kid_id] = template_date_str
                elif clear_this_kid:
                    per_kid_due_dates[kid_id] = None
                else:
                    date_value = user_input.get(f"due_date_{kid_name}")
                    if date_value:
                        with contextlib.suppress(ValueError, TypeError):
                            utc_dt = kh.dt_parse(
                                date_value,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                per_kid_due_dates[kid_id] = utc_dt.isoformat()
                    else:
                        # Preserve existing date if field left blank
                        per_kid_due_dates[kid_id] = existing_per_kid_dates.get(kid_id)

            # Validate per-kid structures
            is_valid_days, days_error = fh.validate_per_kid_applicable_days(
                per_kid_applicable_days
            )
            if not is_valid_days and days_error:
                errors[const.CFOP_ERROR_BASE] = days_error

            if is_daily_multi and not errors:
                is_valid_times, times_error = fh.validate_per_kid_daily_multi_times(
                    per_kid_daily_multi_times, recurring_frequency
                )
                if not is_valid_times and times_error:
                    errors[const.CFOP_ERROR_BASE] = times_error

            if not errors:
                # Store per-kid data in chore
                chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = (
                    per_kid_applicable_days
                )
                chore_data[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

                if is_daily_multi:
                    chore_data[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = (
                        per_kid_daily_multi_times
                    )

                # PKAD-2026-001: For INDEPENDENT chores, clear chore-level fields
                # (per-kid structures are now the single source of truth)
                chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None
                chore_data[const.DATA_CHORE_DUE_DATE] = None
                if is_daily_multi:
                    chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

                # Update storage using entity_helpers (direct storage pattern)
                merged_chore = eh.build_chore(chore_data, existing=stored_chore)
                coordinator._data[const.DATA_CHORES][internal_id] = merged_chore
                coordinator._recalculate_all_badges()
                coordinator._persist()
                coordinator.async_update_listeners()
                coordinator.hass.async_create_task(
                    coordinator._remove_orphaned_kid_chore_entities()
                )

                const.LOGGER.debug(
                    "Updated per-kid details for chore %s: days=%s, dates=%s",
                    internal_id,
                    per_kid_applicable_days,
                    per_kid_due_dates,
                )

                # Clear stored state
                self._chore_being_edited = None
                self._chore_template_date_raw = None
                self._chore_template_applicable_days = None
                self._chore_template_daily_multi_times = None
                self._mark_reload_needed()
                return await self.async_step_init()

        # Build form schema
        schema_fields: dict[Any, Any] = {}
        kid_names_list: list[str] = []

        # Template section - "Apply to All" checkboxes
        if template_applicable_days:
            schema_fields[
                vol.Optional(const.CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL, default=False)
            ] = selector.BooleanSelector()

        if is_daily_multi and template_daily_multi_times:
            schema_fields[
                vol.Optional(const.CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL, default=False)
            ] = selector.BooleanSelector()

        if template_date_display:
            schema_fields[
                vol.Optional(
                    const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, default=False
                )
            ] = selector.BooleanSelector()

        # Per-kid fields
        for kid_name, kid_id in name_to_id.items():
            kid_names_list.append(kid_name)

            # Applicable days multi-select
            # Convert stored integers back to string keys for selector default
            existing_days_ints = existing_per_kid_days.get(kid_id, [])
            weekday_keys = list(const.WEEKDAY_OPTIONS.keys())
            default_days = [
                weekday_keys[i]
                for i in existing_days_ints
                if 0 <= i < len(weekday_keys)
            ]
            # If no existing per-kid days, use template
            if not default_days and template_applicable_days:
                default_days = template_applicable_days

            schema_fields[
                vol.Optional(f"applicable_days_{kid_name}", default=default_days)
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=cast(
                        "list[selector.SelectOptionDict]",
                        [
                            {"value": key, "label": f"{kid_name}: {label}"}
                            for key, label in const.WEEKDAY_OPTIONS.items()
                        ],
                    ),
                    multiple=True,
                )
            )

            # Daily multi times text input (conditional on DAILY_MULTI)
            if is_daily_multi:
                default_times = existing_per_kid_times.get(
                    kid_id, template_daily_multi_times
                )
                schema_fields[
                    vol.Optional(f"daily_multi_times_{kid_name}", default=default_times)
                ] = selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                )

            # Due date picker
            existing_date = existing_per_kid_dates.get(kid_id)
            default_date_value = None
            if existing_date:
                with contextlib.suppress(ValueError, TypeError):
                    default_date_value = kh.dt_parse(
                        existing_date,
                        default_tzinfo=const.DEFAULT_TIME_ZONE,
                        return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                    )

            schema_fields[
                vol.Optional(f"due_date_{kid_name}", default=default_date_value)
            ] = vol.Any(None, selector.DateTimeSelector())

            # Add clear checkbox if date exists
            if existing_date:
                schema_fields[
                    vol.Optional(f"clear_due_date_{kid_name}", default=False)
                ] = selector.BooleanSelector()

        # Build description placeholders
        chore_name = chore_data.get(const.DATA_CHORE_NAME, "Unknown")
        kid_list_text = ", ".join(kid_names_list)

        # Build template info section for description
        template_info_parts: list[str] = []
        if template_applicable_days:
            days_display = ", ".join(
                const.WEEKDAY_OPTIONS.get(d) or d for d in template_applicable_days
            )
            template_info_parts.append(f"**Template days:** {days_display}")
        if is_daily_multi and template_daily_multi_times:
            template_info_parts.append(
                f"**Template times:** {template_daily_multi_times}"
            )
        if template_date_display:
            template_info_parts.append(f"**Template date:** {template_date_display}")

        template_info = ""
        if template_info_parts:
            template_info = "\n\n" + "\n".join(template_info_parts)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS,
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={
                "chore_name": chore_name,
                "kid_names": kid_list_text,
                "template_info": template_info,
            },
        )

    # ----- Daily Multi Times Helper Step -----
    async def async_step_chores_daily_multi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect daily time slots for FREQUENCY_DAILY_MULTI chores.

        CFE-2026-001 Feature 2: Helper form to collect pipe-separated times.
        Pattern follows edit_chore_per_kid_dates helper.

        Features:
        - Shows chore name in title
        - Collects pipe-separated times (e.g., "08:00|17:00")
        - Validates format, count (2-6 times), and range
        - Stores validated times in chore data
        """
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}

        # Get chore data from stored state
        chore_data = getattr(self, "_chore_being_edited", None)
        if not chore_data:
            const.LOGGER.error("Daily multi times step called without chore data")
            return await self.async_step_init()

        internal_id = chore_data.get(const.DATA_INTERNAL_ID)
        if not internal_id:
            const.LOGGER.error("Daily multi times step: missing internal_id")
            return await self.async_step_init()

        chore_name = chore_data.get(const.DATA_CHORE_NAME, "Unknown")

        if user_input is not None:
            times_str = user_input.get(
                const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES, ""
            ).strip()

            # Validate the times string
            is_valid, error_key = kh.validate_daily_multi_times(times_str)

            if not is_valid and error_key:
                errors[const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES] = error_key
            else:
                # Valid - store times in chore data and persist
                chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = times_str

                # Update storage using entity_helpers (direct storage pattern)
                stored_chore = coordinator.chores_data.get(internal_id, {})
                merged_chore = eh.build_chore(chore_data, existing=stored_chore)
                coordinator._data[const.DATA_CHORES][internal_id] = merged_chore
                coordinator._recalculate_all_badges()
                coordinator._persist()
                coordinator.async_update_listeners()
                coordinator.hass.async_create_task(
                    coordinator._remove_orphaned_kid_chore_entities()
                )

                const.LOGGER.info(
                    "Set daily multi times for chore '%s': %s",
                    chore_name,
                    times_str,
                )

                self._mark_reload_needed()
                # Clear temp state
                self._chore_being_edited = None
                return await self.async_step_init()

        # Get existing times if editing
        existing_times = chore_data.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")

        # Build form schema
        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES,
                    default=existing_times,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI,
            data_schema=schema,
            errors=errors,
            description_placeholders={"chore_name": chore_name},
        )

    # ----- Edit Achievement-Linked Badge -----
    async def async_step_edit_badge_achievement(
        self, user_input=None, default_data=None
    ):
        """Handle editing an achievement-linked badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_ACHIEVEMENT_LINKED,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Challenge-Linked Badge -----
    async def async_step_edit_badge_challenge(self, user_input=None, default_data=None):
        """Handle editing a challenge-linked badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CHALLENGE_LINKED,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Cumulative Badge -----
    async def async_step_edit_badge_cumulative(
        self, user_input=None, default_data=None
    ):
        """Handle editing a cumulative badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CUMULATIVE,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Daily Badge -----
    async def async_step_edit_badge_daily(self, user_input=None, default_data=None):
        """Handle editing a daily badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_DAILY,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Periodic Badge -----
    async def async_step_edit_badge_periodic(self, user_input=None, default_data=None):
        """Handle editing a periodic badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_PERIODIC,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Special Occasion Badge -----
    async def async_step_edit_badge_special(self, user_input=None, default_data=None):
        """Handle editing a special occasion badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_SPECIAL_OCCASION,
            default_data=default_data,
            is_edit=True,
        )

    # --- Rewards ---

    async def async_step_edit_reward(self, user_input=None):
        """Edit an existing reward."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        rewards_dict = coordinator.rewards_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in rewards_dict:
            const.LOGGER.error("Edit Reward - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_REWARD)

        existing_reward = rewards_dict[internal_id]

        if user_input is not None:
            # Build a temporary dict for duplicate checking that excludes current reward
            rewards_for_validation = {
                rid: rdata for rid, rdata in rewards_dict.items() if rid != internal_id
            }

            # Layer 2: UI validation (uniqueness check)
            errors = fh.validate_rewards_inputs(user_input, rewards_for_validation)

            if not errors:
                try:
                    # Layer 3: Entity helper builds complete structure
                    # Convert CFOF_* form keys to DATA_* keys, then build reward
                    data_input = eh.map_cfof_to_reward_data(user_input)
                    updated_reward = eh.build_reward(
                        data_input, existing=existing_reward
                    )

                    # Layer 4: Store updated reward (preserves internal_id)
                    coordinator._data[const.DATA_REWARDS][internal_id] = dict(
                        updated_reward
                    )
                    coordinator._persist()
                    coordinator.async_update_listeners()

                    const.LOGGER.debug(
                        "Edited Reward '%s' with ID: %s",
                        updated_reward[const.DATA_REWARD_NAME],
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    # Map field-specific error for form highlighting
                    errors[err.field] = err.translation_key

        schema = fh.build_reward_schema(default=existing_reward)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_REWARD,
            data_schema=schema,
            errors=errors,
        )

    # --- Penalties ---

    async def async_step_edit_penalty(self, user_input=None):
        """Edit an existing penalty."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        penalties_dict = coordinator.penalties_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in penalties_dict:
            const.LOGGER.error("Edit Penalty - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PENALTY)

        penalty_data = penalties_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_PENALTIES_INPUT_NAME].strip()

            # Check for duplicate names excluding current penalty
            penalties_except_current = {
                eid: data for eid, data in penalties_dict.items() if eid != internal_id
            }
            errors = fh.validate_penalties_inputs(user_input, penalties_except_current)

            if not errors:
                # Transform form input keys to DATA_* keys
                transformed_input = {
                    const.DATA_PENALTY_NAME: user_input.get(const.CFOF_PENALTIES_INPUT_NAME, penalty_data[const.DATA_PENALTY_NAME]),
                    const.DATA_PENALTY_DESCRIPTION: user_input.get(const.CFOF_PENALTIES_INPUT_DESCRIPTION, penalty_data.get(const.DATA_PENALTY_DESCRIPTION, const.SENTINEL_EMPTY)),
                    const.DATA_PENALTY_POINTS: user_input.get(const.CFOF_PENALTIES_INPUT_POINTS, penalty_data.get(const.DATA_PENALTY_POINTS, const.DEFAULT_PENALTY_POINTS)),
                    const.DATA_PENALTY_ICON: user_input.get(const.CFOF_PENALTIES_INPUT_ICON, penalty_data.get(const.DATA_PENALTY_ICON, const.DEFAULT_PENALTY_ICON)),
                }
                # Build updated penalty data using unified helper
                updated_penalty_data = eh.build_bonus_or_penalty(
                    transformed_input, "penalty", existing=penalty_data
                )

                # Direct storage write
                coordinator._data[const.DATA_PENALTIES][internal_id] = updated_penalty_data
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "Edited Penalty '%s' with ID: %s", new_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        # Prepare data for schema (convert points to positive for display)
        display_data = dict(penalty_data)
        display_data[const.CFOF_PENALTIES_INPUT_POINTS] = abs(
            display_data[const.DATA_PENALTY_POINTS]
        )
        schema = fh.build_penalty_schema(default=display_data)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_PENALTY,
            data_schema=schema,
            errors=errors,
        )

    # --- Bonuses ---

    async def async_step_edit_bonus(self, user_input=None):
        """Edit an existing bonus."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        bonuses_dict = coordinator.bonuses_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in bonuses_dict:
            const.LOGGER.error("Edit Bonus - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BONUS)

        bonus_data = bonuses_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_BONUSES_INPUT_NAME].strip()

            # Check for duplicate names excluding current bonus
            bonuses_except_current = {
                eid: data for eid, data in bonuses_dict.items() if eid != internal_id
            }
            errors = fh.validate_bonuses_inputs(user_input, bonuses_except_current)

            if not errors:
                # Transform form input keys to DATA_* keys
                transformed_input = {
                    const.DATA_BONUS_NAME: user_input.get(const.CFOF_BONUSES_INPUT_NAME, bonus_data[const.DATA_BONUS_NAME]),
                    const.DATA_BONUS_DESCRIPTION: user_input.get(const.CFOF_BONUSES_INPUT_DESCRIPTION, bonus_data.get(const.DATA_BONUS_DESCRIPTION, const.SENTINEL_EMPTY)),
                    const.DATA_BONUS_POINTS: user_input.get(const.CFOF_BONUSES_INPUT_POINTS, bonus_data.get(const.DATA_BONUS_POINTS, const.DEFAULT_BONUS_POINTS)),
                    const.DATA_BONUS_ICON: user_input.get(const.CFOF_BONUSES_INPUT_ICON, bonus_data.get(const.DATA_BONUS_ICON, const.DEFAULT_BONUS_ICON)),
                }
                # Build updated bonus data using unified helper
                updated_bonus_data = eh.build_bonus_or_penalty(
                    transformed_input, "bonus", existing=bonus_data
                )

                # Direct storage write
                coordinator._data[const.DATA_BONUSES][internal_id] = updated_bonus_data
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "Edited Bonus '%s' with ID: %s", new_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        # Prepare data for schema (convert points to positive for display)
        display_data = dict(bonus_data)
        display_data[const.CFOF_BONUSES_INPUT_POINTS] = abs(
            display_data[const.DATA_BONUS_POINTS]
        )
        schema = fh.build_bonus_schema(default=display_data)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_BONUS,
            data_schema=schema,
            errors=errors,
        )

    # --- Achievements ---

    async def async_step_edit_achievement(self, user_input=None):
        """Edit an existing achievement."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        achievements_dict = coordinator.achievements_data

        internal_id = self.context.get(const.DATA_INTERNAL_ID)
        if not internal_id or internal_id not in achievements_dict:
            const.LOGGER.error(
                "Edit Achievement - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT)

        achievement_data = achievements_dict[internal_id]

        if user_input is not None:
            # Check for duplicate names excluding current achievement
            achievements_except_current = {
                eid: data
                for eid, data in achievements_dict.items()
                if eid != internal_id
            }

            # Build kids name to ID mapping for options flow
            kids_name_to_id = {
                kid[const.DATA_KID_NAME]: kid[const.DATA_KID_INTERNAL_ID]
                for kid in coordinator.data.get(const.DATA_KIDS, {}).values()
            }

            # Build achievement data with integrated validation
            achievement_data_dict, errors = fh.build_achievements_data(
                user_input, achievements_except_current, kids_name_to_id
            )

            if not errors:
                _, updated_achievement_data = next(iter(achievement_data_dict.items()))

                coordinator.update_achievement_entity(
                    internal_id, updated_achievement_data
                )

                new_name = user_input[const.CFOF_ACHIEVEMENTS_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "Edited Achievement '%s' with ID: %s",
                    new_name,
                    internal_id,
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }
        chores_dict = coordinator.chores_data

        # Create reverse mapping from internal_id to name
        id_to_name = {
            kid_id: kid_data[const.DATA_KID_NAME]
            for kid_id, kid_data in coordinator.kids_data.items()
        }

        # Convert assigned_kids from internal_ids to names for display
        assigned_kids_ids = achievement_data.get(
            const.DATA_ACHIEVEMENT_ASSIGNED_KIDS, []
        )
        assigned_kids_names = [
            id_to_name.get(kid_id, kid_id) for kid_id in assigned_kids_ids
        ]

        achievement_schema = fh.build_achievement_schema(
            kids_dict=kids_dict,
            chores_dict=chores_dict,
            default={
                **achievement_data,
                const.DATA_ACHIEVEMENT_ASSIGNED_KIDS: assigned_kids_names,
            },
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_ACHIEVEMENT,
            data_schema=achievement_schema,
            errors=errors,
        )

    # --- Challenges ---

    async def async_step_edit_challenge(self, user_input=None):
        """Edit an existing challenge."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        challenges_dict = coordinator.challenges_data
        internal_id = cast("str | None", self.context.get(const.DATA_INTERNAL_ID))

        if not internal_id or internal_id not in challenges_dict:
            const.LOGGER.error("Edit Challenge - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHALLENGE)

        challenge_data = challenges_dict[internal_id]

        if user_input is None:
            kids_dict = {
                data[const.DATA_KID_NAME]: kid_id
                for kid_id, data in coordinator.kids_data.items()
            }
            chores_dict = coordinator.chores_data

            # Create reverse mapping from internal_id to name
            id_to_name = {
                kid_id: data[const.DATA_KID_NAME]
                for kid_id, data in coordinator.kids_data.items()
            }

            # Convert assigned_kids from internal_ids to names for display
            assigned_kids_ids = challenge_data.get(
                const.DATA_CHALLENGE_ASSIGNED_KIDS, []
            )
            assigned_kids_names = [
                id_to_name.get(kid_id, kid_id) for kid_id in assigned_kids_ids
            ]

            # Convert stored start/end dates to selector format for display
            start_date_display = None
            end_date_display = None
            if challenge_data.get(const.DATA_CHALLENGE_START_DATE):
                start_date_display = kh.dt_parse(
                    challenge_data[const.DATA_CHALLENGE_START_DATE],
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                )
            if challenge_data.get(const.DATA_CHALLENGE_END_DATE):
                end_date_display = kh.dt_parse(
                    challenge_data[const.DATA_CHALLENGE_END_DATE],
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                )

            default_data = {
                **challenge_data,
                const.DATA_CHALLENGE_START_DATE: start_date_display,
                const.DATA_CHALLENGE_END_DATE: end_date_display,
                const.DATA_CHALLENGE_ASSIGNED_KIDS: assigned_kids_names,
            }
            schema = fh.build_challenge_schema(
                kids_dict=kids_dict, chores_dict=chores_dict, default=default_data
            )
            return self.async_show_form(
                step_id=const.OPTIONS_FLOW_STEP_EDIT_CHALLENGE,
                data_schema=schema,
                errors=errors,
            )

        # Use helper to build and validate challenge data
        challenge_data_dict, errors = fh.build_challenges_data(
            user_input,
            coordinator.kids_data,
            existing_challenges=coordinator.challenges_data,
            current_id=internal_id,  # Editing existing challenge
        )

        if not errors and challenge_data_dict:
            # Additional validation for options flow: dates must be in the future
            updated_data = challenge_data_dict[internal_id]
            start_date_str = updated_data[const.DATA_CHALLENGE_START_DATE]
            end_date_str = updated_data[const.DATA_CHALLENGE_END_DATE]

            start_dt = dt_util.parse_datetime(start_date_str)
            end_dt = dt_util.parse_datetime(end_date_str)

            if start_dt and start_dt < dt_util.utcnow():
                errors = {
                    const.CFOP_ERROR_START_DATE: const.TRANS_KEY_CFOF_START_DATE_IN_PAST
                }
            elif end_dt and end_dt <= dt_util.utcnow():
                errors = {
                    const.CFOP_ERROR_END_DATE: const.TRANS_KEY_CFOF_END_DATE_IN_PAST
                }

        if not errors and challenge_data_dict:
            updated_data = challenge_data_dict[internal_id]
            coordinator.update_challenge_entity(internal_id, updated_data)

            new_name = user_input[const.CFOF_CHALLENGES_INPUT_NAME].strip()
            const.LOGGER.debug(
                "Edited Challenge '%s' with ID: %s",
                new_name,
                internal_id,
            )
            self._mark_reload_needed()
            return await self.async_step_init()

        # Show form again with validation errors, preserving user input
        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }
        chores_dict = coordinator.chores_data

        challenge_schema = fh.build_challenge_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=user_input
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHALLENGE,
            data_schema=challenge_schema,
            errors=errors,
        )

    # ----------------------------------------------------------------------------------
    # DELETE METHODS (Cross-Entity - Keep Together)
    # ----------------------------------------------------------------------------------

    # --- Kids ---

    async def async_step_delete_kid(self, user_input=None):
        """Delete a kid."""
        coordinator = self._get_coordinator()
        kids_dict = coordinator.kids_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in kids_dict:
            const.LOGGER.error("Delete Kid - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_KID)

        kid_name = kids_dict[internal_id][const.DATA_KID_NAME]

        if user_input is not None:
            coordinator.delete_kid_entity(internal_id)

            const.LOGGER.debug("Deleted Kid '%s' with ID: %s", kid_name, internal_id)
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_KID,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_KID_NAME: kid_name
            },
        )

    # --- Parents ---

    async def async_step_delete_parent(self, user_input=None):
        """Delete a parent."""
        coordinator = self._get_coordinator()
        parents_dict = coordinator.parents_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in parents_dict:
            const.LOGGER.error("Delete Parent - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PARENT)

        parent_name = parents_dict[internal_id][const.DATA_PARENT_NAME]

        if user_input is not None:
            coordinator.delete_parent_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Parent '%s' with ID: %s", parent_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_PARENT,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_PARENT_NAME: parent_name
            },
        )

    # --- Chores ---

    async def async_step_delete_chore(self, user_input=None):
        """Delete a chore."""
        coordinator = self._get_coordinator()
        chores_dict = coordinator.chores_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in chores_dict:
            const.LOGGER.error("Delete Chore - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHORE)

        chore_name = chores_dict[internal_id][const.DATA_CHORE_NAME]

        if user_input is not None:
            coordinator.delete_chore_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Chore '%s' with ID: %s", chore_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_CHORE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_CHORE_NAME: chore_name
            },
        )

    # --- Badges ---

    async def async_step_delete_badge(self, user_input=None):
        """Delete a badge."""
        coordinator = self._get_coordinator()
        badges_dict = coordinator.badges_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in badges_dict:
            const.LOGGER.error("Delete Badge - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE)

        badge_name = badges_dict[internal_id][const.DATA_BADGE_NAME]

        if user_input is not None:
            coordinator.delete_badge_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Badge '%s' with ID: %s", badge_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BADGE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_BADGE_NAME: badge_name
            },
        )

    # --- Rewards ---

    async def async_step_delete_reward(self, user_input=None):
        """Delete a reward."""
        coordinator = self._get_coordinator()
        rewards_dict = coordinator.rewards_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in rewards_dict:
            const.LOGGER.error("Delete Reward - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_REWARD)

        reward_name = rewards_dict[internal_id][const.DATA_REWARD_NAME]

        if user_input is not None:
            coordinator.delete_reward_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Reward '%s' with ID: %s", reward_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_REWARD,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_REWARD_NAME: reward_name
            },
        )

    # --- Penalties ---

    async def async_step_delete_penalty(self, user_input=None):
        """Delete a penalty."""
        coordinator = self._get_coordinator()
        penalties_dict = coordinator.penalties_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in penalties_dict:
            const.LOGGER.error("Delete Penalty - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PENALTY)

        penalty_name = penalties_dict[internal_id][const.DATA_PENALTY_NAME]

        if user_input is not None:
            coordinator.delete_penalty_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Penalty '%s' with ID: %s", penalty_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_PENALTY,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_PENALTY_NAME: penalty_name
            },
        )

    # --- Achievements ---

    async def async_step_delete_achievement(self, user_input=None):
        """Delete an achievement."""
        coordinator = self._get_coordinator()
        achievements_dict = coordinator.achievements_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in achievements_dict:
            const.LOGGER.error(
                "Delete Achievement - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT)

        achievement_name = achievements_dict[internal_id][const.DATA_ACHIEVEMENT_NAME]

        if user_input is not None:
            coordinator.delete_achievement_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Achievement '%s' with ID: %s",
                achievement_name,
                internal_id,
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_ACHIEVEMENT,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_ACHIEVEMENT_NAME: achievement_name
            },
        )

    # --- Challenges ---

    async def async_step_delete_challenge(self, user_input=None):
        """Delete a challenge."""
        coordinator = self._get_coordinator()
        challenges_dict = coordinator.challenges_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in challenges_dict:
            const.LOGGER.error(
                "Delete Challenge - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHALLENGE)

        challenge_name = challenges_dict[internal_id][const.DATA_CHALLENGE_NAME]

        if user_input is not None:
            coordinator.delete_challenge_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Challenge '%s' with ID: %s", challenge_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_CHALLENGE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_CHALLENGE_NAME: challenge_name
            },
        )

    # --- Bonuses ---

    async def async_step_delete_bonus(self, user_input=None):
        """Delete a bonus."""
        coordinator = self._get_coordinator()
        bonuses_dict = coordinator.bonuses_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in bonuses_dict:
            const.LOGGER.error("Delete Bonus - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BONUS)

        bonus_name = bonuses_dict[internal_id][const.DATA_BONUS_NAME]

        if user_input is not None:
            coordinator.delete_bonus_entity(internal_id)

            const.LOGGER.debug(
                "Deleted Bonus '%s' with ID: %s", bonus_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BONUS,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_BONUS_NAME: bonus_name
            },
        )

    # ----------------------------------------------------------------------------------
    # GENERAL OPTIONS
    # ----------------------------------------------------------------------------------

    async def async_step_manage_general_options(self, user_input=None):
        """Manage general options: points adjust values, update interval, retention, and backup settings."""
        # Check if this is a backup management action
        if user_input is not None and const.CFOF_BACKUP_ACTION_SELECTION in user_input:
            action = user_input[const.CFOF_BACKUP_ACTION_SELECTION]
            # Skip empty/default selection
            if action and action.strip():
                if action == "create_backup":
                    return await self.async_step_create_manual_backup()
                if action == "delete_backup":
                    return await self.async_step_select_backup_to_delete()
                if action == "restore_backup":
                    return await self.async_step_select_backup_to_restore()

        if user_input is not None:
            # Get the raw text from the multiline text area.
            points_str = user_input.get(
                const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES, const.SENTINEL_EMPTY
            ).strip()
            if points_str:
                # Parse the values by splitting on separator.
                parsed_values = kh.parse_points_adjust_values(points_str)
                # Always store as a list of floats.
                self._entry_options[const.CONF_POINTS_ADJUST_VALUES] = parsed_values
            else:
                # Remove the key if the field is left empty.
                self._entry_options.pop(const.CONF_POINTS_ADJUST_VALUES, None)
            # Update the update interval.
            self._entry_options[const.CONF_UPDATE_INTERVAL] = user_input.get(
                const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL
            )
            # update calendar show period
            self._entry_options[const.CONF_CALENDAR_SHOW_PERIOD] = user_input.get(
                const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD
            )
            # Parse consolidated retention periods
            retention_str = user_input.get(
                const.CFOF_SYSTEM_INPUT_RETENTION_PERIODS, ""
            ).strip()
            if retention_str:
                try:
                    daily, weekly, monthly, yearly = fh.parse_retention_periods(
                        retention_str
                    )
                    self._entry_options[const.CONF_RETENTION_DAILY] = daily
                    self._entry_options[const.CONF_RETENTION_WEEKLY] = weekly
                    self._entry_options[const.CONF_RETENTION_MONTHLY] = monthly
                    self._entry_options[const.CONF_RETENTION_YEARLY] = yearly
                except ValueError as err:
                    const.LOGGER.error("Failed to parse retention periods: %s", err)
                    # Use defaults if parsing fails
                    self._entry_options[const.CONF_RETENTION_DAILY] = (
                        const.DEFAULT_RETENTION_DAILY
                    )
                    self._entry_options[const.CONF_RETENTION_WEEKLY] = (
                        const.DEFAULT_RETENTION_WEEKLY
                    )
                    self._entry_options[const.CONF_RETENTION_MONTHLY] = (
                        const.DEFAULT_RETENTION_MONTHLY
                    )
                    self._entry_options[const.CONF_RETENTION_YEARLY] = (
                        const.DEFAULT_RETENTION_YEARLY
                    )
            # Update legacy entities toggle
            self._entry_options[const.CONF_SHOW_LEGACY_ENTITIES] = user_input.get(
                const.CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES,
                const.DEFAULT_SHOW_LEGACY_ENTITIES,
            )
            # Update backup retention (count-based)
            self._entry_options[const.CONF_BACKUPS_MAX_RETAINED] = user_input.get(
                const.CFOF_SYSTEM_INPUT_BACKUPS_MAX_RETAINED,
                const.DEFAULT_BACKUPS_MAX_RETAINED,
            )
            const.LOGGER.debug(
                "General Options Updated: Points Adjust Values=%s, "
                "Update Interval=%s, Calendar Period to Show=%s, "
                "Retention Periods=%s, "
                "Show Legacy Entities=%s, Backup Retention=%s",
                self._entry_options.get(const.CONF_POINTS_ADJUST_VALUES),
                self._entry_options.get(const.CONF_UPDATE_INTERVAL),
                self._entry_options.get(const.CONF_CALENDAR_SHOW_PERIOD),
                retention_str,
                self._entry_options.get(const.CONF_SHOW_LEGACY_ENTITIES),
                self._entry_options.get(const.CONF_BACKUPS_MAX_RETAINED),
            )
            await self._update_system_settings_and_reload()
            # After saving settings, return to main menu
            return await self.async_step_init()

        general_schema = fh.build_general_options_schema(self._entry_options)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_MANAGE_GENERAL_OPTIONS,
            data_schema=general_schema,
            description_placeholders={},
        )

    async def async_step_restore_backup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle restore_backup step - delegate to restore_from_options."""
        return await self.async_step_restore_from_options(user_input)

    async def async_step_restore_from_options(self, user_input=None):
        """Handle restore options from general options menu (same as config flow)."""
        from pathlib import Path

        errors: dict[str, str] = {}

        if user_input is not None:
            selection = user_input.get(const.CFOF_DATA_RECOVERY_INPUT_SELECTION)

            if selection == "cancel":
                # Return to backup management menu without making changes
                return await self.async_step_manage_general_options()
            if selection == "start_fresh":
                return await self._handle_start_fresh_from_options()
            if selection == "current_active":
                return await self._handle_use_current_from_options()
            if selection == "paste_json":
                return await self.async_step_restore_paste_json_options()
            # Otherwise it's a backup filename - restore it
            if selection:
                return await self._handle_restore_backup_from_options(selection)

            errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_INVALID_SELECTION

        # Build selection menu
        storage_path = Path(self.hass.config.path(".storage", const.STORAGE_KEY))
        storage_file_exists = await self.hass.async_add_executor_job(
            storage_path.exists
        )

        # Discover backups (pass None for storage_manager - not needed for discovery)
        backups = await fh.discover_backups(self.hass, None)
        if not isinstance(backups, list):
            backups = []  # Handle any unexpected return type

        # Build options list for SelectSelector
        # Start with fixed options that can be translated
        options = []

        # Add cancel option first (for easy access)
        options.append("cancel")

        # Only show "use current" if file actually exists
        if storage_file_exists:
            options.append("current_active")

        options.append("start_fresh")

        # Add discovered backups (these use dynamic labels)
        for backup in backups:
            options.append(backup["filename"])

        # Add paste JSON option
        options.append("paste_json")

        # Build description placeholders for dynamic backup labels
        backup_labels = {}
        for backup in backups:
            age_str = fh.format_backup_age(backup["age_hours"])
            tag_display = backup["tag"].replace("-", " ").title()
            backup_labels[backup["filename"]] = (
                f"[{tag_display}] {backup['filename']} ({age_str})"
            )

        # Build schema using SelectSelector with translation_key
        data_schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_DATA_RECOVERY_INPUT_SELECTION
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="data_recovery_selection",
                        custom_value=True,  # Allow backup filenames not in translations
                    )
                )
            }
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_RESTORE_BACKUP,
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "storage_path": str(storage_path.parent),
                "backup_count": str(len(backups)),
            },
        )

    async def _handle_start_fresh_from_options(self):
        """Handle 'Start Fresh' from options - backup existing and delete, then reload."""
        import os
        from pathlib import Path

        from .storage_manager import KidsChoresStorageManager

        try:
            storage_manager = KidsChoresStorageManager(self.hass)
            storage_path = Path(storage_manager.get_storage_path())

            # Create safety backup if file exists
            if storage_path.exists():
                backup_name = await fh.create_timestamped_backup(
                    self.hass, storage_manager, const.BACKUP_TAG_RECOVERY
                )
                if backup_name:
                    const.LOGGER.info(
                        "Created safety backup before fresh start: %s", backup_name
                    )

                # Delete active file
                await self.hass.async_add_executor_job(os.remove, str(storage_path))
                const.LOGGER.info("Deleted active storage file for fresh start")

            # Reload the entry to reinitialize from scratch
            self._mark_reload_needed()
            return await self.async_step_init()

        except Exception as err:
            const.LOGGER.error("Fresh start failed: %s", err)
            return self.async_abort(reason="unknown")

    async def _handle_use_current_from_options(self):
        """Handle 'Use Current Active' from options - validate and reload."""
        import json
        from pathlib import Path

        try:
            # Get storage path without creating storage manager yet
            storage_path = Path(self.hass.config.path(".storage", const.STORAGE_KEY))

            if not storage_path.exists():
                return self.async_abort(reason="file_not_found")

            # Validate JSON
            data_str = await self.hass.async_add_executor_job(
                storage_path.read_text, "utf-8"
            )

            try:
                json.loads(data_str)  # Parse to validate
            except json.JSONDecodeError:
                return self.async_abort(reason="corrupt_file")

            # Validate structure
            if not fh.validate_backup_json(data_str):
                return self.async_abort(reason="invalid_structure")

            const.LOGGER.info("Using current active storage file")
            self._mark_reload_needed()
            return await self.async_step_init()

        except Exception as err:
            const.LOGGER.error("Use current failed: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_restore_paste_json_options(self, user_input=None):
        """Allow user to paste JSON data from diagnostics in options flow."""
        import json
        from pathlib import Path

        errors: dict[str, str] = {}

        if user_input is not None:
            json_text = user_input.get(
                const.CFOF_DATA_RECOVERY_INPUT_JSON_DATA, ""
            ).strip()

            if not json_text:
                errors[const.CFOP_ERROR_BASE] = "empty_json"
            else:
                try:
                    # Parse JSON
                    pasted_data = json.loads(json_text)

                    # Validate structure
                    if not fh.validate_backup_json(json_text):
                        errors[const.CFOP_ERROR_BASE] = "invalid_structure"
                    else:
                        # Determine data format and extract storage data
                        storage_data = pasted_data

                        # Handle diagnostic format (KC 4.0+ diagnostic exports)
                        if "home_assistant" in pasted_data and "data" in pasted_data:
                            const.LOGGER.info("Processing diagnostic export format")
                            storage_data = pasted_data["data"]
                        # Handle Store format (KC 3.0/3.1/4.0beta1)
                        elif "version" in pasted_data and "data" in pasted_data:
                            const.LOGGER.info("Processing Store format")
                            storage_data = pasted_data["data"]
                        # Raw storage data format
                        else:
                            const.LOGGER.info("Processing raw storage format")
                            storage_data = pasted_data

                        # Always wrap in HA Store format for storage file
                        wrapped_data = {
                            "version": 1,
                            "minor_version": 1,
                            "key": const.STORAGE_KEY,
                            "data": storage_data,
                        }

                        # Write to storage file
                        storage_path = Path(
                            self.hass.config.path(".storage", const.STORAGE_KEY)
                        )

                        # Write wrapped data to storage (directory created by HA/test fixtures)
                        await self.hass.async_add_executor_job(
                            storage_path.write_text,
                            json.dumps(wrapped_data, indent=2),
                            "utf-8",
                        )

                        const.LOGGER.info("Successfully imported JSON data to storage")

                        # Cleanup old backups
                        from .storage_manager import KidsChoresStorageManager

                        storage_manager = KidsChoresStorageManager(self.hass)
                        max_backups = const.DEFAULT_BACKUPS_MAX_RETAINED
                        await fh.cleanup_old_backups(
                            self.hass, storage_manager, max_backups
                        )

                        # Reload and return to init
                        self._mark_reload_needed()
                        return await self.async_step_init()

                except json.JSONDecodeError:
                    errors[const.CFOP_ERROR_BASE] = "invalid_json"
                except Exception as err:
                    const.LOGGER.error("Paste JSON failed: %s", err)
                    errors[const.CFOP_ERROR_BASE] = "unknown"

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_PASTE_JSON_RESTORE,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.CFOF_DATA_RECOVERY_INPUT_JSON_DATA
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            multiline=True,
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_paste_json_restore(self, user_input=None) -> dict[str, Any]:
        """Handle paste_json_restore step - delegate to paste_json_options."""
        return await self.async_step_restore_paste_json_options(user_input)

    async def _handle_restore_backup_from_options(self, backup_filename: str):
        """Handle restoring from a specific backup file in options flow."""
        import json
        from pathlib import Path
        import shutil

        from .storage_manager import KidsChoresStorageManager

        try:
            # Get storage path directly without creating storage manager yet
            storage_path = Path(self.hass.config.path(".storage", const.STORAGE_KEY))
            backup_path = storage_path.parent / backup_filename

            if not backup_path.exists():
                const.LOGGER.error("Backup file not found: %s", backup_filename)
                return self.async_abort(reason="file_not_found")

            # Read and validate backup
            backup_data_str = await self.hass.async_add_executor_job(
                backup_path.read_text, "utf-8"
            )

            try:
                json.loads(backup_data_str)  # Validate parseable JSON
            except json.JSONDecodeError:
                const.LOGGER.error("Backup file has invalid JSON: %s", backup_filename)
                return self.async_abort(reason="corrupt_file")

            # Validate structure
            if not fh.validate_backup_json(backup_data_str):
                const.LOGGER.error(
                    "Backup file missing required keys: %s", backup_filename
                )
                return self.async_abort(reason="invalid_structure")

            # Create safety backup of current file if it exists
            if storage_path.exists():
                # Create storage manager only for safety backup creation
                storage_manager = KidsChoresStorageManager(self.hass)
                safety_backup = await fh.create_timestamped_backup(
                    self.hass, storage_manager, const.BACKUP_TAG_RECOVERY
                )
                if safety_backup:
                    const.LOGGER.info(
                        "Created safety backup before restore: %s", safety_backup
                    )

            # Parse backup data
            backup_data = json.loads(backup_data_str)

            # Check if backup already has Home Assistant storage format
            if "version" in backup_data and "data" in backup_data:
                # Already in storage format - restore as-is
                await self.hass.async_add_executor_job(
                    shutil.copy2, str(backup_path), str(storage_path)
                )
            else:
                # Raw data format (like v30, v31, v40beta1 samples)
                # Load through storage manager to add proper wrapper
                storage_manager = KidsChoresStorageManager(self.hass)
                storage_manager.set_data(backup_data)
                await storage_manager.async_save()

            const.LOGGER.info("Restored backup: %s", backup_filename)

            # Cleanup old backups
            storage_manager = KidsChoresStorageManager(self.hass)
            max_backups = const.DEFAULT_BACKUPS_MAX_RETAINED
            await fh.cleanup_old_backups(self.hass, storage_manager, max_backups)

            # Reload and return to init
            self._mark_reload_needed()
            return await self.async_step_init()

        except Exception as err:
            const.LOGGER.error("Restore backup failed: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_backup_actions_menu(self, user_input=None):
        """Show backup management actions menu."""
        from .storage_manager import KidsChoresStorageManager

        if user_input is not None:
            action = user_input[const.CFOF_BACKUP_ACTION_SELECTION]

            if action == "create_backup":
                return await self.async_step_create_manual_backup()
            if action == "delete_backup":
                return await self.async_step_select_backup_to_delete()
            if action == "restore_backup":
                return await self.async_step_select_backup_to_restore()
            if action == "return_to_menu":
                return await self.async_step_init()

        # Discover backups to show count
        storage_manager = KidsChoresStorageManager(self.hass)
        backups = await fh.discover_backups(self.hass, storage_manager)
        backup_count = len(backups)

        # Calculate total storage usage
        total_size_mb = sum(b.get("size_bytes", 0) for b in backups) / (1024 * 1024)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_BACKUP_ACTIONS,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.CFOF_BACKUP_ACTION_SELECTION
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "create_backup",
                                "delete_backup",
                                "restore_backup",
                                "return_to_menu",
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU,
                        )
                    )
                }
            ),
            description_placeholders={
                "backup_count": str(backup_count),
                "storage_size": f"{total_size_mb:.2f}",
            },
        )

    async def async_step_select_backup_to_delete(self, user_input=None):
        """Select a backup file to delete."""
        from .storage_manager import KidsChoresStorageManager

        storage_manager = KidsChoresStorageManager(self.hass)

        if user_input is not None:
            selection = user_input.get(const.CFOF_BACKUP_SELECTION)

            if selection == "cancel":
                return await self.async_step_backup_actions_menu()

            # Extract backup filename from emoji-prefixed selection
            if selection and selection.startswith("🗑️"):
                filename = self._extract_filename_from_selection(selection)
                if filename:
                    assert filename is not None  # Type narrowing for mypy
                    self._backup_to_delete = filename
                    return await self.async_step_delete_backup_confirm()

            return await self.async_step_backup_actions_menu()

        # Discover all backups
        backups = await fh.discover_backups(self.hass, storage_manager)

        # Build backup options - EMOJI ONLY for files (no hardcoded action text)
        # All backups can be deleted (no protected backups concept)
        backup_options = []

        for backup in backups:
            age_str = fh.format_backup_age(backup["age_hours"])
            size_kb = backup["size_bytes"] / 1024
            tag_display = backup["tag"].replace("-", " ").title()

            # Emoji-only prefix - NO hardcoded English text
            option = (
                f"🗑️ [{tag_display}] {backup['filename']} ({age_str}, {size_kb:.1f} KB)"
            )
            backup_options.append(option)

        # Add cancel option (translated via translation_key)
        backup_options.append("cancel")

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE,
            data_schema=vol.Schema(
                {
                    vol.Required(const.CFOF_BACKUP_SELECTION): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=backup_options,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_SELECT_BACKUP_TO_DELETE,
                            custom_value=True,
                        )
                    )
                }
            ),
            description_placeholders={
                "backup_count": str(len(backups)),
            },
        )

    async def async_step_select_backup_to_restore(self, user_input=None):
        """Select a backup file to restore."""
        from .storage_manager import KidsChoresStorageManager

        storage_manager = KidsChoresStorageManager(self.hass)

        if user_input is not None:
            selection = user_input.get(const.CFOF_BACKUP_SELECTION)

            if selection == "cancel":
                return await self.async_step_backup_actions_menu()

            # Extract backup filename from emoji-prefixed selection
            if selection and selection.startswith("🔄"):
                filename = self._extract_filename_from_selection(selection)
                if filename:
                    assert filename is not None  # Type narrowing for mypy
                    self._backup_to_restore = filename
                    return await self.async_step_restore_backup_confirm()

            return await self.async_step_backup_actions_menu()

        # Discover all backups
        backups = await fh.discover_backups(self.hass, storage_manager)

        if not backups:
            # No backups available - return to menu
            return await self.async_step_backup_actions_menu()

        # Build backup options - EMOJI ONLY for files (no hardcoded action text)
        backup_options = []

        for backup in backups:
            age_str = fh.format_backup_age(backup["age_hours"])
            size_kb = backup["size_bytes"] / 1024
            tag_display = backup["tag"].replace("-", " ").title()

            # Emoji-only prefix - NO hardcoded English text
            option = (
                f"🔄 [{tag_display}] {backup['filename']} ({age_str}, {size_kb:.1f} KB)"
            )
            backup_options.append(option)

        # Add cancel option (translated via translation_key)
        backup_options.append("cancel")

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_RESTORE,
            data_schema=vol.Schema(
                {
                    vol.Required(const.CFOF_BACKUP_SELECTION): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=backup_options,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_SELECT_BACKUP_TO_RESTORE,
                            custom_value=True,
                        )
                    )
                }
            ),
            description_placeholders={"backup_count": str(len(backups))},
        )

    def _extract_filename_from_selection(self, selection: str) -> str | None:
        """Extract backup filename from emoji-prefixed selection.

        Format: "🔄 [Tag] filename.json (age, size)" or "🗑️ [Tag] filename.json (age, size)"
        Returns: "filename.json" or None if extraction fails
        """
        # Remove emoji prefix (first 2-3 characters depending on emoji width)
        if selection.startswith(("🔄 ", "🗑️ ")):
            display_part = selection[2:].strip()

            # Extract from "[Tag] filename.json (age, size)"
            if "] " in display_part and " (" in display_part:
                start_idx = display_part.find("] ") + 2
                end_idx = display_part.rfind(" (")
                if start_idx < end_idx:
                    return display_part[start_idx:end_idx]

        # Fallback: return None (couldn't parse)
        return None

    async def async_step_create_manual_backup(self, user_input=None):
        """Create a manual backup."""
        from .storage_manager import KidsChoresStorageManager

        storage_manager = KidsChoresStorageManager(self.hass)

        if user_input is not None:
            if user_input.get("confirm"):
                # Create manual backup
                backup_filename = await fh.create_timestamped_backup(
                    self.hass,
                    storage_manager,
                    const.BACKUP_TAG_MANUAL,
                    self.config_entry,
                )

                if backup_filename:
                    const.LOGGER.info("Manual backup created: %s", backup_filename)
                    # Run cleanup with current retention setting
                    retention = self._entry_options.get(
                        const.CONF_BACKUPS_MAX_RETAINED,
                        const.DEFAULT_BACKUPS_MAX_RETAINED,
                    )
                    await fh.cleanup_old_backups(self.hass, storage_manager, retention)

                    # Show success message and return to backup menu
                    const.LOGGER.info(
                        "Manual backup created successfully: %s", backup_filename
                    )
                    return await self.async_step_backup_actions_menu()
                const.LOGGER.error("Failed to create manual backup")
                return await self.async_step_backup_actions_menu()
            return await self.async_step_backup_actions_menu()

        # Get backup count and retention for placeholders
        available_backups = await fh.discover_backups(self.hass, storage_manager)
        backup_count = len(available_backups)
        retention = self._entry_options.get(
            const.CONF_BACKUPS_MAX_RETAINED,
            const.DEFAULT_BACKUPS_MAX_RETAINED,
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_CREATE_MANUAL_BACKUP,
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={
                "backup_count": str(backup_count),
                "retention": str(retention),
            },
        )

    async def async_step_delete_backup_confirm(self, user_input=None):
        """Confirm backup deletion."""
        from pathlib import Path

        from .storage_manager import KidsChoresStorageManager

        # Get backup filename from context (set by select_backup_to_delete step)
        backup_filename = getattr(self, "_backup_to_delete", None)

        if user_input is not None:
            if user_input.get("confirm"):
                storage_manager = KidsChoresStorageManager(self.hass)
                storage_path = Path(storage_manager.get_storage_path())
                # Type guard: ensure backup_filename is a string before using in Path operation
                if isinstance(backup_filename, str):
                    backup_path = storage_path.parent / backup_filename

                    if backup_path.exists():
                        try:
                            await self.hass.async_add_executor_job(backup_path.unlink)
                            const.LOGGER.info("Deleted backup: %s", backup_filename)
                        except Exception as err:
                            const.LOGGER.error(
                                "Failed to delete backup %s: %s", backup_filename, err
                            )
                    else:
                        const.LOGGER.error("Backup file not found: %s", backup_filename)
                else:
                    const.LOGGER.error("Invalid backup filename: %s", backup_filename)

            # Clear the backup filename and return to backup menu
            self._backup_to_delete = None
            return await self.async_step_backup_actions_menu()

        # Show confirmation form
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BACKUP_CONFIRM,
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"backup_filename": backup_filename or "unknown"},
        )

    async def async_step_restore_backup_confirm(self, user_input=None):
        """Confirm backup restoration."""
        from pathlib import Path
        import shutil

        from .storage_manager import KidsChoresStorageManager

        # Get backup filename from context (set by select_backup_to_restore step)
        backup_filename = getattr(self, "_backup_to_restore", None)

        if user_input is not None:
            if user_input.get("confirm"):
                storage_manager = KidsChoresStorageManager(self.hass)
                storage_path = Path(storage_manager.get_storage_path())
                # Type guard: ensure backup_filename is a string before using in Path operation
                if not isinstance(backup_filename, str):
                    const.LOGGER.error("Invalid backup filename: %s", backup_filename)
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                backup_path = storage_path.parent / backup_filename

                if not backup_path.exists():
                    const.LOGGER.error("Backup file not found: %s", backup_filename)
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                # Read and validate backup
                try:
                    backup_data_str = await self.hass.async_add_executor_job(
                        backup_path.read_text, "utf-8"
                    )
                except Exception as err:
                    const.LOGGER.error(
                        "Failed to read backup file %s: %s", backup_filename, err
                    )
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                if not fh.validate_backup_json(backup_data_str):
                    const.LOGGER.error("Invalid backup file: %s", backup_filename)
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                try:
                    import json

                    # Create safety backup of current file
                    safety_backup = await fh.create_timestamped_backup(
                        self.hass,
                        storage_manager,
                        const.BACKUP_TAG_RECOVERY,
                        self.config_entry,
                    )
                    const.LOGGER.info("Created safety backup: %s", safety_backup)

                    # Restore backup
                    await self.hass.async_add_executor_job(
                        shutil.copy2, backup_path, storage_path
                    )
                    const.LOGGER.info("Restored backup: %s", backup_filename)

                    # Extract and apply config_entry_settings if present
                    backup_data_str = await self.hass.async_add_executor_job(
                        backup_path.read_text, "utf-8"
                    )
                    backup_data = json.loads(backup_data_str)

                    if const.DATA_CONFIG_ENTRY_SETTINGS in backup_data:
                        settings = backup_data[const.DATA_CONFIG_ENTRY_SETTINGS]
                        validated = fh._validate_config_entry_settings(settings)

                        if validated:
                            # Merge with defaults for any missing keys
                            new_options = {
                                key: validated.get(key, default)
                                for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
                            }
                            # Update config entry with restored settings
                            self.hass.config_entries.async_update_entry(
                                self.config_entry, options=new_options
                            )
                            const.LOGGER.info(
                                "Restored %d system settings from backup",
                                len(validated),
                            )
                        else:
                            const.LOGGER.info(
                                "No valid system settings in backup, keeping current settings"
                            )
                    else:
                        const.LOGGER.info(
                            "Backup does not contain system settings, keeping current settings"
                        )

                    # Cleanup old backups
                    retention = self._entry_options.get(
                        const.CONF_BACKUPS_MAX_RETAINED,
                        const.DEFAULT_BACKUPS_MAX_RETAINED,
                    )
                    await fh.cleanup_old_backups(self.hass, storage_manager, retention)

                    # Clear context and reload integration to pick up restored data
                    self._backup_to_restore = None
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )

                    return self.async_abort(reason="backup_restored")

                except Exception as err:
                    const.LOGGER.error(
                        "Failed to restore backup %s: %s", backup_filename, err
                    )
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()
            else:
                # User cancelled - clear context and return to backup menu
                self._backup_to_restore = None
                return await self.async_step_backup_actions_menu()

        # Show confirmation form
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_RESTORE_BACKUP_CONFIRM,
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"backup_filename": backup_filename or "unknown"},
        )

    # ----------------------------------------------------------------------------------
    # HELPER METHODS (RELOAD & PERSISTENCE)
    # ----------------------------------------------------------------------------------

    def _mark_reload_needed(self):
        """Mark that a reload is needed after the current flow completes.

        When entities (rewards, bonuses, chores, etc.) are added, edited, or deleted,
        the coordinator data is updated but new sensors are not automatically created.
        We defer the reload until the user returns to the main menu to avoid
        interrupting the flow mid-operation.
        """
        const.LOGGER.debug("Marking reload needed after entity change")
        self._reload_needed = True

    async def _reload_entry_after_entity_change(self):
        """Reload the config entry to recreate sensors.

        This is called when returning to the main menu after entity changes.
        After reload, triggers an immediate coordinator refresh so new entities get data.
        """
        const.LOGGER.debug(
            "Reloading entry after entity changes: %s",
            self.config_entry.entry_id,
        )
        try:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            const.LOGGER.debug("Entry reloaded successfully")
        except Exception as err:
            const.LOGGER.error(
                "Failed to reload config entry after entity changes: %s",
                err,
                exc_info=True,
            )
            # Continue despite reload failure - UI still shows menu and entities
            # will reload on next Home Assistant restart

        # Trigger immediate coordinator refresh so new entities get data right away
        # instead of waiting for the next update interval
        coordinator = self._get_coordinator()
        if coordinator:
            const.LOGGER.debug("Triggering immediate coordinator refresh after reload")
            await coordinator.async_request_refresh()
            const.LOGGER.debug("Coordinator refresh completed")

    async def _update_system_settings_and_reload(self):
        """Update system settings in config and reload (for points_label, update_interval, etc.)."""
        new_data = dict(self.config_entry.data)
        new_data[const.DATA_LAST_CHANGE] = dt_util.utcnow().isoformat()

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data, options=self._entry_options
        )
        const.LOGGER.debug(
            "Updating system settings. Reloading entry: %s",
            self.config_entry.entry_id,
        )
        try:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            const.LOGGER.debug("System settings updated and KidsChores reloaded")
        except Exception as err:
            const.LOGGER.error(
                "Failed to reload config entry after system settings update: %s",
                err,
                exc_info=True,
            )
            # Continue despite reload failure - settings saved in config entry
            # and will take effect on next Home Assistant restart
