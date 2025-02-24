# File: options_flow.py
"""Options Flow for the KidsChores integration, managing entities by internal_id.

Handles add/edit/delete operations with entities referenced internally by internal_id.
Ensures consistency and reloads the integration upon changes.
"""

import datetime
import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    ACHIEVEMENT_TYPE_STREAK,
    CONF_APPLICABLE_DAYS,
    CONF_ACHIEVEMENTS,
    CONF_BADGES,
    CONF_CHALLENGES,
    CONF_CHORES,
    CONF_KIDS,
    CONF_NOTIFY_ON_APPROVAL,
    CONF_NOTIFY_ON_CLAIM,
    CONF_NOTIFY_ON_DISAPPROVAL,
    CONF_PARENTS,
    CONF_PENALTIES,
    CONF_POINTS_ICON,
    CONF_POINTS_LABEL,
    CONF_REWARDS,
    CONF_SPOTLIGHTS,
    DEFAULT_APPLICABLE_DAYS,
    DEFAULT_NOTIFY_ON_APPROVAL,
    DEFAULT_NOTIFY_ON_CLAIM,
    DEFAULT_NOTIFY_ON_DISAPPROVAL,
    DEFAULT_POINTS_ICON,
    DEFAULT_POINTS_LABEL,
    DOMAIN,
    LOGGER,
)
from .flow_helpers import (
    build_points_schema,
    build_kid_schema,
    build_parent_schema,
    build_chore_schema,
    build_badge_schema,
    build_reward_schema,
    build_penalty_schema,
    build_achievement_schema,
    build_challenge_schema,
    ensure_utc_datetime,
    build_spotlight_schema,
)


def _ensure_str(value):
    """Convert anything to string safely."""
    if isinstance(value, dict):
        # Attempt to get a known key or fallback
        return str(value.get("value", next(iter(value.values()), "")))
    return str(value)


class KidsChoresOptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for adding/editing/deleting kids, chores, badges, rewards, penalties, and spotlights.

    Manages entities via internal_id for consistency and historical data preservation.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize the options flow."""
        self._entry_options = {}
        self._action = None
        self._entity_type = None

    async def async_step_init(self, user_input=None):
        """Display the main menu for the Options Flow.

        Add/Edit/Delete kid, chore, badge, reward, penalty, or done.
        """
        self._entry_options = dict(self.config_entry.options)

        if user_input is not None:
            selection = user_input["menu_selection"]
            if selection.startswith("manage_"):
                self._entity_type = selection.replace("manage_", "")
                # If user chose manage_points
                if self._entity_type == "points":
                    return await self.async_step_manage_points()
                # Else manage other entities
                return await self.async_step_manage_entity()
            elif selection == "done":
                return self.async_abort(reason="setup_complete")

        main_menu = [
            "manage_points",
            "manage_kid",
            "manage_parent",
            "manage_chore",
            "manage_badge",
            "manage_reward",
            "manage_penalty",
            "manage_spotlight",
            "manage_achievement",
            "manage_challenge",
            "done",
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("menu_selection"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=main_menu,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="main_menu",
                        )
                    )
                }
            ),
        )

    async def async_step_manage_points(self, user_input=None):
        """Let user edit the points label/icon after initial setup."""
        if user_input is not None:
            new_label = user_input.get(CONF_POINTS_LABEL, DEFAULT_POINTS_LABEL)
            new_icon = user_input.get(CONF_POINTS_ICON, DEFAULT_POINTS_ICON)

            self._entry_options = dict(self.config_entry.options)
            self._entry_options[CONF_POINTS_LABEL] = new_label
            self._entry_options[CONF_POINTS_ICON] = new_icon
            LOGGER.debug(
                "Before saving points, entry_options = %s", self._entry_options
            )
            await self._update_and_reload()

            return await self.async_step_init()

        # Get existing values from entry options
        current_label = self._entry_options.get(CONF_POINTS_LABEL, DEFAULT_POINTS_LABEL)
        current_icon = self._entry_options.get(CONF_POINTS_ICON, DEFAULT_POINTS_ICON)

        # Build the form
        points_schema = build_points_schema(
            default_label=current_label, default_icon=current_icon
        )

        return self.async_show_form(
            step_id="manage_points",
            data_schema=points_schema,
            description_placeholders={},
        )

    async def async_step_manage_entity(self, user_input=None):
        """Handle entity management."""
        if user_input is not None:
            self._manage_action = user_input["manage_action"]
            self._entry_options = dict(self.config_entry.options)

            if self._entity_type == "penalty":
                penalties_dict = self._entry_options.get(CONF_PENALTIES, {})
                if not penalties_dict and self._manage_action != "add":
                    return self.async_abort(reason="no_penalties")
            elif self._entity_type == "spotlight":
                spotlights_dict = self._entry_options.get(CONF_SPOTLIGHTS, {})
                if not spotlights_dict and self._manage_action != "add":
                    return self.async_abort(reason="no_spotlights")

            # Route to the corresponding step based on action
            if self._manage_action == "add":
                return await getattr(self, f"async_step_add_{self._entity_type}")()
            elif self._manage_action in ["edit", "delete"]:
                return await self.async_step_select_entity()
            elif self._manage_action == "back":
                return await self.async_step_init()

        # Define manage action choices
        manage_action_choices = [
            "add",
            "edit",
            "delete",
            "back",  # Option to go back to the main menu
        ]

        return self.async_show_form(
            step_id="manage_entity",
            data_schema=vol.Schema(
                {
                    vol.Required("manage_action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=manage_action_choices,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="manage_actions",
                        )
                    )
                }
            ),
            description_placeholders={"entity_type": self._entity_type},
        )

    async def async_step_select_entity(self, user_input=None):
        """Select an entity (kid, chore, etc.) to edit or delete based on internal_id."""
        if self._action not in ["edit", "delete"]:
            LOGGER.error("Invalid action '%s' for select_entity step", self._action)
            return self.async_abort(reason="invalid_action")

        entity_dict = self._get_entity_dict()
        entity_names = [data["name"] for data in entity_dict.values()]

        if user_input is not None:
            selected_name = _ensure_str(user_input["entity_name"])
            internal_id = next(
                (
                    eid
                    for eid, data in entity_dict.items()
                    if data["name"] == selected_name
                ),
                None,
            )
            if not internal_id:
                LOGGER.error("Selected entity '%s' not found", selected_name)
                return self.async_abort(reason="invalid_entity")

            # Store internal_id in context for later use
            self.context["internal_id"] = internal_id

            # Route to the corresponding edit/delete step
            return await getattr(
                self, f"async_step_{self._action}_{self._entity_type}"
            )()

        if not entity_names:
            return self.async_abort(reason=f"no_{self._entity_type}s")

        return self.async_show_form(
            step_id="select_entity",
            data_schema=vol.Schema(
                {
                    vol.Required("entity_name"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=entity_names,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    )
                }
            ),
            description_placeholders={
                "entity_type": self._entity_type,
                "action": self._action,
            },
        )

    def _get_entity_dict(self):
        """Retrieve the appropriate entity dictionary based on entity_type."""
        entity_type_to_conf = {
            "kid": CONF_KIDS,
            "parent": CONF_PARENTS,
            "chore": CONF_CHORES,
            "badge": CONF_BADGES,
            "reward": CONF_REWARDS,
            "penalty": CONF_PENALTIES,
            "achievement": CONF_ACHIEVEMENTS,
            "challenge": CONF_CHALLENGES,
            "spotlight": CONF_SPOTLIGHTS,
        }
        key = entity_type_to_conf.get(self._entity_type)
        if key is None:
            LOGGER.error(
                "Unknown entity_type '%s'. Cannot retrieve entity dictionary",
                self._entity_type,
            )
            return {}
        return self._entry_options.get(key, {})

    # ------------------ ADD ENTITY ------------------
    async def async_step_add_kid(self, user_input=None):
        """Add a new kid."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        kids_dict = self._entry_options.setdefault(CONF_KIDS, {})

        if user_input is not None:
            kid_name = user_input["kid_name"].strip()
            ha_user_id = user_input.get("ha_user") or ""
            enable_mobile_notifications = user_input.get(
                "enable_mobile_notifications", True
            )
            notify_service = user_input.get("mobile_notify_service") or ""
            enable_persist = user_input.get("enable_persistent_notifications", True)

            if any(kid_data["name"] == kid_name for kid_data in kids_dict.values()):
                errors["kid_name"] = "duplicate_kid"
            else:
                internal_id = user_input.get("internal_id", str(uuid.uuid4()))
                kids_dict[internal_id] = {
                    "name": kid_name,
                    "ha_user_id": ha_user_id,
                    "enable_notifications": enable_mobile_notifications,
                    "mobile_notify_service": notify_service,
                    "use_persistent_notifications": enable_persist,
                    "internal_id": internal_id,
                }
                self._entry_options[CONF_KIDS] = kids_dict

                LOGGER.debug("Added kid '%s' with ID: %s", kid_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()
        schema = build_kid_schema(
            self.hass,
            users=users,
            default_kid_name="",
            default_ha_user_id=None,
            default_enable_mobile_notifications=False,
            default_mobile_notify_service=None,
            default_enable_persistent_notifications=False,
        )
        return self.async_show_form(
            step_id="add_kid", data_schema=schema, errors=errors
        )

    async def async_step_add_parent(self, user_input=None):
        """Add a new parent."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        parents_dict = self._entry_options.setdefault(CONF_PARENTS, {})

        if user_input is not None:
            parent_name = user_input["parent_name"].strip()
            ha_user_id = user_input.get("ha_user_id") or ""
            associated_kids = user_input.get("associated_kids", [])
            enable_mobile_notifications = user_input.get(
                "enable_mobile_notifications", True
            )
            notify_service = user_input.get("mobile_notify_service") or ""
            enable_persist = user_input.get("enable_persistent_notifications", True)

            if any(
                parent_data["name"] == parent_name
                for parent_data in parents_dict.values()
            ):
                errors["parent_name"] = "duplicate_parent"
            else:
                internal_id = user_input.get("internal_id", str(uuid.uuid4()))
                parents_dict[internal_id] = {
                    "name": parent_name,
                    "ha_user_id": ha_user_id,
                    "associated_kids": associated_kids,
                    "enable_notifications": enable_mobile_notifications,
                    "mobile_notify_service": notify_service,
                    "use_persistent_notifications": enable_persist,
                    "internal_id": internal_id,
                }
                self._entry_options[CONF_PARENTS] = parents_dict

                LOGGER.debug("Added parent '%s' with ID: %s", parent_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Retrieve HA users and existing kids for linking
        users = await self.hass.auth.async_get_users()
        kids_dict = {
            kid_data["name"]: kid_id
            for kid_id, kid_data in self._entry_options.get(CONF_KIDS, {}).items()
        }

        parent_schema = build_parent_schema(
            self.hass,
            users=users,
            kids_dict=kids_dict,
            default_parent_name="",
            default_ha_user_id=None,
            default_associated_kids=[],
            default_enable_mobile_notifications=False,
            default_mobile_notify_service=None,
            default_enable_persistent_notifications=False,
            internal_id=None,
        )
        return self.async_show_form(
            step_id="add_parent", data_schema=parent_schema, errors=errors
        )

    async def async_step_add_chore(self, user_input=None):
        """Add a new chore."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        chores_dict = self._entry_options.setdefault(CONF_CHORES, {})

        if user_input is not None:
            chore_name = user_input["chore_name"].strip()
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if user_input.get("due_date"):
                raw_due = user_input["due_date"]
                try:
                    due_date_str = ensure_utc_datetime(self.hass, raw_due)
                    due_dt = dt_util.parse_datetime(due_date_str)
                    if due_dt and due_dt < dt_util.utcnow():
                        errors["due_date"] = "due_date_in_past"
                except ValueError:
                    errors["due_date"] = "invalid_due_date"
                    due_date_str = None
            else:
                due_date_str = None

            if any(
                chore_data["name"] == chore_name for chore_data in chores_dict.values()
            ):
                errors["chore_name"] = "duplicate_chore"

            if errors:
                kids_dict = {
                    data["name"]: eid
                    for eid, data in self._entry_options.get(CONF_KIDS, {}).items()
                }
                schema = build_chore_schema(kids_dict, default=user_input)
                return self.async_show_form(
                    step_id="add_chore", data_schema=schema, errors=errors
                )

            chores_dict[internal_id] = {
                "name": chore_name,
                "default_points": user_input["default_points"],
                "partial_allowed": user_input["partial_allowed"],
                "shared_chore": user_input["shared_chore"],
                "allow_multiple_claims_per_day": user_input[
                    "allow_multiple_claims_per_day"
                ],
                "assigned_kids": user_input["assigned_kids"],
                "description": user_input.get("chore_description", ""),
                "icon": user_input.get("icon", ""),
                "recurring_frequency": user_input.get("recurring_frequency", "none"),
                "due_date": due_date_str,
                "applicable_days": user_input.get(
                    CONF_APPLICABLE_DAYS, DEFAULT_APPLICABLE_DAYS
                ),
                "notify_on_claim": user_input.get(
                    CONF_NOTIFY_ON_CLAIM, DEFAULT_NOTIFY_ON_CLAIM
                ),
                "notify_on_approval": user_input.get(
                    CONF_NOTIFY_ON_APPROVAL, DEFAULT_NOTIFY_ON_APPROVAL
                ),
                "notify_on_disapproval": user_input.get(
                    CONF_NOTIFY_ON_DISAPPROVAL, DEFAULT_NOTIFY_ON_DISAPPROVAL
                ),
                "internal_id": internal_id,
            }
            self._entry_options[CONF_CHORES] = chores_dict

            LOGGER.debug("Added chore '%s' with ID: %s", chore_name, internal_id)
            LOGGER.debug(
                "Final stored 'due_date' for chore '%s': %s",
                chore_name,
                due_date_str,
            )
            await self._update_and_reload()
            return await self.async_step_init()

        # Use flow_helpers.build_chore_schema, passing current kids
        kids_dict = {
            data["name"]: eid
            for eid, data in self._entry_options.get(CONF_KIDS, {}).items()
        }
        schema = build_chore_schema(kids_dict)
        return self.async_show_form(
            step_id="add_chore", data_schema=schema, errors=errors
        )

    async def async_step_add_badge(self, user_input=None):
        """Add a new badge."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        badges_dict = self._entry_options.setdefault(CONF_BADGES, {})

        if user_input is not None:
            badge_name = user_input["badge_name"].strip()
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                badge_data["name"] == badge_name for badge_data in badges_dict.values()
            ):
                errors["badge_name"] = "duplicate_badge"
            else:
                badges_dict[internal_id] = {
                    "name": badge_name,
                    "threshold_type": user_input["threshold_type"],
                    "threshold_value": user_input["threshold_value"],
                    "points_multiplier": user_input["points_multiplier"],
                    "icon": user_input.get("icon", ""),
                    "internal_id": internal_id,
                    "description": user_input.get("badge_description", ""),
                }
                self._entry_options[CONF_BADGES] = badges_dict

                LOGGER.debug("Added badge '%s' with ID: %s", badge_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_badge_schema()
        return self.async_show_form(
            step_id="add_badge", data_schema=schema, errors=errors
        )

    async def async_step_add_reward(self, user_input=None):
        """Add a new reward."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        rewards_dict = self._entry_options.setdefault(CONF_REWARDS, {})

        if user_input is not None:
            reward_name = user_input["reward_name"].strip()
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                reward_data["name"] == reward_name
                for reward_data in rewards_dict.values()
            ):
                errors["reward_name"] = "duplicate_reward"
            else:
                rewards_dict[internal_id] = {
                    "name": reward_name,
                    "cost": user_input["reward_cost"],
                    "description": user_input.get("reward_description", ""),
                    "icon": user_input.get("icon", ""),
                    "internal_id": internal_id,
                }
                self._entry_options[CONF_REWARDS] = rewards_dict

                LOGGER.debug("Added reward '%s' with ID: %s", reward_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_reward_schema()
        return self.async_show_form(
            step_id="add_reward", data_schema=schema, errors=errors
        )

    async def async_step_add_penalty(self, user_input=None):
        """Add a new penalty."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        penalties_dict = self._entry_options.setdefault(CONF_PENALTIES, {})

        if user_input is not None:
            penalty_name = user_input["penalty_name"].strip()
            penalty_points = user_input["penalty_points"]
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                penalty_data["name"] == penalty_name
                for penalty_data in penalties_dict.values()
            ):
                errors["penalty_name"] = "duplicate_penalty"
            else:
                penalties_dict[internal_id] = {
                    "name": penalty_name,
                    "description": user_input.get("penalty_description", ""),
                    "points": -abs(penalty_points),  # Ensure points are negative
                    "icon": user_input.get("icon", ""),
                    "internal_id": internal_id,
                }
                self._entry_options[CONF_PENALTIES] = penalties_dict

                LOGGER.debug(
                    "Added penalty '%s' with ID: %s", penalty_name, internal_id
                )
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_penalty_schema()
        return self.async_show_form(
            step_id="add_penalty", data_schema=schema, errors=errors
        )

    async def async_step_add_achievement(self, user_input=None):
        """Add a new achievement."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        achievements_dict = self._entry_options.setdefault(CONF_ACHIEVEMENTS, {})

        chores_dict = self._entry_options.get(CONF_CHORES, {})

        if user_input is not None:
            achievement_name = user_input["name"].strip()
            if any(
                data["name"] == achievement_name for data in achievements_dict.values()
            ):
                errors["name"] = "duplicate_achievement"
            else:
                internal_id = user_input.get("internal_id", str(uuid.uuid4()))

                _type = user_input["type"]
                if _type == "chore":
                    chosen_chore_id = user_input.get("selected_chore_id")
                    final_criteria = chosen_chore_id
                else:
                    final_criteria = user_input.get("criteria", "")

                achievements_dict[internal_id] = {
                    "name": achievement_name,
                    "description": user_input.get("description", ""),
                    "icon": user_input.get("icon", ""),
                    "assigned_kids": user_input["assigned_kids"],
                    "type": _type,
                    "criteria": final_criteria,
                    "target_value": user_input["target_value"],
                    "reward_points": user_input["reward_points"],
                    "internal_id": internal_id,
                    "progress": {},
                }
                self._entry_options[CONF_ACHIEVEMENTS] = achievements_dict
                LOGGER.debug(
                    "Added achievement '%s' with ID: %s", achievement_name, internal_id
                )
                await self._update_and_reload()
                return await self.async_step_init()

        kids_dict = {
            kid_data["name"]: kid_id
            for kid_id, kid_data in self._entry_options.get(CONF_KIDS, {}).items()
        }
        achievement_schema = build_achievement_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=None
        )
        return self.async_show_form(
            step_id="add_achievement", data_schema=achievement_schema, errors=errors
        )

    async def async_step_add_challenge(self, user_input=None):
        """Add a new challenge."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        challenges_dict = self._entry_options.setdefault(CONF_CHALLENGES, {})

        chores_dict = self._entry_options.get(CONF_CHORES, {})

        if user_input is not None:
            challenge_name = user_input["name"].strip()
            if any(data["name"] == challenge_name for data in challenges_dict.values()):
                errors["name"] = "duplicate_challenge"
            else:
                internal_id = user_input.get("internal_id", str(uuid.uuid4()))

                _type = user_input["type"]
                if _type == "chore":
                    final_criteria = user_input.get("selected_chore_id")
                else:
                    final_criteria = user_input.get("criteria", "")

                # Process start_date and end_date using the helper:
                start_date_input = user_input.get("start_date")
                end_date_input = user_input.get("end_date")

                if start_date_input:
                    try:
                        start_date = ensure_utc_datetime(self.hass, start_date_input)
                        start_dt = dt_util.parse_datetime(start_date)
                        if start_dt and start_dt < dt_util.utcnow():
                            errors["start_date"] = "start_date_in_past"
                    except Exception:
                        errors["start_date"] = "invalid_start_date"
                        start_date = None
                else:
                    start_date = None

                if end_date_input:
                    try:
                        end_date = ensure_utc_datetime(self.hass, end_date_input)
                        end_dt = dt_util.parse_datetime(end_date)
                        if end_dt and end_dt <= dt_util.utcnow():
                            errors["end_date"] = "end_date_in_past"
                        if start_date:
                            sdt = dt_util.parse_datetime(start_date)
                            if sdt and end_dt and end_dt <= sdt:
                                errors["end_date"] = "end_date_not_after_start_date"
                    except Exception:
                        errors["end_date"] = "invalid_end_date"
                        end_date = None
                else:
                    end_date = None

            if errors:
                kids_dict = {
                    data["name"]: kid_id
                    for kid_id, data in self._entry_options.get(CONF_KIDS, {}).items()
                }
                schema = build_challenge_schema(
                    kids_dict=kids_dict, chores_dict=chores_dict, default=user_input
                )
                return self.async_show_form(
                    step_id="add_challenge", data_schema=schema, errors=errors
                )

            challenges_dict[internal_id] = {
                "name": challenge_name,
                "description": user_input.get("description", ""),
                "icon": user_input.get("icon", ""),
                "assigned_kids": user_input["assigned_kids"],
                "type": _type,
                "criteria": final_criteria,
                "target_value": user_input["target_value"],
                "reward_points": user_input["reward_points"],
                "start_date": start_date,
                "end_date": end_date,
                "internal_id": internal_id,
                "progress": {},
            }
            self._entry_options[CONF_CHALLENGES] = challenges_dict
            LOGGER.debug(
                "Added challenge '%s' with ID: %s", challenge_name, internal_id
            )
            await self._update_and_reload()
            return await self.async_step_init()
        kids_dict = {
            kid_data["name"]: kid_id
            for kid_id, kid_data in self._entry_options.get(CONF_KIDS, {}).items()
        }
        challenge_schema = build_challenge_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=None
        )
        return self.async_show_form(
            step_id="add_challenge", data_schema=challenge_schema, errors=errors
        )

    async def async_step_add_spotlight(self, user_input=None):
        """Add a new spotlight."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        spotlights_dict = self._entry_options.setdefault(CONF_SPOTLIGHTS, {})

        if user_input is not None:
            spotlight_name = user_input["spotlight_name"].strip()
            spotlight_points = user_input["spotlight_points"]
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                spotlight_data["name"] == spotlight_name
                for spotlight_data in spotlights_dict.values()
            ):
                errors["spotlight_name"] = "duplicate_spotlight"
            else:
                spotlights_dict[internal_id] = {
                    "name": spotlight_name,
                    "description": user_input.get("spotlight_description", ""),
                    "points": abs(spotlight_points),  # Ensure points are positive
                    "icon": user_input.get("icon", ""),
                    "internal_id": internal_id,
                }
                self._entry_options[CONF_SPOTLIGHTS] = spotlights_dict

                LOGGER.debug(
                    "Added spotlight '%s' with ID: %s", spotlight_name, internal_id
                )
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_spotlight_schema()
        return self.async_show_form(
            step_id="add_spotlight", data_schema=schema, errors=errors
        )

    # ------------------ EDIT ENTITY ------------------
    async def async_step_edit_kid(self, user_input=None):
        """Edit an existing kid."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        kids_dict = self._entry_options.get(CONF_KIDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in kids_dict:
            LOGGER.error("Edit kid: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_kid")

        kid_data = kids_dict[internal_id]

        if user_input is not None:
            new_name = user_input["kid_name"].strip()
            ha_user_id = user_input.get("ha_user") or ""
            enable_notifications = user_input.get("enable_mobile_notifications", True)
            mobile_notify_service = user_input.get("mobile_notify_service") or ""
            use_persistent = user_input.get("enable_persistent_notifications", True)

            # Check for duplicate names excluding current kid
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in kids_dict.items()
            ):
                errors["kid_name"] = "duplicate_kid"
            else:
                kid_data["name"] = new_name
                kid_data["ha_user_id"] = ha_user_id
                kid_data["enable_notifications"] = enable_notifications
                kid_data["mobile_notify_service"] = mobile_notify_service
                kid_data["use_persistent_notifications"] = use_persistent

                self._entry_options[CONF_KIDS] = kids_dict

                LOGGER.debug("Edited kid '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()
        schema = build_kid_schema(
            self.hass,
            users=users,
            default_kid_name=kid_data["name"],
            default_ha_user_id=kid_data.get("ha_user_id"),
            default_enable_mobile_notifications=kid_data.get(
                "enable_notifications", True
            ),
            default_mobile_notify_service=kid_data.get("mobile_notify_service"),
            default_enable_persistent_notifications=kid_data.get(
                "use_persistent_notifications", True
            ),
            internal_id=internal_id,
        )
        return self.async_show_form(
            step_id="edit_kid", data_schema=schema, errors=errors
        )

    async def async_step_edit_parent(self, user_input=None):
        """Edit an existing parent."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        parents_dict = self._entry_options.get(CONF_PARENTS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in parents_dict:
            LOGGER.error("Edit parent: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_parent")

        parent_data = parents_dict[internal_id]

        if user_input is not None:
            new_name = user_input["parent_name"].strip()
            ha_user_id = user_input.get("ha_user_id") or ""
            associated_kids = user_input.get("associated_kids", [])
            enable_notifications = user_input.get("enable_mobile_notifications", True)
            mobile_notify_service = user_input.get("mobile_notify_service") or ""
            use_persistent = user_input.get("enable_persistent_notifications", True)

            # Check for duplicate names excluding current parent
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in parents_dict.items()
            ):
                errors["parent_name"] = "duplicate_parent"
            else:
                parent_data["name"] = new_name
                parent_data["ha_user_id"] = ha_user_id
                parent_data["associated_kids"] = associated_kids
                parent_data["enable_notifications"] = enable_notifications
                parent_data["mobile_notify_service"] = mobile_notify_service
                parent_data["use_persistent_notifications"] = use_persistent

                self._entry_options[CONF_PARENTS] = parents_dict

                LOGGER.debug("Edited parent '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Retrieve HA users and existing kids for linking
        users = await self.hass.auth.async_get_users()
        kids_dict = {
            kid_data["name"]: kid_id
            for kid_id, kid_data in self._entry_options.get(CONF_KIDS, {}).items()
        }

        parent_schema = build_parent_schema(
            self.hass,
            users=users,
            kids_dict=kids_dict,
            default_parent_name=parent_data["name"],
            default_ha_user_id=parent_data.get("ha_user_id"),
            default_associated_kids=parent_data.get("associated_kids", []),
            default_enable_mobile_notifications=parent_data.get(
                "enable_notifications", True
            ),
            default_mobile_notify_service=parent_data.get("mobile_notify_service"),
            default_enable_persistent_notifications=parent_data.get(
                "use_persistent_notifications", True
            ),
            internal_id=internal_id,
        )
        return self.async_show_form(
            step_id="edit_parent", data_schema=parent_schema, errors=errors
        )

    async def async_step_edit_chore(self, user_input=None):
        """Edit an existing chore."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        chores_dict = self._entry_options.get(CONF_CHORES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in chores_dict:
            LOGGER.error("Edit chore: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_chore")

        chore_data = chores_dict[internal_id]

        if user_input is not None:
            new_name = user_input["chore_name"].strip()
            raw_due = user_input.get("due_date")

            # Check for duplicate names excluding current chore
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in chores_dict.items()
            ):
                errors["chore_name"] = "duplicate_chore"
            else:
                chore_data["name"] = new_name
                chore_data["description"] = user_input.get("chore_description", "")
                chore_data["default_points"] = user_input["default_points"]
                chore_data["shared_chore"] = user_input["shared_chore"]
                chore_data["partial_allowed"] = user_input["partial_allowed"]
                chore_data["allow_multiple_claims_per_day"] = user_input[
                    "allow_multiple_claims_per_day"
                ]
                chore_data["assigned_kids"] = user_input["assigned_kids"]
                chore_data["icon"] = user_input.get("icon", "")
                chore_data["recurring_frequency"] = user_input.get(
                    "recurring_frequency", "none"
                )
                if raw_due:
                    try:
                        if isinstance(raw_due, datetime.datetime):
                            parsed_due = raw_due
                        else:
                            parsed_due = dt_util.parse_datetime(
                                raw_due
                            ) or datetime.datetime.fromisoformat(raw_due)
                        due_utc = dt_util.as_utc(parsed_due)
                        if due_utc < dt_util.utcnow():
                            errors["due_date"] = "due_date_in_past"
                        else:
                            chore_data["due_date"] = due_utc.isoformat()
                    except Exception:
                        errors["due_date"] = "invalid_due_date"
                else:
                    chore_data["due_date"] = None
                    LOGGER.debug("No date/time provided; defaulting to None")

                chore_data["applicable_days"] = user_input.get("applicable_days", [])
                chore_data["notify_on_claim"] = user_input.get("notify_on_claim", True)
                chore_data["notify_on_approval"] = user_input.get(
                    "notify_on_approval", True
                )
                chore_data["notify_on_disapproval"] = user_input.get(
                    "notify_on_disapproval", True
                )

            if errors:
                kids_dict = {
                    data["name"]: eid
                    for eid, data in self._entry_options.get(CONF_KIDS, {}).items()
                }
                default_data = user_input.copy()
                return self.async_show_form(
                    step_id="edit_chore",
                    data_schema=build_chore_schema(
                        kids_dict, default={**chore_data, **default_data}
                    ),
                    errors=errors,
                )

            self._entry_options[CONF_CHORES] = chores_dict

            LOGGER.debug("Edited chore '%s' with ID: %s", new_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        # Use flow_helpers.build_chore_schema, passing current kids
        kids_dict = {
            data["name"]: eid
            for eid, data in self._entry_options.get(CONF_KIDS, {}).items()
        }

        # Convert stored string to datetime for DateTimeSelector
        existing_due_str = chore_data.get("due_date")
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
                LOGGER.debug(
                    "Processed existing_due_date for DateTimeSelector: %s",
                    existing_due_date,
                )
            except ValueError as e:
                LOGGER.error(
                    "Failed to parse existing_due_date '%s': %s", existing_due_str, e
                )

        schema = build_chore_schema(
            kids_dict, default={**chore_data, "due_date": existing_due_date}
        )
        return self.async_show_form(
            step_id="edit_chore", data_schema=schema, errors=errors
        )

    async def async_step_edit_badge(self, user_input=None):
        """Edit an existing badge."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        badges_dict = self._entry_options.get(CONF_BADGES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in badges_dict:
            LOGGER.error("Edit badge: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_badge")

        badge_data = badges_dict[internal_id]

        if user_input is not None:
            new_name = user_input["badge_name"].strip()

            # Check for duplicate names excluding current badge
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in badges_dict.items()
            ):
                errors["badge_name"] = "duplicate_badge"
            else:
                badge_data["name"] = new_name
                badge_data["threshold_type"] = user_input["threshold_type"]
                badge_data["threshold_value"] = user_input["threshold_value"]
                badge_data["points_multiplier"] = user_input["points_multiplier"]
                badge_data["icon"] = user_input.get("icon", "")
                badge_data["description"] = user_input["badge_description"]

                self._entry_options[CONF_BADGES] = badges_dict

                LOGGER.debug("Edited badge '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_badge_schema(default=badge_data)
        return self.async_show_form(
            step_id="edit_badge", data_schema=schema, errors=errors
        )

    async def async_step_edit_reward(self, user_input=None):
        """Edit an existing reward."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        rewards_dict = self._entry_options.get(CONF_REWARDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in rewards_dict:
            LOGGER.error("Edit reward: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_reward")

        reward_data = rewards_dict[internal_id]

        if user_input is not None:
            new_name = user_input["reward_name"].strip()

            # Check for duplicate names excluding current reward
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in rewards_dict.items()
            ):
                errors["reward_name"] = "duplicate_reward"
            else:
                reward_data["name"] = new_name
                reward_data["cost"] = user_input["reward_cost"]
                reward_data["description"] = user_input.get("reward_description", "")
                reward_data["icon"] = user_input.get("icon", "")

                self._entry_options[CONF_REWARDS] = rewards_dict

                LOGGER.debug("Edited reward '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_reward_schema(default=reward_data)
        return self.async_show_form(
            step_id="edit_reward", data_schema=schema, errors=errors
        )

    async def async_step_edit_penalty(self, user_input=None):
        """Edit an existing penalty."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        penalties_dict = self._entry_options.get(CONF_PENALTIES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in penalties_dict:
            LOGGER.error("Edit penalty: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_penalty")

        penalty_data = penalties_dict[internal_id]

        if user_input is not None:
            new_name = user_input["penalty_name"].strip()
            penalty_points = user_input["penalty_points"]

            # Check for duplicate names excluding current penalty
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in penalties_dict.items()
            ):
                errors["penalty_name"] = "duplicate_penalty"
            else:
                penalty_data["name"] = new_name
                penalty_data["description"] = user_input.get("penalty_description", "")
                penalty_data["points"] = -abs(
                    penalty_points
                )  # Ensure points are negative
                penalty_data["icon"] = user_input.get("icon", "")

                self._entry_options[CONF_PENALTIES] = penalties_dict

                LOGGER.debug("Edited penalty '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Prepare data for schema (convert points to positive for display)
        display_data = dict(penalty_data)
        display_data["penalty_points"] = abs(display_data["points"])
        schema = build_penalty_schema(default=display_data)
        return self.async_show_form(
            step_id="edit_penalty", data_schema=schema, errors=errors
        )

    async def async_step_edit_spotlight(self, user_input=None):
        """Edit an existing spotlight."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        spotlights_dict = self._entry_options.get(CONF_SPOTLIGHTS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in spotlights_dict:
            LOGGER.error("Edit spotlight: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_spotlight")

        spotlight_data = spotlights_dict[internal_id]

        if user_input is not None:
            new_name = user_input["spotlight_name"].strip()
            spotlight_points = user_input["spotlight_points"]

            # Check for duplicate names excluding current penalty
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in spotlights_dict.items()
            ):
                errors["spotlight_name"] = "duplicate_spotlight"
            else:
                spotlight_data["name"] = new_name
                spotlight_data["description"] = user_input.get("spotlight_description", "")
                spotlight_data["points"] = abs(
                    spotlight_points
                )  # Ensure points are positive
                spotlight_data["icon"] = user_input.get("icon", "")

                self._entry_options[CONF_SPOTLIGHTS] = spotlights_dict

                LOGGER.debug("Edited spotlight '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Prepare data for schema (convert points to positive for display)
        display_data = dict(penalty_data)
        display_data["spotlight_points"] = abs(display_data["points"])
        schema = build_spotlight_schema(default=display_data)
        return self.async_show_form(
            step_id="edit_spotlight", data_schema=schema, errors=errors
        )    

    async def async_step_edit_achievement(self, user_input=None):
        """Edit an existing achievement."""
        self._entry_options = dict(self.config_entry.options)

        errors = {}
        achievements_dict = self._entry_options.get(CONF_ACHIEVEMENTS, {})

        internal_id = self.context.get("internal_id")
        if not internal_id or internal_id not in achievements_dict:
            LOGGER.error("Edit achievement: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_achievement")

        achievement_data = achievements_dict[internal_id]

        if user_input is not None:
            new_name = user_input["name"].strip()
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in achievements_dict.items()
            ):
                errors["name"] = "duplicate_achievement"
            else:
                _type = user_input["type"]
                achievement_data["name"] = new_name
                achievement_data["description"] = user_input.get("description", "")
                achievement_data["icon"] = user_input.get("icon", "")
                achievement_data["assigned_kids"] = user_input["assigned_kids"]
                achievement_data["type"] = _type
                achievement_data["selected_chore_id"] = user_input.get(
                    "selected_chore_id", achievement_data.get("selected_chore_id", "")
                )
                achievement_data["criteria"] = user_input.get(
                    "criteria", achievement_data.get("criteria", "")
                )
                achievement_data["target_value"] = user_input["target_value"]
                achievement_data["reward_points"] = user_input["reward_points"]
                achievements_dict[internal_id] = achievement_data
                self._entry_options[CONF_ACHIEVEMENTS] = achievements_dict
                LOGGER.debug(
                    "Edited achievement '%s' with ID: %s", new_name, internal_id
                )
                await self._update_and_reload()
                return await self.async_step_init()

        kids_dict = {
            kid_data["name"]: kid_id
            for kid_id, kid_data in self._entry_options.get(CONF_KIDS, {}).items()
        }
        chores_dict = self._entry_options.get(CONF_CHORES, {})

        achievement_schema = build_achievement_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=achievement_data
        )
        return self.async_show_form(
            step_id="edit_achievement", data_schema=achievement_schema, errors=errors
        )

    async def async_step_edit_challenge(self, user_input=None):
        """Edit an existing challenge."""
        self._entry_options = dict(self.config_entry.options)
        errors = {}
        challenges_dict = self._entry_options.get(CONF_CHALLENGES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in challenges_dict:
            LOGGER.error("Edit challenge: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_challenge")

        challenge_data = challenges_dict[internal_id]

        if user_input is not None:
            new_name = user_input["name"].strip()
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in challenges_dict.items()
            ):
                errors["name"] = "duplicate_challenge"
            else:
                _type = user_input["type"]
                challenge_data["name"] = new_name
                challenge_data["description"] = user_input.get("description", "")
                challenge_data["icon"] = user_input.get("icon", "")
                challenge_data["assigned_kids"] = user_input["assigned_kids"]
                challenge_data["type"] = _type
                challenge_data["selected_chore_id"] = user_input.get(
                    "selected_chore_id", challenge_data.get("selected_chore_id", "")
                )

                challenge_data["criteria"] = user_input.get(
                    "criteria", challenge_data.get("criteria", "")
                )
                challenge_data["target_value"] = user_input["target_value"]
                challenge_data["reward_points"] = user_input["reward_points"]

                # Process start_date and end_date using ensure_utc_datetime:
                start_date_input = user_input.get("start_date")
                end_date_input = user_input.get("end_date")

                if start_date_input:
                    try:
                        start_date = ensure_utc_datetime(
                            self.hass, user_input["start_date"]
                        )
                        start_dt = dt_util.parse_datetime(start_date)
                        if start_dt and start_dt < dt_util.utcnow():
                            errors["start_date"] = "start_date_in_past"
                        else:
                            challenge_data["start_date"] = start_date
                    except Exception:
                        errors["start_date"] = "invalid_start_date"
                else:
                    challenge_data["start_date"] = None

                if end_date_input:
                    try:
                        end_date = ensure_utc_datetime(
                            self.hass, user_input["end_date"]
                        )
                        end_dt = dt_util.parse_datetime(end_date)
                        if end_dt and end_dt <= dt_util.utcnow():
                            errors["end_date"] = "end_date_in_past"
                        if challenge_data.get("start_date"):
                            sdt = dt_util.parse_datetime(challenge_data["start_date"])
                            if sdt and end_dt and end_dt <= sdt:
                                errors["end_date"] = "end_date_not_after_start_date"
                            else:
                                challenge_data["end_date"] = end_date
                        else:
                            challenge_data["end_date"] = end_date
                    except Exception:
                        errors["end_date"] = "invalid_end_date"
                else:
                    challenge_data["end_date"] = None

            if errors:
                kids_dict = {
                    data["name"]: kid_id
                    for kid_id, data in self._entry_options.get(CONF_KIDS, {}).items()
                }
                chores_dict = self._entry_options.get(CONF_CHORES, {})
                default_data = user_input.copy()
                return self.async_show_form(
                    step_id="edit_challenge",
                    data_schema=build_challenge_schema(
                        kids_dict=kids_dict,
                        chores_dict=chores_dict,
                        default=default_data,
                    ),
                    errors=errors,
                )

            challenges_dict[internal_id] = challenge_data
            self._entry_options[CONF_CHALLENGES] = challenges_dict
            LOGGER.debug("Edited challenge '%s' with ID: %s", new_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        kids_dict = {
            kid_data["name"]: kid_id
            for kid_id, kid_data in self._entry_options.get(CONF_KIDS, {}).items()
        }
        chores_dict = self._entry_options.get(CONF_CHORES, {})

        challenge_schema = build_challenge_schema(
            kids_dict=kids_dict, chores_dict=chores_dict, default=challenge_data
        )
        return self.async_show_form(
            step_id="edit_challenge", data_schema=challenge_schema, errors=errors
        )

    # ------------------ DELETE ENTITY ------------------
    async def async_step_delete_kid(self, user_input=None):
        """Delete a kid."""
        self._entry_options = dict(self.config_entry.options)

        kids_dict = self._entry_options.get(CONF_KIDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in kids_dict:
            LOGGER.error("Delete kid: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_kid")

        kid_name = kids_dict[internal_id]["name"]

        if user_input is not None:
            kids_dict.pop(internal_id, None)

            self._entry_options[CONF_KIDS] = kids_dict

            LOGGER.debug("Deleted kid '%s' with ID: %s", kid_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_kid",
            data_schema=vol.Schema({}),
            description_placeholders={"kid_name": kid_name},
        )

    async def async_step_delete_parent(self, user_input=None):
        """Delete a parent."""
        self._entry_options = dict(self.config_entry.options)

        parents_dict = self._entry_options.get(CONF_PARENTS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in parents_dict:
            LOGGER.error("Delete parent: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_parent")

        parent_name = parents_dict[internal_id]["name"]

        if user_input is not None:
            parents_dict.pop(internal_id, None)

            self._entry_options[CONF_PARENTS] = parents_dict

            LOGGER.debug("Deleted parent '%s' with ID: %s", parent_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_parent",
            data_schema=vol.Schema({}),
            description_placeholders={"parent_name": parent_name},
        )

    async def async_step_delete_chore(self, user_input=None):
        """Delete a chore."""
        self._entry_options = dict(self.config_entry.options)

        chores_dict = self._entry_options.get(CONF_CHORES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in chores_dict:
            LOGGER.error("Delete chore: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_chore")

        chore_name = chores_dict[internal_id]["name"]

        if user_input is not None:
            chores_dict.pop(internal_id, None)

            self._entry_options[CONF_CHORES] = chores_dict

            LOGGER.debug("Deleted chore '%s' with ID: %s", chore_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_chore",
            data_schema=vol.Schema({}),
            description_placeholders={"chore_name": chore_name},
        )

    async def async_step_delete_badge(self, user_input=None):
        """Delete a badge."""
        self._entry_options = dict(self.config_entry.options)

        badges_dict = self._entry_options.get(CONF_BADGES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in badges_dict:
            LOGGER.error("Delete badge: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_badge")

        badge_name = badges_dict[internal_id]["name"]

        if user_input is not None:
            badges_dict.pop(internal_id, None)

            self._entry_options[CONF_BADGES] = badges_dict

            LOGGER.debug("Deleted badge '%s' with ID: %s", badge_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_badge",
            data_schema=vol.Schema({}),
            description_placeholders={"badge_name": badge_name},
        )

    async def async_step_delete_reward(self, user_input=None):
        """Delete a reward."""
        self._entry_options = dict(self.config_entry.options)

        rewards_dict = self._entry_options.get(CONF_REWARDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in rewards_dict:
            LOGGER.error("Delete reward: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_reward")

        reward_name = rewards_dict[internal_id]["name"]

        if user_input is not None:
            rewards_dict.pop(internal_id, None)

            self._entry_options[CONF_REWARDS] = rewards_dict

            LOGGER.debug("Deleted reward '%s' with ID: %s", reward_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_reward",
            data_schema=vol.Schema({}),
            description_placeholders={"reward_name": reward_name},
        )

    async def async_step_delete_penalty(self, user_input=None):
        """Delete a penalty."""
        self._entry_options = dict(self.config_entry.options)

        penalties_dict = self._entry_options.get(CONF_PENALTIES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in penalties_dict:
            LOGGER.error("Delete penalty: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_penalty")

        penalty_name = penalties_dict[internal_id]["name"]

        if user_input is not None:
            penalties_dict.pop(internal_id, None)

            self._entry_options[CONF_PENALTIES] = penalties_dict

            LOGGER.debug("Deleted penalty '%s' with ID: %s", penalty_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_penalty",
            data_schema=vol.Schema({}),
            description_placeholders={"penalty_name": penalty_name},
        )

    async def async_step_delete_achievement(self, user_input=None):
        """Delete an achievement."""
        self._entry_options = dict(self.config_entry.options)

        achievements_dict = self._entry_options.get(CONF_ACHIEVEMENTS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in achievements_dict:
            LOGGER.error("Delete achievement: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_achievement")

        achievement_name = achievements_dict[internal_id]["name"]
        if user_input is not None:
            achievements_dict.pop(internal_id, None)
            self._entry_options[CONF_ACHIEVEMENTS] = achievements_dict
            LOGGER.debug(
                "Deleted achievement '%s' with ID: %s", achievement_name, internal_id
            )

            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_achievement",
            data_schema=vol.Schema({}),
            description_placeholders={"achievement_name": achievement_name},
        )

    async def async_step_delete_challenge(self, user_input=None):
        """Delete a challenge."""
        self._entry_options = dict(self.config_entry.options)

        challenges_dict = self._entry_options.get(CONF_CHALLENGES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in challenges_dict:
            LOGGER.error("Delete challenge: Invalid internal_id '%s'", internal_id)
            return self.async_abort(reason="invalid_challenge")

        challenge_name = challenges_dict[internal_id]["name"]
        if user_input is not None:
            challenges_dict.pop(internal_id, None)
            self._entry_options[CONF_CHALLENGES] = challenges_dict
            LOGGER.debug(
                "Deleted challenge '%s' with ID: %s", challenge_name, internal_id
            )

            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_challenge",
            data_schema=vol.Schema({}),
            description_placeholders={"challenge_name": challenge_name},
        )

    # ------------------ HELPER METHODS ------------------
    async def _update_and_reload(self):
        """Update the config entry options and reload the integration."""
        new_data = dict(self.config_entry.data)
        new_data["last_change"] = dt_util.utcnow().isoformat()

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data, options=self._entry_options
        )
        LOGGER.debug(
            "Called update_entry. Now reloading entry: %s", self.config_entry.entry_id
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        LOGGER.debug("Options updated and integration reloaded")
