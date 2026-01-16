# Configuration: Periodic Badges

**Version**: v0.5.0+
**Last Updated**: January 2026
**Tier**: Configuration Guide
**Related**: [Badge Gamification](Badge-Gamification.md) | [Badge Periodic Advanced](Badge-Periodic-Advanced.md) | [Badge Entities Detail](Technical-Reference:-Badge-Entities-Detail.md)

---

## Overview

Periodic badges are **mission-based badges** that track performance within specific time windows and reset automatically. Unlike cumulative badges (lifetime rank progression), periodic badges represent time-bound goals with clear success/failure outcomes.

**Key Characteristics**:

- ⏰ **Time-Bound**: Missions have defined windows (daily, weekly, monthly, custom)
- 🔄 **Auto-Reset**: Progress resets at end of each cycle
- 🎯 **Multiple Target Types**: 19 different ways to measure success (points, count, days, streaks)
- 🧹 **Tracked Chores**: Optional filter to count only specific chores
- ⚠️ **Penalties**: Auto-applied when mission fails
- 🚫 **No Multipliers**: Periodic badges don't provide ongoing point bonuses (cumulative only)

### Daily vs Periodic Badges

| Feature               | Daily Badges                   | Periodic Badges                   |
| --------------------- | ------------------------------ | --------------------------------- |
| **Reset Timing**      | Midnight (00:00) automatically | Custom schedule (weekly, monthly) |
| **Configuration**     | Simpler (no reset fields)      | Full reset schedule configuration |
| **Evaluation**        | Once per day at midnight       | At end of defined period          |
| **Use Case**          | Daily habits                   | Weekly/monthly goals              |
| **Threshold Example** | "Earn 50 points today"         | "Earn 200 points this week"       |

> [!TIP]
> Daily badges are perfect for building consistent habits. Periodic badges work better for cumulative goals that span multiple days.

---

## Creating Periodic Badges

### Config Flow (Initial Setup)

Periodic badges can be created during initial integration setup:

1. Navigate to **Settings** → **Devices & Services** → **Add Integration** → **KidsChores**
2. Complete kid setup
3. On the **Manage Badge** step, select **Add Periodic Badge** or **Add Daily Badge**
4. Configure badge settings (see Configuration Fields below)
5. Click **Submit** to create the badge

### Options Flow (Post-Setup Management)

After setup, manage badges through the integration's options:

1. Navigate to **Settings** → **Devices & Services** → **KidsChores**
2. Click **Configure** on your KidsChores integration
3. Select **Manage Badge** from the menu
4. Choose an action:
   - **Add Periodic Badge** → Create new periodic badge
   - **Add Daily Badge** → Create new daily badge
   - **Edit Badge** → Select badge to modify
   - **Delete Badge** → Remove badge permanently

---

## Configuration Fields

Periodic and daily badges share most configuration fields. Daily badges omit the Reset Schedule section (auto-reset at midnight).

### Basic Information

| Field                 | Required | Description                                             | Example                                   |
| --------------------- | -------- | ------------------------------------------------------- | ----------------------------------------- |
| **Badge Name**        | Yes      | Unique name for the badge. Displayed in UI.             | "Week of Clean"                           |
| **Badge Description** | No       | Detailed explanation of badge purpose or criteria.      | "Complete all assigned chores for 7 days" |
| **Labels**            | No       | Tags to categorize badges (for filtering/organization). | `["weekly", "routine"]`                   |
| **Icon**              | No       | Material Design Icon (mdi:xxx format).                  | `mdi:calendar-check`                      |

**Defaults**:

- Icon: `mdi:medal-outline`
- Description: Empty
- Labels: Empty list

---

### Target Settings

| Field               | Required | Description                                            | Example                          |
| ------------------- | -------- | ------------------------------------------------------ | -------------------------------- |
| **Target Type**     | Yes      | Type of goal to track (see Target Type Guide below).   | "Days Selected Chores Completed" |
| **Threshold Value** | Yes      | Number required to earn badge (varies by target type). | `5` (5 days meeting criteria)    |

**Target Type Determines Threshold Meaning**:

- **Points/Count**: Total points or chores needed
- **Days**: Number of days meeting criteria (can be non-consecutive)
- **Streaks**: Consecutive days meeting criteria

> [!IMPORTANT] > **Daily Badges + "Days" Target Types**: For daily badges using "Days" target types, the threshold should always be set to **1** (since a daily cycle only contains 1 day). Setting threshold > 1 will make the badge impossible to earn.

> [!WARNING] > **Strict Mode Target Types** (5 types ending with "No Overdue"): These types fail the daily criteria if ANY tracked chore goes overdue during evaluation. Depending on your target type, this may fail the entire badge:
>
> - **Streak Badges**: Streak resets to 0 immediately (badge fails for cycle)
> - **"All Days" Badges**: Badge invalidated for entire cycle (missed day = failed badge)
> - **"80% Days" Badges**: Lose credit for that day (but may recover with buffer days)

---

### Tracked Chores (Optional Filter)

| Field               | Required | Description                                                       | Example                            |
| ------------------- | -------- | ----------------------------------------------------------------- | ---------------------------------- |
| **Selected Chores** | No       | Chores that count toward this badge. Blank = all assigned chores. | `["chore_abc123", "chore_def456"]` |

**How Tracked Chores Work**:

- **Empty list** (default): Badge counts ALL chores assigned to kid
- **Selected chores**: Badge ONLY counts points/completions from listed chores
- **Common Use Cases**:
  - "Dishwasher Badge" → Only tracks dishwasher-related chores
  - "Morning Routine" → Only tracks bed-making and teeth-brushing
  - "Pet Care Mission" → Only tracks feeding dog, walking dog

> [!NOTE] > **Tracked Chores vs Assigned Kids**:
>
> - **Tracked Chores**: Filters which _tasks_ count toward the goal (what kid does)
> - **Assigned Kids**: Filters who _can see/earn_ the badge (who participates)
>
> Tracked chores are a **periodic/daily badge exclusive feature**. Cumulative badges always count all points from all sources.

---

### Assigned Kids (Required)

| Field           | Required | Description                                           | Example                                     |
| --------------- | -------- | ----------------------------------------------------- | ------------------------------------------- |
| **Assigned To** | **Yes**  | Kids who can earn this badge. Must select at least 1. | `["internal_id_sarah", "internal_id_alex"]` |

**Assignment Behavior**:

- **Mandatory Selection**: You MUST explicitly select which kids can earn this badge
- **No Global Default**: There is no "Apply to All" toggle — to make a badge available to all kids, you must manually select each kid
- **Un-Assignment**: If you edit a badge and uncheck a kid, the system immediately removes that badge's progress data from their profile

> [!IMPORTANT] > **Assignments are Required**: Unlike tracked chores (which default to "all chores" if blank), badge assignments require explicit selection. The integration will not allow you to create a badge without assigning it to at least one kid.

**Use Cases**:

- **Age-appropriate badges**: Assign harder challenges only to older kids
- **Themed badge sets**: Create personalized badge collections per kid
- **Individual contracts**: Target specific behavior changes for one kid

---

### Awards

| Field               | Required | Description                                                               | Example                                      |
| ------------------- | -------- | ------------------------------------------------------------------------- | -------------------------------------------- |
| **Award Items**     | No       | Types of awards granted on success (points, rewards, bonuses, penalties). | `["points", "rewards", "penalties"]`         |
| **Award Points**    | If ↑     | Points awarded when badge is earned (if "points" selected).               | `50`                                         |
| **Award Rewards**   | If ↑     | Rewards granted when badge is earned (if "rewards" selected).             | `["internal_id_treat", "internal_id_movie"]` |
| **Award Bonuses**   | If ↑     | Bonuses granted when badge is earned (if "bonuses" selected).             | `["internal_id_bonus_chore_skip"]`           |
| **Award Penalties** | If ↑     | Penalties applied when badge is NOT earned (if "penalties" selected).     | `["internal_id_penalty_lost_privilege"]`     |

**How Penalties Work**:

- Penalties are **auto-applied when badge fails** (not earned by end date/reset time)
- Example: "Perfect Attendance" badge with `-10 points` penalty → If kid misses goal, penalty applies automatically
- Use for accountability contracts ("No Sass Contract" with privilege loss)

> [!CAUTION]
> Penalties can frustrate kids if overused. Balance consequences with achievable goals. See [Badge Periodic Advanced](Badge-Periodic-Advanced.md#contract-penalty-patterns) for best practices.

---

### Reset Schedule (Periodic Badges Only)

Daily badges omit this section (auto-reset at midnight).

| Field                    | Required | Description                                                                 | Example               |
| ------------------------ | -------- | --------------------------------------------------------------------------- | --------------------- |
| **Recurring Frequency**  | Yes      | How often badge resets (daily, weekly, monthly, quarterly, yearly, custom). | `weekly`              |
| **Custom Interval**      | If ↑     | Number of units for custom frequency (e.g., 3 for "every 3 weeks").         | `3`                   |
| **Custom Interval Unit** | If ↑     | Unit for custom interval (days, weeks, months).                             | `weeks`               |
| **Start Date**           | No       | When badge tracking begins. Blank = calculated automatically per kid.       | `2026-01-06` (Monday) |
| **End Date**             | No       | When badge tracking stops permanently. Blank = continues indefinitely.      | `2026-06-30`          |

**Reset Schedule Examples**:

- **Weekly**: `recurring_frequency: weekly` → Resets every Monday
- **Monthly**: `recurring_frequency: monthly` → Resets 1st of each month
- **Custom (2 weeks)**: `recurring_frequency: custom, custom_interval: 2, custom_interval_unit: weeks`
- **Limited Time**: Set `end_date` to create finite mission (e.g., summer challenge)

---

## Target Type Guide

Periodic and daily badges support **19 different target types** organized into 5 categories:

### 1. Points-Based (2 types)

| Target Type                     | Tracks                             | Example                          |
| ------------------------------- | ---------------------------------- | -------------------------------- |
| **Points Earned**               | Total points from ALL sources      | "Earn 100 points this week"      |
| **Points Earned (From Chores)** | Points ONLY from chore completions | "Earn 50 chore points this week" |

**When to Use**:

- Points Earned: Simple weekly/monthly point goals
- Points Earned (From Chores): Reward chore work specifically (exclude bonus manipulation)

---

### 2. Count-Based (1 type)

| Target Type          | Tracks                            | Example                        |
| -------------------- | --------------------------------- | ------------------------------ |
| **Chores Completed** | Total number of chore completions | "Complete 20 chores this week" |

**When to Use**:

- Volume challenges ("Chore-a-thon")
- Building work habits (quantity over perfection)

---

### 3. Days-Based (9 types)

**Concept**: Check if criteria was met on X number of days (can be non-consecutive).

| Target Type                                         | Tracks                                           | Strict Mode |
| --------------------------------------------------- | ------------------------------------------------ | ----------- |
| **Days Selected Chores Completed**                  | Days where 100% of tracked chores were completed | No          |
| **Days 80% of Selected Chores Completed**           | Days where 80%+ of tracked chores were completed | No          |
| **Days Selected Chores Completed (No Overdue)**     | Days where 100% completed AND no overdue         | **Yes**     |
| **Days Selected Due Chores Completed**              | Days where all due chores were completed         | No          |
| **Days 80% of Selected Due Chores Completed**       | Days where 80%+ of due chores were completed     | No          |
| **Days Selected Due Chores Completed (No Overdue)** | Days where all due chores completed on time      | **Yes**     |
| **Days Minimum 3 Chores Completed**                 | Days where at least 3 chores completed           | No          |
| **Days Minimum 5 Chores Completed**                 | Days where at least 5 chores completed           | No          |
| **Days Minimum 7 Chores Completed**                 | Days where at least 7 chores completed           | No          |

**When to Use**:

- 100% completion: Perfectionist goals ("Complete everything 5 days this week")
- 80% completion: Flexible goals (allows occasional misses)
- Minimum daily: Consistency goals ("Do at least 3 chores every day")

> [!WARNING] > **Strict Mode** ("No Overdue" types): Badge fails if ANY tracked chore goes overdue during the cycle, even if you meet the day count. Use for accountability contracts only!

---

### 4. Streak-Based (7 types)

**Concept**: Require CONSECUTIVE days meeting criteria (no gaps allowed).

| Target Type                                            | Tracks                                   | Strict Mode |
| ------------------------------------------------------ | ---------------------------------------- | ----------- |
| **Streak: Selected Chores Completed**                  | Consecutive days, 100% completion        | No          |
| **Streak: 80% of Selected Chores Completed**           | Consecutive days, 80%+ completion        | No          |
| **Streak: Selected Chores Completed (No Overdue)**     | Consecutive days, 100% on time           | **Yes**     |
| **Streak: 80% of Selected Due Chores Completed**       | Consecutive days, 80%+ due chores        | No          |
| **Streak: Selected Due Chores Completed (No Overdue)** | Consecutive days, all due chores on time | **Yes**     |

**When to Use**:

- Building daily habits ("7-day perfect routine")
- Accountability challenges (no breaks allowed)
- Momentum-based rewards

> [!CAUTION]
> Streaks reset to 0 if criteria not met on any single day. Use 80% types for forgiving streaks.

---

## Special Occasion Badges

**Purpose**: Short-term buffs or gifts (Birthdays, Holidays) that repeat annually or on a custom schedule.

**Key Characteristics**:

- ⏰ **Active Window**: Badge is only earnable from 00:00 to 23:59 on the specific `start_date`
- 🎯 **Target**: Hardcoded to 1 Chore — completing ANY assigned chore on that day earns the badge
- 🔄 **Recurrence**: When the date passes, the system automatically calculates the next occurrence based on the Frequency (e.g., Yearly) and moves both `start_date` and `end_date` forward
- 💤 **Inactive State**: Badge stays in the system but remains inactive until the next occurrence date arrives

**Common Use Cases**:

- **Birthday Badge**: Active only on kid's birthday, grants special reward
- **Holiday Bonus**: Active on Christmas/Hanukkah/etc., encourages participation
- **Anniversary Badge**: Celebrates membership milestones

**Configuration Example**: "Birthday Bonus"

- **Badge Type**: Special Occasion
- **Start Date**: `2026-03-15` (kid's birthday)
- **Recurring Frequency**: Yearly
- **Awards**: 100 points, "Birthday Special" reward
- **Behavior**: Active only on March 15th each year, completing 1 chore earns badge

> [!TIP]
> Special Occasion badges are perfect for creating excitement around special dates without requiring complex daily tracking.

---

## How Periodic Badges Work

### Earning Periodic Badges

**Evaluation Timing**:

- **Daily badges**: Evaluated at midnight (00:00) each night
- **Periodic badges**: Evaluated at end of reset cycle (e.g., Sunday 23:59 for weekly)

**Earning Process**:

1. Badge tracks progress throughout cycle via `sensor.kc_<kid>_badge_progress_<badge_name>`
2. At cycle end, integration checks if `threshold_value` reached
3. **If earned**: Awards granted (points, rewards, bonuses), badge marked "earned"
4. **If failed**: Penalties applied (if configured), badge marked "failed"
5. Progress resets to 0 for next cycle

### Cycle Resets

**Daily Badges**:

- Reset at midnight (00:00) automatically
- No configuration needed

**Periodic Badges**:

- Reset based on `recurring_frequency` setting
- Weekly = resets Monday at 00:00
- Monthly = resets 1st of month at 00:00
- Custom = resets per specified interval

**Start Date Behavior**:

- If `start_date` blank → Integration calculates first cycle start per kid
- If `start_date` set → All kids use same start date (synchronized cycles)

### Penalty Triggers

Penalties are applied when badge is NOT earned by end of cycle:

**Example: "Perfect Attendance" Badge**

- Target: "Days Selected Chores Completed (No Overdue)", Threshold: 7
- Penalty: -20 points, Remove screen time privilege
- **Scenario 1**: Kid completes all chores on time for 7 days → Badge earned, penalty NOT applied
- **Scenario 2**: Kid misses 1 chore or goes overdue → Badge fails, penalty applied at cycle end

> [!NOTE]
> Penalties apply automatically at cycle end. Parents cannot prevent penalty once badge fails.

### Strict Mode Logic ("No Overdue" Target Types)

When a target type includes "(No Overdue)", the system enforces strict punctuality for that specific day's evaluation.

**Evaluation Process**:

1. Every time badge logic runs, system checks if ANY tracked chore is currently in the overdue state
2. If any chore is overdue, the **daily criteria is marked as Failed** for that day

**The Consequences**:

- **Streak Badges**: Since today failed, the streak will reset to 0 when the system processes the day change (midnight)
- **"All Days" Badges**: If the badge requires perfection (e.g., 7 days out of 7), failing one day makes the badge impossible to earn for the rest of the cycle
- **"80% Days" Badges**: You lose credit for today, but may still recover if you have enough buffer days remaining in the cycle

**Example**: "Week of Perfect Attendance" (Streak: 7 days, No Overdue)

- Monday-Thursday: All chores completed on time → Current streak = 4
- Friday: One chore goes overdue (even if completed later) → Today's criteria fails → **Streak resets to 0 at midnight**
- Saturday-Sunday: Complete all on time → Streak rebuilds to 2, but badge fails (needed 7 consecutive)

> [!CAUTION]
> Strict mode is unforgiving. One overdue chore at any point during the cycle can invalidate the entire badge, depending on target type. Use for serious accountability contracts only.

---

## Periodic Badge Progress Sensor

Each periodic/daily badge creates a progress sensor: `sensor.kc_<kid>_badge_progress_<badge_name>`

### State Values

| State         | Meaning                                      |
| ------------- | -------------------------------------------- |
| `not_started` | Badge cycle hasn't begun (before start_date) |
| `in_progress` | Badge currently tracking, not yet earned     |
| `earned`      | Badge successfully earned this cycle         |
| `failed`      | Badge failed this cycle (penalties applied)  |
| `expired`     | Badge ended permanently (past end_date)      |

### Progress Tracking Attributes

| Attribute             | Type  | Description                                        |
| --------------------- | ----- | -------------------------------------------------- |
| `current_progress`    | int   | Current count toward threshold (e.g., 3 days of 5) |
| `threshold`           | int   | Target value to earn badge                         |
| `percentage_complete` | float | Progress as percentage (e.g., 60.0)                |
| `days_until_reset`    | int   | Days remaining in current cycle                    |
| `next_reset_date`     | str   | ISO timestamp of next reset                        |
| `current_cycle_start` | str   | ISO timestamp of cycle start                       |
| `current_cycle_end`   | str   | ISO timestamp of cycle end                         |
| `times_earned`        | int   | Total times badge earned (lifetime)                |
| `times_failed`        | int   | Total times badge failed (lifetime)                |
| `current_streak`      | int   | Consecutive cycles earned (resets on failure)      |
| `best_streak`         | int   | Best consecutive cycles earned (all-time)          |
| `tracked_chores`      | list  | Chore IDs counted toward badge (if filtered)       |

**Example Automation**:

```yaml
automation:
  - alias: "Celebrate Weekly Mission Success"
    trigger:
      - platform: state
        entity_id: sensor.kc_sarah_badge_progress_week_of_clean
        to: "earned"
    action:
      - service: notify.mobile_app
        data:
          title: "🎉 Mission Complete!"
          message: "Sarah earned the Week of Clean badge!"
```

---

## Mission Examples

### Example 1: "Week of Clean" (Daily Habit Badge)

**Goal**: Complete all assigned chores every day for 7 consecutive days.

**Configuration**:

- **Badge Type**: Periodic
- **Target Type**: Streak: Selected Chores Completed
- **Threshold**: 7 (days)
- **Tracked Chores**: All chores (leave blank)
- **Awards**: 100 points, "Movie Night" reward
- **Reset**: Weekly (Monday start)

**Why This Works**:

- Streak requirement builds momentum
- Full week commitment feels achievable
- Reward is exciting enough to motivate

---

### Example 2: "Perfect Attendance" (Strict Mode Contract)

**Goal**: Complete all chores on time with zero overdue chores for 5 days.

**Configuration**:

- **Badge Type**: Periodic
- **Target Type**: Days Selected Chores Completed (No Overdue) ⚠️ **Strict Mode**
- **Threshold**: 5 (days)
- **Tracked Chores**: All chores (leave blank)
- **Awards**: 50 points
- **Penalties**: -20 points, remove "Extra Screen Time" bonus
- **Reset**: Weekly

**Why This Works**:

- Teaches time management and accountability
- Penalty reinforces consequences of procrastination
- 5 days (not 7) allows for recovery/planning days

> [!CAUTION]
> Strict mode badges can frustrate young kids. Consider starting with 80% completion types before using "No Overdue" variants.

---

### Example 3: "Dishwasher King" (Specialist Badge)

**Goal**: Complete dishwasher chores 10 times this week.

**Configuration**:

- **Badge Type**: Periodic
- **Target Type**: Chores Completed
- **Threshold**: 10 (completions)
- **Tracked Chores**: `["Load Dishwasher", "Unload Dishwasher"]` ✅ **Filtered**
- **Awards**: 30 points, "Dishwasher King" badge icon
- **Reset**: Weekly

**Why This Works**:

- Tracked chores make goal clear (only dishwasher counts)
- Volume-based (encourages doing it multiple times per day)
- Specialist identity ("King/Queen" title) builds pride

---

### Example 4: "No Sass Contract" (Penalty Enforcement)

**Goal**: Complete all chores without any going overdue for 7 days straight.

**Configuration**:

- **Badge Type**: Daily (resets midnight)
- **Target Type**: Days Selected Chores Completed (No Overdue) ⚠️ **Strict Mode**
- **Threshold**: 1 (evaluated daily)
- **Tracked Chores**: All chores (leave blank)
- **Awards**: 10 points (daily)
- **Penalties**: -15 points, "Loss of Video Game Time" (30 minutes)
- **Reset**: Daily (automatic)

**Why This Works**:

- Daily evaluation provides immediate feedback
- Penalty is significant enough to motivate behavior change
- "Contract" framing sets clear expectations

> [!TIP]
> Use daily badges for accountability contracts. Kids see consequences immediately (midnight each night) rather than waiting for weekly evaluation.

---

## Managing Periodic Badges

### Editing Existing Badges

1. Navigate to **Settings** → **Devices & Services** → **KidsChores** → **Configure**
2. Select **Badges** → **Edit Badge**
3. Choose badge to edit from list
4. Modify fields as needed
5. Click **Submit**

**What You Can Change**:

- Badge name, description, labels, icon
- Target type and threshold (⚠️ resets progress)
- Tracked chores, assigned kids
- Awards and penalties
- Reset schedule

**What Happens to Progress**:

- Changing target type or threshold → Resets current cycle progress
- Changing tracked chores → Recalculates progress (may decrease)
- Changing awards/penalties → Applies to next cycle only

---

### Deleting Badges

1. Navigate to **Settings** → **Devices & Services** → **KidsChores** → **Configure**
2. Select **Badges** → **Delete Badge**
3. Choose badge to delete
4. Confirm deletion

**What Gets Deleted**:

- Badge configuration
- Progress sensor (`sensor.kc_<kid>_badge_progress_<badge_name>`)
- Historical earn/fail records

**What's Preserved**:

- Points/rewards/bonuses already granted
- Penalties already applied

> [!WARNING]
> Badge deletion is permanent and cannot be undone. Export your configuration before deleting important badges.

---

## Troubleshooting

### Issue 1: Badge Shows "failed" But Kid Completed Everything

**Symptoms**: Badge marked "failed" at cycle end despite kid completing all chores.

**Possible Causes**:

1. **Strict Mode activated**: Target type includes "No Overdue" and one chore went overdue (even if later completed)
2. **Tracked chores mismatch**: Badge filtered to specific chores, but kid completed different chores
3. **Timing issue**: Chore completed after cycle end (e.g., completed Monday at 00:30, but weekly badge reset at Monday 00:00)

**Solutions**:

- Switch from "No Overdue" to standard completion types (more forgiving)
- Verify tracked chores filter matches assigned chores
- Check `next_reset_date` attribute to confirm cycle boundaries

---

### Issue 2: Penalty Applied Multiple Times

**Symptoms**: Same penalty applied twice for single badge failure.

**Possible Cause**: Badge configured with penalty in both periodic badge AND linked bonus/penalty entity.

**Solution**: Penalties should be configured in ONE place only:

- **Option A**: Use badge penalty field (applies automatically on failure)
- **Option B**: Create separate penalty entity and trigger via automation

Don't configure penalty in both locations.

---

### Issue 3: Progress Sensor Shows "0%" Despite Work Done

**Symptoms**: `current_progress` = 0 even though kid completing chores.

**Possible Causes**:

1. **Tracked chores filter**: Badge only counts specific chores, but kid completing different chores
2. **Target type mismatch**: Badge tracks "Days" (daily criteria met), but you're checking mid-day (day not complete yet)
3. **Start date in future**: Badge hasn't started yet (check `current_cycle_start`)

**Solutions**:

- Verify tracked chores includes chores kid is actually assigned to
- For "Days" target types, check progress at end of day (not mid-day)
- Check `state` attribute: If `not_started`, badge hasn't begun yet

---

### Issue 4: Shared First Conflict (Advanced)

**Symptoms**: Kid completes shared chore first, but badge doesn't count it toward their progress.

**Cause**: Badge configured to track shared chore, but sibling completed it first (chore now claimed).

**Solution**: See [Badge Periodic Advanced: Shared First Conflict Trap](Badge-Periodic-Advanced.md#the-shared-first-conflict-trap) for detailed explanation and workarounds:

- Use "minimum X chores" target types (counts ANY chore, not specific ones)
- Don't filter badges to shared chores if fairness is concern
- Create separate specialist badges for non-shared chores

---

### Issue 5: Weekly Badge Resets on Wrong Day

**Symptoms**: Weekly badge resets on Wednesday instead of Monday.

**Cause**: `start_date` was set to a Wednesday.

**Solution**:

1. Edit badge
2. Change `start_date` to desired reset day (e.g., next Monday)
3. Current cycle will adjust to new schedule

> [!NOTE] > **Reset Day Logic**: Weekly badges reset at 00:00 on the day matching `start_date` day-of-week. If start_date is Tuesday, all future resets happen on Tuesdays. The system uses the `start_date` as the baseline to calculate all subsequent cycle boundaries.

---

## Related Documentation

### Conceptual

- **[Badge Gamification](Badge-Gamification.md)** - Badge system overview (ranks vs missions)
- **[Getting Started: Badges](Getting-Started:-Your-First-Badges.md)** - Badge creation walkthrough

### Configuration

- **[Configuration: Cumulative Badges](Configuration:-Cumulative-Badges.md)** - Rank-based badge configuration

### Advanced

- **[Badge Periodic Advanced](Badge-Periodic-Advanced.md)** - Advanced mechanics (scope filtering, strict mode, penalty patterns, shared conflicts)
- **[Badge Cumulative Advanced](Badge-Cumulative-Advanced.md)** - Multiplier engine (for comparison)

### Technical

- **[Technical Reference: Badge Entities Detail](Technical-Reference:-Badge-Entities-Detail.md)** - Sensor entity attributes
- **[Technical Reference: Configuration Detail](Technical-Reference:-Configuration-Detail.md)** - Config/options flow architecture

---

**Next Steps**:

- Create your first periodic badge: [Getting Started: Badges](Getting-Started:-Your-First-Badges.md)
- Understand advanced tactics: [Badge Periodic Advanced](Badge-Periodic-Advanced.md)
- Combine with cumulative ranks: [Badge Gamification](Badge-Gamification.md)
