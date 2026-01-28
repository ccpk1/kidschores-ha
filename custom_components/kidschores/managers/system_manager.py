# File: managers/system_manager.py
"""System Manager for KidsChores integration.

The "Janitor" - handles entity registry cleanup via reactive signals.

Platinum Architecture Principles:
- REACTIVE: Listens to DELETED signals, does NOT get called directly by other managers
- ISOLATED: No imports from other managers, only entity_helpers and const
- STARTUP: Runs safety net cleanup once during async_setup()

Entity Cleanup Strategy:
1. TARGETED (Domain Managers): When ChoreManager.delete_chore() runs, it calls
   entity_helpers.remove_entities_by_item_id() directly for that specific chore.
2. REACTIVE (SystemManager): Listens to *_DELETED signals for cross-domain cleanup
   (e.g., when a kid is deleted, scrub any remaining kid-related entities).
3. SAFETY NET (Startup): Runs remove_all_orphaned_entities() once to catch any
   orphans from crashes, incomplete deletes, or edge cases.

Signals Consumed:
- SIGNAL_SUFFIX_KID_DELETED: Scrub kid entities from registry
- SIGNAL_SUFFIX_CHORE_DELETED: Scrub chore entities from registry
- SIGNAL_SUFFIX_REWARD_DELETED: Scrub reward entities from registry
- SIGNAL_SUFFIX_BADGE_DELETED: Scrub badge entities from registry
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .. import const
from ..helpers.entity_helpers import (
    is_shadow_kid,
    parse_entity_reference,
    remove_entities_by_item_id,
    remove_orphaned_kid_chore_entities,
    remove_orphaned_manual_adjustment_buttons,
    remove_orphaned_progress_entities,
    remove_orphaned_shared_chore_sensors,
    should_create_entity,
    should_create_gamification_entities,
    should_create_workflow_buttons,
)
from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator


class SystemManager(BaseManager):
    """System Manager - The Janitor.

    Handles reactive entity registry cleanup via domain signals.
    Runs startup safety net to catch orphaned entities.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize system manager.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator
        """
        super().__init__(hass, coordinator)

    async def async_setup(self) -> None:
        """Set up the system manager.

        Subscribes to DELETED signals for reactive cleanup.
        Note: Startup safety net is called separately AFTER platform setup
        via run_startup_safety_net() - not in async_setup().
        """
        # Subscribe to lifecycle DELETED signals
        self.listen(const.SIGNAL_SUFFIX_KID_DELETED, self._handle_kid_deleted)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DELETED, self._handle_chore_deleted)
        self.listen(const.SIGNAL_SUFFIX_REWARD_DELETED, self._handle_reward_deleted)
        self.listen(const.SIGNAL_SUFFIX_BADGE_DELETED, self._handle_badge_deleted)

        const.LOGGER.debug(
            "SystemManager initialized with 4 DELETED signal subscriptions for entry %s",
            self.entry_id,
        )

    async def run_startup_safety_net(self) -> int:
        """Run startup safety net - removes orphaned entities.

        Called once during fresh startup AFTER platform setup is complete.
        This ensures all legitimate entities have been created before scanning
        for orphans.

        Returns:
            Total count of removed entities.
        """
        total_removed = await self.remove_all_orphaned_entities()
        if total_removed > 0:
            const.LOGGER.info(
                "SystemManager startup safety net removed %d orphaned entities",
                total_removed,
            )
        return total_removed

    # =========================================================================
    # Signal Handlers - Reactive Entity Cleanup
    # =========================================================================

    @callback
    def _handle_kid_deleted(self, payload: dict[str, Any]) -> None:
        """Handle KID_DELETED signal - scrub registry for kid entities.

        Called AFTER the kid has been deleted from storage and _persist() called.
        The payload contains the kid_id needed for registry scrubbing.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with kid_id, kid_name, was_shadow
        """
        kid_id = payload.get("kid_id")
        if not kid_id:
            const.LOGGER.warning("KID_DELETED signal missing kid_id in payload")
            return

        # Domain Managers already do targeted cleanup - this is for any stragglers
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            kid_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted kid %s",
                removed,
                kid_id,
            )

    @callback
    def _handle_chore_deleted(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DELETED signal - scrub registry for chore entities.

        Called AFTER the chore has been deleted from storage and _persist() called.
        ChoreManager already calls remove_entities_by_item_id() - this catches stragglers.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with chore_id, chore_name
        """
        chore_id = payload.get("chore_id")
        if not chore_id:
            const.LOGGER.warning("CHORE_DELETED signal missing chore_id in payload")
            return

        # ChoreManager already does targeted cleanup - this is a safety net
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            chore_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted chore %s",
                removed,
                chore_id,
            )

    @callback
    def _handle_reward_deleted(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_DELETED signal - scrub registry for reward entities.

        Called AFTER the reward has been deleted from storage and _persist() called.
        RewardManager already calls remove_entities_by_item_id() - this catches stragglers.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with reward_id, reward_name
        """
        reward_id = payload.get("reward_id")
        if not reward_id:
            const.LOGGER.warning("REWARD_DELETED signal missing reward_id in payload")
            return

        # RewardManager already does targeted cleanup - this is a safety net
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            reward_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted reward %s",
                removed,
                reward_id,
            )

    @callback
    def _handle_badge_deleted(self, payload: dict[str, Any]) -> None:
        """Handle BADGE_DELETED signal - scrub registry for badge entities.

        Called AFTER the badge has been deleted from storage and _persist() called.
        GamificationManager already calls remove_entities_by_item_id() - this catches stragglers.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with badge_id, badge_name
        """
        badge_id = payload.get("badge_id")
        if not badge_id:
            const.LOGGER.warning("BADGE_DELETED signal missing badge_id in payload")
            return

        # GamificationManager already does targeted cleanup - this is a safety net
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            badge_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted badge %s",
                removed,
                badge_id,
            )

    # =========================================================================
    # Orphan Entity Removal
    # =========================================================================

    async def remove_all_orphaned_entities(self) -> int:
        """Run all orphan cleanup methods. Called on startup.

        Consolidates all data-driven orphan removal into a single call.
        Delegates to entity_helpers functions for the actual cleanup.

        Returns:
            Total count of removed entities.
        """
        perf_start = time.perf_counter()
        total_removed = 0
        entry_id = self.coordinator.config_entry.entry_id

        # Kid-chore assignment orphans
        total_removed += await remove_orphaned_kid_chore_entities(
            self.hass,
            entry_id,
            self.coordinator.kids_data,
            self.coordinator.chores_data,
        )

        # Shared chore sensor orphans
        total_removed += await remove_orphaned_shared_chore_sensors(
            self.hass, entry_id, self.coordinator.chores_data
        )

        # Badge progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.coordinator.badges_data,
            entity_type="badge",
            progress_suffix=const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR,
            assigned_kids_key=const.DATA_BADGE_ASSIGNED_TO,
        )

        # Achievement progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.coordinator.achievements_data,
            entity_type="achievement",
            progress_suffix=const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX,
            assigned_kids_key=const.DATA_ACHIEVEMENT_ASSIGNED_KIDS,
        )

        # Challenge progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.coordinator.challenges_data,
            entity_type="challenge",
            progress_suffix=const.DATA_CHALLENGE_PROGRESS_SUFFIX,
            assigned_kids_key=const.DATA_CHALLENGE_ASSIGNED_KIDS,
        )

        # Manual adjustment button orphans
        current_deltas = set(self.coordinator.economy_manager.adjustment_deltas)
        total_removed += await remove_orphaned_manual_adjustment_buttons(
            self.hass, entry_id, current_deltas
        )

        perf_elapsed = time.perf_counter() - perf_start
        if total_removed > 0:
            const.LOGGER.info(
                "Startup orphan cleanup: removed %d entities in %.3fs",
                total_removed,
                perf_elapsed,
            )
        else:
            const.LOGGER.debug(
                "PERF: startup orphan cleanup completed in %.3fs, no orphans found",
                perf_elapsed,
            )

        return total_removed

    async def remove_conditional_entities(
        self,
        *,
        kid_ids: list[str] | None = None,
    ) -> int:
        """Remove entities no longer allowed by feature flags.

        Removes entities that are no longer allowed based on current flag settings.
        Uses should_create_entity() from helpers/entity_helpers.py as single source of truth.

        This consolidates:
        - Extra entity cleanup (show_legacy_entities flag)
        - Shadow kid workflow entity cleanup
        - Shadow kid gamification entity cleanup

        Args:
            kid_ids: List of kid IDs to check, or None for all kids.
                     Use targeted kid_ids when a specific kid's flags change.
                     Use None for bulk cleanup (fresh startup, post-migration).

        Returns:
            Count of removed entities.

        Call patterns:
            - Options flow (extra flag changes): kid_ids=None (affects all)
            - Options flow (parent flags change): kid_ids=[shadow_kid_id]
            - Unlink service: kid_ids=[shadow_kid_id]
            - Fresh HA startup (not reload): kid_ids=None
            - Post-migration: kid_ids=None
        """
        perf_start = time.perf_counter()
        ent_reg = er.async_get(self.hass)
        prefix = f"{self.coordinator.config_entry.entry_id}_"
        removed_count = 0

        # Get system-wide extra flag
        extra_enabled = self.coordinator.config_entry.options.get(
            const.CONF_SHOW_LEGACY_ENTITIES, False
        )

        # Build kid filter set (None = check all)
        target_kids = set(kid_ids) if kid_ids else None

        for entity_entry in list(ent_reg.entities.values()):
            if entity_entry.config_entry_id != self.coordinator.config_entry.entry_id:
                continue

            unique_id = str(entity_entry.unique_id)
            if not unique_id.startswith(prefix):
                continue

            # Extract kid_id from unique_id using helper
            parts = parse_entity_reference(unique_id, prefix)
            if not parts:
                continue
            kid_id = parts[0]

            # Skip if not in target list (when targeted)
            if target_kids and kid_id not in target_kids:
                continue

            # Determine kid context
            is_shadow = is_shadow_kid(self.coordinator, kid_id)
            workflow_enabled = should_create_workflow_buttons(self.coordinator, kid_id)
            gamification_enabled = should_create_gamification_entities(
                self.coordinator, kid_id
            )

            # Check if entity should exist using unified filter
            if not should_create_entity(
                unique_id,
                is_shadow_kid=is_shadow,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
                extra_enabled=extra_enabled,
            ):
                const.LOGGER.debug(
                    "Removing conditional entity for kid %s: %s (shadow=%s)",
                    kid_id,
                    entity_entry.entity_id,
                    is_shadow,
                )
                ent_reg.async_remove(entity_entry.entity_id)
                removed_count += 1

        perf_elapsed = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: remove_conditional_entities() scanned in %.3fs, removed %d",
            perf_elapsed,
            removed_count,
        )
        if removed_count > 0:
            const.LOGGER.info(
                "Cleaned up %d conditional entit(y/ies) based on current settings",
                removed_count,
            )
        return removed_count
