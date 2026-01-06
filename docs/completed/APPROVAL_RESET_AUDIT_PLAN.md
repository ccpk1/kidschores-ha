# Approval Reset Type Audit Plan

**Created**: January 3, 2026
**Status**: ✅ FIX IMPLEMENTED - VALIDATION COMPLETE (Awaiting Manual Verification)
**Priority**: HIGH - Production Bug Fix
**Last Updated**: January 4, 2026

---

## Quick Reference: Approval Reset Behavior (User Guide)

This section explains how approval reset types work, including edge cases like overdue chores.

### Reset Type Summary

| Reset Type            | When Does Period Reset?    | Can Claim Again After Approval?          |
| --------------------- | -------------------------- | ---------------------------------------- |
| **At Midnight Once**  | Every day at midnight      | NO - wait until midnight                 |
| **At Midnight Multi** | Every day at midnight      | YES - can earn multiple times per day    |
| **At Due Date Once**  | When due date passes       | NO - wait until due date passes          |
| **At Due Date Multi** | When due date passes       | YES - can earn multiple times per period |
| **Upon Completion**   | Immediately after approval | YES - immediately available              |

### Cross-Period Approval Behavior (Overdue Chores)

**Question**: What happens when a kid claims an overdue chore from yesterday and the parent approves today?

**Answer**: The approval counts for the **current period** (today).

**Example**:

```
Scenario: "Brush Teeth" chore with AT_MIDNIGHT_ONCE reset
- Monday 8PM: Due time passes, chore becomes OVERDUE
- Tuesday 7AM: Kid claims the overdue chore
- Tuesday 7:30AM: Parent approves
- Result: Chore is APPROVED until Wednesday midnight (Tuesday's period)
```

**Rationale**:

- The parent explicitly approved the work, so the approval should count
- If parent wanted the kid to do it again today, they could reject the claim
- Simple, predictable rule: approval always counts for the current period

### Pending Claim Action (What Happens at Period Reset?)

| Setting                     | Behavior at Period Reset                                          |
| --------------------------- | ----------------------------------------------------------------- |
| **Clear Pending** (default) | Pending claims are discarded, kid must re-claim                   |
| **Hold Pending**            | Pending claims stay pending, parent can still approve after reset |
| **Auto-Approve Pending**    | Pending claims are automatically approved, then reset to pending  |

---

## Problem Statement

The approval reset functionality is not working correctly. Specifically, independent chores with `at_midnight_once` reset type are allowing multiple claims/approvals when they should only allow one completion per day.

---

## Resolution Summary - Bug #1 (COMPLETED)

**Root Cause**: Code in `_process_chore_state()` was incorrectly **deleting `last_approved`** timestamp when transitioning to PENDING state. This broke `is_approved_in_current_period()` which checks if `last_approved` exists.

**Fix Applied**: Removed code that deletes `last_approved` in 3 locations:

1. `coordinator.py` PENDING state branch (lines 3403-3407)
2. `coordinator.py` COMPLETED_BY_OTHER state branch (lines 3434-3442)
3. `services.py` reset_all_chores service (lines 897-908) - changed to remove `approval_period_start` instead

**Key Principle**: `last_approved` should **NEVER be removed** - it's for historical tracking only. The `approval_period_start` mechanism handles period-based validation.

**Validation**:

- ✅ Lint: 9.61/10
- ✅ test_approval_reset_timing.py: 39/39 passed
- ✅ test_workflow_independent_approval_reset.py: 6/6 passed
- ✅ Full test suite: 699 passed, 35 skipped, 1 pre-existing error (unrelated)

---

## 🔴 CRITICAL BUG #2 FOUND - Immediate PENDING Reset After Approval

**Discovered**: January 3, 2026 (during production testing)
**Status**: ANALYSIS IN PROGRESS

### Symptom

After approving an INDEPENDENT chore with `at_midnight_once` reset type:

1. Chore immediately goes back to PENDING state
2. `approval_period_start` is set AFTER `last_approved` (by ~20ms)
3. Kid can claim and approve again immediately (unlimited times)

### Evidence from Storage

```json
{
  "approval_period_start": "2026-01-03T22:33:22.374444+00:00",
  "last_approved": "2026-01-03T22:33:22.354998+00:00"
}
```

Note: `approval_period_start` is 20ms AFTER `last_approved`, causing `is_approved_in_current_period()` to return `False`.

### Root Cause

**Location**: `coordinator.py` line 8771-8772 in `_reschedule_chore_next_due_date_for_kid()`

**Code**:

```python
# Reset kid's chore state to PENDING (clears overdue status)
self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
```

**Call Chain**:

1. `approve_chore()` calls `_process_chore_state(APPROVED)` → sets `last_approved = now`
2. `approve_chore()` calls `_reschedule_chore_next_due_date_for_kid()` (for INDEPENDENT chores)
3. `_reschedule_chore_next_due_date_for_kid()` calls `_process_chore_state(PENDING)` → sets `approval_period_start = now` (slightly later)

**Result**: `approval_period_start > last_approved`, so `is_approved_in_current_period()` returns `False`, allowing unlimited claims.

### Similar Issue in SHARED Chores

**Location**: `coordinator.py` line 8667-8670 in `_reschedule_chore_next_due_date()`

```python
# Update all assigned kids' state to PENDING
for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
    if kid_id:
        self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
```

### Required Fix Analysis

The fix is NOT simply removing `_process_chore_state(PENDING)` - we need to consider:

1. **Different reset types** have different expected behaviors
2. **Overdue handling** may need the PENDING reset
3. **Due date rescheduling** should NOT reset approval tracking for `*_ONCE` types

See **SCENARIO MATRIX** below for full analysis.

---

## 🔴 BUG #2 FIX: Comprehensive Scenario Matrix

### Configuration Dimensions

**Dimension 1: Approval Reset Type (5 options)**
| Constant | Value | Expected After Approval |
|----------|-------|------------------------|
| `APPROVAL_RESET_AT_MIDNIGHT_ONCE` | `at_midnight_once` | Stay APPROVED until midnight |
| `APPROVAL_RESET_AT_MIDNIGHT_MULTI` | `at_midnight_multi` | Stay APPROVED, allow reclaim |
| `APPROVAL_RESET_AT_DUE_DATE_ONCE` | `at_due_date_once` | Stay APPROVED until due date passes |
| `APPROVAL_RESET_AT_DUE_DATE_MULTI` | `at_due_date_multi` | Stay APPROVED, allow reclaim |
| `APPROVAL_RESET_UPON_COMPLETION` | `upon_completion` | Immediate reset to PENDING |

**Dimension 2: Completion Criteria (3 options)**
| Constant | Value | Due Date Handling | Reschedule Function |
|----------|-------|-------------------|---------------------|
| `COMPLETION_CRITERIA_INDEPENDENT` | `independent` | Per-kid due dates | `_reschedule_chore_next_due_date_for_kid()` |
| `COMPLETION_CRITERIA_SHARED` | `shared` | Single chore-level due date | `_reschedule_chore_next_due_date()` |
| `COMPLETION_CRITERIA_SHARED_FIRST` | `shared_first` | Single chore-level due date | `_reschedule_chore_next_due_date()` |

**Dimension 3: Overdue Handling Type (3 options)**
| Constant | Value | Behavior |
|----------|-------|----------|
| `OVERDUE_HANDLING_AT_DUE_DATE` | `at_due_date` | Mark overdue when past due (default) |
| `OVERDUE_HANDLING_NEVER_OVERDUE` | `never_overdue` | Never mark as overdue |
| `OVERDUE_HANDLING_AT_DUE_DATE_THEN_RESET` | `at_due_date_then_reset` | Mark overdue, clear at next reset |

### The Problem in Detail

When `approve_chore()` runs for non-UPON_COMPLETION types:

1. `_process_chore_state(APPROVED)` sets `last_approved = now`
2. For INDEPENDENT: calls `_reschedule_chore_next_due_date_for_kid()` which:
   - Updates due date to next occurrence
   - Calls `_process_chore_state(PENDING)` → sets `approval_period_start = now + ε`
3. Result: `approval_period_start > last_approved`, so `is_approved_in_current_period()` returns `False`

### Key Question: What Should Reschedule Do?

The reschedule functions serve TWO purposes:

1. **Update due date** to next occurrence (always needed after approval)
2. **Reset state to PENDING** (only needed for UPON_COMPLETION!)

For `AT_MIDNIGHT_*` and `AT_DUE_DATE_*` types:

- Due date should update (so next period's deadline is correct)
- State should NOT reset (stays APPROVED until scheduled reset)

### Overdue Handling Interaction Analysis

The overdue system marks chores as OVERDUE when past due date. Questions:

1. **Does resetting to PENDING clear overdue?** → Yes, `_process_chore_state(PENDING)` clears from `DATA_KID_OVERDUE_CHORES`
2. **Do we NEED the PENDING reset to clear overdue after approval?** → NO!
   - If approved, chore shouldn't be overdue anyway (approval implies completion)
   - The `is_approved_in_current_period()` check in overdue logic skips approved chores
3. **What about `AT_DUE_DATE_THEN_RESET`?** → This type means "mark overdue at due date, clear at next reset cycle"
   - The "next reset cycle" is midnight/due-date, NOT immediately after approval
   - So this doesn't affect our fix

### Full Verification Matrix (5 × 3 × 3 = 45 scenarios)

For practical testing, we focus on the critical combinations:

| #                     | Reset Type        | Completion   | Overdue                | After Approve | Can Claim? | Can Approve? | Due Date        |
| --------------------- | ----------------- | ------------ | ---------------------- | ------------- | ---------- | ------------ | --------------- |
| **AT_MIDNIGHT_ONCE**  |
| 1                     | AT_MIDNIGHT_ONCE  | INDEPENDENT  | AT_DUE_DATE            | APPROVED      | NO         | NO           | Updated to next |
| 2                     | AT_MIDNIGHT_ONCE  | INDEPENDENT  | NEVER_OVERDUE          | APPROVED      | NO         | NO           | Updated to next |
| 3                     | AT_MIDNIGHT_ONCE  | INDEPENDENT  | AT_DUE_DATE_THEN_RESET | APPROVED      | NO         | NO           | Updated to next |
| 4                     | AT_MIDNIGHT_ONCE  | SHARED       | AT_DUE_DATE            | APPROVED      | NO         | NO           | Updated to next |
| 5                     | AT_MIDNIGHT_ONCE  | SHARED_FIRST | AT_DUE_DATE            | APPROVED      | NO         | NO           | Updated to next |
| **AT_MIDNIGHT_MULTI** |
| 6                     | AT_MIDNIGHT_MULTI | INDEPENDENT  | AT_DUE_DATE            | APPROVED      | YES\*      | YES\*        | Updated to next |
| 7                     | AT_MIDNIGHT_MULTI | SHARED       | AT_DUE_DATE            | APPROVED      | YES\*      | YES\*        | Updated to next |
| **AT_DUE_DATE_ONCE**  |
| 8                     | AT_DUE_DATE_ONCE  | INDEPENDENT  | AT_DUE_DATE            | APPROVED      | NO         | NO           | Updated to next |
| 9                     | AT_DUE_DATE_ONCE  | SHARED       | AT_DUE_DATE            | APPROVED      | NO         | NO           | Updated to next |
| **AT_DUE_DATE_MULTI** |
| 10                    | AT_DUE_DATE_MULTI | INDEPENDENT  | AT_DUE_DATE            | APPROVED      | YES\*      | YES\*        | Updated to next |
| 11                    | AT_DUE_DATE_MULTI | SHARED       | AT_DUE_DATE            | APPROVED      | YES\*      | YES\*        | Updated to next |
| **UPON_COMPLETION**   |
| 12                    | UPON_COMPLETION   | INDEPENDENT  | AT_DUE_DATE            | PENDING       | YES        | YES          | Updated to next |
| 13                    | UPON_COMPLETION   | SHARED       | AT_DUE_DATE            | PENDING       | YES        | YES          | Updated to next |
| 14                    | UPON_COMPLETION   | INDEPENDENT  | NEVER_OVERDUE          | PENDING       | YES        | YES          | Updated to next |

\*YES = `_can_claim_chore()` and `_can_approve_chore()` need to allow multi-claim for MULTI types

### Current Bug Analysis by Scenario

| Scenario                  | Current Behavior      | Expected               | Bug?                                          |
| ------------------------- | --------------------- | ---------------------- | --------------------------------------------- |
| 1-5 (AT_MIDNIGHT_ONCE)    | PENDING (can reclaim) | APPROVED (blocked)     | ❌ BUG                                        |
| 6-7 (AT_MIDNIGHT_MULTI)   | PENDING (can reclaim) | APPROVED (can reclaim) | ⚠️ State wrong, behavior accidentally correct |
| 8-9 (AT_DUE_DATE_ONCE)    | PENDING (can reclaim) | APPROVED (blocked)     | ❌ BUG                                        |
| 10-11 (AT_DUE_DATE_MULTI) | PENDING (can reclaim) | APPROVED (can reclaim) | ⚠️ State wrong, behavior accidentally correct |
| 12-14 (UPON_COMPLETION)   | PENDING (can reclaim) | PENDING (can reclaim)  | ✅ CORRECT                                    |

---

## BUG #2 FIX: Implementation Plan

### Fix Option A: Conditional Reset Based on Reset Type (RECOMMENDED)

Modify both reschedule functions to only call `_process_chore_state(PENDING)` for `UPON_COMPLETION`:

**In `_reschedule_chore_next_due_date_for_kid()` (line ~8771-8772):**

```python
# BEFORE (BUG):
# Reset kid's chore state to PENDING (clears overdue status)
self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)

# AFTER (FIX):
# Only reset to PENDING for UPON_COMPLETION type
# Other types stay APPROVED until scheduled reset (midnight/due_date)
approval_reset = chore_info.get(
    const.DATA_CHORE_APPROVAL_RESET_TYPE,
    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE
)
if approval_reset == const.APPROVAL_RESET_UPON_COMPLETION:
    self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
```

**In `_reschedule_chore_next_due_date()` (line ~8667-8670):**

```python
# BEFORE (BUG):
# Update all assigned kids' state to PENDING
for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
    if kid_id:
        self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)

# AFTER (FIX):
# Only reset to PENDING for UPON_COMPLETION type
approval_reset = chore_info.get(
    const.DATA_CHORE_APPROVAL_RESET_TYPE,
    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE
)
if approval_reset == const.APPROVAL_RESET_UPON_COMPLETION:
    for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
        if kid_id:
            self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)
```

### Overdue Handling - No Changes Needed

Analysis confirms overdue handling does NOT require immediate PENDING reset:

1. **Approved chores skip overdue check** - `is_approved_in_current_period()` check in `_check_overdue_*` methods
2. **Due date update sufficient** - Overdue status derived from comparing current time vs due_date
3. **`AT_DUE_DATE_THEN_RESET`** - "Reset" refers to scheduled reset cycle, not approval

### Additional Consideration: MULTI Type Behavior

For `*_MULTI` types, after approval:

- State stays APPROVED
- But `_can_claim_chore()` should allow new claims (it checks reset type)
- Verify this logic works correctly after fix

---

## 🔴 DIMENSION 4: Cross-Period Approval (CRITICAL EDGE CASE)

### The Problem

The 3-dimensional matrix above assumes approval happens **within the same period** as the due date.
But what happens when:

1. Chore becomes overdue (missed period)
2. Approval happens AFTER the period boundary has passed

### Concrete Scenarios

**Scenario A: Same-Day Approval (Standard)**

```
AT_MIDNIGHT_ONCE | INDEPENDENT | AT_DUE_DATE
- Monday 8PM: Chore due, kid misses it → OVERDUE
- Monday 9PM: Kid claims
- Monday 9:15PM: Parent approves
- Expected: APPROVED until midnight Tuesday
- Tuesday 12:01AM: Resets to PENDING
```

✅ Standard behavior - approval is within same period

**Scenario B: Cross-Day Approval (Edge Case)**

```
AT_MIDNIGHT_ONCE | INDEPENDENT | AT_DUE_DATE
- Monday 8PM: Chore due, kid misses it → OVERDUE
- Tuesday 7AM: Kid claims (chore still OVERDUE from Monday)
- Tuesday 7:30AM: Parent approves
- Question: Does approval stay until Wednesday midnight (17+ hours)?
           Or reset immediately since Monday's period already passed?
```

### Analysis: What SHOULD Happen in Cross-Period Approval?

**Two valid interpretations:**

**Interpretation A: "Approval counts for current day"**

- Tuesday's approval → counts for Tuesday → stays approved until Wednesday midnight
- Rationale: Simple rule - approval always counts for current period
- Downside: Kid "skips" Monday's chore with no consequence

**Interpretation B: "Approval clears overdue only, current day still pending"**

- Tuesday's approval → clears Monday's overdue → Tuesday's instance immediately available
- Rationale: Kid missed Monday, shouldn't block Tuesday
- Downside: Complex logic, may confuse users ("I just approved, why can they claim again?")

### Current Code Behavior

With the proposed fix (don't reset to PENDING after approval), the current logic is:

1. `approve_chore()` sets `last_approved = Tuesday 7:30AM`
2. `_reschedule_chore_next_due_date_for_kid()` updates due_date to Tuesday 8PM (next occurrence)
3. `is_approved_in_current_period()` checks: `last_approved >= approval_period_start`
   - If `approval_period_start` was set Monday 12:01AM (last reset), then Tuesday 7:30AM > Monday 12:01AM
   - Returns TRUE → chore stays approved until next reset (Tuesday midnight)

**Result**: Current code implements **Interpretation A** - approval counts for current day.

### Additional Complexity: Pending Claim Action

**Dimension 5: Pending Claim Action (3 options)**
| Constant | Value | At Period Reset Behavior |
|----------|-------|-------------------------|
| `APPROVAL_RESET_PENDING_CLAIM_HOLD` | `hold_pending` | Keep pending claim, don't reset kid's state |
| `APPROVAL_RESET_PENDING_CLAIM_CLEAR` | `clear_pending` | Clear pending claim, reset to PENDING (default) |
| `APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE` | `auto_approve_pending` | Auto-approve pending claim, then reset |

This setting affects what happens to pending claims at the period boundary:

- **HOLD**: If kid claimed Monday 8PM but parent didn't approve by midnight → claim stays pending
- **CLEAR**: Claim gets discarded at midnight, kid must re-claim
- **AUTO_APPROVE**: Claim gets auto-approved at midnight, then resets for new period

### Cross-Period + Pending Claim Scenarios

**Scenario C: Hold + Cross-Day**

```
AT_MIDNIGHT_ONCE | INDEPENDENT | AT_DUE_DATE | HOLD_PENDING
- Monday 8PM: Chore due
- Monday 9PM: Kid claims → pending
- Tuesday 12:01AM: HOLD keeps claim pending (no reset)
- Tuesday 7:30AM: Parent approves the pending claim
- What period does this count for?
```

**Scenario D: Clear + Cross-Day**

```
AT_MIDNIGHT_ONCE | INDEPENDENT | AT_DUE_DATE | CLEAR_PENDING
- Monday 8PM: Chore due
- Monday 9PM: Kid claims → pending
- Tuesday 12:01AM: CLEAR discards claim, resets to PENDING
- Tuesday 7AM: Kid claims again
- Tuesday 7:30AM: Parent approves
- Expected: Standard Tuesday approval, wait until Wednesday
```

### Design Decision Required

For **Cross-Period Approval**, the question is:

**Option 1: Keep current behavior (Interpretation A)**

- Pros: Simple, predictable
- Cons: Kid can "skip" days by waiting until next day to claim

**Option 2: Implement "catch-up" logic (Interpretation B)**

- Pros: Fair - kid can't skip days without consequence
- Cons: Complex, potentially confusing UX

**Recommendation**: Start with **Option 1** (current behavior) for the bug fix.
If users request "catch-up" logic, implement as separate feature with new setting.

### Updated Matrix with Cross-Period Consideration

| #   | Reset Type       | Claim Day           | Approve Day | Expected Result                         |
| --- | ---------------- | ------------------- | ----------- | --------------------------------------- |
| 1   | AT_MIDNIGHT_ONCE | Monday              | Monday      | APPROVED until Tuesday midnight         |
| 2   | AT_MIDNIGHT_ONCE | Monday (overdue)    | Tuesday     | APPROVED until Wednesday midnight       |
| 3   | AT_MIDNIGHT_ONCE | Tuesday             | Tuesday     | APPROVED until Wednesday midnight       |
| 4   | AT_DUE_DATE_ONCE | Before due          | Same cycle  | APPROVED until next due date            |
| 5   | AT_DUE_DATE_ONCE | After due (overdue) | After due   | APPROVED until next due date after that |
| 6   | UPON_COMPLETION  | Any                 | Any         | Immediate reset to PENDING              |

---

## BUG #2 FIX: Progress Tracking

| Step                                                         | Status      | Notes                                                                    |
| ------------------------------------------------------------ | ----------- | ------------------------------------------------------------------------ |
| Identify root cause                                          | ✅ Complete | `_process_chore_state(PENDING)` in reschedule functions                  |
| Analyze reset type interactions                              | ✅ Complete | Only UPON_COMPLETION should reset immediately                            |
| Analyze overdue handling interactions                        | ✅ Complete | No dependency on immediate PENDING reset                                 |
| Analyze completion criteria interactions                     | ✅ Complete | Both INDEPENDENT and SHARED functions affected                           |
| Create verification matrix                                   | ✅ Complete | 14 key scenarios documented                                              |
| Analyze cross-period approval behavior                       | ✅ Complete | Decision: Interpretation A - approval counts for current period          |
| Implement fix in `_reschedule_chore_next_due_date_for_kid()` | ✅ Complete | Only UPON_COMPLETION resets to PENDING                                   |
| Implement fix in `_reschedule_chore_next_due_date()`         | ✅ Complete | Only UPON_COMPLETION resets to PENDING                                   |
| Run linting                                                  | ✅ Complete | 9.61/10 - all checks passed                                              |
| Run tests                                                    | ✅ Complete | 699 passed, 35 skipped (1 unrelated teardown error in notification mock) |
| Manual verification                                          | ⬜ Pending  | Awaiting production testing                                              |

---

## Correct Behavior Specification

### APPROVAL_RESET_AT_MIDNIGHT_ONCE

| Aspect             | Expected Behavior                                                                                         |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| **Claim**          | Kid can claim multiple times per day (if rejected, they can re-submit). Only one pending claim at a time. |
| **Approval**       | Parent can approve **only once** per day                                                                  |
| **After Approval** | Chore remains in **APPROVED state**. New claims AND approvals blocked until midnight.                     |
| **Reset**          | At midnight, `approval_period_start` updates, chore resets to PENDING                                     |
| **last_approved**  | **NEVER removed** - historical tracking only                                                              |

### APPROVAL_RESET_AT_MIDNIGHT_MULTI

| Aspect             | Expected Behavior                                                     |
| ------------------ | --------------------------------------------------------------------- |
| **Claim**          | Kid can claim multiple times per day                                  |
| **Approval**       | Parent can approve **multiple times** per day                         |
| **After Approval** | Chore remains in APPROVED state, but can be claimed again immediately |
| **Reset**          | At midnight, `approval_period_start` updates, chore resets to PENDING |
| **last_approved**  | **NEVER removed** - updated with each approval                        |

### APPROVAL_RESET_AT_DUE_DATE_ONCE

| Aspect             | Expected Behavior                                                              |
| ------------------ | ------------------------------------------------------------------------------ |
| **Claim**          | Kid can claim multiple times (if rejected), one pending at a time              |
| **Approval**       | Parent can approve **only once** per due date period                           |
| **After Approval** | Chore remains APPROVED, new claims/approvals blocked until due date passes     |
| **Reset**          | When due date passes, `approval_period_start` updates, chore resets to PENDING |
| **last_approved**  | **NEVER removed**                                                              |

### APPROVAL_RESET_AT_DUE_DATE_MULTI

| Aspect             | Expected Behavior                                         |
| ------------------ | --------------------------------------------------------- |
| **Claim**          | Kid can claim multiple times per due date period          |
| **Approval**       | Parent can approve **multiple times** per due date period |
| **After Approval** | Chore remains APPROVED, can be claimed again immediately  |
| **Reset**          | When due date passes, chore resets to PENDING             |
| **last_approved**  | **NEVER removed**                                         |

### APPROVAL_RESET_UPON_COMPLETION

| Aspect             | Expected Behavior                              |
| ------------------ | ---------------------------------------------- |
| **Claim**          | Kid can claim anytime                          |
| **Approval**       | Parent can approve anytime                     |
| **After Approval** | Chore **immediately resets to PENDING**        |
| **Reset**          | Instant - no blocking period                   |
| **last_approved**  | **NEVER removed** - updated with each approval |

---

## Key State Transitions

### Normal Flow (ONCE variants)

```
PENDING → [claim] → CLAIMED → [approve] → APPROVED → [midnight/due_date reset] → PENDING
                        ↓
                  [disapprove] → PENDING (can re-claim)
```

### Multi Flow (MULTI variants)

```
PENDING → [claim] → CLAIMED → [approve] → APPROVED → [immediate] → can claim again
                                              ↓
                                    [midnight/due_date reset] → PENDING
```

### Upon Completion Flow

```
PENDING → [claim] → CLAIMED → [approve] → PENDING (immediate reset)
```

---

## Phase 1: Code Audit

### 1.1 Review `_can_claim_chore()` method

- [ ] Verify ONCE variants block claims after approval (not just pending claims)
- [ ] Verify MULTI variants allow claims even after approval
- [ ] Verify UPON_COMPLETION allows claims after approval
- [ ] Verify pending claim check (only one pending at a time for ONCE)

### 1.2 Review `_can_approve_chore()` method

- [ ] Verify ONCE variants block approvals after first approval in period
- [ ] Verify MULTI variants allow multiple approvals
- [ ] Verify UPON_COMPLETION allows unlimited approvals

### 1.3 Review `_process_chore_state()` method

- [ ] Verify APPROVED state is preserved (not reset to PENDING for ONCE/MULTI)
- [ ] Verify UPON_COMPLETION resets to PENDING after approval
- [ ] Verify `last_approved` is NEVER removed
- [ ] Verify `approval_period_start` is set correctly

### 1.4 Review `is_approved_in_current_period()` method

- [ ] Verify correct period calculation for AT_MIDNIGHT variants
- [ ] Verify correct period calculation for AT_DUE_DATE variants
- [ ] Verify UPON_COMPLETION always returns False (to allow re-approval)

### 1.5 Review `has_pending_claim()` method

- [ ] Verify pending claim detection is working correctly
- [ ] Verify claim is cleared after approval

### 1.6 Review reset logic

- [ ] Verify midnight reset in `_check_for_resets()` or scheduler
- [ ] Verify due date reset logic
- [ ] Verify `approval_period_start` is updated on reset

---

## Phase 2: Identify Issues

### 🔴 CRITICAL BUG FOUND

**Location**: `coordinator.py` lines 3403-3407 in `_process_chore_state()` PENDING branch

**Code**:

```python
# Clear last_approved timestamp to reset to pending (v0.4.0+ timestamp-based)
# NOTE: last_claimed is intentionally preserved for historical tracking
kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
if chore_id in kid_chores_data:
    kid_chores_data[chore_id].pop(
        const.DATA_KID_CHORE_DATA_LAST_APPROVED, None
    )
```

**Issue**: Code **removes `last_approved`** when transitioning to PENDING state

**Expected**: `last_approved` should **NEVER be removed** - it's for historical tracking only

**Actual**: `last_approved` is deleted, causing `is_approved_in_current_period()` to always return `False`

**Impact**:

- `is_approved_in_current_period()` checks `if not last_approved: return False` (line 3152)
- When `last_approved` is deleted, approval check fails
- This allows multiple claims/approvals when ONCE variants should block them

**Root Cause Analysis**:

1. Chore is approved → `last_approved` set to current timestamp
2. State somehow transitions to PENDING (bug or manual reset)
3. `last_approved` is **deleted** by the PENDING branch code
4. `is_approved_in_current_period()` returns `False` because `last_approved` doesn't exist
5. Kid can claim again even though they already completed the chore today

**Fix**: Remove the code that deletes `last_approved`. The `approval_period_start` mechanism already handles period-based validation:

- When period resets (midnight/due_date), `approval_period_start` is updated to current time
- `is_approved_in_current_period()` compares `last_approved >= approval_period_start`
- If `last_approved` < `approval_period_start`, the approval is from a previous period and returns `False`

| Location                 | Issue                                          | Expected                     | Actual                              |
| ------------------------ | ---------------------------------------------- | ---------------------------- | ----------------------------------- |
| coordinator.py:3403-3407 | Deleting `last_approved` on PENDING transition | Never remove `last_approved` | Code pops `last_approved` from dict |

---

## Phase 3: Implementation Fixes

### 3.1 Fix `_can_claim_chore()` (if needed)

- Current logic:
  - Check pending claim → block if ONCE
  - Check approved in period → block if ONCE
- Required logic:
  - Check approved in period → block if ONCE (AFTER approval, no more claims allowed)
  - Check pending claim → block if ONCE (only one pending at a time)

### 3.2 Fix `_process_chore_state()` for APPROVED state (if needed)

- ONCE/MULTI: Remain in APPROVED state
- UPON_COMPLETION: Immediately reset to PENDING

### 3.3 Fix reset logic (if needed)

- Ensure `approval_period_start` is updated correctly
- Ensure state transitions to PENDING on reset

---

## Phase 4: Testing

### 4.1 Update/Create Test Cases

- [ ] `test_at_midnight_once_blocks_claims_after_approval`
- [ ] `test_at_midnight_once_allows_reclaim_after_disapproval`
- [ ] `test_at_midnight_once_blocks_approval_after_first_approval`
- [ ] `test_at_midnight_multi_allows_multiple_approvals`
- [ ] `test_at_due_date_once_blocks_until_due_date`
- [ ] `test_upon_completion_immediate_reset`

### 4.2 Run Test Suite

```bash
python -m pytest tests/test_approval_reset_timing.py -v
```

---

## Phase 5: Validation

- [ ] Lint check passes: `./utils/quick_lint.sh --fix`
- [ ] All tests pass: `python -m pytest tests/ -v --tb=line`
- [ ] Manual testing with dev instance confirms correct behavior

---

## Progress Tracking

| Phase                    | Status      | Notes                                         |
| ------------------------ | ----------- | --------------------------------------------- |
| Phase 1: Code Audit      | ✅ Complete | Found critical bug in \_process_chore_state() |
| Phase 2: Identify Issues | ✅ Complete | Bug documented below                          |
| Phase 3: Implementation  | ✅ Complete | Fixed in 3 locations                          |
| Phase 4: Testing         | ✅ Complete | All approval reset tests pass                 |
| Phase 5: Validation      | ✅ Complete | Full test suite passes                        |

---

## Key Files to Review

- `custom_components/kidschores/coordinator.py`:

  - `_can_claim_chore()` - ~line 3180
  - `_can_approve_chore()` - ~line 3220
  - `_process_chore_state()` - ~line 3280
  - `is_approved_in_current_period()` - need to locate
  - `has_pending_claim()` - need to locate
  - `approve_chore()` - ~line 2570
  - `claim_chore()` - ~line 2400

- `custom_components/kidschores/const.py`:

  - `APPROVAL_RESET_*` constants

- `tests/test_approval_reset_timing.py`:
  - Existing tests for approval reset behavior
