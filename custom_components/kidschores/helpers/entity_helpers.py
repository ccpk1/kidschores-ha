# File: helpers/entity_helpers.py
"""Entity registry helper functions for KidsChores.

Functions that interact with Home Assistant's entity registry for querying,
parsing unique IDs, and removing entities.

All functions here require a `hass` object or interact with HA registries.
"""

from __future__ import annotations

from collections.abc import Callable
import re
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity_registry import (
    RegistryEntry,
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.label_registry import async_get as async_get_label_registry

from .. import const

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ==============================================================================
# Entity Registry Queries
# ==============================================================================


def get_integration_entities(
    hass: HomeAssistant,
    entry_id: str,
    platform: str | None = None,
) -> list[RegistryEntry]:
    """Get all integration entities, optionally filtered by platform.

    Centralizes entity registry queries used across multiple coordinator
    methods. Read-only utility - does not modify entities.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID to filter entities.
        platform: Optional platform filter (e.g., "button", "sensor").
            If None, returns all platforms.

    Returns:
        List of RegistryEntry objects matching criteria.

    Example:
        # Get all sensor entities for this integration
        sensors = get_integration_entities(hass, entry.entry_id, "sensor")

        # Get all entities regardless of platform
        all_entities = get_integration_entities(hass, entry.entry_id)
    """
    entity_registry = async_get_entity_registry(hass)
    entities = [
        entry
        for entry in entity_registry.entities.values()
        if entry.config_entry_id == entry_id
    ]

    if platform:
        entities = [e for e in entities if e.domain == platform]

    return entities


def parse_entity_reference(
    unique_id: str,
    prefix: str,
) -> tuple[str, ...] | None:
    """Parse entity unique_id into component parts after removing prefix.

    Used to extract kid IDs, chore IDs, etc. from entity unique IDs.
    Read-only utility - does not modify entities.

    Args:
        unique_id: Entity unique_id (e.g., "entry_123_kid_456_chore_789").
        prefix: Config entry prefix to strip (e.g., "entry_123_").

    Returns:
        Tuple of ID components after prefix, or None if invalid format.

    Example:
        >>> parse_entity_reference("entry_123_kid_456_chore_789", "entry_123_")
        ('kid_456', 'chore_789')

        >>> parse_entity_reference("invalid", "entry_123_")
        None

    Note:
        Uses underscore delimiters. Returns None for malformed IDs.
    """
    if not unique_id.startswith(prefix):
        return None

    # Strip prefix and split by underscore
    remainder = unique_id[len(prefix) :]
    if not remainder:
        return None

    # Split into component parts
    parts = remainder.split("_")
    if not parts or any(not part for part in parts):
        return None

    return tuple(parts)


def build_orphan_detection_regex(
    valid_ids: list[str],
    separator: str = "_",
) -> re.Pattern[str]:
    """Build compiled regex for O(n) orphan detection.

    Creates a regex pattern that matches ANY of the provided valid IDs,
    enabling efficient detection of orphaned references in unique_ids.

    Args:
        valid_ids: List of valid internal IDs to match against.
        separator: Delimiter used in unique_ids (default: "_").

    Returns:
        Compiled regex pattern for matching valid IDs.

    Example:
        >>> pattern = build_orphan_detection_regex(['uuid1', 'uuid2'])
        >>> bool(pattern.search('entry_uuid1_sensor'))
        True
        >>> bool(pattern.search('entry_uuid3_sensor'))
        False
    """
    if not valid_ids:
        # Return pattern that never matches
        return re.compile(r"(?!)")

    # Escape IDs for regex safety
    escaped_ids = [re.escape(id_str) for id_str in valid_ids]

    # Build pattern: separator + ID + (separator or end)
    pattern = (
        f"{re.escape(separator)}({'|'.join(escaped_ids)})(?:{re.escape(separator)}|$)"
    )

    return re.compile(pattern)


def remove_entities_by_item_id(
    hass: HomeAssistant,
    entry_id: str,
    item_id: str,
) -> int:
    """Remove all entities whose unique_id references the given item_id.

    Called when deleting kids, chores, rewards, penalties, bonuses, badges.
    Uses delimiter matching to prevent false positives (e.g., kid_1 should
    not match kid_10).

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID prefix for unique_id matching.
        item_id: The UUID of the deleted item.

    Returns:
        Count of removed entities.
    """
    perf_start = time.perf_counter()
    ent_reg = async_get_entity_registry(hass)
    prefix = f"{entry_id}_"
    item_id_str = str(item_id)
    removed_count = 0

    for entity_entry in list(ent_reg.entities.values()):
        if entity_entry.config_entry_id != entry_id:
            continue

        unique_id = str(entity_entry.unique_id)

        # Safety: verify our entry prefix
        if not unique_id.startswith(prefix):
            continue

        # Match item_id with proper delimiters (midfix or suffix)
        # Patterns: ..._{item_id}_... or ..._{item_id}
        if f"_{item_id_str}_" in unique_id or unique_id.endswith(f"_{item_id_str}"):
            ent_reg.async_remove(entity_entry.entity_id)
            removed_count += 1
            const.LOGGER.debug(
                "Removed entity %s (uid: %s) for deleted item %s",
                entity_entry.entity_id,
                unique_id,
                item_id_str,
            )

    perf_elapsed = time.perf_counter() - perf_start
    if removed_count > 0:
        const.LOGGER.info(
            "Removed %d entities for deleted item in %.3fs",
            removed_count,
            perf_elapsed,
        )

    return removed_count


# ==============================================================================
# Entity ID Lookups
# ==============================================================================


def get_first_kidschores_entry(hass: HomeAssistant) -> str | None:
    """Get the entry_id of the first loaded KidsChores config entry.

    Args:
        hass: HomeAssistant instance

    Returns:
        Config entry ID string, or None if no loaded entries
    """
    entries = hass.config_entries.async_entries(const.DOMAIN)
    for entry in entries:
        if entry.state.name == "LOADED":
            return entry.entry_id
    return None


def get_entity_id_from_unique_id(hass: HomeAssistant, unique_id: str) -> str | None:
    """Get entity_id from a unique_id.

    Args:
        hass: HomeAssistant instance
        unique_id: The unique_id to look up

    Returns:
        entity_id string, or None if not found
    """
    entity_registry = async_get_entity_registry(hass)
    for entry in entity_registry.entities.values():
        if entry.unique_id == unique_id:
            return entry.entity_id
    return None


def get_friendly_label(hass: HomeAssistant, label_name: str) -> str:
    """Get a friendly display name for a label.

    Args:
        hass: HomeAssistant instance
        label_name: The label ID/name to look up

    Returns:
        Label's display name, or the label_name if not found
    """
    label_registry = async_get_label_registry(hass)
    label_entry = label_registry.async_get_label(label_name)
    if label_entry:
        return label_entry.name
    return label_name


# ==============================================================================
# Orphan Entity Removal
# ==============================================================================


async def remove_entities_by_validator(
    hass: HomeAssistant,
    entry_id: str,
    *,
    platforms: list[str] | None = None,
    suffix: str | None = None,
    midfix: str | None = None,
    is_valid: Callable[[str], bool],
    entity_type: str = "entity",
) -> int:
    """Remove entities that fail a validation check.

    Core helper for removing orphaned entities whose underlying data relationship
    no longer exists. Uses efficient platform filtering and consistent logging.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID for filtering entities.
        platforms: Platforms to scan (None = all platforms for this entry).
        suffix: Only check entities with this UID suffix.
        midfix: Only check entities containing this string.
        is_valid: Callback(unique_id) → True if entity should be kept.
        entity_type: Display name for logging.

    Returns:
        Count of removed entities.

    Example:
        # Remove entities referencing deleted kids
        removed = await remove_entities_by_validator(
            hass, entry_id,
            platforms=["sensor"],
            is_valid=lambda uid: extract_kid_id(uid) in valid_kid_ids,
            entity_type="kid sensor",
        )
    """
    perf_start = time.perf_counter()
    prefix = f"{entry_id}_"
    removed_count = 0
    scanned_count = 0

    ent_reg = async_get_entity_registry(hass)

    # Get entities to scan (platform-filtered or all for this entry)
    if platforms:
        entities_to_scan = []
        for platform in platforms:
            entities_to_scan.extend(get_integration_entities(hass, entry_id, platform))
    else:
        entities_to_scan = [
            e for e in ent_reg.entities.values() if e.config_entry_id == entry_id
        ]

    for entity_entry in list(entities_to_scan):
        unique_id = str(entity_entry.unique_id)

        # Apply prefix filter
        if not unique_id.startswith(prefix):
            continue

        # Apply suffix filter if specified
        if suffix and not unique_id.endswith(suffix):
            continue

        # Apply midfix filter if specified
        if midfix and midfix not in unique_id:
            continue

        scanned_count += 1

        # Check validity - remove if not valid
        if not is_valid(unique_id):
            const.LOGGER.debug(
                "Removing orphaned %s: %s (uid: %s)",
                entity_type,
                entity_entry.entity_id,
                unique_id,
            )
            ent_reg.async_remove(entity_entry.entity_id)
            removed_count += 1

    perf_elapsed = time.perf_counter() - perf_start
    if removed_count > 0:
        const.LOGGER.info(
            "Removed %d orphaned %s(s) in %.3fs",
            removed_count,
            entity_type,
            perf_elapsed,
        )
    else:
        const.LOGGER.debug(
            "PERF: orphan scan for %s: %d checked in %.3fs, none removed",
            entity_type,
            scanned_count,
            perf_elapsed,
        )

    return removed_count


async def remove_orphaned_shared_chore_sensors(
    hass: HomeAssistant,
    entry_id: str,
    chores_data: dict[str, Any],
) -> int:
    """Remove shared chore sensors for chores no longer marked as shared.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        chores_data: Dict of chore_id → chore_info.

    Returns:
        Count of removed entities.
    """
    prefix = f"{entry_id}_"
    suffix = const.DATA_GLOBAL_STATE_SUFFIX

    def is_valid(unique_id: str) -> bool:
        chore_id = unique_id[len(prefix) : -len(suffix)]
        chore_info = chores_data.get(chore_id)
        return bool(
            chore_info
            and chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            == const.COMPLETION_CRITERIA_SHARED
        )

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.SENSOR],
        suffix=suffix,
        is_valid=is_valid,
        entity_type="shared chore sensor",
    )


async def remove_orphaned_kid_chore_entities(
    hass: HomeAssistant,
    entry_id: str,
    kids_data: dict[str, Any],
    chores_data: dict[str, Any],
) -> int:
    """Remove kid-chore entities for kids no longer assigned to chores.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        kids_data: Dict of kid_id → kid_info.
        chores_data: Dict of chore_id → chore_info.

    Returns:
        Count of removed entities.
    """
    if not kids_data or not chores_data:
        return 0

    prefix = f"{entry_id}_"

    # Build valid kid-chore combinations
    valid_combinations: set[tuple[str, str]] = set()
    for chore_id, chore_info in chores_data.items():
        for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            valid_combinations.add((kid_id, chore_id))

    # Build regex for efficient extraction
    kid_ids = "|".join(re.escape(kid_id) for kid_id in kids_data)
    chore_ids = "|".join(re.escape(chore_id) for chore_id in chores_data)
    pattern = re.compile(rf"^({kid_ids})_({chore_ids})")

    def is_valid(unique_id: str) -> bool:
        core = unique_id[len(prefix) :]
        match = pattern.match(core)
        if not match:
            return True  # Not a kid-chore entity, keep it
        return (match.group(1), match.group(2)) in valid_combinations

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.SENSOR, const.Platform.BUTTON],
        is_valid=is_valid,
        entity_type="kid-chore entity",
    )


async def remove_orphaned_progress_entities(
    hass: HomeAssistant,
    entry_id: str,
    domain_data: dict[str, Any],
    *,
    entity_type: str,
    progress_suffix: str,
    assigned_kids_key: str,
) -> int:
    """Remove progress entities for kids no longer assigned (generic).

    Used for badges, achievements, and challenges.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        domain_data: Dict of parent_entity_id → entity_info (e.g., badges_data).
        entity_type: Display name for logging (e.g., "badge", "achievement").
        progress_suffix: Suffix for progress sensors.
        assigned_kids_key: Key in entity_info for assigned kids list.

    Returns:
        Count of removed entities.
    """
    prefix = f"{entry_id}_"

    def is_valid(unique_id: str) -> bool:
        core_id = unique_id[len(prefix) : -len(progress_suffix)]
        parts = core_id.split("_", 1)
        if len(parts) != 2:
            return True  # Can't parse, keep it

        kid_id, parent_entity_id = parts
        parent_info = domain_data.get(parent_entity_id)
        return bool(parent_info and kid_id in parent_info.get(assigned_kids_key, []))

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.SENSOR],
        suffix=progress_suffix,
        is_valid=is_valid,
        entity_type=f"{entity_type} progress sensor",
    )


async def remove_orphaned_manual_adjustment_buttons(
    hass: HomeAssistant,
    entry_id: str,
    current_deltas: set[float],
) -> int:
    """Remove manual adjustment buttons with obsolete delta values.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        current_deltas: Set of currently valid delta values.

    Returns:
        Count of removed entities.
    """
    button_suffix = const.BUTTON_KC_UID_SUFFIX_PARENT_POINTS_ADJUST

    def is_valid(unique_id: str) -> bool:
        # New format: {entry_id}_{kid_id}_{slugified_delta}_parent_points_adjust_button
        if button_suffix not in unique_id:
            return False
        try:
            # Extract the part before the suffix
            prefix_part = unique_id.split(button_suffix)[0]
            # Get last segment which is the slugified delta
            delta_slug = prefix_part.split("_")[-1]
            # Convert slugified delta back to float (replace 'neg' prefix and 'p' decimal)
            delta_str = delta_slug.replace("neg", "-").replace("p", ".")
            delta = float(delta_str)
            return delta in current_deltas
        except (ValueError, IndexError):
            const.LOGGER.warning(
                "Could not parse delta from adjustment button uid: %s", unique_id
            )
            return True  # Can't parse, keep it

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.BUTTON],
        midfix=button_suffix,
        is_valid=is_valid,
        entity_type="manual adjustment button",
    )
