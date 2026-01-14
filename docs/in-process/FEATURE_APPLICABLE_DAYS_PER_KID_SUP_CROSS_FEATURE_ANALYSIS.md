# Per-Kid Applicable Days: Cross-Feature Analysis & Data Model Refinement

**Date**: January 14, 2026
**Context**: Feasibility review for per-kid applicable days feature + analysis of synergy with daily multi-times (CFE-2026-001)

---

## Updated Data Model (No Schema Increment)

**Key Decision**: Mirror the `per_kid_due_dates` approach—**only store in per_kid structure for INDEPENDENT chores**.

### Data Storage by Chore Type

**SHARED Chores** (all kids get same days):

```json
{
  "chore_uuid_shared": {
    "name": "Wash dishes",
    "completion_criteria": "shared_all",
    "applicable_days": [0, 1, 2, 3, 4, 5, 6], // ← Chore-level (authoritative)
    "daily_multi_times": "08:00|17:00", // ← Chore-level (if DAILY_MULTI)
    "assigned_kids": ["kid_1", "kid_2", "kid_3"],
    "per_kid_applicable_days": null, // ← Not used for SHARED
    "per_kid_daily_multi_times": null, // ← Not used for SHARED
    "per_kid_due_dates": {
      // ← One date, shared across all kids
      "kid_1": "2026-01-15T08:00:00+00:00",
      "kid_2": "2026-01-15T08:00:00+00:00",
      "kid_3": "2026-01-15T08:00:00+00:00"
    }
  }
}
```

**INDEPENDENT Chores** (each kid gets their own days/times):

```json
{
  "chore_uuid_independent": {
    "name": "Wash up AM",
    "completion_criteria": "independent",
    "applicable_days": null, // ← ALWAYS NULL for independent (cleared on save)
    "daily_multi_times": null, // ← ALWAYS NULL for independent (cleared on save)
    "assigned_kids": ["kid_1", "kid_2", "kid_3"],
    "per_kid_applicable_days": {
      // ← ONLY place days stored (authoritative)
      "kid_1": [0, 3], // Mon, Thu
      "kid_2": [1, 4], // Tue, Fri
      "kid_3": [2, 5] // Wed, Sat
    },
    "per_kid_daily_multi_times": {
      // ← ONLY place times stored (if DAILY_MULTI)
      "kid_1": "08:00|17:00",
      "kid_2": "06:00|12:00|18:00",
      "kid_3": "14:00|20:00"
    },
    "per_kid_due_dates": {
      // ← Derived from per_kid_applicable_days + per_kid_daily_multi_times
      "kid_1": "2026-01-16T08:00:00+00:00", // Next Mon/Thu at 8am or 5pm
      "kid_2": "2026-01-17T06:00:00+00:00", // Next Tue/Fri at 6am, 12pm, or 6pm
      "kid_3": "2026-01-18T14:00:00+00:00" // Next Wed/Sat at 2pm or 8pm
    }
  }
}
```

**SHARED_FIRST Chores** (any kid, but bonus for first to complete):

```json
{
  "chore_uuid_shared_first": {
    "name": "Free-for-all chore",
    "completion_criteria": "shared_first",
    "applicable_days": [6], // ← Chore-level (Sunday only)
    "daily_multi_times": null, // ← Not typically used for shared_first
    "assigned_kids": ["kid_1", "kid_2", "kid_3"],
    "per_kid_applicable_days": null, // ← Not used for shared_first
    "per_kid_daily_multi_times": null, // ← Not used for shared_first
    "per_kid_due_dates": {
      // ← All same (all can do any time on applicable days)
      "kid_1": "2026-01-19T00:00:00+00:00",
      "kid_2": "2026-01-19T00:00:00+00:00",
      "kid_3": "2026-01-19T00:00:00+00:00"
    }
  }
}
```

### Why This Approach (Storage Decision Rationale)

**Key Principle**: INDEPENDENT chores have **no chore-level days/times** (always null)—per-kid structure is the ONLY source of truth.

**Problem with fallback to chore-level**:

- If `applicable_days: [0, 3]` at chore-level AND `per_kid_applicable_days: {kid_1: [1, 4]}` exist
- What happens if user deletes `per_kid_applicable_days[kid_1]`?
  - Fallback to chore-level? = wrong (kid_1 should have Tue/Fri, not Mon/Thu)
  - Delete completely? = unclear intent
  - No way to distinguish "override" from "delete"

**Solution**: **Clear chore-level values when saving INDEPENDENT chores**

- User edits chore → enters `applicable_days: [0, 3]` in main form
- Helper form appears (templating feature)
- User clicks "Apply to all kids" → template copied to all per-kid structures
- On save: `applicable_days` cleared to `null` (one source of truth = per-kid only)

**Benefits**:

- ✅ No ambiguity: per-kid structure is authoritative, always
- ✅ Consistent with `per_kid_due_dates` model
- ✅ Prevents accidental fallback to wrong values
- ✅ UI clear: edit independent chore → always see per-kid days/times helper
- ✅ No runtime logic needed to choose between chore-level and per-kid

---

## Cross-Feature Analysis: Applicable Days × Daily Multi-Times

### Current State (CFE-2026-001: Daily Multi-Times)

**Phase 4 complete**: Multi-daily scheduling exists

```json
{
  "chore_uuid": {
    "recurring_frequency": "daily_multi",
    "daily_multi_times": "08:00|17:00", // ← Fixed times for all kids
    "assigned_kids": ["kid_1", "kid_2", "kid_3"],
    "completion_criteria": "independent"
  }
}
```

**Current Constraint**: INDEPENDENT + multiple kids + DAILY_MULTI **blocked by validation**

- Reason: Would need TWO helper forms (per-kid due dates + daily times)
- Decision: Restrict to single kid only (avoids UI complexity)

### Proposed Enhancement: Per-Kid Multi-Times

**What if we extended to per-kid times?**

```json
{
  "chore_uuid": {
    "recurring_frequency": "daily_multi",
    "per_kid_daily_multi_times": {
      // ← NEW: Per-kid times
      "kid_1": "08:00|17:00", // Morning or evening
      "kid_2": "06:00|12:00|18:00", // Morning, midday, evening
      "kid_3": "14:00|20:00" // Afternoon or night
    },
    "assigned_kids": ["kid_1", "kid_2", "kid_3"],
    "completion_criteria": "independent"
  }
}
```

**Benefits**:

- ✅ Kid A: work schedule (8am, 5pm)
- ✅ Kid B: school schedule (6am, 12pm, 6pm)
- ✅ Kid C: evening kid (2pm, 8pm)
- ✅ All use DAILY_MULTI + INDEPENDENT in one chore

**UI Complexity**:

- Single helper form for per-kid applicable days
- Same form could collect `daily_multi_times` too (if frequency = DAILY_MULTI)
- Example flow:
  ```
  Edit Chore: "Wash dishes"
  → Recurrence: Daily Multi
  → Helper Form: Set applicable days + times per kid
     ├─ Kid A: Days [Mon-Fri], Times [08:00|17:00]
     ├─ Kid B: Days [Mon-Sun], Times [06:00|12:00|18:00]
     └─ Kid C: Days [Tue,Thu,Sat], Times [14:00|20:00]
  ```

---

## Should We Do Them Together?

### Option A: Applicable Days Only (Current Plan)

**Timeline**: ✅ 10-12 hours, v0.6.0-1

**Scope**:

- Per-kid applicable days (weekdays Mon-Sun)
- Auto-compute per-kid due dates from days
- Single per-kid date helper form (extended)

**Advantages**:

- Simpler scope, faster delivery
- Proven UI pattern (extend existing helper)
- Low risk

**Limitations**:

- Still can't do Kid A (8am/5pm), Kid B (6am/12pm/6pm), Kid C (2pm/8pm) in one chore
- If user wants per-kid times, they need to create 3 separate chores

---

### Option B: Applicable Days + Per-Kid Multi-Times (Enhanced)

**Timeline**: ⚠️ 14-18 hours (4-6 hours additional), v0.6.0

**Scope**:

- Per-kid applicable days (weekdays Mon-Sun)
- Per-kid daily multi-times (conditional, if frequency = DAILY_MULTI)
- Extended per-kid date helper form (shows time selector when needed)

**Advantages**:

- ✅ Handles both use cases simultaneously
- ✅ UI compounds naturally (same helper form handles both)
- ✅ No duplicate helpers for INDEPENDENT + DAILY_MULTI + multiple kids
- ✅ Maximum flexibility for complex schedules

**Challenges**:

- Helper form more complex (conditional time selector visibility)
- Need to validate per-kid times format per kid
- Coordinator needs `_calculate_next_multi_daily_due()` extended to per-kid times
- More test scenarios needed

**Data Model**:

```json
{
  "per_kid_applicable_days": {
    "kid_1": [0, 1, 2, 3, 4], // Mon-Fri only
    "kid_2": [0, 1, 2, 3, 4, 5, 6], // Every day
    "kid_3": [1, 2, 3, 4, 5] // Tue-Sat
  },
  "per_kid_daily_multi_times": {
    // Only if frequency = DAILY_MULTI
    "kid_1": "08:00|17:00",
    "kid_2": "06:00|12:00|18:00",
    "kid_3": "14:00|20:00"
  }
}
```

---

### Option C: Phase Per-Kid Multi-Times (Future v0.7)

**Timeline**: ✅ 10-12 hours now, 8-10 hours in v0.7

**Scope v0.6**:

- Per-kid applicable days only (this feature)

**Scope v0.7**:

- Per-kid daily multi-times (separate feature)

**Advantages**:

- Independent, smaller deliverables
- Can gather user feedback on per-kid days before adding times
- Less risk of scope creep

**Disadvantages**:

- ❌ Duplicates helper form work (build for days now, extend for times later)
- ❌ Users need 3 chores if they want per-kid times (gap until v0.7)
- ❌ Larger refactor in v0.7 (retroactively add to existing helper)

---

## Recommendation

### 🎯 **Option B: Do Both Together in v0.6** (Recommended)

**Rationale**:

1. **Helper form compounds naturally**

   - Already building: per-kid day selector
   - Extension cost: +40-50 lines (add time input when DAILY_MULTI selected)
   - Not a separate helper; same form

2. **Solves the original problem completely**

   - Your scenario: 10 chores × 3 kids = 30 entries
   - With Option A: Still need 3 chores if kids have different schedules
   - With Option B: 1 chore with 3 day/time combos = massive win

3. **CFE-2026-001 validation already done**

   - DAILY_MULTI + INDEPENDENT validation exists
   - Time format parsing exists (`parse_daily_multi_times()`)
   - `_calculate_next_multi_daily_due()` exists
   - Just need to extend to per-kid lookup

4. **Risk is LOW**

   - Same helper form + conditional rendering
   - Extends existing coordinator logic (not new)
   - Same test patterns as DAILY_MULTI (already proven)

5. **User experience improvement**
   - Edit ONE chore → set all 3 kids' days + times
   - Single submission (not multiple edits)

### Implementation Plan (Option B)

**Total Effort**: ~14-16 hours (4 phases)

| Phase | What                                              | Hours | Notes                                                |
| ----- | ------------------------------------------------- | ----- | ---------------------------------------------------- |
| 1     | Constants, data structure, migration              | 3-4   | No schema increment (v43)                            |
| 2     | Per-kid date helper (days + conditional times)    | 3-4   | Extended form with visibility rules                  |
| 3     | Coordinator logic (compute due from days + times) | 2-3   | Extends existing `_calculate_next_multi_daily_due()` |
| 4     | Tests (scenarios, edge cases)                     | 3-4   | Use CFE-2026-001 test patterns                       |

### Per-Kid Date Helper Form (Enhanced with Templating)

**UI Flow** (options_flow.py):

```
Edit Chore: "Wash dishes"
(INDEPENDENT & Daily/Daily Multi detected)
         ↓
Main Form: User enters applicable_days/daily_multi_times
         ↓
Helper Form: Set per-kid days (+ times if DAILY_MULTI)
             WITH TEMPLATING FEATURE
┌─────────────────────────────────────────────────────────┐
│ Configure "Wash dishes" for each kid                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Template (from main form):                              │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Days: Mon ☑ Tue ☑ Wed ☑ Thu ☑ Fri ☑ Sat ☑ Sun ☐ │ │
│ │ Times: [08:00|17:00]  ← Only if DAILY_MULTI        │ │
│ │                                                     │ │
│ │ [ Apply to all kids ]  ← Convenience button        │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ─────────────────────────────────────────────────────── │
│                                                         │
│ Per-Kid Settings:                                       │
│                                                         │
│ Kid A (Sarah)                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Days: Mon ☑ Tue ☑ Wed ☑ Thu ☑ Fri ☑ Sat ☑ Sun ☐ │ │
│ │ Times: [08:00|17:00]  ← Only if DAILY_MULTI        │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ Kid B (Tommy)  [Edit to customize]                      │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Days: Mon ☑ Tue ☑ Wed ☑ Thu ☑ Fri ☑ Sat ☑ Sun ☐ │ │
│ │ Times: [08:00|17:00]  ← Only if DAILY_MULTI        │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ Kid C (Emma)  [Edit to customize]                       │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Days: Mon ☑ Tue ☑ Wed ☑ Thu ☑ Fri ☑ Sat ☑ Sun ☐ │ │
│ │ Times: [08:00|17:00]  ← Only if DAILY_MULTI        │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌──────────┐  ┌────────┐                               │
│ │ Submit   │  │ Cancel │                               │
│ └──────────┘  └────────┘                               │
└─────────────────────────────────────────────────────────┘
```

**Templating Feature Workflow**:

1. **User edits INDEPENDENT chore → main form**

   - Selects `completion_criteria: independent`
   - Enters `applicable_days: [0,1,2,3,4,5]` (Mon-Sat)
   - If DAILY_MULTI: enters `daily_multi_times: "08:00|17:00"`
   - Clicks Submit

2. **Routed to helper form (templating enabled)**

   - Template section shows values from main form
   - All kids pre-populated with template values
   - `[Apply to all kids]` button visible

3. **User can**:

   - Click `[Apply to all kids]` → all kids set to template, submit
   - Edit Kid A separately → override template for Kid A only
   - Keep defaults → submit as-is

4. **On Save**:
   - Chore-level `applicable_days` **cleared to null**
   - Chore-level `daily_multi_times` **cleared to null**
   - Only `per_kid_applicable_days` + `per_kid_daily_multi_times` stored
   - Coordinator computes per-kid due dates

**Implementation Details**:

```python
# options_flow.py (new method or extend existing)
async def async_step_edit_chore_per_kid_details(self):
    """Edit per-kid applicable days and times (if DAILY_MULTI).

    Uses TEMPLATING: if user entered values in main form, they're pre-populated here
    with an "Apply to all kids" button for convenience.
    """

    chore_data = self._chore_being_edited
    assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    is_independent = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA) == const.COMPLETION_CRITERIA_INDEPENDENT
    is_daily_multi = chore_data.get(const.DATA_CHORE_RECURRING_FREQUENCY) == const.FREQUENCY_DAILY_MULTI

    # Get template values from main form (if user entered them)
    template_days = chore_data.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
    template_times = chore_data.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")

    # Get existing per-kid values (if editing existing chore)
    per_kid_days = chore_data.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
    per_kid_times = chore_data.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})

    # TEMPLATING LOGIC: if no per-kid values yet, use template
    if not per_kid_days and template_days:
        per_kid_days = {kid_id: template_days for kid_id in assigned_kids}

    if not per_kid_times and template_times:
        per_kid_times = {kid_id: template_times for kid_id in assigned_kids}

    if user_input is None:
        # FIRST LOAD: Show template section + "Apply to all" button
        description = (
            "Values from main form (if any) are shown below as a template.\n"
            "Click 'Apply to all kids' to copy them to all kids, or customize per kid."
        )

        schema_dict = {}

        # TEMPLATE SECTION (read-only display of chore-level values)
        schema_dict[vol.Marker.SHOW_ADVANCED] = True  # Or could use a custom separator

        # Per-kid selectors
        for kid_id in assigned_kids:
            kid_name = get_kid_by_id(kid_id)

            # Days selector (for INDEPENDENT chores)
            if is_independent:
                schema_dict[vol.Required(
                    f"days_{kid_id}",
                    description={"suggested_value": per_kid_days.get(kid_id, template_days)}
                )] = SelectSelector(option=get_day_options(), multiple=True)

            # Times selector (for DAILY_MULTI chores)
            if is_daily_multi:
                schema_dict[vol.Required(
                    f"times_{kid_id}",
                    description={"suggested_value": per_kid_times.get(kid_id, template_times)}
                )] = StringSelector()  # Pipe-separated "HH:MM|HH:MM|..."

        return self.async_show_form(
            step_id="edit_chore_per_kid_details",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "template_info": (
                    f"Template Days: {self._format_days(template_days) or 'None'}\n"
                    f"Template Times: {template_times or 'None'}"
                ),
                "apply_to_all_button": "[Click 'Submit' after selecting 'apply_to_all' option]"
            },
        )

    # USER SUBMITTED FORM

    # Check if "apply to all" was clicked (special handling)
    if user_input.get("_apply_to_all"):
        # Copy template to all kids
        if is_independent and template_days:
            per_kid_days = {kid_id: template_days for kid_id in assigned_kids}
        if is_daily_multi and template_times:
            per_kid_times = {kid_id: template_times for kid_id in assigned_kids}

        # Re-show form with values populated
        user_input = None  # Reset to redisplay
        return await self.async_step_edit_chore_per_kid_details()

    # NORMAL SUBMISSION: Store per-kid values
    if is_independent:
        chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
            kid_id: user_input.get(f"days_{kid_id}", [])
            for kid_id in assigned_kids
        }

    if is_daily_multi:
        chore_data[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = {
            kid_id: user_input.get(f"times_{kid_id}", "")
            for kid_id in assigned_kids
        }

    # Coordinator will:
    # 1. Clear chore-level applicable_days (if independent)
    # 2. Clear chore-level daily_multi_times (if daily_multi)
    # 3. Compute per-kid due dates from per_kid_applicable_days + per_kid_daily_multi_times

    return await self._finalize_chore_edit(chore_data)
```

### Coordinator Logic: Clearing Chore-Level Fields for INDEPENDENT

**Critical Step**: When saving an INDEPENDENT chore, **always clear chore-level applicable_days and daily_multi_times**.

```python
# coordinator.py (async_update_chore method)

async def async_update_chore(self, chore_data):
    """Update chore, enforcing single-source-of-truth for INDEPENDENT chores."""

    chore_id = chore_data[const.DATA_CHORE_ID]
    completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)

    # For INDEPENDENT chores: CLEAR chore-level days/times
    # (per-kid structure is the ONLY source of truth)
    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        # Clear chore-level fields
        chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None
        chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

        # Verify per-kid structure exists
        if const.DATA_CHORE_PER_KID_APPLICABLE_DAYS not in chore_data:
            chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {}

        if (chore_data.get(const.DATA_CHORE_RECURRING_FREQUENCY) == const.FREQUENCY_DAILY_MULTI
            and const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES not in chore_data):
            chore_data[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = {}

    # For SHARED/SHARED_FIRST chores: USE chore-level only
    else:
        # Clear per-kid structures (not used for shared)
        chore_data.pop(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, None)
        chore_data.pop(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, None)

    # Compute per-kid due dates (different logic for independent vs shared)
    await self._compute_per_kid_due_dates(chore_data)

    # Save to storage
    self._persist()
```

**Key Points**:

- ✅ No runtime logic needed to choose "which source" (always use per-kid for independent)
- ✅ Prevents accidental fallback to wrong chore-level values
- ✅ Clear enforcement: chore-level fields MUST be null for independent

```python
def _compute_next_due_date_from_applicable_days_and_times(
    self,
    applicable_days: list[int],
    daily_multi_times: str | None,
    template_due_time: str
) -> str:
    """
    Compute next due from applicable days + optional multi-times.

    Args:
        applicable_days: [0, 3] = Mon, Thu
        daily_multi_times: "08:00|17:00" or None
        template_due_time: Default time if no multi-times

    Returns:
        ISO datetime string of next scheduled slot
    """

    now = kh.get_now_utc()

    # Find next applicable day
    current = now.replace(hour=0, minute=0, second=0, microsecond=0)
    while current.weekday() not in applicable_days:
        current += datetime.timedelta(days=1)

    # If DAILY_MULTI: find next time slot
    if daily_multi_times:
        times = kh.parse_daily_multi_times(daily_multi_times)
        # Find next time slot on applicable days
        for slot_time in times:
            slot_dt = current.replace(hour=slot_time.hour, minute=slot_time.minute)
            if slot_dt > now:
                return slot_dt.isoformat()

        # No slots today, move to next applicable day
        current += datetime.timedelta(days=1)
        while current.weekday() not in applicable_days:
            current += datetime.timedelta(days=1)
        slot_time = times[0]
        slot_dt = current.replace(hour=slot_time.hour, minute=slot_time.minute)
        return slot_dt.isoformat()

    # Regular scheduling: use template_due_time
    # (existing logic)
```

---

## Migration Strategy (No Schema Increment)

**Existing chores** (v43 data with global `applicable_days`):

**For INDEPENDENT chores**:

```python
# Migrate on first load (coordinator initialization)
for chore_id, chore in chores.items():
    if (chore.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        == const.COMPLETION_CRITERIA_INDEPENDENT):

        # Copy global days to each kid
        global_days = chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
        if global_days:
            chore[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
                kid_id: global_days
                for kid_id in chore.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            }

            # Clear global (or keep as comment that it's unused for INDEPENDENT)
            # chore.pop(const.DATA_CHORE_APPLICABLE_DAYS, None)
```

**For SHARED chores**:

- No change; keep `applicable_days` at chore level

---

## Templating Feature: "Apply to All Kids" Pattern

### Problem It Solves

When editing an INDEPENDENT chore, users often want all kids to have the same days/times initially, then customize exceptions.

**Without templating**:

```
Edit Chore → Helper form
→ Manually enter Mon-Fri for Kid A
→ Manually enter Mon-Fri for Kid B
→ Manually enter Mon-Fri for Kid C
(Repetitive)
```

**With templating** (proposed):

```
Edit Chore → Main form: enter "Mon-Fri" + "08:00|17:00"
→ Helper form: pre-filled for all kids
→ Click [Apply to all kids] button
→ All kids now have Mon-Fri + 08:00|17:00 (1 click!)
→ Edit Kid A separately if needed
```

### How It Works

**Phase 1: Main Chore Form**

- User edits INDEPENDENT chore
- Enters `applicable_days: [0,1,2,3,4]` (Mon-Fri)
- If DAILY_MULTI: enters `daily_multi_times: "08:00|17:00"`
- Submits → routed to helper form

**Phase 2: Helper Form (Templating Enabled)**

- Template section displays values from main form
- All per-kid selectors pre-populated with template values
- `[Apply to all kids]` button copies template → all kids
- User can:
  - Accept template as-is → Submit
  - Customize Kid A (override) → Submit
  - Mix: Kid A custom, Kids B/C use template → Submit

**Phase 3: Save & Validation**

- Coordinator receives chore data
- **Clears chore-level `applicable_days` and `daily_multi_times` to null**
- Stores only `per_kid_applicable_days` + `per_kid_daily_multi_times`
- Computes per-kid due dates

### Benefits

✅ **User Experience**:

- One-click "apply to all" for common case (all kids same days)
- Faster editing (not repeating 3 times)
- Template displayed as reference (transparency)

✅ **Data Integrity**:

- Clear source of truth: per-kid structure authoritative
- Chore-level values always null for INDEPENDENT
- No ambiguity in coordinator runtime logic

✅ **Code Simplicity**:

- Coordinator doesn't need "chore-level fallback" logic
- Helper form logic straightforward (just copy dict)
- Validation only needs to check per-kid values

### Implementation Checklist

- [ ] Main form validation: Accept `applicable_days` + `daily_multi_times` for INDEPENDENT (template purpose)
- [ ] Helper form: Display template section at top (read-only summary)
- [ ] Helper form: Pre-populate all kids with template values on first load
- [ ] Helper form: Add `[Apply to all kids]` button (or checkbox option)
- [ ] Coordinator: Clear chore-level fields for INDEPENDENT on save
- [ ] Tests: Verify template → per-kid population works
- [ ] Tests: Verify override (customize Kid A) still works
- [ ] Tests: Verify chore-level fields cleared after save

---

**New Test Scenarios** (in addition to CFE-2026-001):

1. **Per-kid days only** (INDEPENDENT + daily/weekly/etc)

   - Edit chore → set Kid A Mon/Thu, Kid B Tue/Fri, Kid C Wed/Sat
   - Verify due dates computed per kid
   - Calendar shows correct days per child

2. **Per-kid times only** (SHARED + DAILY_MULTI)

   - Edit chore → set all kids 08:00|17:00
   - Verify first due = today at 8am (or 5pm if past 8am)

3. **Per-kid days + times** (INDEPENDENT + DAILY_MULTI)

   - Edit chore → Kid A Mon/Fri 8am/5pm, Kid B Tue/Sat 6am/12pm, Kid C Wed 2pm/8pm
   - Verify next due for each kid combines days + times
   - Calendar shows all slots per child

4. **Migration backward compat**

   - Old chore with `applicable_days: [0, 3]` (Mon, Thu)
   - Load as INDEPENDENT → auto-populate per-kid days
   - Edit chore → verify migration worked

5. **Switching frequencies**
   - DAILY chore → user changes to DAILY_MULTI
   - Helper form appears with time selector
   - Switching back to DAILY removes time selector

---

## Final Recommendation Summary

| Aspect                   | Option A (Days Only)                             | Option B (Days + Times)                               |
| ------------------------ | ------------------------------------------------ | ----------------------------------------------------- |
| **Timeline**             | 10-12 hrs, v0.6.0                                | 14-16 hrs, v0.6.0                                     |
| **Solves your use case** | ✅ Partially (still 10 chores for per-kid times) | ✅ Completely (1 chore, all kids' days + times)       |
| **UI Complexity**        | Low                                              | Medium (conditional rendering)                        |
| **Code Reuse**           | High (CFE-2026-001 logic)                        | High (extends CFE-2026-001)                           |
| **Risk**                 | Very Low                                         | Low                                                   |
| **User Impact**          | Good (reduces 30→10 chores)                      | Excellent (reduces 30→10 chores, maximum flexibility) |
| **Maintenance**          | Simpler, fewer edge cases                        | More edge cases, but documented                       |

**🎯 Recommendation**: **Option B** if timeline allows (v0.6.0 release window), else **Option A** now + **Option B in v0.6.1** (quick follow-up).

Given your original request ("This would massively reduce my chore count and make things far easier to manage"), **Option B delivers the most value** with only modest additional effort (4-6 hours).
