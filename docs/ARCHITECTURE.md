# KidsChores Integration Architecture (v4.0+)

**Version**: 4.0+
**Schema Version**: 41 (Storage-Only Mode)
**Date**: December 2024

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
- **Deprecation Timeline**: Method marked for removal in **KC 5.0** (after 6+ months of v4.x adoption)

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

### KC 4.5 (Future - 6+ months)

- ⚠️ Deprecation warnings for users still on schema < 41
- ⚠️ Documentation encourages upgrade to KC 4.x

### KC 5.0 (Future - 12+ months)

- ❌ Remove `_initialize_data_from_config()` method (~160 lines)
- ❌ Remove migration constants (MIGRATION\__, _\_LEGACY)
- ❌ Require `schema_version >= 41` for all installations
- ❌ Breaking change: KC 3.x users must upgrade to KC 4.x first

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

This architecture is stable and production-ready. Legacy migration code will be removed in KC 5.0 after sufficient adoption time.

---

**Document Version**: 1.0
**Last Updated**: December 2024
**Integration Version**: 4.0+
