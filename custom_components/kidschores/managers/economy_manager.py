"""Economy Manager - Point transactions and ledger management.

This manager handles all point-related operations:
- Deposits (adding points)
- Withdrawals (removing points with NSF checks)
- Ledger management (transaction history)
- Penalty application (point deductions)
- Bonus application (point additions)
- Event emission for point changes

ARCHITECTURE (v0.5.0+ "Clean Break"):
- EconomyManager = "The Bank" (STATEFUL point operations)
- EconomyEngine = Pure math and ledger logic (STATELESS)
- GamificationManager listens to POINTS_CHANGED events (Event Bus coupling)

Point transactions emit POINTS_CHANGED events which trigger GamificationManager
to evaluate badges/achievements/challenges automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

from custom_components.kidschores import const
from custom_components.kidschores.engines.economy_engine import (
    EconomyEngine,
    InsufficientFundsError,
)
from custom_components.kidschores.managers.base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.type_defs import KidData, LedgerEntry


# Re-export exception for external use
__all__ = ["EconomyManager", "InsufficientFundsError"]


class EconomyManager(BaseManager):
    """Manager for all point transactions and ledger operations.

    Responsibilities:
    - Execute deposits and withdrawals
    - Maintain transaction ledger per kid
    - Emit SIGNAL_SUFFIX_POINTS_CHANGED events
    - Prune ledger to prevent storage bloat

    NOT responsible for:
    - Gamification checks (handled by Coordinator in Phase 3)
    - Notifications (handled by Coordinator calling NotificationManager)
    - Period-based statistics (handled by StatisticsEngine via Coordinator)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize the EconomyManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main KidsChores coordinator
        """
        super().__init__(hass, coordinator)
        self._coordinator = coordinator

    async def async_setup(self) -> None:
        """Set up the EconomyManager.

        Phase 3: No event subscriptions needed - Coordinator calls us directly.
        Phase 5: Will subscribe to events when gamification is decoupled.
        """
        # No-op for Phase 3 - EconomyManager doesn't listen to events yet

    def _get_kid(self, kid_id: str) -> KidData | None:
        """Get kid data by ID.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            KidData dict or None if not found
        """
        return self._coordinator.kids_data.get(kid_id)

    def _ensure_ledger(self, kid_data: KidData) -> list[LedgerEntry]:
        """Ensure kid has a ledger list, creating if needed.

        Args:
            kid_data: The kid's data dict

        Returns:
            The ledger list (possibly empty but never None)
        """
        if const.DATA_KID_LEDGER not in kid_data:
            kid_data[const.DATA_KID_LEDGER] = []  # type: ignore[typeddict-unknown-key]
        return kid_data[const.DATA_KID_LEDGER]  # type: ignore[typeddict-item]

    def get_balance(self, kid_id: str) -> float:
        """Get current point balance for a kid.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            Current point balance, or 0.0 if kid not found
        """
        kid = self._get_kid(kid_id)
        if not kid:
            const.LOGGER.warning(
                "EconomyManager.get_balance: Kid ID '%s' not found",
                kid_id,
            )
            return 0.0

        try:
            return float(kid.get(const.DATA_KID_POINTS, 0.0))
        except (ValueError, TypeError):
            return 0.0

    def get_history(
        self,
        kid_id: str,
        limit: int = const.DEFAULT_LEDGER_MAX_ENTRIES,
    ) -> list[LedgerEntry]:
        """Get recent transaction history for a kid.

        Args:
            kid_id: The internal UUID of the kid
            limit: Maximum entries to return (newest first)

        Returns:
            List of LedgerEntry dicts (newest last in storage, but we could reverse)
        """
        kid = self._get_kid(kid_id)
        if not kid:
            return []

        ledger = kid.get(const.DATA_KID_LEDGER, [])
        if not isinstance(ledger, list):
            return []

        # Return most recent entries (end of list = newest)
        return ledger[-limit:] if len(ledger) > limit else ledger

    async def deposit(
        self,
        kid_id: str,
        amount: float,
        *,
        source: str,
        reference_id: str | None = None,
        apply_multiplier: bool = False,
    ) -> float:
        """Add points to a kid's balance.

        Args:
            kid_id: The internal UUID of the kid
            amount: Amount to add (must be positive)
            source: Transaction source (POINTS_SOURCE_CHORES, POINTS_SOURCE_BONUSES, etc.)
            reference_id: Optional related entity ID (chore_id, etc.)
            apply_multiplier: If True, apply kid's points_multiplier

        Returns:
            New balance after deposit

        Raises:
            ValueError: If kid not found or amount is negative
        """
        kid = self._get_kid(kid_id)
        if not kid:
            const.LOGGER.error(
                "EconomyManager.deposit: Kid ID '%s' not found",
                kid_id,
            )
            raise ValueError(f"Kid not found: {kid_id}")

        if amount < 0:
            raise ValueError(f"Deposit amount must be positive, got {amount}")

        # Apply multiplier if requested (e.g., for chore approvals)
        actual_amount = amount
        if apply_multiplier:
            multiplier = float(kid.get(const.DATA_KID_POINTS_MULTIPLIER, 1.0))
            actual_amount = EconomyEngine.calculate_with_multiplier(amount, multiplier)

        # Get current balance
        current_balance = self.get_balance(kid_id)

        # Create ledger entry
        entry = EconomyEngine.create_ledger_entry(
            current_balance=current_balance,
            delta=actual_amount,
            source=source,
            reference_id=reference_id,
        )

        # Update balance
        new_balance = EconomyEngine.calculate_new_balance(
            current_balance, actual_amount
        )
        kid[const.DATA_KID_POINTS] = new_balance

        # Append to ledger and prune
        ledger = self._ensure_ledger(kid)
        ledger.append(entry)
        EconomyEngine.prune_ledger(ledger, const.DEFAULT_LEDGER_MAX_ENTRIES)

        # Emit event for listeners (StatisticsManager will handle stats)
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_CHANGED,
            kid_id=kid_id,
            old_balance=current_balance,
            new_balance=new_balance,
            delta=actual_amount,
            source=source,
            reference_id=reference_id,
        )

        const.LOGGER.debug(
            "EconomyManager.deposit: kid=%s, amount=%.2f (actual=%.2f), "
            "old=%.2f, new=%.2f, source=%s",
            kid_id,
            amount,
            actual_amount,
            current_balance,
            new_balance,
            source,
        )

        return new_balance

    async def withdraw(
        self,
        kid_id: str,
        amount: float,
        *,
        source: str,
        reference_id: str | None = None,
    ) -> float:
        """Remove points from a kid's balance.

        Args:
            kid_id: The internal UUID of the kid
            amount: Amount to remove (must be positive - will be negated internally)
            source: Transaction source (POINTS_SOURCE_REWARDS, POINTS_SOURCE_PENALTIES, etc.)
            reference_id: Optional related entity ID (reward_id, etc.)

        Returns:
            New balance after withdrawal

        Raises:
            ValueError: If kid not found or amount is negative
            InsufficientFundsError: If balance is less than amount (NSF)
        """
        kid = self._get_kid(kid_id)
        if not kid:
            const.LOGGER.error(
                "EconomyManager.withdraw: Kid ID '%s' not found",
                kid_id,
            )
            raise ValueError(f"Kid not found: {kid_id}")

        if amount < 0:
            raise ValueError(f"Withdraw amount must be positive, got {amount}")

        # Get current balance
        current_balance = self.get_balance(kid_id)

        # NSF check
        if not EconomyEngine.validate_sufficient_funds(current_balance, amount):
            const.LOGGER.warning(
                "EconomyManager.withdraw: NSF for kid=%s, balance=%.2f, requested=%.2f",
                kid_id,
                current_balance,
                amount,
            )
            raise InsufficientFundsError(
                kid_id=kid_id,
                current_balance=current_balance,
                requested_amount=amount,
            )

        # Create ledger entry (negative delta for withdrawal)
        entry = EconomyEngine.create_ledger_entry(
            current_balance=current_balance,
            delta=-amount,  # Negative for withdrawal
            source=source,
            reference_id=reference_id,
        )

        # Update balance
        new_balance = EconomyEngine.calculate_new_balance(current_balance, -amount)
        kid[const.DATA_KID_POINTS] = new_balance

        # Append to ledger and prune
        ledger = self._ensure_ledger(kid)
        ledger.append(entry)
        EconomyEngine.prune_ledger(ledger, const.DEFAULT_LEDGER_MAX_ENTRIES)

        # Emit event for listeners (StatisticsManager will handle stats)
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_CHANGED,
            kid_id=kid_id,
            old_balance=current_balance,
            new_balance=new_balance,
            delta=-amount,
            source=source,
            reference_id=reference_id,
        )

        const.LOGGER.debug(
            "EconomyManager.withdraw: kid=%s, amount=%.2f, old=%.2f, new=%.2f, source=%s",
            kid_id,
            amount,
            current_balance,
            new_balance,
            source,
        )

        return new_balance

    # =========================================================================
    # Penalty Operations
    # =========================================================================

    async def apply_penalty(
        self, parent_name: str, kid_id: str, penalty_id: str
    ) -> float:
        """Apply penalty to kid - deducts points via withdraw().

        This method:
        1. Validates penalty and kid exist
        2. Withdraws points (emits POINTS_CHANGED)
        3. Updates penalty tracking counter
        4. Sends notification to kid
        5. Persists changes

        Args:
            parent_name: Name of parent applying penalty (for audit trail)
            kid_id: The kid's internal ID
            penalty_id: The penalty's internal ID

        Returns:
            New balance after penalty

        Raises:
            HomeAssistantError: If kid or penalty not found
        """
        penalty_info = self._coordinator.penalties_data.get(penalty_id)
        if not penalty_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PENALTY,
                    "name": penalty_id,
                },
            )

        kid_info: KidData | None = self._get_kid(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        penalty_pts = penalty_info.get(const.DATA_PENALTY_POINTS, const.DEFAULT_ZERO)

        # Penalties are negative - use withdraw for deduction
        # Note: Penalties can go negative, so we don't use NSF check
        # We manually update balance to allow negative
        current_balance = self.get_balance(kid_id)
        new_balance = current_balance - abs(penalty_pts)
        kid_info[const.DATA_KID_POINTS] = new_balance

        # Create ledger entry
        entry = EconomyEngine.create_ledger_entry(
            current_balance=current_balance,
            delta=-abs(penalty_pts),
            source=const.POINTS_SOURCE_PENALTIES,
            reference_id=penalty_id,
        )
        ledger = self._ensure_ledger(kid_info)
        ledger.append(entry)
        EconomyEngine.prune_ledger(ledger, const.DEFAULT_LEDGER_MAX_ENTRIES)

        # Emit event for GamificationManager
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_CHANGED,
            kid_id=kid_id,
            old_balance=current_balance,
            new_balance=new_balance,
            delta=-abs(penalty_pts),
            source=const.POINTS_SOURCE_PENALTIES,
            reference_id=penalty_id,
        )

        # Update penalty tracking counter
        penalty_applies = kid_info[const.DATA_KID_PENALTY_APPLIES]
        if penalty_id in penalty_applies:
            penalty_applies[penalty_id] = int(penalty_applies[penalty_id]) + 1  # type: ignore[assignment]
        else:
            penalty_applies[penalty_id] = 1  # type: ignore[assignment]

        # Emit event for NotificationManager to send notification
        self.emit(
            const.SIGNAL_SUFFIX_PENALTY_APPLIED,
            kid_id=kid_id,
            penalty_id=penalty_id,
            penalty_name=penalty_info[const.DATA_PENALTY_NAME],
            points=penalty_pts,
        )

        const.LOGGER.debug(
            "EconomyManager.apply_penalty: kid=%s, penalty=%s, pts=%.2f, new_balance=%.2f",
            kid_id,
            penalty_id,
            penalty_pts,
            new_balance,
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        return new_balance

    async def reset_penalties(
        self, kid_id: str | None = None, penalty_id: str | None = None
    ) -> None:
        """Reset penalty tracking counters.

        Does NOT restore points - only clears the "times applied" counters.

        Args:
            kid_id: Optional kid ID to reset penalties for
            penalty_id: Optional penalty ID to reset

        Behavior:
        - kid_id + penalty_id: Reset specific penalty counter for specific kid
        - penalty_id only: Reset that penalty counter for all kids
        - kid_id only: Reset all penalty counters for that kid
        - Neither: Reset all penalty counters for all kids

        Raises:
            HomeAssistantError: If specified kid not found or penalty not assigned
        """
        if penalty_id and kid_id:
            # Reset a specific penalty for a specific kid
            kid_info: KidData | None = self._get_kid(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if penalty_id not in kid_info.get(const.DATA_KID_PENALTY_APPLIES, {}):
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Penalty ID '%s' does not apply to Kid ID '%s'",
                    penalty_id,
                    kid_id,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": f"penalty '{penalty_id}'",
                        "kid": kid_id,
                    },
                )

            kid_info[const.DATA_KID_PENALTY_APPLIES].pop(penalty_id, None)

        elif penalty_id:
            # Reset a specific penalty for all kids
            found = False
            for kid_info_loop in self._coordinator.kids_data.values():
                if penalty_id in kid_info_loop.get(const.DATA_KID_PENALTY_APPLIES, {}):
                    found = True
                    kid_info_loop[const.DATA_KID_PENALTY_APPLIES].pop(penalty_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Penalties - Penalty ID '%s' not found in any kid's data",
                    penalty_id,
                )

        elif kid_id:
            # Reset all penalties for a specific kid
            kid_info_elif: KidData | None = self._get_kid(kid_id)
            if not kid_info_elif:
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info_elif[const.DATA_KID_PENALTY_APPLIES].clear()

        else:
            # Reset all penalties for all kids
            const.LOGGER.info(
                "INFO: Reset Penalties - Resetting all penalties for all kids"
            )
            for kid_info in self._coordinator.kids_data.values():
                kid_info[const.DATA_KID_PENALTY_APPLIES].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Penalties completed - Kid ID '%s', Penalty ID '%s'",
            kid_id,
            penalty_id,
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    # =========================================================================
    # Bonus Operations
    # =========================================================================

    async def apply_bonus(self, parent_name: str, kid_id: str, bonus_id: str) -> float:
        """Apply bonus to kid - adds points via deposit().

        This method:
        1. Validates bonus and kid exist
        2. Deposits points (emits POINTS_CHANGED)
        3. Updates bonus tracking counter
        4. Sends notification to kid
        5. Persists changes

        Args:
            parent_name: Name of parent applying bonus (for audit trail)
            kid_id: The kid's internal ID
            bonus_id: The bonus's internal ID

        Returns:
            New balance after bonus

        Raises:
            HomeAssistantError: If kid or bonus not found
        """
        bonus_info = self._coordinator.bonuses_data.get(bonus_id)
        if not bonus_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BONUS,
                    "name": bonus_id,
                },
            )

        kid_info: KidData | None = self._get_kid(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        bonus_pts = bonus_info.get(const.DATA_BONUS_POINTS, const.DEFAULT_ZERO)

        # Use deposit for bonus (emits POINTS_CHANGED)
        new_balance = await self.deposit(
            kid_id=kid_id,
            amount=bonus_pts,
            source=const.POINTS_SOURCE_BONUSES,
            reference_id=bonus_id,
            apply_multiplier=False,  # Bonuses don't use multiplier
        )

        # Update bonus tracking counter
        bonus_applies = kid_info[const.DATA_KID_BONUS_APPLIES]
        if bonus_id in bonus_applies:
            bonus_applies[bonus_id] = int(bonus_applies[bonus_id]) + 1  # type: ignore[assignment]
        else:
            bonus_applies[bonus_id] = 1  # type: ignore[assignment]

        # Emit event for NotificationManager to send notification
        self.emit(
            const.SIGNAL_SUFFIX_BONUS_APPLIED,
            kid_id=kid_id,
            bonus_id=bonus_id,
            bonus_name=bonus_info[const.DATA_BONUS_NAME],
            points=bonus_pts,
        )

        const.LOGGER.debug(
            "EconomyManager.apply_bonus: kid=%s, bonus=%s, pts=%.2f, new_balance=%.2f",
            kid_id,
            bonus_id,
            bonus_pts,
            new_balance,
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        return new_balance

    async def reset_bonuses(
        self, kid_id: str | None = None, bonus_id: str | None = None
    ) -> None:
        """Reset bonus tracking counters.

        Does NOT remove points - only clears the "times applied" counters.

        Args:
            kid_id: Optional kid ID to reset bonuses for
            bonus_id: Optional bonus ID to reset

        Behavior:
        - kid_id + bonus_id: Reset specific bonus counter for specific kid
        - bonus_id only: Reset that bonus counter for all kids
        - kid_id only: Reset all bonus counters for that kid
        - Neither: Reset all bonus counters for all kids

        Raises:
            HomeAssistantError: If specified kid not found or bonus not assigned
        """
        if bonus_id and kid_id:
            # Reset a specific bonus for a specific kid
            kid_info: KidData | None = self._get_kid(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if bonus_id not in kid_info.get(const.DATA_KID_BONUS_APPLIES, {}):
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Bonus '%s' does not apply to Kid ID '%s'",
                    bonus_id,
                    kid_id,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": f"bonus '{bonus_id}'",
                        "kid": kid_id,
                    },
                )

            kid_info[const.DATA_KID_BONUS_APPLIES].pop(bonus_id, None)

        elif bonus_id:
            # Reset a specific bonus for all kids
            found = False
            for kid_info_loop in self._coordinator.kids_data.values():
                if bonus_id in kid_info_loop.get(const.DATA_KID_BONUS_APPLIES, {}):
                    found = True
                    kid_info_loop[const.DATA_KID_BONUS_APPLIES].pop(bonus_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Bonuses - Bonus '%s' not found in any kid's data",
                    bonus_id,
                )

        elif kid_id:
            # Reset all bonuses for a specific kid
            kid_info_elif: KidData | None = self._get_kid(kid_id)
            if not kid_info_elif:
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info_elif[const.DATA_KID_BONUS_APPLIES].clear()

        else:
            # Reset all bonuses for all kids
            const.LOGGER.info(
                "INFO: Reset Bonuses - Resetting all bonuses for all kids"
            )
            for kid_info in self._coordinator.kids_data.values():
                kid_info[const.DATA_KID_BONUS_APPLIES].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Bonuses completed - Kid ID '%s', Bonus ID '%s'",
            kid_id,
            bonus_id,
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)
