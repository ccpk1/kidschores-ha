# Chore Advanced Features

**Target Audience**: Power Users
**Prerequisites**: Understanding of [Core Configuration](Configuration:-Chores.md)
**Covers**: Per-kid customization, daily multi-times, custom scheduling

---

## Overview

This guide covers advanced features for users who need per-kid customization, multiple daily completions, or non-standard scheduling patterns.

**When You Need This Guide**:

- Different kids need different schedules (Alice Mon-Wed, Bob Thu-Sun)
- Chores happen multiple times per day (breakfast/lunch/dinner dishes)
- Non-standard recurrence (every 3 days, every 4 hours)

**When You Don't Need This**:

- All kids do chores the same way → Use basic configuration
- Standard daily/weekly/monthly scheduling → Use [Core Configuration Guide](Configuration:-Chores.md)

> [!IMPORTANT] > **Per-Kid Schedule Helper**: The per-kid customization form appears automatically when you create an INDEPENDENT chore with **2 or more kids** assigned. Single-kid INDEPENDENT chores use the main form (data is stored the same way internally).

**Related Documentation**:

- [Chore Configuration Guide](Configuration:-Chores.md) - Basic setup

---

## Custom Recurrence & Hourly Intervals

For non-standard scheduling patterns that don't fit Daily/Weekly/Monthly/Yearly.

### Custom Recurrence

Schedule based on custom intervals (every 3 days, every 2 weeks, every 90 days).

**Two Types**:

1. **Custom (calendar-based)**: Recurs at fixed intervals regardless of completion
   - Example: Every Tuesday, every 2 weeks on Sunday

2. **Custom from completion**: Next recurrence calculated from completion date
   - Example: Oil change 90 days after last change, replace toothbrush 3 months after replacement

**Configuration**:

- Set **Frequency** to `Custom` or `Custom from completion date`
- Set **Custom Interval**: Number (e.g., 3, 10, 90)
- Set **Custom Interval Unit**: hours, days, weeks, months

**Example: Toothbrush Replacement**

```yaml
Chore: "Replace Toothbrush"
Frequency: Custom from completion date
Interval: 90
Unit: days

Result:
  - Completed Jan 15 → Next due April 15 (90 days later)
  - Tracks from actual completion, not fixed calendar dates
```

### Hourly Intervals

Very frequent tasks using hours as the interval unit (every 2 hours, every 4 hours).

**Use Cases** (short-term only):

- New pet monitoring (check every 2 hours)
- Temporary medication (every 4 hours for 3 days)
- Intensive plant care during germination

**Configuration**:

- Set **Approval Reset** to `At Due Date *` or `Upon Completion` if less than 24 hours `At Midnight` doesn't work
- Set **Frequency** to `Custom`
- Set **Interval Unit** to `hours`
- Set interval (e.g., 2, 4, 6)

**Example: Pet Monitoring**

```yaml
Chore: "Check Puppy"
Frequency: Custom
Interval: 2
Unit: hours
Due Date: 8:00 AM

Result:
  - Repeats every 2 hours: 8am, 10am, 12pm, 2pm, 4pm, 6pm, 8pm
  - Crosses midnight boundary (not reset at midnight)
  - Use for 1-2 weeks max, then switch to Daily
```

### Tips

- **Use standard frequencies when possible**: Simpler to understand
- **Custom from completion**: Best for maintenance tasks where interval matters
- **Hourly = short-term only**: Exhausting for long periods, use 1-2 weeks max
- **Lower points for hourly**: Frequent = less points each (2 points vs 20 points)

---

## Daily Multi-Times

Schedule chores multiple times per day with specific time slots (breakfast dishes at 7am, lunch at 12pm, dinner at 6pm).

**Works With**: All completion modes (INDEPENDENT, SHARED_ALL, SHARED_FIRST)

### Two Configuration Forms

**Simple Form** (SHARED or single-kid INDEPENDENT):

- Single text input: "Daily Times"
- Format: `07:00|12:00|18:00` (pipe-separated, 24-hour)
- All assigned kids use same times
- Min 2 times, max 6 times per day

**Per-Kid Helper** (INDEPENDENT with 2+ kids):

- Each kid gets own `daily_multi_times_KidName` field
- Format: Same pipe-separated (e.g., `08:00|17:00`)
- Different kids can have different time slots
- Also includes per-kid applicable days and due dates

### Configuration Steps

1. Create chore (any completion mode)
2. Set **Frequency** to `Daily - Multiple times per day`
3. Set **Due Date** (required - defines timing reference)
4. Submit → Daily times form appears:
   - **SHARED or 1 kid**: Enter times like `07:00|12:00|18:00`
   - **INDEPENDENT 2+ kids**: Enter times per kid in per-kid helper

### Example: Pet Feeding

```yaml
Chore: "Feed Dog"
Frequency: Daily Multi
Due Date: 8:00 AM
Points: 5 per feeding

Times Entered: 08:00|18:00

Result:
  - 8:00 AM: "Feed Dog" available (morning)
  - 6:00 PM: "Feed Dog" available (evening)
  - Each feeding = separate claim/approval
  - Kids earn 5 points per completed feeding
```

### Requirements & Constraints

- ✅ Due date must be set
- ✅ Approval reset must be "At Due Date" or "Upon Completion" (not "At Midnight")
- ✅ Min 2 times, max 6 times per day
- ✅ Pipe-separated format: `HH:MM|HH:MM|HH:MM`
- ✅ Works with all completion modes (INDEPENDENT, SHARED_ALL, SHARED_FIRST)
- ⚠️ Each time slot creates a separate completion opportunity

### Tips

- **Timing**: Space slots 2+ hours apart, align with routines (meals, wake/sleep)
- **Points**: Lower per occurrence (3 times × 5 pts = 15 pts/day total)
- **Slots**: Use 2-3 times/day max (not overwhelming)

---

## Per-Kid Schedule Helper

Dynamic configuration form for INDEPENDENT chores with 2+ kids that lets you customize applicable days, daily multi times, and due dates per kid.

**When It Appears**: Automatically after submitting an INDEPENDENT chore with 2+ kids assigned

**Why Not for Single Kid?**: Single-kid INDEPENDENT uses main chore form fields (stored identically internally, just simpler UI)

> [!NOTE] > **Platform Limitations**: Some of these advanced features involve complex dynamic form generation that goes beyond Home Assistant's standard config flow architecture. As a result, some per-kid helper sections cannot be fully translated—the platform requires static translation keys, but kid-specific field names are generated dynamically. Main instructions and labels are translatable, but individual per-kid field sections display in English only.

### Helper Structure

#### 1. Template Values (Top)

Shows defaults from main form:

```
Kids: Dad, Kid3
Template days: Friday
```

Kids use these values unless you customize individually.

#### 2. Apply Template Shortcuts

- **Apply template days to all kids**: Copies chore-level days to everyone

#### 3. Per-Kid Sections (Bottom)

Each kid gets:

- **applicable_days_KidName**: Expandable day selector (shows chips for selected days)
- **daily_multi_times_KidName**: Pipe-separated times (if Daily Multi selected)
- **due_date_KidName**: Date/time picker with AM/PM
- **clear_due_date_KidName**: Toggle to remove per-kid due date

---

## Per-Kid Applicable Days

Customize which days of the week each kid can complete a chore (Alice Mon-Wed, Bob Thu-Sun).

**Requires**: INDEPENDENT with 2+ kids (uses per-kid helper form)

**Default Behavior**: Blank = all days (recommended unless you need restrictions)

> [!NOTE] > **Platform Limitations**: Some of these advanced features involve complex dynamic form generation that goes beyond Home Assistant's standard config flow architecture. As a result, some per-kid helper sections cannot be fully translated—the platform requires static translation keys, but kid-specific field names are generated dynamically. Main instructions and labels are translatable, but individual per-kid field sections display in English only.

### How to Configure

1. Create INDEPENDENT chore with 2+ kids
2. Submit chore → Per-kid helper appears
3. For each kid, click `applicable_days_KidName` to expand day selector
4. Select specific days (or leave blank for all days)
5. Submit helper

### Example: Split Week Schedule

```yaml
Chore: "Feed Pets"
Completion: Independent
Frequency: Daily
Assigned: Alice, Bob

Per-Kid Days (in helper):
  - Alice: Mon, Tue, Wed
  - Bob: Thu, Fri, Sat, Sun

Result:
  - Alice sees "Feed Pets" Mon-Wed only
  - Bob sees "Feed Pets" Thu-Sun only
  - Coverage all week, no overlap
```

### Tips

- **Leave blank unless needed**: Blank = all days (maximum flexibility)
- **Use for rotations**: Split week, alternating schedules, activity conflicts
- **Verify in calendar**: Visual check that schedule works as expected
- **Communicate clearly**: Kids need to know their assigned days

---

## Troubleshooting

### Per-Kid Helper Not Appearing

**Problem**: Helper form doesn't show after submitting chore.

**Solution**: Check that chore is INDEPENDENT with 2+ kids assigned. Single-kid INDEPENDENT uses main form.

---

### Daily Multi Form Missing

**Problem**: No form to enter times after selecting Daily Multi.

**Solution**: Due date is required. Go back and set a due date on main chore form.

---

### Kid Not Seeing Chore on Expected Day

**Problem**: Kid says chore isn't showing up on their assigned day.

**Solution**:

1. Edit chore → Check per-kid helper
2. Click `applicable_days_KidName` to expand
3. Verify days selected (blank = all days)
4. If blank, chore should show every day

---

### Daily Multi Times Not Working

**Problem**: Times entered but chore only shows once per day.

**Solution**:

- Check format: Must be pipe-separated `HH:MM|HH:MM|HH:MM`
- Example: `07:00|12:00|18:00` (not commas or spaces)
- Min 2 times, max 6 times

---

### Per-Kid Changes Not Saving

**Problem**: Made changes in per-kid helper but they didn't apply.

**Solution**: Scroll to bottom and click Submit button. Changes only save when submitted.

---

_Last updated: January 14, 2026 (v0.5.0)_

This guide covers advanced chore features that enable sophisticated scheduling and per-kid customization. These features unlock capabilities like alternating weeks, rotating responsibilities, and multiple daily completions.

**What You'll Learn**:

- Per-kid applicable days for custom schedules per child
- Daily multi-times for multiple completions at specific time slots
- Hourly intervals for very frequent tasks
- How to combine features for complex real-world scenarios

**Prerequisites Check**:

- ✅ You understand [completion modes](Configuration:-Chores.md#completion-modes) (INDEPENDENT, SHARED_ALL, SHARED_FIRST)
- ✅ You know how [scheduling works](Configuration:-Chores.md#scheduling--recurrence) (frequency, applicable days)
- ✅ You're comfortable with basic chore configuration

**Important**: Most features in this guide **require INDEPENDENT completion mode** (per-kid applicable days, per-kid due dates) because they need individual tracking per kid. However, **daily multi-times works with all completion modes** - SHARED chores can have multiple time slots per day.

---

## Next Steps

**Need More Depth on Reset Behaviors?**

- [Chore Approval & Reset Reference](Chore-Approval-Reset-Reference.md): All 6 reset types explained
- [Overdue Handling Types](Chore-Approval-Reset-Reference.md#overdue-handling): Behavior when past due date
- [Pending Claim Actions](Chore-Approval-Reset-Reference.md#pending-claim-actions): What happens on reset

**Ready to Implement?**

- Review [Core Configuration Guide](Configuration:-Chores.md) if you need basics refresher
- Test your schedule for a week before committing long-term
- Use dashboard calendar view to visualize complex schedules

**Questions?**

- Check the [FAQ](FAQ.md) for common advanced feature questions
- See [Tips & Tricks](Tips-&-Tricks:-Getting-Started.md) for creative scheduling ideas
