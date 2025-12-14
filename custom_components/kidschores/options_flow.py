# File: options_flow.py
"""Options Flow for the KidsChores integration, managing entities by internal_id.

Handles add/edit/delete operations with entities referenced internally by internal_id.
Ensures consistency and reloads the integration upon changes.
"""
# pylint: disable=protected-access
# Note: Options flow is tightly coupled to coordinator and needs direct access
# to internal creation/persistence methods (_create_* and _persist).

import asyncio
import datetime
import uuid
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from . import const
from . import flow_helpers as fh
from . import kc_helpers as kh


def _ensure_str(value):
    """Convert anything to string safely."""
    if isinstance(value, dict):
        # Attempt to get a known key or fallback
        return str(
            value.get(const.CONF_VALUE, next(iter(value.values()), const.CONF_EMPTY))
        )
    return str(value)


class KidsChoresOptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for adding/editing/deleting configuration elements."""

    def __init__(self, _config_entry: config_entries.ConfigEntry):
        """Initialize the options flow."""
        self._entry_options = {}
        self._action = None
        self._entity_type = None
        self._reload_needed = False  # Track if reload is needed

    def _get_coordinator(self):
        """Get the coordinator from hass.data."""
        return self.hass.data[const.DOMAIN][self.config_entry.entry_id][
            const.COORDINATOR
        ]

    async def async_step_init(self, user_input=None):
        """Display the main menu for the Options Flow."""
        # Check if reload is needed from previous entity add/edit operations
        if self._reload_needed and user_input is None:
            const.LOGGER.debug("DEBUG: Performing deferred reload after entity changes")
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

            elif selection == const.OPTIONS_FLOW_GENERAL_OPTIONS:
                return await self.async_step_manage_general_options()

            elif selection.startswith(const.OPTIONS_FLOW_MENU_MANAGE_PREFIX):
                self._entity_type = selection.replace(
                    const.OPTIONS_FLOW_MENU_MANAGE_PREFIX, const.CONF_EMPTY
                )
                return await self.async_step_manage_entity()

            elif selection == const.OPTIONS_FLOW_FINISH:
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
        errors = {}

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
                    "DEBUG: Configured points with name %s and icon %s",
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
            elif self._action in [
                const.OPTIONS_FLOW_ACTIONS_EDIT,
                const.OPTIONS_FLOW_ACTIONS_DELETE,
            ]:
                return await self.async_step_select_entity()
            elif self._action == const.OPTIONS_FLOW_ACTIONS_BACK:
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
            description_placeholders={  # type: ignore[arg-type]
                const.OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE: self._entity_type
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
            data.get(const.OPTIONS_FLOW_DATA_ENTITY_NAME, const.UNKNOWN_ENTITY)
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
                const.LOGGER.error(
                    "ERROR: Selected entity '%s' not found", selected_name
                )
                return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ENTITY)

            # Store internal_id in context for later use
            self.context[const.OPTIONS_FLOW_INPUT_INTERNAL_ID] = internal_id  # type: ignore[typeddict-unknown-key]

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
                    elif badge_type == const.BADGE_TYPE_DAILY:
                        return await self.async_step_edit_badge_daily(
                            default_data=badge_data
                        )
                    elif badge_type == const.BADGE_TYPE_PERIODIC:
                        return await self.async_step_edit_badge_periodic(
                            default_data=badge_data
                        )
                    elif badge_type == const.BADGE_TYPE_ACHIEVEMENT_LINKED:
                        return await self.async_step_edit_badge_achievement(
                            default_data=badge_data
                        )
                    elif badge_type == const.BADGE_TYPE_CHALLENGE_LINKED:
                        return await self.async_step_edit_badge_challenge(
                            default_data=badge_data
                        )
                    elif badge_type == const.BADGE_TYPE_SPECIAL_OCCASION:
                        return await self.async_step_edit_badge_special(
                            default_data=badge_data
                        )
                    else:
                        const.LOGGER.error(
                            "ERROR: Unknown badge type '%s' for badge ID '%s'",
                            badge_type,
                            internal_id,
                        )
                        return self.async_abort(
                            reason=const.TRANS_KEY_CFOF_INVALID_BADGE_TYPE
                        )
                else:
                    # For other entity types, route to their specific edit step
                    return await getattr(
                        self,
                        f"async_step_edit_{self._entity_type}",
                    )()

            elif self._action == const.OPTIONS_FLOW_ACTIONS_DELETE:
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
            description_placeholders={  # type: ignore[arg-type]
                const.OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE: self._entity_type,
                const.OPTIONS_FLOW_PLACEHOLDER_ACTION: self._action,
            },
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
        key = entity_type_to_data.get(self._entity_type)  # type: ignore[assignment]
        if key is None:
            const.LOGGER.error(
                "ERROR: Unknown entity type '%s'. Cannot retrieve entity dictionary",
                self._entity_type,
            )
            return {}
        return coordinator.data.get(key, {})

    # ------------------ ADD ENTITY ------------------
    async def async_step_add_kid(self, user_input=None):
        """Add a new kid."""
        coordinator = self._get_coordinator()
        errors = {}
        kids_dict = coordinator.kids_data

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_kids_inputs(user_input, kids_dict)

            if not errors:
                # Build kid data
                kid_data = fh.build_kids_data(user_input, kids_dict)

                # Get internal_id and the kid data dict
                internal_id = list(kid_data.keys())[0]
                new_kid_data = kid_data[internal_id]
                kid_name = new_kid_data[const.DATA_KID_NAME]

                # Add to coordinator
                coordinator._create_kid(internal_id, new_kid_data)
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "DEBUG: Added Kid '%s' with ID: %s", kid_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()
        schema = await fh.build_kid_schema(
            self.hass,
            users=users,
            default_kid_name=const.CONF_EMPTY,
            default_ha_user_id=None,
            default_enable_mobile_notifications=False,
            default_mobile_notify_service=None,
            default_enable_persistent_notifications=False,
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_KID, data_schema=schema, errors=errors
        )

    async def async_step_add_parent(self, user_input=None):
        """Add a new parent."""
        coordinator = self._get_coordinator()
        errors = {}
        parents_dict = coordinator.parents_data

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_parents_inputs(user_input, parents_dict)

            if not errors:
                # Build parent data
                parent_data = fh.build_parents_data(user_input, parents_dict)

                # Get internal_id and the parent data dict
                internal_id = list(parent_data.keys())[0]
                new_parent_data = parent_data[internal_id]
                parent_name = new_parent_data[const.DATA_PARENT_NAME]

                # Add to coordinator
                coordinator._create_parent(internal_id, new_parent_data)
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "DEBUG: Added Parent '%s' with ID: %s", parent_name, internal_id
                )
                return await self.async_step_init()

        # Retrieve HA users and existing kids for linking
        users = await self.hass.auth.async_get_users()
        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }

        parent_schema = fh.build_parent_schema(
            self.hass,
            users=users,
            kids_dict=kids_dict,
            default_parent_name=const.CONF_EMPTY,
            default_ha_user_id=None,
            default_associated_kids=[],
            default_enable_mobile_notifications=False,
            default_mobile_notify_service=None,
            default_enable_persistent_notifications=False,
            internal_id=None,
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_PARENT,
            data_schema=parent_schema,
            errors=errors,
        )

    async def async_step_add_chore(self, user_input=None):
        """Add a new chore."""
        coordinator = self._get_coordinator()
        errors = {}
        chores_dict = coordinator.chores_data

        if user_input is not None:
            # Build kids_dict for name→UUID conversion
            kids_dict = {
                data[const.DATA_KID_NAME]: eid
                for eid, data in coordinator.kids_data.items()
            }

            # Build and validate chore data
            chore_data, errors = fh.build_chores_data(
                self.hass, user_input, kids_dict, chores_dict
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

            # Add to coordinator
            coordinator._create_chore(internal_id, new_chore_data)
            coordinator._persist()
            coordinator.async_update_listeners()

            const.LOGGER.debug(
                "DEBUG: Added Chore '%s' with ID: %s and Due Date %s",
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

    async def async_step_add_badge(self, user_input=None):
        """Entry point to add a new badge."""
        if user_input is not None:
            badge_type = user_input[const.CFOF_BADGES_INPUT_TYPE]
            self.context[const.CFOF_BADGES_INPUT_TYPE] = badge_type  # type: ignore[typeddict-unknown-key]

            # Redirect to the appropriate step based on badge type
            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                return await self.async_step_add_badge_cumulative()
            elif badge_type == const.BADGE_TYPE_DAILY:
                return await self.async_step_add_badge_daily()
            elif badge_type == const.BADGE_TYPE_PERIODIC:
                return await self.async_step_add_badge_periodic()
            elif badge_type == const.BADGE_TYPE_ACHIEVEMENT_LINKED:
                return await self.async_step_add_badge_achievement()
            elif badge_type == const.BADGE_TYPE_CHALLENGE_LINKED:
                return await self.async_step_add_badge_challenge()
            elif badge_type == const.BADGE_TYPE_SPECIAL_OCCASION:
                return await self.async_step_add_badge_special()
            else:
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
        user_input: Optional[Dict[str, Any]] = None,
        badge_type: str = const.BADGE_TYPE_CUMULATIVE,
        default_data: Optional[Dict[str, Any]] = None,
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

        errors: Dict[str, str] = {}

        # Determine internal_id
        if is_edit:
            internal_id = self.context.get(const.CFOF_GLOBAL_INPUT_INTERNAL_ID)
            if not internal_id or internal_id not in badges_dict:
                const.LOGGER.error("ERROR: Invalid Internal ID for editing badge.")
                return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE)
        else:
            # Generate a new internal_id for adding a badge
            internal_id = str(uuid.uuid4())
            self.context[const.CFOF_GLOBAL_INPUT_INTERNAL_ID] = internal_id  # type: ignore[typeddict-unknown-key]

        if user_input is not None:
            # --- Validate Inputs ---
            errors = fh.validate_badge_common_inputs(
                user_input=user_input,
                internal_id=internal_id,
                existing_badges=badges_dict,
                rewards_dict=rewards_dict,
                bonuses_dict=bonuses_dict,
                penalties_dict=penalties_dict,
                badge_type=badge_type,
            )

            if not errors:
                # --- Build Data ---
                updated_badge_data = fh.build_badge_common_data(
                    user_input=user_input,
                    internal_id=internal_id,
                    badge_type=badge_type,
                )
                updated_badge_data[const.DATA_BADGE_TYPE] = badge_type

                # --- Save Data ---
                if is_edit:
                    coordinator.update_badge_entity(internal_id, updated_badge_data)
                else:
                    coordinator._create_badge(internal_id, updated_badge_data)
                    coordinator._persist()
                    coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "%s Badge '%s' with ID: %s. Data: %s",
                    "Updated" if is_edit else "Added",
                    updated_badge_data[const.DATA_BADGE_NAME],
                    internal_id,
                    updated_badge_data,
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
            const.LOGGER.error("ERROR: Invalid badge type '%s'.", badge_type)
            return self.async_abort(reason="invalid_badge_type")

        return self.async_show_form(
            step_id=step_name,
            data_schema=data_schema,
            errors=errors,
            description_placeholders=None,
            last_step=False,
        )

    async def async_step_add_reward(self, user_input=None):
        """Add a new reward."""
        coordinator = self._get_coordinator()
        errors = {}
        rewards_dict = coordinator.rewards_data

        if user_input is not None:
            reward_name = user_input[const.CFOF_REWARDS_INPUT_NAME].strip()
            internal_id = user_input.get(
                const.CFOF_GLOBAL_INPUT_INTERNAL_ID, str(uuid.uuid4())
            )

            if any(
                reward_data[const.DATA_REWARD_NAME] == reward_name
                for reward_data in rewards_dict.values()
            ):
                errors[const.CFOP_ERROR_REWARD_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_REWARD
                )
            else:
                new_reward_data = {
                    const.DATA_REWARD_NAME: reward_name,
                    const.DATA_REWARD_COST: user_input[const.CFOF_REWARDS_INPUT_COST],
                    const.DATA_REWARD_DESCRIPTION: user_input.get(
                        const.CFOF_REWARDS_INPUT_DESCRIPTION, const.CONF_EMPTY
                    ),
                    const.DATA_REWARD_LABELS: user_input.get(
                        const.CFOF_REWARDS_INPUT_LABELS, []
                    ),
                    const.DATA_REWARD_ICON: user_input.get(
                        const.CFOF_REWARDS_INPUT_ICON, const.DEFAULT_REWARD_ICON
                    ),
                    const.DATA_REWARD_INTERNAL_ID: internal_id,
                }
                coordinator._create_reward(internal_id, new_reward_data)
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "DEBUG: Added Reward '%s' with ID: %s", reward_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_reward_schema()
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_REWARD,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_bonus(self, user_input=None):
        """Add a new bonus."""
        coordinator = self._get_coordinator()
        errors = {}
        bonuses_dict = coordinator.bonuses_data

        if user_input is not None:
            bonus_name = user_input[const.CFOF_BONUSES_INPUT_NAME].strip()
            bonus_points = user_input[const.CFOF_BONUSES_INPUT_POINTS]
            internal_id = user_input.get(
                const.CFOF_GLOBAL_INPUT_INTERNAL_ID, str(uuid.uuid4())
            )

            if any(
                bonus_data[const.DATA_BONUS_NAME] == bonus_name
                for bonus_data in bonuses_dict.values()
            ):
                errors[const.CFOP_ERROR_BONUS_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_BONUS
                )
            else:
                new_bonus_data = {
                    const.DATA_BONUS_NAME: bonus_name,
                    const.DATA_BONUS_DESCRIPTION: user_input.get(
                        const.CFOF_BONUSES_INPUT_DESCRIPTION, const.CONF_EMPTY
                    ),
                    const.DATA_BONUS_LABELS: user_input.get(
                        const.CFOF_BONUSES_INPUT_LABELS, []
                    ),
                    const.DATA_BONUS_POINTS: abs(bonus_points),
                    const.DATA_BONUS_ICON: user_input.get(
                        const.CFOF_BONUSES_INPUT_ICON, const.DEFAULT_BONUS_ICON
                    ),
                    const.DATA_BONUS_INTERNAL_ID: internal_id,
                }
                coordinator._create_bonus(internal_id, new_bonus_data)
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "DEBUG: Added Bonus '%s' with ID: %s", bonus_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_bonus_schema()
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_BONUS, data_schema=schema, errors=errors
        )

    async def async_step_add_penalty(self, user_input=None):
        """Add a new penalty."""
        coordinator = self._get_coordinator()
        errors = {}
        penalties_dict = coordinator.penalties_data

        if user_input is not None:
            penalty_name = user_input[const.CFOF_PENALTIES_INPUT_NAME].strip()
            penalty_points = user_input[const.CFOF_PENALTIES_INPUT_POINTS]
            internal_id = user_input.get(
                const.CFOF_GLOBAL_INPUT_INTERNAL_ID, str(uuid.uuid4())
            )

            if any(
                penalty_data[const.DATA_PENALTY_NAME] == penalty_name
                for penalty_data in penalties_dict.values()
            ):
                errors[const.CFOP_ERROR_PENALTY_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_PENALTY
                )
            else:
                new_penalty_data = {
                    const.DATA_PENALTY_NAME: penalty_name,
                    const.DATA_PENALTY_DESCRIPTION: user_input.get(
                        const.CFOF_PENALTIES_INPUT_DESCRIPTION, const.CONF_EMPTY
                    ),
                    const.DATA_PENALTY_LABELS: user_input.get(
                        const.CFOF_PENALTIES_INPUT_LABELS, []
                    ),
                    const.DATA_PENALTY_POINTS: -abs(
                        penalty_points
                    ),  # Ensure points are negative
                    const.DATA_PENALTY_ICON: user_input.get(
                        const.CFOF_PENALTIES_INPUT_ICON, const.DEFAULT_PENALTY_ICON
                    ),
                    const.DATA_PENALTY_INTERNAL_ID: internal_id,
                }
                coordinator._create_penalty(internal_id, new_penalty_data)
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "DEBUG: Added Penalty '%s' with ID: %s", penalty_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_penalty_schema()
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_PENALTY,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_achievement(self, user_input=None):
        """Add a new achievement."""
        coordinator = self._get_coordinator()
        errors = {}
        achievements_dict = coordinator.achievements_data

        chores_dict = coordinator.chores_data

        if user_input is not None:
            achievement_name = user_input[const.CFOF_ACHIEVEMENTS_INPUT_NAME].strip()
            if any(
                data[const.DATA_ACHIEVEMENT_NAME] == achievement_name
                for data in achievements_dict.values()
            ):
                errors[const.CFOP_ERROR_ACHIEVEMENT_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_ACHIEVEMENT
                )
            else:
                _type = user_input[const.CFOF_ACHIEVEMENTS_INPUT_TYPE]

                chore_id = const.CONF_EMPTY

                if _type == const.ACHIEVEMENT_TYPE_STREAK:
                    c = (
                        user_input.get(const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID)
                        or const.CONF_EMPTY
                    )
                    if not c or c == const.CONF_NONE_TEXT:
                        errors[const.CFOP_ERROR_SELECT_CHORE_ID] = (
                            const.TRANS_KEY_CFOF_CHORE_MUST_BE_SELECTED
                        )
                    chore_id = c

                if not errors:
                    # Convert kid names to internal IDs for storage
                    coordinator = self._get_coordinator()
                    assigned_kids_names = user_input[
                        const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_KIDS
                    ]
                    kids_dict = {
                        kid[const.DATA_KID_NAME]: kid[const.DATA_KID_INTERNAL_ID]
                        for kid in coordinator.data.get(const.DATA_KIDS, [])
                    }
                    assigned_kids_ids = [
                        kids_dict.get(name, name) for name in assigned_kids_names
                    ]

                    internal_id = user_input.get(
                        const.CFOF_GLOBAL_INPUT_INTERNAL_ID, str(uuid.uuid4())
                    )
                    new_achievement_data = {
                        const.DATA_ACHIEVEMENT_NAME: achievement_name,
                        const.DATA_ACHIEVEMENT_DESCRIPTION: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION, const.CONF_EMPTY
                        ),
                        const.DATA_ACHIEVEMENT_LABELS: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_LABELS, []
                        ),
                        const.DATA_ACHIEVEMENT_ICON: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_ICON,
                            const.DEFAULT_ACHIEVEMENTS_ICON,
                        ),
                        const.DATA_ACHIEVEMENT_ASSIGNED_KIDS: assigned_kids_ids,
                        const.DATA_ACHIEVEMENT_TYPE: _type,
                        const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: chore_id,
                        const.DATA_ACHIEVEMENT_CRITERIA: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_CRITERIA, const.CONF_EMPTY
                        ).strip(),
                        const.DATA_ACHIEVEMENT_TARGET_VALUE: user_input[
                            const.CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE
                        ],
                        const.DATA_ACHIEVEMENT_REWARD_POINTS: user_input[
                            const.CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS
                        ],
                        const.DATA_ACHIEVEMENT_INTERNAL_ID: internal_id,
                        const.DATA_ACHIEVEMENT_PROGRESS: {},
                    }
                    coordinator._create_achievement(internal_id, new_achievement_data)
                    coordinator._persist()
                    coordinator.async_update_listeners()
                    const.LOGGER.debug(
                        "DEBUG: Added Achievement '%s' with ID: %s",
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

    async def async_step_add_challenge(self, user_input=None):
        """Add a new challenge."""
        coordinator = self._get_coordinator()
        errors = {}
        challenges_dict = coordinator.challenges_data

        chores_dict = coordinator.chores_data

        if user_input is not None:
            challenge_name = user_input[const.CFOF_CHALLENGES_INPUT_NAME].strip()
            if any(
                data[const.DATA_CHALLENGE_NAME] == challenge_name
                for data in challenges_dict.values()
            ):
                errors[const.CFOP_ERROR_CHALLENGE_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_CHALLENGE
                )
            else:
                _type = user_input[const.CFOF_CHALLENGES_INPUT_TYPE]

                chore_id = const.CONF_EMPTY
                if _type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                    c = (
                        user_input.get(const.CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID)
                        or const.CONF_EMPTY
                    )
                    if not c or c == const.CONF_NONE_TEXT:
                        errors[const.CFOP_ERROR_SELECT_CHORE_ID] = (
                            const.TRANS_KEY_CFOF_CHORE_MUST_BE_SELECTED
                        )
                    chore_id = c

                # Process start_date and end_date using the helper:
                start_date_input = user_input.get(
                    const.CFOF_CHALLENGES_INPUT_START_DATE
                )
                end_date_input = user_input.get(const.CFOF_CHALLENGES_INPUT_END_DATE)

                if start_date_input:
                    try:
                        start_date = fh.ensure_utc_datetime(self.hass, start_date_input)
                        start_dt = dt_util.parse_datetime(start_date)
                        if start_dt and start_dt < dt_util.utcnow():
                            errors[const.CFOP_ERROR_START_DATE] = (
                                const.TRANS_KEY_CFOF_START_DATE_IN_PAST
                            )
                    except (ValueError, TypeError, AttributeError):
                        errors[const.CFOP_ERROR_START_DATE] = (
                            const.TRANS_KEY_CFOF_INVALID_START_DATE
                        )
                        start_date = None
                else:
                    start_date = None

                if end_date_input:
                    try:
                        end_date = fh.ensure_utc_datetime(self.hass, end_date_input)
                        end_dt = dt_util.parse_datetime(end_date)
                        if end_dt and end_dt <= dt_util.utcnow():
                            errors[const.CFOP_ERROR_END_DATE] = (
                                const.TRANS_KEY_CFOF_END_DATE_IN_PAST
                            )
                        if start_date:
                            sdt = dt_util.parse_datetime(start_date)
                            if sdt and end_dt and end_dt <= sdt:
                                errors[const.CFOP_ERROR_END_DATE] = (
                                    const.TRANS_KEY_CFOF_END_DATE_NOT_AFTER_START_DATE
                                )
                    except (ValueError, TypeError, AttributeError):
                        errors[const.CFOP_ERROR_END_DATE] = (
                            const.TRANS_KEY_CFOF_INVALID_END_DATE
                        )
                        end_date = None
                else:
                    end_date = None

                if not errors:
                    # Convert kid names to internal IDs for storage
                    coordinator = self._get_coordinator()
                    assigned_kids_names = user_input[
                        const.CFOF_CHALLENGES_INPUT_ASSIGNED_KIDS
                    ]
                    kids_dict = {
                        kid[const.DATA_KID_NAME]: kid[const.DATA_KID_INTERNAL_ID]
                        for kid in coordinator.data.get(const.DATA_KIDS, [])
                    }
                    assigned_kids_ids = [
                        kids_dict.get(name, name) for name in assigned_kids_names
                    ]

                    internal_id = user_input.get(
                        const.CFOF_GLOBAL_INPUT_INTERNAL_ID, str(uuid.uuid4())
                    )
                    new_challenge_data = {
                        const.DATA_CHALLENGE_NAME: challenge_name,
                        const.DATA_CHALLENGE_DESCRIPTION: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_DESCRIPTION, const.CONF_EMPTY
                        ),
                        const.DATA_CHALLENGE_LABELS: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_LABELS, []
                        ),
                        const.DATA_CHALLENGE_ICON: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_ICON,
                            const.DEFAULT_CHALLENGES_ICON,
                        ),
                        const.DATA_CHALLENGE_ASSIGNED_KIDS: assigned_kids_ids,
                        const.DATA_CHALLENGE_TYPE: _type,
                        const.DATA_CHALLENGE_SELECTED_CHORE_ID: chore_id,
                        const.DATA_CHALLENGE_CRITERIA: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_CRITERIA, const.CONF_EMPTY
                        ).strip(),
                        const.DATA_CHALLENGE_TARGET_VALUE: user_input[
                            const.CFOF_CHALLENGES_INPUT_TARGET_VALUE
                        ],
                        const.DATA_CHALLENGE_REWARD_POINTS: user_input[
                            const.CFOF_CHALLENGES_INPUT_REWARD_POINTS
                        ],
                        const.DATA_CHALLENGE_START_DATE: start_date,
                        const.DATA_CHALLENGE_END_DATE: end_date,
                        const.DATA_CHALLENGE_INTERNAL_ID: internal_id,
                        const.DATA_CHALLENGE_PROGRESS: {},
                    }
                    coordinator._create_challenge(internal_id, new_challenge_data)
                    coordinator._persist()
                    coordinator.async_update_listeners()
                    const.LOGGER.debug(
                        "DEBUG: Added Challenge '%s' with ID: %s",
                        challenge_name,
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }
        challenge_schema = fh.build_challenge_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=user_input
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_CHALLENGE,
            data_schema=challenge_schema,
            errors=errors,
        )

    # ------------------ EDIT ENTITY ------------------
    async def async_step_edit_kid(self, user_input=None):
        """Edit an existing kid."""
        coordinator = self._get_coordinator()

        errors = {}
        kids_dict = coordinator.kids_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in kids_dict:
            const.LOGGER.error(
                "ERROR: Edit Kid - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_KID)

        kid_data = kids_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_KIDS_INPUT_KID_NAME].strip()
            ha_user_id = (
                user_input.get(const.CFOF_KIDS_INPUT_HA_USER) or const.CONF_EMPTY
            )
            enable_notifications = user_input.get(
                const.CFOF_KIDS_INPUT_ENABLE_MOBILE_NOTIFICATIONS, True
            )
            mobile_notify_service = (
                user_input.get(const.CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE)
                or const.CONF_EMPTY
            )
            use_persistent = user_input.get(
                const.CFOF_KIDS_INPUT_ENABLE_PERSISTENT_NOTIFICATIONS, True
            )

            dashboard_language = user_input.get(
                const.CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE,
                const.DEFAULT_DASHBOARD_LANGUAGE,
            )

            # Check for duplicate names excluding current kid
            if any(
                data[const.DATA_KID_NAME] == new_name and eid != internal_id
                for eid, data in kids_dict.items()
            ):
                errors[const.CFOP_ERROR_KID_NAME] = const.TRANS_KEY_CFOF_DUPLICATE_KID
            else:
                # Build update data
                updated_kid_data = {
                    const.DATA_KID_NAME: new_name,
                    const.DATA_KID_HA_USER_ID: ha_user_id,
                    const.DATA_KID_ENABLE_NOTIFICATIONS: enable_notifications,
                    const.DATA_KID_MOBILE_NOTIFY_SERVICE: mobile_notify_service,
                    const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS: use_persistent,
                    const.DATA_KID_DASHBOARD_LANGUAGE: dashboard_language,
                }

                # Update via coordinator
                coordinator.update_kid_entity(internal_id, updated_kid_data)

                const.LOGGER.debug(
                    "DEBUG: Edited Kid '%s' with ID: %s", new_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()
        schema = await fh.build_kid_schema(
            self.hass,
            users=users,
            default_kid_name=kid_data[const.DATA_KID_NAME],
            default_ha_user_id=kid_data.get(const.DATA_KID_HA_USER_ID),
            default_enable_mobile_notifications=kid_data.get(
                const.DATA_KID_ENABLE_NOTIFICATIONS, True
            ),
            default_mobile_notify_service=kid_data.get(
                const.DATA_KID_MOBILE_NOTIFY_SERVICE
            ),
            default_enable_persistent_notifications=kid_data.get(
                const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS, True
            ),
            default_dashboard_language=kid_data.get(
                const.DATA_KID_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            ),
            internal_id=internal_id,
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_KID, data_schema=schema, errors=errors
        )

    async def async_step_edit_parent(self, user_input=None):
        """Edit an existing parent."""
        coordinator = self._get_coordinator()
        errors = {}
        parents_dict = coordinator.parents_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in parents_dict:
            const.LOGGER.error(
                "ERROR: Edit Parent - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PARENT)

        parent_data = parents_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_PARENTS_INPUT_NAME].strip()
            ha_user_id = (
                user_input.get(const.CFOF_PARENTS_INPUT_HA_USER) or const.CONF_EMPTY
            )
            associated_kids = user_input.get(
                const.CFOF_PARENTS_INPUT_ASSOCIATED_KIDS, []
            )
            enable_notifications = user_input.get(
                const.CFOF_PARENTS_INPUT_ENABLE_MOBILE_NOTIFICATIONS, True
            )
            mobile_notify_service = (
                user_input.get(const.CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE)
                or const.CONF_EMPTY
            )
            use_persistent = user_input.get(
                const.CFOF_PARENTS_INPUT_ENABLE_PERSISTENT_NOTIFICATIONS, True
            )

            # Check for duplicate names excluding current parent
            if any(
                data[const.DATA_PARENT_NAME] == new_name and eid != internal_id
                for eid, data in parents_dict.items()
            ):
                errors[const.CFPO_ERROR_PARENT_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_PARENT
                )
            else:
                updated_parent_data = {
                    const.DATA_PARENT_NAME: new_name,
                    const.DATA_PARENT_HA_USER_ID: ha_user_id,
                    const.DATA_PARENT_ASSOCIATED_KIDS: associated_kids,
                    const.DATA_PARENT_ENABLE_NOTIFICATIONS: enable_notifications,
                    const.DATA_PARENT_MOBILE_NOTIFY_SERVICE: mobile_notify_service,
                    const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS: use_persistent,
                }

                coordinator.update_parent_entity(internal_id, updated_parent_data)

                const.LOGGER.debug(
                    "DEBUG: Edited Parent '%s' with ID: %s", new_name, internal_id
                )
                return await self.async_step_init()

        # Retrieve HA users and existing kids for linking
        users = await self.hass.auth.async_get_users()
        kids_dict = {
            kid_data[const.DATA_KID_NAME]: kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
        }

        parent_schema = fh.build_parent_schema(
            self.hass,
            users=users,
            kids_dict=kids_dict,
            default_parent_name=parent_data[const.DATA_PARENT_NAME],
            default_ha_user_id=parent_data.get(const.DATA_PARENT_HA_USER_ID),
            default_associated_kids=parent_data.get(
                const.DATA_PARENT_ASSOCIATED_KIDS, []
            ),
            default_enable_mobile_notifications=parent_data.get(
                const.DATA_PARENT_ENABLE_NOTIFICATIONS, True
            ),
            default_mobile_notify_service=parent_data.get(
                const.DATA_PARENT_MOBILE_NOTIFY_SERVICE
            ),
            default_enable_persistent_notifications=parent_data.get(
                const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, True
            ),
            internal_id=internal_id,
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_PARENT,
            data_schema=parent_schema,
            errors=errors,
        )

    async def async_step_edit_chore(self, user_input=None):
        """Edit an existing chore."""
        coordinator = self._get_coordinator()
        errors = {}
        chores_dict = coordinator.chores_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in chores_dict:
            const.LOGGER.error(
                "ERROR: Edit Chore - Invalid Internal ID '%s'", internal_id
            )
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
                cid: cdata for cid, cdata in chores_dict.items()
                if cid != internal_id
            }

            # Build and validate chore data using helper function
            chore_data_dict, errors = fh.build_chores_data(
                self.hass, user_input, kids_dict, chores_for_validation
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

            # Update chore and check if assigned kids changed
            assignments_changed = coordinator.update_chore_entity(
                internal_id, updated_chore_data
            )

            new_name = updated_chore_data.get(
                const.DATA_CHORE_NAME,
                chore_data.get(const.DATA_CHORE_NAME),
            )
            const.LOGGER.debug(
                "DEBUG: Edited Chore '%s' with ID: %s", new_name, internal_id
            )

            # Only reload if assignments changed (entities added/removed)
            if assignments_changed:
                const.LOGGER.debug(
                    "DEBUG: Chore assignments changed, marking reload needed"
                )
                self._mark_reload_needed()

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

        if existing_due_str:
            try:
                # Attempt to parse using dt_util or fallback to fromisoformat
                parsed_date = dt_util.parse_datetime(
                    existing_due_str
                ) or datetime.datetime.fromisoformat(existing_due_str)
                # Convert to the required format for DateTimeSelector
                existing_due_date = dt_util.as_local(parsed_date).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                const.LOGGER.debug(
                    "DEBUG: Processed existing_due_date for DateTimeSelector: %s",
                    existing_due_date,
                )
            except ValueError as e:
                const.LOGGER.error(
                    "ERROR: Failed to parse existing_due_date '%s': %s",
                    existing_due_str,
                    e,
                )

        # Convert assigned_kids from internal_ids to names for display
        assigned_kids_ids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
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

    async def async_step_edit_reward(self, user_input=None):
        """Edit an existing reward."""
        coordinator = self._get_coordinator()
        errors = {}
        rewards_dict = coordinator.rewards_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in rewards_dict:
            const.LOGGER.error(
                "ERROR: Edit Reward - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_REWARD)

        reward_data = rewards_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_REWARDS_INPUT_NAME].strip()

            # Check for duplicate names excluding current reward
            if any(
                data[const.DATA_REWARD_NAME] == new_name and eid != internal_id
                for eid, data in rewards_dict.items()
            ):
                errors[const.CFOP_ERROR_REWARD_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_REWARD
                )
            else:
                updated_reward_data = {
                    const.DATA_REWARD_NAME: new_name,
                    const.DATA_REWARD_COST: user_input[const.CFOF_REWARDS_INPUT_COST],
                    const.DATA_REWARD_DESCRIPTION: user_input.get(
                        const.CFOF_REWARDS_INPUT_DESCRIPTION, const.CONF_EMPTY
                    ),
                    const.DATA_REWARD_LABELS: user_input.get(
                        const.CFOF_REWARDS_INPUT_LABELS, []
                    ),
                    const.DATA_REWARD_ICON: user_input.get(
                        const.CFOF_REWARDS_INPUT_ICON, const.CONF_EMPTY
                    ),
                }

                coordinator.update_reward_entity(internal_id, updated_reward_data)

                const.LOGGER.debug(
                    "DEBUG: Edited Reward '%s' with ID: %s", new_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_reward_schema(default=reward_data)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_REWARD,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_edit_penalty(self, user_input=None):
        """Edit an existing penalty."""
        coordinator = self._get_coordinator()
        errors = {}
        penalties_dict = coordinator.penalties_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in penalties_dict:
            const.LOGGER.error(
                "ERROR: Edit Penalty - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PENALTY)

        penalty_data = penalties_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_PENALTIES_INPUT_NAME].strip()
            penalty_points = user_input[const.CFOF_PENALTIES_INPUT_POINTS]

            # Check for duplicate names excluding current penalty
            if any(
                data[const.DATA_PENALTY_NAME] == new_name and eid != internal_id
                for eid, data in penalties_dict.items()
            ):
                errors[const.CFOP_ERROR_PENALTY_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_PENALTY
                )
            else:
                updated_penalty_data = {
                    const.DATA_PENALTY_NAME: new_name,
                    const.DATA_PENALTY_DESCRIPTION: user_input.get(
                        const.CFOF_PENALTIES_INPUT_DESCRIPTION, const.CONF_EMPTY
                    ),
                    const.DATA_PENALTY_LABELS: user_input.get(
                        const.CFOF_PENALTIES_INPUT_LABELS, []
                    ),
                    const.DATA_PENALTY_POINTS: -abs(
                        penalty_points
                    ),  # Ensure points are negative
                    const.DATA_PENALTY_ICON: user_input.get(
                        const.CFOF_PENALTIES_INPUT_ICON, const.CONF_EMPTY
                    ),
                }

                coordinator.update_penalty_entity(internal_id, updated_penalty_data)

                const.LOGGER.debug(
                    "DEBUG: Edited Penalty '%s' with ID: %s", new_name, internal_id
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

    async def async_step_edit_bonus(self, user_input=None):
        """Edit an existing bonus."""
        coordinator = self._get_coordinator()
        errors = {}
        bonuses_dict = coordinator.bonuses_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in bonuses_dict:
            const.LOGGER.error(
                "ERROR: Edit Bonus - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BONUS)

        bonus_data = bonuses_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_BONUSES_INPUT_NAME].strip()
            bonus_points = user_input[const.CFOF_BONUSES_INPUT_POINTS]

            # Check for duplicate names excluding current bonus
            if any(
                data[const.DATA_BONUS_NAME] == new_name and eid != internal_id
                for eid, data in bonuses_dict.items()
            ):
                errors[const.CFOP_ERROR_BONUS_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_BONUS
                )
            else:
                updated_bonus_data = {
                    const.DATA_BONUS_NAME: new_name,
                    const.DATA_BONUS_DESCRIPTION: user_input.get(
                        const.CFOF_BONUSES_INPUT_DESCRIPTION, const.CONF_EMPTY
                    ),
                    const.DATA_BONUS_LABELS: user_input.get(
                        const.CFOF_BONUSES_INPUT_LABELS, []
                    ),
                    const.DATA_BONUS_POINTS: abs(
                        bonus_points
                    ),  # Ensure points are positive
                    const.DATA_BONUS_ICON: user_input.get(
                        const.CFOF_BONUSES_INPUT_ICON, const.CONF_EMPTY
                    ),
                }

                coordinator.update_bonus_entity(internal_id, updated_bonus_data)

                const.LOGGER.debug(
                    "DEBUG: Edited Bonus '%s' with ID: %s", new_name, internal_id
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

    async def async_step_edit_achievement(self, user_input=None):
        """Edit an existing achievement."""
        coordinator = self._get_coordinator()
        errors = {}
        achievements_dict = coordinator.achievements_data

        internal_id = self.context.get(const.DATA_INTERNAL_ID)
        if not internal_id or internal_id not in achievements_dict:
            const.LOGGER.error(
                "ERROR: Edit Achievement - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT)

        achievement_data = achievements_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_ACHIEVEMENTS_INPUT_NAME].strip()
            if any(
                data[const.DATA_ACHIEVEMENT_NAME] == new_name and eid != internal_id
                for eid, data in achievements_dict.items()
            ):
                errors[const.CFOP_ERROR_ACHIEVEMENT_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_ACHIEVEMENT
                )
            else:
                _type = user_input[const.CFOF_ACHIEVEMENTS_INPUT_TYPE]

                chore_id = const.CONF_EMPTY
                if _type == const.ACHIEVEMENT_TYPE_STREAK:
                    c = (
                        user_input.get(const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID)
                        or const.CONF_EMPTY
                    )
                    if not c or c == const.CONF_NONE_TEXT:
                        errors[const.CFOP_ERROR_SELECT_CHORE_ID] = (
                            const.TRANS_KEY_CFOF_CHORE_MUST_BE_SELECTED
                        )
                    chore_id = c

                if not errors:
                    # Convert kid names to internal IDs for storage
                    coordinator = self._get_coordinator()
                    assigned_kids_names = user_input[
                        const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_KIDS
                    ]
                    kids_dict = {
                        kid[const.DATA_KID_NAME]: kid[const.DATA_KID_INTERNAL_ID]
                        for kid in coordinator.data.get(const.DATA_KIDS, [])
                    }
                    assigned_kids_ids = [
                        kids_dict.get(name, name) for name in assigned_kids_names
                    ]

                    updated_achievement_data = {
                        const.DATA_ACHIEVEMENT_NAME: new_name,
                        const.DATA_ACHIEVEMENT_DESCRIPTION: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION, const.CONF_EMPTY
                        ),
                        const.DATA_ACHIEVEMENT_LABELS: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_LABELS, []
                        ),
                        const.DATA_ACHIEVEMENT_ICON: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_ICON, const.CONF_EMPTY
                        ),
                        const.DATA_ACHIEVEMENT_ASSIGNED_KIDS: assigned_kids_ids,
                        const.DATA_ACHIEVEMENT_TYPE: _type,
                        const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: chore_id,
                        const.DATA_ACHIEVEMENT_CRITERIA: user_input.get(
                            const.CFOF_ACHIEVEMENTS_INPUT_CRITERIA, const.CONF_EMPTY
                        ).strip(),
                        const.DATA_ACHIEVEMENT_TARGET_VALUE: user_input[
                            const.CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE
                        ],
                        const.DATA_ACHIEVEMENT_REWARD_POINTS: user_input[
                            const.CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS
                        ],
                    }

                    coordinator.update_achievement_entity(
                        internal_id, updated_achievement_data
                    )

                    const.LOGGER.debug(
                        "DEBUG: Edited Achievement '%s' with ID: %s",
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

    async def async_step_edit_challenge(self, user_input=None):
        """Edit an existing challenge."""
        coordinator = self._get_coordinator()
        errors = {}
        challenges_dict = coordinator.challenges_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in challenges_dict:
            const.LOGGER.error(
                "ERROR: Edit Challenge - Invalid Internal ID '%s'", internal_id
            )
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

            # Convert stored start/end dates to a display format (e.g. local time string)
            default_data = {
                **challenge_data,
                const.DATA_CHALLENGE_START_DATE: challenge_data.get(
                    const.DATA_CHALLENGE_START_DATE
                )
                and dt_util.as_local(
                    dt_util.parse_datetime(  # type: ignore[arg-type]
                        challenge_data[const.DATA_CHALLENGE_START_DATE]
                    )
                ).strftime("%Y-%m-%d %H:%M:%S"),
                const.DATA_CHALLENGE_END_DATE: challenge_data.get(
                    const.DATA_CHALLENGE_END_DATE
                )
                and dt_util.as_local(
                    dt_util.parse_datetime(  # type: ignore[arg-type]
                        challenge_data[const.DATA_CHALLENGE_END_DATE]
                    )
                ).strftime("%Y-%m-%d %H:%M:%S"),
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

        start_date_input = user_input.get(const.CFOF_CHALLENGES_INPUT_START_DATE)
        if start_date_input:
            try:
                new_start_date = fh.ensure_utc_datetime(self.hass, start_date_input)
                start_dt = dt_util.parse_datetime(new_start_date)
                if start_dt and start_dt < dt_util.utcnow():
                    errors[const.CFOP_ERROR_START_DATE] = (
                        const.TRANS_KEY_CFOF_START_DATE_IN_PAST
                    )
            except (ValueError, TypeError, AttributeError):
                errors[const.CFOP_ERROR_START_DATE] = (
                    const.TRANS_KEY_CFOF_INVALID_START_DATE
                )
                new_start_date = None
        else:
            new_start_date = None

        end_date_input = user_input.get(const.CFOF_CHALLENGES_INPUT_END_DATE)
        if end_date_input:
            try:
                new_end_date = fh.ensure_utc_datetime(self.hass, end_date_input)
                end_dt = dt_util.parse_datetime(new_end_date)

                if end_dt and end_dt <= dt_util.utcnow():
                    errors[const.CFOP_ERROR_END_DATE] = (
                        const.TRANS_KEY_CFOF_END_DATE_IN_PAST
                    )

                if new_start_date:
                    sdt = dt_util.parse_datetime(new_start_date)
                    if sdt and end_dt and end_dt <= sdt:
                        errors[const.CFOP_ERROR_END_DATE] = (
                            const.TRANS_KEY_CFOF_END_DATE_NOT_AFTER_START_DATE
                        )
            except (ValueError, TypeError, AttributeError):
                errors[const.CFOP_ERROR_END_DATE] = (
                    const.TRANS_KEY_CFOF_INVALID_END_DATE
                )
                new_end_date = None
        else:
            new_end_date = None

        if user_input is not None:
            new_name = user_input[const.CFOF_CHALLENGES_INPUT_NAME].strip()
            if any(
                data[const.DATA_CHALLENGE_NAME] == new_name and eid != internal_id
                for eid, data in challenges_dict.items()
            ):
                errors[const.CFOP_ERROR_CHALLENGE_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_CHALLENGE
                )
            else:
                _type = user_input[const.CFOF_CHALLENGES_INPUT_TYPE]

                chore_id = const.CONF_EMPTY
                if _type == const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW:
                    c = (
                        user_input.get(const.CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID)
                        or const.CONF_EMPTY
                    )
                    if not c or c == const.CONF_NONE_TEXT:
                        errors[const.CFOP_ERROR_SELECT_CHORE_ID] = (
                            const.TRANS_KEY_CFOF_CHORE_MUST_BE_SELECTED
                        )
                    chore_id = c

                if not errors:
                    # Convert kid names to internal IDs for storage
                    coordinator = self._get_coordinator()
                    assigned_kids_names = user_input[
                        const.CFOF_CHALLENGES_INPUT_ASSIGNED_KIDS
                    ]
                    kids_dict = {
                        kid[const.DATA_KID_NAME]: kid[const.DATA_KID_INTERNAL_ID]
                        for kid in coordinator.data.get(const.DATA_KIDS, [])
                    }
                    assigned_kids_ids = [
                        kids_dict.get(name, name) for name in assigned_kids_names
                    ]

                    updated_challenge_data = {
                        const.DATA_CHALLENGE_NAME: new_name,
                        const.DATA_CHALLENGE_DESCRIPTION: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_DESCRIPTION, const.CONF_EMPTY
                        ),
                        const.DATA_CHALLENGE_LABELS: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_LABELS, []
                        ),
                        const.DATA_CHALLENGE_ICON: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_ICON, const.CONF_EMPTY
                        ),
                        const.DATA_CHALLENGE_ASSIGNED_KIDS: assigned_kids_ids,
                        const.DATA_CHALLENGE_TYPE: _type,
                        const.DATA_CHALLENGE_SELECTED_CHORE_ID: chore_id,
                        const.DATA_CHALLENGE_CRITERIA: user_input.get(
                            const.CFOF_CHALLENGES_INPUT_CRITERIA, const.CONF_EMPTY
                        ).strip(),
                        const.DATA_CHALLENGE_TARGET_VALUE: user_input[
                            const.CFOF_CHALLENGES_INPUT_TARGET_VALUE
                        ],
                        const.DATA_CHALLENGE_REWARD_POINTS: user_input[
                            const.CFOF_CHALLENGES_INPUT_REWARD_POINTS
                        ],
                        const.DATA_CHALLENGE_START_DATE: new_start_date,
                        const.DATA_CHALLENGE_END_DATE: new_end_date,
                    }

                    coordinator.update_challenge_entity(
                        internal_id, updated_challenge_data
                    )

                    const.LOGGER.debug(
                        "DEBUG: Edited Challenge '%s' with ID: %s",
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

        default_data = {
            **challenge_data,
            const.DATA_CHALLENGE_START_DATE: new_start_date,
            const.DATA_CHALLENGE_END_DATE: new_end_date,
        }
        challenge_schema = fh.build_challenge_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=default_data
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHALLENGE,
            data_schema=challenge_schema,
            errors=errors,
        )

    # ------------------ DELETE ENTITY ------------------
    async def async_step_delete_kid(self, user_input=None):
        """Delete a kid."""
        coordinator = self._get_coordinator()
        kids_dict = coordinator.kids_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in kids_dict:
            const.LOGGER.error(
                "ERROR: Delete Kid - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_KID)

        kid_name = kids_dict[internal_id][const.DATA_KID_NAME]

        if user_input is not None:
            coordinator.delete_kid_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Kid '%s' with ID: %s", kid_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_KID,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_KID_NAME: kid_name
            },
        )

    async def async_step_delete_parent(self, user_input=None):
        """Delete a parent."""
        coordinator = self._get_coordinator()
        parents_dict = coordinator.parents_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in parents_dict:
            const.LOGGER.error(
                "ERROR: Delete Parent - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PARENT)

        parent_name = parents_dict[internal_id][const.DATA_PARENT_NAME]

        if user_input is not None:
            coordinator.delete_parent_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Parent '%s' with ID: %s", parent_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_PARENT,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_PARENT_NAME: parent_name
            },
        )

    async def async_step_delete_chore(self, user_input=None):
        """Delete a chore."""
        coordinator = self._get_coordinator()
        chores_dict = coordinator.chores_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in chores_dict:
            const.LOGGER.error(
                "ERROR: Delete Chore - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHORE)

        chore_name = chores_dict[internal_id][const.DATA_CHORE_NAME]

        if user_input is not None:
            coordinator.delete_chore_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Chore '%s' with ID: %s", chore_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_CHORE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_CHORE_NAME: chore_name
            },
        )

    async def async_step_delete_badge(self, user_input=None):
        """Delete a badge."""
        coordinator = self._get_coordinator()
        badges_dict = coordinator.badges_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in badges_dict:
            const.LOGGER.error(
                "ERROR: Delete Badge - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE)

        badge_name = badges_dict[internal_id][const.DATA_BADGE_NAME]

        if user_input is not None:
            coordinator.delete_badge_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Badge '%s' with ID: %s", badge_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BADGE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_BADGE_NAME: badge_name
            },
        )

    async def async_step_delete_reward(self, user_input=None):
        """Delete a reward."""
        coordinator = self._get_coordinator()
        rewards_dict = coordinator.rewards_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in rewards_dict:
            const.LOGGER.error(
                "ERROR: Delete Reward - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_REWARD)

        reward_name = rewards_dict[internal_id][const.DATA_REWARD_NAME]

        if user_input is not None:
            coordinator.delete_reward_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Reward '%s' with ID: %s", reward_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_REWARD,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_REWARD_NAME: reward_name
            },
        )

    async def async_step_delete_penalty(self, user_input=None):
        """Delete a penalty."""
        coordinator = self._get_coordinator()
        penalties_dict = coordinator.penalties_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in penalties_dict:
            const.LOGGER.error(
                "ERROR: Delete Penalty - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PENALTY)

        penalty_name = penalties_dict[internal_id][const.DATA_PENALTY_NAME]

        if user_input is not None:
            coordinator.delete_penalty_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Penalty '%s' with ID: %s", penalty_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_PENALTY,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_PENALTY_NAME: penalty_name
            },
        )

    async def async_step_delete_achievement(self, user_input=None):
        """Delete an achievement."""
        coordinator = self._get_coordinator()
        achievements_dict = coordinator.achievements_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in achievements_dict:
            const.LOGGER.error(
                "ERROR: Delete Achievement - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT)

        achievement_name = achievements_dict[internal_id][const.DATA_ACHIEVEMENT_NAME]

        if user_input is not None:
            coordinator.delete_achievement_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Achievement '%s' with ID: %s",
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

    async def async_step_delete_challenge(self, user_input=None):
        """Delete a challenge."""
        coordinator = self._get_coordinator()
        challenges_dict = coordinator.challenges_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in challenges_dict:
            const.LOGGER.error(
                "ERROR: Delete Challenge - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHALLENGE)

        challenge_name = challenges_dict[internal_id][const.DATA_CHALLENGE_NAME]

        if user_input is not None:
            coordinator.delete_challenge_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Challenge '%s' with ID: %s", challenge_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_CHALLENGE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_CHALLENGE_NAME: challenge_name
            },
        )

    async def async_step_delete_bonus(self, user_input=None):
        """Delete a bonus."""
        coordinator = self._get_coordinator()
        bonuses_dict = coordinator.bonuses_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in bonuses_dict:
            const.LOGGER.error(
                "ERROR: Delete Bonus - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BONUS)

        bonus_name = bonuses_dict[internal_id][const.DATA_BONUS_NAME]

        if user_input is not None:
            coordinator.delete_bonus_entity(internal_id)

            const.LOGGER.debug(
                "DEBUG: Deleted Bonus '%s' with ID: %s", bonus_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BONUS,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_BONUS_NAME: bonus_name
            },
        )

    # ------------------ GENERAL OPTIONS ------------------
    async def async_step_manage_general_options(self, user_input=None):
        """Manage general options: points adjust values and update interval."""
        if user_input is not None:
            # Get the raw text from the multiline text area.
            points_str = user_input.get(
                const.CONF_POINTS_ADJUST_VALUES, const.CONF_EMPTY
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
                const.CONF_UPDATE_INTERVAL
            )
            # update calendar show period
            self._entry_options[const.CONF_CALENDAR_SHOW_PERIOD] = user_input.get(
                const.CONF_CALENDAR_SHOW_PERIOD
            )
            # Update retention periods
            self._entry_options[const.CONF_RETENTION_DAILY] = user_input.get(
                const.CONF_RETENTION_DAILY
            )
            self._entry_options[const.CONF_RETENTION_WEEKLY] = user_input.get(
                const.CONF_RETENTION_WEEKLY
            )
            self._entry_options[const.CONF_RETENTION_MONTHLY] = user_input.get(
                const.CONF_RETENTION_MONTHLY
            )
            self._entry_options[const.CONF_RETENTION_YEARLY] = user_input.get(
                const.CONF_RETENTION_YEARLY
            )
            const.LOGGER.debug(
                "DEBUG: General Options Updated: Points Adjust Values=%s, "
                "Update Interval=%s, Calendar Period to Show=%s, "
                "Retention Daily=%s, Retention Weekly=%s, "
                "Retention Monthly=%s, Retention Yearly=%s",
                self._entry_options.get(const.CONF_POINTS_ADJUST_VALUES),
                self._entry_options.get(const.CONF_UPDATE_INTERVAL),
                self._entry_options.get(const.CONF_CALENDAR_SHOW_PERIOD),
                self._entry_options.get(const.CONF_RETENTION_DAILY),
                self._entry_options.get(const.CONF_RETENTION_WEEKLY),
                self._entry_options.get(const.CONF_RETENTION_MONTHLY),
                self._entry_options.get(const.CONF_RETENTION_YEARLY),
            )
            await self._update_system_settings_and_reload()
            return await self.async_step_init()

        general_schema = fh.build_general_options_schema(self._entry_options)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_MANAGE_GENERAL_OPTIONS,
            data_schema=general_schema,
            description_placeholders={},
        )

    # ------------------ HELPER METHODS ------------------
    def _mark_reload_needed(self):
        """Mark that a reload is needed after the current flow completes.

        When entities (rewards, bonuses, chores, etc.) are added, edited, or deleted,
        the coordinator data is updated but new sensors are not automatically created.
        We defer the reload until the user returns to the main menu to avoid
        interrupting the flow mid-operation.
        """
        const.LOGGER.debug("DEBUG: Marking reload needed after entity change")
        self._reload_needed = True

    async def _reload_entry_after_entity_change(self):
        """Reload the config entry to recreate sensors.

        This is called when returning to the main menu after entity changes.
        After reload, triggers an immediate coordinator refresh so new entities get data.
        """
        const.LOGGER.debug(
            "DEBUG: Reloading entry after entity changes: %s",
            self.config_entry.entry_id,
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        const.LOGGER.debug("DEBUG: Entry reloaded successfully")

        # Trigger immediate coordinator refresh so new entities get data right away
        # instead of waiting for the next update interval
        coordinator = self._get_coordinator()
        if coordinator:
            const.LOGGER.debug(
                "DEBUG: Triggering immediate coordinator refresh after reload"
            )
            await coordinator.async_request_refresh()
            const.LOGGER.debug("DEBUG: Coordinator refresh completed")

    async def _update_system_settings_and_reload(self):
        """Update system settings in config and reload (for points_label, update_interval, etc.)."""
        new_data = dict(self.config_entry.data)
        new_data[const.DATA_LAST_CHANGE] = dt_util.utcnow().isoformat()

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data, options=self._entry_options
        )
        const.LOGGER.debug(
            "DEBUG: Updating system settings. Reloading entry: %s",
            self.config_entry.entry_id,
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        const.LOGGER.debug("DEBUG: System settings updated and KidsChores reloaded")
