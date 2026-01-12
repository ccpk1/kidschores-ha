# Disapproval Button "Undo" Feature Investigation

**Date**: January 12, 2026
**Status**: Investigation Complete
**Feature**: Kid-initiated "undo" vs parent/admin disapproval

---

## Current Behavior

### Disapproval Flow (Chores & Rewards)

1. **Authorization Check** (services.py):
   - Function: `is_user_authorized_for_global_action()` in `kc_helpers.py`
   - Currently allows: **Admin users** OR **registered parents** (via `DATA_PARENT_HA_USER_ID`)
   - Currently blocks: **Kids** (even if they have `DATA_KID_HA_USER_ID` linked)

2. **Disapprove Chore** (`coordinator.py:2856`):
   - Decrements `pending_claim_count` by 1
   - Resets state to `PENDING` via `_process_chore_state()`
   - Tracks disapproval stats in `_update_chore_data_for_kid()` (line 3850-3873):
     - `last_disapproved` → timestamp (ISO)
     - `period_disapproved` → increments daily/weekly/monthly/yearly counters
     - `disapproved_all_time` → lifetime total
   - Sends notification to kid (if `notify_on_disapproval` enabled)

3. **Disapprove Reward** (`coordinator.py:4865`):
   - Decrements `pending_count` by 1
   - Updates tracking:
     - `last_disapproved` → timestamp
     - `total_disapproved` → +1
     - `period_disapproved` → increments via `_increment_reward_period_counter()`
   - Sends notification to kid

### Stat Tracking Logic

**Chores** (in `_update_chore_data_for_kid()`, lines 3850-3873):
```python
# Triggered when state changes from CLAIMED → PENDING
if state == const.CHORE_STATE_PENDING and previous_state == const.CHORE_STATE_CLAIMED:
    kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = now_iso
    # Only increments if first disapproval TODAY for this chore
    if first_disapproved_today:
        daily_data[const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED] = 1
        update_periods({const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 1})
        inc_stat(const.DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME, 1)
```

**Rewards** (in `disapprove_reward()`, lines 4865-4915):
```python
reward_entry[const.DATA_KID_REWARD_DATA_LAST_DISAPPROVED] = dt_util.utcnow().isoformat()
reward_entry[const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED] = (
    reward_entry.get(const.DATA_KID_REWARD_DATA_TOTAL_DISAPPROVED, 0) + 1
)
self._increment_reward_period_counter(
    reward_entry, const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED
)
```

---

## Proposed "Undo" Feature

### Requirements

When a **kid user** clicks the disapproval button:
- **Same effect**: Remove the claim (reset to pending/unclaimed state)
- **Different tracking**: Do NOT increment disapproval stats
- **Different notification**: Optional - use different message or skip notification

### Implementation Strategy

#### Option A: Separate Service (Recommended)

Create new services: `undo_chore_claim` and `undo_reward_claim`

**Pros:**
- Clear separation of concerns
- Easier to audit and test
- Dashboard can conditionally show "Undo" or "Disapprove" button based on user
- Service names clearly communicate intent

**Cons:**
- Requires dashboard changes to use new button entity IDs
- More entities/services to maintain

#### Option B: Conditional Logic in Existing Services

Modify `handle_disapprove_chore()` and `handle_disapprove_reward()` to detect kid users

**Pros:**
- No dashboard changes needed
- Reuses existing button entities
- Simpler from user configuration perspective

**Cons:**
- Mixed responsibilities in one service
- Harder to test and reason about
- Logs/audit trail less clear

---

## Recommended Implementation (Option A)

### 1. New Services

**Service Names:**
- `kidschores.undo_chore_claim`
- `kidschores.undo_reward_claim`

**Schemas:**
```python
UNDO_CHORE_CLAIM_SCHEMA = vol.Schema({
    vol.Required(const.FIELD_KID_NAME): cv.string,
    vol.Required(const.FIELD_CHORE_NAME): cv.string,
})

UNDO_REWARD_CLAIM_SCHEMA = vol.Schema({
    vol.Required(const.FIELD_KID_NAME): cv.string,
    vol.Required(const.FIELD_REWARD_NAME): cv.string,
})
```

### 2. Authorization

**New helper function** in `kc_helpers.py`:
```python
async def is_user_authorized_for_kid_undo(
    hass: HomeAssistant,
    user_id: str,
    kid_id: str,
) -> bool:
    """Check if user is authorized to undo their own claim.

    Authorization rules:
      - Admin users => authorized
      - Registered parents => authorized
      - Kid with matching ha_user_id => authorized
      - Everyone else => not authorized
    """
    # Similar to is_user_authorized_for_kid but explicitly allows kid users
```

### 3. New Coordinator Methods

**For chores** (`coordinator.py`):
```python
def undo_chore_claim(self, kid_id: str, chore_id: str):
    """Undo a chore claim without tracking as disapproval.

    Similar to disapprove_chore but:
    - Does NOT update last_disapproved timestamp
    - Does NOT increment disapproval stats
    - Uses different notification (or skips notification)
    """
    # Validation (same as disapprove_chore)

    # Decrement pending_count (same)

    # Reset to PENDING via _process_chore_state (same)
    # BUT: _process_chore_state will still trigger stat tracking
    # Solution: Add skip_stats parameter to _process_chore_state

    # Send "claim removed" notification instead of "disapproved"
```

**For rewards** (`coordinator.py`):
```python
def undo_reward_claim(self, kid_id: str, reward_id: str):
    """Undo a reward claim without tracking as disapproval."""
    # Similar pattern
```

### 4. Modify `_process_chore_state()`

Add parameter to skip stat tracking:
```python
def _process_chore_state(
    self,
    kid_id: str,
    chore_id: str,
    new_state: str,
    *,
    points_awarded: float | None = None,
    reset_approval_period: bool = False,
    skip_disapproval_stats: bool = False,  # NEW
) -> None:
```

In the disapproval tracking section (line 3850-3873):
```python
elif (
    state == const.CHORE_STATE_PENDING
    and previous_state == const.CHORE_STATE_CLAIMED
):
    if not skip_disapproval_stats:  # NEW CONDITION
        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = now_iso
        # ... rest of stat tracking
```

### 5. Button Entities

**New button types** (in `button.py`):
- `UndoChoreButton` (kid-only accessible)
- `UndoRewardButton` (kid-only accessible)

Or alternatively, use dynamic authorization in existing button press handlers.

### 6. Translation Keys

**New constants** (in `const.py`):
```python
# Services
SERVICE_UNDO_CHORE_CLAIM: Final = "undo_chore_claim"
SERVICE_UNDO_REWARD_CLAIM: Final = "undo_reward_claim"

# Translations
TRANS_KEY_NOTIF_TITLE_CHORE_UNDO: Final = "notif_title_chore_undo"
TRANS_KEY_NOTIF_MESSAGE_CHORE_UNDO: Final = "notif_message_chore_undo"
TRANS_KEY_NOTIF_TITLE_REWARD_UNDO: Final = "notif_title_reward_undo"
TRANS_KEY_NOTIF_MESSAGE_REWARD_UNDO: Final = "notif_message_reward_undo"
```

**New strings** (in `translations/en.json`):
```json
{
  "services": {
    "undo_chore_claim": {
      "name": "Undo chore claim",
      "description": "Remove a chore claim without tracking as disapproval"
    },
    "undo_reward_claim": {
      "name": "Undo reward claim",
      "description": "Remove a reward claim without tracking as disapproval"
    }
  },
  "notifications": {
    "chore_undo_title": "Chore claim removed",
    "chore_undo_message": "Your claim for {chore_name} has been removed",
    "reward_undo_title": "Reward claim removed",
    "reward_undo_message": "Your claim for {reward_name} has been removed"
  }
}
```

---

## Testing Requirements

### Unit Tests
- `test_undo_chore_claim_basic` - Kid unclaims chore, stats unchanged
- `test_undo_chore_claim_authorization` - Verify kid/parent/admin access
- `test_undo_chore_claim_shared_first` - Verify correct behavior for shared chores
- `test_undo_reward_claim_basic` - Kid unclaims reward, stats unchanged
- `test_disapproval_stats_unchanged_on_undo` - Verify no stat increments

### Integration Tests
- Verify button entities work correctly
- Test notification content
- Verify dashboard behavior (if modified)

---

## Alternative: Option B Implementation

If we go with conditional logic in existing services:

**Modify authorization check** in `handle_disapprove_chore()`:
```python
# Check authorization
user_id = call.context.user_id
is_kid_undo = False

if user_id:
    # Check if user is a kid for this chore
    coordinator = ...
    kid_info = coordinator.kids_data.get(kid_id)
    if kid_info and kid_info.get(const.DATA_KID_HA_USER_ID) == user_id:
        is_kid_undo = True
    elif not await kh.is_user_authorized_for_global_action(...):
        raise HomeAssistantError(...)

# Call appropriate method
if is_kid_undo:
    coordinator.undo_chore_claim(kid_id=kid_id, chore_id=chore_id)
else:
    coordinator.disapprove_chore(parent_name=parent_name, kid_id=kid_id, chore_id=chore_id)
```

**Cons of this approach:**
- `parent_name` field becomes optional/meaningless for kid-initiated undo
- Harder to distinguish in logs
- Tests become more complex

---

## Recommendation

**Go with Option A** - separate services for clarity and maintainability:

1. Create `undo_chore_claim` and `undo_reward_claim` services
2. Add `skip_disapproval_stats` parameter to `_process_chore_state()`
3. Create coordinator methods that use this flag
4. Add authorization helper for kid-initiated actions
5. Update button entities or add new ones for "undo" action
6. Dashboard modifications can conditionally show appropriate button

**Estimated Effort:**
- Core implementation: 4-6 hours
- Testing: 3-4 hours
- Documentation: 1-2 hours
- Dashboard updates (if needed): 2-3 hours

**Total:** ~10-15 hours

---

---

## Additional Analysis: Kid Access & Same-Day Undo

### Question 1: Should parameter be `skip_stats` instead of `skip_disapproval_stats`?

**Answer: YES** ✅

**Rationale:**
- More flexible naming for future use cases
- Could apply to other stat-skipping scenarios (e.g., admin corrections, bulk operations)
- Still clear in context when passed as `skip_stats=True`
- Follows Python naming convention for boolean flags

**Recommendation:** Use `skip_stats` parameter

---

### Question 2: Are services necessary if users only interact via buttons?

**Current Architecture:**
- **Buttons** (in `button.py`) call **coordinator methods directly**
- **Services** (in `services.py`) ALSO call **same coordinator methods**
- Services are registered in `async_setup_services()` for automation/script access

**Button Example** (`ParentChoreDisapproveButton.async_press()`, line 600):
```python
self.coordinator.disapprove_chore(
    parent_name=parent_name,
    kid_id=self._kid_id,
    chore_id=self._chore_id,
)
```

**Service Example** (`handle_disapprove_chore()`, line 290):
```python
coordinator.disapprove_chore(
    parent_name=parent_name,
    kid_id=kid_id,
    chore_id=chore_id,
)
```

**Answer: Services are OPTIONAL for button-only features**

**Pros of adding services:**
- Consistency with existing pattern
- Enables automation/script access
- Testable via service calls
- Developer Tools → Services UI testing
- Future-proofing

**Cons of adding services:**
- More code to maintain
- 2 registration points (button + service)
- Duplicated authorization checks
- If users only need buttons, services add complexity

**Recommendation for "Undo" feature:**
- **SKIP services initially** - implement button-only
- Buttons call new coordinator methods directly: `undo_chore_claim()`, `undo_reward_claim()`
- Add services later if automation access is requested
- Reduces initial implementation scope by ~30%

**Revised Effort Estimate (Button-only):**
- Core coordinator methods: 3-4 hours
- Button authorization logic: 2-3 hours
- Testing: 2-3 hours
- **Total: ~7-10 hours** (vs 10-15 with services)

---

### Question 3: Allowing Kids to Use Disapproval Button

**Current State:**
- Authorization: `is_user_authorized_for_global_action()` → **blocks kids**
- Only allows: Admin OR registered parents

**To Allow Kid Access:**

#### Implementation Approach

**Option 1: New Authorization Helper (Recommended)**
```python
async def is_user_authorized_for_undo(
    hass: HomeAssistant,
    user_id: str,
    kid_id: str,
) -> bool:
    """Check if user can undo claim for this kid.

    - Admin users => authorized
    - Registered parents => authorized
    - Kid with matching ha_user_id => authorized
    - Everyone else => not authorized
    """
    # Check admin/parent (existing logic)
    if await is_user_authorized_for_global_action(...):
        return True

    # NEW: Check if user is the kid
    user = await hass.auth.async_get_user(user_id)
    coordinator = _get_kidschores_coordinator(hass)
    kid_info = coordinator.kids_data.get(kid_id)

    if kid_info and kid_info.get(const.DATA_KID_HA_USER_ID) == user.id:
        return True

    return False
```

**Option 2: Modify Button Authorization** (Simpler)
```python
# In ParentChoreDisapproveButton.async_press()
user_id = self._context.user_id if self._context else None

# Check if user is the kid for this chore
is_kid = False
if user_id:
    user_obj = await self.hass.auth.async_get_user(user_id)
    kid_info = self.coordinator.kids_data.get(self._kid_id)
    if kid_info and kid_info.get(const.DATA_KID_HA_USER_ID) == user_id:
        is_kid = True

# If not kid, check parent/admin authorization
if not is_kid:
    if not await kh.is_user_authorized_for_global_action(...):
        raise HomeAssistantError(...)

# Call appropriate method
if is_kid:
    self.coordinator.undo_chore_claim(kid_id=self._kid_id, chore_id=self._chore_id)
else:
    self.coordinator.disapprove_chore(
        parent_name=parent_name,
        kid_id=self._kid_id,
        chore_id=self._chore_id,
    )
```

**Impact Assessment:**

| Area | Change Required | Complexity |
|------|----------------|------------|
| Authorization | Add kid check in button | LOW - simple ID comparison |
| Coordinator | Add `undo_chore_claim()` method | LOW - similar to disapprove |
| Button Logic | Conditional method call | LOW - if/else switch |
| Notifications | Different message for undo | LOW - new translation keys |
| Testing | Test kid vs parent behavior | MEDIUM - 2 paths to test |

**Effort Estimate:**
- Authorization logic: 1 hour
- Conditional button logic: 1 hour
- Testing: 2 hours
- **Total: ~4 hours**

**Risks:**
- Kids could abuse "undo" to avoid disapproval counts
- Parents might want to disable kid undo access (requires config option)
- UI confusion if button text doesn't change based on user

**Recommendation:**
- ✅ **LOW RISK - Implement with Option 2** (conditional in button)
- Add config option later if needed: `allow_kid_undo` (default: true)
- Button already shows correct authorization error if blocked

---

### Question 4: Undo Approval on Same Day

**User Request:** Allow removing a chore that was approved the same day

**Current Approval Flow** (`approve_chore()`, lines 2589-2855):

1. **State Change:** CLAIMED → APPROVED via `_process_chore_state()`
2. **Points Award:** Add points to kid's balance (`update_kid_points()`)
3. **Stats Tracking:** (in `_update_chore_data_for_kid()`, lines 3750-3780)
   - `last_approved` → timestamp
   - Period counters (daily/weekly/monthly/yearly) → +1
   - `approved_all_time` → +1
   - `total_points_from_chores_all_time` → +points
4. **Streak Calculation:** Update daily/all-time streaks
5. **Badge/Challenge Progress:** Increment counts
6. **Achievements:** Update streak-based achievements
7. **Due Date Rescheduling:** (INDEPENDENT + UPON_COMPLETION only)
8. **Notification:** Send approval notification to kid

**What "Undo Approval" Would Require:**

#### Reversals Needed

| System | Reversal Action | Complexity | Risk |
|--------|----------------|------------|------|
| **State** | APPROVED → CLAIMED | LOW | Safe - straightforward |
| **Points** | Deduct awarded points | MEDIUM | Kid might have spent points already |
| **Stats** | Decrement period counters | MEDIUM | Only safe if "first approval today" |
| **Streak** | Recalculate yesterday's streak | HIGH | Complex multi-day logic |
| **Badges** | Reverse progress increments | HIGH | Multiple badge types, cycle tracking |
| **Challenges** | Decrement challenge counts | MEDIUM | Daily min vs total window |
| **Achievements** | Reverse streak progress | HIGH | State-based, multiple kids |
| **Due Date** | Un-reschedule next occurrence | MEDIUM | Only UPON_COMPLETION chores |
| **Notifications** | Send "approval removed" notification | LOW | Simple |

#### Critical Issues

**1. Points Balance Problem**
```
Scenario:
- Kid gets 10 points for chore approval
- Kid immediately spends 8 points on reward
- Parent tries to undo approval (needs to deduct 10 points)
- Kid now has negative balance (-6 points)

Solution: Check if kid has sufficient points before allowing undo
```

**2. Streak Calculation Dependency**
```
Current: Today's streak = yesterday's streak + 1
Problem: If undo approval from yesterday, today's streak is now WRONG
Solution: Must recalculate ALL streaks from undo date forward (EXPENSIVE)
```

**3. Badge Progress Interdependency**
```
Example: Daily target badge (complete 3 chores per day)
- Kid completes 3 chores, badge awarded
- Parent undoes 1 approval
- Badge was already awarded - do we revoke it?
- If badge triggered point bonus, do we reverse that too?

Solution: Block undo if badge was awarded based on that approval
```

**4. Challenge Window Boundaries**
```
Challenge Type: "Complete 10 chores within 7 days"
- Kid completes 10th chore, challenge complete, reward given
- Parent undoes 1 chore - now only 9 complete
- Challenge is ALREADY marked complete - reversal cascade

Solution: Block undo if challenge completion depends on that approval
```

#### Implementation Complexity Analysis

**Easy Parts** (20% of work):
- State change: APPROVED → CLAIMED
- Simple notification
- Authorization check (same day only)

**Medium Parts** (30% of work):
- Points deduction with balance check
- Basic stat decrement (daily/weekly/monthly)
- Due date un-rescheduling

**Hard Parts** (50% of work):
- Streak recalculation cascades
- Badge progress reversal logic
- Challenge dependency detection
- All-time stat corrections
- Achievement state rollback

**Estimated Implementation Effort:**
- Core reversal logic: 8-12 hours
- Dependency detection: 6-8 hours
- Cascade prevention: 4-6 hours
- Testing (multiple scenarios): 8-10 hours
- Edge case handling: 4-6 hours
- **Total: ~30-42 hours**

**Comparison:**
- Basic "undo claim" (disapproval): ~7-10 hours
- "Undo approval same day": ~30-42 hours
- **4x more complex**

#### Recommendation: **DO NOT IMPLEMENT** ❌

**Reasons:**
1. **High Complexity:** Reversal cascades affect 8+ subsystems
2. **Data Integrity Risk:** Streak/badge/challenge state corruption
3. **Edge Cases:** Insufficient points, already-awarded badges, completed challenges
4. **User Confusion:** What gets reversed? What stays? Not intuitive.
5. **Testing Burden:** Exponential combinations of states
6. **Maintenance Cost:** Every new gamification feature adds reversal logic

**Alternative Solutions:**

**Option A: Admin Override (Simpler)**
- Add admin-only service: `adjust_chore_approval(kid_id, chore_id, points_delta)`
- Allows manual correction without full reversal
- Logs correction reason for audit trail
- Effort: ~5-8 hours

**Option B: Time-Limited Undo Window**
- Allow undo only within 5 minutes of approval (before kid sees notification)
- Block if kid has claimed/spent points since approval
- Simpler dependency checks
- Effort: ~15-20 hours (still significant)

**Option C: "Mark as Error" Flag**
- Don't reverse stats, just flag approval as erroneous
- Exclude from future stat calculations
- Preserves data integrity, allows audit
- Effort: ~10-12 hours

---

## Final Recommendations

### Implement (Priority Order)

1. **Kid "Undo Claim" via Disapproval Button** ✅
   - Effort: ~7-10 hours (button-only, no services)
   - Risk: LOW
   - Value: HIGH (common use case)
   - Implementation: Conditional button logic with `skip_stats=True`

2. **Rename Parameter to `skip_stats`** ✅
   - Effort: 15 minutes (just naming)
   - Risk: NONE
   - Value: Future flexibility

### Skip

3. **Undo Approval Same Day** ❌
   - Effort: ~30-42 hours
   - Risk: HIGH (data integrity, cascading effects)
   - Value: UNCERTAIN (rare use case?)
   - Alternative: Admin correction service (5-8 hours)

---

## Next Steps

1. ✅ Confirm: Implement kid "undo claim" with `skip_stats` parameter (button-only)
2. ✅ Confirm: Skip "undo approval" feature (or go with admin override alternative)
3. Create implementation plan for kid undo feature
4. Begin coding with button authorization changes first

