# KidsChores Performance Issues - Status & Action Items

**Last Updated**: December 23, 2025 - 16:45 UTC (Debounce optimization phase complete - immediate=True as default, race conditions fixed)
**Purpose**: Central tracking of all identified performance concerns and their resolution status

---

## 📊 **Executive Summary**

| Category                    | Issues Identified     | Resolved | In Progress | Deferred |
| --------------------------- | --------------------- | -------- | ----------- | -------- |
| **Coordinator Performance** | 5 critical + 3 medium | 1 ✅     | 0           | 7        |
| **Sensor Performance**      | 8 critical hotspots   | 8 ✅     | 0           | 0        |
| **Performance Testing**     | Baseline capture      | 3 ✅     | 0           | 0        |
| **Badge Optimization**      | 5 proposed changes    | 1 ✅     | 0           | 0        |
| **Persistence Strategy**    | Debounce vs Immediate | 1 ✅     | 0           | 0        |
| **Total**                   | **22**                | **13**   | **0**       | **9**    |

**Status**: ✅ **COMPLETE - Spun off Parent Notification Concurrency as separate initiative**

**Final Status**:
- ✅ Persistence strategy complete (immediate=True as default)
- ✅ Performance baselines captured and validated
- ✅ Badge optimization phase complete
- ✅ Sensor performance fully optimized
- 📋 Remaining coordinator items deferred (see below)
- 🎯 Parent Notification Concurrency spun off to [PARENT_NOTIFICATION_CONCURRENCY_PLAN.md](PARENT_NOTIFICATION_CONCURRENCY_PLAN.md)

**Latest Completion - Persistence Strategy Phase (Dec 23, 2025)**:

**Strategic Decision**: Changed `_persist()` default from `immediate=False` to `immediate=True`

- ✅ Fixed race condition: Config entry reload no longer reads stale storage
- ✅ Eliminated test hangs: Debounce delays (5s per entity creation) removed
- ✅ Improved performance: 548 tests now complete in 18.96s (vs. timeout/hanging)
- ✅ Enhanced code clarity: Immediate persistence is the default, correct approach
- ✅ Normalized options_flow.py: All 9 entity creations use `_persist()` without explicit parameter
- ✅ Improved docstring: Comprehensive explanation of immediate=True strategy

**Key Findings**:

1. **Debouncing Unnecessary**: High-frequency operations (badge checking, overdue scanning) don't call `_persist()` directly
2. **Race Condition Critical**: Config entry reload timing (0.1s) vs persist debounce (5s) caused lost data in tests
3. **Immediate Default Correct**:
   - Ensures data consistency (always safe)
   - Eliminates hidden delays from tests
   - Simplifies mental model (no surprise timing behavior)
   - Backward compatible (can still use `immediate=False` if profiling shows need)
4. **Test Performance Impact**: 5-second debounce delays accumulate across 548 tests, causing timeouts
5. **Analysis Result**: Comprehensive code review found no high-frequency batch operations that would benefit from debouncing

**Accomplishments**:

- ✅ Created `test_true_performance_baseline.py` with PERF operation capture
- ✅ Built `PerfCapture` class to intercept PERF log messages
- ✅ Stress test dataset created (`testdata_scenario_performance_stress.yaml` - 100 kids, 55 chores, 18 badges)
- ✅ Enhanced baseline test with repeated/cumulative measurements for microsecond precision
- ✅ Captured 3-kid scenario baseline: overdue scanning, badge checking, persistence timing
- ✅ Captured 100-kid stress test baseline: scale performance validation (STRESS TEST NOW FULLY PASSING)
- ✅ All tests passing with performance assertions in place (531 passed, 10 skipped)
- ✅ Identified badge checking as primary bottleneck (372ms for 100 kids)
- ✅ Fixed `BadgeTracker._get_badge_progress_safe()` timing issue preventing stress test execution
- ✅ Validated performance infrastructure ready for Phase 1 optimization work

**Baseline Metrics Captured**:

**Small Scale (3 kids, 7 chores, 6 badges)**:

- Overdue checking: **0.219ms avg** (10 iterations), **10.45µs/operation**
- Badge checking: **4.190ms per kid**, **698.35µs per badge check**
- Persistence queue: **146.8µs** (async save)
- All measurements precise enough to track 2-3x optimization improvements

**Stress Test (100 kids, 55 chores, 18 badges)** ✅ **NEW**:

- Overdue checking: **1.0ms** for 5,500 operations (**0.18µs/operation** - 58x faster per-op at scale!)
- Badge checking: **372ms total** (**3.7ms per kid** - consistent with small scale baseline)
- Sequential badge sample (10 kids): **34ms** (3.4ms per kid)
- Full data persistence: **9.258s** for 100-kid dataset
- Coordinator refresh: **3ms**
- Memory usage: **198.1MB total** (2,028.5KB per kid)
- Total entities created: 6 (system-level only)

**Key Findings**:

1. ✅ Badge checking scales linearly and consistently (3.7-4.2ms per kid regardless of scale)
2. ✅ Overdue checking is extremely efficient at scale (sub-microsecond per operation)
3. 🔥 **Badge checking is PRIMARY BOTTLENECK** (372ms for 100 kids vs 1ms for overdue scan)
4. ✅ Memory usage reasonable (2MB per kid)
5. ⚠️ Persistence time high but expected for large dataset writes

**Optimization Priority** (based on stress test data + learnings):

1. ~~**Badge checking optimization**~~ - Phase 1 complete, limited gains without algorithm changes
2. ~~**Storage write batching**~~ (Issue #2) - REJECTED (race condition risk outweighs I/O benefit)
3. ~~**Decouple overdue scan**~~ (Issue #1) - LOW ROI (1ms overhead, negligible impact)
4. **Parent notification concurrency** (Issue #5) - MEDIUM ROI, 2-3 hour effort (UX improvement)
5. **Entity registry cleanup** (Issue #3) - MEDIUM ROI, 8-12 hour effort (scalability)
6. **Badge reference updates** (Issue #6) - LOW priority (monitor real usage first)
7. **Minor cleanups** (Issues #7, #8) - Nice-to-have (15-30 min each)

**Next Action**: Implement Parent Notification Concurrency (Issue #5) - quick win for UX improvement

---

## 💾 **Persistence Strategy - Complete (Debounce Optimization Decision)**

**Status**: ✅ COMPLETE - Strategic decision made and implemented

### Problem Discovered

During Phase 2 implementation (debounced persist), a critical race condition emerged:

1. **Config Flow**: Entity creation called `coordinator._persist()` (debounced 5s delay)
2. **Reload Logic**: Config entry reload triggered after 0.1s wait
3. **Race**: Reload read storage BEFORE new entity was persisted
4. **Result**: New entities missing from reloaded coordinator → test failures

**Impact**: Tests timing out or hanging due to accumulated 5-second debounce delays

### Strategic Decision: Immediate=True as Default

**Changed**: `def _persist(self, immediate: bool = False):` → `def _persist(self, immediate: bool = True):`

**Rationale**:

1. **Safety First**: Immediate persistence ensures data consistency, eliminates race conditions
2. **No Hidden Delays**: Tests and operations complete predictably without surprise timing behavior
3. **Simpler Model**: Developers don't need to remember when to add `immediate=True`
4. **Backward Compatible**: Can still use `immediate=False` if profiling identifies high-frequency batch operations
5. **Supported by Analysis**: Comprehensive review found no high-frequency batch operations that would benefit from debouncing

### Findings from Code Analysis

**High-Frequency Operations** (Don't call `_persist()` directly):

- `_check_badges_for_kid()` - Evaluates badges, doesn't persist
- `_check_achievements_for_kid()` - Checks achievements, doesn't persist
- `_check_challenges_for_kid()` - Checks challenges, doesn't persist
- Overdue scanning - Reads only, doesn't persist

**Lower-Frequency Update Methods** (Call `_persist()` once):

- `update_kid_entity()`, `update_parent_entity()`, etc. - One persist per call
- Update/delete operations - Not in loops
- Entity creation - One persist per new entity

**Final Persist Timing**:

- Happens once per `coordinator.async_refresh()` cycle
- No cascading delays from multiple debounced operations

**Conclusion**: Debouncing optimization doesn't address any real bottleneck. Immediate=True is correct.

### Results

**Test Performance**:

- Before: Tests timing out (>300s) or hanging
- After: 548 tests pass in 18.96 seconds
- Per-test average: ~35ms

**Code Quality**:

- All 9 entity creation calls in options_flow.py normalized to `coordinator._persist()`
- Docstring enhanced with comprehensive explanation
- Linting: 9.65/10 (maintained)
- All tests passing: 548 passed, 10 skipped

**Fixed Issues**:

- ✅ Race condition between persist and reload
- ✅ Test hanging/timeout issues
- ✅ Hidden timing delays in operations

---

## 🎯 **Badge Optimization - Phase 1 Complete**

**Status**: ✅ COMPLETE - Performance baseline restored after discovering false optimization

### Journey Summary

**Baseline**: 372ms for 100 kids × 18 badges (3.7ms per kid)

**Optimizations Attempted**:

1. ❌ Pre-compute KidDailyStatsCache - **REVERTED** (caused 62% regression)
2. ✅ Cache kid-assigned chores - **KEPT** (minimal but harmless)
3. ✅ Hoist today_local_iso - **KEPT** (minimal but harmless)
4. ✅ Defer persist operations - **KEPT** (correct optimization)
5. ❌ Prune days_completed dict - **REVERTED** (tied to cache)

**Performance Results**:

- After all optimizations: 600ms (62% WORSE!)
- After reverting Opt 1: 372ms (baseline restored)
- Net improvement: 0% (but valuable lessons learned!)

**Root Cause Analysis**:

- **Baseline**: Helpers called on-demand when specific badge handlers needed them
- **"Optimized"**: Helpers always called upfront for ALL kids (always-on execution)
- **Problem**: No work reduction + cache construction overhead = worse performance

**Key Findings**:

1. 🔥 Cache construction has cost (dataclass creation, memory allocation, parameter passing)
2. 🔥 On-demand execution beats always-on caching when not all code paths need data
3. 🔥 Operation count reduction ≠ actual performance improvement
4. ✅ Test coverage critical (27 badge tests caught all functional issues)
5. ✅ Baseline validation essential (stress test revealed regression)

**Final State**:

- Performance: 372ms (exact baseline)
- Tests: 552 passed, 10 skipped
- Linting: 9.65/10
- Documentation: Updated with lessons learned

**Recommendation**: Badge evaluation is already efficient (3.7ms per kid). Focus optimization efforts on higher-impact areas:

- Storage I/O batching (90%+ reduction potential)
- Overdue scan decoupling (event loop relief)
- Parent notification concurrency (UX improvement)

**Reference**: [BADGE_OPTIMIZATION_PROPOSAL.md](BADGE_OPTIMIZATION_PROPOSAL.md)

---

## ✅ **RESOLVED - Sensor Performance Issues**

**Status**: COMPLETE (documented in [docs/completed/SENSOR_CLEANUP_AND_PERFORMANCE.md](completed/SENSOR_CLEANUP_AND_PERFORMANCE.md))

### Issues Fixed:

1. ✅ **DashboardHelperSensor**: Replaced 8 O(n) entity registry iterations with O(1) lookups
2. ✅ **KidChoreStatusSensor**: Replaced 3 O(n) lookups per chore with O(1) `async_get_entity_id()`
3. ✅ **KidRewardStatusSensor**: Replaced 3 O(n) lookups per reward with O(1) pattern
4. ✅ **KidPenaltyAppliedSensor**: Replaced O(n) lookup with O(1) pattern
5. ✅ **KidBonusAppliedSensor**: Replaced O(n) lookup with O(1) pattern
6. ✅ **SystemPendingChoreApprovalsSensor**: Already using efficient O(1) pattern
7. ✅ **SystemPendingRewardApprovalsSensor**: Already using efficient O(1) pattern
8. ✅ **All status sensors**: Migrated to `entity_registry.async_get_entity_id()` pattern

**Impact**: Eliminated 1,600+ unnecessary entity registry iterations for installations with 200+ entities

---

## 📋 **DEFERRED - Coordinator Performance Issues**

**Status**: ✅ Analyzed and catalogued. Remaining items deferred for future optimization phase.

**Spun Off Initiative**: Parent Notification Concurrency (Issue #5) has been moved to a separate effort:
- **Document**: [PARENT_NOTIFICATION_CONCURRENCY_PLAN.md](PARENT_NOTIFICATION_CONCURRENCY_PLAN.md)
- **Status**: Design complete, awaiting implementation approval
- **Scope**: Concurrent parent notifications + approval debouncing + claim-specific notifications
- **Estimated Effort**: 2-2.5 hours for phases 1-2, plus broader claims architecture review

**Documentation**: [docs/in-process/coordinator-remediation-supporting/COORDINATOR_CODE_REVIEW.md](in-process/coordinator-remediation-supporting/COORDINATOR_CODE_REVIEW.md#performance-analysis--optimization-opportunities)

### 🔴 **Critical Issues (High Priority)**

#### 1. Periodic Update Performs Full Overdue Scan

- **Location**: coordinator.py lines 842-855 (update), 7679-7878 (scan)
- **Problem**: O(#chores × #kids) scan runs every update interval
- **Impact**: Can monopolize event loop as scale increases
- **Status**: 📋 **DEFERRED** (catalogued, ready for future phase)

**Recommended Solution**:

```python
# Decouple from DataUpdateCoordinator
# Use async_track_time_interval with fixed 1-hour interval
async def async_setup_entry(...):
    cancel_overdue = async_track_time_interval(
        hass, coordinator._check_overdue_chores, timedelta(hours=1)
    )
    entry.async_on_unload(cancel_overdue)
```

**Effort**: 4-6 hours
**Priority**: HIGH - Should be addressed before v4.3 release

---

#### 2. Storage Writes Too Frequent

- **Location**: 52 `_persist()` call sites throughout coordinator.py
- **Problem**: Immediate JSON serialization + file write on every mutation
- **Impact**: Would reduce I/O by 90%+ with batching, but introduces race condition risk
- **Status**: ✅ **ANALYZED & REJECTED** (Decided against in Persistence Strategy phase)

**Why Rejected**:

Our Persistence Strategy phase analysis revealed that debounced writes create unacceptable race conditions:

- Config entry reload timing (0.1s) vs persist debounce (5s) causes lost data
- New entities missing from reloaded coordinator when persist hasn't completed
- Test hangs and timeouts from accumulated 5-second delays
- Risk of data inconsistency outweighs I/O optimization benefits

**Decision**: Keep immediate=True as default for safety and correctness

**Note**: Could be revisited if:

1. A safer batching strategy is designed (e.g., batch within same refresh cycle only)
2. Reload logic is refactored to wait for pending persists
3. Real-world performance monitoring shows I/O saturation as actual bottleneck

**Effort**: 6-8 hours (if reconsidered with safety improvements)
**Priority**: LOW (REJECTED) - Safety > I/O optimization

---

#### 3. Entity Registry Full Scans with O(#entities × #chores) Parsing

- **Location**: coordinator.py lines 1198-1211, 1237-1291
- **Problem**: Nested loops in orphan cleanup: O(#entities × #chores)
- **Impact**: Heavy CPU work stalls event loop during migrations/cleanup
- **Status**: 📋 **DEFERRED** (catalogued, ready for future phase)

**Recommended Solution**:

```python
# Use predictable unique_id format for O(1) parsing
# Format: {domain}_{kid_internal_id}_{entity_type}_{chore_internal_id}

def _parse_unique_id(unique_id: str) -> tuple[str, str, str, str] | None:
    """Parse unique_id into components."""
    parts = unique_id.split("_")
    if len(parts) >= 4:
        return parts[0], parts[1], parts[2], "_".join(parts[3:])
    return None

# Then in cleanup:
for entity in entity_registry.entities.values():
    if entity.platform != const.DOMAIN:
        continue
    parsed = _parse_unique_id(entity.unique_id)
    if parsed and parsed[1] == kid_id:  # O(1) check
        # Remove entity
```

**Effort**: 8-12 hours (includes migration for existing unique_ids)
**Priority**: HIGH - Critical for scalability

---

#### 4. Reminder Implementation Uses Long-Lived Sleeping Tasks

- **Location**: coordinator.py lines 8870-8935 (`remind_in_minutes()`)
- **Problem**: `asyncio.sleep(minutes * 60)` creates long-lived tasks (30+ minutes)
- **Impact**: Tasks may outlive config entry unload, no cleanup mechanism
- **Status**: ❌ **NOT ADDRESSED**

**Recommended Solution**:

```python
# Use Home Assistant scheduler with proper cleanup
from homeassistant.helpers.event import async_call_later

class KidsChoresDataCoordinator:
    def __init__(self, ...):
        self._reminder_handles: dict[tuple[str, str], Callable] = {}

    def _schedule_reminder(self, kid_id: str, entity_id: str, delay_minutes: int):
        """Schedule reminder with deduplication."""
        key = (kid_id, entity_id)

        # Cancel existing reminder
        if key in self._reminder_handles:
            self._reminder_handles[key]()

        # Schedule new reminder
        async def _send_reminder():
            await self._notify_kid_translated(kid_id, ...)
            self._reminder_handles.pop(key, None)

        cancel = async_call_later(self.hass, delay_minutes * 60, _send_reminder)
        self._reminder_handles[key] = cancel

        # Register cleanup
        self.config_entry.async_on_unload(lambda: cancel())
```

**Effort**: 4-6 hours
**Priority**: HIGH - Anti-pattern in HA integrations

---

#### 5. Parent Notifications Sent Sequentially

- **Location**: coordinator.py lines 8790-8869 (`_notify_parents()`)
- **Problem**: Sequential `await` for each parent notification
- **Impact**: Makes approval flows feel slow, scales poorly with number of parents
- **Status**: ❌ **NOT ADDRESSED**

**Recommended Solution**:

```python
async def _notify_parents(self, ...):
    """Send notifications concurrently with isolated failures."""
    tasks = []
    for parent_id in parent_ids:
        tasks.append(self._send_notification(parent_id, ...))

    # Send concurrently, isolate failures
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Log any failures
    for parent_id, result in zip(parent_ids, results):
        if isinstance(result, Exception):
            const.LOGGER.warning("Failed to notify parent %s: %s", parent_id, result)
```

**Effort**: 2-3 hours
**Priority**: MEDIUM-HIGH - UX improvement

---

### 🟠 **Medium Priority Issues**

#### 6. Badge Reference Updates Are Heavy and Repeated

- **Location**: coordinator.py lines 5710-5768, 5106-5125
- **Problem**: Full rebuild of badge references on every change
- **Complexity**: O(#kids × #chores + #badges × #kids × #chores)
- **Status**: ❌ **NOT ADDRESSED**

**Recommended Solution**: Incremental updates, cache scope lists

**Effort**: 12-16 hours
**Priority**: MEDIUM - Monitor in real usage first

---

#### 7. Unnecessary Work Inside Overdue Check

- **Location**: coordinator.py lines 7706-7710
- **Problem**: Sets `kid_info` but doesn't use it
- **Status**: ❌ **NOT ADDRESSED**

**Recommended Solution**: Remove unused assignment or document intent

**Effort**: 15 minutes
**Priority**: LOW - Cleanup item

---

#### 8. Potential Wasted Auth Lookup

- **Location**: coordinator.py lines 8685-8778 (`send_kc_notification()`)
- **Problem**: Calls `await hass.auth.async_get_user(user_id)` but doesn't use result
- **Status**: ❌ **NOT ADDRESSED**

**Recommended Solution**: Remove if not needed, or use result

**Effort**: 30 minutes
**Priority**: LOW - Minor optimization

---

## 📋 **Recommended Action Plan**

### Phase 0: Baseline Performance Measurement (2-3 hours)

**Target**: IMMEDIATE - Before any optimization work
**Status**: ✅ **COMPLETE** - Enhanced precision baseline captured successfully

**Completed**:

- ✅ Created `testdata_scenario_performance_stress.yaml` (100 kids, 25 parents, 500+ chores, 18 badges)
- ✅ Added performance instrumentation to 6 key coordinator methods with PERF: log prefix
- ✅ Created comprehensive test suite (`test_true_performance_baseline.py`) with 3 test functions
- ✅ Enhanced `test_full_scenario_performance_comprehensive` with:
  - **Repeated measurements** (10 iterations) for stable averages
  - **Cumulative measurements** (all kids summed) for larger numbers
  - **Microsecond precision** (µs reporting) for fine-grained tracking
  - **Performance assertions** with generous limits to catch regressions
- ✅ All tests passing with linting clean

**Baseline Metrics Captured** (Full Scenario: 3 kids, 7 chores, 6 badges):

| Operation            | Measurement                 | Per-Operation Cost | Notes                             |
| -------------------- | --------------------------- | ------------------ | --------------------------------- |
| **Overdue Checking** | 0.219ms avg (10 iterations) | **10.45µs/op**     | 21 operations (7 chores × 3 kids) |
|                      | Range: 0.163ms - 0.622ms    |                    | Variance tracked for stability    |
| **Badge Checking**   | 12.570ms total (cumulative) | **4.190ms/kid**    | 3 kids, 6 badges each             |
|                      |                             | **698.35µs/badge** | 18 total badge checks             |
| **Persistence**      | Queue time: 146.8µs         |                    | Async save (non-blocking)         |

**Performance Assertions** (generous limits allow optimization tracking):

- ✅ Overdue scanning: <50ms (currently ~0.2ms → **250x headroom**)
- ✅ Badge checking: <1000ms (currently ~12.5ms → **80x headroom**)
- ✅ Persistence queueing: <5000µs (currently ~146µs → **34x headroom**)

**Why Precision Matters**:

- Previous measurements (0.000s, 0.004s) rounded to milliseconds - **insufficient to track optimizations**
- Enhanced approach provides:
  - **Repeated iterations** → stable averages immune to system noise
  - **Cumulative totals** → larger numbers easier to compare (12.57ms vs 5ms = clear 2.5x speedup)
  - **Microsecond precision** → tracks sub-millisecond improvements (698µs → 300µs = 2.3x speedup visible)

**Test Functions Created**:

1. `test_true_performance_baseline` - Empty scenario (baseline overhead)
2. `test_stress_dataset_true_performance` - 100 kids stress test (NOT YET EXECUTED - waiting for conftest.py badge_progress fix)
3. `test_full_scenario_performance_comprehensive` - ✅ **Enhanced with precision measurements** (BASELINE CAPTURED)

**Critical Success**: Test infrastructure now provides measurements precise enough to validate 2-3x optimization improvements. When caching reduces badge checking from 12.57ms to 5ms, the improvement will be clearly measurable.

**Next Steps**:

1. ✅ Execute stress test with 100 kids - **COMPLETE** (all 531 tests passing)
2. ✅ Document stress test baseline metrics - **COMPLETE** (372ms badge checking for 100 kids captured)
3. ➡️ **Begin Phase 1 optimizations with clear before/after metrics**

---

### Phase 1: Critical Performance Fixes (20-30 hours)

**Target**: Before v4.3 release
**Status**: ✅ **READY TO START** - Phase 0 baseline complete & validated, stress test passing, objective measurement data available

**Prerequisites**: ✅ Phase 0 baseline metrics captured and instrumentation validated
✅ All performance tests passing (531 passed, 10 skipped)
✅ Linting clean (ALL CHECKS PASSED)

**Performance Infrastructure Validated**:

- ✅ PERF: log message capture working correctly
- ✅ Microsecond precision measurements stable and repeatable
- ✅ Stress test dataset (100 kids) loads and executes without timeouts
- ✅ Badge progress initialization fixed and optimized

**Optimization Tasks** (in priority order):

1. ❌ Implement debounced storage saving (6-8 hours) - **Issue #2**
   - **Priority**: HIGH - Current measurements show async queuing working well, but can still benefit from debouncing at scale
2. ❌ Decouple overdue scanning from periodic updates (4-6 hours) - **Issue #1**
   - **Priority**: HIGH - Current scan is fast but will scale poorly with large datasets
3. ❌ Replace sleep-based reminders with HA scheduler (4-6 hours) - **Issue #4**
   - **Priority**: HIGH - Anti-pattern in HA integrations, needs cleanup
4. ❌ Parallelize parent notifications (2-3 hours) - **Issue #5**
   - **Priority**: MEDIUM-HIGH - Framework is in place to measure improvement
5. ⚠️ Fix unique_id parsing (defer to Phase 2 if time-constrained) - **Issue #3**
   - **Priority**: MEDIUM - Entity cleanup currently fast, but will be critical at scale

**Validation Approach**: Re-run `test_performance_baseline.py` after each fix to measure impact with PERF: logs

---

### Phase 2: Structural Improvements (8-16 hours)

**Target**: v4.4
**Status**: ❌ **NOT STARTED**

1. ❌ Implement predictable unique_id format with migration - **Issue #3**
2. ❌ Optimize badge reference updates - **Issue #6**
3. ❌ Clean up minor inefficiencies (#7, #8) - **Issues #7, #8**

**Validation**: Re-run Phase 0 test scenarios with full stress test data

---

### Phase 3: Performance Monitoring (ongoing)

**Target**: Post-v4.3
**Status**: ❌ **NOT STARTED**

1. ❌ Add performance metrics/logging
2. ❌ Monitor in production with typical family sizes
3. ❌ Validate optimization impact with real usage data

---

## 🔍 **Performance Measurement Strategy**

**Stress Test Dataset**: `tests/testdata_performance_stress.yaml`

- **Scale**: 100 kids, 25 parents, 500+ chores, 18 badges (8 cumulative + 10 periodic)
- **Expected Entity Count**: ~1,500 entities
- **Purpose**: Establish baseline metrics before optimization, validate improvements after

### Baseline Metrics to Capture (Phase 0)

Run Home Assistant with stress test data loaded and capture these metrics:

| Metric                                    | Measurement Method                                        | Expected Current           | Target After Optimization  |
| ----------------------------------------- | --------------------------------------------------------- | -------------------------- | -------------------------- |
| **Initial Load Time**                     | Time from config entry setup to first coordinator refresh | TBD                        | < 10 seconds               |
| **`_check_overdue_chores()` duration**    | Time to scan all kids/chores for overdue status           | TBD (est. 2-5s)            | < 100ms                    |
| **`_persist()` calls per chore approval** | Count storage writes during single approval flow          | TBD (est. 3-5)             | 1 (debounced)              |
| **Storage writes per minute**             | Monitor `.storage/` write frequency during active use     | TBD (est. 10-20)           | 1-2                        |
| **Pending reminder tasks**                | Count long-lived asyncio tasks for reminders              | TBD (est. 10-50)           | 0 (scheduler-based)        |
| **Parent notification latency**           | Time to send notifications to 25 parents                  | TBD (est. 7.5s sequential) | < 200ms total (concurrent) |
| **Entity registry scan duration**         | Time for orphan cleanup with 1,500 entities               | TBD (est. 5-10s)           | < 500ms                    |
| **Badge evaluation duration**             | Time to evaluate 18 badges for 100 kids                   | TBD (est. 1-3s)            | < 500ms                    |
| **Coordinator update cycle**              | Full periodic refresh with 1,500 entities                 | TBD (est. 3-8s)            | < 1s                       |

### How to Capture True Baseline Performance

**IMPORTANT**: The performance instrumentation has been validated with small test scenarios, but **true baseline metrics require the stress test dataset**:

1. **Load stress test data into dev Home Assistant**:

   ```bash
   # Manual process (Home Assistant UI):
   # Settings → Devices & Services → Add Integration → KidsChores
   # Choose "Restore from Backup" or use config flow
   # Load: tests/testdata_scenario_performance_stress.yaml
   # Expected: ~1,500 entities (100 kids × ~15 entities each)
   ```

2. **Enable debug logging** in `configuration.yaml`:

   ```yaml
   logger:
     default: warning
     logs:
       custom_components.kidschores: debug
   ```

3. **Run test scenarios with stress data and capture metrics**:

   - **Overdue scan**: Trigger coordinator refresh → measure O(500+ chores × 100 kids)
   - **Badge evaluation**: Run evaluation → measure 18 badges × 100 kids = 1,800 evaluations
   - **Parent notifications**: Approve chore → measure sequential notifications to 25 parents
   - **Entity cleanup**: Reload integration → measure scan of ~1,500 entities
   - **Storage operations**: Perform bulk approvals → measure persist frequency
   - **Bulk workflows**: Chain multiple claims/approvals → measure workflow scaling

4. **Filter logs for baseline data**:
   ```bash
   grep "PERF:" home-assistant.log
   ```

**Expected Stress Test Results** (to validate optimization impact):

- `_check_overdue_chores()`: Should show significant duration (500+ chores × 100 kids = 50,000+ operations)
- `_check_badges_for_kid()`: Should show scaling impact (18 badges × 100 kids with complex evaluations)
- `_notify_parents()`: Should show sequential latency (25 parents × notification time)
- `_remove_orphaned_kid_chore_entities()`: Should show entity scan overhead (~1,500 entities)
- `_persist()`: Should show call frequency during bulk operations

**Why Stress Test Matters**: Small test scenarios (~3 kids, 7 chores) show ~0.000s timing because operations complete too quickly. Real performance bottlenecks only appear at scale (100 kids, 500+ chores).

---

## 📚 **Related Documentation**

- **Sensor fixes**: [docs/completed/SENSOR_CLEANUP_AND_PERFORMANCE.md](completed/SENSOR_CLEANUP_AND_PERFORMANCE.md)
- **Coordinator review**: [docs/in-process/coordinator-remediation-supporting/COORDINATOR_CODE_REVIEW.md](in-process/coordinator-remediation-supporting/COORDINATOR_CODE_REVIEW.md)
- **Code standards**: [docs/CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md)
- **Architecture**: [docs/ARCHITECTURE.md](ARCHITECTURE.md)

---

## ❓ **Questions for Decision**

1. **Debounced saving**: Are you comfortable with 5-second delay before persistence? (HA can crash/restart during window)
2. **Unique_id migration**: Do you want to migrate existing installations to new format, or only apply to new entities?
3. **Overdue scan frequency**: Is 1-hour interval acceptable, or do you need configurable interval?
4. **Performance vs. complexity**: Which optimizations are must-have for v4.3 vs. nice-to-have for v4.4?

---

## 🎯 **CURRENT STATUS & NEXT ACTIONS**

### ✅ Phase 0 Achievement: Performance Measurement Infrastructure

**COMPLETE**: Comprehensive performance instrumentation successfully implemented and validated.

**What We Now Have**:

- **6 instrumented methods** with contextual timing data:
  - `_persist()`: Storage write frequency and async queue performance
  - `_check_overdue_chores()`: O(chores × kids) scan timing with operation counts
  - `_check_badges_for_kid()`: Per-kid badge evaluation with badge count context
  - `_notify_parents()`: Parent notification latency measurement framework
  - `_remove_orphaned_kid_chore_entities()`: Entity registry scan duration
  - `claim_chore()` & `approve_chore()`: Core workflow timing including point calculations
- **Comprehensive test suite**: `test_performance_baseline.py` exercises all instrumentation
- **Actionable metrics**: PERF: log entries provide operation counts, timing breakdowns, context
- **Validated approach**: All timing correctly captured, linting passed, tests working

**Critical Insights Captured**:

1. **Storage Pattern Works**: Async queuing shows ~0.000s timing, validating current implementation
2. **Badge Evaluation Scales**: ~0.001-0.003s per kid with 6 badges, linear scaling confirmed
3. **Workflow Timing**: Claim (~0.001s) vs Approve (~0.004s) including 10.0 points addition
4. **Measurement Infrastructure**: Consistently captures operation context for optimization decisions

### 🚀 Ready for Phase 1: Data-Driven Optimization

**Immediate Next Steps** (recommended priority order):

1. **Issue #2 - Debounced Storage** (6-8 hours)

   - **Evidence**: Have baseline timing for comparison (current async queue performance)
   - **Impact**: Will reduce I/O frequency during bulk operations
   - **Risk**: Low - well-understood HA pattern

2. **Issue #4 - Scheduler-based Reminders** (4-6 hours)

   - **Evidence**: Anti-pattern cleanup, no performance data needed
   - **Impact**: Proper Home Assistant integration patterns
   - **Risk**: Low - standard HA scheduler replacement

3. **Issue #1 - Decouple Overdue Scanning** (4-6 hours)

   - **Evidence**: Current scan shows 21 operations (7 chores × 3 kids) in ~0.000s
   - **Impact**: Will prevent event loop monopolization at scale
   - **Risk**: Medium - requires update coordinator changes

4. **Issue #5 - Parallel Notifications** (2-3 hours)
   - **Evidence**: Framework ready to measure sequential vs concurrent improvements
   - **Impact**: UX improvement for multi-parent households
   - **Risk**: Low - standard async pattern

### 🧪 Validation Strategy Ready

Each optimization can be validated using:

```bash
pytest tests/test_performance_baseline.py -v -s | grep "PERF:"
```

**Before/After Comparison**:

- Storage: Measure write frequency reduction
- Overdue: Measure scan duration at scale
- Notifications: Measure concurrent vs sequential timing
- Workflows: Ensure no regression in claim/approve performance

### 📋 Additional Test Coverage Confirmed

Beyond performance timing, we also have test coverage for critical functionality:

- **Pending Approvals**: `test_pending_approvals_consolidation.py` validates dashboard helper sensor functionality
- **Core Workflows**: Chore claim/approve flows work correctly with performance instrumentation
- **Data Integrity**: All operations maintain data consistency while being measured
- **Scale Testing**: Performance instrumentation ready for stress test scenarios (100 kids, 500+ chores)

**Confidence Level**: HIGH - Ready to begin optimization work with objective measurement capability.

---

## ✅ **VALIDATION: Critical Concerns Coverage Confirmed**

Our performance instrumentation and testing comprehensively addresses all critical concerns identified:

### 🎯 **Performance Issues - Full Coverage**

| Critical Issue                  | Instrumentation Status                                 | Test Coverage                         | Validation Ready                            |
| ------------------------------- | ------------------------------------------------------ | ------------------------------------- | ------------------------------------------- |
| **#1 Periodic Overdue Scan**    | ✅ `_check_overdue_chores()` timing + operation counts | ✅ Bulk scenario testing              | ✅ Ready to measure optimization impact     |
| **#2 Storage Write Frequency**  | ✅ `_persist()` timing + frequency tracking            | ✅ Bulk operations coverage           | ✅ Ready to measure debouncing benefit      |
| **#3 Entity Registry Scans**    | ✅ `_remove_orphaned_kid_chore_entities()` timing      | ✅ Entity cleanup testing             | ✅ Ready to measure parsing optimization    |
| **#4 Sleep-based Reminders**    | ✅ Architecture review documented                      | ✅ Pattern identified for replacement | ✅ Ready for scheduler implementation       |
| **#5 Sequential Notifications** | ✅ `_notify_parents()` timing framework                | ✅ Multi-parent scenario ready        | ✅ Ready to measure concurrent improvements |

### 🧪 **Test Infrastructure - Complete Coverage**

| Testing Need              | Implementation                            | Status       | Validation Capability                                 |
| ------------------------- | ----------------------------------------- | ------------ | ----------------------------------------------------- |
| **Baseline Measurement**  | `test_performance_baseline.py`            | ✅ Complete  | All 6 methods instrumented with context               |
| **Bulk Operations**       | 8 test scenarios in baseline test         | ✅ Complete  | Measures claim/approve workflows end-to-end           |
| **Data Integrity**        | Core functionality tests                  | ✅ Complete  | Ensures performance changes don't break logic         |
| **Dashboard Integration** | `test_pending_approvals_consolidation.py` | ✅ Complete  | Validates UI data flows work with performance changes |
| **Scale Testing Ready**   | `testdata_performance_stress.yaml`        | ✅ Available | 100 kids, 500+ chores for stress testing              |

### 📊 **Optimization Readiness - All Systems Go**

**What We Can Measure with Stress Test Dataset**:

- ✅ **Before/After Performance**: Each optimization validated objectively with 100 kids, 500+ chores
- ✅ **Operation Context**: Timing includes massive entity counts (1,500+), operation counts (50,000+), workflow stages
- ✅ **Scale Impact**: True performance bottlenecks revealed (O(chores × kids) = 50,000 operations)
- ✅ **Functionality Preservation**: Core workflows tested to ensure no regression during bulk operations
- ✅ **Real-World Performance**: Parent notifications to 25 parents, badge evaluation for 100 kids × 18 badges

**What We Can Optimize Confidently**:

1. **Storage Patterns**: Stress test will reveal true persist() call frequency during bulk operations
2. **Scanning Performance**: O(chores × kids) will show real duration with 500+ chores × 100 kids
3. **Notification Latency**: Sequential vs concurrent comparison with 25 parent notifications
4. **Architecture Patterns**: Anti-pattern impact clear with long-lived reminder tasks at scale
5. **Entity Management**: Entity scan performance with ~1,500 entities will show optimization value

**Confidence Assessment**: **HIGH** - Comprehensive instrumentation in place and validated. **Ready for stress test baseline capture** using 100 kids, 25 parents, 500+ chores dataset to reveal true performance characteristics before optimization.

---

## 🏁 **SUMMARY: Ready for Production Optimization**

**Phase 0 Achievement**: Successfully implemented and validated comprehensive performance measurement infrastructure.

**Key Success Metrics**:

- ✅ **6 critical methods** instrumented with contextual timing data
- ✅ **Instrumentation validated** with test scenarios - all PERF: logs working correctly
- ✅ **Actionable insights** available via PERF: log filtering
- ✅ **Optimization readiness** confirmed for all 5 critical issues
- ✅ **Data integrity** preserved through all measurement additions

**Next Required Step**: **Execute comprehensive performance baseline capture** using stress test dataset (100 kids, 25 parents, 500+ chores) to establish optimization targets.

---

## 🧪 **Test Infrastructure Summary**

### Active Performance Test File

**`tests/test_true_performance_baseline.py`** - Comprehensive performance measurement suite

**Test Functions**:

1. `test_true_performance_baseline()` - Minimal overhead baseline (empty config entry)

   - Measures integration setup, entity/device registry operations
   - Captures PERF operations: `_check_overdue_chores`, `_check_badges_for_kid`, `_persist`
   - Uses `mock_config_entry` fixture (0 kids, 0 chores)

2. `test_stress_dataset_true_performance()` - Performance at scale
   - Uses `scenario_stress` fixture (100 kids, 25 parents, 500+ chores, 18 badges)
   - Expected ~1,500+ entities created
   - Comprehensive timing: overdue checking, badge processing, persistence, coordinator refresh
   - Per-kid and per-operation metrics calculated

**Data Files**:

- `testdata_scenario_performance_stress.yaml` - 100 kids stress test dataset (37KB)
- `testdata_scenario_full.yaml` - 3 kids baseline (Stârblüm family)
- `testdata_scenario_medium.yaml` - 2 kids
- `testdata_scenario_minimal.yaml` - 1 kid

**How to Run**:

```bash
# Comprehensive baseline (empty dataset)
pytest tests/test_true_performance_baseline.py::test_true_performance_baseline -v -s

# Stress test (100 kids)
pytest tests/test_true_performance_baseline.py::test_stress_dataset_true_performance -v -s
```

**What Gets Measured**:

- ✅ Full integration setup time
- ✅ Entity/device registry operations
- ✅ PERF instrumented operations with call counts and totals
- ✅ Memory usage during operations
- ✅ Sequential vs concurrent badge processing comparison
- ✅ Per-kid and per-entity performance metrics

**Ready for Phase 1**: Performance measurement infrastructure complete. True baseline capture with stress dataset will provide the objective data needed to prioritize and validate optimizations.

---

## 🎯 **Immediate Next Steps (Recommended Order)**

### Step 1: Execute Stress Test Baseline ⏱️ **15 minutes**

**Purpose**: Capture performance metrics at scale (100 kids) to establish true baseline

**Action**:

```bash
# Execute stress test (will fail until badge_progress fix applied to conftest.py)
cd /workspaces/kidschores-ha
pytest tests/test_true_performance_baseline.py::test_stress_dataset_true_performance -v -s
```

**Expected Outcome**:

- Overdue checking: ~20-30ms for 5,500 operations (500 chores × 100 kids)
- Badge checking: ~400-500ms cumulative for 100 kids (1,800 badge checks)
- Persistence: <500µs queue time
- Memory usage: ~50-100MB for 100 kids

**Blocker**: Requires `badge_progress: {}` initialization fix in `conftest.py` create_mock_kid_data() (already identified)

---

### Step 2: Begin Phase 1 Critical Fixes 🔧 **4-6 hours**

**Priority Order** (based on baseline metrics):

#### 2.1: Implement Debounced Storage (6-8 hours)

**Why First**: Current measurements show ~146µs queue time, but frequency is the real issue

- **Pattern**: See Issue #2 recommended solution
- **Validation**: Re-run full scenario test, expect <10 `_persist()` calls vs current 52+ call sites
- **Impact**: Reduces disk I/O by 80-90%, improves overall responsiveness

#### 2.2: Decouple Overdue Scanning (4-6 hours)

**Why Second**: Currently fast (0.219ms) but couples to coordinator refresh

- **Pattern**: Use `async_track_time_interval` with 1-hour fixed interval
- **Validation**: Confirm overdue scan no longer triggered by periodic update
- **Impact**: Event loop no longer blocked by O(chores × kids) scan during updates

#### 2.3: Replace Sleep-Based Reminders (4-6 hours)

**Why Third**: Anti-pattern cleanup, prevents task leaks

- **Pattern**: Use `async_call_later` with proper cleanup registration
- **Validation**: Inspect task list, confirm no long-lived sleep tasks
- **Impact**: Proper cleanup on config entry unload, no task orphans

#### 2.4: Parallelize Parent Notifications (2-3 hours)

**Why Fourth**: Quick win for UX improvement

- **Pattern**: Use `asyncio.gather(*tasks, return_exceptions=True)`
- **Validation**: Re-run with 25 parents, measure <200ms total vs previous sequential timing
- **Impact**: Makes approval flows feel instant even with many parents

---

### Step 3: Document Optimization Results 📝 **1 hour**

After each optimization:

1. Re-run `test_full_scenario_performance_comprehensive`
2. Compare new metrics vs baseline captured in Phase 0
3. Update this plan with before/after measurements
4. Calculate and document improvement percentages (e.g., "2.5x faster badge checking")

---

### Step 4: Validate Phase 1 Complete ✅ **30 minutes**

**Checklist**:

- [ ] Debounced storage: <10 writes per typical workflow (vs 52+ call sites)
- [ ] Overdue scanning: Decoupled from coordinator update cycle
- [ ] Reminders: Zero long-lived asyncio.sleep tasks
- [ ] Parent notifications: <200ms for 25 parents (vs sequential ~7.5s)
- [ ] All tests passing with new patterns
- [ ] Linting clean (./utils/quick_lint.sh --fix)

**Outcome**: Phase 1 complete, ready to move to Phase 2 structural improvements or release v4.3 with performance wins

---

## 📊 **Success Metrics**

### Phase 0 Success Criteria ✅ **ACHIEVED**

- [x] Performance instrumentation validated and working
- [x] Baseline metrics captured with microsecond precision
- [x] Test infrastructure can measure 2-3x optimization improvements
- [x] All measurements repeatable and stable (10 iterations show consistent results)

### Phase 1 Success Criteria (Target Goals)

- [ ] Storage writes reduced by 80%+ (from 52+ call sites to <10 effective writes)
- [ ] Overdue scanning decoupled (no longer runs on coordinator update)
- [ ] Zero long-lived reminder tasks (proper HA scheduler pattern)
- [ ] Parent notifications <200ms for 25 parents (previously would be ~7.5s sequential)
- [ ] All optimizations validated with before/after metrics from test suite

### Phase 2 Success Criteria (Future)

- [ ] Entity cleanup <500ms with 1,500 entities (via predictable unique_id parsing)
- [ ] Badge reference updates optimized (incremental vs full rebuild)
- [ ] Minor inefficiencies cleaned up (issues #7, #8)

**Status Legend**:

- ✅ COMPLETE - Implementation done and tested
- 🚧 READY TO START - Prerequisites complete, can begin immediately
- 🔄 IN PROGRESS - Work started but not finished
- ❌ NOT ADDRESSED - Identified but not started
- ⚠️ DEFERRED - Intentionally postponed
