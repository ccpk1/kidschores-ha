# Per-Kid Applicable Days Feature - Implementation Plan

**Code**: PKAD-2026-001
**Target Release**: v0.5.0
**Storage Schema**: v43 (no increment)
**Status**: Ready for Implementation
**Approved Data Model**:

- INDEPENDENT chores: only `per_kid_applicable_days` (chore-level cleared)
- SHARED chores: only chore-level `applicable_days` (per-kid unused)
- Templating: user enters values in main form → helper form pre-populates → "apply to all" button

---

## Initiative Snapshot

| Aspect             | Details                                                  |
| ------------------ | -------------------------------------------------------- |
| **Name**           | Per-Kid Applicable Days + Per-Kid Multi-Times (Option B) |
| **Code**           | PKAD-2026-001                                            |
| **Target Release** | v0.5.0                                                   |
| **Owner**          | Strategic Planning / Builder Agent                       |
| **Status**         | Planning → Ready for Implementation                      |
| **Scope**          | Two options identified (see below)                       |

---

## Selected Implementation: Option B (Full Feature)

**Deliverables**:

- Per-kid applicable days (weekdays Mon-Sun)
- Per-kid daily multi-times (conditional, if frequency = DAILY_MULTI)
- Auto-compute per-kid due dates from days
- Extended per-kid date helper with templating feature
- Unified helper form handles both days + times
- Removes INDEPENDENT+DAILY_MULTI validation restriction
- Full test coverage

**Timeline**: 14-16 hours
**User Value**: Reduces 30 chores → 10 chores with maximum flexibility ✅✅

**Why it works**:

- Same helper form (not 2 separate forms)
- CFE-2026-001 already validated time parsing + coordinator logic
- Solves "different kid schedules" problem completely
- Synergizes with existing daily multi-times feature

---

## Summary Table

| Phase                 | Description                                           | % Complete | Notes                                                     |
| --------------------- | ----------------------------------------------------- | ---------- | --------------------------------------------------------- |
| Phase 1 – Setup       | Constants, data structure, validation (days + times)  | 0%         | No schema increment (v43)                                 |
| Phase 2 – UI Flow     | Extend per-kid helper with templating (unified form)  | 0%         | Conditional rendering (days always, times if DAILY_MULTI) |
| Phase 3 – Coordinator | Compute due from days/times, clear chore-level fields | 0%         | Single source of truth enforcement                        |
| Phase 4 – Integration | Calendar, dashboard helper, entity state updates      | 0%         | Low effort (existing patterns)                            |
| Phase 5 – Testing     | Comprehensive scenarios, edge cases, multi-times      | 0%         | Service-based + validation tests                          |

---

## Detailed Phase Breakdown

### Phase 1: Setup (1-2 hours)

**Goal**: Add constants, define data structure, implement validation

#### Step 1.1: Add Constants (30 min)

**File**: `const.py`

**Changes**:

- [ ] Add `DATA_CHORE_PER_KID_APPLICABLE_DAYS: Final = "per_kid_applicable_days"`
- [ ] Add `DATA_CHORE_PER_KID_DAILY_MULTI_TIMES: Final = "per_kid_daily_multi_times"`
- [ ] Add `CFOP_CHORES_INPUT_APPLICABLE_DAYS_PER_KID: Final = "per_kid_applicable_days"`
- [ ] Add `CFOP_CHORES_INPUT_DAILY_MULTI_TIMES_PER_KID: Final = "per_kid_daily_multi_times"`
- [ ] Add translation keys:
  - `TRANS_KEY_FLOW_HELPERS_PER_KID_APPLICABLE_DAYS`
  - `TRANS_KEY_FLOW_HELPERS_PER_KID_DAILY_MULTI_TIMES`
  - `TRANS_KEY_FORM_TEMPLATE_APPLY_TO_ALL_KIDS`
  - `CFOP_ERROR_PER_KID_APPLICABLE_DAYS_EMPTY`
  - `CFOP_ERROR_PER_KID_DAILY_MULTI_TIMES_INVALID`

**Testing**:

```bash
grep -n "DATA_CHORE_PER_KID_APPLICABLE_DAYS" custom_components/kidschores/const.py
./utils/quick_lint.sh --fix
```

#### Step 1.2: Add Validation Functions (30 min)

**File**: `flow_helpers.py`

**New Functions**:

```python
def validate_per_kid_applicable_days(per_kid_days: dict[str, list[int]]) -> dict[str, list[int]] | str:
    """Validate per-kid applicable days structure.

    Args:
        per_kid_days: {kid_id: [0, 3], ...}

    Returns:
        Validated dict or error string

    Validation Rules:
    - Each kid must have list of integers (0-6 for Mon-Sun)
    - At least 1 day per kid (or allow empty for "never on schedule"?)
    - No duplicate days in single kid's list
    """
    if not per_kid_days:
        return "At least one kid must have assigned days"

    for kid_id, days in per_kid_days.items():
        if not isinstance(days, list):
            return f"Days for {kid_id} must be a list"

        for day in days:
            if not isinstance(day, int) or day < 0 or day > 6:
                return f"Invalid day value: {day}"

        # Check for duplicates
        if len(days) != len(set(days)):
            return f"Duplicate days for {kid_id}"

    return per_kid_days

def validate_per_kid_daily_multi_times(per_kid_times: dict[str, str], frequency: str) -> dict[str, str] | str:
    """Validate per-kid daily multi-times (only for DAILY_MULTI frequency)."""
    if frequency != const.FREQUENCY_DAILY_MULTI:
        return {}

    # Reuse existing validation from CFE-2026-001
    for kid_id, times_str in per_kid_times.items():
        if not times_str:
            continue  # Optional

        try:
            times = kh.parse_daily_multi_times(times_str)
            if len(times) < 2:
                return f"Minimum 2 times required for {kid_id}"
            if len(times) > 6:
                return f"Maximum 6 times allowed for {kid_id}"
        except ValueError as err:
            return f"Invalid time format for {kid_id}: {err}"

    return per_kid_times
```

#### Step 1.3: Add to `en.json` Translations (15 min)

**File**: `translations/en.json`

**Entries**:

```json
{
  "flow_helpers": {
    "per_kid_applicable_days": "Applicable days per kid",
    "per_kid_daily_multi_times": "Daily times per kid",
    "template_section_label": "Template (from main form)",
    "apply_to_all_kids_button": "Apply to all kids",
    "per_kid_settings_label": "Per-kid settings"
  },
  "config": {
    "error": {
      "per_kid_applicable_days_empty": "At least one kid must have assigned days",
      "per_kid_applicable_days_invalid": "Invalid day values",
      "per_kid_daily_multi_times_invalid": "Invalid time format or count"
    }
  }
}
```

---

### Phase 2: Config Flow & Helper (3-4 hours)

**Goal**: Create extended per-kid helper form with templating feature (days + times)

#### Step 2.1: Extend Helper Form (2-3 hours)

**File**: `options_flow.py`

**New/Extended Method**:

```python
async def async_step_edit_chore_per_kid_details(self):
    """Extended helper: per-kid days + times with templating.

    TEMPLATING FEATURE:
    - If user entered applicable_days in main form → template section shows
    - If user entered daily_multi_times in main form → template section shows
    - All kids pre-populated with template values
    - [Apply to all kids] button copies template to all
    - User can customize per kid
    """
```

**Implementation Details** (see cross-feature analysis doc):

- [ ] Display template section (read-only) if chore-level values exist
- [ ] Pre-populate per-kid selectors with template values
- [ ] Add `[Apply to all kids]` button/option
- [ ] Multi-select for days (Mon-Sun)
- [ ] String input for times (if DAILY_MULTI)
- [ ] Conditional visibility (times only if frequency = DAILY_MULTI)
- [ ] Validation on submit (call helper validation functions)

**UI Mockup Reference**: See cross-feature analysis document

#### Step 2.2: Update Main Chore Form (45 min)

**File**: `config_flow.py`

**Changes**:

- [ ] For INDEPENDENT chores: Allow `applicable_days` input in main form (template purpose)
- [ ] For INDEPENDENT + DAILY_MULTI: Allow `daily_multi_times` input in main form (template purpose)
- [ ] Add description: "Values entered here will be suggested in per-kid configuration (next step)"
- [ ] Do NOT compute per-kid due dates in main form (helper does that)

**Routing**:

- [ ] After main chore form → route to helper form (if INDEPENDENT)
- [ ] Helper form → route to final save

#### Step 2.3: Routing & Flow Integration (30 min)

**Files**: `config_flow.py`, `options_flow.py`

**Sequence**:

1. Edit chore → main form (name, recurrence, points, etc.)
2. If INDEPENDENT: route to `async_step_edit_chore_per_kid_details()`
3. If SHARED: skip helper, go straight to save

**Validation on Helper Submit**:

- [ ] Per-kid applicable days: at least 1 kid has days
- [ ] Per-kid times (if DAILY_MULTI): valid format per kid
- [ ] Missing kids: error if assigned_kids not all present

---

### Phase 3: Coordinator Logic (2-3 hours)

**Goal**: Compute per-kid due dates from days/times, enforce single source of truth

#### Step 3.1: Clear Chore-Level Fields (30 min)

**File**: `coordinator.py`

**New/Extended Method**:

```python
async def async_update_chore(self, chore_data):
    """Update chore, enforcing single-source-of-truth for INDEPENDENT chores."""

    completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)

    # For INDEPENDENT chores: CLEAR chore-level days/times
    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None
        chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

        # Verify per-kid structure exists
        if const.DATA_CHORE_PER_KID_APPLICABLE_DAYS not in chore_data:
            chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {}
```

**Key Point**: This prevents accidental fallback to chore-level values

#### Step 3.2: Compute Per-Kid Due Dates (1.5-2 hours)

**File**: `coordinator.py`

**New Method**:

```python
async def _compute_per_kid_due_dates(self, chore_data: dict) -> None:
    """Compute per-kid due dates based on applicable days + optional times.

    Handles:
    - INDEPENDENT chores: per_kid_applicable_days → per-kid due dates
    - SHARED chores: chore-level applicable_days → shared due date
    - DAILY_MULTI: days + times (if per-kid times exist)
    """

    completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
    recurring_frequency = chore_data.get(const.DATA_CHORE_RECURRING_FREQUENCY)
    template_due_time = chore_data.get(const.DATA_CHORE_DUE_DATE, "08:00")  # Default

    per_kid_due_dates = {}

    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        # INDEPENDENT: iterate per-kid days + times
        per_kid_days = chore_data.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        per_kid_times = chore_data.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})

        for kid_id in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            days = per_kid_days.get(kid_id, [])
            times = per_kid_times.get(kid_id, "")

            if not days:
                # No days for this kid = never on schedule
                per_kid_due_dates[kid_id] = None
                continue

            # Compute next due date from days (+ times if DAILY_MULTI)
            due_date = self._compute_next_due_from_days_and_times(
                days,
                times if recurring_frequency == const.FREQUENCY_DAILY_MULTI else None,
                template_due_time
            )
            per_kid_due_dates[kid_id] = due_date

    else:
        # SHARED/SHARED_FIRST: one due date for all kids
        days = chore_data.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
        times = chore_data.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")

        shared_due_date = self._compute_next_due_from_days_and_times(
            days,
            times if recurring_frequency == const.FREQUENCY_DAILY_MULTI else None,
            template_due_time
        )

        for kid_id in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            per_kid_due_dates[kid_id] = shared_due_date

    chore_data[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

def _compute_next_due_from_days_and_times(
    self,
    applicable_days: list[int],
    daily_multi_times: str | None,
    template_due_time: str
) -> str:
    """Compute next due date from applicable days + optional times.

    Args:
        applicable_days: [0, 3] = Mon, Thu
        daily_multi_times: "08:00|17:00" or None
        template_due_time: "08:00" (default time if no multi-times)

    Returns:
        ISO datetime string or None (if no applicable days)
    """
    if not applicable_days:
        return None

    now = kh.get_now_utc()

    # Find next applicable day
    current = now.replace(hour=0, minute=0, second=0, microsecond=0)
    while current.weekday() not in applicable_days:
        current += datetime.timedelta(days=1)

    # If DAILY_MULTI: find next time slot
    if daily_multi_times:
        times = kh.parse_daily_multi_times(daily_multi_times)
        for slot_time in times:
            slot_dt = current.replace(hour=slot_time.hour, minute=slot_time.minute)
            if slot_dt > now:
                return kh.get_utc_now(slot_dt).isoformat()

        # No slots today, move to next applicable day
        current += datetime.timedelta(days=1)
        while current.weekday() not in applicable_days:
            current += datetime.timedelta(days=1)
        slot_time = times[0]
        slot_dt = current.replace(hour=slot_time.hour, minute=slot_time.minute)
        return kh.get_utc_now(slot_dt).isoformat()

    # Regular: use template_due_time
    hour, minute = map(int, template_due_time.split(":"))
    due_dt = current.replace(hour=hour, minute=minute)
    if due_dt <= now:
        # Move to next day
        due_dt += datetime.timedelta(days=1)
        while due_dt.weekday() not in applicable_days:
            due_dt += datetime.timedelta(days=1)

    return kh.get_utc_now(due_dt).isoformat()
```

**Testing**:

```bash
pytest tests/test_coordinator_per_kid_due_dates.py -v
```

---

### Phase 4: Integration (1-2 hours)

**Goal**: Update calendar, dashboard helper, entity attributes

#### Step 4.1: Calendar Updates (30 min)

**File**: `calendar.py`

**Changes**:

- [ ] When querying chore for calendar, look up per-kid applicable days
- [ ] Fall back to chore-level if per-kid not set (backward compat)
- [ ] Use per-kid days to generate calendar events

**Code** (minimal change):

```python
def _get_applicable_days_for_kid(self, chore: dict, kid_id: str) -> list[int]:
    """Get applicable days for kid (per-kid override or chore-level)."""
    per_kid_days = chore.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
    if kid_id in per_kid_days:
        return per_kid_days[kid_id]

    # Fall back to chore-level (for backward compat or shared chores)
    return chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
```

#### Step 4.2: Dashboard Helper Updates (30 min)

**File**: `sensor.py` (dashboard helper section)

**Changes**:

- [ ] Add `assigned_days` field to chore dict in helper sensor
- [ ] Format as human-readable: "Mon, Thu" (using helper function)
- [ ] Call `_format_applicable_days(days_list)` → string

**Code**:

```python
def _format_applicable_days(days: list[int]) -> str:
    """Format day list as human-readable string.

    Args:
        days: [0, 3] or empty

    Returns:
        "Mon, Thu" or "No scheduled days"
    """
    if not days:
        return const.TRANS_KEY_DISPLAY_NO_SCHEDULED_DAYS

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return ", ".join(day_names[d] for d in sorted(days))
```

#### Step 4.3: Entity Attributes (optional) (15 min)

**File**: `sensor.py` (kid chore state sensor)

**Changes** (optional, for automation support):

- [ ] Add `assigned_days` attribute to chore entity
- [ ] Add `next_due_time` (derived from per-kid_due_dates)
- [ ] Helps automations filter "only on scheduled days"

---

### Phase 5: Testing (2-3 hours)

**Goal**: Comprehensive coverage, edge cases, migration

#### Test Scenarios

**1. Per-Kid Days Only** (30 min)

**File**: `tests/test_per_kid_applicable_days.py`

```python
async def test_create_independent_chore_with_per_kid_days(hass, coordinator):
    """Create INDEPENDENT chore, set different days per kid."""
    # Create chore with:
    #   Kid A: Mon, Thu
    #   Kid B: Tue, Fri
    #   Kid C: Wed, Sat
    # Verify per_kid_applicable_days populated
    # Verify per_kid_due_dates computed (next Mon for A, next Tue for B, etc.)
    # Verify chore-level applicable_days = null

async def test_edit_per_kid_days_with_templating(hass, coordinator):
    """Edit chore using templating feature."""
    # Create chore with template (Mon-Fri all kids)
    # Edit → set Kid A custom (Mon, Wed, Fri)
    # Verify Kid B/C still Mon-Fri, Kid A is custom

async def test_calendar_respects_per_kid_days(hass, calendar_entity):
    """Calendar shows correct days per child."""
    # Kid A sees Mon, Thu
    # Kid B sees Tue, Fri
    # Kid C sees Wed, Sat

async def test_dashboard_helper_shows_assigned_days(hass, sensor_helper):
    """Dashboard helper includes assigned_days field."""
    # Chore attributes show: "assigned_days": "Mon, Thu"
```

**2. Templating Feature** (30 min)

```python
async def test_template_apply_to_all_kids(hass, flow):
    """Templating: apply-to-all button works."""
    # Create INDEPENDENT chore
    # Main form: applicable_days = Mon-Fri
    # Helper form: click "Apply to all"
    # Verify all kids get Mon-Fri

async def test_template_override_single_kid(hass, flow):
    """Templating: can customize individual kid."""
    # Template = Mon-Fri (all kids)
    # Override Kid A = Tue, Thu
    # Verify Kid A custom, B/C use template
```

**3. Migration & Backward Compat** (30 min)

```python
async def test_migration_old_data_independent_chore(hass, coordinator):
    """Old INDEPENDENT chore with global applicable_days loads correctly."""
    # Load chore with:
    #   applicable_days: [0, 1, 2, 3, 4]  (old format)
    #   no per_kid_applicable_days
    # Verify coordinator migrates to per-kid (each kid gets Mon-Fri)
    # Verify applicable_days cleared to null

async def test_migration_shared_chore_unchanged(hass, coordinator):
    """SHARED chores unchanged (no per-kid logic)."""
    # Load SHARED chore
    # Verify applicable_days still at chore-level
    # Verify per_kid_applicable_days = null
```

**4. Edge Cases** (30 min)

```python
async def test_empty_applicable_days_never_on_schedule(hass, coordinator):
    """Kid with no applicable days = never on schedule."""
    # per_kid_applicable_days[kid] = []
    # Verify due_date = None
    # Verify calendar doesn't show event

async def test_kid_removed_from_chore(hass, coordinator):
    """When kid removed, per_kid days also removed."""
    # Remove kid_id from assigned_kids
    # Coordinator cleans up per_kid_applicable_days[kid_id]

async def test_switch_completion_criteria(hass, coordinator):
    """Switch INDEPENDENT → SHARED (or vice versa)."""
    # Change from INDEPENDENT to SHARED
    # Verify per_kid_applicable_days cleared
    # Verify applicable_days populated (or keep template?)
```

**5. Per-Kid Times** (30 min)

```python
async def test_daily_multi_per_kid_times(hass, coordinator):
    """DAILY_MULTI + INDEPENDENT: per-kid times work."""
    # Create chore with:
    #   Kid A: Mon-Fri, 08:00|17:00
    #   Kid B: Every day, 06:00|12:00|18:00
    # Verify next due for each kid includes correct times

async def test_template_apply_to_all_with_times(hass, flow):
    """Templating with times: apply-to-all copies both days + times."""
    # Template: Mon-Fri, 08:00|17:00
    # All kids get same on apply-to-all
```

**Coverage Target**: >95% for new code paths

---

## Migration Strategy (No Schema Increment)

**Timing**: On first coordinator load (after code update)

**For INDEPENDENT chores**:

```python
async def _load_data_with_per_kid_migration(self):
    """Ensure per-kid days exist for INDEPENDENT chores."""
    for chore_id, chore in self._data.get(const.DATA_CHORES, {}).items():
        if chore.get(const.DATA_CHORE_COMPLETION_CRITERIA) != const.COMPLETION_CRITERIA_INDEPENDENT:
            continue

        # If per-kid days don't exist but chore-level does: migrate
        if not chore.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS):
            global_days = chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
            if global_days:
                chore[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
                    kid_id: global_days
                    for kid_id in chore.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                }
```

**For SHARED chores**: No change needed

---

## Success Criteria

✅ **Implementation complete when**:

1. [ ] Data model: Chores include `per_kid_applicable_days` + `per_kid_daily_multi_times` for INDEPENDENT
2. [ ] Chore-level fields cleared: `applicable_days = null`, `daily_multi_times = null` for INDEPENDENT chores
3. [ ] UI: Edit chore → helper form with templating + per-kid selectors (days + times)
4. [ ] Templating works: "Apply to all kids" button copies template (both days and times)
5. [ ] Coordinator: Auto-computes per-kid due dates from days + times
6. [ ] Calendar: Shows correct days + times per child
7. [ ] Dashboard helper: Includes `assigned_days` + `assigned_times` attributes
8. [ ] Tests: >95% coverage, all scenarios passing (including multi-times)
9. [ ] Migration: Old data loads correctly, gets populated
10. [ ] Backward compat: Code still works with SHARED chores

---

## Files to Modify

| File                                    | Changes                                                      | Effort |
| --------------------------------------- | ------------------------------------------------------------ | ------ |
| `const.py`                              | Add DATA_CHORE_PER_KID_APPLICABLE_DAYS, translation keys     | Low    |
| `flow_helpers.py`                       | Add validation functions                                     | Low    |
| `config_flow.py`                        | Main form for INDEPENDENT chores (optional templating input) | Low    |
| `options_flow.py`                       | New/extended helper form with templating + per-kid selectors | Medium |
| `coordinator.py`                        | Clear chore-level fields, compute per-kid due dates          | Medium |
| `calendar.py`                           | Look up per-kid days for event generation                    | Low    |
| `sensor.py`                             | Dashboard helper: add assigned_days attribute                | Low    |
| `en.json`                               | Add translation keys                                         | Low    |
| `tests/test_per_kid_applicable_days.py` | New test file (~250 lines)                                   | Medium |
| `tests/conftest.py`                     | Update scenario helpers (optional)                           | Low    |

---

## References

- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) - Data structure, chore schema, per_kid_due_dates pattern
- [DEVELOPMENT_STANDARDS.md](../docs/DEVELOPMENT_STANDARDS.md) - Constants naming, logging, type hints
- [CHORE_FREQUENCY_ENHANCEMENTS_IN-PROCESS.md](./CHORE_FREQUENCY_ENHANCEMENTS_IN-PROCESS.md) - CFE-2026-001 (DAILY_MULTI reference)
- [FEATURE_APPLICABLE_DAYS_PER_KID_SUP_CROSS_FEATURE_ANALYSIS.md](./FEATURE_APPLICABLE_DAYS_PER_KID_SUP_CROSS_FEATURE_ANALYSIS.md) - Detailed analysis, data model, templating feature, Option B details

---

## Next Steps

1. ✅ **Review this plan** (with user/stakeholder)
2. **Builder implements** Phases 1-5 in order
3. **Move to** `docs/completed/` after PR merge
