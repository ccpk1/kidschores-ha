# KidsChores Performance Issues - Status & Action Items

**Last Updated**: December 23, 2025  
**Purpose**: Central tracking of all identified performance concerns and their resolution status

---

## 📊 **Executive Summary**

| Category | Issues Identified | Resolved | In Progress | Not Started |
|----------|-------------------|----------|-------------|-------------|
| **Coordinator Performance** | 5 critical + 3 medium | 0 | 0 | 8 |
| **Sensor Performance** | 8 critical hotspots | 8 ✅ | 0 | 0 |
| **Total** | **16** | **8** | **0** | **8** |

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

## ⚠️ **UNRESOLVED - Coordinator Performance Issues**

**Documentation**: [docs/in-process/coordinator-remediation-supporting/COORDINATOR_CODE_REVIEW.md](in-process/coordinator-remediation-supporting/COORDINATOR_CODE_REVIEW.md#performance-analysis--optimization-opportunities)

### 🔴 **Critical Issues (High Priority)**

#### 1. Periodic Update Performs Full Overdue Scan
- **Location**: coordinator.py lines 842-855 (update), 7679-7878 (scan)
- **Problem**: O(#chores × #kids) scan runs every update interval
- **Impact**: Can monopolize event loop as scale increases
- **Status**: ❌ **NOT ADDRESSED**

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
- **Impact**: Saturates disk I/O, especially in badge evaluation loops (lines 4970-5060)
- **Status**: ❌ **NOT ADDRESSED**

**Recommended Solution**:
```python
# Implement debounced saving pattern
from homeassistant.helpers.storage import Store

self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
self._save_task = None

async def _persist_debounced(self):
    """Save with 5-second debounce."""
    if self._save_task:
        self._save_task.cancel()
    
    async def _delayed_save():
        await asyncio.sleep(5)
        await self._persist()
    
    self._save_task = hass.async_create_task(_delayed_save())
```

**Effort**: 6-8 hours  
**Priority**: HIGH - Reduces I/O by 90%+ in typical usage

---

#### 3. Entity Registry Full Scans with O(#entities × #chores) Parsing
- **Location**: coordinator.py lines 1198-1211, 1237-1291
- **Problem**: Nested loops in orphan cleanup: O(#entities × #chores)
- **Impact**: Heavy CPU work stalls event loop during migrations/cleanup
- **Status**: ❌ **NOT ADDRESSED**

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

### Phase 1: Critical Performance Fixes (20-30 hours)
**Target**: Before v4.3 release

1. ✅ Implement debounced storage saving (6-8 hours)
2. ✅ Decouple overdue scanning from periodic updates (4-6 hours)
3. ✅ Replace sleep-based reminders with HA scheduler (4-6 hours)
4. ✅ Parallelize parent notifications (2-3 hours)
5. ⚠️ Fix unique_id parsing (defer to Phase 2 if time-constrained)

### Phase 2: Structural Improvements (8-16 hours)
**Target**: v4.4

1. ✅ Implement predictable unique_id format with migration
2. ✅ Optimize badge reference updates
3. ✅ Clean up minor inefficiencies (#7, #8)

### Phase 3: Performance Monitoring (ongoing)
**Target**: Post-v4.3

1. ✅ Add performance metrics/logging
2. ✅ Monitor in production with typical family sizes
3. ✅ Validate optimization impact with real usage data

---

## 🔍 **Performance Measurement Strategy**

To validate optimization impact, capture these metrics in test instance (5 kids, 50 chores, 30 badges):

| Metric | Current (estimated) | Target |
|--------|-------------------|---------|
| `_check_overdue_chores()` duration | 500-1000ms | < 100ms |
| `_persist()` calls per action | 3-5x | 1x |
| Storage writes per minute | 10-20 | 1-2 |
| Pending reminder tasks | 10-50 | 0 (scheduler-based) |
| Parent notification latency | Sequential (300ms/parent) | Concurrent (< 100ms total) |
| Entity registry scan duration | 2-5s (200 entities) | < 100ms |

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

**Status Legend**:
- ✅ COMPLETE - Implementation done and tested
- 🚧 IN PROGRESS - Work started but not finished
- ❌ NOT ADDRESSED - Identified but not started
- ⚠️ DEFERRED - Intentionally postponed
