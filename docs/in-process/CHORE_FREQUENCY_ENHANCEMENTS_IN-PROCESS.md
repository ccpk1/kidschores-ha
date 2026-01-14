# Chore Frequency Enhancements - Implementation Plan

## Initiative snapshot

- **Name / Code**: Chore Frequency Enhancements (CFE-2026-001)
- **Target release / milestone**: v0.6.0
- **Owner / driver(s)**: Strategic Planning Agent
- **Status**: Planning - Ready for Implementation

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Constants & Validation | Add 3 frequency constants, translation keys, validation logic | 0% | All 3 features: constants + validation |
| Phase 2 – Feature 1 Core Logic | Implement completion-based rescheduling (pass last_completed instead of due_date) | 0% | Simple: 1 parameter change |
| Phase 3 – Feature 2 Helper Flow | Create multi-daily times helper form (like existing per-kid dates helper) | 0% | Complex: new step + parsing |
| Phase 4 – Features 2 & 3 Core Logic | Implement multi-time-per-day + hourly scheduling | 0% | DAILY_MULTI + HOURLY logic |
| Phase 5 – Testing | Comprehensive test coverage for all three features | 0% | Service-based + validation tests |

### Key Objectives

1. **Feature 1 (FREQUENCY_CUSTOM_FROM_COMPLETE)**: Reschedule from completion date instead of due_date (simple enhancement)
2. **Feature 2 (FREQUENCY_DAILY_MULTI)**: Support multiple times per day (complex - requires new helper form + time parsing)
3. **Feature 3 (FREQUENCY_HOURLY)**: Support hourly intervals (1-23 hours) with AT_MIDNIGHT reset restrictions

### Recent Work
- Initial analysis complete  
- Existing helper flow structure understood (`edit_chore_per_kid_dates` pattern)
- Approval reset interaction clarified
- **INDEPENDENT chore dual-form UX issue identified and resolved**
- **Cron syntax consideration analyzed** (future enhancement vs current simplicity)

### Next Steps
1. Add constants and translation keys (Phase 1)
2. Implement Feature 1 core logic (pass completion timestamp - Phase 2)
3. Build Feature 2 helper form (collect times list - Phase 3)
4. Implement Feature 2 scheduling logic (Phase 4)

### Risks / Blockers
- ⚠️ Feature 2 (FREQUENCY_DAILY_MULTI) **incompatible** with `AT_MIDNIGHT_*` reset types by design (resets once at midnight, but needs multiple resets per day)
- Feature 2 requires new form step (similar to `edit_chore_per_kid_dates`)
- Time format validation required (24-hour HH:MM with pipe separator)

### References
- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - Data model, storage schema
- [DEVELOPMENT_STANDARDS.md](../../docs/DEVELOPMENT_STANDARDS.md) - Coding standards
- [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) - Test patterns
- Existing helper pattern: `options_flow.py` lines 1574+ (`async_step_edit_chore_per_kid_dates`)

### Decisions & completion check

**Key Decisions**:
1. Feature 1 (CUSTOM_FROM_COMPLETE): Simple - just pass `last_completed` timestamp to existing reschedule calculation (no new helpers needed)
2. Feature 2 (DAILY_MULTI): Complex - requires new helper form step (pattern: like per-kid dates form)  
3. Feature 3 (HOURLY): Medium - leverage existing FREQUENCY_CUSTOM logic but add hourly intervals
4. DAILY_MULTI validation: Accept UPON_COMPLETION, AT_DUE_DATE_ONCE, and AT_DUE_DATE_MULTI (reject AT_MIDNIGHT_*)
5. HOURLY validation: Block AT_MIDNIGHT_* entirely (disrupts natural hourly cycles)
6. UPON_COMPLETION recommended for DAILY_MULTI (immediate slot advancement vs delayed with AT_DUE_DATE_MULTI)
7. Time format: Pipe-separated 24-hour time ("|" separator enforced by validation)
8. Timezone handling: Use existing `kc_helpers` patterns - parse times with `const.DEFAULT_TIME_ZONE`, convert to UTC for storage/comparison
9. **INDEPENDENT chore restriction**: DAILY_MULTI only allowed with single kid selection (prevents dual helper forms: per-kid dates + daily times)

**Completion confirmation**: 
- [ ] All follow-up items completed (architecture updates, cleanup, documentation) before requesting owner approval

---

## Detailed phase tracking

### Phase 1 – Constants & Validation (0%)

**Goal**: Define new frequency types, add translation keys, implement validation

**Steps**:

1. **Add frequency constants to const.py** (~line 145)
   - Add: `FREQUENCY_CUSTOM_FROM_COMPLETE: Final = "custom_from_complete"`
   - Add: `FREQUENCY_DAILY_MULTI: Final = "daily_multi"`
   - Add: `FREQUENCY_HOURLY: Final = "hourly"`
   - Update `FREQUENCY_OPTIONS` list (~line 2639) to include all three

2. **Add data field constants** (~line 650)
   - Add: `DATA_CHORE_DAILY_MULTI_TIMES: Final = "daily_multi_times"`
   - Add: `DATA_CHORE_CUSTOM_INTERVAL_HOURS: Final = "custom_interval_hours"`
   - Add: `CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: Final = "daily_multi_times"` (~line 300)
   - Add: `CFOF_CHORES_INPUT_CUSTOM_INTERVAL_HOURS: Final = "custom_interval_hours"` (~line 300)

3. **Add translation keys** (~line 2400)
   - `TRANS_KEY_FLOW_HELPERS_FREQUENCY_CUSTOM_FROM_COMPLETE`
   - `TRANS_KEY_FLOW_HELPERS_FREQUENCY_DAILY_MULTI`
   - `TRANS_KEY_FLOW_HELPERS_FREQUENCY_HOURLY`
   - `TRANS_KEY_CFOF_CHORES_INPUT_DAILY_MULTI_TIMES`
   - `TRANS_KEY_CFOF_CHORES_INPUT_CUSTOM_INTERVAL_HOURS`
   - `TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET` (validation error)
   - `TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_KIDS` (validation error)
   - `TRANS_KEY_CFOF_ERROR_HOURLY_REQUIRES_COMPATIBLE_RESET` (validation error)
   - `TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_REQUIRED` (validation error)
   - `TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_INVALID_FORMAT` (validation error)
   - `TRANS_KEY_STEP_CHORES_DAILY_MULTI_TITLE`
   - `TRANS_KEY_STEP_CHORES_DAILY_MULTI_DESCRIPTION`

4. **Add validation for Features 2 & 3 incompatibility in flow_helpers.py** (~line 870+ in `build_chores_data()`)
   ```python
   # Feature 2: DAILY_MULTI requires UPON_COMPLETION, AT_DUE_DATE_ONCE, or AT_DUE_DATE_MULTI
   if (
       recurring_frequency == const.FREQUENCY_DAILY_MULTI
       and approval_reset_type not in [
           const.APPROVAL_RESET_UPON_COMPLETION,
           const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
           const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
       ]
   ):
       raise vol.Invalid(
           message="",
           error_message=const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET,
       )
   
   # Feature 2: DAILY_MULTI + INDEPENDENT incompatible with multiple kids (dual helper forms)
   if (
       recurring_frequency == const.FREQUENCY_DAILY_MULTI
       and chore_type == const.CHORE_TYPE_INDEPENDENT
       and len(assigned_kid_ids) > 1
   ):
       raise vol.Invalid(
           message="",
           error_message=const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_KIDS,
       )
   
   # Feature 3: HOURLY incompatible with AT_MIDNIGHT_* (resets mid-cycle)
   if (
       recurring_frequency == const.FREQUENCY_HOURLY
       and approval_reset_type in [
           const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
           const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
       ]
   ):
       raise vol.Invalid(
           message="",
           error_message=const.TRANS_KEY_CFOF_ERROR_HOURLY_REQUIRES_COMPATIBLE_RESET,
       )
   ```

5. **Add entries to translations/en.json**
   ```json
   {
     "options": {
       "step": {
         "chores_daily_multi": {
           "title": "Set daily times for: {chore_name}",
           "description": "Enter times when this chore should be available each day. Use 24-hour format (HH:MM) separated by | (pipe).\n\nExample: 07:00|12:00|18:00 for morning, midday, and evening.\n\nLeave blank to use default daily schedule."
         }
       }
     },
     "config": {
       "error": {
         "cfof_error_daily_multi_requires_compatible_reset": "Daily multi frequency requires 'upon completion', 'at due date (once)', or 'at due date (multi)' reset type. Cannot use 'at midnight' reset types which block subsequent time slots.",
         "cfof_error_daily_multi_independent_multi_kids": "Daily multi frequency with independent chores only supports single kid selection. Multiple kids would require separate due dates per kid, which conflicts with shared daily time slots.",
         "cfof_error_hourly_requires_compatible_reset": "Hourly frequency requires 'upon completion' or 'at due date' reset types. 'At midnight' resets interrupt hourly cycles.",
         "cfof_error_daily_multi_times_required": "Daily multi frequency requires time list. Please enter times in HH:MM format separated by | (e.g., 08:00|17:00).",
         "cfof_error_daily_multi_times_invalid_format": "Invalid time format. Please use HH:MM format with 24-hour time separated by | (e.g., 08:00|12:00|18:00)."
       }
     },
     "selector": {
       "recurring_frequency": {
         "options": {
           "custom_from_complete": "Custom interval from completion date",
           "daily_multi": "Multiple times per day (requires time list)",
           "hourly": "Every X hours (1-23 hour intervals)"
         }
       }
     }
   }
   ```

**Validation**:
```bash
grep -n "FREQUENCY_CUSTOM_FROM_COMPLETE\|FREQUENCY_DAILY_MULTI" custom_components/kidschores/const.py
./utils/quick_lint.sh --fix
```

**Key Issues**:
- Feature 2 fundamentally incompatible with AT_MIDNIGHT_* reset types (validation prevents these combinations)
- Rationale: DAILY_MULTI needs immediate advancement to next slot, but AT_MIDNIGHT_* keeps chore APPROVED until midnight (blocks subsequent time slots)

### CRITICAL BEHAVIOR: Overdue Completion Timing

**Discovered Issue**: When using `AT_DUE_DATE_MULTI` with DAILY_MULTI, overdue completions create delayed slot advancement:

**Scenario**: 
- Chore due at 7am (AT_DUE_DATE overdue handling)
- Kid completes at 8am (1 hour overdue) 
- Parent approves immediately
- **Reset doesn't happen until 6pm** (next due time passes)
- **Next day's 7am slot scheduled at 6pm**, not at approval time

**Root Cause** (coordinator.py line 8717+):
```python
# Reset only triggers when due_date passes, not at approval time
if current_datetime >= chore_due_date and reset_type == AT_DUE_DATE_MULTI:
    # Reschedule to next slot
```

**Recommendation**: **UPON_COMPLETION strongly preferred** for DAILY_MULTI
- Immediate slot advancement regardless of completion timing
- No delayed rescheduling behavior  
- Consistent user experience (complete → next slot available immediately)

**AT_DUE_DATE_MULTI acceptable** if user understands delayed advancement for overdue completions.

### Feature 2: Daily Multi Times UI Flow (Detailed Example)

**Main Chore Form** (`add_chore` or `edit_chore`):
1. User selects "Multiple times per day (requires time list)" from frequency dropdown
2. User fills other fields (name, points, reset type, etc.)
3. User clicks "Submit" 
4. **System routes to helper form** (instead of creating chore immediately)

**Helper Form** (`chores_daily_multi` step):
```
┌─────────────────────────────────────────────────────────────┐
│ Set daily times for: Feed the pets                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Enter times when this chore should be available each day.  │
│ Use 24-hour format (HH:MM) separated by | (pipe).         │
│                                                             │
│ Example: 07:00|12:00|18:00 for morning, midday, and        │
│ evening.                                                    │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Daily Times: │08:00|17:00                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌──────────┐  ┌────────┐                                  │
│ │ Submit   │  │ Back   │                                  │
│ └──────────┘  └────────┘                                  │
└─────────────────────────────────────────────────────────────┘
```

**Processing**:
- Parse "08:00|17:00" → `[time(8,0), time(17,0)]` 
- Store as `daily_multi_times` field in chore data
- First due date = today at 8:00 AM (or 5:00 PM if past 8:00 AM)

**Validation Examples**:
- ✅ `"08:00|17:00"` → Two times (8am, 5pm)
- ✅ `"07:00|12:00|18:00"` → Three times (7am, noon, 6pm)
- ✅ `"23:30|06:45"` → Late night and early morning
- ❌ `"8am|5pm"` → Invalid format (not 24-hour HH:MM)
- ❌ `"25:00|17:00"` → Invalid hour (25 doesn't exist)
- ❌ `"08:00"` → Only one time (use regular DAILY instead)
- ❌ `""` → Empty (validation error)

### Feature 2: Timezone Handling Strategy

**Challenge**: User enters times in local timezone ("08:00|17:00"), but system stores/works with UTC.

**Solution**: Use existing `kc_helpers` timezone infrastructure:

1. **UI Input**: User enters pipe-separated local times: `"08:00|17:00"`
2. **Parsing**: `parse_daily_multi_times()` combines with reference date + `const.DEFAULT_TIME_ZONE`
   - `"08:00"` + today's date + system timezone → timezone-aware datetime
   - Convert to UTC for storage/comparison: `dt_util.as_utc(dt_with_tz)`
3. **Scheduling**: Next slot calculation compares UTC times from parsed slots
4. **Storage**: Times string stored as-is (`"08:00|17:00"`), timezone applied at parse-time

**Follows existing patterns**:
- `flow_helpers.py` line 924+: `kh.normalize_datetime_input()` with `DEFAULT_TIME_ZONE`
- DateTimeSelector usage (line 831): Already handles local→UTC conversion
- All due dates stored as UTC ISO strings in `.storage/kidschores_data`

**Cross-timezone behavior**: Times interpreted in system's `const.DEFAULT_TIME_ZONE` (like all other chore scheduling)

### Feature 2: INDEPENDENT Chore Flow Complexity

**Problem**: INDEPENDENT chores with multiple kids create dual helper forms:

**Current Flow** (options_flow.py line 1459):
1. User creates INDEPENDENT chore with multiple kids selected
2. After main chore form: **First helper** = `edit_chore_per_kid_dates()` (different due dates per kid)
3. If DAILY_MULTI selected: **Second helper** = `chores_daily_multi()` (collect times)
4. Result: Two consecutive popup forms = confusing UX

**Solution**: **Restrict DAILY_MULTI to single kid for INDEPENDENT chores**

**Allowed Combinations**:
- ✅ **SHARED + DAILY_MULTI**: All kids, any number → only `chores_daily_multi()` helper
- ✅ **INDEPENDENT + single kid + DAILY_MULTI**: Only `chores_daily_multi()` helper  
- ❌ **INDEPENDENT + multiple kids + DAILY_MULTI**: Blocked by validation

**Rationale**:
- DAILY_MULTI means "same times for everyone" (7am, 6pm)
- Multiple kids with different due dates conflicts with "same times" concept
- Single kid INDEPENDENT + DAILY_MULTI = valid use case (kid can do morning OR evening slot)

### Alternative Scheduling Syntax Consideration

**Current Format**: Pipe-separated times (`"08:00|17:00"`)
- ✅ Simple for users to understand
- ✅ Clear validation (`HH:MM` format only)
- ❌ Limited to daily recurrence only

**Cron-style Format**: Standard Unix cron syntax
- Examples: 
  - `"0 8,17 * * *"` → 8am and 5pm daily
  - `"0 8,17 * * 1-5"` → 8am and 5pm weekdays only
  - `"*/30 9-17 * * *"` → Every 30 minutes during business hours
- ✅ Industry standard, very flexible
- ✅ Could support weekly patterns, specific days, etc.
- ❌ Complex for average users to learn
- ❌ Requires cron parsing library
- ❌ Much broader scope than current "daily multi-times" feature

**Recommendation**: **Start with simple pipe format, consider cron as future enhancement**
- Phase 1: Implement `"HH:MM|HH:MM"` for daily multi-times only
- Future consideration: Add cron syntax as advanced option (keeping pipe format for simplicity)

### Feature 3: Hourly Frequency Analysis

**Use Cases**:
- "Take medication every 4 hours"
- "Check on baby every 2 hours" 
- "Water plants every 6 hours during growing season"

**Implementation Pattern**: 
- Leverage existing FREQUENCY_CUSTOM logic (coordinator.py line 8912+)
- Add branch: `if freq == FREQUENCY_HOURLY:`
- Use `custom_interval_hours` instead of `custom_interval_days`
- Helper function: `adjust_datetime_by_interval(completion_date, hours=X)`

**AT_MIDNIGHT Reset Analysis**:

**Scenario**: "Every 4 hours" starting at 6am
- Natural cycle: 6am → 10am → 2pm → 6pm → 10pm → 2am → 6am...
- With AT_MIDNIGHT_ONCE: Complete at 10pm → Reset at midnight → Next due = 12am + 4h = 4am
- **Problem**: 4am ≠ natural 2am cycle (off by 2 hours)

**Conclusion**: AT_MIDNIGHT_* breaks hourly cycles by forcing midnight boundary reset instead of natural intervals.

**Validation Logic**: Block AT_MIDNIGHT_* for FREQUENCY_HOURLY (regardless of interval length)

---

### Phase 2 – Feature 1 Core Logic (0%)

**Goal**: Implement completion-based rescheduling by passing last_completed timestamp

**Steps**:

1. **Modify `_calculate_next_due_date_from_info()` in coordinator.py** (~line 8912)
   - Add parameter: `completion_timestamp: datetime | None = None`
   - Add branch for FREQUENCY_CUSTOM_FROM_COMPLETE:
     ```python
     if freq == const.FREQUENCY_CUSTOM_FROM_COMPLETE:
         # Use completion timestamp if available, fallback to due_date
         base_date = completion_timestamp if completion_timestamp else current_due_utc
         
         next_due_utc = kh.adjust_datetime_by_interval(
             base_date=base_date,
             interval_unit=custom_unit,
             delta=custom_interval,
             require_future=True,
             return_type=const.HELPER_RETURN_DATETIME,
         )
     ```
   - Keep existing FREQUENCY_CUSTOM branch unchanged (always uses due_date as base)

2. **Update `_reschedule_chore_next_due_date()` (SHARED chores)** (~line 8968)
   - Extract `last_completed` from chore_info
   - Parse to UTC: `completion_utc = kh.parse_datetime_to_utc(chore_info.get(const.DATA_CHORE_LAST_COMPLETED))`
   - Pass to calculation function:
     ```python
     next_due_utc = self._calculate_next_due_date_from_info(
         original_due_utc,
         chore_info,
         completion_timestamp=completion_utc  # NEW parameter
     )
     ```

3. **Update `_reschedule_chore_next_due_date_for_kid()` (INDEPENDENT chores)** (~line 9098)
   - Extract per-kid `last_completed` from kid's chore data
   - Parse to UTC and pass to calculation function
   - Note: INDEPENDENT chores have per-kid completion timestamps

**Validation**:
```bash
pytest tests/test_frequency_custom_from_complete.py -v
mypy custom_components/kidschores/coordinator.py
```

**Key Issues**:
- Must preserve existing FREQUENCY_CUSTOM behavior (always from due_date)
- Fallback required: If no last_completed timestamp, use due_date (for manual rescheduling)
- SHARED vs INDEPENDENT: Different timestamp sources (chore-level vs per-kid chore data)

---

### Phase 3 – Feature 2 Helper Flow (0%)

**Goal**: Create multi-daily times collection form (pattern: like `edit_chore_per_kid_dates`)

**Steps**:

1. **Add step constant to const.py** (~line 200)
   ```python
   CFOF_STEP_CHORES_DAILY_MULTI: Final = "chores_daily_multi"
   ```

2. **Create `async_step_chores_daily_multi()` in options_flow.py** (~after line 1800, after `edit_chore_per_kid_dates`)
   - **Pattern**: Similar to `async_step_edit_chore_per_kid_dates()` (lines 1574+)
   - Show title with chore name
   - Description: Explain pipe-separated format (`07:00|12:00|18:00`)
   - Single text field for times input
   - Validation: Parse times using new `kh.parse_daily_multi_times()` helper
   - On submit: Store in `daily_multi_times` field
   - Return to main menu or edit chore form

3. **Modify `async_step_add_chore()` and `async_step_edit_chore()` to route to helper**
   - After chore form submit, check:
     ```python
     if (
         user_input.get(const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY) == const.FREQUENCY_DAILY_MULTI
         and const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES not in user_input
     ):
         # Store chore data in temp state
         self._chore_being_edited = updated_chore_data
         # Route to helper form
         return await self.async_step_chores_daily_multi()
     ```

4. **Add helper function `parse_daily_multi_times()` to kc_helpers.py** (~line 1450)
   ```python
   def parse_daily_multi_times(
       times_str: str,
       reference_date: str | date | datetime | None = None,
       timezone_info: tzinfo | None = None
   ) -> list[datetime]:
       """Parse pipe-separated time strings into timezone-aware datetime objects.
       
       Args:
           times_str: Pipe-separated times in HH:MM format (e.g., "08:00|12:00|18:00")
           reference_date: Date to combine with times (defaults to today)
           timezone_info: Timezone for the times (defaults to const.DEFAULT_TIME_ZONE)
       
       Returns:
           List of timezone-aware datetime objects sorted chronologically.
           Empty list if parsing fails or no valid times found.
       
       Example:
           >>> parse_daily_multi_times("08:00|17:00")
           [datetime(2026, 1, 13, 8, 0, tzinfo=...), datetime(2026, 1, 13, 17, 0, tzinfo=...)]
       """
       if not times_str or not isinstance(times_str, str):
           return []
       
       # Default to today's date if no reference provided
       if reference_date is None:
           base_date = get_today_local_date()
       else:
           # Use normalize_datetime_input to handle various date formats
           normalized_dt = normalize_datetime_input(
               reference_date, 
               return_type=const.HELPER_RETURN_DATE
           )
           base_date = normalized_dt if isinstance(normalized_dt, date) else get_today_local_date()
       
       # Default to system timezone if none provided
       tz_info = timezone_info or const.DEFAULT_TIME_ZONE
       
       result = []
       for time_part in times_str.split("|"):
           time_part = time_part.strip()
           if not time_part:
               continue
           
           try:
               hour, minute = time_part.split(":")
               time_obj = time(int(hour), int(minute))
               
               # Combine date + time and apply timezone
               dt_local = datetime.combine(base_date, time_obj)
               dt_with_tz = dt_local.replace(tzinfo=tz_info)
               
               result.append(dt_with_tz)
           except (ValueError, AttributeError):
               const.LOGGER.warning(
                   "Invalid time format in daily_multi_times: %s (expected HH:MM)",
                   time_part,
               )
               continue
       
       return sorted(result)
   ```

**Validation**:
```bash
pytest tests/test_options_flow.py::test_daily_multi_helper_form -v
./utils/quick_lint.sh --fix
```

**Key Issues**:
- Helper form follows existing pattern (`edit_chore_per_kid_dates`)
- Validation happens in helper step (not main chore form)
- Store as string (`"08:00|12:00|18:00"`), parse when needed

---

### Phase 4 – Features 2 & 3 Core Logic (0%)

**Goal**: Implement multi-time-per-day scheduling (Feature 2) and hourly intervals (Feature 3)

**Steps**:

1. **Implement next time slot calculation in coordinator.py** (~line 9000)
   ```python
   def _calculate_next_multi_daily_due(
       self,
       chore_info: dict[str, Any],
       base_due_utc: datetime
   ) -> datetime | None:
       """Calculate next due datetime for DAILY_MULTI frequency.
       
       Args:
           chore_info: Chore data containing daily_multi_times
           base_due_utc: Current due datetime
       
       Returns:
           Next due datetime (same day if before last slot, next day if past)
       """
       times_str = chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")
       if not times_str:
           const.LOGGER.warning("DAILY_MULTI frequency missing times string")
           return None
       
       # Convert base_due_utc to local timezone for date reference
       base_local = dt_util.as_local(base_due_utc)
       base_date = base_local.date()
       
       # Parse times with timezone awareness (converts to local, then to UTC)
       time_slots_local = kh.parse_daily_multi_times(
           times_str,
           reference_date=base_date,
           timezone_info=const.DEFAULT_TIME_ZONE
       )
       
       if not time_slots_local:
           const.LOGGER.warning("DAILY_MULTI frequency has no valid times")
           return None
       
       # Convert time slots to UTC for comparison
       time_slots_utc = [dt_util.as_utc(dt) for dt in time_slots_local]
       current_utc = dt_util.utcnow()
       
       # Find next available slot
       for slot_utc in time_slots_utc:
           if slot_utc > current_utc:
               return slot_utc
       
       # Past all slots today, wrap to first slot tomorrow
       tomorrow_local = (base_local + timedelta(days=1)).replace(
           hour=time_slots_local[0].hour,
           minute=time_slots_local[0].minute,
           second=0,
           microsecond=0
       )
       return dt_util.as_utc(tomorrow_local)
   ```

2. **Update `_calculate_next_due_date_from_info()` to handle DAILY_MULTI** (~line 8912)
   ```python
   if freq == const.FREQUENCY_DAILY_MULTI:
       return self._calculate_next_multi_daily_due(chore_info, current_due_utc)
   ```

3. **Extend `_generate_events_for_chore()` in calendar.py** (~line 321)
   - Add branch for FREQUENCY_DAILY_MULTI
   - Parse time slots using `kh.parse_daily_multi_times()`
   - Generate separate CalendarEvent for each time slot per day
   - Event summary: "Chore Name (Morning)" / "(Midday)" / "(Evening)" based on time
   - Event start/end: slot_time to slot_time+15min

4. **Update approval reset to work with DAILY_MULTI**
   - After approval with AT_MIDNIGHT_MULTI, call reschedule to advance to next slot
   - Chore remains available multiple times per day until midnight

**Validation**:
```bash
pytest tests/test_frequency_daily_multi.py -v
pytest tests/test_calendar.py::test_daily_multi_events -v
```

**Key Issues**:
- Calendar generates N events per day (1 per time slot)
- Next slot calculation wraps to next day after last slot
- AT_MIDNIGHT_MULTI reset type allows multiple claims per day

**Feature 3: HOURLY Implementation**

4. **Add HOURLY frequency branch to `_calculate_next_due_date_from_info()`** (~line 8912)
   ```python
   if freq == const.FREQUENCY_HOURLY:
       interval_hours = int(chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL_HOURS, 1))
       if completion_timestamp:
           # Use completion time as base (Feature 1 pattern)
           base_datetime = completion_timestamp
       else:
           # Use due date as base (existing pattern)
           base_datetime = current_due_utc
       
       return kh.adjust_datetime_by_interval(
           base_datetime, 
           hours=interval_hours
       )
   ```

5. **Add `adjust_datetime_by_interval()` hours support to kc_helpers.py** (~line 1450)
   ```python
   def adjust_datetime_by_interval(
       base_dt: datetime, 
       days: int = 0, 
       hours: int = 0
   ) -> datetime:
       """Adjust datetime by specified interval.
       
       Args:
           base_dt: Starting datetime
           days: Number of days to add (default: 0)
           hours: Number of hours to add (default: 0)
       
       Returns:
           Adjusted datetime
       """
       return base_dt + timedelta(days=days, hours=hours)
   ```

6. **Add HOURLY to chore form schema** (flow_helpers.py)
   - Add number input field for hour interval when HOURLY selected
   - Validation: 1 ≤ hours ≤ 23 (24+ hours should use DAILY instead)

**Feature 3 Validation**:
```bash
pytest tests/test_frequency_hourly.py -v
./utils/quick_lint.sh --fix
```

---

### Phase 5 – Comprehensive Testing (0%)

**Goal**: Validate all scenarios and edge cases for all three features

**Steps**:

1. **Create test scenario: `tests/scenarios/scenario_enhanced_frequencies.yaml`**
   - Feature 1 chore: CUSTOM_FROM_COMPLETE with custom_interval=10 days
   - Feature 2 chore: DAILY_MULTI with times "07:00|12:00|18:00"  
   - Feature 3 chore: HOURLY with custom_interval_hours=4
   - Include both SHARED and INDEPENDENT chores

2. **Create test file: `tests/test_frequency_custom_from_complete.py`**
   - Test early completion (complete 3 days before due, verify next due = completion + interval)
   - Test late completion (complete 2 days after due, verify next due = completion + interval)
   - Test no completion timestamp (manual reschedule, verify uses due_date as fallback)
   - Test SHARED vs INDEPENDENT (different timestamp sources)

3. **Create test file: `tests/test_frequency_daily_multi.py`**
   - Test next slot calculation (before first, between slots, after last)
   - Test wrap to next day (past last slot, advances to first slot tomorrow)
   - Test timezone handling (local times → UTC comparison → correct next slot)
   - Test cross-timezone scenarios (if system timezone differs from test timezone)
   - Test calendar generates N events per day
   - Test multi-claim with AT_DUE_DATE_MULTI (can claim 3 times per day)
   - Test validation rejection (DAILY_MULTI + AT_MIDNIGHT_ONCE → error)

4. **Create test file: `tests/test_frequency_hourly.py`**
   - Test 4-hour interval (6am → 10am → 2pm → 6pm → 10pm → 2am cycle)
   - Test completion-based rescheduling (complete at 11am, next due = 3pm)
   - Test interval range validation (1-23 hours accepted, 24+ rejected)
   - Test cross-midnight cycles (10pm → 2am works correctly)

5. **Create test file: `tests/test_frequency_validation.py`**
   - **DAILY_MULTI validation**:
     - Test DAILY_MULTI + UPON_COMPLETION → accepted
     - Test DAILY_MULTI + AT_DUE_DATE_ONCE → accepted
     - Test DAILY_MULTI + AT_DUE_DATE_MULTI → accepted
     - Test DAILY_MULTI + AT_MIDNIGHT_ONCE → rejected (validation error)
     - Test DAILY_MULTI + AT_MIDNIGHT_MULTI → rejected (validation error)
     - Test invalid time format ("8am|5pm") → rejected
     - Test empty times string → rejected
     - **INDEPENDENT chore restrictions**:
       - Test DAILY_MULTI + INDEPENDENT + single kid → accepted
       - Test DAILY_MULTI + INDEPENDENT + multiple kids → rejected (validation error)
       - Test DAILY_MULTI + SHARED + multiple kids → accepted (no restriction)
   - **HOURLY validation**:
     - Test HOURLY + UPON_COMPLETION → accepted
     - Test HOURLY + AT_DUE_DATE_ONCE → accepted
     - Test HOURLY + AT_DUE_DATE_MULTI → accepted  
     - Test HOURLY + AT_MIDNIGHT_ONCE → rejected (validation error)
     - Test HOURLY + AT_MIDNIGHT_MULTI → rejected (validation error)
     - Test interval validation (0 hours → error, 25 hours → error)

6. **Run full test suite**
   ```bash
   pytest tests/test_frequency_*.py -v
   pytest tests/test_workflow_*.py -v
   pytest tests/ --cov=custom_components/kidschores --cov-report term-missing
   ./utils/quick_lint.sh --fix
   mypy custom_components/kidschores/
   ```

**Validation**:
- All tests pass
- No regressions in existing frequency behavior
- Coverage >95% for new code

**Key Issues**:
- Must validate both features work with SHARED and INDEPENDENT completion criteria
- Must validate Feature 2 validation rejection (incompatible reset types)
- Must not break existing FREQUENCY_DAILY, FREQUENCY_CUSTOM, etc.

---

## Notes & Context

### Feature 1: FREQUENCY_CUSTOM_FROM_COMPLETE

**What it is**: Reschedule from completion date instead of due date

**Example**:
- Chore due: January 10
- Kid completes: January 7 (3 days early)
- Current: Next due = January 10 + 10 days = January 20
- **Enhanced**: Next due = January 7 + 10 days = January 17

**Implementation**: Simple - just pass `last_completed` timestamp to existing reschedule calculation

**Works with**: All approval reset types (no conflicts)

### Feature 2: FREQUENCY_DAILY_MULTI

**What it is**: Multiple specific times per day (e.g., "Feed pet: 7am and 6pm")

**Example**:
- Times: "07:00|12:00|18:00"
- Kid sees 3 opportunities per day to complete chore
- Each completion advances to next time slot (or next day after last slot)

**Implementation**: Complex - requires helper form (collect times), time parsing, calendar multi-event, next-slot calculation

**Works with**: AT_MIDNIGHT_* ONLY (not AT_DUE_DATE or UPON_COMPLETION)

**Why restricted**: 
- DAILY_MULTI needs chore available at specific times per day (7am, 12pm, 6pm)
- AT_MIDNIGHT_* resets at midnight (allows multiple claims throughout day)
- AT_DUE_DATE_* resets when due date passes (doesn't work with intra-day scheduling)
- UPON_COMPLETION resets immediately (doesn't respect time slots)

### Existing Helper Pattern Reference

**Per-kid dates helper** (`options_flow.py` lines 1574+):
- Shows after main chore form for INDEPENDENT chores
- Collects individual due dates per kid
- Validates dates, applies template date option
- Stores in `per_kid_due_dates` dictionary

**Daily multi times helper** (to be created):
- Shows after main chore form for DAILY_MULTI frequency
- Collects pipe-separated time list
- Validates format (HH:MM|HH:MM)
- Stores in `daily_multi_times` string field

---

**Status**: Plan complete, ready for implementation
