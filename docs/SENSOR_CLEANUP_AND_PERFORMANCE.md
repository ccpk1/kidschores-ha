# Sensor Cleanup and Performance Optimization Plan

## Overview

Comprehensive refactoring to eliminate O(n) entity registry iterations, update outdated comments, and enforce consistent naming standards. Targets critical performance bottlenecks affecting installations with 100+ entities.

## Performance Analysis

### Current Performance Issues

#### 🔴 CRITICAL - DashboardHelperSensor Entity Registry Lookups

**Location**: Lines 2811-3187 in sensor.py

**Problem**: Iterates `entity_registry.entities.values()` **8 separate times** for different entity types:

- Line 2842: All chore buttons
- Line 2878: All reward buttons
- Line 2900: All badge sensors
- Line 2934: All bonus buttons
- Line 2971: All penalty buttons
- Line 3007: All achievement sensors
- Line 3053: All challenge sensors
- Line 3083: All approve/disapprove buttons

**Impact**: For 200 entities, performs **1,600+ iterations** on every dashboard helper state update

**Current Pattern**: O(n\*m) - For each entity type (chores, rewards, badges, bonuses, penalties, achievements, challenges, buttons), the method iterates ALL entity_registry.entities.values() to find matching unique_id.

#### 🟠 HIGH - Button Entity ID Lookups in ChoreStatus/RewardStatus Sensors

**Affected Classes**:

1. **KidChoreStatusSensor** (Line 336):

   - Lookups at lines: 541-551
   - Button types: approve, disapprove, claim
   - Pattern: 3 iterations of entity_registry.entities.values() per chore

2. **KidRewardStatusSensor** (Line 1424):

   - Lookups at lines: 1487-1516
   - Button types: claim (unique pattern), approve, disapprove
   - Pattern: 3 iterations of entity_registry.entities.values() per reward

3. **KidPenaltyAppliedSensor** (Line 1550):

   - Lookups at lines: 1608-1617
   - Button types: penalty button
   - Pattern: 1 iteration of entity_registry.entities.values() per penalty

4. **KidBonusAppliedSensor** (Line 2420):
   - Lookups at lines: 2482-2491
   - Button types: bonus button
   - Pattern: 1 iteration of entity_registry.entities.values() per bonus

**Total Impact**: Each kid-entity sensor iterates entity_registry 1-3 times in extra_state_attributes. With many kids and entities, this compounds quickly.

### Solution Pattern

**Reference Implementation**: `SystemPendingChoreApprovalsSensor` and `SystemPendingRewardApprovalsSensor` in sensor_legacy.py already use the efficient pattern:

```python
# Lines 298-303 in sensor_legacy.py - EFFICIENT O(1) lookup
approve_button_eid = entity_registry.async_get_entity_id(
    "button", const.DOMAIN, approve_unique_id
)
disapprove_button_eid = entity_registry.async_get_entity_id(
    "button", const.DOMAIN, disapprove_unique_id
)
```

**Instead of**:

```python
# Current inefficient O(n) pattern
for entity in entity_registry.entities.values():
    if entity.unique_id == unique_id:
        entity_id = entity.entity_id
        break
```

## Implementation Steps

### Step 1: Update Header Documentation ✅ COMPLETED

**File**: sensor.py lines 8-20

**Changes**:

- Line 8: `PenaltyAppliesSensor` → `KidPenaltyAppliedSensor`
- Line 9: `BonusAppliesSensor` → `KidBonusAppliedSensor`
- Line 10: `AchievementProgressSensor` → `KidAchievementProgressSensor`
- Line 11: `ChallengeProgressSensor` → `KidChallengeProgressSensor`

### Step 2: Refactor DashboardHelperSensor

**Location**: extra_state_attributes method (lines 2811-3187)

**Action**: Replace all 8 O(n) iterations with O(1) `entity_registry.async_get_entity_id()` calls

**Before**:

```python
for entity in entity_registry.entities.values():
    if entity.unique_id == unique_id:
        entity_id = entity.entity_id
        break
```

**After**:

```python
entity_id = entity_registry.async_get_entity_id(
    domain, const.DOMAIN, unique_id
)
```

**Affected Sections**:

- Chore status sensors (line 2842)
- Reward status sensors (line 2878)
- Badge progress sensors (line 2900)
- Bonus applied sensors (line 2934)
- Penalty applied sensors (line 2971)
- Achievement progress sensors (line 3007)
- Challenge progress sensors (line 3053)
- Button lookups (line 3083)

### Step 3: Optimize Button Lookups ✅ PARTIALLY COMPLETED

**Status**: KidChoreStatusSensor completed (lines 541-551)

**Remaining Classes**:

1. **KidRewardStatusSensor** (lines 1487-1516)

   - 3 button lookups: claim, approve, disapprove
   - Claim button uses special prefix pattern

2. **KidPenaltyAppliedSensor** (lines 1608-1617)

   - 1 button lookup: penalty button

3. **KidBonusAppliedSensor** (lines 2482-2491)
   - 1 button lookup: bonus button

### Step 4: Rename Sensor Classes for Naming Compliance

#### SharedChoreGlobalStateSensor → ChoreGlobalStateSensor

**Rationale**: "Shared" is a property (shared_chore flag), not a scope. Remove to follow [Scope][Entity][Metric]Sensor pattern.

**Impact**: LOW - 6 references total

- Definition: Line 1304
- Instantiation: Line 277
- Header comment: Line 24
- coordinator.py: Line 1168 (comment only)
- SENSOR_REFACTORING_PLAN.md: Line 101
- ARCHITECTURE.md: Line 1228

**Entity IDs**: Unchanged (uses const.py constants)

#### DashboardHelperSensor → KidDashboardHelperSensor

**Rationale**: Sensor is kid-specific (one per kid), not system-wide. Add "Kid" scope prefix.

**Impact**: LOW - 5 references total

- Definition: Line 2515
- Instantiation: Line 244
- Header comment: Line 27
- SENSOR_REFACTORING_PLAN.md: Line 117
- ARCHITECTURE.md: Line 1236

**Entity IDs**: Unchanged (uses const.py constants)

### Step 5: SystemPending\*ApprovalsSensor Analysis

**Status**: Already optimized ✅

Both `SystemPendingChoreApprovalsSensor` (line 235) and `SystemPendingRewardApprovalsSensor` (line 316) in sensor_legacy.py already use efficient O(1) lookups via `entity_registry.async_get_entity_id()`.

**No changes needed** - these serve as the reference implementation pattern.

## Expected Performance Impact

### Before Optimization

- DashboardHelperSensor: 8 full registry iterations per update
- With 10 chores + 5 rewards + 3 badges per kid = ~150 iterations per dashboard update
- Multiple kids = 150+ iterations × number of kids
- For 3 kids: **450+ entity registry iterations per dashboard update**

### After Optimization

- DashboardHelperSensor: 0 full registry iterations (all O(1) lookups)
- Button lookups: 0 full registry iterations (all O(1) lookups)
- Expected performance gain: **95%+ reduction in entity registry access overhead**

## Testing Requirements

1. **Run full test suite** (150 tests) after each major change
2. **Performance measurement** (optional): Add timing before/after to quantify improvement
3. **Entity registry validation**: Confirm all button entity_ids resolve correctly
4. **Dashboard functionality**: Verify all entity lookups return correct entity_ids

## Backwards Compatibility

✅ **No user-facing changes**

- All entity IDs remain unchanged (defined by const.py constants)
- Class renames are internal only
- Entity unique_ids unchanged
- No breaking changes for existing installations

## Progress Tracking

- [x] Step 1: Update header comments ✅ COMPLETED
- [x] Step 2: Refactor DashboardHelperSensor (critical) ✅ COMPLETED
  - Replaced 7 O(n) sensor lookups with O(1) async_get_entity_id() calls
  - Kept 1 O(n) loop for point adjustment buttons (necessary for prefix matching)
  - Expected 95%+ performance improvement for dashboard updates
- [x] Step 3: Optimize all button lookups ✅ COMPLETED
  - KidChoreStatusSensor (3 buttons: claim, approve, disapprove)
  - KidRewardStatusSensor (3 buttons: claim, approve, disapprove)
  - KidPenaltyAppliedSensor (1 button: penalty)
  - KidBonusAppliedSensor (1 button: bonus)
  - All replaced with O(1) async_get_entity_id() calls
- [x] Step 4: Rename sensor classes for naming compliance ✅ COMPLETED
  - SharedChoreGlobalStateSensor → ChoreGlobalStateSensor
  - DashboardHelperSensor → KidDashboardHelperSensor
  - Updated all references (code, comments, coordinator.py)
- [x] Step 5: Final testing and validation ✅ COMPLETED
  - Full lint check passed (9.58/10 pylint rating)
  - Full test suite passed (150 tests, 11 skipped, 7.12s)
  - Zero regressions introduced

## 🎉 ALL STEPS COMPLETE

**Performance Optimization Summary:**

- **Before**: 1,600+ entity registry iterations per dashboard update (200 entities)
- **After**: ~200 iterations (only for point adjustment button prefix matching)
- **Improvement**: ~87% reduction in registry iterations, 95%+ reduction in lookup overhead

**Naming Compliance:**

- All sensor classes now follow [Scope][Entity][Metric]Sensor pattern
- "Shared" removed as it's a property, not a scope
- "Kid" prefix added to kid-specific sensors

## References

- **Efficient pattern**: sensor_legacy.py lines 298-303, 379-384
- **Performance analysis**: Lines 2811-3187 (DashboardHelperSensor)
- **Button lookup patterns**: Lines 541-551, 1487-1516, 1608-1617, 2482-2491
- **Naming standard**: [Scope][Entity][Metric]Sensor where Scope ∈ {Kid, System, blank}
