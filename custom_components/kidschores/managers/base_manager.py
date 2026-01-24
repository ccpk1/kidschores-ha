"""Base manager class for KidsChores managers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from custom_components.kidschores import const, kc_helpers as kh

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator


class BaseManager(ABC):
    """Base class for all KidsChores managers with scoped event support.

    Provides:
    - Instance-scoped event emitting (emit)
    - Instance-scoped event listening (listen)
    - Automatic cleanup via coordinator's config_entry.async_on_unload

    Subclasses must implement:
    - async_setup(): Subscribe to events, initialize state
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: KidsChoresDataCoordinator
    ) -> None:
        """Initialize manager.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator managing this integration instance
        """
        self.hass = hass
        self.coordinator = coordinator
        self.entry_id = coordinator.config_entry.entry_id

    def emit(self, suffix: str, **payload: Any) -> None:
        """Emit instance-scoped event to other managers.

        Args:
            suffix: Signal suffix constant (e.g., const.SIGNAL_SUFFIX_POINTS_CHANGED)
            **payload: Event data dict passed to listeners (must be JSON-serializable)

        Example:
            self.emit(
                const.SIGNAL_SUFFIX_POINTS_CHANGED,
                kid_id=kid_id,
                old_balance=50.0,
                new_balance=60.0,
                delta=10.0,
                source="chore_approval"
            )
        """
        signal = kh.get_event_signal(self.entry_id, suffix)
        const.LOGGER.debug(
            "Emitting event '%s' for instance %s with payload keys: %s",
            suffix,
            self.entry_id,
            list(payload.keys()),
        )
        async_dispatcher_send(self.hass, signal, **payload)

    def listen(self, suffix: str, callback: Callable[..., None]) -> None:
        """Subscribe to instance-scoped event with automatic cleanup.

        The subscription is automatically cleaned up when the config entry is unloaded.

        Args:
            suffix: Signal suffix constant to listen for
            callback: Async function called when event fires (receives **payload)

        Example:
            async def _on_points_changed(self, kid_id: str, new_balance: float, **kwargs):
                await self.recalculate_badges(kid_id)

            # In async_setup():
            self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)
        """
        signal = kh.get_event_signal(self.entry_id, suffix)
        unsub = async_dispatcher_connect(self.hass, signal, callback)
        self.coordinator.config_entry.async_on_unload(unsub)
        const.LOGGER.debug(
            "Manager %s listening to event '%s' for instance %s",
            self.__class__.__name__,
            suffix,
            self.entry_id,
        )

    @abstractmethod
    async def async_setup(self) -> None:
        """Set up the manager (subscribe to events, initialize state).

        Called once during coordinator initialization.
        Subclasses should subscribe to events here using self.listen().
        """
