# Research: Cumulative Badges (Badge Configuration)

**Date**: 2025-01-16
**Purpose**: Detailed research on cumulative badge configuration fields, validation, and workflows. This is separate from periodic/daily badges which have different fields.

**⚠️ CRITICAL**: Cumulative badges are distinct from periodic/daily badges. Do not mix up their fields:

- **Cumulative badges**: Lifetime points tracking, no tracked chores, optional maintenance cycles
- **Periodic/daily badges**: Time-bound targets, tracked chores required, mandatory reset schedules

---

## Overview

**Cumulative badges** reward kids for reaching **lifetime total points** thresholds. Once earned, they are permanent but can have optional **maintenance cycles** to keep multipliers active.

**Key characteristics**:

- **Target**: Always based on lifetime total points (no target_type selector)
- **Earning**: Triggered automatically when kid's lifetime points reach threshold
- **Permanence**: Highest badge earned is NEVER removed (but current effective badge can be demoted one level)
- **Maintenance**: Optional recurring cycle requiring minimum points to keep multiplier active
- **Chores**: NOT tracked (cumulative badges count ALL points from ALL sources)
- **Assignment**: Optional (assign to specific kids for themed badge sets)
- **Demotion**: If maintenance not met, kid drops one level (multiplier from next lower badge applies)
- **Requalification**: Immediate when maintenance goal is met (no full cycle required)
- **Award Frequency**: Each maintenance cycle completion awards points/rewards/bonuses (motivates progress)

**Tracking Sensor**: `sensor.kc_<kid>_badges` (formerly `highest_badge`) - Single sensor showing all cumulative badge progress

**Legacy Conversion**: Pre-v0.5.0 badges convert to cumulative type (points-only, chore counts not supported)

---

## Configuration Fields (Cumulative Badges)

### Common Fields (All Badge Types)

| Field           | Input Constant                  | Data Constant            | Type      | Required | Default                     | Validation                     |
| --------------- | ------------------------------- | ------------------------ | --------- | -------- | --------------------------- | ------------------------------ |
| **Badge Name**  | `CFOF_BADGES_INPUT_NAME`        | `DATA_BADGE_NAME`        | string    | ✅ Yes   | None                        | Non-empty, unique among badges |
| **Description** | `CFOF_BADGES_INPUT_DESCRIPTION` | `DATA_BADGE_DESCRIPTION` | string    | ❌ No    | Empty string                | Any text                       |
| **Labels**      | `CFOF_BADGES_INPUT_LABELS`      | `DATA_BADGE_LABELS`      | list[str] | ❌ No    | `[]`                        | Label selector (multiple)      |
| **Icon**        | `CFOF_BADGES_INPUT_ICON`        | `DATA_BADGE_ICON`        | string    | ❌ No    | `"mdi:shield-star-outline"` | Icon selector (mdi:xxx)        |

### Target Component (Cumulative-Specific)

**Note**: Cumulative badges **do NOT include** the `target_type` field. They always use lifetime points.

| Field                  | Input Constant                             | Data Constant                                             | Type  | Required | Default | Validation                              |
| ---------------------- | ------------------------------------------ | --------------------------------------------------------- | ----- | -------- | ------- | --------------------------------------- |
| **Threshold Value**    | `CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE` | `DATA_BADGE_TARGET` → `DATA_BADGE_TARGET_THRESHOLD_VALUE` | float | ✅ Yes   | `50.0`  | ≥ 0, coerced to float                   |
| **Maintenance Points** | `CFOF_BADGES_INPUT_MAINTENANCE_RULES`      | `DATA_BADGE_TARGET` → `DATA_BADGE_MAINTENANCE_RULES`      | int   | ❌ No    | `0`     | ≥ 0, coerced to int, 0 = no maintenance |

**Target data structure** (stored in `DATA_BADGE_TARGET`):

```python
{
    "threshold_value": 100.0,  # Lifetime points required to earn badge
    "maintenance_rules": 20    # Optional: min points per cycle to keep multiplier
    # NOTE: NO "type" field for cumulative badges (always uses points)
}
```

### Assigned To Component

| Field             | Input Constant                  | Data Constant            | Type      | Required | Default | Validation                         |
| ----------------- | ------------------------------- | ------------------------ | --------- | -------- | ------- | ---------------------------------- |
| **Assigned Kids** | `CFOF_BADGES_INPUT_ASSIGNED_TO` | `DATA_BADGE_ASSIGNED_TO` | list[str] | ❌ No    | `[]`    | Kid internal_ids, empty = all kids |

**Behavior**:

- Empty list: Badge available to all kids
- Specific kids: Only assigned kids can earn/track this badge

### Awards Component

| Field                 | Input Constant                        | Data Constant                                               | Type      | Required | Default | Validation                                            |
| --------------------- | ------------------------------------- | ----------------------------------------------------------- | --------- | -------- | ------- | ----------------------------------------------------- |
| **Award Items**       | `CFOF_BADGES_INPUT_AWARD_ITEMS`       | N/A (controls which awards appear)                          | list[str] | ❌ No    | `[]`    | Options: points, rewards, bonuses, multiplier         |
| **Award Points**      | `CFOF_BADGES_INPUT_AWARD_POINTS`      | `DATA_BADGE_AWARDS` → `DATA_BADGE_AWARDS_POINTS`            | float     | ❌ No    | `0.0`   | ≥ 0, only if "points" in award_items                  |
| **Points Multiplier** | `CFOF_BADGES_INPUT_POINTS_MULTIPLIER` | `DATA_BADGE_AWARDS` → `DATA_BADGE_AWARDS_POINTS_MULTIPLIER` | float     | ❌ No    | `1.0`   | > 0, only if "multiplier" in award_items              |
| **Award Rewards**     | `CFOF_BADGES_INPUT_AWARD_REWARD`      | `DATA_BADGE_AWARDS` → `DATA_BADGE_AWARDS_REWARDS`           | list[str] | ❌ No    | `[]`    | Reward internal_ids, only if "rewards" in award_items |
| **Award Bonuses**     | `CFOF_BADGES_INPUT_AWARD_BONUS`       | `DATA_BADGE_AWARDS` → `DATA_BADGE_AWARDS_BONUSES`           | list[str] | ❌ No    | `[]`    | Bonus internal_ids, only if "bonuses" in award_items  |

**Award Items Selector** (user picks which awards to grant):

- `"points"` → Award points immediately when badge is earned
- `"rewards"` → Grant rewards automatically when badge is earned
- `"bonuses"` → Grant bonuses automatically when badge is earned
- `"multiplier"` → Apply points multiplier while badge is active

### Reset Schedule Component (Maintenance Cycle)

**Purpose**: Optional recurring cycle requiring minimum points to keep multiplier active. If kid doesn't earn enough points during the cycle, the multiplier deactivates (but badge remains earned).

| Field                    | Input Constant                                          | Data Constant                                                                  | Type   | Required       | Default  | Validation                                                   |
| ------------------------ | ------------------------------------------------------- | ------------------------------------------------------------------------------ | ------ | -------------- | -------- | ------------------------------------------------------------ |
| **Recurring Frequency**  | `CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY`  | `DATA_BADGE_RESET_SCHEDULE` → `DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY`  | string | ❌ No          | `"none"` | Options: none, daily, weekly, monthly, custom                |
| **Custom Interval**      | `CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL`      | `DATA_BADGE_RESET_SCHEDULE` → `DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL`      | int    | ❌ Conditional | `None`   | Required if frequency = custom                               |
| **Custom Interval Unit** | `CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT` | `DATA_BADGE_RESET_SCHEDULE` → `DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT` | string | ❌ Conditional | `None`   | Options: days, weeks, months; required if frequency = custom |
| **Start Date**           | `CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE`           | `DATA_BADGE_RESET_SCHEDULE` → `DATA_BADGE_RESET_SCHEDULE_START_DATE`           | string | ❌ No          | `None`   | ISO date, optional                                           |
| **End Date**             | `CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE`             | `DATA_BADGE_RESET_SCHEDULE` → `DATA_BADGE_RESET_SCHEDULE_END_DATE`             | string | ❌ No          | `None`   | ISO date, optional                                           |
| **Grace Period Days**    | `CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS`    | `DATA_BADGE_RESET_SCHEDULE` → `DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS`    | int    | ❌ No          | `0`      | ≥ 0, extra days after cycle end to meet requirement          |

**Reset Schedule data structure** (stored in `DATA_BADGE_RESET_SCHEDULE`):

```python
{
    "recurring_frequency": "weekly",  # or "none", "daily", "monthly", "custom"
    "custom_interval": None,          # Only for "custom" frequency
    "custom_interval_unit": None,     # Only for "custom" frequency
    "start_date": "2025-01-01",       # Optional start date (ISO format)
    "end_date": None,                 # Optional end date (ISO format)
    "grace_period_days": 3            # Extra days after cycle to meet requirement
}
```

---

## Fields That Cumulative Badges Do NOT Have

These fields are used by periodic/daily badges but **NOT** cumulative badges:

- ❌ **Target Type** (`CFOF_BADGES_INPUT_TARGET_TYPE`) - Cumulative badges always use lifetime points
- ❌ **Tracked Chores** (`CFOF_BADGES_INPUT_SELECTED_CHORES`) - Cumulative badges count ALL points
- ❌ **Daily Threshold Type** - Only for daily badges
- ❌ **Penalties** (`CFOF_BADGES_INPUT_AWARD_PENALTY`) - Only for periodic/daily badges
- ❌ **Occasion Type** (`CFOF_BADGES_INPUT_OCCASION_TYPE`) - Only for special occasion badges
- ❌ **Associated Achievement/Challenge** - Only for linked badge types

---

## Included Components (Feature Flags)

**Source**: `const.py` lines 2988-3050

Cumulative badges include these components:

```python
BADGE_TYPE_CUMULATIVE in:
- INCLUDE_TARGET_BADGE_TYPES          ✅ Yes (threshold value + maintenance rules)
- INCLUDE_ASSIGNED_TO_BADGE_TYPES     ✅ Yes (assign to specific kids)
- INCLUDE_AWARDS_BADGE_TYPES          ✅ Yes (points, rewards, bonuses, multiplier)
- INCLUDE_RESET_SCHEDULE_BADGE_TYPES  ✅ Yes (maintenance cycle for multiplier)

BADGE_TYPE_CUMULATIVE NOT in:
- INCLUDE_TRACKED_CHORES_BADGE_TYPES  ❌ No (cumulative badges count ALL points)
- INCLUDE_PENALTIES_BADGE_TYPES       ❌ No (only periodic/daily have penalties)
- INCLUDE_SPECIAL_OCCASION_BADGE_TYPES ❌ No (separate badge type)
- INCLUDE_ACHIEVEMENT_LINKED_BADGE_TYPES ❌ No (separate badge type)
- INCLUDE_CHALLENGE_LINKED_BADGE_TYPES ❌ No (separate badge type)
```

---

## Validation Rules

**Source**: `flow_helpers.py` function `validate_badge_common_inputs()`

### Name Validation

- **Rule**: Non-empty after stripping whitespace
- **Error key**: `TRANS_KEY_CFOF_NAME_REQUIRED` → `"name_required"`
- **Uniqueness**: Checked against existing badges (case-insensitive)
- **Error key**: `TRANS_KEY_CFOF_BADGE_NAME_DUPLICATE` → `"badge_name_duplicate"`

### Threshold Value Validation

- **Rule**: Must be coercible to float, ≥ 0
- **Default**: `50.0` if invalid
- **Logging**: Warning if coercion fails

### Maintenance Rules Validation

- **Rule**: Must be coercible to int, ≥ 0
- **Default**: `0` (no maintenance) if invalid
- **Meaning**: 0 = no maintenance required, > 0 = min points per cycle

### Reset Schedule Validation (if enabled)

- **Frequency**: Must be one of: none, daily, weekly, monthly, quarterly, yearly
- **Custom frequency**: NOT supported for cumulative badges (use predefined frequencies only)
- **Dates**: Must be valid ISO format if provided (used as templates for per-kid calculation)
- **Grace period**: Must be ≥ 0

### Award Items Validation

- **Points**: If "points" in award_items, award_points must be ≥ 0
- **Multiplier**: If "multiplier" in award_items, points_multiplier must be > 0
- **Rewards/Bonuses**: Must reference valid internal_ids

---

## UI Labels (Translations)

**Source**: `translations/en.json` lines 130-200, 488-530

### Config Flow Step

**Step ID**: `"badges"` (during initial setup) or `"add_badge_cumulative"` (in options flow)

**Title**: "Add Cumulative Badge"

**Description**: "Configure the details for a cumulative badge. These badges reward kids for reaching lifetime point thresholds and support maintenance cycles to encourage ongoing performance."

### Field Labels

```json
{
  "badge_name": "Badge Name",
  "badge_description": "Badge Description (Optional)",
  "badge_labels": "Labels (Optional)",
  "icon": "Badge Icon (mdi:xxx)",
  "threshold_value": "🎯 TARGET: Threshold Value",
  "maintenance_rules": "🎯 TARGET: Maintenance Points (Optional)",
  "assigned_to": "🧒 Assigned Kids (Optional)",
  "award_items": "🎁 AWARDS: Select Points, Rewards, Bonuses, Multiplier (Optional)",
  "award_points": "🎁 AWARDS: Points Awarded (Optional)",
  "points_multiplier": "🎁 AWARDS: Points Multiplier (Default 💎 1.0x)",
  "recurring_frequency": "🔄 MAINTENANCE CYCLE: Frequency",
  "custom_interval": "🔄 MAINTENANCE CYCLE: Custom Interval (Required for Custom Frequency)",
  "custom_interval_unit": "🔄 MAINTENANCE CYCLE: Custom Interval Unit (Required for Custom Frequency)",
  "start_date": "🔄 RESET CYCLE: Start Date (Optional)",
  "end_date": "🔄 MAINTENANCE CYCLE: End Date (Optional)",
  "grace_period_days": "🔄 MAINTENANCE CYCLE: Grace Period in Days (Optional)"
}
```

### Field Descriptions (Help Text)

```json
{
  "badge_name": "Enter a unique name for the badge. This name will be displayed in the system.",
  "badge_description": "Provide a description of the badge's purpose or criteria (optional).",
  "badge_labels": "Add labels to categorize or tag the badge (optional).",
  "icon": "Specify an icon for the badge using Material Design Icons (e.g., mdi:star).",
  "threshold_value": "Set the total lifetime points required to earn this badge.",
  "maintenance_rules": "Specify the minimum points required during the maintenance cycle to retain the badge and its active multiplier (optional).",
  "assigned_to": "Assign this badge to specific kids for tracking.",
  "award_items": "Select one or more from points, rewards, bonuses, or a points multiplier. All selected items will be granted or applied when the badge is earned. (optional)",
  "award_points": "If points are a selected award, specify the number of points to apply when this badge is earned. (optional).",
  "points_multiplier": "If multiplier is a selected award, set a multiplier for points earned while this badge is active (e.g., 1.5x).",
  "recurring_frequency": "Enable the maintenance cycle, requiring the specified minimum points to be earned before the end of the period. (e.g., weekly, monthly).",
  "custom_interval": "Specify the NUMBER of days, week, months, etc. for Custom Frequency (e.g., 3 if you set 3 weeks). Only applies to Custom Frequency.",
  "custom_interval_unit": "Select the unit for the custom interval (e.g., days, weeks). Only applies to Custom Frequency.",
  "start_date": "Set the start date (optional).",
  "end_date": "Select the date for the end of the maintenance cycle. (optional).",
  "grace_period_days": "Specify the number of extra days after the end of the cycle kids to meet required points before demotion. (optional)."
}
```

---

## Constants & Defaults

**Source**: `const.py` lines 1209-1273

```python
# Badge icons
DEFAULT_BADGE_ICON: Final = "mdi:shield-star-outline"

# Target defaults
DEFAULT_BADGE_TARGET_TYPE: Final = "points"  # Not used by cumulative (always points)
DEFAULT_BADGE_TARGET_THRESHOLD_VALUE: Final = 50.0

# Maintenance defaults
DEFAULT_BADGE_MAINTENANCE_THRESHOLD: Final = 0  # 0 = no maintenance required

# Award defaults
DEFAULT_BADGE_AWARD_POINTS: Final = 0.0

# Reset schedule defaults
DEFAULT_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY = FREQUENCY_NONE  # "none"
DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_START_DATE: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_END_DATE: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: Final = 0

DEFAULT_BADGE_RESET_SCHEDULE = {
    DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: DEFAULT_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
    DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL,
    DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT,
    DATA_BADGE_RESET_SCHEDULE_START_DATE: DEFAULT_BADGE_RESET_SCHEDULE_START_DATE,
    DATA_BADGE_RESET_SCHEDULE_END_DATE: DEFAULT_BADGE_RESET_SCHEDULE_END_DATE,
    DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS,
}

DEFAULT_BADGE_TARGET = {
    "type": DEFAULT_BADGE_TARGET_TYPE,
    "value": DEFAULT_BADGE_TARGET_THRESHOLD_VALUE,
}
```

---

## Cumulative vs Periodic Badges

**Key differences to emphasize in documentation**:

| Feature                     | Cumulative Badges                                | Periodic/Daily Badges                                 |
| --------------------------- | ------------------------------------------------ | ----------------------------------------------------- |
| **Points tracked**          | ALL lifetime points from ALL sources             | Only points from tracked chores during cycle          |
| **Target type**             | Always lifetime points (no selector)             | Selector: points, chore count, streak types           |
| **Tracked chores**          | NOT included (counts everything)                 | REQUIRED field (which chores contribute)              |
| **Earning trigger**         | Automatic when lifetime points reach threshold   | End of cycle if target met                            |
| **Permanence**              | Once earned, badge is permanent                  | Re-earned each cycle (or lost if target not met)      |
| **Maintenance cycle**       | OPTIONAL (to keep multiplier active)             | MANDATORY (defines the badge period)                  |
| **Maintenance requirement** | Min points per cycle to keep multiplier          | Target must be met to retain/earn badge               |
| **Penalties**               | NOT supported                                    | Supported (applied if target not met)                 |
| **Use case**                | Long-term achievement (Bronze/Silver/Gold tiers) | Recurring performance (Weekly Star, Monthly Champion) |

---

## Configuration Flow Location

**Initial Setup** (config_flow.py):

1. Welcome → Points Label → Kids → Chores → **Badge Count**
2. For each badge: **`async_step_badges()`** calls **`async_add_badge_common()`**
3. Badge type defaults to `BADGE_TYPE_CUMULATIVE` during setup

**Post-Setup** (options_flow.py):

- Navigate to: Configure → Manage Badges → Add Badge → **Add Cumulative Badge**
- Step ID: `OPTIONS_FLOW_STEP_ADD_BADGE_CUMULATIVE` = `"add_badge_cumulative"`
- Calls same `async_add_badge_common()` with `badge_type=BADGE_TYPE_CUMULATIVE`

**Edit Badge** (options_flow.py):

- Navigate to: Configure → Manage Badges → Edit Badge → (select cumulative badge)
- Step ID: `OPTIONS_FLOW_STEP_EDIT_BADGE_CUMULATIVE` = `"edit_badge_cumulative"`

---

## Example Configuration

### Basic Cumulative Badge (Bronze Badge)

**User input**:

```yaml
badge_name: "Bronze Badge"
badge_description: "Earn 100 lifetime points"
badge_labels: ["beginner", "tier-1"]
icon: "mdi:shield-bronze"
threshold_value: 100.0
maintenance_rules: 0 # No maintenance
assigned_to: [] # All kids
award_items: ["multiplier"]
points_multiplier: 1.2
```

**Stored data**:

```python
{
    "name": "Bronze Badge",
    "description": "Earn 100 lifetime points",
    "labels": ["beginner", "tier-1"],
    "icon": "mdi:shield-bronze",
    "internal_id": "uuid-123",
    "type": "cumulative",
    "target": {
        "threshold_value": 100.0,
        "maintenance_rules": 0
    },
    "assigned_to": [],
    "awards": {
        "points_multiplier": 1.2
    },
    "reset_schedule": {
        "recurring_frequency": "none",
        "custom_interval": None,
        "custom_interval_unit": None,
        "start_date": None,
        "end_date": None,
        "grace_period_days": 0
    }
}
```

### Advanced Cumulative Badge with Maintenance (Gold Badge)

**User input**:

```yaml
badge_name: "Gold Badge"
badge_description: "Earn 500 lifetime points, maintain with 50 points/month"
badge_labels: ["advanced", "tier-3"]
icon: "mdi:shield-crown"
threshold_value: 500.0
maintenance_rules: 50 # Require 50 points per month
assigned_to: ["kid-uuid-1", "kid-uuid-2"] # Specific kids only
award_items: ["points", "multiplier", "rewards"]
award_points: 25.0
points_multiplier: 1.5
award_reward: ["reward-uuid-1"]
recurring_frequency: "monthly"
start_date: "2025-01-01"
grace_period_days: 3
```

**Stored data**:

```python
{
    "name": "Gold Badge",
    "description": "Earn 500 lifetime points, maintain with 50 points/month",
    "labels": ["advanced", "tier-3"],
    "icon": "mdi:shield-crown",
    "internal_id": "uuid-456",
    "type": "cumulative",
    "target": {
        "threshold_value": 500.0,
        "maintenance_rules": 50
    },
    "assigned_to": ["kid-uuid-1", "kid-uuid-2"],
    "awards": {
        "points": 25.0,
        "points_multiplier": 1.5,
        "rewards": ["reward-uuid-1"]
    },
    "reset_schedule": {
        "recurring_frequency": "monthly",
        "custom_interval": None,
        "custom_interval_unit": None,
        "start_date": "2025-01-01",
        "end_date": None,
        "grace_period_days": 3
    }
}
```

---

## System Behavior & Tracking

### Kid Badges Sensor

**Entity**: `sensor.kc_<kid>_badges` (formerly `sensor.kc_<kid>_highest_badge`)

**Purpose**: Single sensor per kid showing complete cumulative badge progress across all badge types.

**Key Attributes**:

- `current_badge_name`: Effective badge in use (reflects demotion if applicable)
- `current_badge_eid`: Entity ID of current badge sensor
- `highest_earned_badge_name`: Highest badge ever achieved (permanent, never removed)
- `next_higher_badge_name`: Next tier to earn
- `next_higher_badge_eid`: Entity ID of next badge sensor
- `next_lower_badge_name`: Badge kid drops to if maintenance not met
- `next_lower_badge_eid`: Entity ID of demotion badge sensor
- `points_to_next_badge`: Points needed to reach next tier
- `badge_status`: Current state - `"active"`, `"grace"`, or `"demoted"`
- `baseline_points`: Points from all completed maintenance cycles
- `cycle_points`: Points earned during current maintenance window
- `highest_badge_threshold_value`: Threshold of highest badge earned
- `award_count`: Number of times awards granted (increments each maintenance cycle completion)
- `last_awarded_date`: Most recent award date
- `all_earned_badges`: Comma-separated list of all badges earned
- `reset_schedule`: Current maintenance cycle settings
- `target`: Badge target configuration
- `awards`: Award items configuration
- `description`: Badge description
- `icon`: Badge icon

**Example Attributes**:

```python
{
    "purpose": "purpose_kid_badges",
    "kid_name": "Sarah",
    "labels": [],
    "all_earned_badges": "Bronze, Silver",
    "highest_badge_threshold_value": 500,
    "points_to_next_badge": 996,
    "current_badge_name": "Bronze",
    "current_badge_eid": "sensor.kc_bronze_badge",
    "highest_earned_badge_name": "Bronze",
    "next_higher_badge_name": "Silver",
    "next_higher_badge_eid": "sensor.kc_silver_badge",
    "next_lower_badge_name": None,
    "next_lower_badge_eid": None,
    "badge_status": "active",
    "last_awarded_date": "2025-11-18",
    "award_count": 1,
    "description": "A great start to building good habits!",
    "baseline_points": 0,
    "cycle_points": 1714,
    "reset_schedule": {
        "custom_interval": None,
        "custom_interval_unit": None,
        "end_date": None,
        "grace_period_days": 0,
        "recurring_frequency": "none",
        "start_date": None
    },
    "target": {
        "maintenance_rules": 0,
        "target_type": "points",
        "threshold_value": 500
    },
    "awards": {
        "award_items": ["multiplier"],
        "award_points": 0,
        "award_reward": "",
        "points_multiplier": 1.2
    },
    "icon": "mdi:medal-outline",
    "friendly_name": "Sarah (KidsChores) Badges"
}
```

### Badge Lifecycle

**Earning**:

1. Kid accumulates lifetime points (baseline + cycle_points)
2. When threshold reached → Badge awarded automatically
3. **Highest badge earned** recorded permanently
4. Awards granted (points, rewards, bonuses) if configured
5. Multiplier activates (if configured)

**Maintenance Cycle** (if configured):

1. Cycle begins based on recurring_frequency (weekly, monthly, quarterly, yearly)
2. Each kid's dates tracked independently based on when they earned badge
3. Kid must earn maintenance_rules points during cycle
4. **Success**: Cycle resets, award_count increments, awards granted again, badge_status: "active"
5. **Failure**:
   - If grace_period_days > 0: badge_status: "grace", extra days to meet goal
   - If grace not met or no grace: badge_status: "demoted", drop one level

**Demotion**:

- Kid drops **one level only** (highest badge earned unchanged)
- current_badge_name reflects next lower badge
- Multiplier switches to next lower badge's multiplier
- **Highest badge never removed**

**Requalification**:

- **Immediate** when kid earns enough points to meet maintenance goal
- No need to complete full maintenance cycle
- badge_status returns to "active"
- Multiplier returns to higher badge level

### Award Frequency

**Without maintenance** (`maintenance_rules: 0`):

- Awards granted **once** when badge first earned
- award_count = 1

**With maintenance** (`maintenance_rules > 0`):

- Awards granted when badge first earned
- Awards granted **each time maintenance cycle completes successfully**
- award_count increments each success
- **Purpose**: Keeps kids motivated during long progression (1000+ points between tiers)

### Supported Frequencies

**Predefined frequencies** (confirmed in const.py):

- `daily`, `weekly`, `monthly`, `quarterly`, `yearly`
- **Custom NOT supported** for cumulative badges

### Per-Kid Date Tracking

**Badge reset dates calculated per kid**:

- Each kid tracks own `maintenance_end_date` and `maintenance_grace_end_date`
- Calculated based on when they individually earned the badge
- NOT synchronized across all kids (independent timelines)

**Start/End date fields in badge config**:

- Optional templates for date calculation
- Actual dates computed per kid in `cumulative_badge_progress` dictionary

### Points Tracking

**Two-part system**:

- `baseline_points`: Sum of points from all **completed** maintenance cycles
- `cycle_points`: Points earned **during current maintenance window**
- **Lifetime points** = baseline_points + cycle_points

**Badge evaluation** uses lifetime points to determine current/next/previous badge levels.

---

## Documentation Notes

When writing the user-facing Badges.md guide:

1. **Emphasize the difference** between cumulative and periodic badges early
2. **Explain lifetime points** clearly (sum of all points ever earned)
3. **Maintenance cycles are optional** for cumulative badges (not mandatory)
4. **No tracked chores** - cumulative badges count ALL points from ALL sources
5. **Maintenance vs earning**: Maintenance keeps the multiplier active, not the badge itself
6. **Grace period** gives extra time to meet maintenance requirement
7. **Use case examples**:
   - Bronze/Silver/Gold tier system (no maintenance)
   - VIP Status badge (with monthly maintenance to keep multiplier)
   - Milestone badges (100, 500, 1000 points)
8. **Avoid confusing with periodic badges**: Cumulative = lifetime achievement, Periodic = recurring performance

---

## Files Referenced

- `custom_components/kidschores/config_flow.py` (lines 836-900) - Badge config flow entry
- `custom_components/kidschores/flow_helpers.py` (lines 1396-1550, 1957-2250) - Schema & data builders
- `custom_components/kidschores/const.py` (lines 270-420, 567-573, 1209-1273, 2988-3050) - Constants & defaults
- `custom_components/kidschores/translations/en.json` (lines 130-200, 488-530, 889-930) - UI labels

---

**Next Step**: Write Configuration:-Badges.md user guide focusing on cumulative badges, then create separate section for periodic badges.
