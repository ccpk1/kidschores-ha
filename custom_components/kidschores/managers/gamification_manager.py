"""Gamification Manager - Debounced badge/achievement/challenge evaluation.

This manager handles gamification evaluation with debouncing:
- Dirty tracking: Which kids need re-evaluation
- Debounced evaluation: Batch evaluations to avoid redundant processing
- Event listening: Responds to points_changed, chore_approved, etc.
- Result application: Awards/revokes badges, achievements, challenges

ARCHITECTURE (v0.5.0+):
- GamificationManager = "The Judge" (STATEFUL orchestration)
- GamificationEngine = Pure evaluation logic (STATELESS)
- Coordinator provides context data and receives result notifications
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from custom_components.kidschores import const, kc_helpers as kh
from custom_components.kidschores.engines.gamification_engine import GamificationEngine
from custom_components.kidschores.managers.base_manager import BaseManager

if TYPE_CHECKING:
    import asyncio

    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.type_defs import (
        AchievementData,
        BadgeData,
        ChallengeData,
        EvaluationContext,
        EvaluationResult,
    )


# Default debounce timing (seconds)
_DEBOUNCE_SECONDS: float = 2.0


class GamificationManager(BaseManager):
    """Manager for gamification evaluation with debouncing.

    Responsibilities:
    - Track which kids need gamification re-evaluation (dirty tracking)
    - Debounce evaluation to batch rapid changes
    - Build evaluation context from coordinator data
    - Apply evaluation results (badge awards, achievements, challenges)
    - Emit gamification events (badge_earned, achievement_unlocked, etc.)

    NOT responsible for:
    - Point calculations (handled by EconomyManager)
    - Notifications (handled by NotificationManager via Coordinator)
    - Storage persistence (handled by Coordinator)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize the GamificationManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main KidsChores coordinator
        """
        super().__init__(hass, coordinator)

        # Dirty tracking - kids needing re-evaluation
        self._dirty_kids: set[str] = set()

        # Debounce timer handle
        self._eval_timer: asyncio.TimerHandle | None = None

        # Debounce configuration
        self._debounce_seconds = _DEBOUNCE_SECONDS

    async def async_setup(self) -> None:
        """Set up the GamificationManager.

        Subscribe to all events that can trigger gamification checks.
        """
        # Point changes affect point-based badges
        self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)

        # Chore events affect chore count, daily completion, streaks
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DISAPPROVED, self._on_chore_disapproved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_STATUS_RESET, self._on_chore_status_reset)

        # Reward events can affect specific badges
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._on_reward_approved)

        # Bonus/penalty events affect points
        self.listen(const.SIGNAL_SUFFIX_BONUS_APPLIED, self._on_bonus_applied)
        self.listen(const.SIGNAL_SUFFIX_PENALTY_APPLIED, self._on_penalty_applied)

        const.LOGGER.debug(
            "GamificationManager initialized with %s second debounce",
            self._debounce_seconds,
        )

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_points_changed(self, payload: dict[str, Any]) -> None:
        """Handle points_changed event.

        Skip re-evaluation for points from gamification awards to prevent
        infinite loops (badge awards points → triggers gamification check
        → awards badge → awards points → ...).

        Args:
            payload: Event data with kid_id, delta, source, etc.
        """
        kid_id = payload.get("kid_id")
        source = payload.get("source", "")

        # Skip gamification-originated point changes to prevent loops
        gamification_sources = {
            const.POINTS_SOURCE_BADGES,
            const.POINTS_SOURCE_ACHIEVEMENTS,
            const.POINTS_SOURCE_CHALLENGES,
        }
        if source in gamification_sources:
            const.LOGGER.debug(
                "GamificationManager: Skipping points_changed from source %s "
                "(gamification-originated)",
                source,
            )
            return

        if kid_id:
            self._mark_dirty(kid_id)

    def _on_chore_approved(self, payload: dict[str, Any]) -> None:
        """Handle chore_approved event.

        Args:
            payload: Event data with kid_id, chore_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_dirty(kid_id)

    def _on_chore_disapproved(self, payload: dict[str, Any]) -> None:
        """Handle chore_disapproved event.

        Args:
            payload: Event data with kid_id, chore_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_dirty(kid_id)

    def _on_chore_status_reset(self, payload: dict[str, Any]) -> None:
        """Handle chore_status_reset event.

        Args:
            payload: Event data with kid_id, chore_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_dirty(kid_id)

    def _on_reward_approved(self, payload: dict[str, Any]) -> None:
        """Handle reward_approved event.

        Args:
            payload: Event data with kid_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_dirty(kid_id)

    def _on_bonus_applied(self, payload: dict[str, Any]) -> None:
        """Handle bonus_applied event.

        Args:
            payload: Event data with kid_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_dirty(kid_id)

    def _on_penalty_applied(self, payload: dict[str, Any]) -> None:
        """Handle penalty_applied event.

        Args:
            payload: Event data with kid_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_dirty(kid_id)

    # =========================================================================
    # DIRTY TRACKING AND DEBOUNCE
    # =========================================================================

    def _mark_dirty(self, kid_id: str) -> None:
        """Mark a kid as needing re-evaluation.

        Args:
            kid_id: The internal UUID of the kid
        """
        self._dirty_kids.add(kid_id)
        self._schedule_evaluation()
        const.LOGGER.debug(
            "Kid %s marked dirty for gamification evaluation, %d total dirty",
            kid_id,
            len(self._dirty_kids),
        )

    def _schedule_evaluation(self) -> None:
        """Schedule debounced evaluation.

        Cancels any existing timer and schedules a new one.
        This batches rapid changes into a single evaluation pass.
        """
        if self._eval_timer:
            self._eval_timer.cancel()

        self._eval_timer = self.hass.loop.call_later(
            self._debounce_seconds,
            lambda: self.hass.async_create_task(self._evaluate_dirty_kids()),
        )

    async def _evaluate_dirty_kids(self) -> None:
        """Evaluate all dirty kids in batch.

        This is the main evaluation loop that runs after debounce timer fires.
        """
        # Clear timer reference
        self._eval_timer = None

        # Capture and clear dirty set atomically
        kids_to_evaluate = self._dirty_kids.copy()
        self._dirty_kids.clear()

        if not kids_to_evaluate:
            return

        const.LOGGER.debug(
            "Starting gamification evaluation for %d kids: %s",
            len(kids_to_evaluate),
            list(kids_to_evaluate),
        )

        for kid_id in kids_to_evaluate:
            try:
                await self._evaluate_kid(kid_id)
            except Exception:
                const.LOGGER.exception(
                    "Error evaluating gamification for kid %s",
                    kid_id,
                )

    async def _evaluate_kid(self, kid_id: str) -> None:
        """Evaluate all gamification criteria for a single kid.

        Args:
            kid_id: The internal UUID of the kid
        """
        # Build evaluation context
        context = self._build_evaluation_context(kid_id)
        if not context:
            const.LOGGER.warning(
                "Could not build evaluation context for kid %s",
                kid_id,
            )
            return

        # Get badge data from coordinator
        badges_data = self.coordinator.badges_data

        # Evaluate each badge
        for badge_id, badge_data in badges_data.items():
            await self._evaluate_badge_for_kid(context, badge_id, badge_data)

        # Get achievement data from coordinator
        achievements_data = self.coordinator.achievements_data

        # Evaluate each achievement
        for achievement_id, achievement_data in achievements_data.items():
            await self._evaluate_achievement_for_kid(
                context, achievement_id, achievement_data
            )

        # Get challenge data from coordinator
        challenges_data = self.coordinator.challenges_data

        # Evaluate each challenge
        for challenge_id, challenge_data in challenges_data.items():
            await self._evaluate_challenge_for_kid(
                context, challenge_id, challenge_data
            )

    # =========================================================================
    # BADGE EVALUATION
    # =========================================================================

    async def _evaluate_badge_for_kid(
        self,
        context: EvaluationContext,
        badge_id: str,
        badge_data: BadgeData,
    ) -> None:
        """Evaluate a single badge for a kid.

        Args:
            context: The evaluation context for the kid
            badge_id: Badge internal ID
            badge_data: Badge definition
        """
        kid_id = context["kid_id"]

        # Check if kid already has this badge
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return

        badges_earned = kid_data.get(const.DATA_KID_BADGES_EARNED, {})
        already_earned = badge_id in badges_earned

        # Cast TypedDict to dict for engine (engine expects generic dict)
        badge_dict = cast("dict[str, Any]", badge_data)

        # Decide whether to check acquisition or retention
        if already_earned:
            result = GamificationEngine.check_retention(context, badge_dict)
        else:
            result = GamificationEngine.check_acquisition(context, badge_dict)

        # Apply result
        await self._apply_badge_result(kid_id, badge_id, badge_data, result)

    async def _apply_badge_result(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        result: EvaluationResult,
    ) -> None:
        """Apply badge evaluation result.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            result: Evaluation result from engine
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return

        badges_earned = kid_data.get(const.DATA_KID_BADGES_EARNED, {})
        already_earned = badge_id in badges_earned
        criteria_met = result.get("criteria_met", False)

        if criteria_met and not already_earned:
            # Award badge - call coordinator to persist and handle awards
            const.LOGGER.info(
                "Kid %s earned badge %s",
                kid_id,
                badge_id,
            )
            # Persist badge award via coordinator (handles data update + notifications)
            self.coordinator._award_badge(kid_id, badge_id)

            # Emit event for any additional listeners
            self.emit(
                const.SIGNAL_SUFFIX_BADGE_EARNED,
                kid_id=kid_id,
                badge_id=badge_id,
                badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
                result=result,
            )

        elif not criteria_met and already_earned:
            # Handle maintenance failure for Cumulative Badges
            badge_type = badge_data.get(const.DATA_BADGE_TYPE)

            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                # 1. COMMIT: Update storage to DEMOTED state (reduces multiplier)
                self.coordinator._demote_cumulative_badge(kid_id)

                # 2. EMIT: Notify listeners of status change
                self.emit(
                    const.SIGNAL_SUFFIX_BADGE_UPDATED,
                    kid_id=kid_id,
                    badge_id=badge_id,
                    status="demoted",
                    badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
                    result=result,
                )

                const.LOGGER.info(
                    "Kid %s demoted for badge %s (maintenance not met)",
                    kid_id,
                    badge_id,
                )
            # NOTE: Non-cumulative badges (periodic, special occasion) are permanent
            # once earned - no maintenance or demotion applies

    # =========================================================================
    # ACHIEVEMENT EVALUATION
    # =========================================================================

    async def _evaluate_achievement_for_kid(
        self,
        context: EvaluationContext,
        achievement_id: str,
        achievement_data: AchievementData,
    ) -> None:
        """Evaluate a single achievement for a kid.

        Args:
            context: The evaluation context for the kid
            achievement_id: Achievement internal ID
            achievement_data: Achievement definition
        """
        kid_id = context["kid_id"]

        # Check if kid already has this achievement (awarded flag in progress)
        achievement_progress = achievement_data.get(const.DATA_ACHIEVEMENT_PROGRESS, {})
        kid_progress = achievement_progress.get(kid_id, {})
        already_awarded = kid_progress.get(const.DATA_ACHIEVEMENT_AWARDED, False)

        if already_awarded:
            # Achievements are permanent - no re-evaluation needed
            return

        # Cast TypedDict to dict for engine (engine expects generic dict)
        achievement_dict = cast("dict[str, Any]", achievement_data)
        result = GamificationEngine.evaluate_achievement(context, achievement_dict)

        # Apply result
        await self._apply_achievement_result(
            kid_id, achievement_id, achievement_data, result
        )

    async def _apply_achievement_result(
        self,
        kid_id: str,
        achievement_id: str,
        achievement_data: AchievementData,
        result: EvaluationResult,
    ) -> None:
        """Apply achievement evaluation result.

        Args:
            kid_id: Kid's internal ID
            achievement_id: Achievement internal ID
            achievement_data: Achievement definition
            result: Evaluation result from engine
        """
        criteria_met = result.get("criteria_met", False)

        if criteria_met:
            const.LOGGER.info(
                "Kid %s unlocked achievement %s",
                kid_id,
                achievement_id,
            )
            # Persist achievement award via coordinator (handles data update + notifications)
            self.coordinator._award_achievement(kid_id, achievement_id)

            # Emit event for any additional listeners
            self.emit(
                const.SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED,
                kid_id=kid_id,
                achievement_id=achievement_id,
                achievement_name=achievement_data.get(
                    const.DATA_ACHIEVEMENT_NAME, "Unknown"
                ),
                result=result,
            )

    # =========================================================================
    # CHALLENGE EVALUATION
    # =========================================================================

    async def _evaluate_challenge_for_kid(
        self,
        context: EvaluationContext,
        challenge_id: str,
        challenge_data: ChallengeData,
    ) -> None:
        """Evaluate a single challenge for a kid.

        Args:
            context: The evaluation context for the kid
            challenge_id: Challenge internal ID
            challenge_data: Challenge definition
        """
        kid_id = context["kid_id"]

        # Check if kid already completed this challenge (awarded flag in progress)
        challenge_progress = challenge_data.get(const.DATA_CHALLENGE_PROGRESS, {})
        kid_progress = challenge_progress.get(kid_id, {})
        already_awarded = kid_progress.get(const.DATA_CHALLENGE_AWARDED, False)

        if already_awarded:
            # Challenges can only be completed once
            return

        # Cast TypedDict to dict for engine (engine expects generic dict)
        challenge_dict = cast("dict[str, Any]", challenge_data)
        result = GamificationEngine.evaluate_challenge(context, challenge_dict)

        # Apply result
        await self._apply_challenge_result(kid_id, challenge_id, challenge_data, result)

    async def _apply_challenge_result(
        self,
        kid_id: str,
        challenge_id: str,
        challenge_data: ChallengeData,
        result: EvaluationResult,
    ) -> None:
        """Apply challenge evaluation result.

        Args:
            kid_id: Kid's internal ID
            challenge_id: Challenge internal ID
            challenge_data: Challenge definition
            result: Evaluation result from engine
        """
        criteria_met = result.get("criteria_met", False)

        if criteria_met:
            const.LOGGER.info(
                "Kid %s completed challenge %s",
                kid_id,
                challenge_id,
            )
            # Persist challenge completion via coordinator (handles data update + notifications)
            self.coordinator._award_challenge(kid_id, challenge_id)

            # Emit event for any additional listeners
            self.emit(
                const.SIGNAL_SUFFIX_CHALLENGE_COMPLETED,
                kid_id=kid_id,
                challenge_id=challenge_id,
                challenge_name=challenge_data.get(const.DATA_CHALLENGE_NAME, "Unknown"),
                result=result,
            )

    # =========================================================================
    # CONTEXT BUILDING
    # =========================================================================

    def _build_evaluation_context(self, kid_id: str) -> EvaluationContext | None:
        """Build evaluation context from coordinator data.

        This extracts minimal data needed for gamification evaluation.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            EvaluationContext dict or None if kid not found
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return None

        # Get today's ISO date using helper
        today_iso = kh.dt_today_iso()

        # Get point stats for total earned (nested in point_stats dict)
        point_stats = kid_data.get(const.DATA_KID_POINT_STATS, {})
        total_earned = float(
            point_stats.get(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME, 0.0)
        )

        # Get badge progress from kid data
        badge_progress = kid_data.get(const.DATA_KID_BADGE_PROGRESS, {})

        # Build achievement progress from achievements_data
        # (progress is stored in each achievement, keyed by kid_id)
        achievement_progress: dict[str, Any] = {}
        for ach_id, ach_data in self.coordinator.achievements_data.items():
            ach_progress = ach_data.get(const.DATA_ACHIEVEMENT_PROGRESS, {})
            if kid_id in ach_progress:
                achievement_progress[ach_id] = ach_progress[kid_id]

        # Build challenge progress from challenges_data
        # (progress is stored in each challenge, keyed by kid_id)
        challenge_progress: dict[str, Any] = {}
        for chal_id, chal_data in self.coordinator.challenges_data.items():
            chal_progress = chal_data.get(const.DATA_CHALLENGE_PROGRESS, {})
            if kid_id in chal_progress:
                challenge_progress[chal_id] = chal_progress[kid_id]

        # Build context (using cast pattern for TypedDict compatibility)
        context: EvaluationContext = {
            "kid_id": kid_id,
            "kid_name": kid_data.get(const.DATA_KID_NAME, "Unknown"),
            "current_points": float(kid_data.get(const.DATA_KID_POINTS, 0.0)),
            "total_points_earned": total_earned,
            "badge_progress": badge_progress,
            "cumulative_badge_progress": kid_data.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
            ),
            "badges_earned": kid_data.get(const.DATA_KID_BADGES_EARNED, {}),
            "chore_stats": kid_data.get(const.DATA_KID_CHORE_STATS, {}),
            "achievement_progress": achievement_progress,
            "challenge_progress": challenge_progress,
            "today_iso": today_iso,
        }

        return context

    # =========================================================================
    # DRY RUN (SHADOW MODE)
    # =========================================================================

    def dry_run_badge(
        self,
        kid_id: str,
        badge_id: str,
    ) -> EvaluationResult | None:
        """Evaluate badge without applying results (for comparison/debugging).

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID

        Returns:
            EvaluationResult or None if context/badge not found
        """
        context = self._build_evaluation_context(kid_id)
        if not context:
            return None

        badge_data = self.coordinator.badges_data.get(badge_id)
        if not badge_data:
            return None

        # Cast TypedDict to dict for engine
        badge_dict = cast("dict[str, Any]", badge_data)
        return GamificationEngine.evaluate_badge(context, badge_dict)

    def dry_run_achievement(
        self,
        kid_id: str,
        achievement_id: str,
    ) -> EvaluationResult | None:
        """Evaluate achievement without applying results.

        Args:
            kid_id: Kid's internal ID
            achievement_id: Achievement internal ID

        Returns:
            EvaluationResult or None if context/achievement not found
        """
        context = self._build_evaluation_context(kid_id)
        if not context:
            return None

        achievement_data = self.coordinator.achievements_data.get(achievement_id)
        if not achievement_data:
            return None

        # Cast TypedDict to dict for engine
        achievement_dict = cast("dict[str, Any]", achievement_data)
        return GamificationEngine.evaluate_achievement(context, achievement_dict)

    def dry_run_challenge(
        self,
        kid_id: str,
        challenge_id: str,
    ) -> EvaluationResult | None:
        """Evaluate challenge without applying results.

        Args:
            kid_id: Kid's internal ID
            challenge_id: Challenge internal ID

        Returns:
            EvaluationResult or None if context/challenge not found
        """
        context = self._build_evaluation_context(kid_id)
        if not context:
            return None

        challenge_data = self.coordinator.challenges_data.get(challenge_id)
        if not challenge_data:
            return None

        # Cast TypedDict to dict for engine
        challenge_dict = cast("dict[str, Any]", challenge_data)
        return GamificationEngine.evaluate_challenge(context, challenge_dict)
