# Chore Logic Gap Analysis (Supporting Document)

**Parent Initiative**: [CHORE_LOGIC_AUDIT_IN-PROCESS.md](CHORE_LOGIC_AUDIT_IN-PROCESS.md)

**Last Updated**: January 18, 2026

---

## Executive Summary

This document provides detailed analysis of identified gaps in chore approval/reset/overdue handling logic. Initial analysis identified **6 gaps** ranging from critical bugs to optimization opportunities.

### Gap Summary Table

| Gap # | Title                                           | Severity              | Status                  | Impact                                            | Priority    |
| ----- | ----------------------------------------------- | --------------------- | ----------------------- | ------------------------------------------------- | ----------- |
| 1     | UPON_COMPLETION missing immediate reset         | 🚨 Critical           | ✅ Fixed by user        | INDEPENDENT chores stayed APPROVED until midnight | HIGH        |
| 2     | Midnight reset processing ALL FREQUENCY_NONE    | 🚨 Critical           | ✅ Fixed by user        | Non-midnight chores reset incorrectly             | HIGH        |
| 3     | AT*DUE_DATE*\* + FREQUENCY_NONE no auto-trigger | ⚠️ Design Question    | ⏳ Pending decision     | Manual reset only, no timer                       | MEDIUM      |
| 4     | Missing validation warnings                     | 📝 Enhancement        | ⏳ Pending              | Users unaware of edge case behaviors              | LOW         |
| 5     | Full overdue scan after approval                | 🔧 Optimization       | ⏳ Pending profile      | Performance concern for large datasets            | LOW         |
| 6     | SHARED + UPON_COMPLETION interaction            | 🚨 Potential Critical | 🔍 Investigation needed | User's fix may break SHARED chore reschedule      | **BLOCKER** |

---

## Detailed Gap Analysis

### Gap 1: UPON_COMPLETION Missing Immediate Reset ✅

**Severity**: 🚨 Critical (FIXED)

**Configuration**:

- `approval_reset_type`: UPON_COMPLETION
- `recurring_frequency`: NONE (non-recurring chore)
- `due_date`: Past date

**Expected Behavior**:

1. User approves chore at 11:50 PM
2. Chore **immediately** resets to PENDING state
3. Overdue check runs immediately
4. Chore marked OVERDUE (due date in past)

**Actual Behavior (before fix)**:

1. User approves chore at 11:50 PM
2. Chore stays APPROVED
3. At midnight (12:00 AM), chore resets to PENDING
4. Overdue check runs, chore marked OVERDUE
5. **10 minutes delay** between approval and reset

**Root Cause**:

- `approve_chore()` method (lines 3138-3598) did not include immediate reset logic for UPON_COMPLETION
- Relied on midnight reset (`_reset_daily_chore_statuses()`) which ran at 12:00 AM
- No overdue check triggered after approval

**User's Fix** (lines 3583-3606):

```python
# At end of approve_chore() method
if chore.get("approval_reset_type") == const.APPROVAL_RESET_UPON_COMPLETION:
    for assigned_kid_id in assigned_kids:
        assigned_kid_name = self.get_kid_name_by_internal_id(assigned_kid_id)
        if assigned_kid_name and assigned_kid_name in kid_statuses:
            kid_statuses[assigned_kid_name]["is_approved_in_current_period"] = False
            kid_statuses[assigned_kid_name]["state"] = const.ENTITY_STATE_PENDING

    chore["kid_statuses"] = kid_statuses
    await self._check_overdue_chores()
```

**Validation**:

- ✅ INDEPENDENT chores now immediately reset to PENDING
- ✅ Overdue check runs after reset
- ⚠️ **Potential issue**: May affect SHARED chores (see Gap 6)

**Test Coverage**:

- [ ] Existing tests: `test_workflow_*.py` scenarios
- [ ] New test needed: `test_upon_completion_immediate_reset.py`

---

### Gap 2: Midnight Reset Processing ALL FREQUENCY_NONE ✅

**Severity**: 🚨 Critical (FIXED)

**Configuration**:

- `recurring_frequency`: NONE
- `approval_reset_type`: AT_DUE_DATE_ONCE, AT_DUE_DATE_MULTI, or UPON_COMPLETION

**Expected Behavior**:

- Midnight reset (`_reset_daily_chore_statuses()`) should **skip** FREQUENCY_NONE chores
- Exception: AT_MIDNIGHT_ONCE and AT_MIDNIGHT_MULTI should still reset at midnight

**Actual Behavior (before fix)**:

- All FREQUENCY_NONE chores reset at midnight regardless of `approval_reset_type`
- Caused incorrect resets for chores configured for upon_completion or at_due_date

**Root Cause**:

- `_reset_daily_chore_statuses()` (lines 9488-9519) processed ALL chores without checking frequency
- Did not filter FREQUENCY_NONE chores by approval_reset_type

**User's Fix** (lines 9498-9507):

```python
# Skip non-recurring chores unless they use midnight-based reset
if (
    chore.get("recurring_frequency") == const.FREQUENCY_NONE
    and chore.get("approval_reset_type")
    not in (
        const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
    )
):
    continue  # Skip this chore
```

**Validation**:

- ✅ FREQUENCY*NONE + AT_MIDNIGHT*\* still reset at midnight (correct)
- ✅ FREQUENCY_NONE + UPON_COMPLETION no longer reset at midnight (correct)
- ✅ FREQUENCY*NONE + AT_DUE_DATE*\* no longer reset at midnight (correct)

**Test Coverage**:

- [ ] Test: FREQUENCY_NONE + AT_MIDNIGHT_ONCE → resets at midnight
- [ ] Test: FREQUENCY_NONE + UPON_COMPLETION → does NOT reset at midnight
- [ ] Test: FREQUENCY_NONE + AT_DUE_DATE_ONCE → does NOT reset at midnight

---

### Gap 3: AT*DUE_DATE*\* + FREQUENCY_NONE No Auto-Trigger ⏳

**Severity**: ⚠️ Design Question (Pending Owner Decision)

**Configuration**:

- `recurring_frequency`: NONE
- `approval_reset_type`: AT_DUE_DATE_ONCE or AT_DUE_DATE_MULTI

**Current Behavior**:

- Chore does **not** automatically reset when due date is reached
- No timer-based check exists for due date reaching
- Requires **manual reset** via config flow or button entity

**Question**: Is this intended behavior or missing feature?

**Analysis**:

**Option A: Keep as Manual-Only** (Document as Design)

- **Pro**: Simpler implementation, no additional timers needed
- **Pro**: Predictable behavior - user explicitly triggers reset
- **Con**: User may forget to reset chore after due date passes
- **Con**: Inconsistent with AT*MIDNIGHT*\* auto-reset behavior

**Option B: Add Timer-Based Auto-Reset** (Implement Feature)

- **Pro**: Consistent with AT*MIDNIGHT*\* auto-reset pattern
- **Pro**: More intuitive for users - "reset at due date" means auto-reset
- **Con**: Additional complexity - need timer to check due dates
- **Con**: Performance impact if checking 100+ chores frequently

**Implementation (if Option B chosen)**:

1. Create `_check_due_date_resets()` method in coordinator.py
2. Call from `async_update_chore_states()` or periodic timer
3. Check all chores with AT_DUE_DATE_ONCE/MULTI approval reset type
4. If current time ≥ due date, trigger reset to PENDING
5. Similar to `_check_overdue_chores()` pattern

**Code Location**:

- Method to create: `_check_due_date_resets()` near line 9195 in coordinator.py
- Caller: Add to `async_update_chore_states()` or create new timer

**Test Coverage** (if implemented):

- [ ] Test: AT_DUE_DATE_ONCE + past due date → auto-resets to PENDING
- [ ] Test: AT_DUE_DATE_MULTI + past due date → allows multi-claim reset
- [ ] Test: AT_DUE_DATE_ONCE + future due date → does NOT reset yet

**Owner Decision Required**:

- [ ] Document as "manual reset only" with validation warning?
- [ ] Implement auto-reset timer-based check?
- [ ] Defer to v0.6.0 for user feedback first?

---

### Gap 4: Missing Validation Warnings 📝

**Severity**: 📝 Enhancement (Low Priority)

**Issue**: Users can create chore configurations with non-obvious behaviors without warnings

**Examples of Surprising Configurations**:

1. **AT*DUE_DATE*\* + FREQUENCY_NONE**
   - Behavior: Manual reset only (no auto-trigger)
   - User expectation: "Reset at due date" sounds like auto-reset
   - Warning needed: "This combination requires manual approval reset after due date"

2. **SHARED + UPON_COMPLETION**
   - Behavior: All assigned kids reset to PENDING when ANY kid approves
   - User expectation: Only approving kid resets
   - Warning needed: "All assigned kids will reset together upon first approval"

3. **NEVER_OVERDUE + due_date set**
   - Behavior: Due date displayed but never marks overdue
   - User expectation: Due date should trigger overdue status
   - Info: "Due date is for display only - chore never becomes overdue"

4. **AT*DUE_DATE*\* + daily/weekly/monthly frequency**
   - Behavior: May conflict if due date not aligned with frequency
   - Warning: "Consider using AT*MIDNIGHT*\* for recurring chores"

**Implementation**:

- File: `custom_components/kidschores/flow_helpers.py`
- Add to: `build_chore_schema()` method (validation section)
- Format: Info messages (not errors) - allow but inform
- Display: Show in config flow UI as warnings (yellow icon)

**Translation Keys to Add** (const.py):

```python
TRANS_KEY_CFOF_WARNING_AT_DUE_DATE_FREQUENCY_NONE = "cfof_warning_at_due_date_frequency_none"
TRANS_KEY_CFOF_WARNING_SHARED_UPON_COMPLETION = "cfof_warning_shared_upon_completion"
TRANS_KEY_CFOF_WARNING_NEVER_OVERDUE_WITH_DUE_DATE = "cfof_warning_never_overdue_with_due_date"
TRANS_KEY_CFOF_INFO_AT_DUE_DATE_RECURRING = "cfof_info_at_due_date_recurring"
```

**Translation Strings** (en.json):

```json
{
  "config_flow": {
    "warning": {
      "at_due_date_frequency_none": "This combination requires manual approval reset after the due date is reached. The chore will not automatically reset.",
      "shared_upon_completion": "All assigned children will reset to pending together when any child's approval is completed, regardless of other children's status.",
      "never_overdue_with_due_date": "The due date will be displayed but this chore will never be marked as overdue.",
      "at_due_date_recurring": "For recurring chores, consider using 'At midnight' reset type instead of 'At due date' for more predictable behavior."
    }
  }
}
```

**Test Coverage**:

- [ ] Test: Config flow displays warnings for each combination
- [ ] Test: Warnings do not block chore creation (info only)
- [ ] Test: Translations load correctly for all warnings

**Priority**: LOW - UX improvement but not blocking functionality

---

### Gap 5: Full Overdue Scan After Approval 🔧

**Severity**: 🔧 Optimization (Low Priority)

**Issue**: User's fix (Gap 1) calls `_check_overdue_chores()` which scans ALL chores

**Current Behavior**:

- After single chore approval, full table scan of all chores
- Method: `_check_overdue_chores()` loops through all kids → all chores
- Performance: O(kids × chores) for single chore state change

**Analysis**:

**Scenario**: 10 kids × 20 chores = 200 chore checks after EACH approval

**Profiling Needed**:

- Run: Add timing logs around `_check_overdue_chores()` call
- Measure: Time taken for 10, 50, 100, 200 chores
- Threshold: If >100ms for typical setup, consider optimization

**Optimization Approach** (if justified):

**Option A: Single-Chore Overdue Check**

```python
async def _check_overdue_for_single_chore_by_id(self, chore_id: str) -> None:
    """Check overdue status for a single chore after state change."""
    chore = self.get_chore_by_internal_id(chore_id)
    if not chore:
        return

    # Extract single-chore logic from _check_overdue_chores() loop
    await self._check_overdue_for_chore(chore)
```

**Option B: Dirty Flag Pattern**

- Mark chores as "needs overdue check" when state changes
- Periodic scan only checks marked chores
- Clear flag after check completes

**Option C: Keep Full Scan (Current)**

- Pro: Simple, reliable, no risk of missing checks
- Con: Potentially wasteful for single chore updates
- Acceptable if profiling shows <50ms impact

**Implementation** (if Option A chosen):

1. Create `_check_overdue_for_single_chore_by_id()` method
2. Replace in approve_chore() line ~3606:
   ```python
   # Old: await self._check_overdue_chores()
   # New:
   await self._check_overdue_for_single_chore_by_id(chore_id)
   ```
3. Test: Verify overdue detection still works correctly

**Test Coverage**:

- [ ] Test: Single chore approval correctly marks overdue (if past due)
- [ ] Test: Other chores not affected by single chore approval
- [ ] Performance: Measure time savings (expect 50-100x faster for large datasets)

**Decision**:

- [ ] Profile performance with realistic dataset (10 kids, 20 chores)
- [ ] If <50ms, keep full scan (simpler is better)
- [ ] If >100ms, implement optimization
- [ ] Defer to v0.6.0 unless profiling shows significant impact

**Priority**: LOW - Premature optimization without profiling data

---

### Gap 6: SHARED + UPON_COMPLETION Interaction 🚨

**Severity**: 🚨 Potential Critical (Investigation Required - **RELEASE BLOCKER**)

**Status**: 🔍 Under Investigation

**Configuration**:

- `completion_criteria`: SHARED
- `approval_reset_type`: UPON_COMPLETION
- `recurring_frequency`: Any (including NONE)

**Critical Question**: Does user's fix (Gap 1) break SHARED chore reschedule logic?

**Issue Analysis**:

**User's Fix Location**: approve_chore() lines 3583-3606

```python
if chore.get("approval_reset_type") == const.APPROVAL_RESET_UPON_COMPLETION:
    # Resets ALL assigned kids to PENDING immediately
    for assigned_kid_id in assigned_kids:
        assigned_kid_name = self.get_kid_name_by_internal_id(assigned_kid_id)
        if assigned_kid_name and assigned_kid_name in kid_statuses:
            kid_statuses[assigned_kid_name]["is_approved_in_current_period"] = False
            kid_statuses[assigned_kid_name]["state"] = const.ENTITY_STATE_PENDING
```

**SHARED Chore Logic**: approve_chore() lines 3503-3526

```python
# For SHARED chores, check if all assigned kids approved
elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
    all_approved = True
    for other_kid in assigned_kids:
        other_kid_name = self.get_kid_name_by_internal_id(other_kid)
        if other_kid_name:
            # Checks is_approved_in_current_period for each kid
            if not self.is_approved_in_current_period(chore_id, other_kid_name):
                all_approved = False
                break

    if all_approved and should_reschedule_immediately:
        await self._reschedule_chore_next_due_date(chore_id)
```

**Race Condition Hypothesis**:

**Scenario**: SHARED chore assigned to Sarah and Emily

1. **Sarah approves chore** (execution enters approve_chore)
2. **Lines 3503-3526 execute**: Checks if all_approved for SHARED
3. **At this point**: Sarah = approved, Emily = not approved
4. **all_approved = False** → reschedule DOES NOT trigger
5. **Lines 3583-3606 execute** (user's fix): Resets ALL kids to PENDING
6. **Result**: Sarah = PENDING, Emily = PENDING
7. **Emily approves chore** (second execution)
8. **Lines 3503-3526 execute again**: Checks all_approved
9. **At this point**: Sarah = PENDING (reset earlier), Emily = approved
10. **all_approved = False** (Sarah not approved) → reschedule DOES NOT trigger
11. **Lines 3583-3606 execute**: Resets ALL kids to PENDING again
12. **Loop continues forever** - reschedule never triggers!

**Key Issue**: User's fix resets ALL kids AFTER the all_approved check, so next approval finds some kids PENDING

**Validation Needed**:

**Test Scenario**:

1. Create SHARED chore with 2 kids (Sarah, Emily)
2. Set approval_reset_type = UPON_COMPLETION
3. Approve Sarah → verify both Sarah and Emily states
4. Approve Emily → verify reschedule triggers
5. Check: Does chore-level reschedule occur correctly?

**Expected Behavior**:

- Sarah approves → Sarah = APPROVED, Emily = PENDING
- Emily approves → all_approved = True → reschedule triggers
- After reschedule: Both Sarah and Emily = PENDING (reset by reschedule logic)

**Actual Behavior (if bug exists)**:

- Sarah approves → Both Sarah and Emily = PENDING (immediate reset)
- Emily approves → all_approved = False (Sarah still PENDING) → no reschedule
- Chore stuck in partial approval loop

**Potential Fixes**:

**Option A: Check completion_criteria Before Resetting**

```python
if chore.get("approval_reset_type") == const.APPROVAL_RESET_UPON_COMPLETION:
    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        # Only reset current kid for INDEPENDENT chores
        # ... existing logic ...
    elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
        # For SHARED, only reset if all_approved already triggered reschedule
        # OR don't reset here - let reschedule method handle it
        pass
```

**Option B: Move User's Fix Inside INDEPENDENT Block**

```python
# At lines 3491-3502 (INDEPENDENT chore handling)
if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
    if should_reschedule_immediately:
        await self._reschedule_chore_next_due_date_for_kid(chore_id, kid_name)

    # Add user's fix HERE (only for INDEPENDENT)
    if chore.get("approval_reset_type") == const.APPROVAL_RESET_UPON_COMPLETION:
        # Reset logic...
```

**Option C: Only Reset Approving Kid for SHARED**

```python
if chore.get("approval_reset_type") == const.APPROVAL_RESET_UPON_COMPLETION:
    if completion_criteria == const.COMPLETION_CRITERIA_SHARED:
        # Only reset the kid who just approved, not all kids
        kid_statuses[kid_name]["is_approved_in_current_period"] = False
        kid_statuses[kid_name]["state"] = const.ENTITY_STATE_PENDING
    else:
        # Reset all kids for INDEPENDENT
        # ... existing logic ...
```

**Recommended Approach**: Option B (move fix inside INDEPENDENT block)

- Cleanest separation of INDEPENDENT vs SHARED logic
- SHARED chores already have reschedule logic at lines 3503-3526
- Let \_reschedule_chore_next_due_date() handle PENDING reset (lines 10062-10089)

**Test Coverage Required**:

- [ ] SHARED + UPON_COMPLETION + 2 kids → both approve → reschedule triggers
- [ ] SHARED + UPON_COMPLETION + 3 kids → partial approval → no reschedule
- [ ] SHARED + UPON_COMPLETION + 3 kids → all approve → reschedule triggers
- [ ] INDEPENDENT + UPON_COMPLETION → immediate reset (regression test)

**Priority**: **CRITICAL - RELEASE BLOCKER**

- Must investigate and resolve before v0.5.1 release
- Potential data corruption if SHARED chores never reschedule
- User impact: SHARED chores become unusable with UPON_COMPLETION

---

## Configuration Combination Matrix

### Valid Combinations (by approval_reset_type)

| approval_reset_type | Compatible recurring_frequency                 | Auto-Reset Trigger         | Notes                               |
| ------------------- | ---------------------------------------------- | -------------------------- | ----------------------------------- |
| AT_MIDNIGHT_ONCE    | daily, weekly, biweekly, monthly, custom, none | Midnight timer             | Most common for daily chores        |
| AT_MIDNIGHT_MULTI   | daily, weekly, biweekly, monthly, custom, none | Midnight timer             | Allows multiple completions per day |
| AT_DUE_DATE_ONCE    | daily, weekly, biweekly, monthly, custom, none | **Manual only** (Gap 3)    | Requires investigation              |
| AT_DUE_DATE_MULTI   | daily, weekly, biweekly, monthly, custom, none | **Manual only** (Gap 3)    | Requires investigation              |
| UPON_COMPLETION     | any                                            | Immediate (after approval) | Fixed in Gap 1                      |

### Invalid Combinations (Validation Errors)

| Configuration                                                         | Why Invalid                                             | Validation Check           |
| --------------------------------------------------------------------- | ------------------------------------------------------- | -------------------------- |
| OVERDUE*HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET + AT_DUE_DATE*\* | Circular logic - cleared at reset but reset at due date | flow_helpers.py line 1228  |
| custom_from_complete + FREQUENCY_NONE                                 | Custom frequency requires base frequency                | flow_helpers.py validation |
| SHARED_FIRST + upon_completion                                        | Complex interaction, not currently supported            | May need validation        |

### Edge Cases (Allowed but Surprising)

| Configuration                   | Behavior                                  | Gap   | Warning Needed?     |
| ------------------------------- | ----------------------------------------- | ----- | ------------------- |
| FREQUENCY*NONE + AT_MIDNIGHT*\* | Resets at midnight but never recurs       | -     | ⚠️ Info only        |
| FREQUENCY*NONE + AT_DUE_DATE*\* | Manual reset only, no auto-trigger        | Gap 3 | ⚠️ Yes              |
| SHARED + UPON_COMPLETION        | All kids reset together on first approval | Gap 6 | ⚠️ Yes (if not bug) |
| NEVER_OVERDUE + due_date        | Due date displayed but never overdue      | -     | ℹ️ Info only        |

---

## Testing Strategy

### Phase 1 Testing (Gap Validation)

**Gap 1 & 2 Regression Tests**:

- File: `tests/test_regression_upon_completion_fix.py`
- Coverage: User's fixes don't break existing functionality

**Gap 6 Critical Test**:

- File: `tests/test_gap6_shared_upon_completion.py`
- Coverage: SHARED chore reschedule logic with upon_completion

### Phase 2 Testing (Comprehensive Coverage)

**Frequency × Approval Reset Matrix**:

- 8 frequencies × 5 approval_reset_types = 40 tests
- File: `tests/test_frequency_approval_matrix.py`

**Overdue Handling Matrix**:

- 4 overdue_handling_types × 2 (on-time vs late) = 8 tests
- File: `tests/test_overdue_handling_comprehensive.py`

**Edge Cases**:

- SHARED_FIRST + various reset types
- Parent-assigned chores + kid approval
- Multi-claim (daily_multi) + approval resets

### Coverage Target

**Minimum**: 95% for chore-related coordinator methods

- approve_chore() (lines 3138-3598)
- \_reset_daily_chore_statuses() (lines 9488-9530)
- \_reschedule_chore_next_due_date() (lines 10023-10107)
- \_reschedule_chore_next_due_date_for_kid() (lines 10107-10232)
- \_check_overdue_chores() (lines 9099-9195)
- \_check_overdue_for_chore() (lines 8945-9024)

---

## Recommendations

### Immediate Actions (Before v0.5.1 Release)

1. **Investigate Gap 6** (Critical)
   - Create test scenario: SHARED + UPON_COMPLETION
   - Validate race condition exists or is false positive
   - Apply fix if confirmed (recommend Option B)

2. **Validate Gaps 1 & 2** (High Priority)
   - Run regression tests for INDEPENDENT chores
   - Confirm no unintended side effects

3. **Owner Decision on Gap 3** (Medium Priority)
   - Auto-reset timer vs manual-only?
   - Document decision for validation warnings

### Post-v0.5.1 Enhancements

4. **Add Validation Warnings** (Gap 4)
   - Inform users of non-obvious behaviors
   - Improve config flow UX

5. **Profile and Optimize** (Gap 5)
   - If performance impact measured >100ms
   - Otherwise defer to future version

6. **Complete Logic Audit** (Phase 2)
   - Map all 480 configuration combinations
   - Identify additional edge cases

---

## Appendix: Code References

### Key Methods

| Method                                     | Lines       | Purpose                          |
| ------------------------------------------ | ----------- | -------------------------------- |
| approve_chore()                            | 3138-3598   | Main approval workflow           |
| \_reset_daily_chore_statuses()             | 9488-9530   | Midnight reset handler           |
| \_reschedule_chore_next_due_date()         | 10023-10107 | Chore-level reschedule (SHARED)  |
| \_reschedule_chore_next_due_date_for_kid() | 10107-10232 | Per-kid reschedule (INDEPENDENT) |
| \_check_overdue_chores()                   | 9099-9195   | Full overdue scan                |
| \_check_overdue_for_chore()                | 8945-9024   | Single chore overdue check       |
| \_calculate_next_due_date_from_info()      | 9884-9960   | Due date calculation helper      |

### Constants

| Constant                         | Value               | File     |
| -------------------------------- | ------------------- | -------- |
| APPROVAL_RESET_AT_MIDNIGHT_ONCE  | "at_midnight_once"  | const.py |
| APPROVAL_RESET_AT_MIDNIGHT_MULTI | "at_midnight_multi" | const.py |
| APPROVAL_RESET_AT_DUE_DATE_ONCE  | "at_due_date_once"  | const.py |
| APPROVAL_RESET_AT_DUE_DATE_MULTI | "at_due_date_multi" | const.py |
| APPROVAL_RESET_UPON_COMPLETION   | "upon_completion"   | const.py |
| FREQUENCY_NONE                   | "none"              | const.py |
| COMPLETION_CRITERIA_SHARED       | "shared"            | const.py |
| COMPLETION_CRITERIA_INDEPENDENT  | "independent"       | const.py |

---

**Document Status**: Draft - Pending Gap 6 investigation results
**Next Update**: After Phase 1 testing completion
