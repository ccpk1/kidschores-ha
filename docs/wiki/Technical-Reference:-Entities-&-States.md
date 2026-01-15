# Technical Reference: Entities & States

**Target Audience**: Developers, Automation Creators, Dashboard Builders
**Covers**: Entity types, key states, critical attributes, Jinja access patterns

---

## Entity Naming Convention

### Pattern Overview

All entities generally follow: `<platform>.kc_<kid_slug>_<purpose>` or `<platform>.kc_<kid_slug>_<desc>_<item>`

**Examples**:

```yaml
sensor.kc_sarah_points                    # Kid scope - Sarah's points
sensor.kc_sarah_chores                    # Kid scope - Sarah's chore stats
sensor.kc_sarah_chore_status_feed_dog     # Kid scope - Sarah's chore status
button.kc_sarah_chore_claim_feed_dog      # Kid scope - Sarah claims
button.kc_sarah_chore_approval_feed_dog   # Parent scope - Parent approves
sensor.kc_global_chore_status_feed_dog    # System scope - Shared chore global state
```

---

## Entity Types Overview

### Modern Sensors (Default - Enabled)

Dense attribute data instead of hundreds of separate entities.

**Per-Kid Sensors**:

- `sensor.kc_<kid>_chore_status_<chore>` (Per Kid / Per Chore) - Individual chore status (KidChoreStatusSensor)
- `sensor.kc_<kid>_points` (Per Kid) - Points balance and earnings (KidPointsSensor)
- `sensor.kc_<kid>_chores` (Per Kid) - Chore statistics aggregated (KidChoresSensor)
- `sensor.kc_<kid>_badges` (Per Kid) - Highest cumulative badge (KidBadgesSensor)
- `sensor.kc_<kid>_badge_status_<badge>` (Per Kid / Per Badge) - Non-cumulative badge progress (KidBadgeProgressSensor)
- `sensor.kc_<kid>_reward_status_<reward>` (Per Kid / Per Reward) - Reward status (KidRewardStatusSensor)
- `sensor.kc_<kid>_achievement_status_<achievement>` (Per Kid / Per Achievement) - Achievement progress (KidAchievementProgressSensor)
- `sensor.kc_<kid>_challenge_status_<challenge>` (Per Kid / Per Challenge) - Challenge progress (KidChallengeProgressSensor)
- `sensor.kc_<kid>_ui_dashboard_helper` (Per Kid) - Dashboard helper with pre-sorted entities (KidDashboardHelperSensor)

**System-Level Sensors**:

- `sensor.kc_<badge>_badge` (System / Per Badge) - System badge info (SystemBadgeSensor)
- `sensor.kc_global_chore_status_<chore>` (System / Per Shared Chore) - SHARED chore global state (SystemChoreSharedStateSensor)
- `sensor.kc_achievement_status_<achievement>` (System / Per Achievement) - System achievement info (SystemAchievementSensor)
- `sensor.kc_challenge_status_<challenge>` (System / Per Challenge) - System challenge info (SystemChallengeSensor)

### Button Entities

**Chore Buttons** (per kid, per chore):

- `button.kc_<kid>_chore_claim_<chore>` - Kid claims chore
- `button.kc_<kid>_chore_approval_<chore>` - Parent approves
- `button.kc_<kid>_chore_disapproval_<chore>` - Parent disapproves

**Reward Buttons** (per kid, per reward):

- `button.kc_<kid>_reward_claim_<reward>` - Kid redeems reward
- `button.kc_<kid>_reward_approval_<reward>` - Parent approves redemption
- `button.kc_<kid>_reward_disapproval_<reward>` - Parent disapproves redemption

**Bonus/Penalty Buttons** (per kid, per item):

- `button.kc_<kid>_bonus_<bonus>` - Parent applies bonus
- `button.kc_<kid>_penalty_<penalty>` - Parent applies penalty

**Parent Adjustment Button**:

- `button.kc_<kid>_points_add` - Parent manually adds points
- `button.kc_<kid>_points_subtract` - Parent manually subtracts points

### Extra Sensors (Optional - Disabled by Default)

Enable in integration options: "Show Extra Entities"

**Purpose**: Separate entities for metrics available as attributes in modern sensors.

**Pending Approvals** (system-wide):

- `sensor.kc_global_chore_pending_approvals` - Claimed chores awaiting approval
- `sensor.kc_global_reward_pending_approvals` - Redeemed rewards awaiting approval

**Chore Completions** (per kid):

- `sensor.kc_<kid>_chores_completed_total` - All-time completions
- `sensor.kc_<kid>_chores_completed_daily` - Today's completions
- `sensor.kc_<kid>_chores_completed_weekly` - This week's completions
- `sensor.kc_<kid>_chores_completed_monthly` - This month's completions

**Points Earned** (per kid):

- `sensor.kc_<kid>_points_earned_daily`
- `sensor.kc_<kid>_points_earned_weekly`
- `sensor.kc_<kid>_points_earned_monthly`
- `sensor.kc_<kid>_points_max_ever`

**Streaks**:

- `sensor.kc_<kid>_chores_highest_streak` - Highest chore completion streak

**Bonus/Penalty Counters** (per kid, per item):

- `sensor.kc_<kid>_penalties_applied_<penalty>` - Count of penalty applications
- `sensor.kc_<kid>_bonuses_applied_<bonus>` - Count of bonus applications

> [!NOTE]
> All Extra Sensor data is available in modern sensor attributes (`sensor.kc_<kid>_chores`, `sensor.kc_<kid>_points`, `sensor.kc_<kid>_ui_dashboard_helper`, etc.). Extra Sensors exist for users who prefer separate entities for specific metrics.

---

## Key Entity Details

### Chore Status Sensor (Per Kid / Per Chore)

**Entity**: `sensor.kc_<kid>_chore_status_<chore>`

**State Values**:

```yaml
pending              # Available for kid to claim
claimed              # Kid claimed, awaiting parent approval
approved             # Parent approved, points awarded
overdue              # Past due date, no claim yet
completed_by_other   # SHARED chore completed by another kid
```

**Critical Attributes**:

```yaml
# Identity & metadata
purpose: "chore_status"
kid_name: "Sarah"
chore_name: "Feed Dog"
chore_icon: "mdi:dog"
description: "Fill dog bowl with food and water"
assigned_kids: ["Sarah", "Alex"]
labels: ["Daily", "Pets"]

# Chore configuration
default_points: 10
completion_criteria: "independent" # or "shared_first", "shared_all"
approval_reset_type: "at_midnight" # or "at_midnight_multi", "at_due_date", etc.
recurring_frequency: "daily"
due_date: "2026-01-15T18:00:00+00:00"
applicable_days: ["mon", "tue", "wed", "thu", "fri"]
# For custom frequency:
custom_frequency_interval: 3 # Only present if recurring_frequency is "custom"
custom_frequency_unit: "days" # Only present if recurring_frequency is "custom"

# Statistics (all-time)
chore_points_earned: 110
chore_approvals_count: 11
chore_claims_count: 12
chore_disapproved_count: 1
chore_overdue_count: 1

# Statistics (today) - Only for multi-approval reset types
chore_approvals_today: 3 # Only if approval_reset_type allows multiple approvals

# Streaks
chore_current_streak: 4
chore_highest_streak: 7
chore_last_longest_streak_date: "2026-01-10"

# Timestamps
last_claimed: "2026-01-15T14:30:00+00:00"
last_approved: "2026-01-15T15:45:00+00:00"
last_disapproved: "2026-01-14T19:00:00+00:00"
last_overdue: "2026-01-13T23:59:59+00:00"

# SHARED chore tracking
global_state: "claimed" # Global state for SHARED chores
claimed_by: "kid_id_123" # Who claimed SHARED chore
completed_by: ["kid_id_123", "kid_id_456"] # SHARED_ALL completion list
approval_period_start: "2026-01-15T00:00:00+00:00" # Current approval period start

# UI integration
claim_button_eid: "button.kc_sarah_chore_claim_feed_dog"
approve_button_eid: "button.kc_sarah_chore_approval_feed_dog"
disapprove_button_eid: "button.kc_sarah_chore_disapproval_feed_dog"
can_claim: true
can_approve: false
```

**Jinja Access**:

```jinja2
# State
{{ states('sensor.kc_sarah_chore_status_feed_dog') }}
# Returns: "claimed"

# Simple attribute
{{ state_attr('sensor.kc_sarah_chore_status_feed_dog', 'default_points') }}
# Returns: 10

# Check if can claim
{{ state_attr('sensor.kc_sarah_chore_status_feed_dog', 'can_claim') }}
# Returns: true

# Conditional based on state
{% if states('sensor.kc_sarah_chore_status_feed_dog') == 'claimed' %}
  Chore is claimed - awaiting approval
{% endif %}
```

---

### Points Sensor (Per Kid)

**Entity**: `sensor.kc_<kid>_points`

**State**: Current points balance (integer)

**Key Attributes**:

```yaml
# Identity
purpose: "points"
kid_name: "Sarah"

# All point stats prefixed with point_stat_*
# Dynamically includes all fields from kid's point_stats data
# Common stats (actual keys vary based on data):
point_stat_points_earned_today: 25
point_stat_points_earned_week: 85
point_stat_points_earned_month: 150
point_stat_points_earned_year: 500
point_stat_points_earned_all_time: 2000

point_stat_points_spent_today: 10
point_stat_points_spent_week: 30
point_stat_points_spent_month: 100
point_stat_points_spent_year: 300
point_stat_points_spent_all_time: 800

point_stat_points_net_today: 15
point_stat_points_net_week: 55
point_stat_points_net_month: 50
point_stat_points_net_year: 200
point_stat_points_net_all_time: 1200

# Source breakdowns (nested dicts)
point_stat_points_by_source_today: { "chores": 20, "bonuses": 5 }
point_stat_points_by_source_week: { "chores": 70, "bonuses": 15 }
# ... and _month, _year, _all_time variants
```

**Jinja Access**:

```jinja2
# Current balance
{{ states('sensor.kc_sarah_points') | int }}
# Returns: 150

# Points earned today
{{ state_attr('sensor.kc_sarah_points', 'point_stat_points_earned_today') }}
# Returns: 25

# Points from chores this week
{{ state_attr('sensor.kc_sarah_points', 'point_stat_points_by_source_week')['chores'] }}
# Returns: 70
```

---

### Chores Sensor (Per Kid)

**Entity**: `sensor.kc_<kid>_chores`

**State**: Total chores completed all-time (integer)

**Key Attributes**:

```yaml
# Identity
purpose: "chores"
kid_name: "Sarah"

# All chore stats prefixed with chore_stat_*
# Dynamically includes all fields from kid's chore_stats data
# Actual keys depend on what stats are tracked (examples):
chore_stat_approved_all_time: 50
chore_stat_approved_today: 3
chore_stat_approved_week: 12
chore_stat_approved_month: 45

chore_stat_claimed_count: 52
chore_stat_overdue_count: 2
chore_stat_disapproved_count: 1
# Additional stats as available in chore_stats dict
# (sorted alphabetically when returned)
```

**Jinja Access**:

```jinja2
# Total completions
{{ states('sensor.kc_sarah_chores') | int }}

# Today's completions
{{ state_attr('sensor.kc_sarah_chores', 'chore_stat_approved_today') }}
```

---

### Dashboard Helper Sensor (Per Kid)

**Entity**: `sensor.kc_<kid>_ui_dashboard_helper`

**State**: Summary count string (e.g., `"chores:5 rewards:3 badges:10 bonuses:2 penalties:1 achievements:2 challenges:1"`)

**Purpose**: Pre-sorted entity lists with minimal attributes for dashboard rendering

**Key Attributes**:

```yaml
# Pre-sorted entity lists (minimal attributes for performance)
chores: [
    {
      eid: "sensor.kc_sarah_chore_status_feed_dog",
      name: "Feed Dog",
      status: "pending",
      labels: ["Daily", "Pets"],
      primary_group: "today", # or "this_week", "other"
      is_today_am: true, # or false, or null
      assigned_days: "Mon, Tue, Wed", # Human-readable
      assigned_days_raw: ["mon", "tue", "wed"], # Machine-readable
    },
  ]

rewards:
  [
    {
      eid: "sensor.kc_sarah_reward_status_ice_cream",
      name: "Ice Cream",
      status: "available",
      labels: ["Treats"],
      cost: 10,
      claims: 5,
      approvals: 4,
    },
  ]

badges: [...] # Badge entity IDs
bonuses: [...] # Bonus entity IDs
penalties: [...] # Penalty entity IDs
achievements: [...] # Achievement entity IDs
challenges: [...] # Challenge entity IDs

# UI helpers
dashboard_helpers:
  {
    date_helper_eid: "input_datetime.kc_sarah_chore_date",
    chore_select_eid: "select.kc_sarah_chore_selector",
  }

# Point buttons
point_button_add_eid: "button.kc_sarah_points_add"
point_button_subtract_eid: "button.kc_sarah_points_subtract"

# Pending parent approvals
pending_approvals:
  {
    chores:
      [
        {
          chore_id,
          chore_name,
          timestamp,
          approve_button_eid,
          disapprove_button_eid,
        },
      ],
    rewards:
      [
        {
          reward_id,
          reward_name,
          timestamp,
          approve_button_eid,
          disapprove_button_eid,
        },
      ],
  }

# Translation delegation
translation_sensor: "sensor.kc_ui_dashboard_lang_en" # Points to system translation sensor
```

**Usage**: Dashboard templates query this sensor once for all entity lists. Additional details fetched from individual entity sensors via `state_attr(chore.eid, 'attribute_name')`.

---

### Kid Badges Sensor (Per Kid)

**Entity**: `sensor.kc_<kid>_badges`

**State**: Name of highest cumulative badge earned (string)

**Purpose**: Tracks cumulative badge progression with maintenance requirements and next badge targets

**Key Attributes**:

```yaml
# Identity
purpose: "kid_badges"
kid_name: "Sarah"

# Current badge (highest earned or target)
current_badge_name: "Gold Star"
current_badge_eid: "sensor.kc_gold_star_badge" # SystemBadgeSensor entity

# Highest earned badge
highest_earned_badge_name: "Silver Star"
highest_badge_threshold_value: 500 # Points threshold for highest badge

# Next higher badge (goal)
next_higher_badge_name: "Platinum Star"
next_higher_badge_eid: "sensor.kc_platinum_star_badge"
points_to_next_badge: 150 # Points needed to reach next badge

# Next lower badge (previously earned)
next_lower_badge_name: "Bronze Star"
next_lower_badge_eid: "sensor.kc_bronze_star_badge"

# Badge progression
badge_status: "earned" # or "in_progress", "grace_period", "lost"
all_earned_badges: ["Bronze Star", "Silver Star"] # List of all earned badges
award_count: 3 # Times this badge was awarded
last_awarded: "2026-01-15T10:00:00+00:00"

# Maintenance tracking (for cumulative badges with maintenance)
baseline_points: 450 # Points at start of maintenance period
cycle_points: 75 # Points earned this maintenance cycle
maintenance_end_date: "2026-01-31T00:00:00+00:00"
grace_end_date: "2026-02-07T00:00:00+00:00"
maintenance_points_required: 100 # Points needed to maintain badge
points_to_maintenance: 25 # Points still needed this cycle

# Badge configuration (if present)
description: "Earn 500 total points"
labels: ["Achievement", "Points"]
target: { ... } # Badge target configuration
awards: { ... } # Badge award items
reset_schedule: { ... } # Badge reset configuration
```

**Jinja Access**:

```jinja2
# Current highest badge
{{ states('sensor.kc_sarah_badges') }}
# Returns: "Gold Star"

# Points needed for next badge
{{ state_attr('sensor.kc_sarah_badges', 'points_to_next_badge') }}
# Returns: 150

# Check maintenance status
{{ state_attr('sensor.kc_sarah_badges', 'badge_status') }}
# Returns: "earned"
```

---

### Kid Badge Status Sensor (Per Kid / Per Badge)

**Entity**: `sensor.kc_<kid>_badge_status_<badge>`

**State**: Progress percentage (0-100)

**Purpose**: Tracks individual non-cumulative badge progress (achievement, challenge, daily, periodic)

**Key Attributes**:

```yaml
# Identity
purpose: "badge_progress"
kid_name: "Sarah"
badge_name: "Weekly Warrior"

# Progress tracking
badge_progress_type: "daily" # or "achievement", "challenge", "periodic"
badge_progress_status: "in_progress" # or "earned", "expired"
overall_progress: 0.75 # 75% complete
criteria_met: 3 # Number of criteria/chores completed

# Target configuration
target_type: "chore_count" # What must be achieved
target_threshold_value: 4 # Number needed
tracked_chores: ["Dishes", "Homework", "Bedtime"] # Chores being tracked

# Time tracking
recurring_frequency: "daily" # or "weekly", "monthly", null
start_date: "2026-01-15T00:00:00+00:00"
end_date: "2026-01-15T23:59:59+00:00"
last_update_day: "2026-01-15"

# Award history
award_count: 5 # Times badge was earned
last_awarded: "2026-01-14T20:00:00+00:00"

# Metadata
description: "Complete 4 chores in one day"
```

**Jinja Access**:

```jinja2
# Current progress
{{ states('sensor.kc_sarah_badge_status_weekly_warrior') | int }}
# Returns: 75

# Chores completed
{{ state_attr('sensor.kc_sarah_badge_status_weekly_warrior', 'criteria_met') }}
# Returns: 3

# Check if earned
{% if states('sensor.kc_sarah_badge_status_weekly_warrior') | int == 100 %}
  Badge earned!
{% endif %}
```

---

### System Badge Sensor (System / Per Badge)

**Entity**: `sensor.kc_<badge>_badge`

**State**: Number of kids who have earned this badge (integer)

**Purpose**: System-wide badge configuration and metadata for all badge types

**Key Attributes**:

```yaml
# Identity
purpose: "badge"
badge_name: "Gold Star"
description: "Earn 500 total points"

# Badge configuration
badge_type: "cumulative" # or "achievement", "challenge", "daily", "periodic", "special"
labels: ["Achievement", "Points"]

# Assignment tracking
kids_assigned: ["Sarah", "Alex"] # Who can earn this badge
kids_earned: ["Sarah"] # Who has earned it

# Target configuration (varies by badge type)
target:
  target_type: "points"
  threshold_value: 500
  maintenance_rules: 100 # Points needed per maintenance period
  # ... other target fields

# Associated entities (if applicable)
associated_achievement: "achievement_id" # For achievement badges
associated_challenge: "challenge_id" # For challenge badges
required_chores: ["Dishes", "Homework"] # For chore-based badges

# Awards given when earned
badge_awards:
  - "Points: 50"
  - "Reward: Ice Cream"
  - "Bonus: Super Bonus"
  - "Multiplier: 1.5"

# Reset configuration (for recurring badges)
reset_schedule:
  recurring_frequency: "weekly"
  reset_day: "monday"
  # ... other reset fields

# Special occasion badges
occasion_type: "birthday" # For occasion-based badges
```

**Jinja Access**:

```jinja2
# Number of kids who earned badge
{{ states('sensor.kc_gold_star_badge') | int }}
# Returns: 1

# Check badge type
{{ state_attr('sensor.kc_gold_star_badge', 'badge_type') }}
# Returns: "cumulative"

# Get kids who earned it
{{ state_attr('sensor.kc_gold_star_badge', 'kids_earned') }}
# Returns: ["Sarah"]
```

---

### Global Chore Status Sensor (System / Per Shared Chore)

**Entity**: `sensor.kc_global_chore_status_<chore>`

**State**: Global state for SHARED chores (string - see values below)

**Purpose**: Tracks the overall state of SHARED chores across all assigned kids

**State Values**:

```yaml
pending            # Available for claiming
claimed            # Kid(s) have claimed (SHARED_FIRST: one kid; SHARED_ALL: all kids)
claimed-in-part    # SHARED_ALL: Some kids claimed, others pending
approved           # Completed and approved
approved-in-part   # SHARED_ALL: Some kids approved, others claimed/pending
overdue            # Past due date
```

**Key Attributes**:

```yaml
# Identity
purpose: "global_chore_status"
chore_name: "Family Cleanup"
chore_icon: "mdi:home-group"

# Configuration
completion_criteria: "SHARED_FIRST" # or "SHARED_ALL"
assigned_kids: ["Sarah", "Alex"]

# State tracking
global_state: "pending" # Current overall state
claimed_by: null # Kid who claimed (SHARED_FIRST only)
approved_by: null # Kid who got approved (SHARED_FIRST only)

# Timestamps
due_date: "2026-01-15T18:00:00+00:00" # When chore is due
```

**Jinja Access**:

```jinja2
# Check if SHARED chore is available
{{ states('sensor.kc_global_chore_status_family_cleanup') }}
# Returns: "pending"

# Get completion criteria
{{ state_attr('sensor.kc_global_chore_status_family_cleanup', 'completion_criteria') }}
# Returns: "SHARED_FIRST"

# Check who claimed it (SHARED_FIRST)
{{ state_attr('sensor.kc_global_chore_status_family_cleanup', 'claimed_by') }}
# Returns: "Sarah"
```

**Usage**: Essential for SHARED chores to display the overall state and determine availability across multiple kids.

---

## Common Automation Patterns

### Notify on Chore Claim

```yaml
automation:
  - alias: "Chore Claimed Notification"
    trigger:
      - platform: state
        entity_id: sensor.kc_sarah_chore_status_feed_dog
        to: "claimed"
    action:
      - service: notify.parent_phone
        data:
          message: "Sarah claimed 'Feed Dog'"
```

### Check Overdue Chores

```yaml
automation:
  - alias: "Overdue Chore Reminder"
    trigger:
      - platform: time
        at: "19:00:00"
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.kc_sarah_chores', 'chore_stat_overdue_count') > 0 }}
    action:
      - service: notify.sarah_device
        data:
          message: "You have {{ state_attr('sensor.kc_sarah_chores', 'chore_stat_overdue_count') }} overdue chores"
```

### Points Milestone

```yaml
automation:
  - alias: "Points Milestone Reached"
    trigger:
      - platform: numeric_state
        entity_id: sensor.kc_sarah_points
        above: 100
    action:
      - service: notify.family_group
        data:
          message: "Sarah reached 100 points!"
```

---

## Chore Global State Handling

Each chore has an individual **state per kid**, but there is also a **`global_state`** attribute that applies when a chore is assigned to multiple kids. The global state helps track progress and ensures proper handling of **independent** and **shared** chores.

### Scenario 1: Single Kid, Single Chore

For chores assigned to only one kid, the **global state always matches** the kid's individual chore state.

| **Chore State** | **Global State (`global_state`)** |
| --------------- | --------------------------------- |
| pending         | pending                           |
| claimed         | claimed                           |
| approved        | approved                          |
| overdue         | overdue                           |

### Scenario 2: Multiple Kids – Independent Completion

When a chore is assigned to multiple kids but completed **individually**, the **global state** is set to **independent** when kids have different chore states.

| **Kids' Chore States**                        | **Global State (`global_state`)** |
| --------------------------------------------- | --------------------------------- |
| All pending                                   | pending                           |
| All claimed                                   | claimed                           |
| All approved                                  | approved                          |
| All overdue                                   | overdue                           |
| Mixed states (including at least one overdue) | independent                       |

### Scenario 3: Shared Chore – Completion Required for All Assigned Kids

For **shared chores** (completion_criteria: SHARED_ALL), all assigned kids must complete the task before it is fully approved. To reflect **partial progress**, two additional states are introduced:

- **claimed-in-part** → At least one kid has claimed it, but others have not
- **approved-in-part** → At least one kid has received approval, but others have not

| **Kids' Chore States**                        | **Global State (`global_state`)** |
| --------------------------------------------- | --------------------------------- |
| All pending                                   | pending                           |
| At least one claimed, others pending          | claimed-in-part                   |
| All claimed                                   | claimed                           |
| At least one approved, others claimed/pending | approved-in-part                  |
| All approved                                  | approved                          |
| At least one overdue                          | overdue                           |

### Scenario 4: Shared First – First Kid to Complete Gets Credit

For **shared-first chores** (completion_criteria: SHARED_FIRST), only the **first kid** to complete and get approved receives credit. Once approved, the chore is completed for all assigned kids. Other kids see the chore as **completed_by_other**.

| **Kids' Chore States**                                      | **Global State (`global_state`)** |
| ----------------------------------------------------------- | --------------------------------- |
| All pending                                                 | pending                           |
| First kid claimed, others pending                           | claimed                           |
| First kid approved, others see completed_by_other           | approved                          |
| At least one overdue (before anyone claims)                 | overdue                           |
| First kid claimed after overdue                             | claimed                           |
| First kid approved after overdue, others completed_by_other | approved                          |

**Key Points**:

- Once the **first kid gets approved**, all other kids' individual states change to **completed_by_other**
- The **global state** reflects the state of the **first kid** who claimed and completed the chore
- If the chore becomes **overdue before anyone claims it**, the global state is **overdue** until someone claims it

### Jinja Access Patterns

```jinja2
# Check if SHARED chore is available
{% if state_attr('sensor.kc_sarah_chore_status_family_cleanup', 'global_state') == 'pending' %}
  Family Cleanup is available!
{% endif %}

# Check for partial completion (SHARED_ALL)
{% if state_attr('sensor.kc_sarah_chore_status_family_cleanup', 'global_state') == 'claimed-in-part' %}
  Some kids have claimed this chore
{% endif %}

# Check who claimed it (SHARED_FIRST)
{{ state_attr('sensor.kc_sarah_chore_status_family_cleanup', 'claimed_by') }}

# Handle independent chores with mixed states
{% if state_attr('sensor.kc_sarah_chore_status_dishes', 'global_state') == 'independent' %}
  Kids are at different stages - check individual states
{% endif %}
```

---

_Last updated: January 15, 2026 (v0.5.0)_
