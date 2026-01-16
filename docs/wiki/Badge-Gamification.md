# Guide to Gamification: The Badge System

The Badge system is the gamification engine of KidsChores. It transforms a simple list of chores into a rewarding experience with Ranks, Multipliers, Quests, and Contracts.

This system is divided into two distinct concepts: **Ranks** (Cumulative) and **Missions** (Periodic).

---

## 1. The Two Badge Concepts

Before you configure a badge, decide which "Engine" you want to use.

### Type A: The Rank System (Cumulative Badges)

Think of this like an RPG Level (Bronze, Silver, Gold).

- **Behavior:** A kid holds **one** rank at a time based on their lifetime points.
- **The Power:** This is the only badge type that grants a **Global Point Multiplier** (e.g., earn 1.5x points on all chores).
- **Maintenance:** To keep a high rank, the kid must earn a specific number of points every week/month. If they fail, they enter a "Grace Period," and eventually drop to a lower rank (Demotion).

### Type B: The Mission System (Periodic & Daily Badges)

Think of these like Quests or Contracts.

- **Behavior:** A kid can work on **multiple** missions at once. They reset automatically (Daily, Weekly, Monthly).
- **The Power:** These track specific goals (e.g., "Clean room 5 days in a row" or "No overdue chores this week").
- **The Contract:** You can configure **Penalties** that automatically apply if the mission fails by the deadline.

---

## 2. Badge Types Explained

### Cumulative (Rank)

Use this to build long-term motivation.

- **Trigger:** Lifetime Points.
- **Awards:** Point Multipliers, One-time Rewards (e.g., a "Level Up" gift).
- **Example:** "Gold Tier." Requires 1000 Lifetime Points. Grants 1.2x points on all chores. Requires earning 50 points a week to maintain.

### Daily / Periodic (Mission)

Use this to build habits.

- **Trigger:** Points, Chore Count, or Streaks within a specific window.
- **Awards:** Items or Bonus Points given immediately upon completion.
- **Example:** "Week of Clean." Requires completing "Clean Room" 7 times in a weekly cycle.

### Special Occasion

Use this for events.

- **Trigger:** A specific date (Birthday, Holiday).
- **Behavior:** Active for exactly 24 hours. The first chore completed on that day triggers the reward.
- **Example:** "Birthday Bonus." Grants 500 points on July 14th.

### Linked

Use this to attach rewards to stats.

- **Trigger:** An Achievement or Challenge entity.
- **Behavior:** When the linked Achievement is earned, this badge grants a tangible reward.
- **Example:** Link a "Pizza" reward to the "100 Chores Total" Achievement.

---

### **Configuration Matrix**

| Badge Type     | Target Options           | Multiplier | Penalties | Rewards/Bonus | Reset Logic |
| :------------- | :----------------------- | :--------: | :-------: | :-----------: | :---------- |
| **Cumulative** | Points Only              |     ✅     |    ❌     |      ✅       | Maintenance |
| **Daily**      | Points, Count            |     ❌     |    ✅     |      ✅       | Midnight    |
| **Periodic**   | Points, Count, Streak, % |     ❌     |    ✅     |      ✅       | Frequency   |
| **Special**    | (Fixed: 1 Chore)         |     ❌     |    ❌     |      ✅       | Recurrence  |
| **Linked**     | (External Entity)        |     ❌     |    ❌     |      ✅       | N/A         |

## 3. Quick Start: Configuring a Badge

### How to Create a Rank (Cumulative)

1.  Go to **Settings > Devices & Services > KidsChores > Configure**.
2.  Select **Manage Badge** > **Add**.
3.  Choose **Cumulative**.
4.  **Badge Name:** Enter a name (e.g., "Gold Tier").
5.  **Target > Threshold Value:** The lifetime points needed to unlock this (e.g., 1000).
6.  **Maintenance Points:** Points needed per cycle to keep this rank (e.g., 50).
7.  **Awards > Points Multiplier:** Set the bonus (e.g., 1.2).
8.  **Assigned To:** Select the kids eligible for this rank.
9.  Click **Submit**.

> ℹ️ **Note:** The system automatically handles Demotion. If a kid fails maintenance and the grace period expires, they drop to the next lower Cumulative Badge you have defined.

### How to Create a Mission (Periodic)

1.  Go to **Settings > Devices & Services > KidsChores > Configure**.
2.  Select **Manage Badge** > **Add**.
3.  Choose **Periodic** (or **Daily**).
4.  **Target Type:** Choose your metric (e.g., "Streak: Selected Chores Completed").
5.  **Tracked Chores:** Select the specific chores that count (e.g., "Make Bed"). If left blank, _all_ chores count.
6.  **Reset Cycle:** Choose how often this resets (e.g., Weekly).
7.  **Awards:** Choose a Reward or Bonus points.
8.  **Penalties (Optional):** Select a penalty to apply if they fail the mission by the end of the week.
9.  Click **Submit**.

---

## 4. Accessing Badge Entities in Home Assistant

The system creates different sensors depending on the badge type.

### The Rank Sensor

- **Entity:** `sensor.kc_[kid_name]_badges`
- **State:** The name of the kid's current highest **Cumulative** badge (e.g., "Gold Tier").
- **Attributes to watch:**
  - `badge_status`: Shows `active`, `grace`, or `demoted`.
  - `maintenance_points_remaining`: How many points they need right now to save their rank.
  - `points_to_next_badge`: How far they are from the next level.

### The Mission Sensors

- **Entity:** `sensor.kc_[kid_name]_badge_progress_[badge_name]`
- **State:** A percentage (`0` to `100`) representing progress toward the goal.
- **Attributes to watch:**
  - `raw_progress`: The actual count (e.g., "3" chores done).
  - `threshold_value`: The goal (e.g., "5" chores).
  - `tracked_chores`: The specific chores required for this badge.

---

## 5. Critical Constraints & "Traps"

> ⚠️ **The "Race" Trap:**
> If you have a chore set to **Shared (First)** (a race between siblings), be careful with Periodic Badges.
> If Sibling A wins the race, Sibling B gets a `0` score for that chore. If Sibling B has a badge requiring "100% completion of assigned chores," **they will fail** because they lost the race.
> **Fix:** Use the **Tracked Chores** filter in the badge settings to exclude "Race" chores from completionist badges.

> ⚠️ **The Multiplier Rule:**
> You can **only** set Point Multipliers on **Cumulative** badges. You cannot create a temporary "Double Points Weekend" badge using the Periodic system. Multipliers are strictly for long-term Ranks.

> ⚠️ **Strict Mode:**
> If you select a Target Type that says **(No Overdue)**, the badge becomes "Strict." If a single tracked chore goes overdue during the cycle, the badge fails immediately (0%) and cannot be earned until the next reset.
