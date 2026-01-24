# Due Window Feature Implementation Plan

## Initiative snapshot

- **Name / Code**: Due Window Feature - Enhanced Chore State Management
- **Target release / milestone**: v0.6.0
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: In Progress

## Summary & immediate steps

| Phase / Step             | Description                             | % complete | Quick notes                                |
| ------------------------ | --------------------------------------- | ---------- | ------------------------------------------ |
| Phase 1a – Frequencies   | Add missing frequency options to chores | 100%       | ✅ Complete - all tests pass               |
| Phase 1b – Configuration | Add due window per-chore settings       | 100%       | ✅ Duration parser, constants, flow fields |
| Phase 2 – State Logic    | Implement DUE state calculation         | 100%       | ✅ New state between PENDING and OVERDUE   |
| Phase 3 – Service/Forms  | Update service schemas and forms        | 100%       | ✅ Complete - UI tested and verified       |
| Phase 4 – Notifications  | Add due window notification triggers    | 0%         | Integrate with existing notification sys   |

1. **Key objective** – Add a "DUE" state that activates X hours/days before chore due date, providing clearer user guidance on when chores should be started vs just available.

2. **Summary of recent work** – **Phase 1a complete**: Added quarterly, yearly, and period-end frequencies. **Phase 1b complete**: Duration parser, constants, flow fields. **Phase 2 complete**: DUE state logic in sensors/coordinator. **Phase 3 complete**: Service schemas updated, UI tested and verified. Documentation updated with due window configuration details.

3. **Next steps (short term)** – Proceed to Phase 4 for notification system updates. Implement due window notification triggers and configurable reminder offsets.

4. **Risks / blockers**
   - Need to ensure backward compatibility with existing chore states
   - Dashboard helper integration will need updates for proper due window display
   - ⏸️ **Notification system details deferred to Phase 4** - Changes coming to notification system, will analyze when ready
   - ✅ Verified kc_helpers.py scheduling functions support all new frequency options (reuses badge code)

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Storage architecture and system settings
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Constants and translation patterns
   - Current chore state logic: `sensor.py` lines 720-750, `coordinator_chore_operations.py`

6. **Decisions & completion check**
   - **Decisions captured**:
     - DUE state will be computed/display state, not stored state (minimal storage impact)
     - Global system settings for default due window with per-chore override capability
     - Replace fixed 30-minute due date reminders with configurable notification system
     - Support multiple notification triggers: due window start + configurable reminder offset
     - Integrate with existing notification infrastructure with enhanced spam prevention
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, testing, documentation) before requesting owner approval.

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after each implementation phase
- **Detailed tracking**: Use phase sections below for granular progress tracking

## Detailed phase tracking

### Phase 1a – Missing Frequency Options

- **Goal**: Add missing frequency options to chores to match badge capabilities
- **Ready for implementation**: ✅ YES
- **Status**: ✅ COMPLETE

#### Implementation Reference

**Current Chore Frequencies** (`const.py` line ~3042 `CHORE_FREQUENCY_OPTIONS`):

- `FREQUENCY_NONE`, `FREQUENCY_DAILY`, `FREQUENCY_DAILY_MULTI`, `FREQUENCY_WEEKLY`
- `FREQUENCY_BIWEEKLY`, `FREQUENCY_MONTHLY`, `FREQUENCY_CUSTOM`, `FREQUENCY_CUSTOM_FROM_COMPLETE`

**Frequencies to Add** (already used in badges `BADGE_RESET_SCHEDULE_OPTIONS` line ~3145):

- `FREQUENCY_QUARTERLY` (const.py line 146)
- `FREQUENCY_YEARLY` (const.py line 148)
- `PERIOD_WEEK_END` (const.py line 155)
- `PERIOD_MONTH_END` (const.py line 153)
- `PERIOD_QUARTER_END` (const.py line 154)
- `PERIOD_YEAR_END` (const.py line 156)

**Service Schema** (`services.py` line ~232 `_CHORE_FREQUENCY_VALUES`):

- Currently only: `FREQUENCY_NONE`, `FREQUENCY_DAILY`, `FREQUENCY_WEEKLY`, `FREQUENCY_MONTHLY`
- Missing: `FREQUENCY_BIWEEKLY`, `FREQUENCY_QUARTERLY`, `FREQUENCY_YEARLY`, `FREQUENCY_CUSTOM`, `FREQUENCY_CUSTOM_FROM_COMPLETE`, all `PERIOD_*_END`

- **Steps / detailed work items**
  1. `[x]` Update frequency constants in `const.py` (line ~3042)
     - Added `FREQUENCY_QUARTERLY`, `FREQUENCY_YEARLY` to `CHORE_FREQUENCY_OPTIONS` list
     - Added `FREQUENCY_QUARTERLY`, `FREQUENCY_YEARLY` to `CHORE_FREQUENCY_OPTIONS_CONFIG_FLOW`
     - Added period-end frequencies: `PERIOD_WEEK_END`, `PERIOD_MONTH_END`, `PERIOD_QUARTER_END`, `PERIOD_YEAR_END` to both arrays
  2. `[x]` Update service schemas in `services.py` (line ~232)
     - Added all missing frequencies to `_CHORE_FREQUENCY_VALUES` array
     - Now includes: `FREQUENCY_BIWEEKLY`, `FREQUENCY_QUARTERLY`, `FREQUENCY_YEARLY`, `FREQUENCY_CUSTOM`, `FREQUENCY_CUSTOM_FROM_COMPLETE`, `PERIOD_WEEK_END`, `PERIOD_MONTH_END`, `PERIOD_QUARTER_END`, `PERIOD_YEAR_END`
  3. `[x]` Verify and add translation support
     - Verified `quarterly`, `yearly` translations exist in selector options
     - Added `week_end`, `month_end`, `quarter_end`, `year_end` to `selector.recurring_frequency.options`
     - Updated `services.yaml` frequency selector options (create_chore and update_chore)
     - Updated `translations/en.json` service field descriptions for frequency
  4. `[x]` Run quality gates
     - `./utils/quick_lint.sh --fix` ✅ Passed
     - `mypy custom_components/kidschores/` ✅ Zero errors
     - `python -m pytest tests/test_frequency*.py -v` ✅ 68 tests passed
     - `python -m pytest tests/test_chore_scheduling.py tests/test_chore_services.py -v` ✅ 93 tests passed
  5. `[ ]` Manual testing (user step)
     - Create chores with new frequency options in UI
     - Verify service calls accept new frequency values via Developer Tools
- **Key issues**
  - Verified `kc_helpers.py` dt*next_schedule() handles PERIOD*\*\_END frequencies (works from badge usage)
  - No schema version change needed - just string value options

### Phase 1b – Configuration & Constants

- **Goal**: Add per-chore due window and reminder configuration fields
- **Ready for implementation**: ✅ YES

#### Design Decisions

**Architecture Clarification** (per DEVELOPMENT_STANDARDS.md):

- `CONF_*` = **ONLY** system-wide settings in `config_entry.options` (9 existing) - NOT expanded
- Due window/reminder = **Per-chore settings** stored with chore data
- `CFOF_CHORES_INPUT_*` = Form input fields for add/edit chore flows
- `DATA_CHORE_*` = Storage fields in `.storage/kidschores_data`

**Duration Offset Format**:

- Default unit: minutes (e.g., `"30"` = 30 minutes)
- Full format: `"1d 6h 30m"` for days/hours/minutes
- Value `"0"` = feature disabled for this chore
- Stored as string, parsed to timedelta at runtime

**New Constants**:

```python
# Flow input fields (add/edit chore forms)
CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET: Final = "chore_due_window_offset"
CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET: Final = "chore_due_reminder_offset"

# Storage fields (per-chore data)
DATA_CHORE_DUE_WINDOW_OFFSET: Final = "chore_due_window_offset"
DATA_CHORE_DUE_REMINDER_OFFSET: Final = "chore_due_reminder_offset"
DATA_CHORE_NOTIFY_ON_DUE_WINDOW: Final = "notify_on_due_window"
DATA_CHORE_NOTIFY_DUE_REMINDER: Final = "notify_due_reminder"
```

- **Steps / detailed work items**
  1. `[ ]` Add duration parser helper to `kc_helpers.py`
     - `parse_duration(value: str) -> timedelta`: Parse "1d 6h 30m" format (default: minutes)
     - `format_duration(td: timedelta) -> str`: Convert timedelta back to string
     - Handle: empty/None → disabled, "0" → disabled, invalid format → log warning + return 0
  2. `[ ]` Add per-chore constants to `const.py`
     - Flow inputs: `CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET`, `CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET`
     - Storage: `DATA_CHORE_DUE_WINDOW_OFFSET`, `DATA_CHORE_DUE_REMINDER_OFFSET`
     - Notifications: `DATA_CHORE_NOTIFY_ON_DUE_WINDOW`, `DATA_CHORE_NOTIFY_DUE_REMINDER`
     - State: `CHORE_STATE_DUE`
     - Defaults: `DEFAULT_DUE_WINDOW_OFFSET` ("0" = disabled), `DEFAULT_DUE_REMINDER_OFFSET` ("30m")
     - Translation keys: `TRANS_KEY_STATE_DUE`, `TRANS_KEY_CFOF_CHORES_DUE_WINDOW_*`
  3. `[ ]` Update chore notification options
     - Add to `CHORE_NOTIFICATION_OPTIONS` array: due_window, due_reminder options
     - Add to `CHORE_NOTIFICATIONS_MAPPING` for notification dispatch
  4. `[ ]` Update add/edit chore flow schemas
     - Add due_window_offset and due_reminder_offset fields to chore forms
     - Add duration format hint in field descriptions
  5. `[ ]` Update translation files
     - Add due window/reminder labels and descriptions in `translations/en.json`
     - Add state translation for "Due" state
     - Add notification option translations
  6. `[ ]` Test constant integration
     - Run `./utils/quick_lint.sh --fix` to validate constants
     - Run `mypy` to verify type hints
     - Test duration parser with various inputs
- **Key issues**
  - "0" or empty = disabled (no due window/reminder for this chore)
  - Duration parser must handle malformed input gracefully

### Phase 2 – State Logic Implementation

- **Goal**: Implement due state calculation logic in coordinator and sensor classes
- **Steps / detailed work items**
  1. `[x]` Add due window calculation helper to `coordinator_chore_operations.py`
     - `chore_is_due(kid_id | None, chore_id) -> bool`: Check if chore is in due window
     - `get_chore_due_window_start(kid_id, chore_id) -> datetime | None`: Calculate due window start time
     - kid_id=None uses chore-level due date (for global sensor)
  2. `[x]` Update chore state calculation in `sensor.py`
     - Modify `native_value` property in `ChoreStatusSensor` (around line 720)
     - Add DUE state: checked at end, only if would otherwise be PENDING
     - Insert `chore_is_due()` check before returning PENDING
  3. `[x]` Update dashboard helper state aggregation
     - Modify `sensor.py` dashboard helper logic to handle DUE state
     - Updated `_build_chore_minimal_attributes()` and `native_value()` in KidDashboardHelperSensor
     - Updated `_calculate_primary_group()` to put DUE chores in "today" group
  4. `[x]` Add due window metadata to chore status attributes
     - Added `due_window_start` attribute to show when due period began
     - Added `time_until_due` calculated attribute (excluded `time_until_overdue` per user request)
  5. `[x]` Update state icons and colors for DUE state
     - Already existed in `icons.json`: `"due": "mdi:clock"` (verified)
  6. `[x]` Update global chore sensor (SystemChoreSharedStateSensor)
     - Updated `native_value` to check `chore_is_due(None, chore_id)` when state is PENDING
     - Uses shared coordinator helper (refactored from duplicate local method)
  7. `[x]` Test state calculation logic
     - All 894 tests pass after Phase 2 implementation
     - Lint and mypy pass with zero errors
- **Key issues**
  - ✅ Performance: Uses same coordinator helper pattern as existing state checks
  - ✅ DUE state doesn't interfere - only checked when would be PENDING
  - ✅ Timezone: Uses kh.dt_to_utc() and dt_util.utcnow() consistently
  - ✅ Shared helper: `chore_is_due(kid_id | None, chore_id)` works for both per-kid and global sensors

### Phase 3 – Frontend & Dashboard Integration

- **Goal**: Update entity sensors, dashboard helpers, and UI representations for due window display
- **Status**: ✅ COMPLETE
- **Steps / detailed work items**
  1. `[x]` ~~Update options flow for due window and notification configuration~~ **NOT NEEDED**
     - Per-chore only settings, no global system configuration
     - Form fields already exist in `flow_helpers.py` (lines 674, 676, 996)
  2. `[x]` ~~Add per-chore due window configuration to chore forms~~ **ALREADY DONE**
     - Form fields exist in `flow_helpers.py` (CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET, CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET)
  3. `[x]` ~~Update dashboard helper for due window display~~ **NOT NEEDED**
     - Dashboard helper already returns `status: "due"` for chores in due window (Phase 2)
     - DUE chores already grouped in "today" bucket via `_calculate_primary_group()`
     - Detailed attributes (`time_until_due`, `time_until_overdue`) available via `state_attr(chore.eid, 'attr')` from ChoreStatusSensor
     - Dashboard helper intentionally provides minimal attributes (6 fields) for performance
  4. `[x]` Update service schemas for due window support
     - Added `SERVICE_FIELD_CHORE_CRUD_DUE_WINDOW_OFFSET` and `SERVICE_FIELD_CHORE_CRUD_DUE_REMINDER_OFFSET` to const.py
     - Added `due_window_offset` and `due_reminder_offset` fields to `CREATE_CHORE_SCHEMA` in services.py
     - Added `due_window_offset` and `due_reminder_offset` fields to `UPDATE_CHORE_SCHEMA` in services.py
     - Added mapping to `_SERVICE_TO_CHORE_DATA_MAPPING` (service field → storage field)
     - Added field descriptions to `services.yaml` for both create_chore and update_chore
  5. `[x]` Test UI integration
     - ✅ Verified due window fields appear in chore creation/edit forms
     - ✅ Tested service calls accept due_window_offset and due_reminder_offset via Developer Tools
     - ✅ Validated dashboard helper updates reflect due window state changes
     - ✅ Confirmed primary_group calculation keeps chores in correct group across state transitions
     - ✅ Updated documentation (Configuration:-Chores.md, Technical:-Chores.md, Technical:-Chore-Detail.md)
     - ✅ Added "due" state to dashboard state_map (kc_dashboard_all.yaml)
     - ✅ Fixed primary_group to check due window status (sensor.py)
- **Key issues**
  - Need to decide on UX for per-chore overrides (checkboxes, separate fields, etc.)
  - Consider mobile UI space constraints for additional form fields
  - Dashboard helper performance impact from additional due window calculations

### Phase 4 – Enhanced Notifications & Automation

- **Goal**: Replace fixed 30-minute due date reminders with configurable notification system and integrate due window notifications
- **Steps / detailed work items**
  1. `[ ]` Migrate from fixed 30-minute reminder system
     - Locate current 30-minute reminder logic in coordinator notification system
     - Replace with configurable timing based on new `CONF_REMINDER_*` settings
     - Ensure backward compatibility during migration (default to 30 minutes if not configured)
  2. `[ ]` Add due window notification triggers to coordinator
     - Modify coordinator update cycle to detect PENDING → DUE state transitions
     - Add due window notification dispatch logic (trigger once when entering due window)
     - Add configurable reminder notification logic (trigger at specified offset before due)
     - Implement notification deduplication to prevent spam
  3. `[ ]` Create enhanced notification message templates
     - Update existing due date reminder templates to use configurable timing
     - Create new due window start notification templates ("Chore now due")
     - Add configurable reminder templates with timing context
     - Include chore details, due date, time remaining, and due window status
  4. `[ ]` Update notification preferences and controls
     - Add per-kid notification preferences for due window alerts
     - Add per-kid notification preferences for configurable reminders
     - Allow users to enable/disable due window vs reminder notifications independently
     - Maintain existing notification delivery mechanisms (persistent, mobile, etc.)
  5. `[ ]` Implement notification timing logic
     - Create helper functions to calculate due window start time
     - Create helper functions to calculate configurable reminder time
     - Add notification scheduling that respects both due window and reminder timing
     - Ensure notifications don't conflict (due window start vs reminder timing)
  6. `[ ]` Update state change automation integration
     - Ensure Home Assistant automations can trigger on DUE state changes
     - Add due window and reminder notification events to automation system
     - Test automation triggers with various notification scenarios
     - Provide automation examples for common notification patterns
  7. `[ ]` Test enhanced notification system
     - Verify migration from 30-minute fixed reminders works correctly
     - Test due window notifications trigger at correct times
     - Test configurable reminder notifications with various timing settings
     - Validate notification frequency controls prevent spam
     - Test notification content accuracy and formatting
- **Key issues**
  - Migration complexity from fixed to configurable reminder system
  - Notification timing conflicts (due window start vs configurable reminder)
  - Performance impact of additional notification calculations and triggers
  - User confusion during transition from simple to complex notification options

## Additional Considerations

### Migration & Compatibility

- No storage schema changes needed (due window is computed state)
- Existing chores will use global due window settings by default
- Backward compatibility maintained (DUE state is additive)

### Enhanced Notification System

> ⏸️ **DEFERRED TO PHASE 4**: Notification system changes are pending. Will analyze current 30-minute reminder system and design enhanced configurable notifications when ready for Phase 4 implementation.

- **Migration Strategy**: Graceful transition from fixed 30-minute reminders to configurable system
- **Notification Types**: Due window start alerts + configurable reminder timing (days/hours/minutes)
- **Spam Prevention**: Deduplication logic to prevent notification conflicts and excessive alerts
- **User Control**: Independent enable/disable for due window vs reminder notifications

### Performance Impact

- State calculation overhead: minimal (simple datetime comparison)
- Dashboard helper: slight increase in processing (due window metadata)
- Notification system: requires enhanced throttling and timing calculations for multiple triggers per chore

### User Experience

- Clearer visual progression: Available → Due → Overdue
- More actionable dashboard (focus on "due now" items)
- Reduced decision fatigue (obvious priority ordering)

### Technical Debt Prevention

- Reuse existing datetime handling utilities from `kc_helpers.py`
- Follow established patterns for system settings and per-entity overrides
- Maintain single source of truth for state calculation logic

## Future Enhancements (Out of Scope)

- Smart due window suggestions based on chore completion patterns
- Different due window behaviors by chore frequency (daily vs weekly)
- Integration with external calendar systems for due window events
- Machine learning-based due window optimization per kid

---

## Phase 1a Handoff

### Ready for Implementation ✅

**Phase 1a - Missing Frequency Options** is ready for implementation handoff.

### Implementation Summary

| Item                 | Details                                                |
| -------------------- | ------------------------------------------------------ |
| **Scope**            | Add 6 missing frequency options to chores              |
| **Files to modify**  | `const.py` (~2 locations), `services.py` (~1 location) |
| **Risk level**       | Low - extending existing functionality                 |
| **Schema change**    | None required                                          |
| **Testing required** | `test_frequency*.py`, manual UI verification           |

### Quick Reference

**const.py changes:**

```python
# Line ~3042 - CHORE_FREQUENCY_OPTIONS - add:
FREQUENCY_QUARTERLY, FREQUENCY_YEARLY, PERIOD_WEEK_END,
PERIOD_MONTH_END, PERIOD_QUARTER_END, PERIOD_YEAR_END

# Line ~3055 - CHORE_FREQUENCY_OPTIONS_CONFIG_FLOW - add same
```

**services.py changes:**

```python
# Line ~232 - _CHORE_FREQUENCY_VALUES - add all missing:
FREQUENCY_BIWEEKLY, FREQUENCY_QUARTERLY, FREQUENCY_YEARLY,
FREQUENCY_CUSTOM, FREQUENCY_CUSTOM_FROM_COMPLETE,
PERIOD_WEEK_END, PERIOD_MONTH_END, PERIOD_QUARTER_END, PERIOD_YEAR_END
```

### Validation Commands

```bash
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/
python -m pytest tests/test_frequency*.py -v
```

### Handoff Checklist

- [x] Implementation steps documented with line numbers
- [x] Files to modify identified
- [x] Quality gates specified
- [x] No blocking dependencies
- [x] Notification work deferred to Phase 4
- [x] Frequency constants renamed to include CHORE prefix ✅ (DONE)
- [ ] **Ready for Plan Agent handoff**
