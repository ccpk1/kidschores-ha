# Chore Enhancements Implementation Plan

## Initiative snapshot

- **Name / Code**: Chore Enhancements (6 major features)
- **Target release / milestone**: KidsChores v0.4.0
- **Owner / driver(s)**: Development Team
- **Status**: Phase 1 complete

## Summary & immediate steps

| Phase / Step                    | Description                                          | % complete | Quick notes                        |
| ------------------------------- | ---------------------------------------------------- | ---------- | ---------------------------------- |
| Phase 1 – Show on Calendar      | Full feature (constants, UI, logic, entities, tests) | 100%       | ✅ COMPLETE                        |
| Phase 2 – Auto Approve          | Full feature (constants, UI, logic, entities, tests) | 100%       | ✅ COMPLETE - All tests passing    |
| Phase 3 – Completion Criteria   | Full feature (constants, UI, logic, entities, tests) | 0%         | INDEPENDENT/SHARED_ALL/FIRST/ALT   |
| Phase 4 – Approval Reset Timing | Full feature (constants, UI, logic, entities, tests) | 0%         | MIDNIGHT/COMPLETION/DUE_DATE reset |
| Phase 5 – Overdue Handling      | Full feature (constants, UI, logic, entities, tests) | 0%         | HOLD/RESET chore expiration        |
| Phase 6 – Multiple Time Slots   | Full feature (constants, UI, logic, entities, tests) | 0%         | Schedule multiple times per day    |

### Key objectives

1. **Phase 1 – Show on Calendar**: Allow hiding chores from calendar entity (optional field)
2. **Phase 2 – Auto Approve**: Automatically approve claimed chores (optional field)
3. **Phase 3 – Completion Criteria**: Support 4 completion modes (INDEPENDENT/SHARED_ALL/SHARED_FIRST/ALTERNATING)
4. **Phase 4 – Approval Reset Timing**: 3 reset modes (AT_MIDNIGHT/UPON_COMPLETION/AT_DUE_DATE)
5. **Phase 5 – Overdue Handling**: 2 overdue modes (HOLD_UNTIL_COMPLETE/RESET_REGARDLESS)
6. **Phase 6 – Multiple Time Slots**: Schedule same chore at multiple times per day independently

### Summary of recent work

- Enhancement requirements documented in chore-enhancements.md
- Current chore data structure reviewed (shared_chore, allow_multiple_claims_per_day, recurring_frequency properties exist)
- No implementation started yet

### Next steps (short term)

1. Start Phase 1: Implement "Show on Calendar" feature end-to-end
2. Each phase includes: constants → UI → coordinator logic → entities → tests
3. Phases are independent - can be implemented in any order, but each phase is complete before moving to next

### Risks / blockers

- **Storage schema version** - May need v43+ if changes are significant (currently v42)
- **Backward compatibility** - Existing chores must work with new fields as optional
- **Complex approval logic** - Shared completion modes (especially alternating) require careful state tracking
- **Testing complexity** - New workflows will need comprehensive test coverage

### References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Storage-only v42 schema, migration patterns
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) - Phase 0 audit framework, quality standards
- [Chore Enhancements Requirements](./chore-enhancements.md) - Detailed feature specifications
- [TESTING_AGENT_INSTRUCTIONS.md](../../tests/TESTING_AGENT_INSTRUCTIONS.md) - Testing patterns and helpers
- [COORDINATOR_CODE_REMEDIATION](./COORDINATOR_CODE_REMEDIATION_IN-PROCESS.md) - Notification/error message patterns (reference)

### Decisions & completion check

- **Decisions captured**:

  - ✅ Features will be implemented one-per-phase (feature-based phases)
  - ✅ Each phase includes: constants, UI, logic, entities, and tests
  - ✅ Phases are independent and can be completed in any order
  - ✅ Storage schema will remain v42 (new fields optional, backward compatible)
  - ✅ All 6 features are additive (no breaking changes to existing chores)

- **Completion confirmation**: `[ ]` All phases complete, tests passing, docs updated, ready for merge

---

## Detailed phase tracking

### Phase 1 – Show on Calendar

**Goal**: Implement calendar visibility filtering - allow users to hide chores from the calendar entity display.

**Overview**: This feature adds a simple boolean flag to each chore to control whether it appears in the calendar entity. Minimal logic complexity - mostly data structure and UI updates.

**Estimated effort**: 6-8 hours

**Steps / detailed work items** ✅ COMPLETE

1. **Define constants in `const.py`**

   - [x] `DATA_CHORE_SHOW_ON_CALENDAR` constant (default: True)
   - [x] `CONF_CHORE_SHOW_ON_CALENDAR` constant for config flow field
   - [x] `TRANS_KEY_CFOF_CHORE_SHOW_ON_CALENDAR` translation key
   - **Status**: ✅ COMPLETE | **Date**: Dec 20, 2024
   - **Validation**: `./utils/quick_lint.sh` passes ✅

2. **Add migration logic for existing chores**

   - [x] Update `coordinator.py` to set `show_on_calendar=True` for all existing chores in `__init__()` migration loop
   - [x] No schema version change needed (optional field with default)
   - **Status**: ✅ COMPLETE | **Date**: Dec 20, 2024
   - **Validation**: Migration test covers existing chores ✅, `pytest tests/ -v` passes ✅

3. **Update config and options flow schemas**

   - [x] Add checkbox field to chore schema in `flow_helpers.py` (in `build_chore_schema()` function)
   - [x] Field: "Show on Calendar" with default True
   - [x] Add translation key `TRANS_KEY_CFOF_CHORE_SHOW_ON_CALENDAR` in `const.py`
   - [x] Update `translations/en.json` with label and description (3 config sections)
   - **Status**: ✅ COMPLETE | **Date**: Dec 20, 2024
   - **Validation**: Field tested in Phase 1 test suite ✅

4. **Implement calendar filtering logic**

   - [x] Update `calendar.py` platform to filter events by `show_on_calendar` flag
   - [x] Only include chores where `show_on_calendar=True`
   - **Status**: ✅ COMPLETE | **Date**: Dec 20, 2024
   - **Validation**: `test_show_on_calendar_feature.py` verifies filtered events ✅

5. **Test comprehensive coverage**
   - [x] Test: Calendar filters chores by show_on_calendar flag
   - [x] Test: Backward compatibility - missing field defaults to True
   - [x] Test: Migration of existing chores sets show_on_calendar=True
   - **Status**: ✅ COMPLETE | **Date**: Dec 20, 2024
   - **Validation**: All tests pass: `pytest tests/ -v` (563 passed, 10 skipped) ✅, linting 10.00/10 ✅

**Test results**

- Phase 1 tests: 3/3 passing ✅ (test_show_on_calendar_feature.py)
- Full suite: 563/573 passing (10 skipped by design), zero regressions ✅
- Linting: 10.00/10 score, zero warnings/errors ✅
- Type hints: 100% ✅

**Key decisions**

- **Default value**: True (shows on calendar by default, preserves backward compatibility)
- **Migration approach**: Set field=True for all existing chores on first load
- **UI element**: BooleanSelector (checkbox) for clean user experience
- **Test pattern**: Used test_calendar_scenarios.py structure, simplified from 8 tests to 3 focused tests

---

### Phase 2 – Auto Approve

**Goal**: Implement automatic approval workflow - chores marked with auto_approve=True are approved immediately when claimed.

**Overview**: Adds boolean flag to control whether claimed chores are auto-approved or require parent approval. Requires updates to coordinator approval logic and notifications.

**Status**: ✅ COMPLETE | **Date**: Dec 27, 2025

**Steps / detailed work items**

1. **Define constants in `const.py`**

   - [x] `DATA_CHORE_AUTO_APPROVE` constant (default: False)
   - [x] `CONF_CHORE_AUTO_APPROVE` constant for config flow field
   - **Status**: ✅ COMPLETE | **Date**: Dec 20, 2024
   - **Validation**: `./utils/quick_lint.sh` passes ✅

2. **Add migration logic for existing chores**

   - [x] Update `coordinator.py` to set `auto_approve=False` for all existing chores
   - **Status**: ✅ COMPLETE | **Date**: Dec 20, 2024
   - **Validation**: Migration test, `pytest tests/ -v` ✅

3. **Update config flow UI**

   - [x] Add checkbox field "Auto Approve" to chore creation form
   - [x] Add same field to options flow for editing
   - [x] Add translation key `TRANS_KEY_CFOF_CHORE_AUTO_APPROVE`
   - [x] Update `translations/en.json` with label and description
   - **Status**: ✅ COMPLETE | **Date**: Dec 20-25, 2025
   - **Validation**: `test_config_flow.py`, `test_options_flow.py` ✅

4. **Implement auto-approval logic in coordinator**

   - [x] In `_claim_chore()`: Check if chore.auto_approve=True
   - [x] If yes, automatically call approval logic (set status to Approved)
   - [x] If no, keep current behavior (wait for parent approval)
   - [x] Ensure notifications sent correctly (auto-approved vs awaiting approval)
   - **Status**: ✅ COMPLETE | **Date**: Dec 20-25, 2025
   - **Validation**: `test_coordinator.py` tests auto vs manual approval paths ✅

5. **Update notification logic**

   - [x] Add notification: When kid claims auto_approve chore, send "Chore Auto-Approved" notification
   - [x] Keep existing notification for manual approval chores
   - [x] Translation keys for new notifications
   - **Status**: ✅ COMPLETE | **Date**: Dec 25-26, 2025
   - **Validation**: Notification tests ✅

6. **Add related sensors/buttons**

   - [x] Optional: Update chore status sensor to show "auto-approved"
   - [x] Optional: Add button to manually override auto-approval (for parent to disapprove if needed)
   - **Status**: ✅ COMPLETE | **Date**: Dec 25-26, 2025
   - **Validation**: Tests if implemented ✅

7. **Test comprehensive coverage**
   - [x] Test: Claiming auto_approve=True chore → auto-approved
   - [x] Test: Claiming auto_approve=False chore → awaits approval
   - [x] Test: Editing to toggle auto_approve
   - [x] Test: Disapproving auto-approved chore
   - [x] Test: Notifications sent correctly for both modes
   - [x] Test: Migration adds auto_approve field to existing chores
   - [x] Test: Multiple chores with different auto_approve settings
   - **Status**: ✅ COMPLETE | **Date**: Dec 27, 2025
   - **Validation**: All 9 tests passing: `pytest tests/test_auto_approve_feature.py -v` ✅, linting 9.90/10 ✅

**Test results**

- Phase 2 tests: 9/9 passing ✅ (test_auto_approve_feature.py)
- Full suite: 572/573 passing (1 skipped by design), zero regressions ✅
- Linting: 9.90/10 score on test file, zero critical errors ✅
- Type hints: 100% ✅

**Key decisions**

- **Default value**: False (requires parent approval by default, preserves current behavior)
- **Disapproval support**: Parents can disapprove auto-approved chores to remove points
- **Notification pattern**: Uses `_notify_kid_translated()` for localized messages
- **Test coverage**: Comprehensive testing of all approval workflows

**Key issues**

- **Notification differentiation**: Need clear messaging that chore was auto-approved vs awaiting parent approval

---

### Phase 3 – Completion Criteria

**Goal**: Implement shared chore completion modes - support 4 ways multiple assigned kids can complete a shared chore.

**Overview**: Adds 4 completion criteria modes (INDEPENDENT, SHARED_ALL, SHARED_FIRST, ALTERNATING). Most complex feature - requires state tracking and approval logic changes.

**Estimated effort**: 12-16 hours

**Steps / detailed work items**

1. **Define constants in `const.py`**

   - [ ] `CHORE_COMPLETION_CRITERIA_INDEPENDENT` enum value
   - [ ] `CHORE_COMPLETION_CRITERIA_SHARED_ALL` enum value
   - [ ] `CHORE_COMPLETION_CRITERIA_SHARED_FIRST` enum value
   - [ ] `CHORE_COMPLETION_CRITERIA_ALTERNATING` enum value
   - [ ] `DATA_CHORE_COMPLETION_CRITERIA` constant (default: INDEPENDENT)
   - [ ] `CONF_CHORE_COMPLETION_CRITERIA` constant for config flow field
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `./utils/quick_lint.sh` passes

2. **Add migration logic for existing chores**

   - [ ] Set `completion_criteria=INDEPENDENT` for all existing chores
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Migration test, `pytest tests/ -v`

3. **Update config flow UI**

   - [ ] Add dropdown field "Completion Criteria" with 4 options
   - [ ] Add field to options flow for editing
   - [ ] Add translation keys for all 4 modes
   - [ ] Update `translations/en.json` with descriptions explaining each mode
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_config_flow.py`, `test_options_flow.py`

4. **Design alternating assignment tracking**

   - [ ] Decision: How to track current "active" kid in alternating mode
   - [ ] Store in chore_data? Or kid_data?
   - [ ] Decision: Rotation scope (daily? weekly? after each completion?)
   - [ ] Document in plan notes
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Design review

5. **Implement INDEPENDENT mode logic** (existing behavior, baseline)

   - [ ] Each kid's claim is independent
   - [ ] No changes needed to existing `_claim_chore()` for this mode
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Test baseline behavior unchanged

6. **Implement SHARED_ALL mode logic**

   - [ ] Track which assigned kids have claimed chore
   - [ ] Only mark complete when ALL assigned kids have claimed
   - [ ] If kid unclaims, revert status
   - [ ] Raise error if kid tries to claim when not assigned
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests all kids must claim

7. **Implement SHARED_FIRST mode logic**

   - [ ] First kid to claim marks complete for all
   - [ ] Remove chore from other assigned kids' pending lists
   - [ ] Prevent other kids from claiming once first completes
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests first-claim behavior

8. **Implement ALTERNATING mode logic**

   - [ ] Track current "active" kid in chore_data
   - [ ] Only allow active kid to claim
   - [ ] After completion, rotate to next assigned kid
   - [ ] Handle edge case: If active kid removed from assignment, rotate to next
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests rotation logic

9. **Add related sensors/buttons**

   - [ ] Add sensor showing completion status (e.g., "2 of 3 kids claimed")
   - [ ] Add sensor showing current active kid (for alternating mode)
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Sensor tests

10. **Test comprehensive coverage**
    - [ ] Test all 4 completion criteria modes
    - [ ] Test mode transitions (changing from INDEPENDENT to SHARED_ALL)
    - [ ] Test edge cases: kid unassignment mid-completion, missing assignments
    - [ ] Test alternating rotation logic
    - **Status**: Not started | **Owner**: TBD
    - **Validation**: `pytest tests/ -v`, coverage 95%+

**Key issues**

- **Alternating algorithm complexity**: Need careful design for fair rotation
- **State consistency**: SHARED_ALL/FIRST modes require careful tracking of claimed status across kids
- **Edge cases**: Unassigning kids mid-completion requires special handling

---

### Phase 4 – Approval Reset Timing

**Goal**: Implement approval reset logic - control when parent approval can be given again for recurring chores.

**Overview**: Adds 3 reset timing modes (AT_MIDNIGHT, UPON_COMPLETION, AT_DUE_DATE). Requires tracking last approval time and checking on approval attempts.

**Estimated effort**: 10-12 hours

**Steps / detailed work items**

1. **Define constants in `const.py`**

   - [ ] `CHORE_APPROVAL_RESET_AT_MIDNIGHT` enum value
   - [ ] `CHORE_APPROVAL_RESET_UPON_COMPLETION` enum value
   - [ ] `CHORE_APPROVAL_RESET_AT_DUE_DATE` enum value
   - [ ] `DATA_CHORE_APPROVAL_RESET_TYPE` constant (default: AT_MIDNIGHT)
   - [ ] `DATA_CHORE_LAST_APPROVAL_TIME` constant (tracks timestamp of last approval)
   - [ ] `CONF_CHORE_APPROVAL_RESET_TYPE` constant for config flow field
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `./utils/quick_lint.sh` passes

2. **Add migration logic**

   - [ ] Set `approval_reset_type=AT_MIDNIGHT` for all existing chores
   - [ ] Set `last_approval_time=None` for all existing chores
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Migration test

3. **Update config flow UI**

   - [ ] Add dropdown field "Approval Reset Type" with 3 options
   - [ ] Add field to options flow for editing
   - [ ] Add translation keys and descriptions
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_config_flow.py`, `test_options_flow.py`

4. **Design approval reset mechanism**

   - [ ] Decision: How often to check for reset needed? (on every approval attempt? on coordinator update?)
   - [ ] Decision: How to efficiently check if reset has occurred? (compare timestamps? lazy evaluation?)
   - [ ] Document in plan notes
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Design review

5. **Implement AT_MIDNIGHT mode**

   - [ ] Check if last_approval_time is before today's midnight (UTC)
   - [ ] If yes, allow approval; if no, prevent with error
   - [ ] Update last_approval_time on approval
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests midnight reset

6. **Implement UPON_COMPLETION mode**

   - [ ] No restriction - can approve unlimited times
   - [ ] Always allow approval regardless of last_approval_time
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests unlimited approvals

7. **Implement AT_DUE_DATE mode**

   - [ ] Check if last_approval_time is before chore's next due date
   - [ ] If yes, allow approval; if no, prevent with error
   - [ ] Integrate with chore due_date calculation logic
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests due-date-based reset

8. **Add notifications and error handling**

   - [ ] Notify parent when approval reset happens
   - [ ] Raise error when trying to approve before reset with helpful message
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Notification and error tests

9. **Add related sensors**

   - [ ] Sensor showing "time until next approval allowed"
   - [ ] Sensor showing last approval timestamp
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Sensor tests

10. **Test comprehensive coverage**
    - [ ] Test all 3 reset modes
    - [ ] Test midnight boundary conditions
    - [ ] Test due-date calculations with different recurring patterns
    - [ ] Test timezone handling (all times UTC)
    - **Status**: Not started | **Owner**: TBD
    - **Validation**: `pytest tests/ -v`, coverage 95%+

**Key issues**

- **Timezone awareness**: All times must be UTC internally, convert for display
- **Performance**: Checking reset on every approval attempt could be slow
- **Due-date complexity**: Calculating next due date needs careful logic

---

### Phase 5 – Overdue Handling

**Goal**: Implement overdue chore handling - control whether overdue chores reset or stay pending.

**Overview**: Adds 2 overdue modes (HOLD_UNTIL_COMPLETE, RESET_REGARDLESS). Requires integration with chore reset scheduling.

**Estimated effort**: 8-10 hours

**Steps / detailed work items**

1. **Define constants in `const.py`**

   - [ ] `CHORE_OVERDUE_HOLD_UNTIL_COMPLETE` enum value
   - [ ] `CHORE_OVERDUE_RESET_REGARDLESS` enum value
   - [ ] `DATA_CHORE_OVERDUE_OPTION` constant (default: HOLD_UNTIL_COMPLETE)
   - [ ] `CONF_CHORE_OVERDUE_OPTION` constant for config flow field
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `./utils/quick_lint.sh` passes

2. **Add migration logic**

   - [ ] Set `overdue_option=HOLD_UNTIL_COMPLETE` for all existing chores
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Migration test

3. **Update config flow UI**

   - [ ] Add dropdown field "Overdue Option" with 2 options
   - [ ] Add field to options flow for editing
   - [ ] Add translation keys and descriptions
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_config_flow.py`, `test_options_flow.py`

4. **Implement HOLD_UNTIL_COMPLETE mode**

   - [ ] If chore past due and still pending, keep in queue
   - [ ] Display overdue indicator in UI
   - [ ] Add notification that chore is overdue
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests hold behavior

5. **Implement RESET_REGARDLESS mode**

   - [ ] At reset time (based on recurring pattern), clear pending claim
   - [ ] Create new instance for next cycle
   - [ ] Notify kid that previous chore was not completed and has been reset
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests reset behavior

6. **Integrate with chore reset scheduler**

   - [ ] Ensure reset logic is called at appropriate times
   - [ ] Verify reset happens for RESET_REGARDLESS mode
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Scheduler integration tests

7. **Add notifications**

   - [ ] Notify when chore becomes overdue
   - [ ] Notify when overdue chore is reset (for RESET_REGARDLESS mode)
   - [ ] Translation keys for overdue notifications
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Notification tests

8. **Add related sensors**

   - [ ] Sensor showing "is_overdue" status
   - [ ] Sensor showing "days_overdue" counter
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Sensor tests

9. **Test comprehensive coverage**
   - [ ] Test both overdue modes
   - [ ] Test mode transitions
   - [ ] Test overdue notifications
   - [ ] Test reset behavior
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `pytest tests/ -v`, coverage 95%+

**Key issues**

- **Reset complexity**: Ensuring reset happens at correct time without race conditions
- **User experience**: Clear communication about overdue chores and reset behavior

---

### Phase 6 – Multiple Time Slots

**Goal**: Implement multiple time slots per day scheduling - allow same chore to be scheduled at multiple times with independent tracking.

**Overview**: Most complex feature - adds array of time slots to chore, tracks independent claim/approval state per slot, handles reset logic per slot.

**Estimated effort**: 14-18 hours

**Steps / detailed work items**

1. **Define constants in `const.py`**

   - [ ] `DATA_CHORE_TIME_SLOTS` constant (array structure)
   - [ ] `CONF_CHORE_TIME_SLOTS` constant for config flow field
   - [ ] Helper constants for time slot properties (time, frequency, applicable_days)
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `./utils/quick_lint.sh` passes

2. **Design time slots data structure**

   - [ ] Decision: Format for time slots array - {time: "HH:MM", frequency: "...", applicable_days: []}?
   - [ ] Decision: How to handle conflicts (same chore at 8am and 3pm - independent or linked)?
   - [ ] Decision: Should reset logic apply per time slot or globally?
   - [ ] Decision: Backward compatibility - single-frequency chores become single-entry array?
   - [ ] Document in plan notes
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Design review

3. **Add migration logic**

   - [ ] Convert existing single recurring_frequency to time_slots array
   - [ ] Existing chores: [{time: "08:00", frequency: recurring_frequency, applicable_days: []}]
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Migration test

4. **Update config flow UI**

   - [ ] Add multi-step form for time slots configuration
   - [ ] Allow adding/removing/editing time slot entries
   - [ ] Validate: time format (HH:MM), no duplicate times, valid frequency
   - [ ] Add translation keys and help text
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_config_flow.py`, `test_options_flow.py`

5. **Implement independent slot tracking**

   - [ ] Track claimed_chores with slot info: {chore_id, slot_index, status}
   - [ ] Each time slot has independent claim/approval state
   - [ ] Claiming slot 0 doesn't affect slot 1
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests independent slots

6. **Implement time slot reset logic**

   - [ ] Each slot resets independently based on its frequency and reset_type
   - [ ] Check if slot's scheduled time has passed
   - [ ] Only allow claiming slot if scheduled time has been reached
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests per-slot reset

7. **Extend claim/approval workflow for slots**

   - [ ] When claiming, specify which time slot (or auto-select next available)
   - [ ] When approving, approve specific slot's claim
   - [ ] Handle completion_criteria logic per slot (SHARED_ALL means all kids claim all slots? Or just the current slot?)
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: `test_coordinator.py` tests slot-specific workflows

8. **Add related sensors**

   - [ ] Sensor showing status of each time slot (pending, claimed, approved, overdue)
   - [ ] Sensor showing which slot is "current" or "next"
   - [ ] Optional: Separate sensor for each time slot
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Sensor tests

9. **Add related buttons**

   - [ ] Button to claim specific time slot
   - [ ] Button to approve specific time slot claim
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Button tests

10. **Handle feature interactions**

    - [ ] If completion_criteria=SHARED_ALL + time_slots, does all kids need to claim all slots? Or just current slot?
    - [ ] If approval_reset=AT_MIDNIGHT + time_slots, does each slot reset at midnight independently?
    - [ ] Document all interactions and edge cases
    - **Status**: Not started | **Owner**: TBD
    - **Validation**: Edge case tests

11. **Test comprehensive coverage**
    - [ ] Test creating chore with multiple time slots
    - [ ] Test claiming each time slot independently
    - [ ] Test approval for each slot
    - [ ] Test per-slot reset logic
    - [ ] Test feature interactions (time slots + completion criteria, etc.)
    - [ ] Test backward compatibility (existing single-frequency chores)
    - **Status**: Not started | **Owner**: TBD
    - **Validation**: `pytest tests/ -v`, coverage 95%+

**Key issues**

- **Data structure complexity**: Time slots array with multiple properties requires careful handling
- **Feature interaction**: Interacting with completion criteria and reset logic is complex
- **UI complexity**: Multi-step form for time slots configuration needs thoughtful UX design
- **State tracking**: Independent per-slot state tracking requires robust implementation

---

## Cross-Phase Considerations

### Shared Work Items (Done Once)

These tasks are shared across all phases and should be done once, before or alongside Phase 1:

1. **Base infrastructure setup** (if needed)

   - [ ] Verify `const.py` structure is suitable for all new constants
   - [ ] Verify `coordinator.py` structure can accommodate new methods
   - [ ] Verify migration pattern works for all new fields
   - [ ] Check storage model doesn't need changes (v42 is sufficient)
   - **Status**: Not started
   - **Validation**: Code review, no structural changes needed

2. **Documentation updates**
   - [ ] Update ARCHITECTURE.md to document new chore properties
   - [ ] Update coordinator.py docstrings for new methods
   - [ ] Create release notes for v0.4.0
   - **Status**: Not started (after all phases complete)
   - **Validation**: Docs reviewed, clear and complete

### Integration Testing (After All Phases)

After all phases complete, integration tests should verify:

- [ ] All features work independently
- [ ] Feature combinations don't have conflicts
- [ ] No regressions in existing functionality
- [ ] Backward compatibility maintained
- [ ] Performance acceptable with large datasets
- [ ] All edge cases handled

**Validation**: Full integration test suite passes, 95%+ coverage maintained

---

- [ ] Describe alternating assignment rotation logic
- [ ] Update storage schema v42 documentation if needed
- **Status**: Not started | **Owner**: TBD
- **Validation**: Architecture doc reflects all new features

4. **Create user-facing documentation**

   - [ ] Update README with new chore enhancement features
   - [ ] Create guide: "How to set up shared chores"
   - [ ] Create guide: "Understanding approval reset modes"
   - [ ] Create guide: "Calendar visibility and scheduling"
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Docs are clear, comprehensive, and accurate

5. **Prepare release notes**

   - [ ] Summarize all 5 new chore enhancements
   - [ ] Highlight impact on workflows
   - [ ] Note any breaking changes (if any)
   - [ ] Provide migration guidance if applicable
   - [ ] Add examples of new features
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: Release notes ready for v0.5.0 announcement

6. **Code quality validation**
   - [ ] Run `./utils/quick_lint.sh --fix` - must pass (9.5+/10 score)
   - [ ] Run full test suite: `pytest tests/ -v --tb=line`
   - [ ] Type hints on all new functions
   - [ ] Lazy logging only (no f-strings in logs)
   - [ ] All user-facing strings use constants and translation keys
   - **Status**: Not started | **Owner**: TBD
   - **Validation**: All checks pass, code review approved

**Key issues**

- **Test complexity**: Matrix of feature combinations could create 50+ test scenarios. Need efficient test organization.
- **Documentation burden**: 5 new features require extensive user documentation.

---

## Testing & validation

### Tests to execute

- **Phase 1**: Migration test suite

  - Command: `pytest tests/test_coordinator.py -k migration -v`
  - Expected: All existing chores migrate correctly with defaults

- **Phase 2**: Config and options flow tests

  - Command: `pytest tests/test_config_flow.py tests/test_options_flow*.py -v`
  - Expected: All new UI fields present and validated

- **Phase 3**: Coordinator business logic tests

  - Command: `pytest tests/test_coordinator.py -v`
  - Expected: 95%+ coverage of new approval logic

- **Phase 4**: Entity platform tests

  - Command: `pytest tests/test_sensor.py tests/test_button.py tests/test_calendar.py -v`
  - Expected: All new entities present and working

- **Phase 5**: Full integration test
  - Command: `pytest tests/ -v --tb=line`
  - Expected: All 150+ tests pass, no regressions

### Code quality validation

- Command: `./utils/quick_lint.sh --fix`
- Expected: 9.5+/10 score, zero critical errors

### Outstanding tests

- Dashboard template validation tests (out of scope for this plan, defer to dashboard project)

---

## Notes & follow-up

### Architecture decisions pending (Phase 1)

1. **Approval reset time tracking**:

   - Option A: Store per chore (DATA_CHORE_LAST_APPROVAL_TIME) - tracks when chore was last approved
   - Option B: Store per kid per chore (nested in kid_data) - tracks individual kid approval times
   - Recommendation: Option A (simpler, covers most use cases)
   - To decide: When reset triggers, who can claim? Just the kid who approved, or any assigned kid?

2. **Alternating assignment algorithm**:

   - Scope: Rotate daily? Weekly? After N completions?
   - Backup logic: How to handle if primary kid can't complete? Does backup take over?
   - Recommendation: Rotate based on completion (after each chore done), track "current_assignee" in chore_data
   - To decide: If current_assignee leaves (removed from chore), what happens?

3. **Completion criteria and auto-approve interaction**:

   - If auto_approve=True and completion_criteria=SHARED_ALL, when does auto-approval trigger?
   - Option A: Auto-approve when all kids have claimed
   - Option B: Auto-approve each kid's claim as it arrives (parallel)
   - Recommendation: Option A (more useful for shared scenarios)

4. **Storage schema version**:
   - Current: v42 (storage-only mode, optional fields)
   - Should new fields bump version to v43? Or stay v42 with optional defaults?
   - Recommendation: Stay v42 (no migration needed, backward compatible)

### Implementation dependencies

- **No external library additions needed** - All features use existing coordinator and HA primitives
- **Timezone handling**: Reuse existing `kc_helpers.parse_datetime_to_utc()` for approval reset time comparisons
- **Notification system**: Reuse Phase 3 notification patterns (TRANS*KEY_NOTIF*\* constants, `async_get_translations()` API)

### Performance considerations

- **Approval reset checks**: Running approval reset validation on every coordinator update could be slow with 50+ chores

  - Recommendation: Cache last reset check timestamp, skip if checked within last 5 minutes
  - Alternative: Lazy evaluation - only check when accessed (less accurate but faster)
  - Benchmark needed after Phase 3 implementation

- **Shared chore state tracking**: SHARED_ALL mode requires iterating claimed kids - acceptable for <50 kids
  - Concern: If >100 kids assigned to one chore, could be slow
  - Mitigation: Index or cache assignment list if performance becomes issue

### Follow-up tasks post-implementation

1. **Dashboard updates**: Coordinate with dashboard project to display new chore properties
2. **Automation examples**: Create blueprint automations showing use of new features
3. **Mobile app support**: Ensure mobile app can display/interact with new entities
4. **Performance monitoring**: Track coordinator update times to catch regressions
5. **User feedback**: Gather feedback on feature usability and refine if needed

### Known limitations & future work

- **Multiple times per day** (Item 6 from original list): Deferred to v0.6.0 (not in this plan)

  - Requires significant data structure changes (time slots array vs single frequency)
  - Will be tackled in separate phase after these 5 enhancements stabilize

- **Conditional feature display**: If some fields should only show based on others (e.g., approval_reset only for shared chores), that's Phase 2 enhancement not included in initial scope

---

## Summary of implementation approach

### Why this phasing?

1. **Phase 1** (Data + Constants): Build foundation so all downstream work has required definitions
2. **Phase 2** (UI): Enable users to set new properties
3. **Phase 3** (Logic): Implement business logic that makes features actually work
4. **Phase 4** (Entities): Expose functionality to Home Assistant ecosystem
5. **Phase 5** (Tests + Docs): Ensure quality and communicate changes

### Why incremental per-phase validation?

- Each phase can be reviewed, tested, and merged independently
- Reduces risk by catching issues early
- Provides clear milestones
- Allows parallel work if needed

### Estimated effort

- **Phase 1**: 8-12 hours (constants, migrations, design decisions)
- **Phase 2**: 6-10 hours (UI forms, validation, translations)
- **Phase 3**: 20-30 hours (complex approval logic, edge cases)
- **Phase 4**: 8-12 hours (sensor/button implementation)
- **Phase 5**: 12-16 hours (test writing, documentation)
- **Total**: 54-80 hours (1.5-2 weeks of full-time work)

---

**Document version**: 1.0
**Created**: December 27, 2025
**Status**: Ready for Phase 1 kickoff
