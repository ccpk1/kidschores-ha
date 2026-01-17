# Automation Example: Calendar-Based Chore Scheduling

**Version:** v0.5.0
**Difficulty:** Advanced
**Prerequisites**: Home Assistant calendar integration (Google, Local, iCloud, etc.)

---

## Overview

Automatically set chore due dates based on calendar events. Perfect for tasks with variable schedules that change weekly or monthly (trash pickup days, lawn mowing based on weather, seasonal chores).

**What You'll Learn**:

- Calendar event lookup with date range
- Dynamic due date assignment using `kidschores.set_chore_due_date`
- Event name matching strategies
- Automation logging for debugging

> [!NOTE]
> This is **NOT** a built-in KidsChores feature but a custom integration pattern using Home Assistant's calendar services. Should work with any calendar integration.

---

## Why Use Calendar-Based Scheduling?

### Traditional Approach ❌

- Manually update chore due dates when schedules change
- Edit KidsChores configuration every time trash day shifts
- Remember to update automations for seasonal changes

### Calendar Approach ✅

- **Single Source of Truth**: Calendar controls chore schedules
- **Easy Updates**: Change calendar event → chore due date updates automatically
- **Recurring Events**: Leverage calendar recurrence for repeating chores
- **Family Coordination**: Everyone sees the schedule in shared calendar

---

## How It Works

### Core Logic

1. **Trigger**: Automation runs on schedule (daily, weekly, etc.)
2. **Lookup**: Searches calendar for next occurrence of specific event
3. **Extract**: Gets event start time
4. **Apply**: Sets chore due date using `kidschores.set_chore_due_date` service
5. **Log**: Records result for debugging

### Calendar Search Parameters

- **Date Range**: Configurable lookahead window (7, 14, 21, 30 days)
- **Event Name**: Exact or partial string matching
- **First Match**: Uses earliest event found in range

---

## Example 1: Trash Pickup (Variable Weekly Schedule)

**Use Case**: Trash pickup day varies weekly (Monday week 1, Tuesday week 2). Calendar event "Garbage Night" set by city/HOA.

### Physical Setup

1. **Add Calendar to Home Assistant**:
   - Settings → Devices & Services → Add Integration
   - Search for your calendar provider (Google, Local Calendar, etc.)
   - Authorize and configure

2. **Create Calendar Event**:
   - Event Title: **"Garbage Night"** (use unique name)
   - Recurrence: Weekly (adjust date each week as needed)
   - Set time: Evening before pickup (e.g., 8 PM night before)

3. **Create Chore in KidsChores**:
   - Chore Name: **"Take Out Trash"**
   - Assign to kid(s)
   - Set recurrence (optional - due date will override)

### Automation Code

```yaml
alias: "Calendar: Set Trash Chore Due Date"
description: "Update trash chore due date from calendar event"
triggers:
  - trigger: time
    at: "08:00:00" # Run daily at 8 AM
conditions: []
actions:
  # Step 1: Query calendar for upcoming events
  - target:
      entity_id: calendar.household_chores # ⚠️ Replace with your calendar entity
    data:
      start_date_time: "{{ now().isoformat() }}"
      end_date_time: "{{ (now() + timedelta(days=21)).isoformat() }}" # ⚠️ Adjust lookahead window
    response_variable: calendar_events
    action: calendar.get_events
    alias: "Fetch calendar events (next 21 days)"

  # Step 2: Find first event matching name and extract start time
  - variables:
      calendar_event_name: "Garbage Night" # ⚠️ Replace with your event name
      next_event_start_timestamp: >-
        {% set ns = namespace(event=None) %}
        {% for key, value in calendar_events.items() %}
          {% for event in value.events %}
            {% if calendar_event_name in event.summary %}
              {% set ns.event = event %}
              {% break %}
            {% endif %}
          {% endfor %}
        {% endfor %}
        {% if ns.event.start is defined and ns.event.start not in [none, 'unknown', 'unavailable'] %}
          {{ ns.event.start | as_datetime | as_timestamp }}
        {% else %}
          {{ none }}
        {% endif %}
    alias: "Extract event start time"

  # Step 3: Log result for debugging
  - action: logbook.log
    metadata: {}
    data:
      name: "Trash Chore Scheduler"
      entity_id: "{{ this.entity_id }}"
      message: >-
        {% if next_event_start_timestamp not in [none, 'unknown', 'unavailable'] %}
          Found event: {{ next_event_start_timestamp | timestamp_custom('%Y-%m-%d %H:%M:%S', true) }}
        {% else %}
          Event not found in next 21 days
        {% endif %}
    alias: "Log calendar lookup result"

  # Step 4: Set chore due date if event found
  - if:
      - condition: template
        value_template: "{{ next_event_start_timestamp not in [none, 'unknown', 'unavailable'] }}"
    then:
      - action: kidschores.set_chore_due_date
        metadata: {}
        data:
          chore_name: "Take Out Trash" # ⚠️ Replace with your chore name
          due_date: >-
            {{ next_event_start_timestamp | timestamp_custom('%Y-%m-%dT%H:%M:%S.000Z', true) }}
        alias: "Update chore due date"
mode: single
```

### Configuration Changes Required

| Parameter                    | What to Change                    | Example                          |
| ---------------------------- | --------------------------------- | -------------------------------- |
| `entity_id` (calendar query) | Your calendar entity ID           | `calendar.household_chores`      |
| `timedelta(days=21)`         | Lookahead window (days to search) | `7` for weekly, `30` for monthly |
| `calendar_event_name`        | Exact or partial event title      | `"Garbage Night"`                |
| `chore_name`                 | KidsChores chore name to update   | `"Take Out Trash"`               |
| Trigger `at`                 | When automation runs daily        | `"08:00:00"` (8 AM)              |

### Event Name Matching Tips

**Good Event Names** (Unique):

- ✅ "Garbage Night Chore"
- ✅ "Trash Pickup Reminder"
- ✅ "Weekly Waste Collection"

**Bad Event Names** (Too Generic):

- ❌ "Trash" (might match unrelated events)
- ❌ "Garbage" (could match "Take Garbage Out to Curb", "Garbage Disposal Repair")
- ❌ "Chore" (would match every chore-related event)

**Matching Logic**: Uses `in` operator (substring match)

```yaml
{ % if calendar_event_name in event.summary % } # Matches partial strings
```

---

## Example 2: Multi-Chore Calendar Integration

**Use Case**: Multiple chores scheduled via different calendar events (lawn mowing, pool cleaning, garden watering).

### Strategy: One Automation Per Chore

Create separate automations for each chore-calendar pair to maintain clarity and independent scheduling.

**Lawn Mowing Automation**:

```yaml
alias: "Calendar: Set Lawn Mowing Due Date"
triggers:
  - trigger: time
    at: "06:00:00" # Run at 6 AM
actions:
  - target:
      entity_id: calendar.household_chores
    data:
      start_date_time: "{{ now().isoformat() }}"
      end_date_time: "{{ (now() + timedelta(days=14)).isoformat() }}" # 2 weeks lookahead
    response_variable: calendar_events
    action: calendar.get_events

  - variables:
      calendar_event_name: "Mow Lawn Day"
      next_event_start_timestamp: >-
        {% set ns = namespace(event=None) %}
        {% for key, value in calendar_events.items() %}
          {% for event in value.events %}
            {% if calendar_event_name in event.summary %}
              {% set ns.event = event %}
              {% break %}
            {% endif %}
          {% endfor %}
        {% endfor %}
        {% if ns.event.start is defined and ns.event.start not in [none, 'unknown', 'unavailable'] %}
          {{ ns.event.start | as_datetime | as_timestamp }}
        {% else %}
          {{ none }}
        {% endif %}

  - if:
      - condition: template
        value_template: "{{ next_event_start_timestamp not in [none, 'unknown', 'unavailable'] }}"
    then:
      - action: kidschores.set_chore_due_date
        data:
          chore_name: "Mow Lawn"
          due_date: "{{ next_event_start_timestamp | timestamp_custom('%Y-%m-%dT%H:%M:%S.000Z', true) }}"
mode: single
```

**Pool Cleaning Automation**: (Same structure, different event name and chore)

```yaml
alias: "Calendar: Set Pool Cleaning Due Date"
triggers:
  - trigger: time
    at: "07:00:00"
actions:
  # ... (same calendar query structure)
  - variables:
      calendar_event_name: "Pool Service Day" # Different event
      # ... (same extraction logic)
  - if:
      # ... (same condition)
    then:
      - action: kidschores.set_chore_due_date
        data:
          chore_name: "Clean Pool" # Different chore
          due_date: "{{ next_event_start_timestamp | timestamp_custom('%Y-%m-%dT%H:%M:%S.000Z', true) }}"
mode: single
```

---

## Advanced: Trigger on Calendar Event Start

**Use Case**: Set chore due date exactly when calendar event starts (no daily polling).

**Limitation**: Requires calendar integration that supports event triggers (Google Calendar, Local Calendar).

### Automation with Event Trigger

```yaml
alias: "Calendar Event: Set Trash Due Date on Event Start"
description: "Triggered when 'Garbage Night' event starts"
triggers:
  - trigger: calendar
    event: start
    entity_id: calendar.household_chores
conditions:
  - condition: template
    value_template: "{{ 'Garbage Night' in trigger.calendar_event.summary }}"
actions:
  - action: kidschores.set_chore_due_date
    data:
      chore_name: "Take Out Trash"
      due_date: "{{ trigger.calendar_event.start }}"
  - action: logbook.log
    data:
      name: "Trash Chore Scheduler"
      message: "Set due date from calendar event: {{ trigger.calendar_event.start }}"
      entity_id: "{{ this.entity_id }}"
mode: single
```

**Advantages**:

- ✅ Instant updates (no polling delay)
- ✅ Simpler logic (no lookahead search)
- ✅ Automatic on event start

**Disadvantages**:

- ❌ Requires calendar integration with event triggers
- ❌ Only sets due date when event starts (not in advance)
- ❌ Can't set due date days before event

---

## Lookahead Window Guidelines

| Chore Frequency        | Recommended Lookahead | Reasoning                                    |
| ---------------------- | --------------------- | -------------------------------------------- |
| **Daily** (variable)   | 7 days                | Catch changes for upcoming week              |
| **Weekly**             | 14-21 days            | Handle schedule variations (holidays, etc.)  |
| **Bi-weekly**          | 30 days               | Ensure next occurrence found                 |
| **Monthly**            | 45-60 days            | Account for month-end variations             |
| **Seasonal/Irregular** | 90+ days              | Find next occurrence regardless of frequency |

**Why Not Search Further?**:

- Longer searches = more API calls (performance impact)
- Calendar integrations may have query limits
- Unnecessary for frequent tasks

**Trigger Frequency**:

- **Daily tasks**: Run automation once daily (morning)
- **Weekly tasks**: Run 2-3x per week
- **Monthly tasks**: Run weekly

---

## Debugging & Troubleshooting

### Issue: "Event not found" in logbook

**Potential Causes**:

1. Event name doesn't match (check spelling/capitalization)
2. Event outside lookahead window
3. Calendar not syncing with Home Assistant

**Debugging Steps**:

```yaml
# Add diagnostic logging before main logic
- action: logbook.log
  data:
    name: "Calendar Debug"
    message: >-
      Searching for: "{{ calendar_event_name }}"
      Calendar events found: {{ calendar_events | length }}
      Date range: {{ now().isoformat() }} to {{ (now() + timedelta(days=21)).isoformat() }}
```

### Issue: Chore due date not updating

**Potential Causes**:

1. Chore name doesn't match KidsChores configuration
2. Timestamp format incorrect
3. Service call failing silently

**Debugging Steps**:

1. Check Developer Tools → States → search for chore sensor
2. Verify chore name in KidsChores: Settings → Integrations → KidsChores → Configure
3. Test service manually in Developer Tools → Services:
   ```yaml
   action: kidschores.set_chore_due_date
   data:
     chore_name: "Take Out Trash"
     due_date: "2025-02-15T20:00:00.000Z"
   ```

### Issue: Wrong date format error

**Cause**: Timestamp not in ISO 8601 format with UTC timezone.

**Solution**: Use exact filter format:

```yaml
{
  {
    next_event_start_timestamp | timestamp_custom('%Y-%m-%dT%H:%M:%S.000Z',
    true),
  },
}
```

**Breakdown**:

- `%Y-%m-%d` = Date (2025-02-15)
- `T` = ISO separator
- `%H:%M:%S` = Time (20:00:00)
- `.000Z` = Milliseconds + UTC indicator
- `true` = Use UTC timezone

### Issue: Multiple events found, wrong one used

**Cause**: Event name matching multiple calendar entries.

**Solution**: Make event name more specific:

```yaml
# Too generic
calendar_event_name: "Trash"

# More specific
calendar_event_name: "Garbage Night Chore"

# Or use exact match instead of substring:
{% if event.summary == calendar_event_name %}  # Exact match only
```

---

## Best Practices

### Calendar Organization

**Separate Calendar for Chores** (Recommended):

- Create dedicated "Household Chores" calendar
- Prevents conflicts with personal/work events
- Easier to share with family

**Event Naming Convention**:

- Prefix chore events: "CHORE: Trash Night", "CHORE: Mow Lawn"
- Use consistent format for easy filtering
- Include location if relevant: "Trash (Curbside)", "Trash (Alley)"

### Automation Management

**Folder Organization**:

1. Create "Calendar Automations" folder in Home Assistant
2. Name pattern: "Calendar: [Chore Name] Scheduler"
3. Group related automations (all trash, all lawn, etc.)

**Documentation**:

- Comment automation YAML with event name and chore mappings
- Keep list of calendar-to-chore pairings in automation description
- Document trigger frequency and lookahead window

### Performance Considerations

**Calendar Query Limits**:

- Don't query calendar too frequently (respect API limits)
- Google Calendar: ~1000 requests/day/user
- Local Calendar: No strict limit but impacts database

**Optimal Trigger Schedule**:

```yaml
# Good: Daily for weekly chores
triggers:
  - trigger: time
    at: "08:00:00"

# Better: 3x weekly for weekly chores
triggers:
  - trigger: time
    at: "08:00:00"
    weekday: [mon, wed, fri]

# Avoid: Hourly (unnecessary API calls)
triggers:
  - trigger: time_pattern
    hours: "*"  # ❌ Too frequent
```

---

## Integration with KidsChores Features

### Shared Chores

**Limitation**: `kidschores.set_chore_due_date` cannot specify individual kids for Shared chores.

**Solution**: Calendar sets due date for entire shared chore (all assigned kids).

```yaml
# This works for Shared chores
- action: kidschores.set_chore_due_date
  data:
    chore_name: "Take Out Trash" # Shared by Sarah and Alex
    due_date: "{{ next_event_start_timestamp | timestamp_custom('%Y-%m-%dT%H:%M:%S.000Z', true) }}"
    # ⚠️ Do NOT include kid_name for Shared chores (will fail)
```

### Independent Chores

**Feature**: Set due dates per kid using `kid_name` parameter.

```yaml
# Different kids, same chore, different due dates
- action: kidschores.set_chore_due_date
  data:
    chore_name: "Clean Room"
    due_date: "2025-02-15T18:00:00.000Z"
    kid_name: "Sarah" # Only Sarah's due date updated

- action: kidschores.set_chore_due_date
  data:
    chore_name: "Clean Room"
    due_date: "2025-02-16T18:00:00.000Z"
    kid_name: "Alex" # Alex gets different due date
```

### One-Time vs Recurring Chores

**One-Time Chores**:

- Due date applies once
- After approval, due date clears automatically
- Perfect for calendar-based seasonal tasks

**Recurring Chores**:

- Due date overrides recurrence pattern temporarily
- After approval, chore resets per recurrence settings
- Calendar event can override next occurrence

---

## Related Documentation

- **[Services Reference](Services:-Reference.md)** - `set_chore_due_date` service documentation
- **[Chore Configuration Guide](Configuration:-Chores.md)** - Recurrence and scheduling settings
- **[Chore Advanced Features](Configuration:-Chores-Advanced.md)** - Shared chores, completion criteria
- **Home Assistant Calendar Integration** - [https://www.home-assistant.io/integrations/calendar/](https://www.home-assistant.io/integrations/calendar/)
