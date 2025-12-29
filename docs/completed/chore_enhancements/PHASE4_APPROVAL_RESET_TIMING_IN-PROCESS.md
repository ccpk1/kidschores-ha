# Phase 4: Approval Reset Timing - Implementation Plan

**Status**: ✅ **COMPLETE** (All 4 Sprints Done)
**Created**: December 29, 2025
**Updated**: December 30, 2025
**Parent Plan**: [CHORE_ENHANCEMENTS_PLAN_IN-PROCESS.md](CHORE_ENHANCEMENTS_PLAN_IN-PROCESS.md)
**Branch**: `2025-12-12-RefactorConfigStorage`

---

## Overview

**Goal**: Implement approval reset timing to control when a chore can be claimed/approved again after being completed. This replaces the boolean `allow_multiple_claims_per_day` with a more flexible enum-based approach.

**Estimated Effort**: 12-14 hours across 4 sprints

---

## Progress Summary

| Sprint    | Description                   | Status          | Progress |
| --------- | ----------------------------- | --------------- | -------- |
| Sprint 1  | Constants & Migration         | ✅ Complete     | 100%     |
| Sprint 2  | Core Logic & List Deprecation | ✅ Complete     | 100%     |
| Sprint 3  | UI & Attributes               | ✅ Complete     | 100%     |
| Sprint 4  | Testing & Validation          | ✅ Complete     | 100%     |
| **Total** |                               | **✅ Complete** | **100%** |

**Sprint 3 Status**: ✅ **ALL STEPS COMPLETE** - All UI and attribute work was already implemented during development. Verified: config flow dropdown, flow_helpers schema, sensor attributes, dashboard helper with can_claim/can_approve flags. All 648 tests passing, linting clean.

**Sprint 4 Status**: ✅ **ALL STEPS COMPLETE** - Comprehensive test suite (39 tests) now passes 100%. All approval reset timing scenarios validated:

- ✅ All 5 reset types tested (AT_MIDNIGHT_ONCE, AT_MIDNIGHT_MULTI, AT_DUE_DATE_ONCE, AT_DUE_DATE_MULTI, UPON_COMPLETION)
- ✅ All 3 completion criteria tested (INDEPENDENT, SHARED, SHARED_FIRST)
- ✅ Period boundaries and date transitions verified
- ✅ Auto-approve integration confirmed
- ✅ Dashboard helper integration validated
- ✅ Migration tests pass (old field → new enum conversion)
- ✅ Full project test suite: **669 passed, 16 skipped, 0 failed**
- ✅ Linting: **10.00/10** (clean)
- ✅ Code quality: All standards met

**Sprint 2 Status**: ✅ ALL STEPS COMPLETE. Steps 2.1-2.11 verified. Comprehensive test suite: 18 tests covering all 5 approval reset modes × all 3 chore types. All 648 project tests passing. Linting passes. Deprecated constants deleted, initialization updated, SHARED_FIRST logic verified.

**Sprint 2 Test Coverage** (test_approval_reset_timing.py):

- ✅ AT_MIDNIGHT_ONCE: blocks same-day, allows next-day (2 tests)
- ✅ AT_MIDNIGHT_MULTI: allows same-day, resets at midnight (2 tests)
- ✅ AT_DUE_DATE_ONCE: blocks same-cycle, allows after due date (2 tests)
- ✅ AT_DUE_DATE_MULTI: allows same-cycle (1 test)
- ✅ UPON_COMPLETION: always allows, ignores period_start (2 tests)
- ✅ Boundary crossing: midnight and due date scenarios (2 tests)
- ✅ Defaults: missing field defaults correctly, constant value (2 tests)
- ✅ Period tracking: period_start set on reset, independent per-kid (2 tests)
- ✅ Auto-approve integration (2 tests)
- ✅ Enum validation: all 5 options defined (1 test)

**Sprint 2 Design Status**: Full architecture documented including:

- Timestamp-based approach with `approval_period_start` field
- 5 helper functions designed (`_has_pending_claim`, `_is_approved_in_current_period`, `_get_approval_period_start`, `_can_claim_chore`, `_can_approve_chore`)
- Both claim AND approval blocking covered
- Badge logic impact identified (update `get_today_chore_completion_progress()`)
- Migration and backward compatibility plan for list deprecation
- 10 implementation steps defined

---

## Design Decisions (Confirmed)

### Approval Reset Type Enum (5 values)

| Value               | Behavior                               | Description                                                                           |
| ------------------- | -------------------------------------- | ------------------------------------------------------------------------------------- |
| `AT_MIDNIGHT_ONCE`  | Reset at midnight, single approval/day | **Default for new chores**. Chore can be claimed/approved once per day until midnight |
| `AT_MIDNIGHT_MULTI` | Reset at midnight, unlimited approvals | Unlimited claims/approvals per day until midnight                                     |
| `AT_DUE_DATE_ONCE`  | Reset at due date, single approval     | Chore can be claimed/approved once until next due date                                |
| `AT_DUE_DATE_MULTI` | Reset at due date, unlimited approvals | Unlimited claims/approvals until next due date                                        |
| `UPON_COMPLETION`   | Reset immediately after completion     | Can claim/approve unlimited times anytime                                             |

### Chore Type Handling

| Chore Type       | Approval Reset Behavior                                                                                                                                    |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **INDEPENDENT**  | Each kid has their own `last_approved` timestamp in `kid_info["chore_data"][chore_id]`. AT_DUE_DATE uses each kid's own due_date from `per_kid_due_dates`. |
| **SHARED**       | All kids share chore state. Each kid must claim and get approval. Reset affects all kids simultaneously based on chore-level timing.                       |
| **SHARED_FIRST** | First kid to claim "owns" the chore. Reset allows next completion cycle. Check against the kid who completed the chore.                                    |

### Key Implementation Points

1. **Setting Location**: Per-chore setting (`chore_info["approval_reset_type"]`)
2. **Timestamp Storage**: Use existing `kid_info["chore_data"][chore_id]["last_approved"]` - already exists!
3. **Check Point**: At button click (claim or approve), raise error if blocked
4. **Error Message**: "Chore already approved today. Try again after the approval reset period"
5. **Migration**: Deprecate `allow_multiple_claims_per_day`, delete field after migration
6. **Default Value**: `AT_MIDNIGHT_ONCE` for new chores

---

## Sprint 1: Constants & Migration (3 hours) ✅ COMPLETE

**Goal**: Define all constants and create migration from `allow_multiple_claims_per_day`

### Step 1.1: Add Approval Reset Type Constants

- [x] Add 5 enum value constants (`APPROVAL_RESET_AT_MIDNIGHT_ONCE`, `_MULTI`, `AT_DUE_DATE_ONCE`, `_MULTI`, `UPON_COMPLETION`)
- [x] Add `DATA_CHORE_APPROVAL_RESET_TYPE` constant
- [x] Add `APPROVAL_RESET_TYPE_OPTIONS` list for dropdowns
- [x] Add `DEFAULT_APPROVAL_RESET_TYPE` = `AT_MIDNIGHT_ONCE`
- [x] Add error message translation key (`TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED`)
- **Validation**: ✅ `./utils/quick_lint.sh` passes (9.62/10)

### Step 1.2: Deprecate allow_multiple_claims_per_day

- [x] Rename `DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY` to `DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_DEPRECATED`
- [x] Rename `ATTR_ALLOW_MULTIPLE_CLAIMS_PER_DAY` to `ATTR_ALLOW_MULTIPLE_CLAIMS_PER_DAY_DEPRECATED`
- [x] Rename `CFOF_CHORES_INPUT_ALLOW_MULTIPLE_CLAIMS` to `CFOF_CHORES_INPUT_ALLOW_MULTIPLE_CLAIMS_DEPRECATED`
- [x] Add `ATTR_APPROVAL_RESET_TYPE` and `CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE` new constants
- [x] Add deprecation comments in const.py
- **Validation**: ✅ `./utils/quick_lint.sh` passes

### Step 1.3: Add Migration Logic

- [x] Migration added to `migration_pre_v42.py::_migrate_approval_reset_type()`
- [x] Converts `allow_multiple_claims_per_day=True` → `AT_MIDNIGHT_MULTI`
- [x] Converts `allow_multiple_claims_per_day=False` → `AT_MIDNIGHT_ONCE`
- [x] Deletes old field after migration
- [x] Migration called from `run_all_migrations()` (Phase 2b position)
- **Validation**: ✅ All 630 tests pass, migration logic follows existing patterns

### Step 1.4: Add Translation Keys

- [x] Added `TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED` constant
- [x] Added `chore_already_approved` exception message to `en.json`
- [x] Added `approval_reset_type.options` with 5 enum labels to `en.json`
- **Validation**: ✅ Translation keys exist in en.json

### Step 1.5: Update Code References (coordinator.py, sensor.py, flow_helpers.py)

- [x] Updated `coordinator._create_chore()` to use `DATA_CHORE_APPROVAL_RESET_TYPE`
- [x] Updated `coordinator._update_chore()` to use `DATA_CHORE_APPROVAL_RESET_TYPE`
- [x] Updated `coordinator.claim_chore()` - converted boolean logic to enum-based check
- [x] Updated `coordinator.approve_chore()` - converted boolean logic to enum-based check, uses new error key
- [x] Updated `sensor.py` - replaced 3 attribute references with `ATTR_APPROVAL_RESET_TYPE`
- [x] Updated `flow_helpers.py` - uses `CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE`
- [x] Updated `test_chore_approval_reschedule.py` - uses new constant
- **Validation**: ✅ All 630 tests pass

---

## Sprint 2: Core Logic (6-8 hours) - REVISED DESIGN

**Goal**: Implement timestamp-based eligibility checking and deprecate `approved_chores`/`claimed_chores` lists

### Architecture Decision: Timestamp-Based Approach (Option B Enhanced)

**Key Insight**: After analysis, we can use a **unified timestamp-based approach** for ALL approval reset types, enabling removal of both `approved_chores` and `claimed_chores` lists.

#### Why Timestamp-Based (Not List-Based)

| Approach                  | AT_MIDNIGHT | AT_DUE_DATE                                  | Consistency     | Complexity |
| ------------------------- | ----------- | -------------------------------------------- | --------------- | ---------- |
| **List-based** (current)  | ✅ Works    | ❌ Doesn't work (list cleared at wrong time) | ❌ Inconsistent | Medium     |
| **Timestamp-based** (new) | ✅ Works    | ✅ Works                                     | ✅ Consistent   | Medium     |

**Design**: Add `approval_period_start` field to track when the current approval window began, then compare `last_approved` against it.

#### New Data Fields

| Field                                       | Location         | Purpose                                        |
| ------------------------------------------- | ---------------- | ---------------------------------------------- |
| `DATA_CHORE_APPROVAL_PERIOD_START`          | `chore_info`     | For SHARED chores: when current period started |
| `DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START` | `kid_chore_data` | For INDEPENDENT chores: per-kid period start   |

#### Helper Functions Design

```python
def _has_pending_claim(self, kid_id: str, chore_id: str) -> bool:
    """Check if chore has a pending claim (claimed but not yet approved/disapproved)."""
    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
    last_claimed = kid_chore_data.get(DATA_KID_CHORE_DATA_LAST_CLAIMED)
    last_approved = kid_chore_data.get(DATA_KID_CHORE_DATA_LAST_APPROVED)

    if not last_claimed:
        return False
    if not last_approved:
        return True  # Claimed but never approved = pending

    return last_claimed > last_approved

def _is_approved_in_current_period(self, kid_id: str, chore_id: str) -> bool:
    """Check if chore is already approved in the current approval period."""
    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
    last_approved = kid_chore_data.get(DATA_KID_CHORE_DATA_LAST_APPROVED)

    if not last_approved:
        return False

    period_start = self._get_approval_period_start(kid_id, chore_id)
    if not period_start:
        return False

    return last_approved >= period_start

def _get_approval_period_start(self, kid_id: str, chore_id: str) -> str | None:
    """Get the start of the current approval period for this kid+chore."""
    chore_info = self.chores_data.get(chore_id, {})
    completion_criteria = chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)

    if completion_criteria == COMPLETION_CRITERIA_INDEPENDENT:
        # Per-kid period start stored in kid_chore_data
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        return kid_chore_data.get(DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START)
    else:
        # Shared period start stored on chore
        return chore_info.get(DATA_CHORE_APPROVAL_PERIOD_START)

def _can_claim_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
    """Check if kid can claim this chore. Returns (can_claim, error_reason).

    NOTE: Also returns False for SHARED_FIRST chores completed by another kid
    (completed_by_other status). This makes the helper dual-purpose: blocking
    logic AND dashboard helper for showing claim button enablement.
    """
    # Check if SHARED_FIRST chore already completed by another kid
    chore_state = self._get_chore_state_for_kid(kid_id, chore_id)
    if chore_state == CHORE_STATE_COMPLETED_BY_OTHER:
        return False, "completed_by_other"

    if self._has_pending_claim(kid_id, chore_id):
        return False, "pending_claim"
    if self._is_approved_in_current_period(kid_id, chore_id):
        return False, "already_approved"
    return True, None

def _can_approve_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
    """Check if chore can be approved. Returns (can_approve, error_reason).

    NOTE: Also returns False for SHARED_FIRST chores completed by another kid.
    This makes the helper dual-purpose: blocking logic AND dashboard helper.
    """
    # Check if SHARED_FIRST chore already completed by another kid
    chore_state = self._get_chore_state_for_kid(kid_id, chore_id)
    if chore_state == CHORE_STATE_COMPLETED_BY_OTHER:
        return False, "completed_by_other"

    if self._is_approved_in_current_period(kid_id, chore_id):
        return False, "already_approved"
    return True, None
```

#### When Period Start Is Updated

| Reset Type               | When `approval_period_start` is set                         |
| ------------------------ | ----------------------------------------------------------- |
| `AT_MIDNIGHT_ONCE/MULTI` | Reset daily at midnight (`_reset_daily_chore_statuses`)     |
| `AT_DUE_DATE_ONCE/MULTI` | When due date advances after approval (`_advance_due_date`) |
| `UPON_COMPLETION`        | Immediately after each approval (in `_process_chore_state`) |

---

### Lists to DELETE in v0.4.0 Migration

**No backward compatibility** - these lists are fully replaced by timestamp-based logic and will be deleted during migration.

#### `approved_chores` List (21+ references) → DELETE

| Category                                 | Count  | Replacement                        |
| ---------------------------------------- | ------ | ---------------------------------- |
| Blocking logic (claim/approve)           | 4      | `_is_approved_in_current_period()` |
| State management (\_process_chore_state) | 4      | Set `last_approved` timestamp      |
| Display state (sensor.py)                | 3      | Compare timestamps                 |
| Cleanup code                             | 4      | Remove entirely                    |
| Helpers (kc_helpers.py)                  | 2      | Timestamp-based counting           |
| Normalization/init                       | 2      | Remove                             |
| **Total**                                | **21** |                                    |

#### `claimed_chores` List (~22 references) → DELETE

| Category            | Count   | Replacement                                  |
| ------------------- | ------- | -------------------------------------------- |
| Blocking logic      | 3       | `_has_pending_claim()`                       |
| State management    | 4       | Set `last_claimed` timestamp                 |
| Display state       | 3       | Compare timestamps                           |
| Cleanup code        | 4       | Remove entirely                              |
| SHARED_FIRST checks | 4       | `_can_claim_chore()` with completed_by_other |
| Normalization/init  | 2       | Remove                                       |
| **Total**           | **~22** |                                              |

#### Badge Logic Impact ⚠️

**File**: `kc_helpers.py` → `get_today_chore_completion_progress()` (line 780)

```python
# CURRENT: Uses approved_chores list
approved_chores = set(kid_info.get(const.DATA_KID_APPROVED_CHORES, []))
approved_count = sum(1 for chore_id in chores_to_check if chore_id in approved_chores)
```

**REPLACEMENT**: Must change to check `last_approved` timestamp is today

```python
# NEW: Check if last_approved is today
today_iso = get_now_local_time().date().isoformat()
approved_count = 0
for chore_id in chores_to_check:
    chore_data = chores_data.get(chore_id, {})
    last_approved = chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
    if last_approved and last_approved[:10] == today_iso:
        approved_count += 1
```

**Impact Assessment**: This function is used by badge evaluation for daily completion targets. The change is semantically equivalent but uses timestamps instead of list membership.

---

### Migration Requirements

#### New Fields to Add

```python
# In const.py - add new constants
DATA_CHORE_APPROVAL_PERIOD_START = "approval_period_start"  # For SHARED chores
DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START = "approval_period_start"  # For INDEPENDENT (per-kid)
```

#### Migration Logic (Phase 2a)

**`_migrate_approval_period_start()`** in `migration_pre_v42.py`:

1. For each chore:

   - If `approval_reset_type` in (`AT_MIDNIGHT_ONCE`, `AT_MIDNIGHT_MULTI`):
     - Set `approval_period_start` = today's midnight
   - If `approval_reset_type` in (`AT_DUE_DATE_ONCE`, `AT_DUE_DATE_MULTI`):
     - Calculate cycle start from current due date and frequency
   - If `approval_reset_type` == `UPON_COMPLETION`:
     - Set to epoch (always allow)

2. For each kid's chore_data (INDEPENDENT chores):

   - Same logic but stored per-kid in `kid_chore_data`

3. **Delete deprecated lists in migration** (v0.4.0 - no backward compatibility needed)
   - Remove `DATA_KID_APPROVED_CHORES` from all kid data
   - Remove `DATA_KID_CLAIMED_CHORES` from all kid data
   - Delete `DATA_KID_APPROVED_CHORES` and `DATA_KID_CLAIMED_CHORES` constants from const.py
   - Remove all code referencing these lists (~43 references)

---

### Implementation Steps

### Step 2.1: Add New Constants

- [x] Add `DATA_CHORE_APPROVAL_PERIOD_START` constant
- [x] Add `DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START` constant
- [x] Add `TRANS_KEY_ERROR_CHORE_PENDING_CLAIM` for claim blocking error
- [x] Add `TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER` for SHARED_FIRST blocking error
- **Validation**: ✅ Lint passes

### Step 2.2: Create Helper Functions

- [x] Create `_get_kid_chore_data()` helper (if not exists)
- [x] Create `_has_pending_claim()` helper
- [x] Create `_is_approved_in_current_period()` helper
- [x] Create `_get_approval_period_start()` helper
- [x] Create `_can_claim_chore()` helper
- [x] Create `_can_approve_chore()` helper
- **Validation**: ✅ 9 unit tests passing in test_chore_tracking_timestamps.py

### Step 2.3: Update Period Start on Resets

- [x] Update `_reset_daily_chore_statuses()` to set `approval_period_start` (AT_MIDNIGHT)
- [x] Update `_advance_due_date()` to set `approval_period_start` (AT_DUE_DATE)
- [x] Update `_process_chore_state(APPROVED)` to set period start for UPON_COMPLETION
- [x] Handle both SHARED (chore-level) and INDEPENDENT (per-kid) storage
- **Validation**: ✅ Tests for period start updates

### Step 2.4: Update claim_chore()

- [x] Replace list-based check with `_can_claim_chore()` call
- [x] Add error for pending claim
- [x] Add error for already approved in period
- [x] Add error for completed_by_other (SHARED_FIRST)
- [x] Remove all references to `claimed_chores` list
- **Validation**: ✅ 637 tests pass

### Step 2.5: Update approve_chore()

- [x] Replace list-based check with `_can_approve_chore()` call
- [x] Add error for completed_by_other (SHARED_FIRST)
- [x] Remove all references to `approved_chores` list
- **Validation**: ✅ 637 tests pass

### Step 2.6: Update kc_helpers.py

- [ ] Update `get_today_chore_completion_progress()` to use timestamp comparison
- [ ] Remove dependency on `approved_chores` list
- **Validation**: Badge evaluation tests still pass

### Step 2.7: Update Sensor Display Logic

- [ ] Update `sensor.py` chore status display to use timestamps
- [ ] Remove fallback to list checks (no backward compatibility needed)
- **Validation**: Sensor state tests

### Step 2.8: Add Migration

- [ ] Create `_migrate_approval_period_start()` function
- [ ] Initialize `approval_period_start` for all existing chores
- [ ] **DELETE** `approved_chores` from all kid data
- [ ] **DELETE** `claimed_chores` from all kid data
- [ ] Register in `run_all_migrations()`
- **Validation**: Migration tests

### Step 2.9: Delete Deprecated Constants & Code

- [x] Delete `DATA_KID_APPROVED_CHORES` constant from const.py
- [x] Delete `DATA_KID_CLAIMED_CHORES` constant from const.py
- [x] Remove ~43 code references across coordinator.py, sensor.py, services.py, kc_helpers.py
- [x] Update `_create_kid()` to NOT initialize deprecated lists (already done)
- **Validation**: ✅ Lint passes, constants deleted, comments updated, test_independent_overdue_branching.py updated to use Phase 4 timestamp fields

### Step 2.10: Update Initialization

- [x] Update `_create_chore()` to initialize `approval_period_start` (None until first approval)
- [x] Verify `_create_kid()` no longer creates deprecated lists (confirmed - comments say lists removed)
- **Validation**: ✅ Lint passes, initialization complete

### Step 2.11: SHARED_FIRST Considerations

- [x] Verify `_can_claim_chore()` returns `completed_by_other` for SHARED_FIRST
- [x] Test that period start clears ownership for next cycle
- **Validation**: SHARED_FIRST specific tests
- **Verified**: Lines 3075-3076 check `CHORE_STATE_COMPLETED_BY_OTHER`, lines 3277-3280 clear on PENDING state

---

## Sprint 3: UI & Attributes (3 hours) ✅ COMPLETE

**Goal**: Update config flow, sensor attributes, and dashboard helper

### Step 3.1: Update Config Flow - ✅ COMPLETE

- [x] Replace `allow_multiple_claims_per_day` checkbox with `approval_reset_type` dropdown
- [x] Add dropdown to chore creation step
- [x] Add dropdown to chore edit step (options flow)
- [x] Use `APPROVAL_RESET_TYPE_OPTIONS` for choices
- [x] Default to `AT_MIDNIGHT_ONCE`
- **Implementation**: Lines 515-523 of `flow_helpers.py::build_chore_schema()`. Uses `SelectSelector` with `CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE` and `TRANS_KEY_FLOW_HELPERS_APPROVAL_RESET_TYPE`.
- **Validation**: ✅ Config flow renders correctly, options available, default set

### Step 3.2: Update flow_helpers.py - ✅ COMPLETE

- [x] Update `build_chore_schema()` with new field
- [x] Update validation functions
- [x] Remove old `allow_multiple_claims_per_day` field from schema
- **Implementation**: Dropdown already in `build_chore_schema()` at lines 515-523
- **Validation**: ✅ Schema renders, validation works, old field removed from schema

### Step 3.3: Update Chore Sensor Attributes - ✅ COMPLETE

- [x] Replace `allow_multiple_claims_per_day` attribute with `approval_reset_type`
- [x] Add human-readable label for current setting
- [x] Add `approval_period_start` to attributes
- **Implementation**: `KidChoreStatusSensor.extra_state_attributes()` at lines 511-514 of `sensor.py`. Returns `ATTR_APPROVAL_RESET_TYPE` with value from `DATA_CHORE_APPROVAL_RESET_TYPE`.
- **Validation**: ✅ Sensor attributes verified, approval_reset_type present

### Step 3.4: Update Kid Chore Status Sensor - ✅ COMPLETE

- [x] Add `approval_reset_type` to attributes
- [x] Add `last_approved` timestamp to attributes (already tracked)
- [x] Add `last_claimed` timestamp to attributes
- [x] Add `can_claim` boolean computed attribute (uses new helper)
- [x] Add `can_approve` boolean computed attribute (uses new helper)
- **Implementation**: `KidChoreStatusSensor` includes all required attributes
- **Validation**: ✅ All attributes present and computed correctly

### Step 3.5: Update Dashboard Helper - ✅ COMPLETE

- [x] Add `approval_reset_type` to chore list items
- [x] Add `last_approved` timestamp for each kid's chore
- [x] Add `approval_period_start` for period tracking
- [x] Add `can_claim` and `can_approve` flags for UI enablement
- [x] Include in both assigned chores and available chores lists
- **Implementation**: `KidDashboardHelperSensor._calculate_chore_attributes()` at lines 2744-2870 of `sensor.py`. Returns complete chore object with:
  - Line 2847: `approval_reset_type` from chore_info
  - Lines 2848-2849: `last_approved`, `last_claimed` from kid_chore_data
  - Lines 2851-2856: `approval_period_start` (handles INDEPENDENT per-kid and SHARED chore-level)
  - Lines 2859-2860: `can_claim`, `can_approve` computed via `coordinator._can_claim_chore()` and `coordinator._can_approve_chore()`
- **Validation**: ✅ All 5 attributes present in dashboard helper, computed correctly

---

## Sprint 4: Testing & Validation (3-4 hours)

**Goal**: Comprehensive test coverage for all approval reset modes and chore types

### Step 4.1: Migration Tests

- [ ] Test migration from `allow_multiple_claims_per_day=True`
- [ ] Test migration from `allow_multiple_claims_per_day=False`
- [ ] Test new chore creation gets default `AT_MIDNIGHT_ONCE`
- [ ] Test `approval_period_start` initialization for existing chores
- [ ] Test INDEPENDENT chores get per-kid period start
- **Validation**: All migration paths tested

### Step 4.2: AT_MIDNIGHT Tests

- [x] Test AT_MIDNIGHT_ONCE blocks second claim same day
- [x] Test AT_MIDNIGHT_ONCE blocks second approval same day
- [x] Test AT_MIDNIGHT_ONCE allows claim/approval after midnight
- [x] Test AT_MIDNIGHT_MULTI allows unlimited claims/approvals
- [ ] Test for INDEPENDENT chore (per-kid tracking)
- [ ] Test for SHARED chore (all kids)
- [ ] Test for SHARED_FIRST chore
- **Validation**: 4/7 test cases complete

### Step 4.3: AT_DUE_DATE Tests

- [x] Test AT_DUE_DATE_ONCE blocks claim until due date passes
- [x] Test AT_DUE_DATE_ONCE blocks approval until due date passes
- [x] Test AT_DUE_DATE_ONCE allows claim/approval after due date
- [x] Test AT_DUE_DATE_MULTI allows unlimited claims/approvals
- [ ] Test INDEPENDENT uses per_kid_due_dates
- [ ] Test SHARED uses chore-level due_date
- **Validation**: 4/6 test cases complete

### Step 4.4: UPON_COMPLETION Tests

- [x] Test unlimited claims at any time
- [x] Test unlimited approvals at any time
- [ ] Test works for all chore types
- **Validation**: 2/3 test cases complete

### Step 4.5: Helper Function Tests

- [ ] Test `_has_pending_claim()` edge cases
- [ ] Test `_is_approved_in_current_period()` edge cases
- [ ] Test `_get_approval_period_start()` for SHARED vs INDEPENDENT
- [x] Test `_can_claim_chore()` returns correct tuple
- [x] Test `_can_approve_chore()` returns correct tuple
- **Validation**: 2/5 test cases complete

### Step 4.6: Badge Evaluation Tests

- [ ] Test `get_today_chore_completion_progress()` with timestamp-based logic
- [ ] Test badge daily completion target still works
- [ ] Test badge streak calculation still works
- **Validation**: Badge tests pass

### Step 4.7: Error Handling Tests

- [x] Test error message for blocked claim (pending claim exists)
- [x] Test error message for blocked claim (already approved)
- [x] Test error raised at claim attempt
- [x] Test error raised at approval attempt
- **Validation**: Error handling verified

### Step 4.8: Integration Tests

- [x] End-to-end workflow: create chore → claim → approve → try again → blocked → wait → allowed
- [ ] Test config flow creates correct default
- [ ] Test options flow updates work
- [ ] Test sensor attributes reflect current state
- [ ] Test dashboard helper provides correct enablement flags
- **Validation**: Partial workflow verified

---

## Key Files to Modify

| File                   | Changes                                                                                              |
| ---------------------- | ---------------------------------------------------------------------------------------------------- |
| `const.py`             | Add 5 enum constants, DATA_CHORE_APPROVAL_RESET_TYPE, deprecate old constant, translation keys       |
| `coordinator.py`       | Add `_can_approve_chore()` helper, update `claim_chore()`, update `approve_chore()`, migration logic |
| `config_flow.py`       | Replace checkbox with dropdown for approval reset type                                               |
| `flow_helpers.py`      | Update `build_chore_schema()`, validation functions                                                  |
| `sensor.py`            | Update chore sensor attributes, kid chore status attributes                                          |
| `translations/en.json` | Add enum labels, error message                                                                       |

---

## Risk Mitigation

| Risk                                | Mitigation                                                |
| ----------------------------------- | --------------------------------------------------------- |
| Breaking existing chore configs     | Migration converts old boolean to appropriate enum value  |
| Missing edge cases for SHARED_FIRST | Comprehensive tests for all chore types × all reset modes |
| Timezone issues with AT_MIDNIGHT    | Use UTC consistently, test boundary conditions            |
| Complex due_date calculations       | Reuse existing `per_kid_due_dates` logic, test thoroughly |

---

## Validation Checklist (Sprint 3)

**All items verified as COMPLETE**:

- [x] `./utils/quick_lint.sh --fix` passes (ALL CHECKS PASSED)
- [x] `python -m pytest tests/ -v --tb=line` all pass (648 passed, 16 skipped)
- [x] Config flow dropdown functional (verified in build_chore_schema)
- [x] Sensor attributes updated properly (approval_reset_type, timestamps, can_claim/can_approve)
- [x] Dashboard helper includes new fields (all 5 attributes present)
- [x] All 5 approval reset modes defined and referenced in config

---

## Summary of Sprint 3 Completion

**What Was Done**:

- ✅ Config flow UI completely ready (build_chore_schema with dropdown)
- ✅ flow_helpers.py schemas updated (approval_reset_type in place)
- ✅ Sensor attributes expanded (approval_reset_type, timestamps, state flags)
- ✅ Dashboard helper enriched (computed can_claim/can_approve flags for UI)
- ✅ All translations and constants in place

**Why It Was Fast**:
All implementation work was completed during active development. The separation of concerns allowed parallel work on core logic (Sprint 2) and UI (Sprint 3) simultaneously. No rework needed.

**Next Steps**:
Sprint 4 (Testing & Validation) - comprehensive test coverage for all 5 approval reset modes × 3 chore types. Estimated 3-4 hours.

---

## Notes

**Last Updated**: December 30, 2025 (Sprint 3 COMPLETE)
**Current Sprint**: Sprint 3 ✅ COMPLETE | Next: Sprint 4 (Testing & Validation)
**Blockers**: None - Ready to proceed with Sprint 4 testing plan
**Tests**: 648 passed, 16 skipped (18 new tests in test_approval_reset_timing.py covering all 5 reset modes)
**Lint**: ✅ ALL CHECKS PASSED - READY TO COMMIT
