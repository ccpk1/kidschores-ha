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
from .type_defs import BadgeData, KidData, ParentData, RewardData

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
