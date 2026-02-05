# Cumulative Badge Maintenance Logic - Complete Reference

**Version:** v0.5.0 (Schema v44)
**Status:** Authoritative Design Document
**Last Updated:** 2026-02-05

## Overview

This document defines the complete behavior of cumulative badge maintenance, grace periods, demotion, and promotion logic. All implementation must align with these rules.

## Data Model (Schema v44)

### Kid Cumulative Badge Progress Fields

```python
cumulative_badge_progress: {
    "status": str,                    # "active" | "grace" | "demoted" | null
    "current_badge_id": str | None,   # Badge currently displayed (affected by demotion)
    "highest_earned_badge_id": str | None,  # Highest badge ever earned (never decreases)
    "maintenance_points": float,      # Points earned since current cycle started
    "period_end": str | None,         # ISO datetime when maintenance check runs
    "grace_end": str | None,          # ISO datetime when grace period expires
}
```

### Key Concepts

- **Earned Points**: Total points earned from chores/bonuses (never decreases with spending)
  - Source: `point_periods.all_time.all_time.earned`
  - Used for: Initial badge qualification, badge progression
- **Maintenance Points**: Points earned since current maintenance cycle started
  - Source: `cumulative_badge_progress.maintenance_points`
  - Used for: Maintenance checks only
  - Resets: After successful maintenance check or demotion
- **Net Points (Balance)**: Current points balance (earned - spent)
  - Source: Kid's `points` field
  - **NEVER used for badge logic** - irrelevant to earning, maintaining, or demotion

## Initial Badge Earn

**Trigger:** Any time points are awarded

**Logic:**

```
if lifetime_earned >= badge.threshold:
    award_badge(badge)
```

**Result:**

- `status` = "active"
- `current_badge_id` = badge.id
- `highest_earned_badge_id` = badge.id
- `maintenance_points` = 0
- `period_end` = now + badge.maintenance_frequency
- `grace_end` = None
- Apply badge.multiplier to kid's profile
- Trigger badge awards (rewards/bonuses)

## Active Maintenance Cycle

**During the cycle:**

- Kid earns points from chores → `maintenance_points` increments
- Kid spends points on rewards → `maintenance_points` UNCHANGED (spending irrelevant)
- Multiplier remains active

**Example:**

- Bronze badge (1.2x multiplier, weekly maintenance, 150 pts threshold)
- Week starts: `maintenance_points` = 0
- Earn 200 pts: `maintenance_points` = 200
- Spend 180 pts: balance = 20, but `maintenance_points` = 200 (unchanged)

## Maintenance Check (at period_end)

**Trigger:** Scheduled task runs at `period_end` datetime

**Logic:**

```
if maintenance_points >= badge.maintenance_threshold:
    PASS
else:
    FAIL
```

### PASS Result

- `status` = "active" (stays active)
- `maintenance_points` = 0 (reset for new cycle)
- `period_end` = now + badge.maintenance_frequency (schedule next check)
- `grace_end` = None
- Re-trigger badge awards (**"Loot Loop"** - bonuses/rewards granted again)
- Multiplier stays active

### FAIL Result

- `status` = "grace" (enter grace period)
- `maintenance_points` UNCHANGED (kid can catch up)
- `period_end` UNCHANGED (or extended to grace_end?)
- `grace_end` = now + badge.grace_period_days
- Multiplier STAYS ACTIVE (1.2x still applies during grace)
- No awards triggered

## Grace Period

**Purpose:** Safety buffer - kid can catch up without losing rank

**During grace:**

- Badge remains visible
- Multiplier remains active (earning advantage persists)
- Kid earns points → `maintenance_points` increments
- Kid spends points → `maintenance_points` UNCHANGED

**Example:**

- Enter grace with `maintenance_points` = 100 (threshold = 150)
- Earn 60 more pts → `maintenance_points` = 160
- Spend 200 pts → balance crashes, but `maintenance_points` = 160

**Trigger:** Scheduled task runs at `grace_end` datetime

### Final Check Logic

```
if maintenance_points >= badge.maintenance_threshold:
    RESCUED
else:
    DEMOTED
```

### RESCUED Result (Passed During Grace)

- `status` = "active" (back to normal)
- `maintenance_points` = 0 (reset)
- `period_end` = now + badge.maintenance_frequency (new cycle)
- `grace_end` = None
- Trigger badge awards (caught up - loot granted)
- Multiplier stays active

### DEMOTED Result (Failed Grace Period)

- `status` = "demoted"
- `current_badge_id` = next_lower_badge.id (display changes)
- `highest_earned_badge_id` UNCHANGED (still shows Gold as earned)
- `maintenance_points` = 0 (WIPED - grace points lost)
- **CRITICAL**: `period_end` = now + **HIGHEST_EARNED_BADGE**.maintenance_frequency
  - NOT the demoted badge's frequency
  - Still evaluated on original badge's schedule
  - Prevents gaming by demoting to easier maintenance
- `grace_end` = None
- Multiplier = next_lower_badge.multiplier (downgrade applied)
- No awards triggered

## Demotion Details

**Badge Selection:**
Find next lower cumulative badge in ladder (sorted by threshold descending).

**If no lower badge exists:**

- `current_badge_id` = None (no badge displayed)
- Multiplier = 1.0 (default - no buff)
- `period_end` = now + highest_earned_badge.frequency (still on original schedule)

**Key Rule:** Maintenance schedule ALWAYS uses `highest_earned_badge.maintenance_frequency`, even when demoted.

**Why:** Prevents exploit where kid demotes to easier maintenance requirements (e.g., Bronze weekly → Silver daily → easier to maintain).

## Promotion from Demotion

**Trigger:** Any time points are awarded while status = "demoted"

**Logic:**

```
# Check if kid now qualifies for any higher badge
for badge in cumulative_badges_sorted_desc:
    if lifetime_earned >= badge.threshold:
        promote_to(badge)
        break
```

### Standard Re-Qualification (Back to Same Badge)

**Example:**

- Demoted from Gold to Silver
- `maintenance_points` = 0, `lifetime_earned` = 2900
- Earn 200 pts → `lifetime_earned` = 3100, `maintenance_points` = 200
- Check: Does 200 >= Gold.maintenance_threshold (150)? YES

**Result:**

- `status` = "active"
- `current_badge_id` = Gold
- `highest_earned_badge_id` = Gold (unchanged)
- `maintenance_points` = 0 (reset - new cycle)
- `period_end` = now + Gold.maintenance_frequency
- `grace_end` = None
- Multiplier = Gold.multiplier
- Trigger awards

### Skip-Level Promotion (Leap to Higher Badge)

**Example:**

- Kid earned Gold (3000 pts), demoted to Silver
- `highest_earned_badge_id` = Gold, `current_badge_id` = Silver
- `lifetime_earned` = 2900
- Platinum badge exists: threshold = 3500

**Scenario:**

- Earn 600 pts → `lifetime_earned` = 3500
- Check qualifications:
  - Platinum (3500)? 3500 >= 3500 → YES ✅

**Result:**

- `status` = "active"
- `current_badge_id` = Platinum (skipped Gold entirely)
- `highest_earned_badge_id` = Platinum (new high)
- `maintenance_points` = 0
- `period_end` = now + Platinum.maintenance_frequency
- `grace_end` = None
- Multiplier = Platinum.multiplier
- Trigger Platinum awards (not Gold awards)

**Why Skip Works:**

- Earned points check happens every award
- System finds highest badge kid qualifies for
- No requirement to re-earn intermediate badges

## Critical Rules Summary

### Rule 1: Earned vs Net Points

- **Badge qualification**: Uses `lifetime_earned` (never decreases)
- **Maintenance checks**: Uses `maintenance_points` (cycle counter)
- **Balance (net points)**: NEVER affects badge logic
- **Spending**: Cannot cause demotion (only affects balance)

### Rule 2: Maintenance Schedule Persistence

- Maintenance schedule uses `highest_earned_badge.maintenance_frequency`
- NEVER changes to demoted badge's frequency
- Persists until kid re-earns original badge or earns higher badge

### Rule 3: Multiplier Application

- Active during: "active" and "grace" status
- Downgraded during: "demoted" status (to lower badge's multiplier)
- Applies immediately to all earned points

### Rule 4: Promotion Logic

- Checks ALL badges sorted by threshold (descending)
- Awards highest qualified badge
- Can skip intermediate badges if lifetime_earned qualifies

### Rule 5: Award Triggers

- Triggered on: Initial earn, successful maintenance check, promotion from demotion
- NOT triggered on: Entering grace, demotion
- "Loot Loop": Awards re-trigger every successful maintenance cycle

## Example Scenarios

### Scenario 1: Maintenance Success with Spending

- Badge: Bronze (500 threshold, 150 maintenance, 1.2x multiplier, weekly)
- Starts week: `lifetime_earned` = 600, `maintenance_points` = 0, balance = 520
- Day 2: Earn 100 pts → `maintenance_points` = 100
- Day 3: Spend 200 on rewards → balance = 420, `maintenance_points` = 100 (unchanged)
- Day 5: Earn 80 pts → `maintenance_points` = 180
- Week end: Check 180 >= 150? YES → PASS, awards trigger, reset to 0

### Scenario 2: Grace Period Rescue

- Badge: Silver (2500 threshold, 300 maintenance, 1.4x multiplier)
- Maintenance check: `maintenance_points` = 250 < 300 → FAIL (grace)
- Grace day 1: Earn 60 pts → `maintenance_points` = 310
- Grace end: Check 310 >= 300? YES → RESCUED, back to active

### Scenario 3: Demotion & Skip-Level Promotion

- Badges: Bronze (500), Silver (2500), Gold (5000), Platinum (7500)
- Kid earned Gold, demoted to Silver
- `highest_earned_badge_id` = Gold, `lifetime_earned` = 4800
- Maintenance schedule = Gold's weekly (not Silver's daily)
- Earn 2800 pts → `lifetime_earned` = 7600
- Check: 7600 >= Platinum (7500)? YES → Promote to Platinum (skip Gold)

## Implementation Checklist

- [ ] Initial badge earn checks `lifetime_earned >= threshold`
- [ ] Maintenance checks compare `maintenance_points >= maintenance_threshold`
- [ ] Spending never affects `maintenance_points` or `lifetime_earned`
- [ ] Demotion uses `highest_earned_badge.frequency`, not demoted badge
- [ ] Promotion checks all badges sorted descending (allows skip-level)
- [ ] Awards only trigger on: earn, maintenance pass, promotion (not grace/demotion)
- [ ] Multiplier active during "active" and "grace", downgraded during "demoted"
- [ ] `highest_earned_badge_id` never decreases (historical record)

---

**End of Document**
