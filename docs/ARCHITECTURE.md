# KidsChores Integration Architecture

**Integration Version**: 0.5.0+
**Storage Schema Version**: 42 (Storage-Only Mode with Meta Section)
**Quality Scale Level**: ⭐ **Silver** (Unofficially Meets Standards)
**Date**: January 2026

---

## 🎯 Silver Quality Standards

This integration unofficially meets **Home Assistant Silver** quality level requirements. See [quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml) for current rule status and [AGENTS.md](../../core/AGENTS.md) for ongoing Home Assistant quality standards.

---

## Executive Summary

Starting with **KidsChores 0.5.0**, the integration uses a **storage-only architecture** where all entity data (kids, chores, badges, rewards, etc.) is stored exclusively in Home Assistant's persistent storage (`.storage/kidschores_data`), while configuration entries contain only system-level settings.

**Schema Version 42** is the current schema, introducing the **meta section architecture** where the storage schema version is stored in a dedicated `meta` section rather than at the top level. This change:

- ✅ Prevents test framework interference with version detection
- ✅ Enables robust migration testing and validation
- ✅ Provides migration history tracking and metadata
- ✅ Separates versioning metadata from entity data

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
│                        │        │ • meta.schema_version: 42│
│                        │        │                          │
│                        │        │ Requires Reload: NO      │
└────────────────────────┘        └──────────────────────────┘
         ↓                                   ↓
    [Reload Flow]                    [Coordinator Refresh]
```

### Schema Version 42: Storage-Only Mode with Meta Section

The **`meta.schema_version`** field in storage data determines the integration's operational mode. Schema 42 is the current version:

| Schema Version | Mode                  | Behavior                                                        |
| -------------- | --------------------- | --------------------------------------------------------------- |
| < 42           | Legacy (Pre-0.5.0)    | Reads entity data from `config_entry.options` or legacy storage |
| ≥ 42           | Storage-Only (0.5.0+) | Reads entity data exclusively from storage with meta section    |

**Key Files**:

- `custom_components/kidschores/const.py`: `SCHEMA_VERSION_STORAGE_ONLY = 42`
- `custom_components/kidschores/coordinator.py`: Lines 851-856 (version check)
- `custom_components/kidschores/__init__.py`: Lines 45-51 (migration detection)

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
**Version**: `STORAGE_VERSION = 1` (Home Assistant Store format), `meta.schema_version = 42` (KidsChores data structure)

### Translation Architecture

KidsChores uses **two separate translation systems**:

#### 1. Integration Translations (Standard HA)

**Location**: `custom_components/kidschores/translations/en.json` (and other language codes)
**Purpose**: Home Assistant integration translations for:

- Exception messages (`exceptions.*`)
- Config flow UI (`config.*`)
- Entity names and states (`entity.*`)
- Service descriptions (`selector.*`)

**Usage**: Standard Home Assistant translation system via `hass.localize()` and `translation_key` attributes.

**Coordinator Notifications** (0.5.0+): Coordinator uses `async_get_translations()` API for:

- Dynamic notification messages (36 translation keys: 18 title + 18 message)
- Test mode detection (5s vs 1800s reminder delays)
- Wrapper methods: `_notify_kid()`, `_notify_reminder()`

**Example**:

```python
translations = await async_get_translations(
    self.hass,
    self.hass.config.language,
    "entity_component",
    {const.DOMAIN}
)
title = translations.get(const.TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED, "Chore Approved")
```

#### 2. Dashboard Translations (Custom System)

**Location**: `custom_components/kidschores/translations_dashboard/` directory with files named like `en_dashboard.json`, `es_dashboard.json`, etc. (10+ languages)
**Purpose**: **Custom dashboard-specific translations** for the KidsChores Dashboard Helper sensor.
**Important**: These are **NOT part of Home Assistant's integration translation system**. This is a custom approach unique to KidsChores.

**File Naming Convention**:

- Directory: `translations_dashboard/` (constant: `DASHBOARD_TRANSLATIONS_DIR`)
- Files: `{language_code}{DASHBOARD_TRANSLATIONS_SUFFIX}.json` where suffix is `_dashboard`
- Examples: `en_dashboard.json`, `es_dashboard.json`, `fr_dashboard.json`, `de_dashboard.json`

**Why Custom?**: The dashboard helper sensor pre-computes all UI translations and exposes them via the `ui_translations` attribute. This allows:

- Frontend dashboard YAML to access translations without backend calls
- Single-language selection per kid (not system-wide)
- Optimized dashboard rendering (no expensive template lookups)
- Support for 10+ languages without HA core language pack dependencies

**Access Pattern**:

```jinja2
{%- set dashboard_helper = 'sensor.kc_' ~ kid_name ~ '_ui_dashboard_helper' -%}
{%- set ui = state_attr(dashboard_helper, 'ui_translations') or {} -%}
{{ ui.get('welcome', 'err-welcome') }}  {# Fallback for missing keys #}
```

**Note**: Dashboard translations are loaded by the dashboard helper sensor (sensor.py) and are completely separate from the integration's standard `translations/en.json` file. The loading functions (`get_available_dashboard_languages()` and `load_dashboard_translation()`) are in `kc_helpers.py`.

### Storage Structure

```json
{
    "version": 1,
    "minor_version": 1,
    "key": "kidschores_data",
    "data": {
        "meta": {
            "schema_version": 42,
            "last_migration_date": "2025-12-18T10:00:00+00:00",
            "migrations_applied": [
                "datetime_utc",
                "chore_data_structure",
                "kid_data_structure",
                "badge_restructure",
                "cumulative_badge_progress",
                "badges_earned_dict",
                "point_stats",
                "chore_data_and_streaks"
            ]
        },
        "kids": {
            "kid_uuid_1": {
                "internal_id": "kid_uuid_1",
                "name": "Sarah",
                "points": 150,
                "ha_user_id": "user_123",
                "badges_earned": {...},
                "point_stats": {...},
                "chore_data": {...},
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

### Versioning Architecture

KidsChores uses a **dual versioning system**:

#### 1. Home Assistant Store Version (File Format)

```json
{
    "version": 1,          // HA Store format version (always 1)
    "minor_version": 1,    // HA Store minor version
    "key": "kidschores_data",
    "data": { ... }        // KidsChores data with schema_version
}
```

#### 2. KidsChores Schema Version (Data Structure)

**Legacy Format (v41 and below)**:

```json
{
    "data": {
        "schema_version": 41,  // Top-level schema version
        "kids": {...}
    }
}
```

**Modern Format (v42+)**:

```json
{
    "data": {
        "meta": {
            "schema_version": 42,                    // Nested in meta section
            "last_migration_date": "2025-12-18...",
            "migrations_applied": ["badge_restructure", ...]
        },
        "kids": {...}
    }
}
```

#### Why Meta Section?

1. **Test Framework Compatibility**: Home Assistant test framework auto-injects `schema_version: 42` at the top level, breaking migration tests. The nested `meta.schema_version` is protected from this interference.

2. **Semantic Separation**: Version metadata is separated from entity data, following database schema versioning patterns.

3. **Migration Tracking**: The `meta` section can track migration history, dates, and applied transformations.

#### Version Detection Logic

```python
# Both __init__.py and coordinator.py use this pattern:
meta_section = storage_data.get("meta", {})
storage_version = meta_section.get(
    "schema_version",
    storage_data.get("schema_version", 0)  # Fallback to top-level
)
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

## Migration Path: Legacy → v0.5.0

### One-Time Migration (Schema Version < 42 → 42)

**File**: `custom_components/kidschores/__init__.py`
**Function**: `_migrate_config_to_storage()` (Lines 45-51)

**Trigger**: Runs automatically on first load after upgrade to v0.5.0+

**Process**:

1. **Check Storage Version**: Read from `meta.schema_version` or fallback to top-level `schema_version`
2. **Detect Clean Install**: If no entity data in `config_entry.options`, create meta section with v42 and skip
3. **Create Backup**: Write timestamped backup to `.storage/kidschores_data_<timestamp>_<tag>`
4. **Merge Entity Data**: Copy kids, parents, chores, badges, etc. from config → storage
5. **Exclude Runtime Fields**: Skip non-persistent fields like `kids_assigned` (relational)
6. **Update Config Entry**: Remove entity data from `config_entry.options`, keep only system settings
7. **Set Schema Version**: Create meta section with `schema_version: 42`, migration date, and applied migrations list

**Result**: After migration, coordinator detects `meta.schema_version >= 42` and skips config sync forever.

### Migration Detection Logic

```python
# coordinator.py (Lines 851-856)
# Get schema version from meta section (v42+) or top-level (v41-)
meta = self._data.get(const.DATA_META, {})
storage_schema_version = meta.get(
    const.DATA_META_SCHEMA_VERSION,
    self._data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
)

if storage_schema_version < const.SCHEMA_VERSION_STORAGE_ONLY:
    # Legacy compatibility path - migrate data
    const.LOGGER.info("Storage version %s < %s, running migrations", ...)
    self._migrate_stored_datetimes()
    self._migrate_chore_data()
    self._migrate_kid_data()
    # ... other migrations
else:
    # v0.5.0+ normal operation
    const.LOGGER.info("Storage version %s >= %s, skipping migrations", ...)
    # Storage is already at current schema version
```

### Backward Compatibility

The integration maintains backward compatibility for legacy installations:

- **Legacy Support**: Migration system handles v30, v31, v40beta1, v41 → v42 upgrades automatically
- **Dual Version Detection**: Code reads from both `meta.schema_version` (v42+) and top-level `schema_version` (legacy)
- **Safety Net**: If storage is corrupted or deleted, clean install creates v42 meta section
- **Migration Testing**: Comprehensive test suite validates all migration paths (see MIGRATION_TESTING_PLAN.md)

---

## Config Flow Architecture

### Current Design (v0.5.0)

The config flow has been significantly simplified in v0.5.0 by writing entities directly to storage:

**Old Pattern (Legacy)**:

```
User Input → config_entry.options → Migration → Storage
                  (inefficient double-write)
```

**New Pattern (v0.5.0)**:

```
User Input → Storage (with meta.schema_version: 42)
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
        const.DATA_META: {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_LAST_MIGRATION_DATE: datetime.now(dt_util.UTC).isoformat(),
            const.DATA_META_MIGRATIONS_APPLIED: []
        },
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

**Before (Legacy)**: Config flow needed complex validation and merging logic because:

- Entity data stored in `config_entry.options` (limited size)
- Options flow had to carefully update config without breaking existing data
- Migration code needed to reconcile config vs storage differences

**After (v0.5.0)**: Config flow is much simpler because:

- ✅ Entities go directly to storage (unlimited size, no size constraints)
- ✅ No merging needed - storage is immediately the source of truth
- ✅ Config entry contains only 9 system settings (easy to validate)
- ✅ Options flow updates storage directly (no config entry involvement)

**Result**: Config flow can focus on collecting data and writing it cleanly, without worrying about config entry size limits or merge conflicts.

---

## Related Documentation

**This document serves as the canonical reference for KidsChores architecture and versioning.** For specific implementation details, see:

### Testing & Migration

- **[MIGRATION_TESTING_PLAN.md](MIGRATION_TESTING_PLAN.md)** - Migration test implementation, sample validation, and test framework patterns
- **[STORAGE_TESTING_SUMMARY.md](STORAGE_TESTING_SUMMARY.md)** - Storage system test coverage and validation results

### Feature Implementation

- **[DATA_RECOVERY_BACKUP_PLAN.md](DATA_RECOVERY_BACKUP_PLAN.md)** - Backup/restore procedures and config flow data recovery
- **[SENSOR_REFACTORING_PLAN.md](SENSOR_REFACTORING_PLAN.md)** - Entity platform architecture and performance optimization
- **[COORDINATOR_REVIEW_IMPROVEMENTS.md](COORDINATOR_REVIEW_IMPROVEMENTS.md)** - Coordinator design patterns and data flow

### Maintenance & Cleanup

- **[LEGACY_CLEANUP.md](LEGACY_CLEANUP.md)** - Deprecation timeline for pre-v42 compatibility code
- **[RELEASE_NOTES_v0.5.0.md](RELEASE_NOTES_v0.5.0.md)** - v0.5.0 release details and storage architecture changes

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

## UI Architecture: Per-Kid Customization

### Service Layer Exposure

KidsChores uses a **layered UI approach** where advanced per-kid customizations are available through the service layer while maintaining simple defaults in the main UI:

**Service Parameters** (exposed in Developer Tools):

- `kid_name`/`kid_id` - Target specific kids for customization
- Template vs. per-kid distinction for INDEPENDENT completion criteria

**Example**: Set per-kid due dates for INDEPENDENT chores:

```yaml
service: kidschores.set_chore_due_date
data:
  chore_name: "Clean Room"
  kid_name: "Sarah"
  due_date: "2026-01-05 18:00:00"
```

### Options Flow Smart Preservation

The options flow maintains a **template + override model**:

1. **Template Date**: Default date shown in main chore edit form
2. **Per-Kid Overrides**: Preserved during edits, customizable via dedicated step
3. **Smart Display**: Shows common date if all kids match, blank if mixed

**Implementation Pattern**:

```python
# Preserve existing customizations during edit
existing_per_kid_due_dates = chore_data.get(const.DATA_PER_KID_DUE_DATES, {})
chore_data = build_chores_data(user_input, existing_per_kid_due_dates=existing_per_kid_due_dates)
```

### Sensor Attribute Organization

Sensors expose data in **categorized attributes** for dashboard consumption:

```python
# Identity & Meta: chore_name, chore_icon, internal_id
# Configuration: completion_criteria, points, frequency, due_date
# Statistics: total_claims, total_approved, points_multiplier
# Timestamps: last_claimed, last_approved, last_disapproved, last_overdue
# State: global_state, assignees
```

**Key Design**: Entity `icon` reflects state (checkmark/clock), `chore_icon` attribute shows identity (mdi:toothbrush).

---

## Deprecation Convention: \_UNUSED Suffix (Development-Cycle Only)

### Purpose & Scope

The `_UNUSED` suffix is a **development-cycle tool** for safe rollback during active refactoring. It allows marking constants as deprecated without immediate deletion, enabling quick reversion if patterns change. **However, all \_UNUSED constants MUST be removed before production candidate testing and release.**

**This approach is NOT a long-term deprecation mechanism** — it's optimized for iterative development, not backward compatibility across releases.

### When to Use \_UNUSED

✅ **Use \_UNUSED when:**

- You're consolidating patterns (e.g., CONF*\* → FREQUENCY*\*) in active development
- Tests confirm new pattern works but old constants might be needed for quick rollback
- Within a single development branch/cycle (v0.5.0 development, for example)
- You want the flexibility to revert without full reconstruction

❌ **Do NOT use \_UNUSED when:**

- Releasing to production (delete before final build)
- Moving code to staging/production branches (must be cleaned first)
- Communicating with external users about deprecation (use release notes + migration code instead)
- Spanning multiple release cycles (indicates long-term deprecation, which needs full deletion + migration)

### Standard Approach (During Development)

**All development-cycle \_UNUSED constants must:**

1. **Use `_UNUSED` suffix at END of constant name**

   ```python
   # ✅ CORRECT (development tool)
   CONF_DAY_END_UNUSED = "day_end"
   CONF_CUSTOM_1_MONTH_UNUSED = "custom_1_month"

   # ❌ WRONG
   CONF_UNUSED_DAY_END = "day_end"
   UNUSED_CONF_CUSTOM_1_MONTH = "custom_1_month"
   ```

2. **Be moved to dedicated `_UNUSED` section at end of `const.py`**

   - Location: After all active constants, in final section marked `# [Category] (Development-Only: Removed before vX.0 production release)`
   - Organization: Group deprecated constants by category/reason for deprecation
   - Purpose: Keep const.py organized; unused constants isolated and visible as temporary
   - Visibility: Makes it obvious what's temporary during code review

3. **Include inline comment explaining replacement AND exit criteria**
   ```python
   # Configuration Keys (Development-Only: Removed before v0.5.0 production release)
   # Replaced by FREQUENCY_* and PERIOD_* patterns
   CONF_CUSTOM_1_MONTH_UNUSED = "custom_1_month"  # Use FREQUENCY_CUSTOM_1_MONTH instead. [DELETE BEFORE PROD]
   CONF_DAY_END_UNUSED = "day_end"  # Use PERIOD_DAY_END instead. [DELETE BEFORE PROD]
   CONF_UNAVAILABLE_UNUSED = "unavailable"  # Unused sentinel. [DELETE BEFORE PROD]
   ```

### Exit Criteria: When to Delete \_UNUSED Constants

**Delete all \_UNUSED constants BEFORE moving to production testing when:**

1. ✅ All tests pass with new pattern (e.g., FREQUENCY\_\* constants work in production code)
2. ✅ Code review confirms new pattern is correct (no planned rollbacks)
3. ✅ No code still references the old \*\_UNUSED constants
4. ✅ Grep returns zero results: `grep "CONSTANT_UNUSED" custom_components/kidschores/*.py`
5. ✅ Final linting passes: `./utils/quick_lint.sh` shows no errors
6. ✅ Before final RC (Release Candidate) build or production deployment

**Timing Guideline**: Remove \_UNUSED constants at the end of each development cycle:

- Development branch (v4.0-dev) → Contains \_UNUSED constants ✅
- Release candidate (v4.0-rc1) → Must be cleaned (no \_UNUSED) ✅
- Production release (v4.0) → Zero \_UNUSED constants ✅

### Comparison: \_UNUSED vs. Proper Deprecation

| Scenario               | \_UNUSED Approach                  | Proper Deprecation                        |
| ---------------------- | ---------------------------------- | ----------------------------------------- |
| **Timeframe**          | Single dev cycle                   | Across release cycles                     |
| **Use Case**           | Safe rollback during refactoring   | Long-term backward compat                 |
| **Lifecycle**          | Delete before prod                 | Document in CHANGELOG + keep for versions |
| **Example**            | CONF*\* → FREQUENCY*\* in v4.0-dev | Removing v3.x feature in v5.0             |
| **User Communication** | None needed (internal tool)        | Release notes + migration guide           |

**Note**: KidsChores does NOT currently have a long-term deprecation system. If you need to deprecate constants across releases (e.g., "remove in v5.0"), use deletion + migration code in next major version instead.

### Example: CONF\_\* Period End Consolidation (Development Cycle)

**Initial State (Development Started):**

```python
# Active constants (lines 358-390)
CONF_DAY_END = "day_end"
CONF_WEEK_END = "week_end"
CONF_MONTH_END = "month_end"
CONF_QUARTER_END = "quarter_end"
CONF_YEAR_END = "year_end"

# Canonical pattern (lines 1000+) - new pattern being introduced
PERIOD_DAY_END = "day_end"
PERIOD_WEEK_END = "week_end"
PERIOD_MONTH_END = "month_end"
PERIOD_QUARTER_END = "quarter_end"
PERIOD_YEAR_END = "year_end"
```

**During Development (Testing new pattern):**

```python
# Active constants (lines 358-390) - now using PERIOD_* everywhere

# Deprecated section (end of file) - marked temporary
# Configuration Keys (Development-Only: Removed before v4.0 production release)
# Replaced by PERIOD_* pattern - PERIOD_* constants now used in all code
CONF_DAY_END_UNUSED = "day_end"  # Use PERIOD_DAY_END instead. [DELETE BEFORE PROD]
CONF_WEEK_END_UNUSED = "week_end"  # Use PERIOD_WEEK_END instead. [DELETE BEFORE PROD]
CONF_MONTH_END_UNUSED = "month_end"  # Use PERIOD_MONTH_END instead. [DELETE BEFORE PROD]
CONF_QUARTER_END_UNUSED = "quarter_end"  # Use PERIOD_QUARTER_END instead. [DELETE BEFORE PROD]
CONF_YEAR_END_UNUSED = "year_end"  # Use PERIOD_YEAR_END instead. [DELETE BEFORE PROD]
```

**Before Production Release (Final cleanup):**

```python
# All active constants (including PERIOD_* patterns)

# _UNUSED section: COMPLETELY REMOVED
# (No deprecated constants left)

# Cleaned, production-ready const.py
```

### Finding & Cleaning \_UNUSED Constants

**Locate all development-cycle \_UNUSED constants:**

```bash
# Find all _UNUSED constants
grep "^[A-Z_]*_UNUSED = " custom_components/kidschores/const.py

# Verify they're not used anywhere (should return no results)
grep -r "CONSTANT_UNUSED" custom_components/kidschores/ --include="*.py"

# Count how many _UNUSED constants remain
grep -c "^[A-Z_]*_UNUSED = " custom_components/kidschores/const.py
```

**Checklist before deleting:**

- [ ] All \_UNUSED constant references removed from codebase
- [ ] Tests pass: `pytest tests/ -q --tb=short` (expect 111 passing)
- [ ] Linting passes: `./utils/quick_lint.sh` (expect 10.00/10)
- [ ] Grep shows zero code references to old constants
- [ ] Code review approved the cleanup
- [ ] Removed before moving to Release Candidate build

---

## Constant Naming Standards (Complete Reference)

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

15. **Error Handling (Phase 3-4B Implementation)** - Template-based internationalized error messages

    **Translation Keys** (5 constants):

    - `TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION` - Action denied for a specific kid (maps to template: "You are not authorized to {action} for this kid.")
    - `TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL` - Global action denied (maps to template: "You are not authorized to {action}.")
    - `TRANS_KEY_ERROR_CALENDAR_CREATE_NOT_SUPPORTED` - Calendar creation not supported
    - `TRANS_KEY_ERROR_CALENDAR_DELETE_NOT_SUPPORTED` - Calendar deletion not supported
    - `TRANS_KEY_ERROR_CALENDAR_UPDATE_NOT_SUPPORTED` - Calendar updates not supported
    - Usage: Exception translation keys in `services.py` (11 uses) and `calendar.py` (3 uses)
    - Consistency: 100% - All error raises use template pattern

    **Action Identifiers** (11 constants):

    - `ERROR_ACTION_APPROVE_CHORES`, `ERROR_ACTION_DISAPPROVE_CHORES`, `ERROR_ACTION_REDEEM_REWARDS`, `ERROR_ACTION_APPROVE_REWARDS`, `ERROR_ACTION_DISAPPROVE_REWARDS`, `ERROR_ACTION_APPLY_PENALTIES`, `ERROR_ACTION_APPLY_BONUSES`, `ERROR_ACTION_RESET_PENALTIES`, `ERROR_ACTION_RESET_BONUSES`, `ERROR_ACTION_RESET_REWARDS`, `ERROR_ACTION_REMOVE_BADGES`
    - Usage: Placeholders in `translation_placeholders={"action": ERROR_ACTION_*}` for template substitution
    - Mapped to: `translations/en.json["action_labels"]` for internationalization
    - Consistency: 100% - All 11 actively used in services.py error raises

    **Implementation Pattern** (HomeAssistantError with translation_key):

    ```python
    # Authorization error (action-specific)
    raise HomeAssistantError(
        translation_domain=const.DOMAIN,
        translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
        translation_placeholders={"action": const.ERROR_ACTION_APPROVE_CHORES},
    )

    # Global authorization error
    raise HomeAssistantError(
        translation_domain=const.DOMAIN,
        translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
    )

    # Calendar operations (no placeholders needed)
    raise HomeAssistantError(
        translation_domain=const.DOMAIN,
        translation_key=const.TRANS_KEY_ERROR_CALENDAR_CREATE_NOT_SUPPORTED,
    )
    ```

    **Translation Templates** (6 entries in `translations/en.json`):

    - `"not_authorized_action"`: "You are not authorized to {action} for this kid."
    - `"not_authorized_action_global"`: "You are not authorized to {action}."
    - `"calendar_create_not_supported"`: "Calendar event creation is not supported"
    - `"calendar_delete_not_supported"`: "Calendar event deletion is not supported"
    - `"calendar_update_not_supported"`: "Calendar event updates are not supported"

    **Phase 3-4B Consolidation Results**:

    - Before: 29 hardcoded ERROR\_\* constants (18 old message constants + 11 unused \_UNUSED constants)
    - After: 16 active constants (5 TRANS*KEY*_ + 11 ERROR*ACTION*_)
    - Benefit: 91% fewer translation keys needed; single template translates to all languages
    - Code Impact: 14 error raises updated to use translation_key pattern (11 in services.py, 3 in calendar.py)
    - Consistency: 100% - All service authorization checks and calendar operations use templated errors

---

## Template Translation System (Phase 3-4B Architecture)

### Design Philosophy: Separation of Content and Templates

KidsChores uses a **template-based translation architecture** that separates:

1. **Message templates** (in `translations/en.json`) - Content that rarely changes
2. **Dynamic placeholders** (via `ERROR_ACTION_*` constants) - Values that vary per context
3. **Translation keys** (via `TRANS_KEY_*` constants) - Stable identifiers for templates

This approach dramatically reduces the translation burden while maintaining full internationalization support.

### How It Works

**Problem (Pre-Phase 3B)**:

- Old system: 29 separate hardcoded error message constants (e.g., `ERROR_NOT_AUTHORIZED_APPROVE_CHORES`, `ERROR_NOT_AUTHORIZED_DISAPPROVE_CHORES`, etc.)
- Each constant required: English definition + translation to es.json, fr.json, de.json, it.json
- Total: 29 × 5 languages = 145 translation entries
- Maintenance: Adding a new action required updating 5+ files

**Solution (Phase 3-4B)**:

- New system: 1 template + 11 action identifiers
- Each action identifier has: 1 English label + translation to es.json, fr.json, de.json, it.json
- Total: 11 × 5 languages = 55 translation entries
- Maintenance: Adding a new action requires: 1 code constant + 5 language labels

**Result**: 62% reduction in translation entries (from 145 to 55)

### Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Template Translation System - Data Flow                        │
└─────────────────────────────────────────────────────────────────┘

CODE (services.py, calendar.py)
    ↓
    raise HomeAssistantError(
        translation_domain=const.DOMAIN,
        translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,  ← Translation Key
        translation_placeholders={"action": const.ERROR_ACTION_APPROVE_CHORES}  ← Placeholder
    )
    ↓
    ↓─────────────────────────────────────────────────────────────┐
    │                                                             │
    │  const.py (Constants)                                      │
    │  ├─ TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION (lookup key)    │
    │  └─ ERROR_ACTION_APPROVE_CHORES (identifier)              │
    │                                                             │
    ↓─────────────────────────────────────────────────────────────┓
    │                                                             │
    │  translations/en.json (Template + Labels)                │
    │  ├─ "exceptions": {                                        │
    │  │   "not_authorized_action": "You are not authorized     │
    │  │     to {action} for this kid."  ← Template             │
    │  ├─ "action_labels": {                                    │
    │  │   "approve_chores": "approve chores"  ← Label          │
    │  │   "disapprove_chores": "disapprove chores"            │
    │  │   ...                                                   │
    │                                                             │
    ↓─────────────────────────────────────────────────────────────┓
    │                                                             │
    │  Home Assistant Template Engine (at runtime)              │
    │  1. Fetch template: "You are not authorized to {action}   │
    │     for this kid."                                         │
    │  2. Fetch label: "approve_chores" → "approve chores"     │
    │  3. Substitute: {action} = "approve chores"              │
    │  4. Render: "You are not authorized to approve chores     │
    │     for this kid."                                        │
    │                                                             │
    ↓─────────────────────────────────────────────────────────────┓

UI (Error Dialog)
    "You are not authorized to approve chores for this kid."
```

### File Structure and Responsibilities

**1. const.py** - Translation Key and Action Constants

```python
# Translation key (single per error pattern)
TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION = "not_authorized_action"

# Action identifiers (one per unique action)
ERROR_ACTION_APPROVE_CHORES = "approve_chores"
ERROR_ACTION_DISAPPROVE_CHORES = "disapprove_chores"
ERROR_ACTION_REDEEM_REWARDS = "redeem_rewards"
# ... 8 more actions
```

**2. translations/en.json** - Templates and Labels

```json
{
  "exceptions": {
    "not_authorized_action": "You are not authorized to {action} for this kid.",
    "not_authorized_action_global": "You are not authorized to {action}."
  },
  "action_labels": {
    "approve_chores": "approve chores",
    "disapprove_chores": "disapprove chores",
    "redeem_rewards": "redeem rewards",
    ...
  }
}
```

**3. services.py, calendar.py** - Error Raises

```python
# All authorization errors use the same template key
raise HomeAssistantError(
    translation_domain=const.DOMAIN,
    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
    translation_placeholders={"action": const.ERROR_ACTION_APPROVE_CHORES},
)
```

### Multi-Language Support (Current and Future)

**Currently Implemented**:

- English (en.json) - COMPLETE ✅
- Mechanism ready for: Spanish (es.json), French (fr.json), German (de.json), Italian (it.json)

**How to Add a New Language**:

1. Copy `translations/en.json` to `translations/es.json` (example: Spanish)
2. Translate ONLY the template strings in `exceptions` and `action_labels`
3. Keep constant names (keys) unchanged
4. No code changes needed - Home Assistant automatically selects language based on user's locale

**Translation File Example (Spanish)**:

```json
{
  "exceptions": {
    "not_authorized_action": "No estás autorizado a {action} para este niño.",
    "not_authorized_action_global": "No estás autorizado a {action}."
  },
  "action_labels": {
    "approve_chores": "aprobar tareas",
    "disapprove_chores": "desaprobar tareas",
    "redeem_rewards": "canjear recompensas",
    ...
  }
}
```

### Advantages Over Hardcoded Constants

| Aspect               | Old Approach (Hardcoded)                 | New Approach (Templates)        |
| -------------------- | ---------------------------------------- | ------------------------------- |
| Constants per action | 1 (message)                              | 1 (identifier only)             |
| Total constants      | 29 ERROR\_\* across all actions          | 11 ERROR*ACTION*\* (reusable)   |
| New language cost    | 29 translations × N languages            | 11 translations × N languages   |
| New action cost      | +1 constant + N translations             | +1 constant + N labels          |
| Consistency          | Error: 11 variations of "not authorized" | Template: 1 source of truth     |
| Maintenance          | Update each constant + each translation  | Update template + labels        |
| i18n Readiness       | 95% done (each message hardcoded)        | 100% ready (structure in place) |
| Scalability          | O(actions × languages)                   | O(actions) + O(languages)       |

### Best Practices for New Errors

When adding new error types to the system:

1. **Define a Translation Key** in `const.py`:

   ```python
   TRANS_KEY_ERROR_MY_NEW_ERROR = "my_new_error"
   ```

2. **Add Exception Template** to `translations/en.json`:

   ```json
   {
     "exceptions": {
       "my_new_error": "Something went wrong: {details}"
     }
   }
   ```

3. **Define Action/Detail Constants** (only if needed):

   ```python
   ERROR_ACTION_MY_NEW_ACTION = "my_new_action"
   ```

4. **Raise Error in Code**:

   ```python
   raise HomeAssistantError(
       translation_domain=const.DOMAIN,
       translation_key=const.TRANS_KEY_ERROR_MY_NEW_ERROR,
       translation_placeholders={"details": const.ERROR_ACTION_MY_NEW_ACTION},
   )
   ```

5. **Add Translations** (for each new language file):
   - Copy template to translations/es.json, fr.json, etc.
   - Translate only the message content
   - Keep JSON structure identical

### Architectural Constraints

- **Template variables**: Must use `{variable_name}` syntax (curly braces required)
- **Placeholder keys**: Must match variable names in template (e.g., `{action}` → `{"action": ...}`)
- **Translation keys**: Must be unique per error pattern (no duplicates across exception types)
- **Action labels**: Must be lowercase, single-word or hyphenated (e.g., `"approve-chores"` not `"ApprovChores"`)
- **JSON format**: Must be valid JSON in all translation files (test with `python -m json.tool`)

---

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
| DATA\_\*          | 500+      | 100%        | Jan 2026     |
| CFOF\_\*          | 150+      | 100%        | Jan 2026     |
| TRANS*KEY_CFOF*\* | 110+      | 100%        | Jan 2026     |
| ATTR\_\*          | 100+      | 100%        | Jan 2026     |
| SENSOR*KC*\*      | 40+       | 100%        | Jan 2026     |
| BUTTON*KC*\*      | 20+       | 100%        | Jan 2026     |
| SERVICE\_\*       | 17        | 100%        | Jan 2026     |
| OPTIONS*FLOW*\*   | 65+       | 100%        | Jan 2026     |
| TRANS_KEY_ERROR   | 5         | 100%        | Jan 2026     |
| ERROR_ACTION\_\*  | 11        | 100%        | Jan 2026     |
| BADGE\_\*         | 30+       | 100%        | Jan 2026     |
| **TOTAL**         | **1000+** | **~99%**    | **Jan 2026** |

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

**Before (Legacy)**:

- Config entry size: 50-200KB (limited by Home Assistant)
- Integration reload: Must process all entity data from config
- Options flow: Complex merging logic to avoid data loss
- Startup time: Slow (reads + migrates large config)

**After (v0.5.0)**:

- Config entry size: < 1KB (only 9 settings)
- Integration reload: Only processes system settings (fast)
- Options flow: Direct storage writes (simple)
- Startup time: Fast (reads lightweight config, storage loads once)

### Reload Performance Comparison

```
┌──────────────────────────────────────────────────┐
│ Integration Reload Time (with 20 kids, 50 chores)│
├──────────────────────────────────────────────────┤
│ Legacy (config-based):     2.5s                  │
│ v0.5.0 (storage-only):     0.3s                  │
│                                                  │
│ Improvement: 8x faster                           │
└──────────────────────────────────────────────────┘
```

---

## Developer Guide

### Entity Lookup Helper Pattern

**Location**: `custom_components/kidschores/kc_helpers.py` (Lines 245-390)

**Version**: ✅ v0.5.0 - Complete coverage for all 9 entity types

The integration provides standardized entity lookup functions for resolving entity names to internal IDs. **All 9 entity types are now fully supported** with consistent patterns.

#### Basic Lookup Functions (Optional Return)

Return `Optional[str]` - caller must handle `None`:

```python
# Supported for 9 entity types (complete coverage):
def get_kid_id_by_name(coordinator: KidsChoresDataCoordinator, kid_name: str) -> Optional[str]
def get_parent_id_by_name(coordinator: KidsChoresDataCoordinator, parent_name: str) -> Optional[str]
def get_chore_id_by_name(coordinator: KidsChoresDataCoordinator, chore_name: str) -> Optional[str]
def get_reward_id_by_name(coordinator: KidsChoresDataCoordinator, reward_name: str) -> Optional[str]
def get_penalty_id_by_name(coordinator: KidsChoresDataCoordinator, penalty_name: str) -> Optional[str]
def get_bonus_id_by_name(coordinator: KidsChoresDataCoordinator, bonus_name: str) -> Optional[str]
def get_badge_id_by_name(coordinator: KidsChoresDataCoordinator, badge_name: str) -> Optional[str]
def get_achievement_id_by_name(coordinator: KidsChoresDataCoordinator, achievement_name: str) -> Optional[str]
def get_challenge_id_by_name(coordinator: KidsChoresDataCoordinator, challenge_name: str) -> Optional[str]
```

**Usage**: When you need to check if entity exists without raising errors:

```python
kid_id = get_kid_id_by_name(coordinator, "Sarah")
if kid_id:
    # Process kid data
else:
    # Handle missing kid case
```

#### Lookup-or-Raise Helper Functions (Non-Optional Return)

Return `str` - raises `HomeAssistantError` if entity not found:

```python
# Supported for 9 entity types (complete coverage):
def get_kid_id_or_raise(coordinator: KidsChoresDataCoordinator, kid_name: str, action: str) -> str
def get_parent_id_or_raise(coordinator: KidsChoresDataCoordinator, parent_name: str, action: str) -> str
def get_chore_id_or_raise(coordinator: KidsChoresDataCoordinator, chore_name: str, action: str) -> str
def get_reward_id_or_raise(coordinator: KidsChoresDataCoordinator, reward_name: str, action: str) -> str
def get_penalty_id_or_raise(coordinator: KidsChoresDataCoordinator, penalty_name: str, action: str) -> str
def get_bonus_id_or_raise(coordinator: KidsChoresDataCoordinator, bonus_name: str, action: str) -> str
def get_badge_id_or_raise(coordinator: KidsChoresDataCoordinator, badge_name: str, action: str) -> str
def get_achievement_id_or_raise(coordinator: KidsChoresDataCoordinator, achievement_name: str, action: str) -> str
def get_challenge_id_or_raise(coordinator: KidsChoresDataCoordinator, challenge_name: str, action: str) -> str
```

**Usage**: Primary pattern for service handlers and validation code:

```python
# Before (4 lines):
kid_id = kh.get_kid_id_by_name(coordinator, kid_name)
if not kid_id:
    const.LOGGER.warning("WARNING: Claim Chore: Kid not found: %s", kid_name)
    raise HomeAssistantError(f"Kid '{kid_name}' not found")

# After (1 line):
kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Claim Chore")
```

**Parameters**:

- `coordinator`: The KidsChores data coordinator instance
- `entity_name`: Name of the entity to look up (kid, chore, reward, etc.)
- `action`: Description of the action for error context (e.g., "Claim Chore", "Apply Penalty")

**Error Handling**:

- Logs warning with context: `"WARNING: {action}: {entity_type} not found: {entity_name}"`
- Raises: `HomeAssistantError(f"{entity_type} '{entity_name}' not found")`

**Implementation Pattern**:
Each helper follows this template:

```python
def get_entity_id_or_raise(coordinator, entity_name: str, action: str) -> str:
    """Get entity ID by name or raise HomeAssistantError if not found."""
    entity_id = get_entity_id_by_name(coordinator, entity_name)
    if not entity_id:
        const.LOGGER.warning("WARNING: %s: Entity not found: %s", action, entity_name)
        raise HomeAssistantError(f"Entity '{entity_name}' not found")
    return entity_id
```

**Design Rationale**:

- **Eliminates Code Duplication**: Reduces ~200+ lines of duplicate validation patterns in services.py
- **HA Core Precedent**: Follows pattern from `device_automation.__init__.py:async_get_entity_registry_entry_or_raise()`
- **Type Safety**: Return type is `str` (not `Optional[str]`), enabling mypy/pylint validation
- **Error Context**: `action` parameter provides meaningful context in logs and errors

**When to Use Each Pattern**:

- **Use `get_*_id_by_name()`**: UI code, optional lookups, existence checks
- **Use `get_*_id_or_raise()`**: Service handlers, validation that must fail fast

---

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

---

### Entity Class Naming Standards

**Core Pattern**: `[Scope][Entity][Property]EntityType`

All entity classes follow a consistent naming convention that makes the code self-documenting and ensures naming consistency across the entire codebase. This pattern applies to **all entity types** (sensors, buttons, selects, calendars, etc.).

#### Components

1. **Scope** (required): Indicates the data scope and ownership

   - `Kid` - Per-kid data/actions initiated by the kid (e.g., `KidPointsSensor`, `KidChoreClaimButton`, `KidRewardRedeemButton`)
   - `Parent` - Per-kid actions initiated by parents/admins (e.g., `ParentChoreApproveButton`, `ParentPenaltyApplyButton`, `ParentPointsAdjustButton`)
   - `System` - System-wide data aggregating across ALL kids (e.g., `SystemBadgeSensor`, `SystemChoresPendingApprovalSensor`)
   - **Rule**: ALL entities MUST have explicit scope prefix (no blank scopes)
   - **Distinction**: `Kid` and `Parent` scopes are per-kid (one instance per kid), while `System` scope is global (one instance shared across all kids)

2. **Entity**: The subject being measured or acted upon

   - Primary: `Chore`, `Badge`, `Reward`, `Penalty`, `Bonus`, `Achievement`, `Challenge`, `Points`
   - Plural form for collections: `Chores`, `Badges`, `Rewards`, etc. (used when representing multiple)

3. **Property**: The specific aspect or action
   - For sensors: `Status`, `Progress`, `Approvals`, `Applied`, `Earned`, `Streak`, `Highest`, `Pending`
   - For buttons: `Claim`, `Approve`, `Disapprove`, `Apply`, `Redeem`
   - For selects: `Assigned`, `Available`, `Filter`
   - **Order**: Property typically follows entity (e.g., `BadgeHighest` not `HighestBadge`)

#### Naming Best Practices

**1. Consistent Property Ordering**

- ✅ `KidBadgeHighestSensor` - Property after entity type
- ❌ `KidHighestBadgeSensor` - Inconsistent ordering

**2. Plural for Collections, Singular for Items**

- ✅ `SystemChoresPendingApprovalSensor` - Multiple chores pending
- ✅ `SystemChoreSharedStateSensor` - Single chore's state
- ❌ `SystemChorePendingApprovalsSensor` - Mixing singular/plural

**3. System Prefix for Global Entities**

- ✅ `SystemBadgeSensor` - Badge data aggregated across system
- ❌ `BadgeSensor` - Ambiguous scope

**4. Descriptive Property Names**

- ✅ `SystemChoreSharedStateSensor` - Clear: shared chore state
- ❌ `SystemChoreGlobalStateSensor` - "Global" ambiguous with "System"

#### Modern Entity Naming (15 Sensor Examples)

**Kid-Specific Sensors** (11 total):

```python
KidChoreStatusSensor          # Status of specific chore for kid
KidPointsSensor               # Current point balance for kid
KidChoresSensor               # All-time chore stats for kid
KidBadgeHighestSensor         # Highest badge earned by kid (property after entity)
KidBadgeProgressSensor        # Progress toward earning specific badge
KidRewardStatusSensor         # Reward claim/approval status for kid
KidPenaltyAppliedSensor       # Count of penalty applications to kid
KidBonusAppliedSensor         # Count of bonus applications to kid
KidAchievementProgressSensor  # Progress toward achievement for kid
KidChallengeProgressSensor    # Progress toward challenge for kid
KidDashboardHelperSensor      # Aggregated dashboard data for kid
```

**System-Level Sensors** (4 total):

```python
SystemBadgeSensor                # Badge information aggregated across system
SystemChoreSharedStateSensor     # Global state of specific shared chore
SystemAchievementSensor          # Achievement progress across all kids
SystemChallengeSensor            # Challenge progress across all kids
```

**Legacy Sensors** (11 total, optional via `show_legacy_entities` flag):

```python
# System aggregate sensors
SystemChoreApprovalsSensor           # Total chore approvals (all kids)
SystemChoreApprovalsDailySensor      # Today's approvals
SystemChoreApprovalsWeeklySensor     # This week's approvals
SystemChoreApprovalsMonthlySensor    # This month's approvals
SystemChoresPendingApprovalSensor    # Pending chore approvals (plural: multiple chores)
SystemRewardsPendingApprovalSensor   # Pending reward approvals (plural: multiple rewards)

# Kid aggregate sensors
KidMaxPointsEverSensor               # Highest points ever reached by kid
KidChoreStreakSensor                 # Longest completion streak for kid
KidPointsEarnedDailySensor           # Points earned today
KidPointsEarnedWeeklySensor          # Points earned this week
KidPointsEarnedMonthlySensor         # Points earned this month
```

#### Applying Naming Pattern to Other Entity Types

The same `[Scope][Entity][Property]EntityType` pattern applies consistently across **all platforms**:

**Button Entities**:

```python
# Kid-scoped buttons (kid-initiated actions)
KidChoreClaimButton                  # Kid claims a chore
KidRewardRedeemButton                # Kid redeems a reward

# Parent-scoped buttons (parent-initiated actions on a specific kid)
ParentChoreApproveButton             # Parent approves chore for kid
ParentChoreDisapproveButton          # Parent disapproves chore for kid
ParentRewardApproveButton            # Parent approves reward for kid
ParentRewardDisapproveButton         # Parent disapproves reward for kid
ParentBonusApplyButton               # Parent applies bonus to kid
ParentPenaltyApplyButton             # Parent applies penalty to kid
ParentPointsAdjustButton             # Parent manually adjusts kid's points
```

**Select Entities**:

```python
# Kid-scoped selects (dashboard helpers)
KidDashboardHelperChoresSelect       # Kid's chores for UI dashboard selection

# System-scoped selects (global lists for system-wide actions)
SystemChoresSelect                   # All chores across all kids
SystemRewardsSelect                  # All rewards across all kids
SystemPenaltiesSelect                # All penalties across all kids
SystemBonusesSelect                  # All bonuses across all kids
```

**Calendar Entities**:

```python
# Kid-scoped calendars
KidScheduleCalendar          # Kid's schedule (chores + challenges combined)
KidRewardHistoryCalendar     # Kid's reward history

# System-scoped calendars
SystemChoreGlobalCalendar    # All chores across all kids
SystemEventMasterCalendar    # System-wide event calendar
```

**DateTime Entities**:

```python
# Kid-scoped datetime (dashboard helpers)
KidDashboardHelperDateTimePicker     # Kid's date/time picker for UI dashboard
KidDailyResetDatetime                # Kid's daily reset time override

# System-scoped datetime
SystemDailyResetDatetime             # System-wide daily reset time
```

#### File Organization Pattern

**Modern Entities** (`sensor.py`, `button.py`, `select.py`, `calendar.py`):

```python
"""Entity file header with counts and organization.

Entities Defined in This File (X):

# Kid-Specific Entities (X)
01. Kid[Entity][Property][Type]
02. ...

# System-Level Entities (X)
XX. System[Entity][Property][Type]
XX+1. ...

Legacy Entities Imported from [type]_legacy.py (X):
- System[Entity]...[Type]  (optional, controlled by show_legacy_entities flag)
"""
```

**Legacy Entities** (`sensor_legacy.py`, etc.):

- Wrapped in `if show_legacy_entities:` blocks during instantiation
- Module-level imports (for Python caching optimization)
- Clearly documented as deprecated with data migration paths

#### Key Implementation Patterns

**1. Performance Optimization** (entity registry access):

```python
# ❌ Bad: O(n) iteration over entire registry
for entity in entity_registry.entities.values():
    if entity.unique_id.endswith("_suffix"):
        found_entity = entity

# ✅ Good: O(1) direct lookup
entity_id = entity_registry.async_get_entity_id(
    platform="sensor",
    domain=const.DOMAIN,
    unique_id=f"{entry_id}_{kid_id}_suffix"
)
```

**2. Legacy Entity Pattern**:

```python
# sensor_legacy.py - Module-level imports (Python caching)
from . import const
from .coordinator import KidsChoresDataCoordinator

class SystemOldFeatureSensor(CoordinatorEntity, SensorEntity):
    """Legacy sensor (data now in modern sensor attributes)."""
    ...

# sensor.py - Conditional instantiation
from .sensor_legacy import SystemOldFeatureSensor

show_legacy_entities = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
if show_legacy_entities:
    entities.append(SystemOldFeatureSensor(coordinator, entry))
```

**3. Coordinator-Based Entities**:

```python
class Kid[Entity][Property]Sensor(CoordinatorEntity, SensorEntity):
    """Sensor description."""

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SENSOR_[ENTITY]_[PROPERTY]

    def __init__(self, coordinator: KidsChoresDataCoordinator, entry: ConfigEntry, ...):
        super().__init__(coordinator)
        # Initialize with coordinator data access

    @property
    def native_value(self):
        """Get value from coordinator data."""
        return self.coordinator.kids_data[self._kid_id].get(const.DATA_[ENTITY]_[PROPERTY])

    @property
    def extra_state_attributes(self):
        """Provide rich context via attributes."""
        return {
            const.ATTR_PURPOSE: "What this sensor value represents",
            const.ATTR_[ENTITY]_NAME: self._entity_name,
            # ... comprehensive attributes for frontend/automations
        }
```

**4. Header Documentation**:

Every entity file MUST have:

- Total count (modern + system-level)
- Categorized list (Kid-Specific vs System-Level)
- Legacy imports documented separately
- Clear numbering for easy reference

#### Benefits of This Pattern

✅ **Self-Documenting Code**: Class name immediately reveals scope, subject, and action
✅ **IDE Auto-Complete**: Typing `Kid` or `System` filters relevant entities
✅ **Grep-Friendly**: Searching `System` finds all system-level entities
✅ **Consistent Maintenance**: Same pattern across 5+ entity types
✅ **Future-Proof**: Easy to add new entity types following same structure
✅ **Performance-Optimized**: O(1) lookups documented and enforced
✅ **Clean Deprecation**: Legacy entities isolated with clear migration paths

See [SENSOR_REFACTORING_PLAN.md](SENSOR_REFACTORING_PLAN.md) and [SENSOR_CLEANUP_AND_PERFORMANCE.md](SENSOR_CLEANUP_AND_PERFORMANCE.md) for the complete refactoring plan and performance optimization details.

---

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

All tests should use `schema_version: 42` in fixtures:

```python
@pytest.fixture
def mock_storage_data():
    return {
        const.DATA_META: {
            const.DATA_META_SCHEMA_VERSION: 42  # v42+ format
        },
        const.DATA_KIDS: {...},
        const.DATA_CHORES: {...},
        # No top-level schema_version in v42+ format
    }
```

---

## Legacy Code Removal Timeline

### v0.5.0 (Current)

- ✅ Storage-only mode active
- ✅ Migration code functional
- ✅ Legacy `_initialize_data_from_config()` present (for pre-v0.5.0 users)

### Future Release (TBD)

- ⚠️ Deprecation warnings for users still on schema < 42
- ⚠️ Documentation encourages upgrade to v0.5.0+
- ⚠️ Evaluate optional deprecation of redundant sensor entities

### Long-term (TBD)

- ❌ Remove `_initialize_data_from_config()` method (~160 lines)
- ❌ Remove migration constants (MIGRATION\*, \*\_LEGACY)
- ❌ Require `meta.schema_version >= 42` for all installations
- ❌ Breaking change: Pre-v0.5.0 users must upgrade to v0.5.0+ first

**Prerequisite**: Telemetry showing <1% of users on schema version < 42

---

## File Reference

### Core Files

| File                 | Purpose                 | Lines | Key Sections                                      |
| -------------------- | ----------------------- | ----- | ------------------------------------------------- |
| `__init__.py`        | Entry point, migration  | 400   | `_migrate_config_to_storage()` (25-237)           |
| `coordinator.py`     | Business logic, storage | 8,517 | Version check (914-929), `_persist()` (8513-8517) |
| `const.py`           | Constants               | 2,325 | `SCHEMA_VERSION_STORAGE_ONLY = 42` (56-58)        |
| `config_flow.py`     | Initial setup           | 1,291 | Direct-to-storage write                           |
| `options_flow.py`    | Settings & entities     | 2,589 | Direct storage updates                            |
| `storage_manager.py` | Storage abstraction     | 76    | `async_save()`, `get_data()`                      |

### Storage Files

| Path                               | Purpose                   | Format                   |
| ---------------------------------- | ------------------------- | ------------------------ |
| `.storage/kidschores_data`         | Entity data + runtime     | JSON (STORAGE_VERSION=1) |
| `.storage/kidschores_data_*_<tag>` | Migration/restore backups | JSON (timestamped)       |

---

## Troubleshooting

### Storage Corruption Recovery

If storage is corrupted, the integration will attempt to recover:

1. **With KC 3.x Backup**: If `meta.schema_version < 42`, runs migration from `config_entry.options`
2. **Without Backup**: Creates fresh storage with `meta.schema_version: 42` (data loss)

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

## Mandatory vs Optional Constants: Usage Requirements

### Mandatory: ALL User-Facing Text MUST Use Constants

**Do NOT hardcode user-visible strings.** This rule applies to **ALL** text that any user—even a developer—might encounter:

#### Categories Requiring Constants

1. **Service Error Messages** (ALL exceptions and errors)

   ```python
   # ❌ WRONG - Hardcoded error message
   raise HomeAssistantError("Kid not found")

   # ✅ CORRECT - Uses constant and translation framework
   raise HomeAssistantError(
       translation_domain=const.DOMAIN,
       translation_key=const.TRANS_KEY_ERROR_ENTITY_NOT_FOUND,
       translation_placeholders={"entity_type": "Kid", "name": kid_name},
   )
   ```

2. **Config/Options Flow Labels, Descriptions, and Errors**

   ```python
   # ❌ WRONG - Hardcoded UI text
   STEP_USER_SCHEMA = vol.Schema({
       vol.Required("name"): cv.string,
   })

   # ✅ CORRECT - Uses const and translation keys
   STEP_USER_SCHEMA = vol.Schema({
       vol.Required(const.CFOF_KIDS_INPUT_NAME): cv.string,
   })
   errors[const.CFOP_ERROR_KID_NAME] = const.TRANS_KEY_CFOF_INVALID_KID_NAME
   ```

3. **Entity Names, Descriptions, and Attributes**

   ```python
   # ❌ WRONG - Hardcoded entity name
   _attr_name = "Temperature"

   # ✅ CORRECT - Uses translation key
   _attr_translation_key = "temperature"
   ```

4. **Notification Messages**

   ```python
   # ❌ WRONG - Hardcoded notification text
   await hass.components.persistent_notification.async_create(
       "Chore approved!"
   )

   # ✅ CORRECT - Uses translation framework
   notification_data = {
       ATTR_TITLE: "Chore Approved",
       ATTR_MESSAGE: translate_template(
           const.TRANS_KEY_NOTIFICATION_CHORE_APPROVED,
           {"chore_name": chore_name}
       ),
   }
   ```

5. **User-Visible Log Messages (INFO, WARNING, ERROR levels)**

   ```python
   # ❌ WRONG - Hardcoded log message at user-visible level
   _LOGGER.warning("User deleted chore successfully")

   # ✅ CORRECT - Uses constant for consistency
   _LOGGER.warning(
       "Claim Chore: %s",
       const.TRANS_KEY_ACTION_CLAIM_CHORE_SUCCESS,
   )
   ```

#### Why This Matters

- **Localization**: Constants enable translation to 40+ languages without code changes
- **Consistency**: All error messages follow the same pattern and tone
- **Maintainability**: Change a message once in `const.py`, applies everywhere
- **Quality**: Code review can verify all user-facing text uses proper frameworks
- **Debugging**: Developers can trace which part of code generated a user message

---

### Optional: Debug Logging Does NOT Require Constants

**Debug logs are developer-only output.** You may use inline f-strings for rapid prototyping and troubleshooting:

#### When Debug Logging is Acceptable

1. **Debug-Level Logs** (not shown to users unless explicitly enabled)

   ```python
   # ✅ ACCEPTABLE - Debug logs don't need constants
   _LOGGER.debug(f"Processing chore: {chore_data}")
   _LOGGER.debug(f"Kid points: {kid_info.get('points', 0)}")
   _LOGGER.debug(f"Badge criteria: {badge_config}")
   ```

2. **Exception Stack Traces and Internal State**

   ```python
   # ✅ ACCEPTABLE - Internal diagnostics
   _LOGGER.debug(f"Storage structure: {json.dumps(coordinator.kids_data, indent=2)}")
   _LOGGER.debug(f"Exception details: {traceback.format_exc()}")
   ```

3. **Temporary Development Output** (removed before commit)
   ```python
   # ✅ ACCEPTABLE FOR DEBUGGING - Remove before commit
   _LOGGER.debug(f"TODO: Fix chore claim for {kid_id} - current state: {state}")
   ```

#### Why This is Acceptable

- Debug logs are only visible when `logger: custom_components.kidschores: debug` is set in `configuration.yaml`
- Users will not see these messages in normal operation
- Developers need rapid iteration without constant overhead
- Performance: Avoids unnecessary constant lookups in debug paths
- Clarity: Context and variable names make the debug intent obvious

#### Non-Negotiable: Do NOT Do This

```python
# ❌ WRONG - Debug logs MUST be at DEBUG level, not INFO
_LOGGER.info(f"Temporary debug: {some_var}")  # USERS WILL SEE THIS

# ❌ WRONG - Don't hardcode user-visible WARNING/ERROR messages
_LOGGER.error("Chore approval failed")  # Should use constant + translation

# ❌ WRONG - Don't mix debug output with user messages
_LOGGER.warning(
    f"DEBUG: Processing {kid_id}, state={state}, expected={expected}"
    # USERS WILL SEE "DEBUG:" label
)
```

---

### Implementation Checklist

When adding new user-facing text, ask yourself:

1. **Is this text shown to a user?** (error message, notification, entity name, config label, log)

   - YES → Use a constant and translation key
   - NO → Check question 2

2. **Is this output at DEBUG log level?**

   - YES → f-string is OK for rapid development (but clean before commit)
   - NO → Check question 3

3. **Is this internal diagnostics or development tool output?**
   - YES → f-string is acceptable
   - NO → Use a constant

**Decision Tree Summary**:

```
User-facing text?
├─ YES → Use const + TRANS_KEY (mandatory)
└─ NO
   ├─ Debug log? → f-string OK (optional)
   ├─ Exception details? → f-string OK (optional)
   └─ Production INFO/WARNING/ERROR? → Use const (mandatory)
```

---

### Code Examples: Before & After

#### Example 1: Service Handler Error

**Before (❌ No constants)**:

```python
async def async_claim_chore(hass: HomeAssistant, service_call: ServiceCall) -> None:
    """Claim a chore."""
    kid_name = service_call.data.get(ATTR_KID)
    chore_name = service_call.data.get(ATTR_CHORE)

    if not kid_info:
        raise HomeAssistantError(f"Kid '{kid_name}' not found")
    if not chore_info:
        raise HomeAssistantError(f"Chore '{chore_name}' not found")
```

**After (✅ With constants)**:

```python
async def async_claim_chore(hass: HomeAssistant, service_call: ServiceCall) -> None:
    """Claim a chore."""
    kid_name = service_call.data.get(ATTR_KID)
    chore_name = service_call.data.get(ATTR_CHORE)

    if not kid_info:
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_ENTITY_NOT_FOUND,
            translation_placeholders={"entity_type": "Kid", "name": kid_name},
        )
    if not chore_info:
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_ENTITY_NOT_FOUND,
            translation_placeholders={"entity_type": "Chore", "name": chore_name},
        )
```

#### Example 2: Config Flow Validation

**Before (❌ No constants)**:

```python
async def async_step_user(self, user_input=None):
    errors = {}

    if not user_input[name]:
        errors["name"] = "invalid_name"

    if duplicate_check(user_input[name]):
        errors["name"] = "name_already_exists"
```

**After (✅ With constants)**:

```python
async def async_step_user(self, user_input=None):
    errors = {}

    if not user_input[const.CFOF_KIDS_INPUT_NAME]:
        errors[const.CFOP_ERROR_KID_NAME] = const.TRANS_KEY_CFOF_KID_NAME_REQUIRED

    if duplicate_check(user_input[const.CFOF_KIDS_INPUT_NAME]):
        errors[const.CFOP_ERROR_KID_NAME] = const.TRANS_KEY_CFOF_DUPLICATE_KID
```

#### Example 3: Debug vs Production Logging

**Before (❌ Mixed concerns)**:

```python
_LOGGER.warning(f"DEBUG: Processing kid {kid_id}")  # Mixed debug into warning
_LOGGER.info(f"Chore update failed: {error}")  # Hardcoded, no constant
```

**After (✅ Separated concerns)**:

```python
_LOGGER.debug(f"Processing kid {kid_id}")  # Debug level OK, f-string fine
_LOGGER.warning(
    "Update Chore: %s",
    const.TRANS_KEY_ACTION_UPDATE_CHORE_FAILED,  # User-visible, use constant
)
```

---

## Quality Standards & Maintenance Guide

This section documents the code quality standards required to maintain Silver certification and the pathway to Gold. These standards are based on [Home Assistant's Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index/) as documented in [AGENTS.md](../../core/AGENTS.md).

### Silver Quality Requirements (Mandatory - All Implemented ✅)

**1. Configuration Flow** ✅

- UI setup required for all configuration
- Multi-step dynamic flow with user input validation
- Error handling with translation keys
- Duplicate detection via unique IDs
- Storage separation: Connection config in `ConfigEntry.data`, settings in `ConfigEntry.options`

**Implementation Reference**: [custom_components/kidschores/config_flow.py](../custom_components/kidschores/config_flow.py)

**2. Entity Unique IDs** ✅

- Every entity has a unique ID stored in entity registry
- Unique IDs use `entry_id` + `internal_id` (UUID) + entity-specific suffix
- Survives entity renames and configuration reloads
- Format: `f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_POINTS}"`

**Implementation Reference**: All entity platforms (sensor.py, button.py, select.py, etc.)

**3. Service Actions with Validation** ✅

- 17 services registered with input validation
- `ServiceValidationError` for user input errors
- `HomeAssistantError` with translation keys for runtime errors
- Config entry existence and loaded state checks

**Implementation Reference**: [custom_components/kidschores/services.py](../custom_components/kidschores/services.py)

**4. Entity Unavailability Handling** ✅

- All 30+ entities implement explicit `available` property
- Returns `False` when coordinator data missing or stale
- Uses `None` for unknown values (not "unknown" or "unavailable" strings)
- Proper error handling in coordinator updates

**Implementation Reference**: All entity classes with `@property def available(self) -> bool:`

**5. Parallel Updates** ✅

- `PARALLEL_UPDATES` set to `0` (unlimited) for coordinator-based entities
- Entities don't poll (rely on coordinator)
- Efficient concurrent state updates

**Implementation Reference**: [custom_components/kidschores/sensor.py](../custom_components/kidschores/sensor.py) (line ~40)

**6. Logging When Unavailable** ✅

- INFO level log when service/device becomes unavailable
- INFO level log when service/device recovers
- Single-log-per-state pattern (avoid log spam)

**Example Pattern**:

```python
_unavailable_logged: bool = False

if not self._unavailable_logged:
    _LOGGER.info("Service unavailable: %s", reason)
    self._unavailable_logged = True

# On recovery:
if self._unavailable_logged:
    _LOGGER.info("Service recovered")
    self._unavailable_logged = False
```

### Code Quality Standards (All Implemented ✅)

**Type Hints**: 100% Required

```python
# ✅ All functions have complete type hints
async def async_claim_chore(
    self,
    kid_id: str,
    chore_id: str,
) -> tuple[bool, str]:
    """Claim a chore for a kid."""
```

**Lazy Logging**: 100% Required (No F-Strings in Logging)

```python
# ✅ Always use lazy logging with %s placeholders
_LOGGER.debug("Processing chore for kid: %s", kid_name)
_LOGGER.info("Points adjusted for kid: %s to %s", kid_name, new_points)

# ❌ Never use f-strings in logging (evaluated even when log level skips)
_LOGGER.debug(f"Processing {kid_name}")  # BAD - performance impact
```

**Constants for All User-Facing Strings**: 100% Required

```python
# ✅ Store constants in const.py
TRANS_KEY_ERROR_KID_NOT_FOUND = "error_kid_not_found"
TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED = "notif_title_chore_approved"

# In code:
raise HomeAssistantError(
    translation_domain=const.DOMAIN,
    translation_key=const.TRANS_KEY_ERROR_KID_NOT_FOUND,
)

# ❌ Never hardcode user-visible strings
raise HomeAssistantError(f"Kid {kid_name} not found")
```

**Exception Handling**: Specific Exceptions Required

```python
# ✅ Use most specific exception type available
try:
    data = await client.fetch_data()
except ApiConnectionError as err:
    raise HomeAssistantError("Connection failed") from err
except ApiAuthError as err:
    raise ConfigEntryAuthFailed("Auth expired") from err

# ❌ Avoid bare exceptions (except in config flows for robustness)
try:
    data = await client.fetch_data()
except Exception:  # Too broad
    _LOGGER.error("Failed")
```

**Docstrings**: Required for All Public Functions

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KidsChores from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Configuration entry

    Returns:
        True if setup successful
    """
```

### Testing Requirements (95%+ Coverage Required)

**Test Categories**:

1. **Config Flow Tests** (`test_config_flow.py`) - All UI paths
2. **Options Flow Tests** (`test_options_flow_*.py`) - Settings navigation
3. **Coordinator Tests** (`test_coordinator.py`) - Business logic
4. **Service Tests** (`test_services.py`) - All 17 services
5. **Workflow Tests** (`test_workflow_*.py`) - End-to-end scenarios

**Current Status**: 699/699 tests passing (100% baseline maintained)

**Validation Commands**:

```bash
# Run full linting (must pass with 9.5+/10 score)
./utils/quick_lint.sh --fix

# Run full test suite (must pass)
python -m pytest tests/ -v --tb=line
```

### Code Review Checklist (Before Committing)

Use this checklist when reviewing or modifying code:

**Phase 0 Audit Framework** (REQUIRED FIRST):

- [ ] Read files to identify all user-facing strings
- [ ] Identify all hardcoded dictionary keys
- [ ] List all repeated string literals
- [ ] Verify all TRANS*KEY*\* constants exist in en.json
- [ ] Document findings in standardized audit report

**Code Quality Checks**:

- [ ] No hardcoded user-facing strings (all use const.py constants)
- [ ] No f-strings in logging calls (lazy logging only)
- [ ] All functions have type hints (args + return type)
- [ ] All exceptions use translation_domain + translation_key pattern
- [ ] Entity unique IDs follow `entry_id_{scope_id}{SUFFIX}` pattern
- [ ] No direct storage access (use coordinator methods)
- [ ] Docstrings present for all public functions

**Silver Quality Scale Checks**:

- [ ] Config flow uses dynamic steps with validation
- [ ] All entities have unique IDs
- [ ] Services use ServiceValidationError for input errors
- [ ] Entities implement `available` property
- [ ] Parallel updates configured correctly
- [ ] Logging follows unavailability pattern

**Testing Checks**:

- [ ] New code has corresponding test cases
- [ ] All tests pass: `pytest tests/ -v --tb=line`
- [ ] Linting passes: `./utils/quick_lint.sh --fix` (9.5+/10)
- [ ] Coverage maintained at 95%+
- [ ] No regressions in existing tests

**Before Marking Complete**:

- [ ] All linting passes (`./utils/quick_lint.sh --fix`)
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Plan document updated (if following phase plan)
- [ ] Commit message documents what was changed and why

### Home Assistant Quality Standards Reference

For ongoing reference and to maintain Silver certification (and pathway to Gold), consult:

- **[AGENTS.md](../../core/AGENTS.md)** - Home Assistant's authoritative code quality guide

  - Covers all quality scale levels (Bronze, Silver, Gold, Platinum)
  - Documents async patterns, exception handling, entity development
  - Provides code examples and best practices

- **[quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml)** - Current rule status

  - Shows which Silver rules are "done"
  - Indicates if any rules are "exempt" with rationale
  - Tracks next steps for Gold certification

- **[CODE_REVIEW_GUIDE.md](../docs/CODE_REVIEW_GUIDE.md)** - KidsChores-specific review patterns
  - Phase 0 audit framework for new files
  - Platform-specific review checklists
  - Common issues and fixes
  - Performance optimization guidelines

### Gold Certification Pathway

Once Silver is stable, Gold certification requires:

- **Phase 5A**: Device Registry Integration (3-4 hours)
- **Phase 6**: Repair Framework (4-6 hours)
- **Phase 7**: Documentation Expansion (5-7 hours)
- **Phase 8**: Testing & Release (1.5-2 hours)

See [docs/in-process/GOLD_CERTIFICATION_ROADMAP.md](../docs/in-process/GOLD_CERTIFICATION_ROADMAP.md) for detailed Gold implementation plans.

---

### Helper Function Enhancements

**Complete Coverage**: All 9 entity types now have standardized lookup helpers:

- ✅ Kids, Parents, Chores, Rewards, Penalties, Bonuses, Badges, Achievements, Challenges
- ✅ Each type supports both optional (`*_by_name`) and required (`*_by_raise`) patterns
- ✅ Consistent error handling and logging across all lookups

### Code Quality Improvements

**Consolidation**:

- ✅ Removed 40+ duplicate entity lookup code patterns
- ✅ Centralized 9 magic constants (END*OF_DAY*_, MONTHS*PER*_, etc.) to `const.py`
- ✅ Refactored 2 inline coordinator lookup loops to use helper functions

**Documentation**:

- ✅ Added comprehensive docstrings to all 18 public helper functions
- ✅ Reorganized kc_helpers.py with 10 emoji-header sections for better navigation
- ✅ Updated ARCHITECTURE.md to document complete 9-type coverage

**Testing**:

- ✅ Added 8 comprehensive edge case test methods covering:
  - Entity lookup boundary conditions
  - Authorization for admins and registered parents
  - Datetime month/year-end transitions
  - Progress calculation with scenario data
- ✅ All 552 existing tests still passing (zero regressions)
- ✅ Linting: 9.64/10 (zero critical errors)

### Performance Optimization

- ✅ Async helper for friendly label lookups: `async_get_friendly_label()`
- ✅ Reduced code duplication by 40+ lines in services.py and coordinator.py
- ✅ Simplified entity lookup patterns (single function + wrappers vs. 6 individual implementations)

### Backward Compatibility

- ✅ All changes maintain schema v42+ (no migration required)
- ✅ All changes backward compatible with existing installations
- ✅ No API changes to public helper functions

---

**Document Version**: 1.6 (Updated for v0.5.0 release)
**Last Updated**: January 4, 2026
**Integration Version**: 0.5.0+
**Quality Level**: Silver (Unofficially Meets Standards)
**Storage Schema**: v42+
