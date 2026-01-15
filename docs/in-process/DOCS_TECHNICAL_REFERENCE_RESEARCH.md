# Technical Reference Documentation - Research & Planning

**Purpose**: Document actual entities, states, and attributes from codebase for Technical Reference Guide
**Status**: Research Phase - Awaiting User Approval
**Target Doc**: Chore-Technical-Reference.md

---

## Modern Sensors (Default - Dense Attributes)

### Per-Kid Modern Sensors

#### 1. KidChoreStatusSensor (`sensor.kc_<kid>_<chore>`)

**File**: sensor.py:424-750
**State Values** (verified from code):

- `pending` - Available for claim
- `claimed` - Kid has claimed, awaiting approval
- `approved` - Parent approved, points awarded
- `overdue` - Past due date, no claims
- `completed_by_other` - SHARED chore completed by another kid

**Key Attributes** (verified from extra_state_attributes):

- Configuration: `default_points`, `completion_criteria`, `approval_reset_type`, `recurring_frequency`, `applicable_days`, `due_date`
- Statistics: `chore_points_earned`, `chore_approvals_count`, `chore_claims_count`, `chore_disapproved_count`, `chore_overdue_count`
- Streaks: `chore_current_streak`, `chore_highest_streak`, `chore_last_longest_streak_date`
- Timestamps: `last_claimed`, `last_approved`, `last_disapproved`, `last_overdue`
- State: `global_state` (for SHARED chores), `claimed_by`, `completed_by`, `approval_period_start`
- UI Integration: `chore_approve_button_entity_id`, `chore_disapprove_button_entity_id`, `chore_claim_button_entity_id`
- Can Actions: `can_claim`, `can_approve`
- Today's Count: `chore_approvals_today` (if multi-approval reset type)

#### 2. KidPointsSensor (`sensor.kc_<kid>_points`)

**File**: sensor.py:724-843
**State**: Total points balance (int)
**Attributes** (need to verify full list):

- Points tracking: earnings, spending, bonuses, penalties
- (Need to read full attributes section)

#### 3. KidChoresSensor (`sensor.kc_<kid>_chores`)

**File**: sensor.py:844-919
**State**: Total chores completed all-time (int)
**Attributes**:

- All `DATA_KID_CHORE_STATS` fields prefixed with `chore_stat_`
- Stats include: approved_all_time, claimed, overdue counts, etc.
- (Need to find full list of chore stats keys)

#### 4. KidBadgesSensor (`sensor.kc_<kid>_badges`)

**File**: sensor.py:920-1050
**State**: Highest cumulative badge name (str)
**Icon**: Dynamic based on highest badge
**Attributes**:

- Badge progression: current, highest earned, next higher/lower
- Maintenance: baseline points, cycle points, grace_end_date
- Points to next badge
- (Need to read full attributes section)

#### 5-9. Other Modern Sensors (Need to Research):

- KidBadgeProgressSensor
- KidRewardStatusSensor
- KidAchievementProgressSensor
- KidChallengeProgressSensor
- KidDashboardHelperSensor

### System-Level Modern Sensors

#### 10-13. System Sensors (Need to Research):

- SystemBadgeSensor
- SystemChoreSharedStateSensor
- SystemAchievementSensor
- SystemChallengeSensor

---

## Extra Sensors (Legacy - Optional, Disabled by Default)

**Enabled by**: `CONF_SHOW_LEGACY_ENTITIES` option
**User-Facing Term**: "Extra Sensors" (not "Legacy")
**Purpose**: Separate entities for metrics that exist as attributes in modern sensors

### Pending Approval Sensors (2)

1. SystemChoresPendingApprovalSensor
2. SystemRewardsPendingApprovalSensor

### System Chore Approval Sensors (4)

1. SystemChoreApprovalsSensor - Total chores completed
2. SystemChoreApprovalsDailySensor - Daily completions
3. SystemChoreApprovalsWeeklySensor - Weekly completions
4. SystemChoreApprovalsMonthlySensor - Monthly completions

**Data Also Available In**: KidChoresSensor attributes

### Kid Points Earned Sensors (4)

1. KidPointsEarnedDailySensor
2. KidPointsEarnedWeeklySensor
3. KidPointsEarnedMonthlySensor
4. KidPointsMaxEverSensor

**Data Also Available In**: KidPointsSensor attributes

### Streak Sensor (1)

1. KidChoreStreakSensor

**Data Also Available In**: KidChoresSensor attributes

### Bonus/Penalty Sensors (2 per bonus/penalty)

1. KidPenaltyAppliedSensor (one per penalty, per kid)
2. KidBonusAppliedSensor (one per bonus, per kid)

**Data Also Available In**: KidDashboardHelperSensor attributes

---

## Button Entities

### Per-Chore Buttons (Need to Research)

**File**: button.py:1-150

From code comments:

- Chore Buttons (Claim & Approve) with user-defined or default icons
- Reward Buttons
- Penalty Buttons
- Bonus Buttons
- ParentPointsAdjustButton
- ParentRewardApproveButton

Need to verify:

- Exact entity naming: `button.kc_<kid>_<chore>_claim`?
- Button states (timestamp of last press?)
- Attributes available

---

## Questions for User

1. **Scope**: Should technical reference cover:

   - Chores only?
   - Or all entities (rewards, bonuses, penalties, achievements, challenges, badges)?

2. **Detail Level**: For each entity type, document:

   - Entity naming pattern?
   - State values?
   - Full attribute list?
   - Jinja access examples?

3. **Extra Sensors**: How to present?

   - Separate section "Extra Sensors (Optional)"?
   - Show which modern sensor contains the same data?

4. **Jinja Examples**: What level of complexity?

   - Basic state access?
   - Attribute access?
   - Nested JSON (chore lists)?
   - Conditional logic?
   - Dashboard card examples?

5. **Global State Mapping**:
   - I saw `global_state` attribute - is this for SHARED chores only?
   - What are all possible global_state values?
   - Where is this defined in code?

---

## Next Steps

1. **User Feedback**: Review this research plan
2. **Complete Research**: Read remaining sensor classes and button.py
3. **Verify All States**: Find where state constants are defined (const.py)
4. **Map Attributes**: Create complete attribute list for each sensor
5. **Build Examples**: Test Jinja templates for accuracy
6. **Draft Document**: Only after all above verified

**No guessing. No assumptions. Everything verified from code.**
