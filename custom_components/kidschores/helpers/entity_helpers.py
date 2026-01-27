# File: helpers/entity_helpers.py
"""Entity registry helper functions for KidsChores.

Functions that interact with Home Assistant's entity registry for querying,
parsing unique IDs, and removing entities.

All functions here require a `hass` object or interact with HA registries.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

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
