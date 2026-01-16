### 1. Kid Badges Sensor (The "Rank" Sensor)

**Class:** `KidBadgesSensor`
**Entity ID:** `sensor.kc_[kid_name]_badges`
**Created For:** Every Kid (if Gamification is enabled).

This is the primary status display for the kid's **Cumulative (Leveling)** progression. It does **not** track periodic missions; it tracks their current "Tier".

- **State Value:** `String`

  - **Display:** The name of the **Highest Earned Cumulative Badge** (e.g., "Gold Tier").
  - **Fallback:** Returns "None" if no cumulative badges have been earned.
  - **Icon:** Dynamically changes to the icon of the highest earned badge (or a default trophy).

- **Primary Attributes (Status & Progression):**

  - `points_to_next_badge`: (Float) Points required to reach the next tier.
  - `next_higher_badge_name`: (String) The name of the next goal (e.g., "Platinum").
  - `badge_status`: (String) Critical for logic:
    - `active`: Healthy state.
    - `grace`: Missed maintenance, currently in grace period.
    - `demoted`: Failed grace period, currently dropped to lower tier.
  - `current_badge_name`: (String) The badge currently in effect (usually same as state, but may differ during demotion logic).

- **Maintenance Attributes (The "Keep It" Mechanics):**

  - `baseline_points`: (Float) Points "locked in" from previous levels.
  - `cycle_points`: (Float) Points earned in the current maintenance window.
  - `maintenance_points_required`: (Int) Target points needed this cycle to avoid grace/demotion.
  - `maintenance_points_remaining`: (Float) `required - cycle`.
  - `maintenance_end_date`: (Date) When the current cycle ends.
  - `maintenance_grace_end_date`: (Date) When the grace period expires (if active).

- **History Attributes:**
  - `all_earned_badges`: (List) Names of all cumulative badges passed to get here.
  - `last_awarded_date`: (Date) When the current rank was achieved.
  - `award_count`: (Int) How many times this rank was achieved/maintained.

---

### 2. Kid Badge Progress Sensor (The "Mission" Sensor)

**Class:** `KidBadgeProgressSensor`
**Entity ID:** `sensor.kc_[kid_name]_badge_progress_[badge_name]`
**Created For:** A specific Kid + A specific **Non-Cumulative** Badge (Daily, Periodic, Special Occasion, Linked).

These are "Progress Bars" for active quests. A kid will have one of these entities for _every_ active Periodic/Daily badge assigned to them.

- **State Value:** `Float` (0.0 - 100.0)

  - **Display:** Percentage of completion toward the goal.
  - **Unit:** `%`
  - **State Class:** `measurement` (Graphable history).

- **Primary Attributes:**

  - `status`: (String) `active`, `inactive`, or `completed`.
  - `criteria_met`: (Boolean) `true` if the target (points/count) has been hit for this cycle.
  - `raw_progress`: (Float) The actual count (e.g., "3" chores done out of 5 required).
  - `threshold_value`: (Float) The target number (e.g., "5").

- **Scope & Context:**

  - `badge_type`: (String) e.g., `daily`, `periodic`.
  - `target_type`: (String) What is being measured? (`points`, `chores`, `streak`, etc.).
  - `tracked_chores`: (List) Friendly names of the specific chores that count toward this badge (if filtered).
  - `recurring_frequency`: (String) When this progress bar will reset (e.g., `weekly`).
  - `start_date` / `end_date`: (Date) The active window for this specific cycle.

- **History:**
  - `last_awarded`: (Date) When this was last completed 100%.
  - `award_count`: (Int) Total times earned.

---

### 3. System Badge Sensor (The "Definition" Sensor)

**Class:** `SystemBadgeSensor`
**Entity ID:** `sensor.kc_[badge_name]_badge`
**Created For:** Every Badge defined in the system.

This represents the Badge _definition_ itself, serving as a global lookup for badge metadata and aggregate stats.

- **State Value:** `Int`

  - **Display:** Count of **Kids who have earned this badge**.
  - **Unit:** `Kids`.

- **Configuration Attributes:**

  - `badge_type`: (String) The specific engine used (`cumulative`, `daily`, etc.).
  - `target`: (Dict) The rules (type, threshold).
  - `reset_schedule`: (Dict) Frequency, custom intervals.
  - `required_chores`: (List) Names of chores if filtered.
  - `badge_awards`: (List) Formatted strings describing the loot (e.g., `["Points: 50", "Reward: Ice Cream"]`).

- **Assignment Attributes:**

  - `kids_assigned`: (List) Names of kids eligible for this badge.
  - `kids_earned`: (List) Names of kids currently holding it.

- **Links:**
  - `associated_achievement`: (ID) If linked to an Achievement.
  - `associated_challenge`: (ID) If linked to a Challenge.

---

### 4. Summary of Data Flow for Dashboard UI Helper

1.  **Dashboard "Level" Card:**

    - Uses **KidBadgesSensor**.
    - Displays State (Current Rank).
    - Uses `points_to_next_badge` to show a "Next Level" progress bar.
    - Uses `maintenance_points_remaining` to show a "Don't Derank" warning.

2.  **Dashboard "Quests" List:**

    - Iterates through all **KidBadgeProgressSensor** entities.
    - Filters by `status: active`.
    - Shows the Name and the State (Percentage Bar).
    - Uses `tracked_chores` to show a tooltip of "What do I need to do?".

3.  **Notifications:**
    - Triggered by state changes in these sensors (internally in coordinator).
    - Uses `badge_awards` data to populate the notification message ("You earned 50 points and Ice Cream!").
