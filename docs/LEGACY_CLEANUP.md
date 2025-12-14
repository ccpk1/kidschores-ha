# KidsChores Legacy Code Cleanup Tracking

**Target Version**: KC 5.0 (12+ months post KC 4.0 release)
**Prerequisite**: <1% of users on schema_version < 41
**Date**: December 2024

---

## Overview

This document tracks legacy code, constants, and methods that support KC 3.x → KC 4.0 migration. These items are marked for removal in **KC 5.0** after sufficient adoption time (6-12 months).

**Current Status**: All legacy code is functional and necessary for backward compatibility. Do not remove until adoption metrics confirm <1% of users remain on KC 3.x.

---

## Coordinator Methods (coordinator.py)

### Legacy Initialization Methods - Lines 951-1124 (~174 lines)

**Purpose**: Merge entity data from `config_entry.options` into storage (KC 3.x compatibility)

**Removal Criteria**:

- ✅ All users upgraded to schema_version ≥ 41
- ✅ Telemetry shows zero calls to these methods for 6+ months
- ✅ KC 4.x stable for 2+ release cycles

| Method                           | Lines     | Purpose                                            | Removal Version |
| -------------------------------- | --------- | -------------------------------------------------- | --------------- |
| `_initialize_data_from_config()` | 951-986   | Main entry point for config sync                   | KC 5.0          |
| `_ensure_minimal_structure()`    | 988-1004  | Creates empty data sections                        | KC 5.0          |
| `_initialize_kids()`             | 1012-1014 | Sync kids from config                              | KC 5.0          |
| `_initialize_parents()`          | 1016-1018 | Sync parents from config                           | KC 5.0          |
| `_initialize_chores()`           | 1020-1022 | Sync chores from config                            | KC 5.0          |
| `_initialize_badges()`           | 1024-1026 | Sync badges from config                            | KC 5.0          |
| `_initialize_rewards()`          | 1028-1030 | Sync rewards from config                           | KC 5.0          |
| `_initialize_penalties()`        | 1032-1034 | Sync penalties from config                         | KC 5.0          |
| `_initialize_achievements()`     | 1037-1043 | Sync achievements from config                      | KC 5.0          |
| `_initialize_bonuses()`          | 1045-1051 | Sync bonuses from config                           | KC 5.0          |
| `_initialize_challenges()`       | 1053-1059 | Sync challenges from config                        | KC 5.0          |
| `_sync_entities()`               | 1065-1124 | Merges config → storage, removes orphaned entities | KC 5.0          |

**Impact of Removal**: ~174 lines removed, eliminates config_entry.options reads

**Code Location**:

```python
# coordinator.py, lines 951-1124
def _initialize_data_from_config(self):
    """LEGACY: Initialize data structures from config_entry.options (KC 3.x compatibility)."""
    # ... 174 lines ...
```

**Replacement**: After removal, coordinator will only load from storage:

```python
# coordinator.py, lines 914-929 (simplified in KC 5.0)
storage_data = self.storage_manager.get_data()
self._data = storage_data  # Direct assignment, no config sync
```

---

## Constants (const.py)

### Migration Infrastructure Constants

**Purpose**: Track migration status and version numbers

| Constant                       | Line | Purpose                                    | Removal Version |
| ------------------------------ | ---- | ------------------------------------------ | --------------- |
| `MIGRATION_PERFORMED`          | 56   | Flag indicating migration completed        | KC 5.0          |
| `MIGRATION_KEY_VERSION`        | 57   | Key for version number in storage          | KC 5.0          |
| `MIGRATION_KEY_VERSION_NUMBER` | 58   | Target version (41) for migration          | KC 5.0          |
| `MIGRATION_DATA_LEGACY_ORPHAN` | 66   | Marker for orphaned legacy data            | KC 5.0          |
| `SCHEMA_VERSION_STORAGE_ONLY`  | 63   | **KEEP** - Threshold for storage-only mode | Permanent       |

**Note**: `SCHEMA_VERSION_STORAGE_ONLY = 41` should be **kept permanently** as it defines the storage-only architecture threshold.

### Legacy Kid Data Keys - Lines 568-630

**Purpose**: Old field names from KC 3.x data structure

| Constant                                   | Line | New Equivalent           | Removal Version |
| ------------------------------------------ | ---- | ------------------------ | --------------- |
| `DATA_KID_BADGES_LEGACY`                   | 568  | `DATA_KID_BADGES_EARNED` | KC 5.0          |
| `DATA_KID_CHORE_APPROVALS_LEGACY`          | 622  | Runtime-only, not stored | KC 5.0          |
| `DATA_KID_CHORE_CLAIMS_LEGACY`             | 623  | Runtime-only, not stored | KC 5.0          |
| `DATA_KID_CHORE_STREAKS_LEGACY`            | 624  | Runtime-only, not stored | KC 5.0          |
| `DATA_KID_COMPLETED_CHORES_MONTHLY_LEGACY` | 626  | `DATA_KID_STATS_MONTHLY` | KC 5.0          |
| `DATA_KID_COMPLETED_CHORES_TOTAL_LEGACY`   | 627  | `DATA_KID_STATS_TOTAL`   | KC 5.0          |
| `DATA_KID_COMPLETED_CHORES_TODAY_LEGACY`   | 628  | `DATA_KID_STATS_DAILY`   | KC 5.0          |
| `DATA_KID_COMPLETED_CHORES_WEEKLY_LEGACY`  | 629  | `DATA_KID_STATS_WEEKLY`  | KC 5.0          |
| `DATA_KID_COMPLETED_CHORES_YEARLY_LEGACY`  | 630  | `DATA_KID_STATS_YEARLY`  | KC 5.0          |
| `DATA_KID_POINTS_EARNED_MONTHLY_LEGACY`    | 781  | `DATA_KID_STATS_MONTHLY` | KC 5.0          |
| `DATA_KID_POINTS_EARNED_TODAY_LEGACY`      | 782  | `DATA_KID_STATS_DAILY`   | KC 5.0          |
| `DATA_KID_POINTS_EARNED_WEEKLY_LEGACY`     | 783  | `DATA_KID_STATS_WEEKLY`  | KC 5.0          |
| `DATA_KID_POINTS_EARNED_YEARLY_LEGACY`     | 784  | `DATA_KID_STATS_YEARLY`  | KC 5.0          |

**Usage**: Only referenced in migration code and `_sync_entities()` method

### Legacy Badge Data Keys - Lines 965-993

**Purpose**: Old badge field names and structures

| Constant                                          | Line | Migration Context              | Removal Version |
| ------------------------------------------------- | ---- | ------------------------------ | --------------- |
| `DATA_BADGE_THRESHOLD_TYPE_LEGACY`                | 965  | Badge system refactor (KC 4.0) | KC 5.0          |
| `DATA_BADGE_THRESHOLD_VALUE_LEGACY`               | 966  | Badge system refactor (KC 4.0) | KC 5.0          |
| `DATA_BADGE_CHORE_COUNT_TYPE_LEGACY`              | 967  | Badge system refactor (KC 4.0) | KC 5.0          |
| `DATA_BADGE_POINTS_MULTIPLIER_LEGACY`             | 968  | Badge system refactor (KC 4.0) | KC 5.0          |
| `DATA_BADGE_REQUIRED_CHORES_LEGACY`               | 972  | Badge chore tracking change    | KC 5.0          |
| `DATA_BADGE_SPECIAL_OCCASION_LAST_AWARDED_LEGACY` | 993  | Special badge tracking change  | KC 5.0          |

**Usage**: Referenced in badge migration logic and data structure conversion

### Badge Award Mode Legacy

**Purpose**: Old badge award configuration (no longer used)

| Constant                       | Line | Removal Version |
| ------------------------------ | ---- | --------------- |
| `CONF_BADGE_AWARD_NONE_LEGACY` | 447  | KC 5.0          |

---

## Migration Function (**init**.py)

### One-Time Migration Function - Lines 25-237

**Purpose**: Move entity data from `config_entry.options` → storage on KC 3.x → 4.x upgrade

| Function                       | Lines  | Purpose                           | Removal Version  |
| ------------------------------ | ------ | --------------------------------- | ---------------- |
| `_migrate_config_to_storage()` | 25-237 | Complete migration implementation | **KEEP FOREVER** |

**Important**: This function must be **kept permanently** because:

- New users could restore old config entries (backups, imports)
- Migration is idempotent (safe to run multiple times)
- Only adds ~213 lines to codebase
- Critical for upgrade path support

**Do NOT Remove**: Even in KC 5.0, this migration function should remain to handle edge cases.

---

## Deprecation Strategy

### Phase 1: KC 4.0 (Current)

- ✅ All legacy code functional and tested
- ✅ Documentation clearly marks legacy methods
- ✅ No user-visible deprecation warnings

### Phase 2: KC 4.5 (6 months post-4.0)

- ⚠️ Add logged warnings when legacy methods execute
- ⚠️ Add integration repair issue for users on schema < 41
- ⚠️ Documentation encourages KC 4.x adoption

**Example Warning**:

```python
# coordinator.py
if storage_schema_version < const.SCHEMA_VERSION_STORAGE_ONLY:
    const.LOGGER.warning(
        "Legacy configuration detected (schema version %s < %s). "
        "Please update via integration options to ensure future compatibility. "
        "Legacy support will be removed in KC 5.0.",
        storage_schema_version,
        const.SCHEMA_VERSION_STORAGE_ONLY
    )
    self._initialize_data_from_config()
```

### Phase 3: KC 5.0 (12+ months post-4.0)

- ❌ Remove all methods listed in this document
- ❌ Remove all `*_LEGACY` constants
- ❌ Remove `MIGRATION_*` constants (except `SCHEMA_VERSION_STORAGE_ONLY`)
- ❌ Require `schema_version >= 41` for all installations
- ❌ **Breaking Change**: Users must upgrade to KC 4.x before KC 5.0

**Upgrade Path**: KC 3.x → KC 4.x → KC 5.0 (no direct KC 3.x → 5.0 path)

---

## Removal Checklist (For KC 5.0 Release)

### Code Removal

- [ ] Delete `coordinator.py` lines 951-1124 (12 methods, ~174 lines)
- [ ] Simplify `coordinator.py` lines 914-929 (remove version check, direct storage load)
- [ ] Delete `const.py` migration constants (lines 55-58, 56-58, 66)
- [ ] Delete `const.py` legacy kid keys (lines 568-630, 622-630, 781-784)
- [ ] Delete `const.py` legacy badge keys (lines 965-993)
- [ ] Delete `const.py` badge award mode legacy (line 447)

### Testing Updates

- [ ] Remove legacy mode tests (if any)
- [ ] Remove migration backward compatibility tests
- [ ] Update all fixtures to use `schema_version: 41`
- [ ] Add test to verify schema < 41 raises clear error

### Documentation Updates

- [ ] Update README.md to remove KC 3.x references
- [ ] Update ARCHITECTURE.md to remove migration section
- [ ] Update CHANGELOG.md with breaking change notice
- [ ] Add upgrade guide: KC 4.x required before KC 5.0

### User Communication

- [ ] Release notes: Clearly state KC 4.x prerequisite
- [ ] Migration guide: Step-by-step KC 3.x → 4.x → 5.0
- [ ] Deprecation timeline: 6 months warning in KC 4.5

---

## Code Statistics

### Current Legacy Code Size

| Component                        | Lines | Percentage of File   |
| -------------------------------- | ----- | -------------------- |
| `coordinator.py` legacy methods  | 174   | 2.0% of 8,517 lines  |
| `const.py` legacy constants      | ~60   | 2.7% of 2,235 lines  |
| `__init__.py` migration function | 213   | **KEEP** (permanent) |

**Total Removable**: ~234 lines (~0.5% of integration codebase)

### Post-Removal Codebase

| File             | Current Lines | Post-KC 5.0 Lines | Reduction        |
| ---------------- | ------------- | ----------------- | ---------------- |
| `coordinator.py` | 8,517         | ~8,343            | -174 (-2.0%)     |
| `const.py`       | 2,235         | ~2,175            | -60 (-2.7%)      |
| **Total**        | **~11,000**   | **~10,766**       | **-234 (-2.1%)** |

---

## Monitoring & Metrics

### Required Telemetry (To Be Implemented)

Track these metrics to determine removal readiness:

```python
# Add to coordinator initialization
if storage_schema_version < const.SCHEMA_VERSION_STORAGE_ONLY:
    # Log telemetry event
    analytics.track_event("legacy_mode_active", {
        "schema_version": storage_schema_version,
        "integration_version": VERSION
    })
```

### Removal Criteria

| Metric                | Target  | Current | Status               |
| --------------------- | ------- | ------- | -------------------- |
| Users on schema < 41  | <1%     | TBD     | ⏳ Monitoring needed |
| Months since KC 4.0   | ≥12     | 0       | ⏳ Just released     |
| Stable release cycles | ≥2      | 0       | ⏳ Just released     |
| Legacy method calls   | 0/month | TBD     | ⏳ Monitoring needed |

**Decision Point**: Review these metrics before starting KC 5.0 development

---

## Risk Assessment

### Risks of Early Removal

| Risk                      | Impact | Mitigation                                               |
| ------------------------- | ------ | -------------------------------------------------------- |
| Users stuck on KC 3.x     | High   | Wait 12+ months, provide clear upgrade path              |
| Backup restoration breaks | Medium | Keep migration function, remove only coordinator methods |
| Support burden            | Low    | Clear error messages, upgrade documentation              |

### Risks of Keeping Forever

| Risk                         | Impact | Mitigation                                          |
| ---------------------------- | ------ | --------------------------------------------------- |
| Code maintenance burden      | Low    | Well-isolated, doesn't interfere with new features  |
| Confusion for new developers | Low    | Clear documentation, "LEGACY" markers               |
| Test complexity              | Low    | Legacy paths are well-tested, can skip in new tests |

**Recommendation**: Follow planned timeline - removal is beneficial but not urgent.

---

## Summary

- **Total Legacy Code**: ~234 lines (2.1% of codebase)
- **Target Removal**: KC 5.0 (12+ months post-KC 4.0)
- **Critical Prerequisite**: <1% of users on schema < 41
- **Breaking Change**: Yes - KC 3.x users must upgrade to KC 4.x first
- **Keep Forever**: `_migrate_config_to_storage()` function in `__init__.py`

**Next Steps**:

1. Monitor KC 4.0 adoption for 6 months
2. Add deprecation warnings in KC 4.5
3. Verify <1% legacy usage before KC 5.0
4. Execute removal checklist for KC 5.0 release

---

**Document Version**: 1.0
**Last Updated**: December 2024
**Review Date**: June 2025 (6 months post-KC 4.0)
