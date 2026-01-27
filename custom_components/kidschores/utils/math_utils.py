# File: utils/math_utils.py
"""Math and calculation utilities for KidsChores.

Pure Python math functions with ZERO Home Assistant dependencies.
All functions here can be unit tested without Home Assistant mocking.

⚠️ DIRECTIVE 1 - UTILS PURITY: NO `homeassistant.*` imports allowed.

Functions:
    - round_points: Consistent rounding to configured precision
    - apply_multiplier: Multiplier arithmetic with proper rounding
    - calculate_percentage: Progress percentage calculations
    - parse_points_adjust_values: Parse pipe-separated point values
"""

from __future__ import annotations

import logging

# Module-level logger (no HA dependency)
_LOGGER = logging.getLogger(__name__)

# ==============================================================================
# Constants (local copies to avoid circular imports)
# ==============================================================================

# Default float precision for point rounding
DATA_FLOAT_PRECISION = 2


# ==============================================================================
# Point Arithmetic Functions (AMENDMENT - Phase 7.1.3)
# ==============================================================================


def round_points(value: float, precision: int = DATA_FLOAT_PRECISION) -> float:
    """Round a point value to the configured precision.

    Provides consistent rounding across the integration for all point-related
    calculations.

    Args:
        value: The float value to round
        precision: Number of decimal places (default: DATA_FLOAT_PRECISION)

    Returns:
        Rounded float value

    Examples:
        round_points(10.456) → 10.46
        round_points(10.454) → 10.45
        round_points(10.0) → 10.0
    """
    return round(value, precision)


def apply_multiplier(
    base: float,
    multiplier: float,
    precision: int = DATA_FLOAT_PRECISION,
) -> float:
    """Apply a multiplier to a base value with proper rounding.

    Used for streak multipliers, bonus multipliers, etc.

    Args:
        base: Base point value
        multiplier: Multiplier to apply (e.g., 1.5 for 50% bonus)
        precision: Number of decimal places for rounding

    Returns:
        Calculated value with proper rounding

    Examples:
        apply_multiplier(10, 1.5) → 15.0
        apply_multiplier(10, 1.333) → 13.33
        apply_multiplier(10, 0.5) → 5.0
    """
    return round_points(base * multiplier, precision)


def calculate_percentage(
    current: float,
    target: float,
    precision: int = DATA_FLOAT_PRECISION,
) -> float:
    """Calculate progress percentage with proper rounding.

    Args:
        current: Current progress value
        target: Target/total value
        precision: Number of decimal places for rounding

    Returns:
        Percentage (0-100) with proper rounding, or 0.0 if target is 0

    Examples:
        calculate_percentage(50, 100) → 50.0
        calculate_percentage(33, 100) → 33.0
        calculate_percentage(1, 3) → 33.33
        calculate_percentage(5, 0) → 0.0  # Division by zero protection
    """
    if target <= 0:
        return 0.0
    return round_points((current / target) * 100, precision)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between minimum and maximum bounds.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Value clamped to [min_val, max_val] range

    Examples:
        clamp(150, 0, 100) → 100
        clamp(-10, 0, 100) → 0
        clamp(50, 0, 100) → 50
    """
    return max(min_val, min(value, max_val))


# ==============================================================================
# Point String Parsing
# ==============================================================================


def parse_points_adjust_values(points_str: str | None) -> list[float]:
    """Parse a pipe-separated string into a list of float values.

    Handles international decimal separator differences by converting
    comma decimal separators to periods before parsing.

    Args:
        points_str: Pipe-separated string of point values (e.g., "5|10|15")

    Returns:
        List of parsed float values. Invalid entries are skipped with warning.

    Examples:
        parse_points_adjust_values("5|10|15") → [5.0, 10.0, 15.0]
        parse_points_adjust_values("5,5|10,5") → [5.5, 10.5]  # European format
        parse_points_adjust_values("invalid|10") → [10.0]  # Skips invalid
        parse_points_adjust_values(None) → []
    """
    if not points_str:
        return []

    values: list[float] = []
    for part in points_str.split("|"):
        part = part.strip()
        if not part:
            continue

        try:
            # Handle European decimal separators (comma → period)
            value = float(part.replace(",", "."))
            values.append(value)
        except ValueError:
            _LOGGER.error("Invalid number '%s' in points adjust values", part)

    return values
