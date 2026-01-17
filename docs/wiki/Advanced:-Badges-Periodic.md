# Advanced Mechanics: Missions & Contracts

This guide details the **Periodic Badge** engine (Daily, Weekly, Periodic). Unlike Ranks, these are parallel missions used to enforce habits ("Clean Room") or create contracts ("No Sass").

## The Core Concept: The Scope

While Ranks look at _all_ points, Missions can be surgical. You define exactly what counts using **Target Types** and **Tracked Chores**.

### 1. Advanced Scope & Filtering

By default, a badge tracks "All Chores." You can narrow this focus to create "Specialist" badges.

- **Scenario:** "The Dishwasher King."
- **Configuration:**
  - **Target:** 10 Count.
  - **Frequency:** Weekly.
  - **Tracked Chores:** Select _only_ "Load Dishwasher" and "Unload Dishwasher."
- **Result:** The kid can clean their room 50 times, but the badge progress will sit at 0%. Only dishwasher activities move the needle.

### 2. Strict Mode (No Overdue)

If you select a Target Type ending in **(No Overdue)**, the logic changes from "Accumulation" to "Survival."

- **The Logic:** The system checks the `last_overdue` timestamp of every **Tracked Chore**.
- **The Fail State:** If _any_ tracked chore goes overdue even once during the badge cycle, the badge status calculates as **0%**.
- **Recovery:** The badge cannot be earned until the cycle resets (e.g., next Monday).
- **Use Case:** "Perfect Week." Use this to reward punctuality rather than just completion.

### 3. The Contract (Auto-Penalties)

Periodic Badges are the only place where **Penalties** are automated based on time.

- **The Logic:** `If Date > End_Date AND Progress < 100% -> Apply Penalty`.
- **The Setup:**
  1.  Create a Penalty Entity (e.g., "Missed Quota: -50 Points").
  2.  Create a Weekly Badge (e.g., "Clean Room").
  3.  Set Awards -> **Penalty** -> "Missed Quota".
- **The Outcome:** This creates a binding contract. If the kid fails to clean their room by Sunday night, the system automatically deducts 50 points on Monday morning.

### 4. Logic Trap: The "Shared First" Conflict

Be extremely careful when combining **Shared (First)** chores (Races) with **Periodic Badges**.

- **The Trap:**
  - Badge Requirement: "Complete 100% of Assigned Chores."
  - Chore: "Feed Dog" (Shared First) assigned to Kid A and Kid B.
  - **Outcome:** Kid A feeds the dog. Kid B's chore status becomes `Completed by Other`.
- **The Calculation:**
  - The badge logic sees Kid B has 1 assigned chore.
  - The badge logic sees Kid B has 0 completions.
  - **Result:** Kid B fails the badge (0% completion).
- **The Fix:** You **must** use the **Tracked Chores** filter to exclude "Shared First" chores from completionist badges, or accept that the badges are competitive.

### 5. Special Occasions

Special Occasion badges are simply Periodic badges with a duration of exactly 24 hours.

- **Hidden Default:** The target defaults to **1 Chore Count**.
- **Behavior:** The badge is "In Effect" only on that specific date. The moment the kid completes _any_ single chore on that day, the badge is awarded (along with any Birthday/Holiday loot).
