# KidsChores Services - Technical Reference

**Version:** v0.5.0b3
**Scope:** Service Definitions, Logic, and Edge Cases
**Files:** `services.py`, `services.yaml`

---

## 1. Core Workflow Services (Chores)

These services drive the primary "Claim -> Approve" loop. They mirror the UI buttons but expose additional parameters for automation.

### `approve_chore`

**Description:** Approves a chore, awards points, and advances the schedule.
**Permission:** Parent/Admin only.

- **Key Inputs:** `kid_name`, `chore_name`.
- **💡 Feature: Points Override (`points_awarded`)**
  - You can optionally pass a float value to `points_awarded`.
  - **Use Case:** Award partial points for a "good enough" job, or double points for speed. Overrides the chore's default configuration for _this specific instance_.
- **⚠️ Trap:** This service triggers the **"One-Click" logic**. If the chore is `pending` (not claimed), it will Claim AND Approve it instantly. Be careful with automations triggering this accidentally.

### `claim_chore`

**Description:** Marks a chore as 'Claimed'.
**Permission:** Kid/Admin.

- **⚠️ Trap:** This service enforces **User ID Authorization**. If triggered via an automation context that isn't linked to the specific Kid profile (or an Admin), it will fail with `not_authorized_action`.

### `disapprove_chore`

**Description:** Rejects a claim or completion.
**Permission:** Parent/Admin.

- **Logic:** Reverts state to `pending`.
- **💡 Feature: Shared First Reset:** If used on a "Shared First" chore (where one kid won and others were locked out), this resets **ALL** assigned kids to `pending`. This re-opens the race for everyone, not just the kid being disapproved.

---

## 2. Reward & Economy Services

Direct manipulation of the point economy.

### `redeem_reward` / `approve_reward` / `disapprove_reward`

**Description:** Standard lifecycle for item redemption.
**Permission:** Redeem (Kid/Admin), Approve/Disapprove (Parent/Admin).

- **⚠️ Trap:** `redeem_reward` performs a balance check (`kid_points >= cost`). If the kid is short on points, the service call raises an error and stops execution. Handle this in automations/scripts.
- **Logic:** Points are only deducted on `approve_reward`.

### `apply_penalty` / `apply_bonus`

**Description:** Ad-hoc point modification.

- **Logic:**
  - `apply_penalty`: Deducts points (converts positive input to negative internally).
  - `apply_bonus`: Adds points.
- **Metadata:** These actions log to the `penalty_applies` and `bonus_applies` counters, which are visible in dashboard helpers and sensors.

---

## 3. Scheduling Services (The Complex Engine)

These services manipulate the Due Dates and Recurrence logic directly.

### `set_chore_due_date`

**Description:** Sets a hard deadline (ISO Timestamp).

- **Inputs:** `chore_name`, `due_date` (Optional), `kid_name` (Optional).
- **💡 Feature: Independent Targeting:**
  - If the chore is **Independent**, providing `kid_name` updates **ONLY** that kid's due date. Other kids stay on their own schedule.
- **⚠️ Trap: Shared Chore Targeting:**
  - If the chore is **Shared**, you **CANNOT** provide `kid_name`. The service will fail. Shared chores must have a global due date.
- **⚠️ Trap: Past Dates:** The service validator (`voluptuous`) allows datetime strings, but the Coordinator logic throws an error if the date is in the past.
- **Clear Date:** Sending an empty `due_date` clears the deadline.

### `skip_chore_due_date`

**Description:** Advances a recurring chore to its _next_ logical slot without awarding points.

- **Inputs:** `chore_name`, `kid_name` (Optional).
- **Logic:**
  1.  Calculates `next_due` based on Frequency + Applicable Days.
  2.  Updates the due date.
  3.  **Resets State:** Forces state to `pending`.
- **Use Case:** "Skip today" buttons on dashboards for sick days or holidays.

---

## 4. Reset & Maintenance Services

Used for bulk operations or fixing data states.

### `reset_overdue_chores`

**Description:** Forces overdue items back to `pending` and reschedules them to their next occurrence based on recurrence pattern.

- **Granularity:** Highly flexible targeting.
  - `chore_name` only: Resets that chore for everyone.
  - `kid_name` only: Resets ALL overdue chores for that kid.
  - Both: Resets specific chore for specific kid.
  - Neither: Global reset of all overdue items.

- **⚠️ Trap: Recurring Chores Only**
  - This service ONLY works on chores with a recurrence pattern (daily, weekly, etc.).
  - One-time or manual chores (no recurrence configured) cannot be reset using this service.
  - The service relies on recurrence logic to calculate the "next occurrence" for rescheduling.

- **💡 Completion Criteria Interaction:**

  **INDEPENDENT Chores:**
  - Each kid maintains their own schedule and state.
  - Resetting one kid's overdue chore does NOT affect other kids' instances.
  - Example: Sarah's "Make Bed" is overdue → reset → only Sarah's instance goes to `pending`. Alex's "Make Bed" remains untouched.

  **SHARED Chores:**
  - Single chore instance with global due date shared by all assigned kids.
  - Resetting affects ALL assigned kids simultaneously (all return to `pending`).
  - Example: "Take Out Trash" shared by Sarah and Alex → reset → both kids return to `pending` state.
  - Use Case: Chore was completed by one kid but went overdue before parent approval.

  **SHARED FIRST Chores:**
  - Winner's completion locks out other kids until next cycle.
  - If winner's chore is overdue and reset, **all kids become eligible again** (race reopens).
  - Example: Alex won "First to Feed Dog" but went overdue → reset → Sarah and Alex both eligible to claim again.
  - Technical Detail: Reset clears the "winner lock" state, returning chore to competitive mode.

  **MULTI-APPROVAL Chores:**
  - Each kid must complete independently, but all completions required for chore to cycle.
  - Resetting one kid's overdue completion does NOT affect other kids' completions.
  - Example: "Walk Dog Together" requires 2 approvals → Sarah completed, Alex overdue → reset Alex → Sarah's completion remains intact, Alex returns to `pending`.
  - Technical Detail: Each kid's state tracked separately; reset only modifies specified kid's state.

- **Rescheduling Logic:**
  - Calculates `next_due` based on chore's Frequency setting (daily, weekly, monthly, custom).
  - Respects Applicable Days configuration (e.g., weekdays only, specific days).
  - Sets chore state to `pending` and updates due date to next logical occurrence.
  - Does NOT award points (clean slate for next cycle).

- **Edge Cases:**
  - **Multiple Overdue**: If kid has multiple overdue instances of same recurring chore (rare), reset advances to next occurrence.
  - **Paused Chores**: Reset will reschedule even if chore was manually paused (due date will be set).
  - **Approved but Overdue**: If chore was approved but system still considers it overdue (timing edge case), reset forces back to `pending`.

### `reset_all_chores`

**Description:** The "Soft Reset."
**Action:** Sets ALL chores to `pending`. Resets `approval_period_start` to `now`.
**Use Case:** Debugging a schedule that got desynchronized.

### `reset_penalties` / `reset_bonuses` / `reset_rewards`

**Description:** Resets the **Counters** (e.g., "Times Applied"), not the definitions.
**Use Case:** Monthly "Clean Slate." If you track "Penalties this month," run this automation on the 1st.

### `remove_awarded_badges`

**Description:** Revokes badges.
**Logic:**
_ Specific Badge + Kid: Revokes one.
_ Badge only: Revokes that badge for everyone. \* Kid only: Revokes **ALL** badges for that kid.

---

## 5. Admin & System Services

### `manage_shadow_link`

**Description:** Links a Kid Profile to a Parent Profile (creating a Shadow Kid).

- **⚠️ Trap: Name Matching:** The `name` field must match **BOTH** an existing Parent Name and an existing Kid Name (case-insensitive). If names don't match, the link fails.
- **Actions:** `link` or `unlink`.
- **Behavior:** Unlinking renames the kid to `[Name]_unlinked` to preserve history rather than deleting data.

### `reset_all_data`

**Description:** The "Factory Reset."
**Action:** 1. Creates a backup (`kidschores_data_<timestamp>_reset`). 2. Wipes the `.storage/kidschores_data` file. 3. Cleans the Entity Registry. 4. Reloads the integration.
**Use Case:** Nuclear option for corrupted data or fresh installs.
