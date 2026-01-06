# Entity Translation Audit Report

## Current Entity Platform Analysis

### Supported Platforms (from `const.PLATFORMS`)

- **Button**: `Platform.BUTTON`
- **Calendar**: `Platform.CALENDAR`
- **Datetime**: `Platform.DATETIME`
- **Select**: `Platform.SELECT`
- **Sensor**: `Platform.SENSOR`

### Current Entity Types with Translation Keys

#### 🟢 Sensor Entities (have translation keys)

1. `KidChoreStatusSensor` → `chore_status_sensor` ✅
2. `KidPointsSensor` → `kid_points_sensor` ✅
3. `KidChoresSensor` → `chores_sensor` ✅
4. `KidBadgesSensor` → `kids_badges_sensor` ✅
5. `KidBadgeProgressSensor` → `badge_progress_sensor` ✅
6. `SystemBadgeSensor` → `badge_sensor` ✅
7. `SystemChoreSharedStateSensor` → `shared_chore_global_status_sensor` ✅
8. `KidRewardStatusSensor` → `reward_status_sensor` ✅
9. `SystemAchievementSensor` → `achievement_state_sensor` ✅
10. `SystemChallengeSensor` → `challenge_state_sensor` ✅
11. `KidAchievementProgressSensor` → `achievement_progress_sensor` ✅
12. `KidChallengeProgressSensor` → `challenge_progress_sensor` ✅
13. `KidDashboardHelperSensor` → `dashboard_helper_sensor` ✅

#### 🟢 Button Entities (have translation keys)

1. `KidChoreClaimButton` → `claim_chore_button` ✅
2. `ParentChoreApproveButton` → `approve_chore_button` ✅
3. `ParentChoreDisapproveButton` → `disapprove_chore_button` ✅
4. `KidRewardRedeemButton` → `claim_reward_button` ✅
5. `ParentRewardApproveButton` → `approve_reward_button` ✅
6. `ParentRewardDisapproveButton` → `disapprove_reward_button` ✅
7. `ParentPenaltyApplyButton` → `penalty_button` ✅
8. `ParentPointsAdjustButton` → `manual_adjustment_button` ✅
9. `ParentBonusApplyButton` → `bonus_button` ✅

#### 🟢 Select Entities (have translation keys)

1. `SystemChoresSelect` → `select_base` ✅
2. `SystemChoresForKidSelect` → `chores_sensor` ✅
3. `SystemRewardsSelect` → `rewards` ✅
4. `SystemPenaltiesSelect` → `penalties` ✅
5. `SystemBonusesSelect` → `bonuses` ✅
6. `KidChoresSelect` → `chores_kid` ✅

#### 🟢 Calendar Entity (has translation key)

1. `KidsChoresCalendar` → `calendar` ✅

#### 🟢 Datetime Entity (has translation key)

1. `ChoresDueDateTimeEntity` → `date_helper` ✅

## Missing Entity Translations Analysis

### ❌ Missing Sensor Translations in en.json

Looking at sensor constants vs. actual en.json entries:

#### **Missing from en.json:**

1. `badge_progress_sensor` (KidBadgeProgressSensor)
2. `dashboard_helper_sensor` (KidDashboardHelperSensor)
3. `chores_completed_daily_sensor` (not found in sensor.py - possible legacy)
4. `chores_completed_monthly_sensor` (not found in sensor.py - possible legacy)
5. `chores_completed_total_sensor` (not found in sensor.py - possible legacy)
6. `chores_completed_weekly_sensor` (not found in sensor.py - possible legacy)
7. `kid_chores_highest_streak_sensor` (not found in sensor.py - possible legacy)
8. `kid_max_points_ever_sensor` (not found in sensor.py - possible legacy)
9. `kid_points_earned_daily_sensor` (not found in sensor.py - possible legacy)
10. `kid_points_earned_monthly_sensor` (not found in sensor.py - possible legacy)
11. `kid_points_earned_weekly_sensor` (not found in sensor.py - possible legacy)
12. `bonus_applies_sensor` (not found in sensor.py - possible legacy)
13. `penalty_applies_sensor` (not found in sensor.py - possible legacy)
14. `pending_chores_approvals_sensor` (not found in sensor.py - possible legacy)
15. `pending_rewards_approvals_sensor` (not found in sensor.py - possible legacy)

### ❌ Missing Button Translations in en.json

All button translation keys exist in en.json - **No missing button translations**.

### ❌ Missing Select Translations in en.json

Need to verify these constants exist in const.py and match en.json:

1. `TRANS_KEY_SELECT_BASE` = `select_base` - **MISSING from en.json**
2. `TRANS_KEY_SELECT_CHORES` = `chores` - **EXISTS in en.json**
3. `TRANS_KEY_SELECT_REWARDS` = `rewards` - **MISSING from en.json**
4. `TRANS_KEY_SELECT_PENALTIES` = `penalties` - **MISSING from en.json**
5. `TRANS_KEY_SELECT_BONUSES` = `bonuses` - **MISSING from en.json**
6. `TRANS_KEY_SELECT_CHORES_KID` = `chores_kid` - **MISSING from en.json**

### ❌ Missing Calendar Translations in en.json

1. `TRANS_KEY_CALENDAR_NAME` = `calendar` - **MISSING from en.json**

### ❌ Missing Datetime Translations in en.json

1. `TRANS_KEY_DATETIME_DATE_HELPER` = `date_helper` - **MISSING from en.json**

## Legacy Entity Cleanup Analysis

### 🔍 Entities to Verify Still Exist

These translation keys exist in en.json but may correspond to removed entities:

1. `chore_claims_sensor` - needs verification if entity still exists
2. `chore_approvals_sensor` - needs verification if entity still exists
3. `reward_claims_sensor` - needs verification if entity still exists
4. `reward_approvals_sensor` - needs verification if entity still exists

**Note**: The `sensor_legacy.py` file exists but per instructions should be excluded from new translations.

## Implementation Plan Summary

### Phase 1: Cleanup (Remove unused translations)

- Verify which translation keys correspond to removed entities
- Remove unused translations from en.json

### Phase 2: Add Missing Core Entity Translations

- Add missing select entity translations (5 entries)
- Add missing calendar translation (1 entry)
- Add missing datetime translation (1 entry)
- Add missing sensor translations for active entities (2 confirmed: badge_progress_sensor, dashboard_helper_sensor)

### Phase 3: Verification

- Cross-reference all remaining const.py TRANS*KEY*\* constants against en.json
- Ensure all active entities have working translations
