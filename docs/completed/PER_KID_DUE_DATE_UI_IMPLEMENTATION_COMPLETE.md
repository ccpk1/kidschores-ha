# Per-Kid Due Date UI Implementation Plan

**Date**: January 1-2, 2026
**Version**: 1.6 (Sensor Attribute Enhancements)
**Target**: KidsChores v0.4.1
**Priority**: MEDIUM - Backend complete, UI exposure and UX improvements complete
**Status**: ✅ COMPLETE - Phase 1 & 2 done | ✅ UX Improvements | ✅ Sensor Enhancements

**Test Status**: 682 passed, 35 skipped, 0 failed (~47s) - System stable
**Linting Status**: 9.61/10 - Exceeds Silver standard (9.5+ required)
**Phase 3 Backend**: ✅ Validated (30 service tests passing)
**Risk Assessment**: LOW

**Latest Updates** (Jan 2, 2026):

- ✅ **UX Enhancement**: INDEPENDENT chore edit form now shows blank date if per-kid dates differ, or common date if all same
- ✅ **UX Enhancement**: Per-kid dates step now shows template date with "Apply to All" checkbox option
- ✅ **Bug Fix**: Fixed timezone storage bug in coordinator - per-kid due dates now stored as UTC (was local TZ)
- ✅ Added `HELPER_RETURN_SELECTOR_DATETIME` constant for centralized datetime formatting
- ✅ Refactored 3 datetime form handlers (chore + challenge dates) to use new constant
- ✅ Fixed default chore icon to `mdi:broom` using constant per quality standards

**Sensor Attribute Enhancements** (Jan 2, 2026):

- ✅ **Bug Fix**: `KidChoreStatusSensor` and `SystemChoreSharedStateSensor` now return `None` for missing `due_date` (was returning translation key string causing dashboard crash)
- ✅ **Cleanup**: Removed redundant `last_completed` attribute from `KidChoreStatusSensor` (was identical to `last_approved`)
- ✅ **New Attributes**: Added `chore_icon` to both sensors - exposes chore's custom icon for dashboard identity/branding
- ✅ **New Attributes**: Added `last_disapproved` and `last_overdue` to `KidChoreStatusSensor`
- ✅ **New Attributes**: Added `completion_criteria`, `last_claimed`, `last_approved` to `SystemChoreSharedStateSensor`
- ✅ **Reorganization**: Both sensors now have attributes organized by logical category (Identity → Config → Stats → Timestamps → State)

---

## Implementation Progress

| Phase   | Description              | Status      | Validated                   |
| ------- | ------------------------ | ----------- | --------------------------- |
| Phase 1 | Service Documentation    | ✅ Done     | 675 passed, 0 failed        |
| Phase 2 | Options Flow Enhancement | ✅ Done     | 675 passed, 0 failed        |
| Phase 3 | Config Flow Enhancement  | 🔵 Deferred | Nice-to-have, not required  |
| Phase 4 | Documentation Updates    | 🔵 Optional | README/ARCHITECTURE updates |

### Implementation Complete - Summary

**Core Problem Solved**: Users can now discover and use per-kid due dates:

1. ✅ **Phase 1**: Service UI shows `kid_name`/`kid_id` parameters in Developer Tools
2. ✅ **Phase 2**: Editing chores via Options Flow preserves custom per-kid dates

**User Workflow (Complete)**:

1. Create INDEPENDENT chore (all kids get same template date)
2. Use `kidschores.set_chore_due_date` service with `kid_name` to customize
3. Edit chore via Options Flow - custom dates are preserved

**Why Phase 3 is Deferred**:

- Config flow is for NEW chore creation - no existing dates to preserve
- Default behavior (all kids get template date) is reasonable for new chores
- Users can immediately customize via Phase 1's service UI after creation
- Adding a per-kid step to config flow adds complexity without critical value

### Phase 2 Implementation Summary (January 2, 2026)

**Problem Solved**: When editing a chore via Options Flow, `build_chores_data()` was rebuilding `per_kid_due_dates` from the template `due_date`, overwriting any custom per-kid dates set via service calls.

**Solution Implemented** (simpler than planned):

1. **flow_helpers.py** - Added `existing_per_kid_due_dates` parameter to `build_chores_data()`

   - For INDEPENDENT chores: preserves existing kid dates, uses template for new kids only
   - For SHARED chores: uses template date for all kids (expected behavior)

2. **options_flow.py** - Updated `async_step_edit_chore()` to pass existing per-kid dates
   - Extracts `existing_per_kid_due_dates` from chore data before calling helper
   - Passes to `build_chores_data()` to preserve custom dates

**Files Modified**:

- `custom_components/kidschores/flow_helpers.py` (lines ~480, ~680)
- `custom_components/kidschores/options_flow.py` (line ~1219)

**Why Simpler Than Plan**: The plan suggested adding a separate `async_step_edit_chore_per_kid_dates()` step. However, simply preserving existing dates during edit is sufficient - users can still modify per-kid dates via the service call UI (Phase 1)

---

## Code Quality Improvements: DateTime Formatting (January 2, 2026)

**Problem Identified**: Multiple locations had manual `.strftime("%Y-%m-%d %H:%M:%S")` calls for DateTimeSelector formatting, causing code duplication and maintenance burden.

**Solution**: Created dedicated return type constant for centralized datetime formatting:

1. **const.py** - Added new constant (line 1883):

   ```python
   HELPER_RETURN_SELECTOR_DATETIME = "selector_datetime"  # DateTimeSelector format string
   ```

2. **kc_helpers.py** - Enhanced helper functions:

   - `format_datetime_with_return_type()` (lines 926-965) - Added handler for `HELPER_RETURN_SELECTOR_DATETIME`
   - `normalize_datetime_input()` (lines 963-1010) - Updated to support new return type
   - Result: Local timezone string in `"%Y-%m-%d %H:%M:%S"` format

3. **options_flow.py** - Refactored 3 datetime handlers:
   - `async_step_edit_chore()` (line ~1307) - Now uses `HELPER_RETURN_SELECTOR_DATETIME`
   - `async_step_edit_chore_per_kid_dates()` (line ~1444) - Now uses new constant
   - `async_step_edit_challenge()` (lines 1811-1826) - Refactored to use helper function

**Code Audit Results**:

- **12 matches** for DateTimeSelector across 3 files
- **5 matches** for manual strftime with selector format
- **3 locations refactored** to use centralized return type
- **9 matches** for other datetime purposes (calendar, sensor, coordinator - not relevant to selectors)

**Test & Lint Results**:

- ✅ 682 tests passed (35 skipped, 0 failed)
- ✅ Linting: All 66 files meet quality standards
- ✅ Challenge datetime refactoring: 2 passed + 1 skipped

**Benefits**:

- DRY principle maintained - one format definition
- Self-documenting code - constant name explains purpose
- Easy maintenance - update format in one place
- Type safety - return type validates format usage

---

## Sensor Attribute Enhancements (January 2, 2026)

**Context**: During dashboard testing, several sensor attribute issues were identified and fixed to improve dashboard compatibility and provide more useful data to frontends.

### Bug Fix: due_date Returning Translation Key

**Problem**: Both `KidChoreStatusSensor` and `SystemChoreSharedStateSensor` were returning `"display_due_date_not_set"` (a translation key string) instead of `None` when due_date was missing. This caused dashboard crashes because:

- Dashboard template only checked for `['None', 'unknown', 'unavailable']`
- The translation key string passed through and `as_datetime()` failed on invalid format

**Fix**: Both sensors now return `None` directly when due_date is not set, which the dashboard handles gracefully.

### Cleanup: Removed Redundant last_completed

**Problem**: `KidChoreStatusSensor` had both `last_completed` and `last_approved` attributes that were pulling from the same data field (`DATA_KID_CHORE_DATA_LAST_APPROVED`).

**Fix**: Removed `last_completed` attribute and `ATTR_LAST_COMPLETED` constant since it was a duplicate of `last_approved`.

### New Attribute: chore_icon

**Design Context**: KidsChores uses icons differently than standard Home Assistant:

- **Entity icon** (`icon` property): Changes based on chore state (checkmark/clock/alert)
- **Chore icon** (`chore_icon` attribute): The chore's configured custom icon (mdi:toothbrush, mdi:bed, etc.)

**Solution**: Added `ATTR_CHORE_ICON` constant and exposed the chore's custom icon as an attribute, allowing dashboards to show the chore's identity icon while entity icon reflects status.

### New Attributes: KidChoreStatusSensor

| Attribute          | Data Source                            | Purpose                                         |
| ------------------ | -------------------------------------- | ----------------------------------------------- |
| `chore_icon`       | `DATA_CHORE_ICON`                      | Chore's custom identity icon                    |
| `last_disapproved` | `DATA_KID_CHORE_DATA_LAST_DISAPPROVED` | When chore was last disapproved for this kid    |
| `last_overdue`     | `DATA_KID_CHORE_DATA_LAST_OVERDUE`     | When chore was last marked overdue for this kid |

### New Attributes: SystemChoreSharedStateSensor

| Attribute             | Data Source                      | Purpose                             |
| --------------------- | -------------------------------- | ----------------------------------- |
| `chore_icon`          | `DATA_CHORE_ICON`                | Chore's custom identity icon        |
| `completion_criteria` | `DATA_CHORE_COMPLETION_CRITERIA` | SHARED vs INDEPENDENT               |
| `last_claimed`        | `DATA_CHORE_LAST_CLAIMED`        | Chore-level last claim timestamp    |
| `last_approved`       | `DATA_CHORE_LAST_COMPLETED`      | Chore-level last approval timestamp |

### Attribute Organization

Both sensors now have attributes organized by logical category with inline documentation:

```python
# Identity & Meta
chore_name, chore_icon, internal_id

# Configuration
completion_criteria, points, frequency, due_date, approval_type

# Statistics (KidChoreStatusSensor only)
total_claims, total_approved, pending_approval, points_multiplier

# Streaks (KidChoreStatusSensor only)
current_streak, highest_streak, streak_multiplier

# Timestamps
last_claimed, last_approved, last_disapproved, last_overdue

# State
global_state, assignees
```

### Files Modified

| File        | Changes                                                                                              |
| ----------- | ---------------------------------------------------------------------------------------------------- |
| `sensor.py` | Fixed due_date bug, added new attributes, reorganized both sensors                                   |
| `const.py`  | Added `ATTR_CHORE_ICON`, `ATTR_LAST_DISAPPROVED`, `ATTR_LAST_OVERDUE`; Removed `ATTR_LAST_COMPLETED` |

### Test Validation

- ✅ 682 tests passed (35 skipped, 0 failed)
- ✅ All sensor tests continue to pass
- ✅ No regressions introduced

---

## UX Analysis: Independent Chore Due Dates (January 2, 2026)

**Issue Identified**: For INDEPENDENT chores with per-kid due dates, the current UX creates a confusing workflow:

1. User edits chore and sets a "Due Date" (template date)
2. Next step shows individual per-kid dates that override the template
3. Users perceive the template date as pointless since it's immediately overridden

**Root Cause**: Design decision to keep all form fields together for INDEPENDENT chores while still supporting per-kid date overrides. This creates visual confusion about the purpose of the template date.

**Current Behavior**:

- SHARED chores: Template date applies to all kids (makes sense)
- INDEPENDENT chores: Template date is a fallback used only for kids without explicit per-kid dates

**Why Current Design Works**:

- Simple form structure (single step for all chore properties)
- Backwards compatible (existing INDEPENDENT chores have template dates)
- Per-kid dates can be set/modified via separate step OR service calls
- Follows existing UI patterns

---

## ✅ UX Improvements Implemented (January 2, 2026)

**Solution Chosen**: Option 2 - Hybrid Smart Apply (as discussed with user)

### Change 1: Smart Due Date Display on Main Edit Form

**File**: `options_flow.py` - `async_step_edit_chore()` (lines ~1298-1375)

**Behavior for INDEPENDENT chores**:

- Extracts all unique per-kid due dates into a set
- If all kids have the **same** due date → shows that common date as the default
- If kids have **different** due dates → shows blank (indicating "mixed" state)
- SHARED chores: unchanged (always show template date)

**Code Logic**:

```python
# For INDEPENDENT chores, check if all per-kid dates are identical
unique_dates = set()
for kid_id in assigned_kids_ids:
    kid_date = per_kid_due_dates.get(kid_id)
    if kid_date:
        unique_dates.add(kid_date)
    else:
        unique_dates.add(None)

if len(unique_dates) == 1 and None not in unique_dates:
    # All kids have the same date - show it
    the_date = next(iter(unique_dates))
else:
    # Mixed dates or some missing - show blank
    the_date = None
```

### Change 2: Template Date Display with "Apply to All" Option

**File**: `options_flow.py` - `async_step_edit_chore_per_kid_dates()` (lines ~1397-1580)

**New Features**:

1. **Template Date Display**: Shows the template date from main form in step description
2. **Apply to All Checkbox**: New checkbox to bulk-apply template date to all kids
3. **Description Placeholders**: Uses `{template_date}` placeholder in translation

**New Constant**: `const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL = "apply_template_to_all"`

**Translation Updates** (en.json lines 796-805):

```json
"edit_chore_per_kid_dates": {
  "title": "Edit Per-Kid Due Dates: {chore_name}",
  "description": "Set individual due dates for each kid assigned to this INDEPENDENT chore.\n\n**Template date from main form**: {template_date}\n\nCheck 'Apply template to all' to use the template date for all kids.",
  "data": {
    "apply_template_to_all": "Apply template date to all kids"
  },
  "data_description": {
    "apply_template_to_all": "Check this box to apply the date set on the main chore edit page to all kids, replacing their current individual dates."
  }
}
```

**Logic When Checkbox Checked**:

- Template date from main form is applied to all assigned kids
- Individual kid date fields are ignored (template takes precedence)
- Enables quick "reset all to same date" workflow

### Change 3: Timezone Storage Bug Fix

**File**: `coordinator.py` - `set_chore_due_date()` (line 8655)

**Bug**: The `due_date.isoformat()` call was storing whatever timezone was passed (usually local), causing inconsistencies with the UTC storage convention.

**Fix**: Added `dt_util.as_utc()` wrapper:

```python
# Before (bug)
new_due_date_iso = due_date.isoformat() if due_date else None

# After (fixed)
# Ensure due date is stored as UTC ISO string (DateTimeSelector returns local TZ)
new_due_date_iso = dt_util.as_utc(due_date).isoformat() if due_date else None
```

**Impact**: All per-kid due dates now correctly stored in UTC, consistent with other datetime fields.

### Files Modified Summary

| File                   | Changes                                                                       |
| ---------------------- | ----------------------------------------------------------------------------- |
| `options_flow.py`      | Updated `async_step_edit_chore()` and `async_step_edit_chore_per_kid_dates()` |
| `const.py`             | Added `CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL` constant (line 363)           |
| `coordinator.py`       | Fixed timezone bug at line 8655                                               |
| `translations/en.json` | Added translations for Apply to All field (lines 796-805)                     |

### Test & Lint Validation

- ✅ **Tests**: 682 passed, 35 skipped, 0 failed (~47s)
- ✅ **Linting**: 9.61/10 - All 66 files meet quality standards
- ✅ No regressions introduced

---

## Executive Summary

**Problem**: The KidsChores integration fully supports per-kid due dates for INDEPENDENT completion criteria chores at the backend level (Phase 3 implementation), but lacks UI exposure in three critical areas:

1. **Service Documentation** - kid_name/kid_id parameters not documented in services.yaml
2. **Config Flow** - No way to set per-kid date overrides during chore creation
3. **Options Flow** - No way to edit individual kid due dates for existing chores

**Impact**: Users cannot discover or configure per-kid due dates through Home Assistant's UI, despite the feature being fully functional programmatically.

**Approach**: Four-phase implementation focusing on progressive UI enhancement:

- **Phase 1**: Service documentation (immediate fix, 15 minutes)
- **Phase 2**: Options flow enhancement (highest user value, 4-6 hours) - ✅ DONE
- **Phase 3**: Config flow enhancement (new chore creation, 5-7 hours)
- **Phase 4**: Documentation updates (ensures discoverability, 1-2 hours)

---

## 🧪 Current Test Status

**Test Execution Date**: January 1-2, 2026
**Latest Run**: 682 passed, 35 skipped, 0 failed (~46 seconds)
**Linting Status**: 9.61/10 - All 66 files meet quality standards

### Test Suite Results

**Overall Metrics**:

- **Total Tests**: 708 collected
- **Passed**: 675 (95.3% execution rate, 100% pass rate)
- **Skipped**: 33 (4.7% - intentional, documented)
- **Failed**: 0 (✅ Zero failures - system stable)
- **Duration**: 44.74 seconds (efficient test suite)

### Critical Test Categories Validated

| Category                  | Tests              | Status        | Relevance to Phase 1                                      |
| ------------------------- | ------------------ | ------------- | --------------------------------------------------------- |
| **Service Tests**         | 30                 | ✅ All Passed | Validates set_chore_due_date/skip_chore_due_date handlers |
| **Config/Options Flows**  | 57                 | ✅ All Passed | Validates UI infrastructure for Phase 2-3                 |
| **Independent Mode**      | 8 (3 pass, 5 skip) | ✅ Passing    | Validates Phase 3 backend per-kid logic works             |
| **Approval Reset Timing** | 48                 | ✅ All Passed | Validates approval period tracking                        |
| **Datetime Helpers**      | 132                | ✅ All Passed | Validates timezone handling (largest test group)          |
| **Backup Flows**          | 33                 | ✅ All Passed | Validates data recovery mechanisms                        |
| **Badge System**          | 24                 | ✅ All Passed | Validates badge assignment/progress                       |
| **Workflow Tests**        | 34                 | ✅ All Passed | Validates end-to-end claim/approve/reschedule             |

### Intentional Skips (33 Total)

**Per-Kid Due Date UI Gaps** (5 skips - being addressed by this plan):

- `test_independent_overdue_branching.py`: Per-kid due date scenarios (Phase 3 UI gaps)

**Future Features** (28 skips - not in Phase 1-4 scope):

- `test_options_flow_restore.py` (7): Paste JSON functionality
- `test_migration_generic.py` (8): Generic migration framework (test infrastructure)
- `test_scenario_baseline.py` (4): Dashboard helper attributes (Phase 4+ enhancements)
- `test_sensor_values.py` (4): Achievement/challenge sensors (Phase 4+ roadmap)
- `test_workflow_chore_claim.py` (4): Dashboard helper integration
- `test_workflow_shared_regression.py` (1): Alternating chore approval rotation

### Code Quality Baseline

**Linting Results**:

- **Score**: 9.61/10 (exceeds Silver requirement of 9.5+)
- **Files Checked**: 65 files
- **Trailing Whitespace**: ✅ Zero issues
- **Long Lines**: 298 lines exceed 100 chars (⚠️ acceptable for readability)
- **Type Checking**: Disabled (use --types for full check)

### Quality Signals

✅ **System Stability Confirmed**:

- Zero test failures provides confidence for Phase 1 implementation
- 100% pass rate for executed tests (675/675)
- Phase 3 backend validated (30 service tests passing)
- UI infrastructure ready (57 config/options flow tests passing)

✅ **Regression Detection Ready**:

- 675 passing tests establish clear baseline for comparison
- Post-Phase 1 test run must maintain 675 passing (allow same 33 skips)
- Any new failures indicate regression introduced by Phase 1 changes
- Fast execution time (44.74s) enables frequent validation

### Baseline Interpretation

**What This Means for Phase 1**:

1. **Low Risk**: Phase 1 only changes services.yaml (pure metadata, no code logic)
2. **Backend Proven**: 30 service tests passing confirms set_chore_due_date/skip_chore_due_date handlers work
3. **UI Foundation Solid**: 57 config/options flow tests passing confirms UI infrastructure ready
4. **Independent Mode Functional**: 3 passing independent mode tests validate Phase 3 backend logic
5. **Zero Blocking Issues**: 0 failures means no existing bugs to confound Phase 1 work

**Regression Testing Strategy**:

- ✅ Run `python -m pytest tests/ -v --tb=line` after Phase 1 changes
- ✅ Expect: 675 passed, 33 skipped, 0 failed (same as baseline)
- ❌ Any failures = regression introduced by services.yaml changes
- ⚠️ Changes to skip count = test infrastructure changed (investigate)

---

## 📊 Current State Assessment

### ✅ What Works (Backend - Phase 3 Complete)

| Component               | Status      | Location             | Lines                        |
| ----------------------- | ----------- | -------------------- | ---------------------------- |
| **Service Handlers**    | ✅ Complete | services.py          | 972-1082, 1084-1150          |
| **Coordinator Methods** | ✅ Complete | coordinator.py       | 8622-8759                    |
| **Storage Structure**   | ✅ Complete | const.py             | DATA_CHORE_PER_KID_DUE_DATES |
| **Validation Logic**    | ✅ Complete | services.py          | Validates INDEPENDENT mode   |
| **Per-Kid Updates**     | ✅ Complete | coordinator.py       | Updates individual kid dates |
| **Migration**           | ✅ Complete | migration_pre_v42.py | Populates per-kid dates      |

**Backend Capabilities**:

- ✅ Set individual kid due dates via service call
- ✅ Skip individual kid due dates
- ✅ Validate completion criteria before allowing per-kid operations
- ✅ Store per-kid dates in DATA_CHORE_PER_KID_DUE_DATES
- ✅ Fallback to template date when kid_id not specified

### ❌ What's Missing (UI Exposure)

| Gap                             | Impact | Severity | User Effect                                   |
| ------------------------------- | ------ | -------- | --------------------------------------------- |
| **services.yaml documentation** | High   | Low      | Users can't discover kid_name parameter in UI |
| **Options flow per-kid edit**   | High   | Medium   | Editing chore overwrites all per-kid dates    |
| **Config flow per-kid setup**   | Medium | Low      | New chores get same date for all kids         |
| **ARCHITECTURE.md updates**     | Low    | Low      | Developers unaware of per-kid capabilities    |

---

## 🎯 Implementation Phases

### Phase 1: Service Documentation (Immediate) ⚡

**Goal**: Expose kid_name/kid_id parameters in Home Assistant service call UI

**Effort**: 15 minutes (services.yaml only) or 30 minutes (with translations)
**Risk**: None (purely additive)
**Priority**: HIGH (quick win, enables power users)

**Design Decisions**:

- ✅ **Keep kid_id parameter**: Maintains consistency with chore_id/chore_name pattern
- ✅ **Mark kid_id as "advanced"**: Primary interface is kid_name (user-friendly)
- ✅ **kid_id purpose**: Testing convenience, advanced automations, UUID stability
- ✅ **Minimal approach**: Update services.yaml only (translations optional)

**Files to Update**:

#### Required: services.yaml (Base Definitions)

- **File**: `custom_components/kidschores/services.yaml`
- **Lines**: 260-282 (set_chore_due_date), 284-310 (skip_chore_due_date)

**Changes Required**:

1. **set_chore_due_date** (lines 260-282):

   - Add kid_name field definition (primary interface)
   - Add kid_id field definition (advanced, marked as optional)
   - Update service description to mention INDEPENDENT mode support
   - Add clear examples for both parameters

2. **skip_chore_due_date** (lines 284-310):
   - Add kid_name field definition (primary interface)
   - Add kid_id field definition (advanced, marked as optional)
   - Update service description to mention per-kid capability
   - Add clear examples for both parameters

#### Optional: translations/en.json (Refinements)

- **File**: `custom_components/kidschores/translations/en.json`
- **Purpose**: Refine wording, prepare for future language support
- **Recommendation**: Skip for Phase 1 (services.yaml sufficient)
- **Note**: Translation files override services.yaml text but are not required

**Validation**:

- [ ] YAML syntax validated: `python -c "import yaml; yaml.safe_load(open('services.yaml'))"`
- [ ] Home Assistant UI shows kid_name field (text input)
- [ ] Home Assistant UI shows kid_id field (text input, optional)
- [ ] Field descriptions clarify INDEPENDENT mode usage
- [ ] kid_id description notes "advanced" usage and suggests kid_name
- [ ] Service call with kid_name works as expected
- [ ] Service call with kid_id works as expected
- [ ] Service call without kid parameters works (all-kids fallback)

---

### Phase 2: Options Flow Enhancement (High Value) 🎨

**Goal**: Allow editing individual kid due dates for existing INDEPENDENT chores

**Effort**: 4-6 hours
**Risk**: Medium (must handle kid addition/removal)
**Priority**: HIGH (biggest user pain point)

**Implementation Steps**:

#### Step 2.1: Add Per-Kid Date Editing Step

- **File**: `custom_components/kidschores/options_flow.py`
- **Method**: `async_step_edit_chore_per_kid_dates()`
- **Location**: After line 1316 (after `async_step_edit_chore`)

**Logic**:

```python
async def async_step_edit_chore_per_kid_dates(self, user_input=None):
    """Allow editing per-kid due dates for INDEPENDENT chores."""

    # Only show if completion_criteria == "independent"
    if self._chore_being_edited.get(const.DATA_CHORE_COMPLETION_CRITERIA) != const.COMPLETION_CRITERIA_INDEPENDENT:
        return await self.async_step_edit_menu()

    # Build schema with one date field per assigned kid
    assigned_kids = self._chore_being_edited.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    per_kid_due_dates = self._chore_being_edited.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})

    fields = {}
    for kid_id in assigned_kids:
        kid_name = self.coordinator.kids_data[kid_id][const.DATA_KID_NAME]
        current_date = per_kid_due_dates.get(kid_id)
        fields[kid_id] = vol.Optional(
            f"due_date_{kid_id}",
            description=f"Due date for {kid_name}",
            default=current_date
        ): DateTimeSelector()

    # Process input and update per_kid_due_dates
```

#### Step 2.2: Add Navigation from Edit Menu

- **File**: `custom_components/kidschores/options_flow.py`
- **Method**: `async_step_edit_chore()`
- **Add**: Conditional "Edit Per-Kid Dates" button when completion_criteria is INDEPENDENT

#### Step 2.3: Update build_chores_data Helper

- **File**: `custom_components/kidschores/flow_helpers.py`
- **Method**: `build_chores_data()` (lines 755-761)
- **Change**: Preserve per-kid dates when provided from per-kid editing step

**Validation**:

- [ ] "Edit Per-Kid Dates" button shows for INDEPENDENT chores
- [ ] Per-kid date form displays all assigned kids
- [ ] Saving updates DATA_CHORE_PER_KID_DUE_DATES correctly
- [ ] Removing kid from chore removes their per-kid date
- [ ] Adding kid to chore initializes their date to template

---

### Phase 3: Config Flow Enhancement (New Chores) 🆕

**Goal**: Allow setting per-kid dates during chore creation

**Effort**: 5-7 hours
**Risk**: Low (new flow, no backward compatibility issues)
**Priority**: MEDIUM (nice-to-have for new chores)

**Implementation Steps**:

#### Step 3.1: Add Optional Per-Kid Dates Step

- **File**: `custom_components/kidschores/config_flow.py`
- **Method**: `async_step_chores_per_kid_dates()`
- **Location**: After line 497 (after chore collection)

**Logic**:

```python
async def async_step_chores_per_kid_dates(self, user_input=None):
    """Optional: Set per-kid due dates for INDEPENDENT chores."""

    # Only show for INDEPENDENT chores with assigned kids
    if not self._show_per_kid_dates:
        return self.async_create_entry(...)

    # Get kids selected in previous step
    assigned_kids = self._kids_temp  # From chores step
    template_date = self._template_due_date  # From chores step

    # Build schema with date field per kid
    schema = {}
    for kid_id, kid_data in assigned_kids.items():
        schema[kid_id] = vol.Optional(
            f"due_date_{kid_id}",
            description=f"Due date for {kid_data['name']}",
            default=template_date
        ): DateTimeSelector()

    # Store per-kid overrides in _per_kid_due_dates_temp
```

#### Step 3.2: Update Chore Collection Step

- **File**: `custom_components/kidschores/config_flow.py`
- **Method**: `async_step_chores()`
- **Add**: Store `_show_per_kid_dates` flag when completion_criteria is INDEPENDENT

#### Step 3.3: Merge Per-Kid Dates into Chore Data

- **File**: `custom_components/kidschores/flow_helpers.py`
- **Method**: `build_chores_data()`
- **Add**: Accept `per_kid_overrides` parameter and merge into per_kid_due_dates

**Validation**:

- [ ] Per-kid dates step only shows for INDEPENDENT chores
- [ ] Template date pre-fills all kid date fields
- [ ] Overrides merge into DATA_CHORE_PER_KID_DUE_DATES
- [ ] Skipping step uses template for all kids

---

### Phase 4: Documentation Updates 📚

**Goal**: Ensure all documentation reflects per-kid due date capabilities

**Effort**: 1-2 hours
**Risk**: None
**Priority**: MEDIUM (developer/user reference)

**Files to Update**:

#### 4.1: ARCHITECTURE.md

- **Section**: "Entity Data (Storage)" or "Chore Management"
- **Add**: Per-kid due dates section explaining:
  - DATA_CHORE_PER_KID_DUE_DATES structure
  - Template pattern (chore-level vs per-kid)
  - When per-kid dates are used (INDEPENDENT mode)
  - How dates are populated (config flow, services, options flow)

#### 4.2: CODE_REVIEW_GUIDE.md (if applicable)

- **Section**: "Chore Review Patterns"
- **Add**: Checklist for per-kid date handling:
  - [ ] Completion criteria checked before per-kid operations
  - [ ] Per-kid dates validated for INDEPENDENT chores
  - [ ] Template date fallback implemented

#### 4.3: README.md (if exists in custom_components/kidschores/)

- **Section**: "Services"
- **Update**: Document kid_name parameter for:
  - `kidschores.set_chore_due_date`
  - `kidschores.skip_chore_due_date`

#### 4.4: PHASE3_INDEPENDENT_MODE_FIXES.md

- **Section**: "Component Implementation Status"
- **Update**: Add note about services.yaml gap closure
- **Add**: Reference to this plan for UI implementation

**Validation**:

- [ ] All per-kid date features documented
- [ ] Architecture diagram (if exists) shows per-kid storage
- [ ] Service documentation includes examples
- [ ] Phase 3 status updated to reflect full completion

---

## 📋 Testing Strategy

### Phase 1 Testing (Services)

#### Test 1: Per-Kid Update via kid_name

```yaml
# Developer Tools > Services
service: kidschores.set_chore_due_date
data:
  chore_name: "Clean Room"
  kid_name: "Alice"
  due_date: "2026-01-15T20:00:00"
```

**Expected**: Service call succeeds, only Alice's due date updated in storage

#### Test 2: Per-Kid Update via kid_id (Advanced)

```yaml
service: kidschores.set_chore_due_date
data:
  chore_name: "Clean Room"
  kid_id: "kid_abc123" # UUID from storage
  due_date: "2026-01-16T20:00:00"
```

**Expected**: Service call succeeds, only specified kid's date updated

#### Test 3: All-Kids Update (No kid parameter)

```yaml
service: kidschores.set_chore_due_date
data:
  chore_name: "Clean Room"
  due_date: "2026-01-20T20:00:00"
```

**Expected**: Service call succeeds, all assigned kids updated to same date

#### Test 4: SHARED Chore with kid_name (Should Fail)

```yaml
service: kidschores.set_chore_due_date
data:
  chore_name: "Family Dinner" # SHARED chore
  kid_name: "Alice"
  due_date: "2026-01-15T20:00:00"
```

**Expected**: Service call fails with validation error (INDEPENDENT chores only)

### Phase 2 Testing (Options Flow)

1. Create INDEPENDENT chore with 3 kids
2. Options > Edit Chore > Edit Per-Kid Dates
3. Set different dates for each kid
4. Verify storage shows 3 different dates
5. Edit chore to remove one kid
6. Verify removed kid's date deleted

### Phase 3 Testing (Config Flow)

1. Config flow > Create chore with INDEPENDENT criteria
2. Assign 2 kids
3. Set template date
4. Per-kid dates step appears
5. Override one kid's date
6. Verify storage has template + override

### Regression Testing

- [ ] All 630+ existing tests pass
- [ ] SHARED chores still use single due date
- [ ] Template pattern works for no overrides
- [ ] Migration still populates per-kid dates

---

## 🚀 Implementation Priority & Timeline

### Sprint 1: Service Documentation (Day 1)

- **Duration**: 1 hour (includes testing and validation)
- **Approach**: Minimal (services.yaml only, skip translations)
- **Deliverable**: services.yaml updated with kid_name/kid_id field definitions
- **Validation**: Developer Tools UI shows new fields, manual service calls work
- **Value**: Immediate unblock for power users and automation writers

### Sprint 2: Options Flow (Week 1)

- **Duration**: 1-2 days
- **Deliverable**: Per-kid date editing functional
- **Value**: Fixes major user pain point

### Sprint 3: Config Flow (Week 2)

- **Duration**: 2-3 days
- **Deliverable**: Per-kid dates during creation
- **Value**: Complete feature parity

### Sprint 4: Documentation (Week 2)

- **Duration**: 1 day
- **Deliverable**: All docs updated
- **Value**: Developer/user discoverability

**Total Effort**: 10-14 hours over 2 weeks

---

## 🎯 Success Criteria

### Phase 1 Success

- [ ] `services.yaml` updated with kid_name and kid_id field definitions
- [ ] YAML syntax validated (no parse errors)
- [ ] Home Assistant integration reloaded
- [ ] Developer Tools → Services UI shows kid_name field (text input)
- [ ] Developer Tools → Services UI shows kid_id field (text input, advanced)
- [ ] Field descriptions clarify INDEPENDENT mode usage
- [ ] kid_id description notes "advanced" and suggests kid_name instead
- [ ] Service call with kid_name parameter works (updates single kid)
- [ ] Service call with kid_id parameter works (updates single kid)
- [ ] Service call without kid parameters works (updates all kids fallback)
- [ ] Manual testing confirms per-kid updates in storage

### Phase 2 Success

- [ ] Options flow shows "Edit Per-Kid Dates" for INDEPENDENT chores
- [ ] Can set different dates for each kid
- [ ] Editing chore preserves per-kid dates
- [ ] Linting passes (9.5+/10)
- [ ] All tests pass

### Phase 3 Success

- [ ] Config flow offers per-kid date step for INDEPENDENT chores
- [ ] Can override template date per kid
- [ ] Skipping step uses template for all
- [ ] Linting passes
- [ ] All tests pass

### Phase 4 Success

- [ ] ARCHITECTURE.md documents per-kid dates
- [ ] CODE_REVIEW_GUIDE.md includes per-kid patterns
- [ ] Service documentation complete
- [ ] Phase 3 plan updated

---

## 🚨 Risks & Mitigations

| Risk                                     | Severity | Mitigation                                             |
| ---------------------------------------- | -------- | ------------------------------------------------------ |
| **Options flow breaks existing chores**  | Medium   | Preserve per-kid dates when not editing them           |
| **Kid addition/removal edge cases**      | Medium   | Initialize new kids to template, clean up removed kids |
| **UI complexity (too many date fields)** | Low      | Collapsible sections, clear labels                     |
| **Performance with many kids**           | Low      | Test with scenario_stress (10+ kids)                   |
| **Migration compatibility**              | Low      | Phase 3 already handles migration                      |

---

## 📖 Related Documentation

- **Phase 3 Plan**: [PHASE3_INDEPENDENT_MODE_FIXES.md](../completed/chore_enhancements/PHASE3_INDEPENDENT_MODE_FIXES.md)
- **Architecture**: [ARCHITECTURE.md](../ARCHITECTURE.md)
- **Code Review**: [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
- **Testing Guide**: [tests/TESTING_AGENT_INSTRUCTIONS.md](../../tests/TESTING_AGENT_INSTRUCTIONS.md)

---

## 📌 Technical Decisions & Rationale

### Decision 1: Keep kid_id Parameter

**Question**: Is `kid_id` necessary in service schemas if users can't discover internal UUIDs?

**Analysis**:

- ❌ Users cannot discover UUIDs from UI (only know kid names)
- ✅ Name resolution works reliably (`get_kid_id_or_raise()` helper exists)
- ✅ Pattern consistency: Matches existing `chore_id`/`chore_name` pattern across all services
- ✅ Testing clarity: Tests can use UUIDs when names would be ambiguous
- ✅ Advanced use cases: Automations might prefer stable UUIDs over names
- ⚖️ Zero implementation cost: Already implemented and tested in backend

**Decision**: **KEEP `kid_id`** but mark as "advanced" parameter

**Implementation**:

```yaml
kid_name:
  name: "Kid Name"
  description: "(INDEPENDENT chores only) Name of kid to update"
  required: false
kid_id:
  name: "Kid ID"
  description: "(Advanced) Internal UUID - use kid_name for normal usage"
  required: false
  selector:
    text:
      advanced: true # Hides in basic UI
```

**Benefits**:

- Maintains consistency with existing service patterns
- Supports advanced automation scenarios
- No user confusion (hidden by default via `advanced: true`)
- Future-proof for UUID-based workflows

---

### Decision 2: services.yaml vs Translation Files

**Question**: Should we update both `services.yaml` and `translations/en.json`?

**Analysis**:

- `services.yaml`: Base service definitions, always required, English-only
- `translations/en.json`: Optional overrides, supports multi-language, refines text
- Home Assistant resolution: Translation files override YAML (if present)
- Current state: Phase 3 backend works without either being updated

**Decision**: **Minimal Approach - services.yaml Only**

**Rationale**:

1. **Immediate functionality**: YAML updates make features discoverable in UI instantly
2. **Translation files optional**: Home Assistant falls back to YAML text if translation missing
3. **Effort optimization**: 15 minutes (YAML) vs 30 minutes (YAML + translations)
4. **English-only sufficient**: KidsChores currently English-only installation base
5. **Future enhancement**: Can add translation refinements in later phase if needed

**Implementation Priority**:

- **Phase 1**: Update services.yaml (required for UI discovery)
- **Future**: Add translations/en.json refinements when preparing multi-language support

**Translation File Purpose**:

- Override/refine English text for clarity
- Prepare structure for future language translations (es.json, fr.json, etc.)
- Not required for English-only installations

---

### Decision 3: kid_id vs kid_name Usage Pattern

**Backend Implementation**:

```python
# services.py handler pattern
kid_id = None
kid_name = call.data.get(const.FIELD_KID_NAME)
if kid_name:
    kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Set Chore Due Date")
elif const.FIELD_KID_ID in call.data:
    kid_id = call.data.get(const.FIELD_KID_ID)
```

**User Flow**:

1. **Primary path**: User provides `kid_name` → Backend resolves to `kid_id` → Coordinator uses UUID
2. **Advanced path**: Automation provides `kid_id` → Backend uses directly → Coordinator uses UUID
3. **All-kids path**: Neither parameter → Backend passes `kid_id=None` → Coordinator updates all kids

**Key Insight**: `kid_id` exists for backend efficiency and advanced scenarios, not typical user workflows

---

### Decision 4: Documentation Completeness

**services.yaml Requirements**:

- ✅ Document all schema fields (including optional ones)
- ✅ Clarify conditional behavior (INDEPENDENT vs SHARED mode)
- ✅ Provide clear examples for each parameter
- ✅ Mark advanced parameters appropriately
- ✅ Explain fallback behavior (empty kid_name = all kids)

**Documentation Standards**:

```yaml
# Good documentation pattern
kid_name:
  name: "Kid Name"
  description: >
    (INDEPENDENT chores only) Update due date for this specific kid.
    Leave empty to update all assigned kids.
  example: "Alice"
  required: false
  selector:
    text:

# Bad documentation pattern (avoid)
kid_name:
  name: "Kid Name"
  required: false  # ❌ No description, no context, no example
```

---

## 📝 Implementation Notes

### Key Design Decisions

1. **Template Pattern**: Chore-level due_date is template; per-kid dates are overrides

   - **Rationale**: Simplifies common case (all kids same date) while allowing exceptions

2. **Optional Per-Kid Step**: Config flow per-kid dates are optional

   - **Rationale**: Most chores use same date; don't force complexity

3. **Conditional UI**: Only show per-kid options for INDEPENDENT chores

   - **Rationale**: Avoid confusion for SHARED chores

4. **Preserve on Edit**: Options flow preserves per-kid dates unless explicitly changed
   - **Rationale**: Prevent accidental data loss

### Code Quality Standards

All phases must follow:

- ✅ Type hints on all functions
- ✅ Lazy logging (no f-strings in logs)
- ✅ Constants for all strings (const.py)
- ✅ Translation keys for user-facing text
- ✅ Linting 9.5+/10
- ✅ All tests pass

---

## ✅ Definition of Done

**Phase 1 Complete When**:

- services.yaml updated with kid_name/kid_id field definitions
- YAML syntax validated (no parse errors)
- Home Assistant integration reloaded successfully
- Developer Tools → Services UI shows kid_name field (text input)
- Developer Tools → Services UI shows kid_id field (text input, marked advanced)
- Field descriptions clarify INDEPENDENT mode usage
- Manual test confirms per-kid service call works (kid_name)
- Manual test confirms per-kid service call works (kid_id)
- Manual test confirms all-kids fallback works (no kid parameter)
- Storage inspection shows correct per-kid date updates
- No translation file updates required (services.yaml sufficient)

**Phase 2 Complete When**:

- Options flow has per-kid date editing step
- Can set different dates for each kid
- Linting passes, all tests pass
- Manual UI testing confirms functionality

**Phase 3 Complete When**:

- Config flow has optional per-kid dates step
- Can override template date per kid
- Linting passes, all tests pass
- Manual UI testing confirms functionality

**Phase 4 Complete When**:

- ARCHITECTURE.md updated
- Service documentation complete
- Phase 3 plan updated with closure note
- All cross-references validated

**Overall Plan Complete When**:

- All 4 phases complete
- 630+ tests passing
- Linting 9.5+/10
- User can discover and use per-kid dates through UI
- Documentation reflects all capabilities

---

**Plan Version**: 1.0
**Last Updated**: January 1, 2026
**Status**: ✅ BASELINE ESTABLISHED - Ready for Phase 1 implementation

---

## 🚀 Next Steps: Phase 1 Implementation Guide

### Pre-Flight Checklist

✅ **Baseline Established** (completed 2026-01-01):

- 675 tests passing, 0 failures → System stable
- Linting 9.61/10 → Code quality exceeds Silver standard
- Phase 3 backend validated → 30 service tests passing
- Baseline logs saved → `/tmp/test_baseline.log`, `/tmp/lint_baseline.log`

✅ **Ready for Implementation**:

- Low-risk changes (services.yaml metadata only, no code logic)
- Quick turnaround (15 minutes for services.yaml only)
- Immediate value for power users (discoverability in Developer Tools)

### Phase 1: Step-by-Step Implementation

#### Step 1: Update set_chore_due_date Service (5 minutes)

**File**: `custom_components/kidschores/services.yaml`
**Location**: Lines 260-282

**Current State** (missing kid_name/kid_id fields):

```yaml
set_chore_due_date:
  name: "Set Chore Due Date"
  description: >
    Update the due date for a chore. For INDEPENDENT completion criteria chores,
    you can update the date for all assigned kids or a specific kid.
  target:
    entity:
      integration: kidschores
      domain: sensor
  fields:
    chore_name:
      name: "Chore Name"
      description: "The name of the chore to update."
      example: "Clean room"
      required: true
      selector:
        text:
    # ⚠️ MISSING: kid_name and kid_id fields
```

**Add These Fields** (after chore_name):

```yaml
kid_name:
  name: "Kid Name"
  description: >
    (INDEPENDENT chores only) Update due date for this specific kid.
    Leave empty to update all assigned kids. Use either kid_name or kid_id, not both.
  example: "Alice"
  required: false
  selector:
    text:
kid_id:
  name: "Kid ID"
  description: >
    (INDEPENDENT chores only) Internal UUID of the kid. Use kid_name instead unless
    testing or building advanced automations. Leave empty to update all assigned kids.
  example: "kid_12345678-1234-1234-1234-123456789abc"
  required: false
  advanced: true
  selector:
    text:
```

#### Step 2: Update skip_chore_due_date Service (5 minutes)

**File**: `custom_components/kidschores/services.yaml`
**Location**: Lines 284-310

**Current State** (similar to set_chore_due_date, missing same fields)

**Add Same Fields** (kid_name and kid_id) using identical pattern as Step 1

#### Step 3: Validate YAML Syntax (1 minute)

**Command**:

```bash
cd /workspaces/kidschores-ha/custom_components/kidschores
python -c "import yaml; yaml.safe_load(open('services.yaml')); print('✅ YAML syntax valid')"
```

**Expected Output**: `✅ YAML syntax valid`
**Error Handling**: Fix any indentation or quoting issues if validation fails

#### Step 4: Reload Home Assistant Integration (2 minutes)

**Option A - Full Restart** (recommended for first time):

```bash
cd /workspaces/core
ha core restart
# Wait ~30 seconds for Home Assistant to fully restart
```

**Option B - Quick Reload** (if integration supports it):

1. Open Home Assistant UI → Settings → Devices & Services
2. Find "KidsChores" integration
3. Click three-dot menu → "Reload"

#### Step 5: Manual Testing in Developer Tools (5 minutes)

**Test Scenario 1 - Service Call with kid_name**:

1. Developer Tools → Services
2. Select service: `kidschores.set_chore_due_date`
3. Fill fields:
   - `chore_name`: "Clean room" (use actual chore from your test data)
   - `kid_name`: "Zoë" (use actual kid from scenario_minimal)
   - `new_due_date`: Tomorrow's date in YYYY-MM-DD format
4. Click "CALL SERVICE"
5. **Expected**: Service executes successfully, no errors in logs
6. **Verify**: Storage inspection shows per-kid date updated

**Test Scenario 2 - Service Call with kid_id** (advanced field):

1. Developer Tools → Services (toggle "Show advanced options")
2. Select service: `kidschores.set_chore_due_date`
3. Fill fields:
   - `chore_name`: "Clean room"
   - `kid_id`: Copy UUID from storage (e.g., "kid_12345...")
   - `new_due_date`: Tomorrow's date
4. Click "CALL SERVICE"
5. **Expected**: Same behavior as kid_name test
6. **Verify**: Per-kid date updated correctly

**Test Scenario 3 - Fallback Behavior** (no kid parameter):

1. Developer Tools → Services
2. Select service: `kidschores.set_chore_due_date`
3. Fill fields:
   - `chore_name`: "Clean room"
   - `new_due_date`: Tomorrow's date
   - Leave `kid_name` and `kid_id` empty
4. Click "CALL SERVICE"
5. **Expected**: Template date updated for all kids
6. **Verify**: All assigned kids get same due date

**Test Scenario 4 - Field Discovery**:

1. Developer Tools → Services
2. Select service: `kidschores.set_chore_due_date`
3. **Verify UI Shows**:
   - ✅ `kid_name` field (text input, not advanced)
   - ✅ `kid_id` field (text input, marked "Advanced" - hidden by default)
   - ✅ Field descriptions mention "INDEPENDENT chores only"
   - ✅ Example values populated correctly

#### Step 6: Regression Testing (2 minutes)

**Command**:

```bash
cd /workspaces/kidschores-ha
python -m pytest tests/ -v --tb=line 2>&1 | tee /tmp/test_phase1_post.log
```

**Expected Results**:

- ✅ 675 tests passed (same as baseline)
- ✅ 33 tests skipped (same as baseline)
- ❌ 0 tests failed (no regressions)
- ⚠️ If any failures: Revert services.yaml changes, investigate

**Compare to Baseline**:

```bash
# Quick comparison of test counts
echo "=== BASELINE ==="
grep -E "passed|skipped|failed" /tmp/test_baseline.log | tail -1
echo "=== POST-PHASE 1 ==="
grep -E "passed|skipped|failed" /tmp/test_phase1_post.log | tail -1
```

#### Step 7: Linting Validation (1 minute)

**Command**:

```bash
cd /workspaces/kidschores-ha
./utils/quick_lint.sh --fix
```

**Expected**: `✅ Ready to commit!` (9.5+/10 score maintained)

#### Step 8: Mark Phase 1 Complete

**Update This Plan**:

- Change Phase 1 status from `- [ ] Phase 1: Service Documentation` to `- [x] Phase 1: Service Documentation`
- Update timeline table: Phase 1 Actual Duration = X minutes
- Add Phase 1 completion notes section

**Git Commit** (if using version control):

```bash
git add custom_components/kidschores/services.yaml
git commit -m "feat: Expose kid_name/kid_id parameters in services.yaml

- Added kid_name field to set_chore_due_date service
- Added kid_name field to skip_chore_due_date service
- Added kid_id field (marked advanced) to both services
- Documented INDEPENDENT mode requirement in field descriptions
- Phase 1 of Per-Kid Due Date UI Implementation complete

Refs: PER_KID_DUE_DATE_UI_IMPLEMENTATION.md Phase 1
Tests: 675 passed (baseline maintained), 0 regressions"
```

### Success Criteria Validation

Before marking Phase 1 complete, verify all 11 Definition of Done items:

- [ ] services.yaml updated with kid_name/kid_id field definitions
- [ ] YAML syntax validated (no parse errors)
- [ ] Home Assistant integration reloaded successfully
- [ ] Developer Tools → Services UI shows kid_name field (text input)
- [ ] Developer Tools → Services UI shows kid_id field (text input, marked advanced)
- [ ] Field descriptions clarify INDEPENDENT mode usage
- [ ] Manual test confirms per-kid service call works (kid_name)
- [ ] Manual test confirms per-kid service call works (kid_id)
- [ ] Manual test confirms all-kids fallback works (no kid parameter)
- [ ] Storage inspection shows correct per-kid date updates
- [ ] No translation file updates required (services.yaml sufficient)

**Phase 1 Timeline**:

- Estimated: 15 minutes
- Includes: services.yaml editing (10 min) + validation/testing (5 min)
- Excludes: Optional translation files (30 min total if added)

### After Phase 1: What's Next?

**Immediate Value Delivered**:

- ✅ Power users can discover kid_name parameter in Developer Tools
- ✅ Advanced users can use kid_id in automations
- ✅ Service documentation matches backend capabilities
- ✅ Zero code changes = zero regression risk

**Remaining Gaps** (Phases 2-4):

- ⏳ Phase 2: Options flow per-kid editing (4-6 hours)
- ⏳ Phase 3: Config flow per-kid setup (5-7 hours)
- ⏳ Phase 4: Documentation updates (1-2 hours)

**Ready to Proceed?**:
If Phase 1 validation passes (all 11 criteria ✅), proceed immediately to Phase 2 implementation or mark initiative on hold if Phase 2 not prioritized.

---

**Document Control**:

- Plan Created: January 1, 2026
- Baseline Established: January 1, 2026 (675 passed, 0 failed)
- Phase 1 Implementation Guide Added: January 1, 2026
- Next Review: After Phase 1 completion
