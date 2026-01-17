# Automation Example: NFC Tag Chore Claiming

**Version:** v0.5.0
**Difficulty:** Intermediate
**Prerequisites**: Home Assistant Companion App with NFC support

---

## Overview

Enable kids to quickly claim chores by scanning NFC tags placed near chore locations (pet feeding station, bedroom, kitchen). No dashboard interaction required - just tap the phone to the tag.

**What You'll Learn**:

- Setting up NFC helper sensor for user tracking
- Creating basic NFC chore claim automation
- Time-based chore selection (AM/PM chores)
- Logbook integration for accountability

> [!NOTE]
> This is **NOT** a built-in KidsChores feature but a tested integration pattern using Home Assistant's native NFC capabilities.

---

## Prerequisites Setup

### Required Components

1. **NFC tags** (NTAG213/215/216 recommended)
2. **Home Assistant Companion App** on kid's device
3. **User accounts** for each kid in Home Assistant

### Step 1: Find User IDs

Each Home Assistant user has a unique alphanumeric ID required for tracking:

1. Navigate to **Settings → People → Users**
2. Click each user to view their profile
3. Copy the **User ID** from the top of the dialog (long alphanumeric string)
4. Store these IDs - you'll need them for the helper sensor

**Example User ID**: `9999999953eb45019c0f3e0811111111`

---

### Step 2: Create NFC Helper Sensor

This sensor translates user IDs into readable names for logging and tracking.

**Add to `configuration.yaml` or template file**:

```yaml
template:
  - trigger:
      - trigger: event
        event_type: tag_scanned
    sensor:
      - name: NFC Last Scan By
        state: >
          {% set user_map = {
            "9999999953eb45019c0f3e0811111111": "Sarah",
            "9999999953eb45019c0f3e0822222222": "Alex",
            "9999999953eb45019c0f3e0833333333": "Mom",
            "9999999953eb45019c0f3e0844444444": "Dad"
          } %}
          {% set user_id = trigger.event.context.user_id %}
          {{ user_map.get(user_id, 'unknown') }}
```

**What This Does**:

- Listens for NFC tag scans
- Maps Home Assistant user IDs to friendly names
- Creates `sensor.nfc_last_scan_by` with the user's name

**Configuration Steps**:

1. Replace the User IDs with your actual Home Assistant user IDs
2. Replace the names with your kids' names (must match KidsChores kid names)
3. Save and restart Home Assistant
4. Verify sensor appears: Developer Tools → States → search "nfc_last_scan_by"

---

## Example 1: Basic Single-Chore NFC Tag

**Use Case**: Kid scans tag on litter box → chore automatically claimed.

**Physical Setup**:

1. Stick NFC tag on/near litter box
2. Register tag in Home Assistant Companion App
3. Note the **Tag ID** (you'll need this for the automation)

**Automation**:

```yaml
alias: "NFC: Clean Litter Box"
description: "Claim litter box chore when NFC tag scanned"
triggers:
  - tag_id: 059701cb-9096-40d3-be04-59c112345678 # ⚠️ Replace with your NFC tag ID
    trigger: tag
conditions: []
actions:
  - variables:
      claim_button: button.kc_sarah_chore_claim_clean_litter_pm # ⚠️ Replace with your button entity
  - action: button.press
    target:
      entity_id: "{{ claim_button }}"
  - wait_for_trigger:
      - trigger: state
        entity_id:
          - sensor.nfc_last_scan_by
    timeout:
      seconds: 5
  - action: logbook.log
    data:
      name: Clean Litter Box
      message: "Claimed by {{ states('sensor.nfc_last_scan_by') }}"
      entity_id: "{{ claim_button }}"
mode: single
```

### Configuration Changes Required

| Field                 | What to Change                                               | Example                                       |
| --------------------- | ------------------------------------------------------------ | --------------------------------------------- |
| `tag_id`              | Your NFC tag's unique ID (from Companion App registration)   | `059701cb-9096-40d3-be04-59c112345678`        |
| `claim_button`        | Button entity for the chore (check Developer Tools → States) | `button.kc_sarah_chore_claim_clean_litter_pm` |
| `name` in logbook.log | Friendly chore name for logbook                              | `Clean Litter Box`                            |

### How to Find Your Button Entity ID

1. Go to Developer Tools → States
2. Search for: `button.kc_<kid_name>_chore_claim_`
3. Find your chore in the list
4. Copy the full entity ID

**Workflow**:

1. Kid scans NFC tag
2. Automation presses claim button
3. Waits for NFC sensor to update (5 sec timeout)
4. Logs entry: "Clean Litter Box: Claimed by Sarah"

---

## Example 2: Time-Based AM/PM Chore Selection

**Use Case**: Single NFC tag on pet food station → claims AM or PM feeding chore based on time of day.

**Physical Setup**:

1. Place NFC tag near pet feeding station
2. Register tag in Companion App
3. Create separate AM and PM chores in KidsChores

**Automation**:

```yaml
alias: "NFC: Feed Cat (AM/PM Auto-Select)"
description: "Claim AM chore before noon, PM chore after noon"
triggers:
  - tag_id: 0b3b18f7-0c99-4f19-9d17-d114ccf87799 # ⚠️ Replace with your NFC tag ID
    trigger: tag
conditions: []
actions:
  - variables:
      claim_button: >-
        {% if 2 <= now().hour < 12 %}
          button.kc_sarah_chore_claim_feed_cat_am  # ⚠️ Replace with AM button entity
        {% else %}
          button.kc_sarah_chore_claim_feed_cat_pm  # ⚠️ Replace with PM button entity
        {% endif %}
  - action: button.press
    target:
      entity_id: "{{ claim_button }}"
  - wait_for_trigger:
      - trigger: state
        entity_id:
          - sensor.nfc_last_scan_by
    timeout:
      seconds: 5
  - action: logbook.log
    data:
      name: Feed Cat
      message: >-
        {{ "AM" if 2 <= now().hour < 12 else "PM" }} chore claimed by {{ states('sensor.nfc_last_scan_by') }}
      entity_id: "{{ claim_button }}"
mode: single
```

### Time Logic Breakdown

| Time Range             | Chore Claimed | Reason                                         |
| ---------------------- | ------------- | ---------------------------------------------- |
| **2:00 AM - 11:59 AM** | AM chore      | Morning feeding window                         |
| **12:00 PM - 1:59 AM** | PM chore      | Afternoon/evening feeding + overnight fallback |

**Why 2 AM Start?**: Prevents late-night scans (12 AM - 2 AM) from triggering morning chore. Adjust if needed:

```yaml
{ % if 6 <= now().hour < 12 % } # Stricter: only 6 AM - noon triggers AM chore
```

### Configuration Changes Required

| Field                                     | What to Change                | Example                                |
| ----------------------------------------- | ----------------------------- | -------------------------------------- |
| `tag_id`                                  | Your NFC tag ID               | `0b3b18f7-0c99-4f19-9d17-d114ccf87799` |
| `button.kc_sarah_chore_claim_feed_cat_am` | AM chore button entity        | Your specific button entity            |
| `button.kc_sarah_chore_claim_feed_cat_pm` | PM chore button entity        | Your specific button entity            |
| Time condition (`2 <= now().hour < 12`)   | Adjust AM/PM cutoff if needed | Change `2` to `6` for stricter morning |

---

## Advanced: Multi-Kid NFC Tag

**Use Case**: Shared chore (e.g., "First to Feed Dog") - any kid can scan to claim.

**Automation**:

```yaml
alias: "NFC: First to Feed Dog (Shared First)"
description: "Claim shared chore for whoever scans first"
triggers:
  - tag_id: your-tag-id-here
    trigger: tag
conditions: []
actions:
  # Get the kid name from NFC sensor
  - variables:
      kid_name: "{{ states('sensor.nfc_last_scan_by') }}"
      claim_button: "button.kc_{{ kid_name | lower }}_chore_claim_feed_dog"
  # Verify kid name is valid (not 'unknown')
  - condition: template
    value_template: "{{ kid_name not in ['unknown', 'unavailable', 'none'] }}"
  # Press claim button
  - action: button.press
    target:
      entity_id: "{{ claim_button }}"
  # Log the claim
  - action: logbook.log
    data:
      name: Feed Dog
      message: "Claimed by {{ kid_name }} (Shared First)"
      entity_id: "{{ claim_button }}"
mode: single
```

**Requirements**:

- NFC helper sensor configured with all kids' names
- Chore must be set to "Shared First" completion criteria
- Button entity IDs must follow pattern: `button.kc_{kid_name}_chore_claim_{chore_name}`

---

## Troubleshooting

### Issue: "Unknown user" in logbook

**Cause**: User ID not in NFC helper sensor map.

**Solution**:

1. Check if user scanned with correct device (must have Home Assistant app)
2. Verify user ID in helper sensor matches user's actual ID
3. Check for typos in user ID (alphanumeric, case-sensitive)

### Issue: Button press doesn't work

**Cause**: Button entity ID incorrect or chore not assigned to kid.

**Solution**:

1. Verify button exists: Developer Tools → States → search for button
2. Check kid is assigned to chore in KidsChores configuration
3. Ensure chore is in `pending` state (not already claimed/approved)

### Issue: Logbook entry missing

**Cause**: `wait_for_trigger` timeout or sensor not updating.

**Solution**:

1. Increase timeout to 10 seconds
2. Test NFC helper sensor manually: scan tag, check States view
3. Restart Home Assistant if sensor stuck

### Issue: Wrong chore claimed (AM/PM)

**Cause**: Time logic boundary issue or timezone mismatch.

**Solution**:

1. Check Home Assistant timezone: Settings → System → General
2. Adjust time boundaries in template (change `2` to `6` for stricter AM)
3. Test at boundary times (11:59 AM, 12:00 PM) to verify behavior

---

## Best Practices

### Physical Placement

- **Pet chores**: Stick tag on food container or feeding station
- **Bedroom chores**: Tag on door frame or nightstand
- **Kitchen chores**: Tag on dishwasher or sink cabinet

### NFC Tag Quality

- Use **NTAG213** or higher (NTAG215/216 for larger data)
- Avoid metal surfaces (blocks NFC signal)
- Test scan distance (kids may need to touch phone directly to tag)

### Automation Organization

- **Name pattern**: "NFC: [Chore Name]"
- **Group in folder**: Create "NFC Automations" folder in HA
- **Document Tag IDs**: Keep list of which tag controls which chore

### Security Considerations

- Kids must have Home Assistant Companion App installed
- User accounts required (can't scan as guest)
- NFC tags can be scanned by anyone - place in kid-accessible but not public areas

---

## Related Documentation

- **[Services Reference](Services:-Reference.md)** - Full service action documentation
- **[Chore Configuration Guide](Configuration:-Chores.md)** - Setting up chores
- **[Configuration: Kids and Parents](Configuration:-Kids-Parents.md)** - User account linking
- **Home Assistant NFC Documentation** - [https://www.home-assistant.io/integrations/tag/](https://www.home-assistant.io/integrations/tag/)
