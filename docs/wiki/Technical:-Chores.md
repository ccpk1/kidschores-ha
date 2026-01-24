# Chore Technical Reference

**Target Audience**: Developers, Automation Creators, Dashboard Builders
**Prerequisites**: Basic Home Assistant automation knowledge, Jinja2 templating
**Covers**: Entity reference, state mapping, Jinja templates, JSON attributes
**Version**: v0.5.0+ (Platinum Quality, Storage Architecture)
**Last Updated**: January 2026

> [!IMPORTANT]
> This reference reflects the **actual implementation** in sensor.py. All entity IDs, attribute names, and sensors documented here have been verified against the codebase. Previous versions contained hypothetical naming conventions that do not exist in the integration.

---

## Overview

This technical reference documents all chore-related entities, their states, attributes, and provides working Jinja2 templates for automations and dashboards.

**What You'll Find**:

- Complete entity naming structure
- Button entities for chore actions
- Sensor entities for chore status and stats
- Global state mapping for SHARED chores
- Working Jinja templates and JSON attribute access
- Common automation patterns

**Entity Naming Convention**:
All KidsChores entities follow the pattern: `<platform>.kc_<kid_slug>_<purpose>`

```yaml
Examples:
  button.kc_sarah_feed_dog_claim         # Sarah's claim button for "Feed Dog"
  button.kc_sarah_feed_dog_approve       # Parent approve button for Sarah's "Feed Dog"
  sensor.kc_sarah_points                 # Sarah's total points
  sensor.kc_sarah_ui_dashboard_helper    # Sarah's dashboard helper (chore lists, stats)
  sensor.kc_sarah_feed_dog               # Individual chore status sensor
```

---

## Button Entities

### Chore Action Buttons

**Per-Kid Chore Buttons**:

```yaml
# Claim buttons (kid presses to claim chore)
button.kc_<kid>_<chore>_claim
  state: "2026-01-15T14:30:00+00:00"  # Last pressed timestamp (HA core managed)
  attributes:
    friendly_name: "Sarah Feed Dog - Claim"
    icon: "mdi:hand-extended"
    device_class: null

# Approve buttons (parent presses to approve claimed chore)
button.kc_<kid>_<chore>_approve
  state: "2026-01-15T15:45:00+00:00"  # Last pressed timestamp (HA core managed)
  attributes:
    friendly_name: "Sarah Feed Dog - Approve"
    icon: "mdi:check-circle"
    device_class: null
```

> [!IMPORTANT] > **Button entities are stateless triggers** - They do not maintain persistent state beyond the last press timestamp (managed by Home Assistant core). Chore state is tracked by the chore sensor (`sensor.kc_<kid>_<chore>`), not the button entities.

### Bulk Action Buttons (v0.5.0+)

**Batch Operations**:

```yaml
# Approve all claimed chores for a specific kid
button.kc_<kid>_approve_all_claimed
  attributes:
    friendly_name: "Sarah - Approve All Claimed"
    icon: "mdi:check-all"

# Reset all chores for a kid (admin action)
button.kc_<kid>_reset_all_chores
  attributes:
    friendly_name: "Sarah - Reset All Chores"
    icon: "mdi:refresh"
```

---

## Sensor Entities

### Kid Status Sensors

**Points and Stats**:

```yaml
sensor.kc_<kid>_points
  state: 150                          # Total points earned
  attributes:
    friendly_name: "Sarah Points"
    icon: "mdi:star"
    unit_of_measurement: "points"
    point_stat_points_earned_today: 25
    point_stat_points_earned_week: 85
    point_stat_points_earned_month: 150
    point_stat_points_earned_all_time: 850
```

**Dashboard Helper** (Chore Lists and Stats):

> [!NOTE]
> The Dashboard Helper sensor (`sensor.kc_<kid>_ui_dashboard_helper`) provides pre-sorted chore lists and aggregated stats optimized for dashboard templates. Individual chore sensors provide detailed per-chore attributes.

```yaml
sensor.kc_<kid>_ui_dashboard_helper
  state: "<kid> has 3 chores available"  # Human-readable summary
  attributes:
    friendly_name: "Sarah Dashboard Helper"
    icon: "mdi:view-dashboard"
    chores:                           # Pre-sorted list of chores
      - eid: "sensor.kc_sarah_feed_dog"  # Entity ID for full attributes
        name: "Feed Dog"
        status: "pending"              # pending/claimed/approved/overdue
        labels: ["daily", "pets"]
        primary_group: "today"         # today/this_week/other
        is_today_am: true              # AM chore indicator
      - eid: "sensor.kc_sarah_make_bed"
        name: "Make Bed"
        status: "claimed"
        labels: ["morning"]
        primary_group: "today"
        is_today_am: true
    # Additional lists: rewards, badges, bonuses, penalties, achievements, challenges
```

### Individual Chore Sensors

**Per-Chore Status**:

```yaml
sensor.kc_<kid>_<chore>
  state: "claimed"                    # Current chore status
  attributes:
    friendly_name: "Sarah Feed Dog"
    icon: "mdi:dog"
    default_points: 10
    completion_criteria: "independent"  # independent/shared/shared_first
    recurring_frequency: "daily"        # daily/weekly/monthly/custom/none
    approval_reset_type: "at_due_date" # at_due_date/start_of_next_period
    due_date: "2026-01-15T18:00:00+00:00"
    last_claimed: "2026-01-15T14:30:00+00:00"
    last_approved: "2026-01-14T17:45:00+00:00"
    chore_approvals_count: 12
    global_state: "claimed"            # For SHARED chores only
    applicable_days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
```

### System Shared Chore Sensors

**Shared Chore Global State**:

For SHARED chores (shared, shared_first), a system-level sensor tracks the global state:

```yaml
sensor.kc_system_<chore>_shared_state
  state: "claimed"                    # Global state across all kids
  attributes:
    friendly_name: "Family Cleanup Shared State"
    icon: "mdi:account-group"
    chore_name: "Family Cleanup"
    completion_criteria: "shared_first"
    assigned_kids: ["Sarah", "Alex"]
    claimed_by: "Sarah"               # Who claimed (shared_first)
```

> [!TIP]
> System sensors use the prefix `sensor.kc_system_<name>` to distinguish from kid-specific sensors.

---

## Global State Reference

**For SHARED Chores** - Single state across all assigned kids:

| Global State      | Description                            | When It Occurs                   | Automation Use                              |
| ----------------- | -------------------------------------- | -------------------------------- | ------------------------------------------- |
| `pending`         | Available for any kid to claim         | Initial state, after reset       | Show chore in available lists               |
| `claimed`         | One kid has claimed, awaiting approval | Kid presses claim button         | Hide from other kids, show pending approval |
| `approved`        | Parent approved, points awarded        | Parent presses approve button    | Remove from lists, trigger rewards          |
| `overdue`         | Past due date, no claims               | Due date passed, no action       | Send reminders, show overdue status         |
| `claimed_overdue` | Claimed but past due date              | Kid claimed after due time       | Handle late completion scenarios            |
| `reset_pending`   | About to reset per schedule            | Reset mechanism about to trigger | Pre-reset notifications                     |

**For INDEPENDENT Chores** - Each kid has individual state (use regular `state` attribute).

---

## Jinja Templates

### Basic State Access

**Get Current Values**:

```jinja2
# Kid's total points
{{ states('sensor.kc_sarah_points') }}

# Dashboard helper summary
{{ states('sensor.kc_sarah_ui_dashboard_helper') }}

# Specific chore status
{{ states('sensor.kc_sarah_feed_dog') }}

# Check if chore is claimed
{{ states('sensor.kc_sarah_make_bed') == 'claimed' }}
```

### Attribute Access

**Simple Attributes**:

```jinja2
# Points earned today
{{ state_attr('sensor.kc_sarah_points', 'point_stat_points_earned_today') }}

# Due date for specific chore
{{ state_attr('sensor.kc_sarah_feed_dog', 'due_date') }}

# Chore completion criteria
{{ state_attr('sensor.kc_sarah_feed_dog', 'completion_criteria') }}

# Global state for SHARED chores
{{ state_attr('sensor.kc_sarah_clean_kitchen', 'global_state') }}
```

### JSON Nested Attributes

**Access Chore List Data**:

```jinja2
# Get all chores for Sarah from dashboard helper
{% set chores = state_attr('sensor.kc_sarah_ui_dashboard_helper', 'chores') %}
{% for chore in chores if chore.status == 'pending' %}
  - {{ chore.name }} ({{ state_attr(chore.eid, 'default_points') }} points)
{% endfor %}

# Find overdue chores
{% set chores = state_attr('sensor.kc_sarah_ui_dashboard_helper', 'chores') %}
{% set overdue = chores | selectattr('status', 'equalto', 'overdue') | list %}
{% if overdue|length > 0 %}
  Sarah has {{ overdue|length }} overdue chores
{% endif %}

# Check specific chore details from list
{% set chores = state_attr('sensor.kc_sarah_ui_dashboard_helper', 'chores') %}
{% set feed_dog = chores | selectattr('name', 'equalto', 'Feed Dog') | first %}
{% if feed_dog %}
  Feed Dog status: {{ feed_dog.status }}
  Points: {{ state_attr(feed_dog.eid, 'default_points') }}
  Due: {{ state_attr(feed_dog.eid, 'due_date') }}
{% endif %}
```

### Conditional Logic

**Status-Based Conditions**:

```jinja2
# Check if kid has any claimed chores
{% set chores = state_attr('sensor.kc_sarah_ui_dashboard_helper', 'chores') %}
{{ chores | selectattr('status', 'equalto', 'claimed') | list | length > 0 }}

# Check if any chores are overdue
{% set chores = state_attr('sensor.kc_sarah_ui_dashboard_helper', 'chores') %}
{{ chores | selectattr('status', 'equalto', 'overdue') | list | length > 0 }}

# Multi-kid comparison
{% set sarah_points = states('sensor.kc_sarah_points') | int %}
{% set alex_points = states('sensor.kc_alex_points') | int %}
{% if sarah_points > alex_points %}
  Sarah is leading with {{ sarah_points }} points!
{% endif %}

# Check if SHARED chore is available globally
{{ state_attr('sensor.kc_sarah_family_cleanup', 'global_state') == 'pending' }}
```

---

## Common Use Cases

### Dashboard Display

**Show Kid's Status**:

```yaml
# Card showing dashboard helper (summary view)
- type: entity
  entity: sensor.kc_sarah_ui_dashboard_helper
  name: "Sarah's Dashboard"
  icon: mdi:view-dashboard

# Template card showing points and badge status
- type: custom:mushroom-template-card
  primary: "Sarah: {{ states('sensor.kc_sarah_points') }} points"
  secondary: "{{ state_attr('sensor.kc_sarah_badges', 'current_badge_name') }} badge"
  icon: mdi:star
  icon_color: >
    {% set points = states('sensor.kc_sarah_points') | int %}
    {% if points > 100 %}
      green
    {% elif state_attr('sensor.kc_sarah_badges', 'award_count') > 2 %}
      orange
    {% else %}
      red
    {% endif %}
```

### Automation Triggers

**Chore Status Changes**:

```yaml
# Notify when chore is claimed
automation:
  - alias: "Chore Claimed Notification"
    trigger:
      - platform: state
        entity_id: sensor.kc_sarah_feed_dog
        to: "claimed"
    action:
      - service: notify.parent_phone
        data:
          title: "Chore Claimed"
          message: "Sarah claimed 'Feed Dog' - please approve when done"

# Remind about overdue chores
automation:
  - alias: "Overdue Chore Reminder"
    trigger:
      - platform: time
        at: "19:00:00"
    condition:
      - condition: template
        value_template: >
          {% set chores = state_attr('sensor.kc_sarah_ui_dashboard_helper', 'chores') %}
          {{ chores | selectattr('status', 'equalto', 'overdue') | list | length > 0 }}
    action:
      - service: notify.sarah_device
        data:
          title: "Overdue Chores"
          message: >
            {% set chores = state_attr('sensor.kc_sarah_ui_dashboard_helper', 'chores') %}
            {% set overdue = chores | selectattr('status', 'equalto', 'overdue') | list %}
            You have {{ overdue | length }} overdue chores. Please complete them!
```

### Point-Based Rewards

**Automatic Reward System**:

```yaml
# Weekly point milestone celebration
automation:
  - alias: "Weekly Points Milestone"
    trigger:
      - platform: state
        entity_id: sensor.kc_sarah_points
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.kc_sarah_points', 'point_stat_points_earned_week') | int(0) >= 100 }}
    action:
      - service: notify.family_group
        data:
          title: "🎉 Milestone Reached!"
          message: "Sarah earned 100+ points this week! Time for a reward!"
```

### SHARED Chore Management

**Handle SHARED Chore Completion**:

```yaml
# Notify all kids when SHARED chore becomes available
automation:
  - alias: "Shared Chore Available"
    trigger:
      - platform: state
        entity_id: sensor.kc_sarah_family_cleanup
        attribute: global_state
        to: "pending"
    action:
      - service: notify.all_kids
        data:
          title: "Family Chore Available"
          message: "Family Cleanup is ready - first to claim gets the points!"

# Hide SHARED chore from other kids when claimed
automation:
  - alias: "Update Shared Chore Visibility"
    trigger:
      - platform: state
        entity_id: sensor.kc_sarah_family_cleanup
        attribute: global_state
        to: "claimed"
    action:
      - service: automation.turn_off
        entity_id: automation.show_family_cleanup_to_alex
```

---

## Entity State Lifecycle

**Typical Chore Flow**:

```
1. pending → kid sees chore in available list
2. claimed → kid presses claim button, chore hidden from others (SHARED only)
3. approved → parent approves, points awarded, chore removed from lists
4. [reset cycle] → back to pending (per reset schedule)

Overdue variants:
- overdue → past due date, no claims
- claimed_overdue → claimed after due date
```

**Useful for Automations**:

- `pending` → Show in chore lists, send reminders
- `claimed` → Hide from other kids (SHARED), notify parents
- `approved` → Award points, trigger celebrations, remove from displays
- `overdue` → Send urgent reminders, change UI colors
- `claimed_overdue` → Handle late completion scenarios

---

_Last updated: January 15, 2026 (v0.5.0)_
