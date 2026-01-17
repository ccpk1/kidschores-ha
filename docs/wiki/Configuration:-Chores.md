# Chore Configuration Guide

**Prerequisites**: Completed [Quick Start Guide](Getting-Started:-Quick-Start.md)
**Time to Read**: 15-20 minutes

> [!NOTE]
> This guide covers the core configuration options you'll use for most chores. For advanced features like per-kid schedules and custom intervals, see [Advanced Features Guide](Configuration:-Chores-Advanced.md).

---

## What You'll Learn

By the end of this guide, you'll understand:

1. **Completion Criteria** - Who completes chores and how tracking works
2. **Scheduling & Recurrence** - When chores become available and repeat
3. **Approval Settings** - How chores get approved and when they reset
4. **Basic Configuration** - Points, notifications, and display options

> [!TIP] > **Getting Started**: During initial integration setup, create just 1-2 simple chores to get familiar with the system. All advanced features (daily multiple times, per-kid customization) are available through **Settings → Devices & Services → KidsChores → Configure** after setup.

---

## Understanding Chore Configuration

When you create or edit a chore, you'll see fields organized into four sections:

1. **Core Details** - Name, description, icon, labels, points
2. **Assignments & Logic** - Who does it, how completion works, approval behavior
3. **Scheduling** - When it's available, how often it repeats
4. **Display & Notifications** - Calendar visibility, notification preferences

> [!TIP]
> The fields appear in the Add/Edit Chore form in this exact order. This guide follows the same sequence to match your experience in the UI.

---

## Quick Decision Guide

**New to chore configuration?** This guide walks you through the essential decisions in order. Follow these 4 steps to configure any chore, then explore the detailed sections below for more information.

> [!TIP]
> This flowchart matches the order fields appear in the Add/Edit Chore form. Each step links to its detailed section if you need more context.

### Step 1: Choose Completion Criteria

**Question**: Who completes this chore?

- Each kid separately → **[Independent](#option-1-independent-most-common)**
- All kids together → **[Shared (All)](#option-2-shared-all-kids-must-complete)**
- Any one kid → **[Shared (First)](#option-3-shared-first-completes)**

### Step 2: Choose Frequency

**Question**: How often does this repeat?

- One-time → **[None](#none)**
- Daily (once) → **[Daily](#daily)**
- Daily (multiple times) → **[Daily Multi](#daily-multi)**
- Weekly → **[Weekly](#weekly)**
- Every 2 weeks → **[Biweekly](#biweekly)**
- Monthly → **[Monthly](#monthly)**
- Custom interval → **[Custom](#custom)** or **[Custom From Completion](#custom-from-completion)**

### Step 3: Choose Approval Reset

**Question**: When should approved status reset?

- Once per day → **[At Midnight (Once)](#option-1-at-midnight-once)**
- Multiple times per day → **[At Midnight (Multi)](#option-2-at-midnight-multi)**
- Once per week/month → **[At Due Date (Once)](#option-3-at-due-date-once)**
- Multiple times per week/month → **[At Due Date (Multi)](#option-4-at-due-date-multi)**
- Immediately after approval → **[Upon Completion](#option-5-upon-completion)**

### Step 4: Configure Other Settings

- **Choose [pending claim action](#pending-claim-action)** (default: Clear Pending):
  - **Clear Pending**: Kid's claim cleared at reset if not approved (no credit, teaches deadlines)
  - **Hold Claim Status**: Claim retained until approved, but may lose next cycle opportunity
  - **Approve Automatically**: Auto-approves claimed chores at reset (low supervision, high trust)
- **Choose [overdue handling](#overdue-handling)** (default: Clear Overdue Immediately When Approved Late):
  - **Default (Option 1)**: "Clear Overdue Immediately When Approved Late" for maximum flexibility
  - **Option 2**: "Clear Overdue at Next Scheduled Reset" (AT_MIDNIGHT only) - hidden misses
  - **Option 3**: "At Due Date" if you want visible accountability for late completion
  - **Option 4**: "Never Overdue" for low-pressure chores
- **[Applicable days](#applicable-days)**: Leave blank unless you need to restrict (e.g., school days only)
- Set [due date](#due-date) if required by frequency

---

> [!NOTE] > **Don't see what you need?** Check [Validation Rules](#validation-rules) to understand which combinations are allowed, or jump to [Common Configuration Patterns](#common-configuration-patterns) for ready-to-use examples.

---

## Name & Description

**Name** (Required): The chore title displayed to kids

- Keep it short and action-oriented: "Make Bed", "Feed Dog", "Do Homework"
- Avoid generic names like "Chore 1" or "Task"

**Description** (Optional): Additional context or instructions

- Use for multi-step tasks: "Vacuum all rooms, wipe counters, take out trash"
- Add helpful details: "Remember to use the blue food bowl"

## Icon

Choose an icon that helps kids quickly recognize the chore:

- Default: `mdi:broom` (cleaning broom)
- Common examples: `mdi:bed`, `mdi:dog`, `mdi:book-open-variant`, `mdi:tooth`, `mdi:silverware-fork-knife`
- Browse all icons at [Material Design Icons](https://pictogrammers.com/library/mdi/)

## Labels

Organize chores with labels (tags):

- **Examples**: "Morning Routine", "After School", "Weekend", "Pet Care"
- **Use Cases**: Filter chores in dashboard, group related tasks, create themed lists
- **Multiple Labels**: Assign as many as needed, but recommend only adding for a specific purpose (e.g., "Morning Routine" + "Daily" + "Hygiene")

## Points

Set the base point value kids earn for completing the chore:

- **Default**: 10 points
- **Tip**: Scale points by effort - simple tasks (5-10 points), complex tasks (20-50 points)
- **Consistency**: Keep similar chores at similar point values for fairness

---

## Assigned Kids

Select which kids can complete this chore:

- **Minimum**: 1 kid required
- **Multiple Kids**: Common for household chores or shared responsibilities
- **Per-Kid Features**: Selecting 2+ kids with Independent mode unlocks per-kid customization (see Advanced Features)

---

## Completion Criteria ⭐ **(Most Important Setting)**

This determines how chore completion is tracked. Choose carefully - this affects all other configuration options.

### Option 1: Independent (Most Common)

**Use For**: Tasks each kid does separately on their own schedule

**How It Works**:

- **Separate tracking**: Each kid has their own status (Pending → Claimed → Approved)
- **Independent due dates**: Each kid can have different due dates/times
- **No dependencies**: One kid's approval doesn't affect others
- **Individual points**: Each kid earns points when parent approves their claim

**Real-World Examples**:

```
Chore: "Make Your Bed" (Daily frequency, At Midnight Once reset)
- Alice makes bed at 8:00 AM and claims chore → Parent approves claim → She earns 10 points → Approval resets at configured period (midnight)
- Bob makes bed at 8:30 AM and claims chore → Parent approves claim → He earns 10 points → Approval resets at configured period (midnight)
- Neither completion affects the other

Note: Kids can press the Disapprove button while chore is Claimed to undo their claim (not tracked as disapproval).
```

**Best For**:

- ✅ Personal hygiene (brush teeth, shower, get dressed)
- ✅ Individual homework or schoolwork
- ✅ Personal spaces (make own bed, clean own room, organize own desk)
- ✅ Daily routines that each kid does at their own pace

**Per-Kid Customization**:
With Independent mode + 2+ kids, advanced customization is available (after initial setup):

- Different applicable days per kid (Alice: Mon-Wed, Bob: Thu-Sun)
- Different daily multi times per kid (Alice feeds dog at 8am/6pm, Bob at 9am/7pm)
- Individual due dates and scheduling

> [!TIP]
> Use Independent mode when kids operate on different schedules or when completion tracking needs to be separate (alternating weeks, age-based responsibilities, activity conflicts). Start with basic schedules during initial setup, then customize through **Settings → Configure**.

---

### Option 2: Shared (All Kids Must Complete)

**Use For**: Group activities where **everyone must participate** to finish the chore

**How It Works**:

- **Shared chore-level period**: The chore has a single reset cycle
- **Per-kid independent tracking**: Each kid's completion is tracked separately within that period
- **All must complete**: Chore fully completes when all assigned kids finish their part
- **Individual points**: Each kid earns points when they complete (not when chore fully completes)

**Real-World Example**:

```
Chore: "Clean Living Room" (Alice, Bob, Charlie assigned)
Period: Daily at midnight

6:00 PM - Chore status: Pending for all
6:15 PM - Alice claims and parent approves → Alice earns 10 points → Chore status: "approved-in-part"
6:30 PM - Bob claims and parent approves → Bob earns 10 points → Chore status: "approved-in-part"
6:45 PM - Charlie claims and parent approves → Charlie earns 10 points → Chore status: "approved" (all complete)
Midnight - Approval resets → Chore status returns to Pending
```

**Important Clarifications**:

- **Chore-level period**: Reset happens at chore level (e.g., daily at midnight)
- **Per-kid completion**: Each kid completes independently within that period
- **All must finish**: If Charlie doesn't complete by midnight, the chore still resets (no carried-over incompleteness)

**Best For**:

- ✅ Family cleanup (everyone helps clean living room, kitchen, yard)
- ✅ Team projects (all kids work on joint activity)
- ✅ Group learning (all kids participate in educational task)
- ⚠️ Requires coordination - all kids must complete within the same period

**Limitations**:

- ❌ Cannot use per-kid applicable days or times
- ✅ Compatible with Daily Multi frequency (uses shared time slots)
- ✅ Compatible with all approval reset types

---

### Option 3: Shared (First Completes)

**Use For**: Household tasks where **any one kid** can handle it

**How It Works**:

- **First claimer owns it**: Whoever claims first is responsible until reset
- **Blocks others**: Once claimed, other kids can't claim until chore resets
- **Single completion**: Only one kid completes per reset cycle
- **Points to claimer**: Only the kid who completes earns points

**Real-World Example**:

```
Chore: "Take Out Trash" (Alice, Bob, Charlie eligible)

6:00 PM - Chore status: Pending (any kid can claim)
6:15 PM - Alice claims → Chore status: Claimed (blocks Bob and Charlie from claiming)
         - Alice: Pending → Claimed → (waiting for approval)
         - Bob & Charlie: Pending → Completed_by_Other (blocking state, cannot claim)
6:20 PM - Parent approves → Alice earns 10 points → Chore status: Approved
6:25 PM - Approval resets per configured type (if UPON_COMPLETION) → Chore status: Pending (available to all again)

Next occurrence:
7:00 PM - Bob claims first → Bob: Pending → Claimed → Approved
                            → Alice & Charlie: Pending → Completed_by_Other (blocked until reset)
```

> [!NOTE] > **Status Progression Details**:
>
> - **First Claimer**: Normal workflow (Pending → Claimed → Approved)
> - **Other Kids**: Pending → Completed_by_Other (blocking state - cannot claim until chore resets)
>
> The `Completed_by_Other` state prevents blocked kids from claiming while another kid owns the chore.

**Best For**:

- ✅ Household maintenance (take out trash, feed pet, water plants)
- ✅ Optional opportunities (bonus project, first volunteer)
- ✅ Tasks where one kid is sufficient

**Strategic Use**:

- **Rotating responsibility**: First-come-first-served encourages initiative
- **Flexibility**: Any available kid can handle the task
- **No scheduling**: Works well with "when you see it needs doing" tasks

**Limitations**:

- ❌ Cannot use per-kid applicable days or times
- ✅ Compatible with Daily Multi frequency (uses shared time slots)
- ✅ Compatible with all approval reset types

---

### Comparison: Which Mode to Choose?

| Question                         | Independent                | Shared (All)          | Shared (First)        |
| -------------------------------- | -------------------------- | --------------------- | --------------------- |
| Each kid does their own version? | ✅ Yes                     | ❌ No                 | ❌ No                 |
| Everyone must participate?       | ❌ No                      | ✅ Yes                | ❌ No                 |
| Only one kid needs to do it?     | ❌ No                      | ❌ No                 | ✅ Yes                |
| Per-kid scheduling?              | ✅ Yes (different per kid) | ❌ No                 | ❌ No                 |
| Daily multi-times?               | ✅ Yes (per-kid times)     | ✅ Yes (shared times) | ✅ Yes (shared times) |
| Separate due dates per kid?      | ✅ Yes                     | ❌ No                 | ❌ No                 |

**Decision Tree**:

1. Does each kid do their own version? → **Independent**
2. Must all assigned kids complete? → **Shared (All)**
3. Can any one kid handle it? → **Shared (First)**

---

## Approval Reset Type

**What This Controls**: When a chore's approved status drops back to pending (becomes claimable again)

This is the second most important setting after Completion Criteria. It determines:

- How many times a chore can be completed in a period
- When the chore becomes available again
- Whether periods are tracked (midnight boundary, due date boundary, or none)

> [!NOTE]
> The word "reset" here means "approval reset" - when the approved status drops → returns to pending. This is different from frequency (when chore becomes available initially).

#### Quick Reference Table

| Reset Type            | Completions/Period   | When Returns to Pending                          | Period Tracking   | Best For                                      |
| --------------------- | -------------------- | ------------------------------------------------ | ----------------- | --------------------------------------------- |
| At Midnight (Once) ⭐ | 1 per day            | At midnight (stays approved until then)          | Midnight boundary | Daily routines (once/day)                     |
| At Midnight (Multi)   | Unlimited per day    | At midnight (stays approved until then)          | Midnight boundary | Daily routines (multiple/day allowed)         |
| Upon Completion       | Unlimited            | Immediately after approval                       | None              | Flexible, anytime tasks                       |
| At Due Date (Once)    | 1 per cycle          | When due date passes (stays approved until then) | Due date boundary | Weekly/monthly (once) - Requires due date     |
| At Due Date (Multi)   | Unlimited per period | When due date passes (stays approved until then) | Due date boundary | Weekly/monthly (multiple) - Requires due date |

**⭐ Default**: At Midnight (Once)

---

### At Midnight (Once) ⭐ **DEFAULT** (One Per Day)

**Behavior**:

- Kid can complete **once per day**
- After approval, chore stays APPROVED until midnight
- At midnight, resets to PENDING (available again)
- Blocks additional claims with "already_approved" error

**Timeline Example**:

```
Monday 8:00 AM - Alice claims "Make Bed"
Monday 8:05 AM - Parent approves → Chore stays APPROVED
Monday 3:00 PM - Alice tries to claim again → Blocked ("already approved today")
Tuesday 12:00 AM (midnight) - Chore resets → PENDING (Alice can claim again)
```

**Best For**:

- ✅ Daily routines that should happen once (make bed, brush teeth, do homework)
- ✅ One-time-per-day requirements
- ✅ Ensuring kids don't "game" the system by claiming multiple times

**Period Tracking**: Midnight boundary (resets every day at 00:00)

**Points**: Awarded once per day maximum

---

### Upon Completion (Immediate Reset, No Periods)

**Behavior**:

- Unlimited completions possible
- After approval, immediately returns to PENDING (available again)
- No period tracking (no midnight or due date boundaries)
- No blocking - can be claimed/approved/reset continuously

**Timeline Example**:

```
8:00 AM - Alice claims → Parent approves → Immediately returns to PENDING (available again)
8:05 AM - Alice claims → Parent approves → Immediately returns to PENDING (available again)
8:10 AM - Alice claims → Parent approves → Immediately returns to PENDING (available again)
```

**Best For**:

- ✅ Flexible tasks done anytime, multiple times
- ✅ "As needed" chores (water plants when needed, help sibling when asked)
- ✅ Practice activities (reading practice, instrument practice)
- ✅ Daily Multi-Times with time slots (slots advance immediately after approval)

**Period Tracking**: None (no boundaries)

**Points**: Awarded every time kid completes (unlimited)

---

### At Midnight (Multi) (Unlimited Per Day)

**Behavior**:

- Kid can complete **unlimited times per day**
- After approval, chore **stays APPROVED** but allows additional claims (bypasses "already approved" check)
- At midnight, approval resets to PENDING
- All completions within same day count toward daily total

**Timeline Example**:

```
Monday 8:00 AM - Alice claims "Help Sibling" → Parent approves → Chore stays APPROVED (but allows another claim)
Monday 10:00 AM - Alice claims again → Parent approves → Still APPROVED (2 completions today)
Monday 2:00 PM - Alice claims again → Parent approves → Still APPROVED (3 completions today)
Tuesday 12:00 AM (midnight) - Approval resets to PENDING, count resets, starts fresh
```

**Best For**:

- ✅ "Good behavior" chores that can happen multiple times
- ✅ Helping tasks (help sibling, be kind, show initiative)
- ✅ Practice-based activities where more is better

**Period Tracking**: Midnight boundary (count resets each day at 00:00)

**Points**: Awarded every time kid completes (unlimited per day)

**Use Case**: Parents want to encourage unlimited good behavior but still track daily totals

---

### At Due Date (Once) (One Per Cycle)

> [!IMPORTANT] > **Requires Due Date**: This reset type requires a due date to be configured. Use with Weekly, Biweekly, Monthly, or Custom frequencies.

**Behavior**:

- Kid can complete **once per reset cycle**
- After approval, chore stays APPROVED until due date passes
- When due date passes, approval resets to PENDING (available for next cycle)
- Blocks additional claims with "already_approved" error

**Timeline Example**:

```
Weekly Chore: "Clean Room" (Due: Sunday 8:00 PM)

Sunday 10:00 AM - Alice claims and completes → APPROVED
Sunday 3:00 PM - Alice tries to claim again → Blocked ("already approved")
Monday 12:00 AM - Due date passed, chore resets → PENDING (available for next week)
Next Sunday due again
```

**Best For**:

- ✅ Weekly allowance tasks (clean room once per week)
- ✅ Monthly chores (change air filter once per month)
- ✅ Scheduled assignments with specific deadlines

**Period Tracking**: Due date boundary (resets when due date passes)

**Points**: Awarded once per cycle maximum

**Requires**: Due date must be set (biweekly, monthly, or custom frequency)

---

### At Due Date (Multi) (Unlimited Per Period)

> [!IMPORTANT] > **Requires Due Date**: This reset type requires a due date to be configured. Use with Weekly, Biweekly, Monthly, or Custom frequencies.

**Behavior**:

- Kid can complete **unlimited times per cycle**
- After approval, chore **stays APPROVED** but allows additional claims (bypasses "already approved" check)
- Due date remains unchanged (doesn't advance with each completion)
- When due date passes, approval resets to PENDING for next period

**Timeline Example**:

```
Weekly Chore: "Extra Credit Reading" (Due: Sunday 8:00 PM)

Sunday 10:00 AM - Alice claims and completes → Parent approves → Stays APPROVED (allows another claim)
Sunday 2:00 PM - Alice claims and completes → Parent approves → Stays APPROVED (2 completions this week)
Sunday 6:00 PM - Alice claims and completes → Parent approves → Stays APPROVED (3 completions this week)
Sunday 8:00 PM - Due date passes → Approval resets to PENDING, new week starts, due next Sunday
```

**Best For**:

- ✅ Bonus opportunities with weekly/monthly cap (extra reading, extra chores)
- ✅ Optional tasks where multiple completions are encouraged
- ✅ Practice activities with periodic reset

**Period Tracking**: Due date boundary (new period when due date passes)

**Points**: Awarded every time kid completes (unlimited per cycle)

**Requires**: Due date must be set (biweekly, monthly, or custom frequency)

---

## Choosing Your Approval Reset Type

**Start with these questions**:

1. **Should this chore be done once or multiple times?**
   - Once → Use "Once" reset type
   - Multiple → Use "Multi" or "Upon Completion"

2. **When should it reset?**
   - Daily → Use "At Midnight"
   - Weekly/Monthly → Use "At Due Date"
   - Anytime/Flexible → Use "Upon Completion"

3. **Do you need period tracking?**
   - Yes (daily totals matter) → Use "At Midnight Multi"
   - Yes (weekly/monthly totals matter) → Use "At Due Date Multi"
   - No (just track completions) → Use "Upon Completion"

**Common Patterns**:

- **Daily routine (once)**: At Midnight Once
- **Daily routine (multiple allowed)**: At Midnight Multi
- **Weekly chore (once)**: At Due Date Once
- **Weekly chore (multiple allowed)**: At Due Date Multi
- **Flexible anytime tasks**: Upon Completion

---

## Pending Claim Action

**What This Controls**: What happens to claimed (but not yet approved) chores when the approval reset period arrives

> [!IMPORTANT]
> A chore is not considered complete until parent approves it. However, once a kid claims a chore, it prevents the chore from going overdue (protecting the kid's work).

When a kid claims a chore but parent hasn't approved it yet, the chore is in CLAIMED status. If the reset mechanism triggers while it's still claimed, you have three options:

### Option 1: Clear Pending ⭐ **DEFAULT**

**Behavior**: Kid's claim is cleared, approval resets to PENDING, kid does not earn credit

> [!WARNING]
> If parent doesn't approve before the reset period, kid gets **no credit** for the work done. Kid must claim again in the next period.

**Use When**: Teaching deadline adherence, strict timing requirements

**Example**:

```
Sunday 10:00 PM - Alice claims "Clean Room" (daily reset at midnight)
Monday 12:00 AM - Midnight reset triggers while still CLAIMED
Action: Claim cleared → Chore returns to PENDING → Alice can claim again, no credit for yesterday
```

**Best For**: Ensuring claims are approved promptly, teaching time management

---

### Option 2: Hold Claim Status (Await Approval/Rejection)

**Behavior**: Kid's claim is retained, chore stays CLAIMED, waiting for approval

> [!WARNING] > **Cycle Loss Risk**: While this protects the kid's claim, it can cause them to **lose a full cycle**. The claim was made yesterday, but approval happens today - the approval reset period won't trigger until tomorrow (losing today's opportunity).
>
> **Example**: Alice claims Monday at 11:00 PM (daily midnight reset). Parent approves Tuesday at 8:00 AM. The approval resets Wednesday at midnight - Alice loses Tuesday's completion opportunity entirely.

**Use When**: You want to protect kids' work despite late parent approval

**Example**:

```
Monday 11:00 PM - Alice claims "Make Bed" (daily midnight reset)
Tuesday 12:00 AM - Midnight passes, claim held (stays CLAIMED)
Tuesday 8:00 AM - Parent approves → Alice earns points → Approval resets immediately per reset type
Result: Alice loses Tuesday's completion opportunity (approval happened in Tuesday's period)
```

**Best For**: Protecting kids when parents may be unavailable to approve promptly

> [!TIP] > **Consider Auto-Approve instead**: If you find yourself using Hold Pending because parents can't approve promptly, Auto-Approve Pending (Option 3) may be a better choice - it awards credit immediately and avoids cycle loss.

---

### Option 3: Auto-Approve Pending Claims

**Behavior**: System automatically approves the claim at reset time, awards points, THEN resets per approval reset type

> [!TIP] > **Recommended over Hold Pending**: This avoids the cycle loss problem. If parent saw the claim but didn't get around to approving it, this option awards credit automatically and resets normally.

**Use When**: Trust-based system, reducing parent approval burden, avoiding cycle loss from late approvals

**Example**:

```
Monday 11:00 PM - Alice claims "Make Bed" (daily midnight reset)
Tuesday 12:00 AM - Midnight reset triggers
Action: System auto-approves → Alice earns points → Approval resets per configured type
Result: No cycle loss, Alice gets credit, chore available again
```

**Best For**: Older kids, trust-based systems, reducing parent workload, avoiding late-approval penalties

---

## Overdue Handling

**What This Controls**: When chores are marked as OVERDUE (past their due date) and how they recover from overdue state

> [!IMPORTANT] > **Claimed chores are NEVER marked overdue**, even if past due date. This protects kids who claimed on time but are waiting for parent approval.

---

### Option 1: Overdue Until Complete (Clear Late Approvals Immediately) (Default) ⭐ 🚀

**Behavior**: Chore goes overdue when due date passes, but if approved AFTER the approval reset boundary, immediately resets to PENDING

**The Key Innovation**: Detects late approvals and immediately recovers the chore for re-claiming

**Compatible With**: ALL approval reset types (At Midnight Once/Multi, At Due Date Once/Multi, Upon Completion) and ALL recurrence schedules

**How It Works**:

**Timeline Logic**:

1. Due date passes → Goes OVERDUE
2. Approval happens → Check if we crossed the reset boundary:
   - **Before reset boundary**: Normal behavior (stays APPROVED until scheduled reset)
   - **After reset boundary**: **Immediately resets to PENDING** (can be claimed again right away)

**Example 1 - Not Late (Normal Behavior)**:

```
Daily dishes due Tuesday 5:00 PM with AT_MIDNIGHT_MULTI

Tuesday 5:01 PM - Goes OVERDUE
Tuesday 6:00 PM - Approved (before Wednesday midnight) → Stays APPROVED ✓
Wednesday 12:00 AM - Scheduled reset, back to PENDING

Result: Normal behavior - approved within same period
```

**Example 2 - Late Approval (Immediate Reset)**:

```
Daily dishes due Tuesday 5:00 PM with AT_MIDNIGHT_MULTI

Tuesday 5:01 PM - Goes OVERDUE
Wednesday 8:00 AM - Approved (past Wednesday midnight boundary) → IMMEDIATELY resets to PENDING ✓
Wednesday 9:00 AM - Kid can claim again!

Result: Wednesday NOT lost - immediate reset recovered the earning window
```

**Example 3 - DAILY_MULTI Time Slots**:

```
Feed dog with time slots: 8:00 AM, 6:00 PM (due Tuesday 11:59 PM)

Tuesday 8:00 AM - Completed slot 1
Tuesday 6:00 PM - Completed slot 2
Tuesday 11:59 PM - Day ends
Wednesday 12:01 AM - Goes OVERDUE (not approved in time)
Wednesday 10:00 AM - Parent approves (late) → IMMEDIATELY resets to PENDING
Wednesday 10:05 AM - Kid can claim 8:00 AM slot for Wednesday!

Result: Wednesday's time slots NOT lost - immediate reset recovered them
```

**Why This Matters**:

- **Maximizes earning opportunities** - Late approval doesn't cost full day/period
- **Critical for DAILY_MULTI** - Time slots aren't lost due to late parent approval
- **Critical for MULTI resets** - Additional claims not blocked by late approval
- **Flexible for ONCE resets** - Kids get another chance immediately after late approval

**Use When**:

- ✅ Any chores where late parent approvals happen (ONCE or MULTI)
- ✅ High-frequency chores (dishes, laundry, daily routines)
- ✅ DAILY_MULTI chores with time slots
- ✅ AT_MIDNIGHT_MULTI or AT_DUE_DATE_MULTI scenarios
- ✅ Families who approve late often
- ✅ Maximum flexibility needed

**Best For**: ANY household where parents may not approve before the reset boundary. This option ensures kids don't lose earning opportunities due to late approvals.

**Impact of Being Late**: Kid did it late, parent approved it late → Kid still gets credit for yesterday **AND** can claim again today. No missed opportunities due to timing.

> [!TIP] > **Why Default**: This option provides the most flexibility. If you approve on time, behavior is normal. If you approve late, the kid doesn't lose that period's earning opportunity. It's the "best of both worlds" option.

---

### Option 2: Clear Overdue at Next Approval Reset

**Behavior**: Chore becomes OVERDUE, then automatically clears when approval reset runs (even if not approved)

**Special Requirement**: **ONLY works with "At Midnight" approval reset types**

**How It Works**:

```
Sunday 8:00 PM - Due date passes → Chore marked OVERDUE
Monday 12:00 AM - Midnight reset runs → Overdue cleared, chore returns to PENDING (even if never approved)
```

**Impact of Being Late**: Kid did it late, parent approved it late → Kid gets credit for yesterday, but the missed opportunity is "hidden" because overdue status auto-cleared at midnight. Less visible than Option 3's permanent overdue.

**Use When**: You want temporary overdue warnings that automatically clear each day

**Best For**: Daily chores with midnight reset, teaching deadlines without permanent overdue status

> [!WARNING]
> This option is **INVALID** with "At Due Date" or "Upon Completion" reset types. The integration will prevent this combination during setup.

---

### Option 3: At Due Date - Overdue Until Complete

**Behavior**: Chore is marked OVERDUE when due date passes. Overdue status persists until parent approves (or kid completes if auto-approve).

**Example**:

```
Weekly room clean
Due: Sunday 8:00 PM

Scenario A (Not Claimed):
Sunday 8:01 PM - Chore marked OVERDUE (visual warning to kid)

Scenario B (Claimed):
Sunday 7:00 PM - Alice claims
Sunday 9:00 PM - Parent approves (past due) → No overdue status, Alice gets full credit
```

**Impact of Being Late**: Kid did it late → Chore showed OVERDUE until approved. Kid missed the opportunity to complete on time, and it's visible. Next cycle starts fresh, but this cycle was "late."

**Recovery**: Stays overdue until approved, then stays APPROVED until next scheduled reset

**Best For**: Families who want clear accountability for missed deadlines, teaching time management

---

### Option 4: Never Overdue

**Behavior**: Chore never shows overdue status, regardless of due date

**Use When**: You want flexible deadlines, no pressure/stress

**Example**:

```
Due: Sunday 8:00 PM
Monday 10:00 AM - Chore still shows PENDING (not overdue)
Alice can still claim and complete normally
```

**Best For**: Flexible households, avoiding deadline stress, accommodating unpredictable schedules, kids who get discouraged by overdue status

---

## Auto-Approve

**What This Controls**: Whether parent approval is required or chores auto-approve on claim

**Default**: Manual approval required (unchecked)

**When Checked (Auto-Approve Enabled)**:

- Kid claims chore → Immediately approved
- Points awarded instantly
- No parent approval step
- Chore resets per approval reset type

**Use When**:

- ✅ Trust-based system for older kids
- ✅ Reducing parent workload
- ✅ Simple chores that don't need verification

**When to Avoid**:

- ❌ Tasks requiring quality check
- ❌ Teaching responsibility and verification
- ❌ Younger kids who need oversight

---

## Frequency

The frequency determines the recurrence pattern and reset schedule.

### None (One-Time)

**Behavior**: Chore never recurs, completes once

**Use For**: Special projects, one-off tasks

**Example**: "Clean out garage" (doesn't need to repeat)

**Due Date**: Optional (can set deadline or leave open-ended)

---

### Daily

**Behavior**: Chore resets every day based on approval reset type

**Use For**: Daily routines, morning/evening tasks

**Example**: "Make bed" (resets every morning)

**Period**: 24-hour cycle, typically midnight to midnight

**Due Date**: Optional (commonly used for morning/evening deadlines)

---

### Daily Multi

**Behavior**: Chore appears multiple times per day with specific time slots

**Use For**: Meal-related tasks, pet care, medication reminders

**Examples**:

- Feed dog (8:00 AM, 6:00 PM)
- Take medicine (morning, afternoon, evening)
- Brush teeth (7:00 AM, 8:00 PM)

> [!NOTE]
> Daily Multi requires additional time slot configuration and is available through **Settings → Configure** after initial integration setup. Start with simpler frequencies during initial setup.

**Requirements**:

- ✅ Must set due date (time slots need reference point)
- ✅ Works with **all completion criteria** (Independent, Shared All, Shared First)
- ❌ Invalid with **At Midnight\*** approval reset types (use Upon Completion or At Due Date instead)

> [!IMPORTANT] > **Due Date for Daily Multi**: The due date provides the **date portion only** (e.g., "start scheduling on January 15"). The **time portion of the due date is ignored** and replaced by the time slots you configure (e.g., 08:00, 18:00). Think of it as "which day to start" rather than "when it's due."

**Per-Kid Times**:

| Completion Criteria   | Per-Kid Times                          |
| --------------------- | -------------------------------------- |
| Independent (1 kid)   | Single time slot set                   |
| Independent (2+ kids) | Each kid can have different time slots |
| Shared (All)          | All kids share same time slots         |
| Shared (First)        | All kids share same time slots         |

**Example (Independent with 2+ kids)**:

```
Feed Dog:
- Alice: 8:00 AM, 6:00 PM
- Bob: 9:00 AM, 7:00 PM
```

**Time Format**: Enter times as pipe-separated 24-hour format

```
08:00|12:00|18:00  (8am, 12pm, 6pm)
```

> [!NOTE]
> When you configure Daily Multi (available after initial setup), a **Per-Kid Schedule helper** appears where you set times for each kid.

---

### Weekly

**Behavior**: Chore resets every 7 days from due date

**Use For**: Weekly chores, allowance tasks

**Example**: "Clean room" (every Sunday)

**Period**: 7-day cycle from due date

**Due Date**: Required (determines which day of week)

---

### Biweekly

**Behavior**: Chore resets every 14 days from due date

**Use For**: Biweekly chores, alternating schedules

**Example**: "Change bed sheets" (every other Sunday)

**Period**: Exactly 14 days (no month-based variation)

> [!IMPORTANT] > **Due Date**: Required - Biweekly recurrence requires a due date to be configured. The integration will enforce this rule.

---

### Monthly

**Behavior**: Chore resets monthly based on due date, with weekday snapping

**Use For**: Monthly maintenance tasks

**Example**: "Change air filter" (first Sunday of each month)

**Period**: 28-37 days (accounts for month length + optional weekday snap)

> [!IMPORTANT] > **Due Date**: Required - Monthly recurrence requires a due date to be configured. The integration will enforce this rule.

**Weekday Snapping**: If due date falls on specific weekday, next due date snaps forward to same weekday in next month

---

### Custom

**Behavior**: Chore resets at fixed calendar intervals (every N hours/days/weeks)

**Use For**: Non-standard schedules

**Configuration**:

- **Custom Interval**: Number (e.g., 3)
- **Custom Unit**: hours, days, or weeks

**Examples**:

- Every 3 days: Interval=3, Unit=days
- Every 2 weeks: Interval=2, Unit=weeks
- Every 4 hours: Interval=4, Unit=hours

> [!IMPORTANT] > **Due Date**: Required for Custom recurrence using days or weeks units. The integration will enforce this rule. Optional for hours unit.

**Reset Timing**: Resets at fixed intervals from original due date

---

### Custom From Completion

**Behavior**: Works exactly like **Custom** scheduling, including respecting the configured approval reset type. The only difference: next due date is calculated from last approval datetime instead of from the current due date.

**Use For**: Rolling schedules where timing depends on when task was actually completed

**Key Difference from Custom**:

- **Custom**: Next due date = current due date + interval (fixed calendar schedule, e.g., "every Monday")
- **Custom From Completion**: Next due date = last approval datetime + interval (rolling schedule, e.g., "3 days after last completion")
- **Both**: Respect the configured approval reset type (at_midnight, at_due_date, upon_completion)

**Examples**:

- Water plants every 3 days (counts from last watering, not calendar)
- Change air filter every 90 days (counts from last change, ensures full interval between changes)
- Clean fridge every 2 weeks (counts from last cleaning, adapts to when you actually cleaned it)

**Configuration**:

- **Custom Interval**: Number
- **Custom Unit**: hours, days, or weeks

**Use When**: Tasks where you want the interval to start from actual completion, not a fixed calendar date

---

### Frequency Comparison Table

| Frequency            | Period Length      | Due Date Required | Best For               |
| -------------------- | ------------------ | ----------------- | ---------------------- |
| None                 | One-time           | Optional          | Special projects       |
| Daily                | 24 hours           | Optional          | Daily routines         |
| Daily Multi          | Multiple/day       | Required          | Meal times, pet care   |
| Weekly               | 7 days             | Required          | Weekly chores          |
| Biweekly             | 14 days            | Required          | Alternating schedules  |
| Monthly              | 28-37 days         | Required          | Monthly maintenance    |
| Custom               | N hours/days/weeks | Required          | Non-standard intervals |
| Custom From Complete | N after completion | Required          | Flexible timing        |

---

## Applicable Days

**What This Controls**: Which days of the week the chore will be scheduled

**Default**: **Leave blank** (empty) = All days valid

> [!IMPORTANT] > **Do NOT select all 7 days manually** - this is redundant and extra work. Leaving the field blank automatically means "all days valid." **Only add days if you want to RESTRICT** which days the chore can be done.

**When to Add Days** (restriction mode):

- ✅ School-day-only chores → Select Mon-Fri only
- ✅ Weekend chores → Select Sat-Sun only
- ✅ Specific day chores → Select single day (e.g., "Wednesday is laundry day")

**How It Works**:

- **Blank/Empty**: Chore available every day (no restrictions)
- **Days selected**: Chore only available on those days; unavailable on others
- If due date falls on non-applicable day, snaps forward to next applicable day

**Example** (restriction):

```
Chore: "Do Homework"
Applicable Days: Mon, Tue, Wed, Thu, Fri (restrict to school days only)
Result: Saturday/Sunday - Chore not available, kid can't claim
```

**Example** (no restriction):

```
Chore: "Make Bed"
Applicable Days: (blank/empty)
Result: Chore available every day of the week
```

**Per-Kid Applicable Days**:
With Independent mode + 2+ kids, customize days per kid:

```
Chore: "Do Dishes"
- Alice: Mon, Wed, Fri (Alice's days)
- Bob: Tue, Thu, Sat, Sun (Bob's days)
```

**Result**: Chore alternates between kids by day of week. Alice can only claim Mon/Wed/Fri, Bob can only claim Tue/Thu/Sat/Sun.

> [!TIP]
> Per-kid applicable days (available through **Settings → Configure** after initial setup) are perfect for rotating schedules or age-based responsibilities. See [Advanced Features](Configuration:-Chores-Advanced.md#per-kid-applicable-days) for details.

---

## Due Date & Time

**What This Controls**: When the chore should be completed

**When Required**:

- ✅ Daily Multi frequency (time slots need reference)
- ✅ Weekly frequency (determines day of week)
- ✅ Biweekly frequency
- ✅ Monthly frequency
- ✅ Custom frequency (days/weeks unit)

**When Optional**:

- Daily frequency (can use for morning/evening deadlines)
- None frequency (can set deadline or leave open)

**Format**: Date + Time (e.g., 2026-01-15 20:00:00)

**Timezone**: Uses your Home Assistant timezone

**Per-Kid Due Dates**:
With Independent mode, each kid can have individual due dates (customizable after initial setup):

```
Chore: "Turn in Homework"
- Alice: Monday 8:00 PM (her teacher's deadline)
- Bob: Tuesday 8:00 PM (his teacher's deadline)
```

---

## Show in Calendar

**What This Controls**: Whether chore appears in Home Assistant calendar entities

**Default**: Checked (visible in calendar)

**When to Uncheck**:

- Chore doesn't have specific timing requirements
- Avoiding calendar clutter
- Task is "as needed" rather than scheduled

**When Checked**: Chore appears in calendar views with due date/time

---

## Enable Notifications

**What This Controls**: Whether kids receive notifications for this chore

**Default**: Checked (notifications enabled)

> [!TIP]
> Notification preferences (due date reminders, overdue alerts, etc.) are configured per-chore in the chore configuration form. Each chore can have different notification settings to reduce notification noise while keeping important alerts active.

**Notification Types**:

- **Due Date Reminders**: 30 minutes before chore becomes due (requires Mobile Notify Service set in kid configuration)
- **Overdue Alerts**: When chore passes due date without completion
- **Claim**: Kid claims chore
- **Approval**: Parent approves chore
- **Disapproval**: Parent rejects chore (with reason)

**When to Uncheck**:

- Reducing notification noise for low-priority chores
- Self-managed chores (kids check dashboard themselves)
- Chores without due dates (no due date reminder needed)

---

## Validation Rules

The integration prevents certain invalid combinations:

### Rule 1: Daily Multi + At Midnight Reset = Invalid

**Why**: Daily Multi uses time slots (UPON_COMPLETION reset), At Midnight uses day boundaries (incompatible)

**Error**: `daily_multi_requires_compatible_reset`

**Solution**: Use "Upon Completion" or "At Due Date" reset types with Daily Multi frequency

---

### Rule 2: Daily Multi Requires Due Date

**Why**: Time slots in Daily Multi need a reference date to begin scheduling

**Error**: `daily_multi_due_date_required`

**Solution**: Set a due date when using Daily Multi frequency

---

### Rule 3: Biweekly/Monthly/Custom Require Due Date

**Why**: These frequencies calculate next occurrence from due date anchor point

**Solution**: Set a due date when using these frequencies

---

### Rule 4: At Due Date Reset Requires Due Date

**Why**: At Due Date reset types need a due date to determine when period resets

**Error**: `at_due_date_reset_requires_due_date`

**Solution**: Set a due date when using "At Due Date (Once)" or "At Due Date (Multi)" reset types

**Exception**: Independent chores with multiple kids can use per-kid due dates (set after creation)

---

### Rule 5: Overdue Handling + Approval Reset Compatibility

**"Clear Overdue at Next Scheduled Reset"** (Option 2):

- **Requires**: "At Midnight Once" or "At Midnight Multi" approval reset type
- **Why**: This overdue type clears at midnight reset, incompatible with other reset types

**"Clear Overdue Immediately When Approved Late"** (Option 1 - Default):

- **Compatible with**: ALL approval reset types (At Midnight, At Due Date, Upon Completion)
- **Works with**: ALL recurrence schedules
- **Why Default**: Provides maximum flexibility - use this instead of Option 2 in most cases

---

### Rule 6: At Least One Kid Must Be Assigned

**Why**: Chores without assigned kids cannot be completed

**Error**: `no_kids_assigned`

**Solution**: Assign at least one kid to the chore

---

## Common Configuration Patterns

### Daily Morning Routine (Once)

```
Name: Make Bed
Completion Criteria: Independent
Frequency: Daily
Approval Reset: At Midnight (Once)
Overdue: Clear Overdue Immediately When Approved Late
Due Date: 8:00 AM daily
Points: 10
```

**Result**: Kid can complete once per day, resets at midnight, encouraged to do by 8am. If parent approves late (next day), kid can claim again immediately.

---

### Weekly Allowance Chore

```
Name: Clean Room
Completion Criteria: Independent
Frequency: Weekly
Approval Reset: At Due Date (Once)
Overdue: Clear Overdue Immediately When Approved Late
Due Date: Sunday 8:00 PM
Points: 50
```

**Result**: Kid completes once per week, due Sunday evening, resets when due date passes. Late approval doesn't cost next week's opportunity.

---

### Family Cleanup (All Kids)

```
Name: Clean Living Room
Completion Criteria: Shared (All)
Frequency: Daily
Approval Reset: At Midnight (Once)
Overdue: Never Overdue
Due Date: 7:00 PM daily
Points: 20 (per kid)
```

**Result**: All kids must complete before midnight, each earns 20 points, chore resets at midnight. No overdue stress.

---

### Pet Care (Multiple Times Per Day)

```
Name: Feed Dog
Completion Criteria: Independent
Frequency: Daily Multi
Time Slots: 8:00 AM, 6:00 PM
Approval Reset: Upon Completion
Overdue: Clear Overdue Immediately When Approved Late
Due Date: Today 8:00 AM (date only, times from slots)
Points: 5 (per time slot)
```

**Result**: Kid earns 5 points for each feeding (8am and 6pm slots). If parent approves late the next morning, kid can immediately claim that day's 8am slot (not lost). Critical for maximizing time slot opportunities.

---

### Flexible Task (Any Kid)

```
Name: Take Out Trash
Completion Criteria: Shared (First)
Frequency: None (or Daily)
Approval Reset: Upon Completion
Overdue: Never Overdue
Points: 15
```

**Result**: Whoever sees trash needs taking can claim it. First kid to claim owns the task. After completion, chore becomes available again immediately.

---

## Next Steps

**Mastered the basics?** Continue learning:

- **[Advanced Features Guide](Configuration:-Chores-Advanced.md)** - Per-kid customization, custom intervals, complex scheduling
- **[Tips & Tricks](Tips-&-Tricks-Automations-with-KidsChores.md)** - Automations, dashboard examples, advanced use cases

**Questions?** Check the [FAQ](FAQ.md) or join the community discussion.

---

**Last Updated**: v0.5.0 (January 2026)
