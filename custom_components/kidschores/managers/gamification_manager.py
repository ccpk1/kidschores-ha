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

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError

from custom_components.kidschores import const, kc_helpers as kh
from custom_components.kidschores.engines.gamification_engine import GamificationEngine
from custom_components.kidschores.managers.base_manager import BaseManager
from custom_components.kidschores.utils.dt_utils import (
    dt_add_interval,
    dt_next_schedule,
    dt_now_local,
    dt_today_iso,
)

if TYPE_CHECKING:
    import asyncio

    from homeassistant.core import HomeAssistant

    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator
    from custom_components.kidschores.type_defs import (
        AchievementData,
        AchievementProgress,
        BadgeData,
        ChallengeData,
        EvaluationContext,
        EvaluationResult,
        KidBadgeProgress,
        KidData,
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

        # Update cumulative badge progress (for positive deltas only)
        delta = payload.get("delta", 0.0)
        if delta > 0 and kid_id:
            kid_info = self.coordinator.kids_data.get(kid_id)
            if kid_info:
                progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
                cycle_points = progress.get(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0.0
                )
                cycle_points += delta
                progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = round(
                    cycle_points, const.DATA_FLOAT_PRECISION
                )

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
    # PUBLIC API
    # =========================================================================

    def recalculate_all_badges(self) -> None:
        """Global re-check of all badges for all kids.

        Marks all kids as dirty for re-evaluation. The debounced evaluation
        logic will handle persistence when changes are actually made.
        """
        const.LOGGER.info("Recalculate All Badges - Starting recalculation")
        for kid_id in self.coordinator.kids_data:
            self._mark_dirty(kid_id)
        const.LOGGER.info("Recalculate All Badges - All kids marked for evaluation")

    async def award_achievement(self, kid_id: str, achievement_id: str) -> None:
        """Award the achievement to the kid.

        Update the achievement progress to indicate it is earned,
        and send notifications to both the kid and their parents.

        Args:
            kid_id: The internal UUID of the kid
            achievement_id: The internal UUID of the achievement
        """
        achievement_info = self.coordinator.achievements_data.get(achievement_id)
        if not achievement_info:
            const.LOGGER.error(
                "ERROR: Achievement Award - Achievement ID '%s' not found.",
                achievement_id,
            )
            return

        # Get or create the existing progress dictionary for this kid
        progress_for_kid = achievement_info.setdefault(
            const.DATA_ACHIEVEMENT_PROGRESS, {}
        ).get(kid_id)
        if progress_for_kid is None:
            # If it doesn't exist, initialize it with baseline from the kid's current total.
            kid_info: KidData | dict[str, Any] = self.coordinator.kids_data.get(
                kid_id, {}
            )
            chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
            progress_dict = {
                const.DATA_ACHIEVEMENT_BASELINE: chore_stats.get(
                    const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME, const.DEFAULT_ZERO
                ),
                const.DATA_ACHIEVEMENT_CURRENT_VALUE: const.DEFAULT_ZERO,
                const.DATA_ACHIEVEMENT_AWARDED: False,
            }
            achievement_info[const.DATA_ACHIEVEMENT_PROGRESS][kid_id] = cast(
                "AchievementProgress", progress_dict
            )
            progress_for_kid = cast("AchievementProgress", progress_dict)

        # Type narrow: progress_for_kid is now guaranteed to be AchievementProgress
        progress_for_kid_checked: AchievementProgress = progress_for_kid

        # Mark achievement as earned for the kid
        progress_for_kid_checked[const.DATA_ACHIEVEMENT_AWARDED] = True
        progress_for_kid_checked[const.DATA_ACHIEVEMENT_CURRENT_VALUE] = (  # type: ignore[typeddict-unknown-key]
            achievement_info.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        )

        # Award the extra reward points defined in the achievement
        extra_points = achievement_info.get(
            const.DATA_ACHIEVEMENT_REWARD_POINTS, const.DEFAULT_ZERO
        )

        # Emit event for NotificationManager to send notifications
        # EconomyManager listens to this and handles point deposit
        self.emit(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED,
            kid_id=kid_id,
            achievement_id=achievement_id,
            achievement_name=achievement_info.get(const.DATA_ACHIEVEMENT_NAME, ""),
            achievement_points=extra_points,
        )

        const.LOGGER.debug(
            "DEBUG: Achievement Award - Achievement ID '%s' to Kid ID '%s'",
            achievement_info.get(const.DATA_ACHIEVEMENT_NAME),
            kid_id,
        )
        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    async def award_challenge(self, kid_id: str, challenge_id: str) -> None:
        """Award the challenge to the kid.

        Update progress and notify kid/parents.

        Args:
            kid_id: The internal UUID of the kid
            challenge_id: The internal UUID of the challenge
        """
        challenge_info = self.coordinator.challenges_data.get(challenge_id)
        if not challenge_info:
            const.LOGGER.error(
                "ERROR: Challenge Award - Challenge ID '%s' not found", challenge_id
            )
            return

        # Get or create the existing progress dictionary for this kid
        progress_for_kid = challenge_info.setdefault(
            const.DATA_CHALLENGE_PROGRESS, {}
        ).setdefault(
            kid_id,
            {
                const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                const.DATA_CHALLENGE_AWARDED: False,
            },
        )

        # Mark challenge as earned for the kid by storing progress
        progress_for_kid[const.DATA_CHALLENGE_AWARDED] = True
        progress_for_kid[const.DATA_CHALLENGE_COUNT] = challenge_info.get(
            const.DATA_CHALLENGE_TARGET_VALUE, 1
        )

        # Get extra reward points from the challenge
        extra_points = challenge_info.get(
            const.DATA_CHALLENGE_REWARD_POINTS, const.DEFAULT_ZERO
        )

        # Emit event for NotificationManager to send notifications
        # EconomyManager listens to this and handles point deposit
        self.emit(
            const.SIGNAL_SUFFIX_CHALLENGE_COMPLETED,
            kid_id=kid_id,
            challenge_id=challenge_id,
            challenge_name=challenge_info.get(const.DATA_CHALLENGE_NAME, ""),
            challenge_points=extra_points,
        )

        const.LOGGER.debug(
            "DEBUG: Challenge Award - Challenge ID '%s' to Kid ID '%s'",
            challenge_info.get(const.DATA_CHALLENGE_NAME),
            kid_id,
        )
        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    def update_streak_progress(
        self, progress: AchievementProgress, today: date
    ) -> None:
        """Update a streak progress dict.

        If the last approved date was yesterday, increment the streak.
        Otherwise, reset to 1.

        Args:
            progress: Achievement progress dictionary to update
            today: Current date for streak calculation
        """
        last_date = None
        last_date_str = progress.get(const.DATA_KID_LAST_STREAK_DATE)
        if last_date_str:
            try:
                last_date = date.fromisoformat(last_date_str)
            except (ValueError, TypeError, KeyError):
                last_date = None

        # If already updated today, do nothing
        if last_date == today:
            return

        # If yesterday was the last update, increment the streak
        if last_date == today - timedelta(days=1):
            current_streak = progress.get(const.DATA_KID_CURRENT_STREAK, 0)
            progress[const.DATA_KID_CURRENT_STREAK] = current_streak + 1

        # Reset to 1 if not done yesterday
        else:
            progress[const.DATA_KID_CURRENT_STREAK] = 1

        progress[const.DATA_KID_LAST_STREAK_DATE] = today.isoformat()

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
            # Award badge - use local method (handles data update + notifications)
            const.LOGGER.info(
                "Kid %s earned badge %s",
                kid_id,
                badge_id,
            )
            await self.award_badge(kid_id, badge_id)

            # Get badge points for the event payload
            award_data = badge_data.get(const.DATA_BADGE_AWARDS, {})
            badge_points = award_data.get(
                const.DATA_BADGE_AWARDS_AWARD_POINTS, const.DEFAULT_ZERO
            )

            # Emit event for any additional listeners
            # EconomyManager listens to this and handles point deposit
            self.emit(
                const.SIGNAL_SUFFIX_BADGE_EARNED,
                kid_id=kid_id,
                badge_id=badge_id,
                badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
                badge_points=badge_points,
                result=result,
            )

        elif not criteria_met and already_earned:
            # Handle maintenance failure for Cumulative Badges
            badge_type = badge_data.get(const.DATA_BADGE_TYPE)

            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                # 1. COMMIT: Update storage to DEMOTED state (reduces multiplier)
                self.demote_cumulative_badge(kid_id)

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
            # Persist achievement award (handles data update + notifications)
            await self.award_achievement(kid_id, achievement_id)

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
            # Persist challenge completion (handles data update + notifications)
            await self.award_challenge(kid_id, challenge_id)

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
        today_iso = dt_today_iso()

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

    # =========================================================================
    # BADGE UTILITIES (Pure Helpers - No Side Effects)
    # =========================================================================
    # These methods perform calculations/lookups without modifying state.
    # Migrated from coordinator.py as Tier 1 (no internal dependencies).

    def process_award_items(
        self,
        award_items: list[str],
        rewards_dict: dict[str, Any],
        bonuses_dict: dict[str, Any],
        penalties_dict: dict[str, Any],
    ) -> tuple[dict[str, list[str]], list[str]]:
        """Process award_items and return dicts of items to award or penalize.

        Args:
            award_items: List of award item strings (e.g., "reward:uuid", "bonus:uuid")
            rewards_dict: Dictionary of reward data keyed by reward_id
            bonuses_dict: Dictionary of bonus data keyed by bonus_id
            penalties_dict: Dictionary of penalty data keyed by penalty_id

        Returns:
            Tuple of (to_award dict, to_penalize list)
        """
        to_award: dict[str, list[str]] = {
            const.AWARD_ITEMS_KEY_REWARDS: [],
            const.AWARD_ITEMS_KEY_BONUSES: [],
        }
        to_penalize: list[str] = []
        for item in award_items:
            if item.startswith(const.AWARD_ITEMS_PREFIX_REWARD):
                reward_id = item.split(":", 1)[1]
                if reward_id in rewards_dict:
                    to_award[const.AWARD_ITEMS_KEY_REWARDS].append(reward_id)
            elif item.startswith(const.AWARD_ITEMS_PREFIX_BONUS):
                bonus_id = item.split(":", 1)[1]
                if bonus_id in bonuses_dict:
                    to_award[const.AWARD_ITEMS_KEY_BONUSES].append(bonus_id)
            elif item.startswith(const.AWARD_ITEMS_PREFIX_PENALTY):
                penalty_id = item.split(":", 1)[1]
                if penalty_id in penalties_dict:
                    to_penalize.append(penalty_id)
        return to_award, to_penalize

    def get_badge_in_scope_chores_list(
        self,
        badge_info: BadgeData,
        kid_id: str,
        kid_assigned_chores: list[str] | None = None,
    ) -> list[str]:
        """Get the list of chore IDs that are in-scope for this badge evaluation.

        For badges with tracked chores:
        - Returns only those specific chore IDs that are also assigned to the kid
        For badges without tracked chores:
        - Returns all chore IDs assigned to the kid

        Args:
            badge_info: Badge configuration dictionary
            kid_id: Kid's internal ID
            kid_assigned_chores: Optional pre-computed list of chores assigned to kid
                                (optimization to avoid re-iterating all chores)

        Returns:
            List of chore IDs in scope for this badge/kid combination
        """
        badge_type = badge_info.get(const.DATA_BADGE_TYPE, const.BADGE_TYPE_PERIODIC)
        include_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES

        # OPTIMIZATION: Use pre-computed list if provided, otherwise compute
        if kid_assigned_chores is None:
            kid_assigned_chores = []
            # Get all chores assigned to this kid
            for chore_id, chore_info in self.coordinator.chores_data.items():
                chore_assigned_to = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                if not chore_assigned_to or kid_id in chore_assigned_to:
                    kid_assigned_chores.append(chore_id)

        # If badge does not include tracked chores, return empty list
        if include_tracked_chores:
            tracked_chores = badge_info.get(const.DATA_BADGE_TRACKED_CHORES, {})
            tracked_chore_ids = tracked_chores.get(
                const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
            )

            if tracked_chore_ids:
                # Badge has specific tracked chores, return only those assigned to the kid
                return [
                    chore_id
                    for chore_id in tracked_chore_ids
                    if chore_id in kid_assigned_chores
                ]
            # Badge considers all chores, return all chores assigned to the kid
            return kid_assigned_chores
        # Badge does not include tracked chores component, return empty list
        return []

    def get_cumulative_badge_levels(
        self, kid_id: str
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
        float,
        float,
    ]:
        """Determine the highest earned cumulative badge and adjacent tier badges.

        Args:
            kid_id: Kid's internal ID

        Returns:
            Tuple of:
            - highest_earned_badge_info (dict or None)
            - next_higher_badge_info (dict or None)
            - next_lower_badge_info (dict or None)
            - baseline (float)
            - cycle_points (float)
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return None, None, None, 0.0, 0.0

        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        baseline = round(
            float(progress.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE, 0)),
            const.DATA_FLOAT_PRECISION,
        )
        cycle_points = round(
            float(
                progress.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0)
            ),
            const.DATA_FLOAT_PRECISION,
        )
        total_points = baseline + cycle_points

        # Get sorted list of cumulative badges (lowest to highest threshold)
        cumulative_badges = sorted(
            (
                (badge_id, badge_info)
                for badge_id, badge_info in self.coordinator.badges_data.items()
                if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE
            ),
            key=lambda item: float(
                item[1]
                .get(const.DATA_BADGE_TARGET, {})
                .get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)
            ),
        )

        if not cumulative_badges:
            # No cumulative badges exist - reset tracking values to 0
            return None, None, None, 0.0, 0.0

        highest_earned: dict[str, Any] | None = None
        next_higher: dict[str, Any] | None = None
        next_lower: dict[str, Any] | None = None
        previous_badge_info: dict[str, Any] | None = None

        for _badge_id, badge_info in cumulative_badges:
            threshold = float(
                badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                )
            )

            # True if list is empty or kid_id is in the assigned list
            is_assigned_to = not badge_info.get(
                const.DATA_BADGE_ASSIGNED_TO, []
            ) or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])

            if is_assigned_to:
                if total_points >= threshold:
                    highest_earned = cast("dict[str, Any]", badge_info)
                    next_lower = previous_badge_info
                else:
                    next_higher = cast("dict[str, Any]", badge_info)
                    break

                previous_badge_info = cast("dict[str, Any]", badge_info)

        return (
            highest_earned,
            next_higher,
            next_lower,
            baseline,
            cycle_points,
        )

    def update_point_multiplier_for_kid(self, kid_id: str) -> None:
        """Update the kid's points multiplier based on current cumulative badge.

        Args:
            kid_id: Kid's internal ID
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        current_badge_id = progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID
        )

        multiplier: float = const.DEFAULT_KID_POINTS_MULTIPLIER

        if current_badge_id:
            badge_data = self.coordinator.badges_data.get(current_badge_id)
            if badge_data:
                badge_awards = badge_data.get(const.DATA_BADGE_AWARDS, {})
                raw_multiplier = badge_awards.get(
                    const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
                    const.DEFAULT_KID_POINTS_MULTIPLIER,
                )
                if isinstance(raw_multiplier, (int, float)):
                    multiplier = float(raw_multiplier)

        kid_info[const.DATA_KID_POINTS_MULTIPLIER] = multiplier

    # =========================================================================
    # BADGE CORE OPERATIONS (State-Modifying Methods)
    # =========================================================================
    # These methods award/demote/remove badges and modify kid/badge state.
    # Migrated from coordinator.py as Tier 2/3 (depend on utilities above).

    def update_badges_earned_for_kid(self, kid_id: str, badge_id: str) -> None:
        """Update the kid's badges-earned tracking for the given badge.

        Updates period stats (daily, weekly, etc.) for badge award tracking.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge's internal ID
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.error(
                "ERROR: Update Kid Badges Earned - Kid ID '%s' not found", kid_id
            )
            return

        badge_info = self.coordinator.badges_data.get(badge_id)
        if not badge_info:
            const.LOGGER.error(
                "ERROR: Update Kid Badges Earned - Badge ID '%s' not found", badge_id
            )
            return

        today_local_iso = dt_today_iso()
        now_local = dt_now_local()

        badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})

        # Get period mapping from StatisticsEngine
        period_mapping = self.coordinator.stats.get_period_keys(now_local)

        # Declare periods variable for use in both branches
        periods: dict[str, Any]

        if badge_id not in badges_earned:
            # Create new badge tracking entry with all_time bucket
            badges_earned[badge_id] = {  # pyright: ignore[reportArgumentType]
                const.DATA_KID_BADGES_EARNED_NAME: badge_info.get(
                    const.DATA_BADGE_NAME, ""
                ),
                const.DATA_KID_BADGES_EARNED_LAST_AWARDED: today_local_iso,
                const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1,
                const.DATA_KID_BADGES_EARNED_PERIODS: {
                    const.DATA_KID_BADGES_EARNED_PERIODS_DAILY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_WEEKLY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_MONTHLY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_YEARLY: {},
                    const.DATA_KID_BADGES_EARNED_PERIODS_ALL_TIME: {},
                },
            }
            # Record initial award using StatisticsEngine
            periods = badges_earned[badge_id][  # type: ignore[assignment]
                const.DATA_KID_BADGES_EARNED_PERIODS
            ]
            self.coordinator.stats.record_transaction(
                periods,
                {const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1},
                period_key_mapping=period_mapping,
            )
            const.LOGGER.info(
                "Update Kid Badges Earned - Created new tracking for badge '%s' for kid '%s'",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )
        else:
            tracking_entry = badges_earned[badge_id]
            tracking_entry[const.DATA_KID_BADGES_EARNED_NAME] = badge_info.get(
                const.DATA_BADGE_NAME, ""
            )
            tracking_entry[const.DATA_KID_BADGES_EARNED_LAST_AWARDED] = today_local_iso
            tracking_entry[const.DATA_KID_BADGES_EARNED_AWARD_COUNT] = (
                tracking_entry.get(const.DATA_KID_BADGES_EARNED_AWARD_COUNT, 0) + 1
            )

            # Ensure periods structure exists with all_time bucket
            periods = tracking_entry.setdefault(
                const.DATA_KID_BADGES_EARNED_PERIODS,
                {},  # type: ignore[typeddict-item]
            )
            periods.setdefault(const.DATA_KID_BADGES_EARNED_PERIODS_ALL_TIME, {})

            # Record award using StatisticsEngine
            self.coordinator.stats.record_transaction(
                periods,
                {const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1},
                period_key_mapping=period_mapping,
            )

            const.LOGGER.info(
                "Update Kid Badges Earned - Updated tracking for badge '%s' for kid '%s'",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )

            # Cleanup old period data using StatisticsEngine
            self.coordinator.stats.prune_history(
                periods, self.coordinator._get_retention_config()
            )

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    def update_chore_badge_references_for_kid(
        self, include_cumulative_badges: bool = False
    ) -> None:
        """Update badge reference lists in kid chore data.

        Maintains a list of which badges reference each chore for quick lookups.

        Args:
            include_cumulative_badges: Include cumulative badges in references.
                Default False since cumulative badges are points-only.
        """
        # Clear existing badge references
        for _kid_id, kid_info in self.coordinator.kids_data.items():
            if const.DATA_KID_CHORE_DATA not in kid_info:
                continue

            for chore_data in kid_info[const.DATA_KID_CHORE_DATA].values():
                chore_data[const.DATA_KID_CHORE_DATA_BADGE_REFS] = []

        # Add badge references to relevant chores
        for badge_id, badge_info in self.coordinator.badges_data.items():
            # Skip cumulative badges if not explicitly included
            if (
                not include_cumulative_badges
                and badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE
            ):
                continue

            # For each kid this badge is assigned to
            assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            for kid_id in (
                assigned_to or self.coordinator.kids_data.keys()
            ):  # If empty, apply to all kids
                kid_info_loop = self.coordinator.kids_data.get(kid_id)
                if not kid_info_loop or const.DATA_KID_CHORE_DATA not in kid_info_loop:
                    continue

                # Use the helper function to get the correct in-scope chores
                in_scope_chores_list = self.get_badge_in_scope_chores_list(
                    badge_info, kid_id
                )

                # Add badge reference to each tracked chore
                for chore_id in in_scope_chores_list:
                    if chore_id in kid_info_loop[const.DATA_KID_CHORE_DATA]:
                        chore_entry = kid_info_loop[const.DATA_KID_CHORE_DATA][chore_id]
                        badge_refs: list[str] = chore_entry.get(
                            const.DATA_KID_CHORE_DATA_BADGE_REFS, []
                        )
                        if badge_id not in badge_refs:
                            badge_refs.append(badge_id)
                            chore_entry[const.DATA_KID_CHORE_DATA_BADGE_REFS] = (
                                badge_refs
                            )

    def get_cumulative_badge_progress(self, kid_id: str) -> dict[str, Any]:
        """Build and return the full cumulative badge progress block for a kid.

        Uses badge level logic, progress tracking, and next-tier metadata.
        Does not mutate state.

        Args:
            kid_id: Kid's internal ID

        Returns:
            Dictionary with cumulative badge progress data
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return {}

        # Make a copy of existing progress to avoid modifying stored data
        stored_progress = kid_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        ).copy()

        # Compute values from badge level logic
        (highest_earned, next_higher, next_lower, baseline, cycle_points) = (
            self.get_cumulative_badge_levels(kid_id)
        )
        total_points = baseline + cycle_points

        # Determine which badge should be considered current
        current_status = stored_progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.CUMULATIVE_BADGE_STATE_ACTIVE,
        )
        if current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED:
            current_badge_info = next_lower
        else:
            current_badge_info = highest_earned

        # Build a new dictionary with computed values
        computed_progress = {
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS: stored_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
                const.CUMULATIVE_BADGE_STATE_ACTIVE,
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE: baseline,
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS: cycle_points,
            # Highest earned badge
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: (
                highest_earned.get(const.DATA_BADGE_INTERNAL_ID)
                if highest_earned
                else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME: (
                highest_earned.get(const.DATA_BADGE_NAME) if highest_earned else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD: (
                float(
                    highest_earned.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                if highest_earned
                else None
            ),
            # Current badge in effect
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: (
                current_badge_info.get(const.DATA_BADGE_INTERNAL_ID)
                if current_badge_info
                else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME: (
                current_badge_info.get(const.DATA_BADGE_NAME)
                if current_badge_info
                else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD: (
                float(
                    current_badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                if current_badge_info
                else None
            ),
            # Next higher tier
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID: (
                next_higher.get(const.DATA_BADGE_INTERNAL_ID) if next_higher else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME: (
                next_higher.get(const.DATA_BADGE_NAME) if next_higher else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_THRESHOLD: (
                float(
                    next_higher.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                if next_higher
                else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED: (
                max(
                    0.0,
                    float(
                        next_higher.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                    - total_points,
                )
                if next_higher
                else None
            ),
            # Next lower tier
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID: (
                next_lower.get(const.DATA_BADGE_INTERNAL_ID) if next_lower else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME: (
                next_lower.get(const.DATA_BADGE_NAME) if next_lower else None
            ),
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_THRESHOLD: (
                float(next_lower.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0))
                if next_lower
                else None
            ),
        }

        # Merge computed values over stored progress
        stored_progress.update(computed_progress)  # type: ignore[typeddict-item]

        return cast("dict[str, Any]", stored_progress)

    def demote_cumulative_badge(self, kid_id: str) -> None:
        """Update cumulative badge status to DEMOTED when maintenance fails.

        Called when a cumulative badge's maintenance requirements are no longer met.
        The badge is not removed, but the kid's status is set to DEMOTED which
        affects their multiplier.

        Args:
            kid_id: Kid's internal ID
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.error(
                "Demote Cumulative Badge - Kid ID '%s' not found", kid_id
            )
            return

        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS)
        if not progress:
            const.LOGGER.debug(
                "Demote Cumulative Badge - No cumulative badge progress for kid '%s'",
                kid_id,
            )
            return

        # Only update if not already demoted
        current_status = progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.CUMULATIVE_BADGE_STATE_ACTIVE,
        )
        if current_status != const.CUMULATIVE_BADGE_STATE_DEMOTED:
            progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
                const.CUMULATIVE_BADGE_STATE_DEMOTED
            )

            # Recalculate multiplier immediately so the penalty takes effect
            self.update_point_multiplier_for_kid(kid_id)

            self.coordinator._persist()
            self.coordinator.async_set_updated_data(self.coordinator._data)

            kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
            const.LOGGER.info(
                "Demoted cumulative badge status for kid '%s' (%s)",
                kid_name,
                kid_id,
            )

    def remove_awarded_badges(
        self, kid_name: str | None = None, badge_name: str | None = None
    ) -> None:
        """Remove awarded badges based on provided kid_name and badge_name.

        This is the public API that accepts names and converts to IDs.

        Args:
            kid_name: Kid's display name (optional)
            badge_name: Badge's display name (optional)
        """
        # Convert kid_name to kid_id if provided
        kid_id: str | None = None
        if kid_name:
            kid_id = kh.get_entity_id_by_name(
                self.coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            if kid_id is None:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid name '%s' not found", kid_name
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_name,
                    },
                )

        # If badge_name is provided, try to find its corresponding badge_id
        badge_id: str | None = None
        if badge_name:
            badge_id = kh.get_entity_id_by_name(
                self.coordinator, const.ENTITY_TYPE_BADGE, badge_name
            )
            if not badge_id:
                # Badge isn't found, may have been deleted - clean up kid data only
                const.LOGGER.warning(
                    "Remove Awarded Badges - Badge name '%s' not found in badges_data. "
                    "Removing from kid data only",
                    badge_name,
                )
                # Remove badge name from specific kid or all kids
                if kid_id:
                    kid_info = self.coordinator.kids_data.get(kid_id)
                    if kid_info:
                        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
                        to_remove = [
                            bid
                            for bid, entry in badges_earned.items()
                            if entry.get(const.DATA_KID_BADGES_EARNED_NAME)
                            == badge_name
                        ]
                        for bid in to_remove:
                            del badges_earned[bid]
                else:
                    for kid_info in self.coordinator.kids_data.values():
                        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
                        to_remove = [
                            bid
                            for bid, entry in badges_earned.items()
                            if entry.get(const.DATA_KID_BADGES_EARNED_NAME)
                            == badge_name
                        ]
                        for bid in to_remove:
                            del badges_earned[bid]

                self.coordinator._persist()
                self.coordinator.async_set_updated_data(self.coordinator._data)
                return

        self.remove_awarded_badges_by_id(kid_id, badge_id)

    def remove_awarded_badges_by_id(
        self, kid_id: str | None = None, badge_id: str | None = None
    ) -> None:
        """Remove awarded badges based on provided kid_id and badge_id.

        This is the internal method that operates on IDs directly.

        Args:
            kid_id: Kid's internal ID (optional)
            badge_id: Badge's internal ID (optional)
        """
        const.LOGGER.info("Remove Awarded Badges - Starting removal process")
        found = False

        if badge_id and kid_id:
            # Reset a specific badge for a specific kid
            kid_info = self.coordinator.kids_data.get(kid_id)
            badge_info = self.coordinator.badges_data.get(badge_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if not badge_info:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Badge ID '%s' not found", badge_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_BADGE,
                        "name": badge_id,
                    },
                )
            badge_name = badge_info.get(const.DATA_BADGE_NAME, badge_id)
            kid_name_str = kid_info.get(const.DATA_KID_NAME, kid_id)
            badge_type = badge_info.get(const.DATA_BADGE_TYPE)

            # Remove the badge from the kid's badges_earned
            badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})
            if badge_id in badges_earned:
                found = True
                const.LOGGER.warning(
                    "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                    badge_name,
                    kid_name_str,
                )
                del badges_earned[badge_id]

            # Remove the kid from the badge earned_by list
            earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
            if kid_id in earned_by_list:
                earned_by_list.remove(kid_id)

            # Update multiplier if cumulative badge was removed
            if found and badge_type == const.BADGE_TYPE_CUMULATIVE:
                self.update_point_multiplier_for_kid(kid_id)

            if not found:
                const.LOGGER.warning(
                    "Remove Awarded Badges - Badge '%s' ('%s') not found in kid '%s' ('%s') data",
                    badge_id,
                    badge_name,
                    kid_id,
                    kid_name_str,
                )

        elif badge_id:
            # Remove a specific awarded badge for all kids
            badge_info_elif = self.coordinator.badges_data.get(badge_id)
            if not badge_info_elif:
                const.LOGGER.warning(
                    "Remove Awarded Badges - Badge ID '%s' not found in badges data",
                    badge_id,
                )
            else:
                badge_name = badge_info_elif.get(const.DATA_BADGE_NAME, badge_id)
                badge_type = badge_info_elif.get(const.DATA_BADGE_TYPE)
                kids_affected: list[str] = []
                for loop_kid_id, kid_info in self.coordinator.kids_data.items():
                    kid_name_str = kid_info.get(const.DATA_KID_NAME, "Unknown Kid")
                    badges_earned = kid_info.setdefault(
                        const.DATA_KID_BADGES_EARNED, {}
                    )
                    if badge_id in badges_earned:
                        found = True
                        kids_affected.append(loop_kid_id)
                        const.LOGGER.warning(
                            "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                            badge_name,
                            kid_name_str,
                        )
                        del badges_earned[badge_id]

                    # Remove the kid from the badge earned_by list
                    earned_by_list = badge_info_elif.get(const.DATA_BADGE_EARNED_BY, [])
                    if loop_kid_id in earned_by_list:
                        earned_by_list.remove(loop_kid_id)

                # Update multiplier for all affected kids if cumulative badge
                if badge_type == const.BADGE_TYPE_CUMULATIVE:
                    for affected_kid_id in kids_affected:
                        self.update_point_multiplier_for_kid(affected_kid_id)

                # Clear orphan earned_by references
                if const.DATA_BADGE_EARNED_BY in badge_info_elif:
                    badge_info_elif[const.DATA_BADGE_EARNED_BY].clear()

                if not found:
                    const.LOGGER.warning(
                        "Remove Awarded Badges - Badge '%s' ('%s') not found in any kid's data",
                        badge_id,
                        badge_name,
                    )

        elif kid_id:
            # Remove all awarded badges for a specific kid
            kid_info_elif = self.coordinator.kids_data.get(kid_id)
            if not kid_info_elif:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            kid_name_str = kid_info_elif.get(const.DATA_KID_NAME, "Unknown Kid")
            had_cumulative = False
            for loop_badge_id, badge_info in self.coordinator.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME, "")
                badge_type = badge_info.get(const.DATA_BADGE_TYPE)
                earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                badges_earned = kid_info_elif.setdefault(
                    const.DATA_KID_BADGES_EARNED, {}
                )
                if kid_id in earned_by_list:
                    found = True
                    if badge_type == const.BADGE_TYPE_CUMULATIVE:
                        had_cumulative = True
                    earned_by_list.remove(kid_id)
                    if loop_badge_id in badges_earned:
                        const.LOGGER.warning(
                            "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                            badge_name,
                            kid_name_str,
                        )
                        del badges_earned[loop_badge_id]

            # Clear orphan badges_earned
            if const.DATA_KID_BADGES_EARNED in kid_info_elif:
                kid_info_elif[const.DATA_KID_BADGES_EARNED].clear()

            # Update multiplier if any cumulative badges were removed
            if had_cumulative:
                self.update_point_multiplier_for_kid(kid_id)

            if not found:
                const.LOGGER.warning(
                    "Remove Awarded Badges - No badge found for kid '%s'",
                    kid_info_elif.get(const.DATA_KID_NAME, kid_id),
                )

        else:
            # Remove all awarded badges for all kids
            const.LOGGER.info(
                "Remove Awarded Badges - Removing all awarded badges for all kids"
            )
            kids_with_cumulative: set[str] = set()
            for loop_badge_id, badge_info in self.coordinator.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME, "")
                badge_type = badge_info.get(const.DATA_BADGE_TYPE)
                for loop_kid_id, kid_info in self.coordinator.kids_data.items():
                    kid_name_str = kid_info.get(const.DATA_KID_NAME, "Unknown Kid")
                    badges_earned = kid_info.setdefault(
                        const.DATA_KID_BADGES_EARNED, {}
                    )
                    if loop_badge_id in badges_earned:
                        found = True
                        if badge_type == const.BADGE_TYPE_CUMULATIVE:
                            kids_with_cumulative.add(loop_kid_id)
                        const.LOGGER.warning(
                            "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                            badge_name,
                            kid_name_str,
                        )
                        del badges_earned[loop_badge_id]

                    # Remove the kid from the badge earned_by list
                    earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                    if loop_kid_id in earned_by_list:
                        earned_by_list.remove(loop_kid_id)

                    # Clear orphan badges_earned
                    if const.DATA_KID_BADGES_EARNED in kid_info:
                        kid_info[const.DATA_KID_BADGES_EARNED].clear()

                # Clear orphan earned_by references
                if const.DATA_BADGE_EARNED_BY in badge_info:
                    badge_info[const.DATA_BADGE_EARNED_BY].clear()

            # Update multiplier for all kids who had cumulative badges removed
            for affected_kid_id in kids_with_cumulative:
                self.update_point_multiplier_for_kid(affected_kid_id)

            if not found:
                const.LOGGER.warning(
                    "Remove Awarded Badges - No awarded badges found in any kid's data"
                )

        const.LOGGER.info("Remove Awarded Badges - Badge removal process completed")
        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    # =========================================================================
    # BADGE AWARDING AND PROGRESS SYNC (State-Modifying Methods)
    # =========================================================================

    async def award_badge(self, kid_id: str, badge_id: str) -> None:
        """Add the badge to kid's 'earned_by' and kid's 'badges' list.

        Handles all aspects of badge awarding:
        - Updates badge earned_by list and kid's badges_earned
        - Processes award items (points, rewards, bonuses, multipliers)
        - Sends notifications to kid and parents
        - Persists changes

        Args:
            kid_id: The kid's internal UUID
            badge_id: The badge's internal UUID
        """
        badge_info: BadgeData | None = self.coordinator.badges_data.get(badge_id)
        kid_info: KidData = cast("KidData", self.coordinator.kids_data.get(kid_id, {}))
        if not kid_info:
            const.LOGGER.error("Award Badge - Kid ID '%s' not found.", kid_id)
            return
        if not badge_info:
            const.LOGGER.error(
                "ERROR: Award Badge - Badge ID '%s' not found. "
                "Cannot be awarded to Kid ID '%s'",
                badge_id,
                kid_id,
            )
            return

        badge_type = badge_info.get(const.DATA_BADGE_TYPE, const.BADGE_TYPE_CUMULATIVE)
        badge_name = badge_info.get(const.DATA_BADGE_NAME)
        kid_name = kid_info[const.DATA_KID_NAME]

        # Award the badge (for all types, including special occasion).
        const.LOGGER.info(
            "INFO: Award Badge - Awarding badge '%s' (%s) to kid '%s' (%s).",
            badge_id,
            badge_name,
            kid_id,
            kid_name,
        )
        earned_by_list = badge_info.setdefault(const.DATA_BADGE_EARNED_BY, [])
        if kid_id not in earned_by_list:
            earned_by_list.append(kid_id)
        self.update_badges_earned_for_kid(kid_id, badge_id)

        # --- Unified Award Items Logic ---
        award_data = badge_info.get(const.DATA_BADGE_AWARDS, {})
        award_items = award_data.get(const.DATA_BADGE_AWARDS_AWARD_ITEMS, [])
        points_awarded = award_data.get(
            const.DATA_BADGE_AWARDS_AWARD_POINTS, const.DEFAULT_ZERO
        )
        multiplier = award_data.get(
            const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
            const.DEFAULT_KID_POINTS_MULTIPLIER,
        )

        # Process award_items using helper
        to_award, _ = self.process_award_items(
            award_items,
            self.coordinator.rewards_data,
            self.coordinator.bonuses_data,
            self.coordinator.penalties_data,
        )

        # 1. Points - handled by EconomyManager via BADGE_EARNED event
        # (deposit call removed in Phase 7.2 - event-driven awards)
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS)
            for item in award_items
        ):
            if points_awarded > const.DEFAULT_ZERO:
                const.LOGGER.info(
                    "INFO: Award Badge - Points: %s for kid '%s' (via event).",
                    points_awarded,
                    kid_name,
                )

        # 2. Multiplier (only for cumulative badges)
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS_MULTIPLIER)
            for item in award_items
        ):
            multiplier_float = float(cast("float", multiplier))
            if multiplier_float > const.DEFAULT_ZERO:
                kid_info[const.DATA_KID_POINTS_MULTIPLIER] = multiplier_float
                const.LOGGER.info(
                    "INFO: Award Badge - Set points multiplier to %.2f for kid '%s'.",
                    multiplier_float,
                    kid_name,
                )
            else:
                kid_info[const.DATA_KID_POINTS_MULTIPLIER] = (
                    const.DEFAULT_POINTS_MULTIPLIER
                )

        # 3. Rewards (multiple) - Badge awards grant rewards directly
        for reward_id in to_award.get(const.AWARD_ITEMS_KEY_REWARDS, []):
            if reward_id in self.coordinator.rewards_data:
                # Use RewardManager helper with cost=0 (free grant from badge)
                self.coordinator.reward_manager._grant_to_kid(
                    kid_id=kid_id,
                    reward_id=reward_id,
                    cost_deducted=const.DEFAULT_ZERO,  # Badge grants are free
                    notif_id=None,
                    is_pending_claim=False,
                )
                const.LOGGER.info(
                    "INFO: Award Badge - Granted reward '%s' to kid '%s'.",
                    self.coordinator.rewards_data[reward_id].get(
                        const.DATA_REWARD_NAME, reward_id
                    ),
                    kid_name,
                )

        # 4. Bonuses (multiple)
        for bonus_id in to_award.get(const.AWARD_ITEMS_KEY_BONUSES, []):
            if bonus_id in self.coordinator.bonuses_data:
                await self.coordinator.economy_manager.apply_bonus(
                    kid_name, kid_id, bonus_id
                )

        # --- Notification ---
        message = f"You earned a new badge: '{badge_name}'!"
        if to_award.get(const.AWARD_ITEMS_KEY_REWARDS):
            reward_names = [
                self.coordinator.rewards_data[rid].get(const.DATA_REWARD_NAME, rid)
                for rid in to_award[const.AWARD_ITEMS_KEY_REWARDS]
            ]
            message += f" Rewards: {', '.join(reward_names)}."
        if to_award.get(const.AWARD_ITEMS_KEY_BONUSES):
            bonus_names = [
                self.coordinator.bonuses_data[bid].get(const.DATA_BONUS_NAME, bid)
                for bid in to_award[const.AWARD_ITEMS_KEY_BONUSES]
            ]
            message += f" Bonuses: {', '.join(bonus_names)}."
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS)
            for item in award_items
        ):
            message += f" Points: {points_awarded}."
        if badge_type == const.BADGE_TYPE_CUMULATIVE and any(
            item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS_MULTIPLIER)
            for item in award_items
        ):
            message += f" Multiplier: {multiplier}x."

        parent_message = f"'{kid_name}' earned a new badge: '{badge_name}'."
        if to_award.get(const.AWARD_ITEMS_KEY_REWARDS):
            reward_names = [
                self.coordinator.rewards_data[rid].get(const.DATA_REWARD_NAME, rid)
                for rid in to_award[const.AWARD_ITEMS_KEY_REWARDS]
            ]
            parent_message += f" Rewards: {', '.join(reward_names)}."
        if to_award.get(const.AWARD_ITEMS_KEY_BONUSES):
            bonus_names = [
                self.coordinator.bonuses_data[bid].get(const.DATA_BONUS_NAME, bid)
                for bid in to_award[const.AWARD_ITEMS_KEY_BONUSES]
            ]
            parent_message += f" Bonuses: {', '.join(bonus_names)}."
        if any(
            item == const.AWARD_ITEMS_KEY_POINTS
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS)
            for item in award_items
        ):
            parent_message += f" Points: {points_awarded}."
        if badge_type == const.BADGE_TYPE_CUMULATIVE and any(
            item == const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER
            or item.startswith(const.AWARD_ITEMS_PREFIX_POINTS_MULTIPLIER)
            for item in award_items
        ):
            parent_message += f" Multiplier: {multiplier}x."

        # NOTE: message and parent_message are built but not used in translated notifications
        # They exist for potential future use with non-translated notifications
        # The BADGE_EARNED event was already emitted by the caller (_check_badge_for_kid)
        # We just persist here
        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)
        # NOTE: Recursive badge checks removed - GamificationManager handles evaluation

    def sync_badge_progress_for_kid(self, kid_id: str) -> None:
        """Sync badge progress for a specific kid.

        Initializes badge progress for new badges and updates existing progress
        for configuration changes. Handles all non-cumulative badge types.

        This method does NOT persist - caller is responsible for persistence.

        Args:
            kid_id: The kid's internal UUID
        """
        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        # Phase 4: Clean up badge_progress for badges no longer assigned to this kid
        if const.DATA_KID_BADGE_PROGRESS in kid_info:
            badges_to_remove = []
            for progress_badge_id in kid_info[const.DATA_KID_BADGE_PROGRESS]:
                badge_info: BadgeData | None = self.coordinator.badges_data.get(
                    progress_badge_id
                )
                # Remove if badge deleted OR kid not in assigned_to list
                if not badge_info or kid_id not in badge_info.get(
                    const.DATA_BADGE_ASSIGNED_TO, []
                ):
                    badges_to_remove.append(progress_badge_id)

            for badge_id in badges_to_remove:
                del kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id]
                const.LOGGER.debug(
                    "DEBUG: Removed badge_progress for badge '%s' from kid '%s' "
                    "(unassigned or deleted)",
                    badge_id,
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

        for badge_id, badge_info in self.coordinator.badges_data.items():
            # Feature Change v4.2: Badges now require explicit assignment.
            # Empty assigned_to means badge is not assigned to any kid.
            assigned_to_list = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            is_assigned_to = kid_id in assigned_to_list
            if not is_assigned_to:
                continue

            # Skip cumulative badges (handled separately)
            if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE:
                continue

            # Initialize progress structure if it doesn't exist
            if const.DATA_KID_BADGE_PROGRESS not in kid_info:
                kid_info[const.DATA_KID_BADGE_PROGRESS] = {}

            badge_type = badge_info.get(const.DATA_BADGE_TYPE)

            # --- Set flags based on badge type ---
            has_target = badge_type in const.INCLUDE_TARGET_BADGE_TYPES
            has_special_occasion = (
                badge_type in const.INCLUDE_SPECIAL_OCCASION_BADGE_TYPES
            )
            has_achievement_linked = (
                badge_type in const.INCLUDE_ACHIEVEMENT_LINKED_BADGE_TYPES
            )
            has_challenge_linked = (
                badge_type in const.INCLUDE_CHALLENGE_LINKED_BADGE_TYPES
            )
            has_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES
            has_assigned_to = badge_type in const.INCLUDE_ASSIGNED_TO_BADGE_TYPES
            has_reset_schedule = badge_type in const.INCLUDE_RESET_SCHEDULE_BADGE_TYPES

            # ===============================================================
            # SECTION 1: NEW BADGE SETUP - Create initial progress structure
            # ===============================================================
            badge_progress_dict = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
            if badge_id not in badge_progress_dict:
                # --- Common fields ---
                progress: dict[str, Any] = {
                    const.DATA_KID_BADGE_PROGRESS_NAME: badge_info.get(
                        const.DATA_BADGE_NAME
                    ),
                    const.DATA_KID_BADGE_PROGRESS_TYPE: badge_type,
                    const.DATA_KID_BADGE_PROGRESS_STATUS: const.BADGE_STATE_IN_PROGRESS,
                }

                # --- Target fields ---
                if has_target:
                    target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_TYPE
                    )
                    threshold_value = float(
                        badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE] = target_type
                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE] = (
                        threshold_value
                    )

                    # Initialize all possible progress fields to their defaults
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0.0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED, {}
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED, {}
                    )

                # --- Achievement Linked fields ---
                if has_achievement_linked:
                    achievement_id = badge_info.get(
                        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                    )
                    if achievement_id:
                        progress[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = (
                            achievement_id
                        )

                # --- Challenge Linked fields ---
                if has_challenge_linked:
                    challenge_id = badge_info.get(const.DATA_BADGE_ASSOCIATED_CHALLENGE)
                    if challenge_id:
                        progress[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = challenge_id

                # --- Tracked Chores fields ---
                if has_tracked_chores and not has_special_occasion:
                    progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = (
                        self.get_badge_in_scope_chores_list(badge_info, kid_id)
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress[const.DATA_BADGE_ASSIGNED_TO] = assigned_to

                # --- Reset Schedule fields ---
                if has_reset_schedule:
                    reset_schedule = badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
                    recurring_frequency = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        const.FREQUENCY_NONE,
                    )
                    start_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_START_DATE
                    )
                    end_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_END_DATE
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY] = (
                        recurring_frequency
                    )

                    # Set initial schedule if there is a frequency and no end date
                    if recurring_frequency != const.FREQUENCY_NONE:
                        if end_date_iso:
                            progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                                start_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                                end_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
                                const.DEFAULT_ZERO
                            )
                        else:
                            # Calculate initial end date from today
                            today_local_iso = dt_today_iso()
                            is_daily = recurring_frequency == const.FREQUENCY_DAILY
                            is_custom_1_day = (
                                recurring_frequency == const.FREQUENCY_CUSTOM
                                and reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                                )
                                == 1
                                and reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                                )
                                == const.TIME_UNIT_DAYS
                            )

                            if is_daily or is_custom_1_day:
                                # Special case: daily badge uses today as end date
                                new_end_date_iso: str | date | None = today_local_iso
                            elif recurring_frequency == const.FREQUENCY_CUSTOM:
                                # Handle other custom frequencies
                                custom_interval = reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                                )
                                custom_interval_unit = reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                                )
                                if custom_interval and custom_interval_unit:
                                    new_end_date_iso = dt_add_interval(
                                        today_local_iso,
                                        interval_unit=custom_interval_unit,
                                        delta=custom_interval,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                                else:
                                    # Default fallback to weekly
                                    new_end_date_iso = dt_add_interval(
                                        today_local_iso,
                                        interval_unit=const.TIME_UNIT_WEEKS,
                                        delta=1,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                            else:
                                # Use standard frequency helper
                                new_end_date_iso = dt_next_schedule(
                                    today_local_iso,
                                    interval_type=recurring_frequency,
                                    require_future=True,
                                    return_type=const.HELPER_RETURN_ISO_DATE,
                                )

                            progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                                start_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                                new_end_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
                                const.DEFAULT_ZERO
                            )

                            # Set penalty applied to False
                            progress[const.DATA_KID_BADGE_PROGRESS_PENALTY_APPLIED] = (
                                False
                            )

                # --- Special Occasion fields ---
                if has_special_occasion:
                    occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE)
                    if occasion_type:
                        progress[const.DATA_BADGE_OCCASION_TYPE] = occasion_type

                # Store the progress data
                kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id] = cast(  # pyright: ignore[reportTypedDictNotRequiredAccess]
                    "KidBadgeProgress", progress
                )

            # ===============================================================
            # SECTION 2: BADGE SYNC - Update existing badge progress data
            # ===============================================================
            else:
                # Remove badge progress if badge no longer available or not assigned
                if badge_id not in self.coordinator.badges_data or (
                    badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    and kid_id not in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                ):
                    if badge_id in badge_progress_dict:
                        del badge_progress_dict[badge_id]
                        const.LOGGER.info(
                            "INFO: Badge Maintenance - Removed badge progress for "
                            "badge '%s' from kid '%s' (badge deleted or unassigned).",
                            badge_id,
                            kid_info.get(const.DATA_KID_NAME, kid_id),
                        )
                    continue

                # The badge already exists in progress data - sync configuration fields
                progress_sync: dict[str, Any] = cast(
                    "dict[str, Any]", badge_progress_dict[badge_id]
                )

                # --- Common fields ---
                progress_sync[const.DATA_KID_BADGE_PROGRESS_NAME] = badge_info.get(
                    const.DATA_BADGE_NAME, "Unknown Badge"
                )
                progress_sync[const.DATA_KID_BADGE_PROGRESS_TYPE] = badge_type

                # --- Target fields ---
                if has_target:
                    target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_TYPE,
                        const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                    )
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE] = (
                        target_type
                    )

                    progress_sync[
                        const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE
                    ] = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )

                # --- Special Occasion fields ---
                if has_special_occasion:
                    occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE)
                    if occasion_type:
                        progress_sync[const.DATA_BADGE_OCCASION_TYPE] = occasion_type

                # --- Achievement Linked fields ---
                if has_achievement_linked:
                    achievement_id = badge_info.get(
                        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                    )
                    if achievement_id:
                        progress_sync[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = (
                            achievement_id
                        )

                # --- Challenge Linked fields ---
                if has_challenge_linked:
                    challenge_id = badge_info.get(const.DATA_BADGE_ASSOCIATED_CHALLENGE)
                    if challenge_id:
                        progress_sync[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = (
                            challenge_id
                        )

                # --- Tracked Chores fields ---
                if has_tracked_chores and not has_special_occasion:
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = (
                        self.get_badge_in_scope_chores_list(badge_info, kid_id)
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress_sync[const.DATA_BADGE_ASSIGNED_TO] = assigned_to

                # --- Reset Schedule fields ---
                if has_reset_schedule:
                    reset_schedule = badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
                    recurring_frequency = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        const.FREQUENCY_NONE,
                    )
                    start_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_START_DATE
                    )
                    end_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_END_DATE
                    )
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY] = (
                        recurring_frequency
                    )
                    # Only update start and end dates if they have values
                    if start_date_iso:
                        progress_sync[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                            start_date_iso
                        )
                    if end_date_iso:
                        progress_sync[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                            end_date_iso
                        )
