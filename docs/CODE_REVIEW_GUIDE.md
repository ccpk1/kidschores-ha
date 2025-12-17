# KidsChores Code Review Guide

**Purpose**: Systematic code review checklist for maintaining quality, consistency, and performance across the KidsChores integration.

**Version**: 1.0
**Last Updated**: December 17, 2025
**Target**: KidsChores v4.0+ (Storage-Only Architecture)

---

## Table of Contents

1. [General Code Quality](#general-code-quality)
2. [Entity Review Checklist](#entity-review-checklist)
3. [Performance Review](#performance-review)
4. [Standards Compliance](#standards-compliance)
5. [Platform-Specific Reviews](#platform-specific-reviews)
6. [Review Process](#review-process)

---

## General Code Quality

### Documentation Standards

**✅ File-Level Docstrings**

```python
"""Platform for KidsChores sensor entities.

Provides 26 sensor types across 3 scopes:
- Kid Scope: Per-kid sensors (points, chores completed, badges)
- Parent Scope: Parent-specific sensors (N/A for sensors)
- System Scope: Global aggregation sensors (pending approvals)
"""
```

- [ ] Module docstring exists and describes purpose
- [ ] Module docstring lists key entity types/counts
- [ ] Module docstring mentions scope categories
- [ ] Copyright/license present if required

**✅ Class Docstrings**

```python
class KidPointsSensor(CoordinatorEntity, SensorEntity):
    """Sensor tracking a kid's current point balance.

    Updates whenever points change via:
    - Chore approvals (adds default_points)
    - Reward redemptions (subtracts cost)
    - Bonus applications (adds bonus_points)
    - Penalty applications (subtracts penalty_points)
    - Direct point adjustments (adds/subtracts adjustment)

    Attributes:
        native_value: Current point balance (float)
        state_class: measurement
        device_class: None
    """
```

- [ ] Class docstring explains entity purpose
- [ ] Class docstring documents when entity updates
- [ ] Class docstring lists key attributes
- [ ] Class docstring includes example if complex

**✅ Method Docstrings**

```python
def _handle_coordinator_update(self) -> None:
    """Handle updated data from coordinator.

    Recalculates point balance from:
    - Base points in kid data
    - Applied badge multipliers
    """
```

- [ ] All public methods have docstrings
- [ ] Docstring describes what method does
- [ ] Docstring documents parameters if not obvious
- [ ] Docstring documents return value if not obvious

### Code Comments

**✅ Inline Comments**

```python
# Calculate net points for today (chores - rewards - penalties + bonuses)
net_points = (
    chore_points
    - reward_points
    - penalty_points
    + bonus_points
)
```

- [ ] Comments explain "why" not "what"
- [ ] Comments describe complex logic
- [ ] No commented-out code
- [ ] No TODO/FIXME comments (create issues instead)

### Type Hints

**✅ Type Annotations**

```python
def _calculate_chore_attributes(
    self,
    chore_id: str,
    chore_info: dict[str, Any],
    kid_info: dict[str, Any],
    chore_eid: str | None,
) -> dict[str, Any]:
    """Calculate chore attributes for dashboard display."""
```

- [ ] All parameters have type hints
- [ ] Return type specified
- [ ] Properties have return type hints
- [ ] Use `str | None` not `Optional[str]` (Python 3.10+)
- [ ] Use `dict[str, Any]` not `Dict[str, Any]`

---

## Entity Review Checklist

### Naming Consistency

**✅ Entity Class Names**

- [ ] Follows `[Scope][EntityType][Property]` pattern
- [ ] Kid scope: `Kid*` (e.g., `KidPointsSensor`)
- [ ] Parent scope: `Parent*` (e.g., `ParentChoreApproveButton`)
- [ ] System scope: `System*` for legacy, `Kid*` for modern helpers

**✅ Unique ID Construction**

```python
self._attr_unique_id = (
    f"{self._entry.entry_id}_{self._kid_id}"
    f"{const.SENSOR_KC_UID_SUFFIX_POINTS}"
)
```

- [ ] Uses `entry_id` as prefix
- [ ] Includes scope-appropriate identifier (`kid_id`, `entry_id`)
- [ ] Uses constant suffix from `const.py`
- [ ] Unique across all platform instances

**✅ Entity ID Pattern**

```python
# Kid scope: kc_<kid_slug>_<purpose>
# System scope: kc_<purpose> or kc_all_<purpose>
```

- [ ] Entity ID automatically generated from name
- [ ] Name follows Home Assistant conventions
- [ ] `has_entity_name = True` set
- [ ] Device info attached correctly

### Entity Attributes

**✅ Required Attributes**

```python
_attr_has_entity_name = True
_attr_device_class = SensorDeviceClass.ENUM
_attr_state_class = SensorStateClass.MEASUREMENT
_attr_native_unit_of_measurement = "Points"
```

- [ ] `_attr_has_entity_name` always `True`
- [ ] Device class set if applicable
- [ ] State class set for numeric sensors
- [ ] Unit of measurement uses config option if applicable
- [ ] Icon uses config option or appropriate MDI icon

**✅ Translation Keys**

```python
_attr_translation_key = "kid_points"
# Corresponds to strings.json:
# "entity": { "sensor": { "kid_points": { "name": "Points" } } }
```

- [ ] Translation key set for all entities
- [ ] Corresponding entry exists in `strings.json`
- [ ] Translation follows naming pattern
- [ ] No hardcoded user-facing strings

### Entity Properties

**✅ Native Value**

```python
@property
def native_value(self) -> float:
    """Return current point balance."""
    kid_info = self.coordinator.kids_data.get(self._kid_id, {})
    return kid_info.get(const.DATA_KID_POINTS, 0.0)
```

- [ ] Returns appropriate type (float, int, str, datetime)
- [ ] Returns `None` for unknown values (not "unknown")
- [ ] No complex calculations (move to coordinator)
- [ ] Efficient data access (no loops if avoidable)

**✅ Extra State Attributes**

```python
@property
def extra_state_attributes(self) -> dict[str, Any]:
    """Return additional sensor attributes."""
    kid_info = self.coordinator.kids_data.get(self._kid_id, {})
    return {
        "lifetime_points": kid_info.get(const.DATA_KID_LIFETIME_POINTS, 0.0),
        "points_multiplier": kid_info.get(const.DATA_KID_POINTS_MULTIPLIER, 1.0),
        "max_points_ever": kid_info.get(const.DATA_KID_MAX_POINTS_EVER, 0.0),
    }
```

- [ ] All keys always present (use `None` for missing values)
- [ ] Attribute names descriptive and snake_case
- [ ] No redundant data (already in native_value)
- [ ] No heavy computation (pre-compute in coordinator)

### Device Registry

**✅ Device Info**

```python
_attr_device_info = DeviceInfo(
    identifiers={(const.DOMAIN, self._kid_id)},
    name=self._kid_name,
    entry_type=DeviceEntryType.SERVICE,
)
```

- [ ] Device identifiers use internal ID
- [ ] Device name uses human-readable name
- [ ] Entry type set appropriately
- [ ] Device shared across related entities

---

## Performance Review

### Coordinator Access Patterns

**✅ Efficient Data Access**

```python
# ✅ Good: Single coordinator access
kid_info = self.coordinator.kids_data.get(self._kid_id, {})
points = kid_info.get(const.DATA_KID_POINTS, 0.0)
name = kid_info.get(const.DATA_KID_NAME, "")

# ❌ Bad: Multiple coordinator accesses
points = self.coordinator.kids_data.get(self._kid_id, {}).get(const.DATA_KID_POINTS, 0.0)
name = self.coordinator.kids_data.get(self._kid_id, {}).get(const.DATA_KID_NAME, "")
```

- [ ] Minimize coordinator data access calls
- [ ] Cache coordinator data in local variable
- [ ] Use `.get()` with defaults for safety
- [ ] No nested dictionary traversals

**✅ Avoid Expensive Operations**

```python
# ❌ Bad: Expensive loop in property
@property
def native_value(self) -> int:
    count = 0
    for chore_id in self.coordinator.chores_data:
        if chore_id in self.coordinator.kids_data[kid_id]["claimed_chores"]:
            count += 1
    return count

# ✅ Good: Pre-computed in coordinator
@property
def native_value(self) -> int:
    kid_info = self.coordinator.kids_data.get(self._kid_id, {})
    return len(kid_info.get(const.DATA_KID_CLAIMED_CHORES, []))
```

- [ ] No loops in properties/native_value
- [ ] No complex calculations in properties
- [ ] Pre-compute aggregations in coordinator
- [ ] Cache expensive lookups

### Memory Efficiency

**✅ Attribute Size Management**

```python
# ❌ Bad: Large list in attributes
@property
def extra_state_attributes(self) -> dict[str, Any]:
    return {
        "all_chore_history": self._get_complete_history()  # 1000+ items
    }

# ✅ Good: Summarized/limited data
@property
def extra_state_attributes(self) -> dict[str, Any]:
    return {
        "recent_history": self._get_recent_history(limit=10)
    }
```

- [ ] Attributes contain reasonable data sizes
- [ ] Large lists paginated or limited
- [ ] Historical data summarized not raw
- [ ] Consider entity registry size limits

### Update Patterns

**✅ Coordinator Updates**

```python
def _handle_coordinator_update(self) -> None:
    """Handle updated data from the coordinator."""
    # Only do work if necessary
    if self._requires_update():
        self._update_internal_state()
    super()._handle_coordinator_update()
```

- [ ] Only updates when data changes
- [ ] Uses `CoordinatorEntity` base class
- [ ] `should_poll = False` when using coordinator
- [ ] No redundant state writes

---

## Standards Compliance

### Home Assistant Best Practices

**✅ Async Programming**

```python
# ✅ All I/O is async
async def async_press(self) -> None:
    """Handle button press."""
    await self.coordinator.async_claim_chore(self._kid_id, self._chore_id)

# ❌ No blocking calls
def _sync_operation(self):
    time.sleep(1)  # ❌ Blocks event loop
```

- [ ] All I/O operations are async
- [ ] No `time.sleep()` (use `asyncio.sleep()`)
- [ ] No blocking file operations
- [ ] Use `@callback` for event loop safe functions

**✅ Error Handling**

```python
try:
    data = await self.coordinator.fetch_data()
except ApiException as err:
    raise UpdateFailed(f"API error: {err}") from err
```

- [ ] Specific exceptions caught
- [ ] Errors logged appropriately
- [ ] User-facing errors use `ServiceValidationError`
- [ ] Coordinator errors use `UpdateFailed`

**✅ State Management**

```python
# ✅ Use None for unknown
@property
def native_value(self) -> float | None:
    kid_info = self.coordinator.kids_data.get(self._kid_id)
    if not kid_info:
        return None
    return kid_info.get(const.DATA_KID_POINTS, 0.0)

# ❌ Don't use "unknown" string
@property
def native_value(self) -> str:
    return "unknown"  # ❌ Bad
```

- [ ] Unknown values return `None`
- [ ] Availability via `available` property
- [ ] No "unknown" or "unavailable" strings

### Integration Quality Scale

**✅ Bronze Requirements (Mandatory)**

- [ ] Config flow implemented
- [ ] All entities have unique IDs
- [ ] Action setup (services) implemented
- [ ] Branding (name, icon) correct

**✅ Silver Requirements**

- [ ] Entity unavailability handled
- [ ] Parallel updates specified
- [ ] Reauthentication flow (N/A for local)

**✅ Gold Requirements**

- [ ] Device registry used
- [ ] Diagnostics implemented
- [ ] Entity/action translations

**✅ Platinum Requirements**

- [ ] Strict typing (all hints present)
- [ ] Async dependencies (no blocking libs)
- [ ] WebSession injection (N/A for local)

---

## Platform-Specific Reviews

### Sensor Platform (`sensor.py`)

**✅ Sensor-Specific Checks**

- [ ] State class appropriate (`measurement`, `total`, `total_increasing`)
- [ ] Device class set if applicable
- [ ] Unit of measurement correct
- [ ] Icon appropriate for state
- [ ] Options populated for enum sensors
- [ ] Last reset tracked for total sensors

**✅ Dashboard Helper Sensor**

```python
class KidDashboardHelperSensor(CoordinatorEntity, SensorEntity):
    """Aggregates all kid data for dashboard consumption."""
```

- [ ] All entity ID references use entity registry lookups
- [ ] Button entity IDs included for actions
- [ ] Lists pre-sorted by appropriate criteria
- [ ] Translations loaded from coordinator
- [ ] Change flags reset after attribute build

### Button Platform (`button.py`)

**✅ Button-Specific Checks**

```python
async def async_press(self) -> None:
    """Handle button press."""
    # Validate authorization
    if not await self._async_validate_authorization():
        raise ServiceValidationError("Unauthorized")

    # Execute action
    self.coordinator.apply_bonus(self._kid_id, self._bonus_id, self._user_id)
```

- [ ] Authorization checked before action
- [ ] User context available (`self._context`)
- [ ] Appropriate exceptions raised
- [ ] Coordinator method called (not direct state change)
- [ ] No return value (buttons don't return data)

### Select Platform (`select.py`)

**✅ Select-Specific Checks**

```python
@property
def options(self) -> list[str]:
    """Return list of available options."""
    return [chore["name"] for chore in self.coordinator.chores_data.values()]

async def async_select_option(self, option: str) -> None:
    """Handle option selection."""
    # No action needed - display only
```

- [ ] Options list always populated
- [ ] Options list kept current with coordinator
- [ ] Legacy selects wrapped with `show_legacy_entities` flag
- [ ] Modern selects always instantiated

### Calendar Platform (`calendar.py`)

**✅ Calendar-Specific Checks**

```python
async def async_get_events(
    self,
    hass: HomeAssistant,
    start_date: datetime,
    end_date: datetime,
) -> list[CalendarEvent]:
    """Return calendar events within date range."""
```

- [ ] Events generated from chore due dates
- [ ] Date range respected
- [ ] All-day events handled correctly
- [ ] Recurring chores processed

### Datetime Platform (`datetime.py`)

**✅ Datetime-Specific Checks**

```python
async def async_set_value(self, value: datetime) -> None:
    """Set new datetime value."""
    self.coordinator.set_chore_due_date(self._chore_id, value)
```

- [ ] Timezone handling correct
- [ ] Min/max values set appropriately
- [ ] Updates propagate to coordinator
- [ ] Date formatting consistent

---

## Review Process

### Step 1: Pre-Review Validation

**Run Automated Checks**

```bash
# Full lint check
./utils/quick_lint.sh --fix

# Full test suite
python -m pytest tests/ -v --tb=line

# Type checking (if enabled)
mypy custom_components/kidschores/
```

- [ ] All linting passes (9.5+/10)
- [ ] All tests pass (150+ tests)
- [ ] No type errors
- [ ] No trailing whitespace

### Step 2: File-by-File Review

**For Each Platform File:**

1. **Open file and scan structure**

   - [ ] File docstring complete
   - [ ] Imports organized (stdlib, third-party, local)
   - [ ] Constants defined at top
   - [ ] Helper functions before classes

2. **Review each entity class**

   - [ ] Use entity checklist above
   - [ ] Check all properties
   - [ ] Verify all attributes
   - [ ] Test method logic

3. **Check platform setup**
   - [ ] `async_setup_entry` correct
   - [ ] Entity instantiation matches patterns
   - [ ] Platform constants used correctly

### Step 3: Cross-File Validation

**Coordinator Integration**

- [ ] All entity data accessed through coordinator
- [ ] No direct storage manager access
- [ ] Coordinator methods called for state changes
- [ ] Update listeners registered correctly

**Constant Usage**

- [ ] All constants from `const.py`
- [ ] No magic strings
- [ ] Naming patterns followed
- [ ] No duplicate definitions

**Translation Coverage**

- [ ] All translation keys exist in `strings.json`
- [ ] All user-facing strings translated
- [ ] No hardcoded English text
- [ ] Error messages translatable

### Step 4: Performance Profiling

**Hot Path Identification**

```python
# Frequently called properties (check performance):
# - native_value (called every state change)
# - extra_state_attributes (called every state change)
# - _handle_coordinator_update (called every coordinator update)
```

- [ ] Profile hot paths with realistic data
- [ ] Measure coordinator update time
- [ ] Check entity state write frequency
- [ ] Identify optimization opportunities

**Memory Profiling**

- [ ] Check entity attribute sizes
- [ ] Monitor coordinator data growth
- [ ] Verify cleanup routines work
- [ ] Test with large datasets (50+ kids, 200+ chores)

### Step 5: Documentation Review

**Code Comments**

- [ ] All complex logic explained
- [ ] Edge cases documented
- [ ] Algorithm choices justified

**External Documentation**

- [ ] ARCHITECTURE.md accurate
- [ ] README.md up to date
- [ ] Breaking changes documented
- [ ] Migration guides provided

### Step 6: Standards Audit

**Naming Conventions**

- [ ] Entity names follow scope pattern
- [ ] Method names descriptive
- [ ] Variable names clear
- [ ] Constants appropriately named

**Code Organization**

- [ ] Related code grouped together
- [ ] Separation of concerns maintained
- [ ] DRY principle followed
- [ ] SOLID principles applied

---

## Review Checklist Summary

### Quick Reference

**Per Entity Review** (5-10 minutes per entity)

- [ ] Documentation complete
- [ ] Type hints present
- [ ] Naming consistent
- [ ] Performance acceptable
- [ ] Standards compliant
- [ ] Tests exist

**Per Platform Review** (30-45 minutes per platform)

- [ ] All entities reviewed
- [ ] Platform setup correct
- [ ] Integration tests pass
- [ ] Performance profiled
- [ ] Documentation updated

**Full Integration Review** (2-3 hours)

- [ ] All platforms reviewed
- [ ] Cross-file validation done
- [ ] Performance acceptable
- [ ] Standards audit complete
- [ ] Documentation current

---

## Common Issues & Fixes

### Issue: Slow Entity Updates

**Problem**: Entity state updates lag behind coordinator updates

**Check**:

- [ ] Entity inherits from `CoordinatorEntity`
- [ ] `should_poll = False` set
- [ ] No blocking operations in properties

**Fix**: Ensure proper coordinator integration

### Issue: Missing Translations

**Problem**: Entity names show as "entity not found" in UI

**Check**:

- [ ] `translation_key` set correctly
- [ ] Entry exists in `strings.json`
- [ ] Translation file format valid

**Fix**: Add missing translations

### Issue: Entity Not Appearing

**Problem**: Entity doesn't show up in entity registry

**Check**:

- [ ] `unique_id` set correctly
- [ ] Platform registered in `PLATFORMS`
- [ ] Entity added in `async_setup_entry`
- [ ] No exceptions during entity creation

**Fix**: Debug entity instantiation

### Issue: Performance Degradation

**Problem**: Integration slows down with many entities

**Check**:

- [ ] Properties don't have expensive calculations
- [ ] Coordinator data accessed efficiently
- [ ] No redundant entity updates
- [ ] Entity attribute sizes reasonable

**Fix**: Profile and optimize hot paths

---

## Tools & Resources

### Linting Tools

```bash
# Quick lint (comprehensive)
./utils/quick_lint.sh --fix

# Individual checks
pylint custom_components/kidschores/sensor.py
mypy custom_components/kidschores/sensor.py
```

### Testing Tools

```bash
# Run specific platform tests
pytest tests/test_sensor_values.py -v

# Run with coverage
pytest tests/ --cov=custom_components.kidschores --cov-report=term-missing

# Run specific test
pytest tests/test_sensor_values.py::test_kid_points_sensor_attributes -v
```

### Performance Tools

```python
# Profile coordinator updates
import cProfile
cProfile.run('coordinator.async_refresh()')

# Memory profiling
import tracemalloc
tracemalloc.start()
# ... run code ...
snapshot = tracemalloc.take_snapshot()
```

### Reference Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) - Integration architecture and patterns
- [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index/)
- [Home Assistant Entity Development](https://developers.home-assistant.io/docs/core/entity/)
- [TESTING_GUIDE.md](../tests/TESTING_GUIDE.md) - Testing patterns and troubleshooting

---

**Review Guide Version**: 1.0
**Last Updated**: December 17, 2025
**Maintainer**: KidsChores Development Team
