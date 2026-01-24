# Due Window Feature Implementation Plan

## Initiative snapshot

- **Name / Code**: Due Window Feature - Enhanced Chore State Management
- **Target release / milestone**: v0.6.0
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: In Progress

## Summary & immediate steps

| Phase / Step             | Description                              | % complete | Quick notes                              |
| ------------------------ | ---------------------------------------- | ---------- | ---------------------------------------- |
| Phase 1a – Frequencies   | Add missing frequency options to chores  | 100%       | ✅ Complete - all tests pass             |
| Phase 1b – Configuration | Add due window system settings           | 0%         | Global + per-chore due window offsets    |
| Phase 2 – State Logic    | Implement DUE state calculation          | 0%         | New state between PENDING and OVERDUE    |
| Phase 3 – Entity Updates | Update sensors and dashboard integration | 0%         | Frontend display changes                 |
| Phase 4 – Notifications  | Add due window notification triggers     | 0%         | Integrate with existing notification sys |

1. **Key objective** – Add a "DUE" state that activates X hours/days before chore due date, providing clearer user guidance on when chores should be started vs just available.

2. **Summary of recent work** – **Phase 1a complete**: Added quarterly, yearly, and period-end (week, month, quarter, year) frequencies to chores. Updated const.py arrays, services.py schema, and translations.

3. **Next steps (short term)** – Manual testing of new frequencies (user step), then proceed to Phase 1b for due window system configuration.

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

- **Goal**: Add due window configuration options to system settings and establish new constants
- **Steps / detailed work items**
  1. `[ ]` Add due window constants to `const.py`
     - `CONF_DUE_WINDOW_ENABLED`: Global enable/disable toggle
     - `CONF_DUE_WINDOW_DEFAULT_DAYS`: Default days before due date
     - `CONF_DUE_WINDOW_DEFAULT_HOURS`: Default hours before due date (additional offset)
     - `CONF_DUE_WINDOW_NOTIFY_ENABLED`: Enable due window start notifications
     - `CONF_REMINDER_NOTIFY_ENABLED`: Enable configurable reminder notifications
     - `CONF_REMINDER_DAYS`: Days before due for reminder notification
     - `CONF_REMINDER_HOURS`: Hours before due for reminder notification
     - `CONF_REMINDER_MINUTES`: Minutes before due for reminder notification
     - `CHORE_STATE_DUE`: New state constant
     - `TRANS_KEY_STATE_DUE`: Translation key for due state
  2. `[ ]` Add to system settings defaults in `const.py`
     - Add to `DEFAULT_CONFIG_OPTIONS` dict
     - Set sensible defaults: due_window(enabled=true, days=1, hours=0)
     - Add notification settings: due_window_notify=true, reminder_notify=true
     - Add configurable reminder timing: reminder_days=0, reminder_hours=0, reminder_minutes=30 (replaces fixed 30min)
  3. `[ ]` Add per-chore due window override fields to chore data schema
     - `DATA_CHORE_DUE_WINDOW_ENABLED`: Per-chore override (true/false/null for default)
     - `DATA_CHORE_DUE_WINDOW_DAYS`: Per-chore days override
     - `DATA_CHORE_DUE_WINDOW_HOURS`: Per-chore hours override
  4. `[ ]` Update translation files
     - Add due window labels and descriptions in `translations/en.json`
     - Add state translation for "Due" state
     - Add notification configuration labels (due window notify, reminder notify, timing options)
     - Add notification message templates for due window and configurable reminder notifications
  5. `[ ]` Test constant integration
     - Run `./utils/quick_lint.sh --fix` to validate constants
     - Verify no circular import issues
- **Key issues**
  - Need to decide if per-chore overrides should be full replacement or additive to global settings
  - Consider if hours/days should be combined into single offset with unit selector

### Phase 2 – State Logic Implementation

- **Goal**: Implement due state calculation logic in coordinator and sensor classes
- **Steps / detailed work items**
  1. `[ ]` Add due window calculation helper to `coordinator_chore_operations.py`
     - `chore_is_due(kid_id, chore_id) -> bool`: Check if chore is in due window
     - `get_chore_due_window_start(kid_id, chore_id) -> datetime | None`: Calculate due window start time
     - Handle global settings + per-chore overrides logic
  2. `[ ]` Update chore state calculation in `sensor.py`
     - Modify `native_value` property in `ChoreStatusSensor` (around line 720)
     - Add DUE state to priority order: approved > completed_by_other > claimed > due > overdue > pending
     - Insert `chore_is_due()` check in appropriate position
  3. `[ ]` Update dashboard helper state aggregation
     - Modify `sensor.py` dashboard helper logic to handle DUE state
     - Ensure proper state counting and filtering for dashboard display
  4. `[ ]` Add due window metadata to chore status attributes
     - Add `due_window_start` attribute to show when due period began
     - Add `time_until_due` and `time_until_overdue` calculated attributes
  5. `[ ]` Update state icons and colors for DUE state
     - Add appropriate mdi icon for due state (e.g., `mdi:clock-alert`)
     - Define color scheme (suggest yellow/amber for "due" vs red for "overdue")
  6. `[ ]` Test state calculation logic
     - Create test scenarios with various due dates and window settings
     - Verify state transitions: pending → due → overdue
     - Test edge cases (no due date, past due date, etc.)
- **Key issues**
  - Need to ensure state calculation performance is acceptable (consider caching)
  - Verify that DUE state doesn't interfere with existing chore completion/approval flows
  - Consider timezone handling for due window calculations

### Phase 3 – Frontend & Dashboard Integration

- **Goal**: Update entity sensors, dashboard helpers, and UI representations for due window display
- **Steps / detailed work items**
  1. `[ ]` Update options flow for due window and notification configuration
     - Add due window settings to system options flow in `options_flow.py`
     - Create schema for global due window settings (enabled, default days/hours)
     - Add configurable notification options (due window notify, reminder timing)
     - Replace fixed 30-minute reminder with configurable days/hours/minutes options
     - Add validation for reasonable values (due window: 0-30 days, notifications: 0-30 days)
  2. `[ ]` Add per-chore due window configuration to chore forms
     - Update `flow_helpers.py` chore schema builders
     - Add due window override fields to chore creation/edit forms
     - Add conditional display logic (only show if global due window enabled)
  3. `[ ]` Update dashboard helper for due window display
     - Modify dashboard helper sensor to include due window metadata
     - Add `due_window_active` and `due_window_remaining` fields to chore objects
     - Ensure proper sorting of chores by due window status
  4. `[ ]` Update service schemas for due window support
     - Add due window fields to `CREATE_CHORE_SCHEMA` and `UPDATE_CHORE_SCHEMA` in `services.py`
     - Update `_SERVICE_TO_CHORE_DATA_MAPPING` for service field mapping
     - Add validation for due window service inputs
  5. `[ ]` Test UI integration
     - Verify due window settings appear in options flow
     - Test chore form due window overrides
     - Validate dashboard helper updates reflect due window state changes
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
