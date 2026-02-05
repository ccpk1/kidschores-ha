# Gamification System Next-Generation Refactor Plan

## Initiative snapshot

- **Name / Code**: Gamification NextGen / GAME-NG
- **Target release / milestone**: v0.5.0 (schema v43)
- **Owner / driver(s)**: KidsChores Team
- **Status**: Not started

## Summary & immediate steps

| Phase / Step              | Description                                              | % complete | Quick notes                                  |
| ------------------------- | -------------------------------------------------------- | ---------- | -------------------------------------------- |
| Phase 1 – Data Refactor   | Separate State vs Definition in storage                  | 0%         | Schema v43, migration required               |
| Phase 2 – Engine Rewrite  | Pure evaluation logic for promotion/demotion/maintenance | 0%         | New `cumulative_badge_engine.py` in engines/ |
| Phase 3 – Manager Rework  | Event-driven orchestration with Statistics as truth      | 0%         | Leverage existing signal infrastructure      |
| Phase 4 – Multiplier Flow | Signal-based multiplier updates via EconomyManager       | 0%         | Partially exists, needs completion           |
| Phase 5 – Testing Suite   | Comprehensive unit tests for all badge state transitions | 0%         | Use Stårblüm Family scenarios                |

1. **Key objective**: Transform cumulative badges into a clean, performant state machine driven by StatisticsEngine as the single source of truth for lifetime points, eliminating stale denormalized data and reducing storage bloat.

2. **Summary of recent work**:
   - Analysis of current 3277-line GamificationManager identified state/definition mixing
   - Identified StatisticsEngine as existing truth source for lifetime points
   - Mapped current signal infrastructure (POINTS_CHANGED, MIDNIGHT_ROLLOVER)
   - Documented current data anti-patterns in `cumulative_badge_progress`

3. **Next steps (short term)**:
   - Design lean `KidCumulativeBadgeProgress` TypedDict (state-only)
   - Create `CumulativeBadgeEngine` pure logic class
   - Write migration for schema v43

4. **Risks / blockers**:
   - Migration complexity for existing users with badge data
   - Dashboard helper sensor depends on current data structure
   - Backward compatibility with existing automations

5. **References**:
   - [ARCHITECTURE.md § Layered Architecture](../ARCHITECTURE.md)
   - [DEVELOPMENT_STANDARDS.md § Event-Driven Communication](../DEVELOPMENT_STANDARDS.md)
   - [type_defs.py lines 385-418](../../custom_components/kidschores/type_defs.py)
   - [gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
   - [statistics_engine.py](../../custom_components/kidschores/engines/statistics_engine.py)

6. **Decisions & completion check**:
   - **Decisions captured**:
     - [ ] Lifetime Points (`point_periods.all_time.all_time.earned`) is single source of truth
     - [ ] Maintenance tracking uses `maintenance_points` (not `cycle_points`)
     - [ ] Relative position (`next_higher_*`, `next_lower_*`) calculated on-demand, not stored
     - [ ] Grace period state (`grace`) is intermediate between `active` and `demoted`
     - [ ] Schema version v43
     - [ ] Badge period tracking already implemented via Landlord/Tenant pattern (Phase 4B)
     - [ ] Badge earning streaks are future work (separate follow-up plan)
     - [ ] Tenants (StatisticsManager) NEVER emit signals - only update period data
   - **Completion confirmation**: `[ ]` All follow-up items completed before marking done

---

## Current State Analysis

### Problem Statement

The existing `cumulative_badge_progress` structure (stored per-kid) **mixes state with definition**:

```python
# CURRENT (Anti-Pattern) - from kidschores_data storage
"cumulative_badge_progress": {
    # STATE (should keep)
    "current_badge_id": "2ad673de-...",
    "status": "demoted",
    "cycle_points": 1506.0,
    "baseline": 0.0,

    # DENORMALIZED DEFINITION (should NOT store - stale risk)
    "current_badge_name": "Bronze",         # ❌ Stale if badge renamed
    "current_threshold": 500.0,             # ❌ Stale if threshold changed
    "next_higher_badge_id": "016aacf9-...", # ❌ Stale if badges reordered
    "next_higher_badge_name": "Silver",     # ❌ Stale if badge renamed
    "next_higher_threshold": 2500.0,        # ❌ Stale if threshold changed
    "next_higher_points_needed": 996.0,     # ❌ Calculated, don't store
    "next_lower_badge_id": null,            # ❌ Stale if badges inserted
    ...
}
```

**Impact**: If admin changes a badge threshold in config, stored data becomes stale immediately. The UI may show incorrect "points needed" until a recalculation is triggered.

### Current Architecture Mapping

| Component           | File                               | Lines | Responsibility                            |
| ------------------- | ---------------------------------- | ----- | ----------------------------------------- |
| GamificationManager | `managers/gamification_manager.py` | 3277  | Badge/achievement/challenge orchestration |
| GamificationEngine  | `engines/gamification_engine.py`   | 1098  | Pure criterion evaluation logic           |
| StatisticsManager   | `managers/statistics_manager.py`   | 2028  | Event-driven period stats                 |
| StatisticsEngine    | `engines/statistics_engine.py`     | 812   | Period key generation, transactions       |
| EconomyManager      | `managers/economy_manager.py`      | ~1500 | Point transactions, multipliers           |

### Key Existing Infrastructure

**Signals (already in place)**:

- `SIGNAL_SUFFIX_POINTS_CHANGED` - Emitted by EconomyManager on deposit/withdraw
- `SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER` - Emitted by SystemManager at midnight
- `SIGNAL_SUFFIX_BADGE_EARNED` - Emitted with Award Manifest (points, multiplier, rewards)
- `SIGNAL_SUFFIX_BADGE_UPDATED` - Emitted on status change
- `SIGNAL_SUFFIX_POINTS_MULTIPLIER_CHANGE_REQUESTED` - Phase 3B pattern

**Statistics Source of Truth** (StatisticsEngine):

```python
# Lifetime earned points (never decreases)
point_periods["all_time"]["all_time"]["earned"]

# This is THE metric for cumulative badge evaluation
```

---

## Detailed Phase Tracking

### Phase 1 – Data Structure Refactor

- **Goal**: Define lean storage structure that separates state from computed/definition data.

- **Steps / detailed work items**:
  1. - [ ] Design new `KidCumulativeBadgeProgress` TypedDict (state-only):

     ```python
     class KidCumulativeBadgeProgress(TypedDict, total=False):
         # IDENTITY (stored)
         current_badge_id: str | None      # Effective badge (may be lower if demoted)
         highest_earned_badge_id: str | None  # High water mark

         # STATUS (stored)
         status: str  # 'active' | 'grace' | 'demoted'

         # MAINTENANCE TRACKING (stored)
         maintenance_points: float  # Points earned in current maintenance window
         period_end: str | None     # ISO date: next maintenance check
         grace_end: str | None      # ISO date: grace period expiration

         # REMOVED - computed on-demand:
         # - current_badge_name, current_threshold
         # - next_higher_*, next_lower_*
         # - cycle_points (renamed to maintenance_points)
         # - baseline (use lifetime points directly)
     ```

  2. - [ ] Add new constants to `const.py`:
     - `DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_POINTS`
     - `DATA_KID_CUMULATIVE_BADGE_PROGRESS_PERIOD_END`
     - `DATA_KID_CUMULATIVE_BADGE_PROGRESS_GRACE_END`
     - `CUMULATIVE_BADGE_STATE_GRACE = "grace"` (already exists)

  3. - [ ] Create migration function `migrate_cumulative_badge_to_v44()`:
     - Rename `cycle_points` → `maintenance_points`
     - Rename `maintenance_end_date` → `period_end`
     - Rename `maintenance_grace_end_date` → `grace_end`
     - Remove denormalized fields (`*_name`, `*_threshold`, `*_points_needed`)
     - Remove `baseline` (no longer needed - use lifetime points)
     - File: `migration_pre_v50.py`

  4. - [ ] Update schema version: `SCHEMA_VERSION_STORAGE_ONLY = 44`

- **Key issues**:
  - Dashboard helper sensor (`sensor.kc_<kid>_ui_dashboard_helper`) reads denormalized fields
  - Must update UIManager to compute these fields on-the-fly for dashboard

---

### Phase 2 – Engine Rewrite (Cumulative Badge Logic)

- **Goal**: Create pure evaluation logic for cumulative badges separate from GamificationEngine.

- **Steps / detailed work items**:
  1. - [ ] Create `engines/cumulative_badge_engine.py` (~200 lines):

     ```python
     class CumulativeBadgeEngine:
         """Pure logic for cumulative badge evaluation.

         Stateless - operates on passed data only.
         """

         @staticmethod
         def get_ladder_context(
             current_badge_id: str | None,
             all_badges: dict[str, BadgeData],
             kid_lifetime_points: float,
         ) -> LadderContext:
             """Compute relative position on badge ladder.

             Returns:
                 LadderContext with current, next_higher, next_lower, points_to_next
             """
             ...

         @staticmethod
         def evaluate_rank(
             kid_lifetime_points: float,
             all_badges: dict[str, BadgeData],
             kid_id: str,
         ) -> str | None:
             """Determine which badge ID kid qualifies for based on points.

             Pure function - no side effects.
             """
             # Filter to cumulative, sort by threshold descending
             # Return highest badge where points >= threshold
             ...

         @staticmethod
         def check_promotion(
             current_badge_id: str | None,
             target_badge_id: str | None,
             all_badges: dict[str, BadgeData],
         ) -> PromotionResult | None:
             """Check if kid should be promoted.

             Returns PromotionResult if moving UP the ladder.
             """
             ...

         @staticmethod
         def process_maintenance_interval(
             progress: KidCumulativeBadgeProgress,
             badge_config: BadgeData,
             today: date,
         ) -> MaintenanceResult | None:
             """Evaluate maintenance period completion.

             Called on MIDNIGHT_ROLLOVER.
             Returns action: 'maintain_success' | 'enter_grace' | 'demote' | None
             """
             ...
     ```

  2. - [ ] Define result TypedDicts in `type_defs.py`:

     ```python
     class LadderContext(TypedDict):
         current: BadgeData | None
         next_higher: BadgeData | None
         next_lower: BadgeData | None
         points_to_next: float | None
         points_above_current: float

     class PromotionResult(TypedDict):
         action: str  # 'promote'
         new_badge_id: str
         reset_maintenance: bool

     class MaintenanceResult(TypedDict):
         action: str  # 'maintain_success' | 'enter_grace' | 'demote'
         new_period_end: str | None
         grace_end: str | None
     ```

  3. - [ ] Add unit tests for engine (`tests/test_cumulative_badge_engine.py`):
     - Test ladder context computation with various badge configurations
     - Test rank evaluation with edge cases (no badges, single badge, kid not assigned)
     - Test promotion detection
     - Test maintenance pass/fail/grace scenarios

- **Key issues**:
  - Must handle badge assignment filtering (kid only qualifies for assigned badges)
  - Edge case: what if all cumulative badges are deleted?

---

### Phase 3 – Manager Rework (Event-Driven Orchestration)

- **Goal**: Refactor GamificationManager to use engine + signals instead of inline logic.

- **Steps / detailed work items**:
  1. - [ ] Refactor `_on_points_changed()` handler:

     ```python
     def _on_points_changed(self, payload: dict[str, Any]) -> None:
         # Skip gamification-originated sources (existing)

         # NEW: Only track maintenance_points, don't recompute full progress
         if delta > 0 and kid_id:
             kid_info = self.coordinator.kids_data.get(kid_id)
             if kid_info:
                 progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
                 maint_pts = progress.get("maintenance_points", 0.0)
                 progress["maintenance_points"] = maint_pts + delta

         # NEW: Check for promotion using engine
         await self._check_cumulative_promotion(kid_id)
     ```

  2. - [ ] Create `_check_cumulative_promotion()` method:

     ```python
     async def _check_cumulative_promotion(self, kid_id: str) -> None:
         """Check if kid should be promoted based on lifetime points."""
         kid_info = self.coordinator.kids_data.get(kid_id)
         lifetime_points = self._get_lifetime_points(kid_id)

         progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
         current_badge_id = progress.get("current_badge_id")

         # Use engine to determine target badge
         target_badge_id = CumulativeBadgeEngine.evaluate_rank(
             lifetime_points,
             self.coordinator.badges_data,
             kid_id,
         )

         # Check if this is a promotion
         result = CumulativeBadgeEngine.check_promotion(
             current_badge_id,
             target_badge_id,
             self.coordinator.badges_data,
         )

         if result:
             await self._apply_promotion(kid_id, result)
     ```

  3. - [ ] Create `_on_midnight_rollover()` handler for maintenance checks:

     ```python
     def _on_midnight_rollover(self, payload: dict[str, Any]) -> None:
         """Process maintenance intervals for all kids."""
         today = date.today()

         for kid_id, kid_info in self.coordinator.kids_data.items():
             progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
             current_badge_id = progress.get("current_badge_id")

             if not current_badge_id:
                 continue

             badge_config = self.coordinator.badges_data.get(current_badge_id)
             if not badge_config:
                 continue

             result = CumulativeBadgeEngine.process_maintenance_interval(
                 progress, badge_config, today
             )

             if result:
                 await self._apply_maintenance_result(kid_id, result)
     ```

  4. - [ ] Refactor `get_cumulative_badge_progress()` to compute on-demand:

     ```python
     def get_cumulative_badge_progress(self, kid_id: str) -> dict[str, Any]:
         """Build full progress block with computed fields for UI."""
         kid_info = self.coordinator.kids_data.get(kid_id)
         if not kid_info:
             return {}

         # Get stored state (lean)
         stored = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
         lifetime_points = self._get_lifetime_points(kid_id)

         # Compute ladder context using engine
         context = CumulativeBadgeEngine.get_ladder_context(
             stored.get("current_badge_id"),
             self.coordinator.badges_data,
             lifetime_points,
         )

         # Build full response for UI (NOT stored)
         return {
             **stored,  # State fields
             # Computed fields (fresh, never stale)
             "current_badge_name": context["current"]["name"] if context["current"] else None,
             "current_threshold": context["current"]["threshold"] if context["current"] else None,
             "next_higher_badge_id": context["next_higher"]["id"] if context["next_higher"] else None,
             "next_higher_badge_name": context["next_higher"]["name"] if context["next_higher"] else None,
             "next_higher_threshold": context["next_higher"]["threshold"] if context["next_higher"] else None,
             "next_higher_points_needed": context["points_to_next"],
             "next_lower_badge_id": context["next_lower"]["id"] if context["next_lower"] else None,
             "next_lower_badge_name": context["next_lower"]["name"] if context["next_lower"] else None,
             "next_lower_threshold": context["next_lower"]["threshold"] if context["next_lower"] else None,
             "lifetime_points": lifetime_points,
         }
     ```

  5. - [ ] Add helper method `_get_lifetime_points()`:

     ```python
     def _get_lifetime_points(self, kid_id: str) -> float:
         """Get lifetime earned points from StatisticsEngine.

         This is the SINGLE SOURCE OF TRUTH for cumulative badge evaluation.
         """
         kid_info = self.coordinator.kids_data.get(kid_id)
         if not kid_info:
             return 0.0

         point_periods = kid_info.get(const.DATA_KID_POINT_PERIODS, {})
         all_time = point_periods.get("all_time", {}).get("all_time", {})
         return float(all_time.get(const.DATA_KID_POINT_PERIOD_POINTS_EARNED, 0.0))
     ```

  6. - [ ] Subscribe to MIDNIGHT_ROLLOVER signal in `async_setup()`:
     ```python
     self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)
     ```

- **Key issues**:
  - `get_cumulative_badge_progress()` is called by UIManager for dashboard helper
  - Must ensure computed fields match current field names for backward compatibility

---

### Phase 4 – Multiplier Flow (Signal-Based)

- **Goal**: Ensure multiplier updates flow correctly through EconomyManager.

- **Steps / detailed work items**:
  1. - [ ] Audit existing `SIGNAL_SUFFIX_POINTS_MULTIPLIER_CHANGE_REQUESTED` usage:
     - Emitted in: `update_point_multiplier_for_kid()`
     - Listened by: EconomyManager (verify)

  2. - [ ] Ensure promotion triggers multiplier update:

     ```python
     async def _apply_promotion(self, kid_id: str, result: PromotionResult) -> None:
         """Apply badge promotion."""
         kid_info = self.coordinator.kids_data.get(kid_id)
         progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})

         # Update state
         progress["current_badge_id"] = result["new_badge_id"]
         progress["highest_earned_badge_id"] = result["new_badge_id"]
         progress["status"] = const.CUMULATIVE_BADGE_STATE_ACTIVE

         if result["reset_maintenance"]:
             progress["maintenance_points"] = 0.0
             progress["period_end"] = self._calculate_next_period_end(result["new_badge_id"])

         # Persist
         self.coordinator._persist()

         # Update multiplier via signal (Phase 3B pattern)
         self.update_point_multiplier_for_kid(kid_id)

         # Emit BADGE_EARNED with Award Manifest
         badge_data = self.coordinator.badges_data.get(result["new_badge_id"])
         if badge_data:
             # Build and emit Award Manifest (existing pattern)
             ...
     ```

  3. - [ ] Ensure demotion reduces multiplier:

     ```python
     async def _apply_maintenance_result(self, kid_id: str, result: MaintenanceResult) -> None:
         """Apply maintenance check result."""
         progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})

         if result["action"] == "maintain_success":
             progress["maintenance_points"] = 0.0
             progress["period_end"] = result["new_period_end"]
             progress["grace_end"] = None
             # Award maintenance bonus if configured
             ...

         elif result["action"] == "enter_grace":
             progress["status"] = const.CUMULATIVE_BADGE_STATE_GRACE
             progress["grace_end"] = result["grace_end"]
             # Notify kid of grace period
             ...

         elif result["action"] == "demote":
             progress["status"] = const.CUMULATIVE_BADGE_STATE_DEMOTED
             # current_badge_id stays at highest_earned (visual)
             # BUT effective multiplier drops to next_lower
             self.update_point_multiplier_for_kid(kid_id)
             # Notify kid of demotion
             ...

         self.coordinator._persist()
     ```

  4. - [ ] Verify `update_point_multiplier_for_kid()` handles demoted state:
     - Current badge for multiplier = `next_lower_badge` if `status == 'demoted'`
     - File: [gamification_manager.py#L1400-1425](../../custom_components/kidschores/managers/gamification_manager.py)

- **Key issues**:
  - Need to ensure demoted kids get lower tier multiplier
  - Dashboard should show "Demoted" visual indicator

---

### Phase 5 – Testing Suite

- **Goal**: Comprehensive test coverage for all badge state transitions.

- **Steps / detailed work items**:
  1. - [ ] Create `tests/test_cumulative_badge_engine.py`:
     - `test_ladder_context_single_badge`
     - `test_ladder_context_multiple_badges`
     - `test_ladder_context_no_badges`
     - `test_ladder_context_kid_not_assigned`
     - `test_evaluate_rank_qualifies_highest`
     - `test_evaluate_rank_qualifies_middle`
     - `test_evaluate_rank_qualifies_none`
     - `test_check_promotion_moving_up`
     - `test_check_promotion_no_change`
     - `test_maintenance_pass`
     - `test_maintenance_fail_enter_grace`
     - `test_maintenance_fail_in_grace_demote`
     - `test_maintenance_grace_recovery`

  2. - [ ] Create `tests/test_cumulative_badge_integration.py`:
     - `test_points_trigger_promotion` (service-based)
     - `test_midnight_triggers_maintenance` (service-based)
     - `test_demotion_reduces_multiplier` (service-based)
     - `test_promotion_awards_badge_rewards` (service-based)
     - Use Stårblüm Family scenarios (medium or full)

  3. - [ ] Update existing tests for new data structure:
     - `tests/test_gamification_manager.py` - update fixtures
     - `tests/test_workflow_chore.py` - update cumulative badge assertions

  4. - [ ] Add migration test:
     - `tests/test_migration.py::test_migrate_to_v43`
     - Verify old data converts correctly

- **Key issues**:
  - Need to mock `dt_now_utc()` for maintenance timing tests
  - Need fixtures with pre-configured cumulative badges

---

## Testing & validation

- **Lint/Type**: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/`
- **Unit Tests**: `pytest tests/test_cumulative_badge_engine.py -v`
- **Integration Tests**: `pytest tests/test_cumulative_badge_integration.py -v`
- **Full Suite**: `pytest tests/ -v --tb=line`

---

## Notes & follow-up

### Future Enhancements (Post-v0.6.0)

1. **Periodic Badges Refactor**: Apply same state/definition separation pattern
2. **Achievement Engine**: Extract achievement evaluation to pure engine
3. **Challenge Engine**: Extract challenge evaluation to pure engine
4. **Gamification Dashboard Card**: Custom Lovelace card for badge progress visualization

---

## Gamification Future Analysis

### Already Implemented (Stats Consolidation Phase 4B)

**Badge Period Tracking** is already fully operational via Landlord/Tenant pattern:

| Component           | Role     | Responsibility                                          |
| ------------------- | -------- | ------------------------------------------------------- |
| GamificationManager | Landlord | Creates `badges_earned[badge_id]["periods"]` bucket     |
| StatisticsManager   | Tenant   | Writes `award_count` into `periods.daily/weekly/etc`    |
| StatisticsEngine    | Reader   | `get_badge_award_count()` reads from `periods.all_time` |

**Signal Flow** (already wired):

```
GamificationManager emits BADGE_EARNED
  → StatisticsManager._on_badge_earned() increments periods.all_time.all_time.award_count
  → EconomyManager._on_badge_earned() deposits bonus points
  → RewardManager._on_badge_earned() grants free rewards
  → NotificationManager._handle_badge_earned() sends notification
```

**Data Structure** (per badge, per kid):

```json
"badges_earned": {
  "uuid-badge-1": {
    "badge_name": "Perfect Week",
    "last_awarded_date": "2026-01-15",
    "periods": {
      "daily": { "2026-01-15": { "award_count": 1 } },
      "weekly": { "2026-W03": { "award_count": 2 } },
      "monthly": { "2026-01": { "award_count": 5 } },
      "all_time": { "all_time": { "award_count": 23 } }
    }
  }
}
```

### New Gamification Opportunities

#### 1. Badge Earning Streaks (NEW - High Value)

**Concept**: Track consecutive days/weeks a kid earns any badge.

**Why Valuable**:

- Creates meta-gamification (badges about earning badges)
- Encourages consistent engagement beyond single chore completion
- Parents can reward "hot streak" behavior

**Data Structure** (at kid level, NOT per badge):

```json
"badge_earning_streak": {
  "current_daily_streak": 5,
  "last_badge_earned_date": "2026-01-15",
  "longest_daily_streak": 12,
  "weekly_streak": 3,
  "last_week_earned": "2026-W03"
}
```

**Signal Extension**:

- StatisticsManager already listens to `BADGE_EARNED`
- Add streak tracking alongside period updates
- Emit new `SIGNAL_SUFFIX_BADGE_EARNING_STREAK_UPDATED` for dashboard refresh

**Dashboard Integration**:

- Add `badge_earning_streak` to dashboard helper sensor attributes
- Jinja2 can display "🔥 5-day badge streak!"

#### 2. Aggregate Badge Stats by Period (NEW - Medium Value)

**Concept**: Kid-level aggregates of total badges earned today/week/month.

**Why Valuable**:

- "You earned 3 badges this week!" motivational messaging
- Enables badge-based challenges ("Earn 5 badges this week")
- Historical comparison ("More badges than last month!")

**Data Structure** (at kid level):

```json
"badge_stats_periods": {
  "daily": { "2026-01-15": { "total_badges_earned": 2, "unique_badges": 2 } },
  "weekly": { "2026-W03": { "total_badges_earned": 7, "unique_badges": 4 } },
  "monthly": { "2026-01": { "total_badges_earned": 23, "unique_badges": 8 } },
  "all_time": { "all_time": { "total_badges_earned": 156, "unique_badges": 12 } }
}
```

**Implementation Path**:

- Landlord (GamificationManager): Create `badge_stats_periods` structure on kid create
- Tenant (StatisticsManager): Increment `total_badges_earned` in `_on_badge_earned()`
- Reader (UIManager): Expose in dashboard helper sensor

#### 3. Achievement Period Tracking (NEW - High Value)

**Concept**: Apply same "Lean Item / Global Bucket" pattern to achievements.

**Why Valuable**:

- Track "Achievements completed today/week/month"
- Enable achievement-based meta-challenges
- Historical achievement velocity

**Current State**:

- Achievements track `progress[target_count]` and `earned_date`
- NO period tracking like badges have

**Data Structure** (mirroring badge pattern):

```json
"achievements_completed": {
  "uuid-achievement-1": {
    "achievement_name": "Chore Master",
    "earned_date": "2026-01-10",
    "periods": {
      "monthly": { "2026-01": { "earned_count": 1 } },
      "all_time": { "all_time": { "earned_count": 1 } }
    }
  }
}
```

**Note**: Achievements are typically one-time, so `earned_count` will usually be 1 unless achievement is repeatable.

#### 4. Challenge Completion Streaks (NEW - Medium Value)

**Concept**: Track consecutive successful challenges.

**Why Valuable**:

- Challenges are time-bound → natural streak mechanics
- "3 challenges in a row!" builds momentum
- Failure breaks streak → adds stakes

**Data Structure** (at kid level):

```json
"challenge_streak": {
  "current_streak": 3,
  "longest_streak": 7,
  "last_challenge_completed_date": "2026-01-14"
}
```

### Traps & Risks to Avoid

#### TRAP 1: Circular Signal Dependencies ⚠️

**Problem**: If StatisticsManager emits a signal after updating badge_earning_streak, and GamificationManager listens to create a "streak badge", infinite loop risk.

**Solution**: Clear signal ownership rules:

```
BADGE_EARNED → StatisticsManager (Tenant) updates periods ONLY
            → Does NOT emit new signals from _on_badge_earned()

BADGE_EARNING_STREAK_UPDATED → New signal, emitted by new StreakManager
                             → GamificationManager can listen for streak badges
```

**Pattern**: Tenants NEVER emit signals. Only Landlords emit signals.

#### TRAP 2: Stale Cumulative Badge Progress ⚠️

**Problem**: If `cumulative_badge_progress` stores `current_badge_name` and admin renames badge, UI shows old name.

**Solution (already in plan)**: Compute `current_badge_name` on-demand in `get_cumulative_badge_progress()`.

**Extension**: Apply same pattern to ALL badge-related computed fields.

#### TRAP 3: Migration Data Loss ⚠️

**Problem**: If migration removes `cycle_points` before renaming to `maintenance_points`, data is lost.

**Solution**: Migration must:

1. Read old value
2. Write to new key
3. Delete old key (after successful write)

**Test**: Migration test with realistic pre-migration data.

#### TRAP 4: Dashboard Helper Staleness ⚠️

**Problem**: Dashboard helper sensor caches `cumulative_badge_progress`. If we change computation, sensor shows stale data.

**Solution**: UIManager must invalidate/refresh dashboard helper attributes when:

- `BADGE_EARNED` signal received
- `BADGE_UPDATED` signal received (status change)
- `MIDNIGHT_ROLLOVER` signal received (maintenance check completed)

**Implementation**: Add listeners in UIManager.async_setup():

```python
self.listen(const.SIGNAL_SUFFIX_BADGE_EARNED, self._on_badge_changed)
self.listen(const.SIGNAL_SUFFIX_BADGE_UPDATED, self._on_badge_changed)
```

#### TRAP 5: Schema Version Collision ⚠️ - NON ISSUE

**Problem**: Plan says "Schema v43"

**Resolution**: This plan will use v43

### Implementation Priority Matrix

| Opportunity                  | Value  | Effort | Dependencies             | Phase          |
| ---------------------------- | ------ | ------ | ------------------------ | -------------- |
| Cumulative Badge Refactor    | HIGH   | HIGH   | None                     | This plan      |
| Badge Earning Streaks        | HIGH   | MEDIUM | This plan completes      | Follow-up plan |
| Aggregate Badge Stats        | MEDIUM | LOW    | Stats Consolidation      | Follow-up plan |
| Achievement Period Tracking  | HIGH   | MEDIUM | Depends on badge pattern | Future         |
| Challenge Completion Streaks | MEDIUM | LOW    | Depends on badge pattern | Future         |

### Pattern Reference: "Lean Item / Global Bucket"

From STATS_CONSOLIDATION_CACHE_OWNERSHIP_COMPLETED.md:

**Principle**: Store minimal state per item, aggregate stats survive item deletion.

**Applied to Cumulative Badges**:

| Field Type      | Where Stored                      | Why                                    |
| --------------- | --------------------------------- | -------------------------------------- |
| State           | `cumulative_badge_progress`       | Per-kid, changes over time             |
| Lifetime Points | `point_periods.all_time.all_time` | Global bucket, survives reset          |
| Badge Config    | `badges_data[badge_id]`           | Definition, computed on-demand         |
| Computed        | NEVER stored                      | `get_cumulative_badge_progress()` calc |

**Key Insight**: `cumulative_badge_progress` should ONLY store:

- `current_badge_id` (state)
- `highest_earned_badge_id` (state)
- `status` (state)
- `maintenance_points` (state)
- `period_end` (state)
- `grace_end` (state)

Everything else is computed from:

- Badge definitions in `badges_data`
- Lifetime points in `point_periods.all_time.all_time.earned`

### Architecture Decision Records

**ADR-001: Lifetime Points as Truth**

- Decision: Use `point_periods.all_time.all_time.earned` as cumulative badge metric
- Rationale: Never decreases (unlike balance), already maintained by StatisticsEngine
- Impact: Removes need for `baseline` field

**ADR-002: On-Demand Computation**

- Decision: Compute `next_higher_*`, `next_lower_*` fields on-demand
- Rationale: Prevents stale data when badge config changes
- Impact: Slightly higher CPU per dashboard refresh (negligible)

**ADR-003: Grace State**

- Decision: Add `grace` as intermediate state between `active` and `demoted`
- Rationale: Gives kids time to recover before losing benefits
- Impact: New state machine transition, notification opportunity

---

## Appendix: Current vs Future Data Comparison

### Current Storage (Schema v42)

```json
{
  "cumulative_badge_progress": {
    "current_badge_id": "uuid",
    "current_badge_name": "Bronze", // ❌ REMOVE
    "current_threshold": 500.0, // ❌ REMOVE
    "cycle_points": 1506.0, // → RENAME: maintenance_points
    "maintenance_end_date": null, // → RENAME: period_end
    "maintenance_grace_end_date": null, // → RENAME: grace_end
    "status": "demoted",
    "baseline": 0.0, // ❌ REMOVE
    "highest_earned_badge_id": "uuid",
    "highest_earned_badge_name": "Bronze", // ❌ REMOVE
    "highest_earned_threshold": 500.0, // ❌ REMOVE
    "next_higher_badge_id": "uuid", // ❌ REMOVE
    "next_higher_badge_name": "Silver", // ❌ REMOVE
    "next_higher_threshold": 2500.0, // ❌ REMOVE
    "next_higher_points_needed": 996.0, // ❌ REMOVE
    "next_lower_badge_id": null, // ❌ REMOVE
    "next_lower_badge_name": null, // ❌ REMOVE
    "next_lower_threshold": null // ❌ REMOVE
  }
}
```

### Future Storage (Schema v43)

```json
{
  "cumulative_badge_progress": {
    "current_badge_id": "uuid",
    "highest_earned_badge_id": "uuid",
    "status": "demoted",
    "maintenance_points": 1506.0,
    "period_end": "2026-03-01",
    "grace_end": null
  }
}
```

**Reduction**: 19 fields → 6 fields (68% storage reduction per kid)

---

> **Template usage notice:** This is an active plan document in `docs/in-process/`. Once complete, rename to `GAMIFICATION_NEXTGEN_PLAN_COMPLETE.md` and move to `docs/completed/`.
