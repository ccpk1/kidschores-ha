# Chore Technical Reference Corrections Log

**Date**: January 2026
**Version**: v0.5.0+
**Document**: Chore-Technical-Reference.md

## Summary

The Chore Technical Reference contained significant inaccuracies that referenced hypothetical naming conventions rather than the actual implementation in sensor.py. All corrections have been verified against the codebase to ensure accuracy.

---

## Corrections Made

### 1. Points Sensor Attributes

**Issue**: Point statistic attributes were documented without the required prefix.

**Incorrect**:

```yaml
sensor.kc_<kid>_points
  attributes:
    points_today: 25
    points_this_week: 85
    points_this_month: 150
```

**Corrected**:

```yaml
sensor.kc_<kid>_points
  attributes:
    point_stat_points_earned_today: 25
    point_stat_points_earned_week: 85
    point_stat_points_earned_month: 150
```

**Source**: `/workspaces/kidschores-ha/custom_components/kidschores/sensor.py` lines 877-880

- All point stats are dynamically prefixed with `ATTR_PREFIX_POINT_STAT` (`"point_stat_"`)
- Defined in `const.py` line 1676

---

### 2. Non-Existent Chores Available Sensor

**Issue**: Documentation referenced `sensor.kc_<kid>_chores_available` which does not exist in sensor.py.

**Removed**: Entire `sensor.kc_<kid>_chores_available` entity reference

**Replaced With**: `sensor.kc_<kid>_ui_dashboard_helper`

**Rationale**:

- Dashboard Helper sensor provides pre-sorted chore lists (`chores` attribute with minimal fields)
- Optimized for dashboard template rendering
- Created in sensor.py line 2918 (class `KidDashboardHelperSensor`)
- Provides `chores` list with fields: `eid`, `name`, `status`, `labels`, `primary_group`, `is_today_am`

**Source**: `/workspaces/kidschores-ha/custom_components/kidschores/sensor.py` lines 2918-3200

---

### 3. Non-Existent Global Chore Stats Sensor

**Issue**: Documentation referenced `sensor.kc_global_chore_stats` which does not exist.

**Removed**: Entire `sensor.kc_global_chore_stats` entity reference

**Replaced With**: System Shared Chore Sensor (`sensor.kc_system_<chore>_shared_state`)

**Rationale**:

- KidsChores tracks SHARED chore global state via system-level sensors (one per SHARED chore)
- Created in sensor.py line 1554 (class `SystemChoreSharedStateSensor`)
- Provides global state across all kids for shared/shared_first chores

**Source**: `/workspaces/kidschores-ha/custom_components/kidschores/sensor.py` lines 1554-1734

---

### 4. Chore Sensor Attribute Names

**Issue**: Chore status sensor attributes used incorrect naming convention.

**Incorrect**:

```yaml
sensor.kc_<kid>_<chore>
  attributes:
    completion_mode: "independent"
    recurrence_pattern: "daily"
    reset_type: "at_due_date"
```

**Corrected**:

```yaml
sensor.kc_<kid>_<chore>
  attributes:
    completion_criteria: "independent"
    recurring_frequency: "daily"
    approval_reset_type: "at_due_date"
```

**Source**: `/workspaces/kidschores-ha/custom_components/kidschores/sensor.py` lines 634-640

- `ATTR_COMPLETION_CRITERIA` (line 634)
- `ATTR_APPROVAL_RESET_TYPE` (line 636)
- `ATTR_RECURRING_FREQUENCY` (line 638)

---

### 5. Button Entity State Clarification

**Issue**: Button state description implied stateful behavior beyond timestamp tracking.

**Added Note**:

> [!IMPORTANT] > **Button entities are stateless triggers** - They do not maintain persistent state beyond the last press timestamp (managed by Home Assistant core). Chore state is tracked by the chore sensor (`sensor.kc_<kid>_<chore>`), not the button entities.

**Rationale**:

- Home Assistant ButtonEntity is stateless by design (core platform behavior)
- `state` attribute shows last press timestamp, managed by HA core
- Chore state (pending/claimed/approved) is tracked by `KidChoreStatusSensor`, NOT button entities

---

## Template Updates

All Jinja2 templates and automation examples were updated to reflect correct:

1. **Attribute Names**: `point_stat_*` prefix for points statistics
2. **Sensor References**: `sensor.kc_<kid>_ui_dashboard_helper` instead of non-existent `chores_available`
3. **Chore Attributes**: `completion_criteria`, `recurring_frequency`, `approval_reset_type`
4. **Conditional Logic**: Access chore lists via dashboard helper `chores` attribute

---

## Verification Sources

All corrections verified against:

- **const.py** line 1676: `ATTR_PREFIX_POINT_STAT: Final = "point_stat_"`
- **sensor.py** lines 424-3889: All sensor class implementations
  - KidPointsSensor (lines 777-884)
  - KidChoreStatusSensor (lines 424-776)
  - KidDashboardHelperSensor (lines 2918-3889)
  - SystemChoreSharedStateSensor (lines 1554-1734)

---

## Impact

### Who This Affects

- **Automation Creators**: Templates using incorrect attribute names now return valid data
- **Dashboard Builders**: Correct sensor references prevent "entity not found" errors
- **Integration Developers**: Technical reference now matches actual implementation

### Breaking Changes (Documentation Only)

No code changes were made - these were documentation-only corrections. Users relying on the incorrect documentation will need to update:

1. Templates accessing point stats: Add `point_stat_` prefix
2. Dashboard templates: Replace `chores_available` with `ui_dashboard_helper`
3. Automations: Update attribute names in conditional logic

---

## Related Documentation

- [Configuration: Chores Guide](Configuration:-Chores-Guide.md)
- [Dashboard: Auto-Populating UI](Dashboard:-Auto-Populating-UI.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)

---

**Status**: ✅ Complete - All corrections verified against sensor.py implementation
