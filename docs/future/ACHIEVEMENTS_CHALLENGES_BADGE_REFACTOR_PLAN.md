# Achievements & Challenges Badge-Style Refactor Plan

**Date**: December 30, 2025
**Status**: Planning Phase
**Scope**: Refactor achievements and challenges to use simplified periodic badge mechanics without reset/maintenance cycles

---

## Executive Summary

**Current State**: Achievements and challenges are implemented with simple, hardcoded logic:

- **Achievements**: 3 types (TOTAL, STREAK, DAILY_MIN) with basic progress tracking
- **Challenges**: 2 types (TOTAL_WITHIN_WINDOW, DAILY_MIN) with time-window constraints

**Target State**: Duplicate periodic badge mechanics WITHOUT the reset/maintenance cycles:

- Flexible metric tracking (points, chores, badges)
- Multiple threshold types (like badges have 17 different target types)
- Badge-aware metrics: "Earn daily badge 5 times", "Earn these 3 badges", etc.
- Simpler than full badges (no periodic resets, no cumulative tracking)

**Estimated Effort**: 40-60 hours total

---

## Architecture Analysis

### Current Badge Architecture (Periodic Type)

**Key Components** (from `coordinator.py` lines 4741-5400):

1. **Target/Threshold System** (17 different types):

   - `BADGE_TARGET_THRESHOLD_TYPE_POINTS` - Total points threshold
   - `BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES` - Points from chores only
   - `BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT` - Number of chores
   - `BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES` - Days with 100% completion
   - `BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES` - Days with 80% completion
   - `BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_3_CHORES` - Days with min 3 chores
   - `BADGE_TARGET_THRESHOLD_TYPE_STREAK_*` - Various streak types (8 variations)

2. **Handler System** (4 core handlers):

   - `_handle_badge_target_points()` - Tracks points with cycle counts
   - `_handle_badge_target_chore_count()` - Tracks chores with cycle counts
   - `_handle_badge_target_daily_completion()` - Tracks daily completion criteria
   - `_handle_badge_target_streak()` - Tracks consecutive days

3. **Progress Tracking** (stored per kid, per badge):

   ```python
   progress = {
       "last_update_day": "2025-12-30",
       "points_today": 50,
       "points_cycle_count": 250,  # Accumulates over time
       "chores_today": 3,
       "chores_cycle_count": 15,
       "days_completed": {"2025-12-28": True, "2025-12-29": True},
       "today_completed": True,
       "overall_progress": 0.75,  # For UI display
       "criteria_met": False,
       "tracked_chores": ["chore_uuid_1", "chore_uuid_2"]
   }
   ```

4. **Chore Tracking**:
   - `_get_badge_in_scope_chores_list()` - Filters chores by badge settings
   - Supports "all chores" or "specific tracked chores"
   - Respects kid assignments

### Current Achievement/Challenge Architecture

**Achievements** (`coordinator.py` lines 7254-7420):

- 3 hardcoded types with basic tracking
- Simple progress structures
- Direct check → award flow
- No cycle counting, no daily rollover

**Challenges** (`coordinator.py` lines 7420+):

- 2 hardcoded types
- Time window constraints (start_date/end_date)
- Daily count tracking for DAILY_MIN type
- Simple award flow

### What to Keep vs. What to Add

**Keep from Current**:

- ✅ One-time award model (no resets)
- ✅ Simple start_date/end_date filtering
- ✅ Notification system

**Add from Badges**:

- ✅ Target/threshold handler system
- ✅ Flexible metric tracking (points, chores, badges)
- ✅ Progress tracking with cycle counts
- ✅ Daily rollover logic (but no reset to zero)
- ✅ Badge-tracking metrics

**Explicitly Exclude**:

- ❌ Periodic resets (weekly/monthly/etc.)
- ❌ Cumulative badge maintenance
- ❌ Baseline/cycle reset logic
- ❌ Badge state machine (active_cycle, earned, in_progress)

---

## Proposed Architecture

### 1. Unified Target/Threshold System

**New Constants** (add to `const.py`):

```python
# Achievement/Challenge Target Types
ACH_TARGET_TYPE_POINTS = "points"
ACH_TARGET_TYPE_POINTS_CHORES = "points_chores"
ACH_TARGET_TYPE_CHORE_COUNT = "chore_count"
ACH_TARGET_TYPE_DAYS_COMPLETE = "days_complete"
ACH_TARGET_TYPE_DAYS_80PCT = "days_80pct"
ACH_TARGET_TYPE_STREAK_COMPLETE = "streak_complete"
ACH_TARGET_TYPE_STREAK_80PCT = "streak_80pct"
ACH_TARGET_TYPE_BADGE_DAILY_COUNT = "badge_daily_count"
ACH_TARGET_TYPE_BADGE_SPECIFIC_SET = "badge_specific_set"
ACH_TARGET_TYPE_BADGE_ANY_COUNT = "badge_any_count"

# Achievement/Challenge Progress Keys
DATA_ACH_PROGRESS_POINTS_TOTAL = "points_total"
DATA_ACH_PROGRESS_CHORES_TOTAL = "chores_total"
DATA_ACH_PROGRESS_DAYS_COMPLETED = "days_completed"
DATA_ACH_PROGRESS_STREAK_CURRENT = "streak_current"
DATA_ACH_PROGRESS_BADGES_EARNED = "badges_earned"
DATA_ACH_PROGRESS_LAST_UPDATE_DAY = "last_update_day"
DATA_ACH_PROGRESS_OVERALL = "overall_progress"
DATA_ACH_PROGRESS_CRITERIA_MET = "criteria_met"
```

### 2. Achievement/Challenge Data Structure

**Storage Schema** (add to achievement/challenge dicts):

```python
achievement_info = {
    # Existing fields
    "name": "Master Organizer",
    "description": "Complete 100 chores",
    "icon": "mdi:trophy",
    "assigned_kids": ["kid_uuid_1"],
    "reward_points": 50,

    # NEW: Target configuration
    "target": {
        "type": "chore_count",  # One of ACH_TARGET_TYPE_*
        "threshold_value": 100,
        "tracked_chores": [],  # Empty = all chores
    },

    # NEW: Progress tracking (per kid)
    "progress": {
        "kid_uuid_1": {
            "chores_total": 75,
            "last_update_day": "2025-12-30",
            "overall_progress": 0.75,
            "criteria_met": False,
            "awarded": False,
        }
    },

    # Optional: Time constraints
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
}
```

### 3. Handler Functions (New)

**Core Handlers** (add to `coordinator.py`):

```python
def _handle_achievement_target_points(
    self, kid_info, achievement_info, progress, threshold_value, from_chores_only=False
):
    """Track points toward achievement (all sources or chores only)."""
    # Similar to badge handler, but cumulative (no cycle reset)

def _handle_achievement_target_chore_count(
    self, kid_info, achievement_info, progress, threshold_value
):
    """Track total chores toward achievement."""

def _handle_achievement_target_days(
    self, kid_info, achievement_info, progress, threshold_value,
    percent_required=1.0, tracked_chores=None
):
    """Track days meeting criteria."""

def _handle_achievement_target_streak(
    self, kid_info, achievement_info, progress, threshold_value,
    percent_required=1.0, tracked_chores=None
):
    """Track consecutive days meeting criteria."""

def _handle_achievement_target_badge_daily(
    self, kid_info, achievement_info, progress, threshold_value
):
    """Track daily badge awards (e.g., 'earn daily badge 5 times')."""
    # NEW: Badge-aware metric

def _handle_achievement_target_badge_set(
    self, kid_info, achievement_info, progress, required_badges
):
    """Track specific badge set completion."""
    # NEW: Badge-aware metric
    # Check if kid has earned all badges in required_badges list

def _handle_achievement_target_badge_count(
    self, kid_info, achievement_info, progress, threshold_value
):
    """Track total badge count."""
    # NEW: Badge-aware metric
```

### 4. Main Check Function (Refactor)

**Replace `_check_achievements_for_kid()`**:

```python
def _check_achievements_for_kid(self, kid_id: str):
    """Evaluate all achievement criteria for a given kid.

    Uses flexible handler system similar to badges but without resets.
    """
    kid_info = self.kids_data.get(kid_id)
    if not kid_info:
        return

    today_local_iso = kh.get_today_local_iso()

    # Map target types to handlers
    target_handlers = {
        const.ACH_TARGET_TYPE_POINTS: (
            self._handle_achievement_target_points, {}
        ),
        const.ACH_TARGET_TYPE_POINTS_CHORES: (
            self._handle_achievement_target_points,
            {"from_chores_only": True}
        ),
        const.ACH_TARGET_TYPE_CHORE_COUNT: (
            self._handle_achievement_target_chore_count, {}
        ),
        const.ACH_TARGET_TYPE_DAYS_COMPLETE: (
            self._handle_achievement_target_days,
            {"percent_required": 1.0}
        ),
        const.ACH_TARGET_TYPE_STREAK_COMPLETE: (
            self._handle_achievement_target_streak,
            {"percent_required": 1.0}
        ),
        const.ACH_TARGET_TYPE_BADGE_DAILY_COUNT: (
            self._handle_achievement_target_badge_daily, {}
        ),
        const.ACH_TARGET_TYPE_BADGE_SPECIFIC_SET: (
            self._handle_achievement_target_badge_set, {}
        ),
        # ... etc
    }

    for achievement_id, achievement_info in self.achievements_data.items():
        # Skip if already awarded
        progress = achievement_info.get("progress", {}).get(kid_id, {})
        if progress.get("awarded", False):
            continue

        # Check time window
        if not self._is_achievement_in_effect(achievement_info, today_local_iso):
            continue

        # Get target configuration
        target = achievement_info.get("target", {})
        target_type = target.get("type")
        threshold_value = target.get("threshold_value", 1)

        # Call appropriate handler
        handler_tuple = target_handlers.get(target_type)
        if handler_tuple:
            handler, kwargs = handler_tuple
            updated_progress = handler(
                kid_info, achievement_info, progress,
                threshold_value, **kwargs
            )
            achievement_info["progress"][kid_id] = updated_progress

            # Award if criteria met
            if updated_progress.get("criteria_met", False):
                self._award_achievement(kid_id, achievement_id)
```

---

## Badge-Aware Metrics Implementation

### New Metric Type: Badge Tracking

**Use Case Examples**:

1. "Earn the Daily Champ badge 5 times this month"
2. "Earn all 3 Bronze tier badges"
3. "Earn any 10 badges"

**Implementation Strategy**:

1. **Track Badge Earnings**:

```python
# Add to kid_info structure
kid_info = {
    # ... existing fields
    "badges_earned": {
        "badge_uuid_1": {
            "first_earned": "2025-12-01T10:00:00Z",
            "times_earned": 3,  # For periodic badges
            "last_earned": "2025-12-20T15:00:00Z",
        },
        "badge_uuid_2": {
            "first_earned": "2025-12-10T12:00:00Z",
            "times_earned": 1,
            "last_earned": "2025-12-10T12:00:00Z",
        }
    }
}
```

2. **Badge Daily Count Handler**:

```python
def _handle_achievement_target_badge_daily(
    self, kid_info, achievement_info, progress, threshold_value
):
    """Track how many times a specific daily badge has been earned."""
    target = achievement_info.get("target", {})
    badge_id = target.get("tracked_badge_id")

    if not badge_id:
        return progress

    badges_earned = kid_info.get("badges_earned", {})
    badge_record = badges_earned.get(badge_id, {})
    times_earned = badge_record.get("times_earned", 0)

    progress["badges_earned_count"] = times_earned
    progress["overall_progress"] = min(times_earned / threshold_value, 1.0)
    progress["criteria_met"] = times_earned >= threshold_value

    return progress
```

3. **Badge Set Handler**:

```python
def _handle_achievement_target_badge_set(
    self, kid_info, achievement_info, progress, required_badges
):
    """Check if kid has earned all badges in a specific set."""
    target = achievement_info.get("target", {})
    required_badge_ids = target.get("required_badges", [])

    badges_earned = kid_info.get("badges_earned", {})
    earned_set = set(badges_earned.keys())
    required_set = set(required_badge_ids)

    earned_count = len(earned_set & required_set)
    total_count = len(required_set)

    progress["badges_earned"] = list(earned_set & required_set)
    progress["badges_remaining"] = list(required_set - earned_set)
    progress["overall_progress"] = earned_count / total_count if total_count else 0
    progress["criteria_met"] = earned_set >= required_set

    return progress
```

4. **Modify `_award_badge()` to Track**:

```python
def _award_badge(self, kid_id: str, badge_id: str):
    """Add badge to kid's earned list and update tracking."""
    # ... existing award logic ...

    # NEW: Track badge earnings
    kid_info = self.kids_data.get(kid_id, {})
    badges_earned = kid_info.setdefault("badges_earned", {})
    badge_record = badges_earned.setdefault(badge_id, {
        "first_earned": None,
        "times_earned": 0,
        "last_earned": None,
    })

    now_iso = dt_util.utcnow().isoformat()
    if badge_record["first_earned"] is None:
        badge_record["first_earned"] = now_iso
    badge_record["times_earned"] += 1
    badge_record["last_earned"] = now_iso

    # Check badge-related achievements
    self._check_achievements_for_kid(kid_id)
```

---

## Migration Strategy

### Phase 1: Data Structure Migration (8-10 hours)

**Tasks**:

1. Add new constants to `const.py` (2 hours)

   - Target types (10+ new constants)
   - Progress tracking keys (10+ new constants)

2. Update achievement/challenge data structure (3 hours)

   - Add `target` dict with type/threshold
   - Add `progress` dict per kid
   - Add `tracked_chores` list (optional)

3. Create migration function (3 hours)
   - Map old `type` field to new `target.type`
   - Map old `target_value` to new `target.threshold_value`
   - Preserve existing progress where possible
   - Test with all 3 scenarios (minimal, medium, full)

### Phase 2: Handler Implementation (12-16 hours)

**Tasks**:

1. Implement 4 core handlers (8 hours)

   - Points handler (2 hours)
   - Chore count handler (2 hours)
   - Days completion handler (2 hours)
   - Streak handler (2 hours)

2. Implement 3 badge-aware handlers (4 hours)

   - Badge daily count (1.5 hours)
   - Badge specific set (1.5 hours)
   - Badge any count (1 hour)

3. Add badge tracking to `_award_badge()` (2 hours)

   - Update kid_info structure
   - Test with periodic badges

4. Create `_is_achievement_in_effect()` helper (1 hour)

   - Time window validation

5. Unit tests for handlers (3 hours)

### Phase 3: Main Check Function Refactor (8-10 hours)

**Tasks**:

1. Refactor `_check_achievements_for_kid()` (4 hours)

   - Handler dispatch system
   - Progress tracking
   - Award logic

2. Refactor `_check_challenges_for_kid()` (3 hours)

   - Similar pattern to achievements

3. Update `_award_achievement()` (1 hour)

   - Ensure progress updates

4. Integration tests (4 hours)
   - Test all target types
   - Test badge-aware metrics

### Phase 4: Config/Options Flow Updates (8-10 hours)

**Tasks**:

1. Update achievement config flow (3 hours)

   - Add target type selector
   - Add threshold input
   - Add tracked chores selector
   - Add badge selector (for badge-aware types)

2. Update challenge config flow (3 hours)

   - Similar to achievements

3. Update options flow (2 hours)

   - Edit existing achievements/challenges

4. UI tests (2 hours)

### Phase 5: Sensor Updates (4-6 hours)

**Tasks**:

1. Update `AchievementSensor` (2 hours)

   - Read new progress structure
   - Display overall_progress

2. Update `ChallengeSensor` (2 hours)

   - Similar to AchievementSensor

3. Update extra_state_attributes (2 hours)
   - Add badge tracking info
   - Add detailed progress

### Phase 6: Testing & Cleanup (8-10 hours)

**Tasks**:

1. Create comprehensive test scenarios (4 hours)

   - Test all 10+ target types
   - Test badge-aware metrics
   - Test time window constraints

2. Update existing tests (2 hours)

   - Fix broken tests due to structure changes

3. Performance testing (1 hour)

   - Verify no regression

4. Documentation (2 hours)

   - Update ARCHITECTURE.md
   - Update user docs

5. Code review & cleanup (1 hour)

---

## Effort Estimate Summary

| Phase | Description              | Hours | Dependencies |
| ----- | ------------------------ | ----- | ------------ |
| 1     | Data Structure Migration | 8-10  | None         |
| 2     | Handler Implementation   | 12-16 | Phase 1      |
| 3     | Main Check Function      | 8-10  | Phase 2      |
| 4     | Config/Options Flow      | 8-10  | Phase 3      |
| 5     | Sensor Updates           | 4-6   | Phase 3      |
| 6     | Testing & Cleanup        | 8-10  | All above    |

**Total Estimated Effort**: 48-62 hours (call it 40-60 hours)

**Critical Path**: Phases 1 → 2 → 3 are sequential. Phases 4 and 5 can be parallelized after Phase 3.

---

## Risk Assessment

### High Risk

- **Data migration complexity**: Existing achievements/challenges have active progress that must be preserved

  - **Mitigation**: Comprehensive backup before migration, rollback plan

- **Badge tracking overhead**: New badge_earned tracking adds complexity to badge award flow
  - **Mitigation**: Performance testing, optimize badge_earned dict structure

### Medium Risk

- **UI/UX confusion**: Users may not understand badge-aware achievement types

  - **Mitigation**: Clear descriptions, examples in config flow

- **Test coverage gaps**: Many new code paths to test
  - **Mitigation**: Systematic test matrix, scenario-based testing

### Low Risk

- **Breaking existing tests**: Structure changes will require test updates
  - **Mitigation**: Update tests incrementally, maintain test coverage

---

## Success Criteria

1. **Functional**:

   - ✅ All 10+ target types work correctly
   - ✅ Badge-aware metrics track badge earnings
   - ✅ Progress persists across restarts
   - ✅ Awards granted when criteria met
   - ✅ No periodic resets (one-time awards only)

2. **Performance**:

   - ✅ No regression in `_check_achievements_for_kid()` execution time
   - ✅ Badge tracking adds < 5ms overhead to `_award_badge()`

3. **Quality**:

   - ✅ 95%+ test coverage maintained
   - ✅ Zero critical linting errors
   - ✅ All existing tests pass (with updates)

4. **User Experience**:
   - ✅ Config flow intuitive for new target types
   - ✅ Sensors display meaningful progress
   - ✅ Notifications work correctly

---

## Implementation Notes

### Key Differences from Badges

1. **No Resets**: Progress accumulates until awarded, then stops (no reset cycles)
2. **Simpler State**: Only 2 states (in_progress, awarded) vs badges (active_cycle, earned, in_progress)
3. **No Maintenance**: No `_manage_achievement_maintenance()` function needed
4. **Badge-Aware**: NEW capability badges don't have (track badge earnings)

### Reusable Code from Badges

- ✅ Handler pattern (dispatch system)
- ✅ Progress tracking structure (days_completed, streak, etc.)
- ✅ Daily rollover logic (last_update_day comparison)
- ✅ Chore filtering (`_get_badge_in_scope_chores_list()`)

### New Code Required

- Badge tracking in kid_info (badges_earned dict)
- Badge-aware handlers (3 new functions)
- Achievement time window validation
- Migration from old structure to new

---

## Next Steps

1. **Review & Approve Plan**: Validate approach with stakeholders
2. **Create Feature Branch**: `feature/achievement-badge-refactor`
3. **Start Phase 1**: Data structure migration & constants
4. **Iterate**: Complete phases sequentially, test thoroughly

---

**Document Version**: 1.0
**Author**: AI Development Agent
**Last Updated**: December 30, 2025
