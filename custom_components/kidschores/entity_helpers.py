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

from typing import Any
import uuid

from . import const
from .type_defs import KidData, ParentData, RewardData

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


def build_reward(
    user_input: dict[str, Any],
    existing: RewardData | None = None,
) -> RewardData:
    """Build reward data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for reward field handling.
    One function handles both create (existing=None) and update (existing=RewardData).

    Args:
        user_input: Form/service data with CFOF_* keys (may have missing fields)
        existing: None for create, existing RewardData for update

    Returns:
        Complete RewardData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies const.DEFAULT_* for missing fields
        reward = build_reward({CFOF_REWARDS_INPUT_NAME: "New Reward"})

        # UPDATE mode - preserves existing fields not in user_input
        reward = build_reward({CFOF_REWARDS_INPUT_COST: 50}, existing=old_reward)
    """
    is_create = existing is None

    def get_field(
        cfof_key: str,
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default.

        Priority:
        1. If cfof_key in user_input → use user_input value
        2. If existing is not None → use existing value (update mode)
        3. Fall back to default (create mode)
        """
        if cfof_key in user_input:
            return user_input[cfof_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(
        const.CFOF_REWARDS_INPUT_NAME,
        const.DATA_REWARD_NAME,
        "",
    )
    name = str(raw_name).strip() if raw_name else ""

    # In create mode, name is required
    # In update mode, name is only validated if provided
    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_REWARDS_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_REWARD_NAME,
        )
    # If name was explicitly provided but is empty/whitespace, reject it
    if const.CFOF_REWARDS_INPUT_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_REWARDS_INPUT_NAME,
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
        cost=float(
            get_field(
                const.CFOF_REWARDS_INPUT_COST,
                const.DATA_REWARD_COST,
                const.DEFAULT_REWARD_COST,
            )
        ),
        description=str(
            get_field(
                const.CFOF_REWARDS_INPUT_DESCRIPTION,
                const.DATA_REWARD_DESCRIPTION,
                const.SENTINEL_EMPTY,
            )
        ),
        icon=str(
            get_field(
                const.CFOF_REWARDS_INPUT_ICON,
                const.DATA_REWARD_ICON,
                const.DEFAULT_REWARD_ICON,
            )
        ),
        reward_labels=list(
            get_field(
                const.CFOF_REWARDS_INPUT_LABELS,
                const.DATA_REWARD_LABELS,
                [],
            )
        ),
    )


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
