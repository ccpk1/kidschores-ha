# Section 6: Unlabeled Legacy Constants Analysis

**Date**: December 27, 2025
**Discovered By**: User manual code review of migration_pre_v42.py
**Context**: Three constants found without `_DEPRECATED` or `_LEGACY` suffix that ARE legacy

---

## Executive Summary

During review of `migration_pre_v42.py`, three constants were discovered that lack proper suffix marking but represent legacy data structures:

1. **DATA_KID_MAX_STREAK** - Migration-only (CORRECT usage, needs \_LEGACY suffix)
2. **DATA_KID_LAST_STREAK_DATE** - Mixed usage (NEEDS INVESTIGATION)
3. **DATA_KID_MAX_POINTS_EVER** - **DOUBLE MAINTENANCE** (Section 6 refactoring required)

**Why These Were Missed**:

- Original analysis searched for `_DEPRECATED|_LEGACY` suffix patterns
- These constants have no suffix (plain field names like `"max_streak"`)
- They are **inner keys** within legacy structures, not top-level structure names
- Example: `chore_streaks[chore_id]["max_streak"]` ← MAX_STREAK is the nested key

---

## 1. DATA_KID_MAX_STREAK Analysis

### Definition

```python
# const.py line 864
DATA_KID_MAX_STREAK: Final = "max_streak"
```

### Usage Pattern

- **Migration Only**: 2 references in `migration_pre_v42.py`
- **Coordinator**: 0 references
- **Sensors**: 0 references

### Context

Inner key within legacy `chore_streaks` dict structure:

```python
# OLD structure (pre-v42):
kid_info["chore_streaks"][chore_id] = {
    "current_streak": 5,
    "max_streak": 10,  # ← THIS CONSTANT
    "last_date": "2024-12-25"
}
```

### Migration Usage

```python
# Line 427: Reading old max_streak value
max_streak = legacy_streak.get(const.DATA_KID_MAX_STREAK, 0)

# Line 553: Migrating to new period structure
] = legacy_streak.get(const.DATA_KID_MAX_STREAK, 0)
```

### Modern Equivalent

```python
# NEW structure (v42+):
chore_data[chore_id]["periods"]["all_time"]["longest_streak"]
# Accessed via: DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
```

### Assessment

✅ **CORRECT USAGE** - Only used in migration to read old data structure
✅ **NO REFACTORING NEEDED** - Not maintained in coordinator
⚠️ **ACTION NEEDED**: Add `_LEGACY` suffix for consistency

### Recommendation

```python
# const.py - Add _LEGACY suffix
DATA_KID_MAX_STREAK_LEGACY: Final = "max_streak"  # Inner key in legacy chore_streaks dict
```

---

## 2. DATA_KID_LAST_STREAK_DATE Analysis

### Definition

```python
# const.py line 862
DATA_KID_LAST_STREAK_DATE: Final = "last_date"
```

### Usage Pattern

- **Migration**: 2 references (reading old structure)
- **Coordinator**: 5 references (lines 2644, 7287, 7608, 7611, 7628)
- **Sensors**: 0 references

### Context

Used in two different places:

1. **Legacy `chore_streaks` dict** (migration reads this)
2. **Modern `progress` dict** (coordinator uses this)

### Migration Usage

```python
# Line 431: Reading from legacy chore_streaks
last_longest_streak_date = legacy_streak.get(
    const.DATA_KID_LAST_STREAK_DATE
)

# Line 504: Another read from legacy structure
last_date = legacy_streak.get(const.DATA_KID_LAST_STREAK_DATE)
```

### Coordinator Usage

**Initialization (lines 2644, 7287)**:

```python
# Creating progress dict for chore
const.DATA_KID_LAST_STREAK_DATE: None,
```

**Active Streak Tracking (lines 7608-7628)**:

```python
# Method: _update_streak_progress
def _update_streak_progress(self, progress: dict, today: date):
    """Update a streak progress dict."""
    last_date = None
    if progress.get(const.DATA_KID_LAST_STREAK_DATE):  # Line 7608
        try:
            last_date = date.fromisoformat(
                progress[const.DATA_KID_LAST_STREAK_DATE]  # Line 7611
            )
        except (ValueError, TypeError, KeyError):
            last_date = None

    # If already updated today, do nothing
    if last_date == today:
        return

    # If yesterday was the last update, increment the streak
    elif last_date == today - timedelta(days=1):
        progress[const.DATA_KID_CURRENT_STREAK] += 1

    # Reset to 1 if not done yesterday
    else:
        progress[const.DATA_KID_CURRENT_STREAK] = 1

    progress[const.DATA_KID_LAST_STREAK_DATE] = today.isoformat()  # Line 7628
```

### Modern Equivalent?

**Question**: Is this replaced by `last_approved` timestamp in chore_data?

Let me check what timestamps are stored in chore_data:

```python
# chore_data structure has:
DATA_KID_CHORE_DATA_LAST_APPROVED  # Full datetime
DATA_KID_CHORE_DATA_LAST_CLAIMED   # Full datetime
DATA_KID_CHORE_DATA_LAST_RESET     # Full datetime
```

### Assessment

⚠️ **UNCLEAR** - Appears to be legacy field but actively maintained

**Arguments for LEGACY**:

- Named `last_date` (vague, not descriptive)
- Stored in `progress` dict (legacy location)
- Redundant with `last_approved` datetime (which includes date)

**Arguments for LEGITIMATE**:

- Used in active streak calculation logic
- May be intentionally simpler (date-only vs datetime)
- Performance optimization (don't parse datetime every check)

### Investigation Needed

1. Check if streak logic could use `last_approved.date()` instead
2. Verify if removing this breaks streak continuation
3. Determine if this is intentional optimization or legacy artifact

### Recommendation

⏳ **DEFER DECISION** - Needs deeper investigation of streak logic

- If redundant: Add to Section 6 refactoring
- If intentional: Document why date-only field is needed

---

## 3. DATA_KID_MAX_POINTS_EVER Analysis ⚠️ **CRITICAL FINDING**

### Definition

```python
# const.py line 863
DATA_KID_MAX_POINTS_EVER: Final = "max_points_ever"
```

### Usage Pattern

- **Migration**: 1 reference (reading old field)
- **Coordinator**: 4 references (**ACTIVE WRITES** at lines 4133-4134)
- **Sensors**: 2 references BUT reads **DIFFERENT** field (reads modern `highest_balance`)

### Smoking Gun: Double Maintenance

**OLD FIELD (lines 4133-4134)** - Never displayed:

```python
# Method: _update_kid_points
# 3) Update max points ever tracking
kid_info.setdefault(const.DATA_KID_MAX_POINTS_EVER, 0.0)
kid_info[const.DATA_KID_MAX_POINTS_EVER] += delta_value  # ← ACTIVE WRITE
```

**NEW FIELD (lines 4204-4205)** - Displayed in sensor:

```python
# 8) Update highest balance (part of point_stats)
if new > point_stats[const.DATA_KID_POINT_STATS_HIGHEST_BALANCE]:
    point_stats[const.DATA_KID_POINT_STATS_HIGHEST_BALANCE] = new
```

### Semantic Difference (But Still Redundant)

**OLD (`max_points_ever`)**:

- Tracks **cumulative earnings** (never decreases)
- Adds every positive delta: `+= delta_value`
- Example: Kid earns 100, spends 50, earns 50 → max_points_ever = 150

**NEW (`highest_balance`)**:

- Tracks **peak balance** (can decrease if points spent)
- Updates only if current balance exceeds previous max: `if new > max`
- Example: Kid earns 100, spends 50, earns 50 → highest_balance = 100

**However**: The old field is **NEVER READ** except in:

1. Initialization (backward compat for migrations)
2. Migration file (one-time read)

### Sensor Proof

```python
# sensor_legacy.py line 726-729
@property
def native_value(self) -> int:
    """Return the highest points total the kid has ever reached."""
    kid_info = self.coordinator.kids_data.get(self._kid_id, {})
    point_stats = kid_info.get(const.DATA_KID_POINT_STATS, {})
    return point_stats.get(
        const.DATA_KID_POINT_STATS_HIGHEST_BALANCE, const.DEFAULT_ZERO  # ← Uses NEW field
    )
```

**The sensor name is misleading!** It says "max points earned" but displays "highest balance".

### Modern Equivalent

```python
# Already exists - this is what sensor displays
DATA_KID_POINT_STATS_HIGHEST_BALANCE
# Stored in: kid_info["point_stats"]["highest_balance"]
```

### Assessment

❌ **CONFIRMED DOUBLE MAINTENANCE** - Pure dead weight

- Old field actively updated but **NEVER READ**
- Sensor displays new field (modern equivalent)
- Exact same pattern as Sections 1-3

### Impact

- **Lines to Remove**: 2 (lines 4133-4134)
- **Tests Affected**: Likely none (field not exposed to UI)
- **Migration**: Already handles this (line 967 reads old value)
- **Refactoring Complexity**: LOW (simple deletion)

### Recommendation

✅ **SECTION 6 REFACTORING REQUIRED**

**Step 1**: Remove coordinator maintenance (lines 4133-4134)

```python
# DELETE THESE LINES:
# 3) Update max points ever tracking
kid_info.setdefault(const.DATA_KID_MAX_POINTS_EVER, 0.0)
kid_info[const.DATA_KID_MAX_POINTS_EVER] += delta_value
```

**Step 2**: Keep initialization for backward compat (line 950-951)

```python
# KEEP THIS (for migrations):
const.DATA_KID_MAX_POINTS_EVER: kid_data.get(
    const.DATA_KID_MAX_POINTS_EVER, const.DEFAULT_ZERO
),
```

**Step 3**: Add `_LEGACY` suffix to constant

```python
# const.py - Mark as legacy
DATA_KID_MAX_POINTS_EVER_LEGACY: Final = "max_points_ever"  # Replaced by point_stats.highest_balance
```

**Step 4**: Update initialization reference

```python
# coordinator.py line 950-951
const.DATA_KID_MAX_POINTS_EVER_LEGACY: kid_data.get(
    const.DATA_KID_MAX_POINTS_EVER_LEGACY, const.DEFAULT_ZERO
),
```

**Step 5**: Verify migration file still works

- Migration reads old field once (line 967)
- Should use `_LEGACY` suffix for consistency

---

## Summary Table

| Constant           | Migration  | Coordinator            | Sensor               | Status          | Action                    |
| ------------------ | ---------- | ---------------------- | -------------------- | --------------- | ------------------------- |
| `MAX_STREAK`       | ✅ 2 reads | ❌ 0 refs              | ❌ 0 refs            | **CORRECT**     | Add `_LEGACY` suffix      |
| `LAST_STREAK_DATE` | ✅ 2 reads | ⚠️ 5 refs (active)     | ❌ 0 refs            | **UNCLEAR**     | Investigate purpose       |
| `MAX_POINTS_EVER`  | ✅ 1 read  | ❌ **2 ACTIVE WRITES** | ✅ Uses modern field | **DEAD WEIGHT** | **Section 6 refactoring** |

---

## Refactoring Plan

### Phase 1: MAX_STREAK (Low Priority - Cleanup Only)

1. Rename constant: `DATA_KID_MAX_STREAK` → `DATA_KID_MAX_STREAK_LEGACY`
2. Update migration references (lines 427, 553)
3. No coordinator changes needed
4. Test: Migration still works

### Phase 2: LAST_STREAK_DATE (Medium Priority - Investigation Required)

1. **Investigate**: Can streak logic use `last_approved.date()` instead?
2. **Test**: Does removing `last_date` break streak continuation?
3. **Decision**:
   - If redundant: Add to Section 6 refactoring
   - If intentional: Document and keep

### Phase 3: MAX_POINTS_EVER (High Priority - Section 6 Refactoring)

1. **Remove Lines 4133-4134** from coordinator (active maintenance)
2. **Keep Line 950-951** (initialization for backward compat)
3. **Rename Constant**: Add `_LEGACY` suffix
4. **Update References**: coordinator.py line 950, migration_pre_v42.py line 967
5. **Test**: All 679 tests pass, no sensor regressions

### Testing Strategy

- Run full test suite after each phase
- Verify 679 baseline tests pass
- Check for regressions in points/streak tracking
- Validate lint score (maintain 9.62/10)

---

## Lessons Learned

### Why These Were Missed in Original Analysis

1. **Search Pattern**: Used `_DEPRECATED|_LEGACY` suffix search
2. **Naming**: These constants have no suffix (plain names)
3. **Structure Type**: These are inner keys, not top-level structures
   - Not `DATA_KID_CHORE_STREAKS_LEGACY` (top-level)
   - But `DATA_KID_MAX_STREAK` (inner key within chore_streaks)

### Improved Search Strategy for Future

1. **Suffix search**: `_DEPRECATED|_LEGACY` (catches marked items)
2. **Semantic search**: "legacy", "old structure", "pre-v42" (catches unmarked)
3. **Migration file review**: Manually scan migration for constant usage
4. **Cross-reference**: Compare migration reads with coordinator writes
5. **Sensor validation**: Verify sensors use modern fields, not legacy

### Pattern Recognition

**Inner keys of legacy structures** need the same scrutiny as top-level structures:

- `chore_streaks[chore_id]["max_streak"]` ← Inner key
- `chore_streaks` itself ← Top-level dict

Both should be marked `_LEGACY` if replaced in modern architecture.

---

## Next Steps

1. ✅ **Document findings** (this file)
2. ⏳ **Update CONSTANT_CLASSIFICATION_ANALYSIS.md** (add Section 6)
3. ⏳ **Execute Phase 1** (MAX_STREAK - simple rename)
4. ⏳ **Investigate Phase 2** (LAST_STREAK_DATE - determine legitimacy)
5. ⏳ **Execute Phase 3** (MAX_POINTS_EVER - Section 6 refactoring)
6. ⏳ **Update DEPRECATED_ITEMS_FINAL_ANALYSIS.md** (include 3 new constants)
7. ⏳ **Test suite validation** (679 tests passing)

---

**Status**: Ready for refactoring
**Priority**: High (MAX_POINTS_EVER has active waste)
**Complexity**: Low (2 lines to remove, simple constant rename)
**Risk**: Low (field not exposed to UI, tests should catch any issues)
