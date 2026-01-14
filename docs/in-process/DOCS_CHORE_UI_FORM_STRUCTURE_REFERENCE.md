# UI Form Structure Reference

**Purpose**: Document the exact order and structure of UI forms as users see them.  
**Source**: Captured from v0.5.0 UI screenshots  
**Use**: Reference for writing user documentation with accurate field order and descriptions

---

## Form 1: Add/Edit Chore (Main Form)

**Modal Title**: Add Chore (or "Edit Chore: [Name]")  
**Sub-instruction**: Create a new chore with points, assignments, and recurring schedule.

### Section 1: Core Details

| Field Order | Label | Type | Default/Placeholder | User-Facing Description |
|-------------|-------|------|---------------------|-------------------------|
| 1 | **📋 Chore Name*** | Text Input | *(empty)* | "Unique name displayed throughout the system." |
| 2 | **📋 Description (optional)** | Text Area | *(empty)* | "Optional instructions or details about how to complete this chore." |
| 3 | **🧹 Icon (mdi:xxx)** | Text Input | `mdi:broom` | Material Design Icon identifier |
| 4 | **🏷️ Labels (optional)** | Multi-select | *(empty)* | "Tags to organize chores (e.g., 'kitchen', 'outdoor'). Leave blank if not needed." + **[+ Add label]** button |
| 5 | **💰 Points Awarded*** | Number Input | `10` | Points earned when completed |

### Section 2: Assignments & Logic

| Field Order | Label | Type | Default | User-Facing Description |
|-------------|-------|------|---------|-------------------------|
| 6 | **👥 Assigned Kids*** | Multi-select checkboxes | *(none)* | List of all available kids with checkboxes |
| 7 | **👥 Completion Type*** | Dropdown | "Independent (Each kid completes on their own)" | "Independent (each kid completes separately), Shared All (all must complete), or Shared First (first to claim blocks others)." |
| 8 | **➡️ Completions Allowed and Approval Reset Timing*** | Dropdown | "Allow 1 completion - resets at midnight" | "Controls when this chore approval resets and how many completions are allowed during that period." |
| 9 | **➡️ Pending Claims Handling at Approval Reset*** | Dropdown | "Clear All Pending Claims" | "When the approval of this chore resets (based on Approval Reset Timing above), what happens to claims still waiting for approval?" |
| 10 | **⏰ Overdue: Handling Type*** | Dropdown | "Show Overdue After Due Date (Until Completion)" | "Action after due date: Hide overdue status, remain overdue until claimed, or reset to pending at next approval cycle." |
| 11 | **✅ Auto-Approve Claims?** | Toggle | OFF (Grey) | "When enabled, claims are instantly approved without parent review." |

### Section 3: Scheduling

| Field Order | Label | Type | Default | User-Facing Description |
|-------------|-------|------|---------|-------------------------|
| 12 | **🔄 Schedule: Frequency*** | Dropdown | "None" | "How often the chore recurs: Daily, Weekly, Monthly, Yearly, Custom, or None." |
| 13 | **🔄 Schedule: Custom Interval (for Custom Frequency)** | Number Input | *(conditional - only for Custom)* | "Number of time units between repetitions (e.g., 3 for 'every 3 weeks'). Only used with Custom frequency." |
| 14 | **🔄 Schedule: Custom Interval Unit** | Dropdown | *(conditional - only for Custom)* | "Time unit for custom interval (days, weeks, months). Only used with Custom frequency." |
| 15 | **➕ 📅 Schedule: Applicable Days (optional)** | Multi-select tags | *(empty = all days)* | "Restrict chore to specific weekdays. Leave blank for all days." + **[+ Add Day]** button |
| 16 | **📅 Schedule: Due Date ...** | Date/Time Picker | *(empty)* | "Optional deadline. Can be combined with recurring schedules." Format: Calendar icon + hh:mm:ss + AM/PM |

### Section 4: Display & Notifications

| Field Order | Label | Type | Default | User-Facing Description |
|-------------|-------|------|---------|-------------------------|
| 17 | **📅 Show on Calendar?** | Toggle | ON (Blue) | "Display this chore on the calendar view." |
| 18 | **🔔 Notification Events (optional)** | Multi-select checkboxes | All checked | "When to send notifications: On claim, on approval, on rejection, or any combination." Options: Notify on Claim, Notify on Approval, Notify on Disapproval |

### Footer
- **[Submit]** button (Blue action button)

---

## Form 2: Per-Kid Schedule (Secondary Helper Modal)

**Modal Title**: Per-Kid Schedule: [Chore Name]  
**Sub-instruction**: Configure individual schedule settings for each kid assigned to this chore. The main form values act as templates—use the checkboxes to apply them to all kids, or customize each kid's settings individually.

**Appears When**:
- Chore is INDEPENDENT completion criteria
- More than 1 kid assigned
- Using DAILY_MULTI frequency OR per-kid applicable days

**Template Display**:
- Active Kids: [List of assigned kid names]
- Template Days: [Days from main form]
- Template Date: [Date from main form in YYYY-MM-DD HH:MM:SS format]

### Global Template Controls

| Field Order | Label | Type | Default | Description |
|-------------|-------|------|---------|-------------|
| 1 | **Apply template days to all kids** | Toggle | OFF (Grey) | "Check to use the applicable days from the main form for all assigned kids." |
| 2 | **Apply template date to all kids** | Toggle | OFF (Grey) | "Check to apply the date set on the main chore form to all assigned kids." |

### Per-Kid Configuration (Repeats for Each Assigned Kid)

**Example: Dad's Configuration**

| Field Order | Label | Type | Format | Description |
|-------------|-------|------|--------|-------------|
| 3a | **Assigned Days: [KidName]** | Multi-select tags | Day badges with X to remove | Show selected days with remove buttons (e.g., "Dad: Monday X", "Dad: Tuesday X") |
| 3b | **+ days_[kidname]** | Button | Add day button | Opens day selector |
| 4 | **Time Range (times_[kidname])** | Text Input | `HH:MM\|HH:MM` format | Pipe-separated time slots (e.g., "08:00\|17:00") |
| 5 | **Specific Date (date_[kidname])** | Date Picker | M/D/YYYY format | Individual due date override |
| 6 | **Time Input** | Time Picker | HH:MM:SS AM/PM | Time portion of due date |
| 7 | **Clear Toggle (clear_[kidname])** | Toggle | OFF | Clear this kid's custom settings |

**Repeats**: One configuration block per assigned kid with kid-specific field names

### Footer
- **[Submit]** button (Blue action button)

---

## Form Field Naming Conventions

**Main Form**:
- All fields use descriptive names matching `CFOF_CHORES_INPUT_*` constants
- Required fields marked with `*`
- Conditional fields only appear based on other selections

**Helper Form (Per-Kid)**:
- Template toggles: `apply_template_days`, `apply_template_date`
- Per-kid days: `days_[KidName]` (multi-select)
- Per-kid times: `times_[KidName]` (text input with `HH:MM|HH:MM|...` format)
- Per-kid date: `date_[KidName]` (date picker)
- Per-kid clear: `clear_[KidName]` (toggle)

**Kid Name Handling**:
- Kid names may contain spaces, special characters, emojis
- Field names use kid's actual name as stored (not slugified)
- Example: Kid named "Kid3" → field is `times_Kid3`
- Example: Kid named "Max!" → field is `times_Max!`

---

## UI Flow Sequence

1. **User clicks "Add Chore"** → Shows Form 1 (Main Form)
2. **User fills Form 1 and clicks Submit**
3. **System checks conditions**:
   - Is completion_criteria = INDEPENDENT?
   - Are 2+ kids assigned?
   - Is frequency = DAILY_MULTI OR are applicable_days set?
4. **If ALL conditions met** → Shows Form 2 (Per-Kid Schedule)
5. **User configures per-kid settings** → Clicks Submit
6. **Chore created** with all data saved

**Alternative Flow** (No Helper Needed):
- If conditions not met → Chore created immediately after Form 1

---

## Validation Rules (From UI Perspective)

**Form 1 Validations**:
- Chore Name: Required, must be unique
- Points Awarded: Required, must be number
- Assigned Kids: At least 1 required
- DAILY_MULTI requires: INDEPENDENT completion, due date set, at least 1 kid
- CUSTOM frequency requires: Custom Interval + Custom Interval Unit

**Form 2 Validations** (Per-Kid Schedule):
- Time Range format: Must be pipe-separated HH:MM values (e.g., "08:00|17:00|22:00")
- Minimum times for DAILY_MULTI: At least 1 time slot per kid
- Maximum times: Implementation-defined limit (6+ tested)
- Days: Valid weekday names (mon-sun)

---

## Notes for Documentation Writers

1. **Field Order Matters**: Users see fields in the exact order listed above. Documentation should follow same sequence.

2. **Icons as Visual Cues**: Each section uses emoji icons in UI. Consider using same icons in documentation for consistency.

3. **Helper Text Integration**: Every field has helper text. Documentation should expand on these, not duplicate.

4. **Progressive Disclosure**: Some fields only appear based on earlier selections (e.g., Custom Interval only when frequency=Custom).

5. **Per-Kid Complexity**: The helper modal is the most complex part. Users need clear examples of when it appears and why.

6. **Template Pattern**: The "template" concept (main form values as defaults, override per-kid) needs clear explanation.

7. **Validation Feedback**: When users enter invalid data, errors appear inline. Documentation should warn about common validation issues.
