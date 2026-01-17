# KidsChores Services Reference

**Version:** v0.5.0
**Purpose:** User-friendly guide to KidsChores service actions for automations and scripts

---

## Service Overview

KidsChores provides 15+ service actions that allow you to automate workflows, integrate with external systems, and manage the chore economy programmatically. All services are available under the `kidschores` domain.

**Service Categories**:

- **Chore Workflow**: Claim, approve, disapprove chores
- **Rewards & Economy**: Redeem, approve rewards; apply bonuses/penalties
- **Scheduling**: Set due dates, skip chores, reset overdue items
- **Maintenance**: Reset chores, clear data, manage badges
- **Admin**: Shadow kid linking, system resets

> [!TIP]
> **Where to Use Services**: Services can be called from automations, scripts, dashboard button cards, or the Developer Tools → Services panel. They provide the same functionality as UI buttons but with additional parameters for automation.

---

## Chore Workflow Services

### `kidschores.claim_chore`

**Purpose**: Mark a chore as claimed by a kid.

**Parameters**:
| Parameter | Required | Description | Example |
| ------------ | -------- | -------------------------------- | ----------------- |
| `chore_name` | Yes | Name of chore to claim | `"Make Bed"` |
| `kid_name` | Yes | Name of kid claiming the chore | `"Sarah"` |

**Authorization**:

- **Dashboard Button**: If triggered by a user (e.g., Dashboard button press), the user must be linked to the Kid profile or be an Admin.
- **Automation Context**: Automations running in the background (System context) bypass this check and can claim chores freely.

**Example**:

```yaml
action: kidschores.claim_chore
data:
  chore_name: "Make Bed"
  kid_name: "Sarah"
```

**Use Cases**:

- NFC tag automation (kid taps tag to claim chore)
- Voice command integration ("Alexa, claim dishes")
- Scheduled auto-claim for routine tasks

---

### `kidschores.approve_chore`

**Purpose**: Approve a chore, award points, and advance the schedule.

**Parameters**:
| Parameter | Required | Description | Example |
| ---------------- | -------- | ------------------------------------------- | ----------------- |
| `chore_name` | Yes | Name of chore to approve | `"Make Bed"` |
| `kid_name` | Yes | Name of kid receiving approval | `"Sarah"` |
| `points_awarded` | No | Override default points for this completion | `5.0` |

**Authorization**: Parent/admin only.

**Points Override Feature**:

- If `points_awarded` is provided, it overrides the chore's default point value for this specific completion
- **Constraint**: Points override must be a positive number (> 0)
- **Use cases**: Award partial points for "good enough" work, or bonus points for exceptional speed
- Example: Chore configured for 10 points, but parent awards 5 points for rushed job

**One-Click Behavior**:

> [!WARNING]
> **One-Click Logic**: If the chore is in `pending` state (not yet claimed), this service will **automatically claim AND approve** it in one action. Be careful with automations that might trigger this unintentionally.

**Example**:

```yaml
# Standard approval
action: kidschores.approve_chore
data:
  chore_name: "Wash Dishes"
  kid_name: "Alex"

# Approval with point override
action: kidschores.approve_chore
data:
  chore_name: "Clean Room"
  kid_name: "Sarah"
  points_awarded: 7.5  # Partial credit
```

**Use Cases**:

- Automatic approval based on sensor data (motion sensor confirms room cleaned)
- Scheduled approval for recurring low-stakes chores
- Point adjustments for quality of work

---

### `kidschores.disapprove_chore`

**Purpose**: Reject a chore claim or completion, reverting state to `pending`.

**Parameters**:
| Parameter | Required | Description | Example |
| ------------ | -------- | ------------------------ | ----------------- |
| `chore_name` | Yes | Name of chore to reject | `"Make Bed"` |
| `kid_name` | Yes | Name of kid being rejected | `"Sarah"` |

**Authorization**: Parent/admin only.

**Shared First Reset**:

> [!IMPORTANT]
> **Shared First Chores**: If used on a "Shared First" chore where one kid won and others were locked out, this service resets **ALL** assigned kids back to `pending`. This re-opens the race for everyone, not just the kid being disapproved.

**Example**:

```yaml
action: kidschores.disapprove_chore
data:
  chore_name: "Take Out Trash"
  kid_name: "Alex"
```

**Use Cases**:

- Undo accidental approvals
- Re-open Shared First chores when winner's work is unsatisfactory
- Reset chores when quality standards not met

---

## Rewards & Economy Services

### `kidschores.redeem_reward`

**Purpose**: Kid requests to claim a reward (spends points).

**Parameters**:
| Parameter | Required | Description | Example |
| ------------- | -------- | ------------------------------ | ----------------- |
| `reward_name` | Yes | Name of reward to redeem | `"Ice Cream"` |
| `kid_name` | Yes | Name of kid redeeming reward | `"Sarah"` |

**Authorization**: Kid or admin.

**Balance Check**:

> [!WARNING]
> **Insufficient Points**: This service performs a balance check (`kid_points >= cost`). If the kid doesn't have enough points, the service call will **fail with an error** and stop automation execution. Handle this with try/catch in scripts if needed.

**Points Deduction**: Points are only deducted when parent approves the reward via `approve_reward`. Redeeming puts the reward in a pending state.

**Example**:

```yaml
action: kidschores.redeem_reward
data:
  reward_name: "Movie Night"
  kid_name: "Alex"
```

---

### `kidschores.approve_reward` / `kidschores.disapprove_reward`

**Purpose**: Parent approves or rejects a reward redemption.

**Parameters**:
| Parameter | Required | Description | Example |
| ------------- | -------- | ---------------------------------- | ----------------- |
| `reward_name` | Yes | Name of reward being approved/rejected | `"Ice Cream"` |
| `kid_name` | Yes | Name of kid whose reward is being processed | `"Sarah"` |

**Authorization**: Parent/admin only.

**Points Deduction**: Points are deducted from kid's balance **only on approval**. Disapproval cancels the redemption without affecting points.

**Example**:

```yaml
# Approve reward
action: kidschores.approve_reward
data:
  reward_name: "Extra Screen Time"
  kid_name: "Sarah"

# Reject reward
action: kidschores.disapprove_reward
data:
  reward_name: "Extra Screen Time"
  kid_name: "Sarah"
```

---

### `kidschores.apply_bonus` / `kidschores.apply_penalty`

**Purpose**: Manually adjust kid's points outside the chore system.

**Parameters**:
| Parameter | Required | Description | Example |
| ------------- | -------- | -------------------------------- | ----------------- |
| `kid_name` | Yes | Name of kid receiving adjustment | `"Alex"` |
| `points` | Yes | Number of points to add/subtract | `10` |
| `reason` | No | Description of why (for logging) | `"Found wallet"` |

**Logic**:

- `apply_bonus`: Adds points to kid's balance
- `apply_penalty`: Deducts points (converts positive input to negative internally)

**Metadata Tracking**: These actions log to `penalty_applies` and `bonus_applies` counters, visible in dashboard helpers and sensors.

**Example**:

```yaml
# Award bonus points
action: kidschores.apply_bonus
data:
  kid_name: "Sarah"
  points: 25
  reason: "Helped neighbor without being asked"

# Apply penalty
action: kidschores.apply_penalty
data:
  kid_name: "Alex"
  points: 15
  reason: "Broke house rule"
```

**Use Cases**:

- Good behavior rewards outside chore system
- Consequences for rule violations
- Special event bonuses (birthdays, holidays)

---

## Scheduling Services

### `kidschores.set_chore_due_date`

**Purpose**: Set or clear the due date for a chore dynamically.

**Parameters**:
| Parameter | Required | Description | Example |
| ------------ | -------- | ------------------------------------------------------ | ---------------------- |
| `chore_name` | Yes | Name of chore to update | `"Pick Up Sticks"` |
| `due_date` | No | ISO timestamp for new due date (leave empty to clear) | `"2025-03-01T23:59:00Z"` |
| `kid_name` | No | Kid name (Independent chores only) | `"Sarah"` |

**Independent vs Shared Chores**:

- **Independent Chores**: If `kid_name` is provided, only that kid's due date is updated. Other kids maintain their own schedules.
- **Shared Chores**: `kid_name` parameter is **not allowed**. Shared chores must have a global due date.

> [!WARNING]
> **Shared Chore Restriction**: Providing `kid_name` for a Shared or Shared First chore will cause the service to **fail with an error**. The system prevents per-kid scheduling for shared chores.

**Past Date Validation**: The service will reject due dates in the past with an error.

**Clearing Due Dates**: Send an empty `due_date` parameter to remove the deadline.

**Example**:

```yaml
# Set due date for Independent chore (specific kid)
action: kidschores.set_chore_due_date
data:
  chore_name: "Clean Room"
  due_date: "2025-02-15T18:00:00Z"
  kid_name: "Sarah"

# Set due date for Shared chore (all kids)
action: kidschores.set_chore_due_date
data:
  chore_name: "Take Out Trash"
  due_date: "2025-02-14T08:00:00Z"

# Clear due date
action: kidschores.set_chore_due_date
data:
  chore_name: "Pick Up Sticks"
```

**Use Cases**:

1. **One-Time Chores**: Assign due dates to non-recurring tasks like "Pick up sticks in yard"
2. **Calendar-Based Automation**: Sync chore due dates with calendar events (e.g., trash pickup day changes weekly)
3. **Dynamic Scheduling**: Adjust deadlines based on family schedule changes

**Interaction with Recurrence**:

- **No Recurrence**: Due date applies once. After approval, due date clears automatically.
- **With Recurrence**: Due date updates per normal recurrence pattern after completion.

**Interaction with States**:

- **Pending Chore**: Stays pending until due date reached
- **Approved Chore**: Remains approved until due date, then resets automatically

---

### `kidschores.skip_chore_due_date`

**Purpose**: Advance a recurring chore to its next scheduled slot without awarding points (skip today).

**Parameters**:
| Parameter | Required | Description | Example |
| ------------ | -------- | ------------------------------------------ | ----------------- |
| `chore_name` | Yes | Name of chore to skip | `"Make Bed"` |
| `kid_name` | No | Kid name (Independent chores only) | `"Alex"` |

**Requirement**: The chore must have a Recurring Frequency (Daily, Weekly, etc.). Skipping a one-time chore (Frequency: None) will fail or do nothing because there is no "next" date to calculate.

**Logic**:

1. Calculates `next_due` based on chore's Frequency + Applicable Days
2. Updates the due date to next occurrence
3. Resets state to `pending`

**Example**:

```yaml
action: kidschores.skip_chore_due_date
data:
  chore_name: "Daily Reading"
  kid_name: "Sarah"
```

**Use Cases**:

- "Skip today" dashboard buttons for sick days
- Holiday automation (skip all daily chores on Christmas)
- Temporary schedule adjustments

---

### `kidschores.reset_overdue_chores`

**Purpose**: Force overdue chores back to `pending` state and reschedule them to their next occurrence.

**Parameters**:
| Parameter | Required | Description | Example |
| ------------ | -------- | ------------------------------------------------ | ----------------- |
| `chore_id` | No | Internal ID of chore to reset | `"abc123"` |
| `chore_name` | No | Name of chore to reset (alternative to chore_id) | `"Wash Dishes"` |
| `kid_name` | No | Name of kid (filters reset to specific kid) | `"Alex"` |

**Flexible Targeting**:
| Parameters Provided | Behavior |
| --------------------------- | ------------------------------------------------- |
| `chore_name` only | Resets that chore for **all assigned kids** |
| `kid_name` only | Resets **all overdue chores** for that kid |
| `chore_name` + `kid_name` | Resets specific chore for specific kid |
| Neither (empty `data`) | **Global reset** of all overdue chores |

> [!IMPORTANT]
> **Recurring Chores Only**: This service only works on chores with a recurrence pattern. One-time or manual chores cannot be reset using this service.

**Completion Criteria Interaction**:

**Independent Chores**:

- Each kid has their own schedule and state
- Resetting one kid's chore does NOT affect other kids
- Example: Sarah's "Make Bed" is overdue, Alex's "Make Bed" stays untouched

**Shared Chores**:

- Single chore instance with global due date
- Resetting affects all assigned kids (resets to `pending` for everyone)
- Example: "Take Out Trash" shared by Sarah and Alex → reset puts both kids back to `pending`

**Shared First Chores**:

- Winner's completion locks out other kids
- If winner's chore is overdue and reset, **all kids become eligible again**
- Example: Alex won "First to Feed Dog" but went overdue → reset reopens race for Sarah and Alex

**Multi-Approval Chores**:

- Each kid must complete independently
- Resetting one kid's completion does NOT affect others
- Example: "Walk Dog Together" requires 2 approvals → resetting Sarah's portion leaves Alex's approval intact

**Example**:

```yaml
# Reset specific chore for all kids
action: kidschores.reset_overdue_chores
data:
  chore_name: "Wash Dishes"

# Reset all overdue chores for one kid
action: kidschores.reset_overdue_chores
data:
  kid_name: "Sarah"

# Reset specific chore for specific kid
action: kidschores.reset_overdue_chores
data:
  chore_name: "Make Bed"
  kid_name: "Alex"

# Global reset (all overdue chores)
action: kidschores.reset_overdue_chores
data: {}
```

**Use Cases**:

- Weekly automation to clear overdue items (fresh start Sundays)
- Dashboard button for parents to bulk-reset overdue chores
- Integration with notification system (reset after reminder sent)

---

## Maintenance Services

### `kidschores.reset_all_chores`

**Purpose**: Soft reset - set all chores to `pending` state without clearing history or points.

**Parameters**: None (no data required)

**Logic**:

- Resets ALL chores to `pending` state
- Resets `approval_period_start` to current time
- Does NOT clear points, history, or streak data

**Example**:

```yaml
action: kidschores.reset_all_chores
data: {}
```

**Use Cases**:

- Fix desynchronized schedule (chores stuck in wrong states)
- Fresh start after vacation
- Debugging automation issues

---

### `kidschores.reset_all_data`

**Purpose**: Factory reset - clear all progress data while keeping configuration intact.

**Parameters**: None (no data required)

> [!CAUTION]
> **Irreversible Action**: This service cannot be undone. All progress data will be permanently lost. A backup is created automatically before reset.

**What Gets Reset**:

- ✅ All chore statuses (claimed, approved, overdue → `pending`)
- ✅ All streaks and progress stats
- ✅ All earned points (balances → 0)
- ✅ All reward claims and history
- ✅ All approval records, penalties, and completions

**What Stays Intact**:

- ❌ Kids registered in the system
- ❌ Chore configurations (assignments, recurrence, points)
- ❌ Reward definitions
- ❌ Badge definitions

**Automatic Backup**: Before wiping data, the system creates a backup file: `kidschores_data_<timestamp>_reset`

**Process**:

1. Creates backup in `.storage/` directory
2. Wipes `.storage/kidschores_data` file
3. Cleans Entity Registry entries
4. Reloads integration

**Example**:

```yaml
action: kidschores.reset_all_data
data: {}
```

**Use Cases**:

- Start new tracking period (New Year's reset)
- Clean up after testing/experimentation
- Restructure reward system (update point labels, badge criteria)
- Remove trial data before official launch

---

### `kidschores.reset_penalties` / `kidschores.reset_bonuses` / `kidschores.reset_rewards`

**Purpose**: Reset counters (e.g., "Times Applied") without deleting definitions.

**Parameters**:
| Parameter | Required | Description | Example |
| ---------- | -------- | ------------------------------------- | ---------- |
| `kid_name` | No | Kid to reset (leave empty for all) | `"Sarah"` |

**Logic**: Resets metadata counters like "penalties applied this month" or "rewards redeemed this week". Does NOT delete the penalty/bonus/reward definitions themselves.

**Example**:

```yaml
# Reset all penalty counters for all kids
action: kidschores.reset_penalties
data: {}

# Reset bonus counters for specific kid
action: kidschores.reset_bonuses
data:
  kid_name: "Alex"
```

**Use Cases**:

- Monthly "Clean Slate" automation (reset counters on 1st of month)
- Tracking penalties/bonuses per period
- Dashboard metrics reset

---

### `kidschores.remove_awarded_badges`

**Purpose**: Revoke badges from kids.

**Parameters**:
| Parameter | Required | Description | Example |
| ------------ | -------- | ---------------------------------------- | ----------------- |
| `badge_name` | No | Specific badge to revoke | `"Gold Star"` |
| `kid_name` | No | Specific kid to revoke from | `"Sarah"` |

**Flexible Targeting**:
| Parameters Provided | Behavior |
| ------------------------- | --------------------------------------------- |
| `badge_name` + `kid_name` | Revokes one badge from one kid |
| `badge_name` only | Revokes that badge from **all kids** |
| `kid_name` only | Revokes **all badges** from that kid |

**Example**:

```yaml
# Revoke specific badge from specific kid
action: kidschores.remove_awarded_badges
data:
  badge_name: "Perfect Week"
  kid_name: "Alex"

# Revoke badge from all kids (badge expired)
action: kidschores.remove_awarded_badges
data:
  badge_name: "Summer Challenge"

# Revoke all badges from one kid
action: kidschores.remove_awarded_badges
data:
  kid_name: "Sarah"
```

**Use Cases**:

- Seasonal badge cleanup (remove expired time-limited badges)
- Demotion logic (kid lost streak, revoke badge)
- Reset kid's badge progress after misbehavior

---

## Admin Services

### `kidschores.manage_shadow_link`

**Purpose**: Link a Kid Profile to a Parent Profile, creating a "Shadow Kid" for parent control.

**Parameters**:
| Parameter | Required | Description | Example |
| --------- | -------- | ----------------------------------------------------------- | ---------- |
| `name` | Yes | Name that exists as **both** Parent and Kid (case-insensitive) | `"Mom"` |
| `action` | Yes | Operation: `link` or `unlink` | `"link"` |

**Name Matching Requirement**:

> [!IMPORTANT]
> **Exact Name Match**: The `name` parameter must match **BOTH** an existing Parent Name AND an existing Kid Name (case-insensitive). If names don't match, the link will fail.

**Unlinking Behavior**: When unlinking, the kid is renamed to `[Name]_unlinked` (e.g., `Mom_unlinked`) to preserve history rather than deleting data.

**Example**:

```yaml
# Link parent to kid profile
action: kidschores.manage_shadow_link
data:
  name: "Dad"
  action: "link"

# Unlink shadow kid
action: kidschores.manage_shadow_link
data:
  name: "Dad"
  action: "unlink"
```

**Use Cases**:

- Enable parents to test kid workflows
- Allow parents to claim/complete chores on behalf of kids
- Demonstration/training mode

---

## Service Integration Examples

> [!TIP]
> These are minimal examples for quick reference. For detailed step-by-step guides with prerequisites, troubleshooting, and best practices, see our comprehensive [Automation Example Guides](#automation-example-guides) below.

### Example 1: NFC Tag Chore Claiming

```yaml
automation:
  - alias: "Claim chore via NFC tag"
    trigger:
      - platform: tag
        tag_id: "bedroom_chore_tag"
    action:
      - action: kidschores.claim_chore
        data:
          chore_name: "Make Bed"
          kid_name: "{{ trigger.event.data.user_name }}"
```

**→ See**: [Automation Example: NFC Tag Chore Claiming](Examples:-NFC-Tags.md) - Complete guide with helper sensor setup, time-based selection, and multi-kid patterns

### Example 2: Calendar-Based Chore Scheduling

```yaml
automation:
  - alias: "Set trash chore due date from calendar"
    trigger:
      - platform: calendar
        event: start
        entity_id: calendar.trash_pickup
    action:
      - action: kidschores.set_chore_due_date
        data:
          chore_name: "Take Out Trash"
          due_date: "{{ trigger.calendar_event.start }}"
```

**→ See**: [Automation Example: Calendar-Based Chore Scheduling](Examples:-Calendar-Scheduling.md) - Detailed calendar integration patterns, lookahead windows, and multi-chore strategies

### Example 3: Automatic Overdue Penalty

```yaml
automation:
  - alias: "Apply penalty for overdue chores"
    trigger:
      - platform: state
        entity_id: sensor.kc_sarah_chores
        attribute: overdue_count
        to:
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.kc_sarah_chores', 'overdue_count') | int > 0 }}"
    action:
      - action: kidschores.apply_penalty
        data:
          kid_name: "Sarah"
          points: 5
          reason: "Overdue chore penalty"
```

**→ See**: [Automation Example: Overdue Chore Penalties](Examples:-Overdue-Penalties.md) - Variable penalties, grace periods, escalating patterns, and forgiveness strategies

> [!TIP]
> **Automatic chore approval** is built into v0.5.0 through multiple mechanisms (One-Click Logic, parent authorization, etc.). For custom approval workflows, use the `approve_chore` service directly in your automations.

---

## Automation Example Guides

Comprehensive step-by-step guides for common automation patterns:

- **[NFC Tag Chore Claiming](Examples:-NFC-Tags.md)** (~520 lines)
  - NFC tag setup with helper sensor configuration
  - Basic single-chore claiming pattern
  - Time-based AM/PM selection (pet feeding)
  - Multi-kid shared chore claiming
  - Troubleshooting (unknown user, button press fails, logbook issues)
  - Best practices (physical placement, tag quality, security)

- **[Calendar-Based Chore Scheduling](Examples:-Calendar-Scheduling.md)** (~660 lines)
  - Calendar integration setup (Google, Local, iCloud)
  - Variable weekly schedules (trash pickup example)
  - Multi-chore calendar patterns
  - Event trigger vs polling strategies
  - Lookahead window guidelines (7, 14, 21, 30+ days)
  - Debugging (event not found, date format errors)
  - Best practices (calendar organization, performance considerations)

- **[Overdue Chore Penalties](Examples:-Overdue-Penalties.md)** (~500 lines)
  - Fixed penalty amounts (simple -10 points pattern)
  - Variable penalties (20% of chore points calculation)
  - Grace period implementation (30-minute buffer)
  - Escalating daily penalties (increasing: -5, -10, -20)
  - First offense forgiveness (warning → penalty pattern)
  - Debugging (penalty not applying, multiple triggers)
  - Best practices (penalty philosophy, amounts, balance with rewards)
  - Integration with completion criteria and reset overdue service

---

## Troubleshooting

### Common Service Errors

**Error: `not_authorized_action`**

- **Cause**: Service requires kid/parent authorization, but automation context lacks proper user
- **Solution**: Use admin account for automation triggers, or ensure Home Assistant user account matches kid/parent profile

**Error: `chore_not_found`** / **`kid_not_found`**

- **Cause**: Name parameter doesn't match any existing entity
- **Solution**: Check spelling (case-insensitive), verify entity exists in Configuration

**Error: `insufficient_points`**

- **Cause**: Kid doesn't have enough points for reward redemption
- **Solution**: Check `sensor.kc_<kid>_points` state before calling `redeem_reward`

**Error: `date_in_past`**

- **Cause**: `set_chore_due_date` provided a past timestamp
- **Solution**: Ensure `due_date` parameter is in the future

**Error: `shared_chore_kid_error`**

- **Cause**: Attempted to provide `kid_name` for a Shared/Shared First chore
- **Solution**: Remove `kid_name` parameter for shared chores (they use global due dates)

---

## Related Documentation

- **[Chore Advanced Features](Configuration:-Chores-Advanced.md)** - Shared chores, multi-approval, completion criteria
- **[Configuration: Points System](Configuration:-Points.md)** - Point economy, manual adjustments
- **[Configuration: Rewards](Configuration:-Rewards.md)** - Reward redemption workflow
- **[Technical Reference: Services](Technical:-Services-Legacy.md)** - Service implementation details, edge cases
- **[Dashboard: Auto-Populating UI](Advanced:-Dashboard.md)** - Dashboard button integration
