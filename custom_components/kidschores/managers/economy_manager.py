"""Economy Manager - Point transactions and ledger management.

This manager handles all point-related operations:
- Deposits (adding points)
- Withdrawals (removing points with NSF checks)
- Ledger management (transaction history)
- Event emission for point changes

ARCHITECTURE (v0.5.0+):
- EconomyManager = "The Bank" (STATEFUL point operations)
- EconomyEngine = Pure math and ledger logic (STATELESS)
- Coordinator handles gamification checks (Phase 3 - inline; Phase 5 - event-based)

The manager does NOT know about NotificationManager - the Coordinator handles
that wiring to keep managers domain-specific.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

        # Emit event for listeners (Phase 5 will use this for gamification)
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

        # Emit event for listeners
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
