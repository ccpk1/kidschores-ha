# Automation Example: Overdue Chore Penalties

**Version:** v0.5.0
**Difficulty:** Beginner
**Prerequisites**: None (uses KidsChores services only)

---

## Overview

Automatically apply point penalties when chores become overdue. Creates accountability and motivates timely completion without constant parent reminders.

> [!NOTE]
> **New in v0.5.0**: [Periodic Badges](Configuration:-Periodic-Badges.md) now include sophisticated penalty systems built-in. If you're tracking daily/weekly completion patterns, consider using Periodic Badges with Strict Mode and penalties instead of custom automations. This automation pattern is still useful for specific use cases not covered by badges.

**What You'll Learn**:

- State change trigger patterns (Pending → Overdue)
- Fixed vs variable penalty amounts
- Notification integration
- Grace period implementation

> [!TIP]
> Penalties work best when paired with positive reinforcement (bonuses for on-time completion). Balance stick with carrot!

---

## Why Use Overdue Penalties?

### Manual Reminder Challenges ❌

- **Parent fatigue**: Constantly nagging about overdue chores
- **Inconsistent consequences**: Forget to apply penalties
- **Delayed feedback**: Kid doesn't connect overdue chore to consequence
- **Negotiation battles**: Kid argues about penalty fairness

### Automated Penalty Benefits ✅

- **Immediate feedback**: Penalty applied moment chore becomes overdue
- **Consistency**: Same consequence every time (no favoritism)
- **Self-accountability**: Kids track due dates to avoid penalties
- **Parent neutrality**: "The system applied penalty, not me"

---

## How It Works

### Overdue Detection

**Chore State Sensors**:

- `sensor.kc_<kid>_chore_<chore_name>_state` reports current state
- State changes: `Pending` → `Overdue` when due date passes

**Overdue Binary Sensors**:

- `binary_sensor.kc_<kid>_chore_<chore_name>_overdue` turns `on` when overdue
- Turns `off` when chore approved or reset

### Penalty Application

**Service**: `kidschores.apply_penalty`

**Parameters**:

- `kid_name` (required): Which kid to penalize
- `amount` (required): Point deduction (positive integer)
- `reason` (optional): Description for penalty log

**Effect**: Immediately deducts points from kid's balance.

---

## Example 1: Fixed Penalty (Simple)

**Use Case**: Apply -10 points when any chore becomes overdue.

### Automation Code

```yaml
alias: "Penalty: Overdue Chore (-10 Points)"
description: "Deduct 10 points when chore becomes overdue"
triggers:
  # Trigger when chore state changes to Overdue
  - trigger: state
    entity_id:
      - sensor.kc_sarah_chore_make_bed_state # ⚠️ Replace with your chore state sensors
      - sensor.kc_sarah_chore_homework_state
      - sensor.kc_sarah_chore_dishes_state
      - sensor.kc_alex_chore_feed_dog_state
      - sensor.kc_alex_chore_clean_room_state
    to: "Overdue"
conditions: []
actions:
  # Extract kid name and chore name from entity ID
  - variables:
      entity_parts: "{{ trigger.entity_id.split('_') }}"
      kid_name: "{{ entity_parts[1] | title }}" # kc_sarah_chore... → Sarah
      chore_name: >-
        {% set parts = trigger.entity_id.split('_chore_')[1].split('_state')[0].split('_') %}
        {{ parts | join(' ') | title }}  # make_bed_state → Make Bed

  # Apply fixed penalty
  - action: kidschores.apply_penalty
    data:
      kid_name: "{{ kid_name }}"
      amount: 10 # ⚠️ Adjust penalty amount
      reason: "Overdue: {{ chore_name }}"

  # Optional: Notify kid
  - action: notify.mobile_app_{{ kid_name.lower() }}_phone # ⚠️ Replace with your notify service
    data:
      title: "⏰ Chore Overdue"
      message: >-
        {{ chore_name }} is overdue!
        Penalty: -10 points
        New balance: {{ states('sensor.kc_' ~ kid_name.lower() ~ '_points') }} points
mode: queued # Allow multiple simultaneous penalties
max: 10
```

### Configuration Changes Required

| Parameter              | What to Change                 | Example                                |
| ---------------------- | ------------------------------ | -------------------------------------- |
| `entity_id` (triggers) | Chore state sensors to monitor | `sensor.kc_sarah_chore_homework_state` |
| `amount`               | Penalty points (fixed value)   | `10` (or `5`, `20`, etc.)              |
| Notify service         | Your notification integration  | `notify.mobile_app_sarah_phone`        |

### Finding Chore State Sensors

1. **Developer Tools → States**
2. **Search**: `sensor.kc_` (all KidsChores sensors)
3. **Filter**: `_state` (state sensors only)
4. **Identify**: Match chore names to entity IDs
   - Example: "Homework" → `sensor.kc_sarah_chore_homework_state`

---

## Example 2: Variable Penalty (Based on Chore Value)

**Use Case**: Apply penalty proportional to chore points (20% of original points).

### Why Proportional Penalties?

**Fixed Penalty Issues**:

- -10 points harsh for low-value chore (5 points)
- -10 points trivial for high-value chore (50 points)

**Proportional Benefits**:

- Fair scaling (20% loss regardless of chore value)
- Matches chore importance

### Automation Code

```yaml
alias: "Penalty: Overdue Chore (20% of Points)"
description: "Deduct 20% of chore points when overdue"
triggers:
  - trigger: state
    entity_id:
      - sensor.kc_sarah_chore_make_bed_state
      - sensor.kc_sarah_chore_homework_state
      - sensor.kc_sarah_chore_dishes_state
    to: "Overdue"
conditions: []
actions:
  - variables:
      entity_parts: "{{ trigger.entity_id.split('_') }}"
      kid_name: "{{ entity_parts[1] | title }}"
      chore_name: >-
        {% set parts = trigger.entity_id.split('_chore_')[1].split('_state')[0].split('_') %}
        {{ parts | join(' ') | title }}

      # Get chore points from points sensor
      chore_points_sensor: >-
        sensor.kc_{{ kid_name.lower() }}_chore_{{ chore_name.lower().replace(' ', '_') }}_points
      chore_points: "{{ states(chore_points_sensor) | int(0) }}"
      # Calculate 20% penalty (minimum 1 point)
      penalty_amount: "{{ [1, (chore_points * 0.2) | round(0) | int] | max }}"

  # Apply proportional penalty
  - action: kidschores.apply_penalty
    data:
      kid_name: "{{ kid_name }}"
      amount: "{{ penalty_amount }}"
      reason: "Overdue: {{ chore_name }} (-{{ penalty_amount }} of {{ chore_points }} points)"

  # Notify with penalty breakdown
  - action: notify.mobile_app_{{ kid_name.lower() }}_phone
    data:
      title: "⏰ Chore Overdue"
      message: >-
        {{ chore_name }} is overdue!
        Chore value: {{ chore_points }} points
        Penalty (20%): -{{ penalty_amount }} points
        New balance: {{ states('sensor.kc_' ~ kid_name.lower() ~ '_points') }} points
mode: queued
max: 10
```

### Penalty Calculation Breakdown

```yaml
# Step 1: Get chore points
chore_points: "{{ states('sensor.kc_sarah_chore_homework_points') | int(0) }}"
# Example: 25 points

# Step 2: Calculate 20%
penalty_raw: "{{ chore_points * 0.2 }}"
# Example: 25 * 0.2 = 5.0

# Step 3: Round to integer
penalty_rounded: "{{ penalty_raw | round(0) | int }}"
# Example: 5

# Step 4: Ensure minimum 1 point (avoid 0 penalty)
penalty_amount: "{{ [1, penalty_rounded] | max }}"
# Example: max(1, 5) = 5
```

---

## Example 3: Grace Period (Delay Penalty Application)

**Use Case**: Give kid 30-minute grace period after due date before applying penalty. Accounts for minor timing issues or clock sync delays.

### Why Grace Periods?

**Without Grace**:

- Due at 6:00 PM, kid completes at 6:02 PM → penalty applied
- Harsh for minor delays
- Discourages near-completion attempts

**With Grace**:

- Due at 6:00 PM, penalty at 6:30 PM
- Kid has buffer to finish
- Reduces frustration

### Automation Code

```yaml
alias: "Penalty: Overdue Chore with Grace Period"
description: "Wait 30 minutes after overdue before applying penalty"
triggers:
  - trigger: state
    entity_id:
      - sensor.kc_sarah_chore_homework_state
      - sensor.kc_sarah_chore_dishes_state
    to: "Overdue"
conditions: []
actions:
  - variables:
      entity_parts: "{{ trigger.entity_id.split('_') }}"
      kid_name: "{{ entity_parts[1] | title }}"
      chore_name: >-
        {% set parts = trigger.entity_id.split('_chore_')[1].split('_state')[0].split('_') %}
        {{ parts | join(' ') | title }}

  # Grace period notification (warning)
  - action: notify.mobile_app_{{ kid_name.lower() }}_phone
    data:
      title: "⚠️ Chore Overdue - Grace Period"
      message: >-
        {{ chore_name }} is overdue!
        You have 30 minutes to complete before penalty (-10 points).

  # Wait 30 minutes
  - delay:
      minutes: 30 # ⚠️ Adjust grace period

  # Check if still overdue (kid might have completed during grace period)
  - if:
      - condition: state
        entity_id: "{{ trigger.entity_id }}"
        state: "Overdue"
    then:
      # Apply penalty (still overdue)
      - action: kidschores.apply_penalty
        data:
          kid_name: "{{ kid_name }}"
          amount: 10
          reason: "Overdue after grace period: {{ chore_name }}"

      # Final penalty notification
      - action: notify.mobile_app_{{ kid_name.lower() }}_phone
        data:
          title: "❌ Penalty Applied"
          message: >-
            {{ chore_name }} penalty: -10 points
            Complete chore to prevent future penalties.
            New balance: {{ states('sensor.kc_' ~ kid_name.lower() ~ '_points') }}
    else:
      # Kid completed during grace period (no penalty)
      - action: notify.mobile_app_{{ kid_name.lower() }}_phone
        data:
          title: "✅ Penalty Avoided"
          message: >-
            {{ chore_name }} completed during grace period!
            No penalty applied. Great job!
mode: queued
max: 5
```

### Grace Period Considerations

| Grace Period  | Best For                                     | Avoid For                      |
| ------------- | -------------------------------------------- | ------------------------------ |
| **5-15 min**  | Time-sensitive chores (bedtime, school prep) | Daily routine tasks            |
| **30-60 min** | Standard chores (homework, cleaning)         | Multi-day projects             |
| **2-4 hours** | Flexible chores (lawn mowing, car washing)   | Recurring high-frequency tasks |

---

## Example 4: Escalating Penalties (Multiple Overdue Days)

**Use Case**: Increase penalty for each day chore remains overdue. Motivates prompt correction.

### Escalation Strategy

- **Day 1**: -5 points (gentle reminder)
- **Day 2**: -10 points (moderate consequence)
- **Day 3+**: -20 points/day (serious consequence)

### Automation Code

```yaml
alias: "Penalty: Escalating Daily for Overdue Chores"
description: "Increase penalty each day chore remains overdue"
triggers:
  - trigger: time
    at: "09:00:00" # Check daily at 9 AM
conditions:
  # At least one overdue chore exists
  - condition: numeric_state
    entity_id: sensor.kc_sarah_overdue_chores_count
    above: 0
actions:
  # Check each chore's overdue duration
  - repeat:
      for_each:
        - sensor.kc_sarah_chore_homework_state
        - sensor.kc_sarah_chore_dishes_state
        - sensor.kc_sarah_chore_clean_room_state
      sequence:
        - if:
            - condition: state
              entity_id: "{{ repeat.item }}"
              state: "Overdue"
          then:
            - variables:
                chore_name: >-
                  {% set parts = repeat.item.split('_chore_')[1].split('_state')[0].split('_') %}
                  {{ parts | join(' ') | title }}
                due_date_sensor: >-
                  sensor.kc_sarah_chore_{{ chore_name.lower().replace(' ', '_') }}_due_date
                days_overdue: >-
                  {% set due = states(due_date_sensor) | as_datetime %}
                  {% if due %}
                    {{ (now() - due).days }}
                  {% else %}
                    0
                  {% endif %}

                # Escalating penalty calculation
                penalty_amount: >-
                  {% if days_overdue == 1 %}
                    5
                  {% elif days_overdue == 2 %}
                    10
                  {% else %}
                    20
                  {% endif %}

            # Apply escalating penalty
            - action: kidschores.apply_penalty
              data:
                kid_name: "Sarah"
                amount: "{{ penalty_amount }}"
                reason: "Day {{ days_overdue }} overdue: {{ chore_name }}"

            # Escalating notification
            - action: notify.mobile_app_sarah_phone
              data:
                title: "⏰ Day {{ days_overdue }} Overdue"
                message: >-
                  {{ chore_name }} penalty: -{{ penalty_amount }} points
                  {% if days_overdue >= 3 %}
                  ⚠️ Penalty increases each day!
                  {% endif %}
                  New balance: {{ states('sensor.kc_sarah_points') }}
mode: single
```

### Why Escalate?

**Flat Penalty Problem**:

- Kid might tolerate constant -10/day
- No motivation to complete quickly

**Escalating Penalty Benefits**:

- Creates urgency (penalty grows daily)
- Rewards prompt correction (lower penalty)
- Prevents chronic overdue chores

---

## Advanced Pattern: Penalty Forgiveness for First Offense

**Use Case**: Waive penalty for first overdue occurrence (per chore per week/month). Builds trust before enforcement.

### Automation Code

```yaml
alias: "Penalty: First Offense Forgiveness"
description: "Warn on first overdue, penalize on subsequent"
triggers:
  - trigger: state
    entity_id:
      - sensor.kc_sarah_chore_homework_state
    to: "Overdue"
conditions: []
actions:
  - variables:
      chore_name: "Homework" # ⚠️ Hardcoded for clarity (can extract from entity ID)
      kid_name: "Sarah"

      # Check penalty counter (requires input_number helper)
      penalty_counter: input_number.kc_sarah_homework_penalty_count
      offenses_this_week: "{{ states(penalty_counter) | int(0) }}"

  - choose:
      # First offense: Warning only
      - conditions:
          - condition: template
            value_template: "{{ offenses_this_week == 0 }}"
        sequence:
          # Increment counter
          - action: input_number.set_value
            target:
              entity_id: "{{ penalty_counter }}"
            data:
              value: 1

          # Warning notification
          - action: notify.mobile_app_sarah_phone
            data:
              title: "⚠️ First Overdue Warning"
              message: >-
                {{ chore_name }} is overdue.
                This is your first offense this week - no penalty.
                Next overdue will result in -10 points.

      # Subsequent offenses: Apply penalty
      - conditions:
          - condition: template
            value_template: "{{ offenses_this_week > 0 }}"
        sequence:
          # Increment counter
          - action: input_number.set_value
            target:
              entity_id: "{{ penalty_counter }}"
            data:
              value: "{{ offenses_this_week + 1 }}"

          # Apply penalty
          - action: kidschores.apply_penalty
            data:
              kid_name: "Sarah"
              amount: 10
              reason: "Repeat overdue: {{ chore_name }} (offense {{ offenses_this_week + 1 }})"

          # Penalty notification
          - action: notify.mobile_app_sarah_phone
            data:
              title: "❌ Penalty Applied"
              message: >-
                {{ chore_name }} penalty: -10 points
                (Offense {{ offenses_this_week + 1 }} this week)
                New balance: {{ states('sensor.kc_sarah_points') }}
mode: single
```

### Required Helper Setup

**Create Input Number Helper** (one per kid-chore pair):

1. **Settings → Devices & Services → Helpers**
2. **Add Helper → Number**
3. **Configuration**:
   - Name: `KidsChores Sarah Homework Penalty Count`
   - Entity ID: `input_number.kc_sarah_homework_penalty_count`
   - Minimum: `0`
   - Maximum: `100`
   - Step: `1`
   - Display mode: `box`

**Reset Counter Weekly**:

```yaml
alias: "Reset: Weekly Penalty Counters"
triggers:
  - trigger: time
    at: "00:00:00"
    weekday: mon # Reset every Monday
actions:
  - action: input_number.set_value
    target:
      entity_id:
        - input_number.kc_sarah_homework_penalty_count
        - input_number.kc_sarah_dishes_penalty_count
    data:
      value: 0
mode: single
```

---

## Debugging & Troubleshooting

### Issue: Penalty not applying

**Potential Causes**:

1. Chore not actually overdue (check due date)
2. Kid name mismatch (capitalization matters)
3. Automation disabled or not triggering

**Debugging Steps**:

1. **Verify Overdue State**:
   - Developer Tools → States
   - Find `sensor.kc_sarah_chore_homework_state`
   - Confirm state = `"Overdue"` (not "Claimed" or "Approved")

2. **Test Service Manually**:

   ```yaml
   # Developer Tools → Services
   action: kidschores.apply_penalty
   data:
     kid_name: "Sarah"
     amount: 10
     reason: "Test penalty"
   ```

   - If fails → kid name incorrect or service unavailable
   - If succeeds → automation trigger issue

3. **Check Automation Traces**:
   - Settings → Automations & Scenes → Select automation
   - Click "Traces" → View last run
   - Verify trigger fired when state changed to "Overdue"

### Issue: Penalty applied multiple times

**Cause**: Automation triggering on every state evaluation (not just change to Overdue).

**Solution**: Add `from` condition to ensure trigger only on change:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.kc_sarah_chore_homework_state
    to: "Overdue"
    from: # ⚠️ Add this
      - "Pending"
      - "Claimed"
```

### Issue: Penalty applied during grace period

**Cause**: Delay not waiting long enough or automation restarting.

**Solution**: Change mode to `single` (prevents restarts):

```yaml
mode: single # Completes full sequence before retriggering
```

### Issue: Notification not sending

**Cause**: Notify service entity ID incorrect or service unavailable.

**Debugging Steps**:

1. **Test Notification Manually**:

   ```yaml
   action: notify.mobile_app_sarah_phone
   data:
     message: "Test notification"
   ```

2. **Check Notify Service Name**:
   - Developer Tools → Services
   - Search `notify.`
   - Find correct service name (varies by mobile app)

---

## Best Practices

### Penalty Philosophy

**Fair and Predictable**:

- ✅ Clearly communicate penalty rules to kids
- ✅ Apply consistently (no exceptions without reason)
- ✅ Start with small penalties (adjust based on behavior)

**Avoid**:

- ❌ Excessive penalties (demotivates)
- ❌ Retroactive penalties (kid didn't know rule)
- ❌ Penalty without warning (surprise punishments)

### Penalty Amounts

| Chore Value   | Recommended Penalty | Reasoning                          |
| ------------- | ------------------- | ---------------------------------- |
| **5-10 pts**  | -2 to -5 points     | ~50% loss (significant but fair)   |
| **15-25 pts** | -5 to -10 points    | ~33% loss (motivating)             |
| **30-50 pts** | -10 to -20 points   | ~25% loss (serious consequence)    |
| **50+ pts**   | -20 to -30 points   | ~33% loss (scales with importance) |

**General Rule**: Penalty = 20-50% of chore value

### Balance with Rewards

**Punishment vs Reinforcement**:

- **Penalties alone**: Discouraging, focus on negative
- **Rewards alone**: No consequences for failure
- **Balanced approach**: Penalties for overdue + bonuses for on-time

**Positive Reinforcement Automation**:

```yaml
alias: "Bonus: On-Time Completion"
description: "Award bonus points for completing before due date"
triggers:
  - trigger: state
    entity_id: sensor.kc_sarah_chore_homework_state
    to: "Approved"
conditions:
  # Approved before due date
  - condition: template
    value_template: >-
      {% set due = states('sensor.kc_sarah_chore_homework_due_date') | as_datetime %}
      {{ due and now() < due }}
actions:
  - action: kidschores.apply_bonus
    data:
      kid_name: "Sarah"
      amount: 5 # Bonus for early completion
      reason: "On-time: Homework"
```

### Parent Communication

**Transparency**:

- Show kids penalty automation in dashboard
- Explain logic (due date → overdue → penalty)
- Review penalty history weekly

**Dashboard Card**:

```yaml
type: markdown
content: >-
  ## Overdue Penalty Rules

  - **Grace Period**: 30 minutes after due date
  - **First Penalty**: -10 points
  - **Daily Increase**: +5 points/day
  - **Maximum**: -20 points/day

  Complete chores on time to avoid penalties!
```

---

## Integration with Other KidsChores Features

### Completion Criteria Interaction

**Shared Chores**:

- Penalty applies to kid whose instance is overdue
- Other kids unaffected (Independent tracking)

**Shared First**:

- Penalty only applies if NO kid completes (entire chore overdue)
- Individual kid penalties inappropriate (race mechanic)

**Multi-Approval**:

- Each kid has separate due date (can be different)
- Penalty applies per kid independently

### Reset Overdue Interaction

**`kidschores.reset_overdue_chores` Service**:

- Resets chore to Pending/Claimed (depending on criteria)
- **Does NOT** reverse penalties already applied
- Use case: Manual forgiveness after discussion

**Penalty After Reset**:

```yaml
# Reset chore to Pending (parent forgives overdue)
- action: kidschores.reset_overdue_chores
  data:
    chore_name: "Homework"
    kid_name: "Sarah"

# Optionally refund penalty (manual bonus)
- action: kidschores.apply_bonus
  data:
    kid_name: "Sarah"
    amount: 10 # Refund previous penalty
    reason: "Forgiven: Homework overdue reset"
```

### Points Balance Protection

**Negative Balance Prevention**:

```yaml
# Check balance before applying penalty
conditions:
  - condition: template
    value_template: >-
      {{ states('sensor.kc_sarah_points') | int > 10 }}
      # Only penalize if balance > penalty amount
actions:
  - action: kidschores.apply_penalty
    data:
      kid_name: "Sarah"
      amount: 10
```

**Why Prevent Negative**:

- Negative balance demotivates ("I can never recover")
- Creates debt mentality
- Consider minimum balance (e.g., 0 points floor)

---

## Related Documentation

- **[Services Reference](Services:-Reference.md)** - `apply_penalty`, `reset_overdue_chores` service documentation
- **[Configuration: Points System](Configuration:-Points.md)** - Points balance, bonuses, penalties
- **[Chore Status and Recurrence Handling](Technical:-Chores.md)** - Overdue state logic
