"""Manager modules for KidsChores integration.

Managers orchestrate workflows and coordinate between engines.
They are stateful, event-aware, and handle cross-cutting concerns.
"""

from .base_manager import BaseManager
from .chore_manager import ChoreManager
from .economy_manager import EconomyManager
from .gamification_manager import GamificationManager
from .notification_manager import NotificationManager
from .reward_manager import RewardManager
from .statistics_manager import StatisticsManager

__all__ = [
    "BaseManager",
    "ChoreManager",
    "EconomyManager",
    "GamificationManager",
    "NotificationManager",
    "RewardManager",
    "StatisticsManager",
]
