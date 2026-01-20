# KidsChores Integration Architecture

**Integration Version**: 0.5.0+
**Storage Schema Version**: 42 (Storage-Only Mode with Meta Section)
**Quality Scale Level**: ⭐ **Silver** (Unofficially Meets Standards)
**Date**: January 2026

---

## 🎯 Silver Quality Standards

This integration unofficially meets **Home Assistant Silver** quality level requirements. See [quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml) for current rule status and [AGENTS.md](../../core/AGENTS.md) and [Home Assistant's Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index/) for ongoing Home Assistant quality standards.

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

---

## Data Architecture

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

#### Reload Performance Comparison

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

### System Settings (config_entry.options)

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

#### Settings Update Flow

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

### Data (Storage)

#### Storage Location

**File**: `.storage/kidschores_data`
**Format**: JSON
**Version**: `STORAGE_VERSION = 1` (Home Assistant Store format), `meta.schema_version = 42` (KidsChores data structure)

#### Storage Structure

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
        "challenges": {...}
    }
}
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

## Type System Architecture

**File**: [type_defs.py](../custom_components/kidschores/type_defs.py)

KidsChores uses a **hybrid type approach** balancing type safety with practical code patterns:

### TypedDict for Static Structures

Used for entities and configurations with fixed keys known at design time:

```python
class ParentData(TypedDict):
    """Fixed structure - all keys known."""
    internal_id: str
    name: str
    ha_user_id: str
    associated_kids: list[str]
    enable_notifications: bool
    # ...

class ChoreData(TypedDict):
    """Entity definition with fixed schema."""
    internal_id: str
    name: str
    state: str
    default_points: float
    # ...
```

**Benefits**:

- ✅ Full IDE autocomplete
- ✅ Mypy catches missing/wrong fields
- ✅ Self-documenting structure

### dict[str, Any] for Dynamic Structures

Used for runtime-constructed data accessed with variable keys:

```python
# Type alias with documentation
KidChoreDataEntry = dict[str, Any]
"""Per-chore tracking data accessed dynamically.

Common runtime pattern:
    chore_entry[field_name] = value  # field_name is a variable
"""

KidChoreStats = dict[str, Any]
"""Aggregated stats accessed with dynamic period keys.

Common runtime pattern:
    stats_data[period_key][stat_type] = count  # both are variables
"""
```

**Benefits**:

- ✅ Honest about actual code behavior
- ✅ Minimal type suppressions (1 in dynamic code vs 150+ if forcing TypedDict)
- ✅ Mypy focuses on real issues

**Note**: Variable-based key access (`entry[field_name]`) is efficient, idiomatic Python. Type suppressions are IDE-level hints only—they don't affect runtime performance or indicate code quality issues.

### Why Hybrid Approach?

**TypedDict requires literal string keys** but KidsChores uses variable-based key access in ~30 locations:

```python
# Variable key access patterns (incompatible with TypedDict):
field_name = "last_approved" if approved else "last_claimed"
kid_chores_data[chore_id][field_name] = kid_name  # field_name is variable

for period_key in ["daily", "weekly", "monthly"]:
    periods_data[period_key][date_str] = stats  # period_key is variable
```

**Solution**: Match type system to actual code patterns. Use TypedDict where keys are static, dict[str, Any] where keys are dynamic. This achieves zero mypy errors without type suppressions.

### Type Safety Guidelines

| Structure Type      | Use TypedDict When             | Use dict[str, Any] When       |
| ------------------- | ------------------------------ | ----------------------------- |
| Entity definitions  | ✅ Keys are fixed in code      | ❌ Keys determined at runtime |
| Config objects      | ✅ Schema is static            | ❌ Schema varies by context   |
| Aggregations        | ❌ (period/stat keys vary)     | ✅ Keys built dynamically     |
| Per-entity tracking | ❌ (field names are variables) | ✅ Accessed with variables    |

See [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md#type-system) for implementation details and [type_defs.py](../custom_components/kidschores/type_defs.py) header for full rationale.

---

## Versioning Architecture

KidsChores uses a **dual versioning system**:

### 1. Home Assistant Store Version (File Format)

```json
{
    "version": 1,          // HA Store format version (always 1)
    "minor_version": 1,    // HA Store minor version
    "key": "kidschores_data",
    "data": { ... }        // KidsChores data with schema_version
}
```

### 2. KidsChores Schema Version (Data Structure)

The **`meta.schema_version`** field in storage data determines the integration's operational mode. Schema 42 is the current version:

| Schema Version | Mode                  | Behavior                                                        |
| -------------- | --------------------- | --------------------------------------------------------------- |
| < 42           | Legacy (Pre-0.5.0)    | Reads entity data from `config_entry.options` or legacy storage |
| ≥ 42           | Storage-Only (0.5.0+) | Reads entity data exclusively from storage with meta section    |

**Key Files**:

- `custom_components/kidschores/const.py`: `SCHEMA_VERSION_STORAGE_ONLY = 42`
- `custom_components/kidschores/coordinator.py`: Lines 851-856 (version check)
- `custom_components/kidschores/__init__.py`: Lines 45-51 (migration detection)

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

---

## Schedule Engine Architecture

### Unified Scheduling: Hybrid rrule + relativedelta Approach

The `schedule_engine.py` module provides a unified scheduling system for chores, badges, and challenges:

- **rrule (RFC 5545)**: Standard patterns (DAILY, WEEKLY, BIWEEKLY, MONTHLY, YEARLY) generate RFC 5545 RRULE strings for iCal export
- **relativedelta**: Period-end clamping (Jan 31 + 1 month = Feb 28) and DST-aware calculations
- **Why both?** rrule lacks month-end semantics; relativedelta lacks iCal compliance

### RecurrenceEngine Class

**Location**: `custom_components/kidschores/schedule_engine.py`

**Key Methods**:

- `get_occurrences(start, end, limit=100)` → list[datetime]: Calculate recurrence instances in time window
- `to_rrule_string()` → str: Generate RFC 5545 RRULE for iCal export
- `add_interval()` → datetime: DST-safe interval arithmetic
- `snap_to_weekday()` → datetime: Advance to next applicable weekday

**Data Flow**: coordinator → RecurrenceEngine.get_occurrences() → calendar events (with RRULE) → kc_helpers adapters → chore/badge logic

### iCal Compatibility

Calendar events for timed recurring chores now include RFC 5545 RRULE strings, enabling Google Calendar API sync, CalDAV support, Outlook sync, and third-party calendar viewers (future phases). Full-day/multi-day events omit RRULE to preserve correct iCal semantics.

### Edge Case Handling

Covers 9 scenarios (EC-01 through EC-09): monthly clamping, leap year handling, year boundary crossing, applicable_days constraints, period-end calculations, DST transitions, midnight boundaries, custom base dates, and iteration safety limits.

---

## Translation Architecture

KidsChores utilizes a multi-tiered translation architecture to manage standard Home Assistant (HA) integration strings alongside specialized custom notifications and dashboard elements.

To support this localization, we use a professional workflow through Crowdin, supported by a granted **Open Source License**. This license enables ongoing collaboration by allowing the team to share direct links with contributors, who can then suggest improvements or provide new translations for the integration. These community-driven updates are then automatically synchronized back into the repository via our automated translation workflow.

### 1. Dual Translation Systems

The integration maintains two distinct systems to balance core HA requirements with specialized functional needs.

#### Standard Integration Translations

- **Location**: `custom_components/kidschores/translations/en.json`.
- **Scope**: Governs exception messages, config flow UI, entity names/states, and service descriptions.
- **Implementation**: Utilizes the standard Home Assistant translation system via `hass.localize()` and `translation_key` attributes.
- **Coordinator Notifications**: The Coordinator uses the `async_get_translations()` API to manage 36 dynamic notification keys for chore approvals, reward redemptions, and system reminders.

#### Custom Managed Translations (Notifications & Dashboard)

These systems handle content requiring specific per-kid customization or frontend-accessible strings.

- **Notification System**: Managed via `translations_custom/en_notifications.json` for chore, reward, and challenge updates.
- **Dashboard System**: Managed via `translations_custom/en_dashboard.json` for the Kid Dashboard UI.

### 2. Dashboard Translation Sensor Architecture

The dashboard translation system uses **system-level translation sensors** to efficiently serve localized UI strings to the dashboard frontend.

#### System-Level Translation Sensors

- **Entity Pattern**: `sensor.kc_ui_dashboard_lang_{code}` (e.g., `sensor.kc_ui_dashboard_lang_en`, `sensor.kc_ui_dashboard_lang_es`)
- **One Sensor Per Language**: Created dynamically based on languages used by kids and parents
- **Attributes**: Exposes `ui_translations` dict with 40+ localized UI strings, plus `language` and `purpose` metadata
- **Size**: Each translation sensor is ~5-6KB (well under HA's 16KB attribute limit)

#### Dashboard Helper Pointer Pattern

- **Dashboard Helper Attribute**: Each kid's `sensor.kc_<kid>_ui_dashboard_helper` includes a `translation_sensor` attribute
- **Indirection**: Dashboard helper returns a pointer (e.g., `"sensor.kc_ui_dashboard_lang_en"`) instead of embedding translations
- **Lookup Pattern**: Dashboard YAML fetches translations via `state_attr(translation_sensor, 'ui_translations')`
- **Size Benefit**: Reduces dashboard helper size by ~4.7KB (99% reduction in translation overhead)

#### Lifecycle Management

- **Dynamic Creation**: Translation sensors are created on-demand when a kid or parent selects a new language
- **Automatic Cleanup**: When the last user of a language is deleted, the corresponding translation sensor is removed
- **Coordinator Tracking**: `coordinator._translation_sensors_created` tracks which language sensors exist
- **Callback Pattern**: `sensor.py` registers `async_add_entities` callback for dynamic sensor creation

### 3. Crowdin Management Strategy

All translation files follow a unified, automated synchronization workflow.

- **Master English Files**: Only English master files are maintained and edited directly in the repository.
- **Automated Sync**: A GitHub Action triggers on pushes to the `l10n-staging` branch to upload English sources and download non-English translations from Crowdin.
- **Read-Only Localizations**: All non-English files are considered read-only artifacts sourced exclusively from the Crowdin project.

### 4. Language Selection Architecture

The architecture provides per-kid and per-parent dashboard language selection using standard Home Assistant infrastructure.

- **Dynamic Detection**: The system scans the `translations_custom/` directory, extracting language codes from filenames (e.g., `es_dashboard.json` → `es`).
- **Validation**: Detected codes are filtered against the Home Assistant `LANGUAGES` set to ensure they are valid.
- **Native UI Selection**: The `LanguageSelector` component is used with `native_name=True`, allowing the frontend to automatically display native language names like "Español".
- **Translation Sensor Loading**: When a language is selected, the system calls `coordinator.ensure_translation_sensor_exists()` to create the sensor if needed.
- **Fallback Handling**: Missing translation files fall back to English; missing keys show `err-*` prefixed strings for debugging.

---

## Config and Options Flow Architecture

The KidsChores integration utilizes a **Direct-to-Storage** architecture that decouples user-defined entities from the Home Assistant configuration entry. This design allows for unlimited entity scaling and optimized system performance.

### Core Design Elements

- **Unified Logic via `flow_helpers.py**`: Both Config and Options flows leverage a shared utility layer to provide consistent validation and schema building. This centralization simplifies ongoing maintenance and ensures a uniform user experience across setup and configuration.
- **Direct Storage Writing**: User input is written directly to persistent storage at `.storage/kidschores_data` using **Schema 42**. This approach treats storage as the immediate source of truth, bypassing intermediate configuration entry merging.
- **Lightweight System Settings**: The `config_entry.options` object is reserved exclusively for nine system-level settings, such as `points_label` and `update_interval`. This keeps the core configuration entry lightweight and easy to validate.

### Operational Workflows

#### Config Flow (Initial Setup)

The configuration process follows a streamlined four-step path:

1. **Introduction**: A welcome screen providing integration context.
2. **System Settings**: Configuration of global labels, icons, and polling intervals.
3. **Entity Setup**: Direct creation of kids, parents, chores, badges, rewards, and other entities.
4. **Summary**: A final review before the storage data is committed and the entry is created.

#### Options Flow (Management)

The Options Flow manages modifications without unnecessary system overhead:

- **Entity Management**: Operations for adding, editing, or deleting entities are performed directly against storage data. The Coordinator handles persistence via `_persist()` and notifies active entities through `async_update_listeners()`, eliminating the need for a full integration reload.
- **System Settings Update**: When the nine core system settings are modified, the flow updates the configuration entry via `self.hass.config_entries.async_update_entry()`. This action triggers a standard Home Assistant integration reload to apply global changes.

### Key Benefits

- **Scalability**: Eliminates the size constraints inherent in Home Assistant configuration entries, allowing for an unlimited number of kids and chores.
- **Efficiency**: Provides significantly faster integration reloads (approximately 8x faster) because the system only needs to process a handful of settings rather than the entire entity database.
- **Data Integrity**: Simplifies the codebase by removing complex merging and reconciliation logic, allowing the config flow to focus solely on clean data collection and storage.

---

## Backward Compatibility

The integration maintains backward compatibility for legacy installations:

- **Legacy Support**: Migration system handles v30, v31, v40beta1, v41 → v42 upgrades automatically
- **Dual Version Detection**: Code reads from both `meta.schema_version` (v42+) and top-level `schema_version` (legacy)
- **Safety Net**: If storage is corrupted or deleted, clean install creates v42 meta section
- **Migration Testing**: Comprehensive test suite validates all migration paths (see MIGRATION_TESTING_PLAN.md)

---

## Shadow Kid Linking

The `kidschores.manage_shadow_link` service provides programmatic control over shadow kid relationships, enabling data-preserving workflows for existing kid profiles.

### Core Concept

**Shadow Kids** are special kid entities created when a parent enables `allow_chore_assignment`. They share the parent's name and serve as a chore assignment target while preserving separate point tracking. The linking service allows converting existing regular kids into shadow kids without losing data.

### Service Operations

**Link Operation** (`action: link`):

- Requires exact name match between existing parent and kid (case-insensitive)
- Validates neither entity is already in a shadow relationship
- Converts kid to shadow profile: sets `is_shadow_kid: true`, `linked_parent_id`, updates parent's `linked_shadow_kid_id`
- Preserves all kid data: points, history, chores, badges, achievements
- Inherits parent's workflow/gamification settings

**Unlink Operation** (`action: unlink`):

- Removes shadow relationship markers from both entities
- Renames kid with `_unlinked` suffix to prevent name conflicts
- Preserves all kid data as regular kid profile
- Updates device registry immediately (no reload required)
- Parent's `allow_chore_assignment` remains enabled but `linked_shadow_kid_id` cleared

### Notification Behavior

Shadow kids are created with `enable_notifications: false` by default to avoid duplicate notifications (parent receives supervised chore notifications). This setting is configurable via "Manage Kids" options flow to enable features like 30-minute due date reminders or separate notification services.

### Usage Pattern

```yaml
# Convert existing kid "Sarah" to shadow kid for parent "Sarah"
service: kidschores.manage_shadow_link
data:
  name: "Sarah"
  action: "link"

# Unlink shadow kid (creates regular kid "Sarah_unlinked")
service: kidschores.manage_shadow_link
data:
  name: "Sarah"
  action: "unlink"
```

**Implementation**: `services.py` lines 1169-1309, `coordinator.py` lines 1238-1310

---
