# KidsChores v0.4.0 Release Notes

## Breaking Changes

### Entity Registry Cleanup Required

**This release includes a complete storage refactoring and entity naming standardization.** As a result:

⚠️ **All manually customized entity names will be reset to defaults**

When upgrading from any previous version to v0.4.0, the integration will perform a one-time cleanup of all entity registry entries to ensure a clean migration to the new storage schema.

### What This Means for Users

- **Entity names**: Any custom entity names you've set will revert to the new standardized names
- **Entity IDs**: All entity IDs will be regenerated using the new naming conventions
- **Dashboards**: You may need to update dashboard references to match new entity IDs
- **Automations/Scripts**: Update any automations or scripts that reference old entity IDs

### Why This Was Necessary

The legacy storage system did not properly track entity metadata, making migrations difficult. The new storage schema (v42) provides:

- Consistent entity ID patterns across all entity types
- Proper unique ID tracking for reliable entity registry management
- Foundation for future entity ID improvements without breaking changes

## Entity Naming Standardization

Entity IDs have been standardized for consistency:

### Kid Sensors

- `sensor.kc_{kid}_highest_badge` → `sensor.kc_{kid}_badges`
- `sensor.kc_{kid}_highest_streak` → `sensor.kc_{kid}_chores_highest_streak`
- `sensor.kc_{kid}_chores` ← **New** (main chores sensor)
- `sensor.kc_{kid}_points` ← Unchanged
- `sensor.kc_{kid}_points_max_ever` ← Unchanged

### Chore Completion Sensors

All use consistent `_chores_completed_*` pattern:

- `sensor.kc_{kid}_chores_completed_total`
- `sensor.kc_{kid}_chores_completed_daily`
- `sensor.kc_{kid}_chores_completed_weekly`
- `sensor.kc_{kid}_chores_completed_monthly`

### Points Earned Sensors

All use consistent `_points_earned_*` pattern:

- `sensor.kc_{kid}_points_earned_daily`
- `sensor.kc_{kid}_points_earned_weekly`
- `sensor.kc_{kid}_points_earned_monthly`

### Constant Naming Cleanup

Internal code cleanup fixed inconsistent constant naming:

- All entity ID suffix constants now correctly named `SENSOR_KC_EID_SUFFIX_*` (previously some were incorrectly named `MIDFIX`)
- Suffix = ends the entity ID (e.g., `_badges`)
- Midfix = appears in middle with additional content after (e.g., `_chore_status_{chore_name}`)

## Migration Path

### Before Upgrading

1. **Document your customizations**: Note any custom entity names you've set
2. **Export dashboards**: Save copies of dashboards that reference entities
3. **Review automations**: List automations/scripts using KidsChores entities

### After Upgrading

1. **Verify entities**: Check that all entities appear with new naming
2. **Update dashboards**: Replace old entity IDs with new standardized names
3. **Test automations**: Ensure automations work with new entity IDs
4. **Recustomize names**: Re-apply custom entity names if desired (now they'll persist correctly!)

### Old Entity Cleanup

The integration will automatically remove legacy entities during migration. If you see any unavailable entities after upgrade:

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Search for unavailable `sensor.kc_*` entities
3. Delete them manually (they're orphaned from the old storage system)

## Going Forward

### Entity ID Stability

Starting with v0.4.0:

- **Unique IDs are stable**: Won't change in future versions
- **Entity IDs may evolve**: We can improve naming without breaking your customizations
- **Customizations persist**: Entity names you set will survive future upgrades

This one-time breaking change establishes a solid foundation for future development without requiring disruptive migrations.

## New Features in v0.4.0

- Complete storage refactoring (schema v42)
- New `sensor.kc_{kid}_chores` main chore sensor with comprehensive attributes
- Standardized entity naming conventions across all platforms
- Improved code quality with consistent constant naming
- Foundation for future enhancements without breaking changes

## Technical Details

### Storage Schema v42

The new storage schema includes:

- Proper entity metadata tracking
- Consistent internal_id usage across all entity types
- Improved data structure for chore/badge/reward tracking
- Migration logic from all legacy versions

### Code Quality Improvements

- 149 passing tests (95%+ coverage)
- Fixed all MIDFIX→SUFFIX naming inconsistencies
- Standardized entity ID construction patterns
- Comprehensive constant naming documentation

---

**Questions or Issues?**

- GitHub Issues: https://github.com/ad-ha/kidschores-ha/issues
- Documentation: https://github.com/ad-ha/kidschores-ha/blob/main/README.md
