# File: kc_helpers.py
"""KidsChores helper functions and shared logic.

## Organization Guide (Sections Below)

This file is organized into logical sections for easy navigation:

1. **Event Signal Helpers** 📡
   - Manager communication signals (get_event_signal)

2. **Data Cleanup Helpers** 🧹
   - Orphan reference removal during entity deletion (stateless functions)

3. **Entity Lookup Helpers** 🔍
   - Basic ID/name lookups (returns None if not found)
   - Error-raising variants for services (raises HomeAssistantError)
   - Kid name lookups

4. **Shadow Kid Helpers** 👤
   - Parent chore capability detection and workflow control

5. **Progress & Completion Helpers** 🧮
   - Badge progress, chore completion, streak calculations

6. **Custom Translation Loaders** 🌐
   - Dashboard and notification translation loading with caching

## Extracted Modules (v0.5.0+)

Pure Python utilities extracted to `utils/`:
- `utils/dt_utils.py` - DateTime parsing, UTC conversion, interval calculations
- `utils/math_utils.py` - Point arithmetic, parsing adjustment values

HA-bound helpers extracted to `helpers/`:
- `helpers/entity_helpers.py` - Entity registry queries, parsing, removal
- `helpers/auth_helpers.py` - User authorization checks
- `helpers/device_helpers.py` - DeviceInfo construction

"""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportReturnType=false, reportOperatorIssue=false

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError

from . import const
from .utils.dt_utils import dt_now_local, dt_today_iso

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

    from .coordinator import KidsChoresDataCoordinator  # Used for type checking only
    from .type_defs import KidData


# ==============================================================================
# Event Signal Helpers (Manager Communication)
# ==============================================================================


def get_event_signal(entry_id: str, suffix: str) -> str:
    """Build instance-scoped event signal name for dispatcher.

    This ensures complete isolation between multiple KidsChores config entries.
    Each instance gets its own signal namespace using its config_entry.entry_id.

    Format: 'kidschores_{entry_id}_{suffix}'

    Multi-instance example:
        - Instance 1 (entry_id="abc123"):
          get_event_signal("abc123", "points_changed") → "kidschores_abc123_points_changed"
        - Instance 2 (entry_id="xyz789"):
          get_event_signal("xyz789", "points_changed") → "kidschores_xyz789_points_changed"

    Managers can emit/listen without cross-talk between instances.

    Args:
        entry_id: ConfigEntry.entry_id from coordinator
        suffix: Signal suffix constant from const.py (e.g., SIGNAL_SUFFIX_POINTS_CHANGED)

    Returns:
        Fully qualified signal name scoped to this integration instance

    Example:
        >>> from . import const
        >>> get_event_signal("abc123", const.SIGNAL_SUFFIX_POINTS_CHANGED)
        'kidschores_abc123_points_changed'
    """
    return f"{const.DOMAIN}_{entry_id}_{suffix}"


# ==============================================================================
# Data Cleanup Helpers (Orphan Reference Removal)
# Stateless functions for cleaning up orphaned references when entities are deleted.
# These are called by the coordinator during delete operations.
# ==============================================================================


def cleanup_chore_from_kid_data(
    kid_data: dict[str, Any],
    chore_id: str,
) -> bool:
    """Remove references to a specific chore from a kid's data dict.

    Stateless helper called during chore deletion or reassignment.

    Args:
        kid_data: The kid's data dict (mutated in place).
        chore_id: ID of the chore to remove references for.

    Returns:
        True if any references were removed, False otherwise.
    """
    cleaned = False

    # Remove from kid_chore_data (timestamp-based tracking v0.4.0+)
    if const.DATA_KID_CHORE_DATA in kid_data:
        if chore_id in kid_data[const.DATA_KID_CHORE_DATA]:
            del kid_data[const.DATA_KID_CHORE_DATA][chore_id]
            const.LOGGER.debug(
                "Removed chore '%s' from kid's chore data",
                chore_id,
            )
            cleaned = True

    return cleaned


def cleanup_orphaned_reward_data(
    kids_data: dict[str, dict[str, Any]],
    valid_reward_ids: set[str],
) -> bool:
    """Remove reward_data entries for rewards that no longer exist.

    Stateless helper called during reward deletion.

    Args:
        kids_data: Dict of kid_id -> kid_data (mutated in place).
        valid_reward_ids: Set of reward IDs that still exist.

    Returns:
        True if any references were removed, False otherwise.
    """
    cleaned = False
    for kid_data in kids_data.values():
        reward_data = kid_data.get(const.DATA_KID_REWARD_DATA, {})
        invalid_ids = [rid for rid in reward_data if rid not in valid_reward_ids]
        for rid in invalid_ids:
            reward_data.pop(rid, None)
            cleaned = True
    return cleaned


def cleanup_orphaned_kid_refs_in_chores(
    chores_data: dict[str, dict[str, Any]],
    valid_kid_ids: set[str],
) -> bool:
    """Remove deleted kid IDs from chore assignments.

    Stateless helper called during kid deletion.

    Args:
        chores_data: Dict of chore_id -> chore_data (mutated in place).
        valid_kid_ids: Set of kid IDs that still exist.

    Returns:
        True if any references were removed, False otherwise.
    """
    cleaned = False
    for chore_info in chores_data.values():
        if const.DATA_CHORE_ASSIGNED_KIDS in chore_info:
            original = chore_info[const.DATA_CHORE_ASSIGNED_KIDS]
            filtered = [kid for kid in original if kid in valid_kid_ids]
            if filtered != original:
                chore_info[const.DATA_CHORE_ASSIGNED_KIDS] = filtered
                const.LOGGER.debug(
                    "Removed orphaned kid refs from chore '%s'",
                    chore_info.get(const.DATA_CHORE_NAME),
                )
                cleaned = True
    return cleaned


def cleanup_orphaned_kid_refs_in_gamification(
    entities_data: dict[str, dict[str, Any]],
    valid_kid_ids: set[str],
    section_name: str,
) -> bool:
    """Remove deleted kid IDs from achievement/challenge progress and assignments.

    Stateless helper called during kid deletion.

    Args:
        entities_data: Dict of entity_id -> entity_data (mutated in place).
        valid_kid_ids: Set of kid IDs that still exist.
        section_name: Name for logging ("achievements" or "challenges").

    Returns:
        True if any references were removed, False otherwise.
    """
    cleaned = False
    for entity in entities_data.values():
        progress = entity.get(const.DATA_PROGRESS, {})
        keys_to_remove = [kid for kid in progress if kid not in valid_kid_ids]
        for kid in keys_to_remove:
            del progress[kid]
            const.LOGGER.debug(
                "Removed progress for deleted kid '%s' in %s",
                kid,
                section_name,
            )
            cleaned = True

        if const.DATA_ASSIGNED_KIDS in entity:
            original_assigned = entity[const.DATA_ASSIGNED_KIDS]
            filtered_assigned = [
                kid for kid in original_assigned if kid in valid_kid_ids
            ]
            if filtered_assigned != original_assigned:
                entity[const.DATA_ASSIGNED_KIDS] = filtered_assigned
                const.LOGGER.debug(
                    "Removed orphaned kid refs from %s '%s'",
                    section_name,
                    entity.get(const.DATA_NAME),
                )
                cleaned = True
    return cleaned


def cleanup_orphaned_chore_refs_in_kids(
    kids_data: dict[str, dict[str, Any]],
    valid_chore_ids: set[str],
) -> bool:
    """Remove deleted chore IDs from all kids' chore data.

    Stateless helper called during chore deletion.

    Args:
        kids_data: Dict of kid_id -> kid_data (mutated in place).
        valid_chore_ids: Set of chore IDs that still exist.

    Returns:
        True if any references were removed, False otherwise.
    """
    cleaned = False
    for kid_data in kids_data.values():
        if const.DATA_KID_CHORE_DATA in kid_data:
            original_count = len(kid_data[const.DATA_KID_CHORE_DATA])
            kid_data[const.DATA_KID_CHORE_DATA] = {
                chore: data
                for chore, data in kid_data[const.DATA_KID_CHORE_DATA].items()
                if chore in valid_chore_ids
            }
            if len(kid_data[const.DATA_KID_CHORE_DATA]) < original_count:
                cleaned = True
    return cleaned


def cleanup_orphaned_kid_refs_in_parents(
    parents_data: dict[str, dict[str, Any]],
    valid_kid_ids: set[str],
) -> bool:
    """Remove deleted kid IDs from parent's associated_kids lists.

    Stateless helper called during kid deletion.

    Args:
        parents_data: Dict of parent_id -> parent_data (mutated in place).
        valid_kid_ids: Set of kid IDs that still exist.

    Returns:
        True if any references were removed, False otherwise.
    """
    cleaned = False
    for parent_info in parents_data.values():
        original = parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, [])
        filtered = [kid_id for kid_id in original if kid_id in valid_kid_ids]
        if filtered != original:
            parent_info[const.DATA_PARENT_ASSOCIATED_KIDS] = filtered
            const.LOGGER.debug(
                "Removed orphaned kid refs from parent '%s'",
                parent_info.get(const.DATA_PARENT_NAME),
            )
            cleaned = True
    return cleaned


def cleanup_deleted_chore_in_gamification(
    entities_data: dict[str, dict[str, Any]],
    valid_chore_ids: set[str],
    selected_chore_key: str,
    default_value: str,
    section_name: str,
) -> bool:
    """Clear selected_chore_id in achievements/challenges if the chore no longer exists.

    Stateless helper called during chore deletion.

    Args:
        entities_data: Dict of entity_id -> entity_data (mutated in place).
        valid_chore_ids: Set of chore IDs that still exist.
        selected_chore_key: Const key for selected chore (e.g., DATA_ACHIEVEMENT_SELECTED_CHORE_ID).
        default_value: Value to set when clearing (e.g., "" or SENTINEL_EMPTY).
        section_name: Name for logging ("achievement" or "challenge").

    Returns:
        True if any references were removed, False otherwise.
    """
    cleaned = False
    for entity_info in entities_data.values():
        selected = entity_info.get(selected_chore_key)
        if selected and selected not in valid_chore_ids:
            entity_info[selected_chore_key] = default_value
            const.LOGGER.debug(
                "Cleared selected chore in %s '%s'",
                section_name,
                entity_info.get(const.DATA_NAME),
            )
            cleaned = True
    return cleaned


# ==============================================================================
# Entity Lookup Helpers
# Basic ID/name lookups returning None, and error-raising variants for services.
# Includes kid name lookups and label registry helpers.
# ==============================================================================


def get_chore_data_for_kid(
    kid_data: Mapping[str, Any], chore_id: str
) -> dict[str, Any]:
    """Get the chore data dict for a specific kid+chore combination.

    Stateless helper function for accessing per-kid chore data from kid_data.
    Returns an empty dict if the chore data doesn't exist.

    Args:
        kid_data: The kid's data dict (from kids_data[kid_id])
        chore_id: The internal ID of the chore

    Returns:
        The kid's chore data dict for this chore, or empty dict if not found.
    """
    chore_data_map = kid_data.get(const.DATA_KID_CHORE_DATA, {})
    return chore_data_map.get(chore_id, {})


def get_entity_id_by_name(
    coordinator: KidsChoresDataCoordinator, entity_type: str, entity_name: str
) -> str | None:
    """Generic entity ID lookup by name across all entity types.

    Replaces duplicate get_*_id_by_name() functions with a single parametrizable
    implementation that maps entity types to their data dictionaries and name keys.

    Args:
        coordinator: The KidsChores data coordinator.
        entity_type: The type of entity ("kid", "chore", "reward", "penalty",
            "badge", "bonus", "parent", "achievement", "challenge").
        entity_name: The name of the entity to look up.

    Returns:
        The internal ID (UUID) of the entity, or None if not found.

    Raises:
        ValueError: If entity_type is not recognized.
    """
    # Map entity type to (data dict, name key constant)
    entity_map = {
        const.ENTITY_TYPE_KID: (coordinator.kids_data, const.DATA_KID_NAME),
        const.ENTITY_TYPE_CHORE: (coordinator.chores_data, const.DATA_CHORE_NAME),
        const.ENTITY_TYPE_REWARD: (coordinator.rewards_data, const.DATA_REWARD_NAME),
        const.ENTITY_TYPE_PENALTY: (
            coordinator.penalties_data,
            const.DATA_PENALTY_NAME,
        ),
        const.ENTITY_TYPE_BADGE: (coordinator.badges_data, const.DATA_BADGE_NAME),
        const.ENTITY_TYPE_BONUS: (coordinator.bonuses_data, const.DATA_BONUS_NAME),
        const.ENTITY_TYPE_PARENT: (coordinator.parents_data, const.DATA_PARENT_NAME),
        const.ENTITY_TYPE_ACHIEVEMENT: (
            coordinator.achievements_data,
            const.DATA_ACHIEVEMENT_NAME,
        ),
        const.ENTITY_TYPE_CHALLENGE: (
            coordinator.challenges_data,
            const.DATA_CHALLENGE_NAME,
        ),
    }

    if entity_type not in entity_map:
        raise ValueError(
            f"Unknown entity_type: {entity_type}. Valid options: {', '.join(entity_map.keys())}"
        )

    data_dict, name_key = entity_map[entity_type]
    data_dict = cast("dict[str, Any]", data_dict)
    for entity_id, entity_info in data_dict.items():
        if entity_info.get(name_key) == entity_name:
            return entity_id
    return None


def get_entity_id_or_raise(
    coordinator: KidsChoresDataCoordinator, entity_type: str, entity_name: str
) -> str:
    """Get entity ID by name or raise HomeAssistantError if not found.

    Generic version of all *_or_raise() functions. Centralizes error
    handling pattern for entity lookups across services.

    Args:
        coordinator: The KidsChores data coordinator.
        entity_type: The type of entity ("kid", "chore", "reward", "penalty",
            "badge", "bonus", "parent", "achievement", "challenge").
        entity_name: The name of the entity to look up.

    Returns:
        The internal ID (UUID) of the entity.

    Raises:
        HomeAssistantError: If the entity is not found.
    """
    entity_id = get_entity_id_by_name(coordinator, entity_type, entity_name)
    if not entity_id:
        raise HomeAssistantError(
            f"{entity_type.capitalize()} '{entity_name}' not found"
        )
    return entity_id


def get_entity_name_or_log_error(
    entity_type: str,
    entity_id: str,
    entity_data: Mapping[str, Any],
    name_key: str,
) -> str | None:
    """Get entity name from data dict, log error if missing (data corruption detection).

    Args:
        entity_type: Type of entity (for logging) e.g. 'kid', 'chore', 'reward'
        entity_id: Entity ID (for logging)
        entity_data: Dict containing entity data
        name_key: Key to look up name in entity_data

    Returns:
        Entity name if present, None if missing (with error log)
    """
    name = entity_data.get(name_key)
    if not name:
        const.LOGGER.error(
            "Data corruption: %s %s missing %s. Entity will not be created. "
            "This indicates a storage issue or validation bypass.",
            entity_type,
            entity_id,
            name_key,
        )
        return None
    return name


def get_kid_name_by_id(
    coordinator: KidsChoresDataCoordinator, kid_id: str
) -> str | None:
    """Retrieve the kid_name for a given kid_id.

    Args:
        coordinator: The KidsChores data coordinator.
        kid_id: The internal ID (UUID) of the kid to look up.

    Returns:
        The name of the kid, or None if not found.
    """
    kid_info = coordinator.kids_data.get(kid_id)
    if kid_info:
        return kid_info.get(const.DATA_KID_NAME)
    return None


# ==============================================================================
# Shadow Kid Helpers
# Parent chore capability detection and workflow/gamification control.
# ==============================================================================


def is_shadow_kid(coordinator: KidsChoresDataCoordinator, kid_id: str) -> bool:
    """Check if a kid is a shadow kid (linked to a parent).

    Shadow kids are created when a parent enables chore assignment. They
    represent the parent's profile in the chore tracking system.

    Args:
        coordinator: The KidsChores data coordinator.
        kid_id: The internal ID (UUID) of the kid to check.

    Returns:
        True if the kid is a shadow kid, False otherwise.
    """
    kid_info: KidData = cast("KidData", coordinator.kids_data.get(kid_id, {}))
    return bool(kid_info.get(const.DATA_KID_IS_SHADOW, False))


def get_parent_for_shadow_kid(
    coordinator: KidsChoresDataCoordinator, kid_id: str
) -> dict[str, Any] | None:
    """Get the parent data for a shadow kid.

    Args:
        coordinator: The KidsChores data coordinator.
        kid_id: The internal ID (UUID) of the shadow kid.

    Returns:
        The parent's data dictionary, or None if not a shadow kid or parent not found.
    """
    kid_info: KidData = cast("KidData", coordinator.kids_data.get(kid_id, {}))
    parent_id = kid_info.get(const.DATA_KID_LINKED_PARENT_ID)
    if parent_id:
        return cast("dict[str, Any] | None", coordinator.parents_data.get(parent_id))
    return None


def should_create_workflow_buttons(
    coordinator: KidsChoresDataCoordinator, kid_id: str
) -> bool:
    """Determine if claim/disapprove buttons should be created for a kid.

    Workflow buttons (Claim, Disapprove) are created for:
    - Regular kids (always have full workflow)
    - Shadow kids with enable_chore_workflow=True

    They are NOT created for:
    - Shadow kids with enable_chore_workflow=False (approval-only mode)

    Args:
        coordinator: The KidsChores data coordinator.
        kid_id: The internal ID (UUID) of the kid.

    Returns:
        True if workflow buttons should be created, False otherwise.
    """
    if not is_shadow_kid(coordinator, kid_id):
        return True  # Regular kids always get workflow buttons

    parent_data = get_parent_for_shadow_kid(coordinator, kid_id)
    if parent_data:
        return parent_data.get(const.DATA_PARENT_ENABLE_CHORE_WORKFLOW, False)
    return False


def should_create_gamification_entities(
    coordinator: KidsChoresDataCoordinator, kid_id: str
) -> bool:
    """Determine if gamification entities should be created for a kid.

    Gamification entities (points sensors, badge progress, reward/bonus/penalty
    buttons, points adjust buttons) are created for:
    - Regular kids (always have gamification)
    - Shadow kids with enable_gamification=True

    They are NOT created for:
    - Shadow kids with enable_gamification=False

    Args:
        coordinator: The KidsChores data coordinator.
        kid_id: The internal ID (UUID) of the kid.

    Returns:
        True if gamification entities should be created, False otherwise.
    """
    if not is_shadow_kid(coordinator, kid_id):
        return True  # Regular kids always get gamification

    parent_data = get_parent_for_shadow_kid(coordinator, kid_id)
    if parent_data:
        return parent_data.get(const.DATA_PARENT_ENABLE_GAMIFICATION, False)
    return False


def is_entity_allowed_for_shadow_kid(
    domain: str,
    unique_id: str,
    workflow_enabled: bool,
    gamification_enabled: bool,
) -> bool:
    """Check if an entity is allowed for a shadow kid based on parent settings.

    Delegates to should_create_entity() which uses ENTITY_REGISTRY.

    Args:
        domain: The entity domain (\"button\", \"sensor\", etc.) - unused, kept for API compatibility
        unique_id: The entity's unique_id string.
        workflow_enabled: Whether parent has chore workflow enabled.
        gamification_enabled: Whether parent has gamification enabled.

    Returns:
        True if entity is allowed, False if it should be removed.
    """
    # Delegate to unified filter function
    # Note: domain is not needed as ENTITY_REGISTRY uses suffix matching
    # Extra flag not passed here - shadow kid filtering doesn't consider extra
    # (extra entities are a system-level flag, not shadow-kid specific)
    return should_create_entity(
        unique_id,
        is_shadow_kid=True,
        workflow_enabled=workflow_enabled,
        gamification_enabled=gamification_enabled,
        extra_enabled=False,  # Shadow kid filtering ignores extra entities
    )


def should_create_entity(
    unique_id_suffix: str,
    *,
    is_shadow_kid: bool = False,
    workflow_enabled: bool = True,
    gamification_enabled: bool = True,
    extra_enabled: bool = False,
) -> bool:
    """Determine if an entity should be created based on its suffix and context.

    Single source of truth for entity creation decisions. Uses ENTITY_REGISTRY.

    === FLAG LAYERING LOGIC ===
    | Requirement   | Regular Kid           | Shadow Kid                           |
    |---------------|-----------------------|--------------------------------------|
    | ALWAYS        | Created               | Created                              |
    | WORKFLOW      | Created               | Only if workflow_enabled=True        |
    | GAMIFICATION  | Created               | Only if gamification_enabled=True    |
    | EXTRA         | If extra_enabled      | If extra_enabled AND gamification    |

    Args:
        unique_id_suffix: The entity's unique_id suffix (e.g., "_chore_status")
        is_shadow_kid: Whether this is a shadow kid
        workflow_enabled: Whether workflow is enabled (for shadow kids)
        gamification_enabled: Whether gamification is enabled (for shadow kids)
        extra_enabled: Whether show_legacy_entities (extra entities) flag is enabled

    Returns:
        True if entity should be created, False otherwise.
    """
    # Find the matching registry entry
    requirement: const.EntityRequirement | None = None
    for suffix, req in const.ENTITY_REGISTRY.items():
        if unique_id_suffix.endswith(suffix):
            requirement = req
            break

    # Unknown suffix - default to gamification (safer for shadow kids)
    if requirement is None:
        return not is_shadow_kid or gamification_enabled

    # Check requirement against context
    match requirement:
        case const.EntityRequirement.ALWAYS:
            return True
        case const.EntityRequirement.WORKFLOW:
            return not is_shadow_kid or workflow_enabled
        case const.EntityRequirement.GAMIFICATION:
            return not is_shadow_kid or gamification_enabled
        case const.EntityRequirement.EXTRA:
            # EXTRA requires BOTH extra flag AND gamification
            # Regular kids: always have gamification, so just check flag
            # Shadow kids: need flag AND gamification_enabled
            if not extra_enabled:
                return False
            return not is_shadow_kid or gamification_enabled

    return False


# ==============================================================================
# Progress & Completion Helpers
# Badge progress, chore completion, streak calculations.
# Used by badges, achievements, and challenges.
# ==============================================================================


def get_today_chore_and_point_progress(
    kid_info: Mapping[str, Any],
    tracked_chores: list[str],
) -> tuple[int, int, int, int, dict[str, int], dict[str, int], dict[str, int]]:
    """
    Calculate today's points from all sources, points from chores, total chore completions,
    and longest streak for the given kid and tracked chores.
    If tracked_chores is empty, use all chores for the kid.

    Returns:
        (
            total_points_all_sources: int,
            total_points_chores: int,
            total_chore_count: int,
            longest_chore_streak: int,
            points_per_chore: {chore_id: points_today, ...},
            count_per_chore: {chore_id: count_today, ...},
            streak_per_chore: {chore_id: streak_length, ...}
        )
    """
    today_iso = dt_today_iso()
    if not tracked_chores:
        tracked_chores = list(kid_info.get(const.DATA_KID_CHORE_DATA, {}).keys())

    total_points_chores = 0
    total_chore_count = 0
    longest_chore_streak = 0
    points_per_chore = {}
    count_per_chore = {}
    streak_per_chore = {}

    for chore_id in tracked_chores:
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        periods_data = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        daily_stats = periods_data.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})

        # Points today (from this chore)
        points_today = daily_stats.get(today_iso, {}).get(
            const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0
        )
        if points_today > 0:
            points_per_chore[chore_id] = points_today
            total_points_chores += points_today

        # Chore count today
        count_today = daily_stats.get(today_iso, {}).get(
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
        )
        if count_today > 0:
            count_per_chore[chore_id] = count_today
            total_chore_count += count_today

        # Streak: now stored in daily period data
        streak_today = daily_stats.get(today_iso, {}).get(
            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
        )
        streak_per_chore[chore_id] = streak_today
        longest_chore_streak = max(longest_chore_streak, streak_today)

    # Note: total_points_all_sources equals total_points_chores here because this
    # helper reads directly from chore period buckets. For accurate all-source
    # totals including bonuses/badges, use StatisticsManager.get_stats() cache.
    total_points_all_sources = total_points_chores

    return (
        total_points_all_sources,
        total_points_chores,
        total_chore_count,
        longest_chore_streak,
        points_per_chore,
        count_per_chore,
        streak_per_chore,
    )


def get_today_chore_completion_progress(
    kid_info: Mapping[str, Any],
    tracked_chores: list[str],
    *,
    kid_id: str | None = None,
    all_chores: Mapping[str, Any] | None = None,
    count_required: int | None = None,
    percent_required: float = 1.0,
    require_no_overdue: bool = False,
    only_due_today: bool = False,
) -> tuple[bool, int, int]:
    """
    Check if a required number or percentage of tracked chores have been completed (approved) today for the given kid.
    If tracked_chores is empty, use all chores for the kid.

    Uses timestamp-based tracking (last_approved field) instead of the deprecated approved_chores list (removed v0.4.0).
    A chore is considered approved today if its last_approved_time matches today's date.

    Args:
        kid_info: The kid's info dictionary.
        tracked_chores: List of chore IDs to check. If empty, all kid's chores are used.
        kid_id: The kid's internal ID (required if only_due_today is True).
        all_chores: Dict of all chores (required if only_due_today is True).
        count_required: Minimum number of chores that must be completed today (overrides percent_required if set).
        percent_required: Float between 0 and 1.0 (e.g., 0.8 for 80%). Default is 1.0 (all required).
        require_no_overdue: If True, only return True if none of the tracked chores went overdue today.
        only_due_today: If True, only consider chores with a due date of today.

    Returns:
        (criteria_met: bool, approved_count: int, total_count: int)

    Example:
        criteria_met, approved_count, total_count = self._get_today_chore_completion_progress(
            kid_info, tracked_chores, kid_id=kid_id, all_chores=coordinator.chores_data,
            count_required=3, percent_required=0.8, require_no_overdue=True, only_due_today=True
        )
    """
    today_local = dt_now_local()
    today_iso = today_local.date().isoformat()
    chores_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

    # Use all kid's chores if tracked_chores is empty
    if not tracked_chores:
        tracked_chores = list(chores_data.keys())

    # Filter chores if only_due_today is set
    if only_due_today:
        if not kid_id or not all_chores:
            # Cannot filter by due date without kid_id and all_chores
            chores_to_check = tracked_chores
        else:
            chores_due_today = []
            for chore_id in tracked_chores:
                # Get chore info from all chores to access per_kid_due_dates
                chore_info = all_chores.get(chore_id, {})
                # For independent chores, read from per_kid_due_dates
                per_kid_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
                due_date_iso = per_kid_dates.get(kid_id)
                if (
                    due_date_iso
                    and due_date_iso[: const.ISO_DATE_STRING_LENGTH] == today_iso
                ):
                    chores_due_today.append(chore_id)
            chores_to_check = chores_due_today
    else:
        chores_to_check = tracked_chores

    total_count = len(chores_to_check)
    if total_count == 0:
        return False, 0, 0

    # Count approved chores using timestamp-based check (last_approved_time matches today)
    approved_count = 0
    for chore_id in chores_to_check:
        chore_data = chores_data.get(chore_id, {})
        last_approved = chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if last_approved and last_approved[: const.ISO_DATE_STRING_LENGTH] == today_iso:
            approved_count += 1

    # Check count_required first (overrides percent_required if set)
    if count_required is not None:
        if approved_count < count_required:
            return False, approved_count, total_count
    else:
        percent_complete = approved_count / total_count
        if percent_complete < percent_required:
            return False, approved_count, total_count

    # Check for overdue if required
    if require_no_overdue:
        for chore_id in chores_to_check:
            chore_data = chores_data.get(chore_id, {})
            # Check if chore state is overdue (single source of truth)
            chore_state = chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
            if chore_state == const.CHORE_STATE_OVERDUE:
                return False, approved_count, total_count
            # Also check if it was marked overdue today (for daily achievements)
            last_overdue_iso = chore_data.get(const.DATA_KID_CHORE_DATA_LAST_OVERDUE)
            if (
                last_overdue_iso
                and last_overdue_iso[: const.ISO_DATE_STRING_LENGTH] == today_iso
            ):
                return False, approved_count, total_count

    return True, approved_count, total_count


def _read_json_file(file_path: str) -> dict:
    """Read and parse a JSON file. Synchronous helper for executor."""
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


async def get_available_dashboard_languages(
    hass: HomeAssistant,
) -> list[str]:
    """Get list of available dashboard language codes.

    Scans the translations directory for dashboard translation files and filters
    against Home Assistant's master LANGUAGES set. Only language codes that have
    actual translation files are returned.

    Returns:
        List of language codes (e.g., ["en", "es", "de"]).
        If directory not found or empty, returns ["en"] as fallback.
    """
    from homeassistant.generated.languages import LANGUAGES

    translations_path = os.path.join(
        os.path.dirname(__file__), const.DASHBOARD_TRANSLATIONS_DIR
    )

    if not await hass.async_add_executor_job(os.path.exists, translations_path):
        const.LOGGER.debug(
            "Dashboard translations directory not found: %s, using English only",
            translations_path,
        )
        return ["en"]

    try:
        filenames = await hass.async_add_executor_job(os.listdir, translations_path)
        available_languages = []

        for filename in filenames:
            # Only process files matching *_dashboard.json pattern
            if not filename.endswith(f"{const.DASHBOARD_TRANSLATIONS_SUFFIX}.json"):
                continue

            # Extract language code from filename (e.g., es_dashboard.json -> es)
            lang_code = filename[
                : -len(".json") - len(const.DASHBOARD_TRANSLATIONS_SUFFIX)
            ]

            # Only include if valid in Home Assistant's LANGUAGES set
            if lang_code in LANGUAGES:
                available_languages.append(lang_code)
            else:
                const.LOGGER.debug(
                    "Ignoring unknown language code: %s (not in LANGUAGES set)",
                    lang_code,
                )

        # Ensure English is always available
        if "en" not in available_languages:
            available_languages.insert(0, "en")
        else:
            # Ensure English is first in the list
            available_languages.remove("en")
            available_languages.insert(0, "en")

        # Sort remaining languages (English stays first)
        if len(available_languages) > 1:
            available_languages = ["en", *sorted(available_languages[1:])]

        const.LOGGER.debug("Available dashboard languages: %s", available_languages)
        return available_languages

    except OSError as err:
        const.LOGGER.error("Error reading dashboard translations directory: %s", err)
        return ["en"]


async def load_dashboard_translation(
    hass: HomeAssistant,
    language: str = "en",
) -> dict[str, str]:
    """Load a specific dashboard translation file with English fallback.

    Args:
        hass: Home Assistant instance
        language: Language code to load (e.g., 'en', 'es', 'de')

    Returns:
        A dict with translation keys and values.
        If the requested language is not found, returns English translations.
    """
    translations_path = os.path.join(
        os.path.dirname(__file__), const.DASHBOARD_TRANSLATIONS_DIR
    )

    if not await hass.async_add_executor_job(os.path.exists, translations_path):
        const.LOGGER.error(
            "Dashboard translations directory not found: %s", translations_path
        )
        return {}

    # Try to load the requested language (with _dashboard suffix)
    lang_path = os.path.join(
        translations_path, f"{language}{const.DASHBOARD_TRANSLATIONS_SUFFIX}.json"
    )
    if await hass.async_add_executor_job(os.path.exists, lang_path):
        try:
            data = await hass.async_add_executor_job(_read_json_file, lang_path)
            const.LOGGER.debug("Loaded %s dashboard translations", language)
            return data
        except (OSError, json.JSONDecodeError) as err:
            const.LOGGER.error("Error loading %s translations: %s", language, err)

    # Fall back to English if requested language not found or errored
    if language != "en":
        const.LOGGER.warning(
            "Language '%s' not found, falling back to English", language
        )
        en_path = os.path.join(
            translations_path, f"en{const.DASHBOARD_TRANSLATIONS_SUFFIX}.json"
        )
        if await hass.async_add_executor_job(os.path.exists, en_path):
            try:
                data = await hass.async_add_executor_job(_read_json_file, en_path)
                const.LOGGER.debug("Loaded English dashboard translations as fallback")
                return data
            except (OSError, json.JSONDecodeError) as err:
                const.LOGGER.error("Error loading English translations: %s", err)

    return {}


async def load_notification_translation(
    hass: HomeAssistant,
    language: str = "en",
) -> dict[str, dict[str, str]]:
    """Load notification translations for a specific language with English fallback.

    Uses module-level caching to avoid repeated file I/O when sending
    notifications to multiple parents with the same language preference (v0.5.0+).

    Args:
        hass: Home Assistant instance
        language: Language code to load (e.g., 'en', 'es', 'de')

    Returns:
        A dict with notification keys mapping to {title, message} dicts.
        If the requested language is not found, returns English translations.
    """
    # Normalize language: default to English if empty/None
    if not language:
        language = "en"

    # Check cache first (v0.5.0+ performance improvement)
    cache_key = f"{language}_notification"
    if cache_key in _translation_cache:
        const.LOGGER.debug(
            "Notification translations for '%s' loaded from cache", language
        )
        return _translation_cache[cache_key]

    translations_path = os.path.join(
        os.path.dirname(__file__), const.CUSTOM_TRANSLATIONS_DIR
    )

    if not await hass.async_add_executor_job(os.path.exists, translations_path):
        const.LOGGER.error(
            "Custom translations directory not found: %s", translations_path
        )
        return {}

    # Try to load the requested language (with _notifications suffix)
    lang_path = os.path.join(
        translations_path, f"{language}{const.NOTIFICATION_TRANSLATIONS_SUFFIX}.json"
    )
    if await hass.async_add_executor_job(os.path.exists, lang_path):
        try:
            data = await hass.async_add_executor_job(_read_json_file, lang_path)
            const.LOGGER.debug("Loaded %s notification translations", language)
            # Cache the loaded translations
            _translation_cache[cache_key] = data
            return data
        except (OSError, json.JSONDecodeError) as err:
            const.LOGGER.error(
                "Error loading %s notification translations: %s", language, err
            )

    # Fall back to English if requested language not found or errored
    if language != "en":
        const.LOGGER.warning(
            "Notification language '%s' not found, falling back to English", language
        )
        # Check if English is already cached
        en_cache_key = "en_notification"
        if en_cache_key in _translation_cache:
            const.LOGGER.debug("English notification translations loaded from cache")
            return _translation_cache[en_cache_key]

        en_path = os.path.join(
            translations_path, f"en{const.NOTIFICATION_TRANSLATIONS_SUFFIX}.json"
        )
        if await hass.async_add_executor_job(os.path.exists, en_path):
            try:
                data = await hass.async_add_executor_job(_read_json_file, en_path)
                const.LOGGER.debug(
                    "Loaded English notification translations as fallback"
                )
                # Cache English translations
                _translation_cache[en_cache_key] = data
                return data
            except (OSError, json.JSONDecodeError) as err:
                const.LOGGER.error(
                    "Error loading English notification translations: %s", err
                )
    else:
        # If we get here, English was requested but file not found
        const.LOGGER.error(
            "English notification translations not found at: %s",
            os.path.join(
                translations_path,
                f"en{const.NOTIFICATION_TRANSLATIONS_SUFFIX}.json",
            ),
        )

    return {}


def clear_translation_cache() -> None:
    """Clear the translation cache.

    Useful for testing or when translation files are updated.
    Call this when reloading the integration or during test teardown.
    """
    _translation_cache.clear()
    const.LOGGER.debug("Translation cache cleared")


# Module-level translation cache for performance (v0.5.0+)
# Key format: f"{language}_{translation_type}" where translation_type is "dashboard" or "notification"
# This avoids repeated file I/O when sending notifications to multiple parents with same language
_translation_cache: dict[str, dict[str, Any]] = {}
