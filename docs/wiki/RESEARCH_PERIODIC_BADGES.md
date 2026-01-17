# Periodic & Daily Badge Research Document

**Research Date**: January 16, 2026
**Version**: v0.5.0+
**Purpose**: Comprehensive code-validated configuration field inventory for periodic and daily badges

---

## Overview

Periodic and daily badges are **mission-based** badges that:

- Track performance within specific time windows
- Reset automatically (daily or custom periods)
- Support tracked chores filtering
- Can apply penalties for failures
- DO NOT provide point multipliers (cumulative-only feature)

**Key Distinction from Cumulative**:

- Cumulative = Lifetime points, one rank at a time, multipliers, maintenance
- Periodic = Time-bound missions, multiple active, no multipliers, penalties

---

## Badge Type Constants

### Badge Types (const.py lines 571-572)

```python
BADGE_TYPE_DAILY: Final = "daily"           # Resets at midnight, evaluated daily
BADGE_TYPE_PERIODIC: Final = "periodic"     # Custom reset cycles (weekly, monthly, etc.)
```

### Related Badge Types (const.py lines 573-577)

```python
BADGE_TYPE_SPECIAL_OCCASION: Final = "special_occasion"  # 24-hour event badges
BADGE_TYPE_ACHIEVEMENT_LINKED: Final = "achievement"     # Tied to achievements
BADGE_TYPE_CHALLENGE_LINKED: Final = "challenge"         # Tied to challenges
```

---

## Configuration Field Inventory

### Daily vs Periodic Field Differences

| Component          | Daily | Periodic | Cumulative | Notes                                |
| ------------------ | ----- | -------- | ---------- | ------------------------------------ |
| **Target**         | ✅    | ✅       | ✅         | Required for all three               |
| **Tracked Chores** | ✅    | ✅       | ❌         | Filter which chores count            |
| **Assigned Kids**  | ✅    | ✅       | ✅         | Kid assignment                       |
| **Awards**         | ✅    | ✅       | ✅         | Rewards/bonuses/points               |
| **Penalties**      | ✅    | ✅       | ❌         | Auto-applied on failure              |
| **Reset Schedule** | ❌    | ✅       | ✅         | Daily auto-resets at midnight        |
| **Multiplier**     | ❌    | ❌       | ✅         | Only cumulative supports multipliers |
| **Maintenance**    | ❌    | ❌       | ✅         | Only cumulative has maintenance      |

---

## Field-by-Field Analysis

### 1. Common Fields (4 fields)

#### Badge Name (required)

- **Input**: `INPUT_BADGE_NAME`
- **Data key**: `DATA_BADGE_NAME`
- **Translation**: `"badge_name": "Badge Name"`
- **Description**: "Enter a unique name for the badge. This name will be displayed in the system."
- **Validation**: Required, must be unique per badge type

#### Badge Description (optional)

- **Input**: `INPUT_BADGE_DESCRIPTION`
- **Data key**: `DATA_BADGE_DESCRIPTION`
- **Translation**: `"badge_description": "Badge Description (Optional)"`
- **Description**: "Provide a description of the badge's purpose or criteria (optional)."
- **Default**: Empty string

#### Labels (optional)

- **Input**: `INPUT_BADGE_LABELS`
- **Data key**: `DATA_BADGE_LABELS`
- **Translation**: `"badge_labels": "Labels (Optional)"`
- **Description**: "Add labels to categorize or tag the badge (optional)."
- **Default**: Empty list

#### Icon (optional)

- **Input**: `INPUT_BADGE_ICON`
- **Data key**: `DATA_BADGE_ICON`
- **Translation**: `"icon": "Badge Icon (mdi:xxx)"`
- **Description**: "Specify an icon for the badge using Material Design Icons (e.g., mdi:star)."
- **Default**: `DEFAULT_BADGE_ICON = "mdi:medal-outline"`

---

### 2. Target Settings (2-3 fields)

#### Target Type (required)

- **Input**: `INPUT_BADGE_TARGET_TYPE`
- **Data key**: `DATA_BADGE_TARGET_TYPE`
- **Translation**: `"target_type": "🎯 TARGET: Target Type"` (periodic) or `"target_type": "🎯 DAILY TARGET: Target Type"` (daily)
- **Description**: "Select the type of target for this badge (e.g., points, chore count, days, or streak)."
- **Options**: 19 target types (see Target Type Options section below)

#### Threshold Value (required)

- **Input**: `INPUT_BADGE_THRESHOLD_VALUE`
- **Data key**: `DATA_BADGE_THRESHOLD_VALUE`
- **Translation**: `"threshold_value": "🎯 TARGET: Threshold Value"`
- **Description**:
  - **Periodic**: "Set the total points, chore count, or number of days (such as for multi-chore completion streaks) required to earn this badge within the defined period."
  - **Daily**: "Set the daily points, chore count, or number of days required to earn this badge. For 'Days' target types, enter 1 since the badge is evaluated daily (e.g., 1 for a one-day complete all selected chores)."
- **Validation**: Must be > 0

#### Maintenance Rules (optional, periodic only - NOT USED)

- **Input**: `INPUT_BADGE_MAINTENANCE_RULES`
- **Data key**: `DATA_BADGE_MAINTENANCE_RULES`
- **Translation**: `"maintenance_rules": "🎯 TARGET: Maintenance Points (Optional)"`
- **Description**: "Specify the minimum points required during the reset cycle to retain the badge and its active multiplier (optional)."
- **Note**: ⚠️ This field appears in periodic badge schema but **maintenance is NOT supported** for periodic badges (cumulative-only feature). Likely legacy field that should be ignored.
- **Default**: 0

---

### 3. Tracked Chores Component (1 field)

> **CRITICAL**: Periodic and daily badges are the ONLY badge types that support tracked chores filtering.

#### Selected Chores (optional)

- **Input**: `INPUT_BADGE_SELECTED_CHORES`
- **Data key**: `DATA_BADGE_SELECTED_CHORES`
- **Translation**: `"selected_chores": "🧹 Tracked Chores (Optional)"`
- **Description**: "Select the chores that contribute points toward this badge. Leave blank if you want to track all assigned chores (optional)."
- **Default**: Empty list (tracks ALL assigned chores)
- **Included in**: `INCLUDE_TRACKED_CHORES_BADGE_TYPES = [BADGE_TYPE_PERIODIC, BADGE_TYPE_DAILY]` (const.py line 3011)

**Behavior**:

- **Empty list**: Badge counts points/completions from ALL chores assigned to kid
- **Selected chores**: Badge ONLY counts points/completions from listed chores
- **Use cases**:
  - "Dishwasher Badge" - Only tracks "Load Dishwasher" + "Unload Dishwasher"
  - "Morning Routine" - Only tracks "Make Bed" + "Brush Teeth"
  - "Pet Care" - Only tracks pet-related chores

---

### 4. Assigned Kids Component (1 field)

#### Assigned To (required)

- **Input**: `INPUT_BADGE_ASSIGNED_KIDS`
- **Data key**: `DATA_BADGE_ASSIGNED_KIDS`
- **Translation**: `"assigned_to": "🧒 Assigned Kids (Required)"`
- **Description**: "Assign this badge to specific kids for tracking. You must select at least one kid."
- **Validation**: Required, must have at least 1 kid selected
- **Included in**: `INCLUDE_ASSIGNED_TO_BADGE_TYPES` (const.py lines 3014-3020)

**Behavior**:

- **Mandatory selection**: Integration will not allow badge creation without at least 1 kid assigned
- **No global default**: There is no "Apply to All" toggle or empty list default
- **To make badge global**: Must manually select every kid in the system
- **Un-assignment**: Removing a kid from badge assignments immediately deletes their progress data via `_sync_badge_progress_for_kid`
- **Use cases**:
  - Age-appropriate badges (harder badges for older kids)
  - Themed badge sets per kid
  - Individual challenges

**Critical Difference from Tracked Chores**:

- **Tracked Chores**: Empty list = all chores (permissive default)
- **Assigned Kids**: Empty list = INVALID, must select at least 1 (restrictive requirement)

---

### 5. Awards Component (5 fields)

#### Award Items Selector (optional)

- **Input**: `INPUT_BADGE_AWARD_ITEMS`
- **Data key**: `DATA_BADGE_AWARD_ITEMS`
- **Translation**: `"award_items": "🎁 AWARDS: Select Points, Rewards, Bonuses, Penalties (Optional)"`
- **Description**: "Select one or more from points, rewards, bonuses, or penalties. All selected items will be granted or applied when the badge is earned. Penalties will only be applied if the badge is not earned by the end date or reset date. (optional)"
- **Options**:
  - `BADGE_AWARD_ITEM_POINTS = "points"` - Grant points immediately
  - `BADGE_AWARD_ITEM_REWARDS = "rewards"` - Grant selected rewards
  - `BADGE_AWARD_ITEM_BONUSES = "bonuses"` - Grant selected bonuses
  - `BADGE_AWARD_ITEM_PENALTIES = "penalties"` - Apply penalty on failure (**periodic/daily only**)
  - `BADGE_AWARD_ITEM_MULTIPLIER = "multiplier"` - NOT available for periodic/daily
- **Default**: Empty list

#### Award Points (conditional)

- **Input**: `INPUT_BADGE_AWARD_POINTS`
- **Data key**: `DATA_BADGE_AWARD_POINTS`
- **Translation**: `"award_points": "🎁 AWARDS: Points Awarded (Optional)"`
- **Description**: "If points are a selected award, specify the number of points to apply when this badge is earned. (optional)."
- **Appears when**: `"points"` selected in award_items
- **Default**: 0

#### Award Rewards (conditional)

- **Input**: `INPUT_BADGE_AWARD_REWARDS`
- **Data key**: `DATA_BADGE_AWARD_REWARDS`
- **Translation**: Not shown in provided excerpt (likely similar to bonuses)
- **Appears when**: `"rewards"` selected in award_items
- **Default**: Empty list

#### Award Bonuses (conditional)

- **Input**: `INPUT_BADGE_AWARD_BONUSES`
- **Data key**: `DATA_BADGE_AWARD_BONUSES`
- **Translation**: Not shown in provided excerpt
- **Appears when**: `"bonuses"` selected in award_items
- **Default**: Empty list

#### Award Penalties (conditional, periodic/daily only)

- **Input**: `INPUT_BADGE_AWARD_PENALTIES`
- **Data key**: `DATA_BADGE_AWARD_PENALTIES`
- **Translation**: Not explicitly shown (appears as part of award_items selector)
- **Appears when**: `"penalties"` selected in award_items
- **Default**: Empty list
- **Included in**: `INCLUDE_PENALTIES_BADGE_TYPES = [BADGE_TYPE_PERIODIC, BADGE_TYPE_DAILY]` (const.py lines 3032-3035)
- **Behavior**: Penalty automatically applied if badge NOT earned by end_date/reset time

---

### 6. Reset Schedule Component (5 fields - Periodic only)

> **NOTE**: Daily badges do NOT have reset schedule fields - they automatically reset at midnight.

#### Recurring Frequency (required for periodic)

- **Input**: `INPUT_BADGE_RESET_RECURRING_FREQUENCY`
- **Data key**: `DATA_BADGE_RESET_RECURRING_FREQUENCY`
- **Translation**: `"recurring_frequency": "🔄 RESET CYCLE: Frequency"`
- **Description**: "Define the reset schedule for this badge (e.g., weekly, monthly)."
- **Options**:
  - `FREQUENCY_DAILY = "daily"`
  - `FREQUENCY_WEEKLY = "weekly"`
  - `FREQUENCY_MONTHLY = "monthly"`
  - `FREQUENCY_QUARTERLY = "quarterly"`
  - `FREQUENCY_YEARLY = "yearly"`
  - `FREQUENCY_CUSTOM = "custom"` (requires custom_interval + custom_interval_unit)
- **Default**: `FREQUENCY_WEEKLY`
- **Included in**: `INCLUDE_RESET_SCHEDULE_BADGE_TYPES` (const.py lines 3041-3047)

#### Custom Interval (conditional)

- **Input**: `INPUT_BADGE_RESET_CUSTOM_INTERVAL`
- **Data key**: `DATA_BADGE_RESET_CUSTOM_INTERVAL`
- **Translation**: `"custom_interval": "🔄 RESET CYCLE: Custom Interval (Required for Custom Frequency)"`
- **Description**: "Specify the NUMBER of days, weeks, months, etc. for Custom Frequency (e.g., 3 if you set 3 weeks)."
- **Appears when**: `recurring_frequency = "custom"`
- **Validation**: Must be > 0
- **Default**: None

#### Custom Interval Unit (conditional)

- **Input**: `INPUT_BADGE_RESET_CUSTOM_INTERVAL_UNIT`
- **Data key**: `DATA_BADGE_RESET_CUSTOM_INTERVAL_UNIT`
- **Translation**: `"custom_interval_unit": "🔄 RESET CYCLE: Custom Interval Unit (Required for Custom Frequency)"`
- **Description**: "Select the unit for the custom interval (e.g., days, weeks)."
- **Appears when**: `recurring_frequency = "custom"`
- **Options**:
  - `CUSTOM_INTERVAL_UNIT_DAYS = "days"`
  - `CUSTOM_INTERVAL_UNIT_WEEKS = "weeks"`
  - `CUSTOM_INTERVAL_UNIT_MONTHS = "months"`
- **Default**: None

#### Start Date (optional)

- **Input**: `INPUT_BADGE_RESET_START_DATE`
- **Data key**: `DATA_BADGE_RESET_START_DATE`
- **Translation**: `"start_date": "🔄 RESET CYCLE: Start Date (Optional)"`
- **Description**: "Set the start date for the reset cycle (optional)."
- **Default**: None (calculated automatically per kid if omitted)

#### End Date (optional)

- **Input**: `INPUT_BADGE_RESET_END_DATE`
- **Data key**: `DATA_BADGE_RESET_END_DATE`
- **Translation**: `"end_date": "🔄 RESET CYCLE: End Date (Optional)"`
- **Description**: "Set the end date for the reset cycle (optional)."
- **Default**: None (badge continues indefinitely)

---

## Target Type Options (19 types)

### Points-Based Targets (2 types)

#### 1. Points Earned

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_POINTS = "points"` (const.py line 1333)
- **Label**: "Points Earned"
- **Tracks**: Total points from ALL sources (chores, bonuses, manual adjustments)
- **Example**: "Earn 100 points this week"

#### 2. Points Earned (From Chores)

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES = "points_chores"` (const.py line 1334)
- **Label**: "Points Earned (From Chores)"
- **Tracks**: Points ONLY from chore completions (excludes bonuses, manual adjustments)
- **Example**: "Earn 50 points from chores only this week"

---

### Count-Based Targets (1 type)

#### 3. Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT = "chore_count"` (const.py line 1335)
- **Label**: "Chores Completed"
- **Tracks**: Total number of chore completions
- **Example**: "Complete 10 chores this week"

---

### Days-Based Targets (9 types)

> **Concept**: "Days" targets check if criteria was met on X number of days within the period.

#### 4. Days Selected Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES = "days_all_chores"` (const.py line 1336)
- **Label**: "Days Selected Chores Completed"
- **Tracks**: Days where ALL tracked chores were completed (100% completion)
- **Example**: "Complete all tracked chores on 5 days this week"
- **Note**: "Selected" refers to tracked_chores filter

#### 5. Days 80% of Selected Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES = "days_80pct_chores"` (const.py line 1337)
- **Label**: "Days 80% of Selected Chores Completed"
- **Tracks**: Days where at least 80% of tracked chores were completed
- **Example**: "Complete 80% of tracked chores on 5 days this week"

#### 6. Days Selected Chores Completed (No Overdue)

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES_NO_OVERDUE = "days_all_chores_no_overdue"` (const.py lines 1338-1340)
- **Label**: "Days Selected Chores Completed (No Overdue)"
- **Tracks**: Days where ALL tracked chores were completed AND no tracked chores went overdue
- **Example**: "Complete all tracked chores on time (no overdue) on 5 days this week"
- **Strict Mode**: See Badge-Periodic-Advanced.md for strict mode behavior

#### 7. Days Selected Due Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES = "days_all_due_chores"` (const.py line 1341)
- **Label**: "Days Selected Due Chores Completed"
- **Tracks**: Days where ALL tracked chores with due dates were completed
- **Example**: "Complete all due chores on 5 days this week"
- **Note**: Only counts chores with due dates (ignores chores without)

#### 8. Days 80% of Selected Due Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_DUE_CHORES = "days_80pct_due_chores"` (const.py line 1342)
- **Label**: "Days 80% of Selected Due Chores Completed"
- **Tracks**: Days where at least 80% of tracked due chores were completed
- **Example**: "Complete 80% of due chores on 5 days this week"

#### 9. Days Selected Due Chores Completed (No Overdue)

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES_NO_OVERDUE = "days_all_due_chores_no_overdue"` (const.py lines 1343-1345)
- **Label**: "Days Selected Due Chores Completed (No Overdue)"
- **Tracks**: Days where ALL tracked due chores were completed on time (no overdue)
- **Example**: "Complete all due chores on time on 5 days this week"
- **Strict Mode**: Fails if any due chore goes overdue

#### 10. Days Minimum 3 Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_3_CHORES = "days_min_3_chores"` (const.py line 1346)
- **Label**: "Days Minimum 3 Chores Completed"
- **Tracks**: Days where at least 3 chores were completed
- **Example**: "Complete at least 3 chores on 5 days this week"
- **Note**: Fixed threshold (3 chores), but badge threshold_value controls number of days

#### 11. Days Minimum 5 Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES = "days_min_5_chores"` (const.py line 1347)
- **Label**: "Days Minimum 5 Chores Completed"
- **Tracks**: Days where at least 5 chores were completed
- **Example**: "Complete at least 5 chores on 5 days this week"

#### 12. Days Minimum 7 Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_7_CHORES = "days_min_7_chores"` (const.py line 1348)
- **Label**: "Days Minimum 7 Chores Completed"
- **Tracks**: Days where at least 7 chores were completed
- **Example**: "Complete at least 7 chores on 5 days this week"

---

### Streak-Based Targets (7 types)

> **Concept**: Streaks require CONSECUTIVE days meeting criteria (unlike "Days" which can be non-consecutive).

#### 13. Streak: Selected Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES = "streak_all_chores"` (const.py line 1349)
- **Label**: "Streak: Selected Chores Completed"
- **Tracks**: Consecutive days where ALL tracked chores were completed
- **Example**: "Complete all tracked chores 5 days in a row"

#### 14. Streak: 80% of Selected Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_CHORES = "streak_80pct_chores"` (const.py line 1350)
- **Label**: "Streak: 80% of Selected Chores Completed"
- **Tracks**: Consecutive days where at least 80% of tracked chores were completed
- **Example**: "Complete 80% of tracked chores 5 days in a row"

#### 15. Streak: Selected Chores Completed (No Overdue)

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE = "streak_all_chores_no_overdue"` (const.py lines 1351-1353)
- **Label**: "Streak: Selected Chores Completed (No Overdue)"
- **Tracks**: Consecutive days where ALL tracked chores were completed on time
- **Example**: "Complete all tracked chores on time 5 days in a row"
- **Strict Mode**: Streak breaks if any chore goes overdue

#### 16. Streak: 80% of Selected Due Chores Completed

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_DUE_CHORES = "streak_80pct_due_chores"` (const.py line 1354)
- **Label**: "Streak: 80% of Selected Due Chores Completed"
- **Tracks**: Consecutive days where at least 80% of tracked due chores were completed
- **Example**: "Complete 80% of due chores 5 days in a row"

#### 17. Streak: Selected Due Chores Completed (No Overdue)

- **Constant**: `BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_DUE_CHORES_NO_OVERDUE = "streak_all_due_chores_no_overdue"` (const.py lines 1355-1357)
- **Label**: "Streak: Selected Due Chores Completed (No Overdue)"
- **Tracks**: Consecutive days where ALL tracked due chores were completed on time
- **Example**: "Complete all due chores on time 5 days in a row"
- **Strict Mode**: Streak breaks if any due chore goes overdue

#### 18-19. Additional Streak Types

Based on the pattern, there are likely 2 more streak types matching the "days" pattern (const.py lines 2918-2986 show 19 total target types).

---

## Fields NOT Included in Periodic/Daily Badges

### Points Multiplier (Cumulative Only)

- **Constant**: `BADGE_AWARD_ITEM_MULTIPLIER = "multiplier"`
- **Why excluded**: Multipliers are for long-term rank progression (cumulative), not time-bound missions
- **Included in**: Cumulative badges only (`INCLUDE_AWARDS_BADGE_TYPES`)

### Maintenance (Cumulative Only)

- **Constants**: Maintenance points, grace period, maintenance dates
- **Why excluded**: Periodic badges reset completely, no concept of "keeping" a badge
- **Note**: `maintenance_rules` appears in periodic schema but is NOT functional (likely legacy field)

### Special Occasion Fields

- **Constants**: Occasion type, specific dates
- **Why excluded**: Special occasion is a separate badge type
- **Badge type**: `BADGE_TYPE_SPECIAL_OCCASION`

### Linked Entity Fields

- **Constants**: Associated achievement, associated challenge
- **Why excluded**: Achievement-linked and challenge-linked are separate badge types
- **Badge types**: `BADGE_TYPE_ACHIEVEMENT_LINKED`, `BADGE_TYPE_CHALLENGE_LINKED`

---

## Component Inclusion Matrix

From const.py lines 2988-3047:

| Component          | Cumulative | Periodic | Daily | Special | Achievement | Challenge |
| ------------------ | ---------- | -------- | ----- | ------- | ----------- | --------- |
| Target             | ✅         | ✅       | ✅    | ✅      | ❌          | ❌        |
| Tracked Chores     | ❌         | ✅       | ✅    | ❌      | ❌          | ❌        |
| Assigned Kids      | ✅         | ✅       | ✅    | ✅      | ❌          | ❌        |
| Awards             | ✅         | ✅       | ✅    | ✅      | ✅          | ✅        |
| Penalties          | ❌         | ✅       | ✅    | ❌      | ❌          | ❌        |
| Reset Schedule     | ✅         | ✅       | ❌    | ✅      | ❌          | ❌        |
| Special Occasion   | ❌         | ❌       | ❌    | ✅      | ❌          | ❌        |
| Achievement Linked | ❌         | ❌       | ❌    | ❌      | ✅          | ❌        |
| Challenge Linked   | ❌         | ❌       | ❌    | ❌      | ❌          | ✅        |

---

## Key Behavioral Differences: Daily vs Periodic

### Daily Badges

- **Reset**: Automatic at midnight (00:00 local time)
- **Reset schedule fields**: NONE (no recurring_frequency, custom_interval, etc.)
- **Evaluation**: Checked once per day at midnight
- **Progress tracking**: `sensor.kc_<kid>_badge_progress_<badge_name>` resets daily
- **Use case**: Daily habits ("Complete 5 chores today", "Earn 50 points today")

### Periodic Badges

- **Reset**: Custom schedule (weekly, monthly, quarterly, yearly, custom)
- **Reset schedule fields**: Required (recurring_frequency, optional start/end dates)
- **Evaluation**: Checked at end of period
- **Progress tracking**: `sensor.kc_<kid>_badge_progress_<badge_name>` resets per cycle
- **Use case**: Weekly goals ("Complete 20 chores this week", "Perfect attendance week")

---

## Validation Rules

### Tracked Chores Validation

- **Rule**: Selected chores must exist in chores_data
- **Rule**: If empty list, interprets as "all chores"
- **Rule**: Cannot select chores the kid is not assigned to (warning, not error)

### Target Type Validation

- **Rule**: Must be one of 19 valid target types
- **Rule**: Threshold value must be > 0
- **Rule**: For daily "Days" targets, threshold typically = 1 (since evaluated daily)

### Reset Schedule Validation (Periodic only)

- **Rule**: `recurring_frequency` required
- **Rule**: If `recurring_frequency = "custom"`, must provide `custom_interval` + `custom_interval_unit`
- **Rule**: `custom_interval` must be > 0
- **Rule**: `start_date` must be <= `end_date` (if both provided)

### Awards Validation

- **Rule**: If `award_items` includes "points", must provide `award_points` > 0
- **Rule**: If `award_items` includes "rewards", must select at least 1 reward
- **Rule**: If `award_items` includes "bonuses", must select at least 1 bonus
- **Rule**: If `award_items` includes "penalties", must select at least 1 penalty

---

## Translation Keys Reference

### Config Flow Keys

- `add_badge_daily` - Daily badge creation step
- `add_badge_periodic` - Periodic badge creation step

### Options Flow Keys

- `edit_badge_daily` - Daily badge edit step
- `edit_badge_periodic` - Periodic badge edit step

### Data Field Keys

All keys prefixed with appropriate emojis:

- 🎯 TARGET fields
- 🧹 Tracked chores
- 🧒 Assigned kids
- 🎁 AWARDS fields
- 🔄 RESET CYCLE fields

---

## Constants Reference Quick Lookup

```python
# Badge types
BADGE_TYPE_DAILY = "daily"
BADGE_TYPE_PERIODIC = "periodic"

# Component inclusion lists
INCLUDE_TRACKED_CHORES_BADGE_TYPES = [BADGE_TYPE_PERIODIC, BADGE_TYPE_DAILY]
INCLUDE_PENALTIES_BADGE_TYPES = [BADGE_TYPE_PERIODIC, BADGE_TYPE_DAILY]

# Target types (19 total)
BADGE_TARGET_THRESHOLD_TYPE_POINTS = "points"
BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES = "points_chores"
BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT = "chore_count"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES = "days_all_chores"
# ... (see Target Type Options section for all 19)

# Award items
BADGE_AWARD_ITEM_POINTS = "points"
BADGE_AWARD_ITEM_REWARDS = "rewards"
BADGE_AWARD_ITEM_BONUSES = "bonuses"
BADGE_AWARD_ITEM_PENALTIES = "penalties"

# Frequencies
FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_MONTHLY = "monthly"
FREQUENCY_QUARTERLY = "quarterly"
FREQUENCY_YEARLY = "yearly"
FREQUENCY_CUSTOM = "custom"

# Custom interval units
CUSTOM_INTERVAL_UNIT_DAYS = "days"
CUSTOM_INTERVAL_UNIT_WEEKS = "weeks"
CUSTOM_INTERVAL_UNIT_MONTHS = "months"
```

---

## Configuration Flow Location

### Config Flow (Initial Setup)

- **File**: `custom_components/kidschores/config_flow.py`
- **Step**: `async_step_badges()` (lines ~836-900)
- **Helper**: `flow_helpers.build_badge_common_schema()` (lines ~1957-2250)

### Options Flow (Post-Setup Management)

- **File**: `custom_components/kidschores/options_flow.py`
- **Steps**:
  - `async_step_select_entity()` - Select badge to edit/delete
  - `async_step_add_badge_periodic()` - Add new periodic badge
  - `async_step_add_badge_daily()` - Add new daily badge
  - `async_step_edit_badge_periodic()` - Edit existing periodic badge
  - `async_step_edit_badge_daily()` - Edit existing daily badge

---

## Related Documentation

- **[Badge-Gamification.md](Advanced:-Badges-Overview.md)** - Badge system overview (ranks vs missions)
- **[Badge-Periodic-Advanced.md](Advanced:-Badges-Periodic.md)** - Advanced periodic mechanics (strict mode, shared chore conflicts, penalties)
- **[Badge-Cumulative-Advanced.md](Advanced:-Badges-Cumulative.md)** - Cumulative rank mechanics (for comparison)
- **[Technical-Reference:-Badge-Entities-Detail.md](Technical:-Badge-Entities.md)** - Badge sensor entities
- **[Technical-Reference:-Configuration-Detail.md](Technical:-Configuration.md)** - Config/Options flow architecture

---

**Next Step**: Create Configuration:-Periodic-Badges.md user guide based on this research + Badge-Periodic-Advanced.md reference.
