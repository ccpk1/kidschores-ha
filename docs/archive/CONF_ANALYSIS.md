# CONF\_\* Constants Analysis & Reorganization Strategy

**Last Updated**: Post-Cleanup Phase 9 (95 CONF\_\* constants remaining)

## Executive Summary

Current state: **95 CONF\_\* constants** organized in const.py with clear comment blocks but without semantic prefix grouping. Analysis identifies **15 distinct semantic categories**, with recommendations for refactoring 8 categories into specialized prefixes while preserving 7 categories as CONF\_\* for backward compatibility.

---

## Category 1: System & Schema (1 constant)

**Purpose**: Config entry schema versioning
**Location**: Lines 57-58
**Count**: 1

```python
CONF_SCHEMA_VERSION = "schema_version"
```

**Decision**: ✅ **KEEP as CONF\_\*** - Required for migrations, backwards compatible

---

## Category 2: Root Configuration Containers (9 constants)

**Purpose**: Top-level config entry data keys (EntityCollection)
**Location**: Lines 130-138
**Count**: 9

```python
CONF_ACHIEVEMENTS = "achievements"
CONF_BADGES = "badges"
CONF_BONUSES = "bonuses"
CONF_CHALLENGES = "challenges"
CONF_CHORES = "chores"
CONF_KIDS = "kids"
CONF_PARENTS = "parents"
CONF_PENALTIES = "penalties"
CONF_REWARDS = "rewards"
```

**Usage**: Primary data keys in storage*manager.py, coordinator.py
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Core architecture, heavily cross-referenced

---

## Category 3: Occasion Types (4 constants)

**Purpose**: Recurring chore occasion classifications
**Location**: Lines 340-343
**Count**: 4

```python
CONF_BIRTHDAY = "birthday"
CONF_BIWEEKLY = "biweekly"
CONF_HOLIDAY = "holiday"
CONF_QUARTERLY = "quarterly"
```

**Usage**: Chore.occasion field in config*flow.py, coordinator.py
**Cross-reference**: FREQUENCY*_ constants use different values ("daily", "weekly", etc.)
**Decision**: 🔄 **CONSIDER BREAKING OUT** → `OCCASION\__`

- Would clarify distinction from FREQUENCY\_\* (schedule repeats vs. special occasions)
- Alternatives: Keep as CONF*\*, consolidate with FREQUENCY*\* (more complex)

---

## Category 4: Sentinel & Display Values (5 constants)

**Purpose**: Special placeholder/display values
**Location**: Lines 353-354, 362-364, 369
**Count**: 5

```python
CONF_DOT = "."                    # Calendar display placeholder
CONF_EMPTY = ""                   # Empty string placeholder
CONF_NONE = None                  # Python None sentinel
CONF_NONE_TEXT = "None"           # String representation of None
CONF_UNKNOWN = "Unknown"          # Unknown state display
```

**Usage**: Dashboard templates, entity state mapping, calendar rendering
**Decision**: 🔄 **BREAK OUT** → `SENTINEL_*` or `DISPLAY_*`

**Proposal**:

```python
SENTINEL_EMPTY = ""
SENTINEL_NONE = None
SENTINEL_NONE_TEXT = "None"
DISPLAY_DOT = "."
DISPLAY_UNKNOWN = "Unknown"
```

**Benefits**:

- Semantic clarity: These aren't config keys, they're display/placeholder values
- IDE autocomplete: `DISPLAY.` and `SENTINEL.` prefixes group naturally
- Reduced confusion: Distinguish from actual configuration data
- Impacts\*\*: ~20 references in dashboard_templates.py, entity state mappings

---

## Category 5: Time Unit Values (9 constants)

**Purpose**: Text representations of time periods (used in custom interval UI)
**Location**: Lines 348-349, 352, 356-357, 360-361, 366-367, 371-372
**Count**: 9

```python
CONF_DAY = "day"
CONF_DAYS = "days"
CONF_HOUR = "hour"
CONF_HOURS = "hours"
CONF_MINUTES = "minutes"
CONF_MONTHS = "months"
CONF_QUARTER = "quarter"
CONF_QUARTERS = "quarters"
CONF_WEEKS = "weeks"
CONF_YEARS = "years"
```

**Usage**: Custom interval UI, time period dropdowns, calculations
**Related**: FREQUENCY*\* constants (for recurring schedule repeats - "daily", "weekly", etc.)
**Distinction**: TIME_UNIT*_ = user-selectable period for custom intervals
**Decision**: 🔄 **BREAK OUT** → `TIME*UNIT*_`

**Proposal**:

```python
TIME_UNIT_DAY = "day"
TIME_UNIT_DAYS = "days"
TIME_UNIT_HOUR = "hour"
TIME_UNIT_HOURS = "hours"
TIME_UNIT_MINUTES = "minutes"
TIME_UNIT_MONTHS = "months"
TIME_UNIT_QUARTER = "quarter"
TIME_UNIT_QUARTERS = "quarters"
TIME_UNIT_WEEKS = "weeks"
TIME_UNIT_YEARS = "years"
```

**Benefits**:

- Semantic clarity: Separates time units from generic config keys
- IDE guidance: `TIME_UNIT.` clearly indicates time period selection
- Consistency: Pairs naturally with FREQUENCY\_\* for schedule configuration
- Impacts\*\*: ~15 references in flow_helpers.py dropdowns, coordinator calculations

---

## Category 6: Generic Data Values (5 constants)

**Purpose**: Generic field/attribute names used across entities
**Location**: Lines 340, 358-359, 364, 370
**Count**: 5

```python
CONF_COST = "cost"                # Reward cost, generic numeric value
CONF_INTERNAL_ID = "internal_id"  # UUID key for all entities
CONF_LABEL = "label"              # Generic label field
CONF_POINTS = "points"            # Points value (achievement, etc.)
CONF_VALUE = "value"              # Generic value field
```

**Usage**: Data structure keys, storage*manager.py, storage YAML
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Backwards compat for storage, foundational keys

---

## Category 7: Global Settings (5 constants)

**Purpose**: Global configuration for integration behavior
**Location**: Lines 345-346, 375-376, 379-380, 383
**Count**: 5

```python
CONF_CALENDAR_SHOW_PERIOD = "calendar_show_period"      # Calendar entity config
CONF_POINTS_ICON = "points_icon"                        # Points display icon
CONF_POINTS_LABEL = "points_label"                      # Points display label
CONF_DASHBOARD_LANGUAGE = "dashboard_language"          # Dashboard language
CONF_HA_USER = "ha_user"                                # Kid's HA user association
CONF_HA_USER_ID = "ha_user_id"                          # Parent's HA user ID
```

**Usage**: config*entry.options, config_flow.py steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - User-facing configuration options

---

## Category 8: Parent Configuration (3 constants)

**Purpose**: Parent entity configuration fields
**Location**: Lines 384-385
**Count**: 3

```python
CONF_PARENT_NAME = "parent_name"
CONF_HA_USER_ID = "ha_user_id"           # (also used in global context)
CONF_ASSOCIATED_KIDS = "associated_kids"
```

**Usage**: Parent entity creation, config*flow steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Entity-specific configuration

---

## Category 9: Chore Configuration (11 constants)

**Purpose**: Chore entity configuration fields
**Location**: Lines 388-399
**Count**: 11

```python
CONF_ALLOW_MULTIPLE_CLAIMS_PER_DAY = "allow_multiple_claims_per_day"
CONF_APPLICABLE_DAYS = "applicable_days"
CONF_ASSIGNED_KIDS = "assigned_kids"
CONF_CHORE_DESCRIPTION = "chore_description"
CONF_CHORE_LABELS = "chore_labels"
CONF_CHORE_NAME = "chore_name"
CONF_CUSTOM_INTERVAL = "custom_interval"
CONF_CUSTOM_INTERVAL_UNIT = "custom_interval_unit"
CONF_DEFAULT_POINTS = "default_points"
CONF_DUE_DATE = "due_date"
CONF_PARTIAL_ALLOWED = "partial_allowed"
CONF_RECURRING_FREQUENCY = "recurring_frequency"
```

**Usage**: Chore entity creation, config*flow.py steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Highly interconnected entity-specific fields

---

## Category 10: Notification Configuration (6 constants)

**Purpose**: Notification settings and triggers
**Location**: Lines 402-407
**Count**: 6

```python
CONF_ENABLE_MOBILE_NOTIFICATIONS = "enable_mobile_notifications"
CONF_ENABLE_PERSISTENT_NOTIFICATIONS = "enable_persistent_notifications"
CONF_MOBILE_NOTIFY_SERVICE = "mobile_notify_service"
CONF_NOTIFY_ON_APPROVAL = "notify_on_approval"
CONF_NOTIFY_ON_CLAIM = "notify_on_claim"
CONF_NOTIFY_ON_DISAPPROVAL = "notify_on_disapproval"
```

**Usage**: config*entry.options, notification_action_handler.py
**Decision**: 🔄 **CONSIDER BREAKING OUT** → `NOTIFICATION*\*` (optional)

**Rationale for keeping CONF\_\***:

- Relatively cohesive group already clearly commented
- Only 6 constants, IDE autocomplete already groups them
- Breaking out gains minimal clarity

**Rationale for breaking out**:

- Signals these are notification-specific settings
- Enables future notification_config.py refactoring
- Clearer semantic intent

**Recommendation**: ✅ **KEEP as CONF\_\*** for now (low priority)

---

## Category 11: Reward Configuration (4 constants)

**Purpose**: Reward entity configuration fields
**Location**: Lines 421-424
**Count**: 4

```python
CONF_REWARD_COST = "reward_cost"
CONF_REWARD_DESCRIPTION = "reward_description"
CONF_REWARD_LABELS = "reward_labels"
CONF_REWARD_NAME = "reward_name"
```

**Usage**: Reward entity creation, config*flow steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Entity-specific configuration

---

## Category 12: Bonus Configuration (4 constants)

**Purpose**: Bonus entity configuration fields
**Location**: Lines 427-430
**Count**: 4

```python
CONF_BONUS_DESCRIPTION = "bonus_description"
CONF_BONUS_LABELS = "bonus_labels"
CONF_BONUS_NAME = "bonus_name"
CONF_BONUS_POINTS = "bonus_points"
```

**Usage**: Bonus entity creation, config*flow steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Entity-specific configuration

---

## Category 13: Penalty Configuration (4 constants)

**Purpose**: Penalty entity configuration fields
**Location**: Lines 433-436
**Count**: 4

```python
CONF_PENALTY_DESCRIPTION = "penalty_description"
CONF_PENALTY_LABELS = "penalty_labels"
CONF_PENALTY_NAME = "penalty_name"
CONF_PENALTY_POINTS = "penalty_points"
```

**Usage**: Penalty entity creation, config*flow steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Entity-specific configuration

---

## Category 14: Achievement Configuration (7 constants)

**Purpose**: Achievement entity configuration fields
**Location**: Lines 439-445
**Count**: 7

```python
CONF_ACHIEVEMENT_ASSIGNED_KIDS = "assigned_kids"
CONF_ACHIEVEMENT_CRITERIA = "criteria"
CONF_ACHIEVEMENT_LABELS = "achievement_labels"
CONF_ACHIEVEMENT_REWARD_POINTS = "reward_points"
CONF_ACHIEVEMENT_SELECTED_CHORE_ID = "selected_chore_id"
CONF_ACHIEVEMENT_TARGET_VALUE = "target_value"
CONF_ACHIEVEMENT_TYPE = "type"
```

**Usage**: Achievement entity creation, config*flow steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Entity-specific configuration

---

## Category 15: Challenge Configuration (8 constants)

**Purpose**: Challenge entity configuration fields
**Location**: Lines 453-461
**Count**: 8

```python
CONF_CHALLENGE_ASSIGNED_KIDS = "assigned_kids"
CONF_CHALLENGE_CRITERIA = "criteria"
CONF_CHALLENGE_END_DATE = "end_date"
CONF_CHALLENGE_LABELS = "challenge_labels"
CONF_CHALLENGE_REWARD_POINTS = "reward_points"
CONF_CHALLENGE_SELECTED_CHORE_ID = "selected_chore_id"
CONF_CHALLENGE_START_DATE = "start_date"
CONF_CHALLENGE_TARGET_VALUE = "target_value"
CONF_CHALLENGE_TYPE = "type"
```

**Usage**: Challenge entity creation, config*flow steps
**Decision**: ✅ \*\*KEEP as CONF*\*\*\* - Entity-specific configuration

---

## Category 16: Retention & Admin Settings (5 constants)

**Purpose**: Data retention and administrative configuration
**Location**: Lines 468-473
**Count**: 5

```python
CONF_POINTS_ADJUST_VALUES = "points_adjust_values"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_RETENTION_DAILY = "retention_daily"
CONF_RETENTION_WEEKLY = "retention_weekly"
CONF_RETENTION_MONTHLY = "retention_monthly"
CONF_RETENTION_YEARLY = "retention_yearly"
```

**Usage**: config*entry.options, admin settings
**Decision**: 🔄 **CONSIDER BREAKING OUT** → `RETENTION*\*` (optional)

**Rationale for keeping CONF\_\***:

- Only 5 constants, already clearly grouped
- Low refactoring priority

**Rationale for breaking out**:

- RETENTION\_\* signals these are retention policy constants
- Separates from configuration keys

**Recommendation**: ✅ **KEEP as CONF\_\*** for now (low priority)

---

## Summary: Recommended Refactoring Plan

### Phase 1: High Priority (Medium Effort, High Value)

**Refactoring 3 categories into semantic groups** - 19 constants

| From                              | To                       | Count | Effort | Benefit                              |
| --------------------------------- | ------------------------ | ----- | ------ | ------------------------------------ |
| CONF_DOT, CONF_EMPTY, CONF_NONE\* | DISPLAY*\* / SENTINEL*\* | 5     | Low    | High (clarity, usage patterns clear) |
| CONF_DAY*, CONF_HOUR*, etc.       | TIME*UNIT*\*             | 9     | Low    | High (distinct from FREQUENCY\_\*)   |
| CONF_BIRTHDAY, CONF_BIWEEKLY\*    | OCCASION\_\*             | 4     | Low    | Medium (less frequently used)        |

**Estimated Impact**: 40-50 references across flow_helpers.py, dashboard_templates.py, coordinator.py

### Phase 2: Low Priority (Minimal Effort, Low Value)

**Optional refactoring** - Keep as CONF\_\* for now

- NOTIFICATION\_\* (6 constants) - Already well-grouped by comments
- RETENTION\_\* (5 constants) - Low usage, already grouped

### Keep As-Is (No Refactoring)

- Root containers (9 constants) - Core architecture
- Generic values (5 constants) - Backwards compatible storage keys
- Global settings (5 constants) - User-facing options
- Entity-specific configs (31 constants) - Tightly integrated
- System schema (1 constant) - Migration critical

---

## Refactoring Effort Estimate

### Option A: Phase 1 Only (Recommended)

- **Scope**: 19 constants → DISPLAY*\*, SENTINEL*_, TIME*UNIT*_, OCCASION\_\*
- **Files**: const.py, flow_helpers.py, dashboard_templates.py, coordinator.py (~50 references)
- **Time**: ~2-3 hours
- **Risk**: Low (localized, well-tested code paths)
- **Breaking Changes**: None (internal constants, not exposed via API/config)

### Option B: Full Reorganization (Ambitious)

- **Scope**: All 95 constants organized by semantic purpose
- **Files**: All integration files (~200+ references)
- **Time**: ~6-8 hours
- **Risk**: Medium (pervasive changes)
- **Breaking Changes**: None (internal constants)

---

## Detailed Refactoring Roadmap (Phase 1)

### Step 1: Add New Constants

Location: After CONF\_\* block, before DEPRECATED section

```python
# Time Units (for custom interval configuration)
TIME_UNIT_DAY = "day"
TIME_UNIT_DAYS = "days"
TIME_UNIT_HOUR = "hour"
TIME_UNIT_HOURS = "hours"
TIME_UNIT_MINUTE = "minute"
TIME_UNIT_MINUTES = "minutes"
TIME_UNIT_MONTH = "month"
TIME_UNIT_MONTHS = "months"
TIME_UNIT_QUARTER = "quarter"
TIME_UNIT_QUARTERS = "quarters"
TIME_UNIT_WEEK = "week"
TIME_UNIT_WEEKS = "weeks"
TIME_UNIT_YEAR = "year"
TIME_UNIT_YEARS = "years"

# Occasion Types (for special recurring chores)
OCCASION_BIRTHDAY = "birthday"
OCCASION_BIWEEKLY = "biweekly"
OCCASION_HOLIDAY = "holiday"
OCCASION_QUARTERLY = "quarterly"

# Sentinel Values (placeholders and special display values)
SENTINEL_EMPTY = ""
SENTINEL_NONE = None
SENTINEL_NONE_TEXT = "None"

# Display Values (UI rendering)
DISPLAY_DOT = "."
DISPLAY_UNKNOWN = "Unknown"
```

### Step 2: Update flow_helpers.py References

- Replace `const.CONF_DAY` → `const.TIME_UNIT_DAY`
- Replace `const.CONF_HOUR` → `const.TIME_UNIT_HOUR`
- (etc. for all 14 TIME*UNIT*\* references in dropdowns)
- Replace `const.CONF_BIRTHDAY` → `const.OCCASION_BIRTHDAY`
- (etc. for all 4 OCCASION\_\* references)

### Step 3: Update dashboard_templates.py References

- Replace sentinel value references in Jinja2 templates
- Update DISPLAY\_\* references in state-to-color mappings

### Step 4: Update coordinator.py References

- Replace TIME*UNIT*\* references in interval calculations
- Replace OCCASION\_\* references in recurring schedule logic

### Step 5: Deprecate Old Constants (Optional)

Keep old CONF*\* constants in a new DEPRECATED_CONF*\* section for one release, then delete:

```python
# DEPRECATED: Moved to TIME_UNIT_*, use those instead
DEPRECATED_CONF_DAY = CONF_DAY = TIME_UNIT_DAY  # Removed in KC 5.1
```

### Step 6: Testing & Validation

```bash
# Run full suite
python -m pytest tests/ -xvs

# Run linting
python utils/lint_check.py --integration

# Verify no orphaned references
grep -r "CONF_DAY\|CONF_HOUR" --include="*.py" | grep -v "const.py"
grep -r "CONF_BIRTHDAY\|CONF_BIWEEKLY" --include="*.py" | grep -v "const.py"
```

---

## Decision Matrix

| Constant Group       | Keep CONF\_\* | Break Out                            | Rationale                                     |
| -------------------- | ------------- | ------------------------------------ | --------------------------------------------- |
| System & Schema      | ✅            | -                                    | Migration critical                            |
| Root Containers      | ✅            | -                                    | Core architecture, cross-referenced           |
| Generic Values       | ✅            | -                                    | Backwards compatible storage keys             |
| Global Settings      | ✅            | -                                    | User-facing config options                    |
| Entity Configs       | ✅            | -                                    | Tightly integrated, 31 constants              |
| **Time Units**       | ❓            | 🔄 **TIME*UNIT*\***                  | Distinct from FREQUENCY\_\*, improves clarity |
| **Display/Sentinel** | ❓            | 🔄 **DISPLAY\_\***, **SENTINEL\_\*** | Not config keys, purely display               |
| **Occasions**        | ❓            | 🔄 **OCCASION\_\***                  | Separates from FREQUENCY\_\*                  |
| Notifications        | ✅            | ❓                                   | Well-grouped already, low priority            |
| Retention            | ✅            | ❓                                   | Well-grouped already, low priority            |

---

## Conclusion

**Current State**: 95 CONF\_\* constants, mostly well-organized with clear comments

**Recommended Action**: Execute Phase 1 refactoring (19 constants → 3 new groups)

- **Benefit**: Improves semantic clarity, enables better IDE autocomplete, distinguishes config keys from display/sentinel/time values
- **Effort**: Low (~2-3 hours)
- **Risk**: Minimal (internal constants, comprehensive test coverage)
- **Impact**: 40-50 references across 4 files

**Not Recommended**: Full reorganization (too ambitious, diminishing returns)

**Next Step**: User decision on execution
