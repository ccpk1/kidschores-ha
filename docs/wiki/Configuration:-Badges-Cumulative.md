# Configuration: Cumulative Badges

**Target Audience**: All Users
**Prerequisites**: [Points System configured](Configuration:-Points.md), Kids created
**Covers**: Creating and configuring cumulative badges for lifetime achievement tracking

---

## Overview

Cumulative badges reward kids for reaching **lifetime point milestones**. They're perfect for long-term motivation and celebrating major achievements.

**Key Features**:

- **Lifetime tracking**: Badge progress never resets (tracks total points earned ever)
- **Permanent achievement**: Highest badge earned is never removed
- **Optional maintenance**: Require recurring points to keep multiplier active
- **Themed sets**: Assign different badge themes to different kids (Bronze/Silver/Gold for older, Beginner/Pro/Legend for younger)
- **Demotion system**: Kids can drop one level if maintenance not met (but never lose highest badge earned)

**What Makes Cumulative Different**:

- ❌ No tracked chores (counts ALL points from ALL sources: chores, bonuses, manual adjustments)
- ❌ No time-bound targets (unlike periodic badges which reset weekly/monthly)
- ✅ Progress accumulates forever
- ✅ Multiple badges work together as tiers (Bronze → Silver → Gold)

> [!NOTE] > **Legacy Badge Conversion**: Pre-v0.5.0 badges automatically convert to cumulative type during migration (points-only, chore counts no longer supported).

---

## Creating Cumulative Badges

### Initial Setup (Config Flow)

During integration setup:

1. **Badge Count**: Enter number of badges (e.g., 3 for Bronze/Silver/Gold)
2. For each badge, configure fields (see below)
3. Badges default to cumulative type during setup

### Post-Setup (Options Flow)

Navigate to: **Settings** → **Devices & Services** → **KidsChores** → **Configure** → **Manage Badges** → **Add Badge** → **Add Cumulative Badge**

---

## Configuration Fields

### Basic Information

| Field           | Required | Default                   | Description                                                    |
| --------------- | -------- | ------------------------- | -------------------------------------------------------------- |
| **Badge Name**  | ✅ Yes   | None                      | Unique name displayed in UI (e.g., "Bronze Badge", "Beginner") |
| **Description** | ❌ No    | Empty                     | Purpose or criteria explanation (optional)                     |
| **Labels**      | ❌ No    | None                      | Categorization tags (e.g., "tier-1", "beginner")               |
| **Icon**        | ❌ No    | `mdi:shield-star-outline` | Material Design Icon (e.g., `mdi:shield-bronze`, `mdi:medal`)  |

**Tips**:

- Use descriptive names: "Bronze Badge" clearer than "Badge 1"
- Icons help visual distinction: `mdi:shield-bronze`, `mdi:shield-silver`, `mdi:shield-crown`
- Labels useful for filtering in automations

---

### Target Settings

| Field                  | Required | Default | Description                                                         |
| ---------------------- | -------- | ------- | ------------------------------------------------------------------- |
| **Threshold Value**    | ✅ Yes   | 50.0    | Lifetime points required to earn badge                              |
| **Maintenance Points** | ❌ No    | 0       | Min points per cycle to keep multiplier active (0 = no maintenance) |

**Target automatically uses lifetime points** (no target type selector for cumulative badges).

> [!TIP] > **Threshold Recommendations**: Space badges 1-2 months apart minimum. For 5 chores/day at 10 points each (350 pts/week):
>
> - **Level 1**: 1000-1500 points (~3-4 weeks)
> - **Level 2**: 2500-3500 points (~7-10 weeks)
> - **Level 3**: 5000+ points (~14+ weeks)
>
> Consider badge multipliers accelerate progress. Kids earning at 1.2x will reach thresholds ~17% faster.

---

### Assigned Kids (Required)

| Field             | Required | Description                                           |
| ----------------- | -------- | ----------------------------------------------------- |
| **Assigned Kids** | **Yes**  | Kids who can earn this badge. Must select at least 1. |

**Assignment Behavior**:

- **Mandatory Selection**: You MUST explicitly select which kids can earn this badge
- **No Global Default**: There is no "Apply to All" toggle — to make a badge available to all kids, you must manually select each kid
- **Un-Assignment**: If you edit a badge and uncheck a kid, the system immediately removes that badge's progress data from their profile

> [!IMPORTANT] > **Assignments are Required**: Badge assignments require explicit selection. The integration will not allow you to create a badge without assigning it to at least one kid.

**Use kid assignment** for themed badge sets:

- Sarah (older): Bronze/Silver/Gold badges
- Tommy (younger): Beginner/Pro/Legend badges

---

### Awards (Optional)

Select what kids receive when badge is earned or maintenance cycle completes:

| Field                 | Required       | Default | Description                                                     |
| --------------------- | -------------- | ------- | --------------------------------------------------------------- |
| **Award Items**       | ❌ No          | None    | Select: points, rewards, bonuses, multiplier                    |
| **Award Points**      | ❌ Conditional | 0       | Points granted (if "points" selected)                           |
| **Points Multiplier** | ❌ Conditional | 1.0     | Points multiplier while badge active (if "multiplier" selected) |
| **Award Rewards**     | ❌ Conditional | None    | Auto-grant rewards (if "rewards" selected)                      |
| **Award Bonuses**     | ❌ Conditional | None    | Auto-grant bonuses (if "bonuses" selected)                      |

**Award Items** determines which fields appear. Select one or more:

- **points**: Grant points immediately when badge earned
- **multiplier**: Apply multiplier to future points earned (most common)
- **rewards**: Automatically grant selected rewards
- **bonuses**: Automatically grant selected bonuses

> [!TIP] > **Multiplier Guidance**:
>
> - **10 points per chore**: Use 1.1x - 1.2x multipliers
> - **50 points per chore**: Use 1.02x - 1.05x multipliers (higher base points = smaller multiplier)
>
> Multiplier applies to chores and bonuses (NOT to rewards, penalties, or manual adjustments).

---

### Maintenance Cycle (Optional)

Optional recurring requirement to keep multiplier active. Badge remains earned, but kid drops one level if maintenance not met.

| Field                    | Required       | Default | Description                                                |
| ------------------------ | -------------- | ------- | ---------------------------------------------------------- |
| **Recurring Frequency**  | ❌ No          | None    | Cycle frequency: daily, weekly, monthly, quarterly, yearly |
| **Custom Interval**      | ❌ Conditional | None    | Number (if frequency = custom)                             |
| **Custom Interval Unit** | ❌ Conditional | None    | Unit: days, weeks, months (if frequency = custom)          |
| **Start Date**           | ❌ No          | None    | Optional cycle start (calculated per kid if omitted)       |
| **End Date**             | ❌ No          | None    | Optional cycle end (calculated per kid if omitted)         |
| **Grace Period Days**    | ❌ No          | 0       | Extra days after cycle end to meet requirement             |

**How Maintenance Works**:

1. Kid earns badge → Multiplier activates
2. Maintenance cycle begins (weekly, monthly, etc.)
3. Kid must earn **Maintenance Points** during cycle
4. **If goal met**: Cycle resets, awards granted again, multiplier stays active
5. **If goal NOT met**: Kid drops one level (multiplier from next lower badge applies)
6. **Requalification**: Immediate when kid earns enough points (no full cycle required)

**Supported Frequencies**:

- `daily`, `weekly`, `monthly`, `quarterly`, `yearly`
- `custom` (**NOT supported** - use predefined frequencies only)

> [!NOTE] > **Per-Kid Tracking**: Each kid's maintenance cycle dates are tracked independently based on when they earned the badge. Maintenance dates are calculated per kid, not synchronized across all kids.

> [!TIP] > **Grace Period Example**: Monthly maintenance requires 200 points, grace period = 3 days.
>
> - Cycle ends Jan 31
> - Grace period extends to Feb 3
> - Kid has until Feb 3 to earn 200 points or drop one level

---

## How Cumulative Badges Work

### Earning Badges

1. Kid earns points from chores, bonuses, manual adjustments
2. **Lifetime points** (baseline + cycle points) tracked automatically
3. When threshold reached → Badge awarded automatically
4. **Highest badge earned** is permanent (never removed)
5. Awards granted (points, rewards, bonuses) and multiplier activates

**Tracking Sensor**: `sensor.kc_<kid>_badges` shows complete cumulative progress

### Demotion & Requalification

If maintenance cycle enabled:

**Demotion** (maintenance goal not met):

- Kid drops **one level only** (e.g., Gold → Silver)
- Multiplier switches to next lower badge's multiplier
- **Highest badge earned** unchanged (still Gold)
- **Current badge** reflects demotion (now Silver)

**Requalification** (immediate):

- Kid earns enough points to meet maintenance goal
- **Instantly** returns to higher badge level
- No need to complete full maintenance cycle

**Example**:

```yaml
Gold Badge:
  Threshold: 5000 points
  Maintenance: 200 points/month
  Multiplier: 1.5x

Silver Badge:
  Threshold: 2500 points
  Multiplier: 1.2x

Timeline:
  - Kid earns Gold (5000 pts) → 1.5x multiplier active
  - Month 1: Earns 180 pts (goal: 200) → Drops to Silver, 1.2x multiplier
  - Month 2: Earns 210 pts → Returns to Gold, 1.5x multiplier immediately
```

### Award Frequency

**Without maintenance**: Awards granted once when badge first earned

**With maintenance**: Awards granted:

- When badge first earned
- **Each time maintenance cycle completes successfully**
- Award count increments in sensor attributes

**Purpose**: Keeps kids motivated during long progression periods (1000+ points between badge levels).

---

## Cumulative Badge Progress Sensor

Each kid has **ONE sensor** showing all cumulative badge status: `sensor.kc_<kid>_badges`

**Key Attributes**:

- `current_badge_name`: Effective badge (reflects demotion if applicable)
- `highest_earned_badge_name`: Highest badge ever achieved (permanent)
- `next_higher_badge_name`: Next tier to earn
- `next_lower_badge_name`: Badge kid would drop to if demoted
- `points_to_next_badge`: Points needed to reach next tier
- `badge_status`: Current state (`active`, `grace`, `demoted`)
- `baseline_points`: Points from completed maintenance cycles
- `cycle_points`: Points earned in current cycle
- `award_count`: Number of times awards granted
- `all_earned_badges`: List of all badges earned (comma-separated)

**Example Attributes**:

```yaml
kid_name: Sarah
current_badge_name: Bronze
highest_earned_badge_name: Bronze
next_higher_badge_name: Silver
points_to_next_badge: 996
badge_status: active
baseline_points: 0
cycle_points: 1504
highest_badge_threshold_value: 1500
award_count: 1
```

---

## Badge Series Examples

### Bronze/Silver/Gold (Classic Tiers)

Standard progression for older kids or family-wide use:

```yaml
Bronze Badge:
  Threshold: 1500 points
  Maintenance: None (0)
  Multiplier: 1.1x
  Icon: mdi:shield-bronze
  Description: "A great start to building good habits!"

Silver Badge:
  Threshold: 3500 points
  Maintenance: 150 points/month
  Multiplier: 1.2x
  Icon: mdi:shield-silver
  Description: "Consistent performance recognized!"

Gold Badge:
  Threshold: 7000 points
  Maintenance: 200 points/month
  Multiplier: 1.3x
  Icon: mdi:shield-crown
  Description: "Elite status achieved!"
```

**Timeline** (5 chores/day, 10 pts each, 350 pts/week):

- Bronze: 4-5 weeks
- Silver: 10 weeks (from start)
- Gold: 20 weeks (from start)

**Multiplier Impact**: At 1.3x (Gold), 350 pts/week becomes 455 pts/week (~30% faster progress).

---

### Beginner/Pro/Legend (Gamer Theme)

XP-style progression for younger kids:

```yaml
Beginner Badge:
  Threshold: 1000 points
  Maintenance: None
  Multiplier: 1.1x
  Icon: mdi:star-outline
  Assigned: Tommy (younger kid)

Pro Badge:
  Threshold: 2500 points
  Maintenance: 100 points/month
  Multiplier: 1.2x
  Icon: mdi:star
  Assigned: Tommy

Legend Badge:
  Threshold: 5000 points
  Maintenance: 150 points/month
  Multiplier: 1.3x
  Icon: mdi:star-circle
  Assigned: Tommy
```

**Kid Assignment**: Use `Assigned Kids` to give Tommy his own themed badge set while Sarah uses Bronze/Silver/Gold.

---

### Star Collector Series (Visual Achievement)

Simple star-based milestones:

```yaml
One Star Badge:
  Threshold: 1200 points
  Maintenance: None
  Multiplier: 1.1x
  Icon: mdi:star-outline

Two Star Badge:
  Threshold: 2800 points
  Maintenance: 100 points/monthly
  Multiplier: 1.15x
  Icon: mdi:star-half-full

Three Star Badge:
  Threshold: 5500 points
  Maintenance: 150 points/monthly
  Multiplier: 1.25x
  Icon: mdi:star
```

---

### VIP Status (Elite Maintenance)

Single high-achievement badge with strict maintenance:

```yaml
VIP Badge:
  Threshold: 10000 points
  Maintenance: 500 points/monthly
  Multiplier: 1.5x
  Grace Period: 5 days
  Icon: mdi:crown-circle
  Description: "Elite performance with ongoing excellence!"
```

**Use Case**: Prestigious badge for high performers, strict monthly requirement, generous grace period.

---

## Managing Cumulative Badges

### Edit Badge

1. Navigate to: **Configure** → **Manage Badges** → **Edit Badge** → Select badge
2. Modify fields (name, threshold, maintenance, awards)
3. Submit changes

**Changes apply**: Immediately to all kids

> [!WARNING] > **Threshold Changes**: Lowering threshold doesn't retroactively award badges. Raising threshold doesn't remove badges already earned.

---

### Delete Badge

1. Navigate to: **Configure** → **Manage Badges** → **Delete Badge** → Select badge
2. Confirm deletion

**Impact**:

- Badge removed from system
- Kids' highest badge sensor recalculates
- Award history preserved
- Multiplier no longer applies

---

## Troubleshooting

| Issue                                  | Solution                                                                                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Kid not earning badge at threshold** | Check sensor `sensor.kc_<kid>_badges` → `cycle_points` + `baseline_points`. Verify sum ≥ threshold. Check `Assigned Kids` (if restricted). |
| **Multiplier not applying**            | Verify `badge_status: active` in sensor. If `demoted`, kid must meet maintenance goal. Check `points_multiplier` in badge awards.          |
| **Kid demoted unfairly**               | Check `reset_schedule` → `recurring_frequency`. Verify `maintenance_rules` value reasonable. Add/increase `grace_period_days`.             |
| **Progress not showing**               | Check `sensor.kc_<kid>_badges` exists and enabled. Verify integration loaded (Settings → Integrations → KidsChores).                       |
| **Wrong badge showing as current**     | Check `current_badge_name` vs `highest_earned_badge_name`. If different, kid demoted. Check `badge_status: demoted` and maintenance goal.  |

---

## Related Documentation

- [Points System](Configuration:-Points.md) - Understanding points earning and spending
- [Chores Configuration](Configuration:-Chores.md) - How kids earn points from chores
- [Rewards Configuration](Configuration:-Rewards.md) - How kids spend points on rewards
- [Technical Reference](Technical:-Entities-States.md) - Complete entity and attribute details

---

_Last updated: January 16, 2026 (v0.5.0)_
