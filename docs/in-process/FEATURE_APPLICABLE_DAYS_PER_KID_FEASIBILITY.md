# Feasibility Review: Per-Kid Applicable Days for Independent Chores

**Date**: January 14, 2026
**Reviewer**: KidsChores Strategist
**Current State**: v0.5.0 (Storage-Only, Silver Quality)
**User Story**: Enable per-kid day assignment to reduce chore duplication (10 → 1 chore base)

---

## Executive Summary

**Good news!** Your feature is **highly feasible** and aligns perfectly with existing architecture.

**Current Situation**:

- 10 base chores × 3 kids = 30 chore entries
- Each requires individual due_date per kid (already supported via `per_kid_due_dates`)
- Days hardcoded into due_dates; no global day list

**Proposed Improvement**:

- 10 base chores with `per_kid_applicable_days` field
- Backend auto-computes kid-specific due dates from applicable days
- Coordinator renders next due date per kid from assigned days

**Effort Assessment**: **LOW-TO-MODERATE** (10-14 hours total)

- Storage schema: +1 (v43 → v44, requires migration)
- UI: Medium (per-kid day selector in edit flow)
- Backend: Low (leverage existing `applicable_days` logic)
- Testing: Medium (new scenarios for per-kid days)

---

## Architecture Fit Analysis

### 1. **Data Model Compatibility** ✅

**Current Structure** (Chore Storage):

```json
{
  "chore_uuid_1": {
    "name": "Wash up AM",
    "applicable_days": [0, 3], // ← Global: Mon, Thu
    "assigned_kids": ["kid_1", "kid_2", "kid_3"],
    "recurring_frequency": "daily",
    "per_kid_due_dates": {
      // ← Already exists!
      "kid_1": "2026-01-14T08:00:00+00:00",
      "kid_2": "2026-01-15T08:00:00+00:00",
      "kid_3": "2026-01-16T08:00:00+00:00"
    },
    "completion_criteria": "independent"
  }
}
```

**Proposed Addition**:

```json
{
  "chore_uuid_1": {
    "name": "Wash up AM",
    "applicable_days": [0, 3], // ← DEPRECATED (keep for backward compat)
    "per_kid_applicable_days": {
      // ← NEW: Day assignments per kid
      "kid_1": [0, 3], // Mon, Thu
      "kid_2": [1, 4], // Tue, Fri
      "kid_3": [2, 5] // Wed, Sat
    },
    "assigned_kids": ["kid_1", "kid_2", "kid_3"],
    "per_kid_due_dates": {
      // ← Derived from per_kid_applicable_days
      "kid_1": "2026-01-16T08:00:00+00:00", // Next Mon/Thu
      "kid_2": "2026-01-17T08:00:00+00:00", // Next Tue/Fri
      "kid_3": "2026-01-18T08:00:00+00:00" // Next Wed/Sat
    }
  }
}
```

**Verdict**: ✅ **Perfect fit**

- `per_kid_applicable_days` mirrors existing `per_kid_due_dates` structure
- No conflict with current data; co-exists naturally
- `applicable_days` becomes "default fallback" for backward compat

---

### 2. **Coordinator Logic** ✅

**Where Due Dates Are Computed** ([coordinator.py](../custom_components/kidschores/coordinator.py)):

```python
# Lines 1333-1335: Read applicable_days from chore
chore_info[const.DATA_CHORE_APPLICABLE_DAYS] = chore_data.get(
    const.DATA_CHORE_APPLICABLE_DAYS,
    chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []),
)

# Lines ~1420+: Calendar platform uses applicable_days to generate events
# calendar.py._generate_non_recurring_without_due_date() iterates applicable_days
```

**New Logic Needed**:

```python
def _compute_next_due_date_from_applicable_days(
    self,
    applicable_days: list[int],
    template_due_time: str
) -> str:
    """Compute next due date based on applicable days (Mon=0, Sun=6)."""
    # Get today's date + due time
    # Loop through next days until finding a day in applicable_days
    # Return ISO datetime string
    # If no applicable_days, return None (never overdue)
```

**Where This Lives**:

- `coordinator._compute_next_due_date_from_applicable_days()` (new helper ~20 lines)
- Call from `async_update_chore()` or new dedicated flow step
- Used by both:
  - **UI update flow**: When user edits per-kid days
  - **Coordinator refresh**: When midnight passes or week rotates

**Verdict**: ✅ **Straightforward**

- Reuse existing `_compute_next_due_date()` logic
- Similar to calendar's `_generate_non_recurring_without_due_date()` logic
- Test with simple scenarios: 1-day week, multi-day ranges, no days assigned

---

### 3. **UI/Flow Integration** ⚠️ MEDIUM EFFORT

**Current Edit Flow**:

```
Edit Chore
  ↓
[Step 1] Basic (name, icon, points) ← EXISTING
  ↓
[Step 2] Recurrence & Due Date ← EXISTING
  ↓
[Step 3] Kid Assignment ← EXISTING
  ↓
[Step 4] Completion Criteria ← EXISTING (shared/independent toggle)
  ↓
[Step 5] Notifications ← EXISTING
  ↓
[Submit]
```

**New Flow Step Needed** (Conditional):

```
Edit Chore
  ↓
... (Steps 1-4 existing)
  ↓
[Step 4b] Per-Kid Applicable Days ← NEW (only if completion_criteria = independent)
  ↓
... (Steps 5+ existing)
```

**New Step 4b Implementation**:

```python
async def async_step_chore_applicable_days_per_kid(self):
    """Configure applicable days per kid (INDEPENDENT chores only)."""
    # Show one day-selector per assigned kid
    # Days: Mon(0) - Sun(6), multi-select for each kid
    # Option: "Use global days for all" → copies global applicapble_days to all kids
    # Option: "Custom days per kid" → individual selectors
```

**UI Complexity Estimate**:

- **Simple**: Day checkboxes (Mon-Sun) repeated for each kid
- **Medium**: Multi-select dropdowns or chip-based selector
- **Ideal**: Match existing selector UI pattern

**Verdict**: ⚠️ **Medium complexity**

- Flow step logic: ~50-80 lines (straightforward conditional)
- Selector UI: Can use `MultiSelectSelector` from Home Assistant
- Validation: Ensure at least 1 day per kid (or allow empty = "never")

---

### 4. **Calendar Integration** ✅

**Current Calendar Logic** ([calendar.py](../custom_components/kidschores/calendar.py)):

```python
# Lines 211-250: Generate all-day events for chores WITHOUT due_date
# Uses applicable_days to determine which days to show

def _generate_non_recurring_without_due_date(
    self,
    events: list,
    summary: str,
    applicable_days: list[int],  # ← Mon=0, Sun=6
    window_start: datetime,
    window_end: datetime,
) -> None:
    """Generate events for applicable_days within time window."""
    current = window_start
    while current <= window_end:
        if current.weekday() in applicable_days:
            # Create full-day event
            events.append(...)
        current += timedelta(days=1)
```

**What Changes**:

```python
# Get per-kid applicable days for THIS kid's calendar
per_kid_applicable_days = chore.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
applicable_days = per_kid_applicable_days.get(
    kid_id,
    chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])  # Fallback to global
)

# Use derived applicable_days (1-line change per chore)
self._generate_non_recurring_without_due_date(
    events, summary, applicable_days, window_start, window_end
)
```

**Verdict**: ✅ **Minimal impact**

- Calendar already supports `applicable_days` lookup
- Just add per-kid override in lookup chain
- ~5-10 line changes to calendar.py

---

### 5. **Dashboard Helper Sensor** ✅

**Current Helper** (`sensor.kc_<kid>_ui_dashboard_helper`):

The dashboard already renders chores from the helper sensor's `chores` attribute. New behavior:

```python
# coordinator._build_dashboard_helper_chores() extracts:
{
    "id": "chore_uuid_1",
    "name": "Wash up AM",
    "due_date": "2026-01-16T08:00:00+00:00",  # ← Per-kid
    "assigned_days": "Mon, Thu",               # ← NEW: Derived from per_kid_applicable_days[kid_id]
    ...
}
```

**What Changes**:

1. When building chore list for helper, look up kid's applicable days
2. Format as human-readable string: "Mon, Thu"
3. Pass to dashboard via attribute

**Verdict**: ✅ **Trivial**

- Add 1 helper method: `_format_applicable_days(day_list) → "Mon, Thu, Sat"`
- Call it when building dashboard helper attributes
- ~10 lines total

---

## Implementation Roadmap

### Phase 1: Schema & Coordinator (3-4 hours)

**Files**: `const.py`, `coordinator.py`, `storage_manager.py`

- [ ] Add constant: `DATA_CHORE_PER_KID_APPLICABLE_DAYS`
- [ ] Add migration v43 → v44:
  - For each independent chore:
    - If `applicable_days` exists → copy to each kid in `per_kid_applicable_days`
    - Clear `applicable_days` (or keep as fallback)
- [ ] Add `_compute_next_due_date_from_applicable_days()` helper
- [ ] Update `async_update_chore()` to accept `per_kid_applicable_days`
- [ ] Update `async_set_chore_due_date()` to compute from days if provided

**Testing**:

```bash
pytest tests/test_migration_v43_v44.py -v
pytest tests/test_coordinator_due_date_computation.py -v
```

---

### Phase 2: Config Flow (2-3 hours)

**Files**: `flow_helpers.py`, `config_flow.py`

- [ ] Add validation helper: `validate_per_kid_applicable_days()`
  - Ensure each kid has at least 1 day (or allow empty)
  - Handle day format normalization
- [ ] Add flow step: `async_step_chore_applicable_days_per_kid()`
  - Show multi-select for each kid (days Mon-Sun)
  - Include "Copy to all kids" convenience button
- [ ] Update chore schema builder:
  - Add field for per-kid days when `completion_criteria = independent`
  - Conditional visibility (don't show for shared chores)
- [ ] Update existing per-kid due date step:
  - If per-kid days provided → auto-compute due dates
  - Show preview: "Kid A: Next Mon or Thu"

**Testing**:

```bash
pytest tests/test_config_flow_chore_edit.py::test_per_kid_applicable_days -v
pytest tests/test_flow_helpers_applicable_days.py -v
```

---

### Phase 3: Calendar & Helper Updates (1-2 hours)

**Files**: `calendar.py`, `sensor.py` (dashboard helper section)

- [ ] Update `calendar.py._query_calendar_events()`:
  - Look up per-kid applicable days from chore
  - Fall back to global `applicable_days` if not set
- [ ] Update dashboard helper sensor:
  - Add `assigned_days` field to chore object
  - Call `_format_applicable_days()` helper
- [ ] Update entity state/attributes:
  - Show "Mon, Thu" in chore entity attributes (if useful for automations)

**Testing**:

```bash
pytest tests/test_calendar_per_kid_days.py -v
pytest tests/test_dashboard_helper_applicable_days.py -v
```

---

### Phase 4: Testing & Edge Cases (2-3 hours)

**Test Scenarios** (from [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)):

1. **Test: Free-for-all rotation** (Sunday double points)

   - Chore with no applicable days = "never on schedule"
   - Can be claimed/completed any time
   - Dashboard shows "No scheduled days"

2. **Test: Kid removed from chore**

   - Delete kid_id from `per_kid_applicable_days`
   - Verify due_date removed from `per_kid_due_dates`

3. **Test: Switch from global to per-kid days**

   - Chore with `applicable_days: [0, 3]` (all kids Mon/Thu)
   - Edit to `per_kid_applicable_days`: Kid A Mon/Thu, Kid B Tue/Fri, Kid C Wed/Sat
   - Verify per-kid dates update

4. **Test: Shared → Independent conversion**

   - User converts shared chore to independent
   - If `applicable_days` exists → auto-populate `per_kid_applicable_days`
   - Calendar updates correctly

5. **Test: Migration backward compat**
   - Old data (no per-kid days) still works
   - Falls back to global `applicable_days`
   - Can be edited to per-kid mode

**Edge Cases**:

- Empty applicable_days (chore never on schedule)
- Single day per kid (very frequent assignments)
- All kids same days (functionally same as global, but per-kid override)
- New kid added to existing chore (should populate per-kid days?)

**Files to Create/Update**:

- `tests/test_migration_per_kid_applicable_days.py` (~80 lines)
- `tests/test_coordinator_per_kid_days.py` (~100 lines)
- Update `tests/conftest.py` scenario builders

---

## Schema Migration Strategy

**Current**: `schema_version = 43` (v0.5.0 storage-only)
**Target**: `schema_version = 44`

**Migration Code** (coordinator.py):

```python
async def _migrate_to_v44(stored_data: dict) -> None:
    """v43 → v44: Add per_kid_applicable_days to independent chores."""
    chores = stored_data.get(const.DATA_CHORES, {})

    for chore_id, chore in chores.items():
        # Only migrate independent chores with applicable_days
        if (chore.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            == const.COMPLETION_CRITERIA_INDEPENDENT
            and chore.get(const.DATA_CHORE_APPLICABLE_DAYS)):

            # Copy global days to each assigned kid
            global_days = chore[const.DATA_CHORE_APPLICABLE_DAYS]
            per_kid_days = {}

            for kid_id in chore.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                per_kid_days[kid_id] = global_days

            chore[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = per_kid_days

            # Optionally clear global applicable_days (or keep as fallback)
            # chore.pop(const.DATA_CHORE_APPLICABLE_DAYS, None)

    # Update schema version
    stored_data[const.DATA_META][const.DATA_META_SCHEMA_VERSION] = 44
```

**Migration Risk**: ⚠️ **Low**

- Data is duplicated, not moved (easier rollback)
- Backward compatible: old code still reads `applicable_days`
- Can be partially deployed (v44 reader works on v43 data as fallback)

---

## Effort Breakdown

| Phase     | Component                   | Hours          | Complexity |
| --------- | --------------------------- | -------------- | ---------- |
| 1a        | Constants + data structure  | 0.5            | Trivial    |
| 1b        | Migration v43 → v44         | 1              | Low        |
| 1c        | Coordinator helpers         | 1.5            | Low        |
| 2a        | Flow validation             | 0.5            | Low        |
| 2b        | New flow step UI            | 1.5            | Medium     |
| 2c        | Schema/selector integration | 0.5            | Low        |
| 3a        | Calendar updates            | 0.75           | Low        |
| 3b        | Dashboard helper            | 0.5            | Trivial    |
| 4a        | Core test scenarios         | 1.5            | Medium     |
| 4b        | Edge case + migration tests | 1              | Medium     |
| 4c        | Manual testing + validation | 1              | Low        |
| **Total** |                             | **~10-12 hrs** |            |

---

## Risk Assessment

### Risks (All Mitigated)

| Risk                            | Likelihood | Impact | Mitigation                                               |
| ------------------------------- | ---------- | ------ | -------------------------------------------------------- |
| **Data Loss**                   | Low        | High   | Backup before migration; dual-write test phase           |
| **Calendar UI breaks**          | Very Low   | High   | Calendar already handles per-kid lookups; minimal change |
| **Shared chores affected**      | Very Low   | Medium | Migration only touches `independent` chores              |
| **Complex per-kid selector UI** | Low        | Medium | Use existing Home Assistant MultiSelectSelector          |
| **Performance (coordinator)**   | Very Low   | Low    | No new loops; just dict lookups                          |

### Unknowns

1. **User preference**: Do users want "copy days to all kids" button?
   - **Resolution**: Add as optional convenience feature in UI
2. **Empty applicable_days**: Should "no scheduled days" be allowed?
   - **Resolution**: Allow it; coordinator returns `due_date = None` (never overdue)
3. **Backward compat period**: When can `applicable_days` be fully removed?
   - **Resolution**: Keep fallback logic indefinitely; deprecate in future major version

---

## Decision Points for Implementation

### 🔴 Must Decide (Blocks Implementation)

1. **Auto-compute per-kid due dates from days?**

   - ✅ **Recommendation**: YES
   - Coordinator runs at midnight → recomputes next due date from applicable days
   - One-time computation at chore save (flow)

2. **Preserve global `applicable_days` as fallback?**

   - ✅ **Recommendation**: YES (for backward compat)
   - Don't delete it; just mark as deprecated in code comment
   - Old clients that read global days still work

3. **Allow empty applicable_days (never on schedule)?**
   - ✅ **Recommendation**: YES
   - Useful for "free for all" chores (e.g., Sundays)
   - Dashboard helper shows: "No scheduled days"

### 🟡 Nice-to-Have (Polish)

1. **"Copy to all kids" button in flow?**
   - Makes editing easier (set one kid, copy to others)
   - Worth 15 min of implementation
2. **Chore entity attribute for applicable days?**
   - Could help automations ("only reminder on applicable days")
   - Worth 10 min of implementation
3. **Dashboard preview: "Next due date (Mon, Thu)"?**
   - Already handled by auto-computed due dates
   - Just format as "Next Wed, Jan 15 @ 8 AM"

---

## Success Criteria

✅ **Feature is complete when**:

1. **Data model**: Chore storage includes `per_kid_applicable_days` dict
2. **Migration**: v43 → v44 seamlessly copies global days to all kids
3. **UI**: Edit chore → Step 4b shows per-kid day selectors (independent chores only)
4. **Coordinator**: Auto-computes per-kid due dates from applicable days at save & midnight
5. **Calendar**: Renders correct days per child (uses per-kid override)
6. **Dashboard helper**: Includes `assigned_days` attribute per chore
7. **Tests**: >95% coverage for new code paths; all existing tests still pass
8. **User experience**: User can edit 1 chore + set all 3 kids' days in <2 minutes
9. **Backward compat**: Old data without per-kid days still loads & functions

---

## Files to Modify

### Core Changes

- [const.py](../custom_components/kidschores/const.py) — Add `DATA_CHORE_PER_KID_APPLICABLE_DAYS`
- [coordinator.py](../custom_components/kidschores/coordinator.py) — Migration, due-date computation
- [flow_helpers.py](../custom_components/kidschores/flow_helpers.py) — Validation, schema builder
- [config_flow.py](../custom_components/kidschores/config_flow.py) — New flow step
- [calendar.py](../custom_components/kidschores/calendar.py) — Per-kid day lookup
- [sensor.py](../custom_components/kidschores/sensor.py) — Dashboard helper updates

### Testing

- `tests/test_migration_per_kid_applicable_days.py` (new)
- `tests/test_coordinator_per_kid_days.py` (new)
- `tests/test_config_flow_chore_*.py` (update existing)
- `tests/test_calendar_*.py` (update existing)

### Supporting

- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) — Document new data structure
- [README.md](../README.md) — Mention feature (optional)

---

## References

| Document                                                                               | Relevant Section                                     |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| [ARCHITECTURE.md](../docs/ARCHITECTURE.md)                                             | Data structure, chore schema, migration pattern      |
| [DEVELOPMENT_STANDARDS.md](../docs/DEVELOPMENT_STANDARDS.md)                           | Constants naming, testing patterns                   |
| [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) | Test scenarios, fixtures, conftest helpers           |
| [QUALITY_REFERENCE.md](../docs/QUALITY_REFERENCE.md)                                   | Silver-quality requirements (type hints, docstrings) |

---

## Next Steps

1. **Review this plan** with user (you)
2. **Approve decision points** (auto-compute, preserve global days, empty days allowed)
3. **Hand off to Builder Agent** with INITIATIVE\_\*\_IN-PROCESS.md plan
4. **Builder implements** Phases 1-4 in order
5. **Move plan to** `docs/completed/` after PR merges

---

## Questions for User?

1. **For free-for-all (Sunday)**: Should that chore have `per_kid_applicable_days = {all: []}` (no days), or just not be assigned to kids?

   - _Context_: You mentioned "free for all, first to do and claim gets double points"

2. **Rotation complexity**: Do any kids have irregular schedules (e.g., Kid A: Mon/Wed/Fri, Kid B: Tue/Thu)?

   - _Planning_: Just helps validate edge cases

3. **Future enhancement**: Would you want "Day override for specific weeks" (e.g., "Kid A off Monday Jan 20 but available Wednesday")?
   - _Planning_: Out of scope for this feature, but good to know
