# Advanced Mechanics: Cumulative Ranks

This guide details the logic behind **Cumulative Badges**. Unlike standard rewards, this system functions as an automated "RPG Leveling" engine. It manages status, applies global buffs (multipliers), and enforces activity requirements to prevent stagnation.

## The Core Concept: The Ladder

The Cumulative system forces a single status at a time. The system automatically sorts all Cumulative badges you create by their **Threshold Value** (Lifetime Points).

- **Logic:** A kid always holds the _highest_ badge they qualify for and can maintain.
- **Behavior:** You cannot manually "equip" these. The system promotes and demotes kids automatically based on the logic below.

### 1. The Multiplier (Global Buff)

This is the most powerful feature in KidsChores.

- **How it works:** When a kid earns a Rank (e.g., Gold), the system applies the configured **Point Multiplier** (e.g., 1.5x) to their profile.
- **The Math:** If a chore is worth 10 points, a 1.5x multiplier awards **15 points** immediately upon approval.
- **Persistence:** This multiplier stays active as long as the badge status is `active` or `grace`.
- **Demotion:** If a kid drops a rank, the multiplier immediately downgrades to the setting of the lower rank.

### 2. The Maintenance Engine

Earning a badge is a one-time event; keeping it is a recurring challenge. The system splits a kid's score into two buckets to manage this:

1.  **Baseline Points:** Points "locked in" from previous ranks.
2.  **Cycle Points:** Points earned _since_ the current maintenance cycle started.

**The Logic Loop:**
Every time the **Frequency** duration ends (e.g., Sunday night at midnight), the system evaluates:

- **Pass:** Did `Cycle Points` >= `Maintenance Points`?
  - **Result:** Status remains **Active**. Cycle Points reset to 0.
  - **Loot Trigger:** Any Rewards or Bonuses attached to this badge are **granted again**.
- **Fail:** Did `Cycle Points` < `Maintenance Points`?
  - **Result:** The kid enters the **Grace Period**.

### 3. Grace & Demotion

The Grace Period is a safety buffer. It allows a kid to keep their Rank and Multiplier for a few extra days to catch up.

- **State: Grace:**
  - The badge remains visible. The Multiplier remains active.
  - Points earned during Grace count toward the _current_ cycle.
- **State: Demoted:**
  - If the Grace Period expires and the target is still missed:
  - **Rank Drop:** The system finds the next lower Cumulative badge.
  - **Buff Loss:** The multiplier is downgraded.
  - **Wipe:** `Cycle Points` are reset to 0. Points earned during the failed Grace period do not carry over.

> ℹ️ **Strategy Tip: The Infinite Loot Loop**
> Cumulative Badges re-trigger their awards (Rewards/Bonuses) **every time** a maintenance cycle completes successfully.
>
> - **Risk:** If you attach a high-value Reward (e.g., "$10 Cash") to a badge with a "Daily" maintenance cycle, the kid will earn $10 _every day_ they meet the maintenance goal.
> - **Best Practice:** Attach high-value rewards to "One-Time" Achievements, and use Multipliers or small Bonuses for Cumulative Ranks.

---
