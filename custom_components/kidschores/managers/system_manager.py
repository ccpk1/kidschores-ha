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

from typing import TYPE_CHECKING, Any

from custom_components.kidschores import const
from custom_components.kidschores.helpers.entity_helpers import (
    remove_entities_by_item_id,
)

from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator


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
        total_removed = await self.coordinator.remove_all_orphaned_entities()
        if total_removed > 0:
            const.LOGGER.info(
                "SystemManager startup safety net removed %d orphaned entities",
                total_removed,
            )
        return total_removed

    # =========================================================================
    # Signal Handlers - Reactive Entity Cleanup
    # =========================================================================

    def _handle_kid_deleted(self, payload: dict[str, Any]) -> None:
        """Handle KID_DELETED signal - scrub registry for kid entities.

        Called AFTER the kid has been deleted from storage and _persist() called.
        The payload contains the kid_id needed for registry scrubbing.

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

    def _handle_chore_deleted(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DELETED signal - scrub registry for chore entities.

        Called AFTER the chore has been deleted from storage and _persist() called.
        ChoreManager already calls remove_entities_by_item_id() - this catches stragglers.

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

    def _handle_reward_deleted(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_DELETED signal - scrub registry for reward entities.

        Called AFTER the reward has been deleted from storage and _persist() called.
        RewardManager already calls remove_entities_by_item_id() - this catches stragglers.

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

    def _handle_badge_deleted(self, payload: dict[str, Any]) -> None:
        """Handle BADGE_DELETED signal - scrub registry for badge entities.

        Called AFTER the badge has been deleted from storage and _persist() called.
        GamificationManager already calls remove_entities_by_item_id() - this catches stragglers.

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
