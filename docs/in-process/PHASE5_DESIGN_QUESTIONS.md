# Phase 5 (Overdue Handling) – Design Decisions

**Status**: ✅ DESIGN COMPLETE (Dec 29, 2025)

**Ready for**: Implementation phase

---

## Final Design Summary

### Two New Fields for Chore Configuration

| Field                                 | Purpose                                          | Values        | Default         |
| ------------------------------------- | ------------------------------------------------ | ------------- | --------------- |
| `overdue_handling_type`               | Controls if/when chore becomes overdue           | 3 enum values | `AT_DUE_DATE`   |
| `approval_reset_pending_claim_action` | Controls what happens to pending claims at reset | 3 enum values | `CLEAR_PENDING` |

### Field 1: `overdue_handling_type`

| Value                    | User Label                             | Goes Overdue?              | At Reset                             |
| ------------------------ | -------------------------------------- | -------------------------- | ------------------------------------ |
| `AT_DUE_DATE`            | "Overdue until complete"               | Yes, when due date passes  | Stays overdue until kid completes    |
| `NEVER_OVERDUE`          | "Never overdue"                        | No, never shows as overdue | Reschedules silently                 |
| `AT_DUE_DATE_THEN_RESET` | "Overdue until complete or next reset" | Yes, when due date passes  | Clears overdue, reschedules at reset |

**Default**: `AT_DUE_DATE` (current behavior - stays overdue until completed)

### Field 2: `approval_reset_pending_claim_action`

| Value                  | User Label               | Behavior at Reset                                        |
| ---------------------- | ------------------------ | -------------------------------------------------------- |
| `HOLD_PENDING`         | "Hold for parent review" | Claim persists, blocks new instance until resolved       |
| `CLEAR_PENDING`        | "Clear and start fresh"  | Claim dropped, new instance created                      |
| `AUTO_APPROVE_PENDING` | "Auto-approve at reset"  | System approves pending claim, then creates new instance |

**Default**: `CLEAR_PENDING` (current behavior - pending claims are dropped at reset)

**Key Insight**: `approval_reset_pending_claim_action` is separate from `overdue_handling_type` because:

- Kid might claim on time but parent doesn't approve before reset - that's not the kid's fault
- The pending claim behavior is an approval workflow concern, not an overdue concern

---

## Shared Chore Considerations

### How Fields Apply to `completion_criteria` Modes

The two new fields interact with Phase 3's `completion_criteria`:

| completion_criteria | overdue_handling_type applies to... | pending_claim_action applies to... |
| ------------------- | ----------------------------------- | ---------------------------------- |
| `INDEPENDENT`       | Each kid independently              | Each kid's pending claim           |
| `SHARED_ALL`        | Chore instance (all kids)           | Each kid's pending claim           |
| `SHARED_FIRST`      | Chore instance (first completer)    | Each kid's pending claim           |

### Scenario Analysis: SHARED_ALL + Overdue Handling

**Setup**: 3 kids (Sarah, Emma, Olivia) share chore, all must complete

| Scenario                          | What Happens                               |
| --------------------------------- | ------------------------------------------ |
| Due date passes, none completed   | Chore shows overdue for all kids           |
| Due date passes, Sarah completed  | Chore shows overdue for Emma & Olivia only |
| At reset (AT_DUE_DATE_THEN_RESET) | New instance created, all kids start fresh |
| At reset (AT_DUE_DATE)            | Stays overdue until all complete           |

### Scenario Analysis: SHARED_FIRST + Overdue Handling

**Setup**: 3 kids share chore, first to complete marks done for all

| Scenario                          | What Happens                                              |
| --------------------------------- | --------------------------------------------------------- |
| Due date passes, none completed   | Chore shows overdue for all kids (all have opportunity)   |
| Sarah completes while overdue     | All kids marked done (SHARED_FIRST logic), overdue clears |
| At reset (AT_DUE_DATE_THEN_RESET) | New instance, all kids can compete again                  |

### Scenario Analysis: Pending Claims at Reset (SHARED_ALL)

**Setup**: 3 kids share chore, Sarah claimed (pending), Emma & Olivia haven't claimed

| pending_claim_action   | At Reset                                                                               |
| ---------------------- | -------------------------------------------------------------------------------------- |
| `HOLD_PENDING`         | Sarah's claim stays pending, blocks new claims for her. Emma/Olivia get new instance.  |
| `CLEAR_PENDING`        | Sarah's claim dropped, all 3 kids get new instance.                                    |
| `AUTO_APPROVE_PENDING` | Sarah auto-approved, then new instance for all (Sarah already has approval in period). |

### Key Decision: Per-Kid vs Per-Chore Application

- **overdue_handling_type**: Stored at CHORE level, affects all kids assigned
- **approval_reset_pending_claim_action**: Stored at CHORE level, but evaluated PER-KID at reset time

This means: Same chore can have one kid with pending claim that gets auto-approved while another kid just gets fresh instance.

---

## Original Design Questions (Resolved)

The original 7 questions have been simplified into the 2-field design above. Below are the original questions with their resolutions.

---

## Question 1: Reset Timing

**Problem**: When exactly should an overdue chore auto-reset in `AT_DUE_DATE_THEN_RESET` mode?

### ✅ RESOLVED: At Period Boundary (Option A)

Reset when the next approval period starts (respects `approval_reset_type` from Phase 4).

**Rationale**: Reuses Phase 4 period logic, minimal code duplication, intuitive timing.

**Examples**:

- `AT_MIDNIGHT_ONCE` chore → resets at midnight
- `AT_DUE_DATE_ONCE` chore → resets at next chore due date
- `UPON_COMPLETION` chore → never auto-resets (always available)

---

## Question 2: Notification Frequency

**Problem**: If chore stays overdue, how often should we notify?

### ✅ RESOLVED: Notify Once When Becomes Overdue (Option A)

Single notification when due date passes, no additional reminders.

**Rationale**: Non-intrusive, simple logic, respects notification fatigue. Parents can use dashboard to monitor persistent overdue items.

---

## Question 3: Multi-Kid Overdue Behavior

**Problem**: For SHARED_ALL/SHARED_FIRST chores, what happens at reset?

### ✅ RESOLVED: All Kids Get Fresh Instance

At reset time for `AT_DUE_DATE_THEN_RESET`:

- **SHARED_ALL**: All kids get fresh instance regardless of who completed
- **SHARED_FIRST**: All kids get fresh instance, previous completion doesn't carry over

**Rationale**: Simplicity and fairness. Reset means "new cycle starts" for the chore.

---

## Question 4: Overdue State Tracking

**Problem**: Where/how should overdue state be stored?

### ✅ RESOLVED: Calculated Real-Time (Option A)

No new storage fields needed. Overdue state is calculated on-the-fly:

```python
is_overdue = current_date > chore_due_date and not completed
```

**Rationale**: Single source of truth, no sync issues. Dashboard helper can include calculated `is_overdue` and `days_overdue` attributes.

---

## Question 5: Points and Overdue Chores

**Problem**: Should points be adjusted for late completion?

### ✅ RESOLVED: No Penalty/Bonus (Option A)

Full points awarded regardless of completion delay.

**Rationale**: Simple, encourages completion even if late. Parents can use existing penalty/bonus system for manual adjustments if desired.

---

## Question 6: Dashboard Helper Attributes

**Problem**: What dashboard attributes are needed?

### ✅ RESOLVED: 5 Essential Attributes

| Attribute               | Type         | Purpose                                  |
| ----------------------- | ------------ | ---------------------------------------- |
| `is_overdue`            | boolean      | Show overdue indicator                   |
| `days_overdue`          | integer      | How many days past due                   |
| `overdue_handling_type` | string       | Which mode applies                       |
| `next_reset_time`       | ISO datetime | When `AT_DUE_DATE_THEN_RESET` will reset |
| `pending_claim_action`  | string       | What happens to pending claims           |

**Deferred**: `overdue_since` timestamp (can add later if needed)

---

## Question 7: Phase 3 & 4 Interactions

**Problem**: How should overdue handling interact with `completion_criteria` and `approval_reset_type`?

### ✅ RESOLVED: Independent Evaluation Per-Kid

Each field operates independently:

1. **completion_criteria** (Phase 3): Determines if chore is INDEPENDENT, SHARED_ALL, or SHARED_FIRST
2. **approval_reset_type** (Phase 4): Determines when approval periods reset
3. **overdue_handling_type** (Phase 5): Determines if/how chore shows overdue
4. **approval_reset_pending_claim_action** (Phase 5): Determines what happens to pending claims at reset

**Interaction Rules**:

- Overdue status is evaluated AFTER completion_criteria logic runs
- Reset timing follows approval_reset_type boundaries
- Pending claim action is evaluated PER-KID at reset, regardless of completion_criteria mode

---

## Implementation Plan

### Constants to Add (const.py)

```python
# Overdue handling type enum values
OVERDUE_HANDLING_TYPE_AT_DUE_DATE = "at_due_date"
OVERDUE_HANDLING_TYPE_NEVER_OVERDUE = "never_overdue"
OVERDUE_HANDLING_TYPE_AT_DUE_DATE_THEN_RESET = "at_due_date_then_reset"
OVERDUE_HANDLING_TYPE_OPTIONS = [
    OVERDUE_HANDLING_TYPE_AT_DUE_DATE,
    OVERDUE_HANDLING_TYPE_NEVER_OVERDUE,
    OVERDUE_HANDLING_TYPE_AT_DUE_DATE_THEN_RESET,
]
OVERDUE_HANDLING_TYPE_DEFAULT = OVERDUE_HANDLING_TYPE_AT_DUE_DATE

# Pending claim action enum values
PENDING_CLAIM_ACTION_HOLD_PENDING = "hold_pending"
PENDING_CLAIM_ACTION_CLEAR_PENDING = "clear_pending"
PENDING_CLAIM_ACTION_AUTO_APPROVE = "auto_approve_pending"
PENDING_CLAIM_ACTION_OPTIONS = [
    PENDING_CLAIM_ACTION_HOLD_PENDING,
    PENDING_CLAIM_ACTION_CLEAR_PENDING,
    PENDING_CLAIM_ACTION_AUTO_APPROVE,
]
PENDING_CLAIM_ACTION_DEFAULT = PENDING_CLAIM_ACTION_CLEAR_PENDING

# Config keys
CONF_CHORE_OVERDUE_HANDLING_TYPE = "overdue_handling_type"
CONF_CHORE_PENDING_CLAIM_ACTION = "approval_reset_pending_claim_action"

# Data keys (if storing at chore level)
DATA_CHORE_OVERDUE_HANDLING_TYPE = "overdue_handling_type"
DATA_CHORE_PENDING_CLAIM_ACTION = "approval_reset_pending_claim_action"

# Translation keys
TRANS_KEY_OVERDUE_HANDLING_TYPE = "overdue_handling_type"
TRANS_KEY_PENDING_CLAIM_ACTION = "pending_claim_action"
```

### Translations to Add (en.json)

```json
{
  "overdue_handling_type": {
    "at_due_date": "Overdue until complete",
    "never_overdue": "Never overdue",
    "at_due_date_then_reset": "Overdue until complete or next reset"
  },
  "pending_claim_action": {
    "hold_pending": "Hold for parent review",
    "clear_pending": "Clear and start fresh",
    "auto_approve_pending": "Auto-approve at reset"
  }
}
```

### Core Logic Changes (coordinator.py)

1. **`_check_overdue_chores()`**: Respect `overdue_handling_type` when determining overdue status
2. **`_process_approval_period_reset()`**: Handle `approval_reset_pending_claim_action` for pending claims
3. **Dashboard helper**: Add 5 new attributes to `ui_*` output

### UI Changes (flow_helpers.py)

1. Add dropdown for `overdue_handling_type` in chore create/edit flow
2. Add dropdown for `approval_reset_pending_claim_action` in chore create/edit flow
3. Default values populated from constants

### Migration

- Existing chores get `overdue_handling_type = AT_DUE_DATE` (current behavior)
- Existing chores get `approval_reset_pending_claim_action = CLEAR_PENDING` (current behavior)

### Test Scenarios

**Independent Chore Tests**:

1. `AT_DUE_DATE` + due date passes → shows overdue, stays until complete
2. `NEVER_OVERDUE` + due date passes → never shows overdue
3. `AT_DUE_DATE_THEN_RESET` + due date passes → shows overdue, clears at next reset

**Pending Claim Tests**: 4. `HOLD_PENDING` + pending claim at reset → claim persists 5. `CLEAR_PENDING` + pending claim at reset → claim dropped, new instance 6. `AUTO_APPROVE_PENDING` + pending claim at reset → auto-approved, then new instance

**Shared Chore Tests**: 7. `SHARED_ALL` + `AT_DUE_DATE_THEN_RESET` + partial completion → all kids get fresh at reset 8. `SHARED_FIRST` + `AT_DUE_DATE_THEN_RESET` → all kids get fresh at reset 9. `SHARED_ALL` + `HOLD_PENDING` + one kid has pending → that kid's claim held, others get fresh

**Interaction Tests**: 10. `AT_DUE_DATE_THEN_RESET` + `AT_MIDNIGHT_ONCE` → reset at midnight 11. `AT_DUE_DATE_THEN_RESET` + `AT_DUE_DATE_ONCE` → reset at due date 12. `AT_DUE_DATE` + `UPON_COMPLETION` → never auto-resets (always available)

### Estimated Effort

| Component                   | Hours         |
| --------------------------- | ------------- |
| Constants + translations    | 1             |
| Core logic (coordinator.py) | 4             |
| UI fields (flow_helpers.py) | 1.5           |
| Migration                   | 1             |
| Dashboard attributes        | 1.5           |
| Tests (12+ scenarios)       | 3             |
| **Total**                   | **~12 hours** |

---

## Appendix: Original Design Options (For Reference)

The sections below preserve the original design options that were considered before the final decisions above.

---

### Original Question 1 Options: Reset Timing

When reset occurs, what's the new state?

- [ ] **New clean instance**: Both kids get fresh?
- [ ] **Keep completed state**: Sarah stays marked complete?
- [ ] **Hybrid**: Some other approach?

### Recommendation Guidance Questions

For both scenarios above, consider:

1. **Fairness**: What's fair to the kid who completed?
2. **Logic**: Does the reset apply to individuals or to the chore instance?
3. **Simplicity**: Can parents understand the behavior?
4. **User expectation**: What would most families expect?

---

## Question 4: Overdue State Tracking (Storage Approach)

**Problem**: Where/how should overdue state be stored? This affects performance and complexity.

### Option A: Calculated Real-Time (No Storage) ✓ RECOMMENDED

Override `_check_overdue_chores()` to calculate if overdue on-the-fly.

**Approach**:

```python
# No new storage fields needed
is_overdue = current_date > chore_due_date
```

**Pros**:

- ✅ Single source of truth (due date)
- ✅ No sync issues between calculated vs stored state
- ✅ Minimal storage schema changes

**Cons**:

- Slightly slower (must recalculate every check)
- Can't track "overdue since" timestamp without extra field

---

### Option B: Cached in Storage (Per-Kid Tracking)

Add `DATA_KID_CHORE_DATA_IS_OVERDUE` boolean to kid chore data.

**Approach**:

```python
# In coordinator.py
kid_chore_data[DATA_KID_CHORE_DATA_IS_OVERDUE] = True
kid_chore_data[DATA_KID_CHORE_DATA_OVERDUE_SINCE] = datetime.now()
```

**Pros**:

- ✅ Fast state lookups
- ✅ Can track "overdue since" timestamp
- ✅ Efficient for dashboard queries

**Cons**:

- ❌ Must keep in sync with actual due date calculation
- ❌ Risk of stale state if coordinator crashes mid-update

---

### Option C: Hybrid (Calculated + Hourly Cache)

Calculate once per hour, cache result.

**Pros**:

- Good balance of performance vs freshness
- Can provide accurate "overdue since" timestamp

**Cons**:

- Could be 1 hour behind (e.g., just became overdue but cached as not-overdue)
- More complex update logic

---

## Question 5: Points and Overdue Chores

**Problem**: If chore stays overdue for days and then is completed, should points be adjusted?

### Option A: No Penalty/Bonus ✓ RECOMMENDED

Full points awarded regardless of completion delay.

**Pros**:

- ✅ Simple logic
- ✅ Doesn't punish kids for delays
- ✅ Encourages completion even if late

**Cons**:

- No incentive to complete on time
- Parents might want to reward on-time completion

---

### Option B: Penalty for Late Completion

Award fewer points based on days overdue.

**Example**:

- Day 0 (on-time): 10 points
- Day 1 overdue: 8 points
- Day 2 overdue: 5 points
- Day 3+: 2 points

**Pros**:

- ✅ Incentivizes timely completion
- ✅ Teaches consequences for procrastination

**Cons**:

- ❌ Complex calculation
- ❌ Feels punitive
- ❌ May discourage delayed completion

---

### Option C: Configurable Per Chore

New field: "Overdue Points Strategy" (full, penalty, custom).

**Pros**:

- ✅ Maximum parent control

**Cons**:

- ❌ More UI complexity
- ❌ Risk of parent confusion
- ❌ Harder to test/maintain

---

### Option D: Refer to Existing Penalty/Bonus System

Use Phase 2 patterns (penalties/bonuses) for delayed completion.

**Approach**:
Parents apply manual bonus/penalty after seeing overdue completion.

**Pros**:

- ✅ Reuses existing infrastructure
- ✅ Gives parents full control
- ✅ Clear parent intention (explicit bonus/penalty)

**Cons**:

- More work for parents (manual action)
- No automatic incentive

---

## Question 6: Dashboard Helper Integration

**Problem**: What dashboard attributes are needed to display overdue chore information?

### Essential Attributes (Must Choose At Least 5):

- [ ] **`is_overdue`** - Boolean: Is chore past due date?
- [ ] **`days_overdue`** - Integer: How many days past due date?
- [ ] **`overdue_since`** - ISO datetime: When chore first became overdue
- [ ] **`overdue_mode`** - String: HOLD_UNTIL_COMPLETE or RESET_REGARDLESS
- [ ] **`can_reset_now`** - Boolean: For RESET_REGARDLESS, can reset happen now?
- [ ] **`next_reset_time`** - ISO datetime: When will RESET_REGARDLESS auto-reset?
- [ ] **`notification_count`** - Integer: How many overdue notifications sent?

### Optional (Nice-to-Have):

- [ ] **`overdue_reason`** - String: Why is this overdue? (complexity, forgetfulness, etc.)
- [ ] **`completions_while_overdue`** - Integer: How many attempts while overdue?

### Dashboard UI Use Cases

Consider which attributes dashboard needs to:

1. **Display overdue indicator**: (`is_overdue` + optional styling)
2. **Show days late**: (`days_overdue` for parent awareness)
3. **Explain when reset happens**: (`next_reset_time` for RESET_REGARDLESS)
4. **Debug kid behavior**: (`notifications_sent` for parents concerned about notification volume)

---

## Question 7: Interaction with Phases 3 & 4 (Multi-Dimension Scheduling)

**Problem**: How should overdue mode interact with `completion_criteria` (Phase 3) and `approval_reset_type` (Phase 4)?

### Scenario 1: SHARED_FIRST + HOLD_UNTIL_COMPLETE + AT_MIDNIGHT_ONCE

**Setup**:

- Shared chore with 2 kids
- First to complete approves for all
- Can only claim once per day (resets at midnight)

**Timeline**:

- Thu 11 PM: Sarah claims (not approved yet)
- Fri 12:01 AM: Period resets (midnight), Sarah's period start updated
- Fri 1 PM: Sarah gets approved (completed, other kids blocked)
- Fri 11:59 PM: Next period about to start, Emma still hasn't done anything

**Questions**:

- At Fri midnight: Does approval period reset for Emma? (She never claimed)
- Does HOLD_UNTIL_COMPLETE apply to Emma's inability to claim post-Sarah?
- Or does SHARED_FIRST mean Emma is blocked (not overdue, just blocked)?

---

### Scenario 2: INDEPENDENT + RESET_REGARDLESS + AT_DUE_DATE_ONCE

**Setup**:

- Independent chore (each kid has own due date)
- Will auto-reset if overdue (RESET_REGARDLESS)
- Can only claim once per due cycle (resets at due date)

**Timeline**:

- Sarah due Fri, Emma due Sun
- Neither completes
- Fri midnight: What happens?
  - Does Sarah's instance reset? (Her due date passed)
  - Does Emma's stay? (Her due date is Sun)

**Questions**:

- Does RESET_REGARDLESS reset Sarah's? (Yes, her due date passed)
- Does approval_reset_type affect the reset? (AT_DUE_DATE_ONCE - yes, reset happens at due date)
- Are Sarah's approval period and reset period the same? (Both AT_DUE_DATE)

---

### Scenario 3: SHARED_ALL + RESET_REGARDLESS (Both Unfinished)

**Setup**:

- Shared chore (all kids see same instance)
- Will auto-reset if overdue
- 3 kids: Sarah (approved), Emma (not), Olivia (not)

**Timeline**:

- Chore due Friday
- Sarah approved Thu, Emma/Olivia still pending
- Fri midnight: Reset fires

**Questions**:

- What gets reset? The chore instance? Sarah's approval?
- Do all 3 kids get a fresh instance?
- Or only unfinished kids?
- What if only 1 kid had approved - does that approval clear?

---

## Recommendation Request

**Before Phase 5 starts**, please provide answers to:

1. **Question 1**: Which reset timing option? (A/B/C)
2. **Question 2**: Which notification frequency? (A/B/C)
3. **Question 3**: Multi-kid overdue behaviors for both scenarios
4. **Question 4**: Which state tracking approach? (A/B/C)
5. **Question 5**: Points strategy for overdue? (A/B/C/D)
6. **Question 6**: Which dashboard attributes are essential? (minimum 5 selected)
7. **Question 7**: For each scenario, what should happen at reset time?

---

## Implementation Prerequisites

Once answers are confirmed, implement in this order:

1. **Update const.py** with decisions (new constants as needed)
2. **Design test scenarios** based on answers (edge cases from Q3 & Q7)
3. **Implement core logic** in coordinator.py
4. **Add UI field** to flow_helpers.py
5. **Implement notifications** for overdue/reset events
6. **Add dashboard attributes** per Q6 selections
7. **Comprehensive testing** covering all interaction scenarios (Q7)

---

**Next Step**: Gather answers to all 7 questions before Phase 5 begins.
