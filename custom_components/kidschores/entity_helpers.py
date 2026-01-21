"""Entity lifecycle management helpers.

This module is the SINGLE SOURCE OF TRUTH for:
- Entity field defaults
- Business logic validation
- Complete entity structure building

Consumers:
- options_flow.py (UI entity management)
- services.py (programmatic entity management)
- coordinator.py (thin storage wrapper)

See Also:
- flow_helpers.py: UI-specific validation (uniqueness, HA user checks)
- type_defs.py: TypedDict definitions for type safety
"""

from __future__ import annotations

from typing import Any, cast
import uuid

from . import const
from .type_defs import BadgeData, ChoreData, KidData, ParentData, RewardData

# ==============================================================================
# HELPER FUNCTIONS FOR FIELD NORMALIZATION
# ==============================================================================


def _normalize_list_field(value: Any) -> list[Any]:
    """Normalize a field that should be a list.

    Handles cases where the value might be:
    - Already a list → return as-is
    - None → return empty list
    - Other types → return as list

    This prevents bugs like list("08:00") → ['0', '8', ':', '0', '0']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    # For strings, don't iterate character by character
    # This shouldn't happen for list fields, but be safe
    if isinstance(value, str):
        return [value] if value else []
    return list(value) if value else []


def _normalize_dict_field(value: Any) -> dict[str, Any]:
    """Normalize a field that should be a dict.

    Handles cases where the value might be:
    - Already a dict → return as-is
    - None → return empty dict
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _pass_through_field(value: Any, default: Any = None) -> Any:
    """Pass field value through as-is, returning default if None.

    For fields that can be various types (string, list, etc.) and should
    not be normalized.
    """
    return value if value is not None else default


# ==============================================================================
# EXCEPTIONS
# ==============================================================================


class EntityValidationError(Exception):
    """Validation error with field-specific information for form highlighting.

    This exception is raised when business logic validation fails in entity
    creation or update. The field attribute allows options_flow to map the
    error back to the specific form field that caused the failure.

    Attributes:
        field: The CFOF_* constant identifying the form field that failed
        translation_key: The TRANS_KEY_* constant for the error message
        placeholders: Optional dict for translation string placeholders

    Example:
        raise EntityValidationError(
            field=const.CFOF_REWARDS_INPUT_COST,
            translation_key=const.TRANS_KEY_INVALID_REWARD_COST,
            placeholders={"value": str(cost)},
        )
    """

    def __init__(
        self,
        field: str,
        translation_key: str,
        placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize EntityValidationError.

        Args:
            field: The CFOF_* constant for the field that failed validation
            translation_key: The TRANS_KEY_* constant for error message
            placeholders: Optional dict for translation placeholders
        """
        self.field = field
        self.translation_key = translation_key
        self.placeholders = placeholders or {}
        super().__init__(translation_key)


# ==============================================================================
# REWARDS
# ==============================================================================


# Mapping from CFOF_* form keys to DATA_* storage keys for rewards
# Used by config_flow/options_flow to convert UI input before calling build_reward()
_CFOF_TO_REWARD_DATA_MAPPING: dict[str, str] = {
    const.CFOF_REWARDS_INPUT_NAME: const.DATA_REWARD_NAME,
    const.CFOF_REWARDS_INPUT_COST: const.DATA_REWARD_COST,
    const.CFOF_REWARDS_INPUT_DESCRIPTION: const.DATA_REWARD_DESCRIPTION,
    const.CFOF_REWARDS_INPUT_ICON: const.DATA_REWARD_ICON,
    const.CFOF_REWARDS_INPUT_LABELS: const.DATA_REWARD_LABELS,
}


def map_cfof_to_reward_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert CFOF_* form keys to DATA_* storage keys for rewards.

    Used by config_flow and options_flow to normalize UI input before
    calling build_reward().

    Args:
        user_input: Dict with CFOF_REWARDS_INPUT_* keys from UI forms

    Returns:
        Dict with DATA_REWARD_* keys for build_reward() consumption
    """
    return {
        _CFOF_TO_REWARD_DATA_MAPPING.get(key, key): value
        for key, value in user_input.items()
        if key in _CFOF_TO_REWARD_DATA_MAPPING
    }


def build_reward(
    user_input: dict[str, Any],
    existing: RewardData | None = None,
) -> RewardData:
    """Build reward data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for reward field handling.
    One function handles both create (existing=None) and update (existing=RewardData).

    Args:
        user_input: Data with DATA_* keys (may have missing fields)
        existing: None for create, existing RewardData for update

    Returns:
        Complete RewardData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies const.DEFAULT_* for missing fields
        reward = build_reward({DATA_REWARD_NAME: "New Reward"})

        # UPDATE mode - preserves existing fields not in user_input
        reward = build_reward({DATA_REWARD_COST: 50}, existing=old_reward)
    """
    is_create = existing is None

    def get_field(
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default.

        Priority:
        1. If data_key in user_input → use user_input value
        2. If existing is not None → use existing value (update mode)
        3. Fall back to default (create mode)
        """
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(const.DATA_REWARD_NAME, "")
    name = str(raw_name).strip() if raw_name else ""

    # In create mode, name is required
    # In update mode, name is only validated if provided
    if is_create and not name:
        raise EntityValidationError(
            field=const.DATA_REWARD_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_REWARD_NAME,
        )
    # If name was explicitly provided but is empty/whitespace, reject it
    if const.DATA_REWARD_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.DATA_REWARD_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_REWARD_NAME,
        )

    # --- Build complete reward structure ---
    # For internal_id: generate new UUID for create, preserve existing for update
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_REWARD_INTERNAL_ID, str(uuid.uuid4()))

    return RewardData(
        internal_id=internal_id,
        name=name,
        cost=float(get_field(const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST)),
        description=str(get_field(const.DATA_REWARD_DESCRIPTION, const.SENTINEL_EMPTY)),
        icon=str(get_field(const.DATA_REWARD_ICON, const.DEFAULT_REWARD_ICON)),
        reward_labels=list(get_field(const.DATA_REWARD_LABELS, [])),
    )


# ==============================================================================
# BONUSES & PENALTIES (Unified)
# ==============================================================================


def build_bonus_or_penalty(
    user_input: dict[str, Any],
    entity_type: str,  # "bonus" or "penalty"
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build bonus or penalty data for create or update operations.

    Bonuses and penalties are 95% identical - only differing in:
    - Points sign: positive for bonus, negative for penalty
    - Storage location: DATA_BONUSES vs DATA_PENALTIES
    - Default icon constant

    This unified function handles both entity types to eliminate code duplication.

    Args:
        user_input: Data with DATA_* keys (may have missing fields)
        entity_type: "bonus" or "penalty"
        existing: None for create, existing entity data for update

    Returns:
        Complete dict ready for storage with DATA_* keys

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)
        ValueError: If entity_type is not "bonus" or "penalty"

    Examples:
        # CREATE bonus - generates UUID, applies defaults
        bonus = build_bonus_or_penalty({DATA_BONUS_NAME: "Extra Credit"}, "bonus")

        # UPDATE penalty - preserves existing fields not in user_input
        penalty = build_bonus_or_penalty({DATA_PENALTY_POINTS: 10}, "penalty", existing=old)
    """
    if entity_type not in ("bonus", "penalty"):
        raise ValueError(
            f"entity_type must be 'bonus' or 'penalty', got: {entity_type}"
        )

    is_bonus = entity_type == "bonus"
    is_create = existing is None

    # --- Field key mapping (different constants for bonus vs penalty) ---
    name_key = const.DATA_BONUS_NAME if is_bonus else const.DATA_PENALTY_NAME
    desc_key = (
        const.DATA_BONUS_DESCRIPTION if is_bonus else const.DATA_PENALTY_DESCRIPTION
    )
    labels_key = const.DATA_BONUS_LABELS if is_bonus else const.DATA_PENALTY_LABELS
    points_key = const.DATA_BONUS_POINTS if is_bonus else const.DATA_PENALTY_POINTS
    icon_key = const.DATA_BONUS_ICON if is_bonus else const.DATA_PENALTY_ICON
    internal_id_key = (
        const.DATA_BONUS_INTERNAL_ID if is_bonus else const.DATA_PENALTY_INTERNAL_ID
    )

    # --- Default values (different for bonus vs penalty) ---
    default_points = (
        const.DEFAULT_BONUS_POINTS if is_bonus else const.DEFAULT_PENALTY_POINTS
    )
    default_icon = const.DEFAULT_BONUS_ICON if is_bonus else const.DEFAULT_PENALTY_ICON
    invalid_name_key = (
        const.TRANS_KEY_CFOF_INVALID_BONUS_NAME
        if is_bonus
        else const.TRANS_KEY_CFOF_INVALID_PENALTY_NAME
    )

    def get_field(data_key: str, default: Any) -> Any:
        """Get field value: user_input > existing > default."""
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(name_key, "")
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=name_key,
            translation_key=invalid_name_key,
        )
    if name_key in user_input and not name:
        raise EntityValidationError(
            field=name_key,
            translation_key=invalid_name_key,
        )

    # --- Points: positive for bonus, negative for penalty ---
    raw_points = get_field(points_key, default_points)
    # Ensure correct sign: bonus = positive, penalty = negative
    stored_points = abs(float(raw_points)) if is_bonus else -abs(float(raw_points))

    # --- Internal ID: generate new for create, preserve for update ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(internal_id_key, str(uuid.uuid4()))

    return {
        name_key: name,
        desc_key: str(get_field(desc_key, const.SENTINEL_EMPTY)),
        labels_key: list(get_field(labels_key, [])),
        points_key: stored_points,
        icon_key: str(get_field(icon_key, default_icon)),
        internal_id_key: internal_id,
    }


# ==============================================================================
# KIDS
# ==============================================================================


def build_kid(
    user_input: dict[str, Any],
    existing: KidData | None = None,
    *,
    is_shadow: bool = False,
    linked_parent_id: str | None = None,
) -> KidData:
    """Build kid data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for kid field handling.
    One function handles both create (existing=None) and update (existing=KidData).

    Args:
        user_input: Form/service data with CFOF_* keys (may have missing fields)
        existing: None for create, existing KidData for update
        is_shadow: If True, mark as shadow kid (for parent chore assignment)
        linked_parent_id: Parent ID to link (required when is_shadow=True)

    Returns:
        Complete KidData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies defaults for missing fields
        kid = build_kid({CFOF_KIDS_INPUT_KID_NAME: "Alice"})

        # UPDATE mode - preserves existing fields not in user_input
        kid = build_kid({CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE: "es"}, existing=old_kid)

        # SHADOW KID mode - creates shadow kid linked to parent
        kid = build_kid(parent_derived_input, is_shadow=True, linked_parent_id="uuid")
    """
    is_create = existing is None

    def get_field(
        cfof_key: str,
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default."""
        if cfof_key in user_input:
            return user_input[cfof_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(
        const.CFOF_KIDS_INPUT_KID_NAME,
        const.DATA_KID_NAME,
        "",
    )
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_KIDS_INPUT_KID_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_KID_NAME,
        )
    if const.CFOF_KIDS_INPUT_KID_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_KIDS_INPUT_KID_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_KID_NAME,
        )

    # --- Internal ID: generate for create, preserve for update ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_KID_INTERNAL_ID, str(uuid.uuid4()))

    # --- Handle HA user and notification service sentinels ---
    ha_user_id = get_field(
        const.CFOF_KIDS_INPUT_HA_USER,
        const.DATA_KID_HA_USER_ID,
        "",
    )
    if ha_user_id in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
        ha_user_id = ""

    notify_service = get_field(
        const.CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE,
        const.DATA_KID_MOBILE_NOTIFY_SERVICE,
        const.SENTINEL_EMPTY,
    )
    if notify_service in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
        notify_service = ""

    # Derive enable_notifications from service presence
    enable_notifications = bool(notify_service)

    # --- Build complete kid structure ---
    # Include all runtime fields that _create_kid() used to add
    kid_data: KidData = {
        # Core identification
        const.DATA_KID_INTERNAL_ID: internal_id,
        const.DATA_KID_NAME: name,
        # Points (runtime initialized)
        const.DATA_KID_POINTS: float(
            get_field(
                const.CFOF_GLOBAL_INPUT_INTERNAL_ID,  # Not a real form field
                const.DATA_KID_POINTS,
                const.DEFAULT_ZERO,
            )
            if existing
            else const.DEFAULT_ZERO
        ),
        const.DATA_KID_POINTS_MULTIPLIER: float(
            existing.get(
                const.DATA_KID_POINTS_MULTIPLIER, const.DEFAULT_KID_POINTS_MULTIPLIER
            )
            if existing
            else const.DEFAULT_KID_POINTS_MULTIPLIER
        ),
        # Linkage
        const.DATA_KID_HA_USER_ID: ha_user_id,
        # Notifications
        const.DATA_KID_ENABLE_NOTIFICATIONS: enable_notifications,
        const.DATA_KID_MOBILE_NOTIFY_SERVICE: notify_service,
        const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS: (
            existing.get(const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS, False)
            if existing
            else False
        ),
        const.DATA_KID_DASHBOARD_LANGUAGE: str(
            get_field(
                const.CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE,
                const.DATA_KID_DASHBOARD_LANGUAGE,
                const.DEFAULT_DASHBOARD_LANGUAGE,
            )
        ),
        # Badge tracking (runtime initialized)
        const.DATA_KID_BADGES_EARNED: (
            existing.get(const.DATA_KID_BADGES_EARNED, {}) if existing else {}
        ),
        # Reward tracking (runtime initialized)
        const.DATA_KID_REWARD_DATA: (
            existing.get(const.DATA_KID_REWARD_DATA, {}) if existing else {}
        ),
        # Penalty/bonus tracking (runtime initialized)
        const.DATA_KID_PENALTY_APPLIES: (
            existing.get(const.DATA_KID_PENALTY_APPLIES, {}) if existing else {}
        ),
        const.DATA_KID_BONUS_APPLIES: (
            existing.get(const.DATA_KID_BONUS_APPLIES, {}) if existing else {}
        ),
        # Overdue tracking (runtime initialized)
        const.DATA_KID_OVERDUE_CHORES: (
            existing.get(const.DATA_KID_OVERDUE_CHORES, []) if existing else []
        ),
        const.DATA_KID_OVERDUE_NOTIFICATIONS: (
            existing.get(const.DATA_KID_OVERDUE_NOTIFICATIONS, {}) if existing else {}
        ),
    }

    # --- Shadow kid markers (only set if requested) ---
    if is_shadow:
        kid_data[const.DATA_KID_IS_SHADOW] = True
        kid_data[const.DATA_KID_LINKED_PARENT_ID] = linked_parent_id
    elif existing:
        # Preserve existing shadow status on update
        if existing.get(const.DATA_KID_IS_SHADOW):
            kid_data[const.DATA_KID_IS_SHADOW] = True
            kid_data[const.DATA_KID_LINKED_PARENT_ID] = existing.get(
                const.DATA_KID_LINKED_PARENT_ID
            )

    return kid_data


# ==============================================================================
# PARENTS
# ==============================================================================


def build_parent(
    user_input: dict[str, Any],
    existing: ParentData | None = None,
) -> ParentData:
    """Build parent data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for parent field handling.
    One function handles both create (existing=None) and update (existing=ParentData).

    Args:
        user_input: Form/service data with CFOF_* keys (may have missing fields)
        existing: None for create, existing ParentData for update

    Returns:
        Complete ParentData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies defaults for missing fields
        parent = build_parent({CFOF_PARENTS_INPUT_NAME: "Dad"})

        # UPDATE mode - preserves existing fields not in user_input
        parent = build_parent({CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: ["uuid1"]}, existing=old)
    """
    is_create = existing is None

    def get_field(
        cfof_key: str,
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default."""
        if cfof_key in user_input:
            return user_input[cfof_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(
        const.CFOF_PARENTS_INPUT_NAME,
        const.DATA_PARENT_NAME,
        "",
    )
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_PARENTS_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_PARENT_NAME,
        )
    if const.CFOF_PARENTS_INPUT_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_PARENTS_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_PARENT_NAME,
        )

    # --- Internal ID: generate for create, preserve for update ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_PARENT_INTERNAL_ID, str(uuid.uuid4()))

    # --- Handle HA user and notification service sentinels ---
    ha_user_id = get_field(
        const.CFOF_PARENTS_INPUT_HA_USER,
        const.DATA_PARENT_HA_USER_ID,
        "",
    )
    if ha_user_id in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
        ha_user_id = ""

    notify_service = get_field(
        const.CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE,
        const.DATA_PARENT_MOBILE_NOTIFY_SERVICE,
        "",
    )
    if notify_service in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
        notify_service = ""

    # Derive enable_notifications from service presence
    enable_notifications = bool(notify_service)

    # --- Build complete parent structure ---
    return ParentData(
        internal_id=internal_id,
        name=name,
        ha_user_id=ha_user_id,
        associated_kids=list(
            get_field(
                const.CFOF_PARENTS_INPUT_ASSOCIATED_KIDS,
                const.DATA_PARENT_ASSOCIATED_KIDS,
                [],
            )
        ),
        enable_notifications=enable_notifications,
        mobile_notify_service=notify_service,
        use_persistent_notifications=(
            existing.get(const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS, False)
            if existing
            else False
        ),
        dashboard_language=str(
            get_field(
                const.CFOF_PARENTS_INPUT_DASHBOARD_LANGUAGE,
                const.DATA_PARENT_DASHBOARD_LANGUAGE,
                const.DEFAULT_DASHBOARD_LANGUAGE,
            )
        ),
        allow_chore_assignment=bool(
            get_field(
                const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT,
                const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT,
                False,
            )
        ),
        enable_chore_workflow=bool(
            get_field(
                const.CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW,
                const.DATA_PARENT_ENABLE_CHORE_WORKFLOW,
                False,
            )
        ),
        enable_gamification=bool(
            get_field(
                const.CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION,
                const.DATA_PARENT_ENABLE_GAMIFICATION,
                False,
            )
        ),
        linked_shadow_kid_id=(
            existing.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID) if existing else None
        ),
    )


# ==============================================================================
# CHORES
# ==============================================================================


def build_chore(
    user_input: dict[str, Any],
    existing: ChoreData | None = None,
) -> ChoreData:
    """Build chore data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for chore field handling.
    One function handles both create (existing=None) and update (existing=ChoreData).

    NOTE: This function does NOT validate for duplicates or complex business rules.
    Use flow_helpers.build_chores_data() for full validation in UI flows.
    This function handles field defaults and type coercion only.

    Args:
        user_input: Form/service data with DATA_* keys (pre-validated by flow_helpers)
        existing: None for create, existing ChoreData for update

    Returns:
        Complete ChoreData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies const.DEFAULT_* for missing fields
        chore = build_chore({DATA_CHORE_NAME: "Clean Room", DATA_CHORE_ASSIGNED_KIDS: [...]})

        # UPDATE mode - preserves existing fields not in user_input
        chore = build_chore({DATA_CHORE_DEFAULT_POINTS: 15}, existing=old_chore)
    """
    is_create = existing is None

    def get_field(
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default.

        NOTE: Uses DATA_* keys directly (not CFOF_*) since chore data
        is pre-processed by flow_helpers.build_chores_data().
        """
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(const.DATA_CHORE_NAME, "")
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_CHORES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_CHORE_NAME,
        )
    if const.DATA_CHORE_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_CHORES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_CHORE_NAME,
        )

    # --- Internal ID: generate for create, preserve for update ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_CHORE_INTERNAL_ID, str(uuid.uuid4()))

    # --- Handle custom interval fields based on frequency ---
    recurring_frequency = get_field(
        const.DATA_CHORE_RECURRING_FREQUENCY,
        const.FREQUENCY_NONE,
    )
    is_custom_frequency = recurring_frequency in (
        const.FREQUENCY_CUSTOM,
        const.FREQUENCY_CUSTOM_FROM_COMPLETE,
    )

    custom_interval = (
        get_field(const.DATA_CHORE_CUSTOM_INTERVAL, None)
        if is_custom_frequency
        else None
    )
    custom_interval_unit = (
        get_field(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, None)
        if is_custom_frequency
        else None
    )

    # --- Build complete chore structure ---
    # Cast to ChoreData - all required fields are populated
    return cast(
        "ChoreData",
        {
            # Core identification
            const.DATA_CHORE_INTERNAL_ID: internal_id,
            const.DATA_CHORE_NAME: name,
            # State - always starts as PENDING for new chores
            const.DATA_CHORE_STATE: get_field(
                const.DATA_CHORE_STATE,
                const.CHORE_STATE_PENDING,
            ),
            # Points and configuration
            const.DATA_CHORE_DEFAULT_POINTS: float(
                get_field(const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS)
            ),
            const.DATA_CHORE_APPROVAL_RESET_TYPE: get_field(
                const.DATA_CHORE_APPROVAL_RESET_TYPE,
                const.DEFAULT_APPROVAL_RESET_TYPE,
            ),
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE: get_field(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.DEFAULT_OVERDUE_HANDLING_TYPE,
            ),
            const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: get_field(
                const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
                const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            ),
            # Description and display
            const.DATA_CHORE_DESCRIPTION: str(
                get_field(const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY)
            ),
            const.DATA_CHORE_LABELS: list(get_field(const.DATA_CHORE_LABELS, [])),
            const.DATA_CHORE_ICON: str(
                get_field(const.DATA_CHORE_ICON, const.DEFAULT_ICON)
            ),
            # Assignment
            const.DATA_CHORE_ASSIGNED_KIDS: list(
                get_field(const.DATA_CHORE_ASSIGNED_KIDS, [])
            ),
            # Scheduling
            const.DATA_CHORE_RECURRING_FREQUENCY: recurring_frequency,
            const.DATA_CHORE_CUSTOM_INTERVAL: custom_interval,
            const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: custom_interval_unit,
            const.DATA_CHORE_DAILY_MULTI_TIMES: _pass_through_field(
                get_field(const.DATA_CHORE_DAILY_MULTI_TIMES, None), None
            ),
            # Due dates
            const.DATA_CHORE_DUE_DATE: get_field(const.DATA_CHORE_DUE_DATE, None),
            const.DATA_CHORE_PER_KID_DUE_DATES: _normalize_dict_field(
                get_field(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            ),
            const.DATA_CHORE_APPLICABLE_DAYS: _normalize_list_field(
                get_field(const.DATA_CHORE_APPLICABLE_DAYS, [])
            ),
            const.DATA_CHORE_PER_KID_APPLICABLE_DAYS: _normalize_dict_field(
                get_field(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
            ),
            const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES: _normalize_dict_field(
                get_field(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
            ),
            # Runtime tracking (preserve existing values on update)
            const.DATA_CHORE_LAST_COMPLETED: get_field(
                const.DATA_CHORE_LAST_COMPLETED, None
            ),
            const.DATA_CHORE_LAST_CLAIMED: get_field(
                const.DATA_CHORE_LAST_CLAIMED, None
            ),
            const.DATA_CHORE_APPROVAL_PERIOD_START: get_field(
                const.DATA_CHORE_APPROVAL_PERIOD_START, None
            ),
            const.DATA_CHORE_CLAIMED_BY: list(
                get_field(const.DATA_CHORE_CLAIMED_BY, [])
            ),
            const.DATA_CHORE_COMPLETED_BY: list(
                get_field(const.DATA_CHORE_COMPLETED_BY, [])
            ),
            # Notifications
            const.DATA_CHORE_NOTIFY_ON_CLAIM: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
                )
            ),
            const.DATA_CHORE_NOTIFY_ON_APPROVAL: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_APPROVAL,
                    const.DEFAULT_NOTIFY_ON_APPROVAL,
                )
            ),
            const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                    const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
                )
            ),
            const.DATA_CHORE_NOTIFY_ON_REMINDER: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_REMINDER,
                    const.DEFAULT_NOTIFY_ON_REMINDER,
                )
            ),
            # Calendar and features
            const.DATA_CHORE_SHOW_ON_CALENDAR: bool(
                get_field(
                    const.DATA_CHORE_SHOW_ON_CALENDAR,
                    const.DEFAULT_CHORE_SHOW_ON_CALENDAR,
                )
            ),
            const.DATA_CHORE_AUTO_APPROVE: bool(
                get_field(
                    const.DATA_CHORE_AUTO_APPROVE,
                    const.DEFAULT_CHORE_AUTO_APPROVE,
                )
            ),
            # Completion criteria
            const.DATA_CHORE_COMPLETION_CRITERIA: get_field(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            ),
        },
    )


# ==============================================================================
# BADGES
# ==============================================================================


def build_badge(
    user_input: dict[str, Any],
    existing: BadgeData | None = None,
    *,
    badge_type: str = const.BADGE_TYPE_CUMULATIVE,
) -> BadgeData:
    """Build badge data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for badge field handling.
    One function handles both create (existing=None) and update (existing=BadgeData).

    Badge types have different required components:
    - CUMULATIVE: target (points-only), awards
    - DAILY: target, awards, assigned_to
    - PERIODIC: target, awards, assigned_to, reset_schedule, tracked_chores
    - SPECIAL_OCCASION: special_occasion_type
    - ACHIEVEMENT_LINKED: associated_achievement
    - CHALLENGE_LINKED: associated_challenge

    Args:
        user_input: Form/service data with CFOF_* keys (may have missing fields)
        existing: None for create, existing BadgeData for update
        badge_type: Type of badge being created/updated

    Returns:
        Complete BadgeData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies const.DEFAULT_* for missing fields
        badge = build_badge(
            {CFOF_BADGES_INPUT_NAME: "Super Star"},
            badge_type=const.BADGE_TYPE_CUMULATIVE
        )

        # UPDATE mode - preserves existing fields not in user_input
        badge = build_badge(
            {CFOF_BADGES_INPUT_NAME: "Renamed Badge"},
            existing=old_badge,
            badge_type=old_badge["badge_type"]
        )
    """
    is_create = existing is None

    def get_field(
        cfof_key: str,
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default."""
        if cfof_key in user_input:
            return user_input[cfof_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(
        const.CFOF_BADGES_INPUT_NAME,
        const.DATA_BADGE_NAME,
        "",
    )
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_BADGES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_BADGE_NAME,
        )
    if const.CFOF_BADGES_INPUT_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_BADGES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_BADGE_NAME,
        )

    # --- Generate or preserve internal_id ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_BADGE_INTERNAL_ID, str(uuid.uuid4()))

    # --- Determine which components this badge type includes ---
    include_target = badge_type in const.INCLUDE_TARGET_BADGE_TYPES
    include_special_occasion = badge_type in const.INCLUDE_SPECIAL_OCCASION_BADGE_TYPES
    include_achievement_linked = (
        badge_type in const.INCLUDE_ACHIEVEMENT_LINKED_BADGE_TYPES
    )
    include_challenge_linked = badge_type in const.INCLUDE_CHALLENGE_LINKED_BADGE_TYPES
    include_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES
    include_assigned_to = badge_type in const.INCLUDE_ASSIGNED_TO_BADGE_TYPES
    include_awards = badge_type in const.INCLUDE_AWARDS_BADGE_TYPES
    include_reset_schedule = badge_type in const.INCLUDE_RESET_SCHEDULE_BADGE_TYPES

    # --- Build base badge data ---
    badge_data: dict[str, Any] = {
        const.DATA_BADGE_INTERNAL_ID: internal_id,
        const.DATA_BADGE_NAME: name,
        const.DATA_BADGE_TYPE: badge_type,
        const.DATA_BADGE_DESCRIPTION: str(
            get_field(
                const.CFOF_BADGES_INPUT_DESCRIPTION,
                const.DATA_BADGE_DESCRIPTION,
                const.SENTINEL_EMPTY,
            )
        ),
        const.DATA_BADGE_LABELS: list(
            get_field(
                const.CFOF_BADGES_INPUT_LABELS,
                const.DATA_BADGE_LABELS,
                [],
            )
        ),
        const.DATA_BADGE_ICON: str(
            get_field(
                const.CFOF_BADGES_INPUT_ICON,
                const.DATA_BADGE_ICON,
                const.DEFAULT_BADGE_ICON,
            )
        ),
        # earned_by is runtime state, preserve on update or empty on create
        const.DATA_BADGE_EARNED_BY: (
            existing.get(const.DATA_BADGE_EARNED_BY, []) if existing else []
        ),
    }

    # --- Target Component ---
    if include_target:
        existing_target = existing.get(const.DATA_BADGE_TARGET, {}) if existing else {}

        # For nested dict fields, get directly from user_input or existing nested dict
        if const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE in user_input:
            threshold_value_input = user_input[
                const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE
            ]
        elif existing_target:
            threshold_value_input = existing_target.get(
                const.DATA_BADGE_TARGET_THRESHOLD_VALUE,
                const.DEFAULT_BADGE_TARGET_THRESHOLD_VALUE,
            )
        else:
            threshold_value_input = const.DEFAULT_BADGE_TARGET_THRESHOLD_VALUE

        try:
            threshold_value = float(threshold_value_input)
        except (TypeError, ValueError, AttributeError):
            const.LOGGER.warning(
                "Could not parse target threshold value '%s'. Using default.",
                threshold_value_input,
            )
            threshold_value = float(const.DEFAULT_BADGE_TARGET_THRESHOLD_VALUE)

        if const.CFOF_BADGES_INPUT_MAINTENANCE_RULES in user_input:
            maintenance_rules_input = user_input[
                const.CFOF_BADGES_INPUT_MAINTENANCE_RULES
            ]
        elif existing_target:
            maintenance_rules_input = existing_target.get(
                const.DATA_BADGE_MAINTENANCE_RULES,
                const.DEFAULT_BADGE_MAINTENANCE_THRESHOLD,
            )
        else:
            maintenance_rules_input = const.DEFAULT_BADGE_MAINTENANCE_THRESHOLD

        target_dict: dict[str, Any] = {
            const.DATA_BADGE_TARGET_THRESHOLD_VALUE: threshold_value,
            const.DATA_BADGE_MAINTENANCE_RULES: maintenance_rules_input,
        }

        # Cumulative badges don't need target_type (they always use points)
        if badge_type != const.BADGE_TYPE_CUMULATIVE:
            if const.CFOF_BADGES_INPUT_TARGET_TYPE in user_input:
                target_type = user_input[const.CFOF_BADGES_INPUT_TARGET_TYPE]
            elif existing_target:
                target_type = existing_target.get(
                    const.DATA_BADGE_TARGET_TYPE,
                    const.DEFAULT_BADGE_TARGET_TYPE,
                )
            else:
                target_type = const.DEFAULT_BADGE_TARGET_TYPE
            target_dict[const.DATA_BADGE_TARGET_TYPE] = target_type

        badge_data[const.DATA_BADGE_TARGET] = target_dict

    # --- Special Occasion Component ---
    if include_special_occasion:
        badge_data[const.DATA_BADGE_SPECIAL_OCCASION_TYPE] = str(
            get_field(
                const.CFOF_BADGES_INPUT_OCCASION_TYPE,
                const.DATA_BADGE_SPECIAL_OCCASION_TYPE,
                const.SENTINEL_EMPTY,
            )
        )

    # --- Achievement-Linked Component ---
    if include_achievement_linked:
        achievement_id = get_field(
            const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT,
            const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT,
            const.SENTINEL_EMPTY,
        )
        # Convert sentinel to empty string for storage
        if achievement_id in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
            achievement_id = ""
        badge_data[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = achievement_id

    # --- Challenge-Linked Component ---
    if include_challenge_linked:
        challenge_id = get_field(
            const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE,
            const.DATA_BADGE_ASSOCIATED_CHALLENGE,
            const.SENTINEL_EMPTY,
        )
        # Convert sentinel to empty string for storage
        if challenge_id in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
            challenge_id = ""
        badge_data[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = challenge_id

    # --- Tracked Chores Component ---
    if include_tracked_chores:
        # Handle nested existing value directly
        if const.CFOF_BADGES_INPUT_SELECTED_CHORES in user_input:
            selected_chores = user_input[const.CFOF_BADGES_INPUT_SELECTED_CHORES]
        elif existing:
            existing_tracked = existing.get(const.DATA_BADGE_TRACKED_CHORES, {})
            selected_chores = existing_tracked.get(
                const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
            )
        else:
            selected_chores = []

        if not isinstance(selected_chores, list):
            selected_chores = [selected_chores] if selected_chores else []
        selected_chores = [
            chore_id
            for chore_id in selected_chores
            if chore_id and chore_id != const.SENTINEL_EMPTY
        ]

        badge_data[const.DATA_BADGE_TRACKED_CHORES] = {
            const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES: selected_chores
        }

    # --- Assigned To Component ---
    if include_assigned_to:
        assigned = get_field(
            const.CFOF_BADGES_INPUT_ASSIGNED_TO,
            const.DATA_BADGE_ASSIGNED_TO,
            [],
        )
        if not isinstance(assigned, list):
            assigned = [assigned] if assigned else []
        assigned = [
            kid_id for kid_id in assigned if kid_id and kid_id != const.SENTINEL_EMPTY
        ]
        badge_data[const.DATA_BADGE_ASSIGNED_TO] = assigned

    # --- Awards Component ---
    if include_awards:
        existing_awards = existing.get(const.DATA_BADGE_AWARDS, {}) if existing else {}

        # Get award points from user_input or existing nested dict
        if const.CFOF_BADGES_INPUT_AWARD_POINTS in user_input:
            points_input = user_input[const.CFOF_BADGES_INPUT_AWARD_POINTS]
        elif existing_awards:
            points_input = existing_awards.get(
                const.DATA_BADGE_AWARDS_AWARD_POINTS,
                const.DEFAULT_BADGE_AWARD_POINTS,
            )
        else:
            points_input = const.DEFAULT_BADGE_AWARD_POINTS

        try:
            points = float(points_input)
        except (TypeError, ValueError, AttributeError):
            const.LOGGER.warning(
                "Could not parse award points value '%s'. Using default.",
                points_input,
            )
            points = float(const.DEFAULT_BADGE_AWARD_POINTS)

        if const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER in user_input:
            multiplier = user_input[const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER]
        elif existing_awards:
            multiplier = existing_awards.get(
                const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
                const.SENTINEL_NONE,
            )
        else:
            multiplier = const.SENTINEL_NONE

        if const.CFOF_BADGES_INPUT_AWARD_ITEMS in user_input:
            award_items = user_input[const.CFOF_BADGES_INPUT_AWARD_ITEMS]
        elif existing_awards:
            award_items = existing_awards.get(
                const.DATA_BADGE_AWARDS_AWARD_ITEMS,
                [],
            )
        else:
            award_items = []

        if not isinstance(award_items, list):
            award_items = [award_items] if award_items else []

        badge_data[const.DATA_BADGE_AWARDS] = {
            const.DATA_BADGE_AWARDS_AWARD_POINTS: points,
            const.DATA_BADGE_AWARDS_POINT_MULTIPLIER: multiplier,
            const.DATA_BADGE_AWARDS_AWARD_ITEMS: award_items,
        }

    # --- Reset Schedule Component ---
    if include_reset_schedule:
        existing_schedule = (
            existing.get(const.DATA_BADGE_RESET_SCHEDULE, {}) if existing else {}
        )

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY in user_input:
            recurring_frequency = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY
            ]
        elif existing_schedule:
            recurring_frequency = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                const.FREQUENCY_WEEKLY,
            )
        else:
            recurring_frequency = const.FREQUENCY_WEEKLY

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE in user_input:
            start_date = user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE]
        elif existing_schedule:
            start_date = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_START_DATE, None
            )
        else:
            start_date = None
        start_date = None if start_date in (None, "") else start_date

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE in user_input:
            end_date = user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE]
        elif existing_schedule:
            end_date = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE, None
            )
        else:
            end_date = None
        end_date = None if end_date in (None, "") else end_date

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS in user_input:
            grace_period_days = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS
            ]
        elif existing_schedule:
            grace_period_days = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS,
                const.DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS,
            )
        else:
            grace_period_days = const.DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL in user_input:
            custom_interval = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL
            ]
        elif existing_schedule:
            custom_interval = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL,
                const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL,
            )
        else:
            custom_interval = const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT in user_input:
            custom_interval_unit = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
            ]
        elif existing_schedule:
            custom_interval_unit = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT,
                const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT,
            )
        else:
            custom_interval_unit = (
                const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
            )

        badge_data[const.DATA_BADGE_RESET_SCHEDULE] = {
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: recurring_frequency,
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE: start_date,
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE: end_date,
            const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: grace_period_days,
            const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: custom_interval,
            const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: custom_interval_unit,
        }

    # Cast to BadgeData - the dict has all required keys based on badge_type
    return cast("BadgeData", badge_data)
