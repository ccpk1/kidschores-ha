# Calendar Refactoring Plan - Phase 4

## Executive Summary

**Objective**: Break the 280-line `_generate_events_for_chore` monolithic method into ~10 focused methods (25-30 lines each), ensuring all 6 existing tests continue passing.

**Current State**:

- **File**: `calendar.py` (534 lines total)
- **Target Method**: `_generate_events_for_chore` (lines 139-418, **280 lines**)
- **Code Paths**: 10+ distinct branches based on frequency, due_date presence, and applicable_days
- **Test Coverage**: 6 comprehensive tests (all passing)

**Expected Outcome**:

- ✅ 10-12 focused methods (~25-30 lines each)
- ✅ Clear separation of concerns
- ✅ Easier to add new recurrence types
- ✅ **All 6 tests still passing** (identical event generation behavior)
- ✅ Leverage existing `kc_helpers` date/time functions

---

## Current Code Complexity

### The `_generate_events_for_chore` Method Breakdown

**Lines 139-418 (280 lines)** with the following structure:

1. **Initialization** (lines 139-165, ~26 lines):

   - Extract chore metadata: name, description, recurring frequency, applicable_days
   - Parse `due_date` if present
   - Define `overlaps()` helper function

2. **Non-recurring chores** (lines 184-229, ~45 lines):

   - **With due_date**: Single 1-hour timed event (lines 188-197)
   - **Without due_date + applicable_days**: Full-day events for next 3 months (lines 207-229)

3. **Recurring chores WITH due_date** (lines 231-311, ~80 lines):

   - **DAILY**: Single 1-hour event on due date (lines 238-247)
   - **WEEKLY**: 7-day block ending at due date (lines 255-268)
   - **BIWEEKLY**: 14-day block ending at due date (lines 275-288)
   - **MONTHLY**: Block from month start to due date (lines 295-304)
   - **CUSTOM**: Variable-length block based on interval/unit (lines 306-311)

4. **Recurring chores WITHOUT due_date** (lines 313-418, ~105 lines):
   - **DAILY**: Full-day events filtered by applicable_days (lines 337-362)
   - **WEEKLY/BIWEEKLY**: Multi-day blocks aligned to Monday (lines 370-385, 392-405)
   - **MONTHLY**: Full month blocks (lines 412-418)
   - **CUSTOM**: Variable-length blocks with custom intervals (lines 420-440+)

---

## Refactoring Strategy

### Phase 1: Extract Shared Helper Methods (3 methods)

#### 1.1 `_event_overlaps_window(event, window_start, window_end)` → Class Method

**Purpose**: Promote nested `overlaps()` function to class method for reusability

**Current Implementation** (lines 167-183):

```python
def overlaps(ev: CalendarEvent) -> bool:
    """Check if event overlaps [window_start, window_end]."""
    sdt = ev.start
    edt = ev.end
    if isinstance(sdt, datetime.date) and not isinstance(sdt, datetime.datetime):
        tz = dt_util.get_time_zone(self.hass.config.time_zone)
        sdt = datetime.datetime.combine(sdt, datetime.time.min, tzinfo=tz)
    if isinstance(edt, datetime.date) and not isinstance(edt, datetime.datetime):
        tz = dt_util.get_time_zone(self.hass.config.time_zone)
        edt = datetime.datetime.combine(edt, datetime.time.min, tzinfo=tz)
    if not sdt or not edt:
        return False
    return (edt > window_start) and (sdt < window_end)
```

**New Signature**:

```python
def _event_overlaps_window(
    self,
    event: CalendarEvent,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> bool:
    """Check if CalendarEvent overlaps [window_start, window_end].

    Handles both date and datetime objects in event start/end.
    """
```

**Location**: Insert before `_generate_events_for_chore` method

---

#### 1.2 `_add_event_if_overlaps(event, events_list, window_start, window_end)`

**Purpose**: Consolidate 20+ duplicate "overlap check + append" blocks

**Current Pattern** (repeated throughout):

```python
e = CalendarEvent(...)
if overlaps(e):
    events.append(e)
```

**New Method**:

```python
def _add_event_if_overlaps(
    self,
    event: CalendarEvent,
    events_list: list[CalendarEvent],
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> None:
    """Add event to list if it overlaps the time window."""
    if self._event_overlaps_window(event, window_start, window_end):
        events_list.append(event)
```

**Benefit**: Reduces ~10 lines per usage to 1 line, improves consistency

---

#### 1.3 `_parse_chore_due_date(chore)` → Use `kc_helpers.normalize_datetime_input()`

**Purpose**: Replace manual parsing with battle-tested helper

**Current Implementation** (lines 155-163):

```python
due_date_str = chore.get(const.DATA_CHORE_DUE_DATE)
due_dt: datetime.datetime | None = None
if due_date_str:
    dt_parsed = dt_util.parse_datetime(due_date_str)
    if dt_parsed:
        # Use stored datetime directly - already has correct timezone
        due_dt = dt_parsed
```

**Replacement**:

```python
due_date_str = chore.get(const.DATA_CHORE_DUE_DATE)
due_dt: datetime.datetime | None = None
if due_date_str:
    # Use kc_helpers for consistent datetime parsing
    due_dt = kh.normalize_datetime_input(
        due_date_str,
        return_type=const.HELPER_RETURN_DATETIME_LOCAL,
    )
```

**Benefit**: Consistent with coordinator's datetime handling, handles edge cases

---

### Phase 2: Extract Non-Recurring Event Generation (2 methods)

#### 2.1 `_generate_non_recurring_with_due_date()`

**Lines**: 188-197 (10 lines)

**Signature**:

```python
def _generate_non_recurring_with_due_date(
    self,
    summary: str,
    description: str,
    due_dt: datetime.datetime,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate single 1-hour timed event for non-recurring chore with due_date."""
```

**Implementation**:

```python
events: list[CalendarEvent] = []
if window_start <= due_dt <= window_end:
    event = CalendarEvent(
        summary=summary,
        start=due_dt,
        end=due_dt + datetime.timedelta(hours=1),
        description=description,
    )
    self._add_event_if_overlaps(event, events, window_start, window_end)
return events
```

---

#### 2.2 `_generate_non_recurring_with_applicable_days()`

**Lines**: 207-229 (23 lines)

**Signature**:

```python
def _generate_non_recurring_with_applicable_days(
    self,
    summary: str,
    description: str,
    applicable_days: list[int],
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate full-day events for applicable days over next 3 months."""
```

**Leverage**: `kh.get_next_applicable_day()` for day filtering

**Implementation**:

```python
events: list[CalendarEvent] = []
gen_start = window_start
gen_end = min(
    window_end,
    dt_util.as_local(datetime.datetime.now() + self._calendar_duration),
)
local_tz = dt_util.get_time_zone(self.hass.config.time_zone)

current = gen_start
while current <= gen_end:
    if current.weekday() in applicable_days:
        day_start = datetime.datetime.combine(
            current.date(), datetime.time(0, 0, 0), tzinfo=local_tz
        )
        day_end = datetime.datetime.combine(
            current.date(), datetime.time(23, 59, 59), tzinfo=local_tz
        )
        event = CalendarEvent(
            summary=summary,
            start=day_start,
            end=day_end,
            description=description,
        )
        self._add_event_if_overlaps(event, events, window_start, window_end)
    current += datetime.timedelta(days=1)
return events
```

---

### Phase 3: Extract Recurring WITH due_date Methods (5 methods)

#### 3.1 `_generate_daily_recurring_with_due_date()`

**Lines**: 238-247 (10 lines)

**Signature**:

```python
def _generate_daily_recurring_with_due_date(
    self,
    summary: str,
    description: str,
    due_dt: datetime.datetime,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate single 1-hour timed event on due date for daily recurring chore."""
```

**Implementation**: Same as non-recurring with due_date

---

#### 3.2 `_generate_weekly_recurring_with_due_date()`

**Lines**: 255-268 (14 lines)

**Leverage**: `kh.adjust_datetime_by_interval(due_dt, const.TIME_UNIT_WEEKS, -1)`

**Signature**:

```python
def _generate_weekly_recurring_with_due_date(
    self,
    summary: str,
    description: str,
    due_dt: datetime.datetime,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate 7-day block ending at due_date for weekly recurring chore."""
```

**Implementation**:

```python
events: list[CalendarEvent] = []
# Use kc_helpers for week calculation
start_event = kh.adjust_datetime_by_interval(
    due_dt, const.TIME_UNIT_WEEKS, -1
)
end_event = due_dt

if start_event < window_end and end_event > window_start:
    event = CalendarEvent(
        summary=summary,
        start=start_event.date(),
        end=(end_event.date() + datetime.timedelta(days=1)),
        description=description,
    )
    self._add_event_if_overlaps(event, events, window_start, window_end)
return events
```

---

#### 3.3 `_generate_biweekly_recurring_with_due_date()`

**Lines**: 275-288 (14 lines)

**Leverage**: `kh.adjust_datetime_by_interval(due_dt, const.TIME_UNIT_WEEKS, -2)`

**Signature**: Similar to weekly, change interval to -2

---

#### 3.4 `_generate_monthly_recurring_with_due_date()`

**Lines**: 295-304 (10 lines)

**Leverage**: `kh.adjust_datetime_by_interval(due_dt, const.TIME_UNIT_MONTHS, -1)` (optional - current `.replace(day=1)` is clearer)

**Signature**:

```python
def _generate_monthly_recurring_with_due_date(
    self,
    summary: str,
    description: str,
    due_dt: datetime.datetime,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate block from month start to due_date for monthly recurring chore."""
```

---

#### 3.5 `_generate_custom_recurring_with_due_date()`

**Lines**: 306-320 (15 lines)

**Leverage**: `kh.adjust_datetime_by_interval(due_dt, unit, -interval)`

**Signature**:

```python
def _generate_custom_recurring_with_due_date(
    self,
    summary: str,
    description: str,
    due_dt: datetime.datetime,
    interval: int,
    unit: str,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate custom interval block ending at due_date."""
```

**Implementation**:

```python
events: list[CalendarEvent] = []
# Use kc_helpers for all interval calculations
start_event = kh.adjust_datetime_by_interval(due_dt, unit, -interval)

if start_event < window_end and due_dt > window_start:
    event = CalendarEvent(
        summary=summary,
        start=start_event.date(),
        end=(due_dt.date() + datetime.timedelta(days=1)),
        description=description,
    )
    self._add_event_if_overlaps(event, events, window_start, window_end)
return events
```

---

### Phase 4: Extract Recurring WITHOUT due_date Methods (4 methods)

#### 4.1 `_generate_daily_recurring_without_due_date()`

**Lines**: 337-362 (26 lines)

**Leverage**: `kh.get_next_applicable_day()` for day filtering

**Signature**:

```python
def _generate_daily_recurring_without_due_date(
    self,
    summary: str,
    description: str,
    applicable_days: list[int],
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate full-day events for each day (filtered by applicable_days)."""
```

---

#### 4.2 `_generate_weekly_biweekly_recurring_without_due_date()`

**Lines**: 370-405 (36 lines) - **Can consolidate weekly + biweekly**

**Signature**:

```python
def _generate_weekly_biweekly_recurring_without_due_date(
    self,
    summary: str,
    description: str,
    frequency: str,  # FREQUENCY_WEEKLY or FREQUENCY_BIWEEKLY
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate Monday-aligned multi-day blocks for weekly/biweekly chores."""
```

**Implementation**:

```python
events: list[CalendarEvent] = []
week_delta = 7 if frequency == const.FREQUENCY_WEEKLY else 14
block_days = 6 if frequency == const.FREQUENCY_WEEKLY else 13

gen_start = window_start
future_limit = dt_util.as_local(
    datetime.datetime.now() + self._calendar_duration
)
cutoff = min(window_end, future_limit)

# Align to Monday
current = gen_start
while current.weekday() != 0:
    current += datetime.timedelta(days=1)

while current <= cutoff:
    start_block = current
    end_block = current + datetime.timedelta(days=block_days)
    event = CalendarEvent(
        summary=summary,
        start=start_block.date(),
        end=end_block.date() + datetime.timedelta(days=1),
        description=description,
    )
    self._add_event_if_overlaps(event, events, window_start, window_end)
    current += datetime.timedelta(days=week_delta)

return events
```

---

#### 4.3 `_generate_monthly_recurring_without_due_date()`

**Lines**: 412-418 (7 lines)

**Signature**:

```python
def _generate_monthly_recurring_without_due_date(
    self,
    summary: str,
    description: str,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate full month blocks for monthly recurring chores."""
```

---

#### 4.4 `_generate_custom_recurring_without_due_date()`

**Lines**: 420-440+ (20+ lines)

**Leverage**: `kh.adjust_datetime_by_interval()` for step calculations

**Signature**:

```python
def _generate_custom_recurring_without_due_date(
    self,
    summary: str,
    description: str,
    interval: int,
    unit: str,
    applicable_days: list[int],
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Generate events with custom interval (days/weeks/months)."""
```

---

### Phase 5: Refactor `_generate_events_for_chore` into Router

**New Structure** (~30 lines):

```python
def _generate_events_for_chore(
    self,
    chore: dict,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
) -> list[CalendarEvent]:
    """Route to appropriate event generation method based on chore type.

    This method serves as a dispatcher, delegating to specialized methods
    for each combination of recurring frequency and due_date presence.
    """
    # Extract common chore attributes
    summary = chore.get(
        const.DATA_CHORE_NAME, const.TRANS_KEY_DISPLAY_UNKNOWN_CHORE
    )
    description = chore.get(const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY)
    recurring = chore.get(
        const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
    )
    applicable_days = chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])

    # Parse due_date if present
    due_date_str = chore.get(const.DATA_CHORE_DUE_DATE)
    due_dt: datetime.datetime | None = None
    if due_date_str:
        due_dt = kh.normalize_datetime_input(
            due_date_str,
            return_type=const.HELPER_RETURN_DATETIME_LOCAL,
        )

    # --- Non-recurring chores ---
    if recurring == const.FREQUENCY_NONE:
        if due_dt:
            return self._generate_non_recurring_with_due_date(
                summary, description, due_dt, window_start, window_end
            )
        if applicable_days:
            return self._generate_non_recurring_with_applicable_days(
                summary, description, applicable_days, window_start, window_end
            )
        return []

    # --- Recurring chores WITH due_date ---
    if due_dt:
        cutoff = min(due_dt, window_end)
        if cutoff < window_start:
            return []

        if recurring == const.FREQUENCY_DAILY:
            return self._generate_daily_recurring_with_due_date(
                summary, description, due_dt, window_start, window_end
            )
        elif recurring == const.FREQUENCY_WEEKLY:
            return self._generate_weekly_recurring_with_due_date(
                summary, description, due_dt, window_start, window_end
            )
        elif recurring == const.FREQUENCY_BIWEEKLY:
            return self._generate_biweekly_recurring_with_due_date(
                summary, description, due_dt, window_start, window_end
            )
        elif recurring == const.FREQUENCY_MONTHLY:
            return self._generate_monthly_recurring_with_due_date(
                summary, description, due_dt, window_start, window_end
            )
        elif recurring == const.FREQUENCY_CUSTOM:
            interval = chore.get(const.DATA_CHORE_CUSTOM_INTERVAL, 1)
            unit = chore.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, const.TIME_UNIT_DAYS
            )
            return self._generate_custom_recurring_with_due_date(
                summary, description, due_dt, interval, unit, window_start, window_end
            )

    # --- Recurring chores WITHOUT due_date ---
    if recurring == const.FREQUENCY_DAILY:
        return self._generate_daily_recurring_without_due_date(
            summary, description, applicable_days, window_start, window_end
        )
    elif recurring in (const.FREQUENCY_WEEKLY, const.FREQUENCY_BIWEEKLY):
        return self._generate_weekly_biweekly_recurring_without_due_date(
            summary, description, recurring, window_start, window_end
        )
    elif recurring == const.FREQUENCY_MONTHLY:
        return self._generate_monthly_recurring_without_due_date(
            summary, description, window_start, window_end
        )
    elif recurring == const.FREQUENCY_CUSTOM:
        interval = chore.get(const.DATA_CHORE_CUSTOM_INTERVAL, 1)
        unit = chore.get(
            const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, const.TIME_UNIT_DAYS
        )
        return self._generate_custom_recurring_without_due_date(
            summary, description, interval, unit, applicable_days,
            window_start, window_end
        )

    return []
```

---

## Implementation Steps

### Step 1: Create Refactoring Branch

```bash
git checkout -b refactor-calendar-event-generation
```

### Step 2: Extract Helper Methods (Test After Each)

1. Extract `_event_overlaps_window()` → Run tests
2. Extract `_add_event_if_overlaps()` → Run tests
3. Replace due_date parsing with `kh.normalize_datetime_input()` → Run tests

**Validation**: `pytest tests/test_calendar_scenarios.py -v` (should pass 6/6)

### Step 3: Extract Non-Recurring Methods

1. Extract `_generate_non_recurring_with_due_date()` → Run tests
2. Extract `_generate_non_recurring_with_applicable_days()` → Run tests
3. Update `_generate_events_for_chore` to call new methods → Run tests

**Validation**: `pytest tests/test_calendar_scenarios.py -v` (should pass 6/6)

### Step 4: Extract Recurring WITH due_date Methods

1. Extract `_generate_daily_recurring_with_due_date()` → Run tests
2. Extract `_generate_weekly_recurring_with_due_date()` → Run tests
3. Extract `_generate_biweekly_recurring_with_due_date()` → Run tests
4. Extract `_generate_monthly_recurring_with_due_date()` → Run tests
5. Extract `_generate_custom_recurring_with_due_date()` → Run tests
6. Update router → Run tests

**Validation**: `pytest tests/test_calendar_scenarios.py -v` (should pass 6/6)

### Step 5: Extract Recurring WITHOUT due_date Methods

1. Extract `_generate_daily_recurring_without_due_date()` → Run tests
2. Extract `_generate_weekly_biweekly_recurring_without_due_date()` → Run tests
3. Extract `_generate_monthly_recurring_without_due_date()` → Run tests
4. Extract `_generate_custom_recurring_without_due_date()` → Run tests
5. Update router → Run tests

**Validation**: `pytest tests/test_calendar_scenarios.py -v` (should pass 6/6)

### Step 6: Final Router Cleanup

1. Transform `_generate_events_for_chore` into clean dispatcher
2. Run full test suite: `pytest tests/test_calendar_scenarios.py -v`
3. Run integration-wide tests: `pytest tests/ -k calendar -v`

### Step 7: Code Quality Check

```bash
# Lint the refactored file
./utils/quick_lint.sh --fix

# Run type checker
mypy custom_components/kidschores/calendar.py
```

---

## Leveraging Existing kc_helpers Functions

### Functions to Use

| kc_helpers Function             | Line | Purpose in Calendar Refactoring                                               |
| ------------------------------- | ---- | ----------------------------------------------------------------------------- |
| `normalize_datetime_input()`    | 538  | Replace manual due_date parsing (lines 155-163)                               |
| `adjust_datetime_by_interval()` | 620  | Replace all manual timedelta calculations for weekly/monthly/custom intervals |
| `get_next_applicable_day()`     | 1140 | Simplify applicable_days checking in daily event generation                   |
| `get_next_scheduled_datetime()` | 880  | Optional - for consistent recurring pattern calculations                      |

### Code Reduction Examples

**Before** (manual calculation):

```python
start_event = due_dt - datetime.timedelta(weeks=1)
```

**After** (using kc_helpers):

```python
start_event = kh.adjust_datetime_by_interval(
    due_dt, const.TIME_UNIT_WEEKS, -1
)
```

**Benefits**:

- Handles edge cases (month boundaries, leap years, DST transitions)
- Consistent with coordinator's date logic
- Battle-tested (used in `_reschedule_chore_next_due_date`)
- Single source of truth for date arithmetic

---

## Success Metrics

### Before Refactoring

- ❌ 280-line monolithic method
- ❌ 10+ branching paths in single method
- ❌ Difficult to understand logic flow
- ❌ Manual date arithmetic scattered throughout
- ✅ 6 passing tests

### After Refactoring

- ✅ 10-12 focused methods (~25-30 lines each)
- ✅ Clear separation of concerns (one method per chore type)
- ✅ Easy to add new recurrence types
- ✅ Consistent date/time handling via kc_helpers
- ✅ **All 6 tests still passing** (identical event generation)
- ✅ Router method ~30 lines (vs 280 lines originally)

### Code Quality Targets

- **Method Length**: No method > 40 lines
- **Cyclomatic Complexity**: Max complexity = 5 per method
- **Test Coverage**: Maintain 100% coverage for calendar event generation
- **Lint Errors**: Zero errors after `./utils/quick_lint.sh`

---

## Testing Strategy

### Existing Test Coverage (6 tests)

1. **test_non_recurring_chore_with_due_date_datetime** - Non-recurring with specific time (3 PM)
2. **test_non_recurring_chore_with_due_date_midnight** - Non-recurring at midnight (edge case)
3. **test_daily_recurring_with_due_date** - Daily recurring shows single 1-hour event on due date
4. **test_daily_recurring_without_due_date_all_days** - Daily recurring without due_date, all days of week
5. **test_daily_recurring_without_due_date_applicable_days** - Daily recurring filtered by weekdays
6. **test_weekly_recurring_with_due_date** - Weekly shows 7-day block ending at due date

### Missing Test Coverage (Add After Refactoring)

7. **test_biweekly_recurring_with_due_date** - Verify 14-day block generation
8. **test_biweekly_recurring_without_due_date** - Monday-aligned biweekly blocks
9. **test_monthly_recurring_with_due_date** - Month-start to due-date block
10. **test_monthly_recurring_without_due_date** - Full month blocks
11. **test_custom_interval_with_due_date** - Custom interval ending at due date
12. **test_custom_interval_without_due_date** - Custom interval repeating pattern

### Test Execution Pattern

**After each method extraction:**

```bash
cd /workspaces/kidschores-ha
python -m pytest tests/test_calendar_scenarios.py -v
```

**Expected output:**

```
6 passed in 0.76s
```

**If any test fails**, immediately revert the extraction and debug before proceeding.

---

## Rollback Plan

If refactoring introduces bugs:

1. **Immediate**: Revert to last working commit
2. **Debug**: Run failing test in isolation with `-xvs` flags
3. **Fix**: Correct the specific method causing failure
4. **Validate**: Re-run full test suite before proceeding

**Git Strategy**:

```bash
# Create checkpoint commits after each phase
git commit -m "Phase 1: Extract helper methods - Tests passing"
git commit -m "Phase 2: Extract non-recurring methods - Tests passing"
# etc.
```

---

## Post-Refactoring Tasks

1. **Update Documentation**:

   - Add docstrings to all new methods
   - Update architecture docs with new structure

2. **Performance Testing**:

   - Verify no performance regression with large chore counts
   - Profile event generation for 100+ chores

3. **Add Missing Tests**:

   - Biweekly, monthly, custom interval scenarios
   - Edge cases (DST transitions, leap years, month boundaries)

4. **Code Review Checklist**:
   - ✅ All methods < 40 lines
   - ✅ No duplicate code between methods
   - ✅ Consistent use of kc_helpers functions
   - ✅ Clear method names and docstrings
   - ✅ All tests passing
   - ✅ No lint errors

---

## Timeline Estimate

| Phase                               | Estimated Time | Validation        |
| ----------------------------------- | -------------- | ----------------- |
| Phase 1: Extract Helpers            | 1 hour         | 6/6 tests pass    |
| Phase 2: Non-Recurring              | 1 hour         | 6/6 tests pass    |
| Phase 3: Recurring WITH due_date    | 2 hours        | 6/6 tests pass    |
| Phase 4: Recurring WITHOUT due_date | 2 hours        | 6/6 tests pass    |
| Phase 5: Router Cleanup             | 30 minutes     | 6/6 tests pass    |
| Phase 6: Code Quality               | 30 minutes     | Lint + type check |
| **Total**                           | **7 hours**    | All tests pass    |

---

## References

- **Test File**: `tests/test_calendar_scenarios.py` (384 lines, 6 tests)
- **Target File**: `custom_components/kidschores/calendar.py` (534 lines)
- **Helper Functions**: `custom_components/kidschores/kc_helpers.py` (lines 466, 538, 620, 880, 1140)
- **Phase Tracking**: See `docs/CONF_ANALYSIS.md` lines 591, 646-648
