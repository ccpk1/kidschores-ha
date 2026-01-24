"""Manager modules for KidsChores integration.

Managers orchestrate workflows and coordinate between engines.
They are stateful, event-aware, and handle cross-cutting concerns.
"""

from .base_manager import BaseManager
from .economy_manager import EconomyManager
from .notification_manager import NotificationManager

__all__ = [
    "BaseManager",
    "EconomyManager",
    "NotificationManager",
]
