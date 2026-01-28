"""User manager for KidsChores integration.

Handles CRUD operations for Kids and Parents with proper event signaling.
Includes shadow kid management for parent chore assignment feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.kidschores import const, data_builders as db

from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator


class UserManager(BaseManager):
    """Manages Kid and Parent CRUD operations.

    Provides centralized methods for:
    - Kid create/update/delete with reference cleanup
    - Parent create/update/delete with shadow kid management
    - Shadow kid creation/unlinking for parent chore assignment

    All mutations emit appropriate signals for cross-manager coordination.
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: KidsChoresDataCoordinator
    ) -> None:
        """Initialize user manager.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator managing this integration instance
        """
        super().__init__(hass, coordinator)

    @property
    def _data(self) -> dict[str, Any]:
        """Access coordinator's data dict dynamically.

        This must be a property to always get the current data dict,
        as coordinator._data may be reassigned during updates.
        """
        return self.coordinator._data

    async def async_setup(self) -> None:
        """Set up the user manager.

        Currently no event subscriptions needed as UserManager
        is the source of kid/parent events, not a consumer.
        """
        const.LOGGER.debug("UserManager async_setup complete")

    # -------------------------------------------------------------------------
    # KID CRUD OPERATIONS
    # -------------------------------------------------------------------------

    def create_kid(
        self,
        user_input: dict[str, Any],
        *,
        internal_id: str | None = None,
        prebuilt: bool = False,
        is_shadow: bool = False,
        linked_parent_id: str | None = None,
    ) -> str:
        """Create a new kid from user input or pre-built data.

        Args:
            user_input: Form input dict or pre-built KidData if prebuilt=True
            internal_id: Optional UUID to use (for pre-built data scenarios)
            prebuilt: If True, user_input is already a complete KidData dict
            is_shadow: If True, creates a shadow kid for parent chore assignment
            linked_parent_id: Parent ID to link if creating shadow kid

        Returns:
            The internal_id of the created kid

        Raises:
            HomeAssistantError: If kid creation fails
        """
        if prebuilt:
            kid_data = dict(user_input)
            kid_id = str(kid_data[const.DATA_KID_INTERNAL_ID])
        else:
            kid_data = dict(
                db.build_kid(
                    user_input,
                    is_shadow=is_shadow,
                    linked_parent_id=linked_parent_id,
                )
            )
            kid_id = str(kid_data[const.DATA_KID_INTERNAL_ID])

        # Override internal_id if provided
        if internal_id:
            kid_data[const.DATA_KID_INTERNAL_ID] = internal_id
            kid_id = internal_id

        # Ensure kids dict exists and store kid data
        self._data.setdefault(const.DATA_KIDS, {})[kid_id] = kid_data
        self.coordinator._persist()
        self.coordinator.async_update_listeners()

        kid_name = kid_data.get(const.DATA_KID_NAME, kid_id)
        const.LOGGER.info(
            "Created kid '%s' (ID: %s, shadow=%s)", kid_name, kid_id, is_shadow
        )

        # Emit kid created event
        self.emit(
            const.SIGNAL_SUFFIX_KID_CREATED,
            kid_id=kid_id,
            kid_name=kid_name,
            is_shadow=is_shadow,
        )

        return kid_id

    def update_kid(self, kid_id: str, updates: dict[str, Any]) -> None:
        """Update an existing kid with new values.

        Args:
            kid_id: Internal ID of the kid to update
            updates: Dict of field updates to merge into kid data

        Raises:
            HomeAssistantError: If kid not found
        """
        if kid_id not in self._data.get(const.DATA_KIDS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Merge updates into existing kid data
        self._data[const.DATA_KIDS][kid_id].update(updates)
        self.coordinator._persist()
        self.coordinator.async_update_listeners()

        kid_name = self._data[const.DATA_KIDS][kid_id].get(const.DATA_KID_NAME, kid_id)
        const.LOGGER.info("Updated kid '%s' (ID: %s)", kid_name, kid_id)

        # Emit kid updated event
        self.emit(
            const.SIGNAL_SUFFIX_KID_UPDATED,
            kid_id=kid_id,
            kid_name=kid_name,
        )

    def delete_kid(self, kid_id: str) -> None:
        """Delete kid from storage and cleanup references.

        For shadow kids (parent-linked profiles), this disables the parent's
        chore assignment flag and uses the existing shadow kid cleanup flow.

        Args:
            kid_id: Internal ID of the kid to delete

        Raises:
            HomeAssistantError: If kid not found
        """
        if kid_id not in self._data.get(const.DATA_KIDS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        kid_info = self._data[const.DATA_KIDS][kid_id]
        kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)

        # Shadow kid handling: disable parent flag and use existing cleanup
        if kid_info.get(const.DATA_KID_IS_SHADOW, False):
            parent_id = kid_info.get(const.DATA_KID_LINKED_PARENT_ID)
            if parent_id and parent_id in self._data.get(const.DATA_PARENTS, {}):
                # Disable chore assignment on parent and clear link
                self._data[const.DATA_PARENTS][parent_id][
                    const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT
                ] = False
                self._data[const.DATA_PARENTS][parent_id][
                    const.DATA_PARENT_LINKED_SHADOW_KID_ID
                ] = None
            # Unlink shadow kid (preserves kid + entities)
            self._unlink_shadow_kid(kid_id)
            # Remove unused translation sensors (if language no longer needed)
            self.coordinator.remove_unused_translation_sensors()
            self.coordinator._persist()
            self.coordinator.async_update_listeners()

            const.LOGGER.info(
                "Deleted shadow kid '%s' (ID: %s) via parent flag disable",
                kid_name,
                kid_id,
            )

            # Emit kid deleted event
            self.emit(
                const.SIGNAL_SUFFIX_KID_DELETED,
                kid_id=kid_id,
                kid_name=kid_name,
                was_shadow=True,
            )
            return  # Done - don't continue to normal kid deletion

        # Normal kid deletion continues below
        del self._data[const.DATA_KIDS][kid_id]

        # Remove HA entities
        self.coordinator._remove_entities_in_ha(kid_id)

        # Remove device from device registry
        self.coordinator._remove_device_from_registry(kid_id)

        # Cleanup references
        self.coordinator._cleanup_deleted_kid_references()
        self.coordinator._cleanup_parent_assignments()
        self.coordinator._cleanup_pending_reward_approvals()

        # Remove unused translation sensors (if language no longer needed)
        self.coordinator.remove_unused_translation_sensors()

        self.coordinator._persist()
        self.coordinator.async_update_listeners()
        const.LOGGER.info("Deleted kid '%s' (ID: %s)", kid_name, kid_id)

        # Emit kid deleted event
        self.emit(
            const.SIGNAL_SUFFIX_KID_DELETED,
            kid_id=kid_id,
            kid_name=kid_name,
            was_shadow=False,
        )

    # -------------------------------------------------------------------------
    # PARENT CRUD OPERATIONS
    # -------------------------------------------------------------------------

    def create_parent(
        self,
        user_input: dict[str, Any],
        *,
        internal_id: str | None = None,
        prebuilt: bool = False,
    ) -> str:
        """Create a new parent from user input or pre-built data.

        If parent has allow_chore_assignment enabled, also creates
        a linked shadow kid for chore assignment.

        Args:
            user_input: Form input dict or pre-built ParentData if prebuilt=True
            internal_id: Optional UUID to use (for pre-built data scenarios)
            prebuilt: If True, user_input is already a complete ParentData dict

        Returns:
            The internal_id of the created parent

        Raises:
            HomeAssistantError: If parent creation fails
        """
        if prebuilt:
            parent_data = dict(user_input)
            parent_id = str(parent_data[const.DATA_PARENT_INTERNAL_ID])
        else:
            parent_data = dict(db.build_parent(user_input))
            parent_id = str(parent_data[const.DATA_PARENT_INTERNAL_ID])

        # Override internal_id if provided
        if internal_id:
            parent_data[const.DATA_PARENT_INTERNAL_ID] = internal_id
            parent_id = internal_id

        parent_name = str(parent_data.get(const.DATA_PARENT_NAME, parent_id))

        # Ensure parents dict exists and store parent data
        self._data.setdefault(const.DATA_PARENTS, {})[parent_id] = parent_data

        # Create shadow kid if chore assignment is enabled
        shadow_kid_id: str | None = None
        if parent_data.get(const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, False):
            shadow_kid_id = self._create_shadow_kid_for_parent(parent_id, parent_data)
            # Link shadow kid to parent
            self._data[const.DATA_PARENTS][parent_id][
                const.DATA_PARENT_LINKED_SHADOW_KID_ID
            ] = shadow_kid_id

        self.coordinator._persist()
        self.coordinator.async_update_listeners()

        const.LOGGER.info("Created parent '%s' (ID: %s)", parent_name, parent_id)

        # Emit parent created event
        self.emit(
            const.SIGNAL_SUFFIX_PARENT_CREATED,
            parent_id=parent_id,
            parent_name=parent_name,
            shadow_kid_id=shadow_kid_id,
        )

        return parent_id

    def update_parent(self, parent_id: str, updates: dict[str, Any]) -> None:
        """Update an existing parent with new values.

        Handles shadow kid creation/deletion based on allow_chore_assignment changes.

        Args:
            parent_id: Internal ID of the parent to update
            updates: Dict of field updates to merge into parent data

        Raises:
            HomeAssistantError: If parent not found
        """
        if parent_id not in self._data.get(const.DATA_PARENTS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PARENT,
                    "name": parent_id,
                },
            )

        parent_data = self._data[const.DATA_PARENTS][parent_id]

        # Check for shadow kid state changes
        existing_shadow_kid_id = parent_data.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID)
        was_enabled = parent_data.get(const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, False)
        allow_chore_assignment = updates.get(
            const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, was_enabled
        )

        # Check if caller explicitly links to an existing kid (non-None value)
        # This skips auto-creation when services.py links a specific kid
        # Options flow passes None (from build_parent), so auto-creation proceeds
        explicit_shadow_link = updates.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID)

        # Merge updates into existing parent data
        self._data[const.DATA_PARENTS][parent_id].update(updates)

        # Handle shadow kid creation/deletion (skip if explicit link to existing kid)
        if allow_chore_assignment and not was_enabled and not explicit_shadow_link:
            # Enabling chore assignment - create shadow kid
            shadow_kid_id = self._create_shadow_kid_for_parent(
                parent_id, self._data[const.DATA_PARENTS][parent_id]
            )
            self._data[const.DATA_PARENTS][parent_id][
                const.DATA_PARENT_LINKED_SHADOW_KID_ID
            ] = shadow_kid_id
        elif not allow_chore_assignment and was_enabled and existing_shadow_kid_id:
            # Disabling chore assignment - unlink shadow kid (preserves data)
            self._unlink_shadow_kid(existing_shadow_kid_id)
            self._data[const.DATA_PARENTS][parent_id][
                const.DATA_PARENT_LINKED_SHADOW_KID_ID
            ] = None

        self.coordinator._persist()
        self.coordinator.async_update_listeners()

        parent_name = self._data[const.DATA_PARENTS][parent_id].get(
            const.DATA_PARENT_NAME, parent_id
        )
        const.LOGGER.info("Updated parent '%s' (ID: %s)", parent_name, parent_id)

        # Emit parent updated event
        self.emit(
            const.SIGNAL_SUFFIX_PARENT_UPDATED,
            parent_id=parent_id,
            parent_name=parent_name,
        )

    def delete_parent(self, parent_id: str) -> None:
        """Delete parent from storage.

        Cascades deletion to any linked shadow kid before removing the parent.

        Args:
            parent_id: Internal ID of the parent to delete

        Raises:
            HomeAssistantError: If parent not found
        """
        if parent_id not in self._data.get(const.DATA_PARENTS, {}):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PARENT,
                    "name": parent_id,
                },
            )

        parent_data = self._data[const.DATA_PARENTS][parent_id]
        parent_name = parent_data.get(const.DATA_PARENT_NAME, parent_id)

        # Cascade unlink shadow kid if exists (preserves data)
        shadow_kid_id = parent_data.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID)
        if shadow_kid_id:
            self._unlink_shadow_kid(shadow_kid_id)
            const.LOGGER.info(
                "Cascade unlinked shadow kid for parent '%s'", parent_name
            )

        del self._data[const.DATA_PARENTS][parent_id]

        # Remove unused translation sensors (if language no longer needed)
        self.coordinator.remove_unused_translation_sensors()

        self.coordinator._persist()
        self.coordinator.async_update_listeners()
        const.LOGGER.info("Deleted parent '%s' (ID: %s)", parent_name, parent_id)

        # Emit parent deleted event
        self.emit(
            const.SIGNAL_SUFFIX_PARENT_DELETED,
            parent_id=parent_id,
            parent_name=parent_name,
        )

    # -------------------------------------------------------------------------
    # SHADOW KID HELPERS
    # -------------------------------------------------------------------------

    def _create_shadow_kid_for_parent(
        self, parent_id: str, parent_info: dict[str, Any]
    ) -> str:
        """Create a shadow kid entity for a parent who enables chore assignment.

        Shadow kids are special kid entities that:
        - Use the parent's name and dashboard language
        - Are marked with is_shadow_kid=True
        - Link back to the parent via linked_parent_id
        - Have notifications disabled by default (editable via Manage Kids)

        Args:
            parent_id: The internal ID of the parent
            parent_info: The parent's data dictionary

        Returns:
            The internal_id of the newly created shadow kid
        """
        parent_name = parent_info.get(const.DATA_PARENT_NAME, const.SENTINEL_EMPTY)

        # Build shadow kid input from parent data
        shadow_input = {
            const.CFOF_KIDS_INPUT_KID_NAME: parent_name,
            const.CFOF_KIDS_INPUT_HA_USER: parent_info.get(
                const.DATA_PARENT_HA_USER_ID, ""
            ),
            const.CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE: parent_info.get(
                const.DATA_PARENT_DASHBOARD_LANGUAGE,
                const.DEFAULT_DASHBOARD_LANGUAGE,
            ),
            # Shadow kids have notifications disabled by default
            const.CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE: const.SENTINEL_EMPTY,
        }

        # Use unified db.build_kid() with shadow markers
        shadow_kid_data = dict(
            db.build_kid(shadow_input, is_shadow=True, linked_parent_id=parent_id)
        )
        shadow_kid_id = str(shadow_kid_data[const.DATA_KID_INTERNAL_ID])

        # Ensure kids dict exists and store shadow kid data (no persist - caller handles)
        self._data.setdefault(const.DATA_KIDS, {})[shadow_kid_id] = shadow_kid_data

        const.LOGGER.info(
            "Created shadow kid '%s' (ID: %s) for parent '%s' (ID: %s)",
            parent_name,
            shadow_kid_id,
            parent_name,
            parent_id,
        )

        return shadow_kid_id

    def _unlink_shadow_kid(self, shadow_kid_id: str) -> None:
        """Unlink a shadow kid from parent, converting to regular kid.

        This preserves all kid data (points, history, badges, etc.) while
        removing the shadow link. The kid is renamed with '_unlinked' suffix
        to prevent name conflicts with the parent.

        Args:
            shadow_kid_id: The internal ID of the shadow kid to unlink

        Raises:
            ServiceValidationError: If kid not found or not a shadow kid
        """
        if shadow_kid_id not in self._data[const.DATA_KIDS]:
            const.LOGGER.warning(
                "Attempted to unlink non-existent shadow kid: %s", shadow_kid_id
            )
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": shadow_kid_id,
                },
            )

        kid_info = self._data[const.DATA_KIDS][shadow_kid_id]
        kid_name = kid_info.get(const.DATA_KID_NAME, shadow_kid_id)

        # Verify this is actually a shadow kid
        if not kid_info.get(const.DATA_KID_IS_SHADOW, False):
            const.LOGGER.error("Attempted to unlink non-shadow kid '%s'", kid_name)
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_KID_NOT_SHADOW,
                translation_placeholders={"name": kid_name},
            )

        # Get linked parent to clear their reference
        parent_id = kid_info.get(const.DATA_KID_LINKED_PARENT_ID)
        if parent_id and parent_id in self._data.get(const.DATA_PARENTS, {}):
            # Clear parent's link to this shadow kid
            self._data[const.DATA_PARENTS][parent_id][
                const.DATA_PARENT_LINKED_SHADOW_KID_ID
            ] = None
            const.LOGGER.debug("Cleared parent '%s' link to shadow kid", parent_id)

        # Convert shadow kid to regular kid
        new_name = f"{kid_name}_unlinked"
        self._data[const.DATA_KIDS][shadow_kid_id][const.DATA_KID_NAME] = new_name
        self._data[const.DATA_KIDS][shadow_kid_id][const.DATA_KID_IS_SHADOW] = False
        self._data[const.DATA_KIDS][shadow_kid_id][const.DATA_KID_LINKED_PARENT_ID] = (
            None
        )

        const.LOGGER.info(
            "Unlinked shadow kid '%s' (ID: %s) → renamed to '%s'",
            kid_name,
            shadow_kid_id,
            new_name,
        )
