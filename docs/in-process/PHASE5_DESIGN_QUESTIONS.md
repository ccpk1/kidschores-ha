# Phase 5 (Overdue Handling) – Critical Design Questions

**Objective**: Answer all 7 design questions before implementation begins.

**Target Response Date**: Before Phase 5 implementation starts

---

## Question 1: RESET_REGARDLESS Auto-Reset Timing

**Problem**: When exactly should an overdue chore auto-reset in RESET_REGARDLESS mode?

### Option A: At Period Boundary (Approval-Reset-Aware) ✓ RECOMMENDED

Reset when the next approval period starts (respects `approval_reset_type` from Phase 4).

**Examples**:

- `AT_MIDNIGHT_ONCE` chore → resets at midnight
- `AT_DUE_DATE_ONCE` chore → resets at next chore due date
- `UPON_COMPLETION` chore → never resets (always available)

**Pros**:

- ✅ Consistent with approval reset logic
- ✅ Minimal code duplication (reuses Phase 4 period logic)
- ✅ Intuitive: reset happens at same time as new claims become available

**Cons**:

- More complex implementation
- Requires understanding Phase 4 approval_reset_type

**Implementation Pattern**:

```python
# In _check_overdue_chores():
if chore_overdue_option == RESET_REGARDLESS:
    # Check if we're at period boundary for this chore's approval_reset_type
    period_start = self._get_approval_period_start(chore, kid)
    if self._is_at_period_boundary(period_start, chore.approval_reset_type):
        # Reset the chore
        self._reset_overdue_chore(kid, chore)
```

---

### Option B: At Chore-Level Due Date

Reset when the chore's configured due date passes (ignore `approval_reset_type`).

**Example**:

- All kids reset at same time regardless of approval_reset_type
- Simpler: single "next due date" calculation

**Pros**:

- ✅ Simple to understand/implement
- ✅ Clear reset point (chore due date)

**Cons**:

- ❌ Duplicates logic with approval_reset_type
- ❌ May feel counterintuitive (different reset times for claims vs reset)
- ❌ Forces parents to understand 2 separate timing concepts

---

### Option C: At Recurring Frequency Boundary

New field for "reset frequency" (daily, weekly, custom) separate from both `approval_reset_type` and chore due_date.

**Pros**:

- ✅ Maximum flexibility
- ✅ Independent control of when resets happen

**Cons**:

- ❌ Most complex
- ❌ Adds 3rd dimension to chore scheduling (due_date, approval_reset_type, overdue_reset_frequency)
- ❌ User confusion: "What's the difference between these 3 times?"

---

## Question 2: HOLD_UNTIL_COMPLETE Notification Frequency

**Problem**: If chore is held overdue for days, how often should we notify the kid?

### Option A: Notify Once When Becomes Overdue ✓ RECOMMENDED

Single notification when due date passes, no additional reminders.

**Pros**:

- ✅ Non-intrusive
- ✅ Simple notification logic
- ✅ Respects notification fatigue concerns

**Cons**:

- Kid might forget about it after 3 days

---

### Option B: Daily Reminders While Overdue

Notification each morning showing overdue status, stopped once kid completes.

**Pros**:

- ✅ Keeps chore visible
- ✅ Prevents "I forgot it was overdue"

**Cons**:

- ❌ More notifications = potential fatigue
- ❌ More complex logic

---

### Option C: Escalating Reminders

Progressive increase in notification frequency as chore stays overdue longer.

**Example**:

- Days 1-3 overdue: Morning notification only
- Days 4-7 overdue: Morning + evening
- Days 8+ overdue: Morning + midday + evening

**Pros**:

- ✅ Gradually increases visibility for persistent issues
- ✅ Reasonable for long-term overdue

**Cons**:

- ❌ Complex logic (hard to test/maintain)
- ❌ Hard to explain to users

---

## Question 3: Multi-Kid Overdue Behavior (Scenarios)

**Problem**: For SHARED_ALL/SHARED_FIRST chores, if one kid completes but another doesn't, what happens during reset?

### Scenario A: SHARED_ALL + RESET_REGARDLESS (2 kids: Sarah ✓, Emma ✗)

At reset time, when should the reset affect:

- [ ] **Both kids**: They get a fresh instance?
- [ ] **Only uncompleted kids**: Emma gets reset, Sarah doesn't?
- [ ] **No one**: Both kids keep current status?

### Scenario B: SHARED_FIRST + RESET_REGARDLESS (Sarah ✓, Emma unassigned)

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
