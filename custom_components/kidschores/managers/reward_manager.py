"""Reward Manager - Reward redemption lifecycle management.

This manager handles the complete reward lifecycle:
- Redeem: Kid claims a reward (enters pending approval state)
- Approve: Parent approves pending reward (deducts points via EconomyManager)
- Disapprove: Parent rejects reward (resets to available)
- Undo: Kid cancels own pending claim

ARCHITECTURE (v0.5.0+ "Clean Break"):
- RewardManager owns the entire reward workflow
- Point deductions via EconomyManager.withdraw() (emits POINTS_CHANGED)
- GamificationManager listens to POINTS_CHANGED (Event Bus coupling only)
- Coordinator provides data access and persistence

Event Flow:
    RewardManager.approve() -> EconomyManager.withdraw() -> emit(POINTS_CHANGED)
                                                                    |
                    GamificationManager (listener) <----------------+
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast
import uuid

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.kidschores import const, kc_helpers as kh

from .base_manager import BaseManager
from .notification_manager import NotificationManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.managers.economy_manager import EconomyManager
    from custom_components.kidschores.type_defs import KidData, RewardData


class RewardManager(BaseManager):
    """Manager for reward redemption lifecycle.

    Responsibilities:
    - Handle reward claims (redeem)
    - Process approvals/disapprovals
    - Track pending reward states
    - Coordinate with EconomyManager for point deductions
    - Send notifications via coordinator's notification routing

    NOT responsible for:
    - Point balance management (delegated to EconomyManager)
    - Gamification checks (handled by GamificationManager via events)
    - Direct storage persistence (delegated to coordinator)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
        economy_manager: EconomyManager,
        notification_manager: NotificationManager,
    ) -> None:
        """Initialize the RewardManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main KidsChores coordinator
            economy_manager: Manager for point transactions
            notification_manager: Manager for sending notifications
        """
        super().__init__(hass, coordinator)
        self._economy = economy_manager
        self._notification = notification_manager
        self._approval_locks: dict[str, asyncio.Lock] = {}

    async def async_setup(self) -> None:
        """Set up the RewardManager.

        Currently no event subscriptions needed - RewardManager is called directly.
        """
        const.LOGGER.debug("RewardManager initialized for entry %s", self.entry_id)

    # =========================================================================
    # Lock Management
    # =========================================================================

    def _get_lock(self, operation: str, *identifiers: str) -> asyncio.Lock:
        """Get or create a lock for a specific operation and identifiers.

        This prevents race conditions when multiple requests try to modify
        the same reward state simultaneously (e.g., two parents clicking approve).

        Args:
            operation: The operation name (e.g., "redeem", "approve")
            *identifiers: Unique identifiers for this lock (e.g., kid_id, reward_id)

        Returns:
            asyncio.Lock for the specified operation+identifiers combination
        """
        lock_key = f"{operation}:{':'.join(identifiers)}"
        if lock_key not in self._approval_locks:
            self._approval_locks[lock_key] = asyncio.Lock()
        return self._approval_locks[lock_key]

    # =========================================================================
    # Data Access Helpers
    # =========================================================================

    def get_kid_reward_data(
        self, kid_id: str, reward_id: str, create: bool = False
    ) -> dict[str, Any]:
        """Get the reward data dict for a specific kid+reward combination.

        Args:
            kid_id: The kid's internal ID
            reward_id: The reward's internal ID
            create: If True, create the entry if it doesn't exist

        Returns:
            Reward tracking dict or empty dict if not found and create=False
        """
        kid_info: KidData = cast("KidData", self.coordinator.kids_data.get(kid_id, {}))
        reward_data = kid_info.setdefault(const.DATA_KID_REWARD_DATA, {})
        if create and reward_id not in reward_data:
            reward_data[reward_id] = {
                const.DATA_KID_REWARD_DATA_NAME: cast(
                    "RewardData", self.coordinator.rewards_data.get(reward_id, {})
                ).get(const.DATA_REWARD_NAME)
                or "",
                const.DATA_KID_REWARD_DATA_PENDING_COUNT: 0,
                const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS: [],
                const.DATA_KID_REWARD_DATA_LAST_CLAIMED: "",
                const.DATA_KID_REWARD_DATA_LAST_APPROVED: "",
                const.DATA_KID_REWARD_DATA_LAST_DISAPPROVED: "",
                const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS: 0,
                const.DATA_KID_REWARD_DATA_TOTAL_APPROVED: 0,
                const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED: 0,
                const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT: 0,
                const.DATA_KID_REWARD_DATA_PERIODS: {
                    const.DATA_KID_REWARD_DATA_PERIODS_DAILY: {},
                    const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY: {},
                    const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY: {},
                    const.DATA_KID_REWARD_DATA_PERIODS_YEARLY: {},
                },
            }
        return cast("dict[str, Any]", reward_data.get(reward_id, {}))

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Compute pending reward approvals dynamically from kid_reward_data.

        Unlike chores (which allow only one pending claim at a time), rewards
        support multiple pending claims via the pending_count field.

        Returns:
            List of dicts with keys: kid_id, reward_id, pending_count, timestamp
            One entry per kid+reward combination with pending_count > 0.
        """
        pending: list[dict[str, Any]] = []
        for kid_id, kid_info in self.coordinator.kids_data.items():
            reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})
            for reward_id, entry in reward_data.items():
                # Skip rewards that no longer exist
                if reward_id not in self.coordinator.rewards_data:
                    continue
                pending_count = entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)
                if pending_count > 0:
                    pending.append(
                        {
                            const.DATA_KID_ID: kid_id,
                            const.DATA_REWARD_ID: reward_id,
                            "pending_count": pending_count,
                            const.DATA_REWARD_TIMESTAMP: entry.get(
                                const.DATA_KID_REWARD_DATA_LAST_CLAIMED, ""
                            ),
                        }
                    )
        return pending

    # =========================================================================
    # Period Counter Management
    # =========================================================================

    def _increment_period_counter(
        self,
        reward_entry: dict[str, Any],
        counter_key: str,
        amount: int = 1,
    ) -> None:
        """Increment a period counter for a reward entry across all period buckets.

        Args:
            reward_entry: The reward_data[reward_id] dict
            counter_key: Which counter to increment (claimed/approved/disapproved/points)
            amount: Amount to add (default 1)
        """
        now_local = kh.dt_now_local()

        # Ensure periods structure exists with all_time bucket
        periods = reward_entry.setdefault(
            const.DATA_KID_REWARD_DATA_PERIODS,
            {
                const.DATA_KID_REWARD_DATA_PERIODS_DAILY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_YEARLY: {},
                const.DATA_KID_REWARD_DATA_PERIODS_ALL_TIME: {},
            },
        )

        # Get period mapping from StatisticsEngine
        period_mapping = self.coordinator.stats.get_period_keys(now_local)

        # Record transaction using StatisticsEngine
        self.coordinator.stats.record_transaction(
            periods,
            {counter_key: amount},
            period_key_mapping=period_mapping,
        )

        # Clean up old period data
        self.coordinator.stats.prune_history(
            periods, self.coordinator._get_retention_config()
        )

    def _recalculate_stats_for_kid(self, kid_id: str) -> None:
        """Delegate reward stats aggregation to StatisticsEngine.

        This method aggregates all kid_reward_stats for a given kid by
        delegating to the StatisticsEngine.

        Args:
            kid_id: The internal ID of the kid.
        """
        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return
        stats = self.coordinator.stats.generate_reward_stats(
            kid_info, self.coordinator.rewards_data
        )
        kid_info[const.DATA_KID_REWARD_STATS] = stats

    # =========================================================================
    # Public API: Redeem
    # =========================================================================

    async def redeem(self, parent_name: str, kid_id: str, reward_id: str) -> None:
        """Kid claims a reward with race condition protection.

        Uses asyncio.Lock to ensure only one redemption processes at a time
        per kid+reward combination, preventing duplicate claims.

        Args:
            parent_name: Name of the kid claiming (stored as parent_name for consistency)
            kid_id: The kid's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If kid/reward not found or insufficient points
        """
        lock = self._get_lock("redeem", kid_id, reward_id)
        async with lock:
            await self._redeem_locked(parent_name, kid_id, reward_id)

    async def _redeem_locked(
        self, parent_name: str, kid_id: str, reward_id: str
    ) -> None:
        """Internal redemption logic executed under lock protection.

        Args:
            parent_name: Name of the kid claiming
            kid_id: The kid's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If kid/reward not found or insufficient points
        """
        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_ZERO)
        if kid_info[const.DATA_KID_POINTS] < cost:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                translation_placeholders={
                    "kid": kid_info[const.DATA_KID_NAME],
                    "current": str(kid_info[const.DATA_KID_POINTS]),
                    "required": str(cost),
                },
            )

        # Update kid_reward_data structure
        reward_entry = self.get_kid_reward_data(kid_id, reward_id, create=True)
        reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = (
            reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) + 1
        )
        reward_entry[const.DATA_KID_REWARD_DATA_LAST_CLAIMED] = (
            dt_util.utcnow().isoformat()
        )
        reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS] = (
            reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_CLAIMS, 0) + 1
        )

        # Update period-based tracking for claimed
        self._increment_period_counter(
            reward_entry, const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED
        )

        # Recalculate aggregated reward stats
        self._recalculate_stats_for_kid(kid_id)

        # Generate a unique notification ID for this claim
        notif_id = uuid.uuid4().hex

        # Track notification ID for this claim
        reward_entry.setdefault(const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS, []).append(
            notif_id
        )

        # Build notification metadata for event
        actions = NotificationManager.build_reward_actions(kid_id, reward_id, notif_id)
        extra_data = NotificationManager.build_extra_data(
            kid_id, reward_id=reward_id, notif_id=notif_id
        )

        # Emit event for NotificationManager to send notifications
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_CLAIMED,
            kid_id=kid_id,
            reward_id=reward_id,
            reward_name=reward_info[const.DATA_REWARD_NAME],
            points=reward_info[const.DATA_REWARD_COST],
            actions=actions,
            extra_data=extra_data,
        )

        # Mark reward changed for dashboard helper
        self.coordinator._pending_reward_changed = True

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    # =========================================================================
    # Public API: Approve
    # =========================================================================

    async def approve(
        self,
        parent_name: str,
        kid_id: str,
        reward_id: str,
        notif_id: str | None = None,
        cost_override: float | None = None,
    ) -> None:
        """Parent approves the reward => deduct points via EconomyManager.

        Thread-safe implementation using asyncio.Lock to prevent race conditions
        when multiple parents click approve simultaneously.

        Args:
            parent_name: Name of approving parent (for stale notification feedback).
            kid_id: Internal ID of the kid receiving the reward.
            reward_id: Internal ID of the reward being approved.
            notif_id: Optional notification ID to clear.
            cost_override: Optional cost to charge instead of the reward's stored cost.
                If None, uses reward's configured cost. Set to 0 for free grants.
        """
        lock = self._get_lock("approve", kid_id, reward_id)
        async with lock:
            await self._approve_locked(
                parent_name, kid_id, reward_id, notif_id, cost_override
            )

    async def _approve_locked(
        self,
        parent_name: str,
        kid_id: str,
        reward_id: str,
        notif_id: str | None = None,
        cost_override: float | None = None,
    ) -> None:
        """Internal approval logic executed under lock protection."""
        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        # Determine actual cost: use override if provided, else reward's stored cost
        if cost_override is not None:
            cost = cost_override
        else:
            cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_ZERO)

        # Get pending_count from kid_reward_data (re-fetch inside lock for safety)
        reward_entry = self.get_kid_reward_data(kid_id, reward_id, create=False)
        pending_count = reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)

        # Determine if this is a pending claim approval
        is_pending = pending_count > 0

        # Validate sufficient points
        if kid_info[const.DATA_KID_POINTS] < cost:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                translation_placeholders={
                    "kid": kid_info[const.DATA_KID_NAME],
                    "current": str(kid_info[const.DATA_KID_POINTS]),
                    "required": str(cost),
                },
            )

        # Deduct points via EconomyManager (emits POINTS_CHANGED)
        if cost > 0:
            await self._economy.withdraw(
                kid_id=kid_id,
                amount=cost,
                source=const.POINTS_SOURCE_REWARDS,
                reference_id=reward_id,
            )

        # Track the reward grant
        self._grant_to_kid(
            kid_id=kid_id,
            reward_id=reward_id,
            cost_deducted=cost,
            notif_id=notif_id,
            is_pending_claim=is_pending,
        )

        # Recalculate aggregated reward stats
        self._recalculate_stats_for_kid(kid_id)

        # NOTE: Badge checks handled by GamificationManager via POINTS_CHANGED event

        # Emit event for NotificationManager to send notification and clear parent claim
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_APPROVED,
            kid_id=kid_id,
            reward_id=reward_id,
            reward_name=reward_info[const.DATA_REWARD_NAME],
        )

        # Mark reward changed for dashboard helper
        self.coordinator._pending_reward_changed = True

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    def _grant_to_kid(
        self,
        kid_id: str,
        reward_id: str,
        cost_deducted: float,
        notif_id: str | None = None,
        is_pending_claim: bool = False,
    ) -> None:
        """Track a reward grant for a kid (unified logic for approvals and badge awards).

        This helper consolidates reward tracking. It updates all counters and timestamps
        but does NOT handle point deduction - that must be done by the caller before
        calling this method.

        Args:
            kid_id: The internal ID of the kid receiving the reward.
            reward_id: The internal ID of the reward being granted.
            cost_deducted: The actual points cost charged (0 for free grants).
            notif_id: Optional notification ID to remove from tracking list.
            is_pending_claim: True if approving a pending claim (decrements pending_count).
        """
        # Get or create reward tracking entry
        reward_entry = self.get_kid_reward_data(kid_id, reward_id, create=True)

        # Handle pending claim decrement if applicable
        if is_pending_claim:
            reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = max(
                0,
                reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) - 1,
            )

        # Update timestamps
        reward_entry[const.DATA_KID_REWARD_DATA_LAST_APPROVED] = (
            dt_util.utcnow().isoformat()
        )

        # Update total counters
        reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_APPROVED] = (
            reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_APPROVED, 0) + 1
        )

        # Track points spent only if cost > 0 (badges grant free rewards)
        if cost_deducted > const.DEFAULT_ZERO:
            reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT] = (
                reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_POINTS_SPENT, 0)
                + cost_deducted
            )

        # Update period-based tracking for approved count
        self._increment_period_counter(
            reward_entry, const.DATA_KID_REWARD_DATA_PERIOD_APPROVED
        )

        # Update period-based tracking for points (only if cost > 0)
        if cost_deducted > const.DEFAULT_ZERO:
            self._increment_period_counter(
                reward_entry,
                const.DATA_KID_REWARD_DATA_PERIOD_POINTS,
                amount=int(cost_deducted),
            )

        # Remove notification ID if provided
        if notif_id:
            notif_ids = reward_entry.get(
                const.DATA_KID_REWARD_DATA_NOTIFICATION_IDS, []
            )
            if notif_id in notif_ids:
                notif_ids.remove(notif_id)

    # =========================================================================
    # Public API: Disapprove
    # =========================================================================

    async def disapprove(self, parent_name: str, kid_id: str, reward_id: str) -> None:
        """Disapprove a reward with race condition protection.

        Uses asyncio.Lock to ensure only one disapproval processes at a time
        per kid+reward combination.

        Args:
            parent_name: Name of disapproving parent (for audit/notifications)
            kid_id: The kid's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If kid or reward not found
        """
        lock = self._get_lock("disapprove", kid_id, reward_id)
        async with lock:
            await self._disapprove_locked(parent_name, kid_id, reward_id)

    async def _disapprove_locked(
        self, parent_name: str, kid_id: str, reward_id: str
    ) -> None:
        """Internal disapproval logic executed under lock protection."""
        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)

        # Update kid_reward_data structure
        if kid_info:
            reward_entry = self.get_kid_reward_data(kid_id, reward_id, create=False)
            if reward_entry:
                reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = max(
                    0, reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) - 1
                )
                reward_entry[const.DATA_KID_REWARD_DATA_LAST_DISAPPROVED] = (
                    dt_util.utcnow().isoformat()
                )
                reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED] = (
                    reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED, 0)
                    + 1
                )

                # Update period-based tracking for disapproved
                self._increment_period_counter(
                    reward_entry, const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED
                )

            # Recalculate aggregated reward stats
            self._recalculate_stats_for_kid(kid_id)

        # Emit event for NotificationManager to send notification and clear parent claim
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_DISAPPROVED,
            kid_id=kid_id,
            reward_id=reward_id,
            reward_name=reward_info[const.DATA_REWARD_NAME],
        )

        # Mark reward changed for dashboard helper
        self.coordinator._pending_reward_changed = True

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    # =========================================================================
    # Public API: Undo Claim
    # =========================================================================

    async def undo_claim(self, kid_id: str, reward_id: str) -> None:
        """Allow kid to undo their own reward claim (no stat tracking).

        This method provides a way for kids to remove their pending reward claim
        without it counting as a disapproval. Unlike disapprove:
        - Does NOT track disapproval stats (no last_disapproved, no counters)
        - Does NOT send notifications (silent undo)
        - Only decrements pending_count

        Args:
            kid_id: The kid's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If kid or reward not found
        """
        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Update kid_reward_data structure - only decrement pending_count
        # Do NOT update last_disapproved, total_disapproved, or period counters
        reward_entry = self.get_kid_reward_data(kid_id, reward_id, create=False)
        if reward_entry:
            reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = max(
                0, reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) - 1
            )

        # Recalculate aggregated reward stats (pending count changed)
        self._recalculate_stats_for_kid(kid_id)

        # Mark reward changed for dashboard helper
        self.coordinator._pending_reward_changed = True

        # No notification sent (silent undo)

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    # =========================================================================
    # Public API: Reset
    # =========================================================================

    async def reset_rewards(
        self, kid_id: str | None = None, reward_id: str | None = None
    ) -> None:
        """Reset rewards based on provided kid_id and reward_id.

        Args:
            kid_id: Optional kid ID to reset rewards for
            reward_id: Optional reward ID to reset

        Behavior:
        - kid_id + reward_id: Reset specific reward for specific kid
        - reward_id only: Reset that reward for all kids
        - kid_id only: Reset all rewards for that kid
        - Neither: Reset all rewards for all kids
        """
        if reward_id and kid_id:
            # Reset a specific reward for a specific kid
            kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Rewards - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            # Clear reward_data entry for this reward
            reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})
            reward_data.pop(reward_id, None)

        elif reward_id:
            # Reset a specific reward for all kids
            found = False
            for kid_info_loop in self.coordinator.kids_data.values():
                reward_data = kid_info_loop.get(const.DATA_KID_REWARD_DATA, {})
                if reward_id in reward_data:
                    found = True
                    reward_data.pop(reward_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Rewards - Reward '%s' not found in any kid's data",
                    reward_id,
                )

        elif kid_id:
            # Reset all rewards for a specific kid
            kid_info_elif: KidData | None = self.coordinator.kids_data.get(kid_id)
            if not kid_info_elif:
                const.LOGGER.error(
                    "ERROR: Reset Rewards - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            # Clear all reward_data for this kid
            if const.DATA_KID_REWARD_DATA in kid_info_elif:
                kid_info_elif[const.DATA_KID_REWARD_DATA].clear()

        else:
            # Reset all rewards for all kids
            const.LOGGER.info(
                "INFO: Reset Rewards - Resetting all rewards for all kids"
            )
            for kid_info in self.coordinator.kids_data.values():
                # Clear all reward_data for this kid
                if const.DATA_KID_REWARD_DATA in kid_info:
                    kid_info[const.DATA_KID_REWARD_DATA].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Rewards completed - Kid ID '%s', Reward ID '%s'",
            kid_id,
            reward_id,
        )

        # Mark reward changed for dashboard helper
        self.coordinator._pending_reward_changed = True

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)
