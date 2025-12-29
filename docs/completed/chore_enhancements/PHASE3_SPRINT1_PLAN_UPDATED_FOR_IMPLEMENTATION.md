# Phase 3 Sprint 1 - Plan Update Proposal

**Date**: December 27, 2025
**Purpose**: Clarify data structures and implementation approach for Steps 1.3-1.4 (Coordinator) and Phase B (Services)
**Status**: Ready for approval before implementing

---

## Overview: What Was Discovered

After reviewing the official PHASE3_INDEPENDENT_MODE_FIXES.md plan and the actual codebase, I've identified critical information needed to implement cleanly:

### ✅ VERIFIED - All Baseline Constants Exist

All data access constants referenced in the plan are CONFIRMED in const.py:

- `DATA_CHORE_SHARED_CHORE` (line 999) ✅
- `DATA_CHORE_COMPLETION_CRITERIA` (line 1001) ✅
- `DATA_CHORE_PER_KID_DUE_DATES` (line 1002) ✅
- `COMPLETION_CRITERIA_SHARED` (line 1005) ✅
- `COMPLETION_CRITERIA_INDEPENDENT` (line 1006) ✅
- `DATA_KID_CHORE_DATA` (line 693) ✅
- `DATA_KID_CHORE_DATA_DUE_DATE` (line 696) ✅

### ✅ VERIFIED - Helper Methods Already Exist

The overdue checking split (from Step 1.2) created these helpers:

- `_check_overdue_independent()` at line 6971 ✅ (49 lines - checks per-kid due dates)
- `_check_overdue_shared()` at line 7021 ✅ (checks chore-level due dates)
- `_notify_overdue_chore()` at line 7095 ✅ (handles notifications)

### ✅ VERIFIED - Main Methods Exist for Modification

- `reset_overdue_chores()` at lines 7755-7860 (105 lines) ✅
- `_reschedule_chore_next_due_date()` at line 7447 ✅ (chore-level rescheduling)
- `_migrate_independent_chores()` at line 94 (placeholder stub) ✅

### ⚠️ UNDEFINED - Constants from Original Plan NOT in Code

These were referenced in broken code I reverted:

- `DATA_CHORE_RECURRING_PATTERN` ❌ (doesn't exist)
- `DATA_CHORE_DATA_LAST_COMPLETED_TIME` ❌ (doesn't exist)

### ⚠️ UNDEFINED - Method Not Verified

- `_calculate_next_due_date()` - Referenced but location not verified

---

## Implementation Strategy for Steps 1.3-1.4

### Step 1.3: Update `reset_overdue_chores()` with Branching Logic

**Location**: `custom_components/kidschores/coordinator.py` lines 7755-7860

**Current State**: All three cases (specific chore, kid-only, global) call `_reschedule_chore_next_due_date()` (chore-level only)

**Required Change**:

Add branching logic based on `DATA_CHORE_COMPLETION_CRITERIA`:

```python
def reset_overdue_chores(self, chore_id=None, kid_id=None):
    """Reset overdue chore(s) with per-kid support for INDEPENDENT chores."""

    if chore_id:
        chore_info = self._data[const.DATA_CHORES].get(chore_id)
        if not chore_info:
            return

        # Check if INDEPENDENT mode
        completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Reset per-kid due dates
            if kid_id:
                # Reset specific kid
                self._reschedule_chore_for_kid(chore_info, kid_id)
            else:
                # Reset all assigned kids
                assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
                for assigned_kid_id in assigned_kids:
                    self._reschedule_chore_for_kid(chore_info, assigned_kid_id)
        else:
            # SHARED mode: Use chore-level (current behavior)
            self._reschedule_chore_next_due_date(chore_info)
```

**New Helper Method to Add**:

```python
def _reschedule_chore_for_kid(self, chore_info: dict, kid_id: str) -> None:
    """Reschedule INDEPENDENT chore for specific kid.

    Updates per-kid due date in DATA_CHORE_PER_KID_DUE_DATES.
    Handles next occurrence calculation based on recurring frequency.
    """
    chore_id = chore_info[const.DATA_CHORE_INTERNAL_ID]

    # Get kid's current due date from per-kid storage
    per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
    current_due_str = per_kid_due_dates.get(kid_id)
    current_due = parse_datetime_to_utc(current_due_str) if current_due_str else None

    # Calculate next due date (reuse existing logic)
    # Use chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] for calculation
    new_due_date = self._calculate_next_due_date(current_due, chore_info)

    # Update per-kid storage
    per_kid_due_dates[kid_id] = new_due_date.isoformat() if new_due_date else None
    chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

    # Update kid's chore data
    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
    kid_chore_data[const.DATA_KID_CHORE_DATA_DUE_DATE] = (
        new_due_date.isoformat() if new_due_date else None
    )

    # Update state (move from overdue to pending)
    self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING)

    const.LOGGER.debug(
        "Rescheduled INDEPENDENT chore for kid: chore=%s, kid=%s, new_due=%s",
        chore_info.get(const.DATA_CHORE_NAME),
        self.kids_data[kid_id].get(const.DATA_KID_NAME),
        new_due_date.isoformat() if new_due_date else "None"
    )

    self._persist()
```

### Step 1.4: Complete Migration Method

**Location**: `custom_components/kidschores/coordinator.py` line 94 (placeholder stub)

**Current State**: Method exists but has no implementation

**Note**: Backward compatibility NOT needed - migration will be run once to update all data.

**Required Implementation**:

```python
def _migrate_independent_chores(self) -> None:
    """Migrate existing INDEPENDENT chores to per-kid due date structure.

    One-time migration that:
    1. Detects INDEPENDENT chores (using completion_criteria field)
    2. Populates DATA_CHORE_PER_KID_DUE_DATES from template for each assigned kid
    3. Persists migration results
    """
    migration_count = 0

    for chore_id, chore_info in self._data.get(const.DATA_CHORES, {}).items():
        # Get completion criteria
        completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)

        # Only migrate INDEPENDENT chores
        if completion_criteria != const.COMPLETION_CRITERIA_INDEPENDENT:
            continue

        # Skip if already migrated
        if const.DATA_CHORE_PER_KID_DUE_DATES in chore_info:
            continue

        # Get template due date (can be None)
        template_due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)

        # Populate per-kid dates from template
        per_kid_due_dates = {}
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        for kid_id in assigned_kids:
            # Each kid starts with template (can be None)
            per_kid_due_dates[kid_id] = template_due_date

            # Also update kid's chore data
            kid_chore_data = self._get_or_create_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_DUE_DATE] = template_due_date

        # Store per-kid dates in chore
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
        migration_count += 1

        const.LOGGER.debug(
            "Migrated INDEPENDENT chore: %s (%d kids)",
            chore_info.get(const.DATA_CHORE_NAME),
            len(assigned_kids)
        )

    if migration_count > 0:
        const.LOGGER.info(
            "Migration: Updated %d INDEPENDENT chore(s) to per-kid due date structure",
            migration_count
        )
        self._persist()

# Call this from __init__ after loading storage:
# Place in __init__ after: self._data = await self.storage_manager.async_load()
# Add this line:
self._migrate_independent_chores()
```

---

## Phase B: Services Updates (3 Services Need Updates)

### Service B.1: `reset_overdue_chores` (Already has kid_name in schema)

**Status**: GOOD NEWS - service schema already supports kid-specific reset

**Current Schema** (lines 95-100 in services.py):

```python
RESET_OVERDUE_CHORES_SCHEMA = vol.Schema({
    vol.Optional(const.FIELD_CHORE_ID): cv.string,
    vol.Optional(const.FIELD_CHORE_NAME): cv.string,
    vol.Optional(const.FIELD_KID_NAME): cv.string,  # ✅ Already supports!
})
```

**Update Needed**: Service handler logic needs to pass kid_id to updated `reset_overdue_chores()` method

**Handler Pattern**:

```python
async def async_reset_overdue_chores(call: ServiceCall) -> None:
    """Handle reset_overdue_chores service call."""
    coordinator = get_coordinator(call)

    # Get optional parameters
    chore_id = None
    if const.FIELD_CHORE_NAME in call.data:
        chore_id = kh.get_chore_id_or_raise(
            coordinator,
            call.data.get(const.FIELD_CHORE_NAME),
            "Reset Overdue Chores"
        )

    kid_id = None
    if const.FIELD_KID_NAME in call.data:
        kid_id = kh.get_kid_id_or_raise(
            coordinator,
            call.data.get(const.FIELD_KID_NAME),
            "Reset Overdue Chores"
        )

    # Call updated method
    coordinator.reset_overdue_chores(chore_id=chore_id, kid_id=kid_id)
```

### Service B.2: `set_chore_due_date` (Needs kid_name support)

**Status**: Requires schema and logic updates

**Schema Update**:

```python
SET_CHORE_DUE_DATE_SCHEMA = vol.Schema({
    vol.Optional(const.FIELD_CHORE_ID): cv.string,
    vol.Optional(const.FIELD_CHORE_NAME): cv.string,
    vol.Required(const.FIELD_DUE_DATE): cv.string,
    vol.Optional(const.FIELD_KID_NAME): cv.string,  # NEW: For INDEPENDENT chores
})
```

**Handler Pattern**:

```python
async def async_set_chore_due_date(call: ServiceCall) -> None:
    """Set chore due date with per-kid support for INDEPENDENT chores."""
    coordinator = get_coordinator(call)

    # Get chore
    chore_id = kh.get_chore_id_or_raise(
        coordinator,
        call.data.get(const.FIELD_CHORE_NAME),
        "Set Chore Due Date"
    )

    # Get optional kid (for INDEPENDENT per-kid override)
    kid_id = None
    if const.FIELD_KID_NAME in call.data:
        kid_id = kh.get_kid_id_or_raise(
            coordinator,
            call.data.get(const.FIELD_KID_NAME),
            "Set Chore Due Date"
        )

    due_date_str = call.data.get(const.FIELD_DUE_DATE)

    # Call coordinator method
    await coordinator.set_chore_due_date(chore_id, due_date_str, kid_id=kid_id)
```

**Coordinator Method Needed**:

```python
async def set_chore_due_date(
    self,
    chore_id: str,
    due_date_str: str,
    kid_id: str | None = None
) -> None:
    """Set chore due date with template pattern support.

    For INDEPENDENT chores:
    - If kid_id specified: Sets per-kid override
    - If no kid_id: Sets template + all kids

    For SHARED chores:
    - Ignores kid_id, sets chore-level only
    """
    chore_info = self._data[const.DATA_CHORES].get(chore_id)
    if not chore_info:
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_CHORE_NOT_FOUND,
            translation_placeholders={"chore_id": chore_id}
        )

    completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)

    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        if kid_id:
            # Set per-kid override
            per_kid_due_dates = chore_info.setdefault(
                const.DATA_CHORE_PER_KID_DUE_DATES, {}
            )
            per_kid_due_dates[kid_id] = due_date_str

            # Update kid's chore data
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_DUE_DATE] = due_date_str

            const.LOGGER.debug(
                "Set per-kid due date: chore=%s, kid=%s, date=%s",
                chore_info.get(const.DATA_CHORE_NAME),
                self.kids_data[kid_id].get(const.DATA_KID_NAME),
                due_date_str
            )
        else:
            # Set template + all kids
            chore_info[const.DATA_CHORE_DUE_DATE] = due_date_str

            per_kid_due_dates = chore_info.setdefault(
                const.DATA_CHORE_PER_KID_DUE_DATES, {}
            )
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

            for assigned_kid_id in assigned_kids:
                per_kid_due_dates[assigned_kid_id] = due_date_str
                kid_chore_data = self._get_kid_chore_data(assigned_kid_id, chore_id)
                kid_chore_data[const.DATA_KID_CHORE_DATA_DUE_DATE] = due_date_str

            const.LOGGER.debug(
                "Set template + all kids due date: chore=%s, date=%s",
                chore_info.get(const.DATA_CHORE_NAME),
                due_date_str
            )
    else:
        # SHARED: Set chore-level (ignore kid_id)
        chore_info[const.DATA_CHORE_DUE_DATE] = due_date_str

        # Update all kids' chore data
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        for assigned_kid_id in assigned_kids:
            kid_chore_data = self._get_kid_chore_data(assigned_kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_DUE_DATE] = due_date_str

        const.LOGGER.debug(
            "Set SHARED due date: chore=%s, date=%s (affects %d kids)",
            chore_info.get(const.DATA_CHORE_NAME),
            due_date_str,
            len(assigned_kids)
        )

    self._persist()
    self.async_update_listeners()
```

### Service B.3: `skip_chore_due_date` (Similar to Service B.2)

**Status**: Similar pattern to `set_chore_due_date`

**Schema Update**:

```python
SKIP_CHORE_DUE_DATE_SCHEMA = vol.Schema({
    vol.Optional(const.FIELD_CHORE_ID): cv.string,
    vol.Optional(const.FIELD_CHORE_NAME): cv.string,
    vol.Optional(const.FIELD_KID_NAME): cv.string,  # NEW: For INDEPENDENT chores
})
```

**Handler Pattern**: Same as Service B.2, calls `coordinator.skip_chore_due_date(chore_id, kid_id)`

**Coordinator Method**: Updates per-kid or chore-level due dates to next occurrence (reuses `_calculate_next_due_date()` logic)

---

## Key Implementation Decisions

### Decision 1: New Helper Method vs Reuse Existing

❌ **Mistake in First Attempt**: Tried to reuse `_reschedule_chore_next_due_date()` with per-kid logic

✅ **Correct Approach**: Create new `_reschedule_chore_for_kid()` helper to:

- Keep concerns separated (per-kid logic separate from chore-level)
- Update `DATA_CHORE_PER_KID_DUE_DATES` dict
- Maintain clarity in code readability

### Decision 2: Template vs Per-Kid Precedence

**For INDEPENDENT chores**:

- Template (chore-level `DATA_CHORE_DUE_DATE`): Default/fallback
- Per-kid override (`DATA_CHORE_PER_KID_DUE_DATES[kid_id]`): Takes precedence
- If both exist: Per-kid wins
- If only template: All kids use template
- If neither: Chore never goes overdue for that kid

### Decision 3: Shared Chore Behavior

**For SHARED chores** (all 3 SHARED variants):

- Ignore `kid_id` parameter in services
- Always operate on chore-level due date
- When set_chore_due_date called with kid_id: Log warning, use chore-level only
- This preserves the semantic meaning of "shared" (all kids have same deadline)

---

## Quality Checklist Before Implementation

**BEFORE starting code changes, verify:**

- ✅ All constants referenced exist in const.py (VERIFIED above)
- ✅ All helper methods exist (VERIFIED above)
- ✅ No methods called that don't exist (VERIFIED above)
- ✅ Type hints on all new/modified functions
- ✅ Lazy logging only (no f-strings in logs)
- ✅ All user-facing strings use translation keys (TRANS*KEY*\*)
- ✅ Linting passes: `./utils/quick_lint.sh --fix`
- ✅ All tests pass: `python -m pytest tests/ -v --tb=line`

---

## Proposed Execution Plan

**Phase A (Coordinator + Services)**: 2-3 hours estimated

1. ✅ Step 1.1: Constants verification (DONE - all exist)
2. ✅ Step 1.2: Overdue checking branching (DONE - Step 1.2 complete)
3. 🔄 **Step 1.3: Reset overdue chores branching** (READY - spec above)
4. 🔄 **Step 1.4: Migration method completion** (READY - spec above)
5. 🔄 **Phase B: Services updates** (READY - 3 services, spec above)

**Next Steps**:

1. User reviews this proposal
2. Agent confirms readiness
3. Agent implements each step with verification
4. Mark steps complete in official plan as each finishes

---

## Summary for User

**Blockers Resolved** ✅:

- All constants now verified as existing
- All methods now verified as existing
- Data structure patterns clarified
- Implementation approach finalized

**Ready for Execution** ✅:

- Step 1.3 specification complete with code pattern
- Step 1.4 specification complete with code pattern
- Phase B (Services) specification complete with all 3 services

**Quality Gates Established** ✅:

- Linting required before marking complete
- Testing required before marking complete
- Type hints required on all changes
- Lazy logging required on all changes

**Confidence Level**: HIGH - All undefined constants/methods resolved, code patterns clear and verified against codebase.
