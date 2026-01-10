"""Shared test helpers for config and options flow testing.

This module provides reusable utilities for both config flow and options flow tests:
1. YAML scenario data → flow form data converters
2. Entity verification helpers
3. Common flow navigation patterns

Usage:
    from tests.flow_test_helpers import FlowTestHelper

    # Convert YAML kid to form data
    form_data = FlowTestHelper.build_kid_form_data(yaml_kid)

    # Verify entities created after flow
    await FlowTestHelper.verify_entity_counts(hass, {"kids": 2, "chores": 5})
"""

from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from tests.helpers import (
    # Badge constants
    BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
    BADGE_TYPE_CUMULATIVE,
    # Config/Options flow field names - Badges
    CFOF_BADGES_INPUT_ASSIGNED_TO,
    CFOF_BADGES_INPUT_AWARD_POINTS,
    CFOF_BADGES_INPUT_END_DATE,
    CFOF_BADGES_INPUT_ICON,
    CFOF_BADGES_INPUT_NAME,
    CFOF_BADGES_INPUT_START_DATE,
    CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
    CFOF_BADGES_INPUT_TARGET_TYPE,
    # Config/Options flow field names - Bonuses
    CFOF_BONUSES_INPUT_DESCRIPTION,
    CFOF_BONUSES_INPUT_ICON,
    CFOF_BONUSES_INPUT_NAME,
    CFOF_BONUSES_INPUT_POINTS,
    # Config/Options flow field names - Chores
    CFOF_CHORES_INPUT_ASSIGNED_KIDS,
    CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
    CFOF_CHORES_INPUT_DEFAULT_POINTS,
    CFOF_CHORES_INPUT_DESCRIPTION,
    CFOF_CHORES_INPUT_ICON,
    CFOF_CHORES_INPUT_NAME,
    CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
    # Config/Options flow field names - Kids
    CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE,
    CFOF_KIDS_INPUT_ENABLE_MOBILE_NOTIFICATIONS,
    CFOF_KIDS_INPUT_ENABLE_PERSISTENT_NOTIFICATIONS,
    CFOF_KIDS_INPUT_HA_USER,
    CFOF_KIDS_INPUT_KID_NAME,
    CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE,
    # Config/Options flow field names - Parents
    CFOF_PARENTS_INPUT_ASSOCIATED_KIDS,
    CFOF_PARENTS_INPUT_ENABLE_MOBILE_NOTIFICATIONS,
    CFOF_PARENTS_INPUT_ENABLE_PERSISTENT_NOTIFICATIONS,
    CFOF_PARENTS_INPUT_HA_USER,
    CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE,
    CFOF_PARENTS_INPUT_NAME,
    # Config/Options flow field names - Penalties
    CFOF_PENALTIES_INPUT_DESCRIPTION,
    CFOF_PENALTIES_INPUT_ICON,
    CFOF_PENALTIES_INPUT_NAME,
    CFOF_PENALTIES_INPUT_POINTS,
    # Config/Options flow field names - Rewards
    CFOF_REWARDS_INPUT_COST,
    CFOF_REWARDS_INPUT_DESCRIPTION,
    CFOF_REWARDS_INPUT_ICON,
    CFOF_REWARDS_INPUT_NAME,
    # Domain and coordinator
    COORDINATOR,
    DOMAIN,
    # Options flow navigation constants
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
)


class FlowTestHelper:
    """Unified helper for config and options flow testing."""

    # =========================================================================
    # YAML → Form Data Converters
    # =========================================================================

    @staticmethod
    def build_kid_form_data(yaml_kid: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML kid data to flow form input.

        Args:
            yaml_kid: Kid data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_KIDS_INPUT_KID_NAME: yaml_kid["name"],
            CFOF_KIDS_INPUT_HA_USER: yaml_kid.get("ha_user_name", ""),
            CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE: yaml_kid.get(
                "dashboard_language", "en"
            ),
            CFOF_KIDS_INPUT_ENABLE_MOBILE_NOTIFICATIONS: yaml_kid.get(
                "enable_mobile_notifications", False
            ),
            CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE: yaml_kid.get(
                "mobile_notify_service", ""
            ),
            CFOF_KIDS_INPUT_ENABLE_PERSISTENT_NOTIFICATIONS: yaml_kid.get(
                "enable_persistent_notifications", False
            ),
        }

    @staticmethod
    def build_parent_form_data(yaml_parent: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML parent data to flow form input.

        Args:
            yaml_parent: Parent data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_PARENTS_INPUT_NAME: yaml_parent["name"],
            CFOF_PARENTS_INPUT_HA_USER: yaml_parent.get("ha_user_name", ""),
            CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: yaml_parent.get("associated_kids", []),
            CFOF_PARENTS_INPUT_ENABLE_MOBILE_NOTIFICATIONS: yaml_parent.get(
                "enable_mobile_notifications", False
            ),
            CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE: yaml_parent.get(
                "mobile_notify_service", ""
            ),
            CFOF_PARENTS_INPUT_ENABLE_PERSISTENT_NOTIFICATIONS: yaml_parent.get(
                "enable_persistent_notifications", False
            ),
        }

    @staticmethod
    def build_chore_form_data(
        yaml_chore: dict[str, Any],
        kid_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Convert YAML chore data to flow form input.

        Args:
            yaml_chore: Chore data from scenario YAML file
            kid_names: List of available kid names for assignment

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        # Map YAML "type" to flow "recurring_frequency"
        frequency_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "once": "once",
            "custom": "custom",
        }
        yaml_type = yaml_chore.get("type", "once")
        recurring_frequency = frequency_map.get(yaml_type, "once")

        return {
            CFOF_CHORES_INPUT_NAME: yaml_chore["name"],
            CFOF_CHORES_INPUT_DEFAULT_POINTS: yaml_chore.get("points", 10),
            CFOF_CHORES_INPUT_ICON: yaml_chore.get("icon", "mdi:check"),
            CFOF_CHORES_INPUT_DESCRIPTION: yaml_chore.get("description", ""),
            CFOF_CHORES_INPUT_ASSIGNED_KIDS: yaml_chore.get("assigned_to", []),
            CFOF_CHORES_INPUT_RECURRING_FREQUENCY: recurring_frequency,
            CFOF_CHORES_INPUT_COMPLETION_CRITERIA: yaml_chore.get(
                "completion_criteria", "independent"
            ),
        }

    @staticmethod
    def build_reward_form_data(yaml_reward: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML reward data to flow form input.

        Args:
            yaml_reward: Reward data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_REWARDS_INPUT_NAME: yaml_reward["name"],
            CFOF_REWARDS_INPUT_COST: yaml_reward.get("cost", 50),
            CFOF_REWARDS_INPUT_ICON: yaml_reward.get("icon", "mdi:gift"),
            CFOF_REWARDS_INPUT_DESCRIPTION: yaml_reward.get("description", ""),
        }

    @staticmethod
    def build_penalty_form_data(yaml_penalty: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML penalty data to flow form input.

        Args:
            yaml_penalty: Penalty data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_PENALTIES_INPUT_NAME: yaml_penalty["name"],
            CFOF_PENALTIES_INPUT_POINTS: yaml_penalty.get("points", 5),
            CFOF_PENALTIES_INPUT_ICON: yaml_penalty.get("icon", "mdi:alert"),
            CFOF_PENALTIES_INPUT_DESCRIPTION: yaml_penalty.get("description", ""),
        }

    @staticmethod
    def build_bonus_form_data(yaml_bonus: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML bonus data to flow form input.

        Args:
            yaml_bonus: Bonus data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_BONUSES_INPUT_NAME: yaml_bonus["name"],
            CFOF_BONUSES_INPUT_POINTS: yaml_bonus.get("points", 10),
            CFOF_BONUSES_INPUT_ICON: yaml_bonus.get("icon", "mdi:star"),
            CFOF_BONUSES_INPUT_DESCRIPTION: yaml_bonus.get("description", ""),
        }

    @staticmethod
    def build_badge_form_data(yaml_badge: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML badge data to flow form input.

        Args:
            yaml_badge: Badge data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        badge_type = yaml_badge.get("badge_type", BADGE_TYPE_CUMULATIVE)
        form_data = {
            CFOF_BADGES_INPUT_NAME: yaml_badge["name"],
            CFOF_BADGES_INPUT_ICON: yaml_badge.get("icon", "mdi:medal"),
            CFOF_BADGES_INPUT_ASSIGNED_TO: yaml_badge.get("assigned_to", []),
            CFOF_BADGES_INPUT_AWARD_POINTS: yaml_badge.get("award_points", 0),
        }

        if badge_type == BADGE_TYPE_CUMULATIVE:
            form_data[CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = yaml_badge.get(
                "target_threshold_value", 10
            )
            form_data[CFOF_BADGES_INPUT_TARGET_TYPE] = yaml_badge.get(
                "target_type", BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT
            )
        else:  # periodic
            form_data[CFOF_BADGES_INPUT_START_DATE] = yaml_badge.get("start_date")
            form_data[CFOF_BADGES_INPUT_END_DATE] = yaml_badge.get("end_date")

        return form_data

    # =========================================================================
    # Entity Verification Helpers
    # =========================================================================

    @staticmethod
    async def get_coordinator(hass: HomeAssistant) -> Any:
        """Get the KidsChores coordinator from hass.data.

        Args:
            hass: Home Assistant instance

        Returns:
            KidsChoresDataCoordinator instance
        """
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state.name == "LOADED":
                return hass.data[DOMAIN][entry.entry_id][COORDINATOR]
        return None

    @staticmethod
    async def verify_entity_counts(
        hass: HomeAssistant,
        expected: dict[str, int],
    ) -> dict[str, bool]:
        """Verify expected entity counts exist after flow completion.

        Args:
            hass: Home Assistant instance
            expected: Dict mapping entity type to expected count
                      Keys: "kids", "parents", "chores", "rewards", etc.

        Returns:
            Dict mapping entity type to pass/fail boolean
        """
        coordinator = await FlowTestHelper.get_coordinator(hass)
        if not coordinator:
            return dict.fromkeys(expected, False)

        actual_counts = {
            "kids": len(coordinator.kids_data),
            "parents": len(coordinator.parents_data),
            "chores": len(coordinator.chores_data),
            "rewards": len(coordinator.rewards_data),
            "penalties": len(coordinator.penalties_data),
            "bonuses": len(coordinator.bonuses_data),
            "badges": len(coordinator.badges_data),
            "achievements": len(coordinator.achievements_data),
            "challenges": len(coordinator.challenges_data),
        }

        results = {}
        for entity_type, expected_count in expected.items():
            actual = actual_counts.get(entity_type, 0)
            results[entity_type] = actual == expected_count
            if not results[entity_type]:
                # Log mismatch for debugging
                pass  # Tests will assert on results

        return results

    @staticmethod
    async def get_entity_by_name(
        hass: HomeAssistant,
        entity_type: str,
        name: str,
    ) -> dict[str, Any] | None:
        """Find an entity by name in coordinator data.

        Args:
            hass: Home Assistant instance
            entity_type: Type ("kids", "chores", "rewards", etc.)
            name: Entity name to find

        Returns:
            Entity data dict or None if not found
        """
        coordinator = await FlowTestHelper.get_coordinator(hass)
        if not coordinator:
            return None

        data_map = {
            "kids": coordinator.kids_data,
            "parents": coordinator.parents_data,
            "chores": coordinator.chores_data,
            "rewards": coordinator.rewards_data,
            "penalties": coordinator.penalties_data,
            "bonuses": coordinator.bonuses_data,
            "badges": coordinator.badges_data,
            "achievements": coordinator.achievements_data,
            "challenges": coordinator.challenges_data,
        }

        data = data_map.get(entity_type, {})
        for entity_data in data.values():
            if entity_data.get("name") == name:
                return entity_data

        return None

    # =========================================================================
    # Options Flow Navigation Helpers
    # =========================================================================

    @staticmethod
    async def navigate_to_entity_menu(
        hass: HomeAssistant,
        entry_id: str,
        entity_type: str,
    ) -> ConfigFlowResult:
        """Navigate options flow to a specific entity management menu.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            entity_type: Menu to navigate to (use OPTIONS_FLOW_* constants)

        Returns:
            Flow result at the manage_entity step
        """
        # Start options flow
        init_result = await hass.config_entries.options.async_init(entry_id)

        # Select entity type menu
        return await hass.config_entries.options.async_configure(
            init_result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: entity_type},
        )

    @staticmethod
    async def add_entity_via_options_flow(
        hass: HomeAssistant,
        entry_id: str,
        menu_type: str,
        add_step: str,
        form_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Add an entity via the options flow.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            menu_type: Menu type constant (OPTIONS_FLOW_KIDS, etc.)
            add_step: Add step constant (OPTIONS_FLOW_STEP_ADD_KID, etc.)
            form_data: Form data for the new entity

        Returns:
            Final flow result
        """
        # Navigate to entity menu
        menu_result = await FlowTestHelper.navigate_to_entity_menu(
            hass, entry_id, menu_type
        )

        # Select "Add" action
        add_result = await hass.config_entries.options.async_configure(
            menu_result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Submit form data
        return await hass.config_entries.options.async_configure(
            add_result["flow_id"],
            user_input=form_data,
        )


# =========================================================================
# YAML Scenario Loading (shared with legacy)
# =========================================================================


def load_scenario_yaml(scenario_name: str) -> dict[str, Any]:
    """Load a test scenario YAML file.

    Args:
        scenario_name: Name of the scenario (minimal, medium, full, performance_stress)

    Returns:
        Dictionary containing the scenario data
    """
    import os

    import yaml

    # Try modern location first, then legacy
    scenario_path = os.path.join(
        os.path.dirname(__file__), f"testdata_scenario_{scenario_name}.yaml"
    )
    if not os.path.exists(scenario_path):
        scenario_path = os.path.join(
            os.path.dirname(__file__),
            "legacy",
            f"testdata_scenario_{scenario_name}.yaml",
        )

    with open(scenario_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_scenario_entity_counts(scenario_data: dict[str, Any]) -> dict[str, int]:
    """Get entity counts from a loaded scenario.

    Args:
        scenario_data: Scenario data loaded from YAML

    Returns:
        Dict mapping entity type to count
    """
    family = scenario_data.get("family", {})
    return {
        "kids": len(family.get("kids", [])),
        "parents": len(family.get("parents", [])),
        "chores": len(scenario_data.get("chores", [])),
        "rewards": len(scenario_data.get("rewards", [])),
        "penalties": len(scenario_data.get("penalties", [])),
        "bonuses": len(scenario_data.get("bonuses", [])),
        "badges": len(scenario_data.get("badges", [])),
        "achievements": len(scenario_data.get("achievements", [])),
        "challenges": len(scenario_data.get("challenges", [])),
    }
