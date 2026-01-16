### 1. Architecture Overview

- **Config Flow (`config_flow.py`):** Used for initial installation and data recovery. It creates the `ConfigEntry`. It uses a sequential "Count -> Loop" pattern to batch-create entities during setup.
- **Options Flow (`options_flow.py`):** Used for ongoing management (Configure button). It uses a "Menu -> Action" pattern to Add, Edit, or Delete specific entities one by one.
- **Flow Helpers (`flow_helpers.py`):** The "Source of Truth." Both flows call into this file to generate UI schemas (`build_*_schema`) and validate data (`validate_*_inputs`). This ensures that a Chore looks the same whether created during setup or added 6 months later.

---

### 2. Trace: The Config Flow (First Time Setup)

The Config Flow is linear. It assumes the user wants to set up the system from scratch or restore a backup.

**Entry Point:** `async_step_user`

1.  **Data Recovery (`async_step_data_recovery`)**

    - **Check:** Scans `.storage` for existing data or backups.
    - **Options:**
      - _Start Fresh:_ Wipes data, creates a safety backup, proceeds to setup.
      - _Use Current Active:_ Keeps existing data (if reinstalling), skips setup wizard.
      - _Restore Backup:_ Selects a specific JSON backup file.
      - _Paste JSON:_ Manual data restoration.

2.  **System Basics**

    - **Intro:** Welcome screen.
    - **Points Label:** Sets the currency name (e.g., "Points", "Stars", "Gold") and icon.
      - _Helper:_ `fh.build_points_schema`, `fh.validate_points_inputs`.

3.  **Entity Loops (The "Count -> Define" Pattern)**

    - _Logic:_ The flow asks "How many [X]?", then loops that many times collecting details for [X].
    - **Kids:**
      - Step: `kid_count` -> `kids` (Loop).
      - _Helper:_ `fh.build_kid_schema`.
    - **Parents:**
      - Step: `parent_count` -> `parents` (Loop).
      - _Helper:_ `fh.build_parent_schema`.
    - **Chores:**
      - Step: `chore_count` -> `chores` (Loop).
      - _Helper:_ `fh.build_chore_schema` (Populates `assigned_kids` dropdown dynamically).
    - **Badges, Rewards, Penalties, Bonuses, Achievements, Challenges:**
      - Follows the exact same pattern: Ask Count -> Loop Schema -> Save to Temp Dict.

4.  **Finish (`async_step_finish`)**

    - **Summary:** Displays a summary of all created entities.
    - **Action:** Writes all temporary data directly to `storage_manager` and creates the Config Entry.

5.  **Reconfigure (`async_step_reconfigure`)**
    - **Trigger:** User clicks "Reconfigure" on the integration entry (not "Configure").
    - **Action:** Allows editing System Settings (Points label, Update Interval, Retention).
    - _Helper:_ `fh.build_all_system_settings_schema`.

---

### 3. Trace: The Options Flow (Ongoing Management)

The Options Flow is menu-driven.

**Entry Point:** `async_step_init` (The Main Menu)

**Main Menu Options:**

1.  **Manage General Options**

    - _Schema:_ `fh.build_general_options_schema`.
    - _Settings:_ Update Interval, Calendar Lookahead, Data Retention (Daily/Weekly/Monthly/Yearly), Legacy Entity Toggle, Backup Retention limits.

2.  **Manage Points**

    - _Action:_ Edit the label and icon for points.

3.  **Manage [Entity] (Kids, Chores, Rewards, etc.)**

    - **Step 1: Select Action** (`add`, `edit`, `delete`).
    - **Step 2 (If Add):**
      - Calls `async_step_add_[entity]`.
      - Uses `fh.build_[entity]_schema` to render the form.
      - Uses `fh.validate_[entity]_inputs` to check data.
      - Uses `fh.build_[entity]_data` to format for storage.
      - Calls Coordinator to persist data immediately.
    - **Step 2 (If Edit/Delete):**
      - Calls `async_step_select_entity`.
      - User picks an entity from a dropdown (filtered by type).
      - **If Edit:** Pre-fills the schema using `fh.build_[entity]_schema(default=current_data)`.
      - **If Delete:** Asks for confirmation, then calls `coordinator.delete_[entity]_entity`.

4.  **Backup Management**
    - _Actions:_ Create Manual Backup, Delete Backup, Restore Backup.
    - _Logic:_ Interfaces directly with `storage_manager` to handle JSON files.

---

### 4. Managed Entities & Configuration Details

Below are the specific fields managed by `flow_helpers` for each entity type. These schemas are identical in both Config and Options flows.

#### **A. Kids**

- **Name:** Display name.
- **HA User:** Link to a specific Home Assistant user (for authorization).
- **Notifications:** Mobile Notify Service selection.
- **Language:** Dashboard language preference.
- **Due Date Reminders:** Toggle for 30-min warnings.

#### **B. Parents**

- **Name:** Display name.
- **HA User:** Link to Home Assistant user (Authorization level: Parent).
- **Associated Kids:** Which kids this parent manages/receives notifications for.
- **Shadow Profile:**
  - _Allow Chores Assigned to Me:_ Creates a "Shadow Kid" entity so parents can have chores.
  - _Enable Workflow:_ Adds Claim/Disapprove buttons for the parent.
  - _Enable Gamification:_ Enables points/badges for the parent.

#### **C. Chores (Complex Entity)**

- **Basics:** Name, Description, Icon, Labels, Points.
- **Assignment:** Assigned Kids (Multi-select).
- **Logic:**
  - _Completion Criteria:_ Independent (Per-kid), Shared (All must do it), Shared First (Race to finish).
  - _Approval Reset:_ At Midnight (Once/Multi), At Due Date (Once/Multi), Upon Completion.
  - _Overdue Handling:_ Mark overdue, ignore, or reset.
  - _Auto-Approve:_ Skip parent approval step.
- **Schedule:**
  - _Frequency:_ Daily, Weekly, Monthly, Custom, etc.
  - _Daily Multi:_ Special mode for chores done multiple times a day (requires times `08:00|14:00`).
  - _Due Date:_ Specific date/time.
- **Per-Kid Overrides (Independent Mode):** Due dates, applicable days, and times can be customized per kid.

#### **D. Badges (Gamification)**

- **Type:** Cumulative (Lifetime points), Daily, Periodic, Achievement-Linked, Challenge-Linked, Special Occasion.
- **Target:** Threshold (Points or Chore Count) required to earn.
- **Awards:** What happens when earned? (Grant Points, Reward, Bonus, or Point Multiplier).
- **Maintenance:**
  - _Frequency:_ How often it resets (e.g., Weekly).
  - _Rules:_ Points required to keep the badge.
  - _Grace Period:_ Days allowed to recover before losing the badge.

#### **E. Rewards**

- **Basics:** Name, Description, Icon, Labels.
- **Cost:** Point cost to redeem.

#### **F. Penalties & Bonuses**

- **Basics:** Name, Description, Icon, Labels.
- **Value:** Point value (Penalties are stored as negative internally, displayed positive).

#### **G. Achievements & Challenges**

- **Achievements:** Track streaks or totals.
  - _Type:_ Chore Streak, Chore Total, Daily Minimum.
  - _Target:_ Count required.
- **Challenges:** Time-boxed goals.
  - _Dates:_ Start Date, End Date.
  - _Type:_ Total within window, Daily minimum.

#### **H. General / System Options**

- **Points Adjust Values:** The buttons shown to parents (e.g., `+1|-1|+5`).
- **Update Interval:** Coordinator polling frequency (default 5 min).
- **Calendar Period:** How many days into the future to forecast (default 90).
- **Retention:** How long to keep history (Daily/Weekly/Monthly/Yearly settings).
- **Legacy Entities:** Toggle to show/hide old sensor entities (cleanup).
- **Backups:** Max backups to retain.
