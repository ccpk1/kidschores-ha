# Chore Configuration Reference - Technical Foundation

**Status**: 🔄 BUILDING FOUNDATION
**Purpose**: Complete technical understanding before writing user documentation
**Next Step**: Validate with test suite analysis

---

## Configuration Field Order (from `build_chore_schema`)

The UI presents fields in this order:

### Basic Information

1. **Name** (required) - Display name
2. **Description** (optional) - Additional details
3. **Icon** (optional, default: `mdi:broom`) - Visual identifier
4. **Labels** (optional, multiple) - Organization tags
5. **Default Points** (required, default: 10, min: 0, step: 0.1) - Point value

### Assignment & Completion

6. **Assigned Kids** (required, multiple) - Which kids can do this chore
7. **Completion Criteria** (required, default: INDEPENDENT) - Who must complete
   - Options: `independent`, `shared_all`, `shared_first`

### Approval & Reset Behavior (GROUPED TOGETHER)

8. **Approval Reset Type** (required, default: `at_midnight_once`)
   - Controls when approved status returns to pending
   - Controls how many completions allowed per period
9. **Approval Reset Pending Claim Action** (required, default: `clear_pending`)
   - What happens to claimed-but-not-approved chores when approval reset occurs
10. **Auto Approve** (required, default: False)

- Skip approval step, auto-award points on claim

### Overdue Handling

11. **Overdue Handling Type** (required, default: `at_due_date_clear_immediate_on_late`)

- Controls when/if chore shows overdue status and how it recovers
- 4 options (in preference order):
  1.  `at_due_date_clear_immediate_on_late` (DEFAULT - v0.6.0, works with ALL reset types)
  2.  `at_due_date_then_reset` (AT_MIDNIGHT only - auto-clears at midnight)
  3.  `at_due_date` (visible accountability for late completion)
  4.  `never_overdue` (flexible, no pressure)

### Scheduling & Recurrence

12. **Recurring Frequency** (required, default: `none`)

- How often chore repeats

13. **Custom Interval** (optional, conditional) - Number value for custom frequency
14. **Custom Interval Unit** (optional, conditional) - Unit (hours/days/weeks/months)
15. **Applicable Days** (optional, default: ALL 7 days) - Which weekdays chore applies
16. **Due Date** (optional) - Specific date/time when chore is due
17. **Clear Due Date** (conditional, edit mode only) - Checkbox to remove existing due date

### Display & Notifications

18. **Show on Calendar** (required, default: True) - Display in calendar view
19. **Notifications** (optional, multiple) - Notify on claim/approval/disapproval

---

## Approval Reset Types - Complete List

From `const.py`, `translations/en.json`, and **VERIFIED via test_chore_scheduling.py**:

| Constant            | User-Facing Label                                     | Verified Behavior                                                                                                                                                                                              | Test Evidence                                                                                          |
| ------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `at_midnight_once`  | Allow 1 completion - resets at midnight               | ✅ Single completion per period. After approval, stays APPROVED until midnight. Period resets at midnight boundary. New claim allowed if `last_approved < period_start`.                                       | `test_at_midnight_once_allows_claim_after_midnight`                                                    |
| `at_midnight_multi` | Allow multiple completions - resets at midnight       | ✅ **Unlimited** completions per day. After approval, **immediately** returns to PENDING for another claim. Approval count resets at midnight. Can claim → approve → claim → approve unlimited times same day. | `test_at_midnight_multi_allows_multiple_approvals`, `test_at_midnight_multi_period_resets_at_midnight` |
| `at_due_date_once`  | Allow 1 completion - resets at due date               | ✅ Single completion per cycle. Blocks second approval with `already_approved` error. Due date does NOT change on approval. Period resets when due date passes (`period_start` advances).                      | `test_at_due_date_once_blocks_second_approval`, `test_at_due_date_once_due_date_unchanged_on_approval` |
| `at_due_date_multi` | Allow multiple completions - resets at due date       | ✅ **Unlimited** completions until due date passes. After approval, **immediately** returns to PENDING for re-claim. Due date stays same (multi-claim within period). Points awarded for each approval.        | `test_at_due_date_multi_allows_multiple_approvals`, `test_at_due_date_multi_tracks_approval_count`     |
| `upon_completion`   | Allow unlimited completions - resets after completion | ✅ **Immediate** reset to PENDING after approval. NO period tracking (ignores `period_start`). Always claimable regardless of when last approved.                                                              | `test_upon_completion_resets_to_pending`, `test_upon_completion_ignores_period_start_entirely`         |

**Key Terminology**:

- "Approval reset" = Approved status drops, chore returns to pending state (NOT the ambiguous "reset")
- "ONCE" = Single completion per period; stays APPROVED until period boundary
- "MULTI" = Multiple completions per period; returns to PENDING after each approval for immediate re-claim
- "Period" = Time boundary when approval tracking resets (midnight for AT_MIDNIGHT, due date for AT_DUE_DATE)
- "Period_start" = Timestamp of when current approval period began (used to check if approval is in current period)

**Verified Relationships**:

- AT_MIDNIGHT types: Period boundary = midnight local time
- AT_DUE_DATE types: Period boundary = when due date passes (not midnight)
- UPON_COMPLETION: No period boundaries at all (immediate availability)
- MULTI types: Award points for each approval (can earn points 3x, 5x, 10x per day/period)
- ONCE types: Block re-claim until period boundary passes

---

## Overdue Handling Types - VERIFIED from Tests + v0.6.0 Enhancement

From `const.py`, `translations/en.json`, and **VERIFIED via test_chore_scheduling.py**:

| Constant                              | User-Facing Label                                  | Verified Behavior                                                                                                                                                                                                                                                                                                     | Test Evidence / Compatibility                                                                              |
| ------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `at_due_date_clear_immediate_on_late` | Clear Overdue Immediately When Approved Late       | ✅ **NEW v0.6.0 DEFAULT**: Goes OVERDUE at due date. If approved BEFORE reset boundary → stays APPROVED (normal). If approved AFTER reset boundary → **immediately resets to PENDING** (recovers earning window). Works with ALL reset types and ALL recurrence schedules. Critical for DAILY_MULTI and MULTI resets. | Compatible: All `at_midnight_*`, `at_due_date_*`, `upon_completion` reset types. All recurrence schedules. |
| `at_due_date_then_reset`              | Show Overdue After Due Date (Until Approval Reset) | ✅ Becomes OVERDUE at due date, stays overdue until approval reset cycle runs. ONLY works with `at_midnight_*` reset types. When `_reset_daily_chore_statuses()` runs, overdue status is cleared and chore returns to PENDING (even if never approved).                                                               | `test_at_due_date_then_reset_becomes_overdue`, `test_at_due_date_then_reset_resets_after_overdue_window`   |
| `at_due_date`                         | Show Overdue After Due Date (Until Completion)     | ✅ Chore becomes OVERDUE when due date passes. Stays overdue until claimed AND approved. Claimed chores are NOT marked overdue (even with past due date). After approval, stays APPROVED until scheduled reset.                                                                                                       | `test_at_due_date_becomes_overdue_when_past`, `test_claimed_chore_not_marked_overdue`                      |
| `never_overdue`                       | Never Show as Overdue                              | ✅ Chore NEVER shows overdue status regardless of due date. Always shows pending or approved/claimed.                                                                                                                                                                                                                 | _(implied by contrast - no explicit test)_                                                                 |

**Key Insights**:

- Claimed chores are NEVER marked overdue (test explicitly verifies this)
- **NEW DEFAULT v0.6.0**: `at_due_date_clear_immediate_on_late` is now the recommended default for maximum flexibility
- `at_due_date_then_reset` mechanism: Overdue status persists until the reset mechanism runs (`_reset_daily_chore_statuses()`), not until kid completes
- The "THEN_RESET" means the overdue state is cleared BY the approval reset cycle (not by completion/approval)
- Validation: `at_due_date_then_reset` + `at_midnight_*` types = valid (tested). Combination with other reset types not validated in tests.
- **`at_due_date_clear_immediate_on_late` Use Cases**: Detects late approvals (after reset boundary) and immediately resets to PENDING. Prevents losing earning windows due to late parent approval. Especially critical for:
  - DAILY_MULTI time slots (prevents losing entire day's time slots)
  - AT_MIDNIGHT_MULTI scenarios (enables additional claims after late approval)
  - AT_DUE_DATE_MULTI scenarios (enables additional claims in same period)
  - Any ONCE reset where immediate re-availability is desired

**Verified Relationships**:

- Overdue handling is independent of approval reset type EXCEPT:
  - `at_due_date_then_reset` (Option 2) requires `at_midnight_*`
  - `at_due_date_clear_immediate_on_late` (Option 1 - DEFAULT) works with ALL reset types
- `is_overdue()` helper returns `True` only when state == `CHORE_STATE_OVERDUE`
- Overdue check runs via `_check_overdue_chores()` method

**Reset Boundary Detection** (for `at_due_date_clear_immediate_on_late`):

- **AT*MIDNIGHT*\***: Boundary is midnight (00:00)
  - Approved before midnight same day as due date = normal (stays APPROVED)
  - Approved after midnight = late (immediate reset to PENDING)
- **AT*DUE_DATE*\***: Boundary is when due date passes
  - Approved before next due date passes = normal (stays APPROVED)
  - Approved after next due date passes = late (immediate reset to PENDING)
- **UPON_COMPLETION**: No fixed boundary, uses approval reset timing
  - Checks if another reset cycle should have occurred between overdue and approval

---

## Approval Reset Pending Claim Action - VERIFIED from Tests

From `const.py`, `translations/en.json`, and **VERIFIED via test_chore_scheduling.py**:

| Constant               | User-Facing Label                               | Verified Behavior                                                                                                                                                                                  | Test Evidence                                                                                                                                    |
| ---------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `hold_pending`         | Keep in Claim Status (Await Approval/Rejection) | ✅ When approval reset occurs, if chore is CLAIMED (not yet approved), state stays CLAIMED. Pending claim status retained. NO points awarded. Parent must still approve/reject manually.           | `test_pending_hold_retains_claim_after_reset`, `test_pending_hold_no_points_awarded`                                                             |
| `clear_pending`        | Clear All Pending Claims                        | ✅ When approval reset occurs, if chore is CLAIMED, state changes to PENDING. Pending claim status cleared. NO points awarded. Kid loses work credit.                                              | `test_pending_clear_resets_to_pending`, `test_pending_clear_removes_pending_claim`, `test_pending_clear_no_points_awarded`                       |
| `auto_approve_pending` | Auto-Approve All Pending Claims                 | ✅ When approval reset occurs, if chore is CLAIMED, chore is automatically approved AND points awarded. Then resets to PENDING per approval reset type. Pending claim cleared after auto-approval. | `test_pending_auto_approve_awards_points`, `test_pending_auto_approve_then_resets_to_pending`, `test_pending_auto_approve_removes_pending_claim` |

**Use Cases**:

- `hold_pending`: Parent wants to verify work even after reset time (lenient deadline)
- `clear_pending`: Strict deadlines - if not approved by reset time, work doesn't count (default behavior)
- `auto_approve_pending`: Lenient approach - give kid credit even if parent didn't approve in time

**Key Mechanics**:

- These actions ONLY trigger when approval reset mechanism runs (`_reset_daily_chore_statuses()`)
- Only affect chores in CLAIMED state (completed but not approved)
- Already-approved chores are unaffected by pending claim action settings
- Unclaimed chores (still PENDING) are unaffected
- AUTO_APPROVE awards points THEN applies the approval reset logic (chore returns to PENDING per reset type)

**Verified Edge Cases**:

- Already approved chores → unaffected by pending claim action, reset normally per approval reset type
- Unclaimed chores → unaffected, no auto-approval occurs
- Due date must be past for reset to process (test uses `set_chore_due_date_to_past()` helper)

---

## Recurring Frequency Options - VERIFIED from Tests

From `const.py`, `translations/en.json`, and **VERIFIED via test_chore_scheduling.py**:

| Constant               | User-Facing Label                 | Due Date Behavior                                                                                                                                            | Test Evidence                                          |
| ---------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `none`                 | Non-recurring                     | No auto-scheduling. Manual due date only.                                                                                                                    | _(setup implies)_                                      |
| `daily`                | Daily                             | Due date advances by 1 day on approval. Works with applicable_days (snaps to next valid day).                                                                | _(implied by daily reset tests)_                       |
| `daily_multi`          | Daily (Multiple Times Per Day)    | **INCOMPATIBLE** with `at_midnight_*` reset types. Must use `at_due_date_*` or `upon_completion`.                                                            | _(validation rule from code)_                          |
| `weekly`               | Weekly                            | Due date advances by 7 days on approval.                                                                                                                     | _(implied)_                                            |
| `biweekly`             | Every 2 Weeks (Biweekly)          | ✅ Reschedules 14 days after approval. Requires initial due date as anchor.                                                                                  | `test_biweekly_chore_reschedules_14_days`              |
| `monthly`              | Monthly                           | ✅ Reschedules 28-31 days after approval (month length varies). Applicable_days can add up to 6 more days (snap to next valid day). Range: 28-37 days total. | `test_monthly_chore_reschedules_approximately_30_days` |
| `custom`               | Custom Interval (Days)            | Reschedules by custom interval value. Requires due date.                                                                                                     | _(implied)_                                            |
| `custom_from_complete` | Custom Interval (From Completion) | Works like `custom` but next due date calculated from last approval datetime (not current due date). Respects approval reset type.                           | _(implied)_                                            |

**Due Date Requirements** (from validation rules):

- `none`, `daily`, `weekly` → Due date optional (though largely unnecessary with v0.5.0+ overdue handling options)
- `biweekly`, `monthly`, `custom`, `custom_from_complete` → **Due date REQUIRED** (provides schedule anchor)
- `daily_multi` → Uses approval reset timing, not traditional due dates (but due date required for time slot calculation)

> [!NOTE] > **v0.5.0+ Context**: With the introduction of **Overdue Handling options** (Never Overdue, At Due Date, At Due Date Then Reset), the pattern of using daily/weekly recurrence WITHOUT a due date is **largely unnecessary**. Users can now set a due date and choose "Never Overdue" to achieve the same "always available, never overdue" behavior.

**Verified Mechanics**:

- Biweekly = exactly 14 days between due dates
- Monthly = approximately 30 days (28-31 base + up to 6 for applicable_days snapping)
- Frequency interacts with applicable_days: If rescheduled due date lands on non-applicable day, snaps forward to next applicable day
- Approval reset type determines WHEN chore becomes available again; frequency determines NEXT due date

| Constant               | User-Facing Label                        | Due Date Requirement                                       |
| ---------------------- | ---------------------------------------- | ---------------------------------------------------------- |
| `none`                 | None                                     | Optional                                                   |
| `daily`                | Daily                                    | Optional                                                   |
| `daily_multi`          | Daily - Multiple times per day           | **Required**                                               |
| `weekly`               | Weekly                                   | Optional                                                   |
| `biweekly`             | Biweekly                                 | **Required**                                               |
| `monthly`              | Monthly                                  | **Required**                                               |
| `custom`               | Custom                                   | **Required** (needs anchor for interval)                   |
| `custom_from_complete` | Custom - Reschedule from completion date | **Required** (initial due date, then uses completion time) |

**User Clarification**:

- Daily/Weekly have defined periods (midnight/Monday) so can work without due date
- Biweekly/Monthly/Custom need due date to establish the schedule anchor point
- **`custom_from_complete`**: Works exactly like `custom` (respects approval reset type), but calculates next due date from last approval datetime instead of from current due date. Enables rolling schedules ("3 days after completion") vs fixed calendar schedules ("every 3 days from Jan 1").

**⚠️ Custom Hours + AT_MIDNIGHT Incompatibility**:

- If using `custom` with hours unit and interval < 24 hours, **do NOT use AT_MIDNIGHT approval reset types** (at_midnight_once or at_midnight_multi)
- Hour-based schedules conflict with midnight reset boundaries, causing unreliable behavior
- **Recommended**: Use `upon_completion` or `at_due_date_*` reset types with custom hours intervals

**Questions to Answer from Tests**:

- How does `weekly` determine the day of week if no due date? (Fixed Monday reset?)
- Does `daily` always reset at midnight regardless of when completed?
- For `custom_from_complete`, what happens if never completed? (Uses initial due date, then switches to approval-based calculation after first completion?)

---

## Applicable Days - VERIFIED from Tests

From `const.py`, `translations/en.json`, and **VERIFIED via test_chore_scheduling.py**:

**Default Behavior**:

- **Storage**: Empty list `[]` = ALL days valid (no filtering)
- **User Guidance**: Leave blank/empty unless you want to RESTRICT which days chore can be completed
- **Do NOT select all 7 days manually** - this is redundant work and produces same result as empty list
- **Filtering**: Non-empty list restricts which weekdays chore can be completed on

| Configuration                                      | Test Evidence                                        | Behavior                                                                            |
| -------------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Empty list `[]` (DEFAULT)                          | ✅ `test_empty_applicable_days_defaults_to_all_days` | **No restriction. All 7 days valid for completion.** Leave blank for this behavior. |
| Weekday-only `["mon", "tue", "wed", "thu", "fri"]` | ✅ `test_applicable_days_loaded_from_yaml`           | **Restriction**: Chore can only be completed Mon-Fri. Sat/Sun skipped.              |
| Weekend-only `["sat", "sun"]`                      | ✅ `test_applicable_days_loaded_from_yaml`           | **Restriction**: Chore can only be completed Sat-Sun. Mon-Fri skipped.              |
| Custom days `["mon", "wed", "fri"]`                | ✅ `test_applicable_days_loaded_from_yaml`           | **Restriction**: MWF pattern. Due date snaps to next applicable day.                |

**Verified Mechanics**:

- When due date is rescheduled (on approval), if it lands on non-applicable day, it **snaps forward** to next applicable day
- Test: `test_applicable_days_affects_next_due_date` verifies MWF chore's due date always falls on Mon=0, Wed=2, or Fri=4 (weekday numbers)
- Applicable days are independent per kid for shared chores (v0.5.0 feature - per-kid applicable days)

---

## Shared Chore Behaviors - VERIFIED from Tests

From test_chore_scheduling.py - `TestSharedChoreApprovalReset` class:

| Completion Criteria             | Approval Reset Type        | Verified Behavior                                                                                                                                                                              | Test Evidence                                                 |
| ------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| SHARED_ALL + AT_MIDNIGHT_ONCE   | All kids must complete     | ✅ Each kid tracked independently. Zoë can claim/approve once per period. Max can still claim separately (independent per-kid tracking). Chore fully complete when ALL assigned kids approved. | `test_shared_all_midnight_once_per_kid_tracking`              |
| SHARED_FIRST + AT_MIDNIGHT_ONCE | First kid to claim owns it | ✅ First kid to claim blocks all other kids. After approval, all other kids still blocked (ONCE mode). Period must reset before anyone can claim again.                                        | `test_shared_first_midnight_once_blocks_all_kids_after_first` |
| SHARED_ALL approval period      | Chore-level tracking       | ✅ For SHARED chores, approval period tracking is consistent across kids. When one kid completes, period tracking applies to the chore entity (not just individual kid).                       | `test_shared_all_uses_chore_level_period_start`               |

**Key Insights**:

- SHARED_ALL: All assigned kids must complete before chore is "done". Each kid has independent approval tracking.
- SHARED_FIRST: First kid to claim "owns" the chore. Others can't claim until reset.
- Approval period for shared chores tracked at CHORE level, not per-kid level (unlike independent chores)
- Pending claim actions apply per kid for SHARED_ALL, apply to chore for SHARED_FIRST

---

## Validation Rules Found (from `flow_helpers.py`) - VERIFIED

### Rule 1: DAILY_MULTI Compatibility ✅

```python
# DAILY_MULTI incompatible with AT_MIDNIGHT_* reset types
if frequency == FREQUENCY_DAILY_MULTI:
    if reset_type in {APPROVAL_RESET_AT_MIDNIGHT_ONCE, APPROVAL_RESET_AT_MIDNIGHT_MULTI}:
        ERROR: daily_multi_requires_compatible_reset
```

**Rationale**: DAILY*MULTI needs immediate slot advancement after approval. AT_MIDNIGHT*\* keeps chore APPROVED until midnight, blocking time slots.

**Valid Combinations for DAILY_MULTI**:

- ✅ `at_due_date_once`
- ✅ `at_due_date_multi`
- ✅ `upon_completion`
- ❌ `at_midnight_once`
- ❌ `at_midnight_multi`

> [!NOTE] > **DAILY_MULTI + Shared Modes** (v0.5.0+): DAILY_MULTI now works with all completion criteria:
>
> - Independent: Per-kid time slots
> - Shared All: Shared time slots (all kids use same times)
> - Shared First: Shared time slots (first claimer uses shared times)

### Rule 2: DAILY_MULTI Requires Due Date

```python
if frequency == FREQUENCY_DAILY_MULTI:
    if not due_date:
        ERROR: daily_multi_requires_due_date
```

**Rationale**: Time slots need reference point for calculation.

---

## Research Progress Summary

### ✅ ANSWERED Questions (from test analysis):

1. **Approval Reset Behaviors** - COMPLETE

   - ✅ All 5 types verified with exact behaviors
   - ✅ Period boundaries understood (midnight vs due date vs none)
   - ✅ ONCE vs MULTI distinction clear
   - ✅ UPON_COMPLETION has no period tracking at all

2. **Overdue Handling** - COMPLETE

   - ✅ All 3 types verified
   - ✅ Claimed chores never become overdue
   - ✅ AT*DUE_DATE_THEN_RESET works with AT_MIDNIGHT*\* types only
   - ✅ Reset mechanism clears overdue for THEN_RESET type

3. **Pending Claim Actions** - COMPLETE

   - ✅ All 3 types verified (hold, clear, auto_approve)
   - ✅ Only trigger at reset time
   - ✅ Only affect CLAIMED chores
   - ✅ AUTO_APPROVE awards points then resets

4. **Applicable Days** - COMPLETE

   - ✅ Empty list = all days valid
   - ✅ Due date snaps to next applicable day
   - ✅ Works independently for SHARED_ALL per kid (v0.5.0)

5. **Shared Chore Behaviors** - COMPLETE

   - ✅ SHARED_ALL: per-kid independent tracking
   - ✅ SHARED_FIRST: first claimer owns until reset
   - ✅ Period tracking at chore level for shared

6. **Frequency Behaviors** - PARTIAL
   - ✅ Biweekly = exactly 14 days
   - ✅ Monthly = 28-37 days (including applicable_days snap)
   - ✅ DAILY_MULTI validation rules confirmed
   - ⏳ Need: daily/weekly without due date behavior

### ❓ REMAINING Questions:

1. **Frequency + Approval Reset Interaction**:

   - How do `daily` frequency + `at_due_date_once` work together?
   - Does frequency control due date advancement independently of reset?
   - Or are they coupled (reset also advances due date)?

2. **Weekly Frequency Without Due Date**:

   - Does it default to Monday midnight reset?
   - Or does it require due date like biweekly?

3. **Custom Frequency Edge Cases**:

   - `custom_from_complete`: What happens on first occurrence (never completed)?
   - Custom interval: How does it interact with applicable_days?

4. **DAILY_MULTI Time Slots**:

   - How many times per day can be completed?
   - Is it unlimited or configurable?
   - How does due date work with intraday completion tracking?

5. **Entity State Attributes**:
   - What attributes are exposed on chore entities?
   - How is overdue status reflected?
   - What's available for dashboard UI?

---

## Next Analysis Steps

**Priority 1**: Finish reading test_chore_scheduling.py (read ~800 of 2747 lines)

- Focus on frequency interaction tests
- Look for daily/weekly without due date tests
- Find custom frequency examples

**Priority 2**: Analyze test_chore_state_matrix.py

- State transition verification
- Invalid state combinations

**Priority 3**: Analyze test_shared_chore_features.py

- Complete shared chore behaviors
- SHARED vs SHARED_FIRST distinctions

**Priority 4**: Build behavior matrix

- Frequency × Reset Type compatibility table
- Overdue handling × Reset type compatibility
- Pending claim × Reset type interactions

**Priority 5**: Rewrite user documentation

- Use only verified behaviors
- Correct terminology (approval reset vs reset)
- Include test-verified examples

5. **Weekly Frequency Without Due Date**: What day does it reset?

   - Fixed Monday midnight?
   - Or based on creation date?

6. **Custom From Complete**: How does first occurrence work?
   - Uses initial due date, then switches to completion-based?
   - What if initial due date passes without completion?

### Medium Priority Questions:

7. **SHARED Chores + Reset Behaviors**: How do partial claims/approvals work with resets?
8. **Applicable Days + Reset Timing**: Do resets only happen on applicable days?
9. **Auto-Approve + Reset**: Does auto-approve skip the claimed status entirely?
10. **Multiple Completions Per Day**: How does `at_midnight_multi` differ from `upon_completion`?

### Test Files to Review:

- `test_chore_*.py` - Core chore behavior
- `test_workflow_*.py` - End-to-end workflows
- `test_config_flow.py` - Validation rules
- Look for test names with: `reset`, `overdue`, `frequency`, `approval`, `recurring`

---

## Next Steps

1. ✅ **Foundation Built**: Field order, options, basic understanding
2. 🔄 **Test Analysis** (IN PROGRESS): Review test suite to answer all questions
3. ⏳ **Behavior Matrix**: Create complete compatibility matrix
4. ⏳ **User Documentation**: Rewrite guides with verified information
5. ⏳ **Plan Update**: Mark Phase 2/3 as needing revision

---

## Test Analysis Tasks

- [ ] Find all chore-related test files
- [ ] Extract test scenarios covering approval reset types
- [ ] Extract test scenarios covering overdue handling
- [ ] Extract test scenarios covering frequency + reset combinations
- [ ] Document actual behaviors observed in tests
- [ ] Build comprehensive behavior matrix
- [ ] Identify any edge cases or special handling
- [ ] Verify default values and fallback behaviors
