"""Engine modules for KidsChores integration.

Contains specialized computation engines:
- chore_engine: Chore state machine, transitions, and validation
- economy_engine: Point transactions and ledger management
- schedule: Recurrence calculation and RRULE generation
- statistics: Point aggregation and history tracking
"""

# Use relative imports within package to avoid mypy module resolution issues
from .chore_engine import (
    CHORE_ACTION_APPROVE,
    CHORE_ACTION_CLAIM,
    CHORE_ACTION_DISAPPROVE,
    CHORE_ACTION_OVERDUE,
    CHORE_ACTION_RESET,
    CHORE_ACTION_UNDO,
    ChoreEngine,
    TransitionEffect,
)
from .economy_engine import EconomyEngine, InsufficientFundsError
from .gamification_engine import GamificationEngine
from .schedule import RecurrenceEngine, calculate_next_due_date_from_chore_info
from .statistics import StatisticsEngine

__all__ = [
    "CHORE_ACTION_APPROVE",
    "CHORE_ACTION_CLAIM",
    "CHORE_ACTION_DISAPPROVE",
    "CHORE_ACTION_OVERDUE",
    "CHORE_ACTION_RESET",
    "CHORE_ACTION_UNDO",
    "ChoreEngine",
    "EconomyEngine",
    "GamificationEngine",
    "InsufficientFundsError",
    "RecurrenceEngine",
    "StatisticsEngine",
    "TransitionEffect",
    "calculate_next_due_date_from_chore_info",
]
