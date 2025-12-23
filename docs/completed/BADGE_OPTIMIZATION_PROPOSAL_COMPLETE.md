# Badge Evaluation Optimization Proposal

> **Document**: Phase 1 Badge Optimization - Post-Implementation Review
> **Created**: 2025-12-23
> **Updated**: 2025-12-23 (Optimization 1 reverted after performance regression discovered)
> **Status**: ✅ ANALYSIS COMPLETE - Optimization 1 was false optimization, reverted successfully
> **Reference**: [BADGE_EVALUATION_FLOW_ANALYSIS.md](BADGE_EVALUATION_FLOW_ANALYSIS.md)

---

## Executive Summary

Based on detailed code analysis, the badge evaluation system uses an **incremental model** (not history scanning). The performance bottleneck is **redundant computation per badge** rather than architectural issues. This proposal outlined 5 optimizations - **1 was found to be a false optimization and reverted**.

**Performance Journey**:

- **Baseline**: 372ms for 100 kids × 18 badges = 3.7ms per kid average
- **After all optimizations**: 600ms (62% SLOWER - regression discovered!)
- **After reverting Opt 1**: 372ms (baseline restored)
- **Root Cause**: Cache construction overhead + always-on execution exceeded savings

**Test Coverage** (Phase 1a ✅ COMPLETE):

- ✅ Comprehensive test suite: `test_badge_target_types_comprehensive.py` (21 tests)
- ✅ All 17 target types covered (2 points + 1 count + 9 daily + 5 streak)
- ✅ Day rollover accumulation logic tested (2 tests)
- ✅ Badge awarding flow tested (2 tests)
- ✅ Uses scenario_full fixture for realistic data (3 kids, 7 chores)
- ✅ All tests passing (5.79s execution time for 27 badge tests)
- ✅ Validates: data structures, helper function integration, threshold calculations, state transitions

**Final Implementation Status**:

- ❌ **Optimization 1**: Pre-compute kid daily stats cache - **REVERTED** (false optimization)
- ✅ **Optimization 2**: Cache kid-assigned chores (kept - minimal but harmless)
- ✅ **Optimization 3**: Hoist today_local_iso (kept - minimal but harmless)
- ✅ **Optimization 4**: Defer persist operations (kept - correct optimization)
- ❌ **Optimization 5**: Prune days_completed dict - **REVERTED** (tied to Opt 1)

**Architecture Consideration**:

Badge processing represents ~1,570 lines (19% of coordinator.py's 8,346 lines) across 22 badge-related methods. Core evaluation section (lines 3952-4740) contains 788 lines of complex logic. See "Badge Module Extraction Analysis" section below for refactoring recommendation.

**Key Learning**:

🔥 **"Optimization" can make performance worse!** Theoretical operation count reduction does not guarantee actual improvement. Always profile and measure. Cache construction overhead + always-on execution can exceed savings from eliminated calls.

---

## Optimization 1: Pre-compute Kid Daily Stats Cache ❌ REVERTED

### Revert Summary

**Status**: ❌ Reverted - Identified as false optimization causing 62% performance regression
**Performance Impact**: Baseline 372ms → 600ms (62% WORSE, not better)

**Root Cause Analysis**:

1. **Baseline behavior**: Called `get_today_chore_and_point_progress()` only when specific badge handlers needed it (on-demand execution)
2. **"Optimized" behavior**: Always called it upfront for every kid before badge loop (always-on execution)
3. **Result**: No reduction in total work + added overhead (dataclass creation, parameter passing) = worse performance

**Why the False Optimization Occurred**:

- ❌ **Assumption**: "Calling helper 18 times per kid is wasteful" - WRONG if not all badges need the data!
- ❌ **Oversight**: Didn't profile which handlers actually called the helpers (only 4 of 17 target types needed it)
- ❌ **Cache overhead**: Dataclass construction + 11 fields of memory allocation + parameter passing cost
- ✅ **Lesson**: On-demand execution is better than always-on caching when not all code paths need the data

**Reverted Changes** (2025-12-23):

1. Removed `KidDailyStatsCache` dataclass (30 lines)
2. Removed cache construction in `_check_badges_for_kid()` (25 lines)
3. Removed cache parameter passing from handler calls
4. Restored original handler implementations calling helpers directly (4 handlers)
5. Removed `_prune_badge_days_completed()` method (39 lines, tied to cache)
6. Removed `DEFAULT_BADGE_DAYS_COMPLETED_RETENTION` constant

**Validation After Revert**:

- ✅ Performance: 372ms (exact baseline match)
- ✅ Linting: 9.65/10
- ✅ Tests: 552 passed, 10 skipped (all badge tests passing)
- ✅ PERF logging: Changed to debug level (7 locations)

### Original Implementation Summary (FOR REFERENCE ONLY - DO NOT RE-IMPLEMENT)

**Status**: ❌ REVERTED - False optimization
**Files Modified**:

- `coordinator.py`: Added `KidDailyStatsCache` dataclass (lines 36-59) - REMOVED
- `coordinator.py`: Cache construction in `_check_badges_for_kid()` (lines 4000-4023) - REMOVED
- `coordinator.py`: Updated 4 badge handlers to use cache (lines 4348-4690) - REVERTED

**Changes Made** (then reverted):

1. Created `@dataclass KidDailyStatsCache` with 11 fields consolidating 2 helper functions
2. Built cache once per kid before badge loop (eliminates 36 helper calls → 1 cache build)
3. Updated handler signatures to accept `daily_stats_cache: KidDailyStatsCache` as keyword-only parameter
4. Modified implementations to use cached data instead of calling helpers
5. Inlined completion logic in daily_completion and streak handlers (~70 lines)

**Validation Before Revert**:

- ✅ Linting: 9.65/10 (improved)
- ✅ Tests: 27/27 badge tests passing
- ✅ Type hints: No Pylance errors (used keyword-only parameters with `*`)
- ❌ Performance: 62% WORSE (600ms vs 372ms baseline)

### Problem Identified

Each badge handler calls helper functions that iterate the same kid data:

```python
# Called per badge in _handle_badge_target_points (line 4289)
kh.get_today_chore_and_point_progress(kid_info, tracked_chores)

# Called per badge in _handle_badge_target_daily_completion (line 4378)
kh.get_today_chore_completion_progress(kid_info, tracked_chores, ...)
```

**Verified Data Sources** (from kc_helpers.py lines 323-500):

| Helper Function                       | Data Read                                                                              | Iteration |
| ------------------------------------- | -------------------------------------------------------------------------------------- | --------- |
| `get_today_chore_and_point_progress`  | `kid_info[DATA_KID_CHORE_DATA][chore_id][periods][daily][today]`                       | Per chore |
| `get_today_chore_completion_progress` | `kid_info[DATA_KID_APPROVED_CHORES]`, `DATA_KID_OVERDUE_CHORES`, `DATA_KID_CHORE_DATA` | Per chore |

With 18 badges and 55 chores, this means **990 chore lookups per kid** (18 × 55).

### Proposed Solution

Pre-compute a **per-kid daily stats cache** ONCE before the badge loop:

```python
@dataclass
class KidDailyStatsCache:
    """Pre-computed daily stats for badge evaluation."""
    today_iso: str

    # From get_today_chore_and_point_progress
    total_points_all_sources: int
    total_points_from_chores: int
    total_chore_count: int
    points_per_chore: dict[str, int]      # {chore_id: points}
    count_per_chore: dict[str, int]       # {chore_id: count}

    # From get_today_chore_completion_progress
    approved_chores: set[str]             # Fast lookup
    overdue_chores: set[str]              # Fast lookup
    chores_due_today: set[str]            # Pre-filtered
    chores_overdue_today: set[str]        # Chores that went overdue today

    # Pre-computed for kid
    all_kid_chores: list[str]             # All chores assigned to this kid
```

### Implementation Location

**File**: `coordinator.py`
**New method**: `_build_kid_daily_stats_cache(kid_id: str) -> KidDailyStatsCache`
**Call site**: Line ~3970, before `for badge_id, badge_info in self.badges_data.items():`

### Verified Compatibility

✅ All data fields exist in current `kid_info` structure
✅ No changes to handler signatures required (pass cache as additional param)
✅ Backward compatible - handlers can still work without cache

### Estimated Impact

- **Before**: 18 badges × 55 chores × 2 lookups = 1,980 dict accesses
- **After**: 55 chores × 1 pass + 18 badges × O(1) lookups = ~73 operations
- **Reduction**: ~96% fewer chore iterations

---

## Optimization 2: Cache Kid-Assigned Chores ✅ IMPLEMENTED

### Implementation Summary

**Status**: ✅ Complete and validated
**Files Modified**:

- `coordinator.py`: Updated `_check_badges_for_kid()` to pre-compute kid chores (line ~4005)
- `coordinator.py`: Modified `_get_badge_in_scope_chores_list()` to accept pre-computed list (line ~4322)

**Changes**:

1. Compute `kid_assigned_chores` once before badge loop
2. Pass pre-computed list to `_get_badge_in_scope_chores_list()` via optional parameter
3. Function checks if list provided, skips iteration if available

**Validation**:

- ✅ Linting: Passed
- ✅ Tests: 27/27 badge tests passing
- ✅ Logic: Backward compatible (function still works without pre-computed list)

### Problem Identified

`_get_badge_in_scope_chores_list()` (lines 4229-4273) iterates ALL chores for EVERY badge:

```python
# Line 4255-4258: Called per badge
for chore_id, chore_info in self.chores_data.items():
    chore_assigned_to = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    if not chore_assigned_to or kid_id in chore_assigned_to:
        kid_assigned_chores.append(chore_id)
```

With 55 chores × 18 badges = **990 iterations** just for assignment checks.

### Proposed Solution

Compute `kid_assigned_chores` ONCE and include in the daily stats cache:

```python
# In _build_kid_daily_stats_cache():
kid_assigned_chores = []
for chore_id, chore_info in self.chores_data.items():
    assigned_to = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    if not assigned_to or kid_id in assigned_to:
        kid_assigned_chores.append(chore_id)

# Store as set for O(1) lookups
cache.all_kid_chores = kid_assigned_chores
cache.kid_chores_set = set(kid_assigned_chores)  # For intersection
```

### Modified Method Signature

```python
def _get_badge_in_scope_chores_list(
    self,
    badge_info: dict,
    kid_id: str,
    cache: KidDailyStatsCache | None = None  # NEW: Optional cache
) -> list:
```

### Verified Compatibility

✅ Logic unchanged - just moves computation earlier
✅ `kid_assigned_chores` is used in two places: all-chores case and intersection
✅ Badge-specific `tracked_chores` still need intersection with kid's chores

### Estimated Impact

- **Before**: 55 chores × 18 badges = 990 iterations
- **After**: 55 chores × 1 pass = 55 iterations
- **Reduction**: 94% fewer iterations

---

## Optimization 3: Hoist `today_local_iso` Outside Badge Loop ✅ IMPLEMENTED

### Implementation Summary

**Status**: ✅ Complete and validated
**Files Modified**:

- `coordinator.py`: Moved `today_local_iso` calculation before badge loop (line ~3975)

**Changes**:

1. Call `kh.get_today_local_iso()` once at function start
2. Use pre-computed value throughout badge loop
3. Eliminated 18 redundant datetime operations per kid

**Validation**:

- ✅ Linting: Passed
- ✅ Tests: 27/27 badge tests passing
- ✅ Logic: Date won't change during single evaluation (atomic operation)

### Problem Identified

`kh.get_today_local_iso()` is called inside the badge loop (line 4144):

```python
for badge_id, badge_info in self.badges_data.items():
    # ... badge assignment check ...

    # Line 4144: Called per badge!
    today_local_iso = kh.get_today_local_iso()
```

Also called again at line 4207 for `LAST_AWARDED` timestamp.

### Proposed Solution

Move to top of function, before the loop:

```python
def _check_badges_for_kid(self, kid_id: str):
    perf_start = time.perf_counter()

    kid_info = self.kids_data.get(kid_id)
    if not kid_info:
        return

    # NEW: Compute once at start
    today_local_iso = kh.get_today_local_iso()

    self._manage_badge_maintenance(kid_id)
    self._manage_cumulative_badge_maintenance(kid_id)

    # ... rest of function uses today_local_iso ...
```

### Verified Compatibility

✅ `get_today_local_iso()` returns same value within a single evaluation
✅ Date won't change mid-evaluation (atomic operation)
✅ Already passed to handlers as parameter

### Estimated Impact

- **Before**: 18 calls to `get_today_local_iso()` per kid
- **After**: 1 call per kid
- **Reduction**: 94% fewer datetime operations

---

## Optimization 4: Defer Persist Until End of Evaluation ✅ IMPLEMENTED

### Implementation Summary

**Status**: ✅ Complete and validated
**Files Modified**:

- `coordinator.py`: Removed persist from cumulative badge branch (removed lines in loop)
- `coordinator.py`: Kept single persist at function end (line ~4212)

**Changes**:

1. Removed `self._persist()` and `async_set_updated_data()` from inside cumulative badge loop
2. Kept single persist at end of `_check_badges_for_kid()`
3. Reduced N+1 persists to 1 persist per kid evaluation

**Validation**:

- ✅ Linting: Passed
- ✅ Tests: 27/27 badge tests passing
- ✅ Logic: Safe approach maintains recursive award flow

### Problem Identified

Inside `_check_badges_for_kid`, there are multiple persist points:

```python
# Line 4132-4133: Inside cumulative badge branch (per badge!)
self._persist()
self.async_set_updated_data(self._data)
continue

# Line 4212-4213: At end of function
self._persist()
self.async_set_updated_data(self._data)
```

The cumulative badge branch persists **per cumulative badge** instead of batching.

### Proposed Solution

Use a flag to track if changes occurred, persist only once at end:

```python
def _check_badges_for_kid(self, kid_id: str):
    # ... setup ...

    changes_made = False  # Track if any updates occurred

    for badge_id, badge_info in self.badges_data.items():
        # ... badge processing ...

        if badge_type == const.BADGE_TYPE_CUMULATIVE:
            # ... cumulative logic ...
            if effective_badge_id == badge_id:
                self._award_badge(kid_id, badge_id)
                changes_made = True
            # REMOVE: self._persist() and async_set_updated_data here
            continue

        # ... periodic badge logic ...
        kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id] = progress
        changes_made = True

    self._update_chore_badge_references_for_kid()

    # Single persist at end
    if changes_made:
        self._persist()
        self.async_set_updated_data(self._data)
```

### Verified Compatibility

⚠️ **CAUTION**: `_award_badge()` also calls `_persist()` (line 4688)
⚠️ `_award_badge()` recursively calls `_check_badges_for_kid()` (line 4690)

**Safe Approach**: Only remove the persist inside cumulative branch (lines 4132-4133), keep the final persist. This avoids breaking the recursive award flow.

### Estimated Impact

- **Before**: Up to N+1 persists per kid (N cumulative badges + 1 final)
- **After**: 1 persist per kid (+ any from \_award_badge)
- **Reduction**: Dependent on cumulative badge count

---

## Optimization 5: Prune `days_completed` Dict (Maintenance) ✅ IMPLEMENTED

### Implementation Summary

**Status**: ✅ Complete and validated
**Files Modified**:

- `const.py`: Added `DEFAULT_BADGE_DAYS_COMPLETED_RETENTION = 1095` (3 years)
- `coordinator.py`: Created `_prune_badge_days_completed()` helper (lines 4290-4320)
- `coordinator.py`: Added pruning calls in both handlers (lines 4557, 4675)

**Changes**:

1. Added retention constant: 1095 days (3 years) to support long-term badges
2. Created pruning method using `adjust_datetime_by_interval()` to calculate cutoff
3. Called pruning after updating `days_completed` in both daily_completion and streak handlers
4. Dict comprehension filters dates older than retention period

**Rationale for 3-year retention**:

- Supports 6-month badges (182 days) with 5x margin
- Supports 1-year badges (365 days) with 3x margin
- Supports theoretical 2-year badges with 1.5x margin
- Prevents unbounded memory growth while handling any realistic badge duration

**Validation**:

- ✅ Linting: 9.65/10 (improved)
- ✅ Tests: 27/27 badge tests passing
- ✅ Memory: Bounded growth with generous retention for long-term badges

### Problem Identified

The `days_completed` dict grows unbounded for streak/daily badges:

```python
# Line 4415 (daily completion) and 4489 (streak):
if criteria_met:
    days_completed[today_local_iso] = True
progress[const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED] = days_completed
```

Over time, this dict accumulates entries for every day criteria was met.

### Verified Usage

The `days_completed` dict is ONLY used in streak handler to check yesterday:

```python
# Line 4476-4477:
if days_completed.get(yesterday_iso):
    streak += 1
```

Daily completion handler stores it but **never reads it** - only `days_cycle_count` matters.

### Proposed Solution

For **streak badges**: Keep only last 7 days (sufficient for continuity check)
For **daily badges**: Don't store `days_completed` at all (not used)

```python
# In _handle_badge_target_streak, after updating days_completed:
# Prune old entries (keep last 7 days for safety)
if len(days_completed) > 7:
    sorted_dates = sorted(days_completed.keys(), reverse=True)
    days_completed = {d: True for d in sorted_dates[:7]}
```

### Verified Compatibility

✅ Streak only checks `yesterday_iso` - never older dates
✅ Daily completion never reads `days_completed`
✅ UI may display history - need to verify before removing from daily

### Estimated Impact

- **Storage**: Bounded growth instead of unbounded
- **Memory**: Prevents long-running systems from accumulating large dicts
- **Performance**: Minimal direct impact, but cleaner data

---

## ❌ OPTIMIZATION REVERTED - POST-IMPLEMENTATION ANALYSIS

**Status**: Optimizations 1 and 5 reverted after discovering 62% performance regression

### What Happened

After implementing all 5 optimizations and running the stress test, we discovered:

- **Baseline**: 372ms for 100 kids × 18 badges
- **After optimizations**: 600ms (62% SLOWER!)
- **After reverting Opt 1**: 372ms (baseline restored)

### Root Cause: Optimization 1 Was False Optimization

**Flawed Assumption**: "Calling helpers 18 times per kid is wasteful"

**Reality**:

- Baseline: Helpers called on-demand only when specific badge handlers needed them
- "Optimized": Helpers always called upfront for ALL kids, even if badges didn't need the data
- Result: No work reduction + cache construction overhead = worse performance

**Cache Overhead Costs**:

1. Dataclass construction (11 fields)
2. Memory allocation and field population
3. Parameter passing through call stack
4. All upfront work even when not needed

**Key Insight**: On-demand execution beats always-on caching when not all code paths need the data!

### What We Kept

- ✅ **Optimization 2**: Kid-assigned chores caching (minimal impact but correct)
- ✅ **Optimization 3**: today_local_iso hoisting (minimal impact but correct)
- ✅ **Optimization 4**: Defer persist operations (correct, reduces persist calls)

### What We Reverted

- ❌ **Optimization 1**: KidDailyStatsCache dataclass and all cache infrastructure
- ❌ **Optimization 5**: Prune days_completed (tied to cache, removed with Opt 1)

### Lessons Learned

1. 🔥 **Always profile, never assume** - Operation count reduction ≠ performance improvement
2. 🔥 **Cache construction has cost** - Dataclass creation, memory, parameter passing
3. 🔥 **On-demand > always-on** - Don't compute data upfront if not all paths need it
4. ✅ **Test coverage critical** - 27 badge tests caught functional issues immediately
5. ✅ **Baseline validation essential** - Stress test revealed regression unit tests couldn't show

### Final Performance

- Current: **372ms** (exact baseline match)
- Tests: **552 passed, 10 skipped**
- Linting: **9.65/10**
- Memory: Reasonable at scale (2MB per kid)

**Conclusion**: Sometimes the best optimization is reverting a bad one. Code is now at baseline with improved test coverage and valuable performance analysis lessons learned.

---

## Implementation Order (HISTORICAL - FOR REFERENCE)

| Priority | Optimization                    | Effort | Impact | Risk   |
| -------- | ------------------------------- | ------ | ------ | ------ |
| 1        | Hoist `today_local_iso`         | Low    | Medium | None   |
| 2        | Cache kid-assigned chores       | Medium | High   | Low    |
| 3        | Pre-compute daily stats         | Medium | High   | Low    |
| 4        | Defer persist (cumulative only) | Low    | Medium | Medium |
| 5        | Prune `days_completed`          | Low    | Low    | Medium |

### Recommended Sequence

1. **Phase 1a**: Optimizations 1-3 together (cache infrastructure)
2. **Phase 1b**: Optimization 4 (persist batching)
3. **Phase 1c**: Optimization 5 (data cleanup - needs UI verification)

---

## Testing Strategy

### Unit Tests Required

1. **Cache correctness**: Verify cache values match helper function results
2. **Badge evaluation**: Existing tests should pass unchanged
3. **Edge cases**: Empty chore lists, no badges assigned, day boundary

### Performance Validation

```python
def test_badge_optimization_performance():
    """Verify optimization reduces evaluation time."""
    # Use scenario_stress fixture (100 kids, 55 chores, 18 badges)

    start = time.perf_counter()
    for kid_id in coordinator.kids_data:
        coordinator._check_badges_for_kid(kid_id)
    duration = time.perf_counter() - start

    # Target: <100ms for 100 kids (was 372ms)
    assert duration < 0.100, f"Badge evaluation too slow: {duration:.3f}s"
```

---

## Phase 1a: Test Coverage ✅ COMPLETE

**File**: `tests/test_badge_target_types_comprehensive.py`

### Test Matrix (All 17 Target Types)

| Category         | Target Type                           | Test Method                                                 | ✅  |
| ---------------- | ------------------------------------- | ----------------------------------------------------------- | --- |
| **Points (2)**   | POINTS                                | `test_points_target_accumulates_all_sources`                | ✅  |
|                  | POINTS_CHORES                         | `test_points_chores_target_only_counts_chore_points`        | ✅  |
| **Count (1)**    | CHORE_COUNT                           | `test_chore_count_target_accumulates_completions`           | ✅  |
| **Daily (9)**    | DAYS_SELECTED_CHORES                  | `test_days_selected_chores_requires_100_percent`            | ✅  |
|                  | DAYS_80PCT_CHORES                     | `test_days_80pct_chores_accepts_partial_completion`         | ✅  |
|                  | DAYS_SELECTED_CHORES_NO_OVERDUE       | `test_days_selected_chores_no_overdue_checks_overdue_state` | ✅  |
|                  | DAYS_SELECTED_DUE_CHORES              | `test_days_selected_due_chores_only_counts_due_today`       | ✅  |
|                  | DAYS_80PCT_DUE_CHORES                 | `test_days_80pct_due_chores_combines_filters`               | ✅  |
|                  | DAYS_SELECTED_DUE_CHORES_NO_OVERDUE   | `test_days_selected_due_chores_no_overdue_triple_filter`    | ✅  |
|                  | DAYS_MIN_3_CHORES                     | `test_days_min_3_chores_requires_minimum_count`             | ✅  |
|                  | DAYS_MIN_5_CHORES                     | `test_days_min_5_chores_requires_five_completions`          | ✅  |
|                  | DAYS_MIN_7_CHORES                     | `test_days_min_7_chores_requires_seven_completions`         | ✅  |
| **Streak (5)**   | STREAK_SELECTED_CHORES                | `test_streak_selected_chores_tracks_consecutive_days`       | ✅  |
|                  | STREAK_80PCT_CHORES                   | `test_streak_80pct_chores_allows_partial_completion`        | ✅  |
|                  | STREAK_SELECTED_CHORES_NO_OVERDUE     | `test_streak_selected_chores_no_overdue_breaks_on_overdue`  | ✅  |
|                  | STREAK_80PCT_DUE_CHORES               | `test_streak_80pct_due_chores_only_counts_due_chores`       | ✅  |
|                  | STREAK_SELECTED_DUE_CHORES_NO_OVERDUE | `test_streak_selected_due_chores_no_overdue_triple_filter`  | ✅  |
| **Rollover (2)** | Day rollover (points)                 | `test_day_rollover_accumulates_points_to_cycle_count`       | ✅  |
|                  | Day rollover (days)                   | `test_day_rollover_increments_days_completed_count`         | ✅  |
| **Award (2)**    | Badge awarding                        | `test_badge_awarded_when_criteria_met`                      | ✅  |
|                  | No duplicate awards                   | `test_badge_not_awarded_twice`                              | ✅  |

**Total Tests**: 21 tests covering all badge evaluation logic

### Coverage Goals Achieved

✅ **Handler Coverage**: All 4 handlers tested (\_handle_badge_target_points, \_chore_count, \_daily_completion, \_streak)
✅ **Data Structure Validation**: All const.py field names verified
✅ **Day Rollover Logic**: Accumulation tested (cycle_count += today_value)
✅ **Threshold Crossing**: criteria_met calculation verified
✅ **Badge Awarding**: Award flow and duplicate prevention tested
✅ **Helper Integration**: Uses actual helper functions (get_today_chore_and_point_progress, get_today_chore_completion_progress)
✅ **Realistic Data**: Uses scenario_full (3 kids, 7 chores, 5 badges)

### Test Execution

```bash
# Run badge target type tests
python -m pytest tests/test_badge_target_types_comprehensive.py -v --tb=line

# Run all badge tests
python -m pytest tests/test_badge*.py -v
```

### Next Step

With comprehensive test coverage in place, we can now safely implement optimizations with confidence that regressions will be caught.

---

## Risk Assessment

| Risk                               | Mitigation                                    |
| ---------------------------------- | --------------------------------------------- |
| Cache stale during evaluation      | Cache built per-kid, discarded after          |
| Handler signature changes          | Optional cache parameter, backward compatible |
| Persist timing changes             | Keep final persist, only remove mid-loop ones |
| `days_completed` removal breaks UI | Verify dashboard usage before removing        |
| Breaking existing badge logic      | ✅ **21 tests prevent regressions**           |

---

## Approval Checklist

- [x] Data structures verified against actual code (Phase 0 complete)
- [x] Test coverage created (Phase 1a complete - 21 tests passing)
- [ ] Optimization 1 implemented (Pre-compute cache)
- [ ] Optimization 2 implemented (Cache kid chores)
- [ ] Optimization 3 implemented (Hoist today_iso)
- [ ] Optimization 4 implemented (Defer persist)
- [ ] Optimization 5 implemented (Prune days_completed)
- [ ] Performance validation (<100ms for 100 kids)
- [ ] Handler signatures compatible
- [ ] No breaking changes to existing tests
- [ ] Performance baseline established

---

## Badge Module Extraction Analysis

### Current State

**Badge processing in coordinator.py**:

- **Total lines**: 8,346 (coordinator.py)
- **Badge-related methods**: 22 methods
- **Badge evaluation core**: Lines 3952-4740 (788 lines)
- **Badge maintenance**: Lines 5331-5900 (570 lines)
- **Total badge logic**: ~1,570 lines (19% of coordinator)

**Key badge methods**:

```python
# Evaluation (lines 3952-4740)
_check_badges_for_kid()              # Main entry, 274 lines
_get_badge_in_scope_chores_list()    # Chore filtering, 42 lines
_handle_badge_target_points()        # Points handler, 48 lines
_handle_badge_target_chore_count()   # Count handler, 48 lines
_handle_badge_target_daily_completion() # Daily handler, 60 lines
_handle_badge_target_streak()        # Streak handler, 71 lines
_award_badge()                       # Award processing, 240 lines

# Maintenance (lines 5331-5900)
_manage_badge_maintenance()          # Non-cumulative badges, 266 lines
_sync_badge_progress_for_kid()       # Progress initialization, 304 lines
_manage_cumulative_badge_maintenance() # Cumulative badges

# CRUD Operations (scattered)
_create_badge(), _update_badge(), delete_badge_entity()
_update_badges_earned_for_kid()
_get_cumulative_badge_progress()
_recalculate_all_badges()
```

### Recommendation: ⚠️ **DEFER MODULE EXTRACTION**

**Rationale**:

1. **Optimization Priority**: Performance optimization has minimal risk with comprehensive test coverage (21 tests). Module extraction is a major refactor.
2. **Circular Dependency Risk**: Badge logic depends heavily on coordinator state (`self.kids_data`, `self.chores_data`, `self.badges_data`, notification methods).
3. **Testing Overhead**: Module extraction requires updating 21+ tests plus existing badge tests to mock new module boundaries.
4. **No Performance Gain**: Splitting code into modules doesn't improve runtime performance - optimization does.

**Proposed Approach**:

1. **Phase 1 (Current)**: Implement 5 optimizations within coordinator.py
2. **Phase 2 (Validate)**: Measure performance gains, validate test coverage
3. **Phase 3 (Consider)**: If coordinator becomes unmaintainable (>12K lines), create `badge_processor.py`:

   ```python
   # Future structure if needed:
   class BadgeProcessor:
       def __init__(self, coordinator):
           self.coordinator = coordinator
           self.kids_data = coordinator.kids_data
           self.badges_data = coordinator.badges_data
           self.chores_data = coordinator.chores_data

       def check_badges_for_kid(self, kid_id: str):
           # Badge evaluation logic

       def manage_badge_maintenance(self, kid_id: str):
           # Badge maintenance logic
   ```

**Alternative: Inline Optimization Benefits**:

- ✅ No test updates required
- ✅ No import refactoring
- ✅ No circular dependency issues
- ✅ Direct access to coordinator state
- ✅ Easier to review changes (single file)
- ✅ Can still add helper classes (e.g., `KidDailyStatsCache`) without module split

**Conclusion**: Optimize first, extract later if maintenance burden justifies it. Current 19% of coordinator is manageable. Home Assistant core has coordinators with similar badge/entity processing inline.

- [ ] Rollback plan documented

---

_Proposal ready for implementation upon approval._
