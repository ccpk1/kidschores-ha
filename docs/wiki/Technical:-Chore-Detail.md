This is a comprehensive, deep-dive technical analysis of the **Chore Entities, Logic, and Services** in KidsChores.

---

# KidsChores: Chore Technical Detail and Logic

**Technical Reference for Advanced Users & Developers**

A "Chore" in KidsChores is fundamentally a **Configuration Template**. When defined, the Coordinator instantiates distinct state machines for every assigned kid. The behavior of these state machines is governed by four interaction drivers.

---

## 1. Chore Logic Drivers

### Driver 1: Instantiation Logic (Completion Criteria)

_Key: `completion_criteria`_

This driver determines the relationship between the chore definition and the assigned kids.

| Mode               | Logic Model            | Data Storage        | Behavior                                                                                                                                           |
| :----------------- | :--------------------- | :------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Independent**    | **Parallel Instances** | `per_kid_due_dates` | Each kid has a completely separate state, due date, and schedule. Kid A can be `approved` while Kid B is `overdue`.                                |
| **Shared (All)**   | **Cooperative (AND)**  | `due_date` (Global) | **Aggregate State.** The Global Status only becomes `approved` when _ALL_ assigned kids complete it. UI shows `approved_in_part` during progress.  |
| **Shared (First)** | **Competitive (XOR)**  | `due_date` (Global) | **Race Condition.** The first kid to Claim/Approve wins. The coordinator immediately forces all other kids into `completed_by_other` (locked out). |

---

### Driver 2: The Scheduling Engine

_Key: `recurring_frequency` + `applicable_days`_

The scheduler combines an **Interval** (Frequency) with a **Filter** (Applicable Days) to calculate the `next_due_date`.

### **Recurrence Modes**

1.  **Calendar Snapping:** Standard `daily`, `weekly`, `monthly` modes reset based on calendar boundaries (e.g., Weekly resets on Monday).
2.  **Relative Interval:** `custom` adds X units to the _Previous Due Date_.
3.  **Sliding Window:** `custom_from_complete` adds X units to the _Actual Completion Timestamp_.
    - _Tech Note:_ Prevents "Schedule Compression." If a 3-day chore is done 2 days late, the next instance is scheduled 3 days from _now_, not tomorrow.
4.  **Slot-Based:** `daily_multi` parses a pipe-separated string (`08:00|14:00`). It calculates the next slot immediately upon completion.

#### **The "Snap-To" Filter**

`applicable_days` acts as a forward-scanning filter.

1.  Scheduler calculates `next_date` based on Frequency.
2.  Coordinator checks if `next_date` matches `applicable_days`.
3.  If invalid, it increments `next_date` until a valid day is found.

- **Per-Kid Forking:** In `Independent` mode, Kid A can be set to `['Mon']` and Kid B to `['Tue']` under the same Chore ID.

---

### Driver 3: The Reset Engine (Lifecycle)

_Key: `approval_reset_type` + `approval_reset_pending_claim_action`_

This driver manages the transition from `Approved` back to `Pending`. It also handles the critical race condition: **"The chore reset time arrived, but a claim is still pending."**

#### **Reset Triggers**

- **Midnight (Once/Multi):** Hard reset at 00:00 local time.
- **Due Date (Once/Multi):** Resets exactly when `Now > Due Date`.
- **Upon Completion:** Immediate reset. State transitions `Pending` -> `Approved` -> `Pending` instantly. (Used for infinite/paid tasks).

#### **Pending Claim Safety Net**

If a reset triggers while state is `claimed`:

1.  **Clear (Default):** Claim is deleted. Kid gets 0 points. Chore resets to Pending.
2.  **Hold:** Reset is aborted for that kid. Chore remains `claimed` (Late).
3.  **Auto-Approve:** Coordinator forces `approve_chore` (Awarding points) -> then resets to `pending`.

---

### Driver 4: Overdue & Backlog Logic

_Key: `overdue_handling_type`_

Determines the behavior of the chore _after_ the deadline passes.

| Type                        | Logic                                                                                | UX Impact                                                                                         |
| :-------------------------- | :----------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------ |
| **Overdue Until Complete**  | **Backlog.** State locks at `overdue`. Does NOT reset at next cycle.                 | Kid must finish Monday's chore to clear the slot for Tuesday.                                     |
| **Never Overdue**           | **Ghost.** State remains `pending` indefinitely.                                     | "Soft deadlines." No red icons, no badge penalties.                                               |
| **Clear at Reset**          | **Fresh Start.** State `overdue` -> `pending` at Reset time.                         | If Monday is missed, it's gone. Tuesday starts fresh.                                             |
| **Clear Immediate on Late** | **Catch-Up.** Acts like Backlog, but if approved late, immediately triggers a reset. | Prevents "Lost Days." Approving Monday's task on Tuesday morning spawns Tuesday's task instantly. |

---

### Technical Traps & Constraints

#### **2. The "Double Jeopardy" Trap**

- **Config:** `Overdue Until Reset` + `Pending Action: Clear`.
- **Scenario:** Kid claims at 11:59 PM. Parent sleeps. Midnight Reset fires.
- **Result:** Claim deleted. Chore resets. Kid did the work but lost the points and the record.
- **Fix:** Use `Auto-Approve` or `Hold` for this combination.

#### **3. Streak Calculation Limits**

- **Constraint:** The Streak engine strictly compares `last_completed` vs `yesterday`.
- **Result:** Streaks **ONLY** function for **Daily** frequencies. Weekly chores will always have a max streak of 1 (because the gap between completions > 1 day).

#### **4. Daily Multi Incompatibility**

- **Constraint:** `daily_multi` is incompatible with `at_midnight` resets.
- **Reason:** `daily_multi` requires the due date to shift forward _immediately_ upon completion to the next slot. `at_midnight` forces the chore to wait until 00:00, breaking the slot logic.

---

## 2. The Chore Entities

A "Chore" is not a single entity. It is a distributed system comprising three distinct sensor types and three interactive buttons, instantiated dynamically for every assigned kid.

### **A. Kid Chore Status Sensor (The "Chore State" Entity)**

**Class:** `KidChoreStatusSensor`
**Entity ID:** `sensor.kc_[kid]_chore_status_[chore_name]`
**Purpose:** Represents the specific relationship between **one kid** and **one chore**. This is the primary entity for Dashboard cards.

#### **State Values (The Lifecycle)**

- `pending`: Task is available to do.
- `claimed`: Kid has marked it done; waiting for approval.
- `approved`: Parent confirmed completion (Points awarded).
- `overdue`: Due date passed (`overdue_handling` is not "Never").
- `completed_by_other`: **(Shared First Only)** A sibling won the race; this kid is locked out.

#### **Attributes: Configuration & Schedule**

These attributes expose the _result_ of the schedule calculations, accounting for per-kid overrides.

- `recurring_frequency`: `daily`, `weekly`, `monthly`, `custom`, `daily_multi`.
- `custom_frequency_interval` / `custom_frequency_unit`: (e.g., `3` / `days`) if Custom.
- `applicable_days`: List of active days (e.g., `['mon', 'wed', 'fri']`).
  - _Logic:_ For **Independent** chores, this reflects the **Kid's specific schedule** (if overridden), not necessarily the template.
- `due_date`: (ISO String) The effective deadline for _this_ kid.
- `approval_reset_type`: Critical logic driver (See Section 3).
- `completion_criteria`: `independent`, `shared_all`, `shared_first`.

#### **Attributes: Statistics (Per-Chore History)**

Specific stats for _this specific chore_ for _this specific kid_.

- `chore_points_earned`: Total points earned from this chore.
- `chore_approvals_count`: Total times approved.
- `chore_claims_count`: Total times claimed.
- `chore_current_streak`: Consecutive completions (based on recurrence).
- `last_claimed` / `last_approved`: Timestamps of last actions.

#### **Attributes: UI Helpers**

- `can_claim`: `Boolean` (True if state is Pending/Overdue/Disapproved).
- `can_approve`: `Boolean` (True if state is Claimed).
- `claim_button_eid`, `approve_button_eid`, `disapprove_button_eid`: **Direct Entity IDs** for the buttons below.

---

### **B. System Shared State Sensor (The "Global" Monitor)**

**Class:** `SystemChoreSharedStateSensor`
**Entity ID:** `sensor.kc_[chore_name]_global_status`
**Created For:** Only `shared_all` and `shared_first` chores.

#### **State Values (Aggregate Logic)**

- `pending`: No one has started.
- `claimed_in_part`: At least one kid claimed; others pending.
- `approved_in_part`: **(Shared All)** At least one kid finished; others pending/claimed.
- `approved`:
  - **Shared All:** _Every_ assigned kid is Approved.
  - **Shared First:** _One_ kid is Approved.

#### **Attributes (Group Stats)**

- `chore_approvals_today`: Count of _all_ kids who finished this today.
- `chore_claimed_by`: Name of the current claimant (Shared First).
- `chore_completed_by`: Name of the winner (Shared First).

---

### **C. Kid Chores Sensor (The "Stats Warehouse")**

**Class:** `KidChoresSensor`
**Entity ID:** `sensor.kc_[kid]_chores`
**Role:** Analytical Database. **NOT** for status display.

- **State:** Integer (Total All-Time Approved Chores).
- **Attributes:** Contains the massive `chore_stats` dictionary.
  - **Categories:** Approved, Claimed, Disapproved, Overdue, Points Earned.
  - **Buckets:** Today, Week, Month, Year, All-Time.
  - **Analysis:**
    - `chore_stat_most_completed_chore_all_time` (e.g., "Feed Dog").
    - `chore_stat_longest_streak_all_time` (Global consistency metric).
    - `chore_stat_avg_per_day_week`.

---

## 3. Interaction Buttons & Deep Logic

Buttons are stateless triggers that execute complex logic in `coordinator.py`.

### **A. Approve Button (`ParentChoreApproveButton`)**

- **Permissions:** Parent / Admin Only.
- **The "One-Click" Workflow:**
  - If chore is `claimed` -> **Approves**.
  - If chore is `pending` -> **Claims AND Approves** instantly.
  - _Value:_ Parents don't need to nag kids to "click the button" before they can mark it done.
- **Race Condition Lock:** Uses `asyncio.Lock` per chore. If Mom and Dad press "Approve" at the same instant, one is rejected to prevent double-points.
- **Reset Logic:**
  - If `approval_reset_type` is `upon_completion`: State flips `Approved` -> `Pending` immediately.
  - Otherwise: State stays `Approved` until the scheduled reset (Midnight/Due Date).

### **B. Disapprove / Undo Button (`ParentChoreDisapproveButton`)**

This single button entity performs **two different actions** based on _who_ clicks it.

1.  **Context: Parent/Admin (The "Disapprove" Action)**

    - **Action:** Rejects the claim. State -> `pending`.
    - **Consequence:** Increments `disapproved_count` in stats (Permanent Record).
    - **Shared First Logic:** Resets **ALL** assigned kids to `pending` so siblings can try to steal the win.

2.  **Context: The Kid (The "Undo" Action)**
    - **Condition:** `user_id == kid_ha_user_id`.
    - **Action:** Withdraws the claim. State -> `pending`.
    - **Consequence:** **NO** stat penalty. It acts as an "Oops" button.

### **C. Claim Button (`KidChoreClaimButton`)**

- **Permissions:** Assigned Kid / Admin.
- **Lockout:** Disabled if `can_claim` is False (e.g., sibling won Shared First or only allowed 1 claim per day).

---

## 4. Chore Services

These services allow automations to manipulate chore state and schedules directly.

### **A. Core Workflow Services**

- `approve_chore`
  - **Field:** `points_awarded` (Optional). Allows overriding the default points.
  - **Logic:** Supports the "One-Click" flow (approves even if pending).
- `claim_chore` / `disapprove_chore`
  - Standard state transitions.

### **B. Scheduling Services**

- `set_chore_due_date`
  - **Function:** Sets a specific ISO datetime.
  - **Independent Chores:** Requires `kid_name` or `kid_id`. Updates **only** that kid's deadline.
  - **Shared Chores:** Updates the global deadline for all kids.
- `skip_chore_due_date`
  - **Function:** Advances the chore to its _next_ calculated recurrence (e.g., skips "Today" -> "Tomorrow").
  - **Logic:** Resets state to `pending`.

### **C. Reset Services**

- `reset_overdue_chores`
  - **Function:** Forces `overdue` chores back to `pending` and reschedules them.
- `reset_all_chores`
  - **Function:** The "Nuclear Option." Sets ALL chores to `pending`. Resets `approval_period_start` to `now`.
