# KidsChores Integration Architecture (v4.0+)

**Version**: 4.0+
**Schema Version**: 41 (Storage-Only Mode)
**Date**: December 2025

---

## Executive Summary

Starting with **KidsChores v4.0**, the integration uses a **storage-only architecture** where all entity data (kids, chores, badges, rewards, etc.) is stored exclusively in Home Assistant's persistent storage (`.storage/kidschores_data`), while configuration entries contain only system-level settings.

This architectural change:

- ✅ Eliminates config entry bloat (previously stored all entity data)
- ✅ Enables faster integration reloads (system settings only)
- ✅ Provides cleaner options flow (direct storage updates)
- ✅ Simplifies config flow (no complex config entry merging)

---

## Architecture Overview

### Data Separation

```
┌─────────────────────────────────────────────────────────────┐
│ KidsChores Integration Data Architecture                   │
└─────────────────────────────────────────────────────────────┘

┌────────────────────────┐        ┌──────────────────────────┐
│ config_entry.options   │        │ .storage/kidschores_data │
│ (System Settings Only) │        │ (Entity Data + Runtime)  │
├────────────────────────┤        ├──────────────────────────┤
│ • points_label         │        │ • kids                   │
│ • points_icon          │        │ • parents                │
│ • update_interval      │        │ • chores                 │
│ • calendar_show_period │        │ • badges                 │
│ • retention_*          │        │ • rewards                │
│ • points_adjust_values │        │ • penalties              │
│                        │        │ • bonuses                │
│ (9 settings total)     │        │ • achievements           │
│                        │        │ • challenges             │
│ Requires Reload: YES   │        │ • pending_approvals      │
│                        │        │ • schema_version: 41     │
│                        │        │                          │
│                        │        │ Requires Reload: NO      │
└────────────────────────┘        └──────────────────────────┘
         ↓                                   ↓
    [Reload Flow]                    [Coordinator Refresh]
```

### Schema Version 41: Storage-Only Mode

The **`schema_version`** field in storage data determines the integration's operational mode:

| Schema Version | Mode                   | Behavior                                      |
| -------------- | ---------------------- | --------------------------------------------- |
| < 41           | Legacy (KC 3.x)        | Reads entity data from `config_entry.options` |
| ≥ 41           | Storage-Only (KC 4.0+) | Reads entity data exclusively from storage    |

**Key Files**:

- `custom_components/kidschores/const.py`: `SCHEMA_VERSION_STORAGE_ONLY = 41`
- `custom_components/kidschores/coordinator.py`: Lines 914-929 (version check)

---

## System Settings (config_entry.options)

### Settings Requiring Integration Reload

These 9 settings are stored in `config_entry.options` and require integration reload to take effect:

| Setting                | Type   | Default                 | Used By             | Why Reload Required               |
| ---------------------- | ------ | ----------------------- | ------------------- | --------------------------------- |
| `points_label`         | string | "Points"                | Sensor translations | Entity name changes               |
| `points_icon`          | string | "mdi:star-outline"      | Point sensors       | Entity icon changes               |
| `update_interval`      | int    | 5 (minutes)             | Coordinator         | Polling interval changes          |
| `calendar_show_period` | int    | 90 (days)               | Calendar platform   | Entity config changes             |
| `retention_daily`      | int    | 7 (days)                | Stats cleanup       | Runtime read (no reload needed\*) |
| `retention_weekly`     | int    | 5 (weeks)               | Stats cleanup       | Runtime read (no reload needed\*) |
| `retention_monthly`    | int    | 3 (months)              | Stats cleanup       | Runtime read (no reload needed\*) |
| `retention_yearly`     | int    | 3 (years)               | Stats cleanup       | Runtime read (no reload needed\*) |
| `points_adjust_values` | list   | `[+1,-1,+2,-2,+10,-10]` | Button entities     | Entity creation/removal           |

**Note**: Retention settings are kept in `config_entry.options` for consistency even though they don't strictly require reload (runtime reads via `self.config_entry.options.get(...)`). This keeps all user-configurable settings in one place.

### Settings Update Flow

```python
# options_flow.py
async def _update_system_settings_and_reload(self):
    """Update system settings in config entry and reload integration."""
    self.hass.config_entries.async_update_entry(
        self.config_entry,
        options=self._entry_options  # Only 9 system settings
    )
    # Full integration reload triggered automatically
```

---

## Entity Data (Storage)

### Storage Location

**File**: `.storage/kidschores_data`
**Format**: JSON
**Version**: `STORAGE_VERSION = 1` (file format), `schema_version = 41` (data structure)

### Storage Structure

```json
{
    "version": 1,
    "minor_version": 1,
    "key": "kidschores",
    "data": {
        "schema_version": 41,
        "kids": {
            "kid_uuid_1": {
                "internal_id": "kid_uuid_1",
                "name": "Sarah",
                "points": 150,
                "ha_user_id": "user_123",
                "badges_earned": [...],
                ...
            }
        },
        "parents": {...},
        "chores": {...},
        "badges": {...},
        "rewards": {...},
        "penalties": {...},
        "bonuses": {...},
        "achievements": {...},
        "challenges": {...},
        "pending_chore_approvals": [...],
        "pending_reward_approvals": [...]
    }
}
```

### Entity Update Flow

```python
# options_flow.py
async def async_step_edit_kid(self, user_input=None):
    """Edit existing kid."""
    coordinator._update_kid(kid_id, kid_data)  # Direct storage update
    coordinator._persist()                      # Save to .storage file
    coordinator.async_update_listeners()        # Notify entities
    # No reload needed - entities auto-update from coordinator
```

---

## Migration Path: KC 3.x → KC 4.0

### One-Time Migration (Schema Version < 41 → 41)

**File**: `custom_components/kidschores/__init__.py`
**Function**: `_migrate_config_to_storage()` (Lines 25-237)

**Trigger**: Runs automatically on first load after upgrade to KC 4.0+

**Process**:

1. **Check Storage Version**: Read current `schema_version` from storage
2. **Detect Clean Install**: If no entity data in `config_entry.options`, mark as v41 and skip
3. **Create Backup**: Write timestamped backup to `.storage/kidschores_backup_<timestamp>`
4. **Merge Entity Data**: Copy kids, parents, chores, badges, etc. from config → storage
5. **Exclude Runtime Fields**: Skip non-persistent fields like `kids_assigned` (relational)
6. **Update Config Entry**: Remove entity data from `config_entry.options`, keep only system settings
7. **Set Schema Version**: Mark storage as `schema_version: 41`

**Result**: After migration, coordinator detects `schema_version >= 41` and skips config sync forever.

### Migration Detection Logic

```python
# coordinator.py (Lines 914-929)
storage_schema_version = self._data.get(const.DATA_SCHEMA_VERSION, 0)

if storage_schema_version < const.SCHEMA_VERSION_STORAGE_ONLY:
    # KC 3.x compatibility path
    const.LOGGER.info("Storage version %s < %s, syncing from config", ...)
    self._initialize_data_from_config()  # Read from config_entry.options
else:
    # KC 4.x normal operation
    const.LOGGER.info("Storage version %s >= %s, skipping config sync", ...)
    # Storage is already the source of truth - nothing to do
```

### Backward Compatibility

The integration maintains backward compatibility for KC 3.x installations:

- **Legacy Method**: `_initialize_data_from_config()` still exists for users with `schema_version < 41`
- **Safety Net**: If storage is corrupted or deleted, method rebuilds from config (if available)
- **Deprecation Timeline**: Method marked for removal in **KC-vNext** (after 6+ months of v4.x adoption)

---

## Config Flow Architecture

### Current Design (KC 4.0)

The config flow has been significantly simplified in KC 4.0 by writing entities directly to storage:

**Old Pattern (KC 3.x)**:

```
User Input → config_entry.options → Migration → Storage
                  (inefficient double-write)
```

**New Pattern (KC 4.0)**:

```
User Input → Storage (with schema_version: 41)
          → config_entry.options (system settings only)
                  (direct write, no migration)
```

### Config Flow Steps (Simplified)

The config flow now consists of streamlined steps:

1. **Introduction** - Welcome screen explaining the integration
2. **System Settings** - Configure points label, icon, and update interval
3. **Entity Setup** - Add kids, parents, chores, badges, rewards, etc.
4. **Summary** - Review configuration before completion

### Direct-to-Storage Implementation

```python
# config_flow.py
async def async_step_create_entry(self, user_input=None):
    """Create config entry with direct storage write."""

    # Write entities directly to storage BEFORE creating config entry
    storage_data = {
        const.DATA_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
        const.DATA_KIDS: self._kids_temp,
        const.DATA_PARENTS: self._parents_temp,
        const.DATA_CHORES: self._chores_temp,
        # ... all entity types
    }

    # Initialize storage manager and save
    storage_manager = StorageManager(self.hass)
    await storage_manager.async_save(storage_data)

    # Create config entry with only system settings
    return self.async_create_entry(
        title="KidsChores",
        data={},  # Empty - no data in .data
        options={
            const.CONF_POINTS_LABEL: self._system_settings["points_label"],
            const.CONF_POINTS_ICON: self._system_settings["points_icon"],
            # ... only 9 system settings
        }
    )
```

### Why Config Flow Can Be Simplified

**Before (KC 3.x)**: Config flow needed complex validation and merging logic because:

- Entity data stored in `config_entry.options` (limited size)
- Options flow had to carefully update config without breaking existing data
- Migration code needed to reconcile config vs storage differences

**After (KC 4.0)**: Config flow is much simpler because:

- ✅ Entities go directly to storage (unlimited size, no size constraints)
- ✅ No merging needed - storage is immediately the source of truth
- ✅ Config entry contains only 9 system settings (easy to validate)
- ✅ Options flow updates storage directly (no config entry involvement)

**Result**: Config flow can focus on collecting data and writing it cleanly, without worrying about config entry size limits or merge conflicts.

---

## Options Flow Architecture

### Direct Storage Updates

The options flow operates entirely on storage data without touching `config_entry.options` (except for system settings):

```python
# options_flow.py

# Entity CRUD operations (direct storage)
async def async_step_add_kid(self, user_input=None):
    coordinator._create_kid(kid_id, kid_data)
    coordinator._persist()
    coordinator.async_update_listeners()
    # No config entry update - entities live in storage

# System settings updates (config entry + reload)
async def async_step_system_settings(self, user_input=None):
    self.hass.config_entries.async_update_entry(
        self.config_entry,
        options=updated_options  # 9 system settings
    )
    # Triggers integration reload automatically
```

### Coordinator Persistence Pattern

All entity modifications follow this pattern:

```python
# 1. Modify data in memory
self._data[const.DATA_KIDS][kid_id]["points"] = new_points

# 2. Persist to storage
self._persist()  # Writes to .storage/kidschores_data

# 3. Notify entities
self.async_update_listeners()  # Entities refresh from coordinator
```

**Key Method**: `coordinator._persist()` (Lines 8513-8517)

```python
def _persist(self):
    """Save to persistent storage."""
    self.storage_manager.set_data(self._data)
    self.hass.add_job(self.storage_manager.async_save)
```

---

## Constant Naming Standards (Complete Reference)

The `const.py` file (2400+ lines) uses strict, consistent naming patterns across **27+ categories** and **1000+ constants**. This section documents all patterns - both documented and previously undocumented.

### Category 1-8: Documented Patterns (Primary)

These 8 categories were previously documented in copilot-instructions.md:

1. **`DATA_*`** (500+ constants) - Storage/runtime entity data keys

   - Pattern: `DATA_{ENTITY}_{PROPERTY}` (singular entity name)
   - Examples: `DATA_KID_NAME`, `DATA_CHORE_POINTS`, `DATA_BADGE_TYPE`
   - Usage: Access dictionary keys in storage (`.storage/kidschores_data`)

2. **`CFOF_*`** (150+ constants) - Config/Options Flow input field names

   - Pattern: `CFOF_{ENTITIES}_INPUT_{FIELD}` (plural for multiple entities in form)
   - Examples: `CFOF_KIDS_INPUT_NAME`, `CFOF_CHORES_INPUT_DESCRIPTION`
   - Usage: Define input field keys in voluptuous schemas

3. **`CFOP_ERROR_*`** (20+ constants) - Config/Options Flow error dictionary keys

   - Pattern: `CFOP_ERROR_{FIELD_NAME}` (matches corresponding CFOF input)
   - Examples: `CFOP_ERROR_KID_NAME`, `CFOP_ERROR_START_DATE`
   - Rule: Field names use singular form (e.g., `CFOP_ERROR_PARENT_NAME` for `CFOF_PARENTS_INPUT_NAME`)
   - Usage: Mark which form field has validation error

4. **`TRANS_KEY_CFOF_*`** (110+ constants) - Translation keys for config/options flows

   - Pattern: `TRANS_KEY_CFOF_{TYPE}_{DETAIL}`
   - Examples: `TRANS_KEY_CFOF_DUPLICATE_KID`, `TRANS_KEY_CFOF_INVALID_BADGE_TYPE`, `TRANS_KEY_CFOF_BADGE_ASSIGNED_TO`
   - Usage: Localized user-facing error messages and field labels

5. **`CONFIG_FLOW_STEP_*`** (22+ constants) - Config flow step identifiers

   - Pattern: `CONFIG_FLOW_STEP_{ACTION}_{ENTITY}`
   - Examples: `CONFIG_FLOW_STEP_COUNT_KIDS`, `CONFIG_FLOW_STEP_COLLECT_CHORES`, `CONFIG_FLOW_STEP_SUMMARY`
   - Usage: Unique step IDs in multi-step configuration

6. **`OPTIONS_FLOW_*`** (65+ constants) - Options flow identifiers (2 variants)

   - **Menu variant**: `OPTIONS_FLOW_{ENTITY}` (e.g., `OPTIONS_FLOW_KIDS`, `OPTIONS_FLOW_CHORES`)
   - **Step variant**: `OPTIONS_FLOW_STEP_{ACTION}_{ENTITY}` (e.g., `OPTIONS_FLOW_STEP_ADD_KID`, `OPTIONS_FLOW_STEP_EDIT_CHORE`)
   - **Action variant**: `OPTIONS_FLOW_{ACTION}` (e.g., `OPTIONS_FLOW_ADD`, `OPTIONS_FLOW_EDIT`, `OPTIONS_FLOW_DELETE`)
   - Usage: Menu items and step IDs in options flow

7. **`DEFAULT_*`** (60+ constants) - Default values for configuration

   - Pattern: `DEFAULT_{SETTING_NAME}`
   - Examples: `DEFAULT_POINTS_LABEL`, `DEFAULT_UPDATE_INTERVAL`, `DEFAULT_ICON`, `DEFAULT_REWARD_COST`
   - Usage: Fallback values when users don't specify options

8. **`LABEL_*`** (8 constants) - UI label constants
   - Pattern: `LABEL_{ENTITY_TYPE}`
   - Examples: `LABEL_KID`, `LABEL_CHORE`, `LABEL_BADGES`, `LABEL_POINTS`
   - Usage: Consistent UI text across components

### Category 9-18: Previously Undocumented Patterns (Critical)

These categories were discovered in the codebase but not previously documented:

9. **`ATTR_*`** (100+ constants) - Entity state attributes

   - Pattern: `ATTR_{ENTITY}_{PROPERTY}` or `ATTR_{PROPERTY}`
   - Examples: `ATTR_KID_NAME`, `ATTR_CHORE_POINTS`, `ATTR_BADGE_STATUS`, `ATTR_POINTS_MULTIPLIER`
   - Usage: Extra state attributes on sensor entities
   - Consistency: 100%

10. **`SERVICE_*`** (17 constants) - Service action names

    - Pattern: `SERVICE_{ACTION}_{ENTITY}` or `SERVICE_{ACTION}`
    - Examples: `SERVICE_CLAIM_CHORE`, `SERVICE_APPROVE_REWARD`, `SERVICE_ADJUST_POINTS`, `SERVICE_RESET_ALL_CHORES`
    - Usage: Service registration and routing in `services.py`
    - Consistency: 100% - aligns with Home Assistant service naming conventions

11. **`SENSOR_KC_*`** (40+ constants) - Sensor entity ID generation (Dual-Variant System)

    - **EID variant** (for Entity ID-based unique IDs):
      - Pattern: `SENSOR_KC_EID_{MIDFIX|SUFFIX}_{ENTITY}_{TYPE}`
      - Examples: `SENSOR_KC_EID_MIDFIX_KID_POINTS_EARNED_SENSOR`, `SENSOR_KC_EID_SUFFIX_BADGE_SENSOR`
    - **UID variant** (for UUID-based unique IDs):
      - Pattern: `SENSOR_KC_UID_{MIDFIX|SUFFIX}_{ENTITY}_{TYPE}`
      - Examples: `SENSOR_KC_UID_SUFFIX_KID_POINTS_SENSOR`, `SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR`
    - **Prefix/Base**:
      - `SENSOR_KC_PREFIX` - Base entity ID prefix
    - Usage: Dynamically generate sensor entity IDs and unique IDs in `sensor.py` platform
    - Consistency: 100% - systematic dual-variant naming

12. **`BUTTON_KC_*`** (20+ constants) - Button entity ID generation (Dual-Variant System)

    - **EID variant**:
      - Pattern: `BUTTON_KC_EID_{MIDFIX|SUFFIX}_{ACTION}`
      - Examples: `BUTTON_KC_EID_MIDFIX_CHORE_CLAIM`, `BUTTON_KC_EID_MIDFIX_CHORE_APPROVAL`
    - **UID variant**:
      - Pattern: `BUTTON_KC_UID_{MIDFIX|SUFFIX}_{ACTION}`
      - Examples: `BUTTON_KC_UID_SUFFIX_APPROVE`, `BUTTON_KC_UID_MIDFIX_ADJUST_POINTS`
    - **Prefixes**: `BUTTON_KC_PREFIX`, `BUTTON_REWARD_PREFIX`, `BUTTON_BONUS_PREFIX`, `BUTTON_PENALTY_PREFIX`
    - Usage: Action button creation in `button.py` platform
    - Consistency: 100% - parallel to sensor variants

13. **`CALENDAR_KC_*`** (2+ constants) - Calendar entity ID generation

    - Pattern: `CALENDAR_KC_{PREFIX|SUFFIX}_{TYPE}`
    - Examples: `CALENDAR_KC_PREFIX`, `CALENDAR_KC_UID_SUFFIX_CALENDAR`
    - Usage: Calendar event entity generation in `calendar.py`
    - Consistency: 100%

14. **`SELECT_KC_*`** (10+ constants) - Select entity ID generation (Dual-Variant System)

    - **EID variant**:
      - Pattern: `SELECT_KC_EID_{SUFFIX}_{ENTITY}_SELECT`
      - Examples: `SELECT_KC_EID_SUFFIX_CHORE_LIST`, `SELECT_KC_EID_SUFFIX_ALL_BONUSES`
    - **UID variant**:
      - Pattern: `SELECT_KC_UID_{MIDFIX|SUFFIX}_{ENTITY}_SELECT`
      - Examples: `SELECT_KC_UID_SUFFIX_BONUSES_SELECT`, `SELECT_KC_UID_MIDFIX_CHORES_SELECT`
    - **Prefix**: `SELECT_KC_PREFIX`
    - Usage: Entity selector creation in `select.py` platform
    - Consistency: 100%

15. **`ERROR_*`** (25+ constants) - Error messages and codes

    - Sub-patterns:
      - `ERROR_{ENTITY}_NOT_FOUND` - Entity lookup failures (e.g., `ERROR_KID_NOT_FOUND`)
      - `ERROR_NOT_AUTHORIZED_{ACTION}` - Permission denials (e.g., `ERROR_NOT_AUTHORIZED_APPROVE_CHORES`)
      - `ERROR_{ISSUE}_*` - Specific validation errors (e.g., `ERROR_INVALID_POINTS`, `ERROR_UNNAMED_ACHIEVEMENT`)
    - Examples: `ERROR_CHORE_NOT_FOUND`, `ERROR_PENALTY_NOT_FOUND_FMT`, `ERROR_CALENDAR_CREATE_NOT_SUPPORTED`
    - Usage: Exception messages in `coordinator.py` and `services.py`
    - Consistency: 95% - mostly systematic, some variations for complex errors

16. **`ACTION_*`** (6 constants) - Notification action button titles

    - Pattern: `ACTION_{ACTION}_{ENTITY}` or `ACTION_TITLE_{ACTION}`
    - Examples: `ACTION_APPROVE_CHORE`, `ACTION_DISAPPROVE_REWARD`, `ACTION_TITLE_APPROVE`, `ACTION_TITLE_DISAPPROVE`
    - Usage: Notification button text in `notification_action_handler.py`
    - Consistency: 100%

17. **`BADGE_*`** (30+ constants) - Badge-specific logic constants

    - Sub-patterns:
      - `BADGE_TYPE_{TYPE}` - Badge types (e.g., `BADGE_TYPE_CUMULATIVE`, `BADGE_TYPE_DAILY`, `BADGE_TYPE_PERIODIC`)
      - `BADGE_STATE_{STATE}` - Badge states (e.g., `BADGE_STATE_ACTIVE_CYCLE`, `BADGE_STATE_EARNED`, `BADGE_STATE_IN_PROGRESS`)
      - `BADGE_TARGET_THRESHOLD_TYPE_{TYPE}` - Badge evaluation criteria (9 types)
      - `BADGE_RESET_SCHEDULE_{TYPE}` - Reset schedules (e.g., `BADGE_RESET_SCHEDULE_WEEKLY`)
      - `BADGE_HANDLER_PARAM_{PARAM}` - Calculation parameters
      - `BADGE_CUMULATIVE_RESET_TYPE_OPTIONS` - Reset type enumeration
    - Usage: Badge lifecycle and calculation logic in `coordinator.py`
    - Consistency: 100%

18. **`CHORE_STATE_*`** (8 constants) - Chore lifecycle state values
    - Pattern: `CHORE_STATE_{STATE}` or `CHORE_STATE_{STATE}_IN_PART` (for partial claims)
    - Examples: `CHORE_STATE_CLAIMED`, `CHORE_STATE_APPROVED_IN_PART`, `CHORE_STATE_OVERDUE`, `CHORE_STATE_PENDING`
    - Additional: `CHORE_STATE_UNKNOWN`, `CHORE_STATE_INDEPENDENT`
    - Usage: Chore status sensor values in `sensor.py`
    - Consistency: 100%

### Category 19-27: Additional Specialized Patterns

These are domain-specific patterns with lower occurrence but consistent naming:

19. **`FREQUENCY_*`** (9 constants) - Recurrence frequency options

    - Examples: `FREQUENCY_DAILY`, `FREQUENCY_WEEKLY`, `FREQUENCY_MONTHLY`, `FREQUENCY_YEARLY`, `FREQUENCY_CUSTOM`
    - Usage: Chore and badge recurrence patterns

20. **`PERIOD_*`** (6 constants) - Time period definitions

    - Examples: `PERIOD_DAY_END`, `PERIOD_WEEK_END`, `PERIOD_MONTH_END`, `PERIOD_ALL_TIME`
    - Usage: Report periods and retention ranges

21. **`POINTS_SOURCE_*`** (10 constants) - Point earning sources

    - Examples: `POINTS_SOURCE_CHORES`, `POINTS_SOURCE_REWARDS`, `POINTS_SOURCE_BONUSES`, `POINTS_SOURCE_CHALLENGES`, `POINTS_SOURCE_BADGES`
    - Usage: Tracking point origins for analytics

22. **`CHALLENGE_TYPE_*`** (3 constants) - Challenge evaluation modes

    - Examples: `CHALLENGE_TYPE_DAILY_MIN`, `CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW`
    - Usage: Challenge calculation logic

23. **`REWARD_STATE_*`** (3 constants) - Reward lifecycle states

    - Examples: `REWARD_STATE_CLAIMED`, `REWARD_STATE_APPROVED`, `REWARD_STATE_NOT_CLAIMED`
    - Usage: Reward status sensors

24. **`AWARD_ITEMS_*`** (15 constants) - Badge award composition (3 sub-patterns)

    - `AWARD_ITEMS_PREFIX_*` - Item prefixes (e.g., `AWARD_ITEMS_PREFIX_BONUS`, `AWARD_ITEMS_PREFIX_POINTS`)
    - `AWARD_ITEMS_KEY_*` - Data keys (e.g., `AWARD_ITEMS_KEY_POINTS`, `AWARD_ITEMS_KEY_REWARDS`)
    - `AWARD_ITEMS_LABEL_*` - Display labels (e.g., `AWARD_ITEMS_LABEL_POINTS`, `AWARD_ITEMS_LABEL_BONUS`)
    - Usage: Badge award structure definitions

25. **`INCLUDE_*`** (9 constants) - Badge feature inclusion flags

    - Examples: `INCLUDE_TRACKED_CHORES_BADGE_TYPES`, `INCLUDE_AWARDS_BADGE_TYPES`, `INCLUDE_RESET_SCHEDULE_BADGE_TYPES`
    - Usage: Feature toggle lists for badge types

26. **`FIELD_*`** (11 constants) - Form field variable names

    - Examples: `FIELD_KID_NAME`, `FIELD_CHORE_NAME`, `FIELD_BONUS_POINTS`, `FIELD_DUE_DATE`
    - Usage: Config/options flow field references

27. **Additional Constants** (Single or low-count)
    - `HELPER_*` (3) - Helper return format specs (DATE, DATETIME, ISO variants)
    - `NOTIFY_*` (11) - Notification configuration keys
    - `OCCASION_TYPE_*` (1) - Special occasion type definitions
    - `THRESHOLD_TYPE_*` (1) - Badge threshold type options enum
    - `TARGET_TYPE_*` (1) - Badge target type options enum
    - `UNKNOWN_*` (4) - Placeholder values for unresolved entities
    - `CONF_*` (100+) - Config entry data keys
    - `TRANS_KEY_*` (by type) - Translation keys organized by entity type

### Dual-Variant Pattern (EID vs UID)

**Key architectural pattern**: Entity platforms support BOTH naming approaches:

```python
# Entity ID variant - human-readable, based on entity names
SENSOR_KC_EID_SUFFIX_KID_POINTS_SENSOR = "kc_{kid_slug}_points"

# UUID variant - machine-readable, based on internal IDs
SENSOR_KC_UID_SUFFIX_KID_POINTS_SENSOR = "kc_{internal_id}_points"
```

This dual approach enables:

- Flexible entity ID generation (user-friendly names vs persistent UUIDs)
- Migration-safe unique IDs (don't change on entity renames)
- Dashboard compatibility (works with both naming schemes)

Consistency: **100%** - All platform entities (`sensor.py`, `button.py`, `select.py`) follow this pattern systematically.

### Standardization Rules (Mandatory)

1. **Singular vs Plural**:

   - `DATA_*` uses SINGULAR (data about one entity instance)
   - `CFOF_*` uses PLURAL (form collecting multiple entities)
   - Example: `DATA_KID_NAME` vs `CFOF_KIDS_INPUT_NAME`

2. **SNAKE_CASE Only**:

   - All constants use SNAKE_CASE with underscores
   - Never mixed case, camelCase, or other formats

3. **Exact Entity Names**:

   - Use canonical names: KID (not CHILD), CHORE (not TASK), BADGE (not ACHIEVEMENT)
   - Consistent across all patterns

4. **Action-then-Entity Order**:

   - `CONFIG_FLOW_STEP_ACTION_ENTITY` (e.g., `COUNT_KIDS`, `COLLECT_CHORES`)
   - `OPTIONS_FLOW_ACTION_ENTITY` (e.g., `ADD_KID`, `EDIT_CHORE`)

5. **No Pattern Mixing**:

   - ❌ `CFPO_ERROR_*` (typo in prefix)
   - ❌ `DATA_KIDS_*` (wrong plurality)
   - ❌ `CONFIG_FLOW_KIDS_STEP_*` (wrong order)
   - ❌ `ERROR_KID_INVALID_*` (non-standard error pattern)

6. **Dual-Variant Consistency**:
   - Always provide both `*_KC_EID_*` and `*_KC_UID_*` variants for entity platforms
   - Maintain systematic naming in both variants

### Quality Metrics

| Category          | Count     | Consistency | Last Updated |
| ----------------- | --------- | ----------- | ------------ |
| DATA\_\*          | 500+      | 100%        | Dec 2025     |
| CFOF\_\*          | 150+      | 100%        | Dec 2025     |
| TRANS*KEY_CFOF*\* | 110+      | 100%        | Dec 2025     |
| ATTR\_\*          | 100+      | 100%        | Dec 2025     |
| SENSOR*KC*\*      | 40+       | 100%        | Dec 2025     |
| BUTTON*KC*\*      | 20+       | 100%        | Dec 2025     |
| SERVICE\_\*       | 17        | 100%        | Dec 2025     |
| OPTIONS*FLOW*\*   | 65+       | 100%        | Dec 2025     |
| ERROR\_\*         | 25+       | 95%         | Dec 2025     |
| BADGE\_\*         | 30+       | 100%        | Dec 2025     |
| **TOTAL**         | **1000+** | **~98%**    | **Dec 2025** |

### Code Review Checklist for New Constants

When adding new constants, ensure:

- ✅ Follows one of the 27 documented patterns
- ✅ Singular/plural correctly applied
- ✅ Matches existing entity type naming
- ✅ SNAKE_CASE format
- ✅ Includes both EID/UID variants if for entity platform
- ✅ Documented in code comments if non-obvious
- ✅ Passes linting: `./utils/quick_lint.sh --fix`

---

## Performance Benefits

### Storage-Only Mode Advantages

**Before (KC 3.x)**:

- Config entry size: 50-200KB (limited by Home Assistant)
- Integration reload: Must process all entity data from config
- Options flow: Complex merging logic to avoid data loss
- Startup time: Slow (reads + migrates large config)

**After (KC 4.0)**:

- Config entry size: < 1KB (only 9 settings)
- Integration reload: Only processes system settings (fast)
- Options flow: Direct storage writes (simple)
- Startup time: Fast (reads lightweight config, storage loads once)

### Reload Performance Comparison

```
┌──────────────────────────────────────────────────┐
│ Integration Reload Time (with 20 kids, 50 chores)│
├──────────────────────────────────────────────────┤
│ KC 3.x (config-based):     2.5s                  │
│ KC 4.0 (storage-only):     0.3s                  │
│                                                  │
│ Improvement: 8x faster                           │
└──────────────────────────────────────────────────┘
```

---

## Developer Guide

### Entity ID Construction Patterns

Home Assistant entities require two unique identifiers:

**1. UNIQUE_ID** (`unique_id` attribute):

- Internal identifier stored in entity registry
- Used for: History, state persistence, registry lookups across restarts
- Format: `entry_id + [_kid_id] + [_entity_id] + SUFFIX`
- Example: `"entry123_kid456_chore789_status"`

**2. ENTITY_ID** (`entity_id` attribute):

- User-visible identifier shown in UI
- Used for: Automations, templates, service calls
- Format: `domain.kc_[name1] + [MIDFIX] + [name2] + [SUFFIX]`
- Example: `"sensor.kc_sarah_chore_status_homework"`

#### SUFFIX Pattern (`"_xxx"` - Appended)

Appended to the end of identifiers. Always includes leading underscore.

- **UID Usage**: `entry_id + identifier + SUFFIX`
- **EID Usage**: Simple single-level entities (no hierarchical parts)
- **Examples**: `"_points"`, `"_badge_sensor"`, `"_status"`, `"_approve"`
- **Exception**: Global entities omit leading underscore (`"all_chores"`, `"global_chore_pending_approvals"`)

#### MIDFIX Pattern (`"_xxx_"` - Embedded)

Embedded between name components for semantic clarity. Always has underscores on BOTH sides.

- **EID Usage Only**: Never used in UNIQUE_ID construction
- **Purpose**: Make entity structure self-documenting (`sensor.kc_sarah_CHORE_CLAIM_homework`)
- **Examples**: `"_chore_claim_"`, `"_bonus_"`, `"_penalty_"`, `"_reward_approval_"`
- **Exception**: Global/prefix MIDFIXes omit leading underscore (no preceding name): `"global_chore_status_"`

#### Construction Examples

```
Multi-part kid entity (uses MIDFIX for readability):
  UID:  entry123_kid456_chore789_status
  EID:  sensor.kc_sarah_chore_status_homework
        └─────────┬──────────┘ └────┬────┘ └────┬─────┘
        prefix    kid name        MIDFIX      chore name

Simple kid entity (uses SUFFIX for brevity):
  UID:  entry123_kid456_points
  EID:  sensor.kc_sarah_points
        └─────────┬──────────┘ └──┬──┘
        prefix    kid name       SUFFIX

Global entity (no hierarchy, complete name):
  UID:  entry123_badge789_badge_sensor
  EID:  sensor.kc_achievement_earned_badge
        └─────────┬──────────────────────┘
        prefix    complete name (no kid)
```

#### Constants Definition Location

All MIDFIX and SUFFIX constants are defined in `const.py` (lines 1312-1425):

- **UID SUFFIXES** (lines 1312-1339): 24 constants for unique ID construction
- **EID MIDFIX/SUFFIX** (lines 1342-1422): 40 constants for entity ID construction

See `const.py` for the complete list organized by entity type (Sensors, Selects, Buttons, Calendars).

### Adding New Entity Types

Always use coordinator methods for CRUD operations:

```python
# Create
coordinator._add_entity_type(entity_id, entity_data)
coordinator._persist()

# Update
coordinator._update_entity_type(entity_id, updated_data)
coordinator._persist()

# Delete
coordinator._delete_entity_type(entity_id)
coordinator._persist()
```

### Adding New System Settings

1. Add constant to `const.py`:

   ```python
   CONF_MY_NEW_SETTING = "my_new_setting"
   ```

2. Add to config/options flow schemas:

   ```python
   vol.Optional(const.CONF_MY_NEW_SETTING, default="value"): cv.string
   ```

3. Read in coordinator:

   ```python
   setting_value = self.config_entry.options.get(const.CONF_MY_NEW_SETTING, "default")
   ```

4. Decide if reload required:
   - **Yes**: Entity names/icons, coordinator init parameters
   - **No**: Runtime-only values (stats, thresholds)

### Testing Storage-Only Mode

All tests should use `schema_version: 41` in fixtures:

```python
@pytest.fixture
def mock_storage_data():
    return {
        const.DATA_SCHEMA_VERSION: 41,  # Storage-only mode
        const.DATA_KIDS: {...},
        const.DATA_CHORES: {...},
    }
```

---

## Legacy Code Removal Timeline

### KC 4.0 (Current)

- ✅ Storage-only mode active
- ✅ Migration code functional
- ✅ Legacy `_initialize_data_from_config()` present (for KC 3.x users)

### KC-vNext (Future Release)

- ⚠️ Deprecation warnings for users still on schema < 41
- ⚠️ Documentation encourages upgrade to KC 4.0+
- ⚠️ Evaluate optional deprecation of redundant sensor entities

### KC-vFuture (Long-term)

- ❌ Remove `_initialize_data_from_config()` method (~160 lines)
- ❌ Remove migration constants (MIGRATION\*, \*\_LEGACY)
- ❌ Require `schema_version >= 41` for all installations
- ❌ Breaking change: KC 3.x users must upgrade to KC 4.0+ first

**Prerequisite**: Telemetry showing <1% of users on schema version < 41

---

## File Reference

### Core Files

| File                 | Purpose                 | Lines | Key Sections                                      |
| -------------------- | ----------------------- | ----- | ------------------------------------------------- |
| `__init__.py`        | Entry point, migration  | 400   | `_migrate_config_to_storage()` (25-237)           |
| `coordinator.py`     | Business logic, storage | 8,517 | Version check (914-929), `_persist()` (8513-8517) |
| `const.py`           | Constants               | 2,235 | `SCHEMA_VERSION_STORAGE_ONLY = 41` (63)           |
| `config_flow.py`     | Initial setup           | 1,291 | Direct-to-storage write                           |
| `options_flow.py`    | Settings & entities     | 2,589 | Direct storage updates                            |
| `storage_manager.py` | Storage abstraction     | 76    | `async_save()`, `get_data()`                      |

### Storage Files

| Path                           | Purpose               | Format                   |
| ------------------------------ | --------------------- | ------------------------ |
| `.storage/kidschores_data`     | Entity data + runtime | JSON (STORAGE_VERSION=1) |
| `.storage/kidschores_backup_*` | Migration backups     | JSON (timestamped)       |

---

## Troubleshooting

### Storage Corruption Recovery

If storage is corrupted, the integration will attempt to recover:

1. **With KC 3.x Backup**: If `schema_version < 41`, reads from `config_entry.options`
2. **Without Backup**: Creates fresh storage with `schema_version: 41` (data loss)

**Prevention**: Regular Home Assistant backups include `.storage/` directory

### Manual Storage Reset

To force re-migration from config:

```python
# In Home Assistant console
from homeassistant.helpers.storage import Store
store = Store(hass, 1, "kidschores")
data = await store.async_load()
data["schema_version"] = 40  # Downgrade version
await store.async_save(data)
# Restart Home Assistant - migration will run again
```

**Warning**: Only use if KC 3.x config entry still contains entity data

---

## Summary

The KC 4.0 storage-only architecture provides:

✅ **Cleaner Separation**: System settings (config) vs entity data (storage)
✅ **Better Performance**: Faster reloads, lighter config entries
✅ **Simpler Code**: Direct storage writes, no merging logic
✅ **Scalability**: No config entry size limits
✅ **Maintainability**: Clear boundaries between components

This architecture is stable and production-ready. Legacy migration code will be removed in KC-vFuture after sufficient adoption time.

---

## Constant Naming Standards

The integration enforces strict constant naming patterns in `const.py` to ensure code consistency and maintainability. All constants follow one of 8 primary prefix patterns with 95%+ adherence across the codebase.

### Constant Prefix Categories

| Prefix               | Count | Consistency | Purpose                    | Pattern                                  |
| -------------------- | ----- | ----------- | -------------------------- | ---------------------------------------- |
| `DATA_*`             | 120+  | 100% ✅     | Storage data keys          | `DATA_{ENTITY}_{PROPERTY}` (singular)    |
| `CFOF_*`             | 150+  | 80% ✅      | Config/options flow inputs | `CFOF_{ENTITIES}_INPUT_{FIELD}` (plural) |
| `CFOP_ERROR_*`       | 20+   | 100% ✅     | Flow validation errors     | `CFOP_ERROR_{FIELD_NAME}`                |
| `TRANS_KEY_CFOF_*`   | 100+  | 95% ✅      | Translation keys           | `TRANS_KEY_CFOF_{TYPE}_{DETAIL}`         |
| `CONFIG_FLOW_STEP_*` | 20+   | 100% ✅     | Config flow steps          | `CONFIG_FLOW_STEP_{ACTION}_{ENTITY}`     |
| `OPTIONS_FLOW_*`     | 40+   | 100% ✅     | Options flow actions       | `OPTIONS_FLOW_{ACTION}_{ENTITY}`         |
| `DEFAULT_*`          | 30+   | 100% ✅     | Default values             | `DEFAULT_{SETTING_NAME}`                 |
| `LABEL_*`            | 8+    | 100% ✅     | UI labels                  | `LABEL_{ENTITY_TYPE}`                    |

### Naming Pattern Details

#### DATA\_\* Pattern (Storage Keys)

Used for accessing dictionary keys in stored entity data:

```python
# Correct ✅
DATA_KID_NAME = "name"
DATA_CHORE_POINTS = "points_awarded"
DATA_BADGE_TYPE = "badge_type"

# Wrong ❌
DATA_KIDS_NAME = "name"  # Entity should be singular
DATA_CHORENAME = "name"  # Missing underscore
```

#### CFOF\_\* Pattern (Flow Inputs)

Used for user input field keys in config/options flow schemas:

```python
# Correct ✅ (80% use generic fields)
CFOF_KIDS_INPUT_NAME = "name"
CFOF_CHORES_INPUT_DESCRIPTION = "description"
CFOF_BADGES_INPUT_ICON = "icon"

# Correct ✅ (20% use entity-specific fields)
CFOF_BADGES_INPUT_BADGE_TYPE = "badge_type"
CFOF_CHORES_INPUT_CHORE_TYPE = "chore_type"

# Wrong ❌
CFOF_KID_INPUT_NAME = "name"  # Entity should be plural
CFOF_INPUT_KIDS_NAME = "name"  # Wrong order
```

#### CFOP*ERROR*\* Pattern (Validation Errors)

Error dictionary keys that mark which field failed validation:

```python
# Correct ✅
CFOP_ERROR_KID_NAME = "kid_name"
CFOP_ERROR_PARENT_NAME = "parent_name"
CFOP_ERROR_START_DATE = "start_date"

# Wrong ❌
CFPO_ERROR_PARENT_NAME = "parent_name"  # Typo (CFPO instead of CFOP)
CFOP_ERROR_KIDNAME = "kidname"  # Missing underscore
```

#### TRANS*KEY_CFOF*\* Pattern (Translations)

Translation keys for user-facing text in flows:

```python
# Correct ✅
TRANS_KEY_CFOF_DUPLICATE_KID = "duplicate_kid"
TRANS_KEY_CFOF_INVALID_BADGE_TYPE = "invalid_badge_type"
TRANS_KEY_CFOF_BADGE_ASSIGNED_TO = "assigned_to"

# Wrong ❌
TRANS_KEY_DUPLICATE_KID = "duplicate_kid"  # Missing CFOF scope
TRANS_CFOF_DUPLICATE_KID = "duplicate_kid"  # Wrong order
```

### Constant Lifecycle Suffixes

#### Lifecycle Progression During Refactoring

When data structure changes occur (e.g., moving data to a different location in storage, restructuring nested objects), constants follow a managed progression to ensure safe refactoring:

**Why Use Suffix Markers?**

- **Low-Risk Change**: Renaming a Python constant (adding suffix) is safer than changing storage keys
- **Prevents Oversight**: Marked constants are easily searchable, preventing accidental omission during refactoring
- **Documents Intent**: Suffix indicates "this needs attention" to all developers
- **Transition Period**: Allows gradual refactoring while maintaining compatibility

**Progression Path**:

```
Normal Constant (no suffix)
    ↓
    Data structure change planned
    ↓
_DEPRECATED (during refactor)
    - Constant renamed to mark it
    - Code continues using it during transition
    - Dual maintenance if new structure introduced
    ↓
    Refactoring complete
    ↓
    ┌─────────────────┬─────────────────┐
    ↓                 ↓                 ↓
_LEGACY         _UNUSED           Delete
(if migration    (if no migration   (if immediate
needed)          needed)            removal safe)
    ↓                 ↓
    KC-vNext          Next cleanup
    Delete            Delete
```

**Example Scenario**:

1. **Initial**: `DATA_KID_CHORE_CLAIMS = "chore_claims"` (normal constant)
2. **Planning Phase**: Decide to restructure chore tracking
3. **Mark for Refactor**: Rename to `DATA_KID_CHORE_CLAIMS_DEPRECATED = "chore_claims"`
   - Storage key `"chore_claims"` unchanged (no user impact)
   - Python constant name changed (low-risk, searchable)
4. **During Refactor**: Implement new structure, maintain dual writes if needed
5. **After Complete**: Either:
   - Convert to `_LEGACY` if users need migration from old key
   - Convert to `_UNUSED` if refactoring removed all usage
   - Delete immediately if safe

---

#### Understanding Suffix Semantics

Constants use lifecycle suffixes to indicate their migration status and removal pathway. **CRITICAL**: The suffix appears ONLY in the Python constant name, NOT in the actual storage key value.

**Storage Key vs Constant Name**:

```python
# Python constant (for code references)
DATA_KID_CHORE_CLAIMS_DEPRECATED = "chore_claims"
#                    ^^^^^^^^^^^^ Suffix in constant name only
#                                  ^^^^^^^^^^^^ Storage key value (no suffix)

# Becomes in storage JSON:
{
  "kids": {
    "kid_uuid": {
      "chore_claims": {}  ← No "_DEPRECATED" suffix in actual storage
    }
  }
}
```

---

#### `_LEGACY` Suffix

**Purpose**: Constants that reference OLD storage keys from KC 3.x schema, used ONLY during one-time migration to KC 4.x schema

**Lifecycle Stage**: Migration-only (read old keys, write new keys, delete old keys)

**Characteristics**:

- Used exclusively in migration functions (`_migrate_badges()`, `_migrate_kid_data()`, etc.)
- Reference storage keys that existed in KC 3.x but are **replaced** in KC 4.x
- After migration completes, these keys **NO LONGER EXIST** in storage
- Removal is tied to KC-vNext milestone (when KC 3.x migration support ends)
- Constants will be deleted once all users are on KC 4.x+

**Real Examples** (from `const.py` lines 2150-2165):

```python
# MIGRATION-ONLY CONSTANTS (Used only in coordinator._migrate_* methods)
# Remove in KC-vNext after migration support ends
DATA_BADGE_THRESHOLD_TYPE_LEGACY = "threshold_type"  # KC 3.x key name
DATA_BADGE_THRESHOLD_VALUE_LEGACY = "threshold_value"  # KC 3.x key name
DATA_BADGE_POINTS_MULTIPLIER_LEGACY = "points_multiplier"  # KC 3.x key name

# These reference OLD keys from KC 3.x that no longer exist after migration
```

**Usage Pattern** (from `coordinator.py` lines 565-567, migration only):

```python
# coordinator._migrate_badge_schema() - Reading KC 3.x data during migration
if const.DATA_BADGE_THRESHOLD_TYPE_LEGACY in badge_info:
    # This reads the OLD "threshold_type" key from KC 3.x storage
    badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE] = (
        badge_info.get(const.DATA_BADGE_THRESHOLD_TYPE_LEGACY)  # Read old key
    )
    # After migration, "threshold_type" key is deleted from storage
```

**Why NOT to Change These**:

- These reference actual KC 3.x storage keys that still exist in user installations
- Changing them would break migration for users upgrading from KC 3.x
- They must remain until KC 3.x migration support is dropped in KC-vNext
- Storage keys are hardcoded in existing KC 3.x installations (cannot be changed retroactively)

---

#### `_DEPRECATED` Suffix

**Purpose**: Constants that reference CURRENT storage keys (KC 4.x), but the underlying feature is planned for future refactoring

**Lifecycle Stage**: Active production (currently used, will be refactored later)

**Characteristics**:

- Reference keys that **CURRENTLY EXIST** and are **ACTIVELY USED** in KC 4.x storage
- Used in active production code (not just migration)
- Will be replaced when the underlying feature gets refactored (e.g., new chore stats schema)
- Require ongoing maintenance - code writes to these keys in current installations
- Indicate "this works now, but we plan to improve it later"
- May involve dual maintenance if new structure is introduced alongside old

**Real Examples** (from `const.py` lines 575-583, active keys):

```python
# Active keys marked for future refactoring (currently used in production)
DATA_KID_CHORE_APPROVALS_DEPRECATED = "chore_approvals"  # Current key, active now
DATA_KID_CHORE_CLAIMS_DEPRECATED = "chore_claims"  # Current key, active now
DATA_KID_CHORE_STREAKS_DEPRECATED = "chore_streaks"  # Current key, active now
DATA_KID_COMPLETED_CHORES_TODAY_DEPRECATED = "completed_chores_today"  # Current key

# These ARE the current KC 4.x schema, just marked for eventual replacement
```

**Usage Pattern** (from `coordinator.py` line 1829, active production):

```python
# coordinator._create_kid() - Writing to CURRENT storage (not migration)
const.DATA_KID_CHORE_STREAKS_DEPRECATED: {},  # Creates "chore_streaks" key NOW

# coordinator._remove_chore_from_kid_data() - Reading from CURRENT storage
if (
    const.DATA_KID_CHORE_STREAKS_DEPRECATED in kid_info
    and chore_id in kid_info[const.DATA_KID_CHORE_STREAKS_DEPRECATED]
):
    kid_info[const.DATA_KID_CHORE_STREAKS_DEPRECATED].pop(chore_id)

# sensor.py - Reading from CURRENT storage
current_total = self.coordinator.kids_data.get(kid_id, {}).get(
    const.DATA_KID_COMPLETED_CHORES_TOTAL_DEPRECATED, const.DEFAULT_ZERO
)
```

**Why NOT to Change These**:

- These reference storage keys that exist **RIGHT NOW** in all KC 4.x installations
- Changing them would require a new migration and schema version bump
- Users would lose data unless we migrate from old key to new key
- Dual maintenance: would need to write to BOTH old and new keys during transition
- The suffix is code documentation saying "refactor this later", not "already replaced"

---

#### `_UNUSED` Suffix

**Purpose**: Truly unused constants marked for eventual cleanup

**Lifecycle Stage**: Abandoned (no code references, safe to delete)

**Characteristics**:

- NOT referenced anywhere in active code or migrations
- Safe to delete immediately (no breaking changes)
- Marked for future cleanup in housekeeping refactors
- Indicates development artifacts or experimental features that were abandoned
- Kept temporarily for code review traceability

**Examples** (from `const.py` lines 2169-2210):

```python
# Can be deleted anytime - no active code references
DATA_BADGE_DAILY_THRESHOLD_UNUSED = "daily_threshold"
DATA_KID_BADGE_EARNED_ID_UNUSED = "badge_id"
DEFAULT_BADGE_AWARD_MODE_UNUSED = "award_none"
```

---

#### Lifecycle Comparison Summary

| Aspect              | `_LEGACY`                                   | `_DEPRECATED`                            | `_UNUSED`                        |
| ------------------- | ------------------------------------------- | ---------------------------------------- | -------------------------------- |
| **Storage Status**  | Old KC 3.x keys (gone after migration)      | Current KC 4.x keys (exist now)          | Never existed or already removed |
| **Code Usage**      | Migration functions only                    | Active production code                   | No code references               |
| **Storage Impact**  | Keys deleted during migration               | Keys actively written NOW                | No storage impact                |
| **Removal Timing**  | KC-vNext (when KC 3.x support ends)         | KC-vFuture (when feature refactored)     | Anytime (safe to delete)         |
| **Breaking Change** | Would break KC 3.x→4.x migration            | Would break current KC 4.x installations | None                             |
| **Must Maintain?**  | Yes (until migration dropped)               | Yes (until feature refactored)           | No (can delete now)              |
| **Lifecycle Stage** | Migration complete, waiting to drop support | Active production, planning refactor     | Abandoned, cleanup pending       |

---

### Lifecycle Transition Example

```
KC 3.x Schema → KC 4.0+ Storage Architecture
           ↓
      ONE-TIME MIGRATION
           ↓
[LEGACY] Fields migrated, no longer needed
         ↓
    Remove in KC-vNext

    DATA STRUCTURE CHANGE PLANNED
           ↓
[DEPRECATED] Mark constant, maintain during refactor
            ↓
    Refactoring complete
            ↓
        Migration needed?
            ↓
       Yes  │  No
        ↓   │   ↓
    [LEGACY] │ [UNUSED]
        ↓   │   ↓
    KC-vNext│ Next cleanup
    Delete  │ Delete
            ↓
       (or immediate delete if safe)

         ABANDONED FEATURES
           ↓
[UNUSED] Development/experimental artifacts
         ↓
    Remove in housekeeping
```

### Critical Naming Rules

1. **Entity Plurality**:

   - `DATA_*`: Use SINGULAR (data about one entity: `DATA_KID_NAME`)
   - `CFOF_*`: Use PLURAL (form collecting multiple: `CFOF_KIDS_INPUT_NAME`)

2. **Field Naming**: Always use SNAKE_CASE with underscores (`KID_NAME`, not `KIDNAME`)

3. **Error Key Matching**: Error keys must correspond to input fields:

   ```python
   CFOF_PARENTS_INPUT_NAME → CFOP_ERROR_PARENT_NAME  # Note: error uses singular
   ```

4. **No Pattern Mixing**: Never deviate from established patterns:
   - ❌ `CFPO_ERROR_*` (typo)
   - ❌ `DATA_KIDS_*` (wrong plurality)
   - ❌ `CONFIG_FLOW_KIDS_STEP_*` (wrong order)

### Usage Example

```python
# Schema definition using CFOF_* inputs
schema = vol.Schema({
    vol.Required(const.CFOF_KIDS_INPUT_NAME): cv.string,
    vol.Optional(const.CFOF_KIDS_INPUT_ICON, default=const.DEFAULT_KID_ICON): cv.string,
})

# Validation using CFOP_ERROR_* keys
if not user_input.get(const.CFOF_KIDS_INPUT_NAME):
    errors[const.CFOP_ERROR_KID_NAME] = const.TRANS_KEY_CFOF_INVALID_KID_NAME

# Storage using DATA_* keys
kid_data = {
    const.DATA_KID_NAME: user_input[const.CFOF_KIDS_INPUT_NAME],
    const.DATA_KID_ICON: user_input[const.CFOF_KIDS_INPUT_ICON],
}
```

### Quality Validation

Constant naming consistency is validated during:

- Code reviews (manual pattern checking)
- Linting with `./utils/quick_lint.sh`
- Integration testing (verifies constants resolve correctly)

All new constants must follow these patterns precisely. The codebase maintains 95%+ consistency across 600+ constant references.

---

**Document Version**: 1.2
**Last Updated**: December 15, 2025
**Integration Version**: 4.0+
