# KidsChores Code Review Guide

**Purpose**: Systematic code review checklist for maintaining quality, consistency, and performance across the KidsChores integration.

**Version**: 2.0
**Last Updated**: January 11, 2026
**Target**: KidsChores v0.5.0+ (Storage-Only Architecture)

**Focus**: Phase 0 Audit Framework, platform-specific reviews, and performance validation. For coding standards, see [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md).

---

## Table of Contents

1. [Phase 0: Repeatable Audit Framework](#phase-0-repeatable-audit-framework) ⭐ **REQUIRED FIRST STEP**
2. [Entity Review Checklist](#entity-review-checklist)
3. [Performance Review](#performance-review)
4. [Platform-Specific Reviews](#platform-specific-reviews)
5. [Review Process](#review-process)

---

## Phase 0: Repeatable Audit Framework

**CRITICAL**: All new files must be audited using this framework BEFORE code review. This ensures consistent identification of user-facing strings, data constants, logging patterns, and translation requirements.

**When to use**: Auditing any new Python file for integration into the KidsChores codebase (entity platforms, helper modules, coordinator changes, etc.)

**Output**: Standardized audit report (JSON format) documenting findings and required constants.

### Step 1: Logging Audit

```bash
# Search for all logging statements in file
grep -n "const\.LOGGER\.\(debug\|info\|warning\|error\)" file.py
```

**Checklist**:

- [ ] Search for all `const.LOGGER.*` calls in file
- [ ] Verify each uses lazy logging (not f-strings): `logger.debug("Message: %s", var)` ✓
- [ ] Count by severity: DEBUG, INFO, WARNING, ERROR
- [ ] Document any hardcoded strings in log messages
- [ ] Verify no f-strings in lazy logging (should use `%s`, `%d` placeholders)

**Documentation**:

- Total log statements: **N**
- Debug: **X**, Info: **Y**, Warning: **Z**, Error: **W**
- Compliance: **100%** (or list issues found)
- Example: "22 log statements reviewed; 100% compliant; all use correct lazy logging patterns"

### Step 1b: Type Checking Validation

**CRITICAL**: MyPy type checking is now enforced in CI/CD (integrated January 2026). All code must pass with zero errors.

```bash
# Validate type compliance for specific file
mypy custom_components/kidschores/[filename].py
```

**Checklist**:

- [ ] Run mypy on the file being audited
- [ ] Verify zero mypy errors reported
- [ ] Check all functions have type hints (args + return)
- [ ] Verify no `# type: ignore` without justification comment
- [ ] Confirm modern type syntax (`str | None` not `Optional[str]`)
- [ ] Check imports from `collections.abc` not `typing` for generic types

**Documentation**:

- MyPy errors found: **N** (must be 0 for approval)
- Functions without type hints: **X** (must be 0)
- Unjustified `# type: ignore`: **Y** (must be 0)
- Compliance: **100%** (or list issues found)
- Example: "Zero mypy errors; all functions fully typed; 2 type: ignore comments justified"

**Common Type Issues to Flag**:

```python
# ❌ BAD: No return type
def calculate_points(kid_id, chore_id):
    return points

# ✅ GOOD: Complete type hints
def calculate_points(kid_id: str, chore_id: str) -> float:
    return points

# ❌ BAD: Old Optional syntax
from typing import Optional
def get_kid(kid_id: str) -> Optional[dict]:
    pass

# ✅ GOOD: Modern syntax
def get_kid(kid_id: str) -> dict[str, Any] | None:
    pass
```

**Validation Command**:

```bash
# Must pass before proceeding to Step 2
mypy custom_components/kidschores/[filename].py
# Expected output: "Success: no issues found in X source files"
```

**Reference**: [DEVELOPMENT_STANDARDS.md § Type Checking](DEVELOPMENT_STANDARDS.md#type-checking-100-coverage---enforced-in-cicd)

### Step 2: User-Facing String Identification

**Checklist**:

- [ ] Identify all user-facing validation error messages (config flow, options flow)
- [ ] Identify all field labels and descriptions (schema builders)
- [ ] Identify all entity names, descriptions used in UI
- [ ] Identify all error messages returned to user
- [ ] Identify all notification titles and messages (coordinator notification calls)
- [ ] Search for hardcoded strings in error dicts: `errors['field'] = 'hardcoded_string'`
- [ ] Search for strings in field builders: `vol.Optional("name", description="...")`
- [ ] Search for hardcoded notification strings: `title="..."`, `message=...`

**Search patterns**:

```python
errors["field"] = "hardcoded"  # ❌ Identify these
vol.Optional("field", description="Hardcoded text")  # ❌ Identify these
return vol.Schema({...})  # Check for embedded strings
```

**Notification-specific patterns**:

```bash
# Find hardcoded notification titles
grep -n 'title="[A-Z]' file.py

# Find hardcoded notification messages (often with f-strings)
grep -n 'message=.*f"' file.py

# Find notification function calls
grep -n '_notify_kid\|_notify_parents\|async_send_notification' file.py
```

**Documentation**:

- Total user-facing strings found: **N**
- Error messages: **X**
- Field labels: **Y**
- Descriptions: **Z**
- Notification titles/messages: **W**
- Other UI text: **V**
- Hardcoded (non-constant) strings: **List with line numbers**

### Step 3: Data/Lookup Constant Identification

**Checklist**:

- [ ] Search for repeated string literals (use `grep` with frequency count)
- [ ] Identify dictionary keys used 2+ times: `dict['key']`, `dict.get('key')`
- [ ] Identify enum-like strings: status values, type names, tag names
- [ ] Identify format strings: date formats, filename patterns, templates
- [ ] Identify magic numbers and delimiters: hardcoded lengths, delimiters

**Search patterns**:

```bash
# Find most-repeated string literals (potential constants)
grep -oE "'[^']+'|\"[^\"]+\"" file.py | sort | uniq -c | sort -rn | head -20

# Find dictionary access patterns
grep -E "\[.?['\"][^'\"]+['\"]" file.py

# Find hardcoded delimiters or formats
grep -E "(split|join|format|strftime)" file.py
```

**Documentation**:

- Total data constants needed: **N**
- Dictionary keys: **X** items
- Entity type/enum values: **Y** items
- Format strings: **Z** items
- Magic strings: **W** items
- **Breakdown by priority**:
  - HIGH (>5 occurrences): **X** items
  - MEDIUM (2-4 occurrences): **Y** items
  - LOW (1 occurrence): **Z** items

### Step 4: Pattern Analysis

**Checklist**:

- [ ] Verify error messages follow `CFOP_ERROR_*` → `TRANS_KEY_CFOF_*` pattern
- [ ] Verify field labels use appropriate `CFOF_*` or `LABEL_*` constants
- [ ] Verify data structure access is consistent (dict keys vs. const references)
- [ ] Verify logging compliance (no f-strings, lazy evaluation)
- [ ] Search for `const.` usage to understand naming patterns in file

**Documentation**:

- Pattern compliance: **X%** (Y errors, Z warnings)
- Naming patterns identified: (e.g., "BACKUP*KEY*", "ENTITY*KEY*", etc.)
- Issues found: (list any inconsistencies)

### Step 5: Translation Key Verification

**Checklist**:

- [ ] Extract all unique `TRANS_KEY_*` and `CFOP_ERROR_*` constants found in file
- [ ] Cross-reference against `en.json` → verify English translations exist
- [ ] Identify missing translation keys (constants defined but no en.json entry)
- [ ] Document gaps for remediation
- [ ] Note: No strings.json required (KidsChores uses en.json as master, storage-only architecture)

**Search patterns**:

```bash
# Find all TRANS_KEY_ and CFOP_ERROR_ references
grep -n "TRANS_KEY_\|CFOP_ERROR_" file.py

# Verify in en.json (master file)
grep -c "TRANS_KEY_\|CFOP_ERROR_" custom_components/kidschores/translations/en.json
```

**Documentation**:

- Translation keys found: **N**
- In en.json: **Y** ✓
- Missing translations: **List with keys**
- Translation coverage: **X%** (en.json is master, 100% expected)

### Step 6: Audit Documentation

**Generate standardized audit report** (JSON format):

```json
{
  "file": "custom_components/kidschores/flow_helpers.py",
  "audit_date": "2025-12-19",
  "loc_total": 3316,
  "sections": {
    "logging": {
      "total_statements": 22,
      "debug": 17,
      "info": 2,
      "warning": 3,
      "error": 0,
      "compliance_percent": 100,
      "issues": []
    },
    "user_facing_strings": {
      "total": 62,
      "error_messages": 32,
      "field_labels": 15,
      "descriptions": 8,
      "other": 7,
      "hardcoded": 6,
      "compliance_percent": 90
    },
    "data_constants": {
      "total": 47,
      "dict_keys": 12,
      "entity_keys": 9,
      "enum_values": 15,
      "format_strings": 9,
      "magic_strings": 3,
      "high_priority": 21,
      "medium_priority": 21,
      "low_priority": 5
    },
    "translation_keys": {
      "found": 28,
      "in_en_json": 28,
      "missing_en_json": 0,
      "coverage_percent": 100
    }
  },
  "summary": "109 total hardcoded strings; 90% user-facing compliance; 53+ constants needed",
  "constants_needed": [
    {
      "string": "tag",
      "occurrences": 9,
      "suggested_constant": "BACKUP_KEY_TAG = 'tag'",
      "priority": "HIGH"
    }
  ],
  "next_phase": "Constant definition and code remediation"
}
```

**Documentation checklist**:

- [ ] All file sections read (line ranges documented)
- [ ] Logging audit completed and verified
- [ ] User-facing strings 100% identified
- [ ] Data constants categorized by priority
- [ ] Translation keys cross-referenced with en.json (master file)
- [ ] Audit report generated (JSON format)
- [ ] Estimated LOC changes calculated
- [ ] Summary statement written

### Audit Completion Checklist

**Before proceeding to code review**, verify:

- [ ] All 6 steps completed for the file
- [ ] Audit report generated and reviewed
- [ ] No identified user-facing strings missing constants
- [ ] All data constants categorized by priority
- [ ] Translation gaps documented
- [ ] Notification strings audited (if file contains notification code)
- [ ] Estimated constants needed: **N** new constants
- [ ] Estimated code locations to update: **M** locations
- [ ] File is ready for remediation OR full code review

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
# Corresponds to en.json (master translation file):
# { "kid_points": "Points" }
```

- [ ] Translation key set for all entities
- [ ] Corresponding entry exists in `en.json` (master file)
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
- [ ] All tests pass (560+ tests)
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

- [ ] All translation keys exist in `en.json` (master file)
- [ ] All user-facing strings translated
- [ ] No hardcoded English text
- [ ] Error messages translatable

### Step 4: Standards Compliance

**For comprehensive standards, see [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md).**

**Quick Checklist**:

- [ ] **Documentation**: Module/class/method docstrings complete ([DEVELOPMENT_STANDARDS § 4](DEVELOPMENT_STANDARDS.md#4-code-quality--performance-standards))
- [ ] **Type Hints**: 100% coverage with modern syntax ([DEVELOPMENT_STANDARDS § 7](DEVELOPMENT_STANDARDS.md#type-checking-100-coverage---enforced-in-cicd))
- [ ] **Constants**: No hardcoded strings ([DEVELOPMENT_STANDARDS § 3](DEVELOPMENT_STANDARDS.md#3-constant-naming-standards))
- [ ] **Logging**: Lazy logging only ([DEVELOPMENT_STANDARDS § 4](DEVELOPMENT_STANDARDS.md#4-code-quality--performance-standards))
- [ ] **Exceptions**: Translation keys used ([DEVELOPMENT_STANDARDS § 6](DEVELOPMENT_STANDARDS.md#6-error-handling-standards))
- [ ] **Translations**: Keys exist in en.json ([DEVELOPMENT_STANDARDS § 2](DEVELOPMENT_STANDARDS.md#2-localization--translation-standards))

**For quality scale compliance, see [QUALITY_REFERENCE.md](QUALITY_REFERENCE.md).**

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
- [ ] Entry exists in `en.json` (master file)
- [ ] Translation file format valid

**Fix**: Add missing translations to en.json

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

## Phase 0 Deliverables

**Before proceeding to code review**, all audit deliverables must be complete:

### Deliverable 1: Audit Report (JSON)

**Filename**: `audit_report_<filename>_<date>.json`

**Contents**: Complete findings with metrics, constants needed, translation gaps

### Deliverable 2: Constants List

**Format**: Table or JSON array with priority classification

### Deliverable 3: Translation Gaps Report

**Format**: List of missing en.json entries with suggested text

### Acceptance Gate

**All of the following must be true before PR approval**:

- [ ] **Audit report generated** – JSON document with complete findings
- [ ] **Constants list created** – All hardcoded strings categorized
- [ ] **Translation gaps identified** – Missing en.json entries documented
- [ ] **Code remediation plan ready** – Estimate of constants + code changes calculated
- [ ] **Phase 0 checklist** – All 6 steps completed with documentation
- [ ] **Sign-off** – Lead developer confirms audit is complete and accurate

**If Phase 0 is incomplete**, PR should not proceed past code review. Return to Phase 0 for completion.

---

**Review Guide Version**: 2.0
**Last Updated**: January 11, 2026
**Focus**: Streamlined for actionable review steps
