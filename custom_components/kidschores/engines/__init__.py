"""Engine modules for KidsChores integration.

Contains specialized computation engines:
- schedule: Recurrence calculation and RRULE generation
- statistics: Point aggregation and history tracking
"""

# Use relative imports within package to avoid mypy module resolution issues
from .schedule import RecurrenceEngine, calculate_next_due_date_from_chore_info
from .statistics import StatisticsEngine

__all__ = [
    "RecurrenceEngine",
    "StatisticsEngine",
    "calculate_next_due_date_from_chore_info",
]
