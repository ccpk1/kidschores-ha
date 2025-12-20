# Phase 1 - Coordinator Logic Changes Analysis

## Current Logic (4 locations identified):

### 1. `_check_badges_for_kid()` - Line ~4953-4954

**Current:**

```python
is_assigned_to = bool(
    not badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])  # ← REMOVE THIS PART
    or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
)
```

**NEW Logic:**

```python
is_assigned_to = kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
```

**Impact:** Primary badge evaluation logic - determines which badges are checked for each kid

---

### 2. `_sync_badge_progress_for_kid()` - Line ~6476-6477

**Current:**

```python
is_assigned_to = bool(
    not badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])  # ← REMOVE THIS PART
    or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
)
```

**NEW Logic:**

```python
is_assigned_to = kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
```

**Impact:** Badge progress sync - determines which badges get progress tracking data

---

### 3. `_sync_badge_progress_for_kid()` - Line ~6809-6810

**Current:**

```python
assigned_badge_ids = {
    badge_id
    for badge_id, badge_info in self.badges_data.items()
    if not badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])  # ← REMOVE THIS PART
    or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
}
```

**NEW Logic:**

```python
assigned_badge_ids = {
    badge_id
    for badge_id, badge_info in self.badges_data.items()
    if kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
}
```

**Impact:** Badge cleanup logic - removes progress for unassigned badges

---

### 4. `_get_cumulative_badge_levels()` - Line ~7198-7200

**Current:**

```python
is_assigned_to = not badge_info.get(
    const.DATA_BADGE_ASSIGNED_TO, []
) or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])  # ← REMOVE FIRST PART
```

**NEW Logic:**

```python
is_assigned_to = kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
```

**Impact:** Cumulative badge level calculation - determines which badges count toward cumulative progress

---

## Summary of Changes Required:

**Pattern to Find:**

```python
not badge_info.get(const.DATA_BADGE_ASSIGNED_TO, []) or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
```

**Pattern to Replace With:**

```python
kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
```

**Alternative Patterns:**
Some locations use list comprehensions, those need similar logic changes.

**Testing Impact:**
Each location needs unit tests to verify:

1. Empty assignment → kid NOT eligible
2. Kid in assignment → kid IS eligible
3. Kid not in assignment → kid NOT eligible
4. Multiple kids: only assigned kids eligible

## Implementation Plan:

1. **Phase 2A:** Update all 4 coordinator locations with new logic
2. **Phase 2B:** Add comprehensive logging to show behavior change
3. **Phase 2C:** Create unit tests for each location
4. **Phase 2D:** Test with normalization to ensure end-to-end flow works

**Risk Mitigation:**

- Keep old commented code until testing complete
- Add extensive debug logging during transition
- Test with multiple badge types and assignment scenarios
